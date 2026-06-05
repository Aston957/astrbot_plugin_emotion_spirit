"""Surface 消费者 — 解析 Sylanne Surface ~60 字段 → SemanticSignals。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import EMA_ALPHA
from .emotion_classifier import (
    classify_distribution,
    classify_primary_secondary,
)
from .trend_utils import EMASmoother


@dataclass
class SemanticSignals:
    """从 Surface 提取的语义信号，所有模块从这里读取数据。"""

    # rhythm
    rhythm_beat: float = 0.0
    rhythm_stability: float = 0.5
    rhythm_strain: float = 0.0

    # connection
    connection_warmth: float = 0.4
    connection_circulation: float = 0.0
    connection_memory_flow: float = 0.0

    # adaptation
    adaptation_plasticity: float = 0.0
    adaptation_sensitivity: float = 0.0
    adaptation_repetition: int = 0
    adaptation_threshold_drift: float = 0.0

    # responsiveness
    responsiveness_readiness: float = 0.2
    responsiveness_fatigue: float = 0.0
    responsiveness_trained_reach: float = 0.0

    # valence
    valence_warmth: float = 0.45
    valence_volatility: float = 0.0
    valence_repair_heat: float = 0.0

    # damage
    damage_open: float = 0.0
    damage_accumulated: float = 0.0
    damage_sensitivity: float = 0.0
    damage_recovery: float = 0.0

    # boundary
    boundary_pressure: float = 0.0
    boundary_autonomy: float = 1.0
    boundary_budget: float = 1.0
    boundary_cooldown: float = 0.0
    boundary_paused: bool = False

    # capacity
    capacity_load: float = 0.0
    capacity_exhaustion: float = 0.0
    capacity_recovery_debt: float = 0.0

    # needs
    needs_expression: float = 0.0
    needs_quiet: float = 0.0
    needs_recovery: float = 0.0
    needs_contact: float = 0.0

    # hot_pool
    hot_pool_temperature: float = 0.0
    hot_pool_pressure: float = 0.0
    cascade_active: bool = False
    cascade_intensity: float = 0.0
    collapse_count: int = 0
    in_recovery: bool = False
    sensitivity_multiplier: float = 1.0

    # decision
    decision_action: str = "hold"
    decision_reason: str = ""
    decision_confidence: float = 0.5
    decision_urgency: float = 0.0

    # guard
    guard_allowed: bool = True
    guard_risk_score: float = 0.0

    # personality (11 维)
    personality_deep: dict[str, float] = field(default_factory=dict)
    personality_surface: dict[str, float] = field(default_factory=dict)

    # relational_time
    relational_interval: float = 0.0
    relational_duration: float = 0.0
    relational_phase: str = "active"

    # affect
    affect_recovery_drive: float = 0.0
    affect_expression_drive: float = 0.0
    affect_quiet_drive: float = 0.0

    # uncertainty
    uncertainty_claim_caution: float = 0.0
    uncertainty_events: int = 0

    # pad
    pad_valence: float = 0.0
    pad_arousal: float = 0.0
    pad_dominance: float = 0.5
    pad_label: str = "neutral"
    pad_confidence: float = 0.5
    # 新增：v1.1.1 情绪表示升级
    pad_distribution: dict[str, float] = field(
        default_factory=lambda: {"neutral": 1.0}
    )
    pad_primary: str = "neutral"
    pad_secondary: str | None = None
    pad_intensity: float = 0.0  # = arousal

    # 共振场 (v2, EMA 平滑后)
    sync_order_smoothed: float = 0.0
    phi_smoothed: float = 0.0
    chi_smoothed: float = 0.0
    plasticity_ratio: float = 0.5
    attractor_count: int = 0

    # 派生信号
    body_integration: float = 0.5
    body_criticality: float = 0.0


class SurfaceConsumer:
    """解析 Sylanne Surface → SemanticSignals，含 EMA 平滑和派生计算。"""

    def __init__(self) -> None:
        self._phi_smoother = EMASmoother(EMA_ALPHA["phi"])
        self._chi_smoother = EMASmoother(EMA_ALPHA["chi"])
        self._sync_smoother = EMASmoother(EMA_ALPHA["sync_order"])
        self._integration_smoother = EMASmoother(EMA_ALPHA["body_integration"])
        self._criticality_smoother = EMASmoother(EMA_ALPHA["body_criticality"])

    def consume(self, surface: dict[str, Any]) -> SemanticSignals:
        """解析 Surface，返回 SemanticSignals。"""
        state = surface.get("state") or {}
        dynamics = surface.get("dynamics") or {}
        decision = surface.get("decision") or {}
        guard = surface.get("guard") or {}
        personality = surface.get("personality") or {}
        pad = surface.get("pad") or {}
        pipeline = surface.get("pipeline") or {}
        debug = surface.get("debug") or {}

        # 解析 body state
        rhythm = state.get("rhythm", {})
        conn = state.get("connection", {})
        adapt = state.get("adaptation", {})
        resp = state.get("responsiveness", {})
        val = state.get("valence", {})
        dmg = state.get("damage", {})
        bnd = state.get("boundary", {})
        cap = state.get("capacity", {})
        needs = state.get("needs", {})

        # 解析 dynamics
        hp = dynamics.get("hot_pool", {})
        rt = dynamics.get("relational_time", {})
        affect = dynamics.get("affect", {})
        unc = dynamics.get("uncertainty", {})

        # 解析共振场
        resonance = pipeline.get("resonance", {}) if pipeline else {}
        debug_dict = debug if isinstance(debug, dict) else {}
        emergence = debug_dict.get("emergence", {})
        order = emergence.get("order", {})

        raw_sync = float(resonance.get("sync_order", 0.0))
        raw_phi = float(emergence.get("phi", 0.0))
        raw_chi = float(order.get("criticality", 0.0))

        signals = SemanticSignals(
            rhythm_beat=float(rhythm.get("beat", 0.0)),
            rhythm_stability=float(rhythm.get("stability", 0.5)),
            rhythm_strain=float(rhythm.get("strain", 0.0)),
            connection_warmth=float(conn.get("warmth", 0.4)),
            connection_circulation=float(conn.get("circulation", 0.0)),
            connection_memory_flow=float(conn.get("memory_flow", 0.0)),
            adaptation_plasticity=float(adapt.get("plasticity", 0.0)),
            adaptation_sensitivity=float(adapt.get("sensitivity", 0.0)),
            adaptation_repetition=int(adapt.get("repetition", 0)),
            adaptation_threshold_drift=float(adapt.get("threshold_drift", 0.0)),
            responsiveness_readiness=float(resp.get("readiness", 0.2)),
            responsiveness_fatigue=float(resp.get("fatigue", 0.0)),
            responsiveness_trained_reach=float(resp.get("trained_reach", 0.0)),
            valence_warmth=float(val.get("warmth", 0.45)),
            valence_volatility=float(val.get("volatility", 0.0)),
            valence_repair_heat=float(val.get("recovery_heat", 0.0)),
            damage_open=float(dmg.get("open", 0.0)),
            damage_accumulated=float(dmg.get("accumulated", 0.0)),
            damage_sensitivity=float(dmg.get("sensitivity", 0.0)),
            damage_recovery=float(dmg.get("recovery", 0.0)),
            boundary_pressure=float(bnd.get("pressure", 0.0)),
            boundary_autonomy=float(bnd.get("autonomy", 1.0)),
            boundary_budget=float(bnd.get("interruption_budget", 1.0)),
            boundary_cooldown=float(bnd.get("cooldown", 0.0)),
            boundary_paused=bool(bnd.get("paused", False)),
            capacity_load=float(cap.get("load", 0.0)),
            capacity_exhaustion=float(cap.get("exhaustion", 0.0)),
            capacity_recovery_debt=float(cap.get("recovery_debt", 0.0)),
            needs_expression=float(needs.get("expression", 0.0)),
            needs_quiet=float(needs.get("quiet", 0.0)),
            needs_recovery=float(needs.get("recovery", 0.0)),
            needs_contact=float(needs.get("contact", 0.0)),
            hot_pool_temperature=float(hp.get("temperature", 0.0)),
            hot_pool_pressure=float(hp.get("pressure", 0.0)),
            cascade_active=bool(hp.get("cascade_active", False)),
            cascade_intensity=float(hp.get("cascade_intensity", 0.0)),
            collapse_count=int(hp.get("collapse_count", 0)),
            in_recovery=bool(hp.get("in_recovery", False)),
            sensitivity_multiplier=float(hp.get("sensitivity_multiplier", 1.0)),
            decision_action=str(decision.get("action", "hold")),
            decision_reason=str(decision.get("reason", "")),
            decision_confidence=float(decision.get("confidence", 0.5)),
            decision_urgency=float(decision.get("urgency", 0.0)),
            guard_allowed=bool(guard.get("allowed", True)),
            guard_risk_score=float(guard.get("risk_score", 0.0)),
            personality_deep=dict(personality.get("deep", {})),
            personality_surface=dict(personality.get("surface", {})),
            relational_interval=float(rt.get("interval_seconds", 0.0)),
            relational_duration=float(rt.get("total_duration", 0.0)),
            relational_phase=str(rt.get("phase", "active")),
            affect_recovery_drive=float(affect.get("recovery_drive", 0.0)),
            affect_expression_drive=float(affect.get("expression_drive", 0.0)),
            affect_quiet_drive=float(affect.get("quiet_drive", 0.0)),
            uncertainty_claim_caution=float(unc.get("claim_caution", 0.0)),
            uncertainty_events=int(unc.get("events", 0)),
            pad_valence=float(pad.get("valence", 0.0)),
            pad_arousal=float(pad.get("arousal", 0.0)),
            pad_dominance=float(pad.get("dominance", 0.5)),
            pad_label=str(pad.get("label", "neutral")),
            pad_confidence=float(pad.get("confidence", 0.5)),
            sync_order_smoothed=self._sync_smoother.update(raw_sync),
            phi_smoothed=self._phi_smoother.update(raw_phi),
            chi_smoothed=self._chi_smoother.update(raw_chi),
            plasticity_ratio=float(resonance.get("plasticity_ratio", 0.5)),
            attractor_count=int(resonance.get("attractor_count", 0)),
        )

        # 派生信号
        signals.body_integration = self._compute_body_integration(signals)
        signals.body_criticality = self._compute_body_criticality(signals)

        # 派生信号 EMA
        self._integration_smoother.update(signals.body_integration)
        self._criticality_smoother.update(signals.body_criticality)

        # v1.1.1: 情绪分类（从 PAD 原始值计算）
        pad_tuple = (signals.pad_valence, signals.pad_arousal, signals.pad_dominance)
        signals.pad_distribution = classify_distribution(pad_tuple)
        primary, secondary = classify_primary_secondary(
            signals.pad_distribution, pad=pad_tuple
        )
        signals.pad_primary = primary
        signals.pad_secondary = secondary
        signals.pad_intensity = signals.pad_arousal

        return signals

    def _compute_body_integration(self, s: SemanticSignals) -> float:
        """7 子系统方向一致性 — 替代 Φ 的空间维度。"""
        directions = [
            s.rhythm_strain,
            s.valence_volatility,
            s.damage_open,
            s.boundary_pressure,
            s.needs_expression,
            s.capacity_exhaustion,
            1.0 - s.connection_warmth,
        ]
        mean_d = sum(directions) / len(directions)
        var_d = sum((d - mean_d) ** 2 for d in directions) / len(directions)
        return max(0.0, 1.0 - var_d * 4.0)

    def _compute_body_criticality(self, s: SemanticSignals) -> float:
        """多指标极端度 — 替代 χ 的临界检测。"""
        extreme_count = sum([
            s.rhythm_strain > 0.7,
            s.damage_open > 0.5,
            s.boundary_pressure > 0.7,
            s.capacity_exhaustion > 0.6,
            s.cascade_active,
            s.valence_volatility > 0.5,
        ])
        return min(1.0, extreme_count / 3.0)
