# Changelog

所有对 emotion_spirit 项目的显著变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [1.2.8] - 2026-07-03 (清 5 项债 + 正式 release, 1358 tests, 48 modules)

> v1.2.8 是 v1.2.7 清债后的干净版, 正式 release。v1.2.7 为过渡版未 release (5 项债未清)。版本号 1.2.5 → 1.2.8 (跳过 1.2.6 文档版 / 1.2.7 过渡版, 均未 tag)。

### 清债 (5 项, v1.2.7 遗留)
- ✅ **债 4**: 删 `personality_feedback.apply_activity_effect` 多余双 docstring
- ✅ **债 3**: 删 `segmented_reply_orchestrator` 3 处多余 `hasattr` 守卫 (depends_on 必注入, §5 风格瑕疵)
- ✅ **债 5**: plan §5.D `start_recovery` 触发点描述对齐代码 (实际在 surface_handler:283, 非 main.py 中转; 文档对齐代码不动代码)
- ✅ **债 2**: 封跨层私有访问 — LifeSimulatorV2 加 `persist_extensions`/`restore_extensions`/`trigger_recovery` 公开方法; memory_pool 加 `get_collapse_archetype`; main/surface_handler 改调公开接口 (不再伸手 `_project_mgr`/`_recovery`/`_collapse_archetype` 私有, §1.3 分层)
- ✅ **债 1**: on_llm_response 薄壳化 — 抽 `_apply_bot_reply_effects` + `_collect_segmented_state` helper, 88→43 行; `test_on_llm_response_bounded` 收紧 ≤90→≤55; on_llm_response 移出 allowlist 真正受 50 行约束 (§1.2 规则 3 兑现)

### 全测
- **1358 passed**, 0 failed

## [1.2.7] - 2026-07-03 (10 项清债 10/10, 1358 tests, 48 modules, 过渡版未 release)

> v1.2.7 是执行 v1.2.6 审计报告的清债版本。10 项清债任务完成 10/10，模块数 58 → 48。

### 清债 (10 项)
- ✅ **Task 1**: utils/ 层建立, 11 工具从原层 `git mv` 集中, 删 `@register` (全仓 import 路径更新 35 文件)
- ✅ **Task 2**: HP-2 + DO-4: `compute_defense_states` 加 `conscience_pressure` 参数, main.py caller 改用 `self._conscience.get_pressure()`
- ✅ **Task 3**: Q3: 删 `event_bus.py` + `AgentEvent` + 4 事件类型 + `base.py emit` + 4 agent emit/bus 参数
- ✅ **Task 4**: 编排抽取: `_extract_bot_emotion` → `utils/tone_extractor.py`; `_on_segmented_reply_v2` → `output/segmented_reply_orchestrator.py` (@register, depends_on 5); `_build_context` → `utils/context_builder.py`; main.py 薄壳化
- ✅ **Task 5**: 8 幽灵接通: environment_context / personality_feedback / project_manager / recovery_tracker 接入 LifeSimulatorV2; user_activity_detector 接 main.py on_llm_request; collapse → recovery 触发链
- ✅ **Task 6**: HP-4: `force_dynamics.restore_offset()` + main.py persist/load
- ✅ **Task 7**: DO-3: `defense_modulator.py` 方法内 import 移到顶部
- ✅ **Task 8**: DO-5: spec drift 注记加到 segmented-reply-fix-design.md
- ✅ **Task 9**: collapse_archetype 核验 (非幽灵, 6+ 消费者)
- ✅ **Task 10**: 9 个可拦测试 (26 用例) 全绿

