# v1.3.0 rc.4: Bug-G 根因修复(set_personality 传全 13 维)+ 清理 Plan

> **日期**:2026-07-04
> **前置**:rc.3 实测(`2026-07-04-emotion-spirit-v130rc3-feedback.md`)—— Bug-H 真修 ✅ / Bug-F 落地 ✅ / **Bug-G 仍饱和** ⚠️。
> **Bug-G rc.3 仍饱和根因**(已核):`set_personality` 只传 `_baseline_personality.get("deep", {})`(5 维),但 KB `conscience_params.json` weights 引用 9 维(3 deep + **6 surface**)→ 6 个 surface 维度 `personality.get(dim, 0.5)` 全取 0.5 兜底 → 参数没真人格化 → 仍用接近 baseline 的 chronic_decay=0.08(慢)→ 饱和。
> **附带 bug**:`_decay_tick_loop`(main.py:1097)logger 打 `self._conscience._raw_pressure`,但 rc.2 删了 `_raw_pressure`(改 _acute+_chronic)→ 跑了 AttributeError(被 except 抓,用户实测"没有新 tick 日志"的来源)。
> **范围**:set_personality 传全 13 维(根因)+ 调 KB baseline + 清理 _decay_tick_loop + 诊断 log + 测试加强。commit 本地,**不 push**。
> **auto mode**:已开启,任意读写。

---

## 上下文

| Bug | rc.3 状态 | rc.4 处理 |
|---|---|---|
| Bug-G | ⚠️ 仍饱和(set_personality 传 deep 不全 + chronic_decay 0.08 太慢) | ✅ 根因修复:传全 13 维 + 调 baseline |
| _decay_tick_loop | 🟡 残留 + logger bug(引用已删的 _raw_pressure) | ✅ 清理(lazy decay 接管) |
| Bug-H | ✅ 真修 | 不动 |
| Bug-F | ✅ 落地(等 24h) | 不动 |

---

## 任务 1:set_personality 传全 13 维(根因修复)

**根因**:`get_personality_params` 返回 `{'deep': {5 维}, 'surface': {8 维}}`。main.py 只传 deep(5 维),KB weights 引用 9 维(含 6 个 surface 维度)→ surface 维度取 0.5 兜底 → 参数没人格化。

### 改动 1.1:main.py:493(初始化)set_personality 传 deep + surface 合并

**文件**:`main.py`(line 488-494 附近)

**现状**:
```python
if hasattr(self, "_conscience") and self._conscience is not None:
    deep_personality = self._baseline_personality.get("deep", {})
    if deep_personality:
        self._conscience.set_personality(deep_personality)
```

**改成**:
```python
if hasattr(self, "_conscience") and self._conscience is not None:
    # rc.4: 传全 13 维 (deep 5 + surface 8), 不是只传 deep.
    # KB conscience_params.json weights 引用 9 维 (3 deep + 6 surface),
    # 只传 deep 会让 surface 维度取 0.5 兜底 → 参数没人格化 (Bug-G rc.3 仍饱和根因).
    deep = self._baseline_personality.get("deep", {})
    surface = self._baseline_personality.get("surface", {})
    full_personality = {**deep, **surface}  # 13 维
    if full_personality:
        self._conscience.set_personality(full_personality)
        logger.info(
            "emotion_spirit: conscience set_personality dims=%d acute_decay=%.3f chronic_decay=%.3f threshold=%.3f",
            len(full_personality),
            self._conscience._acute_decay_rate_per_min,
            self._conscience._chronic_decay_rate_per_hour,
            self._conscience._collapse_threshold,
        )
```

**注意**:诊断 log 确认参数真覆盖(用户 §2.4 建议)。dims 应=13。若 dims<13 或参数=默认,说明 _baseline_personality 不全。

### 改动 1.2:main.py:798(relabel)set_personality 同样改

**文件**:`main.py`(line 793-799 附近)

**现状**:
```python
new_conscience = ConscienceTracker()
if hasattr(self, "_baseline_personality"):
    deep_personality = self._baseline_personality.get("deep", {})
    if deep_personality:
        new_conscience.set_personality(deep_personality)
self._conscience = new_conscience
```

