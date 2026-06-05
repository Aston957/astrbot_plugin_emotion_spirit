# emotion_spirit v1.3

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

## 版本演进

| 版本 | 日期 | 关键变化 | 测试 |
|------|------|---------|------|
| v1.0.3 | 2026-06-05 | persona 持久化修复 + 2 阶段 relabel | 188/188 |
| v1.0.4 | 2026-06-05 | 死代码清理（v1.0.3 残留） | 188/188 |
| v1.1.1 | 2026-06-05 | 情绪表示升级（概率分布 + 派生） | 214/214 |
| v1.1.2 | 2026-06-05 | DRY 重构（build_emotion_payload 共享层） | 218/218 |
| v1.2 | 2026-06-05 | 情绪动态表示（ambiguity/velocity/trajectory） | 250/250 |
| v1.2+ | 2026-06-05 | VELOCITY_BURST_THRESHOLD + emotion_burst 事件 | 252/252 |
| **v1.3** | 2026-06-05 | **compute_ambiguity 改 1 - max(p)（区分度改善）** | **254/254** |

详见 [CHANGELOG.md](CHANGELOG.md)。

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

### 情绪表示（v1.1+）— 我感受如何

- **概率分布**: 单一字符串 → 7 类情绪概率分布（不损失信息）
- **数据驱动 + 最小必要公开**: LLM 消费者读结构化数据，description 仅供人类
- **隐私边界**: 不暴露 damage/intimacy/conscience 等敏感数据

#### 公开 API：`get_emotion_state()` 返回 11 字段（v1.2）

```python
{
    # PAD 三维
    "pad": {"valence": float, "arousal": float, "dominance": float},
    # 概率分布
    "distribution": dict[str, float],
    "primary": str,                  # 主要情绪
    "secondary": str | None,         # 次要情绪
    "intensity": float,              # 强度（= arousal）
    "description": str,              # 懒渲染中文描述
    "label": str,                    # 向后兼容
    # v1.2 新增：动态信号
    "emotion_ambiguity": float,      # 模糊度 (0=确定, 1=模糊) [v1.3: 1-max(p)]
    "emotion_velocity": dict | None, # 变化率 {valence, arousal, dominance, dt}
}
```

#### 高级 API：`get_emotion_trajectory()` 返回 N=8 帧（v1.2）

```python
[
    {"valence": 0.5, "arousal": 0.6, "dominance": 0.7, "timestamp": 1234.0},
    ...
]
```

**为什么 trajectory 走高级 API？** —— 隐私分层。tts_profile 等不需要时序数据；journal/diary/life_simulator 需要时显式 opt-in。

### 情绪动态（v1.2）— 情绪怎么变

| 字段 | 类型 | 含义 |
|------|------|------|
| `emotion_ambiguity` | float (0-1) | 模糊度（1 - max(p)，v1.3） |
| `emotion_velocity` | dict | 瞬时变化率（每帧差分） |
| `emotion_trajectory` | list | 最近 8 帧时序（环形缓冲） |
| `emotion_burst` | bool (v1.2+) | 突变事件（\|Δvalence\| 或 \|Δarousal\| > 0.05）|

**关键决策**：
- **保持 PAD raw**（不引入 EMA）— 0 破坏性变更，向后兼容 100%
- **5 min 定时写** + dirty flag — 平衡性能与断电恢复
- **trajectory 走高级 API** — 隐私分层

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

## 公开 API（开发者用）

### 情绪状态

```python
# 11 字段（含 v1.2 动态信号）
state = await plugin.get_emotion_state(session_key)

# 高级 API: N=8 帧时序
trajectory = await plugin.get_emotion_trajectory(session_key)
```

### 身体状态

```python
# 4 字段（v1.1.1 重命名自 get_emotion_values）
body = await plugin.get_body_state(session_key)
# 返回 {warmth, pulse, expression, repair}
```

## 目录结构

