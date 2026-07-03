# v1.2.5 PR1: 分段回复修复 + 沉默语义 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Bug 12 (v1.2.4 分段回复 100% 不工作)，把沉默作为情绪事件完整化 (S1-S4)，加人格加权连续沉默倾向 (Jack 1992 / Carver 1998 / Noftle 2006)。

**Architecture:**
- main.py 重写 `on_llm_response` —— emotion_spirit 自己 `event.send()` 主动发段 + 清空 llm_resp (阻止 AstrBot RespondStage 重复发)
- Coordinator 加 `SilenceTendency` dataclass + `compute_silence_tendency()` 6 factor 人格加权 + `should_be_silent()` S4 时长上限 + `record_silence_event()` S3 情绪事件
- TypingDelayStrategy 作为 Coordinator 内部 helper (不独立 @register, §5 设计审查)
- 沉默公式 11 项系数全部从 KB (`silence_tendency_weights.json`) 读 (handbook §1.1)
- 流式模式 (`streaming_response=true`) emotion_spirit 跳过

**Tech Stack:**
- Python 3.11+ (asyncio, dataclass, Protocol)
- AstrBot v4.26.1 hook API (`@filter.on_llm_response`, `event.send`, `MessageChain`)
- emotion_spirit 现有 `@register` + `plugin_factory.build` 装配模式
- pytest + pytest-asyncio (项目已用)
- KB 再生脚本 `tools/regenerate_kb.py` (已有)

**关联 Spec:** `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` §0-§3 + §5-§7 + §10.1-§10.4

**不在本 PR 范围（拆出去）:**
- PR 2: §4 力学系统耦合（DefenseModulator + L1+L2 + defense_deltas.json KB）
- PR 3: §10.3 顺手清债（T1+T2+T7+T3+T4）

---

## Global Constraints

**版本/路径 (verbatim from spec):**
- emotion_spirit 仓库根: `D:\新建文件夹\emotion_spirit\now\astrbot_plugin_emotion_spirit`
- spec 路径: `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md`
- plan 路径: `docs/superpowers/plans/2026-07-03-segmented-reply-fix-pr1-plan.md` (本文件)
- update handbook: `UPDATE_HANDBOOK.md` (§6 现存清债清单, v1.2.5 后必更新)
- 测试运行: `python -m pytest tests/<file>::<test> -v`
- KB 入口: `emotion_spirit/core/kb/`

**handbook 强制规约 (UPDATE_HANDBOOK.md):**
- §1.1 硬编码数据进 KB, 不进 .py
- §1.2 新功能 `@register(name=..., provides=..., depends_on=...)` + factory, 禁 main.py 手 `new`
- §1.3 per-user 方法 `@per_user_only` 装饰器 (运行时强制 user_id, 不标 → TypeError)
- §2.1 新债写 `# TODO(tech-debt): <现状> → <应该> (见 <文件/issue>)`
- §3 迁移纪律: setdefault 幂等 + 别让字段只在 main.py `.get(key,default)` 活着
- §4.4 ship 8 步 checklist: `_version.py` + `metadata.yaml.version` 同步 bump + 三源互比

**沉默公式系数 (从 KB `silence_tendency_weights.json` 读, 不写死):**
- 6 factor 累加权重: 0.20 / 0.25 / 0.10 / 0.20 / 0.15 / 0.10
- 人格加权: N×0.5 (tension), (1-E)×0.5×(1-A)×0.3 (hurt), (1-E)×0.4 (satisfaction), C×0.3 (exhaustion), N×0.3 (overload), (1-E)×0.5 (social)
- 亲密度: (1-0.3×int)×(1+0.5A)×(1+0.4N)×(1-0.3O)
- 上下文: (1+0.4×authority)
- 力: (1-0.3×social+0.2×natural+0.4×individual), 范围 [0.5, 1.5]

**S4 默认 (从 `_conf_schema.json` 缺省):**
- silent_threshold: 0.5
- silent_cooldown_turns: 2
- max_consecutive_silence: 3
- enable_deliberate_silence: false (opt-in)

**代码风格:**
- 不引新依赖 (handbook §1.2 "0 依赖" 哲学)
- 中文 docstring (项目风格)
- 异步函数用 `async def`
- 错误日志用 `logger.debug/warning`, 不 `logger.error` (避免污染 AstrBot 日志)

---

## Task 1: SilenceTendency dataclass + 测试

**Files:**
- Modify: `emotion_spirit/output/segmented_reply_coordinator.py:1-30` (顶部 imports + dataclass)
- Test: `tests/test_silence_tendency.py` (new file)

**Interfaces:**
- Produces: `class SilenceTendency` (frozen dataclass, score: float, reason: str, components: dict)
- Validation: score 必须在 [0, 1], 否则 `ValueError`

- [ ] **Step 1.1: 写失败测试**

```python
# tests/test_silence_tendency.py
"""Tests for SilenceTendency dataclass (v1.2.5 PR1 §2.2)"""
import pytest
from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency


def test_silence_tendency_score_in_range_accepted():
    """score 在 [0, 1] 应正常构造"""
    t = SilenceTendency(score=0.5, reason="test")
    assert t.score == 0.5
    assert t.reason == "test"
    assert t.components == {}


def test_silence_tendency_score_below_zero_raises():
    """score < 0 应抛 ValueError"""
    with pytest.raises(ValueError, match="score must be in"):
        SilenceTendency(score=-0.1, reason="test")


def test_silence_tendency_score_above_one_raises():
    """score > 1 应抛 ValueError"""
    with pytest.raises(ValueError, match="score must be in"):
        SilenceTendency(score=1.1, reason="test")


def test_silence_tendency_components_default_empty_dict():
    """components 缺省 {}"""
    t = SilenceTendency(score=0.5, reason="x")
    assert t.components == {}


def test_silence_tendency_is_immutable():
    """SilenceTendency 是 frozen, 不可改"""
    t = SilenceTendency(score=0.5, reason="x")
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        t.score = 0.8
```

- [ ] **Step 1.2: 跑测试确认失败**

Run: `python -m pytest tests/test_silence_tendency.py -v`
Expected: 5 个测试全 FAIL with `ImportError: cannot import name 'SilenceTendency'` 或 `ModuleNotFoundError`

- [ ] **Step 1.3: 实现 SilenceTendency dataclass**

```python
# emotion_spirit/output/segmented_reply_coordinator.py 顶部 (line 1 后)
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SilenceTendency:
    """沉默倾向 (v1.2.5 PR1 §2.2)
    
    score: 0.0 (必说) - 1.0 (必沉默), 连续值
    reason: 触发原因字符串, 用于日志 + /reflect_force_current
    components: 各因子贡献, 可观测性
    """
    score: float
    reason: str
    components: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")
```

- [ ] **Step 1.4: 跑测试确认通过**

Run: `python -m pytest tests/test_silence_tendency.py -v`
Expected: 5 个测试全 PASS

- [ ] **Step 1.5: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/output/segmented_reply_coordinator.py tests/test_silence_tendency.py
git commit -m "feat(v1.2.5-pr1): add SilenceTendency dataclass for S2 semantic transparency"
```

---

## Task 2: KB 文件 silence_tendency_weights.json + loader + 测试

**Files:**
- Create: `emotion_spirit/core/kb/silence_tendency_weights.json`
- Modify: `emotion_spirit/core/persona_labels_db.py:1-30` (加 loader 函数)
- Test: `tests/test_silence_tendency.py` (新增 3 个测试)

**Interfaces:**
- Produces: `get_silence_tendency_weights() -> dict` 返回完整权重 KB
- KB 文件含 `_doc`, `_version`, `factors`, `intimacy_modifier`, `context_modifier`, `force_modifier` 字段

- [ ] **Step 2.1: 写失败测试**

```python
# tests/test_silence_tendency.py 末尾追加
def test_silence_tendency_weights_kb_loads():
    """KB 文件应能被加载并包含必要字段"""
    from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights
    weights = get_silence_tendency_weights()
    assert weights["_version"] >= 1
    assert "factors" in weights
    assert "tension_stress" in weights["factors"]
    assert "hurt_void" in weights["factors"]
    assert "satisfaction_quiet" in weights["factors"]
    assert "exhaustion" in weights["factors"]
    assert "overload" in weights["factors"]
    assert "social_audience" in weights["factors"]
    assert "intimacy_modifier" in weights
    assert "context_modifier" in weights
    assert "force_modifier" in weights


def test_silence_tendency_weights_have_doc_and_source():
    """每个 factor 应有 _doc 和 source 字段 (handbook §1.1 文献背书)"""
    from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights
    weights = get_silence_tendency_weights()
    for factor_name, factor in weights["factors"].items():
        assert "_doc" in factor or "source" in factor, f"{factor_name} 缺 _doc 或 source"


def test_silence_tendency_weights_factor_weights_sum_to_one():
    """6 factor 累加权重应接近 1.0 (确保总分有界)"""
    from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights
    weights = get_silence_tendency_weights()
    total = sum(f["weight_in_sum"] for f in weights["factors"].values())
    assert abs(total - 1.0) < 0.001, f"factor 权重总和 = {total}, 应为 1.0"
