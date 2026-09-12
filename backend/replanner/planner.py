"""Backend B's LLM-driven, multi-day replanning implementation."""

from __future__ import annotations

import logging
from datetime import datetime

from ..models import (
    Event,
    Plan,
    PlanChange,
    PlanFeatures,
    PlanningResult,
    Preference,
    ReplanContext,
    Trip,
    WeatherContext,
)
from .client import OpenAIPlanningClient, PlanningClient
from .config import ReplannerSettings
from .errors import PlanValidationError, ReplannerError
from .fixtures import PlanningFixtures
from .schemas import (
    FallbackPlanTemplate,
    PlanDraft,
    PlanningDraft,
    PlanningRepairFeedback,
    ScheduledItemDraft,
)
from .scoring import calculate_features, calculate_impacts, rank_plans
from .validation import materialize_plan, schedule_signature, validate_context

logger = logging.getLogger(__name__)


class LLMReplanner:
    """Generate, validate, enrich, and rank three multi-day candidates."""

    def __init__(
        self,
        *,
        client: PlanningClient | None,
        fixtures: PlanningFixtures,
        max_attempts: int = 3,
    ) -> None:
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self._client = client
        self._fixtures = fixtures
        self._max_attempts = max_attempts

    @classmethod
    def from_settings(
        cls,
        settings: ReplannerSettings | None = None,
        *,
        fixtures: PlanningFixtures | None = None,
    ) -> "LLMReplanner":
        """Construct the app-boundary service from shared root settings."""
        resolved_settings = settings or ReplannerSettings.from_env()
        client: PlanningClient | None = None
        if resolved_settings.mode == "live":
            client = OpenAIPlanningClient(resolved_settings)
        return cls(
            client=client,
            fixtures=fixtures or PlanningFixtures.load(),
            max_attempts=resolved_settings.max_attempts,
        )

    async def generate_plans(self, context: ReplanContext, /) -> PlanningResult:
        """Implement the stable ``Replanner`` protocol without runtime I/O."""
        validate_context(context)
        failures: list[str] = []
        accepted: dict[str, Plan] = {}
        accepted_drafts: dict[str, PlanDraft] = {}
        accepted_warnings: dict[str, list[str]] = {}
        validation_feedback: PlanningRepairFeedback | None = None
        if self._client is not None:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    draft = await self._client.generate(
                        context,
                        self._fixtures,
                        validation_feedback=validation_feedback,
                    )
                    errors = self._accept_valid_candidates(
                        context,
                        draft,
                        accepted,
                        accepted_drafts,
                        accepted_warnings,
                    )
                    if len(accepted) == 3:
                        plans = list(accepted.values())
                        _validate_distinct_plans(plans)
                        ranked, recommended = rank_plans(plans, context.preferences)
                        warnings = [
                            f"方案 {plan_id}：{warning}"
                            for plan_id in ("A", "B", "C")
                            for warning in accepted_warnings.get(plan_id, [])
                        ]
                        return PlanningResult(
                            source="live",
                            plans=ranked,
                            recommended_plan_id=recommended,
                            warnings=_deduplicate(warnings),
                        )
                    missing = [
                        plan_id
                        for plan_id in ("A", "B", "C")
                        if plan_id not in accepted
                    ]
                    validation_feedback = PlanningRepairFeedback(
                        accepted_plans=[
                            accepted_drafts[plan_id]
                            for plan_id in ("A", "B", "C")
                            if plan_id in accepted_drafts
                        ],
                        errors=[
                            *errors,
                            f"Missing valid plan ids: {', '.join(missing)}",
                        ],
                    )
                    failures.append("PlanValidationError")
                    logger.warning(
                        "Planning attempt %s/%s left %s valid candidates",
                        attempt,
                        self._max_attempts,
                        len(accepted),
                    )
                except ReplannerError as exc:
                    failures.append(type(exc).__name__)
                    validation_feedback = PlanningRepairFeedback(
                        accepted_plans=[],
                        errors=[str(exc)],
                    )
                    logger.warning(
                        "Planning attempt %s/%s failed: %s",
                        attempt,
                        self._max_attempts,
                        type(exc).__name__,
                    )

        fallback_reason = (
            "；".join(failures) if failures else "replanner configured for fixture mode"
        )
        return self._fixture_result(context, fallback_reason)

    def _accept_valid_candidates(
        self,
        context: ReplanContext,
        draft: PlanningDraft,
        accepted: dict[str, Plan],
        accepted_drafts: dict[str, PlanDraft],
        accepted_warnings: dict[str, list[str]],
    ) -> list[str]:
        errors: list[str] = []
        for candidate in draft.plans:
            if candidate.id in accepted:
                continue
            try:
                plan, warnings = self._build_plan(context, candidate)
            except ReplannerError as exc:
                errors.append(f"Plan {candidate.id}: {exc}")
                continue
            if any(
                schedule_signature(plan.items) == schedule_signature(other.items)
                for other in accepted.values()
            ):
                errors.append(f"Plan {candidate.id}: candidate duplicates another plan")
                continue
            accepted[candidate.id] = plan
            accepted_drafts[candidate.id] = candidate.model_copy(deep=True)
            accepted_warnings[candidate.id] = warnings
        return errors

    def _build_plan(
        self, context: ReplanContext, candidate: PlanDraft
    ) -> tuple[Plan, list[str]]:
        items, changes, warnings = materialize_plan(
            context, candidate, self._fixtures
        )
        travel_delta, cost_delta = calculate_impacts(
            context.trip, items, self._fixtures
        )
        return Plan(
            id=candidate.id,
            strategy=candidate.strategy,
            title=candidate.title,
            items=items,
            feasible=True,
            changes=changes,
            additional_travel_minutes=travel_delta,
            additional_cost_jpy=cost_delta,
            booking_warnings=[],
            features=calculate_features(context.trip, items, self._fixtures),
            explanation="",
        ), warnings

    def _build_plans(
        self, context: ReplanContext, draft: PlanningDraft
    ) -> tuple[list[Plan], list[str]]:
        plans: list[Plan] = []
        warnings: list[str] = []
        for candidate in draft.plans:
            plan, candidate_warnings = self._build_plan(context, candidate)
            plans.append(plan)
            warnings.extend(
                f"方案 {candidate.id}：{warning}" for warning in candidate_warnings
            )
        _validate_distinct_plans(plans)
        return plans, _deduplicate(warnings)

    def _fixture_result(
        self, context: ReplanContext, reason: str
    ) -> PlanningResult:
        scenario = next(
            (
                entry
                for entry in self._fixtures.fallback.scenarios
                if entry.trip_id == context.trip.id
                and entry.start_date == context.trip.start_date
                and entry.end_date == context.trip.end_date
                and entry.event_type == context.event.event_type
            ),
            None,
        )
        fallback_warning = (
            "行程規劃使用可離線重現的 fixture，並非即時 LLM 結果。"
        )
        if reason:
            fallback_warning += f" 原因：{reason}。"
        if scenario is None:
            return PlanningResult(
                source="fixture",
                plans=_unavailable_plans(context.trip),
                recommended_plan_id=None,
                warnings=[
                    fallback_warning,
                    "沒有符合目前行程與事件的 planning fixture。",
                ],
            )

        try:
            draft = PlanningDraft(
                plans=[
                    _draft_from_template(context.trip, template)
                    for template in scenario.plans
                ]
            )
            plans, warnings = self._build_plans(context, draft)
        except ReplannerError as exc:
            logger.warning("Planning fixture failed validation: %s", type(exc).__name__)
            return PlanningResult(
                source="fixture",
                plans=_unavailable_plans(context.trip),
                recommended_plan_id=None,
                warnings=[fallback_warning, "Planning fixture 未通過方案限制驗證。"],
            )

        ranked, recommended = rank_plans(plans, context.preferences)
        return PlanningResult(
            source="fixture",
            plans=ranked,
            recommended_plan_id=recommended,
            warnings=[fallback_warning, *warnings],
        )


