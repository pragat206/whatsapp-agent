"""CSV/Excel upload parsing + mapping + dedupe for campaigns."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignUpload,
)
from app.models.contact import Contact
from app.utils import csv_parser
from app.utils.phone import safe_normalize


PREVIEW_LIMIT = 20


def ingest_upload(
    db: Session,
    *,
    campaign: Campaign,
    filename: str,
    content: bytes,
) -> CampaignUpload:
    df = csv_parser.parse(content, filename)
    columns = list(df.columns)
    records = csv_parser.iter_rows(df)
    suggested = csv_parser.suggest_mapping(columns)

    # No object storage: persist the full parsed rows as JSON on the upload row.
    # This keeps the pipeline self-contained. For very large files (>50k rows)
    # this can be swapped for streaming inserts without changing callers.
    upload = CampaignUpload(
        campaign_id=campaign.id,
        filename=filename,
        row_count=len(records),
        mapping={"_suggested": suggested, "_columns": columns, "_all_rows": records},
        preview=records[:PREVIEW_LIMIT],
    )
    db.add(upload)
    db.flush()
    return upload


def confirm_mapping(
    db: Session,
    *,
    campaign: Campaign,
    upload: CampaignUpload,
    mapping: dict[str, str],           # csv_col -> internal_field
    template_param_columns: list[str], # csv cols used for templateParams (ordered)
    dedupe: bool = True,
) -> CampaignUpload:
    """Materialize CampaignRecipients from the uploaded rows."""
    all_rows: list[dict[str, Any]] = (
        (upload.mapping or {}).get("_all_rows") or upload.preview or []
    )

    valid = 0
    invalid = 0
    duplicates = 0
    phone_col = _find_phone_column(mapping)
    if phone_col is None:
        raise ValueError("Mapping must include a column mapped to 'phone'.")

    seen: set[str] = set()

    for row in all_rows:
        raw_phone = row.get(phone_col) or ""
        phone_e164 = safe_normalize(raw_phone)
        if not phone_e164:
            invalid += 1
            continue
        if dedupe and phone_e164 in seen:
            duplicates += 1
            continue
        seen.add(phone_e164)

        contact = _upsert_contact(db, phone_e164=phone_e164, mapping=mapping, row=row)

        params = [str(row.get(col, "") or "") for col in template_param_columns]

        attrs = {
            k: row.get(k)
            for k in row.keys()
            if mapping.get(k) not in {"phone"} and row.get(k)
        }

        db.add(
            CampaignRecipient(
                campaign_id=campaign.id,
                contact_id=contact.id,
                phone_e164=phone_e164,
                template_params=params,
                attributes=attrs,
                status=CampaignRecipientStatus.pending,
            )
        )
        valid += 1

    cleaned = {k: v for k, v in (upload.mapping or {}).items() if k != "_all_rows"}
    upload.mapping = {
        **cleaned,
        "mapping": mapping,
        "template_param_columns": template_param_columns,
        "dedupe": dedupe,
    }
    upload.valid_count = valid
    upload.invalid_count = invalid
    upload.duplicate_count = duplicates
    db.flush()
    return upload


def _find_phone_column(mapping: dict[str, str]) -> str | None:
    for col, internal in mapping.items():
        if internal == "phone":
            return col
    return None


def _upsert_contact(
    db: Session, *, phone_e164: str, mapping: dict[str, str], row: dict[str, Any]
) -> Contact:
    contact = db.scalar(select(Contact).where(Contact.phone_e164 == phone_e164))
    if contact is None:
        contact = Contact(phone_e164=phone_e164)
        db.add(contact)
        db.flush()
    for col, internal in mapping.items():
        val = row.get(col)
        if not val:
            continue
        if internal == "name" and not contact.name:
            contact.name = str(val)[:200]
        elif internal == "city":
            contact.city = str(val)[:120]
        elif internal == "state":
            contact.state = str(val)[:120]
        elif internal == "property_type":
            contact.property_type = str(val)[:60]
        elif internal == "monthly_bill":
            contact.monthly_bill = str(val)[:60]
        elif internal == "roof_type":
            contact.roof_type = str(val)[:60]
        elif internal == "source":
            contact.source = str(val)[:120]
        elif internal == "notes":
            contact.notes = str(val)[:1000]
    return contact
