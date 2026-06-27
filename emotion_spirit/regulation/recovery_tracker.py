"""Emotional recovery trajectory tracker.

Based on Bonanno (2004) and Walker (2013) 4F model.
Different collapse archetypes have different recovery paths.
"""

from __future__ import annotations
import random
import time
from typing import Any

from ..core.registry import register


# Literature-backed recovery trajectories
RECOVERY_TRAJECTORIES: dict[str, list[str]] = {
    "volcanic": ["发泄", "独处消化", "轻度活动", "恢复正常"],      # 2-3 days
    "collapse": ["寻求安慰", "休息", "轻度社交", "恢复正常"],     # 3-5 days
    "freeze":   ["独处", "缓慢恢复", "试探性社交", "恢复正常"],   # 5-7 days
    "drift":    ["无目的活动", "反思", "重新定向", "恢复正常"],   # 3-5 days
    "cold":     ["独处分析", "整理思绪", "重新连接", "恢复正常"], # 2-4 days
}

STAGE_ACTIVITY_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "volcanic": {
        "发泄": ["在空旷的地方大声喊叫", "写下愤怒然后撕掉", "在枕头上打几下"],
        "独处消化": ["独自散步", "泡个热水澡", "听舒缓音乐"],
        "轻度活动": ["做简单的家务", "整理房间", "准备一顿饭"],
        "恢复正常": ["回到日常节奏", "和家人朋友相聚", "做喜欢的事"],
    },
    "collapse": {
        "寻求安慰": ["给信任的人打个电话", "写一封不会发出的信", "抱着玩偶说会儿话"],
        "休息": ["躺在安静的房间里", "小睡一会儿", "喝杯温热的饮品"],
        "轻度社交": ["在群里冒个泡", "回复一条友好消息", "点个喜欢吃的外卖"],
        "恢复正常": ["主动约朋友见面", "恢复工作节奏", "尝试新活动"],
    },
    "freeze": {
        "独处": ["裹在毯子里", "喝热饮", "看窗外发呆"],
        "缓慢恢复": ["做简单的拉伸", "打开窗户通风", "整理一个抽屉"],
        "试探性社交": ["给一个老朋友发消息", "在群里回复一句话", "点个外卖"],
        "恢复正常": ["主动约朋友见面", "恢复工作节奏", "尝试新活动"],
    },
    "drift": {
        "无目的活动": ["随意浏览网页", "漫无目的地散步", "整理一些零碎物品"],
        "反思": ["写下最近的想法", "回顾过去几天的心情", "思考未来的方向"],
        "重新定向": ["设定一个小目标", "尝试一个新习惯", "重新安排日程"],
        "恢复正常": ["恢复日常作息", "和亲近的人聊聊", "做一件有意义的事"],
    },
    "cold": {
        "独处分析": ["写下问题分析清单", "梳理事件来龙去脉", "阅读相关内容"],
        "整理思绪": ["做思维导图", "列出感受和想法", "写下解决方案"],
        "重新连接": ["和信任的人简短交流", "参加一个小型聚会", "分享一个想法"],
        "恢复正常": ["回到日常工作", "和朋友共进晚餐", "享受独处时光"],
    },
}


@register(
    name="recovery_tracker",
    provides=["RecoveryTracker"],
    depends_on=[],
)
class RecoveryTracker:
    """Track emotional recovery trajectory after a collapse event."""

    def __init__(self):
        self._active_recovery: str | None = None
        self._recovery_stage: int = 0
        self._recovery_start: float = 0.0

    def start_recovery(self, archetype: str):
        """Start recovery trajectory for given collapse archetype."""
        self._active_recovery = archetype
        self._recovery_stage = 0
        self._recovery_start = time.time()

    def advance_stage(self):
        """Move to next stage of recovery. Clears if complete."""
        if not self._active_recovery:
            return
        self._recovery_stage += 1
        trajectory = RECOVERY_TRAJECTORIES.get(self._active_recovery, [])
        if self._recovery_stage >= len(trajectory):
            self._active_recovery = None  # Recovery complete

    def adapt_plan_for_recovery(self, plan):
        """Replace current events with recovery-stage appropriate activities."""
        from .life_plan import PlannedEvent
        if not self._active_recovery:
            return
        trajectory = RECOVERY_TRAJECTORIES.get(self._active_recovery, [])
        if self._recovery_stage >= len(trajectory):
            return
        current_stage = trajectory[self._recovery_stage]
        templates = STAGE_ACTIVITY_TEMPLATES.get(
            self._active_recovery, {}
        ).get(current_stage, [f"恢复阶段: {current_stage}"])
        # Cancel existing planned events
        for event in plan.events:
            if event.status == "planned":
                event.status = "cancelled"
                event.cancellation_reason = f"恢复阶段: {current_stage}"
        # Add recovery activities (1-2 events)
        for i, template in enumerate(random.sample(templates, min(2, len(templates)))):
            plan.events.append(PlannedEvent(
                id=f"recovery_{self._recovery_stage}_{i}",
                time_slot="morning" if i == 0 else "afternoon",
                approximate_time="10:00" if i == 0 else "15:00",
                activity=template,
                category="recovery",
                flexibility=0.2,
            ))

    def to_dict(self):
        return {"active": self._active_recovery, "stage": self._recovery_stage,
                "start": self._recovery_start}

    def from_dict(self, data):
        self._active_recovery = data.get("active")
        self._recovery_stage = data.get("stage", 0)
        self._recovery_start = data.get("start", 0.0)
