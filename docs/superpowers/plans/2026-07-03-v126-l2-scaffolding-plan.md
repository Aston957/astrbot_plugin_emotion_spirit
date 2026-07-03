# emotion_spirit v1.2.6 — L2 脚手架完善 (HP-3 + HP-4 + DO-2)

> **日期**: 2026-07-03
> **作者**: Aston (本 session)
> **状态**: ⏸ DEFERRED (2026-07-03 用户拍板: v1.2.6 改为架构审计, 原 L2 脚手架 plan 推 v1.2.8+ 债清后. 本 plan 留作 L2 完善参考, 不删)
>
> **新 v1.2.6**: 架构审计 (只读) — 21 候选空转核实 + agents 事件流 + main.py 219 行编排 + 分层合理性 + handbook 规约漏洞. 见审计进行中.
> **前置**: v1.2.5 已 ship (`a35d689`, tag `v1.2.5`, 58 modules, 1348 tests)
> **关联**: v1.2.5 ship 后审查 (见 [[emotion-spirit-v125-shipped]] "本次 ship 后审查发现" 段 + [[emotion-spirit-current-truth]] §1 ⚠️ 行)

---

## §0 范围与非目标

### v1.2.6 范围 (3 项, 用户拍板)

| # | 名称 | 来源 | 估时 |
|---|---|---|---|
| 1 | **DO-2**: 拆 `compute_silence_only()` — on_llm_response 高频路径只算 silence, 省 suppression/collapse 计算 | 审查 DO-2 | 30 min |
| 2 | **HP-3**: L2 接全三子 — suppression (定期) + collapse (事件) 回写, 当前只接了 silence 1/3 | 审查 HP-3 | 1.5 h |
| 3 | **HP-4**: `_cumulative_offset` 持久化 — 进 `_store`, 重启不清零 | 审查 HP-4 | 1 h |
| 4 | **HP-2** (D1=纳入): DefenseModulator conscience 死代码修复 — `compute_defense_states` 加 `conscience_pressure` 参数, caller 传 `self._conscience.get_pressure()` (绕过 factory param_wire 限制) | 审查 HP-2 | 30 min |
| 5 | **HP-1** (D5=顺手): `/reflect_force_current` 加 offset 显示 (4 行, 兑现 shift() docstring 承诺) | 审查 HP-1 | 15 min |
| 6 | **DO-3**: `apply_event` 顶部 import (方法内 import 移顶部, 2 min) | 审查 DO-3 | 2 min |
| 7 | **DO-4**: 统一 conscience 源 — `main.py:399` 改用 `self._conscience.get_pressure()`, 跟 HP-2/force_dynamics 一致 | 审查 DO-4 | 30 min |
| 8 | **DO-5**: v1.2.5 spec drift 回扫标注 (文档) | 审查 DO-5 | 20 min |

### v1.2.6 顺手项 (已纳入, 2026-07-03 决策)

- **HP-1** (D5=顺手做): `/reflect_force_current` 加 offset 显示 — 见 §4.2
- **HP-2** (D1=纳入): DefenseModulator conscience 死代码修复 (**HP-3 的隐藏依赖**) — 见 §4.1
- **DO-3** + **DO-4** + **DO-5**: 见 §4.4 / §4.3 / §4.5
- **DO-1**: 由 DO-2 解决 (双算消失), 作为 DO-2 验证项, 不独立任务 — 见 §0 "DO-1 状态"

### v1.2.6 不做 (推 v1.3)

- **L3 fixpoint**: `compute()` 读 `_cumulative_offset` 调制输出 — 这是 L2 真正生效的开关, v1.3 做

### DO-1 状态: 由 DO-2 解决 (不独立任务)

DO-1 原指 "on_llm_response 同流程双算 suppression" (main.py:396 直调 + main.py:1423 DefenseModulator). v1.2.6 做 DO-2 后, 1423 改调 `compute_silence_only` (不算 suppression), 双算消失. suppression 在 on_llm_response 只算一次 (396, 给 life_simulator), schedule loop 算一次 (HP-3 回写, 不同流程). **DO-1 作为 DO-2 验证项** (测试确认 on_llm_response 内 suppression 只算一次), 不独立任务. "彻底收敛" (让 396 也走 DefenseModulator) 跟 DO-2 冲突 (会让 on_llm_response 算全三子, DO-2 白拆), 不做.

