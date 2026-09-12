import unittest
from fastapi.testclient import TestClient
from backend.main import app


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_and_trip(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertEqual(len(self.client.get("/api/trip").json()["items"]), 5)

    def test_replan_contract_and_booking_preservation(self):
        result = self.client.post("/api/replan", json={"message": "下午下大雨"})
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["status"], "placeholder")
        self.assertEqual(len(data["plans"]), 3)
        self.assertTrue(data["warnings"])
        original = self.client.get("/api/trip").json()["items"]
        for plan in data["plans"]:
            self.assertEqual([x for x in plan["items"] if x["booking"]],
                             [x for x in original if x["booking"]])

    def test_invalid_request(self):
        for payload in ({"message": ""}, {"message": "   "},
                        {"message": "test", "trip_id": "missing"}):
            self.assertEqual(self.client.post("/api/replan", json=payload).status_code, 422)
