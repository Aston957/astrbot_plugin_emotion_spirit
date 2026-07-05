"""时间工具: 逻辑日 (6am 边界) + 日程显示标签. v1.3.0 rc.5.

用户模型: day(n) 的 6am 前 = day(n-1). cron 在 02:00 (6am 前) 触发,
生成即将到来的逻辑日的 plan. logical_today() 用于显示标签, 不用于 plan.date
(plan.date = date.today() at 02:00 = 即将到来的逻辑日, 二者天然对齐).
"""
from __future__ import annotations
from datetime import date, datetime, timedelta


def logical_today(now: datetime | None = None) -> date:
    """当前逻辑日 (6am 为界, 6am 前 = 昨天).

    Args:
        now: 当前时间 (默认 datetime.now()). 测试可注入.

    Returns:
        逻辑日 date. 06:00 前 = 日历昨天, 06:00 后 = 日历今天.
    """
    from emotion_spirit.core.config import LIFE_SIM_V2_CONFIG
    start_hour = LIFE_SIM_V2_CONFIG.get("logical_day_start_hour", 6)
    now = now or datetime.now()
    today = now.date()
    if now.hour < start_hour:
        return today - timedelta(days=1)
    return today


def plan_date_label(date_str: str, now: datetime | None = None) -> str:
    """日程显示标签, 基于逻辑日边界.

    plan.date 是日历日 (生成时 date.today()). 标签按 plan.date 与 logical_today
    的差值显示: 0 = 今天, 1 = 明天, -1 = 昨天, 其他 = 日期.

    Args:
        date_str: plan.date (ISO 格式, e.g. "2026-07-05").
        now: 当前时间 (测试注入).

    Returns:
        "今天日程 (2026-07-05)" / "明天日程 (2026-07-06)" / "日程计划 (2026-07-07)"
    """
    plan_date = date.fromisoformat(date_str)
    today = logical_today(now)
    delta = (plan_date - today).days
    if delta == 0:
        return f"今天日程 ({date_str})"
    if delta == 1:
        return f"明天日程 ({date_str})"
    if delta == -1:
        return f"昨天日程 ({date_str})"
    return f"日程计划 ({date_str})"
