import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.agent.runtime import RuntimeStore
from backend.main import app, get_replanner, get_store
from backend.models import PlanningResult, ReplanContext
from backend.replanner.planner import candidate_plans


class ReadyReplanner:
    def __init__(self) -> None:
        self.context: ReplanContext | None = None

    async def generate_plans(self, context: ReplanContext) -> PlanningResult:
        self.context = context
        plans = candidate_plans(
            context.trip,
            event=context.event,
            weather=context.weather,
            preferences=context.preferences,
            now=context.now,
        )
        plans = [plan.model_copy(update={"feasible": True}) for plan in plans]
        return PlanningResult(
            source="fixture",
            plans=plans,
            recommended_plan_id="A",
            warnings=["B fixture"],
        )


class InfeasibleReplanner:
    async def generate_plans(self, context: ReplanContext) -> PlanningResult:
        plans = candidate_plans(
            context.trip,
            event=context.event,
            weather=context.weather,
            preferences=context.preferences,
            now=context.now,
        )
        return PlanningResult(
            source="fixture",
            plans=plans,
            recommended_plan_id=None,
            warnings=["沒有可行方案"],
        )


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = RuntimeStore(Path(self.temp.name))
        app.dependency_overrides[get_store] = lambda: self.store
        self.addCleanup(app.dependency_overrides.clear)
        self.enterContext(patch.dict(os.environ, {"WEATHER_MODE": "mock"}))
        self.client = self.enterContext(TestClient(app))

    def test_health_and_trip(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        trip = self.client.get("/api/trip").json()
        self.assertEqual(trip["start_date"], "2026-09-12")
        self.assertEqual(trip["end_date"], "2026-09-14")
        self.assertEqual(trip["version"], 1)
        self.assertEqual(len(trip["items"]), 9)
        self.assertEqual(
            {item["scheduled_date"] for item in trip["items"]},
            {"2026-09-12", "2026-09-13", "2026-09-14"},
        )

    def test_health_does_not_create_runtime(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertFalse(self.store.path.exists())

    def test_openapi_exposes_multi_day_contract(self):
        schemas = self.client.get("/openapi.json").json()["components"]["schemas"]
        self.assertIn("start_date", schemas["Trip"]["properties"])
        self.assertIn("end_date", schemas["Trip"]["properties"])
        self.assertIn("version", schemas["Trip"]["properties"])
        self.assertIn("scheduled_date", schemas["TripItem"]["properties"])
        self.assertIn("affected_dates", schemas["Event"]["properties"])
        self.assertIn("affected_item_ids", schemas["Event"]["properties"])
        self.assertIn("start_date", schemas["WeatherContext"]["properties"])
        self.assertIn("end_date", schemas["WeatherContext"]["properties"])
        self.assertNotIn("date", schemas["WeatherContext"]["properties"])

    def test_openapi_exposes_complete_replan_and_selection_contracts(self):
        document = self.client.get("/openapi.json").json()
        schemas = document["components"]["schemas"]
        for schema in (
            "HealthResponse",
            "PlanChange",
            "PlanFeatures",
            "ReplanResponse",
            "SelectionRequest",
            "SelectionResponse",
            "ErrorResponse",
        ):
            self.assertIn(schema, schemas)

        replan_properties = schemas["ReplanResponse"]["properties"]
        for field in (
            "replan_id",
            "planning_source",
            "recommended_plan_id",
            "preference_insight",
        ):
            self.assertIn(field, replan_properties)

        plan_properties = schemas["Plan"]["properties"]
        for field in (
            "feasible",
            "changes",
            "additional_travel_minutes",
            "additional_cost_jpy",
            "booking_warnings",
            "features",
        ):
            self.assertIn(field, plan_properties)
        self.assertEqual(set(schemas["Plan"]["required"]), set(plan_properties))

        replan_required = set(schemas["ReplanResponse"]["required"])
        self.assertEqual(replan_required, set(replan_properties))

        change_properties = schemas["PlanChange"]["properties"]
        self.assertEqual(set(schemas["PlanChange"]["required"]), set(change_properties))
        for schema_name in (
            "Event",
            "HealthResponse",
            "PlanFeatures",
            "Preference",
            "PreferenceWeights",
            "Trip",
            "TripItem",
            "WeatherContext",
            "WeatherHour",
        ):
            schema = schemas[schema_name]
            self.assertEqual(set(schema["required"]), set(schema["properties"]))

        selection = document["paths"]["/api/selections"]["post"]
        self.assertEqual(
            set(selection["responses"]),
            {"200", "404", "409", "422", "503"},
        )

    def test_replan_contract_and_booking_preservation(self):
        result = self.client.post("/api/replan", json={
            "message": "後天迪士尼會下大雨",
            "now": "2026-09-12T09:00:00+09:00",
        })
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["status"], "placeholder")
        self.assertIsNone(data["replan_id"])
        self.assertEqual(data["planning_source"], "unavailable")
        self.assertIsNone(data["recommended_plan_id"])
        self.assertEqual(len(data["plans"]), 3)
        self.assertTrue(data["warnings"])
        self.assertEqual(data["weather"]["source"], "fixture")
        self.assertEqual(data["weather"]["start_date"], "2026-09-12")
        self.assertEqual(data["weather"]["end_date"], "2026-09-14")
        self.assertEqual(data["preferences"]["selection_count"], 0)
        original = self.client.get("/api/trip").json()["items"]
        for plan in data["plans"]:
            self.assertEqual([x for x in plan["items"] if x["booking"]],
                             [x for x in original if x["booking"]])

    def test_invalid_request(self):
        for payload in ({"message": ""}, {"message": "   "},
                        {"message": "test", "trip_id": "missing"},
                        {"message": "test", "unexpected": True}):
            self.assertEqual(self.client.post("/api/replan", json=payload).status_code, 422)

    def test_now_requires_timezone_offset(self):
        response = self.client.post("/api/replan", json={
            "message": "下午下雨", "now": "2026-09-12T11:00:00",
        })
        self.assertEqual(response.status_code, 422)

    def test_replan_receives_persisted_context_and_does_not_change_state(self):
        trip = self.store.get_trip()
        trip.items[0].name = "目前已套用的行程"
        preferences = self.store.get_preferences()
        preferences.weights.preserve_booking = 3
        preferences.selection_count = 2
        self.store.save_state(trip, preferences)
        state_bytes = self.store.path.read_bytes()

        with patch("backend.main.candidate_plans", wraps=candidate_plans) as planner:
            response = self.client.post("/api/replan", json={
                "message": "下午下雨", "now": "2026-09-12T23:30:00+08:00",
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(planner.call_args.args[0], trip)
        context = planner.call_args.kwargs
        self.assertEqual(context["event"].summary, "下午下雨")
        self.assertEqual(context["preferences"], preferences)
        self.assertEqual(context["now"].isoformat(), "2026-09-13T00:30:00+09:00")
        self.assertEqual(context["weather"].start_date.isoformat(), "2026-09-13")
        self.assertEqual(context["weather"].end_date.isoformat(), "2026-09-14")
        self.assertEqual(self.client.get("/api/preferences").json(),
                         preferences.model_dump(mode="json"))
        self.assertEqual(self.client.get("/api/trip").json(), trip.model_dump(mode="json"))
        self.assertEqual(self.store.path.read_bytes(), state_bytes)

    def test_corrupt_runtime_returns_503_without_reset(self):
        self.store.load_state()
        contents = b"{broken"
        self.store.path.write_bytes(contents)
        for endpoint in ("/api/trip", "/api/preferences"):
            self.assertEqual(self.client.get(endpoint).status_code, 503)
        response = self.client.post("/api/replan", json={"message": "下雨"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.store.path.read_bytes(), contents)

    def test_unknown_selection_returns_404(self):
        invalid = self.client.post(
            "/api/selections", json={"replan_id": "x", "plan_id": "A"},
        )
        self.assertEqual(invalid.status_code, 422)
        invalid_plan = self.client.post(
            "/api/selections",
            json={"replan_id": str(uuid4()), "plan_id": "D"},
        )
        self.assertEqual(invalid_plan.status_code, 422)

        response = self.client.post(
            "/api/selections", json={"replan_id": str(uuid4()), "plan_id": "A"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("snapshot", response.json()["detail"])

    def test_ready_replan_can_be_selected_once_and_retried_idempotently(self):
        replanner = ReadyReplanner()
        app.dependency_overrides[get_replanner] = lambda: replanner
        response = self.client.post("/api/replan", json={
            "message": "後天迪士尼會下大雨",
            "now": "2026-09-12T09:00:00+09:00",
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["planning_source"], "fixture")
        self.assertEqual(data["recommended_plan_id"], "A")
        self.assertIn("B fixture", data["warnings"])
        self.assertEqual(replanner.context.event.affected_item_ids, ["item-9"])
        self.assertIn(data["replan_id"], self.store.load_state().replan_snapshots)

        request = {"replan_id": data["replan_id"], "plan_id": "A"}
        selected = self.client.post("/api/selections", json=request)
        retried = self.client.post("/api/selections", json=request)

        self.assertEqual(selected.status_code, 200)
        self.assertEqual(retried.json(), selected.json())
        self.assertEqual(selected.json()["trip"]["version"], 2)
        self.assertEqual(selected.json()["preferences"]["selection_count"], 1)
        self.assertEqual(selected.json()["preferences"]["weights"]["preserve_booking"], 2)
        self.assertEqual(self.store.get_trip().version, 2)
        self.assertEqual(self.store.get_preferences().selection_count, 1)

        changed = self.client.post("/api/selections", json={
            "replan_id": data["replan_id"],
            "plan_id": "B",
        })
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(self.store.get_preferences().selection_count, 1)

    def test_stale_replan_cannot_be_selected(self):
        app.dependency_overrides[get_replanner] = lambda: ReadyReplanner()
        response = self.client.post("/api/replan", json={
            "message": "睡過頭兩小時",
            "now": "2026-09-12T09:00:00+09:00",
        })
        replan_id = response.json()["replan_id"]
        trip = self.store.get_trip()
        trip.version += 1
        self.store.save_trip(trip)

        selected = self.client.post("/api/selections", json={
            "replan_id": replan_id,
            "plan_id": "A",
        })

        self.assertEqual(selected.status_code, 409)
        self.assertIn("版本", selected.json()["detail"])

    def test_infeasible_plan_cannot_be_selected(self):
        app.dependency_overrides[get_replanner] = lambda: InfeasibleReplanner()
        response = self.client.post("/api/replan", json={
            "message": "後天迪士尼會下大雨",
            "now": "2026-09-12T09:00:00+09:00",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertIsNone(response.json()["recommended_plan_id"])
        selected = self.client.post("/api/selections", json={
            "replan_id": response.json()["replan_id"],
            "plan_id": "A",
        })

        self.assertEqual(selected.status_code, 409)
        self.assertIn("不可行", selected.json()["detail"])
        self.assertEqual(self.store.get_trip().version, 1)
