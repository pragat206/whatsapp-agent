"""FastAPI dependencies: DB session, current user, RBAC guards."""
from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import Role, User


def db_dep(db: Session = Depends(get_db)) -> Session:
    return db


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(db_dep),
) -> User:
    token = _extract_token(authorization)
    try:
        payload = decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token subject")
    user = db.get(User, uuid.UUID(sub))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user inactive")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = set(roles)

    def _checker(user: User = Depends(current_user)) -> User:
        if user.role not in allowed and user.role != Role.admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient permissions")
        return user

    return _checker