**改成**:
```python
new_conscience = ConscienceTracker()
if hasattr(self, "_baseline_personality"):
    deep = self._baseline_personality.get("deep", {})
    surface = self._baseline_personality.get("surface", {})
    full_personality = {**deep, **surface}  # rc.4: 13 维
    if full_personality:
        new_conscience.set_personality(full_personality)
self._conscience = new_conscience
```

**注意**:relabel 时同样传全 13 维。诊断 log 可选(relabel 不频繁,加 log 可选)。

---

## 任务 2:调 KB baseline(默认参数不饱和)

**文件**:`emotion_spirit/core/kb/conscience_params.json`

rc.3 baseline 让 chronic 累积快(0.15/次)+ 衰减慢(0.08/hour)→ 3-4 次 → 0.6 → critical。调 baseline 让默认参数(无人格)+ 人格算出的参数都不饱和。

### 改动 2.1:chronic_decay_rate_per_hour baseline 0.08 → 0.20

```json
"chronic_decay_rate_per_hour": {
  "baseline": 0.20,
  "weights": { ... },
  "range": [0.05, 0.40]
}
```

**语义**:半衰期从 8.3h → 3.1h(慢性更快消散)。range 上限也调高(0.20→0.40)让人格能调出更快衰减。

### 改动 2.2:chronic_multiplier baseline 0.30 → 0.20

```json
"chronic_multiplier": {
  "baseline": 0.20,
  "weights": { ... },
  "range": [0.05, 0.60]
}
```

**语义**:慢性累积系数降(0.30→0.20),每次 conflict chronic += 0.5×0.20=0.10(原 0.15)→ 累积更慢。

### 改动 2.3:核对 weights 正负语义

**关键**:`chronic_decay_rate_per_hour` 的 weights 正负方向需核对。当前:
```json
"weights": {
  "inner_coherence": -0.04,   // inner_coherence 高 → decay 降 → 慢消散??
  "patience": -0.03,
  "exploration_openness": -0.02
}
```

**语义检查**:inner_coherence(内聚/韧性)高 → 该**快消散**(衰减率升,正权重)。当前是负权重(inner_coherence 高 → 衰减率降 → 慢消散)**方向反了**。

**改成**(正权重):
```json
"chronic_decay_rate_per_hour": {
  "baseline": 0.20,
  "weights": {
    "inner_coherence": 0.06,        // 韧性高 → 衰减快 (压力消散快)
    "patience": 0.04,               // 耐心高 → 衰减快
    "exploration_openness": 0.03
  },
  "range": [0.05, 0.40]
}
```

**同样核对其他参数 weights 正负**:
- `acute_decay_rate_per_min`:patience/inner_coherence 高 → 急性快恢复 → 衰减率升(正权重)。当前 patience=-0.05(反)→改正。
- `collapse_threshold`:inner_coherence/patience 高 → 阈值高(不易崩,正权重)。当前正,核对保持。
- `chronic_multiplier`:intimacy_pull 高 → 慢性累积快(正权重)。当前正,核对保持。
- `suppression_efficiency`:boundary_permeability 高 → 压抑效率低(负权重)。当前负,核对保持。

**小模型逐个核对 weights 正负**:`baseline + Σ(dim × weight)` 后,该维度高时参数该升还是降,跟语义对齐。

---

## 任务 3:清理 _decay_tick_loop(lazy decay 接管)

**文件**:`main.py`

rc.2 双通道重写后,`get_pressure()` 用 lazy decay(`_apply_lazy_decay` 按时间差衰)。`_decay_tick_loop`(hourly 调 tick_pressure)是 backup,但:
1. logger 打 `self._conscience._raw_pressure`(rc.2 删了 `_raw_pressure`)→ AttributeError(被 except 抓,静默失败)
2. lazy decay 已接管(get_pressure 时必衰),tick_pressure 多余

### 改动 3.1:删 _decay_tick_loop 调度(line 869-872)

```python
# 删掉这段:
# Bug-G (v1.2.11): conscience pressure hourly decay. tick_pressure 原是死代码
# (_raw_pressure 单调递增 → P95 失效 → 每条对话 critical). 每小时调一次让 _raw_pressure 衰减.
self._last_decay_tick = time.time()
asyncio.ensure_future(self._decay_tick_loop())
```

