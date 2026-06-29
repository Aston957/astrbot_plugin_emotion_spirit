# Changelog

所有对 emotion_spirit 项目的显著变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [1.2.1] — 2026-06-29

> 自 v1.1.0 (2026-06-28) 以来的变更。DI 双轨清零 + ForceState 入日记 + 注册模块 48→56。

### Added

- **ForceState 入日记**: `DiaryWriter` 新增 `_format_force_state_block` helper + `configure_force_dynamics` 方法, 日记与超我反思 prompt 均注入三元力学基调 (自然/社会/个体)
- **`get_current_force_state(labels)` 公开 API**: 基于 `force_state_from_labels(labels)` 便捷入口
- **8 模块补 `@register` spec**: `bridge/{engine_manager, hotpool_forwarder, personality_bridge}`, `output/{realtime_dispatch, rhythm_learner, command_router}`, `agents/self_core`, `regulation/life_simulator_v2` — 注册模块 48→56
- **UPDATE_HANDBOOK.md**: 可拦式规约手册 (框架规则三件套 + 技术债管理 + 迁移纪律 + ship 纪律)
- **Plan 文档**: `docs/PLAN_2026-06-29_MEMORY_ARCHIVE_AND_FORCE_WIRING.md`

### Changed

- **DI 双轨清零 (12→0)**: `main.py` 从 `self._modules[...]` 取 9 个组件, 删除 12 处手 `new` + `TODO(tech-debt)` 注释 + 8 处 unused import
- **`emotion_spirit/__init__.py`**: 新增 bridge/agents 子目录 + realtime_dispatch + rhythm_learner + command_router imports (触发 56 模块注册)
- **`tests/*`**: 注册数 48→56 维护 (3 处 disable list + consistency check + dry_run count)

### Fixed

- **`life_agent.py`**: `perceive`/`gate` 加 `or 0.0` 防御 `None`, 修 `abs(None)` 运行时报错
- **`main.py`**: 删 2 dead imports (`save_report`, `load_report` from `persona_analyzer`), 删 `save_report`/`load_report` 死代码
- **`CommandRouter`**: 0 参 → factory DI (plan §0 漏列的真双轨)

### Known Issues (未修)

- `test_v2_full_lifecycle`: wall clock 偶发 flaky (`_time_to_slot` 对齐问题)
- `test_periodic_save_dirty_only`: Windows 概率性 1/3 失败
- 4 `CognitiveAgent` 子类仍手 `new` (factory `param_wire` 不支持 `dep.attr`, 待 v1.2.x 工厂扩展)
- `merge_life_sim_config` 漏搬 `enable_life_fragment` (待下个带 schema 变更版本修)

## [1.1.0] — 2026-06-28

> 自 v1.0.0 (2026-06-24) 以来的累计变更。ship 完整闭环 — 5 矩阵格 CI 全绿。

### Added

#### 新增子系统
- **LifeSimulatorV2**: 规则 + LLM 双模式日程生成引擎, 6 维事件权重 (阅读/散步/烹饪/思考/创造/休息/观察), 随机事件注入, `DailyPlan` 持久化, `/view_schedule` 命令
- **Migration Framework**: `MigrationRegistry` + `MigrationRunner` + `MigrationState` + `@register_migration` 装饰器; v3→v4 `split_llm_tier` rule 把旧 `llm_tier` 5 个 provider_id 迁移到各功能段

#### 配置改造 (15 WebUI 段)
- **删除** `llm_tier` + `diary_schedule` 段
- **新建** `sylanne` 段 (engine + analyzer provider_id) + `diary` 段 (enable + provider + schedule)
- `life_sim_v2` / `dream` 各加 provider_id
- **`_get_llm_callable(feature)` chokepoint**: 5 个分级 provider_id 真正接线 (engine / analyzer / life_sim / dream / diary), 之前 schema-only 死配置

#### 功能升级
- **DiaryWriter**: 真接 LLM 生成正文 + 定时写日记 (之前只构造 prompt 不调 LLM)
- **`_schedule_diary_generation_loop`**: 防重复触发, 异步调度 (复刻 2am scheduler 模式)
- **Migration 幂等**: 重复跑 split_llm_tier 不会覆盖用户已有的 diary 配置

