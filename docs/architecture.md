# emotion_spirit 架构文档

> v1.0.2v3

## 1. 系统定位

emotion_spirit 是 SylannEngine 的下游插件，负责**长期记忆**和**人格演化**。SylannEngine 处理即时情感计算（ms~hr），emotion_spirit 在其之上构建跨时间尺度的状态管理（hr~month）。

```
┌─────────────────────────────────────────────────────┐
│                    AstrBot                           │
│  ┌───────────────┐    ┌──────────────────────────┐  │
│  │ SylannEngine  │───▶│    emotion_spirit         │  │
│  │ (本我/即时)    │    │  (自我+超我/长期)          │  │
│  │ ms ~ hr       │    │  hr ~ month               │  │
│  └───────────────┘    └──────────────────────────┘  │
│         │                       │                    │
│         ▼                       ▼                    │
│    Surface 输出           PromptInjector 注入        │
│    (~80 字段)             (6 sections)               │
└─────────────────────────────────────────────────────┘
```

## 2. 分层架构

### 2.1 Phase 1 — 基础层

负责数据采集、存储和基础状态管理。

| 模块 | 职责 | 可关闭 |
|------|------|--------|
| `SurfaceConsumer` | Surface → SemanticSignals 解析 | ❌ |
| `MemoryPool` | 四层记忆管理（buffer/warm/cold/ghost） | ❌ |
| `IntimacyTracker` | 6 维亲密度追踪 | ❌ |
| `ValueAlignment` | 行为-价值观对齐 | ❌ |
| `ConscienceTracker` | 良心事件记录 | ❌ |
| `IdealSelf` | 理想自我差距计算 | ❌ |

### 2.2 Phase 2 — 演化层

负责模式识别、趋势检测和高级功能。

| 模块 | 职责 | 可关闭 |
|------|------|--------|
| `MeaningReservoir` | 高 Φ 时刻的意义储备 | ❌ |
| `PatternExtractor` | 行为模式提取（循环/趋势/触发/回避） | ❌ |
| `BufferSignals` | 缓冲池衍生信号（6 个） | ❌ |
| `ShadowDetector` | 荣格式阴影检测 | ✅ |
| `LifeSimulator` | Mode A/B 自主生活模拟 | ✅ |
| `DiaryWriter` | 定时日记生成 | ❌ |
| `PersonalityDrift` | 11 维人格漂移检测 | ❌ |
| `PredictiveSentinel` | 13 信号早期预警 | ✅ |
| `NarrativeIdentity` | 月度叙事弧生成 | ✅ |
| `Counterfactual` | 反事实模拟 + 幽灵消化 | ❌ |

### 2.3 输出层

| 模块 | 职责 | 可关闭 |
|------|------|--------|
| `PromptInjector` | 组装 6 sections 注入 LLM | ❌ |

## 3. 依赖关系图

```
SurfaceConsumer
  │
  ├─▶ MemoryPool ─────────▶ PatternExtractor ──▶ ShadowDetector
  │        │                      │                    │
  │        ├─▶ BufferSignals ────┼────                │
  │        │        │            │                    │
  │        │        ├─▶ PredictiveSentinel            │
  │        │        │                                 │
  │        │        ├─▶ DiaryWriter ──────┐           │
  │        │                             │           │
  │        ├─▶ LifeSimulator             │           │
  │        │                             │           │
  │        └─▶ Counterfactual            │           │
  │                                      │           │
  ├─▶ IntimacyTracker ────┐              │           │
  │                       │              │           │
  ├─▶ MeaningReservoir    │              │           │
  │        │              │              │           │
  │        └─▶ PersonalityDrift          │           │
  │                       │              │           │
  ├─▶ ValueAlignment ─────┼─▶ PromptInjector ◀──────┘
  ├─▶ ConscienceTracker ──┘       ▲
  ├─▶ IdealSelf ──────────────────┘
  │
  └─▶ NarrativeIdentity
        (reads: MemoryPool, PatternExtractor,
         PersonalityDrift, BufferSignals, DiaryWriter)
```

**关键依赖链：**
- `MemoryPool` → 8 个下游模块（最核心）
- `BufferSignals` → 5 个下游模块
- `PromptInjector` ← 7 个上游模块（最多输入）

## 4. 数据模型

### 4.1 SemanticSignals

SurfaceConsumer 解析 SylannEngine Surface 后的结构化信号：

