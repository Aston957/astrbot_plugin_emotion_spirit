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
    pad_label: str              # pleasure/arousal/dominance 综合标签 (向后兼容)
    pad_confidence: float       # pad_label 置信度 (向后兼容)

    # v1.1.1: 结构化情绪数据 (LLM 消费者读这些字段)
    pad_valence: float          # 效价 [-1, 1]
    pad_arousal: float          # 唤醒度 [0, 1]
    pad_dominance: float        # 支配度 [0, 1]
    pad_distribution: dict      # 7 类基本情绪概率分布 (e.g. {"joy": 0.6, "neutral": 0.3})
    pad_primary: str            # 主要情绪 (e.g. "joy")
    pad_secondary: str | None   # 次要情绪 (e.g. "excitement" or None)
    pad_intensity: float        # 强度 (即 pad_arousal, 派生冗余字段便于直接读)
```

**v1.1.1 情绪数据流**：

```
SylannEngine Surface
  ↓ (raw pad + 60+ signals)
SurfaceConsumer.consume()
  ├── EMA 平滑
  ├── compute_pad()
  ├── emotion_classifier.classify_distribution()  ← 新增
  ├── emotion_classifier.classify_primary_secondary()  ← 新增
  └── 填充 pad_* 4 个新字段
  ↓
SemanticSignals (完整结构化数据)
  ↓
3 个 LLM 消费者:
  - get_emotion_state() 公开 API (9 字段，懒渲染 description)
  - diary_writer.build_diary_prompt() (注入结构化块)
  - life_simulator Mode A/B payload (注入 emotion 块)
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

## 7.5 v1.1.1 情绪表示升级 (2026-06-05)

emotion_spirit 从"单一字符串 pad_label"升级为"概率分布 + 派生数据"。

### 核心变化

- `SemanticSignals` 扩展 4 个字段：`pad_distribution` / `pad_primary` / `pad_secondary` / `pad_intensity`
- 新增 `emotion_spirit/emotion_classifier.py` 模块：
  - `CATEGORICAL_REGIONS` (7 类基本情绪 PAD 区域)
  - `COMPOUND_REGIONS` (4 类复合情绪: sad_excitement/angry_despair/joyful_anxiety/sad_calm)
  - `classify_distribution(pad)` → 概率分布
  - `classify_primary_secondary(distribution, pad)` → (primary, secondary)
  - `render_description(distribution, intensity)` → 中文描述（仅人类辅助层）
- 公开 API: 新增 `get_emotion_state()` (9 字段) + `get_body_state()` (4 字段)
- 删除: 未实现的 `get_emotion_snapshot()` (v1.1 决定)
- 重命名: `get_emotion_values → get_body_state` (v1.1.1)
- 不加: `get_latest_signals()` 暴露全量 60+ 字段 (v1.1.1 决定，隐私边界)

### 架构原则

- **数据驱动**: LLM 直接读 `signals.pad_distribution` (结构化数据，零信息损失)
- **description 是辅助层**: 仅人类查看 (WebUI, `/spirit_status`)，每次 `get_emotion_state()` 懒渲染
- **最小必要公开**: 公开 9+4=13 字段，不暴露 damage/intimacy/conscience 等隐私数据
- **5 形态分布**: single_dominant / mixed / blended / calm_baseline / multi_color

### 严格规则

`top1 > 0.5 AND ratio > 2.5` (用于 single_dominant 判断) 在 `classify_primary_secondary` 和 `render_description` 中**必须一致**，避免 description 跳脱于数据。

### 影响的消费者

| 消费者 | 改动 |
|--------|------|
| `diary_writer.build_diary_prompt()` | 接受 `signals: SemanticSignals \| None`，注入结构化数据块 |
| `diary_writer.build_superego_reflection_prompt()` | 接受 `signals: SemanticSignals \| None` |
| `life_simulator.check_mode_a()` payload | signals 块新增 `pad` / `emotion_distribution` / `emotion_primary` / `emotion_secondary` / `emotion_intensity` |
| `life_simulator.check_mode_b()` payload (life_event/reflection/soliloquy) | 新增 `emotion` 块（统一从 `_build_emotion_payload()` 生成） |
| `main.py` 记忆 tag | `signals.pad_label` → `signals.pad_primary` (更稳定) |
| `main.py` get_emotion_state() API | 9 字段 dict 返回 |

### 详细设计

- Spec: `docs/superpowers/specs/2026-06-05-emotion-representation-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-emotion-representation.md`

## 8. 已知限制

1. **单会话**: 数据按 `session_id` 隔离，不同会话不共享记忆
2. **无热切换**: 功能开关修改后需重启生效
3. **LLM 依赖**: auto 模式和日记生成依赖 LLM provider
4. **无数据迁移框架**: schema 变更需要手动处理
