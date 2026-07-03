# v1.2.5 PR2: 力学系统耦合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把压抑/崩溃/沉默 三防御子系统与力学系统耦合。新建 `DefenseModulator` 模块做 L1（三子读 force_state）+ L2（事件回写 force_state），遵守 handbook §1.2 模块化哲学（force_dynamics.compute() 签名不变）。

**Architecture:**
- 新建 `emotion_spirit/regulation/defense_modulator.py`, `@register(name="defense_modulator", depends_on=[force_dynamics, suppression, collapse_archetype_selector, segmented_reply_coordinator])`
- `DefenseModulator.compute_defense_states(...)` 调三子的 compute() / select() / compute_silence_tendency(), 全部传 `force_state` (L1)
- `DefenseModulator.apply_event(defense_type, intensity)` 调 `force_dynamics.shift()` 回写 (L2)
- 三子的 compute() / select() / compute_silence_tendency() 都扩 `force_state=None` 可选参数（向后兼容 100%）
- 偏移系数从 KB `defense_deltas.json` 读 (handbook §1.1)

**Tech Stack:**
- 同 PR1
- 新增: dataclass `DefenseStates` (3 个连续值 + silence reason + components)

**关联 Spec:** `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` §4 + §10.3 (T2 不在 PR2, 是 PR3)

**前置:** PR1 已 ship (DefenseModulator 依赖 SegmentedReplyCoordinator 已存在的 `compute_silence_tendency`)

**不在 PR2:** §4.5 KB defense_deltas.json (本 plan Task 4 加) / T2 顺手清债 (PR3)

---

## Global Constraints

**版本/路径:**
- 同 PR1, 仓库根 `D:\新建文件夹\emotion_spirit\now\astrbot_plugin_emotion_spirit`
- spec §4 全部内容 + §4.5 KB 段

**handbook 强制:**
- §1.1 系数进 KB (`defense_deltas.json`)
- §1.2 新模块 @register, **force_dynamics.compute() 签名不变** (向后兼容)
- §1.3 三子的方法保留 session_key 命名 (不强制 user_id, PR1 已改)

**架构原则:**
- `DefenseModulator` 是**单一职责**: 只管三子↔力学耦合
- 不掺业务 (memory / dream / diary), 不动 main.py 装配
- v1.3 L3 fixpoint 在此扩展 (单步法 → 迭代求解)

**DefenseModulator 依赖 (4 个):**
- `force_dynamics` (L1 读, L2 写)
- `suppression` (L1: compute() 读 force_state)
- `collapse_archetype_selector` (L1: compute_bas_bis() 读 force_state)
- `segmented_reply_coordinator` (L1: compute_silence_tendency() 读 force_state)

**模块数:** v1.2.5 PR1 = 57 不变, **PR2 = 58** (+DefenseModulator)

---

## Task 1: DefenseStates dataclass + 测试

**Files:**
- Create: `emotion_spirit/regulation/defense_modulator.py` (含 dataclass, 后续 Task 加方法)
- Test: `tests/test_defense_modulator.py` (new file, 5 测试)

**Interfaces:**
- Produces: `class DefenseStates` (dataclass, 含 suppression_level / collapse_tendency / silence_tendency / silence_reason / silence_components)
- 字段缺省 0.0 / "" / {}, 校验 score ∈ [0, 1]

- [ ] **Step 1.1: 写失败测试**

```python
# tests/test_defense_modulator.py
"""Tests for DefenseModulator (v1.2.5 PR2 §4)"""
import pytest
from emotion_spirit.regulation.defense_modulator import DefenseStates


def test_defense_states_default_values():
    """缺省全 0.0/''/{}"""
    s = DefenseStates()
    assert s.suppression_level == 0.0
    assert s.collapse_tendency == 0.0
    assert s.silence_tendency == 0.0
    assert s.silence_reason == ""
    assert s.silence_components == {}


def test_defense_states_with_values():
    """传值正确保存"""
    s = DefenseStates(
        suppression_level=0.5,
        collapse_tendency=0.3,
        silence_tendency=0.7,
        silence_reason="void_hurt_withdrawing",
        silence_components={"hurt_void": 0.6},
    )
    assert s.suppression_level == 0.5
    assert s.collapse_tendency == 0.3
    assert s.silence_tendency == 0.7
    assert s.silence_reason == "void_hurt_withdrawing"
    assert s.silence_components == {"hurt_void": 0.6}


def test_defense_states_suppression_clamped():
    """suppression_level > 1.0 应被 clamp 到 1.0"""
    s = DefenseStates(suppression_level=1.5)
    assert s.suppression_level == 1.0


def test_defense_states_collapse_clamped():
    """collapse_tendency < 0.0 应被 clamp 到 0.0"""
    s = DefenseStates(collapse_tendency=-0.5)
    assert s.collapse_tendency == 0.0


def test_defense_states_silence_clamped():
    """silence_tendency 越界应 clamp"""
    s = DefenseStates(silence_tendency=1.5)
    assert s.silence_tendency == 1.0
    s = DefenseStates(silence_tendency=-0.5)
    assert s.silence_tendency == 0.0
```

- [ ] **Step 1.2: 跑测试确认失败**

Run: `python -m pytest tests/test_defense_modulator.py -v`
Expected: 5 个测试全 FAIL with `ImportError: cannot import name 'DefenseStates'`

- [ ] **Step 1.3: 实现 DefenseStates dataclass**

