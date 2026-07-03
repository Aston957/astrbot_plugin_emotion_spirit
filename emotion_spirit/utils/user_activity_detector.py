"""Detect user-mentioned activities and plans from text.

v1.1.0C Task 5.5 — UserActivityDetector.
Parses user text messages to extract:
- joint plans (一起/陪/我们...去...)
- busy signals (忙/没时间)
- wish / generic activity mentions (keyword based)
"""

from __future__ import annotations

import re


__all__ = ["UserActivityDetector"]


_JOINT_PATTERNS = [
    r"陪.*去(.+)",
    r"一起(.+)",
    r"我们.*去(.+)",
]
_BUSY_PATTERNS = [
    r"(很|有点)?忙",
    r"没时间",
    r"在忙",
]
_ACTIVITY_KEYWORDS = [
    "逛街", "吃饭", "看电影", "唱歌", "购物", "玩游戏", "运动", "散步",
]


def _extract_time_hint(text: str) -> str:
    """Pick a coarse time hint from natural-language markers."""
    if "明天" in text:
        return "明天"
    if "后天" in text:
        return "后天"
    if "周末" in text:
        return "周末"
    if "今晚" in text or "今天晚上" in text:
        return "今晚"
    return "soon"


class UserActivityDetector:
    """Extract user activity plans from text messages."""

    def detect_plan(self, user_text: str) -> dict | None:
        """Detect activity plan from user text.

        Returns:
        - {"type": "joint", "activity": str, "time": str} for shared plans
        - {"type": "busy", "implication": "reduce打扰"} for busy signals
        - {"type": "wish", "activity": str, "time": str} for general wishes
        - None if no plan detected
        """
        if not user_text:
            return None

        # busy signal takes priority — if the user is busy, joint/wish plans
        # are dominated by the cancellation rule.
        for pattern in _BUSY_PATTERNS:
            if re.search(pattern, user_text):
                return {"type": "busy", "implication": "reduce打扰"}

        # joint plans
        for pattern in _JOINT_PATTERNS:
            m = re.search(pattern, user_text)
            if m:
                activity = m.group(1).strip()[:20]
                return {
                    "type": "joint",
                    "activity": activity,
                    "time": _extract_time_hint(user_text),
                }

        # generic activity wishes (keyword)
        for keyword in _ACTIVITY_KEYWORDS:
            if keyword in user_text:
                return {
                    "type": "wish",
                    "activity": keyword,
                    "time": _extract_time_hint(user_text),
                }

        return None

    def inject_into_plan(self, plan, detected: dict) -> None:
        """Apply detected plan to a DailyPlan."""
        from ..regulation.life_plan import PlannedEvent

        if not detected:
            return

        dtype = detected.get("type")
        if dtype == "joint":
            activity = detected.get("activity", "一起活动")
            time_hint = detected.get("time", "soon")
            plan.events.append(
                PlannedEvent(
                    id=f"user_{time_hint}_{activity}",
                    time_slot="afternoon",
                    approximate_time="15:00",
                    activity=f"和用户一起{activity}",
                    category="user_joint",
                    flexibility=0.2,
                )
            )
        elif dtype == "busy":
            for e in plan.events:
                if e.category == "template" and e.flexibility > 0.5:
                    e.status = "cancelled"
                    e.cancellation_reason = "用户忙"