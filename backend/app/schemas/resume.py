"""Pydantic schemas for resume upload, parsing, evidence tracking and user review."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PersonalInfo(BaseModel):
    full_name: str = Field(default="", max_length=160)
    email: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=60)
    linkedin: str = Field(default="", max_length=240)
    location: str = Field(default="", max_length=160)
    evidence_quote: str = Field(default="", max_length=600)


class ExperienceItem(BaseModel):
    role: str = Field(default="", max_length=180)
    company: str = Field(default="", max_length=180)
    period: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence_quote: str = Field(default="", max_length=1200)
    evidence_verified: bool = True


class EducationItem(BaseModel):
    degree: str = Field(default="", max_length=200)
    institution: str = Field(default="", max_length=200)
    period: str = Field(default="", max_length=120)
    evidence_quote: str = Field(default="", max_length=600)
    evidence_verified: bool = True


class CertificationItem(BaseModel):
    name: str = Field(default="", max_length=200)
    issuer: str = Field(default="", max_length=160)
    year: str = Field(default="", max_length=40)
    evidence_quote: str = Field(default="", max_length=600)
    evidence_verified: bool = True


class SkillItem(BaseModel):
    name: str = Field(default="", max_length=120)
    category: str = Field(default="Técnica", max_length=80)
    evidence_quote: str = Field(default="", max_length=600)
    evidence_verified: bool = True


class LanguageItem(BaseModel):
    language: str = Field(default="", max_length=80)
    proficiency: str = Field(default="", max_length=80)
    evidence_quote: str = Field(default="", max_length=400)
    evidence_verified: bool = True


class ProjectItem(BaseModel):
    name: str = Field(default="", max_length=180)
    description: str = Field(default="", max_length=1000)
    technologies: list[str] = Field(default_factory=list)
    url: str = Field(default="", max_length=240)
    evidence_quote: str = Field(default="", max_length=800)
    evidence_verified: bool = True


class ParsedResumeData(BaseModel):
    """Structured resume extracted either by an LLM provider or deterministic fallback."""

    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    professional_summary: str = Field(default="", max_length=4000)
    summary_evidence_quote: str = Field(default="", max_length=1000)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    technical_skills: list[SkillItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)


class EvidenceValidationReport(BaseModel):
    total_items_checked: int = 0
    verified_items: int = 0
    unverified_warnings: list[str] = Field(default_factory=list)


ExtractionMethod = Literal["llm", "deterministic_fallback"]


class ResumeUploadResponse(BaseModel):
    filename: str
    kind: Literal["pdf", "docx", "txt"]
    size_bytes: int
    char_count: int
    raw_text: str


class ResumeParseRequest(BaseModel):
    text: str | None = Field(default=None, max_length=60_000)
    use_deterministic_only: bool = False

    @field_validator("text")
    @classmethod
    def _strip_text(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v


class ResumeConfirmRequest(BaseModel):
    data: ParsedResumeData
    confirmed: bool = True


class ResumeSessionState(BaseModel):
    has_resume: bool = False
    filename: str | None = None
    source_kind: Literal["pdf", "docx", "txt", "pasted"] | None = None
    raw_text: str = ""
    data: ParsedResumeData | None = None
    extraction_method: ExtractionMethod | None = None
    provider_used: str | None = None
    provider_fallback_reason: str | None = None
    evidence_report: EvidenceValidationReport = Field(default_factory=EvidenceValidationReport)
    confirmed: bool = False
