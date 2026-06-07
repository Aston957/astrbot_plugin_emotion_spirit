"""emotion_spirit 知识库 — 集中所有声明性数据 (Phase B, P3-2)。

Step 1: label_mapper 全量迁移 (thresholds + 5 persona baseline + 5 轴 delta, 155 项)
Step 2: emotion + narrative + tension (后续 task)
Step 3: 删旧字段 (后续 task)

所有 persona/情绪/叙事/threshold 的"事实性数据"统一在此调用, 不再散在 6 个文件。
算法逻辑仍留在原模块, 但数据查询走 KnowledgeBase.X 路径。
"""
from __future__ import annotations
from typing import Any


class KnowledgeBase:
    """统一知识库 — 声明性数据 + 查询 API。"""

    # ═══ 1. 13 维 personality (含 gossip_tendency) ═══
    PERSONALITY_DIMS_DEEP: frozenset[str] = frozenset({
        "expression_drive", "perception_acuity", "boundary_permeability",
        "inner_coherence", "relational_gravity",
    })
    PERSONALITY_DIMS_SURFACE: frozenset[str] = frozenset({
        "warmth_bias", "directness", "curiosity", "patience",
        "intimacy_pull", "relational_autonomy", "exploration_openness",
        "gossip_tendency",
    })
    ALL_PERSONALITY_DIMS: frozenset[str] = (
        PERSONALITY_DIMS_DEEP | PERSONALITY_DIMS_SURFACE
    )

    # ═══ 2. 5 persona baseline (含 gossip_tendency) ═══
    PERSONA_BASELINES: dict[str, dict[str, float]] = {
        "INFP-A": {
            "expression_drive": 0.25, "perception_acuity": 0.70,
            "boundary_permeability": 0.40, "inner_coherence": 0.95,
            "relational_gravity": 0.20, "warmth_bias": 0.45,
            "directness": 0.85, "curiosity": 0.60, "patience": 0.70,
            "intimacy_pull": 0.30, "relational_autonomy": 0.20,
            "exploration_openness": 0.75, "gossip_tendency": 0.30,
        },
        "ISTJ-S": {
            "expression_drive": 0.25, "perception_acuity": 0.70,
            "boundary_permeability": 0.40, "inner_coherence": 0.95,
            "relational_gravity": 0.20, "warmth_bias": 0.30,
            "directness": 0.85, "curiosity": 0.60, "patience": 0.70,
            "intimacy_pull": 0.15, "relational_autonomy": 0.90,
            "exploration_openness": 0.40, "gossip_tendency": 0.15,
        },
        "ENTP-AV": {
            "expression_drive": 0.25, "perception_acuity": 0.70,
            "boundary_permeability": 0.40, "inner_coherence": 0.95,
            "relational_gravity": 0.20, "warmth_bias": 0.40,
            "directness": 0.85, "curiosity": 0.60, "patience": 0.70,
            "intimacy_pull": 0.45, "relational_autonomy": 0.85,
            "exploration_openness": 0.95, "gossip_tendency": 0.65,
        },
        "ISFJ-D": {
            "expression_drive": 0.25, "perception_acuity": 0.70,
            "boundary_permeability": 0.40, "inner_coherence": 0.95,
            "relational_gravity": 0.20, "warmth_bias": 0.50,
            "directness": 0.85, "curiosity": 0.60, "patience": 0.70,
            "intimacy_pull": 0.40, "relational_autonomy": 0.55,
            "exploration_openness": 0.15, "gossip_tendency": 0.40,
        },
        "ESTP-A": {
            "expression_drive": 0.25, "perception_acuity": 0.70,
            "boundary_permeability": 0.40, "inner_coherence": 0.95,
            "relational_gravity": 0.20, "warmth_bias": 0.35,
            "directness": 0.85, "curiosity": 0.60, "patience": 0.70,
            "intimacy_pull": 0.50, "relational_autonomy": 0.45,
            "exploration_openness": 0.55, "gossip_tendency": 0.70,
        },
    }

    # ═══ 3. 5 轴标签 delta (按类型) ═══
    MBTI_LETTER_DELTAS: dict[str, dict[str, float]] = {
        "I": {"expression_drive": -0.10, "warmth_bias": -0.05, "intimacy_pull": -0.10, "exploration_openness": -0.05},
        "E": {"expression_drive": +0.15, "warmth_bias": +0.10, "intimacy_pull": +0.10, "exploration_openness": +0.05},
        "N": {"curiosity": +0.15, "perception_acuity": +0.05, "boundary_permeability": +0.10, "exploration_openness": +0.20},
        "S": {"curiosity": -0.10, "perception_acuity": -0.05, "inner_coherence": +0.05, "exploration_openness": -0.15},
        "F": {"warmth_bias": +0.20, "relational_gravity": +0.15, "intimacy_pull": +0.15, "relational_autonomy": -0.05},
        "T": {"warmth_bias": -0.10, "directness": +0.10, "inner_coherence": +0.05, "relational_autonomy": +0.10},
        "P": {"boundary_permeability": +0.15, "patience": -0.10, "relational_autonomy": -0.05},
        "J": {"inner_coherence": +0.05, "patience": +0.05, "relational_autonomy": +0.05},
    }
    ATTACHMENT_DELTAS: dict[str, dict[str, float]] = {
        "安全型": {"boundary_permeability": +0.10, "inner_coherence": +0.10, "intimacy_pull": +0.05, "relational_autonomy": +0.05, "exploration_openness": +0.10},
        "焦虑型": {"boundary_permeability": +0.25, "inner_coherence": -0.20, "intimacy_pull": +0.30, "relational_autonomy": -0.15, "exploration_openness": -0.05, "expression_drive": +0.15},
        "回避型": {"boundary_permeability": -0.20, "inner_coherence": +0.10, "intimacy_pull": -0.20, "relational_autonomy": +0.20, "exploration_openness": -0.15},
        "混乱型": {"boundary_permeability": +0.10, "inner_coherence": -0.30, "intimacy_pull": +0.20, "relational_autonomy": -0.10, "exploration_openness": +0.05},
    }
    EMOTION_STYLE_DELTAS: dict[str, dict[str, float]] = {
        "压抑型": {"expression_drive": -0.20, "warmth_bias": -0.05, "relational_autonomy": +0.10},
        "表达型": {"expression_drive": +0.20, "warmth_bias": +0.10, "relational_autonomy": -0.05},
        "波动型": {"inner_coherence": -0.15, "relational_autonomy": -0.05},
        "稳定型": {"inner_coherence": +0.10, "relational_autonomy": +0.05},
    }
    CONFLICT_STYLE_DELTAS: dict[str, dict[str, float]] = {
        "攻击型": {"directness": +0.15, "relational_autonomy": +0.10, "relational_gravity": -0.10},
        "顺应型": {"warmth_bias": +0.10, "relational_autonomy": -0.05, "directness": -0.10},
        "合作型": {"warmth_bias": +0.05, "directness": +0.05, "relational_autonomy": 0.0},
        "回避型": {"boundary_permeability": -0.10, "relational_autonomy": +0.05, "relational_gravity": -0.05},
    }
    TIME_FOCUS_DELTAS: dict[str, dict[str, float]] = {
        "活在过去": {"relational_gravity": +0.10, "patience": +0.10, "exploration_openness": -0.10},
        "活在当下": {"patience": +0.05, "relational_gravity": +0.05},
        "活在未来": {"exploration_openness": +0.15, "patience": -0.05, "relational_autonomy": -0.05},
    }

    # ═══ 4. 数值阈值 ═══
    THRESHOLDS: dict[str, Any] = {
        "intimacy_segments": (0.65, 0.40, 0.15, 0.0),
        "lifecycle_intimate_intimacy": 0.75,
        "lifecycle_intimate_repair": 5,
        "lifecycle_close_intimacy": 0.5,
        "lifecycle_close_repair": 2,
        "lifecycle_acquaintance_intimacy": 0.2,
        "lifecycle_acquaintance_temporal": 168,
        "buffer_capacity": 30,
        "buffer_dwell_seconds": 86400,
        "buffer_7d_window": 7 * 86400,
        "confirmation_history_max": 200,
        "recent_expired_max": 50,
        "warm_max": 100,
        "cold_max": 50,
        "delta_clamp": (-0.3, +0.3),
        "deep_regression_rate": 0.005,
        "surface_regression_rate": 0.010,
        "trajectory_window": 8,
        "pad_save_interval_seconds": 300,
    }

    # ═══ 统一查询 API ═══

    @classmethod
    def get_persona_baseline(cls, persona_id: str) -> dict[str, float]:
        """5 persona baseline 查询 (返回 dict 副本)。"""
        if persona_id not in cls.PERSONA_BASELINES:
            raise KeyError(
                f"未知 persona: {persona_id} (5 persona: {list(cls.PERSONA_BASELINES.keys())})"
            )
        return dict(cls.PERSONA_BASELINES[persona_id])

    @classmethod
    def get_delta_for_label(cls, label_type: str, label_value: str) -> dict[str, float]:
        """查 5 轴标签的 dim delta。"""
        delta_map = {
            "mbti": cls.MBTI_LETTER_DELTAS,
            "attachment": cls.ATTACHMENT_DELTAS,
            "emotion_style": cls.EMOTION_STYLE_DELTAS,
            "conflict_style": cls.CONFLICT_STYLE_DELTAS,
            "time_focus": cls.TIME_FOCUS_DELTAS,
        }
        if label_type not in delta_map:
            raise KeyError(f"未知标签类型: {label_type}")
        if label_value not in delta_map[label_type]:
            valid_values = list(delta_map[label_type].keys())
            raise KeyError(
                f"未知 label_value: '{label_value}' (类型 {label_type}, 合法值: {valid_values})"
            )
        return dict(delta_map[label_type][label_value])

    @classmethod
    def get_threshold(cls, name: str) -> Any:
        """查数值阈值。"""
        if name not in cls.THRESHOLDS:
            raise KeyError(f"未知阈值: {name}")
        return cls.THRESHOLDS[name]
