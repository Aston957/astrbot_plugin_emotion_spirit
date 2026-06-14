# ADR-0002: 不使用 `requires_plugins` 声明依赖

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

emotion_spirit v3.0 之前在 `metadata.yaml` 用 `requires_plugins: [sylannengine]` 声明依赖 SylannEngine。
v3.0 (Phase F) 把 SylannEngine 46 模块内嵌后,`requires_plugins` 被移除。

需要决定:内嵌 SylannEngine 后,如何处理依赖声明?

## Decision Drivers

* **不强制用户装不需要的插件**(已内嵌,不应再 require 外部)
* **防止 AstrBot 启动死锁**:`requires_plugins` 会让 AstrBot 强制检查并加载
* **降低用户安装摩擦**

## Considered Options

* **A**: 保留 `requires_plugins: [sylannengine]`(尽管已不需要)
* **B**: 移除 `requires_plugins`,完全靠内嵌 ← 选定
* **C**: 改成 `optional_plugins: [sylannengine]`(声明但不强制)

## Decision Outcome

Chosen option: **B**,因为:

v3.0 把 SylannEngine 46 模块嵌入 `emotion_spirit/sylanne/`,功能完全自包含(per [ADR-0008](0008-rename-sylanne-core-to-sylanne.md),`sylanne_core` 已于 2026-06-14 重命名为 `sylanne`)。继续声明 `requires_plugins` 会让 AstrBot 在用户没装 SylannEngine 时报错(虽然不需要),造成**死锁级安装问题**。

### Positive Consequences

* 用户只需 `pip install astrbot_plugin_emotion_spirit`,无副作用
* AstrBot 启动时不检查已废弃的 SylannEngine 依赖
* 未来 SylannEngine 拆出去做独立插件时,只需重新加回 `requires_plugins`(向后兼容容易)

### Negative Consequences

* 不知道有用户因性能原因想用外部 SylannEngine(目前没有反馈)
* `metadata.yaml` 失去"插件依赖图"的 single source of truth

### Confirmation

* `metadata.yaml` 注释明确说明"已内嵌,不再需要外部依赖"
* 用户安装流程不再报错

## More Information

* 实施于 v3.0.0v1 (2026-06-09)
* 详见 [[emotion-spirit-secret-leak]] 后重新审视依赖关系的副作用
* 相关 ADR-0003: 内嵌 SylannEngine
