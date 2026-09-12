import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from backend.agent.runtime import DATA_DIR
from backend.agent.weather import fetch_weather, get_weather
from backend.models import Trip


class WeatherTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.trip = Trip.model_validate_json((DATA_DIR / "trip.json").read_bytes())
        self.now = datetime.fromisoformat("2026-09-12T23:30:00+08:00")

    async def test_mock_does_not_call_provider_and_aligns_trip_date(self):
        with patch.dict(os.environ, {"WEATHER_MODE": "mock"}), \
                patch("backend.agent.weather.fetch_weather") as fetch:
            weather = await get_weather(self.trip, now=self.now)
        fetch.assert_not_called()
        self.assertEqual(weather.source, "fixture")
        self.assertEqual(weather.date, date(2026, 9, 13))
        self.assertEqual(weather.timezone, "Asia/Tokyo")
        self.assertTrue(weather.warnings)
        self.assertTrue(all(hour.time.date() == weather.date for hour in weather.hours))

    async def test_live_adapter_normalizes_provider_shape_and_preserves_unknown(self):
        def forecast(request):
            self.assertEqual(request.url.params["start_date"], "2026-09-13")
            self.assertEqual(request.url.params["end_date"], "2026-09-13")
            self.assertEqual(request.url.params["timezone"], "Asia/Tokyo")
            return httpx.Response(200, json={"hourly": {
                "time": ["2026-09-13T14:00", "2026-09-13T15:00"],
                "precipitation_probability": [90, None],
            }})

        client = httpx.AsyncClient(transport=httpx.MockTransport(forecast))
        with patch("backend.agent.weather.httpx.AsyncClient", return_value=client):
            weather = await fetch_weather(35.7, 139.7, timezone="Asia/Tokyo", day=date(2026, 9, 13))
        self.assertEqual(weather.source, "live")
        self.assertEqual(weather.hours[0].time.isoformat(), "2026-09-13T14:00:00+09:00")
        self.assertEqual(weather.hours[0].precipitation_probability, 90)
        self.assertIsNone(weather.hours[1].precipitation_probability)

    async def test_timeout_falls_back_with_explicit_source(self):
        with patch.dict(os.environ, {"WEATHER_MODE": "live"}), \
                patch("backend.agent.weather.fetch_weather", new_callable=AsyncMock,
                      side_effect=httpx.ReadTimeout("sensitive provider diagnostics")):
            weather = await get_weather(self.trip, now=self.now)
        self.assertEqual(weather.source, "fixture")
        self.assertTrue(any("Open-Meteo" in warning for warning in weather.warnings))
        self.assertNotIn("sensitive", " ".join(weather.warnings))

    async def test_malformed_provider_data_falls_back(self):
        invalid_responses = [
            {},
            {"hourly": {"time": ["2026-09-13T14:00"], "precipitation_probability": []}},
            {"hourly": {"time": ["2026-09-12T14:00"], "precipitation_probability": [90]}},
            {"hourly": {"time": ["2026-09-13T14:00"], "precipitation_probability": [101]}},
            {"hourly": {"time": ["2026-09-13T14:00"], "precipitation_probability": [None]}},
        ]
        for payload in invalid_responses:
            with self.subTest(payload=payload):
                client = httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=payload)))
                with patch.dict(os.environ, {"WEATHER_MODE": "live"}), \
                        patch("backend.agent.weather.httpx.AsyncClient", return_value=client):
                    weather = await get_weather(self.trip, now=self.now)
                self.assertEqual(weather.source, "fixture")

    async def test_missing_fixture_is_unavailable_not_sunny(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"WEATHER_MODE": "mock"}), \
                    patch("backend.agent.weather.FIXTURE_FILE", Path(directory) / "missing.json"):
                weather = await get_weather(self.trip, now=self.now)
        self.assertEqual(weather.source, "unavailable")
        self.assertEqual(weather.hours, [])
        self.assertTrue(weather.warnings)

    async def test_unknown_mode_does_not_call_provider(self):
        with patch.dict(os.environ, {"WEATHER_MODE": "typo"}), \
                patch("backend.agent.weather.fetch_weather") as fetch:
            weather = await get_weather(self.trip, now=self.now)
        fetch.assert_not_called()
        self.assertEqual(weather.source, "unavailable")
