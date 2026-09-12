"""Shared, server-side OpenAI-compatible structured-output client."""
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM cannot return usable structured output."""


def llm_is_configured() -> bool:
    """Return whether both server-side credentials required for a call exist."""
    return bool(
        os.getenv("LLM_API_KEY", "").strip()
        and os.getenv("LLM_MODEL", "").strip()
    )


@dataclass(frozen=True, slots=True)
class LLMConfig:
    api_key: str = field(repr=False)
    model: str
    base_url: str
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "LLMConfig | None":
        api_key = os.getenv("LLM_API_KEY", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        if not api_key or not model:
            return None
        try:
            timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))
        except ValueError as exc:
            raise LLMProviderError("LLM timeout configuration is invalid") from exc
        if timeout_seconds <= 0:
            raise LLMProviderError("LLM timeout configuration is invalid")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip()
        if not base_url:
            raise LLMProviderError("LLM base URL is missing")
        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url.rstrip("/"),
            timeout_seconds=timeout_seconds,
        )


async def structured_completion(
    *,
    schema_name: str,
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Return provider JSON text without logging sensitive request data."""
    config = LLMConfig.from_env()
    if config is None:
        raise LLMProviderError("LLM is not configured")

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(
                f"{config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            message = body["choices"][0]["message"]
            if message.get("refusal"):
                raise LLMProviderError("LLM refused the request")
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("LLM response content is empty")
            return content
    except LLMProviderError:
        raise
    except (
        httpx.HTTPError,
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        raise LLMProviderError("LLM provider request failed") from exc
