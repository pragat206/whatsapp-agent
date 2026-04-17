"""CSV/Excel parsing helpers (no object storage, files live only in memory)."""
from __future__ import annotations

import io
from typing import Any

import pandas as pd


SUGGEST_SYNONYMS = {
    "name": {"name", "full_name", "customer", "contact_name"},
    "phone": {"phone", "mobile", "phone_number", "whatsapp", "number", "contact"},
    "city": {"city", "town"},
    "state": {"state", "region"},
    "property_type": {"property", "property_type", "building_type"},
    "monthly_bill": {"bill", "monthly_bill", "electricity_bill"},
    "roof_type": {"roof", "roof_type"},
    "notes": {"notes", "comments", "remarks"},
    "source": {"source", "lead_source", "channel"},
}


def _read(content: bytes, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    buf = io.BytesIO(content)
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(buf, dtype=str, keep_default_na=False)
    return pd.read_csv(buf, dtype=str, keep_default_na=False)


def parse(content: bytes, filename: str) -> pd.DataFrame:
    df = _read(content, filename)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def suggest_mapping(columns: list[str]) -> dict[str, str]:
    """Return csv_column -> internal_field best guesses."""
    mapping: dict[str, str] = {}
    lower_cols = {c: c.strip().lower().replace(" ", "_") for c in columns}
    for col, norm in lower_cols.items():
        for internal, syns in SUGGEST_SYNONYMS.items():
            if norm in syns:
                mapping[col] = internal
                break
    return mapping


def iter_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.to_dict(orient="records")
