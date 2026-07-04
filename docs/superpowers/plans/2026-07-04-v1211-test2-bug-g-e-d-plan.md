# v1.2.11 Bug-G + Bug-E 重修 + Bug-D 补全 Plan(测试版 2,不 push)

> **日期**:2026-07-04
> **前置**:v1.2.10-test-20260704.zip(HEAD `2e419ab`)已实测。反馈见 `C:\Users\Aston\Downloads\2026-07-04-emotion-spirit-v1210test-feedback.md` + `2026-07-04-emotion-spirit-feedback-to-author.md`。
> **实测结论**:Patch A/B 生效 ✅、Bug-F 待 24h 验证 ⏳、Bug-D 只修一半 ❌、**Bug-E 修法方向错了** ❌(混淆 `response.result_chain` 与 `event.get_result()`,event.send 绕过 on_decorating_result)、**新发现 Bug-G(P0)** ❌(tick_pressure 死代码 + _window 累加值 → P95 失效 → 每条对话 critical)。
> **本次范围**:修 Bug-G(P0,方案 A 治本)+ Bug-E 重修(P1,方向 1 append to result_chain,**保留 event_send 接口**待 v1.3+ 接回 delay)+ Bug-D 补成功路径日志。commit 本地,**不 push**,打包 zip 给用户再实测。
> **不做**:不 bump(保持 1.2.10)、不写 CHANGELOG、不 push、不动 Patch A/B/Bug-F(已生效)。
> **auto mode**:已开启,任意读写。

---

## 上下文(实测反馈)

| Bug | 严重度 | 上次状态 | 本次 |
|---|---|---|---|
| Bug-G | **P0** | 新发现(tick_pressure 死代码 → 每条对话 critical) | ✅ 修(方案 A) |
| Bug-E | P1 | 修法方向错(MessageChain([]) 无效,event.send 绕过 on_decorating_result) | ✅ 重修(方向 1 + 保留接口) |
| Bug-D | P3 | 只修一半(成功路径无日志) | ✅ 补全 |
| Patch A/B | — | 生效 | 不动 |
| Bug-F | P2 | 已修,待 24h 验证 | 不动 |

---

## 任务 1:Bug-G — 良心压力死代码(P0,方案 A 治本)

**根因**(已核 `emotion_spirit/regulation/superego/conscience.py`):
1. `tick_pressure(hours)`(line 208)定义了但**零调用方**(grep 全 emotion_spirit + main.py 只有定义)→ `_raw_pressure` 从不衰减,单调递增
2. `_window.append(self._raw_pressure)`(line 96/116/133/150/167/176/212)append 累加值 → 单调序列 P95 ≈ 当前值 → `get_pressure()` line 206 `min(1.0, _raw_pressure / _window_quantile)` = 1.0 永真
3. `pressure_rise_threshold=0.6` 永远被过 → `conscience_pressure_rising` 永触发 → 每条对话 critical + superego reflection diary enqueue

**修法(方案 A)**:① main.py 加 hourly `_decay_tick_loop` 调 `tick_pressure`;② conscience.py 4 个 record 方法的 `_window.append` 改单次增量(record_repair 不 append);③ 加测试。

### 改动 1.1:conscience.py record 方法 _window 改增量语义

文件:`emotion_spirit/regulation/superego/conscience.py`

4 个"事件"record 方法,`_window.append(self._raw_pressure)` 改成 append 单次增量:

- **record_value_conflict**(line 95-96):
  ```python
  self._raw_pressure += abs(conscience_impact)
  # OLD: self._window.append(self._raw_pressure)
  self._window.append(abs(conscience_impact))  # Bug-G v1.2.11: 增量语义 (P95 = 单次事件强度高分位)
  ```

- **record_guard_reflex**(line 115-116):
  ```python
  self._raw_pressure += severity
  self._window.append(severity)  # Bug-G: 增量
  ```

- **record_cascade**(line 132-133):
  ```python
  self._raw_pressure += severity * 0.5
  self._window.append(severity * 0.5)  # Bug-G: 增量
  ```

- **record_collapse**(line 149-150):
  ```python
  self._raw_pressure += 0.8
  self._window.append(0.8)  # Bug-G: 增量
  ```