### Changed

- README / public_api_stable 同步 v1.1.0 (4+2 处版本号 + 3 个新功能子段)
- `_version.py` + `metadata.yaml` 双处统一 1.1.0
- `TestVersionConsistency` bump-proof (硬编码 → 两源互比 + SemVer regex, 未来 bump 不会破)
- `tools/sync_plugin_to_source.py` 支持 `--direction=source-to-plugin --apply` 双向 sync

### Fixed

#### Ship-prep 修复 (让 CI 5/5 全绿)
- **`test_activity_history.py`**: `TestRegistryIntegration::test_registered_in_registry` 漏 restore registry, 加 try/finally save+restore (镜像 `test_module_registry.py:isolate_registry`), 修全套 34 isolation fail
- **`test_plugin_factory.py`**: 硬编码 `assert len == 35/36` 陈旧, 改用动态 `expected_count = sum(provides)` (v1.1.0 模块 35→43)
- **`test_split_llm_tier.py`**: 撤销误加的 autouse reset fixture (该文件 test 走函数体不走 registry, reset 反倒污染后续 test)
- **`test_integration.py`**: 加 `_ensure_all_rules_registered` autouse fixture, 强制 reset + importlib.reload 4 rule; 函数体内 `reset + import` 改 `reset + importlib.reload` (避免 import 跳过 `@register_migration` 副作用)
- **`test_suggest_project_for_high_conscientiousness`**: 断言漏 `physical` (权重 0.1 ~4% 概率被 random.choices 选中), 跟 v1.1.0C T1 修的 extraversion 同根, 抄同修法模板
- **`release.yml`**: cmd_config.json sanity check 反向 (require → exclude, AstrBot 平台级运行时配置不该进 release zip)
- **`docs/api.md` / `docs/architecture.md` / `docs/ARCHITECTURE_FRAMEWORK.md`**: 头部 `> v1.0.0` 同步到 `> v1.1.0`

#### Debt cleanup (9 commits, 见 `docs/PLAN_2026-06-28_DEBT_CLEANUP.md`)
- T1 flaky test_suggest_project exon stabilization
- T2 `diary_writer.should_write` 死方法删除
- T3 reasoning 模型日记生成 30s+ 文档提示
- T4 `*.egg-info` / `.gitignore` 收紧
- T5 `tools/sync_plugin_to_source.py` 双端 drift checker
- F1-a main.py 11 组件 DI 双轨 TODO 锚点 (真改留 v1.2)
- E1 `data/cmd_config.json` secret 防护 (双闸: .gitignore + check_secrets pre-commit)

### Removed

- 远端污染 tag `v2.0.0` / `v3.0.0` / `v3.0.1` 已删 (版本号倒退污染)
- `manual_personas` 死配置 (main.py + README)
- 7 个 stale `1.0.0` 字符串残留 (README / public_api_stable / docs)

### Tests

- **1242 tests, 0 failed** (本地 Windows + Python 3.12)
- **CI 5 矩阵格 (3.11/3.13 × 4.9.2/4.14.6/4.25.5) 全绿** (3 of 3 required status checks PASS)
- secret scan 三道闸 (file check / pre-commit hook / 双 .gitignore) 全过
- 已知问题 (推 v1.1.1 patch): `test_periodic_save_dirty_only` 概率性 fail (Windows mtime 精度) + `merge_life_sim_config` 升级时 `enable_life_fragment` 字段丢失

### Migration Notes

- 用户从 v1.0.0 升级: 配置文件无需手动改, Migration Framework 自动跑 v3→v4 split_llm_tier
- 用户从 v3.1 升级 (若有): 同样自动跑, 但 `enable_life_fragment` 字段会丢 (已知问题, v1.1.1 修)
- 旧 `llm_tier` 段会自动迁移到 `sylanne` / `life_sim_v2` / `dream` / `diary` 各段, 用户无感

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
