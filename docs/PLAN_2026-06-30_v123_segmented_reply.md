# PLAN 2026-06-30 — v1.2.3: 分段回复功能 (segmented reply)

> 来源: 用户诉求 (`now/2026-06-30-emotion-spirit-v121-install-feedback (1).md` §用户投票)
>   "希望 emotion_spirit 在自己的 persona 配置里也提供 segmented_reply 开关 (per-persona 节奏控制),
>    而不是只能依赖 AstrBot 全局的 segmented_reply.enable"
> 作者: Aston (本 session 设计, 2026-06-30)
> 前置: v1.2.2 已修完 B1-B6 + CI (见同目录 v122 plan)
> 目标: v1.2.3 — 接通现成但未连线的分段回复引擎, 行为变更 opt-in, 不破坏老用户

---

## §0 范围与设计原则

**单一核心**:把 `RealtimeDispatch` / `RhythmLearner` / `DeliberateSilence` / `BreathingRhythmController` 这些**已 `@register`、已实例化但从未连线**的引擎,通过新建 `SegmentedReplyCoordinator` 桥接到 main.py 的回复链路。

**三条铁律** (沿用 realtime_dispatch.py 顶部 docstring, line 14-15):
1. 引擎层 (output) **纯数据结构输出, 不涉及 async/IO** —— Coordinator 也不碰 async/yield
2. 实际消息发送 (async sleep + yield) 仍归 main.py 宿主层
3. 模块新增走现有 `@register` + DI, 零新架构概念

---

## §1 用户已拍板的决策 (2026-06-30 本 session, 全部固化)

| # | 决策点 | 选择 | 理由摘要 |
|---|---|---|---|
| D1 | Bug 2 修法 (属 v1.2.2, 此处仅关联) | `find()` | 删手维护白名单 |
| D2 | Bug 4 修法 (属 v1.2.2) | 方案 A (加 `*args`) | — |
| D3 | Bug 6 修法 (属 v1.2.2) | 不调 LLM + 留 `initialized=False` | — |
| D4 | 分段功能版本归属 | **v1.2.3** (v1.2.2 只纯修复) | 隔离行为变更 |
| D5 | 发送机制 (X/Y/Z) | **先 POC 再定** (见 §3) | 唯一硬卡点, 不凭断言 |
| D6 | 全局开关默认值 | **默认关** (`enable=false`) | 可见行为变更必须 opt-in |
| D7 | 段间延迟风格 | **拟真打字 + 上限兜底** | 用 `build_segmented_parts` 现成 `delay=len/cps`, 加 `max_delay_seconds` 上限 |
| D8 | `recent_ignored_rate` 来源 | **Coordinator 现算近似** | 激活 RhythmLearner 退缩分支, 否则人格少一半表达力 |
| D9 | 呼吸/沉默的 `tension` 信号 | **`rhythm_strain`** | 与 docstring 语义对齐, 纯读现成字段 |
| D10 | `void_pressure` 代用 | `hot_pool_pressure` | 现成字段, 不反向依赖 engine 层 |
| D11 | `valence` 信号 | `pad_valence` | 无争议, 纯读现成字段 |

**关键影响**: D8 + D9 = 接上 Sylanne 1.4.7 原作者埋好但断开的**两条半成品回路**(退缩分支 + 呼吸按节奏张力), 不仅补全分段功能, 也让 v1.3 力学叙事层直接受益。

---

## §2 架构落点