def candidate_plans(
    trip: Trip,
    *,
    event: Event,
    weather: WeatherContext,
    preferences: Preference,
    now: datetime,
) -> list[Plan]:
    """Keep the old synchronous placeholder until Backend A wires the Protocol."""
    del event, weather, preferences, now
    return _unavailable_plans(trip)


def _draft_from_template(
    trip: Trip, template: FallbackPlanTemplate
) -> PlanDraft:
    cancelled = set(template.cancels)
    known_ids = {item.id for item in trip.items}
    if set(template.moves) - known_ids or cancelled - known_ids:
        raise PlanValidationError("Planning fixture references unknown original ids")
    scheduled: list[ScheduledItemDraft] = []
    for item in trip.items:
        if item.id in cancelled:
            continue
        moved = template.moves.get(item.id)
        scheduled.append(
            ScheduledItemDraft(
                id=item.id,
                scheduled_date=moved[0] if moved else item.scheduled_date,
                start_time=moved[1] if moved else item.start_time,
            )
        )
    scheduled.extend(template.adds)
    return PlanDraft(
        id=template.id,
        strategy=template.strategy,
        title=template.title,
        items=scheduled,
    )


def _unavailable_plans(trip: Trip) -> list[Plan]:
    titles = {
        "A": ("preserve_booking", "保留預約"),
        "B": ("maximize_attractions", "保留最多景點"),
        "C": ("relaxed", "最輕鬆"),
    }
    plans: list[Plan] = []
    for plan_id, (strategy, title) in titles.items():
        items = [item.model_copy(deep=True) for item in trip.items]
        changes = [
            PlanChange(
                item_id=item.id,
                action="keep",
                from_date=item.scheduled_date,
                from_start_time=item.start_time,
                to_date=item.scheduled_date,
                to_start_time=item.start_time,
                reason="沒有可套用的已驗證重排方案",
            )
            for item in trip.items
        ]
        plans.append(
            Plan(
                id=plan_id,
                strategy=strategy,
                title=title,
                items=items,
                feasible=False,
                changes=changes,
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
        )
    return plans


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _validate_distinct_plans(plans: list[Plan]) -> None:
    signatures = {schedule_signature(plan.items) for plan in plans}
    if len(signatures) != len(plans):
        raise PlanValidationError("Planning candidates must be distinct")
