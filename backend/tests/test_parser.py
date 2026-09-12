import json
import os
import unittest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

from backend.agent.parser import parse_event
from backend.agent.runtime import DATA_DIR
from backend.llm import LLMProviderError
from backend.models import Event, Trip


class ParserTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.enterContext(patch.dict(os.environ, {
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }))
        self.trip = Trip.model_validate_json((DATA_DIR / "trip.json").read_bytes())
        self.now = datetime.fromisoformat("2026-09-12T09:00:00+09:00")

    async def parse(self, message: str) -> Event:
        return await parse_event(message, trip=self.trip, now=self.now)

    async def test_recognizes_demo_events(self) -> None:
        delayed = await self.parse("睡過頭兩小時")
        rainy = await self.parse("後天迪士尼會下大雨")
        closed = await self.parse("博物館今天休館")

        self.assertEqual((delayed.event_type, delayed.delay_minutes), ("delay", 120))
        self.assertEqual(rainy.event_type, "weather")
        self.assertEqual(rainy.affected_item_ids, ["item-9"])
        self.assertEqual(rainy.affected_dates, [date(2026, 9, 14)])
        self.assertEqual(closed.event_type, "closure")
        self.assertEqual(closed.affected_item_ids, ["item-2"])
        self.assertEqual(closed.affected_dates, [date(2026, 9, 12)])

    async def test_recognizes_english_delay(self) -> None:
        event = await self.parse("We are delayed 45 minutes")

        self.assertEqual((event.event_type, event.delay_minutes), ("delay", 45))
        self.assertEqual(event.affected_dates, [date(2026, 9, 12)])

    async def test_delay_can_span_days(self) -> None:
        event = await self.parse("航班延誤兩天")

        self.assertEqual((event.event_type, event.delay_minutes), ("delay", 2880))

    async def test_explicit_date_and_item_id_are_resolved_locally(self) -> None:
        event = await self.parse("2026-09-13 的 item-8 關閉")

        self.assertEqual(event.event_type, "closure")
        self.assertEqual(event.affected_item_ids, ["item-8"])
        self.assertEqual(event.affected_dates, [date(2026, 9, 13)])

    async def test_dates_outside_trip_are_not_forwarded(self) -> None:
        event = await self.parse("2026-09-20 下雨")

        self.assertEqual(event.event_type, "weather")
        self.assertEqual(event.affected_dates, [])

    async def test_unknown_text_stays_conservative(self) -> None:
        event = await self.parse("想換個行程")

        self.assertEqual(event.event_type, "unknown")
        self.assertEqual(event.delay_minutes, 0)
        self.assertEqual(event.affected_item_ids, [])
        self.assertEqual(event.affected_dates, [])

    async def test_valid_structured_output_is_used_with_minimal_context(self) -> None:
        completion = AsyncMock(return_value=json.dumps({
            "event_type": "weather",
            "delay_minutes": 0,
            "affected_item_ids": ["item-9"],
            "affected_dates": ["2026-09-14"],
            "summary": "provider summary",
        }))
        with patch.dict(os.environ, {
            "LLM_API_KEY": "test-key", "LLM_MODEL": "test-model",
        }), patch("backend.agent.parser.structured_completion", completion):
            event = await self.parse("後天迪士尼會下大雨")

        self.assertEqual(event.event_type, "weather")
        self.assertEqual(event.affected_item_ids, ["item-9"])
        self.assertEqual(event.summary, "後天迪士尼會下大雨")
        prompt = json.loads(completion.await_args.kwargs["user_prompt"])
        self.assertEqual(prompt["context"]["timezone"], "Asia/Tokyo")
        self.assertEqual(prompt["context"]["items"][0].keys(), {
            "id", "name", "scheduled_date",
        })
        self.assertNotIn("latitude", completion.await_args.kwargs["user_prompt"])

    async def test_invalid_provider_output_uses_local_fallback(self) -> None:
        with patch.dict(os.environ, {
            "LLM_API_KEY": "test-key", "LLM_MODEL": "test-model",
        }), patch(
            "backend.agent.parser.structured_completion",
            AsyncMock(return_value="not-json"),
        ):
            event = await self.parse("We are delayed 45 minutes")

        self.assertEqual((event.event_type, event.delay_minutes), ("delay", 45))

    async def test_unknown_provider_reference_uses_local_fallback(self) -> None:
        completion = AsyncMock(return_value=json.dumps({
            "event_type": "closure",
            "delay_minutes": 0,
            "affected_item_ids": ["invented-item"],
            "affected_dates": ["2026-09-13"],
            "summary": "ignored",
        }))
        with patch.dict(os.environ, {
            "LLM_API_KEY": "test-key", "LLM_MODEL": "test-model",
        }), patch("backend.agent.parser.structured_completion", completion):
            event = await self.parse("博物館今天休館")

        self.assertEqual(event.affected_item_ids, ["item-2"])
        self.assertEqual(event.affected_dates, [date(2026, 9, 12)])

    async def test_provider_date_outside_trip_uses_local_fallback(self) -> None:
        completion = AsyncMock(return_value=json.dumps({
            "event_type": "weather",
            "delay_minutes": 0,
            "affected_item_ids": [],
            "affected_dates": ["2026-09-20"],
            "summary": "ignored",
        }))
        with patch.dict(os.environ, {
            "LLM_API_KEY": "test-key", "LLM_MODEL": "test-model",
        }), patch("backend.agent.parser.structured_completion", completion):
            event = await self.parse("2026-09-20 下雨")

        self.assertEqual(event.event_type, "weather")
        self.assertEqual(event.affected_dates, [])

    async def test_provider_failure_uses_local_fallback(self) -> None:
        with patch.dict(os.environ, {
            "LLM_API_KEY": "test-key", "LLM_MODEL": "test-model",
        }), patch(
            "backend.agent.parser.structured_completion",
            AsyncMock(side_effect=LLMProviderError("timeout")),
        ):
            event = await self.parse("航班延誤兩天")

        self.assertEqual(event.delay_minutes, 2880)


if __name__ == "__main__":
    unittest.main()