**record_repair**(line 167 + 176,两个方法):**删掉 `_window.append(self._raw_pressure)`**。理由:repair 是缓解事件(减 _raw_pressure),不是正向事件强度,不该入 P95 window。只保留 `self._raw_pressure = max(0.0, ...)` + `self._window_quantile = 0.0`(失效缓存)。

```python
# record_alignment_repair (line 166-168) + record_repair (line 175-177) 都改成:
self._raw_pressure = max(0.0, self._raw_pressure - relief)
# OLD: self._window.append(self._raw_pressure)
self._window_quantile = 0.0  # 失效缓存, 等下次 get_pressure 重算
```

**tick_pressure**(line 211-212):`_window.append(self._raw_pressure)` **保留不动**(衰减后 append 当前 _raw_pressure 是合理的——记录衰减轨迹,P95 取历史峰值)。或者也改增量语义(append 0 表示"无新事件,仅衰减")。**建议保留**(tick_pressure 是衰减,不是事件,append 当前值让 P95 反映历史压力峰值,归一化 current/peak 有意义)。

### 改动 1.2:main.py 加 _decay_tick_loop

文件:`main.py`

在 `EmotionSpiritPlugin.__init__` 末尾(或现有 `asyncio.ensure_future` 调用附近,如 line 818 `_drain_diary_reflection_loop`)加:

```python
# Bug-G (v1.2.11): conscience pressure hourly decay. tick_pressure 原是死代码
# (_raw_pressure 单调递增 → P95 失效 → 每条对话 critical). 每小时调一次让 _raw_pressure 衰减.
self._last_decay_tick = time.time()
asyncio.ensure_future(self._decay_tick_loop())
```

在类里加 `_decay_tick_loop` 方法(放在 `_drain_diary_reflection_loop` 附近,如 line 1014 后):

```python
async def _decay_tick_loop(self) -> None:
    """Bug-G (v1.2.11): conscience pressure 每小时衰减. tick_pressure 原死代码, 现接线."""
    while True:
        await asyncio.sleep(3600)  # 每小时
        try:
            now = time.time()
            hours = (now - self._last_decay_tick) / 3600.0
            self._last_decay_tick = now
            if hasattr(self, "_conscience") and self._conscience is not None:
                self._conscience.tick_pressure(hours)
                logger.info(
                    "emotion_spirit: conscience pressure decayed hours=%.2f raw=%.3f",
                    hours, self._conscience._raw_pressure,
                )
        except Exception:
            logger.warning("emotion_spirit: conscience decay tick error", exc_info=True)
```

**注意**:`time` 模块——main.py 顶部确认有 `import time`(若无可复用 `_apply_bot_reply_effects` 内的 `import time as _time_mod` 模式,但 loop 用模块级 `import time` 更干净;若 main.py 顶部已 import datetime,加 `import time`)。

### 改动 1.3:Bug-G 测试

新建文件:`tests/test_pressure_decay.py`

