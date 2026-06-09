# emotion_spirit v2.0.0v1

> [中文] SylannEngine 之上的长期记忆、人格演化与超我调控层
> [English] Long-term memory, personality evolution, and superego regulation, built on top of SylannEngine

[![Tests](https://img.shields.io/badge/tests-612%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)]()
[![AstrBot](https://img.shields.io/badge/astrbot-%3E%3D4.9.2-orange)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

[架构图 (architecture-diagram.html)](docs/mockups/architecture-diagram.html) | [版本: v2.0.0v1 (PEP 440: 2.0.0.post1)](public_api_stable.md) | [CHANGELOG](CHANGELOG.md)

---

## 这是什么 / What is this

emotion_spirit 是 AstrBot 生态的 SylannEngine 下游插件，负责"自我 + 超我"层。SylannEngine 处理即时情感（本我，ms ~ hr），emotion_spirit 在其之上构建四层长期记忆（缓冲池 / 温池 / 冷池 / 幽灵）、11+3=14 维人格演化、月度叙事弧、阴影检测、三元力学引擎、价值对齐、良心压力、理想自我等高级功能。Phase 3 引入三元力学（自然/社会/个体），Phase 4 完成 v2.0 收尾（4 层目录重构、ConscienceTracker 滑动窗口 P95 归一化、pyproject 现代打包、Public API 稳定契约）。

emotion_spirit is an AstrBot ecosystem plugin sitting downstream of SylannEngine, responsible for the "ego + superego" layer. While SylannEngine handles immediate affect (id, ms ~ hr), emotion_spirit builds on top with: a four-tier long-term memory (buffer / warm / cold / ghost), 11+3=14-dimensional personality evolution, monthly narrative arcs, shadow detection, a three-force dynamics engine, value alignment, conscience pressure, and ideal-self gap analysis. Phase 3 introduced three-force dynamics (natural / social / individual). Phase 4 closes the v2.0 release (4-layer directory refactor, ConscienceTracker sliding-window P95 normalization, modern pyproject packaging, public API stability contract).

```
弗洛伊德           实现                  时间尺度
────────────────────────────────────────────────
本我 (Id)          SylannEngine          ms ~ hr
自我 (Ego)         emotion_spirit v2.0   hr ~ month
超我 (Superego)    emotion_spirit v2.0   贯穿
```

## 核心能力 / Key Features

### 记忆层 / Memory Layer (Phase 2)
- **4 层记忆**: 缓冲池（待确认）→ 温池（已确认）→ 冷池（模式沉淀）→ 幽灵（永久创伤）
- **6 维亲密度**: 不对称的亲密度追踪（warmth / trust / dependence / security / familiarity / longing）
- **Ebbinghaus 遗忘**: 记忆自然衰减，被召回时强化
- **关系人格微调** (Phase 2.5): 每个关系独立的人格参数

### 演化层 / Evolution Layer (Phase 1.5 + Phase 3)
- **14 维人格漂移检测** (双 EMA): 11 维 (Phase 1.5) + 3 维 (Phase 3) + v1.7 拆分 2 维
- **月度叙事弧**: 上升 / 下降 / 停滞 / 循环型
- **阴影检测** (荣格式): 回声模式、回避模式、确认偏差
- **反事实模拟**: 为无法消化的创伤提供替代视角

### 调控层 / Regulation Layer (Phase 1.5 + Phase 3 + Phase 4)
- **价值对齐**: 追踪行为是否符合人格的价值观
- **ConscienceTracker 滑动窗口 P95 归一化** (Phase 4 C1, **v2.0 新**): 区分"持续 N 次小冲突"vs"持续 1 次大冲突"
- **理想自我差距**: 当前人格与理想人格的差距计算
- **意义蓄水池**: 长期意义积累与释放

### 三元力学引擎 / Three-Force Dynamics (Phase 3, **v2.0 算法 H**)
- **3 维权重**: natural (自然) / social (社会) / individual (个体), 各维 ∈ [0, 1], sum = 1
- **算法 H**: 5 fixture × 8 场景仿真 + P95 分位 baseline
- **3072 KB 文献化 baseline** (Phase 3.0C): 涵盖 5 轴人格 (MBTI × 依恋 × 情绪策略 × 冲突风格 × 时间取向)
- **Step 4 narrative 回测**: natural 10.2% / social 32.6% / individual 57.2%

### v2.0 新增 / v2.0 New
- **ConscienceTracker B2 滑动窗口 P95 归一化**: 累加器是真相源, 消费时归一化, 给极端事件留 5% headroom
- **pyproject.toml 现代打包**: `pip install -e .[dev]` 干净, setuptools >=80, python >=3.11
- **4 层目录重构**: `emotion_spirit/{core|memory|regulation|output}/`, 依赖方向严格单向
- **Public API 稳定契约**: 38 modules 加 `__all__`, `public_api_stable.md` 列 stable/internal/deprecated 三表
- **v1.x 兼容垫片**: `_v1_compat.py` + `_DeprecatedImportFinder` hook (codebase 内部卫生)

## 截图 / Screenshots

5 张 mockup 在 `docs/mockups/`:

| Mockup | 内容 | 引用时机 |
|--------|------|----------|
| [chat-transcript-intimacy.html](docs/mockups/chat-transcript-intimacy.html) | 3 轮对话, 亲密度 0.5 → 0.73 | README §核心能力 记忆层 |
| [chat-transcript-trauma.html](docs/mockups/chat-transcript-trauma.html) | 1 轮 trauma 触发幽灵消化 + ConscienceTracker B2 减压 | README §核心能力 演化层 |
| [spirit-status-output.html](docs/mockups/spirit-status-output.html) | `/view_status` 完整输出 (含三元力学 + ConscienceTracker B2) | README §指令 |
| [personality-timeline.html](docs/mockups/personality-timeline.html) | 6 个月 14 维人格漂移时间线 | README §核心能力 演化层 |
| [architecture-diagram.html](docs/mockups/architecture-diagram.html) | v2.0 4 层架构图 (core/memory/regulation/output) | architecture.md §架构 + README §快速开始 |

## 安装 / Installation

### 前置条件 / Prerequisites

- AstrBot v4.9.2+
- Python >= 3.11
- SylannEngine v1.0.0rc1+ 插件

### 通过 pip (推荐, **v2.0 新**)

```bash
# 从源码安装 (editable)
cd astrbot_plugin_emotion_spirit
pip install -e .[dev]

# 验证
python -c "import emotion_spirit; print(emotion_spirit.__version__)"
# 期望: 2.0.0.post1
```

### 通过 AstrBot 拖拽 (传统)

1. 将 `astrbot_plugin_emotion_spirit` 目录复制到 AstrBot 的 `data/plugins/` 目录
2. 重启 AstrBot
3. 插件会自动连接 SylannEngine（延迟 2 秒，等待 SylannEngine 初始化）

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

# 4. 三元力学状态 (Phase 3, v2.0 新)
from emotion_spirit.regulation.force_dynamics import ForceDynamics
forces = ForceDynamics().compute(personality, body_state, conscience_pressure)
# 返回 {natural: float, social: float, individual: float, dominant: str}

# 5. ConscienceTracker 压力 (Phase 4 C1, v2.0 新)
from emotion_spirit.regulation.superego import ConscienceTracker
tracker = ConscienceTracker()
pressure = tracker.get_pressure()
# ∈ [0, 1] (P95-normalized over 200-frame sliding window)
```

### 3 个最常用命令

| 命令 | 说明 |
|------|------|
| `/view_status` | 查看系统状态 (含三元力学 + ConscienceTracker B2 输出) |
| `/reflect_drift` | 查看 14 维人格漂移状态 |
| `/reflect_diary` | 手动触发日记写入 |

## 配置 / Configuration

在 AstrBot WebUI 的插件配置中，分为 4 个区域：

### 1. 人格管理模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `persona_mode` | select | `auto` | auto / manual / disabled |
| `auto_source` | select_persona | - | AstrBot 人格 (auto 模式 LLM 自动解析) |
| `manual_personas` | template_list | - | 手动配置列表 (每项 5 轴标签) |

### 2. 功能开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_shadow_detector` | bool | true | 阴影检测 |
| `enable_sentinel` | bool | true | 预警系统 (13 信号) |
| `enable_narrative` | bool | true | 月度叙事弧 |
| `enable_life_simulator` | bool | true | 自主生活模拟 |
| `life_simulator_mode` | select | `both` | both / passive / silent |

### 3. 性能调优

| Env Var | 默认 | 说明 |
|---------|------|------|
| `EMOTION_SPIRIT_PRESSURE_WINDOW` | 200 | ConscienceTracker 滑动窗口大小 (Phase 4 C1, v2.0 新) |

### 4. 高级 / 调试

v1.x 兼容垫片 (`_v1_compat.py`) 在 codebase 内部卫生用, 触发 `DeprecationWarning`. v1.x 旧 import path (`emotion_spirit.public_api` 等 38 mapping) 自动 redirect 到 v2.0 路径 (`emotion_spirit.output.public_api`) 同样触发 `DeprecationWarning`.

## 命令 / Commands

3 个 namespace, 12 个命令 (Phase 4 post-merge ns 化, v1.x 旧 `/spirit_*` 入口已删).

### `setup_*` ns (4 命令) — 人格配置

| 命令 | 说明 | 依赖模块 |
|------|------|----------|
| `/setup_init` | 初始化当前人格参数 (仅 auto 模式) | PersonaAnalyzer (L2) |
| `/setup_relabel` | 重新分析人格 (LLM 重新解析) | PersonaAnalyzer (L2) |
| `/setup_switch <name>` | 切换人格 | PersonaProfile (L1) |
| `/setup_list` | 列出所有人格 | PersonaProfile (L1) |

### `view_*` ns (3 命令) — 状态查看

| 命令 | 说明 | 依赖模块 |
|------|------|----------|
| `/view_status` | 查看系统状态 (含三元力学 + ConscienceTracker B2) | PublicAPI (L3) |
| `/view_detail` | 查看 14 维参数详情 | PersonaProfile (L1) |
| `/view_whoami` | 查看 5 轴人格标签 | PersonaProfile (L1) |

### `reflect_*` ns (5 命令) — 内省

| 命令 | 说明 | 依赖模块 |
|------|------|----------|
| `/reflect_drift` | 查看 14 维人格漂移状态 | PersonalityDrift (L2) |
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
| **Spec** | [docs/superpowers/specs/2026-06-08-phase-4-launch-design.md](docs/superpowers/specs/2026-06-08-phase-4-launch-design.md) | v2.0 设计 spec (12 章节) |
| **Plan** | [docs/superpowers/plans/2026-06-08-phase-4-launch.md](docs/superpowers/plans/2026-06-08-phase-4-launch.md) | v2.0 实施 plan (6 task) |

## v2.0 4 层目录结构 / v2.0 4-Layer Directory Structure

```
emotion_spirit/
├── __init__.py                # 公开 API 入口 + _DeprecatedImportFinder (C3) + PEP 440 version (C2)
├── layer.py                   # 抽象基类 (留根)
├── _version.py                # PEP 440 version 真相源 (2.0.0.post1)
├── _v1_compat.py              # v1.x 兼容垫片 + DeprecationWarning
├── core/                      # L0: 基础 (6 modules)
│   ├── registry.py            # @register_module 装饰器
│   ├── config.py              # 配置常量
│   ├── knowledge.py           # 14 维人格知识库
│   ├── persona_labels_db.py   # 3072 KB loader
│   ├── label_mapper.py        # 标签 → 参数双向映射
│   └── plugin_factory.py      # 插件装配入口
├── memory/                    # L1: 状态 (7 modules)
│   ├── memory_pool.py         # 4 层记忆池
│   ├── intimacy.py            # 6 维亲密度
│   ├── relationship_personality.py  # 关系人格
│   ├── social_graph.py        # 社交图
│   ├── topic_privacy.py       # 话题隐私
│   ├── meaning_reservoir.py   # 意义蓄水池
│   └── persona_profiles.py    # 人格档案
├── regulation/                # L2: 调控 (11 modules)
│   ├── superego.py            # 价值对齐 + ConscienceTracker (Phase 4 C1 B2)
│   ├── superego_guard.py      # 守门人
│   ├── body_state.py          # 身体状态
│   ├── force_dynamics.py      # 三元力学 (Phase 3 算法 H)
│   ├── personality_drift.py   # 14 维漂移
│   ├── shadow_detector.py     # 阴影检测
│   ├── pattern_extractor.py   # 行为模式
│   ├── life_simulator.py      # 生活模拟
│   ├── persona_analyzer.py    # 人格分析器
│   ├── persona_report_parser.py  # 报告解析器
│   └── counterfactual.py      # 反事实模拟
└── output/                    # L3: 输出 (13 modules)
    ├── public_api.py          # 公开 API 入口 (PublicAPI)
    ├── bot_decision.py        # Bot 决策
    ├── emotion_classifier.py  # 情绪分类
    ├── prompt_injector.py     # Prompt 组装
    ├── surface_consumer.py    # Surface 消费
    ├── surface_handler.py     # Surface 处理
    ├── diary_writer.py        # 日记
    ├── command_router.py      # 命令路由
    ├── commands.py            # 命令实现
    ├── narrative_identity.py  # 叙事身份
    ├── predictive_sentinel.py # 预警
    ├── buffer_signals.py      # 缓冲池信号
    └── trend_utils.py         # EMA 工具
```

**依赖方向**: `L0 ← L1 ← L2 ← L3` (严格单向, `test_layer_dependency_no_reverse` enforce)

## v2.0 → v1.x 版本映射 / Versioning

| v2.0 (2026-06) | v1.x (历史) | 变化 |
|----------------|------------|------|
| 38 modules 在 4 sub-packages | 38 modules 平铺 | 重构, 不影响 behavior |
| `ConscienceTracker.get_pressure() ∈ [0, 1]` | 同样 ∈ [0, 1] | **语义改**: P95 归一化, 区分"持续冲突"vs"极端事件" |
| `emotion_spirit.regulation.superego.ConscienceTracker` | `emotion_spirit.superego.ConscienceTracker` | 路径改, v1.x 兼容垫片 redirect |
| `emotion_spirit.output.public_api.PublicAPI` | `emotion_spirit.public_api.PublicAPI` | 路径改, v1.x 兼容垫片 redirect |
| 14 维人格 (11+3+2 拆分) | 11 维 (Phase 1.5) | Phase 3 增 3 维, v1.7 拆 2 维 |

## 许可 / License

MIT — 详见 [LICENSE](LICENSE)

## 引用 / Citations

完整理论依据见 [docs/theory.md](docs/theory.md). 关键 5 篇:

1. Tononi, G. (2004). *An Information Integration Theory of Consciousness*. BMC Neuroscience. (Φ 门控)
2. Bowlby, J. (1969). *Attachment and Loss, Vol. 1: Attachment*. Basic Books. (依恋理论)
3. McCrae, R. R., & Costa, P. T. (1992). *Revised NEO Personality Inventory*. Psychological Assessment Resources. (大五人格)
4. Russell, J. A., & Mehrabian, A. (1977). *Evidence for a three-factor theory of emotions*. Journal of Research in Personality. (PAD 模型)
5. Jung, C. G. (1968). *The Archetypes and the Collective Unconscious*. Princeton University Press. (阴影 / 投射 / 自性)

v2.0 Phase 3 三元力学 (natural / social / individual) 灵感来源:
- 社会生态学 (Bronfenbrenner 1979): 微观 / 中观 / 宏观系统
- 道德基础理论 (Haidt 2007): 多基础道德心理学
- 自我决定理论 (Deci & Ryan 2000): 自主 / 胜任 / 关联
