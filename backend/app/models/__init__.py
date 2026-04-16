"""All SQLAlchemy ORM models. Import here so Alembic picks them up."""
from app.models.user import User, Role  # noqa: F401
from app.models.contact import Contact  # noqa: F401
from app.models.conversation import (  # noqa: F401
    Conversation,
    ConversationState,
    Message,
    MessageDirection,
    MessageStatus,
    MessageStatusEvent,
    ConversationStateLog,
    HandoffEvent,
)
from app.models.campaign import (  # noqa: F401
    Campaign,
    CampaignStatus,
    CampaignUpload,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignRecipientEvent,
)
from app.models.knowledge import (  # noqa: F401
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeChunk,
    FaqEntry,
)
from app.models.agent import AgentProfile, AgentProfileKbLink  # noqa: F401
from app.models.ai_run import AiRun  # noqa: F401
from app.models.audit import AuditLog, RawWebhookEvent  # noqa: F401
from app.models.settings import Setting  # noqa: F401
