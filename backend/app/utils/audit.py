"""Audit logging helper."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details or {},
        )
    )