### 重要声明: v1.2.6 完成后 L2 仍空转

v1.2.5 的 L2 回写**对行为零影响** (`compute()` 不读 `_cumulative_offset`, `get_cumulative_offset()` 零调用者)。v1.2.6 做完三子全接 + 持久化后, **L2 仍然不影响 `compute()` 输出** — 要等 v1.3 L3 让 `compute()` 读 offset 才真正生效。

**v1.2.6 的价值是"脚手架完整化"**: 三子都回写 + offset 能存活, 这样 v1.3 L3 只要"让 compute() 读 offset"一步就激活整个回路, 不用同时补三子接线和持久化。这是增量推进, 不是功能交付。

---

## §1 DO-2: 拆 `compute_silence_only()` (最简单, 先做)

### 1.1 现状

`on_llm_response` (main.py:1423) 每次回复都调 `compute_defense_states(...)`, 内部算 suppression + collapse + silence 三子, 但 main.py 只读 `silence_tendency` (line 1432-1434)。suppression/collapse 白算 (高频浪费)。

### 1.2 改法

`defense_modulator.py` 加一个只算 silence 的窄方法:

```python
def compute_silence(
    self,
    personality: dict,
    signals: Optional[Any],
    body_state: Optional[Any],
    intimacy_level: float,
    context: dict,
    force_state: Optional[dict],
) -> "SilenceTendency":
    """v1.2.6 DO-2: 只算沉默倾向 (on_llm_response 高频路径用).

    比 compute_defense_states 省 suppression + collapse 两次子计算.
    suppression/collapse 的 L2 回写走低频钩子 (见 §2), 不在此路径.
    """
    session_key = context.get("session_key", "default")
    return self._segmented_coordinator.compute_silence_tendency(
        user_id=session_key,
        personality=personality,
        force_state=force_state,
        body_state=body_state,
        signals=signals,
        intimacy_level=intimacy_level,
        context=context,
    )
```

main.py:1423-1435 改:

```python
# v1.2.6 DO-2: 只算 silence (高频路径省 suppression/collapse)
silence_tendency_obj = self._defense_modulator.compute_silence(
    personality=personality,
    signals=signals,
    body_state=body_state,
    intimacy_level=intimacy,
    context=context,
    force_state=force_state,
)
should_silent, reason, _ = self._segmented_coordinator.should_be_silent(
    user_id, silence_tendency_obj, seg_config
)
```

**`compute_defense_states` 保留**: 低频钩子 (schedule loop, §2.2) + `/reflect` + v1.3 L3 仍用它算全三子。

### 1.3 为什么 DO-2 跟 HP-3 不冲突

- on_llm_response 高频路径: 只算 silence (DO-2 省钱)
- suppression L2 回写: 挂 `_schedule_plan_generation_loop` (每天 1 次, 低频), 用 `compute_defense_states` 算 suppression
- collapse L2 回写: 挂 collapse 事件触发点 (低频离散)

三子回写各有低频落点, on_llm_response 只管 silence, 互不打架。

---

## §2 HP-3: L2 接全三子

### 2.1 三子回写现状与落点

| 子系统 | 触发性质 | 当前 | v1.2.6 落点 | intensity |
|---|---|---|---|---|
| **silence** | 高频事件 (每次回复) | ✅ 已接 (main.py:1447) | 不动 | `silence_tendency.score` (连续) |
| **collapse** | 低频离散事件 (崩溃触发) | ❌ 未接 | `memory_pool.tick()` 后状态变化检测 (§2.3) | `1.0` (离散全强度, 见 §5 D2) |
| **suppression** | 慢变量 (定期累积) | ❌ 未接 | `_schedule_plan_generation_loop` (§2.2) | `suppression_level` (连续) |

### 2.2 suppression L2 定期回写

在 `_schedule_plan_generation_loop` (main.py:829, 每天 2am 跑) 的日程生成后加:

```python
# v1.2.6 HP-3: suppression L2 定期回写 (每天 1 次, 慢变量)
try:
    defense_states = self._defense_modulator.compute_defense_states(
        personality=personality,
        signals=None,  # schedule loop 无实时 signals
        body_state=self._body_state.default() if hasattr(self, "_body_state") else None,
        intimacy_level=0.5,  # schedule loop 无特定 user
        context={},
        force_state=self._force_dynamics.get_current_force_state(self._labels) if hasattr(self, "_force_dynamics") else None,
    )
    self._defense_modulator.apply_event("suppression", intensity=defense_states.suppression_level)
except Exception:
    logger.debug("emotion_spirit: suppression L2 回写失败", exc_info=True)
```

