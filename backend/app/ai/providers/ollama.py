"""Ollama local LLM provider (default free local AI engine).

Includes CPU-optimized hybrid structured inference (`enrich_resume_fast`, `enrich_job_fast`)
so 3B models (`llama3.2`) running on 4-core CPUs without dedicated VRAM respond in seconds
instead of timing out on 1,500-token JSON generation.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.ai.providers.base import _CODE_FENCE_RE, parse_and_validate_json
from app.core.errors import AIUnavailableError
from app.core.logging import get_logger
from app.schemas.job import ParsedJobData
from app.schemas.resume import ParsedResumeData, SkillItem

T = TypeVar("T", bound=BaseModel)
log = get_logger("app.ai.ollama")


def _compact_schema_template(schema: type[BaseModel]) -> str:
    try:
        empty_instance = schema()
        return json.dumps(empty_instance.model_dump(), ensure_ascii=False)
    except Exception:
        return json.dumps(schema.model_json_schema(), ensure_ascii=False)


def _coerce_ollama_payload(raw_content: str, schema: type[T], provider_name: str) -> T:
    try:
        return parse_and_validate_json(raw_content, schema, provider_name=provider_name)
    except Exception:
        cleaned = _CODE_FENCE_RE.sub("", (raw_content or "").strip()).strip()
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise
        if "technical_skills" in payload and isinstance(payload["technical_skills"], list):
            payload["technical_skills"] = [
                {"name": s, "category": "Técnica", "evidence_quote": s, "evidence_verified": True}
                if isinstance(s, str)
                else s
                for s in payload["technical_skills"]
            ]
        if "certifications" in payload and isinstance(payload["certifications"], list):
            payload["certifications"] = [
                {"name": c, "issuer": "", "year": "", "evidence_quote": c, "evidence_verified": True}
                if isinstance(c, str)
                else c
                for c in payload["certifications"]
            ]
        if "languages" in payload and isinstance(payload["languages"], list):
            payload["languages"] = [
                {"language": l, "proficiency": "", "evidence_quote": l, "evidence_verified": True}
                if isinstance(l, str)
                else l
                for l in payload["languages"]
            ]
        if "experiences" in payload and isinstance(payload["experiences"], list):
            for exp in payload["experiences"]:
                if isinstance(exp, dict):
                    if isinstance(exp.get("responsibilities"), str):
                        exp["responsibilities"] = [exp["responsibilities"]]
                    if isinstance(exp.get("achievements"), str):
                        exp["achievements"] = [exp["achievements"]]
        return schema.model_validate(payload)


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        temperature: float = 0.2,
        timeout_seconds: float = 180.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self._client = http_client

    async def _post_chat(self, payload: dict[str, Any]) -> str:
        url = f"{self.base_url}/api/chat"
        timeout_cfg = httpx.Timeout(
            self.timeout_seconds,
            connect=min(10.0, self.timeout_seconds),
        )
        try:
            if self._client is not None:
                resp = await self._client.post(url, json=payload, timeout=timeout_cfg)
            else:
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    resp = await client.post(url, json=payload)
        except httpx.RequestError as exc:
            log.warning("ollama_unreachable", extra={"exc_type": type(exc).__name__})
            raise AIUnavailableError(
                "Servidor Ollama local indisponível em "
                f"{self.base_url}. Verifique se o Ollama está em execução."
            ) from exc

        if resp.status_code >= 400:
            log.warning("ollama_http_error", extra={"status": resp.status_code})
            raise AIUnavailableError(
                f"Falha ao comunicar com o Ollama (HTTP {resp.status_code})."
            )

        try:
            body = resp.json()
            return str(body.get("message", {}).get("content", ""))
        except Exception as exc:
            raise AIUnavailableError("Resposta inesperada do servidor Ollama.") from exc

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        template_hint = _compact_schema_template(schema)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"Retorne um objeto JSON seguindo estas chaves:\n{template_hint}"
                    ),
                },
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": 2048,
                "num_predict": 512,
            },
        }
        raw_content = await self._post_chat(payload)
        return _coerce_ollama_payload(raw_content, schema, provider_name=self.name)

    async def enrich_resume_fast(
        self,
        raw_text: str,
        baseline: ParsedResumeData,
    ) -> ParsedResumeData:
        """Executes a compact, CPU-friendly structured LLM pass on Ollama and merges grounded results."""
        safe_excerpt = raw_text[:1800].replace("</curriculo>", "")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extraia do currículo apenas dados literalmente presentes. "
                        "Responda SOMENTE JSON com as chaves: "
                        '{"full_name": "", "location": "", "skills": [""]}'
                    ),
                },
                {
                    "role": "user",
                    "content": f"<curriculo>\n{safe_excerpt}\n</curriculo>",
                },
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 1536,
                "num_predict": 140,
            },
        }
        raw_content = await self._post_chat(payload)
        cleaned = _CODE_FENCE_RE.sub("", raw_content.strip()).strip()
        try:
            llm_obj = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIUnavailableError("Ollama retornou JSON inválido.") from exc

        merged = baseline.model_copy(deep=True)
        if isinstance(llm_obj, dict):
            fn = str(llm_obj.get("full_name") or "").strip()
            if fn and not merged.personal_info.full_name and fn.lower() in raw_text.lower():
                merged.personal_info.full_name = fn[:160]
            loc = str(llm_obj.get("location") or "").strip()
            if loc and not merged.personal_info.location and loc.lower() in raw_text.lower():
                merged.personal_info.location = loc[:160]
            llm_skills = llm_obj.get("skills")
            if isinstance(llm_skills, list):
                existing_names = {s.name.lower() for s in merged.technical_skills}
                for item in llm_skills:
                    s_name = str(item).strip() if isinstance(item, str) else ""
                    if (
                        1 < len(s_name) <= 50
                        and s_name.lower() not in existing_names
                        and s_name.lower() in raw_text.lower()
                    ):
                        existing_names.add(s_name.lower())
                        merged.technical_skills.append(
                            SkillItem(
                                name=s_name,
                                category="Técnica",
                                evidence_quote=s_name,
                                evidence_verified=True,
                            )
                        )
        return merged

    async def enrich_job_fast(
        self,
        raw_text: str,
        baseline: ParsedJobData,
    ) -> ParsedJobData:
        """Executes a compact structured LLM pass on Ollama for job descriptions."""
        safe_excerpt = raw_text[:1800].replace("</vaga>", "")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extraia da vaga apenas dados literalmente presentes. "
                        "Responda SOMENTE JSON com as chaves: "
                        '{"title": "", "company": "", "seniority": ""}'
                    ),
                },
                {
                    "role": "user",
                    "content": f"<vaga>\n{safe_excerpt}\n</vaga>",
                },
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 1536,
                "num_predict": 100,
            },
        }
        raw_content = await self._post_chat(payload)
        cleaned = _CODE_FENCE_RE.sub("", raw_content.strip()).strip()
        try:
            llm_obj = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIUnavailableError("Ollama retornou JSON inválido.") from exc

        merged = baseline.model_copy(deep=True)
        if isinstance(llm_obj, dict):
            t = str(llm_obj.get("title") or "").strip()
            if t and not merged.title and t.lower() in raw_text.lower():
                merged.title = t[:180]
            c = str(llm_obj.get("company") or "").strip()
            if c and not merged.company and c.lower() in raw_text.lower():
                merged.company = c[:180]
        return merged

    async def enrich_ats_summary_fast(
        self,
        *,
        original_summary: str,
        job_title: str,
        verified_keywords: list[str],
    ) -> str:
        """Refines the professional summary for ATS readability using ONLY verified candidate data."""
        safe_summary = original_summary[:1200].replace("</resumo_original>", "")
        safe_title = job_title[:160]
        kw_str = ", ".join(verified_keywords[:12])
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Reescreva o resumo profissional em português de forma objetiva para sistemas ATS, "
                        "preservando TODOS os fatos e anos de experiência do resumo original e destacando "
                        "apenas as competências comprovadas listadas. NUNCA invente tecnologias ou experiências. "
                        'Responda SOMENTE JSON no formato: {"optimized_summary": ""}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Cargo-alvo: {safe_title}\n"
                        f"Competências comprovadas do candidato: {kw_str}\n"
                        f"<resumo_original>\n{safe_summary}\n</resumo_original>"
                    ),
                },
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 1536,
                "num_predict": 160,
            },
        }
        raw_content = await self._post_chat(payload)
        cleaned = _CODE_FENCE_RE.sub("", raw_content.strip()).strip()
        try:
            llm_obj = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIUnavailableError("Ollama retornou JSON inválido na otimização ATS.") from exc
        if isinstance(llm_obj, dict):
            return str(llm_obj.get("optimized_summary") or "").strip()
        return ""
