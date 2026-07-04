# v1.3.0 rc.2: Bug-G ConscienceTracker 轴心重写 Plan(按 handbook §1.7)

> **日期**:2026-07-04
> **前置**:rc.1 = handbook §1.7 轴心驱动规约(已写 UPDATE_HANDBOOK.md,待 commit)。本 rc.2 按 §1.7 重写 ConscienceTracker 治 Bug-G。
> **Bug-G 根因**:tick_pressure 死代码 + _window.append(累加值) + get_pressure 公式 `_raw_pressure / P95`(分子累加无界/分母有界 → 饱和 1.0)→ 每条对话 critical。
> **§1.7 要求**:轴心参数从 13维 personality 映射(不硬编码 SUPEREGO_CONFIG)+ 轴心模块接受 personality(静态)+ 其他轴心状态(动态)。
> **用户设计意图**:事件瞬时大压力(急性)+ 累计压力(慢性)= 当下压力,达阈值引起崩溃,压抑系数(suppression_level)影响积累速度。
> **范围**:ConscienceTracker 双通道重写 + KB 人格映射 + main.py/surface_handler 接线 + test_axis_coupling(§1.7 拦截)+ test_pressure_formula(Bug-G 验证)。commit 本地,**不 push**(v1.3.0 后续 rc + ship 一起)。
> **auto mode**:已开启,任意读写。

---

## 上下文

| Bug | 严重度 | 状态 | rc.2 处理 |
|---|---|---|---|
| Bug-G | P0 | test2 半修(_window 增量 + tick 接线,但 get_pressure 公式没改 → 仍饱和) | ✅ 按 §1.7 轴心重写 |

rc.2 只治 Bug-G。Bug-E/H(framework)+ Bug-F(memory_type)+ Patch A/B/D 合入是后续 rc。

---

## 任务 1:KB 加 conscience_params.json(13维 personality → 轴心参数映射)

**文件**:`emotion_spirit/core/kb/conscience_params.json`(新)

**结构**:13维 personality 每维对轴心参数的影响权重 + 基线默认值。

```json
{
  "_meta": {
    "description": "ConscienceTracker 轴心参数从 13维 personality 映射 (handbook §1.7). v1.3.0 rc.2.",
    "dimensions": ["warmth_bias", "patience", "boundary_permeability", "relational_gravity", "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence", "curiosity", "perception_acuity", "directness", "relational_autonomy", "exploration_openness"]
  },
  "acute_decay_rate_per_min": {
    "baseline": 0.12,
    "weights": {
      "patience": -0.05,
      "inner_coherence": -0.04,
      "boundary_permeability": 0.03
    },
    "range": [0.03, 0.30]
  },
  "chronic_decay_rate_per_hour": {
    "baseline": 0.08,
    "weights": {
      "inner_coherence": -0.04,
      "patience": -0.03,
      "exploration_openness": -0.02
    },
    "range": [0.02, 0.20]
  },
  "collapse_threshold": {
    "baseline": 0.75,
    "weights": {
      "inner_coherence": 0.15,
      "patience": 0.10,
      "boundary_permeability": -0.08
    },
    "range": [0.5, 0.95]
  },
  "acute_multiplier": {
    "baseline": 1.0,
    "weights": {
      "expression_drive": 0.30,
      "gossip_tendency": 0.10
    },
    "range": [0.5, 2.0]
  },
  "chronic_multiplier": {
    "baseline": 0.30,
    "weights": {
      "intimacy_pull": 0.15,
      "warmth_bias": 0.08
    },
    "range": [0.1, 0.8]
  },
  "suppression_efficiency": {
    "baseline": 0.50,
    "weights": {
      "boundary_permeability": -0.20,
      "directness": -0.10,
      "inner_coherence": 0.10
    },
    "range": [0.1, 0.9]
  }
}
```