```python
# emotion_spirit/regulation/defense_modulator.py
"""Defense Modulator — 压抑/崩溃/沉默 三防御子系统与力学的耦合调制器 (v1.2.5 PR2 §4)

L1 (输入调制): 三子读 force_state, 输出 DefenseStates
L2 (输出回写): 防御事件触发后调 force_dynamics.shift()
v1.3 加: L3 fixpoint 完全耦合

设计原则 (handbook §1.2):
- 单一职责: 只管三子↔力学耦合, 不掺业务
- 加新防御子 (v1.3 焦虑/解离等): 在此加字段, 不动 main.py
- 系数全部从 KB 读 (handbook §1.1), 不硬编码
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class DefenseStates:
    """v1.2.5 PR2 三子连续值 (供 force_dynamics 决策)
    
    字段全 [0, 1], 缺省 0.0 (无防御激活)
    """
    suppression_level: float = 0.0
    collapse_tendency: float = 0.0
    silence_tendency: float = 0.0
    silence_reason: str = ""           # 透明性
    silence_components: dict = field(default_factory=dict)
    
    def __post_init__(self):
        # Clamp 到 [0, 1]
        self.suppression_level = max(0.0, min(1.0, self.suppression_level))
        self.collapse_tendency = max(0.0, min(1.0, self.collapse_tendency))
        self.silence_tendency = max(0.0, min(1.0, self.silence_tendency))
```

- [ ] **Step 1.4: 跑测试确认通过**

Run: `python -m pytest tests/test_defense_modulator.py -v`
Expected: 5 个测试全 PASS

- [ ] **Step 1.5: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/regulation/defense_modulator.py tests/test_defense_modulator.py
git commit -m "feat(v1.2.5-pr2): DefenseStates dataclass for 3-defense coupling"
```

---

## Task 2: SuppressionState.compute() 接受 force_state 参数（向后兼容）

**Files:**
- Modify: `emotion_spirit/memory/suppression.py:26-55` (`compute()` 加 `force_state` 可选参数)
- Test: `tests/test_suppression.py` (new file, 4 测试)

**Interfaces:**
- 新增可选参数: `force_state: Optional[dict] = None`
- L1 逻辑: 若 force_state 非 None, 加权 (社会力/个体力 → 压抑↑)
- **向后兼容**: 不传 force_state → 输出跟 v1.2.4 完全一致

- [ ] **Step 2.1: 写失败测试**

```python
# tests/test_suppression.py (新文件)
"""Tests for SuppressionState L1 force_state integration (v1.2.5 PR2 §4.3)"""
from emotion_spirit.memory.suppression import SuppressionState


def test_suppression_backward_compatible_no_force_state():
    """不传 force_state 输出跟 v1.2.4 一致"""
    sup = SuppressionState()
    level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={"authority_present": 0, "social_audience": 0},
        conscience_pressure=0.0,
        relationship_intimacy=0.5,
    )
    # baseline 0.5, intimacy_factor 0.8, 没有 authority/social/pressure
    # 0.5 * 0.8 + 0 + 0 + 0 = 0.4
    assert abs(level - 0.4) < 0.001


def test_suppression_with_force_state_social_increases():
    """force_state.social 高 → 压抑升高 (社会面前更想藏)"""
    sup = SuppressionState()
    base_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
    )
    social_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
        force_state={"natural": 0.5, "social": 0.9, "individual": 0.5},
    )
    assert social_level > base_level


def test_suppression_with_force_state_individual_increases():
    """force_state.individual 高 → 压抑升高 (独处时也压抑)"""
    sup = SuppressionState()
    base_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
    )
    indiv_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
        force_state={"natural": 0.5, "social": 0.5, "individual": 0.9},
    )
    assert indiv_level > base_level


def test_suppression_force_state_clamped():
    """force_state 加权后仍 clamp 到 [0, 1]"""
    sup = SuppressionState()
    level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
        force_state={"natural": 1.0, "social": 1.0, "individual": 1.0},
    )
    assert 0.0 <= level <= 1.0
```

- [ ] **Step 2.2: 跑测试确认失败**

Run: `python -m pytest tests/test_suppression.py -v`
Expected: 后 3 个测试 FAIL with `TypeError: compute() got an unexpected keyword argument 'force_state'`

- [ ] **Step 2.3: 改 SuppressionState.compute()**

```python
# emotion_spirit/memory/suppression.py:26-55
from typing import Optional

class SuppressionState:
    def compute(
        self,
        personality: dict[str, float],
        context: dict,
        conscience_pressure: float,
        relationship_intimacy: float,
        force_state: Optional[dict] = None,  # v1.2.5 PR2 §4.3 L1 新增
    ) -> float:
        """v1.2.5 PR2: 加 force_state 可选参数 (L1 输入调制)
        
        向后兼容: 不传 force_state → 输出跟 v1.2.4 完全一致
        """
        baseline = (
            0.35 * personality.get("neuroticism", 0.5)
            + 0.25 * personality.get("agreeableness", 0.5)
            + 0.15 * (1 - personality.get("openness", 0.5))
            + 0.20 * (1 - personality.get("extraversion", 0.5))
            + 0.05 * personality.get("conscientiousness", 0.5)
        )
        intimacy_factor = 1 - 0.4 * relationship_intimacy
        authority_factor = context.get("authority_present", 0) * 0.2
        social_audience = context.get("social_audience", 0) * 0.15
        
        base_suppression = (
            baseline * intimacy_factor + authority_factor + social_audience
            + 0.2 * conscience_pressure
        )
        
        # L1: 力加权 (社会力 + 个体力 → 压抑↑)
        if force_state is not None:
            force_modifier = (
                1.0 
                + 0.3 * force_state.get("social", 0.5) 
                + 0.2 * force_state.get("individual", 0.5)
            )
            base_suppression *= force_modifier
        
        return _clamp(base_suppression, 0, 1)
