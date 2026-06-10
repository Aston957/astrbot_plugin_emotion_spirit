# AstrBot Emotion Spirit 插件 — 框架结构报告

> **生成日期**: 2026-06-09
> **版本**: v2.0.0v1（基于 612/612 tests，30 modules，29 modules 后的 KB ship 修正）
> **位置**: `D:\新建文件夹\emotion_spirit\now\astrbot_plugin_emotion_spirit\`
> **目标读者**: 项目维护者、新加入的贡献者

---

## 1. 顶层（Top-Level）文件与目录速览

### 1.1 顶层目录

| 名称 | 类型 | 作用 |
|------|------|------|
| `emotion_spirit/` | Python 包 | **核心包**——人格/情感/关系/调节/输出的全部逻辑实现 |
| `tests/` | Python 测试 | **测试套件**——与 `emotion_spirit/` 子包镜像对应 |
| `docs/` | 文档 | **用户/开发者文档**——架构、API、理论、用户指南、HTML 样张 |
| `tools/` | Python 脚本 | **维护工具**——KB 重建、维度一致性检查、import 迁移、registry 校验 |
| `data/` | 资源 | **运行时数据/模板**——命令配置 cmd_config.json、T2I HTML 模板、临时目录 |
| `output/` | 仿真产物 | **仿真输出**——压力测试的 trace/turns、property/simulation report |
| `verification/` | 实验台 | **实验 harness**——回测、属性测试、drift simulator、narrative 3072、可视化 |
| `astrbot_plugin_emotion_spirit.egg-info/` | 元数据 | pip 打包产物（PKG-INFO、SOURCES.txt 等），自动生成 |
| `__pycache__/` / `.pytest_cache/` | 缓存 | Python 与 pytest 编译/缓存目录，`.gitignore` 忽略 |
| `.git/` | 版本控制 | git 仓库 |

### 1.2 顶层文件

| 文件 | 作用 |
|------|------|
| `main.py` | AstrBot 插件入口（注册指令、事件钩子、把 `emotion_spirit` 包挂到 bot lifecycle） |
| `metadata.yaml` | AstrBot 插件元数据（name、author、version、desc） |
| `_conf_schema.json` | AstrBot WebUI 配置表单 schema（生成 config 页面） |
| `pyproject.toml` | 现代 Python 打包配置（依赖、build backend） |
| `requirements.txt` | 运行依赖（轻量列表，依赖具体库） |
| `dev-requirements.txt` | 开发依赖（pytest、hypothesis 等） |
| `conftest.py` | 顶层 pytest 共享 fixture（可能仅 import 公共 fixtures） |
| `public_api_stable.md` | **稳定公共 API 文档**——对外部用户承诺不破坏的接口清单 |
| `README.md` | 项目说明（中文，定位、功能、用法） |
| `CHANGELOG.md` | 完整变更日志（自 v1.0 到 v2.0.0v1） |
| `LICENSE` | 许可证 |
| `.gitignore` / `.gitattributes` | git 配置 |

---

## 2. `emotion_spirit/` 核心包结构

核心包按 **4 个职责层 + 1 个 layer 抽象 + 1 个 store 持久化** 的方式组织：

```
emotion_spirit/
├── __init__.py           # 对外公共 API 入口
├── _v1_compat.py         # v1 → v2 兼容层（老接口别名）
├── _version.py           # 版本号
├── layer.py              # 层级抽象（定义 core/memory/output/regulation 的依赖关系）
├── store.py              # 状态持久化（SpiritStore / per-session 存储）
├── core/                 # —— 第 1 层：人格内核 ——
│   ├── config.py         # 运行时配置加载
│   ├── knowledge.py      # 知识库基类/接口
│   ├── label_mapper.py   # 维度标签映射（12 维 → 人格描述）
│   ├── persona_labels_db.py  # 人格标签数据库（PAD raw + 12 维标签生成）
│   ├── plugin_factory.py # 插件对象工厂（组装 Spirit 实例）
│   ├── registry.py       # 模块注册表（模块 ↔ 维度映射）
│   └── kb/
│       └── persona_labels_db.json  # 打包进插件的标签数据库（2.74 MB）
├── memory/               # —— 第 2 层：关系记忆 ——
│   ├── intimacy.py       # 亲密度（Bowlby 内部工作模型）
│   ├── meaning_reservoir.py  # 意义水库
│   ├── memory_pool.py    # 记忆池（per-user/per-relationship）
│   ├── persona_profiles.py   # 人格档案存储
│   ├── relationship_personality.py  # 关系级人格（Bowlby per-relationship）
│   ├── social_graph.py   # 社交图（per-user）
│   └── topic_privacy.py  # 话题隐私分级
├── output/               # —— 第 3 层：输出/表面 ——
│   ├── bot_decision.py   # 机器人行为决策（如何回应）
│   ├── buffer_signals.py # 缓冲信号（per-user 状态信号）
│   ├── command_router.py # 指令路由
│   ├── commands.py       # AstrBot 指令实现
│   ├── diary_writer.py   # 日记/叙事身份输出
│   ├── emotion_classifier.py  # 情绪分类器
│   ├── narrative_identity.py  # 叙事身份
│   ├── predictive_sentinel.py  # 预测哨兵（前瞻性压力检测）
│   ├── prompt_injector.py  # 提示注入（向 LLM prompt 注入情绪/人格信号）
│   ├── public_api.py     # 公共 API facade
│   ├── surface_consumer.py  # 表面消费者（处理 AstrBot 事件流）
│   ├── surface_handler.py   # 表面处理器
│   └── trend_utils.py    # 趋势工具
└── regulation/           # —— 第 4 层：调节/力力学 ——
    ├── body_state.py     # 躯体状态（per-session）
    ├── counterfactual.py # 反事实推理
    ├── force_dynamics.py # 三元力学动力学（自然/社会/个体 → 力）
    ├── life_simulator.py # 人生模拟器
    ├── pattern_extractor.py  # 模式提取
    ├── persona_analyzer.py   # 人格分析（12 维拆解）
    ├── persona_report_parser.py  # 人格报告解析（外部 LLM 输出）
    ├── personality_drift.py  # 人格漂移
    ├── shadow_detector.py    # 阴影检测
    ├── superego.py           # 自我/超我（conscience + 内化规则）
    └── superego_guard.py     # 超我守卫（保护边界）
