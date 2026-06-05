# emotion_spirit v1.0.2v3

> SylannEngine 之上的长期记忆、人格演化与超我调控层

## 这是什么

emotion_spirit 是 [SylannEngine](https://github.com/Ayleovelle/SylannEngine) 的下游插件。SylannEngine 负责即时情感计算（本我），emotion_spirit 在其之上构建长期记忆、人格演化和自我反思（自我 + 超我）。

```
弗洛伊德          实现                时间尺度
──────────────────────────────────────────
本我 (Id)         SylannEngine        ms ~ hr
自我 (Ego)        emotion_spirit      hr ~ month
超我 (Superego)   分布在两个插件之间    贯穿
```

## 核心能力

### 记忆层 — 我记得什么

- **缓冲池 + Φ 门控**: 每条消息先进缓冲池，SylannEngine 的 Φ（整合信息）决定是否值得记住
- **四层记忆**: 缓冲池（待确认）→ 温池（已确认）→ 冷池（模式沉淀）→ 幽灵（永久创伤）
- **6 维亲密度**: 不对称的亲密度追踪，不同人格对同一用户的亲密度不同
- **Ebbinghaus 遗忘**: 记忆自然衰减，被召回时强化

### 演化层 — 我变成了谁

- **人格漂移检测**: 追踪 SylannEngine 11 维人格的长期趋势（双 EMA）
- **预测性预警**: 13 个信号（7 body + 3 缓冲池 + 3 级联）监测系统健康
- **月度叙事弧**: 每月扫描记忆，生成上升/下降/停滞/循环型叙事
- **反事实模拟**: 为无法消化的创伤提供替代视角
- **阴影检测**: 荣格式阴影识别（回声模式、回避模式、确认偏差）

### 调控层 — 我应该成为谁

- **价值对齐**: 追踪行为是否符合人格的价值观
- **良心事件**: 从 guard 拒绝和级联事件生成内疚信号
- **理想自我**: 当前人格与理想人格的差距计算

### 人格管理 — 我是谁

- **三模式管理**: auto（LLM 自动解析）/ manual（手动配置）/ disabled（默认值）
- **5 轴标签**: MBTI × 依恋风格 × 情绪策略 × 冲突风格 × 时间取向
- **11 维参数**: 5 深层（Embodiment Five）+ 6 表层（Sylanne Six）
- **LLM 分析**: 自动从 AstrBot 人格报告提取标签，生成参数

## 安装

### 前置条件

- AstrBot v4.9.2+
- SylannEngine v1.0.0rc1+ 插件

### 安装步骤

1. 将 `astrbot_plugin_emotion_spirit` 目录复制到 AstrBot 的 `data/plugins/` 目录
2. 重启 AstrBot
3. 插件会自动连接 SylannEngine（延迟 2 秒，等待 SylannEngine 初始化）

## 配置

在 AstrBot WebUI 的插件配置中，分为三个区域：

### 1. 人格管理模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `persona_mode` | select | `auto` | auto: LLM 自动解析; manual: 手动配置; disabled: 默认值 |

### 2. 自动模式配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `auto_source` | select_persona | 选择 AstrBot 人格，插件自动通过 LLM 解析 5 轴标签 |

### 3. 手动模式配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `manual_personas` | template_list | 自定义人格列表，每个可选 5 轴标签 |

### 4. 功能开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_shadow_detector` | bool | true | 阴影检测 |
| `enable_sentinel` | bool | true | 预警系统 |
| `enable_narrative` | bool | true | 叙事身份 |
| `enable_life_simulator` | bool | true | 自主生活模拟 |
| `life_simulator_mode` | select | `both` | both/passive/silent |

## 指令

| 指令 | 说明 | 依赖模块 |
|------|------|----------|
| `/spirit_status` | 查看系统状态 | 无 |
| `/spirit_persona` | 查看 5 轴人格标签 | 无 |
| `/spirit_detail` | 查看 11 维参数详情 | 无 |
| `/spirit_personas` | 列出所有人格 | 无 |
| `/spirit_switch <名称>` | 切换人格 | 无 |
| `/spirit_drift` | 查看人格漂移状态 | PersonalityDrift |
| `/spirit_sentinel` | 查看预警状态 | PredictiveSentinel |
| `/spirit_shadows` | 查看阴影检测 | ShadowDetector |
| `/spirit_diary` | 手动触发日记 | DiaryWriter |
| `/spirit_patterns` | 查看行为模式 | PatternExtractor |

## 目录结构

```
astrbot_plugin_emotion_spirit/
├── main.py                     # AstrBot 插件入口
├── metadata.yaml               # 插件元数据 (v1.0.2v3)
├── _conf_schema.json           # 配置 Schema
├── README.md                   # 本文件
│
├── docs/                       # 文档
│   ├── architecture.md         # 架构文档
│   ├── api.md                  # API 文档
│   └── user-guide.md           # 用户手册
│
├── emotion_spirit/             # 核心模块
│   ├── store.py                # JSON 持久化 (dirty flag)
│   ├── config.py               # 配置常量
│   ├── persona_profiles.py     # 人格映射 (标签 → 参数)
│   ├── persona_analyzer.py     # LLM 人格分析器
│   ├── persona_report_parser.py # 规则解析器 (fallback)
│   ├── label_mapper.py         # 标签→参数双向映射
│   ├── trend_utils.py          # EMA 趋势工具
│   ├── surface_consumer.py     # Surface → SemanticSignals
│   ├── memory_pool.py          # 缓冲池 + 温池 + 冷池 + 幽灵
│   ├── buffer_signals.py       # 缓冲池信号计算
│   ├── intimacy.py             # 亲密度追踪
│   ├── superego.py             # 超我反思层 (3 类)
│   ├── meaning_reservoir.py    # 意义蓄水池
│   ├── pattern_extractor.py    # 行为模式提取
│   ├── shadow_detector.py      # 阴影检测
│   ├── life_simulator.py       # Mode A/B 双模式
│   ├── diary_writer.py         # 定时日记
│   ├── prompt_injector.py      # Prompt 组装 (6 sections)
│   ├── personality_drift.py    # 人格漂移检测
│   ├── predictive_sentinel.py  # 预警系统 (13 信号)
│   ├── narrative_identity.py   # 月度叙事弧
│   └── counterfactual.py       # 反事实模拟
│
└── tests/                      # 测试套件 (19 个文件)
```

## 数据流

```
用户消息
    │
    ▼
SylannEngine process() → Surface (~80 字段)
    │
    ▼
emotion_spirit _on_surface() 回调
    │
    ├── surface_consumer: 解析 → SemanticSignals
    ├── memory_pool: Φ 门控 → 缓冲池 → 确认 → 温池
    ├── intimacy: 更新亲密度
    ├── superego: 更新价值对齐 / 良心事件
    ├── reservoir: 积累意义
    ├── drift: 更新人格趋势
    ├── sentinel: 更新预警信号 (如果启用)
    ├── shadow: 检测阴影 (如果启用)
    ├── life_sim: 自主生活模拟 (如果启用)
    │
    ▼
on_llm_request() 注入
    │
    ├── prompt_injector: 印象 + 日记 + 关系 + 超我 + 阴影 + 理想
    ├── engine.inject(): 良心事件回写热池
    │
    ▼
LLM 生成回复 (带 emotion_spirit 上下文)
```

## 持久化

数据存储在 `data/plugin_data/emotion_spirit/spirit_data.json`，包含：

| 键 | 说明 | 可关闭 |
|----|------|--------|
| `memory_pool` | 缓冲池 + 温池 + 冷池 + 幽灵 | ❌ |
| `intimacy` | 所有用户的亲密度 | ❌ |
| `alignment` | 价值对齐历史 | ❌ |
| `conscience` | 良心事件 | ❌ |
| `reservoir` | 意义蓄水池 | ❌ |
| `patterns` | 行为模式 | ❌ |
| `buffer_signals` | 缓冲池信号历史 | ❌ |
| `shadow` | 阴影检测结果 | ✅ |
| `life_sim` | Life Sim 状态 | ✅ |
| `diary` | 日记条目 | ❌ |
| `drift` | 人格漂移历史 | ❌ |
| `sentinel` | 预警历史 | ✅ |
| `narrative` | 叙事弧 | ✅ |
| `counterfactual` | 反事实模拟历史 | ❌ |

## 理论依据

| 机制 | 来源 |
|------|------|
| Φ 意义门控 | Tononi (2004), SylannEngine 论文 §6.8 |
| Ebbinghaus 遗忘 | MemoryBank (AAAI 2024) |
| 人格漂移 Dual-EMA | LD-Agent (NAACL 2025) |
| 关系生命周期 | Jańczak (2023) Earned Secure AAF |
| 情绪双稳态 | PNAS (2014) |
| 共振场信号 | SylannEngine v2 论文 §6.4, §6.8, §6.9 |
| 阴影/投射/自性 | Jung 分析心理学 |
| 依恋理论 | Bowlby (1969), Ainsworth (1978) |
| 大五人格 | McCrae & Costa (1992) |

## 依赖

- `astrbot` >= 4.9.2
- `sylanne_core` (通过 SylannEngine 插件提供)
- 无额外第三方依赖

## License

MIT