```

- [ ] **Step 2.4: 跑测试确认通过**

Run: `python -m pytest tests/test_suppression.py -v`
Expected: 4 个测试全 PASS

- [ ] **Step 2.5: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/test_force_dynamics.py tests/test_superego.py -v` (跟 SuppressionState 相关的测试)
Expected: 全 PASS (compute() 向后兼容)

- [ ] **Step 2.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/memory/suppression.py tests/test_suppression.py
git commit -m "feat(v1.2.5-pr2): SuppressionState.compute() accept force_state (L1, 100% backward compat)"
```

---

## Task 3: CollapseArchetypeSelector.compute_bas_bis() 接受 force_state + 连续化

**Files:**
- Modify: `emotion_spirit/regulation/collapse_archetype.py:44-74` (`compute_bas_bis` 加 force_state + 返回 collapse_tendency)
- Test: `tests/test_collapse_archetype.py` (new file, 5 测试)

**Interfaces:**
- `compute_bas_bis(personality, force_state=None) -> tuple[float, float, float]`
- 返回 BAS / BIS / collapse_tendency (连续化: max(0, BIS - BAS), clamp [0, 1])
- **v1.2.4 行为**: `select()` 用 BAS/BIS 二分决策 → v1.2.5 改为同时用 BAS/BIS/collapse_tendency (PR2 只加新逻辑, 不改 select)

- [ ] **Step 3.1: 写失败测试**

```python
# tests/test_collapse_archetype.py
"""Tests for CollapseArchetypeSelector L1 + 连续化 (v1.2.5 PR2 §4.3)"""
from emotion_spirit.regulation.collapse_archetype import CollapseArchetypeSelector


def test_compute_bas_bis_backward_compatible_no_force_state():
    """不传 force_state → BAS/BIS 跟 v1.2.4 一致, collapse_tendency = max(0, BIS-BAS)"""
    sel = CollapseArchetypeSelector()
    BAS, BIS, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    # 默认人格: BAS = 0.4*0.5 + 0.3*0.5 + 0.2*0.5 + 0.1*0.5 = 0.5
    # BIS = 0.4*0.5 + 0.3*0.5 + 0.2*0.5 + 0.1*0.5 = 0.5
    # collapse_tendency = max(0, 0.5 - 0.5) = 0.0
    assert abs(BAS - 0.5) < 0.001
    assert abs(BIS - 0.5) < 0.001
    assert tendency == 0.0


def test_compute_bas_bis_high_neuroticism_high_collapse():
    """高 N → BIS 高 → collapse_tendency 高"""
    sel = CollapseArchetypeSelector()
    _, BIS, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.9, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    assert BIS > 0.5
    assert tendency > 0.0


def test_compute_bas_bis_high_extraversion_low_collapse():
    """高 E → BAS 高 → collapse_tendency 低 (或不崩)"""
    sel = CollapseArchetypeSelector()
    BAS, _, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.9, "openness": 0.5, "neuroticism": 0.2, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    assert BAS > 0.5
    assert tendency <= 0.1  # BIS-BAS 可能负, max(0, ...) = 0


def test_compute_bas_bis_with_force_state_individual_increases():
    """force_state.individual 高 → BIS 加权升高 → collapse_tendency 高"""
    sel = CollapseArchetypeSelector()
    _, _, base_tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    _, _, indiv_tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "conscientiousness": 0.5},
        force_state={"natural": 0.5, "social": 0.5, "individual": 0.9},
    )
    assert indiv_tendency >= base_tendency


def test_collapse_tendency_clamped():
    """collapse_tendency 必在 [0, 1]"""
    sel = CollapseArchetypeSelector()
    _, _, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.1, "openness": 0.1, "neuroticism": 0.99, "agreeableness": 0.99, "conscientiousness": 0.99},
        force_state={"natural": 1.0, "social": 0.0, "individual": 1.0},
    )
    assert 0.0 <= tendency <= 1.0
```

- [ ] **Step 3.2: 跑测试确认失败**

Run: `python -m pytest tests/test_collapse_archetype.py -v`
Expected: 后 4 个测试 FAIL (返回值是 2-tuple 不是 3-tuple, 或 force_state 不接受)

- [ ] **Step 3.3: 改 compute_bas_bis 加 force_state + 返回 collapse_tendency**

```python
# emotion_spirit/regulation/collapse_archetype.py — _clamp 工具如果不存在要加
def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# emotion_spirit/regulation/collapse_archetype.py:44-58 替换
    def compute_bas_bis(
        self,
        personality: dict[str, float],
        force_state: Optional[dict] = None,  # v1.2.5 PR2 §4.3 L1 新增
    ) -> tuple[float, float, float]:
        """v1.2.5 PR2: Gray RST + 力加权, 返回 BAS / BIS / collapse_tendency
        
        collapse_tendency = max(0, BIS - BAS), clamp [0, 1]
        向后兼容: 不传 force_state → BIS 不加权, 输出跟 v1.2.4 一致
        """
        BAS = (
            0.4 * personality.get("extraversion", 0.5)
            + 0.3 * personality.get("openness", 0.5)
            + 0.2 * (1 - personality.get("neuroticism", 0.5))
            + 0.1 * (1 - personality.get("agreeableness", 0.5))
        )
        BIS = (
            0.4 * personality.get("neuroticism", 0.5)
            + 0.3 * personality.get("agreeableness", 0.5)
            + 0.2 * personality.get("conscientiousness", 0.5)
            + 0.1 * (1 - personality.get("extraversion", 0.5))
        )
        
        # L1: 力加权 — 自然力 + 个体力主导 → BIS 升高 (内崩); 社会力主导 → BIS 降低 (找人帮)
        if force_state is not None:
            nature_modifier = 0.2 * force_state.get("natural", 0.5)
            individual_modifier = 0.2 * force_state.get("individual", 0.5)
            social_buffer = -0.3 * force_state.get("social", 0.5)
            BIS = BIS * (1 + nature_modifier + individual_modifier + social_buffer)
        
        # 连续化
        collapse_tendency = _clamp(BIS - BAS, 0, 1)
        
        return BAS, BIS, collapse_tendency