**频率决策** (§5 D3): 每天 1 次 (schedule_plan_loop) vs 每天 2 次 (diary_loop)。suppression 是慢变量, 1 次/天可能够, 但待讨论。

**⚠️ HP-2 依赖**: `compute_defense_states` 内部 suppression 用 `conscience_pressure=0.0` (HP-2 死代码)。**不修 HP-2, suppression 回写就用错值**。见 §4。

### 2.3 collapse L2 事件回写 (状态变化检测)

`check_collapse` 在 `memory_pool.tick()` (memory_pool.py:455) 内部被调, 触发时设 `_collapse_active=True` + `_collapse_archetype`。main.py 不直接调 check_collapse。

**方案 B (推荐, 不改 memory_pool)**: main.py 在调 `pool.tick()` 后, 检测 `_collapse_active` 状态变化:

```python
# v1.2.6 HP-3: collapse L2 事件回写 (状态变化检测)
prev_collapse = getattr(self, "_prev_collapse_active", False)
curr_collapse = getattr(self._pool, "_collapse_active", False)
if curr_collapse and not prev_collapse:
    # 本 tick 刚触发崩溃 → L2 回写
    self._defense_modulator.apply_event("collapse", intensity=1.0)
    logger.info("emotion_spirit: collapse L2 回写 (archetype=%s)", getattr(self._pool, "_collapse_archetype", None))
self._prev_collapse_active = curr_collapse
```

**Step 0 (实施前验证)**: grep 确认 main.py 哪里调 `self._pool.tick(...)`, 把这段状态检测挂在那个 caller 后面。若 main.py 不直接调 (life_sim 代调), 则挂 life_sim tick 后的下一个 main.py 钩子。

**intensity 决策** (§5 D2): `1.0` (离散全强度, 崩溃是极端事件, KB `defense_deltas.json` 的 collapse delta 本就大: natural -0.08) vs 算 `collapse_tendency` (要改 check_collapse 返回 tendency, 增加耦合)。推荐 `1.0`。

### 2.4 KB 一致性

`defense_deltas.json` 已有 silence/collapse/suppression 三档 delta (v1.2.5 PR2 建好), v1.2.6 不动 KB, 只是终于把 collapse/suppression 两档用起来。

---

## §3 HP-4: `_cumulative_offset` 持久化

### 3.1 现状

`force_dynamics._cumulative_offset` (force_dynamics.py:160) 在 `__init__` 初始化为 0, 内存态。`_store` 持久化列表 (main.py:1675-1682) 无 force_dynamics。重启 / persona 切换 / `_reset_superego_modules` 都不清它 (force_dynamics 不在 superego sub), 但重启后 `__init__` 重新归零。

### 3.2 改法

**force_dynamics.py 加 restore** (get_cumulative_offset 已有, 加一个 setter):

```python
def restore_offset(self, offset: dict[str, float]) -> None:
    """v1.2.6 HP-4: 从持久化恢复累积偏移 (启动时调)."""
    if not offset:
        return
    self._cumulative_offset["individual"] = float(offset.get("individual", 0.0))
    self._cumulative_offset["natural"] = float(offset.get("natural", 0.0))
    self._cumulative_offset["social"] = float(offset.get("social", 0.0))
```

**main.py `_persist_modules` (line 1668) 加一行**:

```python
self._store.set("force_dynamics_offset", self._force_dynamics.get_cumulative_offset())
```

**main.py load 段 (`_store.load()` 后, ~line 790 附近的恢复逻辑) 加**:

```python
# v1.2.6 HP-4: 恢复 force_dynamics 累积偏移
fd_offset = self._store.get("force_dynamics_offset", None)
if fd_offset and hasattr(self, "_force_dynamics"):
    self._force_dynamics.restore_offset(fd_offset)
```

### 3.3 per-persona 决策 (§5 D4)

`force_dynamics` 是 `@register(depends_on=[])` 全局单例 (非 per-persona), 所以 offset 天然全局共享。**推荐: persona 切换不重置 offset** (bot 的力学漂移是整体状态, 不是 per-persona)。若用户要 per-persona 隔离, 需把 offset 改成 dict[persona_id, offset], 复杂度上升, 不建议 v1.2.6 做。

