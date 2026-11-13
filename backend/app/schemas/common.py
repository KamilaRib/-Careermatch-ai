from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    environment: str
    ai_provider: str
    ai_configured: bool
    ai_key_warning: str | None = None


class SessionInfo(BaseModel):
    active: bool
    ttl_minutes: int


class SessionDeleted(BaseModel):
    deleted: bool