### 改动 3.2:删 _decay_tick_loop 定义(line 1082-1100)

删整个 `_decay_tick_loop` 方法。

### 改动 3.3:tick_pressure 方法保留

**文件**:`emotion_spirit/regulation/superego/conscience.py`

`tick_pressure(hours)` 方法**保留**(test_pressure_formula 测试调 + lazy decay 内部备用)。不删。

### 改动 3.4:确认 _last_tick_time 初始化

conscience.py `__init__` 的 `self._last_tick_time = time.time()`(lazy decay 用)**保留**。main.py 的 `self._last_decay_tick`(line 871,删)是 _decay_tick_loop 用的,跟 _last_tick_time 不同,删 _decay_tick_loop 后 _last_decay_tick 也删。

---

## 任务 4:测试加强

### 改动 4.1:test_axis_coupling 加维度覆盖检查

**文件**:`tests/test_axis_coupling.py`

加测试:KB weights 引用的维度 ∈ set_personality 传入的 personality 维度(防 rc.3 错配重蹈)。

```python
def test_kb_weights_dims_covered_by_personality():
    """KB conscience_params.json weights 引用的维度必须 ∈ 13维 personality (防 rc.3 错配)."""
    import json
    from pathlib import Path
    kb = json.loads(Path("emotion_spirit/core/kb/conscience_params.json").read_text(encoding="utf-8"))
    # 13 维 personality (force_dynamics.py:4-7)
    PERSONALITY_DIMS = {
        "warmth_bias", "patience", "boundary_permeability",  # 自然
        "relational_gravity", "intimacy_pull", "expression_drive", "gossip_tendency",  # 社会
        "inner_coherence", "curiosity", "perception_acuity", "directness",
        "relational_autonomy", "exploration_openness",  # 个体
    }
    for param_name, spec in kb.items():
        if param_name == "_meta":
            continue
        for dim in spec.get("weights", {}):
            assert dim in PERSONALITY_DIMS, (
                f"KB {param_name}.weights 引用 {dim!r}, 但不在 13维 personality 内 — "
                "set_personality 传 deep+surface 合并 (13维), weights 维度必须在其中"
            )
```

### 改动 4.2:加 test_pressure_saturation(用户 §7.3 建议)

**新建**:`tests/test_pressure_saturation.py`