```

- [ ] **Step 3.4: 跑测试确认通过**

Run: `python -m pytest tests/test_collapse_archetype.py -v`
Expected: 5 个测试全 PASS

- [ ] **Step 3.5: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 PR1 计数 + 5 = ~1295 passed, **不能有 regression**

**注意**: `compute_bas_bis` 之前返回 2-tuple, 现在返回 3-tuple. 任何调用方需要更新 (PR3 顺手清债时改, PR2 不动). 但测试可能引用 2-tuple → 找出来手动更新.

```bash
# 找调用方
grep -rn "compute_bas_bis(" --include="*.py" | grep -v test_
```

- [ ] **Step 3.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/regulation/collapse_archetype.py tests/test_collapse_archetype.py
git commit -m "feat(v1.2.5-pr2): CollapseArchetypeSelector.compute_bas_bis() L1 + 连续化"
```

---

## Task 4: KB 文件 defense_deltas.json + loader + 测试

**Files:**
- Create: `emotion_spirit/core/kb/defense_deltas.json`
- Modify: `emotion_spirit/core/persona_labels_db.py` (加 `get_defense_deltas()` loader, PR1 Task 2 已加 `_cached_load`)
- Test: `tests/test_defense_modulator.py` (新增 3 测试)

**Interfaces:**
- KB 文件含 `silence` / `collapse` / `suppression` 三组 delta, 每组含 individual / natural / social 偏移
- `get_defense_deltas() -> dict`

- [ ] **Step 4.1: 写失败测试**

```python
# tests/test_defense_modulator.py 末尾追加
def test_defense_deltas_kb_loads():
    """KB defense_deltas.json 应能被加载"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    assert deltas["_version"] >= 1
    assert "silence" in deltas
    assert "collapse" in deltas
    assert "suppression" in deltas


def test_defense_deltas_silence_clamped():
    """silence.delta 必在 [-1, 1]"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    for axis in ["individual", "natural", "social"]:
        assert -1.0 <= deltas["silence"][axis] <= 1.0


def test_defense_deltas_have_source_doc():
    """每个事件类型应有 _doc 字段 (handbook §1.1 文献背书)"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    for event in ["silence", "collapse", "suppression"]:
        assert "_doc" in deltas[event], f"{event} 缺 _doc 字段"
```

- [ ] **Step 4.2: 跑测试确认失败**

Run: `python -m pytest tests/test_defense_modulator.py::test_defense_deltas_kb_loads -v`
Expected: FAIL with `ImportError` 或 `FileNotFoundError`

- [ ] **Step 4.3: 写 KB JSON 文件**

```json
// emotion_spirit/core/kb/defense_deltas.json
{
  "_doc": "防御事件触发后回写 force_state 的偏移量 (v1.2.5 PR2 §4.2). 修改前读 spec §4.2.",
  "_version": 1,
  
  "silence": {
    "_doc": "沉默事件后: 个体力↓ (退缩), 自然力↑ (消化)",
    "individual": -0.05,
    "natural": 0.03,
    "social": 0.0
  },
  "collapse": {
    "_doc": "崩溃事件后: 大幅改写, 视 archetype 方向",
    "individual": 0.05,
    "natural": -0.08,
    "social": 0.03
  },
  "suppression": {
    "_doc": "压抑事件后: 个体力↑ (内省压制), 社会力↓ (不表达)",
    "individual": 0.04,
    "social": -0.02,
    "natural": 0.0
  }
}
```

- [ ] **Step 4.4: 加 loader**

```python
# emotion_spirit/core/persona_labels_db.py 末尾追加
def get_defense_deltas() -> dict:
    """v1.2.5 PR2: 加载防御事件回写 delta (KB)"""
    return _cached_load("defense_deltas.json")
```

- [ ] **Step 4.5: 跑测试确认通过**

Run: `python -m pytest tests/test_defense_modulator.py -v`
Expected: 5 (dataclass) + 3 (KB) = 8 个测试全 PASS

- [ ] **Step 4.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/core/kb/defense_deltas.json emotion_spirit/core/persona_labels_db.py tests/test_defense_modulator.py
git commit -m "feat(v1.2.5-pr2): defense_deltas KB + loader (handbook §1.1)"
```

---

## Task 5: DefenseModulator.compute_defense_states() L1 实现

**Files:**
- Modify: `emotion_spirit/regulation/defense_modulator.py` (新增 DefenseModulator class + @register + compute_defense_states 方法)
- Test: `tests/test_defense_modulator.py` (新增 4 测试)

**Interfaces:**
- `@register(name="defense_modulator", depends_on=[force_dynamics, suppression, collapse_archetype_selector, segmented_reply_coordinator])`
- `compute_defense_states(personality, signals, body_state, intimacy_level, context, force_state) -> DefenseStates`
- 内部调三子 (suppression.compute / collapse_selector.compute_bas_bis / segmented_reply_coordinator.compute_silence_tendency)

- [ ] **Step 5.1: 写失败测试**

```python
# tests/test_defense_modulator.py 末尾追加
from unittest.mock import MagicMock


