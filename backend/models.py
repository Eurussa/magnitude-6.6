from typing import Literal
from pydantic import BaseModel, Field


class TripItem(BaseModel):
    id: str
    name: str
    start_time: str
    duration_minutes: int = Field(gt=0)
    latitude: float
    longitude: float
    priority: int = Field(ge=1, le=5)
    booking: bool
    movable: bool
    indoor: bool


class Trip(BaseModel):
    id: str
    city: str
    timezone: str
    items: list[TripItem]


class Event(BaseModel):
    event_type: Literal["weather", "delay", "closure", "unknown"]
    delay_minutes: int = Field(ge=0, le=1440)
    affected_item_id: str | None
    summary: str


class ReplanRequest(BaseModel):
    trip_id: Literal["tokyo-demo"] = "tokyo-demo"
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class Plan(BaseModel):
    id: str
    strategy: Literal["preserve_booking", "maximize_attractions", "relaxed"]
    title: str
    items: list[TripItem]
    explanation: str


class ReplanResponse(BaseModel):
    status: Literal["placeholder"] = "placeholder"
    event: Event
    plans: list[Plan]
    warnings: list[str]
