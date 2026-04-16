"""Password hashing + JWT utilities for dashboard auth."""
from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGO = "HS256"


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=s.jwt_access_ttl_min)).timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, s.app_secret_key, algorithm=_ALGO)


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    return jwt.decode(token, s.app_secret_key, algorithms=[_ALGO])
