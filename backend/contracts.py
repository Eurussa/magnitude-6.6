from typing import Protocol

from .models import PlanningResult, ReplanContext


class Replanner(Protocol):
    """Stable orchestration boundary implemented by Backend B."""

    async def generate_plans(self, context: ReplanContext, /) -> PlanningResult:
        """Generate, validate, rank, and return the three planning strategies."""
        ...