**映射语义**(weights 正负 = 该维度高时参数增/减):
- `acute_decay_rate_per_min`:急性衰减率(每分钟)。patience/inner_coherence 高 → 衰减快(恢复快,负权重降衰减率?**注意**:weights 是"该维度高时参数的增量",负权重 = 该维度高时参数降。patience 高 → acute_decay 降?不对,patience 高该急性快恢复 = 衰减率升。**小模型核对 weights 正负语义**,baseline + Σ(dim_value × weight),clamp 到 range)。
- `chronic_decay_rate_per_hour`:慢性衰减(每小时)。inner_coherence 高 → 韧性强 → 慢性快衰减。
- `collapse_threshold`:崩溃阈值。inner_coherence/patience 高 → 阈值高(不易崩)。
- `acute_multiplier`:急性倍率(事件瞬时冲击强度)。expression_drive 高 → 急性大。
- `chronic_multiplier`:慢性倍率(事件累积速度)。intimacy_pull 高 → 慢性积累快。
- `suppression_efficiency`:压抑效率(suppression_level 调制慢性积累的强度)。boundary_permeability 高 → 压抑效率低(边界透,压抑不住)。

**注意**:weights 正负 + 数值是初始设想,小模型可调整使测试通过。关键是有映射(不硬编码固定值),具体值可调试。

**验证**:`python -c "import json; d=json.load(open('emotion_spirit/core/kb/conscience_params.json')); print(d['_meta']['dimensions'])"`

---

## 任务 2:compute_conscience_params_from_personality 函数

**文件**:`emotion_spirit/utils/persona_profiles.py`(加函数,跟 `get_personality_params` 同文件)

```python
def compute_conscience_params_from_personality(personality: dict[str, float]) -> dict[str, float]:
    """从 13维 personality 算 ConscienceTracker 轴心参数 (handbook §1.7).

    读 KB conscience_params.json, 每参数 = baseline + Σ(dim_value × weight), clamp 到 range.
    缺维度用 0.5 中性兜底.
    """
    from emotion_spirit.core.persona_labels_db import get_conscience_params_kb
    kb = get_conscience_params_kb()
    params = {}
    for param_name, spec in kb.items():
        if param_name == "_meta":
            continue
        baseline = spec["baseline"]
        weights = spec["weights"]
        lo, hi = spec["range"]
        val = baseline
        for dim, w in weights.items():
            val += personality.get(dim, 0.5) * w
        params[param_name] = max(lo, min(hi, val))
    return params
```

**配套**:`emotion_spirit/core/persona_labels_db.py` 加 `get_conscience_params_kb()`(像 `get_persona_labels_db()` 加载 + 缓存 conscience_params.json)。

**注意**:persona_labels_db.py 现有 `get_persona_labels_db()` 加载 persona_labels_db.json。加 `get_conscience_params_kb()` 加载 conscience_params.json(同模式:DB_PATH 旁加路径 + 缓存)。

---

## 任务 3:ConscienceTracker 双通道重写

**文件**:`emotion_spirit/regulation/superego/conscience.py`

### 改动 3.1:__init__ 双通道 + 人格参数默认值

```python
class ConscienceTracker:
    """良心追踪 — 价值冲突增压 + 价值对齐减压 (v1.3.0 rc.2: 双通道 + 人格耦合).

    v1.3.0 §1.7 轴心驱动: 衰减率/阈值/倍率从 13维 personality 算 (set_personality),
    不硬编码 SUPEREGO_CONFIG. 双通道: _acute (瞬时, 快衰减) + _chronic (累计, 慢衰减).
    suppression_level 动态调制慢性积累速度.
    """

    def __init__(self) -> None:
        self.guilt_events: list[GuiltEvent] = []
        self.alignment_events: list[AlignmentEvent] = []
        self._last_collapse_count: int = 0
        # Bug-G v1.3.0: 双通道 (急性瞬时 + 慢性累计)
        self._acute_pressure: float = 0.0
        self._chronic_pressure: float = 0.0
        self._last_tick_time: float = time.time()  # lazy decay 用
        # 人格参数 (set_personality 覆盖; 默认值 = SUPEREGO_CONFIG 旧值, 向后兼容)
        self._acute_decay_rate_per_min: float = 0.12
        self._chronic_decay_rate_per_hour: float = SUPEREGO_CONFIG["pressure_decay_rate_per_hour"]
        self._collapse_threshold: float = 0.75
        self._acute_multiplier: float = 1.0
        self._chronic_multiplier: float = 0.30
        self._suppression_efficiency: float = 0.50
        # _window 保留诊断 (get_pressure_breakdown 用, 不用于归一化)
        self._window: deque[float] = deque(maxlen=_get_window_size())
```

