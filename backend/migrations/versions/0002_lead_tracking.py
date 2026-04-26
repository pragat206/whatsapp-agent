"""Add lead-tracking columns to contacts.

Revision ID: 0002_lead_tracking
Revises: 0001_initial
Create Date: 2026-04-22

Additive only — no data backfill, no breaking changes. All new columns are
nullable (or default to empty JSON) so existing rows remain valid and current
messaging flows continue working without modification.

Powers two features:
  * AI runner's per-contact memory block (so the assistant stops re-asking
    for facts the user has already shared in earlier turns).
  * The Leads tab in the dashboard.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0002_lead_tracking"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("lead_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("lead_next_action", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("lead_next_action_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("contacts", sa.Column("lead_summary", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("lead_score", sa.Integer(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column(
            "lead_extracted_attributes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        "contacts",
        sa.Column("lead_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_contacts_lead_status", "contacts", ["lead_status"])
    op.create_index("ix_contacts_lead_updated_at", "contacts", ["lead_updated_at"])


def downgrade() -> None:
    op.drop_index("ix_contacts_lead_updated_at", table_name="contacts")
    op.drop_index("ix_contacts_lead_status", table_name="contacts")
    op.drop_column("contacts", "lead_updated_at")
    op.drop_column("contacts", "lead_extracted_attributes")
    op.drop_column("contacts", "lead_score")
    op.drop_column("contacts", "lead_summary")
    op.drop_column("contacts", "lead_next_action_at")
    op.drop_column("contacts", "lead_next_action")
    op.drop_column("contacts", "lead_status")
