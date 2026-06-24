# Changelog

所有对 emotion_spirit 项目的显著变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [1.0.0] — 2026-06-24

> 首个正式版本。emotion_spirit 是 AstrBot 生态的情感计算插件，负责"自我 + 超我"层。
> SylannEngine 计算核心已内嵌，零外部依赖。

### Added

#### 核心架构
- **4 层目录结构**: `core/` (基础) / `memory/` (记忆) / `regulation/` (调控) / `output/` (输出)
- **SylannEngine 内嵌**: 46 模块从 SylannEngine v2 内嵌到 `emotion_spirit/sylanne/`
- **109 模块**: 58 core + 46 sylanne + 5 migrations，886 tests

#### 记忆系统
- **4 层记忆池**: buffer / warm / cold / ghost，flat 存储
- **统一记忆条目**: `UnifiedEntry` + `DecayModel` (Ebbinghaus 衰减)
- **级联引擎**: `CascadeEngine` 倒排索引级联传播
- **记忆采样器**: `MemorySampler` 人格加权多层采样 + 向量相似检索
- **记忆崩溃系统**: 5 种 `CollapseArchetype` 行为模式
- **情境衰减**: 人格因子 + 亲密关系 + 情感权重联合调制

#### 人格系统
- **13 维人格**: PAD 情感空间 + 10 维人格特质
- **人格知识库**: 3072 条 persona labels (2.74 MB)
- **人格漂移**: `PersonalityDrift` 13 维漂移引擎
- **人格分析**: `PersonaAnalyzer` LLM 驱动的人格标签解析

#### 超我调控
- **良心追踪**: `ConscienceTracker` 滑动窗口 P95 归一化
- **价值对齐**: `ValueAlignment` + `IdealSelf` + `ValueResistance`
- **超我守卫**: `SuperegoGuard` 行为边界检查
- **三元力学**: `ForceDynamics` 自然/社会/个体三力引擎

#### 情绪表示
- **PAD 分类**: 7 类基本情绪 + 4 类复合情绪
- **情绪动态**: ambiguity / velocity / trajectory
- **情绪突变检测**: `emotion_burst` 基于 velocity 阈值

#### 生活模拟
- **Mode A (LifeFragment)**: 对话中插入 LLM 生成的生活片段
- **Mode B (ProactiveChat)**: 长沉默后主动注入 prompt 发起对话
- **LLM 集成**: `LifeSimulator.configure(llm_caller=)` 注入 LLM callable

#### 输出层
- **14 个命令**: setup_* (4) / view_* (5) / reflect_* (5)
- **Prompt 注入**: `PromptInjector` 组装 system prompt
- **日记生成**: `DiaryWriter` 定时生成 + 手动触发
- **叙事身份**: `NarrativeIdentity` 月度叙事弧
- **预警系统**: `PredictiveSentinel` 13 信号早期预警
- **阴影检测**: `ShadowDetector` 未符号化情绪模式

#### Bot 回复记忆
- **on_llm_response**: bot 回复写入 MemoryPool
- **情绪提取**: 规则引擎提取 warm/apologetic/curious/detailed/neutral

#### 配置系统
- **8 个配置段**: persona_mode / auto_source / feature_toggles / llm_tier / memory_pool / life_simulator / proactive_chat / diary_schedule / emotion_sensitivity / sentinel_thresholds / safety_layer
- **Config Migration Framework**: `@register_migration` 装饰器 + Runner + State 持久化
- **Web API**: `POST /emotion_spirit/re_run_migration` 手动重跑迁移

#### 桥接层
- **EngineManager**: SylannEngine 生命周期管理
- **PersonalityBridge**: 5D↔12D 人格映射
- **HotPoolForwarder**: inject 信号 → MemoryPool 转发
- **RealtimeDispatch**: 即时分段回复 + 打断检测
- **RhythmLearner**: 节律学习

### Changed

- 无（首个版本）

### Fixed

- 无（首个版本）

### Tests

- **886 tests passed, 0 failures**
- 覆盖: 记忆系统 / 人格系统 / 超我调控 / 情绪表示 / 生活模拟 / 输出层 / 迁移框架

### 兼容性

- **Python**: >= 3.11
- **AstrBot**: >= 4.9.2, < 5
- **平台**: aiocqhttp / telegram / qq_official
- **外部依赖**: 0（仅依赖 AstrBot）

---

## Archive (开发历史)

> 以下为开发过程中的版本记录，已整合到 v1.0.0 中。

### v3.0.1 (2026-06-13) — AstrBot v4.25.5 兼容性修复
- 10 个 bug fix: Python 3.13 / namespace package / 命令签名 / handler 语义 / 持久化 sentinel

### v3.0.0 (2026-06-12) — Phase A-I 大合并
- Phase A: 统一记忆系统 (7 modules)
- Phase B: Bridge + Output 增强 (6 modules)
- Phase C: 向量记忆空间
- Phase D: 记忆系统重构
- Phase E: 生产流程接入
- Phase F: sylanne_core 内嵌
- Phase G: LLM LifeSimulator
- Phase H: on_llm_response
- Phase I: 集成 + 发布

### v2.0.0v1 (2026-06-09) — Phase 4 Launch
- C1: ConscienceTracker B2 滑动窗口 P95 归一化
- C2: Plugin Packaging (pyproject.toml)
- C3: Public API Markers (__all__)
- C4: 4-Layer Dir Restructure
- C5: Marketing Materials
- C5.5: Pre-existing Tech Debt Cleanup

### v1.3.0 (2026-06-05) — compute_ambiguity 重构
- 从 Shannon entropy / log(K) 改为 `1 - max(p)`

### v1.2.0 (2026-06-05) — 情绪动态表示
- emotion_ambiguity / emotion_velocity / emotion_trajectory

### v1.1.1 (2026-06-05) — 情绪表示升级
- PAD 概率分布 + 派生字段

### v1.0.3 (2026-06-05) — persona 持久化
- SpiritStore persona namespace + /setup_relabel

---

## 链接

- [README.md](README.md) - 项目说明
- [docs/architecture.md](docs/architecture.md) - 架构文档
- [docs/superpowers/specs/](docs/superpowers/specs/) - 设计规格
- [docs/superpowers/plans/](docs/superpowers/plans/) - 实施计划
- [docs/DEVELOPMENT_HISTORY.md](docs/DEVELOPMENT_HISTORY.md) - 完整开发历史
