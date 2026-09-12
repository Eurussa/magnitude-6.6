from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class Event(BaseModel):
    event_type: Literal["weather", "delay", "closure", "unknown"]
    delay_minutes: int = Field(ge=0, le=1440)
    affected_item_id: str | None
    summary: str


class PreferenceWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preserve_booking: float = Field(default=1, ge=0, allow_inf_nan=False)
    maximize_attractions: float = Field(default=1, ge=0, allow_inf_nan=False)
    relaxed: float = Field(default=1, ge=0, allow_inf_nan=False)


class Preference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: Literal["demo-user"] = "demo-user"
    weights: PreferenceWeights = Field(default_factory=PreferenceWeights)
    selection_count: int = Field(default=0, ge=0)


class WeatherHour(BaseModel):
    time: AwareDatetime
    precipitation_probability: float | None = Field(default=None, ge=0, le=100)


class WeatherContext(BaseModel):
    source: Literal["live", "fixture", "unavailable"]
    date: date
    timezone: str
    hours: list[WeatherHour] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReplanContext(BaseModel):
    trip: Trip
    event: Event
    weather: WeatherContext
    preferences: Preference
    now: AwareDatetime


class ReplanRequest(BaseModel):
    trip_id: Literal["tokyo-demo"] = "tokyo-demo"
    message: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    now: AwareDatetime | None = None


class Plan(BaseModel):
    id: str
    strategy: Literal["preserve_booking", "maximize_attractions", "relaxed"]
    title: str
    items: list[TripItem]
    explanation: str = ""


class ReplanResponse(BaseModel):
    status: Literal["placeholder"] = "placeholder"
    event: Event
    weather: WeatherContext
    preferences: Preference
    plans: list[Plan]
    warnings: list[str]
