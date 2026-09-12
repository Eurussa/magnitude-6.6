"""Materialize LLM schedules and enforce deterministic trip constraints."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..models import PlanChange, ReplanContext, TripItem
from .errors import PlanValidationError
from .fixtures import PlanningFixtures
from .schemas import PlanDraft, ScheduledItemDraft

RAIN_RISK_THRESHOLD = 70.0


def validate_context(context: ReplanContext) -> None:
    """Validate cross-model references before spending a provider request."""
    trip_ids = {item.id for item in context.trip.items}
    unknown_ids = set(context.event.affected_item_ids) - trip_ids
    if unknown_ids:
        raise PlanValidationError("Event references unknown trip item ids")
    if any(
        not context.trip.start_date <= affected <= context.trip.end_date
        for affected in context.event.affected_dates
    ):
        raise PlanValidationError("Event affected date is outside the trip range")
    if context.weather.timezone != context.trip.timezone:
        raise PlanValidationError("Weather and trip timezones must match")
    if (
        context.weather.start_date < context.trip.start_date
        or context.weather.end_date > context.trip.end_date
    ):
        raise PlanValidationError("Weather range must stay inside the trip range")


def materialize_plan(
    context: ReplanContext,
    draft: PlanDraft,
    fixtures: PlanningFixtures,
) -> tuple[list[TripItem], list[PlanChange], list[str]]:
    """Turn an untrusted schedule draft into trusted items and verified changes."""
    original = {item.id: item for item in context.trip.items}
    seen: set[str] = set()
    items: list[TripItem] = []
    for scheduled in draft.items:
        if scheduled.id in seen:
            raise PlanValidationError(f"Plan {draft.id} repeats item {scheduled.id}")
        seen.add(scheduled.id)
        items.append(_materialize_item(scheduled, original, fixtures))

    _validate_item_dates(context, items)
    _validate_locked_and_completed(context, original, items)
    _validate_opening_hours(items, fixtures)
    _validate_daily_timing(items, fixtures)
    _validate_event(context, original, items)

    ordered = sorted(items, key=lambda item: (item.scheduled_date, item.start_time, item.id))
    changes = _derive_changes(context, original, ordered)
    warnings = _weather_warnings(context, ordered)
    return ordered, changes, warnings


def schedule_signature(items: list[TripItem]) -> tuple[tuple[str, str, str], ...]:
    """Return a stable identity used to require materially distinct candidates."""
    return tuple(
        sorted(
            (item.id, item.scheduled_date.isoformat(), item.start_time)
            for item in items
        )
    )


def _materialize_item(
    scheduled: ScheduledItemDraft,
    original: dict[str, TripItem],
    fixtures: PlanningFixtures,
) -> TripItem:
    if scheduled.id in original:
        return original[scheduled.id].model_copy(
            update={
                "scheduled_date": scheduled.scheduled_date,
                "start_time": scheduled.start_time,
            },
            deep=True,
        )
    candidate = fixtures.candidates.get(scheduled.id)
    if candidate is None:
        raise PlanValidationError(f"Unknown or untrusted item id: {scheduled.id}")
    return TripItem(
        **candidate.model_dump(exclude={"cost_jpy"}),
        scheduled_date=scheduled.scheduled_date,
        start_time=scheduled.start_time,
    )


def _validate_item_dates(context: ReplanContext, items: list[TripItem]) -> None:
    timezone = ZoneInfo(context.trip.timezone)
    now = context.now.astimezone(timezone)
    original = {item.id: item for item in context.trip.items}
    for item in items:
        if not context.trip.start_date <= item.scheduled_date <= context.trip.end_date:
            raise PlanValidationError(f"Item {item.id} is outside the trip date range")
        planned_at = _local_datetime(item, timezone)
        source = original.get(item.id)
        unchanged = source is not None and _same_slot(source, item)
        if planned_at < now and not unchanged:
            raise PlanValidationError(f"Item {item.id} was moved into the past")


def _validate_locked_and_completed(
    context: ReplanContext,
    original: dict[str, TripItem],
    items: list[TripItem],
) -> None:
    planned = {item.id: item for item in items}
    timezone = ZoneInfo(context.trip.timezone)
    now = context.now.astimezone(timezone)
    for item in original.values():
        must_keep = item.booking or not item.movable or _item_end(item, timezone) <= now
        if not must_keep:
            continue
        candidate = planned.get(item.id)
        if candidate is None or not _same_slot(item, candidate):
            raise PlanValidationError(
                f"Locked or completed item {item.id} must remain unchanged"
            )


def _validate_opening_hours(
    items: list[TripItem], fixtures: PlanningFixtures
) -> None:
    for item in items:
        hours = fixtures.business_hours.get(item.id)
        if hours is None:
            raise PlanValidationError(f"Business hours missing for item {item.id}")
        start = _minutes(item.start_time)
        end = start + item.duration_minutes
        opening = _minutes(hours.open_time)
        closing = _minutes(hours.close_time)
        if end > 24 * 60:
            raise PlanValidationError(f"Item {item.id} crosses midnight")
        if start < opening or end > closing:
            raise PlanValidationError(f"Item {item.id} is outside business hours")
        if hours.last_entry_time is not None and start > _minutes(hours.last_entry_time):
            raise PlanValidationError(f"Item {item.id} starts after last entry")


def _validate_daily_timing(
    items: list[TripItem], fixtures: PlanningFixtures
) -> None:
    by_date: dict[date, list[TripItem]] = defaultdict(list)
    for item in items:
        by_date[item.scheduled_date].append(item)
    for day_items in by_date.values():
        ordered = sorted(day_items, key=lambda item: (item.start_time, item.id))
        for previous, current in zip(ordered, ordered[1:]):
            required_start = (
                _minutes(previous.start_time)
                + previous.duration_minutes
                + fixtures.travel_minutes(previous.id, current.id)
            )
            if _minutes(current.start_time) < required_start:
                raise PlanValidationError(
                    f"Items {previous.id} and {current.id} overlap or lack travel time"
                )


def _validate_event(
    context: ReplanContext,
    original: dict[str, TripItem],
    items: list[TripItem],
) -> None:
    planned = {item.id: item for item in items}
    event = context.event
    if event.event_type == "delay" and event.delay_minutes:
        _validate_delay(context, original, planned)
    elif event.event_type == "closure":
        _validate_closure(context, original, planned)
    elif event.event_type == "weather":
        _validate_weather(context, original, planned)


def _validate_delay(
    context: ReplanContext,
    original: dict[str, TripItem],
    planned: dict[str, TripItem],
) -> None:
    timezone = ZoneInfo(context.trip.timezone)
    blocked_from = context.now.astimezone(timezone)
    blocked_until = blocked_from + timedelta(minutes=context.event.delay_minutes)
    target_ids = set(context.event.affected_item_ids) or set(original)
    affected_dates = set(context.event.affected_dates)
    for item_id in target_ids:
        item = planned.get(item_id)
        if item is None:
            continue
        scheduled_at = _local_datetime(item, timezone)
        date_matches = not affected_dates or item.scheduled_date in affected_dates
        if date_matches and blocked_from <= scheduled_at < blocked_until:
            raise PlanValidationError(
                f"Item {item.id} starts during the delay interval"
            )


def _validate_closure(
    context: ReplanContext,
    original: dict[str, TripItem],
    planned: dict[str, TripItem],
) -> None:
    target_ids = set(context.event.affected_item_ids)
    if not target_ids:
        return
    affected_dates = set(context.event.affected_dates)
    for item_id in target_ids:
        if item_id not in original:
            raise PlanValidationError(f"Closure references unknown item {item_id}")
        item = planned.get(item_id)
        if item is not None and (
            not affected_dates or item.scheduled_date in affected_dates
        ):
            raise PlanValidationError(
                f"Closed item {item_id} remains on an affected date"
            )


def _validate_weather(
    context: ReplanContext,
    original: dict[str, TripItem],
    planned: dict[str, TripItem],
) -> None:
    target_ids = set(context.event.affected_item_ids)
    if not target_ids:
        affected_dates = set(context.event.affected_dates)
        target_ids = {
            item.id
            for item in original.values()
            if not item.indoor and item.scheduled_date in affected_dates
        }
    for item_id in target_ids:
        item = planned.get(item_id)
        if item is None or item.indoor:
            continue
        probability = _max_precipitation_probability(context, item)
        if probability is not None and probability >= RAIN_RISK_THRESHOLD:
            raise PlanValidationError(
                f"Weather-affected outdoor item {item.id} remains in a high-risk slot"
            )


def _derive_changes(
    context: ReplanContext,
    original: dict[str, TripItem],
    items: list[TripItem],
) -> list[PlanChange]:
    planned = {item.id: item for item in items}
    reason = context.event.summary.strip()[:120] or "行程事件"
    changes: list[PlanChange] = []
    for source in context.trip.items:
        result = planned.get(source.id)
        if result is None:
            changes.append(
                PlanChange(
                    item_id=source.id,
                    action="cancel",
                    from_date=source.scheduled_date,
                    from_start_time=source.start_time,
                    to_date=None,
                    to_start_time=None,
                    reason=f"因應「{reason}」取消",
                )
            )
        elif _same_slot(source, result):
            changes.append(
                PlanChange(
                    item_id=source.id,
                    action="keep",
                    from_date=source.scheduled_date,
                    from_start_time=source.start_time,
                    to_date=result.scheduled_date,
                    to_start_time=result.start_time,
                    reason="保留原時段",
                )
            )
        else:
            changes.append(
                PlanChange(
                    item_id=source.id,
                    action="move",
                    from_date=source.scheduled_date,
                    from_start_time=source.start_time,
                    to_date=result.scheduled_date,
                    to_start_time=result.start_time,
                    reason=f"因應「{reason}」調整日期或時間",
                )
            )
    original_ids = set(original)
    for item in items:
        if item.id not in original_ids:
            changes.append(
                PlanChange(
                    item_id=item.id,
                    action="add",
                    from_date=None,
                    from_start_time=None,
                    to_date=item.scheduled_date,
                    to_start_time=item.start_time,
                    reason=f"因應「{reason}」加入可信候選",
                )
            )
    return changes


def _weather_warnings(context: ReplanContext, items: list[TripItem]) -> list[str]:
    warnings: list[str] = []
    if context.weather.source == "unavailable":
        warnings.append("天氣資料不可用；方案未把未知天氣視為晴天。")
        return warnings
    risky = [
        item.name
        for item in items
        if not item.indoor
        and (_max_precipitation_probability(context, item) or 0)
        >= RAIN_RISK_THRESHOLD
    ]
    if risky:
        warnings.append(f"高降雨機率戶外活動：{'、'.join(risky)}。")
    return warnings


def _max_precipitation_probability(
    context: ReplanContext, item: TripItem
) -> float | None:
    timezone = ZoneInfo(context.trip.timezone)
    start = _local_datetime(item, timezone)
    end = start + timedelta(minutes=item.duration_minutes)
    values = [
        hour.precipitation_probability
        for hour in context.weather.hours
        if hour.precipitation_probability is not None
        and start <= hour.time.astimezone(timezone) < end
    ]
    return max(values) if values else None


def _same_slot(left: TripItem, right: TripItem) -> bool:
    return (
        left.scheduled_date == right.scheduled_date
        and left.start_time == right.start_time
    )


def _local_datetime(item: TripItem, timezone: ZoneInfo) -> datetime:
    return datetime.combine(
        item.scheduled_date,
        time.fromisoformat(item.start_time),
        tzinfo=timezone,
    )


def _item_end(item: TripItem, timezone: ZoneInfo) -> datetime:
    return _local_datetime(item, timezone) + timedelta(minutes=item.duration_minutes)


def _minutes(value: str) -> int:
    parsed = time.fromisoformat(value)
    return parsed.hour * 60 + parsed.minute
