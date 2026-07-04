# v1.3.0 rc.3: Bug-E/H framework 防护 + Bug-F memory_type 彻底修 Plan

> **日期**:2026-07-04
> **前置**:rc.1(handbook §1.7)+ rc.2(Bug-G ConscienceTracker 双通道)已 commit(`7869caa`),1407 passed,未 push。
> **本 rc.3 范围**:Bug-E/H(framework bug,emotion_spirit 侧防护 + 诊断 + push 上游)+ Bug-F(memory_type 字段彻底修,替 token filter "不入 pool")。
> **不做**:不 push(等 v1.3.0 后续 + ship)、不 bump、不改 Patch A/B/D(已在 test2 commit,合入 v1.3.0)。
> **auto mode**:已开启,任意读写。

---

## 上下文

| Bug | 严重度 | 状态 | rc.3 处理 |
|---|---|---|---|
| Bug-E | P1 | test2 append 撞 Bug-H,event_send 失图 | emotion_spirit 侧防护(默认 event_send)+ push framework |
| Bug-H | P0 | framework respond.stage:287 Reply/At 检查,append 模式经默认 send 撞 bug | emotion_spirit 侧防护 + 诊断 log + push AstrBot 上游 |
| Bug-F | P2 | token filter 临时修(不入 pool) | ✅ memory_type 字段彻底修(标类型入 pool + 召回过滤) |

**Bug-E/H 根因**(test2 实测 + framework 源码确认):append 模式经 framework 默认 send(result_decorate + respond.stage),framework 某处把 emotion_spirit 的 [Plain] 换成 [Reply(placeholder)] → respond.stage:287 skip send → bot 不回复。event_send 模式走 platform adapter 直发绕过 respond.stage(能发但失表情包)。两全需 AstrBot 加 `send_delayed(parts, delays)` API(framework 改动,非 emotion_spirit 能解)。

**Bug-F 根因**:_apply_bot_reply_effects 无差别把 bot_text 写进 warm pool,bot ephemeral state("我刚到")和 long-term fact("我喜欢火锅")都入,召回注入 system_prompt → 上下文错乱。token filter(test1)硬编码词表"不入 pool",治标不治本(漏判/误判 + ephemeral 完全不记录)。

---

## 任务 1:Bug-E/H emotion_spirit 侧防护

### 改动 1.1:delivery_mode 默认 append → event_send

**文件**:`_conf_schema.json`(line 453-456 附近)

```json
"delivery_mode": {
  "description": "分段回复投递模式。event_send(默认): 逐段 event.send + delay, 保回复 + 打字节奏, 但绕过 on_decorating_result → 表情包消失 (Bug-E 旧行为). append: segments → result_chain, 经 on_decorating_result → 兼容表情包, 但撞 AstrBot framework bug (Bug-H: respond.stage:287 Reply/At 检查 skip send → bot 不回复). append 模式有诊断 log, 等 AstrBot 修 Bug-H + 加 send_delayed API 后可启用. v1.3.0 rc.3 默认改 event_send (Bug-H 让 append 不可用).",
  "type": "string",
  "default": "event_send",
  "enum": ["event_send", "append"]
}
```

**注意**:default 从 `"append"` 改 `"event_send"`。enum 顺序也调(event_send 在前,体现是默认)。

### 改动 1.2:orchestrator append 模式加诊断 log

**文件**:`emotion_spirit/output/segmented_reply_orchestrator.py`(append 分支)

在 append 分支末尾(`response.result_chain.chain.append(Plain(...))` 循环后,`response.completion_text = ""` 前)加 sanity log:

```python
# Bug-H (v1.3.0 rc.3): 诊断 log — append 后 chain 内容, 给 framework 调试.
# 实测 framework 某处把 [Plain] 换成 [Reply(placeholder)] → respond.stage:287 skip.
# 此 log 确认 emotion_spirit 写入的 chain 是否含 Plain (定位 framework 替换点).
logger.info(
    "emotion_spirit: append mode result_chain id=%s chain=%s",
    id(response.result_chain),
    [(type(c).__name__, getattr(c, "text", "")[:30]) for c in response.result_chain.chain],
)
```