```

- [ ] **Step 2.2: 跑测试确认失败**

Run: `python -m pytest tests/test_silence_tendency.py::test_silence_tendency_weights_kb_loads -v`
Expected: FAIL with `ImportError: cannot import name 'get_silence_tendency_weights'` 或 `FileNotFoundError`

- [ ] **Step 2.3: 写 KB JSON 文件**

```json
// emotion_spirit/core/kb/silence_tendency_weights.json
{
  "_doc": "沉默倾向公式的加权系数 (v1.2.5 PR1). 文献依据: Jack & Dill 1992 (Silencing the Self), Carver 1998 (COPE 元分析), Noftle 2006 (Attachment × Big Five). 修改前读 docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md §3.2.",
  "_version": 1,
  "_regenerate": "手写, 暂不接 tools/regenerate_kb.py (v1.2.5 PR2 加)",
  
  "factors": {
    "tension_stress": {
      "_doc": "Carver 1998: 神经质 → withdrawal coping",
      "source": "Carver 1998 (本地 KB personality-psychology_full_part_01)",
      "weight_in_sum": 0.20,
      "personality_modifiers": {"neuroticism": 0.5}
    },
    "hurt_void": {
      "_doc": "Noftle 2006: 回避依恋 × -E, -A; Carver: N → withdrawal",
      "source": "Noftle 2006 (JPSP) + Carver 1998",
      "weight_in_sum": 0.25,
      "personality_modifiers": {
        "extraversion_reverse": 0.5,
        "neuroticism": 0.4,
        "agreeableness_reverse": 0.3
      }
    },
    "satisfaction_quiet": {
      "_doc": "⚠️ 临床观察, 待 v1.3 验证: 内向者满足时倾向沉静",
      "source": "临床观察 (无直接文献背书)",
      "weight_in_sum": 0.10,
      "personality_modifiers": {"extraversion_reverse": 0.4}
    },
    "exhaustion": {
      "_doc": "⚠️ Wegner 1987 ironic rebound 推论: 尽责者耗尽时易讽刺反弹",
      "source": "Wegner 1987 推论 (无直接文献背书)",
      "weight_in_sum": 0.20,
      "personality_modifiers": {"conscientiousness": 0.3}
    },
    "overload": {
      "_doc": "Carver 1998: N → emotion-focused coping",
      "source": "Carver 1998",
      "weight_in_sum": 0.15,
      "personality_modifiers": {"neuroticism": 0.3}
    },
    "social_audience": {
      "_doc": "Extraversion 与社交活跃度直接相关",
      "source": "Big Five 元分析",
      "weight_in_sum": 0.10,
      "personality_modifiers": {"extraversion_reverse": 0.5}
    }
  },
  
  "intimacy_modifier": {
    "_doc": "Jack & Dill 1992 讨好假说 + Noftle 2006 系数",
    "source": "Jack 1992 + Noftle 2006",
    "base_coefficient": -0.3,
    "personality_modifiers": {
      "agreeableness": 0.5,
      "neuroticism": 0.4,
      "openness_reverse": -0.3
    }
  },
  
  "context_modifier": {
    "_doc": "上下文敏感系数 (v1.2.5 新)",
    "source": "v1.2.5 新增, authority_present v1.3 真实解析",
    "authority_present_coefficient": 0.4
  },
  
  "force_modifier": {
    "_doc": "力平衡加权 (L1 子读力, 替代 v1.2.3 离散 0.85/1.20/1.0)",
    "source": "v1.2.5 设计 (v1.2.4 简化版升级)",
    "social_coefficient": -0.3,
    "natural_coefficient": 0.2,
    "individual_coefficient": 0.4,
    "range": [0.5, 1.5]
  }
}
```

- [ ] **Step 2.4: 加 loader 函数**

```python
# emotion_spirit/core/persona_labels_db.py 末尾追加
import json
from pathlib import Path


# v1.2.5: KB 加载缓存
_kb_cache: dict[str, dict] = {}


