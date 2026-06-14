# Architecture Decision Records (ADR)

emotion_spirit 项目的所有关键设计决策都记录在这里。

格式基于 [MADR 3.0](https://adr.github.io/madr/) 模板。

## 索引

| 编号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| [ADR-0001](0001-four-layer-directory.md) | 4 层目录结构 (core/bridge/extensions/interfaces) | ✅ Accepted | 2026-06-13 |
| [ADR-0002](0002-no-requires-plugins.md) | 不使用 `requires_plugins` 声明依赖 | ✅ Accepted | 2026-06-13 |
| [ADR-0003](0003-embed-sylanne-core.md) | 内嵌 SylannEngine (vs 外部依赖) | ✅ Accepted | 2026-06-13 |
| [ADR-0004](0004-persona-id-sentinel.md) | persona_id default 当 sentinel (不显式存 null) | ✅ Accepted | 2026-06-13 |
| [ADR-0005](0005-v30-phase-order.md) | v3.0 Phase A-I 实施顺序 | ✅ Accepted | 2026-06-13 |
| [ADR-0006](0006-v17-autonomy-guard-split.md) | v1.7 autonomy_guard 拆分 (11→12 维) | ✅ Accepted | 2026-06-13 |
| [ADR-0007](0007-pre-commit-secret-scan.md) | pre-commit secret scan (vs CI-only) | ✅ Accepted | 2026-06-13 |

## 添加新 ADR

1. 复制 `template.md`(MADR 模板)到 `NNNN-short-title.md`
2. 编号递增,不复用旧编号
3. 改 `## Status` 为 `Accepted` / `Proposed` / `Deprecated` / `Superseded by ADR-NNNN`
4. 在本文档索引表加一行

## 决策状态说明

- **Proposed** — 提议中,团队讨论
- **Accepted** — 已决定并实施
- **Deprecated** — 不再推荐,但代码仍存在
- **Superseded by ADR-NNNN** — 被新决策取代

## 范围

每个 ADR 记录**一个具体决策**,不写大段哲学:
- Context: 为什么做这个决定(2-3 句)
- Options: 考虑了哪些方案(2-3 个)
- Decision: 选哪个 + 为什么
- Consequences: 正面/负面