**注意**:import logger 确认在 orchestrator 顶部(已有 `logger`)。此 log 在 append 模式每次跑都打(INFO),帮 framework 调试 + 未来 framework 修后确认 chain 流转。

### 改动 1.3:framework issue 文档(给用户提 AstrBot 上游)

**新建**:`docs/framework-issue-bug-h.md`(docs/ 不进 zip,export-ignore)

```markdown
# AstrBot Framework Issue — Bug-H reply preservation + send_delayed API

## Bug-H: respond.stage:287 Reply/At 检查误杀 emotion_spirit append chain

**环境**:AstrBot 4.26.4 Docker + emotion_spirit v1.3.0 rc.2 (append 模式)
**现象**:emotion_spirit append 模式 (segments → response.result_chain.chain.append(Plain)) → bot 完全不回复. AstrBot 报:
\`\`\`
[respond.stage:287] 消息链全为 Reply 和 At 消息段, 跳过发送阶段。chain:
[Reply(type=..., id='...', chain=[], sender_id=0, sender_nickname='', time=0, ...)]
\`\`\`
**期望**:chain 应含 emotion_spirit 写入的 Plain segments, 不该是 [Reply(placeholder)].

**静态分析**:
- emotion_spirit.on_llm_response append Plain 到 response.result_chain (LLMResponse)
- on_agent_done 传的 llm_response 跟 get_final_llm_resp() 同一对象 (self.final_llm_resp, coze:324+377 / dashscope:359+402 确认)
- aggregator.finalize (third_party.py:104-119): result_chain 非 None → final_chain = result_chain.chain (应读到 Plain)
- event.set_result(chain=final_chain) → result_decorate → respond.stage:287
- 实测 respond.stage 看到 [Reply(placeholder)] 而非 [Plain] → framework 在 aggregator → respond.stage 之间替换了 chain

**诊断 log (emotion_spirit 侧已加, rc.3)**:append 后 log chain 内容 + id(response). 若 emotion_spirit 写入含 Plain 但 framework 端读到 [Reply] → 确认 framework 替换.

**诉求**:定位 framework 哪个 stage 把 [Plain] 换成 [Reply(placeholder)] (placeholder: chain=[], sender_id=0, time=0). 可能是 result_decorate 或 set_result 覆盖.

## send_delayed API 需求 (Bug-E 两全)

**背景**:emotion_spirit 分段回复 + meme_manager 表情包冲突.
- event_send 模式: 逐段 event.send + delay → 保打字节奏, 但绕过 on_decorating_result → meme_manager 表情包消失.
- append 模式: segments → result_chain → 经 on_decorating_result → 表情包回来, 但撞 Bug-H + 失段间 delay.

**诉求**:AstrBot 加 \`event.send_delayed(parts, delays)\` API:
\`\`\`python
await event.send_delayed(
    parts=[MessageChain([Plain(seg1)]), MessageChain([Plain(seg2)]), ...],
    delays=[0.0, 1.5, 1.0],
)
\`\`\`
**语义**:每段延迟发 + 每段都触发 on_decorating_result (让 meme_manager append image). 这样 emotion_spirit 可同时保 delay + 表情包.
```

**注意**:此文档不进 zip(docs/ export-ignore)。用户手动提 issue 给 AstrBot 上游。

---

## 任务 2:Bug-F memory_type 字段彻底修

### 改动 2.1:UnifiedEntry 加 memory_type 字段

**文件**:`emotion_spirit/memory/memory_pool.py`(或 UnifiedEntry 定义处)

UnifiedEntry dataclass 加字段:
```python
memory_type: str = "bot_reply"  # v1.3.0 rc.3 Bug-F: bot_reply / bot_ephemeral_state / bot_long_term_fact / user_fact
```

**注意**:确认 UnifiedEntry 定义位置(memory_pool.py 或 memory/models.py)。`@dataclass` 加字段带默认值,向后兼容。memory_type 值域:
- `bot_reply`(默认):普通 bot 回复
- `bot_ephemeral_state`:bot 短期状态("我刚到/我准备出门")
- `bot_long_term_fact`:bot 长期事实("我喜欢火锅")
- `user_fact`:用户事实(用户消息)

### 改动 2.2:add_for_user 加 memory_type 参数