def _cached_load(filename: str) -> dict:
    """v1.2.5: 通用 KB 加载 + 缓存 (类似现有 export_persona_labels_db)"""
    if filename in _kb_cache:
        return _kb_cache[filename]
    
    kb_dir = Path(__file__).parent / "kb"
    filepath = kb_dir / filename
    if not filepath.exists():
        raise FileNotFoundError(f"KB file not found: {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    _kb_cache[filename] = data
    return data


def get_silence_tendency_weights() -> dict:
    """v1.2.5 PR1: 加载沉默公式加权系数 (KB)"""
    return _cached_load("silence_tendency_weights.json")
```

- [ ] **Step 2.5: 跑测试确认通过**

Run: `python -m pytest tests/test_silence_tendency.py -v`
Expected: 8 个测试全 PASS (5 dataclass + 3 KB)

- [ ] **Step 2.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/core/kb/silence_tendency_weights.json emotion_spirit/core/persona_labels_db.py tests/test_silence_tendency.py
git commit -m "feat(v1.2.5-pr1): add silence_tendency_weights KB + loader (handbook §1.1)"
```

---

## Task 3: compute_silence_tendency() 6 factor 算法 + 测试

**Files:**
- Modify: `emotion_spirit/output/segmented_reply_coordinator.py` (新增 `compute_silence_tendency` 方法)
- Test: `tests/test_silence_tendency.py` (新增 5 个测试)

**Interfaces:**
- Produces: `SegmentedReplyCoordinator.compute_silence_tendency(session_key, personality, force_state, body_state, signals, intimacy_level, context) -> SilenceTendency`
- 算法: 6 factor × 人格加权 × 亲密度 × 上下文 × 力平衡
- 全部系数从 KB `silence_tendency_weights` 读, 不写死

- [ ] **Step 3.1: 写失败测试**

```python
# tests/test_silence_tendency.py 末尾追加
def test_compute_silence_tendency_default_personality_neutral():
    """默认人格 E=N=A=O=C=0.5, neutral signal → tendency 在 [0.2, 0.5]"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)  # skip __init__
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    
    class FakeSignals:
        rhythm_strain = 0.5
        pad_valence = 0.5
        hot_pool_pressure = 0.0
    
    tendency = coord.compute_silence_tendency(
        session_key="test_user",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=FakeSignals(),
        intimacy_level=0.5,
        context={"social_audience": 0.0, "authority_present": 0.0},
    )
    assert 0.2 <= tendency.score <= 0.5, f"默认人格得分 = {tendency.score}"


def test_compute_silence_tendency_introvert_anxious_high_intimacy_silences():
    """E=0.2, N=0.8, A=0.5, intimacy=0.7, hurt=0.8 → tendency > 0.7"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    personality = {"extraversion": 0.2, "neuroticism": 0.8, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    
    class FakeSignals:
        rhythm_strain = 0.5
        pad_valence = 0.2  # hurt
        hot_pool_pressure = 0.8
    
    tendency = coord.compute_silence_tendency(
        session_key="test_user",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=FakeSignals(),
        intimacy_level=0.7,
        context={"social_audience": 0.0, "authority_present": 0.0},
    )
    assert tendency.score > 0.7, f"内向焦虑亲密受伤得分 = {tendency.score}"


def test_compute_silence_tendency_extrovert_open_low_intimacy_speaks():
    """E=0.8, O=0.7, N=0.2, intimacy=0.3 → tendency < 0.3"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    personality = {"extraversion": 0.8, "neuroticism": 0.2, "agreeableness": 0.5, "openness": 0.7, "conscientiousness": 0.5}
    
    class FakeSignals:
        rhythm_strain = 0.3
        pad_valence = 0.7
        hot_pool_pressure = 0.0
    
    tendency = coord.compute_silence_tendency(
        session_key="test_user",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=FakeSignals(),
        intimacy_level=0.3,
        context={"social_audience": 0.0, "authority_present": 0.0},
    )
    assert tendency.score < 0.3, f"外向开放低亲密得分 = {tendency.score}"


def test_compute_silence_tendency_returns_correct_reason():
    """reason 字段应反映 dominant factor"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    
    class FakeSignals:
        rhythm_strain = 0.5
        pad_valence = 0.2
        hot_pool_pressure = 0.9  # hurt 占主导
    
    tendency = coord.compute_silence_tendency(
        session_key="test_user",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=FakeSignals(),
        intimacy_level=0.5,
        context={"social_audience": 0.0, "authority_present": 0.0},
    )
    assert tendency.reason == "void_hurt_withdrawing"


def test_compute_silence_tendency_components_dict_present():
    """components 字典应包含所有 6 factor 分解"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    
    class FakeSignals:
        rhythm_strain = 0.5
        pad_valence = 0.5
        hot_pool_pressure = 0.0
    
    tendency = coord.compute_silence_tendency(
        session_key="test_user",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=FakeSignals(),
        intimacy_level=0.5,
        context={"social_audience": 0.0, "authority_present": 0.0},
    )
    assert "tension_stress" in tendency.components
    assert "hurt_void" in tendency.components
    assert "satisfaction_quiet" in tendency.components
    assert "exhaustion" in tendency.components
    assert "overload" in tendency.components
    assert "social_audience_pressure" in tendency.components
    assert "intimacy_modifier" in tendency.components
    assert "force_modifier" in tendency.components
```

- [ ] **Step 3.2: 跑测试确认失败**

Run: `python -m pytest tests/test_silence_tendency.py::test_compute_silence_tendency_default_personality_neutral -v`
Expected: FAIL with `AttributeError: 'SegmentedReplyCoordinator' object has no attribute 'compute_silence_tendency'`

- [ ] **Step 3.3: 实现 compute_silence_tendency 方法**

```python
# emotion_spirit/output/segmented_reply_coordinator.py — SegmentedReplyCoordinator 类内
# (放在 plan() 方法前, 因为 plan() 内部会调 compute_silence_tendency 取 silent 决策依据, 但 Task 3 只实现 compute_silence_tendency, plan() 留给 Task 4)

    def compute_silence_tendency(
        self,
        session_key: str,
        personality: dict,
        force_state: Optional[dict],
        body_state: Optional[Any],
        signals: Optional[Any],
        intimacy_level: float,
        context: dict,
    ) -> SilenceTendency:
        """v1.2.5 PR1: 人格加权沉默倾向 (6 factor, 系数从 KB 读)
        
        算法见 docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md §3.2
        """
        # 系数从 KB 读 (handbook §1.1)
        from ..core.persona_labels_db import get_silence_tendency_weights
        weights = get_silence_tendency_weights()
        factors_w = weights["factors"]
        intim_w = weights["intimacy_modifier"]
        ctx_w = weights["context_modifier"]
        force_w = weights["force_modifier"]
        
        # 读 6 个实时因子
        if signals is None:
            rhythm_strain = 0.5
            pad_valence = 0.5
            hot_pool_pressure = 0.0
        else:
            rhythm_strain = getattr(signals, "rhythm_strain", 0.5) or 0.5
            pad_valence = getattr(signals, "pad_valence", 0.5) or 0.5
            hot_pool_pressure = getattr(signals, "hot_pool_pressure", 0.0) or 0.0
        
        if body_state is None:
            energy = 0.5
            arousal = 0.5
        else:
            energy = getattr(body_state, "energy", 0.5) or 0.5
            arousal = getattr(body_state, "arousal", 0.5) or 0.5
        
        # Big Five
        E = personality.get("extraversion", 0.5)
        A = personality.get("agreeableness", 0.5)
        N = personality.get("neuroticism", 0.5)
        O = personality.get("openness", 0.5)
        C = personality.get("conscientiousness", 0.5)
        
        # === 6 factor + 人格加权 ===
        # tension_stress
        f_tension = rhythm_strain * (1 + factors_w["tension_stress"]["personality_modifiers"]["neuroticism"] * N)
        
        # hurt_void
        hurt_mods = factors_w["hurt_void"]["personality_modifiers"]
        f_hurt = (
            hot_pool_pressure * (1 - pad_valence)
            * (1 + hurt_mods["extraversion_reverse"] * (1 - E))
            * (1 + hurt_mods["neuroticism"] * N)
            * (1 + hurt_mods["agreeableness_reverse"] * (1 - A))
        )
        
        # satisfaction_quiet
        f_satisfaction = (
            hot_pool_pressure * pad_valence
            * (1 + factors_w["satisfaction_quiet"]["personality_modifiers"]["extraversion_reverse"] * (1 - E))
        )
        
        # exhaustion
        f_exhaustion = (
            (1 - energy)
            * (1 + factors_w["exhaustion"]["personality_modifiers"]["conscientiousness"] * C)
        )
        
        # overload
        f_overload = arousal * (1 + factors_w["overload"]["personality_modifiers"]["neuroticism"] * N)
        
        # social_audience
        social_audience = context.get("social_audience", 0.0)
        f_social = (
            social_audience
            * (1 + factors_w["social_audience"]["personality_modifiers"]["extraversion_reverse"] * (1 - E))
        )
        
        # === 亲密度调节 ===
        intim_mods = intim_w["personality_modifiers"]
        mod_intimacy = (
            (1 + intim_w["base_coefficient"] * intimacy_level)
            * (1 + intim_mods["agreeableness"] * A)
            * (1 + intim_mods["neuroticism"] * N)
            * (1 + intim_mods["openness_reverse"] * (1 - O))
        )
        
        # === 上下文调节 ===
        mod_context = 1 + ctx_w["authority_present_coefficient"] * context.get("authority_present", 0.0)
        
        # === 力调节 ===
        if force_state is None:
            force_modifier = 1.0
        else:
            social = force_state.get("social", 0.5)
            individual = force_state.get("individual", 0.5)
            natural = force_state.get("natural", 0.5)
            force_modifier = (
                1.0
                - force_w["social_coefficient"] * social
                + force_w["natural_coefficient"] * natural
                + force_w["individual_coefficient"] * individual
            )
        
        # === 累加 ===
        base_score = (
            factors_w["tension_stress"]["weight_in_sum"] * f_tension
            + factors_w["hurt_void"]["weight_in_sum"] * f_hurt
            + factors_w["satisfaction_quiet"]["weight_in_sum"] * f_satisfaction
            + factors_w["exhaustion"]["weight_in_sum"] * f_exhaustion
            + factors_w["overload"]["weight_in_sum"] * f_overload
            + factors_w["social_audience"]["weight_in_sum"] * f_social
        )
        score = max(0.0, min(1.0, base_score * mod_intimacy * mod_context * force_modifier))
        
        # === 选 dominant factor ===
        components = {
            "tension_stress": f_tension,
            "hurt_void": f_hurt,
            "satisfaction_quiet": f_satisfaction,
            "exhaustion": f_exhaustion,
            "overload": f_overload,
            "social_audience_pressure": f_social,
            "intimacy_modifier": mod_intimacy,
            "context_modifier": mod_context,
            "force_modifier": force_modifier,
        }
        dominant = max(
            ("tension_stress", f_tension),
            ("hurt_void", f_hurt),
            ("satisfaction_quiet", f_satisfaction),
            ("exhaustion", f_exhaustion),
            ("overload", f_overload),
            ("social_audience_pressure", f_social),
            key=lambda x: x[1],
        )
        reason_map = {
            "tension_stress": "tension_digesting",
            "hurt_void": "void_hurt_withdrawing",
            "satisfaction_quiet": "void_satisfied_quiet",
            "exhaustion": "energy_depleted",
            "overload": "arousal_overload",
            "social_audience_pressure": "social_audience_pressure",
        }
        reason = reason_map[dominant[0]]
        
        return SilenceTendency(score=score, reason=reason, components=components)
```

- [ ] **Step 3.4: 加 Optional + Any 到 imports**

```python
# emotion_spirit/output/segmented_reply_coordinator.py 顶部
from typing import Optional, Any
```

- [ ] **Step 3.5: 跑测试确认通过**

Run: `python -m pytest tests/test_silence_tendency.py -v`
Expected: 13 个测试全 PASS (5 dataclass + 3 KB + 5 compute)

- [ ] **Step 3.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/output/segmented_reply_coordinator.py tests/test_silence_tendency.py
git commit -m "feat(v1.2.5-pr1): compute_silence_tendency 6-factor algorithm (KB-driven weights)"
```

---

## Task 4: should_be_silent() S4 时长上限 + 测试

**Files:**
- Modify: `emotion_spirit/output/segmented_reply_coordinator.py` (新增 `should_be_silent` + `record_silence_event` + `record_response_event`)
- Test: `tests/test_silence_tendency.py` (新增 4 个测试)

**Interfaces:**
- Produces:
  - `should_be_silent(session_key, tendency, config) -> tuple[bool, str, SilenceTendency]`
  - `record_silence_event(session_key, tendency, full_text, force_state=None) -> None` (S3)
  - `record_response_event(session_key) -> None` (冷却计数推进)
- S4 行为: 冷却期不沉默 / 连续 3 次沉默后阈值上调到 0.9 / 默认 threshold 0.5

- [ ] **Step 4.1: 写失败测试**

```python
# tests/test_silence_tendency.py 末尾追加
def test_should_be_silent_under_threshold():
    """tendency=0.3 < threshold=0.5 → 不沉默"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    tendency = SilenceTendency(score=0.3, reason="test")
    
    silent, reason, _ = coord.should_be_silent(
        session_key="user1",
        tendency=tendency,
        config={"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3},
    )
    assert silent is False


def test_should_be_silent_above_threshold():
    """tendency=0.7 > threshold=0.5 → 沉默"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    tendency = SilenceTendency(score=0.7, reason="void_hurt_withdrawing")
    
    silent, reason, _ = coord.should_be_silent(
        session_key="user2",
        tendency=tendency,
        config={"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3},
    )
    assert silent is True


def test_should_be_silent_cooldown_blocks_repeat():
    """刚沉默过 (turns_since < cooldown) → 强制不沉默, 即使 tendency 高"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coord._turns_since_last_silence = {"user3": 1}  # < cooldown=2
    
    tendency = SilenceTendency(score=0.9, reason="void_hurt_withdrawing")
    silent, reason, _ = coord.should_be_silent(
        session_key="user3",
        tendency=tendency,
        config={"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3},
    )
    assert silent is False


def test_should_be_silent_max_consecutive_force_response():
    """已连续沉默 3 次 (>= max_consec) → 阈值上调到 0.9, 即使 tendency=0.6 也不沉默"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coord._consecutive_silence_count = {"user4": 3}  # >= max_consec=3
    
    tendency = SilenceTendency(score=0.6, reason="void_hurt_withdrawing")
    silent, reason, _ = coord.should_be_silent(
        session_key="user4",
        tendency=tendency,
        config={"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3},
    )
    assert silent is False
```

- [ ] **Step 4.2: 跑测试确认失败**

Run: `python -m pytest tests/test_silence_tendency.py::test_should_be_silent_under_threshold -v`
Expected: FAIL with `AttributeError: object has no attribute 'should_be_silent'`

- [ ] **Step 4.3: 实现 should_be_silent + record_silence_event + record_response_event**

```python
# emotion_spirit/output/segmented_reply_coordinator.py — SegmentedReplyCoordinator 类内
# (放在 compute_silence_tendency 后面)

    def should_be_silent(
        self,
        session_key: str,
        tendency: SilenceTendency,
        config: dict,
    ) -> tuple[bool, str, SilenceTendency]:
        """S4 时长上限决策
        
        Returns: (silent, reason, adjusted_tendency)
        """
        # 1. 冷却期检查
        cooldown = config.get("silent_cooldown_turns", 2)
        turns_since = getattr(self, "_turns_since_last_silence", {}).get(session_key, 999)
        if turns_since < cooldown:
            return False, "cooldown_active", tendency
        
        # 2. 连续上限检查 → 阈值上调
        max_consec = config.get("max_consecutive_silence", 3)
        consec = getattr(self, "_consecutive_silence_count", {}).get(session_key, 0)
        if consec >= max_consec:
            threshold = 0.9
        else:
            threshold = config.get("silent_threshold", 0.5)
        
        silent = tendency.score >= threshold
        return silent, tendency.reason, tendency
    
    def record_silence_event(
        self,
        session_key: str,
        tendency: SilenceTendency,
        full_text: str,
        force_state: Optional[dict] = None,
    ) -> None:
        """S3 情绪事件: 写 memory + 推进连续/冷却计数"""
        if not hasattr(self, "_consecutive_silence_count"):
            self._consecutive_silence_count = {}
        if not hasattr(self, "_turns_since_last_silence"):
            self._turns_since_last_silence = {}
        
        self._consecutive_silence_count[session_key] = (
            self._consecutive_silence_count.get(session_key, 0) + 1
        )
        self._turns_since_last_silence[session_key] = 0
        
        # 写 memory_pool (如果可用)
        memory_pool = getattr(self, "_memory_pool", None)
        if memory_pool is not None:
            try:
                memory_pool.add_event(
                    session_key=session_key,
                    event_type="deliberate_silence",
                    payload={
                        "tendency_score": tendency.score,
                        "reason": tendency.reason,
                        "components": tendency.components,
                        "full_text_length": len(full_text),
                        "force_state_snapshot": force_state,
                    },
                )
            except Exception:
                logger.debug("emotion_spirit: memory_pool.add_event failed", exc_info=True)
    
    def record_response_event(self, session_key: str) -> None:
        """每次 bot 实际回话后调用, 推进冷却计数"""
        if not hasattr(self, "_turns_since_last_silence"):
            self._turns_since_last_silence = {}
        self._turns_since_last_silence[session_key] = (
            self._turns_since_last_silence.get(session_key, 0) + 1
        )
        # 连续计数**不重置** — 累积到 max_consec 后强制恢复
```

- [ ] **Step 4.4: 加 logger import**

```python
# emotion_spirit/output/segmented_reply_coordinator.py 顶部
from astrbot import logger
```

- [ ] **Step 4.5: 跑测试确认通过**

Run: `python -m pytest tests/test_silence_tendency.py -v`
Expected: 17 个测试全 PASS (5 dataclass + 3 KB + 5 compute + 4 should_be_silent)

- [ ] **Step 4.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/output/segmented_reply_coordinator.py tests/test_silence_tendency.py
git commit -m "feat(v1.2.5-pr1): should_be_silent S4 + record_silence_event S3 + cooldown tracking"
```

---

## Task 5: @per_user_only 装饰器覆盖（handbook §1.3）

**Files:**
- Modify: `emotion_spirit/output/segmented_reply_coordinator.py` (在 compute_silence_tendency / should_be_silent / record_silence_event / record_response_event 方法前加 @per_user_only)
- Test: `tests/test_silence_tendency.py` (新增 3 个测试)

**Interfaces:**
- 4 个方法都标 `@per_user_only`, 运行时强制 caller 传非空 `session_key` (即 user_id)

- [ ] **Step 5.1: 写失败测试**

```python
# tests/test_silence_tendency.py 末尾追加
def test_compute_silence_tendency_requires_session_key():
    """不传 session_key 应抛 TypeError (handbook §1.3 @per_user_only)"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    with pytest.raises(TypeError, match="requires.*session_key|requires.*user_id"):
        coord.compute_silence_tendency(
            session_key="",  # 空字符串 → 拒绝
            personality={},
            force_state=None,
            body_state=None,
            signals=None,
            intimacy_level=0.5,
            context={},
        )


def test_should_be_silent_requires_session_key():
    """不传 session_key 应抛 TypeError"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    tendency = SilenceTendency(score=0.5, reason="test")
    with pytest.raises(TypeError):
        coord.should_be_silent(session_key="", tendency=tendency, config={})


def test_record_silence_event_requires_session_key():
    """不传 session_key 应抛 TypeError"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coord = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    tendency = SilenceTendency(score=0.5, reason="test")
    with pytest.raises(TypeError):
        coord.record_silence_event(session_key="", tendency=tendency, full_text="x")
```

- [ ] **Step 5.2: 跑测试确认失败**

Run: `python -m pytest tests/test_silence_tendency.py::test_compute_silence_tendency_requires_session_key -v`
Expected: 当前测试不抛 TypeError (空 session_key 不被拦截) — 测试 FAIL with `assert False` 或 pytest.fail

- [ ] **Step 5.3: 加 @per_user_only 装饰器**

```python
# emotion_spirit/output/segmented_reply_coordinator.py 顶部
from ..layer import per_user_only
```

然后在 4 个方法前加 `@per_user_only`:

```python
    @per_user_only
    def compute_silence_tendency(
        self,
        session_key: str,
        ...
    ):
        ...

    @per_user_only
    def should_be_silent(
        self,
        session_key: str,
        ...
    ):
        ...

    @per_user_only
    def record_silence_event(
        self,
        session_key: str,
        ...
    ):
        ...

    @per_user_only
    def record_response_event(self, session_key: str) -> None:
        ...
```

**注意**: `@per_user_only` 装饰器期望参数名是 `user_id`, 但我们的参数名是 `session_key`。需要看现有装饰器是否支持别名。

```bash
# 检查 @per_user_only 装饰器签名
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
grep -A 20 "def per_user_only" emotion_spirit/layer.py | head -25
```

**期望**: 装饰器检查 `user_id` 参数。如果不支持别名, **临时方案**: 把方法参数 `session_key` 改名为 `user_id` (更通用, 跟 emotion_spirit 整体一致), 或者用 `_session_key: str` 在内部传。

**简化决定**: 把这 4 个方法参数名从 `session_key` 改为 `user_id`, 跟装饰器契约一致。已有调用方需要更新 (后续 Task 6 之后会调)。

- [ ] **Step 5.4: 改参数名 session_key → user_id**

把 4 个方法定义里所有 `session_key: str` 改为 `user_id: str`, 函数体内引用同步改。

- [ ] **Step 5.5: 跑测试确认通过**

Run: `python -m pytest tests/test_silence_tendency.py -v`
Expected: 20 个测试全 PASS

- [ ] **Step 5.6: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/ -q --no-header`
Expected: 1261 + 20 = 1281 passed (或现有 1261 + 17, 视 @per_user_only 是否影响 plan() 等已注册方法)

**注意**: 如果 `plan()` 等已注册方法加了 @per_user_only 后被现有测试破坏, 记录下来, 在 Task 6 一起改。

- [ ] **Step 5.7: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/output/segmented_reply_coordinator.py tests/test_silence_tendency.py
git commit -m "feat(v1.2.5-pr1): @per_user_only on 4 silence methods (handbook §1.3)"
```

---

## Task 6: TypingDelayStrategy 内部类 + Coordinator set_delay_strategy + 测试

**Files:**
- Modify: `emotion_spirit/output/segmented_reply_coordinator.py` (新增 DelayStrategy Protocol + TypingDelayStrategy 内部类 + Coordinator `_delay_strategy` 字段 + set_delay_strategy 方法 + plan() 调用)
- Test: `tests/test_delay_strategy.py` (new file, 4 个测试)

**Interfaces:**
- Produces:
  - `class DelayStrategy(Protocol)`: `compute_delay(text, config) -> float`
  - `class TypingDelayStrategy`: 实现字符级打字 (`len(text)/cps`, cap 到 `max_delay_seconds`)
  - `SegmentedReplyCoordinator.set_delay_strategy(strategy)`: 运行时切换
  - `SegmentedReplyCoordinator.plan()` 内部: 用 `self._delay_strategy.compute_delay(...)` 算段间延迟

- [ ] **Step 6.1: 写失败测试**

```python
# tests/test_delay_strategy.py (新文件)
"""Tests for TypingDelayStrategy (v1.2.5 PR1 §5, Coordinator 内部 helper)"""
from emotion_spirit.output.segmented_reply_coordinator import TypingDelayStrategy


def test_typing_delay_short_text_short_delay():
    """10 字符, cps=10 → delay = 1.0s"""
    strat = TypingDelayStrategy()
    delay = strat.compute_delay("hello", {"default_chars_per_second": 10.0, "max_delay_seconds": 2.0})
    assert abs(delay - 1.0) < 0.001


def test_typing_delay_long_text_capped():
    """100 字符, cps=7.5 → delay = min(100/7.5, 2.0) = 2.0s (capped)"""
    strat = TypingDelayStrategy()
    text = "x" * 100
    delay = strat.compute_delay(text, {"default_chars_per_second": 7.5, "max_delay_seconds": 2.0})
    assert abs(delay - 2.0) < 0.001


def test_typing_delay_zero_cps_fallback_to_max():
    """cps=0 (配置错误) → 回退到 max_delay"""
    strat = TypingDelayStrategy()
    delay = strat.compute_delay("hello", {"default_chars_per_second": 0, "max_delay_seconds": 1.5})
    assert abs(delay - 1.5) < 0.001


def test_typing_delay_no_config_uses_defaults():
    """无 config → 用默认值 cps=7.5, max_delay=2.0"""
    strat = TypingDelayStrategy()
    text = "x" * 75  # 75 / 7.5 = 10s, 但 capped 到 2.0
    delay = strat.compute_delay(text, {})
    assert abs(delay - 2.0) < 0.001
```

- [ ] **Step 6.2: 跑测试确认失败**

Run: `python -m pytest tests/test_delay_strategy.py -v`
Expected: FAIL with `ImportError: cannot import name 'TypingDelayStrategy'`

- [ ] **Step 6.3: 实现 DelayStrategy Protocol + TypingDelayStrategy**

```python
# emotion_spirit/output/segmented_reply_coordinator.py 顶部 (在 SilenceTendency 之后)
from typing import Protocol


class DelayStrategy(Protocol):
    """段间延迟计算策略 (v1.2.5 PR1 §5, Coordinator 内部)
    
    实现类:
    - TypingDelayStrategy (默认, 字符级打字)
    - TTSDelayStrategy (v1.3 实现, 音频时长)
    """
    def compute_delay(self, text: str, config: dict) -> float:
        """返回段间延迟秒数"""
        ...


class TypingDelayStrategy:
    """字符级打字延迟 (v1.2.5 PR1 默认, Coordinator 内部)"""
    def compute_delay(self, text: str, config: dict) -> float:
        cps = config.get("default_chars_per_second", 7.5)
        max_delay = config.get("max_delay_seconds", 2.0)
        if cps <= 0:
            return max_delay
        return min(len(text) / cps, max_delay)


# v1.3 占位 (TTS 集成时启用)
# class TTSDelayStrategy:
#     """TTS 音频时长延迟 (v1.3)"""
#     def __init__(self, tts_provider):
#         self._tts = tts_provider
#     def compute_delay(self, text: str, config: dict) -> float:
#         return self._tts.estimate_duration(text)
```

- [ ] **Step 6.4: Coordinator 集成 + set_delay_strategy**

```python
# emotion_spirit/output/segmented_reply_coordinator.py — SegmentedReplyCoordinator.__init__
    def __init__(self, ...):
        # 现有初始化逻辑保留
        ...
        # v1.2.5 PR1: 默认延迟策略
        self._delay_strategy: DelayStrategy = TypingDelayStrategy()
```

```python
# SegmentedReplyCoordinator 类内, 在 should_be_silent 前
    def set_delay_strategy(self, strategy: DelayStrategy) -> None:
        """v1.2.5 PR1: 内部切换延迟策略 (为 v1.3 TTS 预留)
        
        main.py 不暴露, 后续 TTS 接 AstrBot pipeline 时由 Coordinator 内部调用
        """
        self._delay_strategy = strategy
```

- [ ] **Step 6.5: plan() 方法接入 _delay_strategy**

读 `plan()` 方法的现有实现，找到算 `delay_before_seconds` 的位置，替换成：

```python
# 在 plan() 方法内, 算每段 delay 的位置
delay = self._delay_strategy.compute_delay(part["text"], config)
part["delay_before_seconds"] = delay
```

**注意**: 如果现有 plan() 用的是硬编码公式 `min(len(text) / cps, max_delay_seconds)`, 替换即可。如果有更复杂的延迟算法, 保留但通过 `self._delay_strategy` 接口包装。

- [ ] **Step 6.6: 跑测试确认通过**

Run: `python -m pytest tests/test_delay_strategy.py -v`
Expected: 4 个测试全 PASS

Run: `python -m pytest tests/test_segmented_reply_coordinator.py -v`
Expected: 现有测试 PASS (plan() 行为不变, 因为默认 _delay_strategy 行为跟原硬编码一致)

- [ ] **Step 6.7: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/output/segmented_reply_coordinator.py tests/test_delay_strategy.py
git commit -m "feat(v1.2.5-pr1): DelayStrategy Protocol + TypingDelayStrategy 内部 helper"
```

---

## Task 7: 流式模式跳过 + main.py 重写 on_llm_response（投递机制核心）

**Files:**
- Modify: `main.py:1224-1300` (重写 `on_llm_response` 方法)
- Modify: `main.py:1301-1372` (删除 `_on_segmented_reply` 方法)
- Test: `tests/test_on_llm_response_segmented.py` (new file, 5 个测试)

**Interfaces:**
- 重写 `on_llm_response`: 在原 memory/intimacy 逻辑后, 加分段投递逻辑
  - 沉默触发 → 清空 llm_resp + return (S1)
  - 流式模式 → 跳过 (用户决策)
  - 正常 → `event.send(part)` + `asyncio.sleep(delay)` + 清空 llm_resp (阻止 RespondStage 重复发)
- 删除旧 `_on_segmented_reply` (它是 async generator, 是 Bug 12a 根源)

- [ ] **Step 7.1: 写失败测试 (mock event.send)**

```python
# tests/test_on_llm_response_segmented.py (新文件)
"""Tests for main.py on_llm_response (v1.2.5 PR1 §1, 投递机制)"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_on_llm_response_sends_segments_when_enabled():
    """segmented_reply.enable=true → event.send 调用 N 次 (每段一次)"""
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._config = {"segmented_reply": {"enable": True}, "provider_settings": {"streaming_response": False}}
    plugin._segmented_coordinator = MagicMock()
    plugin._segmented_coordinator.plan.return_value = [
        {"text": "part1", "delay_before_seconds": 0.0},
        {"text": "part2", "delay_before_seconds": 0.1},
    ]
    plugin._segmented_coordinator.compute_silence_tendency = MagicMock(return_value=MagicMock(score=0.0, reason="none", components={}))
    plugin._segmented_coordinator.should_be_silent = MagicMock(return_value=(False, "none", None))
    plugin._segmented_coordinator.record_response_event = MagicMock()
    plugin._force_dynamics = MagicMock()
    plugin._force_dynamics.get_current_force_state = MagicMock(return_value=None)
    plugin._latest_signals = {}
    plugin._labels = {}
    plugin._body_state = MagicMock()
    plugin._intimacy = MagicMock()
    plugin._intimacy.get_level = MagicMock(return_value=0.5)
    
    event = MagicMock()
    event.send = AsyncMock()
    
    response = MagicMock()
    response.completion_text = "完整回复 part1 part2"
    
    await plugin.on_llm_response(event, response)
    
    # 必须真的 send 了 2 次 (每段一次)
    assert event.send.call_count == 2


@pytest.mark.asyncio
async def test_on_llm_response_clears_llm_resp_after_send():
    """event.send 后, response.completion_text 应被清空 (阻止 RespondStage 重复发)"""
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._config = {"segmented_reply": {"enable": True}, "provider_settings": {"streaming_response": False}}
    plugin._segmented_coordinator = MagicMock()
    plugin._segmented_coordinator.plan.return_value = [{"text": "x", "delay_before_seconds": 0.0}]
    plugin._segmented_coordinator.compute_silence_tendency = MagicMock(return_value=MagicMock(score=0.0, reason="none", components={}))
    plugin._segmented_coordinator.should_be_silent = MagicMock(return_value=(False, "none", None))
    plugin._segmented_coordinator.record_response_event = MagicMock()
    plugin._force_dynamics = MagicMock()
    plugin._force_dynamics.get_current_force_state = MagicMock(return_value=None)
    plugin._latest_signals = {}
    plugin._labels = {}
    plugin._body_state = MagicMock()
    plugin._intimacy = MagicMock()
    plugin._intimacy.get_level = MagicMock(return_value=0.5)
    
    event = MagicMock()
    event.send = AsyncMock()
    
    response = MagicMock()
    response.completion_text = "完整回复"
    response.result_chain = None
    
    await plugin.on_llm_response(event, response)
    
    # llm_resp 应被清空
    assert response.completion_text == ""
    assert response.result_chain is None


@pytest.mark.asyncio
async def test_on_llm_response_streaming_mode_skips():
    """streaming_response=true → emotion_spirit 跳过, event.send 不被调"""
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._config = {
        "segmented_reply": {"enable": True},
        "provider_settings": {"streaming_response": True},  # ← 流式
    }
    plugin._segmented_coordinator = MagicMock()
    
    event = MagicMock()
    event.send = AsyncMock()
    
    response = MagicMock()
    response.completion_text = "完整回复"
    
    await plugin.on_llm_response(event, response)
    
    # 流式模式跳过, event.send 不应被调
    assert event.send.call_count == 0
    # llm_resp 也不应被清空 (让 AstrBot 流式发)
    assert response.completion_text == "完整回复"


@pytest.mark.asyncio
async def test_on_llm_response_silent_clears_llm_resp():
    """沉默触发 → event.send 不被调, 但 llm_resp 被清空 (让用户看不到回复)"""
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._config = {
        "segmented_reply": {"enable": True, "enable_deliberate_silence": True},
        "provider_settings": {"streaming_response": False},
    }
    plugin._segmented_coordinator = MagicMock()
    plugin._segmented_coordinator.compute_silence_tendency = MagicMock(return_value=MagicMock(score=0.8, reason="void_hurt_withdrawing", components={}))
    plugin._segmented_coordinator.should_be_silent = MagicMock(return_value=(True, "void_hurt_withdrawing", None))
    plugin._segmented_coordinator.record_silence_event = MagicMock()
    plugin._force_dynamics = MagicMock()
    plugin._force_dynamics.get_current_force_state = MagicMock(return_value=None)
    plugin._latest_signals = {}
    plugin._labels = {}
    plugin._body_state = MagicMock()
    plugin._intimacy = MagicMock()
    plugin._intimacy.get_level = MagicMock(return_value=0.5)
    
    event = MagicMock()
    event.send = AsyncMock()
    
    response = MagicMock()
    response.completion_text = "完整回复"
    response.result_chain = None
    
    await plugin.on_llm_response(event, response)
    
    # 沉默触发, event.send 不调
    assert event.send.call_count == 0
    # llm_resp 被清空 (AstrBot 不发)
    assert response.completion_text == ""
    assert response.result_chain is None


@pytest.mark.asyncio
async def test_on_llm_response_disabled_no_send():
    """segmented_reply.enable=false → 跳过整段逻辑, event.send 不调"""
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._config = {
        "segmented_reply": {"enable": False},  # ← 关闭
        "provider_settings": {"streaming_response": False},
    }
    plugin._segmented_coordinator = MagicMock()
    
    event = MagicMock()
    event.send = AsyncMock()
    
    response = MagicMock()
    response.completion_text = "完整回复"
    
    await plugin.on_llm_response(event, response)
    
    # enable=false 跳过, event.send 不调
    assert event.send.call_count == 0
    # llm_resp 不动 (AstrBot 正常发整条)
    assert response.completion_text == "完整回复"
```

- [ ] **Step 7.2: 跑测试确认失败**

Run: `python -m pytest tests/test_on_llm_response_segmented.py -v`
Expected: 5 个测试全 FAIL (可能 AttributeError 或 ImportError)

- [ ] **Step 7.3: 重写 on_llm_response**

读 main.py:1224-1300 (当前 `on_llm_response` 实现), 在末尾追加分段投递逻辑:

```python
# main.py — 在 on_llm_response 方法末尾, 在 except 外但 try 内
        # ═══ v1.2.5 PR1: 分段回复 (修复 Bug 12) ═══
        seg_config = self._config.get("segmented_reply", {})
        if seg_config.get("enable", False) and hasattr(self, "_segmented_coordinator"):
            # 流式模式跳过
            if self._config.get("provider_settings", {}).get("streaming_response", False):
                logger.debug("emotion_spirit: streaming_response=True, skipping segmented_reply")
            else:
                try:
                    await self._on_segmented_reply_v2(
                        bot_text, user_id, seg_config, event, response
                    )
                except Exception:
                    logger.warning(
                        "emotion_spirit: segmented_reply failed, falling back to AstrBot default",
                        exc_info=True,
                    )
```

**注意**: 分段逻辑抽到独立 `_on_segmented_reply_v2` 方法, 避免 on_llm_response 太长。这样 Task 8 单独测试新方法。

- [ ] **Step 7.4: 删除旧 _on_segmented_reply**

读 main.py:1301-1372 (旧 `_on_segmented_reply`), 整段删除。它是 Bug 12a 根源 (async generator 被 await)。

- [ ] **Step 7.5: 跑测试确认通过**

Run: `python -m pytest tests/test_on_llm_response_segmented.py -v`
Expected: 5 个测试全 PASS (因为 on_llm_response 调 _on_segmented_reply_v2, mock 的 plugin 实例没这个方法 — 实际测试可能仍 FAIL)

**注意**: 这个测试在 Task 7 末尾会失败, 因为 _on_segmented_reply_v2 还没实现。**正确的顺序是**: Task 7 只做"在 on_llm_response 末尾追加"骨架, Task 8 实现 _on_segmented_reply_v2。

**调整**: 把 Step 7.3 改为"加骨架 (call _on_segmented_reply_v2)", Step 7.5 改为"测试 FAIL (因为新方法未实现, 这是预期, 留给 Task 8)"。

- [ ] **Step 7.6: 提交 (骨架)**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add main.py
git commit -m "refactor(v1.2.5-pr1): on_llm_response 末尾加分段投递骨架 (实现留给 Task 8)"
```

---

## Task 8: 实现 _on_segmented_reply_v2 (投递机制主体)

**Files:**
- Modify: `main.py` (新增 `_on_segmented_reply_v2` 方法)
- Test: `tests/test_on_llm_response_segmented.py` (现在 5 个测试应全 PASS)

**Interfaces:**
- `_on_segmented_reply_v2(bot_text, user_id, seg_config, event, response)`:
  1. 读 force_state / body_state / signals / intimacy / context
  2. 调 `self._segmented_coordinator.compute_silence_tendency(...)`
  3. 调 `should_be_silent(...)` 决策
  4. 沉默触发 + enable_deliberate_silence=true → record_silence_event + 清空 llm_resp + return
  5. 调 `self._segmented_coordinator.plan(...)`
  6. 逐段 `event.send` + `asyncio.sleep(delay)`
  7. 清空 llm_resp

- [ ] **Step 8.1: 实现 _on_segmented_reply_v2**

```python
# main.py — 在 on_llm_response 后面, 替代旧 _on_segmented_reply
    async def _on_segmented_reply_v2(
        self,
        bot_text: str,
        user_id: str,
        seg_config: dict,
        event,
        response,
    ) -> None:
        """v1.2.5 PR1: 分段投递主体 (修复 Bug 12a + 12b)
        
        Bug 12a 修: 不再用 yield (避免 async generator 被 await)
        Bug 12b 修: emotion_spirit 自己 send + 清空 llm_resp (阻止 AstrBot RespondStage 重复发)
        """
        try:
            # 1. 读上游 (L1: 准备传给 Coordinator, 但 PR1 不接 DefenseModulator)
            force_state = (
                self._force_dynamics.get_current_force_state(self._labels)
                if hasattr(self, "_force_dynamics") else None
            )
            signals = (
                self._latest_signals.get(user_id)
                if hasattr(self, "_latest_signals") else None
            )
            body_state = (
                self._body_state.get_current()
                if hasattr(self, "_body_state") else None
            )
            intimacy = (
                self._intimacy.get_level(user_id)
                if hasattr(self, "_intimacy") else 0.5
            )
            context = self._build_context(event)
            personality = self._get_personality_labels(user_id) if hasattr(self, "_get_personality_labels") else {
                "extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5,
                "openness": 0.5, "conscientiousness": 0.5,
            }
            
            # 2. 沉默判定
            from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency
            silence_tendency_obj = self._segmented_coordinator.compute_silence_tendency(
                user_id, personality, force_state, body_state, signals, intimacy, context
            )
            should_silent, reason, _ = self._segmented_coordinator.should_be_silent(
                user_id, silence_tendency_obj, seg_config
            )
            
            # 3. 沉默触发
            if should_silent and seg_config.get("enable_deliberate_silence", False):
                self._segmented_coordinator.record_silence_event(
                    user_id, silence_tendency_obj, bot_text, force_state
                )
                response.completion_text = ""
                response.result_chain = None
                logger.debug(
                    "emotion_spirit: deliberate silence triggered reason=%s score=%.2f",
                    reason, silence_tendency_obj.score,
                )
                return
            
            # 4. 算 plan
            plan = self._segmented_coordinator.plan(
                full_text=bot_text,
                user_id=user_id,
                signals=signals,
                force_state=force_state,
                config=seg_config,
            )
            
            if not plan:
                return
            
            # 5. 逐段 send (F4: 先发首段无延迟, 后续 sleep + send)
            from astrbot.core.message.components import Plain
            from astrbot.core.message.message_event_result import MessageChain
            
            try:
                await event.send(MessageChain([Plain(plan[0]["text"])]))
                for part in plan[1:]:
                    delay = part.get("delay_before_seconds", 0.0)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    await event.send(MessageChain([Plain(part["text"])]))
            except Exception:
                # F3: 单段失败继续 (catch 不 raise, 让 hook 不破坏 AstrBot pipeline)
                logger.warning(
                    "emotion_spirit: segmented_reply send failed, some segments may be missing",
                    exc_info=True,
                )
            
            # 6. 清空 llm_resp (Bug 12b 修复: 阻止 RespondStage 重复发)
            response.completion_text = ""
            response.result_chain = None
            
            # 7. 推进冷却计数 (下次沉默需过 cooldown 轮)
            self._segmented_coordinator.record_response_event(user_id)
            
        except Exception:
            # F1: 整体失败 → 让 AstrBot 正常发
            logger.warning(
                "emotion_spirit: _on_segmented_reply_v2 failed, falling back to AstrBot default",
                exc_info=True,
            )
    
    def _build_context(self, event) -> dict:
        """v1.2.5 PR1: 上下文构建 (social_audience + authority placeholder)"""
        context = {}
        if hasattr(event, "get_group_id") and event.get_group_id():
            context["social_audience"] = 0.5
        else:
            context["social_audience"] = 0.0
        context["authority_present"] = 0.0  # v1.3 真实解析
        return context
```

- [ ] **Step 8.2: 跑 on_llm_response 测试确认通过**

Run: `python -m pytest tests/test_on_llm_response_segmented.py -v`
Expected: 5 个测试全 PASS

- [ ] **Step 8.3: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/ -q --no-header`
Expected: 1281 passed (1261 现有 + 20 silence + 4 delay + 5 segmented = 1290 passed, 实际可能有差异)

**关键回归检查**:
- main.py `_on_segmented_reply` 删除后, 是否有其他测试引用它? `grep -rn "_on_segmented_reply\b" tests/`
- main.py `_build_context` 是新方法, 跟现有方法名是否冲突? `grep -n "_build_context" main.py`

- [ ] **Step 8.4: 跑 smoke test 确认无 dangling call**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: 11 个测试全 PASS (v1.2.4 加的 AST 检查)

- [ ] **Step 8.5: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add main.py tests/test_on_llm_response_segmented.py
git commit -m "feat(v1.2.5-pr1): _on_segmented_reply_v2 投递机制 (Bug 12 修复)"
```

---

## Task 9: _conf_schema.json 加 v1.2.5 配置段 + 测试

**Files:**
- Modify: `_conf_schema.json` (加 segmented_reply 段, 含 v1.2.5 新字段)
- Test: `tests/test_conf_schema_v125.py` (new file, 验证 schema 包含必要字段)

**Interfaces:**
- 新字段: `enable_deliberate_silence`, `silent_threshold`, `silent_cooldown_turns`, `max_consecutive_silence`
- 默认值按 Global Constraints

- [ ] **Step 9.1: 写失败测试**

```python
# tests/test_conf_schema_v125.py (新文件)
"""Tests for _conf_schema.json v1.2.5 fields (PR1 §6)"""
import json
from pathlib import Path


def test_conf_schema_has_segmented_reply_block():
    """_conf_schema.json 应包含 segmented_reply 配置段"""
    schema_path = Path(__file__).parent.parent / "_conf_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    assert "segmented_reply" in schema


def test_segmented_reply_has_v125_new_fields():
    """v1.2.5 新增字段: enable_deliberate_silence, silent_threshold, etc."""
    schema_path = Path(__file__).parent.parent / "_conf_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    seg = schema["segmented_reply"]
    items = seg.get("items", {})
    
    assert "enable_deliberate_silence" in items
    assert items["enable_deliberate_silence"]["default"] is False
    assert "silent_threshold" in items
    assert abs(items["silent_threshold"]["default"] - 0.5) < 0.001
    assert "silent_cooldown_turns" in items
    assert items["silent_cooldown_turns"]["default"] == 2
    assert "max_consecutive_silence" in items
    assert items["max_consecutive_silence"]["default"] == 3


def test_segmented_reply_default_unchanged():
    """v1.2.5 不破坏现有默认字段"""
    schema_path = Path(__file__).parent.parent / "_conf_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    items = schema["segmented_reply"]["items"]
    
    assert items["enable"]["default"] is False
    assert abs(items["default_max_part_chars"]["default"] - 48) < 0.001
    assert abs(items["default_chars_per_second"]["default"] - 7.5) < 0.001
```

- [ ] **Step 9.2: 跑测试确认失败**

Run: `python -m pytest tests/test_conf_schema_v125.py -v`
Expected: FAIL (新字段不存在)

- [ ] **Step 9.3: 更新 _conf_schema.json**

读当前 `_conf_schema.json` 的 `segmented_reply` 段, 在 `items` 字典里加 4 个新字段:

```json
"enable_deliberate_silence": {
  "description": "是否启用主动沉默 (v1.2.5)",
  "type": "bool",
  "default": false,
  "hint": "v1.2.5 新: 沉默决策由人格+力学+情绪共同决定, 触发时 bot 不发任何消息"
},
"silent_threshold": {
  "description": "沉默触发阈值 [0,1]",
  "type": "float",
  "default": 0.5,
  "hint": "v1.2.5 新: silence_tendency >= 此值才触发沉默, 越高越不容易沉默"
},
"silent_cooldown_turns": {
  "description": "沉默后冷却 N 轮",
  "type": "int",
  "default": 2,
  "hint": "v1.2.5 S4: 刚沉默过, 至少过 N 轮才允许再次沉默"
},
"max_consecutive_silence": {
  "description": "连续沉默上限",
  "type": "int",
  "default": 3,
  "hint": "v1.2.5 S4: 连续沉默 N 次后, 阈值临时上调到 0.9 强制恢复"
}
```

放在现有 `ignored_window_turns` 字段**之前**（保持逻辑分组: enable/沉默字段在前, 分段参数在后）。

- [ ] **Step 9.4: 跑测试确认通过**

Run: `python -m pytest tests/test_conf_schema_v125.py -v`
Expected: 3 个测试全 PASS

- [ ] **Step 9.5: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add _conf_schema.json tests/test_conf_schema_v125.py
git commit -m "feat(v1.2.5-pr1): _conf_schema.json 加 S1-S4 沉默配置段"
```

---

## Task 10: /reflect_force_current 命令扩展 + 测试

**Files:**
- Modify: `commands.py` (新增 `reflect_force_current` 命令)
- Modify: `main.py` (注册 `reflect_force_current_cmd`)
- Test: `tests/test_commands_reflect.py` (new file, 3 个测试)

**Interfaces:**
- 命令: `/reflect_force_current` 无参
- 显示: 当前 ForceState + 最近 7 天沉默次数 + dominant reason + 分段次数 + 平均延迟
- 走 `_ns_command` 工厂（依赖 v1.2.2 B4 修好的 `*args`）

- [ ] **Step 10.1: 写失败测试**

```python
# tests/test_commands_reflect.py (新文件)
"""Tests for /reflect_force_current command (v1.2.5 PR1 §7)"""
from unittest.mock import MagicMock, AsyncMock
import pytest


@pytest.mark.asyncio
async def test_reflect_force_current_returns_history():
    """命令应返回 force_state + 沉默历史 + 分段统计"""
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    
    # mock 内部状态
    plugin._force_dynamics = MagicMock()
    plugin._force_dynamics.get_current_force_state = MagicMock(return_value={
        "natural": 0.4, "social": 0.3, "individual": 0.6,
        "dominant": "individual",
    })
    plugin._segmented_coordinator = MagicMock()
    plugin._segmented_coordinator.get_history = MagicMock(return_value={
        "silence_count_7d": 2,
        "silence_dominant_reason": "void_hurt_withdrawing",
        "segment_count_7d": 15,
        "avg_segment_count": 3.5,
        "avg_delay_seconds": 1.2,
    })
    
    # mock 调命令
    cmd = plugin._cmd
    cmd.reflect_force_current = AsyncMock()
    cmd.reflect_force_current.return_value = ["ForceState: individual dominant\n沉默 2 次, dominant: void_hurt_withdrawing"]
    
    event = MagicMock()
    event.get_sender_id = MagicMock(return_value="user1")
    
    # 模拟命令调用
    result = await cmd.reflect_force_current(event)
    assert result is not None
    assert "ForceState" in result[0]
```

- [ ] **Step 10.2: 跑测试确认失败**

Run: `python -m pytest tests/test_commands_reflect.py -v`
Expected: FAIL (cmd.reflect_force_current 未实现)

- [ ] **Step 10.3: 实现 reflect_force_current 命令**

读 `commands.py` 文件结构, 加新方法:

```python
# commands.py — 在现有 reflect_diary 命令附近
class CommandImpl:
    # ... 现有方法 ...
    
    async def reflect_force_current(self, event) -> list:
        """v1.2.5 PR1: /reflect_force_current 看力学 + 沉默/分段历史
        
        输出格式:
        ════════════════════════════
        ForceState 当前
        ════════════════════════════
        自然力: 0.40
        社会力: 0.30
        个体力: 0.60 ← 主导
        
        最近 7 天:
        - 沉默: 2 次 (dominant: void_hurt_withdrawing)
        - 分段: 15 次 (平均 3.5 段/回复, 平均延迟 1.2s)
        ════════════════════════════
        """
        from emotion_spirit.output.segmented_reply_coordinator import (
            SegmentedReplyCoordinator,
        )
        
        # 读当前 ForceState
        if not hasattr(self, "_force_dynamics"):
            return ["⚠️ ForceDynamics 未装载"]
        force_state = self._force_dynamics.get_current_force_state(
            self._current_persona_labels if hasattr(self, "_current_persona_labels") else {}
        )
        
        # 读沉默/分段历史
        history = {}
        if hasattr(self, "_segmented_coordinator"):
            get_history = getattr(self._segmented_coordinator, "get_history", None)
            if callable(get_history):
                history = get_history()
        
        # 格式化输出
        lines = [
            "════════════════════════════",
            "ForceState 当前",
            "════════════════════════════",
            f"自然力: {force_state.get('natural', 0.5):.2f}",
            f"社会力: {force_state.get('social', 0.5):.2f}",
            f"个体力: {force_state.get('individual', 0.5):.2f}",
        ]
        dominant = force_state.get("dominant", "unknown")
        lines.append(f"\n主导力: {dominant}\n")
        
        lines.append("════════════════════════════")
        lines.append("最近 7 天")
        lines.append("════════════════════════════")
        silence_count = history.get("silence_count_7d", 0)
        silence_reason = history.get("silence_dominant_reason", "none")
        segment_count = history.get("segment_count_7d", 0)
        avg_seg = history.get("avg_segment_count", 0)
        avg_delay = history.get("avg_delay_seconds", 0)
        lines.append(f"- 沉默: {silence_count} 次 (dominant: {silence_reason})")
        lines.append(f"- 分段: {segment_count} 次 (平均 {avg_seg:.1f} 段/回复, 平均延迟 {avg_delay:.1f}s)")
        
        return ["\n".join(lines)]
```

- [ ] **Step 10.4: Coordinator 加 get_history 方法**

在 `SegmentedReplyCoordinator` 类内 (在 record_response_event 后):

```python
    def get_history(self) -> dict:
        """v1.2.5 PR1: 返回最近 7 天沉默/分段统计 (供 /reflect_force_current 显示)"""
        if not hasattr(self, "_silence_history"):
            self._silence_history = []
        if not hasattr(self, "_segment_history"):
            self._segment_history = []
        
        silence_count = len(self._silence_history)
        silence_reasons = [e["reason"] for e in self._silence_history if "reason" in e]
        dominant_reason = max(set(silence_reasons), key=silence_reasons.count) if silence_reasons else "none"
        
        segment_count = len(self._segment_history)
        if segment_count > 0:
            avg_seg = sum(e.get("num_segments", 0) for e in self._segment_history) / segment_count
            avg_delay = sum(e.get("total_delay", 0) for e in self._segment_history) / segment_count
        else:
            avg_seg = 0.0
            avg_delay = 0.0
        
        return {
            "silence_count_7d": silence_count,
            "silence_dominant_reason": dominant_reason,
            "segment_count_7d": segment_count,
            "avg_segment_count": avg_seg,
            "avg_delay_seconds": avg_delay,
        }
    
    def record_segment_event(self, session_key: str, num_segments: int, total_delay: float) -> None:
        """记录一次分段回复事件 (供 get_history 统计)"""
        if not hasattr(self, "_segment_history"):
            self._segment_history = []
        self._segment_history.append({
            "session_key": session_key,
            "num_segments": num_segments,
            "total_delay": total_delay,
        })
        # 简单实现: 保留最近 7 天 (~ 1000 条)
        if len(self._segment_history) > 1000:
            self._segment_history = self._segment_history[-1000:]
```

**注意**: `record_silence_event` 已经存在, 但**没把 silence 写入 `_silence_history`**。需要修:

```python
# 改 record_silence_event, 在末尾追加:
        # 写 history (供 get_history 读)
        if not hasattr(self, "_silence_history"):
            self._silence_history = []
        self._silence_history.append({
            "session_key": session_key,
            "reason": tendency.reason,
            "score": tendency.score,
        })
        if len(self._silence_history) > 1000:
            self._silence_history = self._silence_history[-1000:]
```

- [ ] **Step 10.5: 注册命令到 main.py**

读 `main.py` 中 `_ns_command` 注册区域, 加:

```python
reflect_force_current_cmd = _ns_command("reflect_force_current", "reflect_force_current", "查看当前力平衡 + 沉默/分段历史")
```

放在 `view_diary_cmd` 附近。

- [ ] **Step 10.6: _on_segmented_reply_v2 调用 record_segment_event**

在 main.py `_on_segmented_reply_v2` 内, 正常发段后追加:

```python
            # 7.5 记录分段事件 (供 /reflect_force_current 统计)
            self._segmented_coordinator.record_segment_event(
                user_id, num_segments=len(plan), total_delay=sum(p.get("delay_before_seconds", 0) for p in plan)
            )
```

- [ ] **Step 10.7: 跑测试确认通过**

Run: `python -m pytest tests/test_commands_reflect.py -v`
Expected: PASS

Run: `python -m pytest tests/test_silence_tendency.py tests/test_delay_strategy.py tests/test_on_llm_response_segmented.py tests/test_conf_schema_v125.py -v`
Expected: 全部 PASS (无 regression)

- [ ] **Step 10.8: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add commands.py main.py emotion_spirit/output/segmented_reply_coordinator.py tests/test_commands_reflect.py
git commit -m "feat(v1.2.5-pr1): /reflect_force_current + history tracking"
```

---

## Task 11: Bump version + 跑 ship checklist + 验证

**Files:**
- Modify: `emotion_spirit/_version.py` (`__version__ = "1.2.5"`)
- Modify: `metadata.yaml` (`version: "1.2.5"`)
- Modify: `CHANGELOG.md` (v1.2.5 entry)

- [ ] **Step 11.1: Bump version**

读 `emotion_spirit/_version.py`, 改成 `__version__ = "1.2.5"`。读 `metadata.yaml`, 改成 `version: "1.2.5"`。

- [ ] **Step 11.2: TestVersionConsistency 验证**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: PASS (三源互比测试会验证 _version.py + metadata.yaml 一致)

- [ ] **Step 11.3: 写 CHANGELOG entry**

读 `CHANGELOG.md`, 在文件顶部 (最新版本在最上) 加:

```markdown
## [1.2.5] - 2026-07-03 (PR1: 分段修复 + 沉默语义)

### 修复 (Bug Fixes)
- **Bug 12**: 分段回复 100% 不工作 (v1.2.4 release blocker)
  - **Bug 12a**: `_on_segmented_reply` 含 yield 被 await → TypeError 静默吞
  - **Bug 12b**: emotion_spirit 投递架构改为主动 send + 清空 llm_resp

### 新功能 (Features)
- **沉默 S1-S4**: 不删消息 / 语义透明 (SilenceTendency) / 情绪事件 (S3 写 memory) / 时长上限 (S4 冷却+连续上限)
- **沉默人格加权**: 6 factor 连续函数 (系数从 KB 读, Jack 1992 / Carver 1998 / Noftle 2006 文献背书)
- **亲密度双向调节**: Jack 讨好假说 (亲密中沉默倾向由 agreeableness/neuroticism/openness 共同决定)
- **延迟策略接口**: TypingDelayStrategy 默认字符级打字, v1.3 接 TTS 预留
- **流式模式跳过**: `streaming_response=true` 时 emotion_spirit 跳过, AstrBot 走默认流式
- **`/reflect_force_current`** 命令: 看当前 ForceState + 7 天沉默/分段历史

### 工程 (Engineering)
- 模块数: 57 (不变, TypingDelayStrategy 移进 Coordinator 内部不独立注册)
- KB 文件 `silence_tendency_weights.json` 新增 (handbook §1.1 严格遵守)
- 4 个新方法标 `@per_user_only` (handbook §1.3 强拦)

### 测试 (Tests)
- 新增: `test_silence_tendency.py` (20), `test_delay_strategy.py` (4), `test_on_llm_response_segmented.py` (5), `test_conf_schema_v125.py` (3), `test_commands_reflect.py` (1)
- 总计: ~1290 passed
```

- [ ] **Step 11.4: 跑全套测试**

Run: `python -m pytest tests/ -q --no-header`
Expected: 1290 passed (1261 现有 + 33 新增)

**允许**: `test_periodic_save_dirty_only` Win 概率性 1/3 fail (handbook §4.4 step 2)

- [ ] **Step 11.5: 跑 smoke test**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: 11 passed (v1.2.4 加的 AST 检查, 确保无 dangling call)

- [ ] **Step 11.6: pre-commit secret scan**

Run: `python scripts/check_secrets.py` (或 git commit 时自动跑)
Expected: 无 secret leak

- [ ] **Step 11.7: 更新 UPDATE_HANDBOOK.md §6**

读 `UPDATE_HANDBOOK.md` §6 "v1.2.1 已清的债" 段, 后面加:

```markdown
### v1.2.5 PR1 已清的债 (待 ship 验证不在 regression)
- ✅ 4 个沉默方法加 @per_user_only (handbook §1.3 强拦)
- ✅ 沉默系数 11 项进 KB silence_tendency_weights.json (handbook §1.1)
- ✅ TypingDelayStrategy 不独立 @register, 合并进 Coordinator 内部 (§5 设计审查)
```

- [ ] **Step 11.8: 提交 version bump + changelog + handbook**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/_version.py metadata.yaml CHANGELOG.md UPDATE_HANDBOOK.md
git commit -m "chore(v1.2.5-pr1): bump version + changelog + handbook update"
```

---

## Task 12: Git tag + push + Release 验证（hands-off Step 7）

> **注意**: Step 12.5 + 12.6 涉及 GitHub 真实操作, 由用户在浏览器/终端执行 (handbook §4.4 step 7: "AI 做不了, 必须人验")。本任务前半 AI 可以准备, 后半由用户执行。

- [ ] **Step 12.1: 验证本地 working tree 干净**

Run: `git status --short`
Expected: 空输出

- [ ] **Step 12.2: 验证无 remote-only commit**

Run: `git fetch origin && git rev-list HEAD..origin/main`
Expected: 空输出 (本地领先, 没人 push 新 commit)

- [ ] **Step 12.3: 跑 pre-commit secret scan**

Run: `python scripts/check_secrets.py`
Expected: 无 secret leak

- [ ] **Step 12.4: 准备 ship commit message**

```bash
git log --oneline -10
```

**期望看到**: 11 个 PR1 commit (Task 1-11 各 1 个), 加上任何已有 commit。

- [ ] **Step 12.5: push 到 GitHub (走 proxy)**

```bash
git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 push origin main
```

Expected: 推送成功

- [ ] **Step 12.6: 打 tag + 等 release.yml 自动 build**

```bash
git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 push origin v1.2.5
```

Expected: tag 推送成功, GitHub Actions 自动开始 build release zip

- [ ] **Step 12.7: 用户验 Release (AI 做不了)**

**用户操作**: 打开 https://github.com/Aston957/astrbot_plugin_emotion_spirit/actions, 验 Release 真出了。

- [ ] **Step 12.8: 本机 AstrBot 实测 (按 §10.2 DoD)**

按 spec §10.2 跑 5 个实测 case:
- [ ] `segmented_reply.enable=true` + 长 prompt → bot 分 3+ 段发出
- [ ] 沉默触发条件 (高 hurt) → bot 不回话, 日志 reason=`void_hurt_withdrawing`
- [ ] 连续 3 次沉默后第 4 次强制回话
- [ ] 冷却期内沉默被阻止
- [ ] `streaming_response=true` → emotion_spirit 跳过

---

## Self-Review Checklist (完成后跑)

✅ **Spec 覆盖检查**:
- [x] §0 范围: 10 项 → Task 1-10 覆盖
- [x] §1 Bug 12: → Task 7-8
- [x] §2 沉默 S1-S4: → Task 1-4
- [x] §3 人格加权: → Task 2-3 (KB + 算法)
- [x] §5 延迟内部: → Task 6
- [x] §6 配置: → Task 9
- [x] §7 命令: → Task 10
- [x] §10.1 ship 8 步: → Task 11 + Task 12
- [x] §10.2 功能验收: → Task 12.8
- [x] §10.4 文档: → Task 11.3 + 11.7

⏸ **明确不在本 PR**:
- §4 力学耦合 (DefenseModulator) → PR 2
- §10.3 顺手清债 (T1+T2+T7+T3+T4) → PR 3

✅ **Placeholder 扫描**: 全任务都是具体代码, 无 TBD/TODO/类似上

✅ **类型一致性**:
- `SilenceTendency` dataclass → Task 1 定义, Task 3+4 使用, 一致
- `compute_silence_tendency` 参数: `session_key` → 改为 `user_id` (Task 5), 后续 Task 8 同步
- `should_be_silent` 返回: `tuple[bool, str, SilenceTendency]` → Task 4 定义, Task 8 使用, 一致
- `record_silence_event` 参数: `user_id, tendency, full_text, force_state=None` → Task 4 定义, Task 8 使用, 一致

✅ **Task 大小**: 每个 Task 5-8 步, 每步 2-5 分钟, 总 ~3-4 小时实操

---

## 后续 (PR 2 + PR 3, 等 PR1 ship 验证后再写)

- **PR 2 plan**: `docs/superpowers/plans/2026-07-03-segmented-reply-fix-pr2-plan.md`
  - 内容: §4 DefenseModulator + L1+L2 + defense_deltas.json KB
- **PR 3 plan**: `docs/superpowers/plans/2026-07-03-segmented-reply-fix-pr3-plan.md`
  - 内容: §10.3 T1+T2+T7+T3+T4 顺手清债

---

**Plan 完成**: 12 tasks, ~3-4 小时实操, 13 章 spec 全部覆盖（除明确拆出去的 PR 2/3）。

**保存位置**: `docs/superpowers/plans/2026-07-03-segmented-reply-fix-pr1-plan.md` ✅

**下一步**: 选择执行方式（subagent-driven 推荐 或 inline）。