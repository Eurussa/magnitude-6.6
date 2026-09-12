"""Parse user incidents locally into the shared multi-day Event contract."""
import re
from datetime import date, datetime, timedelta

from ..models import Event, Trip

CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _parse_amount(value: str) -> int:
    if value.isdigit():
        return int(value)
    if value.startswith("十"):
        return 10 + CHINESE_NUMBERS.get(value[1:], 0)
    if "十" in value:
        tens, ones = value.split("十", 1)
        return CHINESE_NUMBERS[tens] * 10 + CHINESE_NUMBERS.get(ones, 0)
    return CHINESE_NUMBERS[value]


def _mentioned_item_ids(message: str, trip: Trip) -> list[str]:
    normalized = message.casefold()
    item_ids = []
    for item in trip.items:
        aliases = {item.id.casefold(), item.name.casefold()}
        if "迪士尼" in item.name:
            aliases.add("迪士尼")
        if "博物館" in item.name:
            aliases.add("博物館")
        if any(alias in normalized for alias in aliases):
            item_ids.append(item.id)
    return item_ids


def _mentioned_dates(message: str, trip: Trip, now: datetime) -> list[date]:
    dates: set[date] = set()
    local_today = now.date()
    normalized = message.casefold()
    if "後天" in message or "day after tomorrow" in normalized:
        dates.add(local_today + timedelta(days=2))
    elif "明天" in message or "tomorrow" in normalized:
        dates.add(local_today + timedelta(days=1))
    elif any(token in normalized for token in ("今天", "今日", "today")):
        dates.add(local_today)

    for year, month, day in re.findall(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", message):
        try:
            dates.add(date(int(year), int(month), int(day)))
        except ValueError:
            continue
    for month, day in re.findall(r"(?<!\d)(\d{1,2})\s*(?:/|月)\s*(\d{1,2})日?", message):
        try:
            dates.add(date(local_today.year, int(month), int(day)))
        except ValueError:
            continue
    return sorted(day for day in dates if trip.start_date <= day <= trip.end_date)


def parse_event(message: str, *, trip: Trip, now: datetime) -> Event:
    """Return a deterministic event without sending user data to a provider."""
    delay_match = re.search(
        r"(?:睡過頭|晚(?:到|起)|延(?:遲|誤)|overslept|delay(?:ed)?)"
        r"[^\d零一二兩三四五六七八九十]*"
        r"(\d+|[零一二兩三四五六七八九十]+)\s*"
        r"(天|小時|分鐘|days?|hours?|hrs?|minutes?|mins?)",
        message,
        flags=re.IGNORECASE,
    )
    event_type = "unknown"
    delay_minutes = 0
    if delay_match:
        event_type = "delay"
        amount = _parse_amount(delay_match.group(1))
        unit = delay_match.group(2).lower()
        if unit in ("天", "day", "days"):
            delay_minutes = amount * 24 * 60
        elif unit in ("小時", "hour", "hours", "hr", "hrs"):
            delay_minutes = amount * 60
        else:
            delay_minutes = amount
    else:
        normalized = message.casefold()
        if any(word in normalized for word in (
            "雨", "颱風", "下雪", "高溫", "天氣", "rain", "typhoon", "snow", "weather",
        )):
            event_type = "weather"
        elif any(word in normalized for word in (
            "休館", "關閉", "停業", "沒開", "closed", "closure",
        )):
            event_type = "closure"

    item_ids = _mentioned_item_ids(message, trip)
    affected_dates = _mentioned_dates(message, trip, now)
    if not affected_dates and event_type != "unknown":
        item_dates = {
            item.scheduled_date for item in trip.items if item.id in item_ids
        }
        if item_dates:
            affected_dates = sorted(item_dates)
        elif trip.start_date <= now.date() <= trip.end_date:
            affected_dates = [now.date()]
    return Event(
        event_type=event_type,
        delay_minutes=delay_minutes,
        affected_item_ids=item_ids,
        affected_dates=affected_dates,
        summary=message,
    )