**注意**:`import time` 加到 conscience.py 顶部(若未有)。

### 改动 3.2:set_personality(personality)

```python
    def set_personality(self, personality: dict[str, float]) -> None:
        """§1.7 轴心耦合: 从 13维 personality 算轴心参数 (调 compute_conscience_params_from_personality)."""
        from emotion_spirit.utils.persona_profiles import compute_conscience_params_from_personality
        params = compute_conscience_params_from_personality(personality)
        self._acute_decay_rate_per_min = params["acute_decay_rate_per_min"]
        self._chronic_decay_rate_per_hour = params["chronic_decay_rate_per_hour"]
        self._collapse_threshold = params["collapse_threshold"]
        self._acute_multiplier = params["acute_multiplier"]
        self._chronic_multiplier = params["chronic_multiplier"]
        self._suppression_efficiency = params["suppression_efficiency"]
```

### 改动 3.3:record_value_conflict 双通道 + suppression 调制

```python
    def record_value_conflict(
        self, value_name: str, action: str, conscience_impact: float, reason: str,
        suppression_level: float = 0.0,  # Bug-G v1.3.0: 动态调制慢性积累
    ) -> GuiltEvent:
        """价值冲突 → 良心增压 (急性 + 慢性双通道).

        急性: += impact * acute_multiplier (大, 快衰减)
        慢性: += impact * chronic_multiplier * (1 - suppression_level * suppression_efficiency)
               (压抑起作用时积累慢)
        """
        impact = abs(conscience_impact)
        acute_gain = impact * self._acute_multiplier
        chronic_gain = impact * self._chronic_multiplier * (1 - suppression_level * self._suppression_efficiency)
        self._acute_pressure += acute_gain
        self._chronic_pressure += max(0.0, chronic_gain)
        self._window.append(impact)  # 诊断: 单次增量
        # ... 原 GuiltEvent 构造 + return 保留 ...
```

**其他 record_* 方法**(`record_guard_reflex` / `record_cascade` / `record_collapse`):同样改双通道 + `suppression_level` 参数(默认 0.0)。急性 += severity * acute_multiplier,慢性 += severity * chronic_multiplier * (1 - supp * eff)。

**record_alignment / record_repair**(减压):减双通道(优先减急性,再减慢性)。加 `suppression_level` 参数(默认 0.0,但减压不受 suppression 调制)。例如:
```python
    def record_repair(self, repair_type: str = "simple", suppression_level: float = 0.0) -> None:
        relief = SUPEREGO_CONFIG["repair_relief"].get(repair_type, SUPEREGO_CONFIG["repair_relief"]["simple"])
        # 减压: 优先减急性 (即时缓解), 再减慢性
        acute_relief = relief * 0.7
        chronic_relief = relief * 0.3
        self._acute_pressure = max(0.0, self._acute_pressure - acute_relief)
        self._chronic_pressure = max(0.0, self._chronic_pressure - chronic_relief)
```

**注意**:`record_guard_rejected`(line 181-183 向后兼容转发 record_guard_reflex)保留。

### 改动 3.4:get_pressure 双通道 + lazy decay

```python
    def get_pressure(self) -> float:
        """良心压力 [0, 1] = 急性 + 慢性 (lazy decay 按时间差衰减, 不饱和)."""
        self._apply_lazy_decay()
        return min(1.0, self._acute_pressure + self._chronic_pressure)

    def _apply_lazy_decay(self) -> None:
        """按时间差衰减双通道 (get_pressure 时调, 避免不调时不衰)."""
        now = time.time()
        hours = (now - self._last_tick_time) / 3600.0
        if hours <= 0:
            return
        mins = hours * 60
        self._acute_pressure *= (1.0 - self._acute_decay_rate_per_min) ** mins
        self._chronic_pressure *= (1.0 - self._chronic_decay_rate_per_hour) ** hours
        self._last_tick_time = now
```