```

### 各子包职责一句话

- **`core/`** —— 人格内核：知识、标签、注册、配置。所有模块都依赖它，但**不依赖** memory/output/regulation。
- **`memory/`** —— 关系记忆：per-user 的亲密度、社交图、话题隐私、人格档案。**不依赖** output/regulation。
- **`output/`** —— 表面输出：把内部状态翻译成 AstrBot 指令/事件/LLM prompt。
- **`regulation/``** —— 调节层：人格分析、力学动力学、超我、漂移检测。**最重的一层**（superego.py 35 KB、force_dynamics.py 16 KB、persona_analyzer.py 12 KB）。

### `layer.py` 与 `store.py` 的角色

- **`layer.py`**：声明 `core < memory < output/regulation` 的依赖层级（与 memory 记录的"四层架构"一致）。
- **`store.py`**：per-session 躯体隔离 + 持久化接口（与 memory 中的 [[sylannengine-architecture]] "per-session 躯体隔离"对齐）。

---

## 3. `tests/` 镜像测试套件

`tests/` 与 `emotion_spirit/` 的子包**一一对应**，确保每个核心模块都有测试：

| 路径 | 测试覆盖 |
|------|----------|
| `tests/core/` | config、label_mapper、persona_labels_db、plugin_factory |
| `tests/memory/` | intimacy、meaning_reservoir、memory_pool、persona_profiles、relationship_personality、social_graph、topic_privacy |
| `tests/output/` | bot_decision、buffer_signals、command_router、diary_writer、emotion_classifier、predictive_sentinel、prompt_injector、public_api、surface_consumer、trend_utils |
| `tests/regulation/` | conscience_tracker_quantile、counterfactual、force_dynamics、life_simulator、pattern_extractor、personality_drift、shadow_detector、superego、superego_guard |
| `tests/test_*.py`（顶层） | cross-cutting：layer_enforcement、dir_structure、public_api_markers、packaging、registry_*、persona_analyzer_split、drift_simulator_labels、narrative_backtest_3072、init_persistence、kb_full_schema、kb_literature_progress、knowledge_base、force_state_from_persona_id、force_dynamics_simulation、force_dynamics_registry、phase2_integration、phase25_integration、emotion_integration、buffer_signals_per_user、downstream_per_user、main_per_user、intimacy_segmentation、spirit_store_ns、store、store_v3、parse_persona_id、persona_labels_db_compat、persona_labels_db_performance、check_registry_consistency、dim_consistency、no_stale_11dim_docstrings、real_scenarios_ambiguity、registry_build_dryrun、registry_mismatch_fix |

`tests/conftest.py` + `tests/fixture_labels.py`：公共 fixture（Persona 样本、KB 子集、dimension 常量）。

> **统计**：约 50 个测试文件，612/612 passed（KB 重建并 ship 进 plugin 之后的状态）。

---

## 4. `docs/` 用户与开发者文档

| 文件 | 作用 |
|------|------|
| `architecture.md` | 架构总览（4 层 + 数据流 + per-session 隔离） |
| `api.md` | 公共 API 详细说明（与 `public_api_stable.md` 互补） |
| `theory.md` | 理论依据（PAD 模型、MBTI 五轴、Bowlby 依恋、Stern 自我发展、Hofstede 等） |
| `user-guide.md` | 终端用户使用指南（如何开账号、看情绪、调参） |
| `mockups/` | 5 个 HTML 可视化样张：architecture-diagram、chat-transcript-intimacy、chat-transcript-trauma、personality-timeline、spirit-status-output |

