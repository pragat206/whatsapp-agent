from fastapi import APIRouter

from app.api.v1 import (
    agents,
    analytics,
    auth,
    campaigns,
    contacts,
    inbox,
    kb,
    settings as settings_router,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(webhooks.router)
api_router.include_router(inbox.router)
api_router.include_router(campaigns.router)
api_router.include_router(kb.router)
api_router.include_router(agents.router)
api_router.include_router(contacts.router)
api_router.include_router(settings_router.router)
api_router.include_router(analytics.router)
