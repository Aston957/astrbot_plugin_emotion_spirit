# emotion_spirit v1.2.9 — L2 脚手架剩余 3 项 (DO-2 + HP-3 + HP-1)

> **日期**: 2026-07-03 (原 v1.2.6 L2 脚手架 plan, 2026-07-03 v1.2.8 ship 后激活为 v1.2.9)
> **作者**: Aston
> **状态**: ✅ ACTIVE (原 v1.2.6 L2 脚手架 8 项中 5 项已在 v1.2.7 顺手做, v1.2.9 聚焦剩 3 项)
>
> **版本号说明**: 原 v1.2.6 L2 脚手架因审计搁置 deferred 到 v1.2.8+. 但 v1.2.8 实际用作"v1.2.7 遗留 5 项债"清债版, L2 脚手架剩余挤到 v1.2.9. 本 plan 原"v1.2.6"引用统一指 v1.2.9. 这是 v1.3 L3 (compute 读 offset) 的前置脚手架.
> **前置**: v1.2.8 已 ship (`442d456`, tag `v1.2.8`, 48 modules, 1358 tests)
> **关联**: [[emotion-spirit-v125-shipped]] "本次 ship 后审查发现" + [[emotion-spirit-current-truth]] §1 ⚠️ 行 + [[emotion-spirit-v127-status]] (v1.2.8 shipped)

## §0.1 v1.2.9 激活说明 (原 8 项 → 聚焦 3 项)

原 v1.2.6 L2 脚手架 8 项, v1.2.7 清债顺手做掉 5 项, v1.2.9 聚焦剩 3 项:

| # | 项 | 状态 | 说明 |
|---|---|---|---|
| 3 | HP-4 offset 持久化 | ✅ v1.2.7 Task 6 已做 | force_dynamics.restore_offset + main.py persist/load. §3 不再重复 |
| 4 | HP-2 conscience 死代码 | ✅ v1.2.7 Task 2 已做 | compute_defense_states 加 conscience_pressure 参数. §4.1 不再重复 |
| 6 | DO-3 apply_event 顶部 import | ✅ v1.2.7 Task 7 已做 | §4.4 不再重复 |
| 7 | DO-4 统一 conscience 源 | ✅ v1.2.7 Task 2 已做 | caller 用 get_pressure(). §4.3 不再重复 |
| 8 | DO-5 spec drift 标注 | ✅ v1.2.7 Task 8 已做 | §4.5 不再重复 |
| **1** | **DO-2 拆 compute_silence_only** | ❌ v1.2.9 做 | §1 聚焦 |
| **2** | **HP-3 L2 接全三子** (suppression + collapse) | ❌ v1.2.9 做 | §2 聚焦 (silence 已接 orchestrator:118, 补 suppression + collapse) |
| **5** | **HP-1 /reflect_force_current offset 显示** | ❌ v1.2.9 做 | §4.2 聚焦 |

**v1.2.9 范围**: DO-2 (§1) + HP-3 suppression/collapse 回写 (§2) + HP-1 offset 显示 (§4.2). 其余 §3/§4.1/§4.3/§4.4/§4.5 已在 v1.2.7 做, 保留作背景参考但不重复执行.

---

## §0.2 执行总纲 (给执行模型)

**执行顺序**: DO-2 (§1) → HP-3 (§2) → HP-1 (§4.2). 按依赖: DO-2 先 (orchestrator 高频路径优化, 独立) → HP-3 (suppression/collapse 回写, 依赖 compute_defense_states 已有) → HP-1 (offset 显示, 依赖 HP-4 持久化已有, 独立).

**每步 TDD**: 先写测试 → 跑红 → 改代码 → 跑绿 → `pytest tests/` 全绿才下一步.

**遇到不确定停下问**: collapse 边沿检测逻辑 (§2.3) / suppression 频率 (§5 D3) / conscience_pressure 参数去留 (§1.2 决策).

