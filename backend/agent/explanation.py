"""Backend A owns user-facing explanations, based on Backend B's actual facts."""
from ..models import Plan


def explain_plan(plan: Plan) -> Plan:
    """Fill a blank explanation using only B's validated plan facts."""
    if plan.explanation.strip():
        return plan
    if not plan.feasible:
        explanation = "此方案未通過可行性驗證，不能套用。"
    else:
        moved = sum(change.action == "move" for change in plan.changes)
        cancelled = sum(change.action == "cancel" for change in plan.changes)
        explanation = (
            f"此方案移動 {moved} 個活動、取消 {cancelled} 個活動；"
            f"交通時間差 {plan.additional_travel_minutes:+d} 分鐘，"
            f"費用差 {plan.additional_cost_jpy:+d} 日圓。"
        )
        if plan.booking_warnings:
            explanation += f" 預約提醒：{'；'.join(plan.booking_warnings)}"
    return plan.model_copy(update={"explanation": explanation})
