import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.agent.runtime import DATA_DIR
from backend.agent.weather import fixture_weather
from backend.models import Event, Preference, PreferenceWeights, ReplanContext, Trip
from backend.replanner.client import OpenAIPlanningClient
from backend.replanner.config import ReplannerSettings
from backend.replanner.errors import (
    PlanningOutputError,
    PlanningProviderError,
    PlanValidationError,
)
from backend.replanner.fixtures import PlanningFixtures
from backend.replanner.planner import LLMReplanner
from backend.replanner.schemas import (
    PlanDraft,
    PlanningDraft,
    ScheduledItemDraft,
)


class FakePlanningClient:
    def __init__(self, draft: PlanningDraft | list[PlanningDraft]):
        self.drafts = draft if isinstance(draft, list) else [draft]
        self.calls = 0
        self.feedback = []

    async def generate(
        self, context, fixtures, /, *, validation_feedback=None
    ):
        del context, fixtures
        self.calls += 1
        self.feedback.append(validation_feedback)
        return self.drafts[min(self.calls - 1, len(self.drafts) - 1)]


class ReplannerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.trip = Trip.model_validate_json((DATA_DIR / "trip.json").read_bytes())
        self.preferences = Preference.model_validate_json(
            (DATA_DIR / "preferences.json").read_bytes()
        )
        self.weather = fixture_weather(
            timezone=self.trip.timezone,
            start_date=self.trip.start_date,
            end_date=self.trip.end_date,
        )
        self.fixtures = PlanningFixtures.load()

    async def test_live_draft_materializes_multi_day_swap_and_complete_changes(self):
        context = self._weather_context()
        client = FakePlanningClient(self._weather_draft())
        result = await LLMReplanner(
            client=client, fixtures=self.fixtures, max_attempts=2
        ).generate_plans(context)

        self.assertEqual(result.source, "live")
        self.assertEqual(client.calls, 1)
        self.assertTrue(all(plan.feasible for plan in result.plans))
        by_id = {plan.id: plan for plan in result.plans}
        swapped_disney = next(item for item in by_id["B"].items if item.id == "item-9")
        self.assertEqual(swapped_disney.scheduled_date, date(2026, 9, 13))
        for plan in result.plans:
            original_change_ids = {
                change.item_id
                for change in plan.changes
                if change.action != "add"
            }
            self.assertEqual(
                original_change_ids,
                {item.id for item in self.trip.items},
            )
        original_bookings = {
            item.id: (item.scheduled_date, item.start_time)
            for item in self.trip.items
            if item.booking
        }
        for plan in result.plans:
            planned = {item.id: item for item in plan.items}
            for item_id, slot in original_bookings.items():
                self.assertEqual(
                    (planned[item_id].scheduled_date, planned[item_id].start_time),
                    slot,
                )

    async def test_invalid_live_output_retries_then_uses_explicit_fixture(self):
        context = self._weather_context()
        invalid = self._weather_draft()
        plan_a = next(plan for plan in invalid.plans if plan.id == "A")
        locked = next(item for item in plan_a.items if item.id == "item-4")
        locked.start_time = "16:00"
        client = FakePlanningClient(invalid)

        with self.assertLogs("backend.replanner.planner", level="WARNING"):
            result = await LLMReplanner(
                client=client, fixtures=self.fixtures, max_attempts=2
            ).generate_plans(context)

        self.assertEqual(client.calls, 2)
        self.assertIsNone(client.feedback[0])
        repair = client.feedback[1]
        self.assertIsNotNone(repair)
        self.assertIn("item-4", " ".join(repair.errors))
        self.assertEqual(
            {plan.id for plan in repair.accepted_plans},
            {"B", "C"},
        )
        self.assertEqual(result.source, "fixture")
        self.assertTrue(any("fixture" in warning for warning in result.warnings))
        self.assertTrue(any(plan.feasible for plan in result.plans))

    async def test_retry_repairs_failed_plan_and_keeps_accepted_candidates(self):
        context = self._weather_context()
        invalid = self._weather_draft()
        plan_a = next(plan for plan in invalid.plans if plan.id == "A")
        locked = next(item for item in plan_a.items if item.id == "item-4")
        locked.start_time = "16:00"
        client = FakePlanningClient([invalid, self._weather_draft()])

        with self.assertLogs("backend.replanner.planner", level="WARNING"):
            result = await LLMReplanner(
                client=client, fixtures=self.fixtures, max_attempts=2
            ).generate_plans(context)

        self.assertEqual(client.calls, 2)
        self.assertEqual(result.source, "live")
        repair = client.feedback[1]
        self.assertEqual(
            {plan.id for plan in repair.accepted_plans},
            {"B", "C"},
        )

    async def test_fixture_supports_delay_and_deterministic_preference_ranking(self):
        event = Event(
            event_type="delay",
            delay_minutes=120,
            affected_item_ids=[],
            affected_dates=[date(2026, 9, 12)],
            summary="睡過頭兩小時",
        )
        context = ReplanContext(
            trip=self.trip,
            event=event,
            weather=self.weather,
            preferences=self.preferences,
            now=datetime.fromisoformat("2026-09-12T09:00:00+09:00"),
        )
        replanner = LLMReplanner(client=None, fixtures=self.fixtures)
        first = await replanner.generate_plans(context)
        second = await replanner.generate_plans(context)

        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertEqual(first.source, "fixture")
        self.assertEqual(first.recommended_plan_id, "A")
        by_id = {plan.id: plan for plan in first.plans}
        self.assertNotIn("item-1", {item.id for item in by_id["A"].items})
        moved = next(item for item in by_id["B"].items if item.id == "item-1")
        self.assertEqual(moved.start_time, "11:00")

    async def test_weight_change_can_recommend_maximize_or_relaxed(self):
        maximize_context = self._weather_context(
            PreferenceWeights(
                preserve_booking=0,
                maximize_attractions=10,
                relaxed=0,
            )
        )
        relaxed_context = self._weather_context(
            PreferenceWeights(
                preserve_booking=0,
                maximize_attractions=0,
                relaxed=10,
            )
        )
        replanner = LLMReplanner(client=None, fixtures=self.fixtures)

        maximize = await replanner.generate_plans(maximize_context)
        relaxed = await replanner.generate_plans(relaxed_context)

        self.assertEqual(maximize.recommended_plan_id, "B")
        self.assertEqual(relaxed.recommended_plan_id, "C")

    async def test_invalid_context_reference_is_rejected_before_provider_call(self):
        context = self._weather_context()
        context.event.affected_item_ids = ["invented-item"]
        client = FakePlanningClient(self._weather_draft())

        with self.assertRaises(PlanValidationError):
            await LLMReplanner(
                client=client, fixtures=self.fixtures
            ).generate_plans(context)

        self.assertEqual(client.calls, 0)

    async def test_openai_client_uses_responses_structured_output_without_storage(self):
        captured = {}
        draft_text = self._weather_draft().model_dump_json()

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers["Authorization"]
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {"type": "reasoning", "summary": []},
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": draft_text}],
                        },
                    ],
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = OpenAIPlanningClient(
                ReplannerSettings(mode="live", api_key="test-secret"),
                http_client=http,
            )
            result = await client.generate(self._weather_context(), self.fixtures)

        self.assertEqual({plan.id for plan in result.plans}, {"A", "B", "C"})
        self.assertEqual(captured["authorization"], "Bearer test-secret")
        body = captured["body"]
        self.assertFalse(body["store"])
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertNotIn("test-secret", json.dumps(body))
        planning_payload = json.loads(body["input"])
        facts = planning_payload["planning_facts"]
        self.assertIn("item-3", facts["fixed_item_ids"])
        travel = planning_payload["constraints"]["transport"]["travel_minutes"]
        self.assertEqual(travel["item-1"]["item-2"], 15)
        self.assertEqual(travel["item-1"]["item-9"], 20)

    async def test_openai_client_sanitizes_timeout_and_malformed_output(self):
        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("secret provider details", request=request)

        settings = ReplannerSettings(mode="live", api_key="test-secret")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout_handler)
        ) as http:
            with self.assertRaisesRegex(
                PlanningProviderError, "Planning provider is unavailable"
            ):
                await OpenAIPlanningClient(settings, http_client=http).generate(
                    self._weather_context(), self.fixtures
                )

        async def malformed_handler(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(200, json={"status": "completed", "output": []})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(malformed_handler)
        ) as http:
            with self.assertRaises(PlanningOutputError):
                await OpenAIPlanningClient(settings, http_client=http).generate(
                    self._weather_context(), self.fixtures
                )

    def test_settings_load_shared_llm_values_from_root_style_env_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {}, clear=True
        ):
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "LLM_API_KEY=local-test-key\n"
                "LLM_BASE_URL=https://example.test/v1/\n"
                "LLM_MODEL=gpt-test\n"
                "LLM_TIMEOUT_SECONDS=8\n",
                encoding="utf-8",
            )
            settings = ReplannerSettings.from_env(env_file)

        self.assertEqual(settings.api_key, "local-test-key")
        self.assertEqual(settings.base_url, "https://example.test/v1")
        self.assertEqual(settings.model, "gpt-test")
        self.assertEqual(settings.timeout_seconds, 8)
        self.assertEqual(settings.mode, "live")

    def test_settings_use_fixture_mode_without_shared_api_key(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {}, clear=True
        ):
            settings = ReplannerSettings.from_env(Path(directory) / ".env")

        self.assertEqual(settings.mode, "fixture")
        self.assertIsNone(settings.api_key)

    def _weather_context(
        self, weights: PreferenceWeights | None = None
    ) -> ReplanContext:
        preference = self.preferences
        if weights is not None:
            preference = preference.model_copy(update={"weights": weights})
        return ReplanContext(
            trip=self.trip,
            event=Event(
                event_type="weather",
                delay_minutes=0,
                affected_item_ids=["item-9"],
                affected_dates=[date(2026, 9, 14)],
                summary="迪士尼大雨，和其他天交換",
            ),
            weather=self.weather,
            preferences=preference,
            now=datetime.fromisoformat("2026-09-12T09:00:00+09:00"),
        )

    def _weather_draft(self) -> PlanningDraft:
        plans = []
        definitions = [
            (
                "A",
                "preserve_booking",
                "穩定優先",
                {},
                {"item-9"},
            ),
            (
                "B",
                "maximize_attractions",
                "完整交換",
                {
                    "item-6": (date(2026, 9, 14), "09:00"),
                    "item-7": (date(2026, 9, 14), "11:00"),
                    "item-8": (date(2026, 9, 14), "14:00"),
                    "item-9": (date(2026, 9, 13), "09:00"),
                },
                set(),
            ),
            (
                "C",
                "relaxed",
                "輕鬆安排",
                {},
                {"item-7", "item-9"},
            ),
        ]
        for plan_id, strategy, title, moves, cancels in definitions:
            items = []
            for item in self.trip.items:
                if item.id in cancels:
                    continue
                scheduled_date, start_time = moves.get(
                    item.id, (item.scheduled_date, item.start_time)
                )
                items.append(
                    ScheduledItemDraft(
                        id=item.id,
                        scheduled_date=scheduled_date,
                        start_time=start_time,
                    )
                )
            plans.append(
                PlanDraft(
                    id=plan_id,
                    strategy=strategy,
                    title=title,
                    items=items,
                )
            )
        return PlanningDraft(plans=plans)


if __name__ == "__main__":
    unittest.main()
