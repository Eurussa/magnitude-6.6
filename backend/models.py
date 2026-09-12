from datetime import date
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

LOCAL_TIME_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"
PlanId = Literal["A", "B", "C"]
PlanStrategy = Literal["preserve_booking", "maximize_attractions", "relaxed"]
PlanningSource = Literal["live", "fixture"]
ReplanPlanningSource = Literal["live", "fixture", "unavailable"]
PlanChangeAction = Literal["keep", "move", "cancel", "add"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ContractModel):
    status: Literal["ok"]


class TripItem(ContractModel):
    id: str
    name: str
    scheduled_date: date
    start_time: str = Field(pattern=LOCAL_TIME_PATTERN)
    duration_minutes: int = Field(gt=0)
    latitude: float
    longitude: float
    priority: int = Field(ge=1, le=5)
    booking: bool
    movable: bool
    indoor: bool


class Trip(ContractModel):
    id: str
    version: int = Field(ge=1)
    city: str
    timezone: str
    start_date: date
    end_date: date
    items: list[TripItem]

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def valid_schedule(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        item_ids = [item.id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("trip item ids must be unique")
        if any(
            not self.start_date <= item.scheduled_date <= self.end_date
            for item in self.items
        ):
            raise ValueError("trip item date must be within the trip date range")
        return self


class Event(ContractModel):
    event_type: Literal["weather", "delay", "closure", "unknown"]
    delay_minutes: int = Field(ge=0)
    affected_item_ids: list[str]
    affected_dates: list[date]
    summary: str


class PreferenceWeights(ContractModel):
    preserve_booking: float = Field(ge=0, allow_inf_nan=False)
    maximize_attractions: float = Field(ge=0, allow_inf_nan=False)
    relaxed: float = Field(ge=0, allow_inf_nan=False)


class Preference(ContractModel):
    user_id: Literal["demo-user"]
    weights: PreferenceWeights
    selection_count: int = Field(ge=0)


class WeatherHour(ContractModel):
    time: AwareDatetime
    precipitation_probability: float | None = Field(ge=0, le=100)


class WeatherContext(ContractModel):
    source: Literal["live", "fixture", "unavailable"]
    start_date: date
    end_date: date
    timezone: str
    hours: list[WeatherHour]
    warnings: list[str]

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("weather end_date must not be earlier than start_date")
        if any(
            not self.start_date <= hour.time.date() <= self.end_date
            for hour in self.hours
        ):
            raise ValueError("weather hour must be within the requested date range")
        return self


class ReplanContext(ContractModel):
    trip: Trip
    event: Event
    weather: WeatherContext
    preferences: Preference
    now: AwareDatetime


class ReplanRequest(ContractModel):
    trip_id: Literal["tokyo-demo"] = "tokyo-demo"
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    now: AwareDatetime | None = None


class PlanFeatures(ContractModel):
    preserve_booking: float = Field(ge=0, le=1, allow_inf_nan=False)
    maximize_attractions: float = Field(ge=0, le=1, allow_inf_nan=False)
    relaxed: float = Field(ge=0, le=1, allow_inf_nan=False)


class PlanChange(ContractModel):
    item_id: str
    action: PlanChangeAction
    from_date: date | None
    from_start_time: str | None = Field(pattern=LOCAL_TIME_PATTERN)
    to_date: date | None
    to_start_time: str | None = Field(pattern=LOCAL_TIME_PATTERN)
    reason: str = Field(min_length=1, pattern=r"\S")

    @model_validator(mode="after")
    def valid_transition(self) -> Self:
        before = (self.from_date, self.from_start_time)
        after = (self.to_date, self.to_start_time)
        has_before = all(value is not None for value in before)
        has_after = all(value is not None for value in after)

        if self.action == "keep" and (not has_before or not has_after or before != after):
            raise ValueError("keep requires identical from and to date/time")
        if self.action == "move" and (not has_before or not has_after or before == after):
            raise ValueError("move requires different, complete from and to date/time")
        if self.action == "cancel" and (
            not has_before or any(value is not None for value in after)
        ):
            raise ValueError("cancel requires only a complete from date/time")
        if self.action == "add" and (any(value is not None for value in before) or not has_after):
            raise ValueError("add requires only a complete to date/time")
        return self


class Plan(ContractModel):
    id: PlanId
    strategy: PlanStrategy
    title: str
    items: list[TripItem]
    feasible: bool
    changes: list[PlanChange]
    additional_travel_minutes: int
    additional_cost_jpy: int
    booking_warnings: list[str]
    features: PlanFeatures
    explanation: str

    @model_validator(mode="after")
    def unique_item_ids(self) -> Self:
        item_ids = [item.id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("plan item ids must be unique")
        return self


def _validate_plan_set(
    plans: list[Plan],
    recommended_plan_id: PlanId | None,
    *,
    require_recommendation: bool,
) -> set[PlanId]:
    expected_strategies: dict[PlanId, PlanStrategy] = {
        "A": "preserve_booking",
        "B": "maximize_attractions",
        "C": "relaxed",
    }
    plan_ids = [plan.id for plan in plans]
    if len(plan_ids) != len(set(plan_ids)):
        raise ValueError("plan ids must be unique")
    if set(plan_ids) != set(expected_strategies):
        raise ValueError("plans must contain exactly ids A, B, and C")
    if any(plan.strategy != expected_strategies[plan.id] for plan in plans):
        raise ValueError("plan id must use its fixed strategy")

    feasible_ids = {plan.id for plan in plans if plan.feasible}
    if require_recommendation and feasible_ids and recommended_plan_id is None:
        raise ValueError("recommended_plan_id is required when a plan is feasible")
    if recommended_plan_id is not None and recommended_plan_id not in feasible_ids:
        raise ValueError("recommended_plan_id must reference a feasible returned plan")
    return feasible_ids


class PlanningResult(ContractModel):
    source: PlanningSource
    plans: list[Plan] = Field(min_length=3, max_length=3)
    recommended_plan_id: PlanId | None
    warnings: list[str]

    @model_validator(mode="after")
    def valid_plans_and_recommendation(self) -> Self:
        _validate_plan_set(
            self.plans,
            self.recommended_plan_id,
            require_recommendation=True,
        )
        return self


class ReplanResponse(ContractModel):
    status: Literal["placeholder", "ready"]
    replan_id: UUID | None
    planning_source: ReplanPlanningSource
    event: Event
    weather: WeatherContext
    preferences: Preference
    plans: list[Plan] = Field(min_length=3, max_length=3)
    recommended_plan_id: PlanId | None
    preference_insight: str | None
    warnings: list[str]

    @model_validator(mode="after")
    def valid_status_and_recommendation(self) -> Self:
        feasible_ids = _validate_plan_set(
            self.plans,
            self.recommended_plan_id,
            require_recommendation=self.status == "ready",
        )
        if self.status == "ready":
            if self.replan_id is None:
                raise ValueError("ready response requires replan_id")
            if self.planning_source == "unavailable":
                raise ValueError("ready response requires an available planning source")
            if feasible_ids and self.recommended_plan_id is None:
                raise ValueError("ready response requires a recommendation when a plan is feasible")
        elif (
            self.replan_id is not None
            or self.planning_source != "unavailable"
            or feasible_ids
        ):
            raise ValueError("placeholder response cannot expose a selectable replan")
        return self


class ReplanSnapshot(ContractModel):
    replan_id: UUID
    trip_id: str
    trip_version: int = Field(ge=1)
    planning_source: PlanningSource
    plans: list[Plan] = Field(min_length=3, max_length=3)
    recommended_plan_id: PlanId | None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def recommendation_exists(self) -> Self:
        _validate_plan_set(
            self.plans,
            self.recommended_plan_id,
            require_recommendation=True,
        )
        return self


class SelectionRequest(ContractModel):
    replan_id: UUID
    plan_id: PlanId


class SelectionRecord(ContractModel):
    replan_id: UUID
    plan_id: PlanId
    created_at: AwareDatetime


class SelectionResponse(ContractModel):
    selection: SelectionRecord
    trip: Trip
    preferences: Preference


class ErrorResponse(ContractModel):
    detail: str
