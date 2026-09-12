"""Backend A: obtain weather context; scheduling decisions belong to Backend B."""
import json
import os
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from ..models import Trip, WeatherContext, WeatherHour

FIXTURE_FILE = Path(__file__).resolve().parent.parent / "data" / "weather.json"


async def fetch_weather(
    latitude: float, longitude: float, *, timezone: str, day: date,
) -> WeatherContext:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": latitude, "longitude": longitude,
            "hourly": "precipitation_probability", "timezone": timezone,
            "start_date": day.isoformat(), "end_date": day.isoformat(),
        })
        response.raise_for_status()
        hourly = response.json()["hourly"]
    hours = []
    for timestamp, probability in zip(
        hourly["time"], hourly["precipitation_probability"], strict=True,
    ):
        instant = datetime.fromisoformat(timestamp)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=ZoneInfo(timezone))
        else:
            instant = instant.astimezone(ZoneInfo(timezone))
        if instant.date() != day:
            raise ValueError("Weather response does not match the requested day")
        hours.append(WeatherHour(time=instant, precipitation_probability=probability))
    if not hours or all(hour.precipitation_probability is None for hour in hours):
        raise ValueError("Weather response has no usable forecast")
    return WeatherContext(source="live", date=day, timezone=timezone, hours=hours)


def fixture_weather(*, timezone: str, day: date) -> WeatherContext:
    fixture = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    if fixture["timezone"] != timezone:
        raise ValueError("Weather fixture timezone does not match the trip")
    hours = [WeatherHour(
        time=datetime.combine(day, time.fromisoformat(hour["time"]), ZoneInfo(timezone)),
        precipitation_probability=hour["precipitation_probability"],
    ) for hour in fixture["hours"]]
    if not hours:
        raise ValueError("Weather fixture is empty")
    return WeatherContext(source="fixture", date=day, timezone=timezone, hours=hours,
                          warnings=["天氣使用示範 fixture，並非即時預報。"])


async def get_weather(trip: Trip, *, now: datetime) -> WeatherContext:
    timezone = trip.timezone
    day = now.astimezone(ZoneInfo(timezone)).date()
    mode = os.getenv("WEATHER_MODE", "mock")
    warnings = []
    if mode == "live":
        try:
            if not trip.items:
                raise ValueError("Trip has no coordinates")
            location = trip.items[0]
            return await fetch_weather(location.latitude, location.longitude,
                                       timezone=timezone, day=day)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            warnings.append("Open-Meteo 暫時無法使用或資料不完整，已嘗試使用示範 fixture。")
    elif mode != "mock":
        return WeatherContext(source="unavailable", date=day, timezone=timezone,
                              warnings=["WEATHER_MODE 必須為 mock 或 live；天氣資料不可用。"])
    try:
        weather = fixture_weather(timezone=timezone, day=day)
        weather.warnings = warnings + weather.warnings
        return weather
    except (OSError, ValueError, KeyError, TypeError):
        return WeatherContext(source="unavailable", date=day, timezone=timezone,
                              warnings=warnings + ["天氣 fixture 無法讀取；未知天氣不能視為晴天。"])