```python
"""Bug-G (v1.2.11): conscience pressure 衰减 + _window 增量语义 守护.

原 bug: tick_pressure 死代码 (_raw_pressure 单调递增) + _window.append(累加值)
→ P95 of 单调序列 ≈ 当前值 → get_pressure()=1.0 永真 → 每条对话 critical.

v1.2.11 方案 A: ① tick_pressure 接线 (decay loop, 本测试直接调); ② _window 改增量语义.
用户反馈: 2026-07-04-emotion-spirit-v1210test-feedback.md §4.
"""
from __future__ import annotations

import pytest

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


@pytest.fixture
def tracker() -> ConscienceTracker:
    return ConscienceTracker()


def test_tick_pressure_decays_raw_pressure(tracker: ConscienceTracker):
    """tick_pressure 衰减 _raw_pressure (原死代码, 现应能调)."""
    tracker.record_value_conflict(
        value_name="v1", action="a", conscience_impact=0.8, reason="test",
    )
    raw_before = tracker._raw_pressure
    assert raw_before > 0
    tracker.tick_pressure(1.0)  # 1 小时衰减
    assert tracker._raw_pressure < raw_before, "tick_pressure 应衰减 _raw_pressure"


def test_window_append_delta_not_cumulative(tracker: ConscienceTracker):
    """_window append 单次增量, 不是累加值 (Bug-G 核心修复)."""
    tracker.record_value_conflict(
        value_name="v1", action="a", conscience_impact=0.3, reason="test",
    )
    tracker.record_value_conflict(
        value_name="v2", action="b", conscience_impact=0.5, reason="test",
    )
    # _window 应含 [0.3, 0.5] (增量), 不是 [0.3, 0.8] (累加)
    assert tracker._window[-1] == pytest.approx(0.5), (
        "_window 应 append 单次增量 (0.5), 不是累加值 (0.8)"
    )
    assert tracker._window[-2] == pytest.approx(0.3)


def test_get_pressure_not_always_one(tracker: ConscienceTracker):
    """灌几次小事件 + 衰减后, get_pressure 不应永等于 1.0."""
    for i in range(15):
        tracker.record_value_conflict(
            value_name=f"v{i}", action="a", conscience_impact=0.2, reason="test",
        )
    tracker.tick_pressure(8.0)  # 8 小时衰减 (半衰期 ~8.3h, 衰减约一半)
    p = tracker.get_pressure()
    # 衰减后 _raw_pressure 应远低于 P95 (0.2), get_pressure < 1.0
    assert p < 1.0, f"get_pressure 衰减后应 < 1.0, 实际 {p} (Bug-G 未修?)"


def test_record_repair_does_not_append_window(tracker: ConscienceTracker):
    """record_repair 不入 _window (缓解不是事件强度)."""
    window_before = len(tracker._window)
    tracker.record_repair("simple")
    assert len(tracker._window) == window_before, "record_repair 不应 append _window"
    assert tracker._raw_pressure == 0.0, "record_repair 在 _raw_pressure=0 时减不出负数"
```

**注意**:`record_value_conflict` 的精确签名——小模型确认 `value_name/action/conscience_impact/reason` 参数名(读 conscience.py:77-96)。若签名不同,调整测试调用。`_COLD_START_THRESHOLD`(get_pressure 冷启动 < 10 帧)——`test_get_pressure_not_always_one` 灌 15 次过冷启动。

---

## 任务 2:Bug-E 重修 — 方向 1 append to result_chain(P1,保留 event_send 接口)

**根因**(已核 AstrBot 4.25.6 源码 + meme_manager 源码,上次修法方向错):
- emotion_spirit `on_llm_response` 里 `event.send(MessageChain)` 走 platform adapter 直发(立即发),**绕过 `result_decorate` stage** → meme_manager.on_decorating_result(result_decorate/stage.py:160)没机会注入 image
- 我上次改 `response.result_chain = MessageChain([])` 无效:① meme_manager 读 `event.get_result()`(event._result),不是 `response.result_chain`;② event.send 路径不经 on_decorating_result

**修法(方向 1)**:emotion_spirit 不 `event.send`,改 append segments 到 `response.result_chain`。AstrBot 用 response 构造 event._result(internal.py:362-363)→ result_decorate stage 跑 on_decorating_result → meme_manager 注入 image → AstrBot send(segments + image)。
- **代价**:失去段间 delay(segments 一次性 send,无 asyncio.sleep 间隔)
- **保留接口**:`delivery_mode` config 切换。默认 `"append"`(保表情包,失 delay);`"event_send"` 保留旧行为(保 delay,失表情包)。v1.3+ 待 AstrBot 加 `event.send_delayed(parts, delays)` API,可实现 `"delayed_append"`(append + delay,两全)。

### 改动 2.1:_conf_schema.json 加 delivery_mode

文件:`_conf_schema.json`

在 `segmented_reply.enable`(line 387)后加:

```json
"delivery_mode": {
  "description": "分段回复投递模式。append(默认): segments 追加到 result_chain, 经 on_decorating_result 钩子 → 兼容 meme_manager 表情包, 但失去段间 delay; event_send: 逐段 event.send + delay, 保留打字节奏, 但绕过 on_decorating_result → 表情包消失 (Bug-E 旧行为). v1.3+ 待 AstrBot send_delayed API 后可加 delayed_append 两全.",
  "type": "string",
  "default": "append",
  "enum": ["append", "event_send"]
},
```

**注意**:JSON 逗号——加在 `enable` 块之后,确保前一块有逗号或本块末尾逗号正确。

