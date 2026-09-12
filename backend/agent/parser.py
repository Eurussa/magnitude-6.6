"""Backend A: replace the explicit offline fallback with structured LLM parsing."""
from ..models import Event


def parse_event(message: str) -> Event:
    return Event(event_type="unknown", delay_minutes=0,
                 affected_item_id=None, summary=message)
