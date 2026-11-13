"""Pydantic schemas for job description parsing, requirement classification and session confirmation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.resume import EvidenceValidationReport, ExtractionMethod

RequirementImportance = Literal["obrigatorio", "desejavel", "contextual", "nao_especificado"]

RequirementCategory = Literal[
    "competencias_tecnicas",
    "experiencia_profissional",
    "formacao_certificacoes",
    "competencias_comportamentais",
    "idiomas",
    "outros",
]


class JobRequirementItem(BaseModel):
    name: str = Field(default="", max_length=220)
    category: RequirementCategory = "competencias_tecnicas"
    importance: RequirementImportance = "obrigatorio"
    is_eliminatory: bool = False
    min_years: int | None = Field(default=None, ge=0, le=40)
    evidence_quote: str = Field(default="", max_length=800)
    evidence_verified: bool = True


class ParsedJobData(BaseModel):
    title: str = Field(default="", max_length=180)
    company: str = Field(default="", max_length=180)
    location: str = Field(default="", max_length=160)
    work_model: str = Field(default="Não especificado", max_length=80)
    seniority: str = Field(default="Não especificado", max_length=80)
    experience_years_required: str = Field(default="", max_length=120)
    education_required: str = Field(default="", max_length=240)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[JobRequirementItem] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class JobParseRequest(BaseModel):
    text: str = Field(..., min_length=30, max_length=60_000)
    use_deterministic_only: bool = False

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class JobExtractUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    parse_immediately: bool = True
    use_deterministic_only: bool = False


class JobConfirmRequest(BaseModel):
    data: ParsedJobData
    raw_text: str | None = Field(default=None, max_length=60_000)
    confirmed: bool = True


class JobSessionState(BaseModel):
    has_job: bool = False
    source_kind: Literal["pasted", "url", "manual"] | None = None
    source_url: str | None = None
    raw_text: str = ""
    data: ParsedJobData | None = None
    extraction_method: ExtractionMethod | None = None
    provider_used: str | None = None
    provider_fallback_reason: str | None = None
    evidence_report: EvidenceValidationReport = Field(default_factory=EvidenceValidationReport)
    confirmed: bool = False