### 改动 2.2:orchestrator handle 改 delivery_mode 分支

文件:`emotion_spirit/output/segmented_reply_orchestrator.py`

**现状**(HEAD `2e419ab`,上次 Bug-E 修错版):line 143-168 是 `event.send` 分段 + `response.result_chain = MessageChain([])`。

**改法**:在 plan 生成后(line 140 `if not plan: return` 后),把"逐段 send + 清 result_chain"段改成 `delivery_mode` 分支:

```python
            if not plan:
                return

            # Bug-E v1.2.11 方向 1: delivery_mode 切换 (保留 event_send 接口, 默认 append).
            delivery_mode = seg_config.get("delivery_mode", "append")

            # Bug-D v1.2.11: 成功路径日志 (补全, 见任务 3)
            logger.info(
                "emotion_spirit: segmented_reply user=%s mode=%s segments=%d chars=%d total_delay=%.1fs",
                user_id[:8], delivery_mode, len(plan),
                sum(len(p["text"]) for p in plan),
                sum(p.get("delay_before_seconds", 0.0) for p in plan),
            )

            if delivery_mode == "event_send":
                # 旧路径 (保留接口): event.send 分段 + delay. 保 delay, 失表情包 (Bug-E 旧行为).
                # v1.3+ 待 AstrBot send_delayed API, 可实现 delayed_append (append + delay, 两全).
                try:
                    await event.send(MessageChain([Plain(plan[0]["text"])]))
                    for part in plan[1:]:
                        delay = part.get("delay_before_seconds", 0.0)
                        if delay > 0:
                            await asyncio.sleep(delay)
                        await event.send(MessageChain([Plain(part["text"])]))
                except Exception:
                    logger.warning(
                        "emotion_spirit: segmented_reply send failed, some segments may be missing",
                        exc_info=True,
                    )
                response.completion_text = ""
                response.result_chain = MessageChain([])  # 防 double-send
            else:
                # 新路径 (默认, Bug-E v1.2.11 方向 1): append segments 到 response.result_chain.
                # AstrBot 走默认 send (经 result_decorate → on_decorating_result → meme_manager 注入 image).
                # 代价: 失段间 delay (一次性 send). 用户反馈 §2.
                if response.result_chain is None:
                    response.result_chain = MessageChain([])
                for part in plan:
                    response.result_chain.chain.append(Plain(part["text"]))
                response.completion_text = ""  # 防 AstrBot 追加默认链
                # 不 event.send, 不清 result_chain (让 on_decorating_result 处理)
```

**注意**:
- `Plain` + `MessageChain` import 已在 handle 开头(line 88-89,上次 Bug-E 修法提上来的),两分支都能用 ✅
- `asyncio` 已 import(orchestrator 顶部 line 14)
- 保留原 `# --- 6. 清空 completion_text (Bug 12b...) ---` 注释段——它现在在 `event_send` 分支内,改注释说明"event_send 模式防 double-send;append 模式在 else 分支处理"
- 删掉原 line 161-168 的"清空 llm_resp"段(已被上面 if/else 替代)
- `record_response_event` + `record_segment_event`(原 line 166-172)**保留不动**——两种模式都该推进冷却 + 记录历史。确保它们在 if/else 之后(两分支都执行)

### 改动 2.3:Bug-E 测试更新

文件:`tests/test_bug_e_result_chain.py`

旧测试(上次修错版)验证 `result_chain != None + = MessageChain([])`。方向 1 改后,append 模式不清 result_chain,旧测试会失败。**更新成验证 delivery_mode + append 逻辑**:

```python
"""Bug-E (v1.2.11 方向 1): orchestrator delivery_mode + append to result_chain 守护.

原 Bug-E 修法 (result_chain=MessageChain([])) 方向错 — event.send 绕过 on_decorating_result,
meme_manager 读 event.get_result() 不是 response.result_chain. 方向 1: 不 event.send,
改 append segments 到 response.result_chain, 让 AstrBot 默认 send 经 on_decorating_result.

保留 event_send 接口 (delivery_mode config), v1.3+ 待 AstrBot send_delayed API 接回 delay.

源码守护 (不调 handle, 避免 astrbot.core.message import 依赖).
用户反馈: 2026-07-04-emotion-spirit-v1210test-feedback.md §2.
"""
from __future__ import annotations

from pathlib import Path

_ORCH = Path(__file__).parent.parent / "emotion_spirit/output/segmented_reply_orchestrator.py"


def test_orchestrator_has_delivery_mode_branch():
    """orchestrator 应读 delivery_mode config (默认 append)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert 'delivery_mode' in source, "orchestrator 应支持 delivery_mode config (Bug-E 方向 1)"
    assert 'seg_config.get("delivery_mode"' in source or "seg_config.get('delivery_mode'" in source


def test_orchestrator_has_append_branch():
    """orchestrator 应有 append 模式 (segments → result_chain.chain.append)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert "response.result_chain.chain.append(Plain(" in source, (
        "append 模式应 append segments 到 result_chain.chain (Bug-E 方向 1)"
    )


def test_orchestrator_keeps_event_send_interface():
    """保留 event_send 接口 (delivery_mode='event_send' 走旧 event.send 路径)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert 'delivery_mode == "event_send"' in source or "delivery_mode == 'event_send'" in source, (
        "应保留 event_send 分支 (接口, v1.3+ 待 send_delayed API 接回 delay)"
    )
    assert "await event.send(MessageChain([Plain(plan[0][\"text\"])]))" in source, (
        "event_send 分支应保留 event.send 分段逻辑"
    )


def test_append_mode_does_not_clear_result_chain():
    """append 模式不清 result_chain (让 on_decorating_result 处理)."""
    source = _ORCH.read_text(encoding="utf-8")
    # event_send 分支有 result_chain=MessageChain([]) 防 double-send, append 分支不应有
    # 简单守护: result_chain = MessageChain([]) 出现次数应 == 1 (仅 event_send 分支)
    count = source.count("response.result_chain = MessageChain([])")
    assert count == 1, f"result_chain=MessageChain([]) 应仅在 event_send 分支出现 1 次, 实际 {count} 次"
```

---

## 任务 3:Bug-D 补全 — orchestrator 成功路径日志(P3)

**根因**:上次只改了 `on_llm_response` 入口日志(main.py:1441 info),orchestrator `handle()` 成功 send 路径(L143-168)一行 log 都没有。用户看不到"分了几段/共几字/总延迟"。

**修法**:在 plan 生成后、delivery_mode 分支前加 1 行 `logger.info`。**已含在任务 2.2 的改法里**(delivery_mode 分支前的 logger.info)——见改动 2.2 的 `# Bug-D v1.2.11: 成功路径日志` 段。

即任务 2.2 改法已包含 Bug-D 修复。无需额外改动。

**验证**:`grep -n "segmented_reply user=" emotion_spirit/output/segmented_reply_orchestrator.py` 应命中 1 处(logger.info)。

---

## 任务 4:测试

### 改动 4.1:跑全套

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
python -m pytest tests/ -q --tb=short
```

**期望**:
- Bug-G 新测试 4 个全过(test_pressure_decay)
- Bug-E 更新测试 4 个全过(test_bug_e_result_chain 更新版)
- 既有测试全过(1388 baseline + 4 Bug-G - 旧 Bug-E 守护调整 ≈ 1390 左右)
- `test_periodic_save_dirty_only` 仍偶发 Win flake(v1.2.6 backlog,非回归)

**如有红**:
- `test_get_pressure_not_always_one` 失败 → get_pressure 衰减后仍 = 1.0,说明方案 A Step 2(改 _window 增量)后 `_raw_pressure / P95(单次)` 仍 > 1。**备选**:只做 Step 1(调 tick_pressure,不改 _window 语义,保留 _window.append(_raw_pressure)),让 P95 = 历史峰值,current 衰减后 < 峰值。或调 get_pressure 公式(方案 C,排期 v1.3)。
- `test_record_repair_does_not_append_window` 失败 → record_repair 还有 append,确认两处都删
- Bug-E 旧测试残留 → 确认 test_bug_e_result_chain.py 已整体替换为新版

### 改动 4.2:Bug-D 验证(轻量)

```bash
grep -n "segmented_reply user=" emotion_spirit/output/segmented_reply_orchestrator.py
```
应命中 1 处 logger.info(成功路径日志)。

---

## 任务 5:commit(本地,不 push)

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git status
git add -A
git commit -m "fix(v1.2.11-test2): Bug-G pressure decay + Bug-E redo (append mode) + Bug-D log (test build, NOT pushed)

Bug-G (P0): tick_pressure 死代码接线 (hourly _decay_tick_loop) + _window 改增量语义
  (4 处 record 方法 append 单次增量, record_repair 不 append). 修每条对话 critical.
Bug-E (P1) 重修: 方向 1 — delivery_mode config (默认 append: segments → result_chain,
  经 on_decorating_result → meme_manager 表情包; 保留 event_send 接口待 v1.3+ send_delayed API).
  上次 MessageChain([]) 修法方向错 (event.send 绕过 on_decorating_result).
Bug-D (P3) 补全: orchestrator 成功路径加 logger.info (segments/chars/delay).

测试版, 不 push, 不 bump. 等用户 AstrBot 实测 Bug-G + Bug-E 方向 1 后 bump+ship v1.2.11.
用户反馈: 2026-07-04-emotion-spirit-v1210test-feedback.md + feedback-to-author.md"
```