```python
@dataclass
class SemanticSignals:
    # 决策信号
    decision_action: str        # express/hold/reflect/...
    decision_confidence: float  # [0, 1]
    decision_reason: str

    # 身体状态
    body_strain: float          # 疲劳度
    body_damage: float          # 损伤度
    body_recovery: float        # 恢复度
    body_integration: float     # 整合度 (衍生)
    body_criticality: float     # 临界度 (衍生)

    # 情感信号
    valence: float              # 效价 [-1, 1]
    arousal: float              # 唤醒度 [0, 1]
    valence_volatility: float   # 效价波动

    # 共振场
    phi_smoothed: float         # Φ (整合信息) 平滑后
    chi_smoothed: float         # χ (共振强度) 平滑后
    resonance_smoothed: float   # 共振度 平滑后

    # 级联
    cascade_active: bool
    cascade_intensity: float

    # Guard
    guard_allowed: bool
    guard_risk_score: float
    guard_decision: str

    # 关系
    relational_duration: float  # 关系持续时间 (秒)
    relational_interval: float  # 距上次互动间隔 (秒)

    # PAD 标签
    pad_label: str              # pleasure/arousal/dominance 综合标签
```

### 4.2 MemoryPool 四层结构

```
Buffer (待确认, Φ 门控)
  │ confirm_check() → phi > threshold?
  ▼
Warm (已确认, 有意义)
  │ consolidation → 模式提取
  ▼
Cold (模式沉淀, 长期)
  │
  ▼
Ghost (永久创伤, 不可遗忘)
```

### 4.3 PersonalityDrift 11 维模型

```
深层 (Embodiment Five):
  expression_drive      表达驱力
  perception_acuity     感知敏锐度
  boundary_permeability 边界通透性
  inner_coherence       内在一致性
  relational_gravity    关系引力

表层 (Sylanne Six):
  warmth_bias           温暖度
  directness            直接性
  curiosity             好奇心
  patience              耐心
  intimacy_pull         亲密拉力
  autonomy_guard        自治守卫
```

## 5. 配置系统

### 5.1 配置层次

```
_conf_schema.json (Schema 定义)
       │
       ▼
AstrBot WebUI (用户编辑)
       │
       ▼
astrbot_plugin_emotion_spirit_config.json (持久化)
       │
       ▼
main.py __init__() (读取并应用)
```

### 5.2 配置区域

| 区域 | 配置项 | 说明 |
|------|--------|------|
| 人格管理 | `persona_mode` | auto / manual / disabled |
| 自动模式 | `auto_source` | LLM 分析的人格来源 |
| 手动模式 | `manual_personas` | template_list 自定义人格 |
| 功能开关 | `feature_toggles.*` | 5 个 bool/select 开关 |

### 5.3 旧配置迁移

插件启动时自动检测旧格式（`auto_read_report` + `default_persona` + `persona_labels`）并迁移到新格式。迁移后旧键被删除，新配置持久化。

## 6. 生命周期

```
插件加载
    │
    ▼
__init__()
    ├── 读取配置
    ├── 迁移旧配置
    ├── 加载手动人格
    ├── 初始化人格模式 (auto/manual/disabled)
    ├── 实例化 Phase 1 组件
    └── 实例化 Phase 2 组件 (根据功能开关)
    │
    ▼
initialize()
    ├── 加载持久化数据
    ├── 延迟连接 SylannEngine (2s)
    ├── LLM 验证 (3s)
    └── 人格分析 (auto 模式, 5s)
    │
    ▼
运行中
    ├── _on_surface(): 消费 Surface，更新所有状态
    ├── on_llm_request(): 注入 PromptInjector 上下文
    └── 定时任务: 日记 (14:00/22:00), 叙事 (月度)
    │
    ▼
插件卸载
    └── _save_all(): 持久化所有数据
```

## 7. 设计原则

1. **单一数据源**: MemoryPool 是唯一的数据存储，所有模块从它读取或写入
2. **事件驱动**: Surface 更新触发所有模块的级联更新
3. **优雅降级**: 禁用的模块设为 None，所有调用点检查后跳过
4. **配置即代码**: 所有数值参数在 `config.py` 中集中管理
5. **持久化透明**: SpiritStore 提供原子写入 + dirty flag 优化

## 8. 已知限制

1. **单会话**: 数据按 `session_id` 隔离，不同会话不共享记忆
2. **无热切换**: 功能开关修改后需重启生效
3. **LLM 依赖**: auto 模式和日记生成依赖 LLM provider
4. **无数据迁移框架**: schema 变更需要手动处理