**关键纪律**:
- 不改 compute_defense_states 签名 (向后兼容, handbook §1.2)
- 不改 force_dynamics.compute() 签名 (v1.3 L3 才动)
- L2 回写仍不影响 compute() 输出 (v1.3 L3 激活, plan §0 "完成后仍空转")
- 每步新增测试进 tests/, 不删旧测试

**DoD**: pytest 全绿 (1358 + ~15 新 = ~1373) + L2 三子回写全接 + offset 显示可观测 + CHANGELOG v1.2.9 entry + handbook §6 更新.

---

## §0 范围与非目标

### v1.2.9 范围 (3 项, 原 v1.2.6 L2 脚手架剩余)

| # | 名称 | 来源 | 估时 |
|---|---|---|---|
| 1 | **DO-2**: 拆 `compute_silence()` — orchestrator 高频路径只算 silence, 省 suppression/collapse 计算 | 审查 DO-2 | 30 min |
| 2 | **HP-3**: L2 接全三子 — suppression (定期) + collapse (事件) 回写, 当前只接了 silence 1/3 | 审查 HP-3 | 1.5 h |
| 3 | **HP-1**: `/reflect_force_current` 加 offset 显示 (4 行, 兑现 shift() docstring 承诺 + HP-4 持久化的 offset 有可观测性) | 审查 HP-1 | 15 min |

### v1.2.9 不做 (推 v1.3)

- **L3 fixpoint**: `compute()` 读 `_cumulative_offset` 调制输出 — 这是 L2 真正生效的开关, v1.3 做

### 重要声明: v1.2.9 完成后 L2 仍空转

v1.2.5 的 L2 回写**对行为零影响** (`compute()` 不读 `_cumulative_offset`, `get_cumulative_offset()` 仅 v1.2.9 HP-1 开始读用于显示)。v1.2.9 做完三子全接 + 持久化 + 可观测后, **L2 仍然不影响 `compute()` 输出** — 要等 v1.3 L3 让 `compute()` 读 offset 才真正生效。

**v1.2.9 的价值是"脚手架完整化"**: 三子都回写 + offset 能存活 + offset 可观测, 这样 v1.3 L3 只要"让 compute() 读 offset"一步就激活整个回路, 不用同时补三子接线和持久化。这是增量推进, 不是功能交付。

---

## §1 DO-2: 拆 `compute_silence()` (最简单, 先做)

### 1.1 现状 (v1.2.9 行号, v1.2.7 抽 orchestrator 后调用点变了)

`SegmentedReplyOrchestrator.handle` (segmented_reply_orchestrator.py:93) 每次回复都调 `compute_defense_states(...)`, 内部算 suppression + collapse + silence 三子, 但只读 `silence_tendency` (orchestrator:102-106 构造 SilenceTendency)。suppression/collapse 白算 (高频浪费)。

### 1.2 改法 (精确 diff)

**Step 1: defense_modulator.py 加 compute_silence 方法**

在 `compute_defense_states` (defense_modulator.py:78-125) 后, `apply_event` (127) 前, 加:

```python
def compute_silence(
    self,
    personality: dict,
    signals: Optional[Any],
    body_state: Optional[Any],
    intimacy_level: float,
    context: dict,
    force_state: Optional[dict],
) -> Any:
    """v1.2.9 DO-2: 只算沉默倾向 (orchestrator 高频路径用).

    比 compute_defense_states 省 suppression + collapse 两次子计算.
    silence 不用 conscience_pressure (silence 公式不读 conscience, 见 compute_defense_states L1 第 3 步).
    suppression/collapse 的 L2 回写走低频钩子 (§2), 不在此路径.

    返回 SilenceTendency (coordinator 产的), 非 DefenseStates。caller 直接用。
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

注意:
- **不加 conscience_pressure 参数** (silence 公式不读 conscience, 见 compute_defense_states:107-117 第 3 步只调 coordinator.compute_silence_tendency)
- 返回 `segmented_reply_coordinator.compute_silence_tendency` 的返回值 (SilenceTendency), 非 DefenseStates
- defense_modulator 不需要 import SilenceTendency (返回值是 coordinator 产的, 不构造)

**Step 2: orchestrator.py:90-106 改调 compute_silence**

当前 (segmented_reply_orchestrator.py:90-106):
```python
            # --- 2. 沉默判定 (L1: 走 DefenseModulator 统一入口) ---
            from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency

            defense_states = self._defense_modulator.compute_defense_states(
                personality=personality,
                signals=signals,
                body_state=body_state,
                intimacy_level=intimacy_level,
                context=context,
                force_state=force_state,
                conscience_pressure=conscience_pressure,
            )
            silence_tendency_obj = SilenceTendency(
                score=defense_states.silence_tendency,
                reason=defense_states.silence_reason,
                components=defense_states.silence_components,
            )