```
                ┌─────────────────────────────────────────────┐
  LLM completion │  on_llm_response (main.py:1224)            │
  (response)    │  现状: 只写 MemoryPool (1224-1266)          │
                └───────────────┬─────────────────────────────┘
                                │ v1.2.3 新增接线
                                ▼
   ┌────────────────────────────────────────────────────────────┐
   │ SegmentedReplyCoordinator (新建, L3 output, @register)     │
   │   depends_on: rhythm_learner + realtime_dispatch           │
   │                                                          │
   │ 输入: full_text, session_key, signals, config             │
   │                                                          │
   │ 1. ignored_rate = self._ignored_rate(session_key)   ← D8 │
   │    (per-session deque 记 bot 回复 / 用户到达时刻,         │
   │     用 config.behavior_ignored_seconds 判定每轮忽略)     │
   │                                                          │
   │ 2. max_part, cps = rhythm_learner.get_rhythm_params(       │
   │      session_key,                                         │
   │      expression_drive=signals.affect_expression_drive,   │
   │      recent_ignored_rate=ignored_rate,                   │
   │      blend=config.blend,                                  │
   │      default_max_part=config.default_max_part_chars,     │
   │      default_cps=config.default_chars_per_second)        │
   │                                                          │
   │ 3. length_factor = realtime_dispatch.next_length_factor(  │
   │      tension=signals.rhythm_strain,        ← D9          │
   │      valence=signals.pad_valence)          ← D11         │
   │    max_part = int(max_part * length_factor) clamped       │
   │                                                          │
   │ 4. silent, reason = realtime_dispatch.should_be_silent(  │
   │      valence=signals.pad_valence,                        │
   │      tension=signals.rhythm_strain,                      │
   │      void_pressure=signals.hot_pool_pressure)  ← D10     │
   │    → silent=True 且 enable_deliberate_silent → 返回 []    │
   │                                                          │
   │ 5. plan = realtime_dispatch.build_segmented_parts(        │
   │      full_text, max_part, cps)                            │
   │    段间 delay = len/cps (D7 拟真打字)                     │
   │    delay = min(delay, config.max_delay_seconds)  ← D7    │
   │                                                          │
   │ 输出: list[{text, delay_before_seconds}] (纯数据)        │
   └──────────────────────────┬─────────────────────────────┘
                            │
                            ▼
   on_llm_response (main.py): 遍历 plan
     for part in plan:
         if part.delay > 0: await asyncio.sleep(part.delay)
         yield event.plain_result(part.text)   ← §3 POC 决定怎么 yield
```

**为什么新建 Coordinator 而非在 main.py 里调** (3 理由):
1. main.py 已 1500+ 行, on_llm_response 再吞分段逻辑会失控
2. Coordinator **能单测**: ignored_rate 计算与 plan 生成都是纯逻辑 (除了 §note 的轻量状态), 不需 AstrBot runtime —— 合 handbook §0 "规则只有能被自动拦下才算规则"
3. 把"用哪几个力学信号 → 调制分段参数"的映射**集中一处**, v1.3 想让社会力也参与只动一个文件 (current-truth §2 路线表 v1.3 = 力学叙事层)

**·note**: D8 让 Coordinator 从纯函数变成**轻量有状态** (per-session deque 记交互时刻)。状态量极小 (每 session 最多几十个时刻), 序列化与 `BreakpointStore` 同一路径 (realtime_dispatch.to_dict/from_dict 的 `breakpoints` 字段同档), **不另开存储**。该状态局限在 Coordinator 内部用于派生 ignored_rate, 不外泄。

---

## §3 发送机制 — 先 POC 再定 (D5, 唯一硬卡点)

**问题本质**: AstrBot `@filter.on_llm_response` 是**后处理回调**, LLM 整条回复已生成, 平台即将/已发出。emotion_spirit 在这里 yield 多条 `plain_result` 能不能让平台分多条发? 当前 handler 签名 `async def on_llm_response(...) -> None` (main.py:1224), 是"后处理", **不是**生成回复之处。

**三个候选方案**:

| 方案 | 思路 | 优点 | 卡点 |
|---|---|---|---|
| **X 后处理切分** | on_llm_response 拦截整条回复, 切多段带延迟重新 yield | 不动 LLM prompt, 最省事 | 平台可能已在发/已发整条; 能否抢在发前改? AstrBot pipeline 阶段未明 |
| **Y 前处理截断** | on_llm_request 改 prompt 让 LLM 只生成首句, 首句发后emotion_spirit 起续写调用 发后续段 | 绕开"拦截已发回复" | 每段一次 LLM 调用, 成本/延迟涨; 续写易跑题; 与"一次生成"架构出入大 |
| **Z 全量生成 + 主动推送** | LLM 整条不动, on_llm_response 拿文本后用 AstrBot 主动消息 API 按计划发, 同时抑制默认那条 | 不动 LLM; 不靠 handler yield | 取决 AstrBot 有无"抑制默认回复 + 主动推送"组合能力 |

**POC 步骤** (实施前必做, 不浪费工作量):

1. **最小多段 yield 测试** (验 X): 在本机 AstrBot (memory [[astrbot-local-setup]] PID 64564 / v4.26.1) 临时 handler:
   ```python
   @filter.on_llm_response(desc="POC: multi-yield")
   async def _poc_multi(self, event, response):
       yield event.plain_result("A")
       yield event.plain_result("B")
   ```
   平台发 1 条还是 2 条?
   - 发 2 条 → 方案 X 成立, Coordinator 直接产出多段让 on_llm_response 逐段 yield, v1.2.3 顺上
   - 发 1 条 → X 不成立, 进步骤 2

2. **查 AstrBot star_manager 对 handler yield 的消费逻辑**:
   - Sylanne 1.4.7 (本项目引擎来源) 当年怎么把分段发出去的? memory [[sylannengine-architecture]] / [[astrbot-local-setup]] 可能有线索
   - 查 AstrBot `star_manager.py` + `on_llm_response` 调用点, 看它怎么处理 handler 的 yield 产物

3. **能否抑制默认回复 + 主动推送** (验 Z): 查 AstrBot 是否有主动消息 API (不经用户交互发到指定 session), 以及能否在 on_llm_response 让默认那条回复不上发。

4. **若 X/Y/Z 全卡**: 分段功能**降级进 v1.3 roadmap**, v1.2.3 只接 Coordinator + 单测 (沉淀引擎接线与力学映射, 发送机制等 AstrBot 支持再上)。

**POC 输出**: 一份决策 —— X/Y/Z 选哪一个 或 全废降级, 写进 `docs/v123_POC_findings.md`, 再动 main.py。

---

## §4 配置位设计 (_conf_schema.json 新增分段, 在 v1.2.2 配置之后)

```json
"segmented_reply": {
  "description": "分段回复 (吸收 Sylanne 1.4.7 实时调度, 力学信号+用户节奏自动调制)",
  "type": "object",
  "hint": "控制 bot 回复是否分段、节奏参数。关闭则一次性 yield (旧行为, 默认)",
  "items": {
    "enable": {
      "description": "是否启用分段回复",
      "type": "bool",
      "default": false,
      "hint": "opt-in 行为变更开关 (D6)。关闭=bot 一次性回复; 开启=按标点+字符数切分, 段间模拟打字延迟"
    },
    "default_max_part_chars": {
      "description": "单段默认最大字符数",
      "type": "int",
      "default": 48,
      "hint": "学不到用户节奏时的默认值; 学到后被 RhythmLearner 调制。与引擎默认 _DEFAULT_MAX_PART_CHARS 对齐"
    },
    "default_chars_per_second": {
      "description": "默认打字速度 (字符/秒, 决定段间延迟)",
      "type": "float",
      "default": 7.5,
      "hint": "越大段间等待越短; 学到用户节奏后被调制。与引擎默认 _DEFAULT_CHARS_PER_SECOND 对齐"
    },
    "blend": {
      "description": "基础同步混合率",
      "type": "float",
      "default": 0.6,
      "hint": "向用户节奏靠拢的比例 (0=全默认, 1=全学用户)"
    },
    "enable_deliberate_silence": {
      "description": "是否启用主动沉默 (受伤/消化/满足时不发或极简)",
      "type": "bool",
      "default": false,
      "hint": "力学信号触发; 关闭则永远回复。子开关独立于 enable, 但 enable=false 时本项无意义"
    },
    "intimacy_gate": {
      "description": "只有亲密度 ≥ 此值才学用户节奏",
      "type": "float",
      "default": 0.6,
      "hint": "RhythmLearner 亲密度门控 (per-persona 可覆盖)"
    },
    "max_delay_seconds": {
      "description": "段间最长延迟上限 (D7 兜底)",
      "type": "float",
      "default": 2.0,
      "hint": "防止 cps 学得太慢导致段间干等过久; delay = min(len/cps, 此值)"
    },
    "ignored_window_turns": {
      "description": "计算被忽略率的回顾轮数 (D8)",
      "type": "int",
      "default": 10,
      "hint": "最近 N 轮中 bot 回复后用户超过 ignored_seconds 回的视为被忽略, 比例=ignored_rate"
    }
  }
}
```