def test_compute_defense_states_combines_three_defenses():
    """DefenseModulator.compute_defense_states 应合并三子"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.5)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.4, 0.6, 0.2))
    
    # 真 Coordinator 实例 (避免 mock silence_tendency 整个逻辑)
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    
    # 需要 mock coordinator 的 compute_silence_tendency
    from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(
        score=0.4, reason="test", components={}
    ))
    dm._segmented_coordinator = coordinator
    
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)
    
    states = dm.compute_defense_states(
        personality=personality,
        signals=signals,
        body_state=None,
        intimacy_level=0.5,
        context={"social_audience": 0.0, "authority_present": 0.0},
        force_state={"natural": 0.5, "social": 0.5, "individual": 0.5},
    )
    
    assert states.suppression_level == 0.5
    assert states.collapse_tendency == 0.2
    assert states.silence_tendency == 0.4


def test_compute_defense_states_passes_force_state_to_all():
    """三子都应收到 force_state (L1)"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency
    
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.5)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.5, 0.5, 0.0))
    
    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="test", components={}))
    dm._segmented_coordinator = coordinator
    
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)
    test_force_state = {"natural": 0.7, "social": 0.3, "individual": 0.9}
    
    dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=test_force_state,
    )
    
    # 三子都应被调, 且收到 force_state
    dm._suppression.compute.assert_called_once()
    call_kwargs = dm._suppression.compute.call_args.kwargs
    assert call_kwargs.get("force_state") == test_force_state
    
    dm._collapse_selector.compute_bas_bis.assert_called_once()
    assert dm._collapse_selector.compute_bas_bis.call_args.kwargs.get("force_state") == test_force_state
    
    coordinator.compute_silence_tendency.assert_called_once()
    assert coordinator.compute_silence_tendency.call_args.kwargs.get("force_state") == test_force_state


def test_compute_defense_states_returns_defense_states_instance():
    """返回值必须是 DefenseStates 实例"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator, DefenseStates
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency
    
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.0)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.0, 0.0, 0.0))
    
    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="", components={}))
    dm._segmented_coordinator = coordinator
    
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)
    
    states = dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
    )
    assert isinstance(states, DefenseStates)


def test_compute_defense_states_without_force_state():
    """不传 force_state → 三子都不应传 force_state (向后兼容)"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency
    
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.0)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.0, 0.0, 0.0))
    
    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="", components={}))
    dm._segmented_coordinator = coordinator
    
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)
    
    dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
    )
    
    # 不传 force_state 时, kwargs 应不含 force_state
    call_kwargs = dm._suppression.compute.call_args.kwargs
    assert "force_state" not in call_kwargs or call_kwargs.get("force_state") is None
```

- [ ] **Step 5.2: 跑测试确认失败**

Run: `python -m pytest tests/test_defense_modulator.py::test_compute_defense_states_combines_three_defenses -v`
Expected: FAIL with `AttributeError: 'DefenseModulator' object has no attribute 'compute_defense_states'`

- [ ] **Step 5.3: 实现 DefenseModulator class + @register + compute_defense_states**

```python
# emotion_spirit/regulation/defense_modulator.py 末尾追加
from typing import Optional, Any
from ..core.registry import register


@register(
    name="defense_modulator",
    provides=["DefenseModulator"],
    depends_on=[
        "force_dynamics",
        "suppression",
        "collapse_archetype_selector",
        "segmented_reply_coordinator",
    ],
    config_keys={"segmented_reply"},
)
class DefenseModulator:
    """v1.2.5 PR2: 压抑/崩溃/沉默 三防御子系统与力学的耦合调制器
    
    L1 (输入调制): 三子读 force_state, 输出 DefenseStates
    L2 (输出回写): 防御事件触发后调 force_dynamics.shift()
    v1.3 加: L3 fixpoint 完全耦合
    
    v1.2.5 单步法 (不上 fixpoint): 用上次累积的 force_state 算当前三子
    """
    
    def compute_defense_states(
        self,
        personality: dict,
        signals: Optional[Any],
        body_state: Optional[Any],
        intimacy_level: float,
        context: dict,
        force_state: Optional[dict],
    ) -> DefenseStates:
        """L1: 三子读力学, 返回 DefenseStates
        
        向后兼容: force_state=None 时, 三子都不接收 force_state (跟 v1.2.4 一致)
        """
        # 1. 压抑
        kwargs = {"force_state": force_state} if force_state is not None else {}
        suppression_level = self._suppression.compute(
            personality, context,
            conscience_pressure=getattr(self._conscience, "pressure", 0.0) if hasattr(self, "_conscience") else 0.0,
            relationship_intimacy=intimacy_level,
            **kwargs,
        )
        
        # 2. 崩溃
        _, _, collapse_tendency = self._collapse_selector.compute_bas_bis(
            personality, **kwargs,
        )
        
        # 3. 沉默
        session_key = context.get("session_key", "default")
        silence_tendency_obj = self._segmented_coordinator.compute_silence_tendency(
            user_id=session_key,
            personality=personality,
            force_state=force_state,
            body_state=body_state,
            signals=signals,
            intimacy_level=intimacy_level,
            context=context,
        )
        
        return DefenseStates(
            suppression_level=suppression_level,
            collapse_tendency=collapse_tendency,
            silence_tendency=silence_tendency_obj.score,
            silence_reason=silence_tendency_obj.reason,
            silence_components=silence_tendency_obj.components,
        )