### 新增可拦测试 (9 文件, 实现 §1.1-§1.6 全可拦)
- `test_kb_centralization.py` (§1.1): AST 扫 .py 单 dict/list 字面量 > 10 项 → CI 红
- `test_registry_liveness.py` (§1.2): @register 活性 + 隐式 import new
- `test_main_py_no_long_orchestration.py` (§1.2 规则 3): main.py 单方法 > 50 行 → CI 红
- `test_layer_dependencies.py` (§1.3): AST 扫 import, core 不依赖业务层
- `test_type_contracts.py` (§1.4): 扫跨子系统参数裸 float + 易错配
- `test_lifecycle_pairs.py` (§1.5): 有状态 @register 模块必须有 to_dict/from_dict 配对
- `test_agent_no_impl.py` (§1.6 规则 1): AST 扫 agent 方法体无算法实现
- `test_no_event_bus.py` (§1.6 规则 3): agents/ 内无 EventBus/AgentEvent/emit
- `test_agent_no_direct_call.py` (§1.6 规则 2): agent 不互相 import/调

### 模块数
- 58 → 48 @register (-11 工具取消 @register, -event_bus 已删, +segmented_reply_orchestrator)

### 全测
- **1358 passed**, 0 failed (test_v300_integration 回归已修: Task 4 抽 `_extract_bot_emotion` → `utils/tone_extractor.py` 后, 测试改调 `extract_bot_emotion`)
- ⚠️ 遗留 5 项债 (on_llm_response 88行 / 跨层私有访问 / 多余 hasattr / 双 docstring / start_recovery drift), 推 v1.2.8 清完。**v1.2.7 未 release** (版本号未 bump, 未 tag)。

## [1.2.6] - 2026-07-03 (架构审计 + handbook 六件套规约, 不改代码, 未 release)

> v1.2.6 是只读审计 + 规约文档, 版本号仍 1.2.5 (未 tag/未 release)。v1.2.7 才改代码。

### 规约 (handbook 六件套, §1.1-§1.6)
- 三件套 → 六件套, 每条绑钩子 (符合 §0 可拦哲学, 从"2/3 不可拦"修到"全可拦")
- §1.2 @register: 4 规则 (判定有状态/活性必被取用/薄壳 main 只调用 50 行/依赖显式 depends_on)
- §1.3 layer: 九层 (加 utils/) + 层归属 + core 元层 + per-user/global (删业务层依赖方向 — 反馈回路耦合允许但 §1.2 规则 4 显式)
- §1.4 类型契约 (新): ConsciencePressure 等带维度标签类型, 治 conscience 源错配
- §1.5 生命周期 (新): 有状态模块 to_dict/from_dict + reset
- §1.6 agent 编排 (新): agent 是连线不实现 + SelfCore 统一编排 + LLM 整合不用事件 + agent vs @register 判定 (认知轴 vs 输出编排)

### 审计 (docs/v126_audit_report.md)
- 58 @register 活性: 9 幽灵 + 7 无状态误用 + 1 双轨 + 3 真在跑 (修正: 36% → 24% 真有问题)
- Q1 main.py 219 行编排: _extract_bot_emotion 抽 utils/ + _on_segmented_reply_v2 抽 @register (SegmentedReplyOrchestrator)
- Q2 分层: regulation 积债非兜底 (8 幽灵+2 该挪 utils/) + 跨层合规 (depends_on 显式) + agent 双轨=编排双轨
- Q3 agents: 主循环运转 (composed 进 prompt) + 事件空转 (4 事件零 subscriber) → 删事件 (LLM 整合)
- 8 幽灵分类: 4 工具 (挪 utils/) + 4 组件 (@register + 接通 LifeSimulatorV2; 7 进 LifeSimulatorV2 + user_activity_detector 进 main.py)
- agent 集合明确: Memory(memory_pool+shadow) / Personality(superego_guard+drift) / Relationship(intimacy+social_graph) / Life(life_simulator_v2 含 7 幽灵)

### 版本重排
- v1.2.6 审计 (完成) / v1.2.7 清债 + 可拦测试 / v1.2.8+ 原 L2 脚手架 (deferred, 见 docs/superpowers/plans/2026-07-03-v126-l2-scaffolding-plan.md)

### v1.2.7 plan
- docs/superpowers/plans/2026-07-03-v127-debt-cleanup-plan.md (10 任务, 给执行模型)

---

## [1.2.5] - 2026-07-03 (PR2: 力学系统耦合 — DefenseModulator L1+L2)

