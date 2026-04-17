from __future__ import annotations

from pydantic import BaseModel, EmailStr

from app.models.user import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role