**⚠️ 不要 `git push`**。本地 commit 即可。

---

## 任务 6:总结报告

新建文件:`docs/v1.2.11-test2-build-report.md`

内容模板:
```markdown
# v1.2.11 测试版 2 构建报告(2026-07-04, 不 push)

## 范围
本次为测试版 2,修 Bug-G(P0 新发现)+ Bug-E(重修,方向 1)+ Bug-D(补全)。**不 push,不 bump,不写 CHANGELOG**。
等用户 AstrBot 实测通过后,单独 bump v1.2.11 + CHANGELOG + push ship。

HEAD: `git rev-parse HEAD` 填入

## 改动清单

### Bug-G(P0,方案 A 治本)
- conscience.py: 4 处 record 方法 _window.append 改增量 (record_value_conflict/guard_reflex/cascade/collapse)
- conscience.py: record_repair 两处删 _window.append (缓解不是事件强度)
- main.py: 加 _decay_tick_loop (hourly 调 tick_pressure) + __init__ 起 asyncio.ensure_future
- 守护: test_pressure_decay.py (4 tests)
- 根因: tick_pressure 死代码 + _window 累加值 → P95 失效 → 每条对话 critical

### Bug-E(P1,方向 1 重修 + 保留接口)
- orchestrator.py: delivery_mode config 分支 (默认 append, 保留 event_send)
- _conf_schema.json: 加 delivery_mode (enum: append/event_send, default append)
- append 模式: segments → response.result_chain.chain.append(Plain), 不 event.send, 经 on_decorating_result
- event_send 模式 (保留接口): 旧 event.send + delay + result_chain=MessageChain([]), v1.3+ 待 send_delayed API
- 守护: test_bug_e_result_chain.py 更新 (4 tests, 验证 delivery_mode + append + 保留 event_send)
- 根因: 上次修法方向错 (response.result_chain ≠ event.get_result(), event.send 绕过 on_decorating_result)

### Bug-D(P3,补全)
- orchestrator.py: 成功路径加 logger.info (user/mode/segments/chars/total_delay)
- 已含在 Bug-E 改法 (delivery_mode 分支前)

## 测试
- pytest tests/ 全套: <填入数字> passed
- 新增: Bug-G 4 + Bug-E 更新 4 = 8 新/更新测试
- 已知: test_periodic_save_dirty_only Win flake (v1.2.6 backlog, 非回归)

## 不做清单
- ❌ git push (本地 commit only)
- ❌ bump 版本号 (保持 1.2.10)
- ❌ CHANGELOG.md

## 实测后后续(另一任务)
1. 用户丢 zip 到 AstrBot 实测:
   - Bug-G: 每条对话不再 critical (docker logs grep "level=critical" 应为 0 或极少)
   - Bug-E 方向 1: segmented_reply.enable=true + delivery_mode=append → 表情包回来 (放弃段间 delay, 一次性 send)
   - Bug-E event_send 模式: delivery_mode=event_send → 保留 delay 但表情包消失 (旧行为, 接口保留)
   - Bug-D: docker logs 看到 "segmented_reply user=... mode=... segments=... chars=... delay=..."
2. 若 Bug-G 实测仍 critical → 备选: 只做 Step 1 (不改 _window 语义) 或调 get_pressure 公式
3. 若 Bug-E append 模式表情包仍不回 → 深入查 result_decorate stage 是否真的跑 on_decorating_result
4. 实测通过 → bump v1.2.11 + CHANGELOG + push ship
5. v1.3: Bug-F memory_type + Bug-E delayed_append (待 AstrBot send_delayed API)
```

