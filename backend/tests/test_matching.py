from __future__ import annotations

from fastapi.testclient import TestClient

from app.schemas.job import JobRequirementItem, ParsedJobData
from app.schemas.resume import (
    EducationItem,
    ExperienceItem,
    LanguageItem,
    ParsedResumeData,
    PersonalInfo,
    SkillItem,
)
from app.services.matching_engine import calculate_matching
from tests.conftest import csrf_headers
from tests.test_jobs import SAMPLE_JOB_TEXT
from tests.test_resumes import SAMPLE_RESUME_TEXT


def test_matching_requires_confirmed_resume_and_confirmed_job(client: TestClient) -> None:
    headers = csrf_headers(client)

    # 1. Neither resume nor job exists
    r1 = client.post("/api/v1/matching/analyze", headers=headers)
    assert r1.status_code == 422
    assert r1.json()["error"]["code"] == "missing_resume"

    # 2. Resume parsed but not confirmed
    r_res = client.post(
        "/api/v1/resumes/parse",
        json={"text": SAMPLE_RESUME_TEXT, "use_deterministic_only": True},
        headers=headers,
    )
    assert r_res.status_code == 200
    r2 = client.post("/api/v1/matching/analyze", headers=headers)
    assert r2.status_code == 422
    assert r2.json()["error"]["code"] == "resume_not_confirmed"

    # Confirm resume
    client.put(
        "/api/v1/resumes/current",
        json={"data": r_res.json()["data"], "confirmed": True},
        headers=headers,
    )

    # 3. Job parsed but not confirmed
    r_job = client.post(
        "/api/v1/jobs/parse",
        json={"text": SAMPLE_JOB_TEXT, "use_deterministic_only": True},
        headers=headers,
    )
    assert r_job.status_code == 200
    r3 = client.post("/api/v1/matching/analyze", headers=headers)
    assert r3.status_code == 422
    assert r3.json()["error"]["code"] == "job_not_confirmed"

    # Confirm job -> now matching succeeds
    client.put(
        "/api/v1/jobs/current",
        json={"data": r_job.json()["data"], "confirmed": True},
        headers=headers,
    )
    r_ok = client.post("/api/v1/matching/analyze", headers=headers)
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert 0 <= body["overall_score"] <= 100
    assert "Python" in body["matched_keywords"]
    assert "FastAPI" in body["matched_keywords"]
    assert "PostgreSQL" in body["matched_keywords"]


def test_weight_renormalization_when_categories_not_applicable() -> None:
    resume = ParsedResumeData(
        personal_info=PersonalInfo(full_name="Candidato"),
        technical_skills=[SkillItem(name="Python", evidence_quote="Python")],
    )
    # Job has ONLY technical skills and no experience, education, behavioral or mandatory multi-word items
    job = ParsedJobData(
        title="Dev Python",
        requirements=[
            JobRequirementItem(
                name="Python",
                category="competencias_tecnicas",
                importance="obrigatorio",
                evidence_quote="Python",
            )
        ],
        technologies=["Python"],
    )
    result = calculate_matching(resume, job, raw_resume_text="Python")
    applicable = [c for c in result.category_scores if c.applicable]
    total_norm_weight = sum(c.normalized_weight_pct for c in applicable)
    assert round(total_norm_weight, 1) == 100.0
    assert result.overall_score == 100
    assert result.band == "alta_compatibilidade"