```
astrbot_plugin_emotion_spirit/
├── main.py                     # AstrBot 插件入口
├── metadata.yaml               # 插件元数据
├── _conf_schema.json           # 配置 Schema
├── README.md                   # 本文件
├── CHANGELOG.md                # 版本更新日志
│
├── docs/                       # 文档
│   ├── architecture.md         # 架构文档（含 v1.1-v1.3 sections）
│   ├── api.md                  # API 文档
│   └── user-guide.md           # 用户手册
│
├── emotion_spirit/             # 核心模块
│   ├── store.py                # JSON 持久化 (v1.2: schema v2, 5 min 定时写)
│   ├── config.py               # 配置常量 (v1.2+: TRAJECTORY_WINDOW, VELOCITY_BURST_THRESHOLD)
│   ├── persona_profiles.py     # 人格映射 (标签 → 参数)
│   ├── persona_analyzer.py     # LLM 人格分析器
│   ├── persona_report_parser.py # 规则解析器 (fallback)
│   ├── label_mapper.py         # 标签→参数双向映射
│   ├── trend_utils.py          # EMA 趋势工具
│   ├── surface_consumer.py     # Surface → SemanticSignals (v1.2: per-session state)
│   ├── emotion_classifier.py   # v1.1: PAD 分类 (v1.3: 1-max(p) ambiguity)
│   ├── memory_pool.py          # 缓冲池 + 温池 + 冷池 + 幽灵
│   ├── buffer_signals.py       # 缓冲池信号计算
│   ├── intimacy.py             # 亲密度追踪
│   ├── superego.py             # 超我反思层 (3 类)
│   ├── meaning_reservoir.py    # 意义蓄水池
│   ├── pattern_extractor.py    # 行为模式提取
│   ├── shadow_detector.py      # 阴影检测
│   ├── life_simulator.py       # Mode A/B 双模式 (v1.1.1: 注入 emotion payload)
│   ├── diary_writer.py         # 定时日记 (v1.1.1: signals 注入)
│   ├── prompt_injector.py      # Prompt 组装 (6 sections)
│   ├── personality_drift.py    # 人格漂移检测
│   ├── predictive_sentinel.py  # 预警系统 (13 信号)
│   ├── narrative_identity.py   # 月度叙事弧
│   └── counterfactual.py       # 反事实模拟
│
└── tests/                      # 测试套件 (254 passed)
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
    │   (v1.2: 内部 per-session _pad_history / _pad_trajectory)
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
    │   (v1.1.1: emotion_classifier.build_emotion_payload 共享层)
    ├── engine.inject(): 良心事件回写热池
    │
    ▼
LLM 生成回复 (带 emotion_spirit 上下文)
```

## 持久化

数据存储在 `data/plugin_data/emotion_spirit/spirit_data.json`，**schema v2**（v1.2 升级）：

| 键 | 说明 | 可关闭 |
|----|------|--------|
| `persona` | v1.0.3 持久化人格 | ❌ |
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
| **`pad_history`** (v1.2) | per-session 最后 1 帧 PAD | ❌ |
| **`pad_trajectory`** (v1.2) | per-session 最近 N=8 帧 | ❌ |

**v1.2 持久化策略**：5 min 定时写 + dirty flag + dirty flag 自动迁移老数据。

## 性能特征（v1.2+）

| 操作 | 耗时 | 备注 |
|------|------|------|
| consume() 总开销 | ~4μs/帧 | 含 ambiguity + velocity + trajectory |
| compute_ambiguity | ~2.5μs | v1.3: O(K) 比较（v1.2 entropy ~5μs） |
| compute_velocity | ~1μs | O(1) 差分 |
| update_trajectory | ~0.5μs | deque.append |
| **100 session 内存** | **~50KB** | trajectory 25.6KB + 持久化副本 |

**总 CPU 占用 < 0.01%**（每帧 4μs @ 100 FPS = 0.04% 单核）。

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
| **PAD 模型** (v1.1) | Russell & Mehrabian (1977), Fontaine et al. (2007) |
| **复合情绪** (v1.1) | RAF-DB (Li 2017) |
| **概率分布** (v1.1) | Juslin & Laukka (2003) arousal = 强度 |
| **情绪时序窗口** (v1.2) | BiERU/Hazarika (2018) 对话历史建模 |
| **Shannon 熵 → 1-max(p)** (v1.3) | 信息论 (Shannon 1948) + 集中度反向 |

## 依赖

- `astrbot` >= 4.9.2
- `sylanne_core` (通过 SylannEngine 插件提供)
- 无额外第三方依赖

## License

MIT
