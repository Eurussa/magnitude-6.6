"""Backend A owns preference persistence; Backend B owns scoring.

These helpers accept trusted server data only. The future selections handler
must validate stored plans and deduplicate choices before updating weights.
"""
from ..models import Preference
from .runtime import RuntimeStore


def get_preferences(store: RuntimeStore) -> Preference:
    return store.get_preferences()


def save_preferences(store: RuntimeStore, preferences: Preference) -> None:
    store.save_preferences(preferences)
