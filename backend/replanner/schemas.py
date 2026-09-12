"""Internal structured-output and fixture schemas owned by Backend B."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import LOCAL_TIME_PATTERN, PlanId, PlanStrategy


class InternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScheduledItemDraft(InternalModel):
    """The only item fields the planning LLM is allowed to choose."""

    id: str = Field(min_length=1)
    scheduled_date: date
    start_time: str = Field(pattern=LOCAL_TIME_PATTERN)


class PlanDraft(InternalModel):
    id: PlanId
    strategy: PlanStrategy
    title: str = Field(min_length=1)
    items: list[ScheduledItemDraft]


class PlanningDraft(InternalModel):
    plans: list[PlanDraft] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def fixed_plan_ids_and_strategies(self) -> Self:
        expected: dict[PlanId, PlanStrategy] = {
            "A": "preserve_booking",
            "B": "maximize_attractions",
            "C": "relaxed",
        }
        ids = [plan.id for plan in self.plans]
        if set(ids) != set(expected) or len(ids) != len(set(ids)):
            raise ValueError("draft must contain exactly one plan for A, B, and C")
        if any(plan.strategy != expected[plan.id] for plan in self.plans):
            raise ValueError("draft plan id must use its fixed strategy")
        return self


class PlanningRepairFeedback(InternalModel):
    """Validated schedules and actionable errors supplied to a retry."""

    accepted_plans: list[PlanDraft]
    errors: list[str] = Field(min_length=1)


class OpeningHours(InternalModel):
    open_time: str = Field(pattern=LOCAL_TIME_PATTERN)
    close_time: str = Field(pattern=LOCAL_TIME_PATTERN)
    last_entry_time: str | None = Field(pattern=LOCAL_TIME_PATTERN)


class BusinessHoursFixture(InternalModel):
    items: dict[str, OpeningHours]


class TransportRoute(InternalModel):
    from_item_id: str
    to_item_id: str
    minutes: int = Field(ge=0)


class TransportFixture(InternalModel):
    default_minutes: int = Field(ge=0)
    routes: list[TransportRoute]


class CandidateDefinition(InternalModel):
    id: str
    name: str
    duration_minutes: int = Field(gt=0)
    latitude: float
    longitude: float
    priority: int = Field(ge=1, le=5)
    booking: Literal[False]
    movable: Literal[True]
    indoor: bool
    cost_jpy: int = Field(ge=0)


class CandidateFixture(InternalModel):
    items: list[CandidateDefinition]


class CostFixture(InternalModel):
    item_cost_jpy: dict[str, int]


class FallbackPlanTemplate(InternalModel):
    id: PlanId
    strategy: PlanStrategy
    title: str
    moves: dict[str, tuple[date, str]]
    cancels: list[str]
    adds: list[ScheduledItemDraft]


class FallbackScenario(InternalModel):
    trip_id: str
    start_date: date
    end_date: date
    event_type: Literal["weather", "delay", "closure"]
    plans: list[FallbackPlanTemplate] = Field(min_length=3, max_length=3)


class FallbackFixture(InternalModel):
    scenarios: list[FallbackScenario]
