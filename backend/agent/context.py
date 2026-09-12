"""Backend A assembles validated context before calling the LLM-driven replanner."""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import ReplanContext, ReplanRequest
from .parser import parse_event_with_warnings
from .runtime import RuntimeStore
from .weather import get_weather


@dataclass(frozen=True, slots=True)
class ContextBuildResult:
    context: ReplanContext
    warnings: tuple[str, ...] = ()


async def build_context_result(
    request: ReplanRequest,
    store: RuntimeStore,
) -> ContextBuildResult:
    """Build B's context and retain A-only provider/fallback metadata."""
    # Read the trip and preferences from the same persisted state snapshot.
    state = store.load_state()
    timezone = ZoneInfo(state.trip.timezone)
    now = request.now.astimezone(timezone) if request.now else datetime.now(timezone)
    parsed = await parse_event_with_warnings(request.message, trip=state.trip, now=now)
    weather = await get_weather(state.trip, now=now)
    context = ReplanContext(
        trip=state.trip,
        event=parsed.event,
        weather=weather,
        preferences=state.preferences,
        now=now,
    )
    return ContextBuildResult(context=context, warnings=parsed.warnings)


async def build_context(request: ReplanRequest, store: RuntimeStore) -> ReplanContext:
    """Build only the fixed A-to-B context contract."""
    return (await build_context_result(request, store)).context