**文件**:`emotion_spirit/memory/memory_pool.py`(line 142-146)

```python
def add_for_user(self, user_id: str, text: str, raw_weight: float, phi: float,
                 tags: list, source_user: str, privacy: str = "private",
                 entities: dict | None = None,
                 memory_type: str = "bot_reply",  # v1.3.0 rc.3 Bug-F
                 ) -> UnifiedEntry:
    return self.add(text, raw_weight, phi, tags, source_user,
                    participants={user_id}, privacy=privacy, entities=entities,
                    memory_type=memory_type)
```

**注意**:`self.add(...)` 也要加 memory_type 参数 + 传给 UnifiedEntry 构造。确认 add(line 84+)签名 + UnifiedEntry 构造。

### 改动 2.3:_apply_bot_reply_effects 标 memory_type(替 token filter "不入 pool")

**文件**:`main.py`(`_apply_bot_reply_effects`,line ~1493-1505)

```python
def _apply_bot_reply_effects(self, user_id: str, bot_text: str, tone: str, weight: float) -> None:
    """Bot 回复副作用: 写 memory + 更新 intimacy + reflex learn.

    v1.3.0 rc.3 Bug-F: 用 memory_type 标记 (替 v1.2.11 token filter "不入 pool").
    bot ephemeral state (含 "我刚到/我准备" 等词) → memory_type="bot_ephemeral_state"
    (仍入 pool 记录, 但召回时过滤, 不污染上下文). 其他 bot reply → "bot_reply".
    """
    head = bot_text[:200]
    if any(tok in head for tok in _EPHEMERAL_BOT_TOKENS):
        memory_type = "bot_ephemeral_state"
        logger.debug(
            "emotion_spirit: ephemeral bot-state tagged user=%s head=%r",
            user_id[:8], head[:50],
        )
    else:
        memory_type = "bot_reply"

    self._pool.add_for_user(
        user_id=user_id, text=bot_text[:500], raw_weight=weight,
        phi=0.4, tags=["bot_reply", tone], source_user="bot",
        memory_type=memory_type,  # v1.3.0 rc.3 Bug-F
    )
    # ... intimacy + reflex + last_bot_reply_time 不变 ...
```

**关键改动**:旧逻辑是 `if ephemeral: 不入 pool`(token filter 拦截)。新逻辑是 `if ephemeral: 标 memory_type=bot_ephemeral_state 仍入 pool`。ephemeral 仍记录(诊断/其他用途),但召回时过滤(不注入 system_prompt)。

**保留 `_EPHEMERAL_BOT_TOKENS`**:用于判定 ephemeral(标 memory_type),不再"不入 pool"。注释更新。

### 改动 2.4:search_by_vector 加 exclude_memory_types 过滤

**文件**:`emotion_spirit/memory/memory_pool.py`(line 425-442)

```python
def search_by_vector(
    self,
    query_vec: tuple[float, float, float],
    top_k: int = 5,
    tier: str | None = None,
    user_id: str | None = None,
    exclude_memory_types: set[str] | None = None,  # v1.3.0 rc.3 Bug-F
) -> list[tuple[str, float]]:
    results: list[tuple[str, float]] = []
    for entry_id, vec in self._vector_index.items():
        if tier is not None or user_id is not None or exclude_memory_types is not None:
            entry = self._find_entry_by_id(entry_id)
            if entry is None:
                continue
            if tier is not None and entry.tier != tier:
                continue
            if user_id is not None and user_id not in entry.participants:
                continue
            # v1.3.0 rc.3 Bug-F: 召回时过滤 ephemeral state (不注入 system_prompt)
            if exclude_memory_types is not None and getattr(entry, "memory_type", "bot_reply") in exclude_memory_types:
                continue
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec, query_vec)))
        results.append((entry_id, dist))
    results.sort(key=lambda x: x[1])
    return results[:top_k]
```

**注意**:`getattr(entry, "memory_type", "bot_reply")` 兜底(旧 entry 无 memory_type 字段 → 默认 bot_reply,不过滤)。

### 改动 2.5:召回端传 exclude_memory_types

**文件**:`emotion_spirit/memory/memory_pool.py`(line 268,search_by_vector 调用方)+ `emotion_spirit/agents/memory_agent.py`(retrieve)

