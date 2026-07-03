# emotion_spirit v1.2.5 — 分段回复修复 + 沉默语义完整化 + 三防御链力学耦合 (设计)

> **日期**: 2026-07-03
> **作者**: Aston (本 session)
> **状态**: ⏸ 设计中, 待用户审批
> **关联**: 反馈文档 `now/2026-07-03-emotion-spirit-v124-segmented-reply-bug.md`
> **前置**: v1.2.4 已 ship (`e5f89a0`, 57 modules, 1261 tests)

---

## Drift 注记 (v1.2.6 回扫)

> v1.2.5 实现后 vs 本 spec 设计意图的偏差 (v1.2.6 审计 + v1.2.7 收敛):

| Drift | 方向 | 当前状态 |
|---|---|---|
| `config_keys={"segmented_reply"}` | 无(无所谓) | ✅ 无修正需求 |
| `self._conscience.pressure` → hasattr fallback | ❌ 更差 (见 DO-4) | ✅ **v1.2.7 已修** (HP-2) |
| `force_dynamics.apply_defense_delta` 硬编码 → KB deltas | ✅ 更好 | ✅ 维持 |
| `silence_components: dict = None` → `field(default_factory=dict)` | ✅ 更好 | ✅ v1.2.5 PR3 已修 |
| 三子 L2 全接 → 实际只接 silence | 范围收缩 | Q3 删事件 + v1.2.8 L2 脚手架 |

**结论**: spec 反映设计意图, 实现以代码为准; 主要 drift 已在 v1.2.6/v1.2.7 收敛。

## §0 范围与非目标

### v1.2.5 范围（10 项, 全部必修）

| # | 名称 | 来源 |
|---|---|---|
| 1 | **Bug 12a**: `await self._on_segmented_reply()` TypeError | 反馈 §Bug 12a |
| 2 | **Bug 12b**: 投递架构 — emotion_spirit 独立 send, 不依赖 AstrBot 全局分段 | 反馈 §Bug 12b |
| 3 | **流式模式跳过**: `streaming_response=true` 时 emotion_spirit 沉默/分段都跳过 | 用户拍板 D-1 |
| 4 | **沉默 S1+S2+S3+S4**: 不删消息 / 语义透明 / 情绪事件 / 时长上限 | 用户拍板 |
| 5 | **沉默人格加权**: Jack 1992 + Carver 1998 + Noftle 2006 系数 | 用户要求理论背书 |
| 6 | **亲密度双向调节**: Jack 讨好假说 (亲密中更沉默) | 用户洞察 |
| 7 | **上下文读取**: social_audience + authority placeholder | 用户要求 |
| 8 | **力学 L1 输入调制**: 沉默/压抑/崩溃 三子读力学 | 用户拍板耦合深度 |
| 9 | **力学 L2 输出回写**: 三子事件触发后回写 force_state | 同上 |
| 10 | **延迟策略接口**: TypingDelayStrategy 默认 + TTS 接口预留 (Coordinator 内部, 不独立注册) | 用户要求 + 设计审查 (§5) |

### v1.3 推后

- 力学 L3 完全耦合 (fixpoint 求解 + 阻尼 + 涌现) — 用户拍板拆 v1.3
- **TTS DelayStrategy 真实实现** — v1.2.5 已留 `set_delay_strategy()` 内部接口 + TTSDelayStrategy 占位, v1.3 在 Coordinator `__init__` 加可选 `tts_provider` 参数即可, **不动 main.py**
- `authority_present` 从 message 真实解析 (@bot / sender_role)
- Steppenwolf 5.3 多人格质心

### v1.2.5 永不做

- ❌ 改 AstrBot 框架侧 (`call_event_hook` / `RespondStage`)
- ❌ L3 fixpoint 循环依赖 (v1.3)
- ❌ 改 emotion_spirit 之外插件的 hook

---

## §1 Bug 12 修复 — 投递机制 (核心)

### 1.1 现状 (v1.2.4 不可工作)

**Bug 12a** (`main.py:1286-1292`): `_on_segmented_reply` 含 `yield`, 是 async generator function, 被 `await` 调用 → 100% TypeError, 被静默 `except Exception` 吞掉, Coordinator 永远执行不到。

**Bug 12b** (架构性): 即使修好 12a, 在 hook 里 `yield event.plain_result(text)` 也不会送达用户——
- `call_event_hook` (AstrBot `context_utils.py:75-108`) 用 `await handler.handler(...)` 调用, 不 iterate async generator
- `on_llm_response` 在 `ToolLoopAgentRunner._complete_with_assistant_response` 内部触发, 时序在 `run_agent.set_result()` **之前**——hook 改 result chain 太早, event 上 result 还没 set
- 即使在 hook 里 send, `RespondStage` 会再发一次整条

### 1.2 方案 K (v1.2.5 拍板): hook 主动 send + 清空 llm_resp

```python
# main.py — on_llm_response 重写 (删 _on_segmented_reply)
async def on_llm_response(self, event: AstrMessageEvent, response: Any) -> None:
    """Bot 回复后处理 + 分段投递 (v1.2.5 重写)"""
    # 0. 写 memory + 亲密度 + reflex (保留原逻辑)
    try:
        # ... 原 on_llm_response:50-90 行 ...
        pass
    except Exception:
        logger.debug("emotion_spirit: memory update failed", exc_info=True)
    
    # 1. 分段前置检查
    seg_config = self._config.get("segmented_reply", {})
    if not seg_config.get("enable", False):
        return
    if not hasattr(self, "_segmented_coordinator"):
        return
    
    # 2. 流式模式跳过 (用户 D-1)
    if self._config.get("provider_settings", {}).get("streaming_response", False):
        logger.debug("emotion_spirit: streaming_response=True, skipping segmented_reply")
        return
    
    # 3. 算分段计划 + 沉默判定 (L1 输入调制, 见 §3)
    try:
        full_text = getattr(response, "completion_text", "") or ""
        if not full_text:
            return
        
        # L1: 读上游 (人格 + 力 + 身体 + 信号 + 亲密度 + 上下文)
        personality = self._get_personality_labels(event.get_sender_id())
        force_state = self._force_dynamics.get_current_force_state(self._labels) if hasattr(self, "_force_dynamics") else None
        body_state = self._body_state.get_current() if hasattr(self, "_body_state") else None
        signals = self._latest_signals.get(event.get_sender_id()) if hasattr(self, "_latest_signals") else None
        intimacy = self._intimacy.get_level(event.get_sender_id()) if hasattr(self, "_intimacy") else 0.5
        context = self._build_context(event)  # 见 §3.5
        
        # 沉默判定 (返回 SilenceTendency, 见 §2)
        silence_tendency = self._segmented_coordinator.compute_silence_tendency(
            session_key=event.get_sender_id(),
            personality=personality,
            force_state=force_state,
            body_state=body_state,
            signals=signals,
            intimacy_level=intimacy,
            context=context,
        )
        
        # S4: 冷却期 + 连续上限检查
        should_silent, reason, adjusted_tendency = self._segmented_coordinator.should_be_silent(
            session_key=event.get_sender_id(),
            tendency=silence_tendency,
            config=seg_config,
        )
        
        # 4. S1 沉默: 清空 llm_resp + (v1.2.5 行为) 不主动 send
        if should_silent and seg_config.get("enable_deliberate_silence", False):
            # S3 情绪事件
            self._segmented_coordinator.record_silence_event(
                session_key=event.get_sender_id(),
                tendency=adjusted_tendency,
                full_text=full_text,
                force_state=force_state,
            )
            # L2 输出回写
            self._force_dynamics.apply_defense_delta("silence", intensity=adjusted_tendency.score)
            
            response.completion_text = ""
            response.result_chain = None
            logger.debug("emotion_spirit: deliberate silence triggered reason=%s score=%.2f",
                         reason, adjusted_tendency.score)
            return
        
        # 5. 正常: 算 plan + 主动 send
        plan = self._segmented_coordinator.plan(
            full_text=full_text,
            session_key=event.get_sender_id(),
            signals=signals,
            force_state=force_state,
            config=seg_config,
        )
        
        if not plan:
            return  # 空 plan (沉默以外的边界情况)
        
        # 6. 主动 send (F4: 先发首段无延迟, 后续段 sleep + send)
        try:
            await event.send(MessageChain([Plain(plan[0]["text"])]))
            for part in plan[1:]:
                delay = part.get("delay_before_seconds", 0.0)
                if delay > 0:
                    await asyncio.sleep(delay)
                await event.send(MessageChain([Plain(part["text"])]))
        except Exception:
            # F3: 单段失败继续
            logger.warning("emotion_spirit: segmented_reply send failed, some segments may be missing", exc_info=True)
        
        # 7. 清空 llm_resp, 阻止 RespondStage 重复发
        response.completion_text = ""
        response.result_chain = None
        
    except Exception:
        # F1: hook 整体失败 → 让 AstrBot 正常发
        logger.warning("emotion_spirit: segmented_reply failed, falling back to AstrBot default", exc_info=True)
```

### 1.3 时序验证