```python
"""Bug-G (v1.3.0 rc.4): 压力不饱和守护.

rc.3 set_personality 只传 deep (5维) → KB weights 6 个 surface 维度取 0.5 兜底 →
参数没人格化 → chronic_decay=0.08 (慢) → 3-4 条 conflict → critical.
rc.4 修: set_personality 传全 13 维 + 调 baseline + 核对 weights 正负.
本测试: 连续灌 conflict, 验证 get_pressure 不饱和 (< 0.95).
"""
from __future__ import annotations

import time as _time

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


def test_pressure_not_saturated_after_50_conflicts():
    """灌 50 条 conflict (模拟时间流逝让急性衰减), get_pressure 应 < 0.95."""
    tracker = ConscienceTracker()
    # 模拟 set_personality (用中性人格, 验证默认参数也不饱和)
    tracker.set_personality({dim: 0.5 for dim in [
        "warmth_bias", "patience", "boundary_permeability", "relational_gravity",
        "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence",
        "curiosity", "perception_acuity", "directness", "relational_autonomy",
        "exploration_openness",
    ]})
    # 灌 50 条 conflict, 每条间隔 60 秒 (让急性衰减)
    for i in range(50):
        tracker.record_value_conflict(
            value_name=f"v{i}", action="a", conscience_impact=0.5, reason="test",
        )
        # 模拟 60 秒流逝 (急性衰减)
        tracker._last_tick_time -= 60  # 回拨 60 秒
    p = tracker.get_pressure()  # 触发 lazy decay
    assert p < 0.95, f"灌 50 条 conflict 后 get_pressure={p}, 应 < 0.95 (Bug-G 饱和?)"


def test_chronic_decays_within_hours():
    """慢性压力在几小时内衰减到低水平."""
    tracker = ConscienceTracker()
    tracker.set_personality({dim: 0.5 for dim in [
        "warmth_bias", "patience", "boundary_permeability", "relational_gravity",
        "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence",
        "curiosity", "perception_acuity", "directness", "relational_autonomy",
        "exploration_openness",
    ]})
    tracker.record_value_conflict("v", "a", 0.8, "test")
    chronic_before = tracker._chronic_pressure
    # 模拟 5 小时流逝
    tracker._last_tick_time -= 5 * 3600
    tracker.get_pressure()  # 触发 lazy decay
    assert tracker._chronic_pressure < chronic_before * 0.5, (
        f"5 小时后 chronic 应衰减到 < 50%, 实际 {tracker._chronic_pressure}/{chronic_before}"
    )


def test_set_personality_changes_params_with_full_dims():
    """set_personality 传全 13 维 → 参数偏离 baseline (人格化生效)."""
    tracker = ConscienceTracker()
    # 高 inner_coherence + patience 人格 → chronic_decay 应升 (快消散, rc.4 正权重)
    resilient = {dim: 0.5 for dim in [
        "warmth_bias", "patience", "boundary_permeability", "relational_gravity",
        "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence",
        "curiosity", "perception_acuity", "directness", "relational_autonomy",
        "exploration_openness",
    ]}
    resilient["inner_coherence"] = 0.9
    resilient["patience"] = 0.9
    tracker.set_personality(resilient)
    # chronic_decay 应 > baseline (inner_coherence/patience 高 → 正权重 → decay 升)
    assert tracker._chronic_decay_rate_per_hour > 0.20, (
        f"高 inner_coherence+patience → chronic_decay 应 > baseline 0.20, "
        f"实际 {tracker._chronic_decay_rate_per_hour} (weights 正负反了?)"
    )
```

**注意**:
- `test_pressure_not_saturated_after_50_conflicts` 用 `_last_tick_time -= 60` 模拟时间流逝(回拨,让 lazy decay 衰减急性)。小模型确认 _last_tick_time 可写。
- `test_set_personality_changes_params_with_full_dims` 验证 weights 正负(rc.4 改正后,inner_coherence 高 → chronic_decay 升)。若 weights 正负没改对,此测试红。
- baseline 0.20 + 高 inner_coherence(0.9)×0.06 + 高 patience(0.9)×0.04 = 0.20+0.054+0.036=0.29 → > 0.20 ✅

### 改动 4.3:跑全套测试

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
python -m pytest tests/ -q --tb=short
```

**期望**:
- 新增 test_pressure_saturation 3 + test_axis_coupling 维度覆盖 1 = 4 新测试全过
- 既有测试全过(rc.3 baseline 1417 + 4 新 = 1421)
- `test_periodic_save_dirty_only` Win flake 仍偶发

**如有红**:
- `test_pressure_not_saturated_after_50_conflicts` 失败 → chronic_decay 仍太慢,调 KB baseline 再升(0.20→0.30)或 chronic_multiplier 再降(0.20→0.15)
- `test_set_personality_changes_params_with_full_dims` 失败 → weights 正负反了,核对(任务 2.3)
- `test_kb_weights_dims_covered_by_personality` 失败 → KB weights 引用了非 13 维的维度名,核对拼写

---

## 任务 5:commit(本地,不 push)

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git status
git add -A
git commit -m "v1.3.0 rc.4: Bug-G 根因修复 (set_personality 传全 13 维) + 清理 (NOT pushed)

Bug-G rc.3 仍饱和根因: set_personality 只传 _baseline_personality['deep'] (5维),
  KB conscience_params.json weights 引用 9 维 (3 deep + 6 surface) → surface 维度
  取 0.5 兜底 → 参数没人格化 → chronic_decay=0.08 (慢) → 3-4 条 conflict → critical.

rc.4 修:
  - main.py:493+798 set_personality 传 deep+surface 合并 (13维) + 诊断 log
  - KB conscience_params.json: chronic_decay baseline 0.08→0.20, chronic_multiplier
    0.30→0.20, 核对 weights 正负 (inner_coherence/patience 高 → decay 升 = 正权重)
  - 清理 _decay_tick_loop (logger 引用已删的 _raw_pressure → AttributeError; lazy decay 接管)
  - test_axis_coupling 加维度覆盖检查 (KB weights 维度 ∈ 13维 personality)
  - test_pressure_saturation: 50 条 conflict 不饱和 + 慢性衰减 + weights 正负验证

测试版, 不 push, 不 bump. 等实测后 ship v1.3.0.
用户反馈: 2026-07-04-emotion-spirit-v130rc3-feedback.md §2 (Bug-G 仍饱和)."
```

