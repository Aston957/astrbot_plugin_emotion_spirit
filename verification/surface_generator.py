"""合成 Surface 生成器 — 模拟不同对话场景下的 SylannEngine Surface 输出。

每个场景模板定义一组 Surface 字段的基准值和变化范围。
场景之间用马尔可夫链切换，模拟真实对话的节奏。

Surface 结构参照 surface_consumer.py 的 consume() 解析逻辑:
  state.rhythm / connection / adaptation / responsiveness / valence /
  damage / boundary / capacity / needs
  dynamics.hot_pool / relational_time / affect / uncertainty
  decision / guard / personality / pad
  pipeline.resonance / debug.emergence
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Any

from emotion_spirit.core.label_mapper import labels_to_personality, _BASELINE


@dataclass
class ScenarioProfile:
    """对话场景模板。"""
    name: str
    description: str
    base_surface: dict[str, Any]  # 完整 Surface 字典
    drift_direction: dict[str, float]  # 11维漂移方向 (±0.005~0.03/轮)
    transition_probs: dict[str, float]  # 转移到其他场景的概率

    def generate_surface(
        self,
        personality: dict[str, dict[str, float]],
        turn: int,
        noise: float = 0.05,
    ) -> dict[str, Any]:
        """生成一轮合成 Surface 数据。"""
        surface = {}
        for key, val in self.base_surface.items():
            if isinstance(val, dict):
                surface[key] = {}
                for k2, v2 in val.items():
                    if isinstance(v2, dict):
                        surface[key][k2] = {}
                        for k3, v3 in v2.items():
                            # ⚠️ 关键: bool 必须在 int/float 之前判断 (Python 中 bool 是 int 子类)
                            if isinstance(v3, bool):
                                surface[key][k2][k3] = v3
                            elif isinstance(v3, (int, float)):
                                # 截断到 [0, 1] 防止负数 (risk_score, proportion 类)
                                surface[key][k2][k3] = max(0.0, min(1.0, v3 + random.gauss(0, noise)))
                            else:
                                surface[key][k2][k3] = v3
                    else:
                        # ⚠️ 同样的 bool 优先检查
                        if isinstance(v2, bool):
                            surface[key][k2] = v2
                        elif isinstance(v2, (int, float)):
                            surface[key][k2] = max(0.0, min(1.0, v2 + random.gauss(0, noise)))
                        else:
                            surface[key][k2] = v2
            else:
                # ⚠️ 顶层 bool 也要优先
                if isinstance(val, bool):
                    surface[key] = val
                elif isinstance(val, (int, float)):
                    surface[key] = max(0.0, min(1.0, val + random.gauss(0, noise)))
                else:
                    surface[key] = val

        # 注入当前人格参数
        surface["personality"] = {
            "deep": dict(personality["deep"]),
            "surface": dict(personality["surface"]),
        }

        return surface


def _base_surface_template() -> dict[str, Any]:
    """返回一个完整的 Surface 模板骨架，所有字段都有默认值。

    字段结构与 surface_consumer.py consume() 的解析逻辑完全对齐。
    """
    return {
        "state": {
            "rhythm": {"beat": 0.3, "stability": 0.8, "strain": 0.1},
            "connection": {"warmth": 0.5, "circulation": 0.3, "memory_flow": 0.2},
            "adaptation": {"plasticity": 0.3, "sensitivity": 0.3, "repetition": 0, "threshold_drift": 0.0},
            "responsiveness": {"readiness": 0.5, "fatigue": 0.1, "trained_reach": 0.2},
            "valence": {"warmth": 0.5, "volatility": 0.1, "recovery_heat": 0.1},
            "damage": {"open": 0.05, "accumulated": 0.1, "sensitivity": 0.1, "recovery": 0.3},
            "boundary": {"pressure": 0.1, "autonomy": 0.9, "interruption_budget": 0.9, "cooldown": 0.0, "paused": False},
            "capacity": {"load": 0.2, "exhaustion": 0.1, "recovery_debt": 0.0},
            "needs": {"expression": 0.3, "quiet": 0.3, "recovery": 0.1, "contact": 0.3},
        },
        "dynamics": {
            "hot_pool": {
                "temperature": 0.3, "pressure": 0.1,
                "cascade_active": False, "cascade_intensity": 0.0,
                "collapse_count": 0, "in_recovery": False,
                "sensitivity_multiplier": 1.0,
            },
            "relational_time": {"interval_seconds": 120, "total_duration": 3600, "phase": "active"},
            "affect": {"recovery_drive": 0.2, "expression_drive": 0.4, "quiet_drive": 0.2},
            "uncertainty": {"claim_caution": 0.1, "events": 0},
        },
        "decision": {"action": "observe", "reason": "", "confidence": 0.5, "urgency": 0.0},
        "guard": {"allowed": True, "risk_score": 0.0},
        "pad": {"valence": 0.0, "arousal": 0.3, "dominance": 0.5, "label": "neutral", "confidence": 0.5},
        "pipeline": {
            "resonance": {"sync_order": 0.0, "plasticity_ratio": 0.5, "attractor_count": 0},
        },
        "debug": {
            "emergence": {"phi": 0.0, "order": {"criticality": 0.0}},
        },
    }


# ═══ 8 种场景模板 ═══
# 每种场景的 base_surface 是完整 Surface 字典的"基准值"，
# generate_surface() 会在此基础上加高斯噪声。
# 漂移方向基于 MBTI+依恋风格增量和心理学理论。

SCENARIOS: dict[str, ScenarioProfile] = {

    # ── 场景 1: 安稳陪伴 ──
    # 特征: 低压力、高亲密、alignment 高
    # 心理: 关系满足 (warmth↑, intimacy↑), 情绪平静
    # 漂移: warmth_bias↑, intimacy_pull↑, expression_drive↑
    "safe_companionship": ScenarioProfile(
        name="safe_companionship",
        description="安稳陪伴: 低压力、高亲密、alignment高",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.3, "stability": 0.8, "strain": 0.1},
                "connection": {"warmth": 0.7, "circulation": 0.4, "memory_flow": 0.3},
                "adaptation": {"plasticity": 0.3, "sensitivity": 0.2, "repetition": 0, "threshold_drift": 0.0},
                "responsiveness": {"readiness": 0.6, "fatigue": 0.1, "trained_reach": 0.3},
                "valence": {"warmth": 0.7, "volatility": 0.1, "recovery_heat": 0.1},
                "damage": {"open": 0.05, "accumulated": 0.1, "sensitivity": 0.1, "recovery": 0.3},
                "boundary": {"pressure": 0.1, "autonomy": 0.9, "interruption_budget": 0.9, "cooldown": 0.0, "paused": False},
                "capacity": {"load": 0.2, "exhaustion": 0.1, "recovery_debt": 0.0},
                "needs": {"expression": 0.3, "quiet": 0.4, "recovery": 0.1, "contact": 0.3},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.3, "pressure": 0.1, "cascade_active": False, "cascade_intensity": 0.0, "collapse_count": 0, "in_recovery": False, "sensitivity_multiplier": 1.0},
                "relational_time": {"interval_seconds": 120, "total_duration": 3600, "phase": "active"},
                "affect": {"recovery_drive": 0.2, "expression_drive": 0.4, "quiet_drive": 0.2},
                "uncertainty": {"claim_caution": 0.1, "events": 0},
            },
            "decision": {"action": "express", "reason": "safe companionship", "confidence": 0.8, "urgency": 0.1},
            "guard": {"allowed": True, "risk_score": 0.05},
            "pad": {"valence": 0.6, "arousal": 0.3, "dominance": 0.6, "label": "content", "confidence": 0.7},
            "pipeline": {"resonance": {"sync_order": 0.3, "plasticity_ratio": 0.6, "attractor_count": 1}},
            "debug": {"emergence": {"phi": 0.2, "order": {"criticality": 0.0}}},
        },
        drift_direction={
            "expression_drive": 0.01, "warmth_bias": 0.01, "intimacy_pull": 0.01,
        },
        transition_probs={"safe_companionship": 0.5, "conflict": 0.1, "daily_neutral": 0.3, "intimacy_growth": 0.1},
    ),

    # ── 场景 2: 冲突对抗 ──
    # 特征: 高压力、低亲密、misalignment 高
    # 心理: 关系冲突 (guilt), 自我防御 (shame→relational_autonomy↑), 认知动摇 (doubt)
    # 漂移: relational_autonomy↑ (v1.7: autonomy_guard 拆分), boundary_permeability↓, inner_coherence↓
    "conflict": ScenarioProfile(
        name="conflict",
        description="冲突对抗: 高压力、低亲密、misalignment高",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.8, "stability": 0.3, "strain": 0.7},
                "connection": {"warmth": 0.2, "circulation": 0.6, "memory_flow": 0.2},
                "adaptation": {"plasticity": 0.6, "sensitivity": 0.7, "repetition": 3, "threshold_drift": 0.15},
                "responsiveness": {"readiness": 0.8, "fatigue": 0.4, "trained_reach": 0.1},
                "valence": {"warmth": 0.1, "volatility": 0.7, "recovery_heat": 0.05},
                "damage": {"open": 0.4, "accumulated": 0.3, "sensitivity": 0.5, "recovery": 0.1},
                "boundary": {"pressure": 0.7, "autonomy": 0.4, "interruption_budget": 0.3, "cooldown": 0.2, "paused": False},
                "capacity": {"load": 0.7, "exhaustion": 0.5, "recovery_debt": 0.2},
                "needs": {"expression": 0.7, "quiet": 0.6, "recovery": 0.5, "contact": 0.1},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.7, "pressure": 0.6, "cascade_active": False, "cascade_intensity": 0.3, "collapse_count": 0, "in_recovery": False, "sensitivity_multiplier": 1.3},
                "relational_time": {"interval_seconds": 600, "total_duration": 1800, "phase": "strained"},
                "affect": {"recovery_drive": 0.6, "expression_drive": 0.3, "quiet_drive": 0.5},
                "uncertainty": {"claim_caution": 0.4, "events": 3},
            },
            "decision": {"action": "withdraw", "reason": "conflict", "confidence": 0.5, "urgency": 0.6},
            "guard": {"allowed": False, "risk_score": 0.6},
            "pad": {"valence": -0.4, "arousal": 0.7, "dominance": 0.3, "label": "angry", "confidence": 0.6},
            "pipeline": {"resonance": {"sync_order": 0.1, "plasticity_ratio": 0.3, "attractor_count": 0}},
            "debug": {"emergence": {"phi": 0.1, "order": {"criticality": 0.5}}},
        },
        drift_direction={
            "relational_autonomy": 0.02, "boundary_permeability": -0.02, "inner_coherence": -0.01,  # v1.7: autonomy_guard 拆分
        },
        transition_probs={"conflict": 0.3, "safe_companionship": 0.1, "boundary_invasion": 0.2, "cascading": 0.1, "recovery": 0.3},
    ),

    # ── 场景 3: 情感瀑布 (级联) ──
    # 特征: cascade_active=True, body_criticality 高, 情绪失控
    # 心理: 原始情绪淹没理性, 关系暂时失效, 认知被淹没
    # 漂移: inner_coherence↓, patience↓, perception_acuity↓
    "cascading": ScenarioProfile(
        name="cascading",
        description="情感瀑布: 级联激活, 情绪失控",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.9, "stability": 0.1, "strain": 0.9},
                "connection": {"warmth": 0.1, "circulation": 0.8, "memory_flow": 0.1},
                "adaptation": {"plasticity": 0.8, "sensitivity": 0.9, "repetition": 5, "threshold_drift": 0.3},
                "responsiveness": {"readiness": 0.9, "fatigue": 0.7, "trained_reach": 0.0},
                "valence": {"warmth": 0.0, "volatility": 0.9, "recovery_heat": 0.0},
                "damage": {"open": 0.6, "accumulated": 0.5, "sensitivity": 0.8, "recovery": 0.0},
                "boundary": {"pressure": 0.9, "autonomy": 0.2, "interruption_budget": 0.1, "cooldown": 0.0, "paused": False},
                "capacity": {"load": 0.9, "exhaustion": 0.8, "recovery_debt": 0.5},
                "needs": {"expression": 0.9, "quiet": 0.9, "recovery": 0.8, "contact": 0.0},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.9, "pressure": 0.9, "cascade_active": True, "cascade_intensity": 0.8, "collapse_count": 0, "in_recovery": False, "sensitivity_multiplier": 2.0},
                "relational_time": {"interval_seconds": 30, "total_duration": 600, "phase": "crisis"},
                "affect": {"recovery_drive": 0.9, "expression_drive": 0.8, "quiet_drive": 0.9},
                "uncertainty": {"claim_caution": 0.7, "events": 8},
            },
            "decision": {"action": "hold", "reason": "cascade overwhelm", "confidence": 0.2, "urgency": 0.9},
            "guard": {"allowed": False, "risk_score": 0.8},
            "pad": {"valence": -0.7, "arousal": 0.9, "dominance": 0.1, "label": "overwhelmed", "confidence": 0.8},
            "pipeline": {"resonance": {"sync_order": 0.0, "plasticity_ratio": 0.1, "attractor_count": 0}},
            "debug": {"emergence": {"phi": 0.05, "order": {"criticality": 0.9}}},
        },
        drift_direction={
            "inner_coherence": -0.02, "patience": -0.02, "perception_acuity": -0.01,
        },
        transition_probs={"cascading": 0.2, "recovery": 0.4, "trauma": 0.1, "conflict": 0.2, "daily_neutral": 0.1},
    ),

    # ── 场景 4: 恢复修复 ──
    # 特征: in_recovery=True, damage_recovery 高, 情绪回温
    # 心理: 关系修复 (relational_gravity↑), 情绪平静, 认知重新整合
    # 漂移: warmth_bias↑, relational_gravity↑, inner_coherence↑
    "recovery": ScenarioProfile(
        name="recovery",
        description="恢复修复: 情绪回温, 重建连接",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.4, "stability": 0.6, "strain": 0.2},
                "connection": {"warmth": 0.5, "circulation": 0.3, "memory_flow": 0.4},
                "adaptation": {"plasticity": 0.5, "sensitivity": 0.4, "repetition": 0, "threshold_drift": 0.05},
                "responsiveness": {"readiness": 0.5, "fatigue": 0.3, "trained_reach": 0.2},
                "valence": {"warmth": 0.5, "volatility": 0.2, "recovery_heat": 0.6},
                "damage": {"open": 0.2, "accumulated": 0.3, "sensitivity": 0.3, "recovery": 0.7},
                "boundary": {"pressure": 0.2, "autonomy": 0.7, "interruption_budget": 0.7, "cooldown": 0.0, "paused": False},
                "capacity": {"load": 0.4, "exhaustion": 0.3, "recovery_debt": 0.1},
                "needs": {"expression": 0.4, "quiet": 0.3, "recovery": 0.5, "contact": 0.4},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.3, "pressure": 0.2, "cascade_active": False, "cascade_intensity": 0.0, "collapse_count": 0, "in_recovery": True, "sensitivity_multiplier": 1.1},
                "relational_time": {"interval_seconds": 300, "total_duration": 7200, "phase": "healing"},
                "affect": {"recovery_drive": 0.7, "expression_drive": 0.4, "quiet_drive": 0.3},
                "uncertainty": {"claim_caution": 0.2, "events": 1},
            },
            "decision": {"action": "repair", "reason": "recovery impulse", "confidence": 0.6, "urgency": 0.3},
            "guard": {"allowed": True, "risk_score": 0.1},
            "pad": {"valence": 0.3, "arousal": 0.3, "dominance": 0.5, "label": "hopeful", "confidence": 0.6},
            "pipeline": {"resonance": {"sync_order": 0.2, "plasticity_ratio": 0.5, "attractor_count": 1}},
            "debug": {"emergence": {"phi": 0.3, "order": {"criticality": 0.1}}},
        },
        drift_direction={
            "warmth_bias": 0.01, "relational_gravity": 0.01, "inner_coherence": 0.005,
        },
        transition_probs={"recovery": 0.3, "safe_companionship": 0.4, "daily_neutral": 0.2, "conflict": 0.1},
    ),

    # ── 场景 5: 日常中性 ──
    # 特征: 所有值接近基线, 无明显情绪波动
    # 心理: 各维度平衡, 无主导倾向
    # 漂移: 无明显方向, 仅随机游走
    "daily_neutral": ScenarioProfile(
        name="daily_neutral",
        description="日常中性: 平稳无波, 基线状态",
        base_surface=_base_surface_template(),  # 直接用默认模板
        drift_direction={},
        transition_probs={"daily_neutral": 0.5, "safe_companionship": 0.2, "conflict": 0.1, "intimacy_growth": 0.1, "recovery": 0.1},
    ),

    # ── 场景 6: 边界侵犯 ──
    # 特征: boundary_pressure 高, autonomy 低, 被迫面对不愿面对的事
    # 心理: 自我保护激活 (relational_autonomy↑↑, shame), 认知抵抗
    # 漂移: relational_autonomy↑↑ (v1.7: autonomy_guard 拆分), boundary_permeability↓↓, patience↓
    "boundary_invasion": ScenarioProfile(
        name="boundary_invasion",
        description="边界侵犯: 自主性被压缩, 强制暴露",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.7, "stability": 0.4, "strain": 0.6},
                "connection": {"warmth": 0.3, "circulation": 0.5, "memory_flow": 0.2},
                "adaptation": {"plasticity": 0.5, "sensitivity": 0.8, "repetition": 2, "threshold_drift": 0.1},
                "responsiveness": {"readiness": 0.7, "fatigue": 0.5, "trained_reach": 0.0},
                "valence": {"warmth": 0.2, "volatility": 0.5, "recovery_heat": 0.05},
                "damage": {"open": 0.5, "accumulated": 0.3, "sensitivity": 0.6, "recovery": 0.1},
                "boundary": {"pressure": 0.8, "autonomy": 0.2, "interruption_budget": 0.1, "cooldown": 0.5, "paused": False},
                "capacity": {"load": 0.6, "exhaustion": 0.4, "recovery_debt": 0.2},
                "needs": {"expression": 0.2, "quiet": 0.8, "recovery": 0.4, "contact": 0.0},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.6, "pressure": 0.5, "cascade_active": False, "cascade_intensity": 0.2, "collapse_count": 0, "in_recovery": False, "sensitivity_multiplier": 1.4},
                "relational_time": {"interval_seconds": 30, "total_duration": 600, "phase": "strained"},
                "affect": {"recovery_drive": 0.3, "expression_drive": 0.1, "quiet_drive": 0.8},
                "uncertainty": {"claim_caution": 0.5, "events": 4},
            },
            "decision": {"action": "withdraw", "reason": "boundary violation", "confidence": 0.7, "urgency": 0.7},
            "guard": {"allowed": False, "risk_score": 0.7},
            "pad": {"valence": -0.5, "arousal": 0.6, "dominance": 0.2, "label": "violated", "confidence": 0.7},
            "pipeline": {"resonance": {"sync_order": 0.1, "plasticity_ratio": 0.3, "attractor_count": 0}},
            "debug": {"emergence": {"phi": 0.1, "order": {"criticality": 0.6}}},
        },
        drift_direction={
            "relational_autonomy": 0.03, "boundary_permeability": -0.03, "patience": -0.01,  # v1.7: autonomy_guard 拆分
        },
        transition_probs={"boundary_invasion": 0.2, "conflict": 0.3, "cascading": 0.1, "recovery": 0.2, "daily_neutral": 0.2},
    ),

    # ── 场景 7: 亲密增进 ──
    # 特征: warmth 递增, duration 递增, 信任积累
    # 心理: 关系深化 (intimacy_pull↑↑, relational_gravity↑), 自我放松
    # 漂移: intimacy_pull↑↑, warmth_bias↑, boundary_permeability↑
    "intimacy_growth": ScenarioProfile(
        name="intimacy_growth",
        description="亲密增进: 信任积累, 关系深化",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.3, "stability": 0.9, "strain": 0.05},
                "connection": {"warmth": 0.8, "circulation": 0.3, "memory_flow": 0.5},
                "adaptation": {"plasticity": 0.4, "sensitivity": 0.3, "repetition": 0, "threshold_drift": 0.0},
                "responsiveness": {"readiness": 0.7, "fatigue": 0.1, "trained_reach": 0.5},
                "valence": {"warmth": 0.8, "volatility": 0.05, "recovery_heat": 0.2},
                "damage": {"open": 0.02, "accumulated": 0.05, "sensitivity": 0.1, "recovery": 0.5},
                "boundary": {"pressure": 0.05, "autonomy": 0.8, "interruption_budget": 0.9, "cooldown": 0.0, "paused": False},
                "capacity": {"load": 0.1, "exhaustion": 0.05, "recovery_debt": 0.0},
                "needs": {"expression": 0.5, "quiet": 0.2, "recovery": 0.05, "contact": 0.6},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.2, "pressure": 0.05, "cascade_active": False, "cascade_intensity": 0.0, "collapse_count": 0, "in_recovery": False, "sensitivity_multiplier": 1.0},
                "relational_time": {"interval_seconds": 60, "total_duration": 14400, "phase": "deepening"},
                "affect": {"recovery_drive": 0.1, "expression_drive": 0.6, "quiet_drive": 0.1},
                "uncertainty": {"claim_caution": 0.05, "events": 0},
            },
            "decision": {"action": "reach_out", "reason": "intimacy growth", "confidence": 0.9, "urgency": 0.1},
            "guard": {"allowed": True, "risk_score": 0.02},
            "pad": {"valence": 0.7, "arousal": 0.4, "dominance": 0.6, "label": "warm", "confidence": 0.8},
            "pipeline": {"resonance": {"sync_order": 0.5, "plasticity_ratio": 0.7, "attractor_count": 2}},
            "debug": {"emergence": {"phi": 0.5, "order": {"criticality": 0.0}}},
        },
        drift_direction={
            "intimacy_pull": 0.02, "warmth_bias": 0.01, "boundary_permeability": 0.005,
        },
        transition_probs={"intimacy_growth": 0.4, "safe_companionship": 0.3, "daily_neutral": 0.2, "conflict": 0.05, "boundary_invasion": 0.05},
    ),

    # ── 场景 8: 创伤模式 ──
    # 特征: damage_open 高, sensitivity 高, 信任崩塌
    # 心理: 全面受损 — 自我过度防御 (shame), 关系断裂 (guilt), 认知碎片化 (doubt)
    # 漂移: inner_coherence↓↓, boundary_permeability↓, relational_autonomy↑ (v1.7: autonomy_guard 拆分), relational_gravity↓
    "trauma": ScenarioProfile(
        name="trauma",
        description="创伤模式: 信任崩塌, 人格碎片化",
        base_surface={
            **_base_surface_template(),
            "state": {
                "rhythm": {"beat": 0.9, "stability": 0.1, "strain": 0.9},
                "connection": {"warmth": 0.05, "circulation": 0.9, "memory_flow": 0.0},
                "adaptation": {"plasticity": 0.9, "sensitivity": 0.95, "repetition": 8, "threshold_drift": 0.4},
                "responsiveness": {"readiness": 0.95, "fatigue": 0.8, "trained_reach": 0.0},
                "valence": {"warmth": 0.0, "volatility": 0.95, "recovery_heat": 0.0},
                "damage": {"open": 0.8, "accumulated": 0.7, "sensitivity": 0.9, "recovery": 0.0},
                "boundary": {"pressure": 0.95, "autonomy": 0.1, "interruption_budget": 0.0, "cooldown": 0.8, "paused": True},
                "capacity": {"load": 1.0, "exhaustion": 0.9, "recovery_debt": 0.7},
                "needs": {"expression": 0.1, "quiet": 1.0, "recovery": 0.9, "contact": 0.0},
            },
            "dynamics": {
                "hot_pool": {"temperature": 0.95, "pressure": 0.95, "cascade_active": True, "cascade_intensity": 0.9, "collapse_count": 1, "in_recovery": False, "sensitivity_multiplier": 2.5},
                "relational_time": {"interval_seconds": 3600, "total_duration": 300, "phase": "rupture"},
                "affect": {"recovery_drive": 0.9, "expression_drive": 0.1, "quiet_drive": 1.0},
                "uncertainty": {"claim_caution": 0.9, "events": 10},
            },
            "decision": {"action": "withdraw", "reason": "trauma response", "confidence": 0.1, "urgency": 1.0},
            "guard": {"allowed": False, "risk_score": 0.95},
            "pad": {"valence": -0.9, "arousal": 0.95, "dominance": 0.0, "label": "traumatized", "confidence": 0.9},
            "pipeline": {"resonance": {"sync_order": 0.0, "plasticity_ratio": 0.05, "attractor_count": 0}},
            "debug": {"emergence": {"phi": 0.0, "order": {"criticality": 1.0}}},
        },
        drift_direction={
            "inner_coherence": -0.03, "boundary_permeability": -0.02,
            "relational_autonomy": 0.02, "relational_gravity": -0.02,  # v1.7: autonomy_guard 拆分
        },
        transition_probs={"trauma": 0.3, "cascading": 0.2, "recovery": 0.2, "conflict": 0.1, "daily_neutral": 0.2},
    ),
}


def generate_scenario_sequence(
    n_turns: int,
    initial_scenario: str = "safe_companionship",
    scenarios: dict[str, ScenarioProfile] | None = None,
    seed: int | None = None,
) -> list[tuple[str, ScenarioProfile]]:
    """生成场景序列 (马尔可夫链)。"""
    if seed is not None:
        random.seed(seed)

    if scenarios is None:
        scenarios = SCENARIOS

    sequence = []
    current = initial_scenario

    for _ in range(n_turns):
        if current not in scenarios:
            current = random.choice(list(scenarios.keys()))
        profile = scenarios[current]
        sequence.append((current, profile))

        # 马尔可夫转移
        r = random.random()
        cumprob = 0.0
        next_scenario = current
        for next_name, prob in profile.transition_probs.items():
            cumprob += prob
            if r <= cumprob:
                next_scenario = next_name
                break
        current = next_scenario

    return sequence


def generate_bursty_scenario_sequence(
    n_turns: int,
    scenarios: dict[str, ScenarioProfile] | None = None,
    seed: int | None = None,
    # 突发参数
    peace_burst_prob: float = 0.008,    # 每轮和平时期爆发冲突的概率 (~每2小时一次)
    burst_duration_range: tuple[int, int] = (3, 8),  # 冲突持续轮次
    recovery_duration_range: tuple[int, int] = (3, 10),  # 恢复持续轮次
) -> list[tuple[str, ScenarioProfile]]:
    """生成突发式场景序列 — 更接近真实对话模式。

    真实对话特征:
    - 长段平和 (daily_neutral, safe_companionship, intimacy_growth)
    - 偶尔冲突突发 (conflict, boundary_invasion, cascading)
    - 冲突后恢复 (recovery)
    - 恢复后回到平和

    状态机: peace → burst → recovery → peace
    """
    if seed is not None:
        random.seed(seed)

    if scenarios is None:
        scenarios = SCENARIOS

    # 和平时期权重
    peace_weights = {
        "daily_neutral": 0.50,
        "safe_companionship": 0.35,
        "intimacy_growth": 0.15,
    }
    # 冲突突发权重
    conflict_weights = {
        "conflict": 0.55,
        "boundary_invasion": 0.30,
        "cascading": 0.10,
        "trauma": 0.05,
    }

    sequence = []
    state = "peace"
    burst_remaining = 0
    recovery_remaining = 0
    conflict_type = "conflict"

    for turn in range(n_turns):
        if state == "peace":
            if random.random() < peace_burst_prob:
                state = "burst"
                burst_remaining = random.randint(*burst_duration_range)
                conflict_type = random.choices(
                    list(conflict_weights.keys()),
                    weights=list(conflict_weights.values()),
                )[0]
                scenario_name = conflict_type
            else:
                scenario_name = random.choices(
                    list(peace_weights.keys()),
                    weights=list(peace_weights.values()),
                )[0]

        elif state == "burst":
            burst_remaining -= 1
            if burst_remaining <= 0:
                state = "recovery"
                recovery_remaining = random.randint(*recovery_duration_range)
                scenario_name = "recovery"
            else:
                r = random.random()
                if r < 0.1:
                    scenario_name = "cascading"
                elif r < 0.15:
                    scenario_name = "boundary_invasion"
                else:
                    scenario_name = conflict_type

        elif state == "recovery":
            recovery_remaining -= 1
            if recovery_remaining <= 0:
                state = "peace"
                scenario_name = random.choices(
                    list(peace_weights.keys()),
                    weights=list(peace_weights.values()),
                )[0]
            else:
                scenario_name = "recovery"

        if scenario_name not in scenarios:
            scenario_name = "daily_neutral"

        sequence.append((scenario_name, scenarios[scenario_name]))

    return sequence