```

改为:
```python
            # --- 2. 沉默判定 (L1: v1.2.9 DO-2 走 compute_silence 只算 silence, 省 suppression/collapse) ---
            silence_tendency_obj = self._defense_modulator.compute_silence(
                personality=personality,
                signals=signals,
                body_state=body_state,
                intimacy_level=intimacy_level,
                context=context,
                force_state=force_state,
            )
```

省了: `from ... import SilenceTendency` + `compute_defense_states` 调用 + `SilenceTendency(...)` 构造 (3 处 → 1 处调用)。

**conscience_pressure 参数去留决策 (§1.2 D1)**:
- DO-2 后, orchestrator.handle 只调 compute_silence (不用 conscience_pressure)
- HP-3 suppression 回写在 main.py schedule loop (§2.2), 不在 orchestrator
- 所以 orchestrator.handle 的 `conscience_pressure` 参数 DO-2 后**不再被使用**
- **决策: 保留参数 (向后兼容)** — main.py `_collect_segmented_state` 仍传, 但 orchestrator 内不用。标 docstring "v1.2.9 DO-2 后未用, 保留向后兼容"。避免改 main.py 签名 + 测试。

### 1.3 为什么 DO-2 跟 HP-3 不冲突

- orchestrator 高频路径: 只算 silence (DO-2 省钱)
- suppression L2 回写: 挂 `_schedule_plan_generation_loop` (每天 1 次, 低频), 用 `compute_defense_states` 算 suppression (§2.2)
- collapse L2 回写: 挂 surface_handler collapse 检测 (低频离散, §2.3)

三子回写各有低频落点, orchestrator 只管 silence, 互不打架。

### 1.4 compute_defense_states 保留

`compute_defense_states` **不删** — HP-3 suppression 回写 (§2.2) + `/reflect` + v1.3 L3 仍用它算全三子。DO-2 只是给高频路径加个窄方法, 不替换全方法。

### 1.5 测试

`tests/test_defense_modulator.py` 加:

```python
def test_compute_silence_only_does_not_compute_suppression(mocker):
    """v1.2.9 DO-2: compute_silence 不调 suppression.compute / collapse_selector.compute_bas_bis"""
    dm = DefenseModulator(
        force_dynamics=mocker.Mock(),
        suppression=mocker.Mock(),
        collapse_archetype_selector=mocker.Mock(),
        segmented_reply_coordinator=mocker.Mock(),
    )
    dm._segmented_coordinator.compute_silence_tendency.return_value = mocker.Mock(score=0.3, reason="", components={})

    dm.compute_silence(personality={}, signals=None, body_state=None,
                       intimacy_level=0.5, context={}, force_state=None)

    dm._suppression.compute.assert_not_called()
    dm._collapse_selector.compute_bas_bis.assert_not_called()
    dm._segmented_coordinator.compute_silence_tendency.assert_called_once()


def test_compute_silence_matches_defense_states_silence_field(mocker):
    """同一输入, compute_silence().score == compute_defense_states().silence_tendency"""
    # mock coordinator.compute_silence_tendency 返回固定 SilenceTendency
    # 调 compute_silence + compute_defense_states, 验证 silence 一致
