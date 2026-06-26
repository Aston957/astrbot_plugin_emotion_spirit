"""LifeSimulator v2 — 日程规划数据结构 + 模板库。"""

from __future__ import annotations

import datetime
import random
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "PlannedEvent", "DailyPlan",
    "PLAN_TEMPLATES", "PERSONALITY_TEMPLATE_WEIGHTS",
    "select_template_activities", "_time_to_slot",
]


@dataclass
class PlannedEvent:
    """一个计划中的事件。"""
    id: str
    time_slot: str           # "morning" / "afternoon" / "evening" / "night"
    approximate_time: str    # "14:00"
    activity: str            # "逛商场"
    category: str            # "template" / "llm_random"
    mood_expectation: str = "平淡"
    flexibility: float = 0.5  # [0,1] 0=不可改变, 1=随时可变
    status: str = "planned"   # "planned" / "active" / "done" / "cancelled" / "replaced"
    cancellation_reason: str | None = None
    replacement: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "time_slot": self.time_slot,
            "approximate_time": self.approximate_time,
            "activity": self.activity, "category": self.category,
            "mood_expectation": self.mood_expectation,
            "flexibility": self.flexibility, "status": self.status,
            "cancellation_reason": self.cancellation_reason,
            "replacement": self.replacement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannedEvent:
        return cls(
            id=data.get("id", ""),
            time_slot=data.get("time_slot", ""),
            approximate_time=data.get("approximate_time", ""),
            activity=data.get("activity", ""),
            category=data.get("category", "template"),
            mood_expectation=data.get("mood_expectation", "平淡"),
            flexibility=float(data.get("flexibility", 0.5)),
            status=data.get("status", "planned"),
            cancellation_reason=data.get("cancellation_reason"),
            replacement=data.get("replacement"),
        )


@dataclass
class DailyPlan:
    """一天的日程计划。"""
    date: str                        # "2026-06-27"
    generated_at: float
    events: list[PlannedEvent] = field(default_factory=list)
    personality_snapshot: dict = field(default_factory=dict)
    adaptations: list[dict] = field(default_factory=list)
    dream_seed: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "generated_at": self.generated_at,
            "events": [e.to_dict() for e in self.events],
            "personality_snapshot": self.personality_snapshot,
            "adaptations": self.adaptations,
            "dream_seed": self.dream_seed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyPlan:
        return cls(
            date=data.get("date", ""),
            generated_at=float(data.get("generated_at", 0.0)),
            events=[PlannedEvent.from_dict(e) for e in data.get("events", [])],
            personality_snapshot=data.get("personality_snapshot", {}),
            adaptations=data.get("adaptations", []),
            dream_seed=data.get("dream_seed", ""),
        )


# ═══ 活动模板库 ═══

PLAN_TEMPLATES: dict[str, list[str]] = {
    "creative": ["画画", "写作", "做手工", "拍照", "弹琴"],
    "intellectual": ["看书", "看纪录片", "学新东西", "思考问题"],
    "social": ["和朋友聊天", "出门见人", "逛商场", "去咖啡店"],
    "physical": ["散步", "跑步", "瑜伽", "做饭", "打扫"],
    "rest": ["午睡", "发呆", "听音乐", "看电影", "泡澡"],
    "routine": ["起床", "吃饭", "洗漱", "整理房间"],
}

# ═══ 人格 → 模板权重 ═══

PERSONALITY_TEMPLATE_WEIGHTS: dict[str, dict[str, float]] = {
    "openness": {"creative": 0.4, "intellectual": 0.3, "social": 0.1, "physical": 0.1, "rest": 0.1},
    "extraversion": {"social": 0.4, "physical": 0.3, "creative": 0.1, "rest": 0.1, "intellectual": 0.1},
    "conscientiousness": {"routine": 0.3, "intellectual": 0.3, "physical": 0.2, "creative": 0.1, "rest": 0.1},
    "agreeableness": {"social": 0.3, "rest": 0.3, "physical": 0.2, "creative": 0.1, "intellectual": 0.1},
    "neuroticism": {"rest": 0.4, "creative": 0.2, "intellectual": 0.2, "physical": 0.1, "social": 0.1},
}


def _time_to_slot(epoch_seconds: float) -> str:
    """将时间戳转为时间段。"""
    dt = datetime.datetime.fromtimestamp(epoch_seconds)
    hour = dt.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def select_template_activities(
    personality: dict[str, float],
    n: int = 2,
    exclude: set[str] | None = None,
) -> list[tuple[str, str]]:
    """按人格权重选择 n 个模板活动。返回 [(category, activity), ...]。"""
    exclude = exclude or set()

    # 计算每个 category 的综合权重
    category_weights: dict[str, float] = {}
    for category in PLAN_TEMPLATES:
        w = 0.0
        for trait, trait_weights in PERSONALITY_TEMPLATE_WEIGHTS.items():
            w += personality.get(trait, 0.5) * trait_weights.get(category, 0.1)
        category_weights[category] = w

    # 归一化
    total = sum(category_weights.values())
    if total > 0:
        category_weights = {k: v / total for k, v in category_weights.items()}

    # 选择 category，然后从 category 中随机选 activity
    result = []
    categories = list(category_weights.keys())
    weights = [category_weights[c] for c in categories]
    for _ in range(n):
        chosen_cat = random.choices(categories, weights=weights, k=1)[0]
        activities = [a for a in PLAN_TEMPLATES[chosen_cat] if a not in exclude]
        if activities:
            chosen_activity = random.choice(activities)
            result.append((chosen_cat, chosen_activity))
            exclude.add(chosen_activity)

    return result
