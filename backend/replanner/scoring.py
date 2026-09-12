"""Derive comparable plan facts and apply deterministic preference ranking."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..models import Plan, PlanFeatures, PlanId, Preference, Trip, TripItem
from .fixtures import PlanningFixtures

TIE_BREAK_ORDER: dict[PlanId, int] = {"A": 0, "B": 1, "C": 2}


def calculate_impacts(
    trip: Trip,
    items: list[TripItem],
    fixtures: PlanningFixtures,
) -> tuple[int, int]:
    """Return deterministic fixture-based travel and activity-cost deltas."""
    original_travel = _total_travel_minutes(trip.items, fixtures)
    planned_travel = _total_travel_minutes(items, fixtures)
    original_cost = sum(fixtures.costs.get(item.id, 0) for item in trip.items)
    planned_cost = sum(fixtures.costs.get(item.id, 0) for item in items)
    return planned_travel - original_travel, planned_cost - original_cost


def calculate_features(
    trip: Trip,
    items: list[TripItem],
    fixtures: PlanningFixtures,
) -> PlanFeatures:
    """Compute normalized, factual inputs used by preference scoring."""
    planned = {item.id: item for item in items}
    protected = [item for item in trip.items if item.booking or item.priority >= 4]
    protected_total = sum(item.priority for item in protected)
    protected_unchanged = sum(
        item.priority
        for item in protected
        if item.id in planned and _same_slot(item, planned[item.id])
    )
    preserve_booking = (
        protected_unchanged / protected_total if protected_total else 1.0
    )

    retained = sum(1 for item in trip.items if item.id in planned)
    maximize_attractions = retained / len(trip.items) if trip.items else 1.0

    day_count = (trip.end_date - trip.start_date).days + 1
    daily_items: dict[date, list[TripItem]] = defaultdict(list)
    for item in items:
        daily_items[item.scheduled_date].append(item)
    daily_loads: list[int] = []
    for day_items in daily_items.values():
        ordered = sorted(day_items, key=lambda item: (item.start_time, item.id))
        activity_minutes = sum(item.duration_minutes for item in ordered)
        travel_minutes = sum(
            fixtures.travel_minutes(previous.id, current.id)
            for previous, current in zip(ordered, ordered[1:])
        )
        daily_loads.append(activity_minutes + travel_minutes)
    average_load = sum(min(minutes / 600, 1.0) for minutes in daily_loads)
    average_load /= day_count
    relaxed = 1.0 - average_load

    return PlanFeatures(
        preserve_booking=round(preserve_booking, 6),
        maximize_attractions=round(maximize_attractions, 6),
        relaxed=round(max(0.0, min(1.0, relaxed)), 6),
    )


def score_plan(plan: Plan, preference: Preference) -> float:
    """Calculate the internal score; it is intentionally not part of the API."""
    weights = preference.weights
    return (
        weights.preserve_booking * plan.features.preserve_booking
        + weights.maximize_attractions * plan.features.maximize_attractions
        + weights.relaxed * plan.features.relaxed
    )


def rank_plans(plans: list[Plan], preference: Preference) -> tuple[list[Plan], PlanId | None]:
    """Sort feasible plans first by score and use A/B/C as a stable tie-break."""
    ordered = sorted(
        plans,
        key=lambda plan: (
            not plan.feasible,
            -score_plan(plan, preference) if plan.feasible else 0.0,
            TIE_BREAK_ORDER[plan.id],
        ),
    )
    recommended = next((plan.id for plan in ordered if plan.feasible), None)
    return ordered, recommended


def _total_travel_minutes(
    items: list[TripItem], fixtures: PlanningFixtures
) -> int:
    by_date: dict[date, list[TripItem]] = defaultdict(list)
    for item in items:
        by_date[item.scheduled_date].append(item)
    total = 0
    for day_items in by_date.values():
        ordered = sorted(day_items, key=lambda item: (item.start_time, item.id))
        total += sum(
            fixtures.travel_minutes(previous.id, current.id)
            for previous, current in zip(ordered, ordered[1:])
        )
    return total


def _same_slot(left: TripItem, right: TripItem) -> bool:
    return (
        left.scheduled_date == right.scheduled_date
        and left.start_time == right.start_time
    )
