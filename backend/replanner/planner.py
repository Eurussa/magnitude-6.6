"""Backend B: deterministic scheduling belongs here, never in the LLM parser."""
from datetime import datetime

from ..models import Event, Plan, Preference, Trip, WeatherContext


def candidate_plans(
    trip: Trip, *, event: Event, weather: WeatherContext,
    preferences: Preference, now: datetime,
) -> list[Plan]:
    """Contract for B: consume context, never read runtime files or call providers.

    Context is wired but deliberately not applied by this placeholder. B will
    implement candidates, feasibility, impact and deterministic preference ranking.
    """
    strategies = [("preserve_booking", "保留預約"),
                  ("maximize_attractions", "保留最多景點"), ("relaxed", "最輕鬆")]
    return [Plan(id=chr(65 + i), strategy=strategy, title=title,
                 items=[item.model_copy(deep=True) for item in trip.items])
            for i, (strategy, title) in enumerate(strategies)]