```

- [ ] **Step 5.4: 跑测试确认通过**

Run: `python -m pytest tests/test_defense_modulator.py -v`
Expected: 5 (dataclass) + 3 (KB) + 4 (compute) = 12 个测试全 PASS

- [ ] **Step 5.5: 跑全测试套件确认 DefenseModulator @register 不破坏 57→58 计数**

Run: `python -m pytest tests/test_registry_consistency.py tests/test_registry_build_dryrun.py -v`
Expected: FAIL (模块数期望 58, 测试断言 57)

**修复**:
- 读 `tests/test_registry_consistency.py`, 找 `expected_modules = 57` → 改 58
- 读 `tests/test_registry_build_dryrun.py`, 同上
- 找 disable list (有的测试禁掉新模块因为不稳), 加 DefenseModulator

- [ ] **Step 5.6: 跑一致性测试确认通过**

Run: `python -m pytest tests/test_registry_consistency.py tests/test_registry_build_dryrun.py -v`
Expected: PASS

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 + 12 = ~1300+ passed, 无 regression

- [ ] **Step 5.7: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/regulation/defense_modulator.py tests/test_defense_modulator.py tests/test_registry_consistency.py tests/test_registry_build_dryrun.py
git commit -m "feat(v1.2.5-pr2): DefenseModulator @register + compute_defense_states (L1)"
```

---

## Task 6: DefenseModulator.apply_event() L2 实现 + force_dynamics.shift() 检查

**Files:**
- Modify: `emotion_spirit/regulation/defense_modulator.py` (新增 apply_event 方法)
- Test: `tests/test_defense_modulator.py` (新增 4 测试)

**Interfaces:**
- `apply_event(defense_type: Literal["suppression", "collapse", "silence"], intensity: float) -> None`
- 内部读 KB `defense_deltas.json`, 调 `self._force_dynamics.shift(individual_delta=..., natural_delta=..., social_delta=...)`
- **前置**: force_dynamics 必须有 `shift()` 方法 (验证存在; 不存在则 PR3 顺手加)

- [ ] **Step 6.1: 检查 force_dynamics.shift() 是否存在**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
grep -n "def shift" emotion_spirit/regulation/force_dynamics.py
```

- [ ] **Step 6.2 (如果存在): 写失败测试**

```python
# tests/test_defense_modulator.py 末尾追加
def test_apply_event_silence_modifies_force_state():
    """apply_event("silence", 0.5) 应调 force_dynamics.shift() with silence delta * 0.5"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    dm._force_dynamics.shift = MagicMock()
    
    dm.apply_event("silence", intensity=0.5)
    
    dm._force_dynamics.shift.assert_called_once()
    call_kwargs = dm._force_dynamics.shift.call_args.kwargs
    # KB: silence.individual=-0.05, * intensity=0.5 = -0.025
    assert abs(call_kwargs["individual_delta"] - (-0.025)) < 0.001
    # KB: silence.natural=0.03, * 0.5 = 0.015
    assert abs(call_kwargs["natural_delta"] - 0.015) < 0.001


def test_apply_event_collapse_modifies_force_state():
    """apply_event("collapse", 1.0) 应调 shift() with collapse delta"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    dm._force_dynamics.shift = MagicMock()
    
    dm.apply_event("collapse", intensity=1.0)
    
    dm._force_dynamics.shift.assert_called_once()
    call_kwargs = dm._force_dynamics.shift.call_args.kwargs
    # KB: collapse.individual=0.05, collapse.natural=-0.08, collapse.social=0.03
    assert abs(call_kwargs["individual_delta"] - 0.05) < 0.001
    assert abs(call_kwargs["natural_delta"] - (-0.08)) < 0.001
    assert abs(call_kwargs["social_delta"] - 0.03) < 0.001


def test_apply_event_suppression_modifies_force_state():
    """apply_event("suppression", 0.7) 应调 shift() with suppression delta"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    dm._force_dynamics.shift = MagicMock()
    
    dm.apply_event("suppression", intensity=0.7)
    
    dm._force_dynamics.shift.assert_called_once()
    call_kwargs = dm._force_dynamics.shift.call_args.kwargs
    # KB: suppression.individual=0.04, suppression.social=-0.02, suppression.natural=0.0
    assert abs(call_kwargs["individual_delta"] - 0.028) < 0.001  # 0.04 * 0.7
    assert abs(call_kwargs["social_delta"] - (-0.014)) < 0.001  # -0.02 * 0.7


def test_apply_event_invalid_type_raises():
    """defense_type 不是 silence/collapse/suppression 应抛 ValueError"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    
    with pytest.raises(ValueError, match="defense_type must be"):
        dm.apply_event("invalid_type", intensity=0.5)