---

## §4 依赖与顺手项

### 4.1 ⚠️ HP-2 是 HP-3 的隐藏依赖

**问题**: HP-3 的 suppression L2 回写 (§2.2) 调 `compute_defense_states`, 内部 `defense_modulator.py:94`:
```python
conscience_pressure=getattr(self._conscience, "pressure", 0.0) if hasattr(self, "_conscience") else 0.0,
```
`self._conscience` 从未注入 (HP-2), `conscience_pressure` 永远 0.0。**不修 HP-2, suppression L2 回写用的是无 conscience 加权的错值**。

**决策 (2026-07-03 D1=纳入)**: 用 **caller 传参法** (绕过 factory param_wire 1:1 限制, R1 风险消除):

```python
# defense_modulator.py — compute_defense_states 加参数 (向后兼容, 默认 0.0)
def compute_defense_states(
    self,
    personality: dict,
    signals: Optional[Any],
    body_state: Optional[Any],
    intimacy_level: float,
    context: dict,
    force_state: Optional[dict],
    conscience_pressure: float = 0.0,  # v1.2.6 HP-2: caller 传, 删 hasattr 死分支
) -> DefenseStates:
    ...
    suppression_level = self._suppression.compute(
        personality, context,
        conscience_pressure=conscience_pressure,  # 不再用 hasattr(self, "_conscience")
        relationship_intimacy=intimacy_level,
        **kwargs,
    )
```

```python
# main.py schedule loop caller 传真值
defense_states = self._defense_modulator.compute_defense_states(
    ...,
    conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0,
)
```

- `compute_silence` (DO-2) **不加** conscience_pressure (silence 不用 conscience)
- 删 `defense_modulator.py:94` 的 `hasattr(self, "_conscience")` 死分支
- 向后兼容: 旧 caller 不传 `conscience_pressure` → 默认 0.0 (跟 v1.2.5 行为一致, 不破坏现有测试)

**HP-2 当前无害的唯一原因** (suppression_level 没人读) 被 HP-3 打破: 一接 suppression 回写就激活陷阱, 必须一起修。

### 4.2 HP-1 顺手建议 (HP-4 完成后)

HP-4 让 offset 能存活, 但若 HP-1 不做, offset 仍没人读 (`get_cumulative_offset()` 仍零调用者)。HP-1 = `/reflect_force_current` (commands.py:623) 加 4 行显示 offset:

```python
# v1.2.6 HP-1: 兑现 shift() docstring 承诺, 显示累积偏移
offset = self._p._force_dynamics.get_cumulative_offset()
lines += [
    "",
    "Cumulative offset (L2 回写累积, v1.3 L3 激活):",
    f"- natural: {offset.get('natural', 0):.3f}",
    f"- social: {offset.get('social', 0):.3f}",
    f"- individual: {offset.get('individual', 0):.3f}",
]
```

**4 行代码, 让 HP-4 持久化的 offset 有诊断可观测性**。建议顺手做 (§5 D5)。

### 4.3 DO-4: 统一 conscience 源 (行为变更, 要回归验证)

**现状**: `main.py:399` `conscience_pressure=getattr(signals, "body_criticality", 0.0)` — 把 body 信号当 conscience 压力传给 `sup_mod.compute()`. 而 `force_dynamics.compute()` 用的是 `conscience_tracker.get_pressure()` (force_dynamics.py:309). 两条 suppression 路径用不同 conscience 源. HP-2 修 DefenseModulator 后, 这个不一致更明显 (新路径用 tracker, 旧路径用 body 信号).

**改法**:
```python
# main.py:399 — v1.2.6 DO-4: 统一用 conscience tracker (跟 force_dynamics + HP-2 一致)
conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0,
```

**风险 (R7)**: 行为变更 — suppression 值会变 (body_criticality → conscience pressure 语义不同, 虽然值域都 [0,1]). life_simulator 消费 suppression_level, 输出可能退化.

**验证策略**:
- 跑现有 `test_life_simulator*.py` + `test_suppression*.py` 全套, 看输出是否在合理范围
- 加 `test_suppression_conscience_source.py`: mock conscience tracker, 验证 `main.py:396` 路径用 `conscience.get_pressure()` 而非 body_criticality
- 若 life_simulator 输出退化, 评估调 suppression 公式权重 (但优先保持公式 — conscience.get_pressure() 是正确源, body_criticality 是 bug)