---

## 5. `tools/` 维护工具

| 文件 | 作用 |
|------|------|
| `regenerate_kb.py` | 重建 `core/kb/persona_labels_db.json`（从 source data 生成 12 维标签库；**已 ship 进 git**） |
| `migrate_v1_imports_to_v2.py` | v1 → v2 import 路径批量迁移（用户从 v1 升级时跑） |
| `check_dim_consistency.py` | 维度常量一致性检查（11 维 vs 12 维 vs 文档） |
| `check_registry_consistency.py` | registry 与 module 实际维度的交叉校验 |

---

## 6. `data/` 运行时数据/模板

| 路径 | 作用 |
|------|------|
| `data/cmd_config.json` | AstrBot 指令运行期配置（默认 8174 字节） |
| `data/t2i_templates/` | Text-to-Image 报告模板（3 个 HTML：base、astrbot_powershell、astrbot_vitepress） |
| `data/temp/tool_images/` | 工具调用期间生成的临时图片占位（空目录） |

> 注：`verification/data/` 是 `data/` 的一个**工作副本**（同一份 cmd_config 与 t2i_templates，被 `data_collection/run_collection.py` 引用）。

---

## 7. `output/` 仿真产物

| 路径 | 作用 |
|------|------|
| `output/property_test_report.txt` | 属性测试结果（Hypothesis 生成） |
| `output/simulation_report.md` | 仿真可读总结 |
| `output/theory_report.md` | 理论一致性报告 |
| `output/simulation_data/personality_trace.json` | 5 persona 的人格漂移 trace（932 KB） |
| `output/simulation_data/turns.csv` | 仿真回合记录（134 KB） |

---

## 8. `verification/` 实验台（独立 harness）

> 这是 **Phase 3/4 验证专用子项目**，与生产代码 (`emotion_spirit/`) 解耦，可以独立运行实验。

| 路径 | 作用 |
|------|------|
| `verification/run_all.py` | 一键跑全部验证脚本的入口 |
| `verification/drift_simulator.py` | 人格漂移仿真器（5 persona × 长时序） |
| `verification/narrative_backtest_3072.py` | 3072 narrative 回测（Phase 3.0C Step 4 的核心实验） |
| `verification/property_tests.py` | Hypothesis 性质测试（不变量 fuzzing） |
| `verification/simulation_runner.py` | 仿真运行器（统一调度 drift + life + gossip） |
| `verification/surface_generator.py` | 表面生成器（合成模拟事件流） |
| `verification/surface_logger.py` | 表面日志器（记录 surface trace） |
| `verification/v12_param_sweep.py` | v1.2 参数扫描（3 字段：ambiguity/velocity/trajectory） |
| `verification/v17_stability_simulation.py` | v1.7 稳定性仿真（拆分 autonomy_guard 后的 12 维） |
| `verification/theory_proofs.py` | 理论证明（数值实验验证理论命题） |
| `verification/test_gossip_tendency_simulation.py` | gossip 倾向仿真（社交图） |
| `verification/statistics.py` | 统计分析工具 |
| `verification/visualize.py` | 可视化（生成 PNG 图表） |
| `verification/data/` | 实验用输入数据（与顶层 `data/` 同源） |
| `verification/data_collection/` | Phase 3.0B 数据收集（run_collection.py、visualize_collection.py、3 份 MD 报告 + 6 张图） |
| `verification/output/` | 实验输出（3072 narrative JSON 4 MB、7 张图） |

---

## 9. 当前框架总览（Framework Overview）

> **核心定位**：在 AstrBot 上挂一个**"灵魂内核"**，让 bot 在与每个用户的对话中表现出**持续演化的人格、关系记忆、情感反应**，并通过**力学动力学 + 自我调节**保持人格稳定。

### 9.1 架构分层（4 层 + 1 抽象 + 1 存储）

