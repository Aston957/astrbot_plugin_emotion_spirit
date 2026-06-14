# ADR-0001: 4 层目录结构 (core/bridge/extensions/interfaces)

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

emotion_spirit v2.0.0v1 (2026-06-09) 之前的代码组织混乱:104 个模块散布在单层 `emotion_spirit/` 下,无清晰边界,导致:
- 跨模块循环 import 风险
- 公开 API 与内部实现混在一起
- 难以为扩展功能(如梦境生成器)找到合适位置

需要决定用几层目录以及每层职责。

## Decision Drivers

* **边界清晰**:core 不依赖 extensions/bridge
* **可扩展**:新增功能(梦境、力学引擎)有明确位置
* **公开 API 稳定**:`interfaces/` 明确定义对外暴露
* **易导航**:104 个模块按职责分组

## Considered Options

* **2 层**:`core/` + `interfaces/`
* **3 层**:`core/` + `bridge/` + `interfaces/`
* **4 层**:`core/` + `bridge/` + `extensions/` + `interfaces/` ← 选定
* **5 层**:`core/` + `bridge/` + `extensions/` + `interfaces/` + `adapters/`

## Decision Outcome

Chosen option: **4 层**,因为:

1. `core/` — 人格内核(特质、情绪、记忆、持久化),不依赖任何上层
2. `bridge/` — 桥接层(LLM / Sylanne / Proactive 适配),可被多个 extension 共享
3. `extensions/` — 高级功能(梦境、力学引擎、社交图),可选挂载
4. `interfaces/` — 公开 API(commands, events, REST),最薄壳层

5 层会引入 `adapters/`,但跟 `bridge/` 职责重叠,得不偿失。2/3 层无法容纳 extensions,扩展功能会散落。

### Positive Consequences

* 导入方向单向:`interfaces → bridge → core`,`extensions → core`
* 新功能直接放 `extensions/`,不破坏核心
* `interfaces/` 单独维护可作为"公开 API stable"承诺

### Negative Consequences

* 简单模块可能"为了分层而分层"(bridge 层有时很薄)
* 新人需要先理解分层再写代码

### Confirmation

CI 测试无循环 import;`docs/architecture.md` 已记录分层;`main.py` 仅 import `interfaces/`。

## More Information

* 实施于 v2.0.0v1 (2026-06-09)
* 4-layer decorator enforcement: `emotion_spirit/layer.py` (per_user_only / global_only)
* 相关: `emotion-spirit-direction` memory 的 4 层架构哲学
