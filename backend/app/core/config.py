"""Application configuration loaded and validated from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)

    frontend_url: str = "http://localhost:5173"

    ai_provider: Literal["gemini", "openai"] = "gemini"
    gemini_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    ai_model: str = ""
    ai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    ai_timeout_seconds: float = Field(default=60.0, gt=0)

    max_upload_mb: int = Field(default=10, ge=1, le=50)
    max_text_chars: int = Field(default=60_000, ge=1_000)

    session_ttl_minutes: int = Field(default=60, ge=1, le=24 * 60)
    session_cleanup_interval_seconds: int = Field(default=60, ge=5)

    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_ai_per_minute: int = Field(default=10, ge=1)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v

    @field_validator("ai_provider", "app_env", mode="before")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.is_production and not self.ai_api_key:
            raise ValueError(
                f"AI_PROVIDER={self.ai_provider} requer a chave de API correspondente em produção."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def ai_api_key(self) -> str:
        return self.gemini_api_key if self.ai_provider == "gemini" else self.openai_api_key

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_api_key)

    @property
    def resolved_ai_model(self) -> str:
        if self.ai_model:
            return self.ai_model
        return "gemini-2.5-flash" if self.ai_provider == "gemini" else "gpt-4o-mini"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