**⚠️ 不要 `git push`**。本地 commit。

---

## 任务 6:报告

**新建**:`docs/v1.3.0-rc4-build-report.md`

```markdown
# v1.3.0 rc.4 构建报告(2026-07-04, 不 push)

## 范围
Bug-G 根因修复 (set_personality 传全 13 维) + KB 调参 + 清理 _decay_tick_loop + 测试加强.
**不 push, 不 bump**. 等实测后 ship v1.3.0.

HEAD: `git rev-parse HEAD` 填入

## 改动清单

### Bug-G 根因修复
- main.py:493+798: set_personality 传 deep+surface 合并 (13维, 原只传 deep 5维)
- main.py:493: 加诊断 log (dims + 参数值, 确认覆盖)
- KB conscience_params.json:
  - chronic_decay_rate_per_hour baseline 0.08→0.20 (半衰期 8.3h→3.1h)
  - chronic_multiplier baseline 0.30→0.20
  - weights 正负核对 (inner_coherence/patience 高 → decay 升 = 正权重)
- 清理: _decay_tick_loop (main.py:869-872 + 1082-1100, logger 引用已删 _raw_pressure + lazy decay 接管)

### 测试加强
- test_axis_coupling: 加 KB weights 维度 ∈ 13维 personality 检查 (防 rc.3 错配重蹈)
- test_pressure_saturation (新): 50 条 conflict 不饱和 + 慢性衰减 + weights 正负验证

## 测试
- pytest tests/ 全套: <填入> passed
- 新增: test_pressure_saturation 3 + test_axis_coupling 维度覆盖 1 = 4
- 已知: test_periodic_save_dirty_only Win flake (v1.2.6 backlog)

## 不做清单
- ❌ git push / bump / CHANGELOG
- ❌ Bug-E/H (framework, 等 AstrBot) / Bug-F (已落地, 等 24h)

## 实测后后续
1. 用户丢 zip 实测: docker logs grep "level=critical" 应接近 0 (Bug-G 真修)
2. grep "conscience set_personality dims=13" 确认 set_personality 生效 (dims=13 + 参数偏离默认)
3. 实测通过 → bump v1.3.0 + ship
```

填入数字 + HEAD 后保存。

---

## 不做清单(明确)

- ❌ `git push` / bump / CHANGELOG
- ❌ Bug-E/H(framework,等 AstrBot)/ Bug-F(已落地,等 24h)
- ❌ 改 rc.1-rc.3 其他改动(只修 Bug-G 根因 + 清理)
- ❌ 其他轴心模块人格化(§1.7 TODO 后续)

---

## 关键源码参考

- set_personality 调用:`main.py:493`(初始化)+ `main.py:798`(relabel)
- `_baseline_personality`:`main.py:484 get_personality_params(self._labels)` → `{'deep': {5维}, 'surface': {8维}}`
- 13 维 personality:`emotion_spirit/regulation/force_dynamics.py:4-7`(自然 3 + 社会 4 + 个体 6)
- KB conscience_params.json:`emotion_spirit/core/kb/conscience_params.json`(6 参数 baseline + weights + range)
- _decay_tick_loop:`main.py:869-872`(调度)+ `1082-1100`(定义,logger 引用 `_raw_pressure` 已删)
- ConscienceTracker:`emotion_spirit/regulation/superego/conscience.py`(set_personality:98, get_pressure:296, tick_pressure:307, _apply_lazy_decay:282)
- 用户反馈:`C:\Users\Aston\Downloads\2026-07-04-emotion-spirit-v130rc3-feedback.md` §2(Bug-G 仍饱和)+ §4(_decay_tick_loop 残留)