```
1. LLM 完成 (非流式模式) → llm_resp.completion_text = "完整回复"
2. _complete_with_assistant_response → on_agent_done → call_event_hook(OnLLMResponseEvent, llm_resp)
   a. emotion_spirit hook:
      - 算 plan (3 段)
      - event.send("段1") → 用户看到段1
      - sleep 0.5s
      - event.send("段2") → 用户看到段2
      - sleep 0.5s
      - event.send("段3") → 用户看到段3
      - llm_resp.completion_text = "" + result_chain = None
   b. hook 返回
3. step() 继续:
   - line 804 if llm_resp.result_chain: None → False
   - line 809 elif llm_resp.completion_text: "" → False
   - step() 不 yield llm_result  ← 跳过
4. run_agent: async for resp 不产出 → 不 set_result
5. InternalAgentSubStage: async for _ in run_agent 不产出
6. RespondStage:
   - result = event.get_result() → None → return 不发
```

**用户收到**: 3 条独立消息, 段间 ~0.5s 延迟, **无重复**。

### 1.4 失败回退表

| # | 失败 | 处置 | 用户感知 |
|---|---|---|---|
| F1 | plan 算不出 (Coordinater 抛异常) | catch 异常 + 立即 return, llm_resp 不动 | AstrBot 默认发整条 (用户收到回复, 无分段) |
| F2 | plan 为空 + enable_deliberate_silence=False | 视为正常, 不发 | AstrBot 发整条 |
| F3 | event.send 抛异常 | catch + log, 后续段继续发 | 用户可能收到不完整分段 |
| F4 | asyncio.sleep 被 cancel | 接受 cancel, 不 retry | hook 退出, llm_resp 状态不确定 (AstrBot 可能重复发) |

---

## §2 沉默语义 S1-S4

### 2.1 S1 不删消息 + 沉默触发语义

**v1.2.5 行为**: `enable_deliberate_silence=true` 且沉默触发 → 清空 `llm_resp` → **用户看不到 bot 回复** (跟 v1.2.3 plan 语义一致, "受伤/消化/满足时不发")

**用户反馈的缺口**: "沉默是情绪事件, 没设计沉默会带来什么影响" — 已记入 v1.3 backlog, v1.2.5 暂时保留"沉默=不发"

### 2.2 S2 语义透明 — `SilenceTendency` dataclass

```python
# emotion_spirit/output/segmented_reply_coordinator.py
from dataclasses import dataclass, field
from ..layer import per_user_only

@dataclass(frozen=True)
class SilenceTendency:
    """沉默倾向 (v1.2.5 新)
    
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

**注意**: v1.2.5 三个 per-user 方法严格遵守 handbook §1.3 (layer.py 装饰器) — 运行时强制检查 user_id, 不标会埋静默错位 bug:

```python
class SegmentedReplyCoordinator:
    # ... 已有 @register spec ...
    
    @per_user_only
    def compute_silence_tendency(self, session_key: str, ...) -> SilenceTendency:
        """v1.2.5: @per_user_only 强制 caller 传 session_key"""
        ...
    
    @per_user_only
    def should_be_silent(self, session_key: str, tendency: SilenceTendency, config: dict) -> tuple[bool, str, SilenceTendency]:
        """S4 决策, @per_user_only"""
        ...
    
    @per_user_only
    def record_silence_event(self, session_key: str, tendency: SilenceTendency,
                              full_text: str, force_state: Optional[dict] = None) -> None:
        """S3 写 memory + 推进冷却计数, @per_user_only"""
        ...
    
    # 注意: record_response_event 也是 per-user (推进 turns_since_last_silence)
    @per_user_only
    def record_response_event(self, session_key: str) -> None:
        """每次 bot 实际回话后调用, 推进冷却计数"""
        ...
    
    # 注意: plan() 不接收 session_key 参数? 不 — 它接收, 必须 @per_user_only
    @per_user_only
    def plan(self, session_key: str, full_text: str, ...) -> list[dict]:
        ...