召回链:memory_agent.retrieve → memory_pool.search_by_vector(line 268)→ results → memory_agent payload → main.py:1423 注入。

在 search_by_vector 调用处(line 268)加 `exclude_memory_types={"bot_ephemeral_state"}`:

```python
# memory_pool.py:268 (search_by_vector 调用方, 在 retrieve 或 search 方法内)
raw = self._memory.search_by_vector(
    query_vec, top_k=k, user_id=current_user,
    exclude_memory_types={"bot_ephemeral_state"},  # v1.3.0 rc.3 Bug-F
)
```

**注意**:确认 line 268 在哪个方法(retrieve/search)。所有"召回注入 system_prompt"的路径都该过滤 bot_ephemeral_state。**诊断路径(get_pressure_breakdown / view_diary 等)不过滤**(ephemeral 仍可查)。

### 改动 2.6:to_dict/from_dict 加 memory_type(§1.5)

**文件**:`emotion_spirit/memory/memory_pool.py`(line 694/708)

to_dict:UnifiedEntry 序列化加 `memory_type`。from_dict:反序列化读 `memory_type`,旧数据无此字段兜底 `"bot_reply"`。

**注意**:确认 UnifiedEntry 的 to_dict/from_dict(或 MemoryPool 的 entry 序列化)。`data.get("memory_type", "bot_reply")` 兜底。

---

## 任务 3:测试

### 改动 3.1:test_delivery_mode_default

**新建**:`tests/test_delivery_mode_default.py`

```python
"""Bug-E/H (v1.3.0 rc.3): delivery_mode 默认 event_send 守护.

Bug-H (framework reply preservation) 让 append 模式不可用 (bot 不回复).
v1.3.0 rc.3 默认改 event_send (保回复, 失表情包, 等 framework send_delayed API).
"""
from __future__ import annotations
import json
from pathlib import Path

_SCHEMA = Path(__file__).parent.parent / "_conf_schema.json"


def test_delivery_mode_default_is_event_send():
    """delivery_mode 默认应为 event_send (Bug-H 让 append 不可用)."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    seg = schema.get("segmented_reply", {})
    dm = seg.get("delivery_mode", {})
    assert dm.get("default") == "event_send", (
        "delivery_mode 默认应为 event_send — Bug-H (framework) 让 append 不可用 (bot 不回复). "
        "等 AstrBot 修 Bug-H + 加 send_delayed API 后可改回 append."
    )
    assert "event_send" in dm.get("enum", [])
    assert "append" in dm.get("enum", [])  # append 保留 (接口, 待 framework 修)
```

### 改动 3.2:test_memory_type

**新建**:`tests/test_memory_type.py`

