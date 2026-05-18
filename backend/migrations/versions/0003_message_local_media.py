"""Add local_media_path to messages.

Revision ID: 0003_message_local_media
Revises: 0002_lead_tracking
Create Date: 2026-05-18

Stores the path (relative to USER_UPLOADS_DIR) where the inbound webhook
saved a customer-shared file (electricity bills, Aadhaar photos, voice
notes). The original CDN URL stays in ``media_url``; this column lets
the inbox UI render the local copy via an authenticated endpoint even
after the provider URL expires.

Additive only — nullable column, no backfill needed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_message_local_media"
down_revision = "0002_lead_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("local_media_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "local_media_path")