**注意**:`get_pressure` 返回 `float`(ForceDynamics 契约,不是 ConsciencePressure 包装类 — 确认现有契约,若 §1.4 要求包装类则保留 `.as_float()`)。旧 `get_pressure` 的 P95 归一化逻辑(_window_quantile)**删除**(双通道不依赖 P95)。`_window` 保留供 `get_pressure_breakdown` 诊断。

### 改动 3.5:tick_pressure 双通道(保留 _decay_tick_loop 接线)

```python
    def tick_pressure(self, hours_elapsed: float) -> None:
        """自然衰减 (hourly, _decay_tick_loop 调). 双通道."""
        mins = hours_elapsed * 60
        self._acute_pressure *= (1.0 - self._acute_decay_rate_per_min) ** mins
        self._chronic_pressure *= (1.0 - self._chronic_decay_rate_per_hour) ** hours_elapsed
        # _last_tick_time 同步 (避免 lazy decay 重复衰)
        self._last_tick_time = time.time()
```

**注意**:`_decay_tick_loop`(main.py,test2 已接)继续调 `tick_pressure(hours)`。lazy decay + tick 双保险(tick 定期强制衰,lazy 在 get_pressure 时按时间差衰)。但避免双重衰减:tick 后更新 _last_tick_time(上面已做)。

### 改动 3.6:get_pressure_breakdown 更新(诊断)

```python
    def get_pressure_breakdown(self) -> dict:
        self._apply_lazy_decay()
        return {
            "acute_pressure": self._acute_pressure,
            "chronic_pressure": self._chronic_pressure,
            "total": min(1.0, self._acute_pressure + self._chronic_pressure),
            "collapse_threshold": self._collapse_threshold,
            "acute_decay_rate_per_min": self._acute_decay_rate_per_min,
            "chronic_decay_rate_per_hour": self._chronic_decay_rate_per_hour,
            "raw_window_recent": list(self._window)[-10:],  # 诊断最近 10 事件
        }
```

### 改动 3.7:to_dict / from_dict / reset(§1.5 生命周期)

ConscienceTracker 是 @register 有状态模块,必须有 to_dict/from_dict/reset。双通道后更新:

```python
    def to_dict(self) -> dict:
        self._apply_lazy_decay()
        return {
            "acute_pressure": self._acute_pressure,
            "chronic_pressure": self._chronic_pressure,
            "guilt_events": self.guilt_events,  # 若 GuiltEvent 可序列化
            "alignment_events": self.alignment_events,
        }

    def from_dict(self, data: dict) -> None:
        self._acute_pressure = data.get("acute_pressure", 0.0)
        self._chronic_pressure = data.get("chronic_pressure", 0.0)
        self.guilt_events = data.get("guilt_events", [])
        self.alignment_events = data.get("alignment_events", [])
        self._last_tick_time = time.time()

    def reset(self) -> None:
        self._acute_pressure = 0.0
        self._chronic_pressure = 0.0
        self.guilt_events = []
        self.alignment_events = []
        self._last_tick_time = time.time()
```

**注意**:确认现有 to_dict/from_dict/reset 是否存在(test_lifecycle_pairs 守护)。若不存在则新增,若存在则更新字段。`guilt_events` / `alignment_events` 若含不可序列化对象(GuiltEvent dataclass),用 `[asdict(e) for e in ...]` + 反序列化。

---

## 任务 4:main.py + surface_handler 接线

### 改动 4.1:main.py set_personality 接线

**文件**:`main.py`

`_baseline_personality` 在 line 484 算(`get_personality_params(self._labels)`)。conscience 在 line 302 取。set_personality 必须在 484 后调。

在 `_setup_persona_state` 或 `_load_persona_state`(labels 算完后)加:

```python
# rc.2 §1.7: ConscienceTracker 轴心耦合 — 从 13维 personality 算衰减率/阈值/倍率
if hasattr(self, "_conscience") and self._conscience is not None:
    deep_personality = self._baseline_personality.get("deep", {})
    if deep_personality:
        self._conscience.set_personality(deep_personality)
```

**注意**:确认 `self._baseline_personality` 的层级名("deep" 跟 main.py:429 `sup_mod.compute(personality=self._baseline_personality.get("deep", {}))` 一致)。放在 `_setup_persona_state` 末尾或 `_load_persona_state` 的 labels 恢复后。**relabel 时也要重调 set_personality**(labels 变 → personality 变 → 参数变),在 `_reset_superego_modules` 或 relabel 流程后加同样的 set_personality 调用。

### 改动 4.2:surface_handler record_* 传 suppression_level

**文件**:`emotion_spirit/output/surface_handler.py`(line 114-133)

surface_handler 调 record_* 时传当前 suppression_level。suppression_level 从哪拿?

**选项 A**(推荐):surface_handler.consume 时 main.py 已算 suppression_level(在 signals 或 defense_states 里)。surface_handler 从 signals 或 self._p._latest_defense_states 拿。

**选项 B**:surface_handler 自己调 `self._p._defense_modulator.compute_defense_states(...)` 算 suppression_level(重复计算,慢)。

**推荐 A**:确认 signals 或 consume 上下文是否携带 suppression_level。若没有,在 main.py consume 入口算一次传给 surface_handler。

```python
# surface_handler.py record_* 调用改:
self._p._conscience.record_value_conflict(
    value_name=..., action=..., conscience_impact=..., reason=...,
    suppression_level=signals.suppression_level if hasattr(signals, "suppression_level") else 0.0,
)
```

**注意**:`signals` 是否有 `suppression_level` 属性需确认。若没有,在 main.py 算 defense_states 时把 `suppression_level` 塞进 signals 或单独传。**小模型确认 signals 结构 + 接线方式**。若接线复杂,选项 C:record_* 的 suppression_level 默认 0.0(不传),先让双通道 + 人格耦合工作(治 Bug-G 饱和),suppression 调制作为后续 rc 增强(标 TODO)。

---

## 任务 5:test_axis_coupling.py(§1.7 拦截)

**新建**:`tests/test_axis_coupling.py`

```python
"""§1.7 轴心驱动守护: 轴心模块必须接受 personality (静态参数).

v1.3.0 rc.2: 本轮只验证 ConscienceTracker (已改). 其他轴心模块 (DefenseModulator/
Suppression/Collapse/IntimacyTracker/DecayModel/ReflexLearner) 标 TODO 后续 rc 耦合.

白名单: ForceDynamics (已耦合 compute(personality, ...)) + ConscienceTracker (rc.2 改).
TODO: 其余轴心模块 v1.3.0 后续 rc 接 personality.
"""
from __future__ import annotations

import inspect

from emotion_spirit.regulation.superego.conscience import ConscienceTracker
from emotion_spirit.regulation.force_dynamics import ForceDynamics


def test_conscience_tracker_has_set_personality():
    """ConscienceTracker 必须有 set_personality(personality) 接口 (§1.7 规则 4)."""
    assert hasattr(ConscienceTracker, "set_personality"), (
        "ConscienceTracker 必须有 set_personality 接受 13维 personality (§1.7 轴心耦合)"
    )
    sig = inspect.signature(ConscienceTracker.set_personality)
    assert "personality" in sig.parameters, "set_personality 必须接受 personality 参数"


def test_conscience_tracker_no_hardcoded_pressure_params():
    """ConscienceTracker 不应硬编码轴心参数 (衰减率/阈值/倍率) 为固定值 — 必须从 personality 算."""
    import inspect as _inspect
    source = _inspect.getsource(ConscienceTracker)
    # 守护: __init__ 里轴心参数应有默认值 (向后兼容) 但 set_personality 必须覆盖
    # 关键: 不该有 get_pressure 用 _raw_pressure / P95 (旧饱和公式)
    assert "_raw_pressure / self._window_quantile" not in source, (
        "get_pressure 不应用 _raw_pressure/P95 公式 (Bug-G 饱和根因), 改双通道 acute+chronic"
    )
    assert "set_personality" in source, "必须有 set_personality 从 personality 算参数"


def test_force_dynamics_accepts_personality():
    """ForceDynamics.compute 必须接受 personality (已耦合, 防退步)."""
    sig = inspect.signature(ForceDynamics.compute)
    assert "personality" in sig.parameters, "ForceDynamics.compute 必须接受 personality (§1.7 耦合典范)"


# TODO (v1.3.0 后续 rc): DefenseModulator / Suppression / CollapseArchetypeSelector /
# IntimacyTracker / DecayModel / ReflexLearner 接 personality. 加测试守护.
```