```python
"""Bug-F (v1.3.0 rc.3): memory_type 字段 + 召回过滤 守护.

v1.2.11 token filter "不入 pool" 治标. v1.3.0 rc.3 改 memory_type:
bot ephemeral state 标类型仍入 pool (记录), 召回时过滤 (不注入 system_prompt).
"""
from __future__ import annotations

import pytest

from emotion_spirit.memory.memory_pool import MemoryPool
from main import _EPHEMERAL_BOT_TOKENS


@pytest.fixture
def pool() -> MemoryPool:
    return MemoryPool()


def test_add_for_user_has_memory_type_param():
    """add_for_user 接受 memory_type 参数."""
    import inspect
    sig = inspect.signature(MemoryPool.add_for_user)
    assert "memory_type" in sig.parameters, "add_for_user 应接受 memory_type (Bug-F)"


def test_ephemeral_bot_state_tagged_not_skipped():
    """bot ephemeral state 仍入 pool (标 memory_type, 不再 '不入 pool')."""
    # 通过 _apply_bot_reply_effects 间接测, 或直接 add_for_user
    pool = MemoryPool()
    pool.add_for_user(
        user_id="u1", text="我刚到门口", raw_weight=0.5, phi=0.4,
        tags=["bot_reply", "warm"], source_user="bot",
        memory_type="bot_ephemeral_state",
    )
    # 应入 pool (不跳过)
    assert len(pool.warm) + len(pool.buffer) > 0, "ephemeral 应入 pool (标类型, 不再跳过)"


def test_search_by_vector_excludes_ephemeral():
    """召回时 exclude_memory_types 过滤 bot_ephemeral_state."""
    pool = MemoryPool()
    # 灌两条: ephemeral + long-term
    pool.add_for_user("u1", "我刚到门口", 0.5, 0.4, ["bot_reply"], "bot",
                      memory_type="bot_ephemeral_state")
    pool.add_for_user("u1", "我喜欢火锅", 0.5, 0.4, ["bot_reply"], "bot",
                      memory_type="bot_long_term_fact")
    # 召回 (query_vec 用任意, 因 MemoryPool 向量是 3-tuple)
    results_all = pool.search_by_vector((0.5, 0.5, 0.5), top_k=10, user_id="u1")
    results_filtered = pool.search_by_vector(
        (0.5, 0.5, 0.5), top_k=10, user_id="u1",
        exclude_memory_types={"bot_ephemeral_state"},
    )
    # 过滤后应少 (ephemeral 被排除)
    assert len(results_filtered) < len(results_all), "exclude_memory_types 应过滤 ephemeral"
    assert len(results_filtered) >= 1, "long-term fact 应保留"


def test_ephemeral_tokens_still_used_for_tagging():
    """_EPHEMERAL_BOT_TOKENS 保留 (用于标 memory_type, 不再 '不入 pool')."""
    assert len(_EPHEMERAL_BOT_TOKENS) >= 10, "token 列表保留 (判定 ephemeral 用)"
```

**注意**:`test_search_by_vector_excludes_ephemeral` 的 query_vec 用 `(0.5, 0.5, 0.5)` 占位(MemoryPool 向量是 3-tuple)。确认 MemoryPool 向量维度 + search_by_vector 行为。若 entry 入 pool 后在 buffer(未 promote warm),search 可能查不到 — 小模型确认 entry tier + search 路径,可能需 `confirm_check` promote 或直接测 warm。

### 改动 3.3:跑全套测试

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
python -m pytest tests/ -q --tb=short
```

**期望**:
- 新增 test_delivery_mode_default 1 + test_memory_type 4 = 5 新测试全过
- 既有测试全过(rc.2 baseline 1407 + 5 新 = 1412)
- `test_periodic_save_dirty_only` Win flake 仍偶发(v1.2.6 backlog,非回归)
- 旧 test_bot_ephemeral_filter(test1 加的)若断言"不入 pool"会红 — **更新它**:改成断言"标 memory_type 入 pool"(替"不入 pool")

**如有红**:
- `test_ephemeral_bot_state_not_written_to_pool`(test1 旧测试)红 → 旧断言"add_for_user 不调"已过时(rc.3 改成标类型入 pool)。更新成"add_for_user 调 + memory_type=bot_ephemeral_state"
- `test_search_by_vector_excludes_ephemeral` 红 → 确认 entry 入 pool 后在哪个 tier(buffer/warm/cold),search_by_vector 是否查该 tier

---

## 任务 4:commit(本地,不 push)

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git status
git add -A
git commit -m "v1.3.0 rc.3: Bug-E/H framework 防护 + Bug-F memory_type 彻底修 (NOT pushed)

Bug-E/H (framework bug, emotion_spirit 侧防护):
  - delivery_mode 默认 append → event_send (Bug-H 让 append 不可用: bot 不回复)
  - append 模式加诊断 log (sanity log: chain 内容 + id, 给 framework 调试)
  - docs/framework-issue-bug-h.md (issue 模板: Bug-H + send_delayed API 需求, 待提 AstrBot)
Bug-F (memory_type 彻底修, 替 token filter '不入 pool'):
  - UnifiedEntry 加 memory_type 字段 (bot_reply/bot_ephemeral_state/bot_long_term_fact/user_fact)
  - add_for_user 加 memory_type 参数
  - _apply_bot_reply_effects: ephemeral 标 memory_type 仍入 pool (不再 '不入 pool')
  - search_by_vector 加 exclude_memory_types 过滤
  - 召回端传 exclude_memory_types={'bot_ephemeral_state'} (不注入 system_prompt)
  - to_dict/from_dict 加 memory_type (§1.5, 旧数据兜底 bot_reply)
  - _EPHEMERAL_BOT_TOKENS 保留 (判定 ephemeral 标类型, 不再拦截入 pool)

测试版, 不 push, 不 bump. v1.3.0 后续 (实测 + push framework issue) 完成后 ship.

用户反馈: 2026-07-04-emotion-spirit-feedback-merged.md §2 (Bug-E/H) + §4 (Bug-F)."
```

