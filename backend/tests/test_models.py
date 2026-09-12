import unittest
from datetime import date, datetime, timedelta

from pydantic import ValidationError

from backend.agent.runtime import DATA_DIR
from backend.models import (
    Event,
    PlanChange,
    PlanningResult,
    Preference,
    PreferenceWeights,
    Trip,
    WeatherContext,
    WeatherHour,
)
from backend.replanner.planner import candidate_plans


class TripModelTest(unittest.TestCase):
    def setUp(self):
        self.trip = Trip.model_validate_json((DATA_DIR / "trip.json").read_bytes())
        self.preferences = Preference(
            user_id="demo-user",
            weights=PreferenceWeights(
                preserve_booking=1,
                maximize_attractions=1,
                relaxed=1,
            ),
            selection_count=0,
        )

    def test_trip_contains_multiple_scheduled_dates(self):
        self.assertEqual(
            {item.scheduled_date for item in self.trip.items},
            {self.trip.start_date + timedelta(days=offset) for offset in range(3)},
        )

    def test_item_date_must_be_inside_trip_range(self):
        payload = self.trip.model_dump(mode="json")
        payload["items"][0]["scheduled_date"] = "2026-09-15"

        with self.assertRaises(ValidationError):
            Trip.model_validate(payload)

    def test_trip_requires_version_and_rejects_unknown_fields(self):
        missing_version = self.trip.model_dump(mode="json")
        missing_version.pop("version")
        with self.assertRaises(ValidationError):
            Trip.model_validate(missing_version)

        unknown_field = self.trip.model_dump(mode="json")
        unknown_field["days"] = []
        with self.assertRaises(ValidationError):
            Trip.model_validate(unknown_field)

    def test_trip_item_ids_must_be_unique(self):
        payload = self.trip.model_dump(mode="json")
        payload["items"][1]["id"] = payload["items"][0]["id"]

        with self.assertRaises(ValidationError):
            Trip.model_validate(payload)

    def test_start_time_uses_twenty_four_hour_hh_mm(self):
        payload = self.trip.model_dump(mode="json")
        payload["items"][0]["start_time"] = "25:00"

        with self.assertRaises(ValidationError):
            Trip.model_validate(payload)

    def test_event_can_reference_multiple_dates_and_items(self):
        event = Event(
            event_type="weather",
            delay_minutes=0,
            affected_item_ids=["item-6", "item-7", "item-8", "item-9"],
            affected_dates=[date(2026, 9, 13), date(2026, 9, 14)],
            summary="迪士尼雨天，交換兩天行程",
        )

        self.assertEqual(len(event.affected_item_ids), 4)
        self.assertEqual(len(event.affected_dates), 2)

    def test_delay_can_span_multiple_days(self):
        event = Event(
            event_type="delay",
            delay_minutes=2 * 24 * 60,
            affected_item_ids=[],
            affected_dates=[date(2026, 9, 12), date(2026, 9, 13)],
            summary="航班延誤兩天",
        )

        self.assertEqual(event.delay_minutes, 2880)

    def test_weather_hours_must_stay_inside_multi_day_range(self):
        with self.assertRaises(ValidationError):
            WeatherContext(
                source="live",
                start_date=date(2026, 9, 13),
                end_date=date(2026, 9, 14),
                timezone="Asia/Tokyo",
                hours=[WeatherHour(
                    time=datetime.fromisoformat("2026-09-15T09:00:00+09:00"),
                    precipitation_probability=10,
                )],
                warnings=[],
            )

    def test_placeholder_plans_preserve_all_trip_dates(self):
        weather = WeatherContext(
            source="fixture",
            start_date=self.trip.start_date,
            end_date=self.trip.end_date,
            timezone=self.trip.timezone,
            hours=[],
            warnings=[],
        )
        plans = candidate_plans(
            self.trip,
            event=Event(
                event_type="unknown",
                delay_minutes=0,
                affected_item_ids=[],
                affected_dates=[],
                summary="test",
            ),
            weather=weather,
            preferences=self.preferences,
            now=datetime.fromisoformat("2026-09-12T09:00:00+09:00"),
        )
        expected_dates = {item.scheduled_date for item in self.trip.items}
        for plan in plans:
            self.assertEqual({item.scheduled_date for item in plan.items}, expected_dates)

        ready_plans = [plan.model_copy(update={"feasible": True}) for plan in plans]
        result = PlanningResult(
            source="fixture",
            plans=ready_plans,
            recommended_plan_id="A",
            warnings=[],
        )
        self.assertEqual(result.recommended_plan_id, "A")

    def test_plan_change_action_controls_before_and_after_fields(self):
        change = PlanChange(
            item_id="item-9",
            action="move",
            from_date=date(2026, 9, 14),
            from_start_time="09:00",
            to_date=date(2026, 9, 13),
            to_start_time="09:00",
            reason="避開迪士尼雨天",
        )
        self.assertEqual(change.action, "move")

        with self.assertRaises(ValidationError):
            PlanChange(
                item_id="item-9",
                action="move",
                from_date=date(2026, 9, 14),
                from_start_time="09:00",
                to_date=None,
                to_start_time=None,
                reason="缺少新時間",
            )

    def test_planning_result_requires_fixed_strategies_and_feasible_recommendation(self):
        weather = WeatherContext(
            source="fixture",
            start_date=self.trip.start_date,
            end_date=self.trip.end_date,
            timezone=self.trip.timezone,
            hours=[],
            warnings=[],
        )
        plans = candidate_plans(
            self.trip,
            event=Event(
                event_type="unknown",
                delay_minutes=0,
                affected_item_ids=[],
                affected_dates=[],
                summary="test",
            ),
            weather=weather,
            preferences=self.preferences,
            now=datetime.fromisoformat("2026-09-12T09:00:00+09:00"),
        )

        with self.assertRaises(ValidationError):
            PlanningResult(
                source="fixture",
                plans=plans,
                recommended_plan_id="A",
                warnings=[],
            )

        feasible = [plan.model_copy(update={"feasible": plan.id != "A"}) for plan in plans]
        with self.assertRaises(ValidationError):
            PlanningResult(
                source="fixture",
                plans=feasible,
                recommended_plan_id="A",
                warnings=[],
            )


if __name__ == "__main__":
    unittest.main()
