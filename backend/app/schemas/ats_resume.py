"""Pydantic v2 schemas for Phase 5 — ATS-Friendly Resume Generation, Review & Export."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.resume import ParsedResumeData


class OptimizationChangeItem(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    section: str = Field(default="", max_length=100)
    change_type: Literal[
        "reordenacao_competencias",
        "alinhamento_resumo",
        "destaque_experiencia",
        "padronizacao_ats",
    ] = "padronizacao_ats"
    before: str = Field(default="", max_length=1200)
    after: str = Field(default="", max_length=1200)
    justification: str = Field(default="", max_length=600)


class KeywordSuggestionItem(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    keyword: str = Field(..., max_length=180)
    importance: str = Field(default="obrigatorio", max_length=40)
    category: str = Field(default="competencias_tecnicas", max_length=60)
    advisory_note: str = Field(default="", max_length=400)


class PreservationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    zero_fabrication_verified: bool = True
    preserved_experiences_count: int = 0
    preserved_education_count: int = 0
    preserved_skills_count: int = 0
    preserved_certifications_count: int = 0
    blocked_fabrications: list[str] = Field(default_factory=list)
    verification_note: str = Field(
        default=(
            "100% dos cargos, empresas, períodos, formações, certificações e competências "
            "foram validados contra o currículo original confirmado. Nenhuma qualificação "
            "não comprovada foi adicionada."
        ),
        max_length=600,
    )


class ATSResumeGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_deterministic_only: bool = False


class ATSResumeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    optimized_data: ParsedResumeData
    markdown_preview: str = Field(default="", max_length=60_000)
    plain_text_preview: str = Field(default="", max_length=60_000)
    changes: list[OptimizationChangeItem] = Field(default_factory=list)
    incorporated_keywords: list[str] = Field(default_factory=list)
    suggested_keywords: list[KeywordSuggestionItem] = Field(default_factory=list)
    preservation_report: PreservationReport = Field(default_factory=PreservationReport)
    optimization_method: Literal["llm", "deterministic_fallback", "deterministic"] = "deterministic"
    provider_used: str = "deterministic"
    provider_fallback_reason: str | None = None
    approved: bool = False


class ATSResumeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimized_data: ParsedResumeData
    approved: bool = True


class CurrentATSResumeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_ats_resume: bool
    result: ATSResumeResult | None = None
