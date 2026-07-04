# AstrBot Framework Issue — Bug-H reply preservation + send_delayed API

## Bug-H: respond.stage:287 Reply/At 检查误杀 emotion_spirit append chain

**环境**: AstrBot 4.26.4 Docker + emotion_spirit v1.3.0 rc.2 (append 模式)
**现象**: emotion_spirit append 模式 (segments → response.result_chain.chain.append(Plain)) → bot 完全不回复. AstrBot 报:
```
[respond.stage:287] 消息链全为 Reply 和 At 消息段, 跳过发送阶段。chain:
[Reply(type=..., id='...', chain=[], sender_id=0, sender_nickname='', time=0, ...)]
```
**期望**: chain 应含 emotion_spirit 写入的 Plain segments, 不该是 [Reply(placeholder)].

**静态分析**:
- emotion_spirit.on_llm_response append Plain 到 response.result_chain (LLMResponse)
- on_agent_done 传的 llm_response 跟 get_final_llm_resp() 同一对象 (self.final_llm_resp, coze:324+377 / dashscope:359+402 确认)
- aggregator.finalize (third_party.py:104-119): result_chain 非 None → final_chain = result_chain.chain (应读到 Plain)
- event.set_result(chain=final_chain) → result_decorate → respond.stage:287
- 实测 respond.stage 看到 [Reply(placeholder)] 而非 [Plain] → framework 在 aggregator → respond.stage 之间替换了 chain

**诊断 log (emotion_spirit 侧已加, rc.3)**: append 后 log chain 内容 + id(response). 若 emotion_spirit 写入含 Plain 但 framework 端读到 [Reply] → 确认 framework 替换.

**诉求**: 定位 framework 哪个 stage 把 [Plain] 换成 [Reply(placeholder)] (placeholder: chain=[], sender_id=0, time=0). 可能是 result_decorate 或 set_result 覆盖.

## send_delayed API 需求 (Bug-E 两全)

**背景**: emotion_spirit 分段回复 + meme_manager 表情包冲突.
- event_send 模式: 逐段 event.send + delay → 保打字节奏, 但绕过 on_decorating_result → meme_manager 表情包消失.
- append 模式: segments → result_chain → 经 on_decorating_result → 表情包回来, 但撞 Bug-H + 失段间 delay.

**诉求**: AstrBot 加 `event.send_delayed(parts, delays)` API:
```python
await event.send_delayed(
    parts=[MessageChain([Plain(seg1)]), MessageChain([Plain(seg2)]), ...],
    delays=[0.0, 1.5, 1.0],
)
```
**语义**: 每段延迟发 + 每段都触发 on_decorating_result (让 meme_manager append image). 这样 emotion_spirit 可同时保 delay + 表情包.