### 新增 (Features)
- **`DefenseModulator` 模块** (`@register`, depends_on 4 个): 统一管理压抑/崩溃/沉默与力学的耦合
  - L1 输入调制: `SuppressionState.compute()` / `CollapseArchetypeSelector.compute_bas_bis()` / `SegmentedReplyCoordinator.compute_silence_tendency()` 都接受 `force_state` 可选参数 (向后兼容 100%)
  - L2 输出回写: `apply_event("silence" | "collapse" | "suppression", intensity)` 从 KB `defense_deltas.json` 读 delta, 调 `force_dynamics.shift()`
  - 模块数 57 → 58 (+DefenseModulator)
- **`ForceDynamics.shift()`** 新增: 累积偏移状态 (v1.3 L3 fixpoint 复用)
- **`CollapseArchetypeSelector.compute_bas_bis()` 3-tuple 化**: 返回 `(BAS, BIS, collapse_tendency)` + 同步修 `select()` 解构
- **KB `defense_deltas.json`** 新增 (handbook §1.1: 系数全从 KB 读)
- **main.py 集成**: `_init_life_and_agents` 加 `self._defense_modulator`, `_on_segmented_reply_v2` 用 DefenseModulator 统一入口 + 沉默触发后 `apply_event("silence")`

### 新增测试
- `test_defense_modulator.py`: 18 个测试 (DefenseStates dataclass + KB + compute_defense_states + apply_event + main.py 集成)
- `test_suppression.py`: 4 个 L1 force_state 测试
- `test_collapse_archetype.py`: 5 个 L1 + 连续化测试
- `tests/regulation/test_collapse_archetype.py`: 3 处解构修复 (2-tuple → 3-tuple)

### 向后兼容 (handbook §1.2 关键)
- `force_dynamics.compute()` 签名不变
- `SuppressionState.compute()` force_state=None → 跟 v1.2.4 一致
- `CollapseArchetypeSelector.compute_bas_bis()` 不传 → 返回 (BAS, BIS, collapse_tendency=0.0)
- `SegmentedReplyCoordinator.compute_silence_tendency()` force_state=None → 跟 PR1 一致

---

## [1.2.5] - 2026-07-03 (PR3: 顺手清债 + Bug 13/14 + 正式 release)

### 修复 (Fixes)
- **T1**: `merge_life_sim_config` 补搬 `enable_life_fragment` (handbook §3.3 漏搬, 旧 v1.0.0 用户升级后字段保留)
- **T2**: `_reset_superego_modules` 双轨 bug 修 — 抽 `_rebuild_superego_subdict()` helper, 走 `_modules["superego"]` 子字典单点重建, `initialize()` 也复用 (身份一致 `self._conscience is _modules["superego"]["conscience"]`)
- **Bug 13**: 修 `main.py` 两处 `datetime.date.today()` / `datetime.date.fromtimestamp()` 类名遮蔽 (line 846 + 1004) → 用 `date.today()` / `date.fromtimestamp()`
- **Bug 14**: 修 `polish_template_events` 嵌套 dict TypeError — 加 `_flatten_personality()` helper, `life_simulator.py` 两处 `personality.items()` format 先拍平; `_get_current_personality_dict()` type hint 改真实 shape `dict[str, Any]`

### 重构 (Refactor)
- **T3 + T4**: main.py 10 个模块改走 `self._modules[...]` 装配, 删手 new
  - facade: PublicAPI
  - memory/output: PatternExtractor / BufferSignals / ShadowDetector / LifeSimulator / PersonalityDrift / PredictiveSentinel / NarrativeIdentity / Counterfactual / PromptInjector
  - 剩余 4 个手 new (CommandImpl / SurfaceHandler / LifeAgent + reset 中新建 ConscienceTracker) 都是 self 注入或重置语义所需, 留 v1.3/v1.2.6
