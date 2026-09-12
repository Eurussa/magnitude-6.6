"""Apply a stored, validated plan and preference update as one transaction."""
from datetime import datetime, timezone

from ..models import SelectionRecord, SelectionRequest, SelectionResponse, Trip
from .preference import apply_strategy_choice
from .runtime import RuntimeState, RuntimeStore


class SelectionNotFoundError(Exception):
    """The requested snapshot or plan does not exist."""


class SelectionConflictError(Exception):
    """The requested selection cannot be safely applied."""


def apply_selection(
    store: RuntimeStore,
    request: SelectionRequest,
    *,
    created_at: datetime | None = None,
) -> SelectionResponse:
    """Apply a feasible snapshot plan exactly once and return an idempotent result."""
    key = str(request.replan_id)
    selected_at = created_at or datetime.now(timezone.utc)
    result: SelectionResponse | None = None

    def update(state: RuntimeState) -> RuntimeState:
        nonlocal result
        previous = state.selection_results.get(key)
        if previous is not None:
            if previous.selection.plan_id != request.plan_id:
                raise SelectionConflictError("同一 replan_id 已選擇其他方案。")
            result = previous
            return state

        snapshot = state.replan_snapshots.get(key)
        if snapshot is None:
            raise SelectionNotFoundError("找不到指定的 replan snapshot。")
        plan = next((item for item in snapshot.plans if item.id == request.plan_id), None)
        if plan is None:
            raise SelectionNotFoundError("找不到指定方案。")
        if not plan.feasible:
            raise SelectionConflictError("不可行方案不能套用。")
        if snapshot.trip_id != state.trip.id or snapshot.trip_version != state.trip.version:
            raise SelectionConflictError("行程版本已變更，請重新產生方案。")

        trip_payload = state.trip.model_dump()
        trip_payload.update({
            "version": state.trip.version + 1,
            "items": [item.model_dump() for item in plan.items],
        })
        updated_trip = Trip.model_validate(trip_payload)
        updated_preferences = apply_strategy_choice(state.preferences, plan.strategy)
        selection = SelectionRecord(
            replan_id=request.replan_id,
            plan_id=request.plan_id,
            created_at=selected_at,
        )
        result = SelectionResponse(
            selection=selection,
            trip=updated_trip,
            preferences=updated_preferences,
        )
        state.trip = updated_trip
        state.preferences = updated_preferences
        state.selection_results[key] = result
        return state

    store.update_state(update)
    if result is None:  # Defensive guard: update() always assigns before returning.
        raise RuntimeError("selection transaction completed without a result")
    return result
