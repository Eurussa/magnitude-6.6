import unittest

from backend.agent.preference import apply_strategy_choice, preference_insight
from backend.models import Preference, PreferenceWeights


class PreferenceTest(unittest.TestCase):
    def preference(self) -> Preference:
        return Preference(
            user_id="demo-user",
            weights=PreferenceWeights(
                preserve_booking=1,
                maximize_attractions=1,
                relaxed=1,
            ),
            selection_count=0,
        )

    def test_choice_updates_only_selected_strategy_on_copy(self):
        original = self.preference()

        updated = apply_strategy_choice(original, "preserve_booking")

        self.assertEqual(original.selection_count, 0)
        self.assertEqual(original.weights.preserve_booking, 1)
        self.assertEqual(updated.selection_count, 1)
        self.assertEqual(updated.weights.preserve_booking, 2)
        self.assertEqual(updated.weights.maximize_attractions, 1)
        self.assertEqual(updated.weights.relaxed, 1)

    def test_insight_distinguishes_no_history_from_prior_choices(self):
        self.assertIn("尚無過往選擇", preference_insight(self.preference(), "relaxed"))
        learned = apply_strategy_choice(self.preference(), "relaxed")
        insight = preference_insight(learned, "relaxed")
        self.assertIn("先前 1 次選擇", insight)
        self.assertIn("較輕鬆", insight)


if __name__ == "__main__":
    unittest.main()
