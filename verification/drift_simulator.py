"""13 维漂移模拟器 — 模拟 SylannEngine 持有的人格参数在长期对话中的演变。

v1.7.2: 12 维 → 13 维 (+gossip_tendency)
v1.7:   11 维 → 12 维 (autonomy_guard 拆分为 relational_autonomy + exploration_openness)

漂移规则:
1. 每轮小漂移: ±0.005~0.03 (由场景和 MBTI+依恋风格约束方向)
2. EMA 回归: 每轮向基线拉回 0.1%~0.5% (深层维度回归力更强)
3. 大事件冲击: 级联/创伤事件可产生一次性大偏移 (±0.05~0.15)
4. Clamp 到 [0, 1]
5. 深层维度变化率为表层的 40% (基于 Roberts & DelVecchio, 2000)

Phase C (Task C3): 新增 gossip_tendency 真消费点仿真
  - DriftSimulator(persona_id=X) 从 KnowledgeBase 读 baseline
  - process_message(topic="gossip", content=...) 触发 gossip_tendency 漂移
  - simulate_persona() 5 persona × 8 scenarios 仿真入口
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from emotion_spirit.label_mapper import labels_to_personality, _BASELINE
from emotion_spirit.knowledge import KnowledgeBase


DEEP_DIMS = [
    "expression_drive", "perception_acuity", "boundary_permeability",
    "inner_coherence", "relational_gravity",
]

SURFACE_DIMS = [
    "warmth_bias", "directness", "curiosity",
    "patience", "intimacy_pull",
    # v1.7: autonomy_guard 拆分为 2 维
    "relational_autonomy", "exploration_openness",
    # v1.7.2: +gossip_tendency (13 维)
    "gossip_tendency",
]

# 每轮的回归强度 (深层 vs 表层)
# v1.7.1: 0.001→0.005 (5x 增强) — 原 0.001 太弱, 1000 轮后 noise 累计 std=0.158 主导
# 新 0.005: 1000 轮后 baseline retention = exp(-5) ≈ 0.7%, half-life = 138 turn (合理)
DEEP_REGRESSION_RATE = 0.010   # 0.2%/轮 → 1.0%/轮 (5x)
SURFACE_REGRESSION_RATE = 0.005  # 0.1%/轮 → 0.5%/轮 (5x)

# gossip 话题触发 gossip_tendency 漂移的速率 (每步)
GOSSIP_DRIFT_STEP = 0.01

# 识别 gossip 内容的关键字
_GOSSIP_KEYWORDS = ("八卦", "说", "听说", "传闻", "据说")


def _is_gossip_content(content: str) -> bool:
    """判断消息内容是否是 gossip (包含 gossip 关键字)。"""
    return any(kw in content for kw in _GOSSIP_KEYWORDS)


def _labels_to_persona_id(labels: dict[str, str]) -> str | None:
    """从 labels 反推 persona_id (用于在 KnowledgeBase 中查询 baseline)。

    简单映射: mbti + attachment 决定 persona_id。
    """
    mbti = labels.get("mbti", "").upper()
    attachment = labels.get("attachment", "")
    if not mbti or len(mbti) < 4:
        return None
    # 简化: 5 persona 跟 mbti+attachment 一一对应
    mbti_letter = mbti[:4]
    # 用 KnowledgeBase 验证
    for pid in KnowledgeBase.PERSONA_BASELINES:
        # 只取 mbti 前缀对比
        if pid.startswith(mbti_letter[:4]):
            return pid
    return None


class DriftSimulator:
    """模拟 SylannEngine 13 维人格参数的长期漂移 (v1.7.2: 12→13)。

    支持两种构造方式:
      1. DriftSimulator(persona_id="INFP-A")  ← 读 KnowledgeBase.PERSONA_BASELINES
      2. DriftSimulator(initial_labels={...})  ← 旧 API, 用 labels_to_personality 算 baseline

    Phase C 新增方法 (gossip_tendency 真消费点仿真):
      - get_initial_personality() → flat dict {dim: value} (13 维)
      - get_current_personality() → flat dict {dim: value} (13 维)
      - process_message(topic, content) → 触发 gossip 漂移
      - run_drift_check() → 记录历史
    """

    def __init__(
        self,
        arg: "str | dict[str, str] | None" = None,
        *,
        persona_id: "str | None" = None,
        initial_labels: "dict[str, str] | None" = None,
    ) -> None:
        # 支持两种调用方式:
        # 1. DriftSimulator(persona_id="INFP-A")  ← 新 API (Phase C)
        # 2. DriftSimulator(initial_labels={...})  ← 旧 API (显式 kwargs)
        # 3. DriftSimulator(labels_dict)  ← 旧 API (positional dict, 向后兼容)
        # 4. DriftSimulator("INFP-A")  ← 新 API (positional str, 简短)
        if persona_id is not None and initial_labels is not None:
            raise TypeError("persona_id 和 initial_labels 不能同时指定")

        if arg is not None and not isinstance(arg, (str, dict)):
            raise TypeError(
                f"DriftSimulator 第一参数必须是 str 或 dict, 收到 {type(arg).__name__}"
            )

        if arg is None:
            # 全用 keyword args
            effective_persona_id = persona_id
            effective_labels = initial_labels
        elif isinstance(arg, str):
            effective_persona_id = arg
            effective_labels = initial_labels
        else:  # dict
            effective_persona_id = persona_id
            effective_labels = arg

        if effective_persona_id is not None and effective_labels is not None:
            raise TypeError("persona_id 和 initial_labels 不能同时指定")

        if effective_persona_id is not None:
            # Phase C 新路径: 从 KnowledgeBase 读 baseline
            self._persona_id = effective_persona_id
            self._labels = None
            baseline_flat = KnowledgeBase.get_persona_baseline(effective_persona_id)
            # 拆成 deep / surface 两层 (跟旧 API 兼容)
            self._baseline = {
                "deep": {d: baseline_flat[d] for d in DEEP_DIMS if d in baseline_flat},
                "surface": {d: baseline_flat[d] for d in SURFACE_DIMS if d in baseline_flat},
            }
            # 完整 flat baseline (13 维)
            self._initial_flat = dict(baseline_flat)
        elif effective_labels is not None:
            # 旧 API: 保留向后兼容
            self._persona_id = None
            self._labels = effective_labels
            self._baseline = labels_to_personality(effective_labels)
            # flat 形式
            self._initial_flat = {
                **{k: v for k, v in self._baseline["deep"].items()},
                **{k: v for k, v in self._baseline["surface"].items()},
            }
        else:
            raise TypeError(
                "DriftSimulator 需要 persona_id 或 initial_labels 参数之一"
            )

        self._current = {
            "deep": dict(self._baseline["deep"]),
            "surface": dict(self._baseline["surface"]),
        }
        # flat 形式 (Phase C 新增)
        self._current_flat = dict(self._initial_flat)
        self._turn = 0
        self._history: list[dict[str, float]] = []

    # ═══ 旧 API (向后兼容) ═══

    @property
    def current(self) -> dict[str, dict[str, float]]:
        return {
            "deep": dict(self._current["deep"]),
            "surface": dict(self._current["surface"]),
        }

    @property
    def baseline(self) -> dict[str, dict[str, float]]:
        return {
            "deep": dict(self._baseline["deep"]),
            "surface": dict(self._baseline["surface"]),
        }

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def persona_id(self) -> str | None:
        return self._persona_id

    def step(
        self,
        scenario_drift: dict[str, float] | None = None,
        is_cascade: bool = False,
        is_trauma: bool = False,
    ) -> dict[str, dict[str, float]]:
        """推进一轮漂移 (旧 API, 12 维 random walk + EMA 回归)。

        Phase C: 增加了 gossip_tendency 维度 (13 维)。

        Args:
            scenario_drift: 场景驱动的方向性漂移 (dim → delta)
            is_cascade: 是否级联事件 (产生大偏移)
            is_trauma: 是否创伤事件 (产生大偏移)

        Returns:
            更新后的 personality (deep + surface)
        """
        self._turn += 1

        for dim in DEEP_DIMS:
            baseline_val = self._baseline["deep"].get(dim, 0.5)
            current_val = self._current["deep"][dim]
            regression = (baseline_val - current_val) * DEEP_REGRESSION_RATE

            noise = random.gauss(0, 0.003)

            scenario_delta = 0.0
            if scenario_drift and dim in scenario_drift:
                scenario_delta = scenario_drift[dim] * 0.4  # 深层变化率 = 表层的 40%

            event_delta = 0.0
            if is_cascade:
                event_delta = random.gauss(0, 0.04)
            if is_trauma:
                event_delta = random.gauss(0, 0.08)

            self._current["deep"][dim] = max(0.0, min(1.0,
                current_val + regression + noise + scenario_delta + event_delta
            ))

        for dim in SURFACE_DIMS:
            baseline_val = self._baseline["surface"].get(dim, 0.5)
            current_val = self._current["surface"][dim]
            regression = (baseline_val - current_val) * SURFACE_REGRESSION_RATE

            noise = random.gauss(0, 0.005)

            scenario_delta = 0.0
            if scenario_drift and dim in scenario_drift:
                scenario_delta = scenario_drift[dim]

            event_delta = 0.0
            if is_cascade:
                event_delta = random.gauss(0, 0.06)
            if is_trauma:
                event_delta = random.gauss(0, 0.12)

            self._current["surface"][dim] = max(0.0, min(1.0,
                current_val + regression + noise + scenario_delta + event_delta
            ))

        # 同步 flat (Phase C)
        self._sync_flat()
        return self.current

    def compute_gap_from_baseline(self) -> float:
        """当前人格与基线的欧氏距离 (旧 API)。"""
        total_sq = 0.0
        count = 0
        for layer in ("deep", "surface"):
            for dim in self._baseline[layer]:
                current_val = self._current[layer][dim]
                baseline_val = self._baseline[layer][dim]
                total_sq += (current_val - baseline_val) ** 2
                count += 1
        return math.sqrt(total_sq / count) if count > 0 else 0.0

    # ═══ Phase C 新 API (gossip_tendency 真消费点) ═══

    def get_initial_personality(self) -> dict[str, float]:
        """返回初始 baseline (flat dict, 13 维, 含 gossip_tendency)。"""
        return dict(self._initial_flat)

    def get_current_personality(self) -> dict[str, float]:
        """返回当前 personality (flat dict, 13 维, 含 gossip_tendency)。"""
        return dict(self._current_flat)

    def process_message(self, topic: str, content: str) -> None:
        """处理一则消息, 触发 personality drift (gossip_tendency 真消费点)。

        漂移规则:
          - topic="gossip" + content 含 gossip 关键字 → gossip_tendency +GOSSIP_DRIFT_STEP
          - topic="neutral" → 无 gossip_tendency 漂移
          - 其他 topic → 无 gossip_tendency 漂移
        """
        if topic == "gossip" and _is_gossip_content(content):
            current_gt = self._current_flat.get("gossip_tendency", 0.5)
            self._current_flat["gossip_tendency"] = min(
                1.0, current_gt + GOSSIP_DRIFT_STEP,
            )
            # 同步分层结构
            if "gossip_tendency" in self._current["surface"]:
                self._current["surface"]["gossip_tendency"] = min(
                    1.0, current_gt + GOSSIP_DRIFT_STEP,
                )

    def run_drift_check(self) -> None:
        """跑 drift 检查 (记录历史快照)。"""
        self._history.append(dict(self._current_flat))
        self._turn += 1

    def _sync_flat(self) -> None:
        """同步 flat dict 跟分层结构。"""
        for k, v in self._current["deep"].items():
            self._current_flat[k] = v
        for k, v in self._current["surface"].items():
            self._current_flat[k] = v


# ═══ Module-level 仿真函数 (Phase C 新增) ═══

# 8 scenarios (跟 plan spec 一致)
_SCENARIOS: list[str] = [
    "neutral_only", "gossip_topic_heavy", "emotional_support",
    "conflict_resolution", "celebration", "complaint_handling",
    "long_silence", "rapid_topic_change",
]

# scenario → topic 映射
_SCENARIO_TOPIC: dict[str, str] = {
    "neutral_only": "neutral",
    "gossip_topic_heavy": "gossip",
    # 其他 6 个 scenario 默认 neutral (本任务只关注 gossip_tendency)
    "emotional_support": "neutral",
    "conflict_resolution": "neutral",
    "celebration": "neutral",
    "complaint_handling": "neutral",
    "long_silence": "neutral",
    "rapid_topic_change": "neutral",
}


def simulate_persona(
    persona_id: str,
    scenario: str,
    steps: int = 20,
) -> dict[str, Any]:
    """单人 + 单 scenario 仿真 (5 persona × 8 scenarios 入口)。

    Args:
        persona_id: 5 persona 之一 (INFP-A, ISTJ-S, ENTP-AV, ISFJ-D, ESTP-A)
        scenario: 8 scenarios 之一
        steps: 仿真步数 (默认 20)

    Returns:
        {
            "persona_id": str,
            "scenario": str,
            "personality": dict[str, float],   # 13 维 flat, 含 gossip_tendency
            "trajectory": list[dict[str, float]],  # 每步快照
        }
    """
    sim = DriftSimulator(persona_id=persona_id)
    topic = _SCENARIO_TOPIC.get(scenario, "neutral")
    trajectory: list[dict[str, float]] = [sim.get_initial_personality()]

    for _ in range(steps):
        if topic == "gossip":
            content = "X 说 Y 的八卦"
        else:
            content = "今天天气不错"
        sim.process_message(topic=topic, content=content)
        sim.run_drift_check()
        trajectory.append(sim.get_current_personality())

    return {
        "persona_id": persona_id,
        "scenario": scenario,
        "personality": sim.get_current_personality(),
        "trajectory": trajectory,
    }
