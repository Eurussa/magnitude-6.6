import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.agent.runtime import RuntimeStore
from backend.main import app, get_store
from backend.replanner.planner import candidate_plans


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
        self.assertEqual(len(self.client.get("/api/trip").json()["items"]), 5)

    def test_health_does_not_create_runtime(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertFalse(self.store.path.exists())

    def test_replan_contract_and_booking_preservation(self):
        result = self.client.post("/api/replan", json={"message": "下午下大雨"})
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["status"], "placeholder")
        self.assertEqual(len(data["plans"]), 3)
        self.assertTrue(data["warnings"])
        self.assertEqual(data["weather"]["source"], "fixture")
        self.assertEqual(data["preferences"]["selection_count"], 0)
        original = self.client.get("/api/trip").json()["items"]
        for plan in data["plans"]:
            self.assertEqual([x for x in plan["items"] if x["booking"]],
                             [x for x in original if x["booking"]])

    def test_invalid_request(self):
        for payload in ({"message": ""}, {"message": "   "},
                        {"message": "test", "trip_id": "missing"}):
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
        self.assertEqual(context["weather"].date.isoformat(), "2026-09-13")
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
        self.assertEqual(self.client.post("/api/replan", json={"message": "下雨"}).status_code, 503)
        self.assertEqual(self.store.path.read_bytes(), contents)

    def test_selection_is_not_exposed_for_placeholder_plans(self):
        response = self.client.post("/api/selections", json={"replan_id": "x", "plan_id": "A"})
        self.assertEqual(response.status_code, 404)
