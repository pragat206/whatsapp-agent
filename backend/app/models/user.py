from __future__ import annotations

import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class Role(str, enum.Enum):
    admin = "admin"
    campaign_manager = "campaign_manager"
    support_agent = "support_agent"
    viewer = "viewer"


class User(UUIDPk, Timestamped, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), nullable=False, default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
