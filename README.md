# emotion_spirit v1.1.0

> [中文] SylannEngine 之上的长期记忆、人格演化与超我调控层
> [English] Long-term memory, personality evolution, and superego regulation, built on top of SylannEngine

[![Tests](https://img.shields.io/badge/tests-886%20passed-brightgreen)]()
[![CI](https://github.com/Aston957/astrbot_plugin_emotion_spirit/actions/workflows/ci.yml/badge.svg)](https://github.com/Aston957/astrbot_plugin_emotion_spirit/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Aston957/astrbot_plugin_emotion_spirit)](https://github.com/Aston957/astrbot_plugin_emotion_spirit/releases)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)]()
[![AstrBot](https://img.shields.io/badge/astrbot-%3E%3D4.9.2-orange)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[架构图 (architecture-diagram.html)](docs/mockups/architecture-diagram.html) | [Public API](public_api_stable.md) | [CHANGELOG](CHANGELOG.md)

---

## 架构说明 / Architecture

**SylannEngine 计算核心 (`sylanne`) 已内嵌到本插件**，无需单独安装外部插件。引擎在插件初始化时自动创建（需要 LLM provider 可用），无 LLM 时优雅降级为纯 emotion_spirit 模式。

`sylanne` 包含 7 层计算脊柱（HDC → 预测编码 → 伤痕-空洞 → 关系层论 → HGT → 自创生 → 相变），源码来自 [SylannEngine](https://github.com/Ayleovelle/SylannEngine)，经作者授权以 MIT 许可使用。

---

## 下载 / Download

### ⭐ 方式 1: GitHub Release slim zip (推荐)

GitHub Release 会自动生成**只含运行所需文件**的 slim zip (~4 MB, 含 sylanne + KB), 跳过测试/仿真/开发工具.

1. 访问 [Releases 页面](https://github.com/Aston957/astrbot_plugin_emotion_spirit/releases)
2. 下载 `astrbot-plugin-emotion-spirit-1.1.0.zip`
3. 解压得到 `astrbot_plugin_emotion_spirit/` 文件夹
4. 复制到 AstrBot 的 `data/plugins/` 目录
5. 重启 AstrBot → 插件自动加载

zip **包含** (用户运行所需):
- `main.py`、`metadata.yaml`、`_conf_schema.json`
- `emotion_spirit/` 核心包 (含 2.74 MB 离线 KB)
- `data/` 运行时配置 (cmd_config.json + t2i_templates/)
- `pyproject.toml`、`requirements.txt`、`README.md`、`LICENSE`

zip **不包含** (开发者专用, 通过 .gitattributes 的 `export-ignore` 排除):
- `tests/`、`verification/`、`output/`、`tools/`、`docs/`
- `conftest.py`、`dev-requirements.txt`、`CHANGELOG.md`
- `.github/`、`.git*`、`__pycache__/`、`.pytest_cache/`

### 方式 2: pip install (开发者)

```bash
git clone https://github.com/Aston957/astrbot_plugin_emotion_spirit.git
cd astrbot_plugin_emotion_spirit
pip install -e .[dev]
```

### 方式 3: 拖拽整个仓库 (不推荐, 含 11 MB 开发者资料)

---

## 这是什么 / What is this

emotion_spirit 是 AstrBot 生态的情感计算插件，负责"自我 + 超我"层。SylannEngine 计算核心已内嵌（`sylanne`），无需外部依赖。插件构建四层长期记忆（缓冲池 / 温池 / 冷池 / 幽灵）、13 维人格演化、三元力学引擎、超我调控、LLM 生活模拟、bot 回复记忆等高级功能。

emotion_spirit is an AstrBot ecosystem emotion-computing plugin responsible for the "ego + superego" layer. The SylannEngine compute core (`sylanne`) is embedded — zero external dependencies. The plugin builds a four-tier long-term memory, 13-dimensional personality evolution, three-force dynamics engine, superego regulation, LLM life simulation, and bot-reply memory.

```
弗洛伊德           实现                  时间尺度
────────────────────────────────────────────────
本我 (Id)          sylanne (内嵌)   ms ~ hr
自我 (Ego)         emotion_spirit        hr ~ month
超我 (Superego)    emotion_spirit        贯穿
```

## 核心能力 / Key Features

### 记忆层 / Memory Layer (Phase 2)
- **4 层记忆**: 缓冲池（待确认）→ 温池（已确认）→ 冷池（模式沉淀）→ 幽灵（永久创伤）
- **6 维亲密度**: 不对称的亲密度追踪（warmth / trust / dependence / security / familiarity / longing）
- **Ebbinghaus 遗忘**: 记忆自然衰减，被召回时强化
- **关系人格微调** (Phase 2.5): 每个关系独立的人格参数

### 演化层 / Evolution Layer (Phase 1.5 + Phase 3)
- **13 维人格漂移检测** (双 EMA): 11 维 (Phase 1.5) + 3 维 (Phase 3) + v1.7 拆分 2 维
- **月度叙事弧**: 上升 / 下降 / 停滞 / 循环型
- **阴影检测** (荣格式): 回声模式、回避模式、确认偏差
- **反事实模拟**: 为无法消化的创伤提供替代视角

### 调控层 / Regulation Layer (Phase 1.5 + Phase 3 + Phase 4)
- **价值对齐**: 追踪行为是否符合人格的价值观
- **ConscienceTracker 滑动窗口 P95 归一化**: 区分"持续 N 次小冲突"vs"持续 1 次大冲突"
- **理想自我差距**: 当前人格与理想人格的差距计算
- **意义蓄水池**: 长期意义积累与释放

### 三元力学引擎 / Three-Force Dynamics
- **3 维权重**: natural (自然) / social (社会) / individual (个体), 各维 ∈ [0, 1], sum = 1
- **算法 H**: 5 fixture × 8 场景仿真 + P95 分位 baseline
- **3072 KB 文献化 baseline** (Phase 3.0C): 涵盖 5 轴人格 (MBTI × 依恋 × 情绪策略 × 冲突风格 × 时间取向)
- **Step 4 narrative 回测**: natural 10.2% / social 32.6% / individual 57.2%

### 生活模拟 / Life Simulation (v1.1.0)
- **LifeSimulatorV2**: 日程生成引擎, 规则模板 + LLM 双模式生成每日计划; 模型人格差异调制活动选择
- **随机事件注入**: 按 personality 概率分布自然插入生活事件, 带 graceful LLM fallback
- **DailyPlan 持久化**: `to_dict`/`from_dict` 跨会话保存, 重启不丢日程
- **`/view_schedule` 命令**: 查看 bot 当日计划与事件
- **6 维事件权重**: 阅读/散步/烹饪/思考/创造/休息/观察, 各含 valence/arousal/share_tendency

### 分级 LLM 调度 / Tiered LLM Dispatch (v1.1.0)
- **`_get_llm_callable(feature)` chokepoint**: 所有无 LLM 注入统一入口, 按 feature 查分级 provider
- **5 个分级 provider**: engine / analyzer (sylanne) / life_sim / dream / diary — 每个功能段独立配 provider_id, 慢的 reasoning 模型给 diary/life_sim, 快的 flash 给 engine
- **配置迁移 framework**: `@register_migration` + 版本号自动推进 + 幂等设计; `split_llm_tier` rule 把旧 v3 的 `llm_tier` 5 provider 自动迁到新的 per-feature 段, 用户 config 无感升级
- **WebUI 15 配置段**: persona_mode / auto_source / feature_toggles / sylanne / memory_pool / emotion_sensitivity / sentinel_thresholds / safety_layer / life_sim_v2 / dream / diary / reflex_learner / intimacy_thresholds / superego_thresholds / shadow_detector

### 日记系统 / Diary (v1.1.0)
- **DiaryWriter LLM 生成**: `enable_diary_llm=true` 时真调 LLM 生成日记正文 (之前只构造 prompt 不调 LLM)
- **定时写日记**: `diary.schedule_hours` 配触发时间, `_schedule_diary_generation_loop` 异步调度 (复刻 2am scheduler 模式, 防重复触发)
- **分级 provider**: reasoning 类模型 30s+ 正常, 快速需求选 flash; 手动 `/reflect_diary` 立即触发

### 其他特性
- **pyproject.toml 现代打包**: `pip install -e .[dev]` 干净, setuptools >=80, python >=3.11
- **4 层目录结构**: `emotion_spirit/{core|memory|regulation|output}/`, 依赖方向严格单向
- **Public API 稳定契约**: 38 modules 加 `__all__`, `public_api_stable.md` 列 stable/internal/deprecated 三表
- **v1.x 兼容垫片**: `_v1_compat.py` + `_DeprecatedImportFinder` hook (codebase 内部卫生)

## 截图 / Screenshots

5 张 mockup 在 `docs/mockups/`:

| Mockup | 内容 | 引用时机 |
|--------|------|----------|
| [chat-transcript-intimacy.html](docs/mockups/chat-transcript-intimacy.html) | 3 轮对话, 亲密度 0.5 → 0.73 | README §核心能力 记忆层 |
| [chat-transcript-trauma.html](docs/mockups/chat-transcript-trauma.html) | 1 轮 trauma 触发幽灵消化 + ConscienceTracker B2 减压 | README §核心能力 演化层 |
| [spirit-status-output.html](docs/mockups/spirit-status-output.html) | `/view_status` 完整输出 (含三元力学 + ConscienceTracker B2) | README §指令 |
| [personality-timeline.html](docs/mockups/personality-timeline.html) | 6 个月 13 维人格漂移时间线 | README §核心能力 演化层 |
| [architecture-diagram.html](docs/mockups/architecture-diagram.html) | 5 层架构图 (core/memory/regulation/output + sylanne) | architecture.md §架构 + README §快速开始 |

## 安装 / Installation

### 前置条件 / Prerequisites

- AstrBot v4.9.2+
- Python >= 3.11
- ~~SylannEngine v1.0.0rc1+ 插件~~ (sylanne 已内嵌，无需安装)

### 通过 pip (推荐)

```bash
# 从源码安装 (editable)
cd astrbot_plugin_emotion_spirit
pip install -e .[dev]

# 验证
python -c "import emotion_spirit; print(emotion_spirit.__version__)"
# 期望: 1.1.0
```

### 通过 AstrBot 拖拽 (传统)

1. 将 `emotion_spirit` 目录复制到 AstrBot 的 `data/plugins/` 目录(从 Release zip 解压后得到的就是这个)
2. 重启 AstrBot
3. 插件自动加载 (sylanne 已内嵌，无需额外安装)

### KB 数据 / KB Data (自动加载 / Auto-loaded)

**3072 组合人格基线 KB 跟 plugin 一起分发,无需额外下载或配置**:

- **位置**: `emotion_spirit/core/kb/persona_labels_db.json` (2.74 MB, 3072 entries, **入 git**)
- **加载**: 启动时第一次查询自动 lazy load (~32 ms),之后查询是 in-memory O(1) lookup
- **覆盖**: 设环境变量 `EMOTION_SPIRIT_PERSONA_KB_PATH=/custom/path.json` 可指向其他位置(部署灵活)
- **何时缺失**: 启动 log 出现 `persona_labels_db loaded: 3072 entries` 表示正常;如果出现 `not found, returning empty KB` 则 plugin 安装不完整(重新 `git clone` 或 `pip install -e .`)
- **重生成** (维护者): 改了 `emotion_spirit/core/knowledge.py` 的 delta 字典后,跑 `python tools/regenerate_kb.py` 重写 JSON

Confidence 分布:**A=0 / B=16 / C=160 / D=2896**(`B` 16-personalities literature 锚点,`C` literature 微调,`D` 算法计算 + 诚实标"computed, no literature",honest disclosure per spec §3.5 D3)

## 快速开始 / Quick Start

```python
# 在 AstrBot 插件中调用
from emotion_spirit import PublicAPI

api = PublicAPI()

# 1. 获取情绪状态
state = await api.get_emotion_state(session_key)
# 返回 11 字段 (PAD + distribution + primary + secondary + intensity + description
#             + label + emotion_ambiguity + emotion_velocity)

# 2. 获取身体状态
body = await api.get_body_state(session_key)
# 返回 {warmth, pulse, expression, repair}

# 3. 情绪轨迹 (N=8 帧, opt-in)
trajectory = await api.get_emotion_state(session_key, include_trajectory=True)
# 返回 emotion_trajectory 字段: list of {valence, arousal, dominance, timestamp}

# 4. 三元力学状态
from emotion_spirit.regulation.force_dynamics import ForceDynamics
forces = ForceDynamics().compute(personality, body_state, conscience_pressure)
# 返回 {natural: float, social: float, individual: float, dominant: str}

# 5. ConscienceTracker 压力
from emotion_spirit.regulation.superego import ConscienceTracker
tracker = ConscienceTracker()
pressure = tracker.get_pressure()
# ∈ [0, 1] (P95-normalized over 200-frame sliding window)
```

### 3 个最常用命令

| 命令 | 说明 |
|------|------|
| `/view_status` | 查看系统状态 (含三元力学 + ConscienceTracker B2 输出) |
| `/reflect_drift` | 查看 13 维人格漂移状态 |
| `/reflect_diary` | 手动触发日记写入 |

## 配置 / Configuration

在 AstrBot WebUI 的插件配置中，分为 4 个区域：

### 1. 人格管理模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `persona_mode` | select | `disabled` | auto / disabled |
| `auto_source` | select_persona | - | AstrBot 人格 (auto 模式 LLM 自动解析) |

### 2. 功能开关

| 配置段 | 配置项 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| `feature_toggles` | `enable_shadow_detector` | bool | true | 阴影检测 |
| `feature_toggles` | `enable_sentinel` | bool | true | 预警系统 (13 信号) |
| `feature_toggles` | `enable_narrative` | bool | true | 月度叙事弧 |
| `life_simulator` | `enable_life_fragment` | bool | true | Mode A: 对话中插入生活片段 |
| `proactive_chat` | `enable_proactive_prompt` | bool | true | Mode B: 长沉默后主动发起对话 |
| `memory_pool` | `warm_max` / `cold_max` / `ghost_max` | int | 500/2000/50 | 记忆池容量 |
| `safety_layer` | `enabled` | bool | true | 安全层开关 |
| `diary` | `enable_diary_llm` | bool | false | 启用 LLM 生成日记正文（关闭时仅存 prompt） |
| `diary` | `diary_provider_id` | select_provider | - | 日记 LLM Provider（reasoning 类模型 30s+ 正常, 快速需求选 flash 类模型） |

### 3. 性能调优

| Env Var | 默认 | 说明 |
|---------|------|------|
| `EMOTION_SPIRIT_PRESSURE_WINDOW` | 200 | ConscienceTracker 滑动窗口大小 |

### 4. 高级 / 调试

兼容垫片 (`_v1_compat.py`) 在 codebase 内部卫生用, 触发 `DeprecationWarning`. 旧 import path (`emotion_spirit.public_api` 等 38 mapping) 自动 redirect 到新路径 (`emotion_spirit.output.public_api`) 同样触发 `DeprecationWarning`.

## 安全 / Security

> **⚠️ `data/cmd_config.json` 含 AstrBot dashboard 凭证 — 必须修改后才能上线使用**

### 当前情况

本插件 `data/cmd_config.json` 内含 AstrBot dashboard admin 配置, **必须视为模板**而非可用凭证。安装后请立即：

1. 启动 AstrBot, 访问 dashboard
2. 首次登录会要求改密码 (因为 `password_change_required: true`)
3. 设置自己的强密码

或者手动编辑 `data/cmd_config.json` 修改 `dashboard.password` 字段。

### 开发者：如何避免泄漏凭证

仓库自带 pre-commit secret 检查。**首次 clone 后跑一次**：

```bash
./scripts/install_hooks.sh
```

这会安装 `scripts/hooks/pre-commit` 到 `.git/hooks/pre-commit`，**任何 commit 前自动扫描**：

| 检查模式 | 例子 |
|----------|------|
| pbkdf2 密码哈希 (AstrBot 格式) | `pbkdf2_sha256$600000$...` |
| OpenAI / Anthropic API key | `sk-...`, `sk-ant-...`, `gsk_...` |
| GitHub PAT | `ghp_...`, `gho_...`, `ghs_...`, `github_pat_...` |
| AWS access key | `AKIA[0-9A-Z]{16}` |
| PEM 私钥块 | `-----BEGIN ... PRIVATE KEY-----` |
| URL 嵌入凭证 | `https://<user>:<pass>@<host>` |

**误报处理**：把路径加到 `.secrets-allowlist`（fnmatch glob 格式）。

**真实泄漏处理**：
1. **立即 rotate** 凭证
2. 用 `git filter-repo --replace-text replacements.txt` 重写历史
3. Force-push

详见 [[emotion-spirit-secret-leak]] memory 或 commit `2ef828b` 的 diff。

### 2026-06-09 事件教训

`data/cmd_config.json` 曾含真实 AstrBot admin 凭证（md5 + pbkdf2），被 force-pushed 清洗。**所有使用过该凭证的 AstrBot 实例必须修改密码**——即使 git history 已清洗，**凭证视为已暴露**。

## 命令 / Commands

3 个 namespace, 12 个命令 (Phase 4 post-merge ns 化, v1.x 旧 `/spirit_*` 入口已删).

### `setup_*` ns (4 命令) — 人格配置

| 命令 | 说明 | 依赖模块 |
|------|------|----------|
| `/setup_init` | 初始化当前人格参数 (仅 auto 模式) | PersonaAnalyzer (L2) |
| `/setup_relabel` | 重新分析人格 (LLM 重新解析) | PersonaAnalyzer (L2) |
| `/setup_switch <name>` | 切换人格 | PersonaProfile (L1) |
| `/setup_list` | 列出所有人格 | PersonaProfile (L1) |

### `view_*` ns (5 命令) — 状态查看

| 命令 | 说明 | 依赖模块 |
|------|------|----------|
| `/view_status` | 查看系统状态 (含三元力学 + ConscienceTracker B2) | PublicAPI (L3) |
| `/view_detail` | 查看 13 维参数详情 | PersonaProfile (L1) |
| `/view_whoami` | 查看 5 轴人格标签 | PersonaProfile (L1) |
| `/view_memory` | 显示当前用户 buffer/warm/cold 条目摘要 | MemoryPool (L1) |
| `/view_force` | 三元力学状态 + 13 维→力映射 | ForceDynamics (L2) |

### `reflect_*` ns (5 命令) — 内省

| 命令 | 说明 | 依赖模块 |
|------|------|----------|
| `/reflect_drift` | 查看 13 维人格漂移状态 | PersonalityDrift (L2) |
| `/reflect_sentinel` | 查看 13 信号预警状态 | PredictiveSentinel (L3) |
| `/reflect_shadows` | 查看阴影检测 | ShadowDetector (L2) |
| `/reflect_diary` | 手动触发日记写入 | DiaryWriter (L3) |
| `/reflect_patterns` | 查看行为模式 | PatternExtractor (L2) |

## 文档导航 / Documentation

| 受众 | 文档 | 内容 |
|------|------|------|
| **Bot operator** | [README.md](README.md) | 本文件 (安装 + 命令 + 快速开始) |
| **Bot operator** | [docs/user-guide.md](docs/user-guide.md) | 用户手册 (人格配置 + 高级功能) |
| **Developer** | [docs/api.md](docs/api.md) | API 完整参考 (Stable / Internal / Deprecated) |
| **Public API 契约** | [public_api_stable.md](public_api_stable.md) | 跨 minor 版本保证不破坏的 API 列表 |
| **Maintainer** | [docs/architecture.md](docs/architecture.md) | 架构文档 (4 层 + Phase 演化) |
| **Maintainer** | [docs/theory.md](docs/theory.md) | 理论依据 (心理学 + 神经科学 + LLM agent) |
| **Spec** | [docs/superpowers/specs/2026-06-08-phase-4-launch-design.md](docs/superpowers/specs/2026-06-08-phase-4-launch-design.md) | 设计 spec (12 章节) |
| **Plan** | [docs/superpowers/plans/2026-06-08-phase-4-launch.md](docs/superpowers/plans/2026-06-08-phase-4-launch.md) | 实施 plan (6 task) |

## 4 层目录结构 / 4-Layer Directory Structure

```
emotion_spirit/
├── __init__.py                # 公开 API 入口 + _DeprecatedImportFinder (C3) + PEP 440 version (C2)
├── layer.py                   # 抽象基类 (留根)
├── _version.py                # PEP 440 version 真相源 (1.1.0)
├── _v1_compat.py              # v1.x 兼容垫片 + DeprecationWarning
├── store.py                   # SpiritStore v3 持久化
├── core/                      # L0: 基础 (6 modules)
│   ├── registry.py            # @register_module 装饰器
│   ├── config.py              # 配置常量
│   ├── knowledge.py           # 13 维人格知识库
│   ├── persona_labels_db.py   # 3072 KB loader
│   ├── kb/                    # KB 数据 (跟 plugin 一起分发)
│   │   └── persona_labels_db.json  # 2.74 MB, 3072 entries (B=16, C=160, D=2896)
│   ├── label_mapper.py        # 标签 → 参数双向映射
│   └── plugin_factory.py      # 插件装配入口
├── memory/                    # L1: 状态 (10 modules)
│   ├── memory_pool.py         # 4 层记忆池 (flat 存储, Phase D 重构)
│   ├── unified_entry.py       # 统一记忆条目 (情境衰减)
│   ├── decay_model.py         # Ebbinghaus 衰减模型
│   ├── cascade_engine.py      # 级联引擎
│   ├── memory_sampler.py      # 记忆采样器
│   ├── intimacy.py            # 6 维亲密度
│   ├── relationship_personality.py  # 关系人格
│   ├── social_graph.py        # 社交图
│   ├── topic_privacy.py       # 话题隐私
│   ├── meaning_reservoir.py   # 意义蓄水池
│   ├── persona_profiles.py    # 人格档案
│   └── suppression.py         # 压制状态 (SuppressionState)
├── regulation/                # L2: 调控 (12 modules)
│   ├── superego.py            # 价值对齐 + ConscienceTracker (Phase 4 C1 B2)
│   ├── superego_guard.py      # 守门人
│   ├── body_state.py          # 身体状态
│   ├── force_dynamics.py      # 三元力学 (Phase 3 算法 H)
│   ├── personality_drift.py   # 13 维漂移
│   ├── shadow_detector.py     # 阴影检测
│   ├── pattern_extractor.py   # 行为模式
│   ├── life_simulator.py      # 生活模拟
│   ├── persona_analyzer.py    # 人格分析器
│   ├── persona_report_parser.py  # 报告解析器
│   ├── counterfactual.py      # 反事实模拟
│   └── collapse_archetype.py  # 记忆崩溃原型
├── output/                    # L3: 输出 (15 modules)
│   ├── public_api.py          # 公开 API 入口 (PublicAPI)
│   ├── bot_decision.py        # Bot 决策 (含 proactive 适配)
│   ├── emotion_classifier.py  # 情绪分类
│   ├── prompt_injector.py     # Prompt 组装
│   ├── surface_consumer.py    # Surface 消费
│   ├── surface_handler.py     # Surface 处理
│   ├── diary_writer.py        # 日记
│   ├── command_router.py      # 命令路由
│   ├── commands.py            # 命令实现
│   ├── narrative_identity.py  # 叙事身份
│   ├── predictive_sentinel.py # 预警
│   ├── buffer_signals.py      # 缓冲池信号
│   ├── trend_utils.py         # EMA 工具
│   ├── realtime_dispatch.py   # 实时调度
│   └── rhythm_learner.py      # 节奏学习
├── bridge/                    # SylannEngine 桥接层 (3 modules)
│   ├── engine_manager.py      # 引擎管理器 (inject/process_async)
│   ├── personality_bridge.py  # 5D→12D 人格映射
│   └── hotpool_forwarder.py   # 热池转发器
├── migrations/                # 配置迁移框架 (5 modules)
│   ├── registry.py            # @register_migration 装饰器
│   ├── state.py               # MigrationState 持久化
│   ├── runner.py              # run_migrations() 主逻辑
│   └── rules/
│       └── v3_0_to_v3_1.py    # 配置迁移规则 (2 条)
└── sylanne/              # SylannEngine 计算核心内嵌 (46 modules)
    ├── adapter.py             # 引擎适配器
    ├── algebra.py             # 代数运算
    ├── compute/               # 7 层计算脊柱 (HDC→预测编码→伤痕-空洞→关系层论→HGT→自创生→相变)
    └── ...                    # (详见 SylannEngine 源码)
```

**依赖方向**: `L0 ← L1 ← L2 ← L3` (严格单向, `test_layer_dependency_no_reverse` enforce)

## 项目规模 / Project Scale

| 指标 | 数值 |
|------|------|
| 模块 | 109 (58 core + 46 sylanne + 5 migrations) |
| 测试 | 886 passed, 0 failures |
| 人格维度 | 13 维 |
| 外部依赖 | 0 (仅依赖 AstrBot) |
| Python | >= 3.11 |
| AstrBot | >= 4.9.2 |

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Aston957/astrbot_plugin_emotion_spirit&type=Date)](https://star-history.com/#Aston957/astrbot_plugin_emotion_spirit&Date)

## License & Attribution / 许可与致谢

**本插件全部源代码**以 **MIT License** 发布(见 [LICENSE](LICENSE) 文件)。

`sylanne/` 目录包含 [SylannEngine](https://github.com/Ayleovelle/SylannEngine) v2 计算核心，经原作者授权以 MIT 许可使用。感谢 SylannEngine 作者的开源贡献。

## 引用 / Citations

完整理论依据见 [docs/theory.md](docs/theory.md). 关键 5 篇:

1. Tononi, G. (2004). *An Information Integration Theory of Consciousness*. BMC Neuroscience. (Φ 门控)
2. Bowlby, J. (1969). *Attachment and Loss, Vol. 1: Attachment*. Basic Books. (依恋理论)
3. McCrae, R. R., & Costa, P. T. (1992). *Revised NEO Personality Inventory*. Psychological Assessment Resources. (大五人格)
4. Russell, J. A., & Mehrabian, A. (1977). *Evidence for a three-factor theory of emotions*. Journal of Research in Personality. (PAD 模型)
5. Jung, C. G. (1968). *The Archetypes and the Collective Unconscious*. Princeton University Press. (阴影 / 投射 / 自性)

三元力学 (natural / social / individual) 灵感来源:
- 社会生态学 (Bronfenbrenner 1979): 微观 / 中观 / 宏观系统
- 道德基础理论 (Haidt 2007): 多基础道德心理学
- 自我决定理论 (Deci & Ryan 2000): 自主 / 胜任 / 关联
