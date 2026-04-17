"""Settings API (runtime-configurable business rules)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, db_dep, require_roles
from app.models.settings import Setting
from app.models.user import Role, User

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def list_settings(
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> dict:
    rows = db.execute(select(Setting)).scalars().all()
    return {r.key: r.value for r in rows}


@router.put("/{key}")
def upsert_setting(
    key: str,
    body: dict,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> dict:
    setting = db.scalar(select(Setting).where(Setting.key == key))
    if setting is None:
        setting = Setting(key=key, value=body.get("value", {}), description=body.get("description"))
        db.add(setting)
    else:
        setting.value = body.get("value", setting.value)
        if "description" in body:
            setting.description = body["description"]
    db.commit()
    return {"ok": True, "key": key, "value": setting.value}