```
┌─────────────────────────────────────────────────────────────┐
│  AstrBot Host (main.py + metadata.yaml + _conf_schema.json) │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  emotion_spirit/  核心包 (4 层架构 + layer.py 抽象 + store) │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  core    │──▶│  memory  │──▶│ output   │   │regulation│  │
│  │  人格内核 │   │ 关系记忆 │   │ 表面输出 │   │ 调节/力  │  │
│  │(无依赖)  │   │(→core)   │   │(→core+   │   │(→core+   │  │
│  │          │   │          │   │  memory) │   │  memory) │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│        │              │              │              │       │
│        └──────────────┴──── layer.py ─┴──────────────┘       │
│        │              │              │              │       │
│        └──────────────┴──── store.py (per-session 持久化)──┘│
└─────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Knowledge Base  (core/kb/persona_labels_db.json, 2.74 MB)  │
│  - PAD raw + 12 维人格标签                                  │
│  - 由 tools/regenerate_kb.py 离线生成，ship 进 plugin       │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 关键设计决策（来自 memory 共识）

1. **per-session 躯体隔离**（[[sylannengine-architecture]]）：每个会话/用户拥有独立的状态副本，绝不跨用户传染。
2. **12 维人格**（[[emotion-spirit-v17]]）：从 11 维 `autonomy_guard` 拆出 `relational_autonomy` + `exploration_openness`，区分 ISTJ/ENTP 类人格差异。
3. **三层力力学**（[[emotion-spirit-phase-3-progress]] + [[three-force-framework]]）：自然/社会/个体三元力 → 力竭落点决定状态。
4. **KB 离线生成 + ship**（[[emotion-spirit-persona-kb-regen-plan]]）：`persona_labels_db.json` 2.74 MB 入 git，clone 即用，**解决 release blocker**。
5. **per-user + SocialGraph + TopicPrivacy**（[[phase2-design]]）：Phase 2.0 完成 8/8 步。
6. **RelationshipPersonality + 4 段 tone**（[[emotion-spirit-phase25]]）：Bowlby 内部工作模型 per-relationship。

### 9.3 关键模块清单

| 关注点 | 负责模块 |
|--------|----------|
| 12 维人格拆解 | `regulation/persona_analyzer.py`、`regulation/persona_report_parser.py` |
| 标签库生成/查询 | `core/persona_labels_db.py`、`core/label_mapper.py`、`core/kb/persona_labels_db.json` |
| 关系记忆 | `memory/memory_pool.py`、`memory/relationship_personality.py`、`memory/intimacy.py` |
| 社交图 | `memory/social_graph.py`、`memory/topic_privacy.py` |
| 三元力 | `regulation/force_dynamics.py`、`regulation/counterfactual.py` |
| 自我调节 | `regulation/superego.py`、`regulation/superego_guard.py`、`regulation/conscience_tracker` |
| 漂移检测 | `regulation/personality_drift.py`、`regulation/shadow_detector.py` |
| LLM 交互 | `output/emotion_classifier.py`、`output/prompt_injector.py`、`output/diary_writer.py` |
| 事件流 | `output/surface_consumer.py`、`output/surface_handler.py`、`output/buffer_signals.py` |
| AstrBot 集成 | `main.py`、`output/commands.py`、`output/command_router.py` |

### 9.4 数据流（一次对话回合）

```
用户消息
  └─▶ AstrBot 事件
        └─▶ emotion_spirit/output/surface_consumer.py
              ├─▶ regulation/persona_analyzer (12 维)
              ├─▶ regulation/force_dynamics (三元力)
              ├─▶ regulation/superego (conscience 守门)
              ├─▶ memory/memory_pool (更新关系/亲密度)
              └─▶ output/prompt_injector (拼装 LLM prompt)
                    └─▶ LLM 生成回复
                          └─▶ output/diary_writer (写日记)
                                └─▶ store.py (持久化到磁盘)
```

### 9.5 测试与验证

- **单元/集成测试**：`tests/` 镜像 4 层子包，约 50 文件，**612/612 passed**。
- **属性测试**：`verification/property_tests.py` (Hypothesis) + `output/property_test_report.txt`。
- **仿真**：`verification/simulation_runner.py` 跑 drift/life/gossip 三套，`output/simulation_report.md` 出总结。
- **3072 narrative 回测**：`verification/narrative_backtest_3072.py` 输出到 `verification/output/narrative_backtest_3072.json` (4 MB)。
- **可视化**：`verification/visualize.py` + `verification/data_collection/visualize_collection.py` 生成 PNG 图表。

### 9.6 下一步可推进方向（基于 memory）

| 方向 | 来源 | 状态 |
|------|------|------|
| Phase 5+ 力学河流 / 内心独白 / Steppenwolf | [[emotion-spirit-phase-4-launch-complete]] | 待用户选执行方式 |
| v2.1 兼容清理 / data 迁移 / GUI 调参 | 同上 | 同上 |
| Main branch 落后 origin 4 commits | [[emotion-spirit-persona-kb-regen-plan]] | 待 `git push` |

---

## 10. 一句话总结

> `astrbot_plugin_emotion_spirit` 是一个 **4 层架构、30 个核心模块、612 个测试、12 维人格 + 三元力学 + per-user 关系记忆** 的 AstrBot 灵魂内核插件；其设计哲学可概括为"**人格内核 → 关系记忆 → 表面输出**"三层流动，配合**调节层**保持人格稳定，并以 `core/kb/persona_labels_db.json` 作为离线可重建的可移植知识库。
