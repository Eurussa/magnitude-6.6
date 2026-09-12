"""Repository-root LLM configuration for Backend B's planning provider."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class ReplannerConfigurationError(RuntimeError):
    """Raised when shared LLM configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ReplannerSettings:
    """Validated settings passed explicitly to the replanner boundary."""

    mode: Literal["live", "fixture"] = "fixture"
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4-mini"
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    max_output_tokens: int = 16_000

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> "ReplannerSettings":
        """Load shared LLM settings from the repository-root env file.

        Process environment variables take precedence, which keeps deployment
        configuration possible without mutating the process environment via
        ``load_dotenv``.
        """
        file_values = dotenv_values(env_file) if env_file.exists() else {}

        def read(name: str) -> str | None:
            value = os.getenv(name)
            if value is None:
                raw = file_values.get(name)
                value = raw if isinstance(raw, str) else None
            return value.strip() if value else None

        api_key = read("LLM_API_KEY")
        mode: Literal["live", "fixture"] = "live" if api_key else "fixture"

        timeout_seconds = _positive_float(
            read("LLM_TIMEOUT_SECONDS"),
            default=30.0,
            name="LLM_TIMEOUT_SECONDS",
        )
        return cls(
            mode=mode,
            api_key=api_key,
            base_url=(
                read("LLM_BASE_URL")
                or "https://api.openai.com/v1"
            ).rstrip("/"),
            model=read("LLM_MODEL") or "gpt-5.4-mini",
            timeout_seconds=timeout_seconds,
        )


def _positive_float(value: str | None, *, default: float, name: str) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ReplannerConfigurationError(f"{name} must be a number") from exc
    if parsed <= 0:
        raise ReplannerConfigurationError(f"{name} must be greater than zero")
    return parsed

