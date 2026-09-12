"""Backend B: deterministic scheduling belongs here, never in the LLM parser."""
from ..models import Plan, Trip


def candidate_plans(trip: Trip) -> list[Plan]:
    strategies = [("preserve_booking", "保留預約"),
                  ("maximize_attractions", "保留最多景點"), ("relaxed", "最輕鬆")]
    return [Plan(id=chr(65 + i), strategy=strategy, title=title,
                 items=trip.items, explanation="初始化佔位方案：沿用原行程，尚未計算重排。")
            for i, (strategy, title) in enumerate(strategies)]
