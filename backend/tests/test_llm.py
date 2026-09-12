import os
import unittest
from unittest.mock import patch

import httpx

from backend.llm import LLMProviderError, structured_completion


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.body


class FakeClient:
    response = FakeResponse({
        "choices": [{"message": {"content": '{"status":"ok"}'}}],
    })
    request = None
    timeout = None

    def __init__(self, *, timeout: float) -> None:
        type(self).timeout = timeout

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> FakeResponse:
        type(self).request = {"url": url, "headers": headers, "json": json}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class LLMTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeClient.response = FakeResponse({
            "choices": [{"message": {"content": '{"status":"ok"}'}}],
        })
        FakeClient.request = None
        FakeClient.timeout = None
        self.enterContext(patch.dict(os.environ, {
            "LLM_API_KEY": "test-secret",
            "LLM_MODEL": "gpt-test",
            "LLM_BASE_URL": "https://provider.test/v1/",
            "LLM_TIMEOUT_SECONDS": "3.5",
        }))
        self.enterContext(patch("backend.llm.httpx.AsyncClient", FakeClient))

    async def test_sends_strict_json_schema_request(self) -> None:
        content = await structured_completion(
            schema_name="test_result",
            schema={"type": "object", "additionalProperties": False},
            system_prompt="system",
            user_prompt="user",
        )

        self.assertEqual(content, '{"status":"ok"}')
        self.assertEqual(FakeClient.timeout, 3.5)
        request = FakeClient.request
        self.assertEqual(request["url"], "https://provider.test/v1/chat/completions")
        self.assertEqual(request["json"]["model"], "gpt-test")
        output = request["json"]["response_format"]
        self.assertEqual(output["type"], "json_schema")
        self.assertTrue(output["json_schema"]["strict"])
        self.assertNotIn("test-secret", str(request["json"]))

    async def test_missing_configuration_is_explicit(self) -> None:
        with patch.dict(os.environ, {"LLM_API_KEY": "", "LLM_MODEL": ""}):
            with self.assertRaisesRegex(LLMProviderError, "not configured"):
                await structured_completion(
                    schema_name="test",
                    schema={},
                    system_prompt="system",
                    user_prompt="user",
                )

    async def test_http_failure_is_wrapped(self) -> None:
        FakeClient.response = httpx.ReadTimeout("slow provider")
        with self.assertRaisesRegex(LLMProviderError, "provider request failed"):
            await structured_completion(
                schema_name="test",
                schema={},
                system_prompt="system",
                user_prompt="user",
            )


if __name__ == "__main__":
    unittest.main()
