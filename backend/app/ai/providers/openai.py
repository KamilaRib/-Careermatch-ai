"""OpenAI API provider (optional cloud provider)."""

from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.ai.providers.base import parse_and_validate_json
from app.core.errors import AIUnavailableError
from app.core.logging import get_logger

T = TypeVar("T", bound=BaseModel)
log = get_logger("app.ai.openai")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self._client = http_client

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        schema_hint = schema.model_json_schema()
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"{user_prompt}\n\nJSON Schema obrigatório:\n{schema_hint}",
                },
            ],
        }

        try:
            if self._client is not None:
                resp = await self._client.post(OPENAI_API_URL, headers=headers, json=payload, timeout=self.timeout_seconds)
            else:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(OPENAI_API_URL, headers=headers, json=payload)
        except httpx.RequestError as exc:
            log.warning("openai_unreachable", extra={"exc_type": type(exc).__name__})
            raise AIUnavailableError("Não foi possível conectar à API da OpenAI.") from exc

        if resp.status_code >= 400:
            log.warning("openai_http_error", extra={"status": resp.status_code})
            raise AIUnavailableError(f"Erro retornado pela API da OpenAI (HTTP {resp.status_code}).")

        try:
            body = resp.json()
            choices = body.get("choices") or []
            raw_content = choices[0].get("message", {}).get("content", "") if choices else ""
        except Exception as exc:
            raise AIUnavailableError("Formato de resposta inesperado da API da OpenAI.") from exc

        return parse_and_validate_json(raw_content, schema, provider_name=self.name)
