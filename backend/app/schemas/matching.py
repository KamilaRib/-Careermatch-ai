"""Pydantic schemas for deterministic ATS matchmaking and compatibility breakdown."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MatchState = Literal[
    "atendido",
    "parcialmente_atendido",
    "nao_identificado",
    "nao_atendido",
    "nao_avaliavel",
]

ScoreBand = Literal[
    "baixa_compatibilidade",
    "compatibilidade_parcial",
    "boa_compatibilidade",
    "alta_compatibilidade",
]

ScoringCategoryKey = Literal[
    "competencias_tecnicas",
    "experiencia_profissional",
    "requisitos_obrigatorios",
    "formacao_certificacoes",
    "competencias_comportamentais",
    "palavras_chave",
]


class RequirementMatchItem(BaseModel):
    requirement_name: str
    category: ScoringCategoryKey
    importance: str
    is_eliminatory: bool = False
    state: MatchState
    credit: float = Field(ge=0.0, le=1.0)
    job_evidence: str = ""
    resume_evidence: str = ""
    explanation: str = ""


class CategoryScoreItem(BaseModel):
    key: ScoringCategoryKey
    label: str
    base_weight_pct: float
    normalized_weight_pct: float
    applicable: bool = True
    score: float = Field(ge=0.0, le=100.0)
    weighted_contribution: float = Field(ge=0.0, le=100.0)
    evaluated_count: int = 0
    matched_count: int = 0
    partial_count: int = 0


class MatchingResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    band: ScoreBand
    band_label: str
    category_scores: list[CategoryScoreItem] = Field(default_factory=list)
    requirement_matches: list[RequirementMatchItem] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    partial_keywords: list[str] = Field(default_factory=list)
    unverified_requirements: list[str] = Field(default_factory=list)
    eliminatory_alerts: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    methodology_note: str = (
        "Este score é uma estimativa técnica determinística de aderência entre o currículo "
        "confirmado e os requisitos da vaga. Ausência de evidência no currículo é tratada como "
        "'não identificado' (não comprovado) e não como ausência real da competência."
    )