```

---

## §2 HP-3: L2 接全三子 (suppression + collapse)

### 2.1 三子回写现状与落点 (v1.2.9 行号)

| 子系统 | 触发性质 | 当前 | v1.2.9 落点 | intensity |
|---|---|---|---|---|
| **silence** | 高频事件 (每次回复) | ✅ 已接 (orchestrator:118) | 不动 | `silence_tendency.score` (连续) |
| **collapse** | 低频离散事件 (崩溃触发) | ❌ 未接 | surface_handler:280 (collapse 检测后, 边沿触发) | `1.0` (离散全强度) |
| **suppression** | 慢变量 (定期累积) | ❌ 未接 | main.py `_schedule_plan_generation_loop:867` (日程生成后) | `suppression_level` (连续) |

### 2.2 suppression L2 定期回写 (main.py schedule loop)

在 `_schedule_plan_generation_loop` (main.py:831) 的日程生成后, `self._last_plan_date = today_str` (main.py:867) 后, `logger.info(...)` (868) 前或后, 加:

```python
                # v1.2.9 HP-3: suppression L2 定期回写 (每天 1 次, 慢变量)
                try:
                    defense_states = self._defense_modulator.compute_defense_states(
                        personality=personality,
                        signals=None,  # schedule loop 无实时 signals
                        body_state=self._body_state.default() if hasattr(self, "_body_state") else None,
                        intimacy_level=0.5,  # schedule loop 无特定 user
                        context={},
                        force_state=(
                            self._force_dynamics.force_state_from_labels(self._labels)
                            if hasattr(self, "_force_dynamics") and hasattr(self, "_labels")
                            else None
                        ),
                        conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0,
                    )
                    self._defense_modulator.apply_event("suppression", intensity=defense_states.suppression_level)
                    logger.debug("emotion_spirit: suppression L2 回写 level=%.3f", defense_states.suppression_level)
                except Exception:
                    logger.debug("emotion_spirit: suppression L2 回写失败", exc_info=True)
```

**插入点**: main.py:867 (`self._last_plan_date = today_str`) 后。`personality` 变量已在 854 定义 (`self._get_current_personality_dict()`), 复用。

**注意**:
- HP-2 已做 (v1.2.7): `conscience_pressure` 显式传 `self._conscience.get_pressure()`, 不再用旧 hasattr 死分支的 0.0
- `compute_defense_states` 仍用 (非 compute_silence), 因为要算 `suppression_level`
- frequency: 每天 1 次 (schedule_plan_loop 2am 跑, §5 D3 决策)

### 2.3 collapse L2 事件回写 (surface_handler, 边沿检测)

⚠️ **v1.2.8 引入的 recovery 重复触发 bug**: surface_handler:280 `if was_collapse and archetype:` 每次 tick (collapse 持续期间) 都调 `trigger_recovery` → `start_recovery` 重置 `_recovery_stage=0` → **恢复永远不推进**。v1.2.9 HP-3 用边沿检测顺便修这个 bug。

当前 (surface_handler.py:278-283):
```python
        # v1.2.8: collapse → recovery 触发 (走公开接口, 不伸手 _collapse_archetype/_recovery 私有)
        archetype = self._p._pool.get_collapse_archetype()
        if was_collapse and archetype:
            lsv2 = getattr(self._p, '_life_sim_v2', None)
            if lsv2 and hasattr(lsv2, 'trigger_recovery'):
                lsv2.trigger_recovery(archetype)
