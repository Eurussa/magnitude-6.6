"""Backend A assembles validated context before calling the LLM-driven replanner."""
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import ReplanContext, ReplanRequest
from .parser import parse_event
from .runtime import RuntimeStore
from .weather import get_weather


async def build_context(request: ReplanRequest, store: RuntimeStore) -> ReplanContext:
    # Read the trip and preferences from the same persisted state snapshot.
    state = store.load_state()
    timezone = ZoneInfo(state.trip.timezone)
    now = request.now.astimezone(timezone) if request.now else datetime.now(timezone)
    event = await parse_event(request.message, trip=state.trip, now=now)
    weather = await get_weather(state.trip, now=now)
    return ReplanContext(trip=state.trip, event=event, weather=weather,
                         preferences=state.preferences, now=now)