**复用现有配置**: `behavior_ignored_seconds` (已在 v1.2.2 配置内, 默认 7200) 作为 D8 判定被忽略的阈值, **不重复定义**。

---

## §5 persona-level 覆盖 + 顺手补漏接线

**lead 用户诉求**: persona 配置里可选 `segmented_reply` 块覆盖全局 (节奏 per-persona)。

**实施** (需先确认 persona 存储结构):
- persona_*.json 加可选 `segmented_reply: {...}` 字段, 同结构, 缺项回退全局
- 加载 persona 时若存在则与全局 merge, Coordinator 取值优先 persona

**顺手补漏接线 (与分段功能无关, 但同属 RhythmLearner 一直没接的钩子)**:
- `RhythmLearner.set_personality_params(intimacy_threshold, blend_rate)` (rhythm_learner.py:186) —— emotion_spirit 侧 **0 caller** (本 session grep 确认, 仅 sylanne 内部引擎用)
- v1.2.3 应在 main.py `_apply_persona_params` 注入 persona 的 intimacy_gate + blend:
  ```python
  self._rhythm_learner.set_personality_params(
      persona.segmented_reply.intimacy_gate if has else config.intimacy_gate,
      persona.segmented_reply.blend        if has else config.blend,
  )
  ```
- **注意**: 需 grep 定位 `_apply_persona_params` 实际方法名/位置 (本 session 未定位其存在, 可能在 force_dynamics/body_state 注入附近)

---

## §6 修改清单 (实施顺序)

1. **POC 先行** (§3 步骤 1-4) → 出 `docs/v123_POC_findings.md` 定 X/Y/Z
2. 新建 `emotion_spirit/output/segmented_reply_coordinator.py`:
   - `@register(name="segmented_reply_coordinator", provides=["SegmentedReplyCoordinator"], depends_on=["rhythm_learner", "realtime_dispatch"])`
   - `plan(full_text, session_key, signals, config) -> list[dict]` 主方法
   - `_ignored_rate(session_key) -> float` + per-session deque (D8)
   - `to_dict`/`from_dict` 序列化 ignored_rate 状态 (与 BreakpointStore 同档)
3. `emotion_spirit/__init__.py` 加 `from .output import segmented_reply_coordinator` (触发 @register, 56→57)
4. `_conf_schema.json` 加 `segmented_reply` 块 (§4)
5. main.py `_apply_persona_params` 加 `rhythm_learner.set_personality_params` 注入 (§5, 顺手补漏)
6. main.py `on_llm_response` (1224) 重构接 Coordinator:
   - enable=false / plan 空 / silent(若开 silence) → 现有行为 (一次性)
   - enable=true → 按 POC 选定的 X/Y/Z 方案发多段
