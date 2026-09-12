"""Backend A owns preference updates and persistence; Backend B owns scoring.

These helpers accept trusted server data only. The future selections handler
must validate stored plans and deduplicate choices before updating weights.
"""
from typing import Literal

from ..models import Preference
from .runtime import RuntimeStore

PlanStrategy = Literal["preserve_booking", "maximize_attractions", "relaxed"]


def get_preferences(store: RuntimeStore) -> Preference:
    return store.get_preferences()


def save_preferences(store: RuntimeStore, preferences: Preference) -> None:
    store.save_preferences(preferences)


def apply_strategy_choice(preferences: Preference, strategy: PlanStrategy) -> Preference:
    """Return updated preferences for one already-validated server-side selection."""
    updated = preferences.model_copy(deep=True)
    current = getattr(updated.weights, strategy)
    setattr(updated.weights, strategy, current + 1)
    updated.selection_count += 1
    return Preference.model_validate(updated.model_dump())


def preference_insight(
    preferences: Preference, strategy: PlanStrategy | None = None,
) -> str:
    """Explain only the persisted preference evidence; do not overstate learning."""
    labels = {
        "preserve_booking": "保留預約",
        "maximize_attractions": "保留較多景點",
        "relaxed": "較輕鬆的節奏",
    }
    if preferences.selection_count == 0:
        return "尚無過往選擇；目前依方案條件排序。"
    if strategy is None:
        return f"已記錄你先前 {preferences.selection_count} 次選擇；等待可行方案完成排序。"
    return f"根據你先前 {preferences.selection_count} 次選擇，本次優先考量{labels[strategy]}。"