- **AST 静态检查 (handbook §1.2 强拦)**:
  - `tests/test_main_py_no_manual_new.py`: 扫描 main.py 手 new 模式 + 已修类回退检查 + initialize() 双轨检查
  - `tests/test_datetime_import_patterns.py`: 防 `datetime.date` / `datetime.time` 类名遮蔽回归
  - `tests/test_personality_shape_contract.py`: 防 `personality.items()` 直接 format 回归

### 正式 release
- **Tag**: `v1.2.5` (PR1 `v1.2.5-rc.1` + PR2 `v1.2.5-rc.2` + PR3 `v1.2.5`)
- **状态**: 完整 v1.2.5 正式版 (含 PR1 沉默语义 + PR2 力学耦合 + PR3 清债 + Bug 13/14 修复)

### 新增测试
- `test_reset_superego_modules.py`: 4 个 (AST 直赋检查 + ConscienceTracker import + modules dict 重建 + identity 同步)
- `test_main_py_no_manual_new.py`: 4 个 (AST 扫描 + T4 回退 + PublicAPI + initialize)
- `test_datetime_import_patterns.py`: 1 个 AST 静态检查
- `test_schedule_plan_loop.py`: 2 个行为测试
- `test_life_simulator_personality_flatten.py`: 6 个 (flatten helper + 集成)
- `test_personality_shape_contract.py`: 2 个 AST 静态检查

---

## [1.2.5] - 2026-07-03 (PR1: 分段修复 + 沉默语义)

### 修复 (Bug Fixes)
- **Bug 12**: 分段回复 100% 不工作 (v1.2.4 release blocker)
  - **Bug 12a**: `_on_segmented_reply` 含 yield 被 await → TypeError 静默吞
  - **Bug 12b**: emotion_spirit 投递架构改为主动 send + 清空 llm_resp

### 新功能 (Features)
- **沉默 S1-S4**: 不删消息 / 语义透明 (SilenceTendency) / 情绪事件 (S3 写 memory) / 时长上限 (S4 冷却+连续上限)
- **沉默人格加权**: 6 factor 连续函数 (系数从 KB 读, Jack 1992 / Carver 1998 / Noftle 2006 文献背书)
- **亲密度双向调节**: Jack 讨好假说
- **延迟策略接口**: TypingDelayStrategy 默认字符级打字, v1.3 接 TTS 预留
- **流式模式跳过**: `streaming_response=true` 时 emotion_spirit 跳过
- **`/reflect_force_current`** 命令: 看当前 ForceState + 7 天沉默/分段历史

### 工程 (Engineering)
- KB 文件 `silence_tendency_weights.json` 新增
- 4 个新方法标 `@per_user_only`

### 测试 (Tests)
- 新增: test_silence_tendency.py (20), test_delay_strategy.py (5), test_on_llm_response_segmented.py (2), test_conf_schema_v125.py (3), test_commands_reflect.py (7)
- 总计: ~1290 passed

## [1.2.4] — 2026-06-30

> main.py 模块化减负。纯重构，无 API/行为变更。

### Changed

- **DB 访问统一**: `_scan_all_personas` / `_detect_default_persona` 也走 `_get_persona_db_cursor()`
- **冗余 import 清理**: `json`/`datetime`/`asyncio` 集中顶层，删方法内重复
- **`Path(get_astrbot_data_path())` 去重**: 12 次 → 5 次（1 初始化 + 1 实例属性 + 3 合理残留如 config/cmd_config/db）
- **`on_llm_request` 拆分**: 171 → 75 行, 抽 `_observe_rhythm_and_dream` / `_run_engine_and_agents` / `_inject_life_event` 3 子方法
- **`_setup_persona_state` 拆分**: 163 → 8 行, 抽 `_init_persona_config` / `_init_feature_toggles` / `_init_modules_phase1` / `_init_modules_phase2` / `_init_social_and_mechanics` / `_init_life_and_agents` / `_init_logging_and_cache` 7 子方法
- **`_load_persistent_data` 拆分**: 126 → 5 行, 抽 `_load_core_data` / `_load_phase2_data` / `_load_life_and_v2_data` 3 子方法
- **过时注释清理**: 删除 `"~470 行"` 误导注释

### Notes