7. `/view_rhythm` 命令 (走 `_ns_command` 工厂, v1.2.2 Bug 4 修好后参数才传得进): 显示 RhythmProfile + 呼吸模式 + 上次中断断点
8. registry consistency test + dryrun test: 56→57 维护 (handbook §1.2 流程)
9. `tests/test_segmented_reply_coordinator.py`:
   - `test_plan_short_text_returns_single_part`
   - `test_plan_long_text_splits_by_punctuation`
   - `test_delay_capped_by_max_delay_seconds` (D7)
   - `test_ignored_rate_after_consecutive_ignores` (D8)
   - `test_silent_when_hurt_and_silence_enabled` (D10)
   - `test_rhythm_blends_with_user_profile` (用 fake RhythmProfile)

---

## §7 完成定义 (DoD)

- [ ] v1.2.3 tag, Release zip 重建
- [ ] `docs/v123_POC_findings.md` 写明 X/Y/Z 决策与 AstrBot handler 多段 yield 实测结果
- [ ] pytest 全绿 (现有 + 新 segmented_reply_coordinator 测试)
- [ ] 本机 AstrBot 实测: `segmented_reply.enable=true`, bot 长回复分多条发, 段间有延迟且 ≤ max_delay_seconds; `enable=false` 回到旧行为
- [ ] persona `segmented_reply` 块覆盖全局生效 (改 persona 的 blend → 观察同步率变化)
- [ ] `enable_deliberate_silence=true` + 触发 hurt 信号时 bot 发 "……" 或不发 (D10)
- [ ] memory: 更新 [[emotion-spirit-current-truth]] v1.2.3 状态 + 新建 [[emotion-spirit-v123-state]]

---

## §8 风险与降级

| # | 风险 | 处置 |
|---|---|---|
| R1 | **POC 发现 on_llm_response 不能多段 yield** | X/Y/Z 全验失败 → v1.2.3 只接 Coordinator + 单测 (沉淀引擎接线), 发送降级进 v1.3 roadmap |
| R2 | ignored_rate 状态序列化与 BreakpointStore 冲突 | 同一个 to_dict 字段命名空间 (coordinator under realtime_dispatch? 独立?) 实施时再定 |
| R3 | persona `segmented_reply` 覆盖需读 persona 存储结构 | §5 实施前 grep persona_labels_db / persona_profiles 弄清字段挂哪 |
| R4 | `_apply_persona_params` 方法可能不存在或叫别的名 | §5 grep 验证, 可能需新建 |
| R5 | registry 56→57 consistency/dryrun test 维护遗漏 | handbook §1.2 历来流程, 跟随 |
| R6 | 拟真打字让用户段间干等感烦 | D7 max_delay_seconds=2.0 兜底, DoD 实测观察体验 |
| R7 | LLM 整条回复含代码块/列表被按标点切断成怪段 | segment_text 已有标点逻辑, 但需测试 markdown 代码块情况; 必要时加 "尊重代码块" 选项 |

---

## §9 与 v1.3 力学叙事层的关系

D8 + D9 接上的**两条半成品回路**正是 v1.3 力学叙事层要用的:
- 退缩分支 (ignored_rate → slowdown) = 个体力受伤的表达
- 呼吸按节奏张力 (rhythm_strain → 4 模式) = 自然力的躯体节律

v1.2.3 沉淀的 Coordinator 力学映射, v1.3 可直接扩展 (让社会力/gossip 驱动也参与分段决策), 不重写。**v1.2.3 在此意义上是 v1.3 的前置基础设施**, 不只是"加个分段开关"。

---

## Related

- 用户诉求原文: `now/2026-06-30-emotion-spirit-v121-install-feedback (1).md` §用户投票
- v1.2.2 修复 plan: 同目录 `PLAN_2026-06-30_v122_install_feedback_and_segmented_reply.md` (§4 分段设计已挪到本文件)
- [[emotion-spirit-current-truth]] — 代码真相锚
- [[emotion-spirit-v122-candidates]] — v1.2.2 候选 + 分段发现记录
- 现成引擎: `emotion_spirit/output/realtime_dispatch.py` + `rhythm_learner.py`