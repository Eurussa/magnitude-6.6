"""Planning instructions and serialized input for the OpenAI Responses API."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..models import ReplanContext, TripItem
from .fixtures import PlanningFixtures
from .schemas import PlanningRepairFeedback

RAIN_RISK_THRESHOLD = 70.0

PLANNING_INSTRUCTIONS = """\
You are SmartTrip's itinerary replanning engine. Produce exactly three complete,
distinct, multi-day schedule candidates using the supplied structured context and
constraints.

Plan A must use id A and strategy preserve_booking; minimize disruption around
bookings and high-priority activities. Plan B must use id B and strategy
maximize_attractions; retain as many original activities as constraints allow.
Plan C must use id C and strategy relaxed; favor useful slack and lower daily load.

Return only original item ids or ids from trusted_candidates. Omitting an original
item means canceling it. Do not change names, durations, coordinates, priority,
booking, movability, or indoor status: the server restores those trusted fields.
All retained booking=true or movable=false items must remain at their original date
and time. Items completed before context.now must also remain unchanged. Never move
or add an item to a slot before now. Never schedule an item outside the trip date
range, outside business hours, overlapping another item, or without the stated
transport gap.

Feasibility is more important than retaining every item: omit movable originals
when the calendar has no valid slot. The supplied planning_facts already contain
computed end timestamps, fixed items, a dense travel-time matrix, event restrictions,
and high-risk weather hours. Use those facts instead of estimating. For every plan,
sort each date chronologically and verify that each next start is at or after the
previous end plus travel_minutes[previous_id][next_id].

Use the event and hourly weather across the entire trip. A disruption may require
moving a full day and redistributing activities on other dates. For weather events,
every affected outdoor activity in a slot with precipitation probability at least 70
must be moved to a lower-risk slot or omitted. Unknown weather is uncertainty, not sun.
For a delay, do not schedule affected activities inside the blocked interval starting
at now. For a dated closure, move the affected item away from a closed date or omit
it. Keep the three candidates materially different while obeying every hard rule.

