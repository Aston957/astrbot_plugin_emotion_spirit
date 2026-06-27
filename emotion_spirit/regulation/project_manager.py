"""Long-term project management with personality-driven suggestions.

v1.1.0C Task 5.2 — ProjectManager for multi-day project tracking.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..core.registry import register

__all__ = ["Project", "ProjectManager"]


@dataclass
class Project:
    """A long-term project that spans multiple days.

    Projects are personality-driven: high openness favours creative projects,
    high conscientiousness favours structured/routine projects, etc.
    """

    name: str
    category: str
    start_date: str
    estimated_days: int = 7
    progress: float = 0.0
    status: str = "active"  # active | paused | completed | abandoned
    milestones: list[str] = field(default_factory=list)


@register(
    name="project_manager",
    provides=["ProjectManager"],
    depends_on=[],
)
class ProjectManager:
    """Manages long-term projects that span multiple days.

    Projects are personality-driven: high openness → creative projects,
    high conscientiousness → structured projects, etc.
    """

    PROJECT_TEMPLATES: dict[str, list[tuple[str, int, list[str]]]] = {
        "creative": [
            ("学吉他", 14, ["基础和弦", "简单歌曲", "完整弹唱"]),
            ("写小说", 30, ["人物设定", "故事大纲", "初稿完成"]),
            ("学画画", 21, ["基础素描", "色彩入门", "完整作品"]),
        ],
        "intellectual": [
            ("读完一本书", 7, ["前半部分", "后半部分", "读书笔记"]),
            ("学一门新语言", 90, ["基础语法", "日常对话", "流利交流"]),
        ],
        "physical": [
            ("健身计划", 30, ["适应期", "力量训练", "有氧运动"]),
            ("学游泳", 14, ["基础动作", "换气", "长距离"]),
        ],
        "routine": [
            ("整理房间", 3, ["断舍离", "清洁", "建立收纳系统"]),
        ],
    }

    def __init__(self) -> None:
        self._projects: list[Project] = []

    # ------------------------------------------------------------------
    #  suggestion
    # ------------------------------------------------------------------

    def suggest_project(
        self,
        personality: dict[str, float],
        recent_activities: list[str] | None = None,
    ) -> Project | None:
        """Suggest a new project based on personality and recent activities.

        Personality traits weight different project categories, and recently
        active categories are deprioritised so the bot suggests variety.
        """
        O = personality.get("openness", 0.5)
        C = personality.get("conscientiousness", 0.5)
        E = personality.get("extraversion", 0.5)
        N = personality.get("neuroticism", 0.5)

        category_weights: dict[str, float] = {
            "creative":     O + E * 0.5,
            "intellectual": O * 0.5 + C,
            "physical":     E + (1.0 - N),
            "routine":      C * 1.5,
        }

        # Deprioritise categories that match recent activities.
        if recent_activities:
            recent_cats = set(self._infer_category(a) for a in recent_activities)
            for cat in recent_cats:
                if cat in category_weights:
                    category_weights[cat] *= 0.3

        total = sum(category_weights.values())
        if total <= 0:
            return None

        r = random.random() * total
        cum = 0.0
        for cat, w in category_weights.items():
            cum += w
            if r <= cum:
                templates = self.PROJECT_TEMPLATES.get(cat, [])
                if not templates:
                    continue
                name_t, days, milestones = random.choice(templates)
                return Project(
                    name=name_t,
                    category=cat,
                    start_date=date.today().isoformat(),
                    estimated_days=days,
                    progress=0.0,
                    status="active",
                    milestones=list(milestones),
                )

        return None

    def _infer_category(self, activity: str) -> str:
        """Infer a project category from an activity description."""
        for cat, templates in self.PROJECT_TEMPLATES.items():
            for tpl_name, _days, _milestones in templates:
                if tpl_name[:2] in activity:
                    return cat
        return "routine"

    # ------------------------------------------------------------------
    #  plan injection
    # ------------------------------------------------------------------

    def inject_into_plan(self, plan: Any) -> None:
        """Add active project events into *plan*.

        Only *active* projects are considered.  Each active project has a
        ~50 % chance of appearing on any given day (deterministic per
        project + date so the same plan always gets the same events).
        """
        from .life_plan import PlannedEvent  # local import to avoid circular deps

        for proj in self._projects:
            if proj.status != "active":
                continue

            # 50 % chance per project-day pair (seeded for determinism).
            if random.Random(proj.name + plan.date).random() < 0.5:
                continue

            milestone = proj.milestones[0] if proj.milestones else "进展"
            plan.events.append(PlannedEvent(
                id=f"proj_{proj.name}_{plan.date}",
                time_slot="afternoon",
                approximate_time="15:00",
                activity=f"继续{proj.name} ({milestone})",
                category="project",
                flexibility=0.4,
            ))

    # ------------------------------------------------------------------
    #  serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "projects": [
                {
                    "name": p.name,
                    "category": p.category,
                    "start_date": p.start_date,
                    "estimated_days": p.estimated_days,
                    "progress": p.progress,
                    "status": p.status,
                    "milestones": list(p.milestones),
                }
                for p in self._projects
            ],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._projects = [
            Project(
                name=p["name"],
                category=p["category"],
                start_date=p["start_date"],
                estimated_days=p.get("estimated_days", 7),
                progress=p.get("progress", 0.0),
                status=p.get("status", "active"),
                milestones=list(p.get("milestones", [])),
            )
            for p in data.get("projects", [])
        ]