---

## 任务 6:test_pressure_formula.py(Bug-G 验证)

**新建**:`tests/test_pressure_formula.py`

```python
"""Bug-G (v1.3.0 rc.2): ConscienceTracker 双通道 + 人格耦合 验证.

旧 bug: get_pressure = _raw_pressure / P95 饱和 1.0 → 每条对话 critical.
rc.2 修法: 双通道 (acute + chronic) + lazy decay + 人格参数 + suppression 调制.

用户反馈: 2026-07-04-emotion-spirit-feedback-merged.md §3.
"""
from __future__ import annotations

import pytest
import time as _time

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


@pytest.fixture
def tracker() -> ConscienceTracker:
    return ConscienceTracker()


def test_get_pressure_not_saturated_after_many_events(tracker: ConscienceTracker):
    """灌 100 次小冲突 + 衰减后, get_pressure 不应永等于 1.0 (Bug-G 核心)."""
    for i in range(100):
        tracker.record_value_conflict(
            value_name=f"v{i}", action="a", conscience_impact=0.2, reason="test",
        )
    # 灌完后急性可能高, 但慢性有界 (衰减 + suppression 调制默认 0)
    p = tracker.get_pressure()
    # 急性 100*0.2*1.0=20 → min(1.0)=1.0 (急性瞬时高). 但急性快衰减.
    # 关键: 衰减后应 < 1.0
    tracker._acute_pressure *= 0.01  # 模拟急性衰减后
    p_after = tracker.get_pressure()
    assert p_after < 1.0, f"衰减后 get_pressure 应 < 1.0, 实际 {p_after} (Bug-G 未修?)"


def test_acute_decays_fast(tracker: ConscienceTracker):
    """急性压力快衰减 (分钟级)."""
    tracker.record_value_conflict("v", "a", 0.8, "test")
    acute_before = tracker._acute_pressure
    tracker._apply_lazy_decay()
    # 立即调 decay (hours≈0) 几乎不衰, 手动 tick
    tracker.tick_pressure(0.1)  # 6 分钟
    assert tracker._acute_pressure < acute_before, "急性应快衰减"


def test_chronic_decays_slow(tracker: ConscienceTracker):
    """慢性压力慢衰减 (小时级), 比急性慢."""
    tracker.record_value_conflict("v", "a", 0.8, "test")
    chronic_before = tracker._chronic_pressure
    tracker.tick_pressure(1.0)  # 1 小时
    assert tracker._chronic_pressure < chronic_before, "慢性应衰减"
    # 慢性衰减率 < 急性 (per_min vs per_hour)
    assert tracker._chronic_decay_rate_per_hour < tracker._acute_decay_rate_per_min * 60


def test_suppression_level_reduces_chronic_accumulation(tracker: ConscienceTracker):
    """suppression_level 高 → 慢性积累慢 (压抑缓冲)."""
    tracker_low = ConscienceTracker()
    tracker_high = ConscienceTracker()
    tracker_low.record_value_conflict("v", "a", 0.5, "test", suppression_level=0.0)
    tracker_high.record_value_conflict("v", "a", 0.5, "test", suppression_level=1.0)
    assert tracker_high._chronic_pressure < tracker_low._chronic_pressure, (
        "suppression_level=1.0 时慢性积累应 < suppression=0.0"
    )


def test_set_personality_changes_params(tracker: ConscienceTracker):
    """set_personality 从 13维 personality 算参数 (不硬编码)."""
    # 高 inner_coherence + patience 人格 → 崩溃阈值高
    resilient = {dim: 0.5 for dim in [
        "warmth_bias", "patience", "boundary_permeability", "relational_gravity",
        "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence",
        "curiosity", "perception_acuity", "directness", "relational_autonomy",
        "exploration_openness",
    ]}
    resilient["inner_coherence"] = 0.9
    resilient["patience"] = 0.9
    tracker.set_personality(resilient)
    assert tracker._collapse_threshold > 0.75, "高 inner_coherence+patience → 崩溃阈值应高于基线"


def test_get_pressure_in_range(tracker: ConscienceTracker):
    """get_pressure ∈ [0, 1]."""
    tracker.record_value_conflict("v", "a", 5.0, "test")  # 大冲击
    p = tracker.get_pressure()
    assert 0.0 <= p <= 1.0, f"get_pressure 应 ∈ [0,1], 实际 {p}"
```

