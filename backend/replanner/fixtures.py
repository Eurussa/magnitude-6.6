"""Read-only planning constraints and fallback fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .errors import ReplannerError
from .schemas import (
    BusinessHoursFixture,
    CandidateDefinition,
    CandidateFixture,
    CostFixture,
    FallbackFixture,
    OpeningHours,
    TransportFixture,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True, slots=True)
class PlanningFixtures:
    """Validated, immutable references to B-owned planning data."""

    business_hours: dict[str, OpeningHours]
    candidates: dict[str, CandidateDefinition]
    costs: dict[str, int]
    transport: TransportFixture
    fallback: FallbackFixture

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> "PlanningFixtures":
        try:
            business_hours = BusinessHoursFixture.model_validate_json(
                (data_dir / "business_hours.json").read_bytes()
            )
            candidates = CandidateFixture.model_validate_json(
                (data_dir / "candidate_items.json").read_bytes()
            )
            costs = CostFixture.model_validate_json(
                (data_dir / "activity_costs.json").read_bytes()
            )
            transport = TransportFixture.model_validate_json(
                (data_dir / "transport.json").read_bytes()
            )
            fallback = FallbackFixture.model_validate_json(
                (data_dir / "planning_fallback.json").read_bytes()
            )
        except (OSError, ValidationError) as exc:
            raise ReplannerError("Planning fixtures are unavailable or invalid") from exc

        candidate_map = {item.id: item for item in candidates.items}
        if len(candidate_map) != len(candidates.items):
            raise ReplannerError("Candidate fixture item ids must be unique")
        return cls(
            business_hours=business_hours.items,
            candidates=candidate_map,
            costs=costs.item_cost_jpy,
            transport=transport,
            fallback=fallback,
        )

    def travel_minutes(self, from_item_id: str, to_item_id: str) -> int:
        if from_item_id == to_item_id:
            return 0
        for route in self.transport.routes:
            if {route.from_item_id, route.to_item_id} == {
                from_item_id,
                to_item_id,
            }:
                return route.minutes
        return self.transport.default_minutes
