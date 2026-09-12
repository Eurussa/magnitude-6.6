import unittest
from datetime import date, datetime

from backend.agent.parser import parse_event
from backend.agent.runtime import DATA_DIR
from backend.models import Trip


class ParserTest(unittest.TestCase):
    def setUp(self):
        self.trip = Trip.model_validate_json((DATA_DIR / "trip.json").read_bytes())
        self.now = datetime.fromisoformat("2026-09-12T09:00:00+09:00")

    def parse(self, message: str):
        return parse_event(message, trip=self.trip, now=self.now)

    def test_recognizes_demo_events(self):
        delayed = self.parse("睡過頭兩小時")
        rainy = self.parse("後天迪士尼會下大雨")
        closed = self.parse("博物館今天休館")

        self.assertEqual((delayed.event_type, delayed.delay_minutes), ("delay", 120))
        self.assertEqual(rainy.event_type, "weather")
        self.assertEqual(rainy.affected_item_ids, ["item-9"])
        self.assertEqual(rainy.affected_dates, [date(2026, 9, 14)])
        self.assertEqual(closed.event_type, "closure")
        self.assertEqual(closed.affected_item_ids, ["item-2"])
        self.assertEqual(closed.affected_dates, [date(2026, 9, 12)])

    def test_recognizes_english_delay(self):
        event = self.parse("We are delayed 45 minutes")

        self.assertEqual((event.event_type, event.delay_minutes), ("delay", 45))
        self.assertEqual(event.affected_dates, [date(2026, 9, 12)])

    def test_delay_can_span_days(self):
        event = self.parse("航班延誤兩天")

        self.assertEqual((event.event_type, event.delay_minutes), ("delay", 2880))

    def test_explicit_date_and_item_id_are_resolved_locally(self):
        event = self.parse("2026-09-13 的 item-8 關閉")

        self.assertEqual(event.event_type, "closure")
        self.assertEqual(event.affected_item_ids, ["item-8"])
        self.assertEqual(event.affected_dates, [date(2026, 9, 13)])

    def test_dates_outside_trip_are_not_forwarded(self):
        event = self.parse("2026-09-20 下雨")

        self.assertEqual(event.event_type, "weather")
        self.assertEqual(event.affected_dates, [date(2026, 9, 12)])

    def test_unknown_text_stays_conservative(self):
        event = self.parse("想換個行程")

        self.assertEqual(event.event_type, "unknown")
        self.assertEqual(event.delay_minutes, 0)
        self.assertEqual(event.affected_item_ids, [])
        self.assertEqual(event.affected_dates, [])


if __name__ == "__main__":
    unittest.main()
