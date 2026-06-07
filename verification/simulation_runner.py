"""蒙特卡洛运行器 — N 轮模拟，记录完整状态快照。

输出:
1. simulation_data/turns.csv — 每轮状态 (人格参数、权重、压力、tension 等)
2. simulation_report.md — 摘要报告
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from emotion_spirit.superego import (
    ValueResistance, ValueAlignment, ConscienceTracker, IdealSelf,
)
from emotion_spirit.superego_guard import SuperegoGuard
from emotion_spirit.surface_consumer import SurfaceConsumer
from emotion_spirit.personality_drift import PersonalityDrift
from emotion_spirit.meaning_reservoir import MeaningReservoir
from emotion_spirit.buffer_signals import BufferSignals
from emotion_spirit.memory_pool import MemoryPool
from emotion_spirit.intimacy import IntimacyTracker
from emotion_spirit.label_mapper import labels_to_personality, _BASELINE

from surface_generator import ScenarioProfile, SCENARIOS, generate_scenario_sequence, generate_bursty_scenario_sequence
from drift_simulator import DriftSimulator


@dataclass
class TurnSnapshot:
    """一轮模拟的状态快照。"""
    turn: int
    scenario: str
    action: str
    # 11 维人格参数
    personality_deep: dict[str, float]
    personality_surface: dict[str, float]
    # 权重分化
    weights: dict[str, float]
    core_dims: list[str]
    # 价值抵抗
    resistance: float
    conflict_values: list[str]
    aligned_values: list[str]
    tension_type: str | None
    behavioral_shift: float
    conscience_impact: float
    # 良心
    pressure: float
    # 对齐
    alignment_score: float
    alignment_trend: float
    # 理想自我
    ideal_gap: float
    # 基线距离
    baseline_gap: float
    # 安全层
    safety_level: str
    # 漂移
    drift_count: int


class SimulationRunner:
    """蒙特卡洛模拟运行器。"""

    def __init__(
        self,
        labels: dict[str, str],
        n_turns: int = 1000,
        seed: int | None = None,
        output_dir: str = "output/simulation_data",
        tick_minutes: float = 5.0,       # 每轮间隔分钟数 (默认5分钟, 更接近真实对话节奏)
        bursty: bool = True,             # 使用突发式场景生成
    ) -> None:
        self._labels = labels
        self._n_turns = n_turns
        self._seed = seed
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._tick_hours = tick_minutes / 60.0
        self._bursty = bursty

        if seed is not None:
            random.seed(seed)

        # 初始化漂移模拟器
        self._drift_sim = DriftSimulator(labels)

        # 初始化 emotion_spirit 各模块
        baseline = labels_to_personality(labels)
        self._consumer = SurfaceConsumer()
        self._pool = MemoryPool()
        self._intimacy = IntimacyTracker()
        self._conscience = ConscienceTracker()
        self._alignment = ValueAlignment("sim")
        self._vr = ValueResistance("sim")
        self._vr._baseline_personality = baseline
        self._vr._interaction_count = 0
        self._ideal = IdealSelf("sim", labels)
        self._guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, "sim",
        )
        self._reservoir = MeaningReservoir()
        self._drift = PersonalityDrift(self._consumer, self._reservoir)

        self._snapshots: list[TurnSnapshot] = []

    def run(self) -> list[TurnSnapshot]:
        """运行完整模拟。"""
        if self._bursty:
            scenario_sequence = generate_bursty_scenario_sequence(
                self._n_turns, SCENARIOS, self._seed,
            )
        else:
            scenario_sequence = generate_scenario_sequence(
                self._n_turns, "safe_companionship", SCENARIOS, self._seed,
            )

        for turn, (scenario_name, scenario_profile) in enumerate(scenario_sequence, 1):
            # 推进漂移
            is_cascade = scenario_name in ("cascading",)
            is_trauma = scenario_name in ("trauma",)
            personality = self._drift_sim.step(
                scenario_drift=scenario_profile.drift_direction,
                is_cascade=is_cascade,
                is_trauma=is_trauma,
            )

            # 生成合成 Surface
            surface = scenario_profile.generate_surface(personality, turn)

            # 消费 Surface
            signals = self._consumer.consume(surface)

            # 更新交互计数
            self._vr._interaction_count = turn
            self._vr._baseline_personality = labels_to_personality(self._labels)

            # 价值抵抗计算
            action = signals.decision_action
            context = {
                "body_criticality": signals.body_criticality,
                "cascade_active": signals.cascade_active,
                "intimacy": self._intimacy.get_intimacy("sim_user", "sim") if hasattr(self._intimacy, 'get_intimacy') else 0.5,
            }
            stress_level = min(1.0, signals.body_criticality + (0.5 if signals.cascade_active else 0.0))

            resistance_result = self._vr.compute(
                action=action, context=context,
                current_personality=personality, stress_level=stress_level,
            )

            # 良心事件记录
            if resistance_result.conflict_values:
                self._conscience.record_value_conflict(
                    resistance=resistance_result.resistance,
                    conflict_values=resistance_result.conflict_values,
                    tension_type=resistance_result.tension_type or "guilt",
                    behavioral_shift=resistance_result.behavioral_shift,
                    conscience_impact=resistance_result.conscience_impact,
                )
            elif resistance_result.aligned_values:
                for v in resistance_result.aligned_values:
                    self._conscience.record_alignment(v, action)

            if not signals.guard_allowed:
                self._conscience.record_guard_reflex(signals.guard_risk_score, "sim")

            if signals.cascade_active:
                self._conscience.record_cascade(signals.cascade_intensity)

            self._conscience.tick_pressure(self._tick_hours)  # 每轮间隔时间

            # 对齐记录
            self._alignment.record(action)

            # 安全层评估
            intervention = self._guard.assess({}, personality)

            # 漂移检测
            self._drift.update(signals)
            drifts = self._drift.check_drift()

            # 理想自我
            ideal_gap = self._ideal.compute_gap(personality)

            # 记录快照
            snapshot = TurnSnapshot(
                turn=turn,
                scenario=scenario_name,
                action=action,
                personality_deep=dict(personality["deep"]),
                personality_surface=dict(personality["surface"]),
                weights=dict(self._vr._values),  # compute() 后已被更新
                core_dims=sorted(
                    self._vr._values.items(), key=lambda x: x[1], reverse=True
                )[:5] if self._vr._values else [],
                resistance=resistance_result.resistance,
                conflict_values=resistance_result.conflict_values,
                aligned_values=resistance_result.aligned_values,
                tension_type=resistance_result.tension_type,
                behavioral_shift=resistance_result.behavioral_shift,
                conscience_impact=resistance_result.conscience_impact,
                pressure=self._conscience.get_pressure(),
                alignment_score=self._alignment.get_score(),
                alignment_trend=self._alignment.get_trend(),
                ideal_gap=ideal_gap,
                baseline_gap=self._drift_sim.compute_gap_from_baseline(),
                safety_level=intervention.level,
                drift_count=len(drifts),
            )
            self._snapshots.append(snapshot)

            # 更新亲密模块 (简化)
            try:
                self._intimacy.update("sim_user", temporal_hours=0.1, interval_seconds=60)
            except Exception:
                pass

            # 更新意义蓄水
            try:
                self._reservoir.accumulate(signals.phi_smoothed, 0.3)
            except Exception:
                pass

        return self._snapshots

    def save_csv(self, filename: str = "turns.csv") -> Path:
        """保存快照到 CSV。"""
        filepath = self._output_dir / filename
        if not self._snapshots:
            return filepath

        fieldnames = [
            "turn", "scenario", "action", "resistance", "tension_type",
            "behavioral_shift", "conscience_impact", "pressure",
            "alignment_score", "alignment_trend", "ideal_gap", "baseline_gap",
            "safety_level", "drift_count",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in self._snapshots:
                writer.writerow({
                    "turn": s.turn, "scenario": s.scenario, "action": s.action,
                    "resistance": s.resistance, "tension_type": s.tension_type or "",
                    "behavioral_shift": s.behavioral_shift, "conscience_impact": s.conscience_impact,
                    "pressure": s.pressure, "alignment_score": s.alignment_score,
                    "alignment_trend": s.alignment_trend, "ideal_gap": s.ideal_gap,
                    "baseline_gap": s.baseline_gap, "safety_level": s.safety_level,
                    "drift_count": s.drift_count,
                })

        # 保存人格参数到单独的 JSON
        personality_data = []
        for s in self._snapshots:
            personality_data.append({
                "turn": s.turn,
                "deep": s.personality_deep,
                "surface": s.personality_surface,
                "weights": s.weights,
            })
        with open(self._output_dir / "personality_trace.json", "w", encoding="utf-8") as f:
            json.dump(personality_data, f, ensure_ascii=False, indent=2)

        return filepath


# ═══ Phase C (Task C3) 新增: gossip_tendency 仿真入口 ═══

def run_simulation(
    persona_id: str,
    scenario: str,
    steps: int = 10,
) -> dict[str, Any]:
    """单人 + 单 scenario 仿真 (5 persona × 8 scenarios 入口)。

    Phase C (Task C3): gossip_tendency 真消费点验证
      - 报告字段包含 gossip_tendency (13 维)
      - 中性话题不漂移, gossip 话题漂移

    Args:
        persona_id: 5 persona 之一 (INFP-A, ISTJ-S, ENTP-AV, ISFJ-D, ESTP-A)
        scenario: 8 scenarios 之一
        steps: 仿真步数 (默认 10)

    Returns:
        {
            "persona_id": str,
            "scenario": str,
            "personality": dict[str, float],   # 13 维 flat, 含 gossip_tendency
            "trajectory": list[dict[str, float]],  # 每步快照
        }
    """
    # 委托给 drift_simulator.simulate_persona (单一实现)
    from drift_simulator import simulate_persona
    return simulate_persona(persona_id=persona_id, scenario=scenario, steps=steps)
