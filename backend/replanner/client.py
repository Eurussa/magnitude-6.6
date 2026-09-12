"""Async OpenAI Responses API adapter for planning structured outputs."""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from ..models import ReplanContext
from .config import ReplannerSettings
from .errors import PlanningOutputError, PlanningProviderError
from .fixtures import PlanningFixtures
from .prompts import PLANNING_INSTRUCTIONS, planning_input
from .schemas import PlanningDraft, PlanningRepairFeedback


class PlanningClient(Protocol):
    """Injectable provider boundary used by deterministic offline tests."""

    async def generate(
        self,
        context: ReplanContext,
        fixtures: PlanningFixtures,
        /,
        *,
        validation_feedback: PlanningRepairFeedback | None = None,
    ) -> PlanningDraft:
        ...


class OpenAIPlanningClient:
    """Call OpenAI without coupling the core replanner to a provider SDK."""

    def __init__(
        self,
        settings: ReplannerSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.api_key:
            raise PlanningProviderError("Planning API key is not configured")
        self._settings = settings
        self._http_client = http_client

    async def generate(
        self,
        context: ReplanContext,
        fixtures: PlanningFixtures,
        /,
        *,
        validation_feedback: PlanningRepairFeedback | None = None,
    ) -> PlanningDraft:
        payload = {
            "model": self._settings.model,
            "store": False,
            "instructions": PLANNING_INSTRUCTIONS,
            "input": planning_input(
                context,
                fixtures,
                validation_feedback=validation_feedback,
            ),
            "max_output_tokens": self._settings.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "smarttrip_planning_draft",
                    "strict": True,
                    "schema": PlanningDraft.model_json_schema(),
                }
            },
        }
        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    f"{self._settings.base_url}/responses",
                    headers=self._headers(),
                    json=payload,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self._settings.timeout_seconds
                ) as client:
                    response = await client.post(
                        f"{self._settings.base_url}/responses",
                        headers=self._headers(),
                        json=payload,
                    )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise PlanningProviderError("Planning provider is unavailable") from exc

        if response.status_code >= 400:
            raise PlanningProviderError(
                f"Planning provider returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise PlanningOutputError("Planning provider returned invalid JSON") from exc

        text = _extract_output_text(body)
        try:
            return PlanningDraft.model_validate_json(text)
        except ValidationError as exc:
            raise PlanningOutputError(
                "Planning provider output does not match the planning schema"
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }


def _extract_output_text(body: Any) -> str:
    if not isinstance(body, dict):
        raise PlanningOutputError("Planning response must be an object")
    if body.get("status") == "incomplete":
        raise PlanningOutputError("Planning response was incomplete")

    output = body.get("output")
    if not isinstance(output, list):
        raise PlanningOutputError("Planning response has no output items")

    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise PlanningOutputError("Planning provider refused the request")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    if not chunks:
        raise PlanningOutputError("Planning response contains no output text")
    return "".join(chunks)
