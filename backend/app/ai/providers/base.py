"""Abstract LLM provider protocol and factory for multi-provider AI orchestration."""

from __future__ import annotations

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import AIUnavailableError, ValidationFailed

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T: ...


def parse_and_validate_json(raw_output: str, schema: type[T], provider_name: str) -> T:
    """Strips markdown fences if present, parses JSON and validates against the Pydantic schema."""
    cleaned = _CODE_FENCE_RE.sub("", (raw_output or "").strip()).strip()
    if not cleaned:
        raise ValidationFailed(
            f"O provedor de IA ({provider_name}) retornou uma resposta vazia.",
            code="ai_empty_response",
        )
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValidationFailed(
            f"O provedor de IA ({provider_name}) retornou um JSON malformado.",
            code="ai_invalid_json",
        ) from exc

    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise ValidationFailed(
            f"A resposta da IA ({provider_name}) não atende ao schema esperado.",
            code="ai_schema_validation_failed",
        ) from exc


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Instantiates the configured LLM provider without altering business rules."""
    provider = settings.ai_provider
    if provider == "ollama":
        from app.ai.providers.ollama import OllamaProvider

        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.resolved_ai_model,
            temperature=settings.ai_temperature,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    if provider == "gemini":
        from app.ai.providers.gemini import GeminiProvider

        if not settings.ai_configured:
            raise AIUnavailableError(
                settings.ai_key_warning
                or "Chave GEMINI_API_KEY não configurada para o provedor Gemini."
            )
        return GeminiProvider(
            api_key=settings.ai_api_key,
            model=settings.resolved_ai_model,
            temperature=settings.ai_temperature,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    if provider == "openai":
        from app.ai.providers.openai import OpenAIProvider

        if not settings.ai_configured:
            raise AIUnavailableError(
                settings.ai_key_warning
                or "Chave OPENAI_API_KEY não configurada para o provedor OpenAI."
            )
        return OpenAIProvider(
            api_key=settings.ai_api_key,
            model=settings.resolved_ai_model,
            temperature=settings.ai_temperature,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    raise AIUnavailableError(f"Provedor de IA desconhecido: {provider}")
