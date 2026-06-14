# ADR-0004: persona_id default 当 sentinel (不显式存 null)

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

emotion_spirit 维护"人格"概念,每个 user 可以绑定一个 `persona_id`(默认 `"default"`)。
持久化时,需要决定:无 persona 时存 `null`、空字符串、还是 `"default"` sentinel?

## Decision Drivers

* **持久化一致性**:JSON 不区分 `null` 和 missing,需要 sentinel
* **跨会话连续性**:user 临时切走再回来要恢复原 persona
* **简化下游代码**:`persona_id or "default"` 比 `persona_id if persona_id is not None else "default"` 简洁

## Considered Options

* **A**: 存 `null`,运行时 fallback 到 `"default"`
* **B**: 存 `""` (空字符串),运行时 fallback
* **C**: 存 `"default"` (sentinel),运行时直接用 ← 选定

## Decision Outcome

Chosen option: **C**,因为:

1. 持久化时"如果 persona 是 null 就存 'default'"统一一个写入点,避免散落
2. 读取时不用做 fallback,代码更直白:`state.persona_id` 永远是合法字符串
3. 跨 plugin 协作时(ProactiveChat / Sylanne adapter)无需处理 null
4. 调试时日志清晰(不会出现 persona_id=null 的困惑)

### Positive Consequences

* 写入侧单点处理,读取侧零成本
* 与 AstrBot / ProactiveChat 等共享 persona 概念时无需特殊协议
* 简化测试(不用 mock null)

### Negative Consequences

* "default" 这个字符串被硬编码,改名需全局搜索
* 用户如果想用 "default" 作为真实 persona 名,会冲突(但这是用户问题,不是设计问题)

### Confirmation

* 持久化 schema 中 `persona_id` 类型固定 `str`
* 代码中 grep `"default"` 应只在 persona_id 默认值定义处出现
* 单元测试: `set_persona(None)` 后 `get_persona() == "default"`

## More Information

* 实施于 v1.0.3(2026-Q1)
* 后续: v1.1.1 增强"情绪表示升级"时,persona_id 保持原设计
* 相关: `emotion-spirit-v103` memory