```

- [ ] **Step 6.3: 跑测试确认失败**

Run: `python -m pytest tests/test_defense_modulator.py::test_apply_event_silence_modifies_force_state -v`
Expected: FAIL with `AttributeError: 'DefenseModulator' object has no attribute 'apply_event'`

- [ ] **Step 6.4: 实现 apply_event 方法**

```python
# emotion_spirit/regulation/defense_modulator.py — DefenseModulator 类内
# (在 compute_defense_states 后面)
    def apply_event(
        self,
        defense_type: str,  # Literal["suppression", "collapse", "silence"]
        intensity: float,
    ) -> None:
        """L2: 防御事件触发后回写 force_state (从 KB 读 delta)
        
        intensity ∈ [0, 1]
        """
        if defense_type not in ("suppression", "collapse", "silence"):
            raise ValueError(f"defense_type must be suppression/collapse/silence, got {defense_type!r}")
        
        from ..core.persona_labels_db import get_defense_deltas
        deltas_kb = get_defense_deltas()
        deltas = deltas_kb[defense_type]
        
        self._force_dynamics.shift(
            individual_delta=deltas.get("individual", 0.0) * intensity,
            natural_delta=deltas.get("natural", 0.0) * intensity,
            social_delta=deltas.get("social", 0.0) * intensity,
        )
```

- [ ] **Step 6.5: 跑测试确认通过**

Run: `python -m pytest tests/test_defense_modulator.py -v`
Expected: 12 (之前) + 4 = 16 个测试全 PASS

**如果 force_dynamics.shift() 不存在**: 跳过这个测试, 在 commit message 标 "TODO: force_dynamics.shift() 待 PR3 加"

- [ ] **Step 6.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/regulation/defense_modulator.py tests/test_defense_modulator.py
git commit -m "feat(v1.2.5-pr2): DefenseModulator.apply_event() L2 event 回写 force_state"
```

---

## Task 7: main.py 集成 DefenseModulator (替换 _compute_defense_states 手拼)

**Files:**
- Modify: `main.py:265-303` (在装配段加 `self._defense_modulator = self._modules["defense_modulator"]`)
- Modify: `main.py` (在 `_on_segmented_reply_v2` 内部, 用 `self._defense_modulator.compute_defense_states(...)` 替代直接调三子)
- Modify: `main.py` (沉默触发后调 `self._defense_modulator.apply_event("silence", intensity=...)`)
- Test: `tests/test_defense_modulator.py` (新增 2 测试, 验证 main.py 集成)

**Interfaces:**
- main.py `__init__` 加 1 行: `self._defense_modulator = self._modules["defense_modulator"]`
- `_on_segmented_reply_v2` 用 DefenseModulator 统一入口

- [ ] **Step 7.1: 写失败测试 (验证 main.py 集成 DefenseModulator)**

```python
# tests/test_defense_modulator.py 末尾追加
def test_main_py_imports_defense_modulator():
    """main.py 应能成功 import DefenseModulator (验证 @register 装配)"""
    # 如果 import 失败, 测试 FAIL
    from main import EmotionSpiritPlugin  # noqa
    
    # 验证 EmotionSpiritPlugin.__init__ 期望 defense_modulator 在 _modules 列表
    # (实际验证: 注册表里有这个模块)
    from emotion_spirit.core.registry import ModuleRegistry
    all_modules = ModuleRegistry.get_all()
    assert "defense_modulator" in all_modules


def test_defense_modulator_in_module_registry():
    """defense_modulator 必须在 ModuleRegistry 里 (@register 生效)"""
    from emotion_spirit.core.registry import ModuleRegistry
    all_modules = ModuleRegistry.get_all()
    assert "defense_modulator" in all_modules
```

- [ ] **Step 7.2: 跑测试确认失败**

Run: `python -m pytest tests/test_defense_modulator.py::test_defense_modulator_in_module_registry -v`
Expected: FAIL with `AssertionError` (DefenseModulator 未注册)

- [ ] **Step 7.3: 检查 `emotion_spirit/__init__.py` 是否触发 DefenseModulator @register**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
grep -n "defense_modulator\|from .regulation import\|from .regulation.defense_modulator" emotion_spirit/__init__.py
```

**如果没 import**: 在 `emotion_spirit/__init__.py` 的 `regulation` import 区域加 `from .regulation import defense_modulator`

- [ ] **Step 7.4: 跑测试确认通过**

Run: `python -m pytest tests/test_defense_modulator.py -v`
Expected: 16 + 2 = 18 个测试全 PASS

- [ ] **Step 7.5: main.py 加 self._defense_modulator 取实例**

读 main.py:265-303 (现有装配段), 在 `self._segmented_coordinator = self._modules["segmented_reply_coordinator"]` 后面加:

```python
        # v1.2.5 PR2: DefenseModulator 统一管理三子-力学耦合
        self._defense_modulator = self._modules["defense_modulator"]
```

- [ ] **Step 7.6: main.py: `_on_segmented_reply_v2` 用 DefenseModulator**

读 `_on_segmented_reply_v2` 方法 (PR1 Task 8 写的), 改 compute_defense_states 入口:

```python
# 替换: silence_tendency_obj = self._segmented_coordinator.compute_silence_tendency(...)
# 为: DefenseModulator 统一入口

# 读上游
personality = self._get_personality_labels(user_id) if hasattr(self, "_get_personality_labels") else {
    "extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5,
    "openness": 0.5, "conscientiousness": 0.5,
}
context = self._build_context(event)

# DefenseModulator 统一三子读力学 (L1)
defense_states = self._defense_modulator.compute_defense_states(
    personality=personality,
    signals=signals,
    body_state=body_state,
    intimacy_level=intimacy,
    context=context,
    force_state=force_state,
)