**注意**:测试里的 `0.75` 基线阈值要跟 KB conscience_params.json 的 `collapse_threshold.baseline` 一致。小模型确认。

---

## 任务 7:跑全套测试

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
python -m pytest tests/ -q --tb=short
```

**期望**:
- 新增 test_axis_coupling 3 + test_pressure_formula 6 = 9 新测试全过
- 既有测试全过(test2 baseline 1388 ± test_bug_e_result_chain 调整)
- `test_periodic_save_dirty_only` Win flake 仍偶发(v1.2.6 backlog,非回归)

**如有红**:
- `test_get_pressure_not_saturated_after_many_events` 失败 → 急性衰减不够快,调 KB `acute_decay_rate_per_min` baseline 升高
- `test_set_personality_changes_params` 失败 → weights 正负或数值不对,调 KB conscience_params.json
- `test_lifecycle_pairs` 失败 → to_dict/from_dict/reset 不一致,确认三件套
- `test_main_py_no_long_orchestration` 失败 → set_personality 接线写太长,抽 helper

---

## 任务 8:commit(本地,不 push)

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git status
git add -A
git commit -m "v1.3.0 rc.1+rc.2: handbook §1.7 轴心驱动 + Bug-G ConscienceTracker 双通道重写 (NOT pushed)

rc.1: UPDATE_HANDBOOK.md §1.7 轴心功能驱动规约 (4 轴 人格/力学/memory/超我 + 参数分层
  反事实测试 + 13维 personality 映射 + test_axis_coupling 拦截).
rc.2: Bug-G 治本 — ConscienceTracker 双通道重写 (急性瞬时 + 慢性累计) + set_personality
  从 13维 personality 算衰减率/阈值/倍率 (KB conscience_params.json) + suppression_level
  动态调制慢性积累 + get_pressure=acute+chronic (去 _raw_pressure/P95 饱和) + lazy decay.
  修每条对话 critical (tick_pressure 死代码 + 公式饱和).

测试版, 不 push, 不 bump. v1.3.0 后续 rc (Bug-E/H framework + Bug-F memory_type + Patch A/B/D)
完成后一起 bump v1.3.0 + ship.

用户反馈: 2026-07-04-emotion-spirit-feedback-merged.md §3 (Bug-G)."
```

**⚠️ 不要 `git push`**。本地 commit。

---

## 任务 9:报告

**新建**:`docs/v1.3.0-rc2-build-report.md`