```

改为 (边沿检测 + L2 回写):
```python
        # v1.2.8: collapse → recovery 触发; v1.2.9 HP-3: 边沿检测 + collapse L2 回写
        # 边沿检测修 v1.2.8 bug: collapse 持续期间不重复 trigger_recovery (否则 start_recovery 重置 stage=0, 恢复永不推进)
        archetype = self._p._pool.get_collapse_archetype()
        curr_collapse = was_collapse and bool(archetype)
        prev_collapse = getattr(self._p, "_prev_collapse_active", False)
        if curr_collapse and not prev_collapse:
            # 本 tick 刚触发崩溃 (False→True 边沿) → recovery + L2 回写各一次
            lsv2 = getattr(self._p, '_life_sim_v2', None)
            if lsv2 and hasattr(lsv2, 'trigger_recovery'):
                lsv2.trigger_recovery(archetype)
            dm = getattr(self._p, '_defense_modulator', None)
            if dm and hasattr(dm, 'apply_event'):
                dm.apply_event("collapse", intensity=1.0)
                logger.info("emotion_spirit: collapse L2 回写 (archetype=%s)", archetype)
        self._p._prev_collapse_active = curr_collapse
```

**关键**:
- `was_collapse` = `check_collapse(...)` 返回值 = 当前 `_collapse_active` (collapse 期间持续 True)
- 边沿检测: 只在 `prev=False, curr=True` 时回写 + trigger (一次)
- `self._p._prev_collapse_active` 存在 plugin 实例上 (跨 tick 记忆)
- intensity `1.0` (§5 D2 决策: 崩溃是极端事件, KB `defense_deltas.json` 的 collapse delta 本就大)
- **同时修 v1.2.8 recovery 重复触发 bug** (额外收益, plan §9 R10 记)

### 2.4 KB 一致性

`defense_deltas.json` 已有 silence/collapse/suppression 三档 delta (v1.2.5 PR2 建好), v1.2.9 不动 KB, 只是终于把 collapse/suppression 两档用起来。

### 2.5 测试

`tests/test_l2_feedback_wiring.py` (新文件):

```python
def test_silence_l2_already_wired():
    """silence 触发 → apply_event('silence') 被调 (v1.2.5 已有, 防回归)"""
    # mock orchestrator handle, 触发沉默, 验证 apply_event('silence') 被调


def test_collapse_l2_wired_on_trigger():
    """v1.2.9 HP-3: _collapse_active False→True → apply_event('collapse', 1.0) 被调一次"""


def test_collapse_l2_not_retriggered_while_active():
    """v1.2.9 HP-3 边沿检测: _collapse_active 持续 True → 不重复 apply_event (修 v1.2.8 bug)"""


def test_suppression_l2_wired_in_schedule_loop():
    """v1.2.9 HP-3: schedule_plan_loop 跑 → apply_event('suppression', level) 被调"""


def test_recovery_not_retriggered_while_collapse_active():
    """v1.2.9 修 v1.2.8 bug: collapse 持续期间 trigger_recovery 只调一次 (start_recovery 不重复重置 stage)"""
```

---

## §3 HP-4: `_cumulative_offset` 持久化 ✅ v1.2.7 已做

HP-4 已在 v1.2.7 Task 6 完成: `force_dynamics.restore_offset()` + main.py `_persist_modules` (line 1591) persist + `_load_state` load。本节保留作背景, v1.2.9 不重复。

v1.2.9 HP-1 (§4.2) 让 HP-4 持久化的 offset 有可观测性 (`/reflect` 显示)。

---

## §4 依赖与顺手项

### §4.1 HP-2 (conscience 死代码) ✅ v1.2.7 已做

HP-2 已在 v1.2.7 Task 2 完成: `compute_defense_states` 加 `conscience_pressure` 参数, caller 传 `self._conscience.get_pressure()`。本节保留作背景, v1.2.9 不重复。

**v1.2.9 HP-3 的 suppression 回写 (§2.2) 依赖 HP-2** (conscience_pressure 传真值, 不再用 0.0 死分支)。HP-2 已做, HP-3 可直接传真值。

### §4.2 HP-1: `/reflect_force_current` offset 显示 (v1.2.9 聚焦)

commands.py:660-671 `reflect_force_current` 的 `lines` 列表, 在 "7d:" 段后 (line 670 后, 671 `yield` 前) 加 offset 段。

当前 (commands.py:660-671):
```python
        lines = [
            "ForceState",
            f"natural: {forces['natural']:.2f}",
            f"social: {forces['social']:.2f}",
            f"individual: {forces['individual']:.2f}",
            f"dominant: {dominant}",
            "",
            "7d:",
            f"- silence: {history.get('silence_count_7d', 0)} (main: {history.get('silence_dominant_reason', 'none')})",
            f"- segment: {history.get('segment_count_7d', 0)} (avg {history.get('avg_segment_count', 0):.1f} seg/rep, delay {history.get('avg_delay_seconds', 0):.1f}s)",
        ]
        yield event.plain_result("\n".join(lines))