填入实际测试数字 + HEAD hash 后保存。

---

## 任务 7:本地打包 zip

**前置**:任务 5 已 commit(本地)。

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git log --oneline -1  # 确认 HEAD 是 test2 commit
git archive --prefix=astrbot_plugin_emotion_spirit/ --format=zip -o ../emotion_spirit-v1.2.10-test2-20260704.zip HEAD
python -c "
import zipfile
z = zipfile.ZipFile('../emotion_spirit-v1.2.10-test2-20260704.zip')
names = z.namelist()
print('文件数:', len(names))
print('含 main.py:', any('main.py' in n and not n.endswith('.pyc') for n in names))
print('含 orchestrator.py:', any('segmented_reply_orchestrator.py' in n for n in names))
print('含 conscience.py:', any('conscience.py' in n for n in names))
print('含 _conf_schema.json:', any('_conf_schema.json' in n for n in names))
print('含 KB json (3):', sum(1 for n in names if 'kb/' in n and n.endswith('.json')))
print('排除 tests/:', not any('/tests/' in n for n in names))
print('排除 docs/:', not any('/docs/' in n for n in names))
"
ls -lh ../emotion_spirit-v1.2.10-test2-20260704.zip
```

**zip 路径**:`D:/新建文件夹/emotion_spirit/now/emotion_spirit-v1.2.10-test2-20260704.zip`。

---

## 不做清单(明确)

- ❌ `git push`(本地 commit only,等用户实测)
- ❌ bump `_version.py` / `metadata.yaml`(保持 1.2.10)
- ❌ 写 `CHANGELOG.md`(等 bump 时写)
- ❌ 改 Patch A/B/Bug-F 代码(已生效,本次不动)
- ❌ 改 `release.yml` / CI

---

## 实测后后续(用户实测通过后,另一任务)

1. **bump v1.2.11**:`_version.py` + `metadata.yaml` → 1.2.11
2. **写 CHANGELOG**:v1.2.11 条目(Patch A/B + Bug-D/E/F/G)
3. **commit + tag v1.2.11 + push**:触发 release.yml
4. **v1.3 待办**:Bug-F memory_type + Bug-E delayed_append(待 AstrBot send_delayed API)
5. **更新 memory**:新建 v1.2.11-shipped memory + 更新 current-truth

---

## 关键源码参考

- emotion_spirit `conscience.py`:`emotion_spirit/regulation/superego/conscience.py`(tick_pressure:208, get_pressure:187-206, record_*:77-180)
- emotion_spirit `main.py` conscience 访问:`self._conscience = self._modules["superego"]["conscience"]`(line 301)
- emotion_spirit `orchestrator.py`:`emotion_spirit/output/segmented_reply_orchestrator.py`(handle, plan 生成后改 delivery_mode 分支)
- AstrBot `on_decorating_result` 调用点:`D:\python\Lib\site-packages\astrbot\core\pipeline\result_decorate\stage.py:160`
- AstrBot `event.send` 绕过 on_decorating_result:`D:\python\Lib\site-packages\astrbot\core\platform\astr_message_event.py:475-493`(只设 _has_send_oper,走 platform adapter 直发)
- AstrBot `LLMResponse.result_chain → event._result`:`D:\python\Lib\site-packages\astrbot\core\pipeline\process_stage\method\agent_sub_stages\internal.py:362-366`
- meme_manager `on_decorating_result` 早退点:`C:\Users\Aston\Downloads\Compressed\meme_manager\main.py:1263-1265`
- 用户反馈:`C:\Users\Aston\Downloads\2026-07-04-emotion-spirit-v1210test-feedback.md` §2(Bug-E)/§4(Bug-G)/§3(Bug-D)
