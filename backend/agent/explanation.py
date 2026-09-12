"""Backend A owns user-facing explanations, based on Backend B's actual facts."""
from ..models import Plan


def explain_plan(plan: Plan) -> Plan:
    # Replace after B supplies computed changes/impact. Never invent feasibility.
    return plan.model_copy(update={
        "explanation": "初始化佔位方案：沿用原行程，尚未計算重排、評分或偏好推薦。",
    })
