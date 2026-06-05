"""亲密度追踪 — 6 维不对称亲密度 + 5 插入点调制。"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from .persona_profiles import get_intimacy_weights, get_intimacy_modulation


@dataclass
class IntimacyProfile:
    """单个用户-人格对的亲密度。"""
    temporal_depth: float = 0.0
    interaction_freq: float = 0.0
    vulnerability_exposure: float = 0.0
    repair_history: float = 0.0
    shared_narrative: float = 0.0
    user_investment: float = 0.0
    last_update: float = field(default_factory=time.time)
    lifecycle: str = "stranger"

    def to_dict(self) -> dict[str, Any]:
        return {
            "temporal_depth": round(self.temporal_depth, 6),
            "interaction_freq": round(self.interaction_freq, 6),
            "vulnerability_exposure": round(self.vulnerability_exposure, 6),
            "repair_history": round(self.repair_history, 6),
            "shared_narrative": round(self.shared_narrative, 6),
            "user_investment": round(self.user_investment, 6),
            "last_update": self.last_update,
            "lifecycle": self.lifecycle,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntimacyProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class IntimacyTracker:
    """管理所有用户的亲密度。"""

    def __init__(self) -> None:
        self._profiles: dict[str, IntimacyProfile] = {}

    def get_profile(self, user_id: str) -> IntimacyProfile:
        if user_id not in self._profiles:
            self._profiles[user_id] = IntimacyProfile()
        return self._profiles[user_id]

    def update(
        self,
        user_id: str,
        temporal_hours: float | None = None,
        interval_seconds: float | None = None,
        repair_count: int | None = None,
        vulnerability_delta: float = 0.0,
        shared_narrative: float | None = None,
        user_investment_delta: float = 0.0,
    ) -> None:
        """更新用户的亲密度。"""
        profile = self.get_profile(user_id)
        now = time.time()

        if temporal_hours is not None:
            profile.temporal_depth = temporal_hours
        if interval_seconds is not None:
            alpha = 0.1
            freq = 1.0 / max(1.0, interval_seconds / 3600.0)
            profile.interaction_freq = profile.interaction_freq * (1 - alpha) + freq * alpha
        if repair_count is not None:
            profile.repair_history = float(repair_count)
        profile.vulnerability_exposure = max(
            0.0,
            profile.vulnerability_exposure + vulnerability_delta,
        )
        if shared_narrative is not None:
            profile.shared_narrative = shared_narrative
        profile.user_investment = max(
            0.0,
            profile.user_investment + user_investment_delta,
        )

        # 自然衰减
        elapsed_days = (now - profile.last_update) / 86400
        vuln_hl = 14.0
        inv_hl = 30.0
        profile.vulnerability_exposure *= math.exp(-0.693 * elapsed_days / vuln_hl)
        profile.user_investment *= math.exp(-0.693 * elapsed_days / inv_hl)
        profile.last_update = now

        # 更新生命周期
        profile.lifecycle = self._compute_lifecycle(profile)

    def get_intimacy(self, user_id: str, persona: str = "") -> float:
        """计算加权亲密度分数 [0, 1]。"""
        profile = self.get_profile(user_id)
        weights = get_intimacy_weights()
        score = (
            profile.temporal_depth / max(1.0, profile.temporal_depth + 720) * weights["temporal_depth"]
            + min(1.0, profile.interaction_freq) * weights["interaction_freq"]
            + min(1.0, profile.vulnerability_exposure) * weights["vulnerability_exposure"]
            + min(1.0, profile.repair_history / 10.0) * weights["repair_history"]
            + min(1.0, profile.shared_narrative) * weights["shared_narrative"]
            + min(1.0, profile.user_investment) * weights["user_investment"]
        )
        return max(0.0, min(1.0, score))

    def get_weight(
        self,
        user_id: str,
        persona: str,
        insertion_point: str,
    ) -> float:
        """获取插入点调制系数。返回乘数 (1.0 = 无调制)。"""
        intimacy = self.get_intimacy(user_id, persona)
        mod = get_intimacy_modulation()

        if insertion_point == "hot_pool":
            return 1.0 + mod["alpha"] * intimacy
        elif insertion_point == "consolidation_speed":
            return 1.0 - mod["beta"] * intimacy
        elif insertion_point == "eruption_threshold":
            return mod["gamma"] * intimacy
        elif insertion_point == "ghost_depth":
            return 1.0 + mod["epsilon"] * intimacy
        elif insertion_point == "drift_pull":
            return intimacy
        return 1.0

    def get_lifecycle(self, user_id: str) -> str:
        return self.get_profile(user_id).lifecycle

    def _compute_lifecycle(self, profile: IntimacyProfile) -> str:
        intimacy = (
            profile.temporal_depth / max(1.0, profile.temporal_depth + 720) * 0.3
            + min(1.0, profile.repair_history / 10.0) * 0.3
            + min(1.0, profile.vulnerability_exposure) * 0.2
            + min(1.0, profile.user_investment) * 0.2
        )
        if intimacy > 0.75 and profile.repair_history >= 5:
            return "intimate"
        if intimacy > 0.5 and profile.repair_history >= 2:
            return "close"
        if intimacy > 0.2 and profile.temporal_depth >= 168:
            return "acquaintance"
        return "stranger"

    def to_dict(self) -> dict[str, Any]:
        return {uid: p.to_dict() for uid, p in self._profiles.items()}

    def from_dict(self, data: dict[str, Any]) -> None:
        self._profiles = {uid: IntimacyProfile.from_dict(p) for uid, p in data.items()}