def test_match_states_and_eliminatory_alert_and_non_fabrication_framing() -> None:
    resume = ParsedResumeData(
        personal_info=PersonalInfo(full_name="Ana"),
        professional_summary="Desenvolvedora Backend com 2 anos de experiência em Python e Docker.",
        experiences=[
            ExperienceItem(
                role="Dev Backend",
                company="Tech",
                period="2024 - 2025",
                responsibilities=["APIs em Python e Docker"],
            )
        ],
        education=[EducationItem(degree="Ciência da Computação", institution="USP")],
        technical_skills=[
            SkillItem(name="Python", evidence_quote="Python"),
            SkillItem(name="Docker", evidence_quote="Docker"),
        ],
        languages=[LanguageItem(language="Português", proficiency="Nativo")],
    )
    job = ParsedJobData(
        title="Arquiteto Cloud",
        requirements=[
            JobRequirementItem(
                name="Python",
                category="competencias_tecnicas",
                importance="obrigatorio",
                evidence_quote="Python",
            ),
            # Compound requirement with Docker (present) + Kubernetes (absent) -> parcialmente_atendido
            JobRequirementItem(
                name="Docker e Kubernetes",
                category="competencias_tecnicas",
                importance="desejavel",
                evidence_quote="Docker e Kubernetes",
            ),
            # Standalone Kubernetes when only Python and Docker exist -> nao_identificado
            JobRequirementItem(
                name="Kubernetes",
                category="competencias_tecnicas",
                importance="desejavel",
                evidence_quote="Kubernetes",
            ),
            # 8 years required vs 2 years on resume -> nao_atendido
            JobRequirementItem(
                name="8 anos de experiência em arquitetura distribuída",
                category="experiencia_profissional",
                importance="obrigatorio",
                min_years=8,
                evidence_quote="8 anos de experiência",
            ),
            # Eliminatory requirement not in resume -> nao_identificado + eliminatory alert
            JobRequirementItem(
                name="Certificação AWS Solutions Architect Professional",
                category="formacao_certificacoes",
                importance="obrigatorio",
                is_eliminatory=True,
                evidence_quote="Certificação AWS Solutions Architect Professional (eliminatório)",
            ),
            # Empty/un-evaluable requirement -> nao_avaliavel
            JobRequirementItem(
                name="de",
                category="outros",
                importance="contextual",
                evidence_quote="de",
            ),
        ],
    )
    result = calculate_matching(
        resume,
        job,
        raw_resume_text="Desenvolvedora Backend com 2 anos de experiência em Python e Docker.",
    )
    by_name = {m.requirement_name: m for m in result.requirement_matches}
    assert by_name["Python"].state == "atendido"
    assert by_name["Docker e Kubernetes"].state == "parcialmente_atendido"
    assert by_name["Kubernetes"].state == "nao_identificado"
    assert by_name["Kubernetes"].credit == 0.0
    assert by_name["8 anos de experiência em arquitetura distribuída"].state == "nao_atendido"
    assert (
        by_name["Certificação AWS Solutions Architect Professional"].state == "nao_identificado"
    )
    assert "Não identificado no texto do currículo" in by_name[
        "Certificação AWS Solutions Architect Professional"
    ].explanation
    assert by_name["de"].state == "nao_avaliavel"
    assert len(result.eliminatory_alerts) == 1


def test_regression_related_technologies_do_not_satisfy_specific_skill() -> None:
    """Regression test: Docker and AWS in resume must NEVER be treated as evidence of Kubernetes."""
    resume = ParsedResumeData(
        personal_info=PersonalInfo(full_name="Carlos Eduardo"),
        professional_summary="Engenheiro DevOps com experiência em Docker e AWS.",
        technical_skills=[
            SkillItem(name="Docker", evidence_quote="Docker"),
            SkillItem(name="AWS", evidence_quote="AWS"),
        ],
    )
    job = ParsedJobData(
        title="Engenheiro de Plataforma",
        requirements=[
            JobRequirementItem(
                name="Kubernetes",
                category="competencias_tecnicas",
                importance="obrigatorio",
                evidence_quote="Experiência em Kubernetes",
            )
        ],
    )
    result = calculate_matching(
        resume,
        job,
        raw_resume_text="Engenheiro DevOps com experiência em Docker e AWS.",
    )
    k8s_match = result.requirement_matches[0]
    assert k8s_match.requirement_name == "Kubernetes"
    assert k8s_match.state == "nao_identificado"
    assert k8s_match.credit == 0.0
    assert k8s_match.resume_evidence == ""
    assert "Kubernetes" in result.unverified_requirements
    assert "Kubernetes" not in result.partial_keywords
    assert "Kubernetes" not in result.matched_keywords
    assert any(
        "kubernetes" in rec.lower() and "tecnologias correlatas" in rec.lower()
        for rec in result.recommendations
    )
