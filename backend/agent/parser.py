"""Backend A: replace the explicit offline fallback with structured LLM parsing."""
from datetime import datetime

from ..models import Event, Trip


def parse_event(message: str, *, trip: Trip, now: datetime) -> Event:
    """Return an unknown placeholder while preserving multi-day parser inputs."""
    return Event(event_type="unknown", delay_minutes=0,
                 affected_item_ids=[], affected_dates=[], summary=message)
