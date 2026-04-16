"""FastAPI entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.business_name} WhatsApp Agent API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.include_router(api_router)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return {"ok": True, "env": settings.app_env}

    logger = get_logger("main")
    logger.info("app_started", env=settings.app_env)
    return app


app = create_app()