```

改为 (加 offset 段):
```python
        # v1.2.9 HP-1: 累积 offset 显示 (L2 回写累积, v1.3 L3 激活; 兑现 shift() docstring 承诺)
        offset = self._p._force_dynamics.get_cumulative_offset()

        lines = [
            "ForceState",
            f"natural: {forces['natural']:.2f}",
            f"social: {forces['social']:.2f}",
            f"individual: {forces['individual']:.2f}",
            f"dominant: {dominant}",
            "",
            "7d:",
            f"- silence: {history.get('silence_count_7d', 0)} (main: {history.get('silence_dominant_reason', 'none')})",
            f"- segment: {history.get('segment_count_7d', 0)} (avg {history.get('avg_segment_count', 0):.1f} seg/rep, delay {history.get('avg_delay_seconds', 0):.1f}s)",
            "",
            "Cumulative offset (L2 回写累积, v1.3 L3 激活):",
            f"- natural: {offset.get('natural', 0):.3f}",
            f"- social: {offset.get('social', 0):.3f}",
            f"- individual: {offset.get('individual', 0):.3f}",
        ]
        yield event.plain_result("\n".join(lines))
```

**注意**:
- `self._p._force_dynamics` 已在 commands.py:626 检查非 None, 安全
- `get_cumulative_offset()` 返回 dict (force_dynamics.py:345, HP-4 已确认存在 + 持久化)
- offset 是 L2 累积 (`apply_event` 累加), v1.3 L3 才影响 `compute()`。显示标注 "v1.3 L3 激活" 避免用户困惑 (§9 R4)
- 这兑现 `force_dynamics.shift()` docstring 承诺 ("/reflect_force_current 显示 offset", v1.2.5 审查发现 docstring 撒谎)

**测试** `tests/test_reflect_force_current.py` (新或扩):

```python
def test_reflect_force_current_shows_offset():
    """v1.2.9 HP-1: /reflect_force_current 输出含 'Cumulative offset' + 三力 offset 值"""
    # mock plugin + force_dynamics.get_cumulative_offset 返回 {natural:0.1, social:0.2, individual:0.3}
    # 调 reflect_force_current, 验证输出含 "Cumulative offset" + "natural: 0.100" 等
