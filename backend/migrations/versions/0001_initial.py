"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # create_type=False prevents SQLAlchemy from auto-creating the type a
    # second time when the Enum is attached to a table column below.
    role = sa.Enum(
        "admin", "campaign_manager", "support_agent", "viewer",
        name="role", create_type=False,
    )
    conv_state = sa.Enum(
        "AI_ACTIVE", "AI_PAUSED", "HUMAN_ACTIVE", "CLOSED",
        name="conversation_state", create_type=False,
    )
    msg_direction = sa.Enum(
        "inbound", "outbound", name="message_direction", create_type=False,
    )
    msg_status = sa.Enum(
        "queued", "sent", "delivered", "read", "failed", "received",
        name="message_status", create_type=False,
    )
    camp_status = sa.Enum(
        "draft", "mapped", "scheduled", "sending", "paused", "completed", "cancelled", "failed",
        name="campaign_status", create_type=False,
    )
    rcp_status = sa.Enum(
        "pending", "sending", "sent", "delivered", "read", "replied", "failed", "skipped", "invalid",
        name="campaign_recipient_status", create_type=False,
    )

    # Create each enum type explicitly (checkfirst skips if it already exists).
    for enum in (role, conv_state, msg_direction, msg_status, camp_status, rcp_status):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", role, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone_e164", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("city", sa.String(120)),
        sa.Column("state", sa.String(120)),
        sa.Column("property_type", sa.String(60)),
        sa.Column("monthly_bill", sa.String(60)),
        sa.Column("roof_type", sa.String(60)),
        sa.Column("source", sa.String(120)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("attributes", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("unsubscribed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contacts_phone_e164", "contacts", ["phone_e164"])

    op.create_table(
        "agent_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), unique=True, nullable=False),
        sa.Column("purpose", sa.Text, nullable=False, server_default=""),
        sa.Column("tone", sa.String(120), nullable=False, server_default="friendly, professional"),
        sa.Column("response_style", sa.String(120), nullable=False, server_default="concise"),
        sa.Column("languages_supported", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("greeting_style", sa.String(300), nullable=False, server_default=""),
        sa.Column("escalation_keywords", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("forbidden_claims", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("allowed_domains", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("fallback_message", sa.Text, nullable=False, server_default=""),
        sa.Column("human_handoff_message", sa.Text, nullable=False, server_default=""),
        sa.Column("business_hours_behavior", sa.String(40), nullable=False, server_default="respond_always"),
        sa.Column("instructions", sa.Text, nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), unique=True, nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("published", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("published", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("meta", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_kb_id", "knowledge_documents", ["kb_id"])
    op.create_index("ix_knowledge_documents_category", "knowledge_documents", ["category"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False, server_default="0"),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.Column("category", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_kb_id", "knowledge_chunks", ["kb_id"])
    op.create_index("ix_knowledge_chunks_category", "knowledge_chunks", ["category"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "faq_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("published", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_faq_entries_kb_id", "faq_entries", ["kb_id"])
    op.create_index("ix_faq_entries_category", "faq_entries", ["category"])

    op.create_table(
        "agent_profile_kb_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_profiles.id"), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_profile_id", "kb_id", name="uq_agent_kb"),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("objective", sa.String(500)),
        sa.Column("status", camp_status, nullable=False, server_default="draft"),
        sa.Column("agent_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_profiles.id")),
        sa.Column("template_name", sa.String(120), nullable=False),
        sa.Column("template_params_schema", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("source", sa.String(120)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaigns_name", "campaigns", ["name"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    op.create_table(
        "campaign_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("invalid_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mapping", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("preview", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaign_uploads_campaign_id", "campaign_uploads", ["campaign_id"])

    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("phone_e164", sa.String(32), nullable=False),
        sa.Column("template_params", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("attributes", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("status", rcp_status, nullable=False, server_default="pending"),
        sa.Column("provider_message_id", sa.String(120)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])
    op.create_index("ix_campaign_recipients_contact_id", "campaign_recipients", ["contact_id"])
    op.create_index("ix_campaign_recipients_phone_e164", "campaign_recipients", ["phone_e164"])
    op.create_index("ix_campaign_recipients_status", "campaign_recipients", ["status"])
    op.create_index("ix_campaign_recipients_provider_message_id", "campaign_recipients", ["provider_message_id"])

    op.create_table(
        "campaign_recipient_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign_recipients.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("raw", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaign_recipient_events_recipient_id", "campaign_recipient_events", ["recipient_id"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("state", conv_state, nullable=False, server_default="AI_ACTIVE"),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True)),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_preview", sa.String(500)),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id")),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversations_contact_id", "conversations", ["contact_id"])
    op.create_index("ix_conversations_state", "conversations", ["state"])
    op.create_index("ix_conversations_source_campaign_id", "conversations", ["source_campaign_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("direction", msg_direction, nullable=False),
        sa.Column("sender_kind", sa.String(20), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("media_url", sa.String(1000)),
        sa.Column("media_type", sa.String(60)),
        sa.Column("status", msg_status, nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(120)),
        sa.Column("provider_payload", sa.JSON),
        sa.Column("template_name", sa.String(120)),
        sa.Column("template_params", sa.JSON),
        sa.Column("error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_provider_message_id", "messages", ["provider_message_id"])
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "message_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("status", msg_status, nullable=False),
        sa.Column("raw", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_message_status_events_message_id", "message_status_events", ["message_id"])

    op.create_table(
        "conversation_state_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("from_state", conv_state),
        sa.Column("to_state", conv_state, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversation_state_logs_conversation_id", "conversation_state_logs", ["conversation_id"])

    op.create_table(
        "handoff_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("source", sa.String(40), nullable=False, server_default="dashboard"),
        sa.Column("details", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_handoff_events_conversation_id", "handoff_events", ["conversation_id"])

    op.create_table(
        "ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id")),
        sa.Column("agent_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_profiles.id")),
        sa.Column("intent", sa.String(60)),
        sa.Column("used_kb_chunks", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("prompt", sa.Text, nullable=False, server_default=""),
        sa.Column("response", sa.Text, nullable=False, server_default=""),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(300)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_runs_conversation_id", "ai_runs", ["conversation_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.String(80)),
        sa.Column("details", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "raw_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("dedupe_key", sa.String(200), unique=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_webhook_events_provider", "raw_webhook_events", ["provider"])
    op.create_index("ix_raw_webhook_events_dedupe_key", "raw_webhook_events", ["dedupe_key"])

    op.create_table(
        "settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("description", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_settings_key", "settings", ["key"])


def downgrade() -> None:
    # Single-shot initial migration — downgrade drops everything.
    for table in [
        "settings",
        "raw_webhook_events",
        "audit_logs",
        "ai_runs",
        "handoff_events",
        "conversation_state_logs",
        "message_status_events",
        "messages",
        "conversations",
        "campaign_recipient_events",
        "campaign_recipients",
        "campaign_uploads",
        "campaigns",
        "agent_profile_kb_links",
        "faq_entries",
        "knowledge_chunks",
        "knowledge_documents",
        "knowledge_bases",
        "agent_profiles",
        "contacts",
        "users",
    ]:
        op.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
    for enum_name in [
        "role",
        "conversation_state",
        "message_direction",
        "message_status",
        "campaign_status",
        "campaign_recipient_status",
    ]:
        op.execute(f'DROP TYPE IF EXISTS {enum_name}')