**⚠️ 不要 `git push`**。本地 commit。

---

## 任务 5:报告

**新建**:`docs/v1.3.0-rc3-build-report.md`

```markdown
# v1.3.0 rc.3 构建报告(2026-07-04, 不 push)

## 范围
Bug-E/H (framework 防护) + Bug-F (memory_type 彻底修). **不 push, 不 bump**.
等用户实测 + push framework issue 后 ship v1.3.0.

HEAD: `git rev-parse HEAD` 填入

## 改动清单

### Bug-E/H (framework, emotion_spirit 侧防护)
- _conf_schema.json: delivery_mode 默认 append → event_send (Bug-H 让 append 不可用)
- orchestrator.py: append 模式加诊断 log (chain 内容 + id)
- docs/framework-issue-bug-h.md: issue 模板 (Bug-H + send_delayed API, 待提 AstrBot)

### Bug-F (memory_type 彻底修)
- memory_pool.py: UnifiedEntry 加 memory_type + add_for_user 加参数 + search_by_vector 加 exclude_memory_types + to_dict/from_dict
- main.py: _apply_bot_reply_effects 标 memory_type (ephemeral 仍入 pool, 不再 '不入 pool')
- _EPHEMERAL_BOT_TOKENS 保留 (判定 ephemeral, 不再拦截)
- 守护: test_delivery_mode_default + test_memory_type

## 测试
- pytest tests/ 全套: <填入> passed
- 新增: test_delivery_mode_default 1 + test_memory_type 4 = 5
- 更新: test_bot_ephemeral_filter (旧 '不入 pool' 断言 → '标类型入 pool')
- 已知: test_periodic_save_dirty_only Win flake (v1.2.6 backlog)

## 不做清单
- ❌ git push / bump / CHANGELOG
- ❌ Bug-E 根治 (等 framework send_delayed API)
- ❌ Bug-H 根治 (framework bug, push 上游)

## 实测后后续
1. 用户丢 zip 实测: delivery_mode=event_send (默认) → bot 回复 + 分段 delay (表情包仍失, 等 framework)
2. push AstrBot issue (docs/framework-issue-bug-h.md)
3. 后续 rc: 等 framework 修 Bug-H + 加 send_delayed API → emotion_spirit 启用 append / delayed_append
4. 全绿后 bump v1.3.0 + ship
```

填入数字 + HEAD 后保存。

---

## 不做清单(明确)

- ❌ `git push` / bump / CHANGELOG
- ❌ Bug-E 根治(等 framework `send_delayed` API)
- ❌ Bug-H 根治(framework bug,push AstrBot 上游,emotion_spirit 侧只防护 + 诊断)
- ❌ 改 Patch A/B/D(已在 test2 commit,合入 v1.3.0)
- ❌ 其他轴心模块人格化(DefenseModulator/Suppression 等,§1.7 TODO 后续 rc)

---

## 关键源码参考

- delivery_mode:`_conf_schema.json:453-456` + `emotion_spirit/output/segmented_reply_orchestrator.py`(delivery_mode 分支)
- memory_pool:`emotion_spirit/memory/memory_pool.py`(add_for_user:142, search_by_vector:425, to_dict:694, from_dict:708)
- _apply_bot_reply_effects:`main.py:1493-1505`(_EPHEMERAL_BOT_TOKENS:34)
- 召回链:`memory_agent.py:62` → `memory_pool.py:268` → `main.py:1423-1425`
- framework 源码:`D:\python\Lib\site-packages\astrbot\core\pipeline\respond\stage.py:283-289`(Reply/At 检查)+ `third_party.py:104-119`(aggregator)
- 用户反馈:`C:\Users\Aston\Downloads\2026-07-04-emotion-spirit-feedback-merged.md` §2(Bug-E/H)+ §4(Bug-F)
