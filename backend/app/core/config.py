"""Application configuration loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["local", "staging", "production"] = "local"
    app_port: int = 8000
    app_secret_key: str
    jwt_access_ttl_min: int = 120
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Database / Redis
    database_url: str
    redis_url: str
    rq_queue_name: str = "whatsapp-agent"

    # AiSensy
    aisensy_api_key: str
    aisensy_base_url: str = "https://backend.aisensy.com"
    aisensy_campaign_endpoint: str = "/campaign/t1/api/v2"
    aisensy_session_endpoint: str = "/direct-apis/t1/messages"
    aisensy_webhook_secret: str
    aisensy_source: str = "terrarex-dashboard"

    # AI
    ai_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ai_model: str = "claude-sonnet-4-6"
    ai_embedding_provider: Literal["openai"] = "openai"
    ai_embedding_model: str = "text-embedding-3-small"
    ai_embedding_dimensions: int = 1536

    # Business
    service_window_hours: int = 24
    campaign_attribution_hours: int = 72
    business_name: str = "Terra Rex Energy"
    business_timezone: str = "Asia/Kolkata"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