On a repair request, accepted_plans have already passed every server-side check.
Reproduce each accepted plan exactly, including title and every item slot. Repair only
the rejected or missing plan ids, using every error as a hard requirement.
"""


def planning_input(
    context: ReplanContext,
    fixtures: PlanningFixtures,
    *,
    validation_feedback: PlanningRepairFeedback | None = None,
) -> str:
    """Serialize all facts the LLM may use; no raw user text is included."""
    payload: dict[str, Any] = {
        "context": context.model_dump(mode="json"),
        "constraints": {
            "business_hours": {
                item_id: hours.model_dump(mode="json")
                for item_id, hours in fixtures.business_hours.items()
            },
            "transport": {
                "routes_are_symmetric": True,
                "travel_minutes": _travel_matrix(context, fixtures),
            },
            "trusted_candidates": [
                candidate.model_dump(mode="json")
                for candidate in fixtures.candidates.values()
            ],
        },
        "planning_facts": _planning_facts(context, fixtures),
    }
    if validation_feedback:
        payload["repair"] = validation_feedback.model_dump(mode="json")
        payload["repair_instruction"] = (
            "Return A, B, and C again. Copy accepted_plans exactly and replace only "
            "rejected or missing plan ids. Correct every listed error."
        )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _planning_facts(
    context: ReplanContext, fixtures: PlanningFixtures
) -> dict[str, Any]:
    timezone = ZoneInfo(context.trip.timezone)
    now = context.now.astimezone(timezone)
    item_constraints: list[dict[str, Any]] = []
    fixed_item_ids: list[str] = []
    for item in context.trip.items:
        start = _item_start(item, timezone)
        end = start + timedelta(minutes=item.duration_minutes)
        fixed_reasons = _fixed_reasons(item, end, now)
        opening_hours = fixtures.business_hours.get(item.id)
        if fixed_reasons:
            fixed_item_ids.append(item.id)
        item_constraints.append(
            {
                "id": item.id,
                "source": "original",
                "original_start_at": start.isoformat(timespec="minutes"),
                "original_end_at": end.isoformat(timespec="minutes"),
                "duration_minutes": item.duration_minutes,
                "opening_hours": opening_hours.model_dump(mode="json")
                if opening_hours
                else None,
                "fixed": bool(fixed_reasons),
                "fixed_reasons": fixed_reasons,
            }
        )
    for candidate in fixtures.candidates.values():
        opening_hours = fixtures.business_hours.get(candidate.id)
        item_constraints.append(
            {
                "id": candidate.id,
                "source": "trusted_candidate",
                "duration_minutes": candidate.duration_minutes,
                "opening_hours": opening_hours.model_dump(mode="json")
                if opening_hours
                else None,
                "fixed": False,
                "fixed_reasons": [],
            }
        )
    return {
        "trip_date_range": {
            "start": context.trip.start_date.isoformat(),
            "end": context.trip.end_date.isoformat(),
            "timezone": context.trip.timezone,
            "now": now.isoformat(timespec="minutes"),
        },
        "fixed_item_ids": fixed_item_ids,
        "item_constraints": item_constraints,
        "event_restrictions": _event_restrictions(context, timezone),
        "high_risk_weather_hours": _high_risk_weather_hours(context, timezone),
    }


def _travel_matrix(
    context: ReplanContext, fixtures: PlanningFixtures
) -> dict[str, dict[str, int]]:
    item_ids = [item.id for item in context.trip.items]
    item_ids.extend(
        item_id for item_id in fixtures.candidates if item_id not in item_ids
    )
    return {
        source: {
            destination: fixtures.travel_minutes(source, destination)
            for destination in item_ids
        }
        for source in item_ids
    }


def _event_restrictions(
    context: ReplanContext, timezone: ZoneInfo
) -> dict[str, Any]:
    event = context.event
    restriction: dict[str, Any] = {
        "event_type": event.event_type,
        "affected_dates": [value.isoformat() for value in event.affected_dates],
        "affected_item_ids": list(event.affected_item_ids),
    }
    if event.event_type == "delay" and event.delay_minutes:
        blocked_from = context.now.astimezone(timezone)
        restriction.update(
            {
                "affected_item_ids": event.affected_item_ids
                or [item.id for item in context.trip.items],
                "forbidden_start_at_or_after": blocked_from.isoformat(
                    timespec="minutes"
                ),
                "forbidden_start_before": (
                    blocked_from + timedelta(minutes=event.delay_minutes)
                ).isoformat(timespec="minutes"),
            }
        )
    elif event.event_type == "weather":
        target_ids = list(event.affected_item_ids)
        if not target_ids:
            affected_dates = set(event.affected_dates)
            target_ids = [
                item.id
                for item in context.trip.items
                if not item.indoor and item.scheduled_date in affected_dates
            ]
        restriction["affected_item_ids"] = target_ids
        restriction["precipitation_probability_must_be_below"] = (
            RAIN_RISK_THRESHOLD
        )
    return restriction


def _high_risk_weather_hours(
    context: ReplanContext, timezone: ZoneInfo
) -> list[dict[str, Any]]:
    return [
        {
            "start_at": hour.time.astimezone(timezone).isoformat(timespec="minutes"),
            "precipitation_probability": hour.precipitation_probability,
        }
        for hour in context.weather.hours
        if hour.precipitation_probability is not None
        and hour.precipitation_probability >= RAIN_RISK_THRESHOLD
    ]


def _fixed_reasons(
    item: TripItem, end: datetime, now: datetime
) -> list[str]:
    reasons: list[str] = []
    if item.booking:
        reasons.append("booking")
    if not item.movable:
        reasons.append("not_movable")
    if end <= now:
        reasons.append("completed")
    return reasons


def _item_start(item: TripItem, timezone: ZoneInfo) -> datetime:
    return datetime.combine(
        item.scheduled_date,
        time.fromisoformat(item.start_time),
        tzinfo=timezone,
    )
