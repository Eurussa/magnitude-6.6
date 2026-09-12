"""Backend A: obtain weather context; scheduling decisions belong to Backend B."""
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from ..models import Trip, WeatherContext, WeatherHour

FIXTURE_FILE = Path(__file__).resolve().parent.parent / "data" / "weather.json"


async def fetch_weather(
    latitude: float,
    longitude: float,
    *,
    timezone: str,
    start_date: date,
    end_date: date,
) -> WeatherContext:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": latitude, "longitude": longitude,
            "hourly": "precipitation_probability", "timezone": timezone,
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
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
        if not start_date <= instant.date() <= end_date:
            raise ValueError("Weather response does not match the requested date range")
        hours.append(WeatherHour(time=instant, precipitation_probability=probability))
    if not hours or all(hour.precipitation_probability is None for hour in hours):
        raise ValueError("Weather response has no usable forecast")
    expected_dates = set(_dates_between(start_date, end_date))
    covered_dates = {
        hour.time.date()
        for hour in hours
        if hour.precipitation_probability is not None
    }
    if not expected_dates.issubset(covered_dates):
        raise ValueError("Weather response does not cover the requested date range")
    return WeatherContext(
        source="live",
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        hours=hours,
        warnings=[],
    )


def _dates_between(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise ValueError("end_date must not be earlier than start_date")
    return [
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    ]


def fixture_weather(
    *, timezone: str, start_date: date, end_date: date,
) -> WeatherContext:
    fixture = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    if fixture["timezone"] != timezone:
        raise ValueError("Weather fixture timezone does not match the trip")
    hours = []
    for weather_day in fixture["days"]:
        day = date.fromisoformat(weather_day["date"])
        if not start_date <= day <= end_date:
            continue
        hours.extend(
            WeatherHour(
                time=datetime.combine(
                    day,
                    time.fromisoformat(hour["time"]),
                    ZoneInfo(timezone),
                ),
                precipitation_probability=hour["precipitation_probability"],
            )
            for hour in weather_day["hours"]
        )
    expected_dates = set(_dates_between(start_date, end_date))
    covered_dates = {
        hour.time.date()
        for hour in hours
        if hour.precipitation_probability is not None
    }
    if not expected_dates.issubset(covered_dates):
        raise ValueError("Weather fixture does not cover the requested date range")
    return WeatherContext(
        source="fixture",
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        hours=hours,
        warnings=["天氣使用多日示範 fixture，並非即時預報。"],
    )


async def get_weather(trip: Trip, *, now: datetime) -> WeatherContext:
    timezone = trip.timezone
    local_date = now.astimezone(ZoneInfo(timezone)).date()
    start_date = max(local_date, trip.start_date)
    end_date = trip.end_date
    if start_date > end_date:
        return WeatherContext(
            source="unavailable",
            start_date=end_date,
            end_date=end_date,
            timezone=timezone,
            hours=[],
            warnings=["行程已結束，沒有需要取得的未來天氣。"],
        )
    mode = os.getenv("WEATHER_MODE", "mock")
    warnings = []
    if mode == "live":
        try:
            if not trip.items:
                raise ValueError("Trip has no coordinates")
            location = next(
                (
                    item
                    for item in trip.items
                    if start_date <= item.scheduled_date <= end_date
                ),
                trip.items[0],
            )
            return await fetch_weather(
                location.latitude,
                location.longitude,
                timezone=timezone,
                start_date=start_date,
                end_date=end_date,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            warnings.append(
                "Open-Meteo 暫時無法使用或資料不完整，"
                "已嘗試使用示範 fixture。"
            )
    elif mode != "mock":
        return WeatherContext(
            source="unavailable",
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
            hours=[],
            warnings=[
                "WEATHER_MODE 必須為 mock 或 live；天氣資料不可用。",
            ],
        )
    try:
        weather = fixture_weather(
            timezone=timezone,
            start_date=start_date,
            end_date=end_date,
        )
        weather.warnings = warnings + weather.warnings
        return weather
    except (OSError, ValueError, KeyError, TypeError):
        return WeatherContext(
            source="unavailable",
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
            hours=[],
            warnings=warnings + ["天氣 fixture 無法讀取；未知天氣不能視為晴天。"],
        )