### 4.4 DO-3: apply_event 顶部 import (2 min)

`defense_modulator.py:139` `from ..core.persona_labels_db import get_defense_deltas` 移到文件顶部 (跟其他 import 一起). 纯风格, 无行为变更.

### 4.5 DO-5: v1.2.5 spec drift 回扫标注 (文档, 20 min)

在 `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` 头加 "实现 drift 注记 (v1.2.5 ship 后回扫)" 段, 列 spec vs 实现的 drift:

| spec 写 | 实际 | 评估 |
|---|---|---|
| `config_keys={"segmented_reply"}` | 无 config_keys | 无所谓 (DefenseModulator 不读 config) |
| `self._conscience.pressure` | `hasattr` fallback (永远 False) | ❌ 更差 → HP-2/DO-4 修 |
| `force_dynamics.apply_defense_delta` 硬编码 | `DefenseModulator.apply_event` + KB | ✅ 更好 (handbook §1.1) |
| `silence_components: dict = None` | `field(default_factory=dict)` | ✅ 更好 (避免 mutable default) |
| 三子 L2 全接 | 实际只接 silence 1/3 | → HP-3 补全 |

标 "spec 反映设计意图, 实现以代码为准; drift 已在 v1.2.6 收敛". 防止未来 session 读 spec 被误导 (跟 [[emotion-spirit-current-truth]] §5 "不要让 docstring 撒谎" 一致).

---

## §5 决策点 (待用户讨论)

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | HP-2 是否纳入? | (a) 纳入 / (b) 绕过 / (c) 缩 HP-3 | ✅ **(a) 纳入** (2026-07-03) — caller 传参法, 30 min |
| **D2** | collapse intensity | `1.0` / 算 tendency | ✅ **`1.0`** (默认采纳) |
| **D3** | suppression 频率 | schedule_plan_loop / diary_loop | ✅ **schedule_plan_loop** (默认采纳) |
| **D4** | offset per-persona? | 全局 / per-persona | ✅ **全局共享** (默认采纳) |
| **D5** | HP-1 顺手? | 是 / 否 | ✅ **是** (2026-07-03) — 4 行, 15 min |
| **D6** | PR 拆分? | 单 PR / 拆 | ✅ **单 PR** (默认采纳) |
| **D7** | DO-3/DO-4/DO-5 补进 v1.2.6? | 多选 | ✅ **全补** (2026-07-03) — DO-3 顶部 import / DO-4 统一 conscience 源 / DO-5 spec drift 标注 |
| **D8** | DO-1 处置? | 独立做 / 由 DO-2 解决 | ✅ **由 DO-2 解决** (技术判断) — 双算在 DO-2 后消失, 作 DO-2 验证项; "彻底收敛" 跟 DO-2 冲突不做 |

---

## §6 文件清单 (预计修改)

| 文件 | 改动 | 估行数 |
|---|---|---|
| `emotion_spirit/regulation/defense_modulator.py` | DO-2 加 `compute_silence()` + HP-2 conscience 修 (取决于 D1) | +25 |
| `emotion_spirit/regulation/force_dynamics.py` | HP-4 加 `restore_offset()` | +10 |
| `main.py` | DO-2 改调 compute_silence + HP-3 suppression/collapse 回写 + HP-4 persist/load + DO-4 conscience 源统一 (line 399) | +40 |
| `emotion_spirit/output/commands.py` | HP-1 `/reflect_force_current` 加 offset 显示 | +8 |
| `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` | DO-5 加 "实现 drift 注记" 段 | +20 |
| `tests/test_defense_modulator.py` | compute_silence 测试 + conscience 修回归 | +30 |
| `tests/test_force_dynamics.py` | restore_offset round-trip 测试 | +15 |
| `tests/test_l2_feedback_wiring.py` (新) | HP-3 三子回写接线测试 (mock schedule loop + collapse 触发) | +60 |
| `tests/test_reflect_force_current.py` (新或扩) | HP-1 offset 显示测试 | +15 |
| `UPDATE_HANDBOOK.md` | §6 加 "v1.2.6 已清的债" 段 | +10 |
| `docs/CHANGELOG.md` | v1.2.6 entry | +15 |

**总**: ~220 行 (含 ~120 测试)

---

## §7 测试策略