```

### §4.3 DO-4 (统一 conscience 源) ✅ v1.2.7 已做

DO-4 已在 v1.2.7 Task 2 完成: main.py caller 用 `self._conscience.get_pressure()`。本节保留作背景。

### §4.4 DO-3 (apply_event 顶部 import) ✅ v1.2.7 已做

DO-3 已在 v1.2.7 Task 7 完成: `from ..core.persona_labels_db import get_defense_deltas` 在顶部 (defense_modulator.py:16)。本节保留作背景。

### §4.5 DO-5 (spec drift 标注) ✅ v1.2.7 已做

DO-5 已在 v1.2.7 Task 8 完成: spec drift 注记加到 segmented-reply-fix-design.md。本节保留作背景。

---

## §5 决策点 (历史 + v1.2.9)

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| **D1** | orchestrator.handle 的 conscience_pressure 参数 DO-2 后去留? | (a) 保留向后兼容 / (b) 删除 | ✅ **(a) 保留** (v1.2.9) — 避免改 main.py 签名 + 测试, 标 "DO-2 后未用" |
| **D2** | collapse intensity | `1.0` / 算 tendency | ✅ **`1.0`** (默认采纳) |
| **D3** | suppression 频率 | schedule_plan_loop (1次/天) / diary_loop (2次/天) | ✅ **schedule_plan_loop** (默认采纳, 慢变量 1 次/天够) |
| **D4** | offset per-persona? | 全局 / per-persona | ✅ **全局共享** (HP-4 已做, force_dynamics 全局单例) |
| **D5** | HP-1 顺手? | 是 / 否 | ✅ **是** — 4 行, 15 min, 兑现 docstring + HP-4 可观测 |
| **D6** | collapse 边沿检测 (修 v1.2.8 recovery bug)? | 是 / 否 | ✅ **是** (v1.2.9) — 顺便修 v1.2.8 重复触发 bug, 否则 recovery 永不推进 |
| D7 (历史) | HP-2 纳入? | ✅ 已纳入 (v1.2.7 做) | — |
| D8 (历史) | DO-3/DO-4/DO-5 补进? | ✅ 已补 (v1.2.7 做) | — |

---

## §6 文件清单 (v1.2.9 预计修改)

| 文件 | 改动 | 估行数 |
|---|---|---|
| `emotion_spirit/regulation/defense_modulator.py` | DO-2 加 `compute_silence()` 方法 | +18 |
| `emotion_spirit/output/segmented_reply_orchestrator.py` | DO-2 改调 compute_silence (93-106 简化) | -10 +2 |
| `main.py` | HP-3 suppression 回写 (schedule_plan_loop:867 后) | +15 |
| `emotion_spirit/output/surface_handler.py` | HP-3 collapse 边沿检测 + L2 回写 (278-283 改) | +10 |
| `emotion_spirit/output/commands.py` | HP-1 `/reflect_force_current` offset 显示 (660-671 改) | +8 |
| `tests/test_defense_modulator.py` | compute_silence 测试 | +25 |
| `tests/test_l2_feedback_wiring.py` (新) | HP-3 三子回写 + recovery 边沿测试 | +60 |
| `tests/test_reflect_force_current.py` (新或扩) | HP-1 offset 显示测试 | +15 |
| `UPDATE_HANDBOOK.md` | §6 加 "v1.2.9 已清的债" | +8 |
| `docs/CHANGELOG.md` | v1.2.9 entry | +12 |

**总**: ~120 行 (含 ~100 测试)

---

## §7 测试策略

### 7.1 DO-2

```python
def test_compute_silence_only_does_not_compute_suppression(mocker):
    """compute_silence 不调 suppression.compute / collapse_selector.compute_bas_bis"""
    # mock 三子, 验证只 silence 被调

def test_compute_silence_matches_defense_states_silence_field(mocker):
    """同一输入, compute_silence().score == compute_defense_states().silence_tendency"""
```

### 7.2 HP-3

```python
def test_silence_l2_already_wired():
    """silence 触发 → apply_event('silence') 被调 (v1.2.5 已有, 防回归)"""

def test_collapse_l2_wired_on_trigger():
    """_collapse_active False→True → apply_event('collapse', 1.0) 被调一次"""

def test_collapse_l2_not_retriggered_while_active():
    """_collapse_active 持续 True → 不重复 apply_event (边沿检测)"""

def test_suppression_l2_wired_in_schedule_loop():
    """schedule_plan_loop 跑 → apply_event('suppression', level) 被调"""

def test_recovery_not_retriggered_while_collapse_active():
    """v1.2.9 修 v1.2.8 bug: collapse 持续期间 trigger_recovery 只调一次"""
```

### 7.3 HP-1

```python
def test_reflect_force_current_shows_offset():
    """/reflect_force_current 输出含 'Cumulative offset' + 三力值"""