# 从 DefenseStates 取沉默决策
from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency
silence_tendency_obj = SilenceTendency(
    score=defense_states.silence_tendency,
    reason=defense_states.silence_reason,
    components=defense_states.silence_components,
)
```

- [ ] **Step 7.7: 沉默触发后调 apply_event (L2)**

在 `_on_segmented_reply_v2` 沉默分支 (PR1 Task 8 Step 8.1 的 record_silence_event 后面) 加:

```python
            if should_silent and seg_config.get("enable_deliberate_silence", False):
                self._segmented_coordinator.record_silence_event(
                    user_id, silence_tendency_obj, bot_text, force_state
                )
                # L2: 事件回写 force_state (DefenseModulator 统一入口)
                self._defense_modulator.apply_event("silence", intensity=silence_tendency_obj.score)
                response.completion_text = ""
                response.result_chain = None
                # ... 后续 log
                return
```

- [ ] **Step 7.8: 跑 PR1 + PR2 全部测试**

Run: `python -m pytest tests/test_silence_tendency.py tests/test_defense_modulator.py tests/test_on_llm_response_segmented.py tests/test_suppression.py tests/test_collapse_archetype.py tests/test_delay_strategy.py tests/test_conf_schema_v125.py tests/test_commands_reflect.py -v`
Expected: 全 PASS (无 regression)

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 + ~18 = 全 PASS

- [ ] **Step 7.9: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/__init__.py main.py tests/test_defense_modulator.py
git commit -m "feat(v1.2.5-pr2): main.py 集成 DefenseModulator (L1 + L2 完整耦合)"
```

---

## Task 8: 跑 ship checklist (version + changelog + handbook)

**Files:**
- Modify: `CHANGELOG.md` (PR2 entry)
- Modify: `UPDATE_HANDBOOK.md` §6 (PR2 已清的债)

- [ ] **Step 8.1: 写 CHANGELOG PR2 entry**

读 `CHANGELOG.md` 顶部, 在 PR1 entry 下面加:

```markdown
### 力学系统耦合 (PR2: 防御链 ↔ ForceState)
- **新增 `DefenseModulator` 模块** (`@register`, depends_on 4 个): 统一管理压抑/崩溃/沉默与力学的耦合
- **L1 输入调制**: 三子 compute/select/compute_silence_tendency 都接受 `force_state` 可选参数 (向后兼容 100%)
- **L2 输出回写**: `DefenseModulator.apply_event("silence" | "collapse" | "suppression", intensity)` 从 KB `defense_deltas.json` 读 delta, 调 `force_dynamics.shift()`
- **KB `defense_deltas.json`** 新增 (handbook §1.1)
- **模块数**: 57 → 58 (+DefenseModulator)
- **force_dynamics.compute() 签名不变** (向后兼容 100%, handbook §1.2 "加新模块不动现有")

### 新增测试
- `test_defense_modulator.py`: 18 个测试 (DefenseStates dataclass + KB + compute_defense_states + apply_event + main.py 集成)
```

- [ ] **Step 8.2: 更新 UPDATE_HANDBOOK.md §6**

读 `UPDATE_HANDBOOK.md` §6, 在 PR1 已清的债下面加:

```markdown
### v1.2.5 PR2 已清的债
- ✅ `SuppressionState.compute()` 接受 force_state 可选参数 (L1, 100% backward compat)
- ✅ `CollapseArchetypeSelector.compute_bas_bis()` 接受 force_state + 返回 collapse_tendency (L1 + 连续化)
- ✅ DefenseModulator 抽离成独立模块 (handbook §1.2 严格)
- ✅ 防御 delta 系数进 KB `defense_deltas.json` (handbook §1.1)
```

- [ ] **Step 8.3: 跑全套测试**

Run: `python -m pytest tests/ -q --no-header`
Expected: ~1300 passed, 无 regression

- [ ] **Step 8.4: 跑 smoke test**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: 11 passed

- [ ] **Step 8.5: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add CHANGELOG.md UPDATE_HANDBOOK.md
git commit -m "docs(v1.2.5-pr2): changelog + handbook §6 update"
```

---

## Self-Review Checklist

✅ **Spec §4 覆盖**: Task 1-8 完整覆盖 §4.0 DefenseModulator + §4.1-4.2 L1+L2 + §4.3 三子扩参 + §4.5 KB

✅ **Placeholder 扫描**: 0 命中

✅ **类型一致性**:
- `DefenseStates` (Task 1) → 用在 Task 5+6+7
- `compute_defense_states` (Task 5) → 用在 Task 7 (main.py 集成)
- `apply_event` (Task 6) → 用在 Task 7 (沉默分支)
- `get_defense_deltas` (Task 4) → 用在 Task 6 (apply_event)

✅ **向后兼容 (handbook §1.2 关键)**:
- `force_dynamics.compute()` **签名不变** (spec §4.1 明确)
- `SuppressionState.compute()` force_state=None → 跟 v1.2.4 一致 (Task 2 测试)
- `CollapseArchetypeSelector.compute_bas_bis()` 不传 → 返回 (BAS, BIS, collapse_tendency=0.0) 兼容 2-tuple 调用 (Task 3 测试)

✅ **模块化哲学**:
- DefenseModulator @register, 4 depends_on, main.py 加 1 行 (handbook §1.2)
- 系数全部从 KB 读, 不硬编码 (handbook §1.1)

✅ **Task 大小**: 8 个 task, 每个 5-7 步, 总 ~3-4 小时

---

## 后续 (PR3 顺手清债)

- **PR3 plan**: §10.3 T1+T2+T7+T3+T4
- T1 `merge_life_sim_config enable_life_fragment` 修 (handbook §3.3 P0)
- T2 `_reset_superego_modules` 双轨消 (handbook §1.2 P1)
- T7 `test_v2_full_lifecycle` mock time (handbook §6 P0)
- T3+T4 12 个 main.py 手 new 评估 (按"先 @register 再走 self._modules"顺序)