```markdown
# v1.3.0 rc.2 构建报告(2026-07-04, 不 push)

## 范围
rc.1 (handbook §1.7) + rc.2 (Bug-G ConscienceTracker 轴心重写). **不 push, 不 bump**.
v1.3.0 后续 rc (Bug-E/H + Bug-F + Patch A/B/D) 完成后一起 ship.

HEAD: `git rev-parse HEAD` 填入

## 改动清单

### rc.1: handbook §1.7 轴心驱动规约
- UPDATE_HANDBOOK.md: §1.7 (4 轴 + 参数分层 + 13维映射 + test_axis_coupling)
- 顶部版本更新 v1.2.9 → v1.2.10 + v1.3.0 进行中

### rc.2: Bug-G ConscienceTracker 双通道重写
- KB: emotion_spirit/core/kb/conscience_params.json (13维 personality → 6 参数映射)
- persona_profiles.py: compute_conscience_params_from_personality
- persona_labels_db.py: get_conscience_params_kb loader
- conscience.py: __init__ 双通道 (_acute + _chronic) + set_personality + record_* suppression 调制 + get_pressure=acute+chronic + lazy decay + tick_pressure 双通道 + to_dict/from_dict/reset
- main.py: set_personality 接线 (labels 算完后)
- surface_handler.py: record_* 传 suppression_level (若接线可行; 否则 TODO 默认 0.0)
- 守护: test_axis_coupling.py (§1.7) + test_pressure_formula.py (Bug-G)

## 测试
- pytest tests/ 全套: <填入> passed
- 新增: test_axis_coupling 3 + test_pressure_formula 6 = 9
- 已知: test_periodic_save_dirty_only Win flake (v1.2.6 backlog)

## 不做清单
- ❌ git push / bump / CHANGELOG (v1.3.0 后续 rc 一起)
- ❌ Bug-E/H (framework, 后续 rc) / Bug-F (memory_type, 后续 rc) / Patch A/B/D 合入 (后续 rc)
- ❌ surface_handler suppression_level 接线若复杂 → 标 TODO (默认 0.0, 双通道仍工作)

## 实测后后续
1. 用户丢 zip 实测: docker logs grep "level=critical" 应大幅减少 (Bug-G 修)
2. get_pressure_breakdown 看双通道值 (诊断)
3. 后续 rc: Bug-E/H + Bug-F + Patch A/B/D
4. 全绿后 bump v1.3.0 + ship
```

填入实际数字 + HEAD 后保存。

---

## 不做清单(明确)

- ❌ `git push` / bump / CHANGELOG(v1.3.0 后续 rc 一起)
- ❌ Bug-E/H(framework,后续 rc)+ Bug-F(memory_type,后续 rc)+ Patch A/B/D 合入(后续 rc)
- ❌ 其他轴心模块人格化(DefenseModulator/Suppression/IntimacyTracker 等)— 标 TODO,后续 rc
- ❌ surface_handler suppression_level 接线若复杂 → 标 TODO(默认 0.0,双通道 + 人格耦合仍治 Bug-G 饱和)

---

## 关键源码参考

- handbook §1.7:`UPDATE_HANDBOOK.md`(rc.1 已写)
- 13维 personality:`emotion_spirit/regulation/force_dynamics.py:4-7`(warmth_bias/patience/boundary_permeability + relational_gravity/intimacy_pull/expression_drive/gossip_tendency + inner_coherence/curiosity/perception_acuity/directness/relational_autonomy/exploration_openness)
- ConscienceTracker:`emotion_spirit/regulation/superego/conscience.py`(__init__:64, record_*:77-183, get_pressure:187, tick_pressure:208)
- SUPEREGO_CONFIG:`emotion_spirit/core/config.py:175+`(轴心参数:pressure_decay_rate/guard_reflex_mult/cascade_mult/alignment_relief/conscience_impact_coef/repair_relief)
- main.py 接线:`self._conscience = self._modules["superego"]["conscience"]`(302)+ `self._baseline_personality = get_personality_params(self._labels)`(484)+ suppression_level 计算(417-431)
- surface_handler record_* 调用:`emotion_spirit/output/surface_handler.py:114-133`
- KB 映射参考:`emotion_spirit/core/persona_labels_db.py` `get_persona_labels_db()` + `emotion_spirit/utils/persona_profiles.py:120 get_personality_params`
- 用户反馈:`C:\Users\Aston\Downloads\2026-07-04-emotion-spirit-feedback-merged.md` §3(Bug-G)