```

---

## §8 DoD

- [ ] `pytest tests/` 全绿 (1358 + ~15 新 = ~1373 passed, 允许 Win 概率性 test_periodic_save_dirty_only flake)
- [ ] module count 保持 48 (v1.2.9 不加新 @register 模块, handbook §1.2)
- [ ] `force_dynamics.compute()` 签名仍不变 (handbook §1.2 向后兼容)
- [ ] `compute_defense_states` 签名仍不变 (DO-2 加 `compute_silence` 不替换)
- [ ] L2 三子回写全接 (silence + collapse + suppression 各有测试)
- [ ] collapse 边沿检测 (修 v1.2.8 recovery 重复触发 bug)
- [ ] offset 显示在 `/reflect_force_current` (HP-1)
- [ ] **声明**: CHANGELOG 明确标 "v1.2.9 是 L2 脚手架完善, L2 仍不影响 compute() 输出, v1.3 L3 激活" (避免重蹈 v1.2.5 "脚手架当功能" 覆辙)
- [ ] handbook §6 更新 "v1.2.9 已清的债"
- [ ] `docs/CHANGELOG.md` v1.2.9 entry
- [ ] bump 1.2.8→1.2.9 (`_version.py` + `metadata.yaml` + `public_api_stable.md` + `UPDATE_HANDBOOK.md`)
- [ ] memory: [[emotion-spirit-current-truth]] §1 ⚠️ 行对应清除 (HP-3 / DO-2 / HP-1)

---

## §9 风险

| # | 风险 | 处置 |
|---|---|---|
| R1 | DO-2 后 orchestrator 不再算 suppression/collapse, 但 HP-3 回写走低频钩子, 互不打架 | §1.3 已说明, 三子各有落点 |
| R2 | collapse 边沿检测 `_prev_collapse_active` 跨 tick 记忆, plugin 重启丢失 | 接受 (重启后首个 tick 若 curr=True 会回写一次, 可容忍; 或后续持久化 _prev) |
| R3 | suppression 回写用错 conscience (HP-2 未修) | ✅ HP-2 已在 v1.2.7 做, 传真值 |
| R4 | offset 持久化 + 显示但 compute() 不读, 用户困惑"为何没变化" | CHANGELOG + /reflect 显示明示 "v1.3 L3 激活" (HP-1 帮此) |
| R5 | schedule loop 里 compute_defense_states 无 signals/body_state, suppression 值偏差 | 接受 (低频回写, 偏差可容忍) |
| R6 | DO-2 拆 compute_silence 后, v1.3 L3 要用全 DefenseStates 时漏接 | compute_defense_states 保留 + §1.4 标注 "L3/schedule loop 用" |
| R7 | DO-4 行为变更 (conscience 源) 让 suppression 值变, life_simulator 退化 | ✅ v1.2.7 已做 + 跑回归未退化 |
| R8 | collapse 边沿检测改了 v1.2.8 recovery 触发逻辑, 破坏 v1.2.8 测试 | 跑 test_recovery_tracker + surface_handler 全套; 边沿检测是修 bug, 旧测试若依赖重复触发需更新 |
| R9 | DO-2 删 orchestrator 的 `from ... import SilenceTendency` + SilenceTendency 构造, 破坏其他用 SilenceTendency 的地方 | grep 确认 orchestrator 内 SilenceTendency 只这一处用; 其他文件不受影响 |
| **R10** | **v1.2.8 recovery 重复触发 bug** (collapse 期间每 tick 调 start_recovery 重置 stage=0, 恢复永不推进) | ✅ v1.2.9 HP-3 边沿检测修 (§2.3)。若不修, recovery_tracker 永远 stage=0, adapt_plan_for_recovery 永远用第一阶段 |

---

## §10 相关

- [[emotion-spirit-v125-shipped]] — v1.2.5 ship + 审查发现 (本 plan 输入)
- [[emotion-spirit-current-truth]] — §1 ⚠️ 行 = 本 plan 清的债
- [[emotion-spirit-update-handbook]] — §6 清债清单 + §1.2 向后兼容规约
- [[emotion-spirit-v127-status]] — v1.2.8 shipped 状态 (本 plan 前置)
- `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` — v1.2.5 spec (HP-3 接 §4.2 三子回写, v1.2.5 只做了 silence)
- `docs/v126_audit_report.md` — v1.2.6 审计报告 (本 plan 来源)
