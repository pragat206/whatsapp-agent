"""Send orchestration for a campaign.

Designed to run inside the RQ worker. Iterates recipients in small batches,
calls AiSensy, writes per-recipient status, respects pause/cancel state, and
resumes safely on restart.
"""
from __future__ import annotations

import datetime as dt
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.integrations.aisensy import CampaignSendPayload
from app.integrations.aisensy.client import get_aisensy_client
from app.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientStatus,
    CampaignStatus,
)
from app.utils.retries import ProviderPermanentError, ProviderTransientError

logger = get_logger("campaign.sender")

BATCH_SIZE = 50
INTER_MESSAGE_SLEEP = 0.05  # tiny pacing to avoid AiSensy rate limits


def send_campaign(campaign_id: uuid.UUID) -> None:
    db: Session = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return
        if campaign.status not in (CampaignStatus.scheduled, CampaignStatus.sending):
            campaign.status = CampaignStatus.sending
        campaign.started_at = campaign.started_at or dt.datetime.now(dt.timezone.utc)
        db.commit()

        while True:
            db.refresh(campaign)
            if campaign.status in (CampaignStatus.paused, CampaignStatus.cancelled):
                logger.info("campaign_halted", campaign_id=str(campaign.id), status=campaign.status.value)
                return

            batch = db.execute(
                select(CampaignRecipient)
                .where(CampaignRecipient.campaign_id == campaign.id)
                .where(CampaignRecipient.status == CampaignRecipientStatus.pending)
                .limit(BATCH_SIZE)
            ).scalars().all()

            if not batch:
                break

            for recipient in batch:
                _send_one(db, campaign=campaign, recipient=recipient)
                db.commit()
                time.sleep(INTER_MESSAGE_SLEEP)

        remaining = db.execute(
            select(CampaignRecipient).where(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.status == CampaignRecipientStatus.pending,
            )
        ).first()
        if not remaining:
            stats = db.execute(
                select(CampaignRecipient.status).where(
                    CampaignRecipient.campaign_id == campaign.id
                )
            ).all()
            counts: dict[CampaignRecipientStatus, int] = {}
            for (status_val,) in stats:
                counts[status_val] = counts.get(status_val, 0) + 1
            sent_like = (
                counts.get(CampaignRecipientStatus.sent, 0)
                + counts.get(CampaignRecipientStatus.delivered, 0)
                + counts.get(CampaignRecipientStatus.read, 0)
                + counts.get(CampaignRecipientStatus.replied, 0)
            )
            failed_n = counts.get(CampaignRecipientStatus.failed, 0)
            # If everything failed, reflect that at campaign level.
            campaign.status = (
                CampaignStatus.failed if sent_like == 0 and failed_n > 0 else CampaignStatus.completed
            )
            campaign.completed_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
    finally:
        db.close()


def _send_one(db: Session, *, campaign: Campaign, recipient: CampaignRecipient) -> None:
    recipient.status = CampaignRecipientStatus.sending
    recipient.attempts = (recipient.attempts or 0) + 1
    db.flush()

    payload = CampaignSendPayload(
        campaign_name=campaign.template_name,  # AiSensy campaign name = template name by convention
        destination=recipient.phone_e164,
        user_name=_display_name(recipient),
        source=campaign.source,
        template_params=list(recipient.template_params or []),
        tags=list(campaign.tags or []),
        attributes=dict(recipient.attributes or {}),
    )

    try:
        resp = get_aisensy_client().send_campaign(payload)
    except ProviderPermanentError as exc:
        recipient.status = CampaignRecipientStatus.failed
        recipient.error = str(exc)[:1000]
        db.add(
            CampaignRecipientEvent(
                recipient_id=recipient.id,
                kind="send_failed_permanent",
                raw={"error": str(exc)},
            )
        )
        logger.warning("campaign_send_permanent_fail", recipient=str(recipient.id), error=str(exc))
        return
    except ProviderTransientError as exc:
        recipient.status = CampaignRecipientStatus.pending  # leave for retry
        recipient.error = str(exc)[:1000]
        db.add(
            CampaignRecipientEvent(
                recipient_id=recipient.id,
                kind="send_transient_fail",
                raw={"error": str(exc)},
            )
        )
        logger.warning("campaign_send_transient_fail", recipient=str(recipient.id), error=str(exc))
        return

    # AiSensy's campaign V2 endpoint typically returns
    # `{"success": true, "message": "Success"}` — no messageId. An inline error
    # signal (e.g. `success: false`, `status: "error"`, non-empty `error`) is the
    # only reliable way to treat a 2xx as a failure. Everything else = accepted
    # by AiSensy; the status webhook later links the real provider message id.
    error_hint = _response_error_hint(resp)
    if error_hint is not None:
        recipient.status = CampaignRecipientStatus.failed
        recipient.error = error_hint[:1000]
        db.add(
            CampaignRecipientEvent(
                recipient_id=recipient.id,
                kind="send_failed_provider_error",
                raw=resp if isinstance(resp, dict) else {"resp": str(resp)},
            )
        )
        logger.warning(
            "campaign_send_provider_error",
            recipient=str(recipient.id),
            response=str(resp)[:500],
        )
        return

    provider_id = _extract_provider_id(resp)
    recipient.status = CampaignRecipientStatus.sent
    recipient.sent_at = dt.datetime.now(dt.timezone.utc)
    recipient.provider_message_id = provider_id  # may be None on campaign API
    db.add(
        CampaignRecipientEvent(
            recipient_id=recipient.id,
            kind="sent",
            raw=resp if isinstance(resp, dict) else {"resp": str(resp)},
        )
    )


def _display_name(recipient: CampaignRecipient) -> str:
    attrs = recipient.attributes or {}
    for k in ("name", "full_name", "customer_name"):
        if attrs.get(k):
            return str(attrs[k])[:100]
    return ""


def _extract_provider_id(resp) -> str | None:
    if not isinstance(resp, dict):
        return None
    for key in ("messageId", "id", "message_id", "providerMessageId"):
        if resp.get(key):
            return str(resp[key])
    data = resp.get("data") or {}
    for key in ("messageId", "id"):
        if data.get(key):
            return str(data[key])
    return None


def _response_error_hint(resp) -> str | None:
    """Return a human-readable error hint if `resp` explicitly signals failure.

    AiSensy returns 2xx on success and often includes a `"message"` field set
    to "Success" — so we must not treat the presence of `message` as an error.
    Only explicit negative signals count:
      * `success: false`  → error
      * `status: "error" | "failed" | "failure"`
      * `error` / `errors` non-empty
      * `code` that is non-2xx numeric
    """
    if not isinstance(resp, dict):
        return None

    success_flag = resp.get("success")
    if success_flag is False:
        return str(resp.get("message") or resp.get("error") or "provider returned success=false")[:500]

    status_val = str(resp.get("status") or "").lower()
    if status_val in {"error", "failed", "failure"}:
        return str(resp.get("message") or resp.get("error") or f"provider status={status_val}")[:500]

    err = resp.get("error") or resp.get("errors")
    if err:
        if isinstance(err, (list, tuple)):
            return ", ".join(str(x) for x in err)[:500]
        return str(err)[:500]

    code = resp.get("code")
    if isinstance(code, int) and code >= 400:
        return f"provider code={code} message={resp.get('message') or ''}"[:500]

    return None
