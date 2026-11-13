"""Pydantic v2 schemas for Phase 6 — Contextual Career & Application Assistant."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssistantMessageRole = Literal["user", "assistant"]
AssistantTopic = Literal[
    "compatibilidade",
    "lacunas",
    "melhorias",
    "entrevista",
    "candidatura",
    "geral",
]


class AssistantCitation(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    source: Literal["curriculo", "vaga", "matching", "ats"] = "matching"
    label: str = Field(..., max_length=160)
    evidence: str = Field(default="", max_length=600)


class AssistantChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(..., max_length=64)
    role: AssistantMessageRole
    content: str = Field(..., max_length=8000)
    created_at: str = Field(..., max_length=64)
    citations: list[AssistantCitation] = Field(default_factory=list)
    response_method: Literal["llm", "deterministic_fallback", "deterministic"] | None = None
    provider_used: str | None = None
    provider_fallback_reason: str | None = None


class AssistantContextSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_resume: bool = False
    resume_confirmed: bool = False
    candidate_name: str = ""
    has_job: bool = False
    job_confirmed: bool = False
    job_title: str = ""
    has_matching: bool = False
    overall_score: int | None = None
    band_label: str | None = None
    has_ats_resume: bool = False
    verified_skills: list[str] = Field(default_factory=list)
    unverified_requirements: list[str] = Field(default_factory=list)


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(..., min_length=2, max_length=1500)
    topic: AssistantTopic = "geral"
    use_deterministic_only: bool = False


class AssistantChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reply: AssistantChatMessage
    history: list[AssistantChatMessage] = Field(default_factory=list)
    context_summary: AssistantContextSummary


class AssistantSessionState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    history: list[AssistantChatMessage] = Field(default_factory=list)
    context_summary: AssistantContextSummary
    suggested_prompts: list[str] = Field(default_factory=list)