- **不新增模块**: 沿用 56+v1.2.3=57 @register, 不破坏 DI 架构
- **为后续功能提供范式**: 新增模块只需在 `_init_life_and_agents()` 和 `_load_life_and_v2_data()` 中添加对应行即可

## [1.2.3] — 2026-06-30

> 分段回复引擎接通。行为变更 opt-in，默认关闭，不破坏旧用户。

### Added

- **SegmentedReplyCoordinator** (`output/segmented_reply_coordinator.py`, @register, 57 模块): 桥接现成的 RealtimeDispatch/RhythmLearner/DeliberateSilence/BreathingRhythmController 到回复链路
  - `plan()`: 1) ignored_rate 计算 (D8) → 2) RhythmLearner 调制 (max_part, cps) → 3) 长度因子 (D9) → 4) 主动沉默判断 (D10) → 5) 分段发送计划
  - per-session deque 记录交互时刻，与 BreakpointStore 同档序列化
- **`_conf_schema.json` `segmented_reply` 配置块**: enable/default_max_part_chars/default_chars_per_second/blend/enable_deliberate_silence/intimacy_gate/max_delay_seconds/ignored_window_turns
- **main.py `on_llm_response` 分段回复路径** (POC X 路径): 启用时遍历 Coordinator 计划逐段 yield 带打字延迟
- **`rhythm_learner.set_personality_params` 注入**: `initialize()` 时从 config 注入 intimacy_gate + blend (顺手补漏接线)

### Changed

- **模块注册 56→57**: `segmented_reply_coordinator` 加入 @register
- **`_persist_modules`**: 新增 segmented_coordinator 状态序列化
- **`_load_persistent_data`**: 新增 segmented_coordinator 状态恢复

## [1.2.2] — 2026-06-30

> 用户安装反馈修复版本。9 bug (B1-B9) 全部修复，纯修复无新功能。

### Fixed

- **B1 (文档)**: README 方式 1 补 `pip install -e .` 步骤，解释 emotion_spirit 绝对导入需要安装为 site-packages 包
- **B2 (打包 🔴)**: pyproject.toml `[tool.setuptools].packages` 改用 `find()` 自动发现，删除手维护白名单，防止新增子包再漏列
- **B3 (导出 🟡)**: `emotion_spirit/__init__.py` 添加 `PublicAPI` 顶层 re-export，`from emotion_spirit import PublicAPI` 现在可用
- **B4 (命令 🔴)**: `_ns_handler` 加 `*args, **kwargs` 接收 AstrBot v4.26.1 CommandFilter 参数注入，兼容旧版 `parsed_params` 兜底
- **B5 (persona 🟡)**: `_load_persona_state` 让 `config.auto_source` 显式指定时覆盖持久化 saved persona，新增 `_list_available_personas()` 扫描数据库
- **B6 (迁移 🔴)**: `_migrate_old_spirit_data` 统一留 `initialized=False`，非 sentinel persona 不再锁 ISTJ 默认值，让 `/setup_init` 走 LLM 路径
- **B7 (持久化 🔴)**: 合并 `_save_if_dirty` / `_save_all` 为 `_persist_modules()` 统一路径，补上漏存的 diary/reservoir/patterns/buffer_signals/shadow/life_sim/drift/sentinel/narrative/counterfactual ≥8 模块
- **B8 (命令 🟡)**: 新增 `/view_diary [days]` 命令，暴露现成 `get_recent_diary()` 方法
- **B9 (解析 🔴)**: `_infer_mbti_from_narrative` tie-breaking 不再偏向 INTJ 轴（E/I tie→E, F/T tie→F, P/J tie→P），否定词预处理，时间取向否定语境处理

### Changed

- **CI 防回归**: 新增 `tests/test_v122_regression.py` (8 tests)，覆盖 B4/B6/B7/B8/B9 行为
- **test_t10**: 更新匹配 B6 新行为（非 sentinel 统一 `initialized=False`）

### Removed

- **packages 白名单**: 删除 pyproject.toml 中手维护的 8 项子包列表，替换为 `find()`

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
