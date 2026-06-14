# ADR-0003: 内嵌 SylannEngine (vs 外部依赖)

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

SylannEngine 是 emotion_spirit 原本的"上游引擎依赖",提供即时情感计算(ms~hr)。
emotion_spirit 在其之上构建长期记忆和人格演化(hr~month)。

需要决定:SylannEngine 应该是外部依赖,还是内嵌到 emotion_spirit?

## Decision Drivers

* **安装简单**:单插件一行安装 vs 两步
* **版本控制**:不同 SylannEngine 版本可能影响 emotion_spirit 行为
* **可观察性**:如果 emotion_spirit + SylannEngine 都有 bug,定位困难
* **可分发性**:AstrBot 强制要求的 `requires_plugins` 可能造成死锁

## Considered Options

* **A**: 保持外部依赖(`pip install sylannengine` + `requires_plugins`)
* **B**: Fork SylannEngine,内嵌为 `emotion_spirit/sylanne_core/` ← 选定
* **C**: 重写为 emotion_spirit 内部模块(完全去除 sylanne 概念)

## Decision Outcome

Chosen option: **B**,因为:

1. SylannEngine 是 Ayleovelle 个人维护,emotion_spirit 无法控制其版本节奏
2. v3.0 时 SylannEngine 上游进入"低活跃期",内嵌可独立迭代
3. Fork 后 emotion_spirit 团队对引擎有完全控制权(改名 / 重构 / 优化)
4. 公共 API 稳定:`emotion_spirit.sylanne_core.SylanneEngine` 仍是公开 API

未来如果 SylannEngine 上游恢复活跃,可以作为"并行实现"重新提供(per [[emotion-spirit-ecosystem-eval-2026-06-13]] R5 风险 6)。

### Positive Consequences

* 完全控制 Sylanne 引擎代码,可独立重构
* 单一安装,无版本错位
* AstrBot 启动无死锁风险(per ADR-0002)

### Negative Consequences

* 跟进 SylannEngine 上游修复需手动 cherry-pick
* 用户没法用"原版 SylannEngine"(因为它已低活跃)
* 内嵌 sylanne_core 跟外部 sylanne-1.4.7 有 namespace 冲突风险 → 后续 R3 修复

### Confirmation

* `emotion_spirit/sylanne_core/` 含 46 模块,~20K LOC
* 所有 emotion_spirit 内部使用 `emotion_spirit.sylanne_core.*` import
* SylannEngine 上游 issue 不再阻塞 emotion_spirit 迭代

## More Information

* 实施于 v3.0.0v1 (2026-06-09), Phase F "SylannEngine 嵌入"
* 后续: [ADR-0008](0008-rename-sylanne-core-to-sylanne.md) 已于 2026-06-14 实施 `sylanne_core` → `sylanne` 重命名
* 相关: [[emotion-spirit-v3-merger-plan]] Phase F
