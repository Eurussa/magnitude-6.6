import json
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from backend.agent.preference import get_preferences, save_preferences
from backend.agent.runtime import DATA_DIR, RuntimeStorageError, RuntimeStore
from backend.models import Preference, Trip


class RuntimeStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.seed_dir = root / "seeds"
        self.seed_dir.mkdir()
        self.seed_bytes = {}
        for name in ("trip.json", "preferences.json"):
            shutil.copyfile(DATA_DIR / name, self.seed_dir / name)
            self.seed_bytes[name] = (self.seed_dir / name).read_bytes()
        self.runtime_dir = root / "runtime"
        self.store = self.fresh_store()

    def fresh_store(self):
        return RuntimeStore(self.runtime_dir, seed_dir=self.seed_dir)

    def changed_trip(self):
        trip = self.store.get_trip()
        trip.items[0].name = "更新後的行程"
        return trip

    def changed_preferences(self):
        preferences = self.store.get_preferences()
        preferences.weights.relaxed = 1.5
        preferences.selection_count = 1
        return preferences

    def test_initialization_is_lazy_and_first_read_copies_seeds(self):
        self.assertFalse(self.runtime_dir.exists())

        state = self.store.load_state()

        self.assertEqual(state.schema_version, 2)
        self.assertEqual(state.trip, Trip.model_validate_json(self.seed_bytes["trip.json"]))
        self.assertEqual(state.preferences,
                         Preference.model_validate_json(self.seed_bytes["preferences.json"]))
        self.assertEqual(self.fresh_store().load_state(), state)
        self.assertTrue(self.store.path.is_file())

    def test_preferences_and_trip_survive_fresh_store_without_changing_seeds(self):
        trip = self.changed_trip()
        preferences = self.changed_preferences()

        self.store.save_trip(trip)
        save_preferences(self.store, preferences)

        reopened = self.fresh_store()
        self.assertEqual(reopened.get_trip(), trip)
        self.assertEqual(get_preferences(reopened), preferences)
        for name, original in self.seed_bytes.items():
            self.assertEqual((self.seed_dir / name).read_bytes(), original)

    def test_save_state_persists_trip_and_preferences_together(self):
        trip = self.changed_trip()
        preferences = self.changed_preferences()

        self.store.save_state(trip, preferences)

        state = self.fresh_store().load_state()
        self.assertEqual(state.trip, trip)
        self.assertEqual(state.preferences, preferences)

    def test_read_result_does_not_persist_changes_without_save(self):
        original = self.store.load_state()
        changed = self.store.load_state()
        changed.trip.items.clear()
        changed.preferences.selection_count = 99

        self.assertEqual(self.store.load_state(), original)

    def test_invalid_or_unsupported_state_is_preserved_on_reads_and_writes(self):
        original = self.store.load_state()
        valid_data = original.model_dump(mode="json")
        unsupported = dict(valid_data, schema_version=3)
        invalid_preferences = dict(valid_data, preferences={"selection_count": -1})
        invalid_timezone = dict(valid_data, trip=dict(valid_data["trip"], timezone="Bad/Timezone"))
        invalid_dates = dict(
            valid_data,
            trip=dict(valid_data["trip"], end_date="2026-09-01"),
        )
        cases = (
            b"{broken json",
            b"{}",
            json.dumps(unsupported).encode(),
            json.dumps(invalid_preferences).encode(),
            json.dumps(invalid_timezone).encode(),
            json.dumps(invalid_dates).encode(),
        )
        operations = (
            self.store.load_state,
            lambda: self.store.save_trip(original.trip),
            lambda: self.store.save_preferences(original.preferences),
            lambda: self.store.save_state(original.trip, original.preferences),
        )

        for contents in cases:
            for operation in operations:
                with self.subTest(contents=contents, operation=operation):
                    self.store.path.write_bytes(contents)
                    with self.assertRaises(RuntimeStorageError):
                        operation()
                    self.assertEqual(self.store.path.read_bytes(), contents)

    def test_invalid_seed_does_not_create_runtime_state_or_reset_seed(self):
        contents = b'{"selection_count": -1}'
        seed_path = self.seed_dir / "preferences.json"
        seed_path.write_bytes(contents)

        with self.assertRaises(RuntimeStorageError):
            self.store.load_state()

        self.assertFalse(self.store.path.exists())
        self.assertEqual(seed_path.read_bytes(), contents)

    def test_failed_atomic_replace_keeps_previous_complete_state(self):
        previous = self.store.load_state()
        previous_bytes = self.store.path.read_bytes()
        trip = self.changed_trip()
        preferences = self.changed_preferences()

        with patch("backend.agent.runtime.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(RuntimeStorageError):
                self.store.save_state(trip, preferences)

        self.assertEqual(self.store.path.read_bytes(), previous_bytes)
        self.assertEqual(self.fresh_store().load_state(), previous)

    def test_invalid_mutated_model_cannot_replace_saved_state(self):
        previous = self.store.load_state()
        preferences = self.store.get_preferences()
        preferences.weights.relaxed = float("nan")

        with self.assertRaises(RuntimeStorageError):
            self.store.save_preferences(preferences)

        self.assertEqual(self.fresh_store().load_state(), previous)

    def test_single_store_concurrent_trip_and_preference_saves_preserve_both(self):
        trip = self.store.get_trip()
        preferences = self.store.get_preferences()
        start = Barrier(2)

        def update_trip():
            start.wait(timeout=5)
            for index in range(20):
                trip.items[0].name = f"行程 {index}"
                self.store.save_trip(trip)

        def update_preferences():
            start.wait(timeout=5)
            for index in range(20):
                preferences.selection_count = index + 1
                self.store.save_preferences(preferences)

        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = (pool.submit(update_trip), pool.submit(update_preferences))
            for task in tasks:
                task.result(timeout=10)

        state = self.fresh_store().load_state()
        self.assertEqual(state.trip, trip)
        self.assertEqual(state.preferences, preferences)


if __name__ == "__main__":
    unittest.main()