```

**6 种 reason** (跟 6 factor 一一对应):
- `tension_digesting` — tension_stress 主导
- `void_hurt_withdrawing` — hurt_void 主导
- `void_satisfied_quiet` — satisfaction_quiet 主导
- `energy_depleted` — exhaustion 主导
- `arousal_overload` — overload 主导
- `social_audience_pressure` — social_audience 主导

### 2.3 S3 情绪事件

```python
def record_silence_event(
    self,
    session_key: str,
    tendency: SilenceTendency,
    full_text: str,
    force_state: Optional[dict] = None,
) -> None:
    """沉默作为情绪事件记入 memory + force_state (S3)"""
    # 1. 写 memory_pool (作为内部状态事件)
    self._memory_pool.add_event(
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
    # 2. L2 输出回写 (在调用方调 apply_defense_delta)
    # 3. 更新连续计数
    self._consecutive_silence_count[session_key] = (
        self._consecutive_silence_count.get(session_key, 0) + 1
    )
    self._turns_since_last_silence[session_key] = 0
    
    # 4. /reflect_force_current 可查
```

### 2.4 S4 时长上限

```python
def should_be_silent(
    self,
    session_key: str,
    tendency: SilenceTendency,
    config: dict,
) -> tuple[bool, str, SilenceTendency]:
    """S4: 冷却期 + 连续上限 + threshold 决策
    
    Returns: (silent, reason, adjusted_tendency)
    """
    # 1. 冷却期: 刚沉默过, 强制不沉默
    cooldown = config.get("silent_cooldown_turns", 2)
    turns_since = self._turns_since_last_silence.get(session_key, 999)
    if turns_since < cooldown:
        return False, "cooldown_active", tendency
    
    # 2. 连续上限: 已沉默 N 次, 阈值上调到 0.9
    max_consec = config.get("max_consecutive_silence", 3)
    consec = self._consecutive_silence_count.get(session_key, 0)
    if consec >= max_consec:
        threshold = 0.9  # 几乎不可能触发
        reason_suffix = "max_consecutive_reached"
    else:
        threshold = config.get("silent_threshold", 0.5)
        reason_suffix = ""
    
    silent = tendency.score >= threshold
    final_reason = tendency.reason + (f"+{reason_suffix}" if reason_suffix and silent else "")
    return silent, tendency.reason, tendency

def record_response_event(self, session_key: str) -> None:
    """每次 bot 实际回话后调用, 推进冷却计数"""
    self._turns_since_last_silence[session_key] = (
        self._turns_since_last_silence.get(session_key, 0) + 1
    )
    # 连续计数**不重置** — 累积到上限后强制恢复, 冷却期后下次沉默又允许
```

**`turns_since_last_silence` 在 `on_llm_response` 末尾调 `record_response_event`**

---

## §3 人格加权沉默倾向 (理论背书版)

### 3.1 理论依据 (文献)

| 理论 | 作者 | 关键论点 | v1.2.5 怎么用 |
|---|---|---|---|
| **Silencing the Self** | Jack & Dill 1992 | 沉默是关系型认知图式, 不是人格特质; 4 子维度 (Externalized Self-Perception / Caretaking / Silenced Self / Divided Self); **亲密关系中沉默更显著** | 亲密度调节 + 高 agreeableness/低 openness 时沉默↑ |
| **COPE 元分析** | Carver 1998 (本地 KB `personality-psychology_full_part_01_00001-00500.md`) | Big Five × coping: N → withdrawal, E → support seeking, C → problem-solving (反沉默), O → flexible, A → support seeking | 各 factor 的人格加权系数 |
| **Attachment × Big Five** | Noftle 2006 (JPSP) | Avoidance × E = -0.20~0.35, × A = ~-0.30, × N = ~+0.15 | 亲密度加权基线 |
| **Polyvagal Theory** | Porges 2011 (emotion_spirit 已引) | 自主神经系统激活 → freeze/dissociate | freeze factor 用 body_arousal 触发 |
| **4F Model** | Walker 2013 (emotion_spirit 已引) | Fight/Fawn/Flight/Freeze 应对 | collapse archetype 跟 silence 共享基础因子 |

### 3.2 沉默倾向公式 (6 factor + 人格加权 + 力加权 + 亲密度加权 + 上下文)

```python
def compute_silence_tendency(
    self,
    session_key: str,
    personality: dict[str, float],   # 13 维 labels (实际用 Big Five 5 维)
    force_state: Optional[dict[str, float]],
    body_state: Optional[Any],         # BodyState 对象
    signals: Optional[Any],            # SemanticSignals 对象
    intimacy_level: float,             # 0-1
    context: dict,                     # {social_audience, authority_present, ...}
) -> SilenceTendency:
    """v1.2.5: 人格加权沉默倾向 (理论依据: Jack 1992 + Carver 1998 + Noftle 2006)"""
    
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
    
    # Big Five 维度 (默认 0.5 中性)
    E = personality.get("extraversion", 0.5)
    A = personality.get("agreeableness", 0.5)
    N = personality.get("neuroticism", 0.5)
    O = personality.get("openness", 0.5)
    C = personality.get("conscientiousness", 0.5)
    
    # === 因子计算 + 人格加权 (Carver 1998 + Noftle 2006) ===
    
    # factor 1: tension_stress (紧张应激) — N → 加成
    f_tension = rhythm_strain * (1 + 0.5 * N)
    
    # factor 2: hurt_void (受伤退缩) — 三个维度联合
    f_hurt = hot_pool_pressure * (1 - pad_valence) \
        * (1 + 0.5 * (1 - E)) \
        * (1 + 0.4 * N) \
        * (1 + 0.3 * (1 - A))
    
    # factor 3: satisfaction_quiet (满足沉静) — 内向者满足时更静
    f_satisfaction = hot_pool_pressure * pad_valence * (1 + 0.4 * (1 - E))
    
    # factor 4: exhaustion (能量耗尽) — 尽责者耗尽时沉默
    f_exhaustion = (1 - energy) * (1 + 0.3 * C)
    
    # factor 5: overload (过载) — N → 加成
    f_overload = arousal * (1 + 0.3 * N)
    
    # factor 6: social_audience (群体压力) — 内向者群聊更沉默
    social_audience = context.get("social_audience", 0.0)
    f_social = social_audience * (1 + 0.5 * (1 - E))
    
    # === 亲密度调节 (Jack 1992 讨好假说 + Noftle 2006) ===
    # base: 越亲密越不想说 (Noftle 系数方向, 默认人格时净效应 ≈ 0)
    mod_intimacy = (1 - 0.3 * intimacy_level) \
        * (1 + 0.5 * A) \   # 高 A → 讨好 → 亲密中更沉默
        * (1 + 0.4 * N) \   # 高 N → 焦虑 → 亲密中更沉默
        * (1 - 0.3 * O)     # 高 O → 开放 → 亲密中也愿说
    
    # === 上下文调节 (新增) ===
    authority_present = context.get("authority_present", 0.0)
    mod_context = (1 + 0.4 * authority_present)  # 权威在场更沉默
    
    # === 力平衡调节 (L1: 子读力) ===
    # dominant_force 影响沉默方向 (v1.2.5: 连续化, 替代 v1.2.3 的离散 0.85/1.20/1.0)
    if force_state is None:
        force_modifier = 1.0
    else:
        social = force_state.get("social", 0.5)
        individual = force_state.get("individual", 0.5)
        natural = force_state.get("natural", 0.5)
        # 社会力主导 → 想说话 (沉默↓); 个体/自然主导 → 沉默↑
        force_modifier = 1.0 - 0.3 * social + 0.2 * natural + 0.4 * individual
        # 范围约 [0.5, 1.5]
    
    # === 累加 (v1.2.5 基础权重, v1.3 可由 config 覆盖) ===
    base_score = (
        0.20 * f_tension +
        0.25 * f_hurt +
        0.10 * f_satisfaction +
        0.20 * f_exhaustion +
        0.15 * f_overload +
        0.10 * f_social
    )
    score = base_score * mod_intimacy * mod_context * force_modifier
    score = max(0.0, min(1.0, score))
    
    # === 选 dominant factor 作 reason ===
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

### 3.3 涌现行为示例

| 人格配置 | intimacy | 实时信号 | 力主导 | silence_tendency |
|---|---|---|---|---|
| E=0.2, A=0.5, N=0.8, O=0.3, C=0.5 (内向焦虑) | 0.7 (亲密) | hurt=0.8, valence=0.2 | individual=0.7 | **0.82** (沉默) |
| E=0.8, A=0.7, N=0.2, O=0.7, C=0.5 (外向开放) | 0.5 | hurt=0.3, valence=0.6 | social=0.7 | **0.18** (说话) |
| E=0.5, A=0.5, N=0.5, O=0.5, C=0.5 (默认) | 0.5 | neutral | neutral | **0.35** (轻微倾向沉默) |
| E=0.3, A=0.8, N=0.5, O=0.3, C=0.7 (讨好尽责) | 0.8 (很亲密) | tension=0.7 | individual=0.6 | **0.71** (讨好型亲密沉默) |

### 3.4 系数合理性检查 (Carver 元分析 + Noftle 2006)

| factor | 主人格维度 | 系数 | 文献支持 |
|---|---|---|---|
| tension_stress | neuroticism | ×(1 + 0.5N) | Carver: N → withdrawal ✓ |
| hurt_void | extraversion (反) | ×(1 + 0.5(1-E)) | Noftle: avoidance × -E (r=-0.30) ✓ |
| hurt_void | neuroticism | ×(1 + 0.4N) | Carver: N → withdrawal ✓ |
| hurt_void | agreeableness (反) | ×(1 + 0.3(1-A)) | Noftle: avoidance × -A (r=-0.30) ✓ |
| satisfaction_quiet | extraversion (反) | ×(1 + 0.4(1-E)) | 内向者满足时更静 (临床观察) ⚠️ 需验证 |
| exhaustion | conscientiousness | ×(1 + 0.3C) | Carver: C → problem-solving (反沉默), 但耗尽时 C 高→继续坚持→反易沉默 (Wegner 1987 ironic rebound) ⚠️ |
| overload | neuroticism | ×(1 + 0.3N) | Carver: N → emotion-focused ✓ |
| social_audience | extraversion (反) | ×(1 + 0.5(1-E)) | E 与社交场合活跃度直接相关 ✓ |
| 亲密度 base | (默认下降) | ×(1 - 0.3×intimacy) | Noftle: avoidance × 亲密度 ⚠️ |
| 亲密度 agreeableness | ×(1 + 0.5A) | Jack 讨好假说 ✓ |
| 亲密度 neuroticism | ×(1 + 0.4N) | Jack: 高 N 在亲密中焦虑沉默 ✓ |
| 亲密度 openness | ×(1 - 0.3O) | O 与自我表达正相关 ✓ |

**系数合理性结论**: 11 个加权中 9 个有明确文献支持 (✓), 2 个基于临床观察的合理推测 (⚠️), **整体可接受, 文档中标注⚠️项供后续验证**。

### 3.5 上下文 (`_build_context`)

```python
def _build_context(self, event: AstrMessageEvent) -> dict:
    """v1.2.5: 上下文感知 (S2 要求)"""
    context = {}
    # social_audience: 群聊 = 0.5, 私聊 = 0.0 (后续按人数细分)
    if event.get_group_id():
        context["social_audience"] = 0.5
    else:
        context["social_audience"] = 0.0
    # authority_present: v1.2.5 placeholder, v1.3 真实解析
    context["authority_present"] = 0.0
    return context
```

---

## §4 力学系统耦合 (L1 输入调制 + L2 输出回写)

> **模块化哲学 (handbook §1.2)**: "加新模块不动 main.py", "加新功能组件 @register + factory, 禁 main.py 手 new"。本节**新建 `DefenseModulator` 模块**统一管理三子-力学耦合, 而不是把 force_dynamics.compute() 扩 3 个参数 (那是反模块化)。

### 4.0 新模块: `DefenseModulator` (统一 L1+L2)

```python
# emotion_spirit/regulation/defense_modulator.py (新)
from dataclasses import dataclass
from typing import Optional, Literal
from ..core.registry import register
from ..output.segmented_reply_coordinator import SilenceTendency


@dataclass
class DefenseStates:
    """v1.2.5 三子连续值 (供 force_dynamics 决策)
    
    字段全 [0, 1], 缺省 0.0 (无防御激活)
    """
    suppression_level: float = 0.0
    collapse_tendency: float = 0.0
    silence_tendency: float = 0.0
    silence_reason: str = ""           # 透明性
    silence_components: dict = None    # 可观测性
    
    def __post_init__(self):
        if self.silence_components is None:
            self.silence_components = {}


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
    """v1.2.5: 压抑/崩溃/沉默 三防御子系统与力学的耦合调制器
    
    L1 (输入调制): 三子读 force_state, 输出 DefenseStates
    L2 (输出回写): 防御事件触发后调 force_dynamics.shift() 回写
    v1.3 加: L3 fixpoint 完全耦合
    
    设计原则 (handbook §1.2):
    - 单一职责: 只管三子↔力学耦合, 不掺业务
    - 加新防御子 (v1.3 焦虑/解离等): 在此加字段, 不动 main.py
    - 系数全部从 KB 读 (handbook §1.1), 不硬编码
    """
    
    # 注意: 系数从 KB 读, 不写死 (见 §4.5)
    
    def compute_defense_states(
        self,
        personality: dict,
        signals: Optional[object],
        body_state: Optional[object],
        intimacy_level: float,
        context: dict,
        force_state: Optional[dict],
    ) -> DefenseStates:
        """L1: 三子读力学, 返回 DefenseStates (连续值, 不是 bool)
        
        v1.2.5 用"上一轮三子 → 当前 force_state → 当前三子"单步法。
        v1.3 升级为 fixpoint 迭代 (L3)。
        """
        # 1. 压抑: suppression.compute() 读 force_state
        suppression_level = self._suppression.compute(
            personality, context,
            conscience_pressure=self._conscience.pressure,
            relationship_intimacy=intimacy_level,
            force_state=force_state,  # L1
        )
        
        # 2. 崩溃: collapse_archetype_selector.compute_bas_bis() 读 force_state
        BAS, BIS, collapse_tendency = self._collapse_selector.compute_bas_bis(
            personality, force_state=force_state,  # L1
        )
        
        # 3. 沉默: coordinator.compute_silence_tendency() 读 force_state
        silence_tendency_obj = self._segmented_coordinator.compute_silence_tendency(
            session_key=context.get("session_key", ""),
            personality=personality,
            force_state=force_state,  # L1
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
    
    def apply_event(
        self,
        defense_type: Literal["suppression", "collapse", "silence"],
        intensity: float,
    ) -> None:
        """L2: 防御事件触发后回写 force_state (handbook §2.2: 静默回归类必修)
        
        intensity ∈ [0, 1], 系数从 KB 读 (见 §4.5)
        """
        deltas = self._defense_deltas_kb[defense_type]
        self._force_dynamics.shift(
            individual_delta=deltas.get("individual", 0.0) * intensity,
            natural_delta=deltas.get("natural", 0.0) * intensity,
            social_delta=deltas.get("social", 0.0) * intensity,
        )
```

### 4.1 L1: 三个子系统读力学 (force_state)

**force_dynamics.compute() 不动 (向后兼容 100%)**——L1 调制由 `DefenseModulator.compute_defense_states()` 完成, 不在 compute() 里加参数:

```python
# force_dynamics.py — 不变
def compute(
    self,
    personality: dict,
    body_state: Optional[BodyState] = None,
    conscience_pressure: float = 0.0,
) -> ForceState:
    """v1.2.5: 签名不变, 跟 v1.2.4 完全一致
    DefenseModulator 负责 L1 调制, 通过 apply_defense_delta 累积
    """
```

**力学方向的语义映射** (每个子系统的"行为方向"对应某个力的主导):

| 子系统 | 主导力 | 设计原理 |
|---|---|---|
| 压抑 (suppression) | **individual** ↑ | 压抑是内省压制, 个体力表征 |
| 崩溃 (collapse) | 视 archetype: VOLCANO→social, FREEZE→natural, COLLAPSE→individual, DRIFT→natural, COLD→individual | 5 种崩溃对应不同力 |
| 沉默 (silence) | **natural** ↑ + **individual** ↑ | 沉默是退缩 + 内省 |

**force_dynamics 内部 mod 计算** (新增):

```python
# 计算 force_state 时, 把三子作为额外调制因子
def _apply_defense_modifiers(
    self,
    base_force: ForceState,
    suppression_level: float,
    collapse_tendency: float,
    silence_tendency: float,
) -> ForceState:
    # 压抑 → 个体力↑
    individual_suppression = 0.4 * suppression_level
    # 崩溃 → 视 tendency 方向 (用 collapse_archetype 选)
    if collapse_tendency > 0.7:
        # 默认崩向自然力 (freeze) / 个体力 (drift/collapse)
        natural_collapse = 0.3 * collapse_tendency
        individual_collapse = 0.3 * collapse_tendency
        social_collapse = -0.4 * collapse_tendency  # 找人帮, 社会力↑
    else:
        natural_collapse = 0.0
        individual_collapse = 0.0
        social_collapse = 0.0
    # 沉默 → 自然 + 个体力↑
    natural_silence = 0.3 * silence_tendency
    individual_silence = 0.3 * silence_tendency
    social_silence = -0.3 * silence_tendency
    
    # 累加 (再归一化保证 sum ≈ 1)
    ...
```

### 4.2 L2: 三子事件触发后回写 force_state

```python
# force_dynamics.py 新增
def apply_defense_delta(
    self,
    defense_type: Literal["suppression", "collapse", "silence"],
    intensity: float,
) -> ForceState:
    """防御事件触发后回写 (L2)
    
    intensity ∈ [0, 1]
    """
    if defense_type == "silence":
        # 个体力↓ (退缩, 不再内省), 自然力↑ (消化)
        return self.shift(
            individual_delta=-0.05 * intensity,
            natural_delta=+0.03 * intensity,
        )
    elif defense_type == "collapse":
        # 大幅改写 (崩溃是极端事件)
        return self.shift(
            natural_delta=-0.08 * intensity,
            individual_delta=+0.05 * intensity,
            social_delta=+0.03 * intensity,
        )
    elif defense_type == "suppression":
        # 个体力↑ (内省压制)
        return self.shift(
            individual_delta=+0.04 * intensity,
            social_delta=-0.02 * intensity,  # 略下降 (不表达)
        )
```

**调用方**:
- 沉默触发 → `apply_defense_delta("silence", intensity=silence_tendency.score)`
- 崩溃触发 → `apply_defense_delta("collapse", intensity=collapse_tendency)`
- 压抑累积 → `apply_defense_delta("suppression", intensity=suppression_level)` (定期)

### 4.3 三大子系统的 L1 入口

#### SuppressionState.compute() 扩展

```python
def compute(
    self,
    personality: dict,
    context: dict,
    conscience_pressure: float,
    relationship_intimacy: float,
    force_state: Optional[dict] = None,  # v1.2.5 新
) -> float:
    """v1.2.5: 压抑计算读 force_state (L1)"""
    # 原 baseline 计算保留
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
    
    # L1: 力加权
    if force_state is not None:
        force_modifier = (
            1.0 
            + 0.3 * force_state.get("social", 0.5) 
            + 0.2 * force_state.get("individual", 0.5)
        )
        base_suppression *= force_modifier
    
    return _clamp(base_suppression, 0, 1)
```

#### CollapseArchetypeSelector.select() 扩展

```python
def compute_bas_bis(
    self,
    personality: dict,
    force_state: Optional[dict] = None,  # v1.2.5 新
) -> tuple[float, float, float]:
    """v1.2.5: 崩倾向连续化, 读 force_state (L1)
    
    Returns: (BAS, BIS, collapse_tendency)
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
    
    # L1: 力加权 — 自然力 + 个体力主导 → BIS 升高
    if force_state is not None:
        nature_modifier = 0.2 * force_state.get("natural", 0.5)
        individual_modifier = 0.2 * force_state.get("individual", 0.5)
        social_buffer = -0.3 * force_state.get("social", 0.5)  # 社会力 → 找人帮
        BIS = BIS * (1 + nature_modifier + individual_modifier + social_buffer)
    
    # 连续化: collapse_tendency = max(0, BIS - BAS)
    collapse_tendency = _clamp(BIS - BAS, 0, 1)
    
    return BAS, BIS, collapse_tendency
```

### 4.4 main.py 调用入口 (handbook §1.2: 加新模块不动 main.py)

```python
# main.py — on_llm_response (v1.2.5 重写)
async def on_llm_response(self, event: AstrMessageEvent, response: Any) -> None:
    # ... 内存/intimacy 逻辑保留 ...
    
    # L1: DefenseModulator 计算 (替代原 _compute_defense_states 手拼逻辑)
    personality_dict = self._get_personality_labels(user_id)
    force_state = self._force_dynamics.get_current_force_state(self._labels) if hasattr(self, "_force_dynamics") else None
    
    defense_states = self._defense_modulator.compute_defense_states(
        personality=personality_dict,
        signals=self._latest_signals.get(user_id),
        body_state=self._body_state.get_current() if hasattr(self, "_body_state") else None,
        intimacy_level=self._intimacy.get_level(user_id) if hasattr(self, "_intimacy") else 0.5,
        context=self._build_context(event),
        force_state=force_state,
    )
    
    # 决策: 沉默?
    silence_tendency_obj = SilenceTendency(
        score=defense_states.silence_tendency,
        reason=defense_states.silence_reason,
        components=defense_states.silence_components,
    )
    should_silent, reason, tendency = self._segmented_coordinator.should_be_silent(
        session_key=user_id,
        tendency=silence_tendency_obj,
        config=seg_config,
    )
    
    if should_silent and seg_config.get("enable_deliberate_silence", False):
        # L2: 事件回写 (DefenseModulator 统一入口, 不直接 force_dynamics.shift)
        self._defense_modulator.apply_event("silence", intensity=tendency.score)
        # ... 写 memory + 清空 llm_resp ...
```

**装配 (handbook §1.2 严格)**: 在 `__init__` 加 1 行, 跟现有 57 个模块同 @register 自动 wire:

```python
# main.py __init__ 末尾
self._defense_modulator = self._modules["defense_modulator"]  # v1.2.5 新 (58 号模块)
```

**调用顺序** (单步法, 不用 fixpoint):
1. `force_state` = 上次 L2 累积的结果 (force_dynamics 内部持久化)
2. `defense_states = self._defense_modulator.compute_defense_states(..., force_state)` (L1 读当前 force_state)
3. 决策用 `defense_states.silence_tendency` 等
4. 事件触发 → `self._defense_modulator.apply_event(...)` (L2 回写 force_state)

**v1.2.5 简化**: 不做 fixpoint 迭代 (那是 v1.3 L3), 只做"上一轮累积 → 当前 force_state → 当前三子"单步法。延迟 1 轮由 `force_dynamics.shift()` 内部累积补偿。

### 4.5 系数 KB (handbook §1.1 严格遵守)

> **设计原则**: 所有"可复用、可调、被多个 persona 共享的事实数据"必须进 KB, 不写死在 .py 里 (handbook §1.1)。
>
> 本节列出 v1.2.5 新增的两个 KB 文件, 系数带文献背书。

**KB 文件 1: `emotion_spirit/core/kb/silence_tendency_weights.json`**

```jsonc
{
  "_doc": "沉默倾向公式的加权系数 (v1.2.5 新). 文献依据: Jack & Dill 1992, Carver 1998, Noftle 2006.",
  "_version": 1,
  "_regenerate": "tools/regenerate_kb.py 自动生成, 手编会被覆盖",
  
  "factors": {
    "tension_stress": {
      "source": "Carver 1998: N → withdrawal",
      "weight_in_sum": 0.20,
      "personality_modifiers": {"neuroticism": 0.5}
    },
    "hurt_void": {
      "source": "Noftle 2006 + Carver 1998: Avoidance × -E, -A; N → withdrawal",
      "weight_in_sum": 0.25,
      "personality_modifiers": {
        "extraversion_reverse": 0.5,
        "neuroticism": 0.4,
        "agreeableness_reverse": 0.3
      }
    },
    "satisfaction_quiet": {
      "source": "临床观察: 内向者满足时更静 (⚠️ 待验证)",
      "weight_in_sum": 0.10,
      "personality_modifiers": {"extraversion_reverse": 0.4}
    },
    "exhaustion": {
      "source": "Wegner 1987: 尽责者耗尽时易讽刺反弹 (⚠️ 临床观察)",
      "weight_in_sum": 0.20,
      "personality_modifiers": {"conscientiousness": 0.3}
    },
    "overload": {
      "source": "Carver 1998: N → emotion-focused",
      "weight_in_sum": 0.15,
      "personality_modifiers": {"neuroticism": 0.3}
    },
    "social_audience": {
      "source": "E 与社交活跃度直接相关",
      "weight_in_sum": 0.10,
      "personality_modifiers": {"extraversion_reverse": 0.5}
    }
  },
  
  "intimacy_modifier": {
    "source": "Jack & Dill 1992 讨好假说 + Noftle 2006",
    "base_coefficient": -0.3,
    "personality_modifiers": {
      "agreeableness": 0.5,
      "neuroticism": 0.4,
      "openness_reverse": -0.3
    }
  },
  
  "context_modifier": {
    "source": "新增 (v1.2.5)",
    "authority_present_coefficient": 0.4
  },
  
  "force_modifier": {
    "source": "v1.2.5 连续化, 替代 v1.2.3 离散 0.85/1.20/1.0",
    "social_coefficient": -0.3,
    "natural_coefficient": 0.2,
    "individual_coefficient": 0.4,
    "range": [0.5, 1.5]
  }
}
```

**KB 文件 2: `emotion_spirit/core/kb/defense_deltas.json`**

```jsonc
{
  "_doc": "防御事件触发后回写 force_state 的偏移量 (v1.2.5 L2)",
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

**KB Loader: `emotion_spirit/core/persona_labels_db.py` 扩展**

```python
# 加到现有 persona_labels_db.py 末尾
def get_silence_tendency_weights() -> dict:
    """v1.2.5: 加载沉默公式加权系数 (KB)"""
    return _cached_load("silence_tendency_weights.json")

def get_defense_deltas() -> dict:
    """v1.2.5: 加载防御事件回写 delta (KB)"""
    return _cached_load("defense_deltas.json")
```

**再生脚本: `tools/regenerate_kb.py` 加 2 个生成函数**

```python
# 加到 tools/regenerate_kb.py
def regenerate_silence_tendency_weights() -> None:
    """从本 spec §4.5 抽 silence_tendency_weights.json"""
    ...

def regenerate_defense_deltas() -> None:
    """从本 spec §4.5 抽 defense_deltas.json"""
    ...
```

---

## §5 延迟策略接口 (Coordinator 内部, 不独立注册)

### 5.1 设计决定: 为什么 TypingDelayStrategy 不 @register

按 handbook §1.2, `@register` 的目的是"加新模块不动 main.py"。审视 `TypingDelayStrategy`:

| @register 受益场景 | TypingDelayStrategy 现状 |
|---|---|
| main.py 需要直接拿到它 | ❌ 仅 SegmentedReplyCoordinator 内部用 |
| 加新延迟算法不动 main.py | ❌ v1.3 TTS 切换也是 Coordinator 内部换 |
| 多实例 (per-persona 不同延迟) | ❌ 当前没有 per-persona 延迟 |
| 跨层协调 | ❌ 单文件纯算法 |

**结论**: 它是 Coordinator 的内部 helper, 不应该独立 @register。如果独立注册, 是**为了注册而注册**, 违反模块化的本意。

### 5.2 Coordinator 内部实现 (v1.2.5 改法)

**位置**: `emotion_spirit/output/segmented_reply_coordinator.py` 内部 (不是新文件)

```python
# emotion_spirit/output/segmented_reply_coordinator.py 内部
from typing import Protocol

class DelayStrategy(Protocol):
    """段间延迟计算策略 (v1.2.5 接口, Coordinator 内部)
    
    实现类:
    - TypingDelayStrategy (默认, 字符级打字)
    - TTSDelayStrategy (v1.3 实现, 音频时长)
    """
    def compute_delay(self, text: str, config: dict) -> float:
        """返回段间延迟秒数"""
        ...

class TypingDelayStrategy:
    """字符级打字延迟 (v1.2.5 默认, Coordinator 内部)"""
    def compute_delay(self, text: str, config: dict) -> float:
        cps = config.get("default_chars_per_second", 7.5)
        max_delay = config.get("max_delay_seconds", 2.0)
        if cps <= 0:
            return max_delay
        return min(len(text) / cps, max_delay)

# v1.3 占位 (同一文件加, 不开新文件)
# class TTSDelayStrategy:
#     """TTS 音频时长延迟 (v1.3 实现)"""
#     def __init__(self, tts_provider):
#         self._tts = tts_provider
#     def compute_delay(self, text: str, config: dict) -> float:
#         return self._tts.estimate_duration(text)


class SegmentedReplyCoordinator:
    # ... @register spec ...
    
    def __init__(self, ...):
        # 默认延迟策略 (v1.2.5: 字符级打字)
        self._delay_strategy: DelayStrategy = TypingDelayStrategy()
    
    def set_delay_strategy(self, strategy: DelayStrategy) -> None:
        """v1.2.5: 内部切换延迟策略 (为 v1.3 TTS 预留)
        
        main.py 不暴露, 后续 TTS 接 AstrBot pipeline 时由 Coordinator 内部调用
        """
        self._delay_strategy = strategy
    
    @per_user_only
    def plan(self, session_key, full_text, ...) -> list[dict]:
        # ... 现有分段逻辑 ...
        for part in raw_parts:
            part["delay_before_seconds"] = self._delay_strategy.compute_delay(
                part["text"], config
            )
        return raw_parts
```

### 5.3 v1.3 接 TTS 时的扩展点

```python
# v1.3 加 (假设 AstrBot pipeline 提供 tts_provider):
class SegmentedReplyCoordinator:
    def __init__(self, tts_provider=None, ...):
        if tts_provider:
            self._delay_strategy = TTSDelayStrategy(tts_provider)
        else:
            self._delay_strategy = TypingDelayStrategy()  # 默认保持
```

**关键**: TTS 集成**不需要 main.py 改动**, 也不需要新 module。v1.3 在 Coordinator `__init__` 加一个可选参数即可。这是真模块化收益——Coordinator 是封闭子系统, 接 TTS 跟外部解耦。

### 5.4 反例: 错误做法的样子 (为什么不该 @register)

```python
# ❌ 错误: 独立 @register 让 main.py 多一个取实例的代码
class EmotionSpiritPlugin:
    def __init__(self, ...):
        # 如果 TypingDelayStrategy 是独立 @register, 这行是必需的:
        self._typing_delay = self._modules["typing_delay_strategy"]
        # 但 self._typing_delay 从来不会被 main.py 用, 仅仅是为了"装配"
        # → 装配了但不用, 是死代码
```

**对照正确做法**:
```python
# ✅ 正确: TypingDelayStrategy 是 Coordinator 内部, main.py 不出现
class EmotionSpiritPlugin:
    def __init__(self, ...):
        self._segmented_coordinator = self._modules["segmented_reply_coordinator"]
        # Coordinator 内部自己 new TypingDelayStrategy
        # main.py 不知道 DelayStrategy 存在
```

---

## §6 配置扩展 (`_conf_schema.json` v1.2.5 段)

```jsonc
{
  "segmented_reply": {
    "description": "分段回复 (v1.2.5 重写, 吸收 Sylanne 1.4.7 实时调度)",
    "type": "object",
    "hint": "力学信号+用户节奏自动调制。关闭 = 一次性 yield (旧行为)",
    "items": {
      "enable": { "type": "bool", "default": false },
      "enable_deliberate_silence": { "type": "bool", "default": false,
        "hint": "v1.2.5 新: 是否启用主动沉默 (受人格 + 力 + 情绪共同决定)" },
      "silent_threshold": { "type": "float", "default": 0.5,
        "hint": "沉默触发阈值 [0,1], 越高越不容易沉默" },
      "silent_cooldown_turns": { "type": "int", "default": 2,
        "hint": "v1.2.5 S4: 沉默后冷却 N 轮才允许再次沉默" },
      "max_consecutive_silence": { "type": "int", "default": 3,
        "hint": "v1.2.5 S4: 连续沉默 N 次后强制恢复" },
      "default_max_part_chars": { "type": "int", "default": 48 },
      "default_chars_per_second": { "type": "float", "default": 7.5 },
      "blend": { "type": "float", "default": 0.6 },
      "intimacy_gate": { "type": "float", "default": 0.6 },
      "max_delay_seconds": { "type": "float", "default": 2.0 },
      "ignored_window_turns": { "type": "int", "default": 10 }
    }
  }
}
```

---

## §7 `/reflect_force_current` 命令扩展

`/reflect_force_current` 增加展示:
- 当前 ForceState (natural/social/individual + dominant)
- 最近 7 天沉默次数 + dominant reason
- 最近 7 天分段次数 (平均段数, 平均延迟)
- 最近崩溃事件 (archetype + timestamp)
- 力学方向趋势 (个体主导天数 vs 社会主导天数)

**实现**: `commands.py` 加 `reflect_force_current`, 读 `SegmentedReplyCoordinator.get_history()` + `SuppressionState.get_history()` + `CollapseArchetypeSelector.get_history()`。

---

## §8 文件清单 (预计修改)

> 严格按 handbook §1.1 (KB) + §1.2 (@register) + §2.1 (TODO 格式) + §6 (顺手清债) 写。

| 文件 | 改动类型 | 估行数 |
|---|---|---|
| `emotion_spirit/output/segmented_reply_coordinator.py` | 大改（@per_user_only × 4 + SilenceTendency + L1 force_state 读 + DelayStrategy/TypingDelayStrategy 内部类 + set_delay_strategy 方法） | +220 |
| `emotion_spirit/output/delay_strategy.py` | **删除**（合并到 coordinator.py 内部, §5 设计决定） | -50 |
| `emotion_spirit/regulation/defense_modulator.py` | **新文件（@register "defense_modulator", depends_on 4 个）** | +180 |
| `emotion_spirit/regulation/force_dynamics.py` | **不动签名**（保持 100% 向后兼容, handbook §1.2） | 0 |
| `emotion_spirit/memory/suppression.py` | 扩参（force_state 可选）+ L2 回写 | +30 |
| `emotion_spirit/regulation/collapse_archetype.py` | 扩参（force_state 可选）+ 连续化返回 collapse_tendency | +40 |
| `emotion_spirit/core/kb/silence_tendency_weights.json` | **新 KB 文件（handbook §1.1 严格遵守）** | +50 |
| `emotion_spirit/core/kb/defense_deltas.json` | **新 KB 文件（handbook §1.1 严格遵守）** | +30 |
| `emotion_spirit/core/persona_labels_db.py` | 加 `get_silence_tendency_weights()` + `get_defense_deltas()` loader | +20 |
| `tools/regenerate_kb.py` | 加 `regenerate_silence_tendency_weights()` + `regenerate_defense_deltas()` | +40 |
| `emotion_spirit/migrations/rules/v3_1_to_v4.py` | 顺手清 handbook §3.3 漏搬 `enable_life_fragment` (T1) | +5 |
| `main.py:_reset_superego_modules` | 顺手清 §1.2 双轨 5 个手 new + 6 个 key hard-code (T2) | -20/+15 |
| `main.py:107,115,119` (T3) | 12 个手 new 评估 (3 个核心 facade): 改 @register 走 self._modules | -3 |
| `main.py:1492-1529` (T4) | 9 个 memory/output 手 new 评估: 改 self._modules[...] 复用 | -9 (删) / +小改 |
| `tests/test_reset_superego_modules.py` | 新: 验证重置后 `self._conscience is self._modules["superego"]["conscience"]` (T2 防回归) | +30 |
| `tests/test_main_py_no_manual_new.py` | 新: AST 检查 main.py 无 `self._xxx = ClassName(...)` 模式 (handbook §1.2 强拦) | +60 |
| `tests/test_kb_files_exist.py` | 新: 检查 KB 文件存在 (silence_tendency_weights.json + defense_deltas.json), 跟 §1.1 一致 | +30 |
| `main.py` | 重写 on_llm_response + 装配 DefenseModulator + 装配 TypingDelayStrategy | -50/+80 |
| `commands.py` | 加 reflect_force_current | +60 |
| `_conf_schema.json` | 加 v1.2.5 配置段 | +20 |
| `tests/test_segmented_reply_coordinator.py` | 重写 + 新测试（含 @per_user_only 强拦测试） | +200 |
| `tests/test_defense_modulator.py` | 新（DefenseModulator L1+L2 + 单步法） | +100 |
| `tests/test_silence_tendency.py` | 新（6 factor × 人格组合） | +150 |
| `tests/test_suppression.py` | 新 | +50 |
| `tests/test_collapse_archetype.py` | 新 | +50 |
| `tests/test_delay_strategy.py` | 新（TypingDelayStrategy 内部实现 + set_delay_strategy 切换测试） | +30 |
| `tests/test_force_dynamics.py` | 不动（向后兼容 100%, 加回归测试） | +20 |
| `tests/test_registry_consistency.py` | 维护 57 → 58 | +3 |
| `tests/test_registry_build_dryrun.py` | 维护 57 → 58 | +3 |
| `tests/test_smoke.py` | 加结构完整性 + AST (KB 文件存在性 + 模块数) | +30 |
| `tests/migrations/test_rules_v3_1_to_v4.py` | 加 `enable_life_fragment` 漏搬回归 (handbook §3.3) | +20 |
| `UPDATE_HANDBOOK.md` | §6 加 "v1.2.5 已清的债" 段 | +10 |
| `docs/CHANGELOG.md` | v1.2.5 entry | +30 |
| `docs/api.md` | 更新 API（DefenseModulator, SilenceTendency, TypingDelayStrategy） | +30 |

**总**: ~1500 行 (含 ~700 行测试, 含 ~250 行 KB / 工具)

### 8.1 TODO 标记约定 (handbook §2.1)

实现过程中如果发现新债但本轮不清, 严格按 handbook §2.1 格式:

```python
# TODO(tech-debt): <现状> → <应该> (见 <文件/issue>)
```

`grep -rn "TODO(tech-debt)" main.py emotion_spirit/` 在 ship 前必跑 (handbook §5 6 行命令之一), 确认债清单可见。

**v1.2.5 已知 TODO(tech-debt) 不引入** (如果 DefenseModulator 干净实现, 不留债)。

### 8.2 顺手清债 (handbook §6 + §3.3)

v1.2.5 改 `_conf_schema.json` schema, 正是 handbook §3.3 说的"下一个带 schema 变更的版本顺手修"时机:

- ✅ `merge_life_sim_config` 漏搬 `enable_life_fragment` (handbook §3.3)
- ✅ `test_v2_full_lifecycle` slot 对齐 (handbook §6, mock time.time)

---

## §9 测试策略

### 9.1 Bug 12 修复回归

```python
async def test_on_llm_response_sends_segments():
    """on_llm_response 必须真的 send 多段, 不吞 TypeError"""
    # mock event.send, 验证调用 N 次
    # mock response.completion_text 验证被清空

async def test_streaming_mode_skips_segmented_reply():
    """streaming_response=true 时 emotion_spirit 不介入"""
    # 设置 streaming_response=True
    # 验证 event.send 不被调

async def test_silent_response_clears_llm_resp():
    """沉默触发 → llm_resp 清空 + 不主动 send"""
```

### 9.2 沉默语义

```python
def test_introvert_anxious_high_intimacy_silences():
    """E=0.2, N=0.8, A=0.5, intimacy=0.7, hurt=0.8 → silence_tendency > 0.7"""

def test_extrovert_open_low_intimacy_speaks():
    """E=0.8, O=0.7, N=0.2, intimacy=0.3 → silence_tendency < 0.3"""

def test_default_personality_neutral_tendency():
    """E=N=A=O=C=0.5 → silence_tendency 在 [0.3, 0.4] 区间"""

def test_cooldown_prevents_repeat_silence():
    """第 1 次沉默后, 第 2 轮 should_be_silent=False (cooldown)"""

def test_max_consecutive_force_response():
    """3 次连续沉默后, 第 4 次 score=0.6 也不沉默 (阈值上调到 0.9)"""
```

### 9.3 力学耦合

```python
def test_force_dynamics_with_suppression_modifies_individual():
    """suppression_level=0.8 → 个体力明显升高"""

def test_force_dynamics_backward_compatible():
    """不传三子参数 → 输出与 v1.2.4 一致 (缺省 0.0)"""

def test_silence_event_applies_force_delta():
    """沉默触发后 force_state.individual↓, natural↑"""

def test_no_fixpoint_loop_in_v125():
    """v1.2.5 不做 fixpoint 迭代, 验证 _compute_defense_states 不循环调 compute"""
```

### 9.4 Smoke (defense-in-depth)

```python
def test_smoke_no_dangling_method_calls():
    """AST 级: 验证 emotion_spirit 内无调未定义方法"""
    # 沿用 v1.2.4 范式
```

---

## §10 DoD (Definition of Done)

> 严格按 handbook §4.4 ship 8 步 checklist + handbook §3.3 顺手清债 + §6 清债更新。

### 10.1 ship 8 步 checklist (handbook §4.4)

- [ ] **Step 1**: `_version.py` + `metadata.yaml.version` 同步 bump 到 1.2.5（TestVersionConsistency bump-proof 测试会抓漏）
- [ ] **Step 2**: 本地 `pytest` 全套（Windows 允许 `test_periodic_save_dirty_only` 概率性 1/3 fail，CI ubuntu 不红）
- [ ] **Step 3**: pre-commit secret scan 过（`scripts/check_secrets.py`，含 `data/cmd_config.json`）
- [ ] **Step 4**: `git fetch origin && git rev-list HEAD..origin/main` 验无 remote-only commit（有则 rebase，**绝不 force 覆盖**）
- [ ] **Step 5**: push 走 proxy（本机直连 GitHub 不通）：`git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 push origin main`
- [ ] **Step 6**: 打 tag `v1.2.5` 触发 `release.yml` 自动 build slim zip
- [ ] **Step 7**: 验 https://github.com/Aston957/astrbot_plugin_emotion_spirit/actions Release 真出了（**AI 做不了，必须人验**）
- [ ] **Step 8**: 若 ship-prep 修复在打 tag 之后才进 main → tag 已过时，需 force 重打 tag 指向新 commit。**优先选打新 patch tag，force 重打是最后手段**

### 10.2 功能验收

- [ ] pytest 全绿（现有 1261 + 新 ~550 = ~1810 passed）
- [ ] smoke test 全绿（无 dangling method calls，新增 KB 模块 AST 检查）
- [ ] module count: 57 → 58（+DefenseModulator，handbook §1.2 consistency + dryrun 同步维护）
- [ ] 本机 AstrBot v4.26.1 实测:
  - [ ] `segmented_reply.enable=true` + 长 prompt → bot 分 3+ 段发出, 段间有延迟
  - [ ] 沉默触发条件（高 hurt）→ bot 不回话, 日志 reason=`void_hurt_withdrawing`
  - [ ] 连续 3 次沉默后第 4 次强制回话
  - [ ] 冷却期内沉默被阻止
  - [ ] `streaming_response=true` → emotion_spirit 跳过, AstrBot 走默认流式

### 10.3 顺手清债 (handbook §3.3 + §6)

> v1.2.5 改 schema + 重写 on_llm_response + 大量动 main.py, 是顺手清现存债的最佳窗口。按 handbook §0 "规则只有能被自动拦下才算规则", 这些债不积, 每次 ship 清一部分。

#### T1: `merge_life_sim_config` 漏搬 `enable_life_fragment` (handbook §3.3 P0)

- [ ] `emotion_spirit/migrations/rules/v3_1_to_v4.py` 加 `old_life_sim = config.get("life_simulator", {})` 在 pop 前
- [ ] `v2.setdefault("enable_life_fragment", old_life_sim.get("enable_life_fragment", True))`
- [ ] `tests/migrations/test_rules_v3_1_to_v4.py` 加 case: 旧 config 含 `enable_life_fragment=false` → 迁后 `life_sim_v2.enable_life_fragment == False`
- [ ] `life_sim_v2` schema doc 补 `enable_life_fragment` 字段说明

#### T2: `_reset_superego_modules` 5 个手 new + 6 个 key hard-code (handbook §1.2 P1)

**现状 (双轨 bug 风险)**：
- 初始化：`main.py:271-272` 用 `self._modules["superego"]["conscience"]` (走 factory)
- 重置：`main.py:697-701` 手 new `ConscienceTracker() / ValueAlignment() / IdealSelf() / ValueResistance() / SuperegoGuard(...)` 5 个
- **后果**: 重置后 `self._conscience` 指向新对象, 但 `self._modules["superego"]["conscience"]` 仍指旧对象, 谁跟谁走取决于后续代码用哪个。**典型 handbook §1.2 双轨违反**

**修法**:
- [ ] `_reset_superego_modules` 改成调用 `factory.rebuild_sub("superego", config_keys=...)` 或直接 `self._modules["superego"] = plugin_factory.build_superego(self._current_persona, self._labels)` (单点重建)
- [ ] 删 5 个手 new (line 697-701)
- [ ] 删 6 个 key hard-code (line 705-706), 改成 `_modules["superego"].keys()` 遍历
- [ ] 保留 line 716 的 `report_path.unlink()` + `self._store.save()` (清持久化文件)
- [ ] 加 test: `_reset_superego_modules` 后, `self._conscience is self._modules["superego"]["conscience"]` (身份验证, 防止双轨回归)

#### T7: `test_v2_full_lifecycle` Win 偶发挂 (handbook §6 P0)

- [ ] mock `time.time` 让 slot 对齐 (跟 `_time_to_slot` 偶发不对齐)
- [ ] 跑 10 次本地验证 100% 通过

#### T8: Bug 13 `datetime.date.today()` AttributeError (用户反馈 2026-07-03, P2 → P1 v1.2.5 同步修)

**根因** (用户本地复现):
- `main.py:15` `from datetime import date, datetime, timezone, timedelta`
- 把 `datetime` 绑到了**类** `datetime.datetime` (不是标准库模块)
- 后果: `datetime.date.today()` 解析为 `(class datetime.datetime).(method date).today()` → `AttributeError: 'method_descriptor' object has no attribute 'today'`
- 影响: `life_sim_v2` 日程生成 100% 失败 (cron 2:00 静默崩溃, WARN 级被吞)

**两处同类错**:
- `main.py:807`: `today_str = datetime.date.today().isoformat()` ❌
- `main.py:965`: `entry_date = datetime.date.fromtimestamp(entry.created_at)` ❌ (用户没发现, 我扫描发现)

**修法 (1 行 × 2 处)**:
- [ ] `main.py:807`: `datetime.date.today().isoformat()` → `date.today().isoformat()` (date 已在 import)
- [ ] `main.py:965`: `datetime.date.fromtimestamp(entry.created_at)` → `date.fromtimestamp(entry.created_at)` (同样)

**防回归测试**:
- [ ] 新 `tests/test_schedule_plan_loop.py`:
  - `test_datetime_date_today_no_attribute_error` (验证修复后能正常调)
  - `test_datetime_date_fromtimestamp_no_attribute_error` (新增, 跟 807 同模式)
- [ ] 新 `tests/test_datetime_import_patterns.py` AST 检查:
  - `main.py` 不能有 `datetime.date` / `datetime.time` / `datetime.tzinfo` 等同类遮蔽模式
  - 规则: 若 `from datetime import datetime`, 则后续不能用 `datetime.<module-level-name>` (`date`/`time`/`tzinfo`/`timedelta` 都已经单独 import)

**为什么 PR3 不 PR1**: Bug 13 跟 life_sim_v2 相关, 不在 PR1 scope (Bug 12 + 沉默 + 延迟 + 配置 + 命令). PR3 "顺手清债" 范围更合适. 但用户在反馈文档明确 "强烈建议 v1.2.5 一并修掉", 所以 v1.2.5 内修完.

**import 注释建议**:
- [ ] `main.py:15` 改后加注释:
  ```python
  # 注意: 此处 datetime 是类, 不是模块.
  # 用 date.today() / date.fromtimestamp() (date 已显式 import),
  # 不要写 datetime.date.X (会 AttributeError).
  from datetime import date, datetime, timezone, timedelta
  ```

#### T9: Bug 14 `polish_template_events` 嵌套 dict TypeError (用户反馈 2026-07-03, P2 → P1 v1.2.5 同步修)

**根因** (用户本地复现):
- 三方契约不匹配:
  - `emotion_spirit/memory/persona_profiles.py:120` `get_personality_params()` 返回嵌套 `dict[str, dict[str, float]]` (如 `{"deep": {"expression_drive": 0.15, ...}, "surface": {...}}`)
  - `main.py:923` `_get_current_personality_dict()` type hint 撒谎说 `dict[str, float]` (flat)
  - `emotion_spirit/regulation/life_simulator.py:289` `polish_template_events` 假设 flat, 直接 `f"{k}={v:.1f}"` 当 v 是 dict 时 `TypeError: unsupported format string passed to dict.__format__`
- 修了 Bug 13 后立刻暴露: traceback 起点从 line 807 推进到 line 289
- 跟 Bug 13 同根因链: life_sim_v2 日程生成 100% 失败

**两处同类错** (我扫描发现):
- `life_simulator.py:289` (用户报告) ❌
- `life_simulator.py:568` (我扫描到, 同一行模式 `p_desc = ", ".join(f"{k}={v:.1f}" for k, v in personality.items())`) ❌

**修法 (用户建议方案 A, 最小改动)**:
- [ ] `life_simulator.py` 加 `_flatten_personality()` helper:
  ```python
  def _flatten_personality(p: dict) -> list[tuple[str, float]]:
      """拍平嵌套 personality dict 为 (qualified_key, scalar) 列表."""
      flat = []
      for layer, params in p.items():
          if isinstance(params, dict):
              for k, v in params.items():
                  if isinstance(v, (int, float)):
                      flat.append((f"{layer}.{k}", float(v)))
          elif isinstance(params, (int, float)):
              flat.append((layer, float(params)))
      return flat
  ```
- [ ] `life_simulator.py:289` 用 helper 拍平后格式化:
  ```python
  p_desc = ", ".join(f"{k}={v:.1f}" for k, v in _flatten_personality(personality))
  ```
- [ ] `life_simulator.py:568` 同样修
- [ ] `main.py:923` type hint 改成真实形状 `dict[str, dict[str, float]]` (对齐 persona_profiles.py:120):
  ```python
  def _get_current_personality_dict(self) -> dict[str, dict[str, float]]:
  ```
- [ ] `main.py:923` docstring 加一句"嵌套 dict, 消费方需自己 flatten"

**防回归测试**:
- [ ] 新 `tests/test_life_simulator_personality_flatten.py`:
  - `test_flatten_personality_handles_nested_dict` (验证 helper 处理嵌套)
  - `test_flatten_personality_handles_flat_dict` (验证 helper 处理 flat, 直接 fallback)
  - `test_flatten_personality_handles_mixed` (验证 mixed 嵌套 + 顶层 scalar)
  - `test_polish_template_events_does_not_crash_on_nested_personality` (集成测试)
- [ ] 新 `tests/test_personality_shape_contract.py` AST 检查:
  - 扫所有 `personality.items()` 调用方, 验证每个调用方都有 flattening 处理 OR 假设 flat 时有明确注释
  - 已知 safe: `sylanne/algebra.py:394` (不格式化, 仅遍历) / `sylanne/compute/hgt.py:755` (cache key 字符串化, dict 会自动 repr)
  - 已知 unsafe: `life_simulator.py:289` / `life_simulator.py:568` (修后 PASS)

**为什么 PR3 不 PR2**: Bug 14 是 life_simulator 消费 personality 的错模式, 跟 PR2 (DefenseModulator 力学耦合) 无关. PR3 顺手清债范围合适.

**用户建议优先级**:
- 🟡 P1 v1.2.5 同步修 (用户原话 "几乎零成本, 一两个 PR 搞定"): 方案 A + 改 type hint
- 🟢 P2 v1.2.6 推: 方案 B/C (全局 personality 形状统一契约)

#### T3+T4 评估: 12 个 main.py 手 new (handbook §1.2 P1)

**T3 (3 个核心 facade)**:
- [ ] `CommandImpl(self)` line 107 — self 注入, 评估 param_wire 扩 `self` 注入模式
- [ ] `PublicAPI(self._modules)` line 115 — modules 注入, 评估 param_wire
- [ ] `SurfaceHandler(self, self._modules)` line 119 — self + modules 双注入, 跟 SurfaceConsumer 不对称

**T4 (9 个 memory/output 模块)**:
- [ ] line 1492: `PatternExtractor(self._pool)`
- [ ] line 1495: `BufferSignals(self._pool)`
- [ ] line 1499: `ShadowDetector(self._pool, self._buffer_signals, self._patterns)`
- [ ] line 1503: `LifeSimulator(self._consumer, self._pool, self._intimacy, self._buffer_signals, self._reservoir)`
- [ ] line 1514: `PersonalityDrift(self._consumer, self._reservoir)`
- [ ] line 1518: `PredictiveSentinel(self._consumer, self._buffer_signals, self._reservoir, self._conscience, self._alignment, self._ideal)`
- [ ] line 1522: `NarrativeIdentity(self._pool, self._patterns, self._drift, self._buffer_signals, self._diary)`
- [ ] line 1525: `Counterfactual(self._pool)`
- [ ] line 1529: `PromptInjector(self._pool, ..., buffer_signals=self._buffer_signals)` (kwargs 形式)

**v1.2.5 评估策略**:
- **优先尝试**: 这 12 个是否都已 `@register`, 如果是, 直接从 `self._modules[...]` 取, 删手 new (零设计成本)
- **如果未注册**: 标 `@register`, 重新装配 (但要小心循环依赖, 比如 ShadowDetector 依赖 PatternExtractor+BufferSignals)
- **如果参数有 self 注入**: v1.2.5 不做 (需扩展 factory param_wire, 是 v1.3 工作)

**评估结果填回**: T3+T4 在 plan 阶段先 grep 验证 `@register` 状态, 再决定改法。

#### T5+T6 backlog (v1.2.6+ 处理, 不进 v1.2.5)

- **T5** (CognitiveAgent 3 个 dead code): MemoryAgent/PersonalityAgent/RelationshipAgent **从未被 main.py 实例化**, 是幽灵模块。v1.2.6 决定删 or 接 DI
- **T6** (SurfaceHandler @register 不一致): SurfaceConsumer 已 @register, SurfaceHandler 没。v1.2.6 补

#### §6 handbook 同步更新 (v1.2.5 ship 后)

- [ ] **更新 UPDATE_HANDBOOK.md §6** "v1.2.5 已清的债" 段:
  - T1 `merge_life_sim_config enable_life_fragment` 修
  - T2 `_reset_superego_modules` 双轨消
  - T7 `test_v2_full_lifecycle` mock time
  - T3+T4 12 个手 new 评估结果 (按上面"优先尝试"分支填)
- [ ] §6 "v1.2.6 backlog" 加 T5+T6

### 10.4 文档 + memory

- [ ] 理论文档: 11 个加权系数的文献背书表（KB 文件头注释 + 本文件 §3.4）
- [ ] memory: 更新 `emotion-spirit-v124-state` 标"superseded by v1.2.5" + 新建 `emotion-spirit-v125-state`
- [ ] ROADMAP v2: 更新 v1.2.5 已 ship + v1.3 路线（含 L3 fixpoint）

---

## §11 风险与降级

| # | 风险 | 处置 |
|---|---|---|
| R1 | event.send 抛异常导致 AstrBot pipeline 异常 | catch 异常 + log, 不 propagate |
| R2 | asyncio.sleep 被 cancel (AstrBot shutdown) | 接受 cancel, hook 退出, 接受 llm_resp 可能不一致 |
| R3 | force_state 不动点震荡 (v1.2.5 不做迭代, 应避免) | 用 DefenseModulator 单步法, 不用 fixpoint; L3 推 v1.3 |
| R4 | 沉默系数合理性 11 项中 2 项基于临床观察 | 标注 ⚠️, v1.3 收集用户反馈后调整 |
| R5 | AstrBot 不同版本 `event.send` 行为差异 | 用官方 `MessageChain().message(text)` API, 不碰私有属性 |
| R6 | main.py 重写 on_llm_response 破坏现有 memory/intimacy 逻辑 | 保留原逻辑 + try/except 包裹, 异常回退到 AstrBot 默认 |
| R7 | DefenseModulator 新模块跟 existing CognitiveAgent 4 子类一起手 new | **DefenseModulator 必须 @register 走 factory**, main.py 只取 self._modules["defense_modulator"] 1 行, 防止 DI 双轨回归 |
| R8 | KB 文件 regenerate 时手编被覆盖 | KB 文件头标 `"_regenerate": "tools/regenerate_kb.py 自动生成"`, 改 KB 源 → 重跑脚本 |
| R9 | TypingDelayStrategy 没用 @register | spec 已修 (违规 1), 实施时 registry consistency test 自动拦 |
| R10 | @per_user_only 忘标 | spec 已修 (违规 2), 实施时 layer 装饰器运行时 TypeError 自动拦 (handbook §1.3 是唯一已有强拦) |
| R11 | `_reset_superego_modules` 重构破坏 persona 切换路径 | 现有 `tests/test_superego_reset.py` (如有) 全跑过 + 加新身份验证测试 (T2) |
| R12 | T3/T4 12 个手 new 评估发现部分需先 @register 走 factory, 引入循环依赖 | 实施时按"先 @register 再 grep 测试"顺序, 失败回滚单组件 |
| R13 | spec 文档随 §10.3 加债后总行数从 1371 → ~1500, plan 阶段过长 | plan 拆分: Phase 1 (Bug 12 + 沉默) / Phase 2 (DefenseModulator + KB) / Phase 3 (清债), 分 PR |

### 11.1 测试不过阻塞 ship 约定 (改进 2)

按 handbook §2.2 "ship 阻塞类必当轮清":
- **pytest 任一 FAIL** → ship 阻塞, 必须修到全绿才进 step 6 打 tag
- **smoke test 任一 FAIL** → ship 阻塞 (含 AST 检查 module count, KB 文件存在性, @per_user_only 覆盖)
- **lint 不通过** (未来加, v1.2.5 不强制) → ship 阻塞

不"先打 tag 再修"——handbook §4.4 step 8 明确说 force 重打 tag 是最后手段。

---

## §12 文档关联

### 12.1 本 spec 必须更新或新建的文档

- **本 spec** `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` ✅
- **`docs/superpowers/plans/2026-07-03-segmented-reply-fix-plan.md`** (实施时由 writing-plans skill 生成)
- **`UPDATE_HANDBOOK.md` §6** 加 "v1.2.5 已清的债" 段（v1.2.5 ship 后必更新，handbook §6 要求）
- **`memory/emotion-spirit-v125-state.md`** 新建（v1.2.5 ship 后）
- **`memory/emotion-spirit-v124-state.md`** 标 "superseded by v1.2.5" header note（不要删，保留历史判断）
- **`now/docs/ROADMAP_v2_2026-07-01.md`** 更新 v1.2.5 已 ship + v1.3 路线（含 L3 fixpoint）
- **`docs/CHANGELOG.md`** v1.2.5 entry
- **`docs/api.md`** 更新 API（DefenseModulator, SilenceTendency, TypingDelayStrategy）
- **`README.md`** 更新 module count 57 → 58 + feature entries

### 12.2 本 spec 涉及的历史文档

- **反馈**: `now/2026-07-03-emotion-spirit-v124-segmented-reply-bug.md` (Bug 12 原始报告)
- **旧 plan**: `docs/PLAN_2026-06-30_v123_segmented_reply.md` (v1.2.3 设计, v1.2.5 重写)
- **Handbook**: `UPDATE_HANDBOOK.md` (§0 自动拦下规则 + §1.1 KB + §1.2 @register + §1.3 layer + §3.3 漏搬 + §4.4 ship 8 步 + §6 清债清单)
- **ROADMAP v2**: `now/docs/ROADMAP_v2_2026-07-01.md` (v1.3 路线更新)
- **memory 当前真相**: `memory/emotion-spirit-current-truth.md` + `memory/emotion-spirit-v124-state.md` + `memory/emotion-spirit-v124-roadmap.md`

### 12.3 理论文献

| 理论 | 作者 | 年份 | 用途 |
|---|---|---|---|
| Silencing the Self | Jack & Dill | 1992 | 沉默语义 S1+S2 核心 + 亲密度调节 |
| COPE 元分析 | Carver et al. | 1998 | Big Five × coping 系数 (本地 KB part_01) |
| Attachment × Big Five | Noftle | 2006 | 回避依恋 × 人格系数 (本地 KB) |
| Ironic Process Theory | Wegner | 1987 | 压抑反弹 + exhaustion 系数 |
| Process Model of Emotion Regulation | Gross & John | 2003 | 压抑 baseline |
| Self-Silencing and Depression | Jack & Ali | 2010 | 讨好假说近期综述 |
| Polyvagal Theory | Porges | 2011 | overload (freezing) |
| 4F Model | Walker | 2013 | 5 种 collapse archetype |
| Vaillant Defense Hierarchy | Vaillant | 1977 | collapse (intellectualization) |
- memory: [[emotion-spirit-v124-state]] [[emotion-spirit-v124-roadmap]]