### 7.1 DO-2

```python
def test_compute_silence_only_does_not_compute_suppression():
    """compute_silence 不调 suppression.compute / collapse_selector.compute_bas_bis"""
    # mock 三子, 验证只 silence 被调

def test_compute_silence_matches_defense_states_silence_field():
    """同一输入, compute_silence().score == compute_defense_states().silence_tendency"""
```

### 7.2 HP-3

```python
def test_silence_l2_already_wired():  # 回归
    """silence 触发 → apply_event('silence') 被调 (v1.2.5 已有, 防回归)"""

def test_collapse_l2_wired_on_trigger():
    """_collapse_active False→True → apply_event('collapse', 1.0) 被调一次"""

def test_collapse_l2_not_retriggered_while_active():
    """_collapse_active 持续 True → 不重复 apply_event"""

def test_suppression_l2_wired_in_schedule_loop():
    """schedule_plan_loop 跑 → apply_event('suppression', level) 被调"""
```

### 7.3 HP-4

```python
def test_offset_persist_round_trip():
    """shift 累加 → to_dict → restore_offset → get_cumulative_offset 一致"""

def test_offset_survives_restart(monkeypatch):
    """_persist_modules + _store.load → force_dynamics offset 恢复"""

def test_offset_global_not_per_persona():
    """persona 切换后 offset 不重置 (D4 决策)"""
```

### 7.4 HP-1 (若 D5=yes)

```python
def test_reflect_force_current_shows_offset():
    """/reflect_force_current 输出含 'Cumulative offset' + 三力值"""
```

---

## §8 DoD

- [ ] pytest 全绿 (1348 + ~120 新 = ~1468 passed)
- [ ] module count 保持 58 (v1.2.6 不加新模块, handbook §1.2)
- [ ] force_dynamics.compute() 签名仍不变 (handbook §1.2 向后兼容)
- [ ] L2 三子回写全接 (silence + collapse + suppression 各有测试)
- [ ] offset 持久化 round-trip 测试通过
- [ ] **声明**: changelog 明确标 "v1.2.6 是 L2 脚手架完善, L2 仍不影响 compute() 输出, v1.3 L3 激活" (避免重蹈 v1.2.5 "脚手架当功能" 覆辙)
- [ ] handbook §6 更新 "v1.2.6 已清的债"
- [ ] memory: [[emotion-spirit-current-truth]] §1 ⚠️ 行对应清除

---

## §9 风险

| # | 风险 | 处置 |
|---|---|---|
| R1 | ~~HP-2 修法 (a) 撞 factory param_wire 1:1 限制~~ | ✅ 已消除 (D1=caller 传参法, 不走 factory 注入) |
| R2 | collapse 状态变化检测漏触发 (pool.tick caller 不在 main.py) | Step 0 grep 确认 tick caller; 必要时挂 on_llm_response 末尾兜底 (低频检测) |
| R3 | suppression 回写用错 conscience (HP-2 未修) | D1 决策: 强烈建议纳入 HP-2 |
| R4 | offset 持久化但 compute() 不读, 用户困惑"为何没变化" | changelog + /reflect 显示明示 "v1.3 L3 激活" (HP-1 顺手帮此) |
| R5 | schedule loop 里 compute_defense_states 无 signals/body_state, suppression 值偏差 | 接受 (低频回写, 偏差可容忍); 或用 main.py:396 同款 signals 源 |
| R6 | DO-2 拆 compute_silence 后, v1.3 L3 要用全 DefenseStates 时漏接 | compute_defense_states 保留 + 文档标注 "L3/schedule loop 用" |
| R7 | DO-4 行为变更: conscience 源 body_criticality → conscience.get_pressure() 让 suppression 值变, life_simulator 输出可能退化 | 跑 life_simulator + suppression 全套回归; 加 test_suppression_conscience_source.py; 若退化评估调权重 (优先保持公式, conscience.get_pressure() 是正确源) |

---

## §10 相关

- [[emotion-spirit-v125-shipped]] — v1.2.5 ship + 审查发现 (本 plan 输入)
- [[emotion-spirit-current-truth]] — §1 ⚠️ 行 = 本 plan 清的债
- [[emotion-spirit-update-handbook]] — §6 清债清单 + §1.2 向后兼容规约
- `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` — v1.2.5 spec (HP-3 接 §4.2 三子回写, v1.2.5 只做了 silence)
