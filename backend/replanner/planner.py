"""Backend B's LLM-driven replanning integration point."""
from datetime import datetime

from ..models import Event, Plan, PlanFeatures, Preference, Trip, WeatherContext


def candidate_plans(
    trip: Trip, *, event: Event, weather: WeatherContext,
    preferences: Preference, now: datetime,
) -> list[Plan]:
    """Return full multi-day placeholder candidates using the replanner interface.

    Context is wired but deliberately not applied by this placeholder. B will call
    the planning LLM with every dated item and the weather range, validate its
    structured plans, compute impact/features, and apply deterministic preference
    ranking. Runtime and weather I/O stay with A.
    """
    strategies = [
        ("A", "preserve_booking", "保留預約"),
        ("B", "maximize_attractions", "保留最多景點"),
        ("C", "relaxed", "最輕鬆"),
    ]
    return [
        Plan(
            id=plan_id,
            strategy=strategy,
            title=title,
            items=[item.model_copy(deep=True) for item in trip.items],
            feasible=False,
            changes=[],
            additional_travel_minutes=0,
            additional_cost_jpy=0,
            booking_warnings=[],
            features=PlanFeatures(
                preserve_booking=0,
                maximize_attractions=0,
                relaxed=0,
            ),
            explanation="",
        )
        for plan_id, strategy, title in strategies
    ]
