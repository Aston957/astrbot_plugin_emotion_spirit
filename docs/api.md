# emotion_spirit API 文档

> v1.2.4 (2026-06-30)

## 1. AstrBot 命令接口

### 1.1 `/view_status`

查看 emotion_spirit 系统状态。

**输出格式：**
```
📊 emotion_spirit 状态
人格模式: auto
当前人格: 小芙
SylannEngine: 已连接
缓冲池: 3 条
温池: 12 条
冷池: 5 条
幽灵: 0 条
关系: 亲近 (亲密度: 0.72)
价值对齐: 0.85
良心压力: 0.12
意义蓄水: 0.45
功能: 阴影:ON / 预警:ON / 叙事:ON / 生活:both
```

**依赖：** 无

---

### 1.2 `/view_whoami`

查看当前人格的 5 轴标签。

**输出格式：**
```
🧠 人格标签 (auto 模式)
来源: LLM 分析 (置信度: 0.85)
MBTI: ENFP
依恋: 焦虑型
情绪策略: 表达型
冲突风格: 顺应型
时间取向: 活在当下
```

**依赖：** 无

---

### 1.3 `/view_detail [名称]`

查看人格的 13 维参数详情。

**参数：**
- `名称` (可选): 人格名称。不填则显示当前人格。

**输出格式：**
```
📐 人格参数详情: 小芙

深层 (Embodiment Five):
  expression_drive:      0.75
  perception_acuity:     0.85
  boundary_permeability: 0.90
  inner_coherence:       0.75
  relational_gravity:    0.35

表层 (Sylanne Six):
  warmth_bias:    0.90
  directness:     0.75
  curiosity:      0.75
  patience:       0.75
  intimacy_pull:  0.80
  autonomy_guard: 0.35
```

**依赖：** 无

---

### 1.4 `/view_whoamis`

列出所有可用人格。

**输出格式：**
```
👥 可用人格:
  ★ 小芙 (auto, ENFP)
    小天 (manual, INTP)
    默认 (manual, ISTJ)
```

**依赖：** 无

---

### 1.5 `/setup_switch <名称>`

切换当前活跃人格。

**参数：**
- `名称`: 目标人格名称。

**输出格式：**
```
✅ 已切换到: 小天 (INTP/回避型/压抑型/攻击型/活在过去)
```

**依赖：** 无

---

### 1.6 `/reflect_drift`

查看人格漂移状态。

**输出格式：**
```
📈 人格漂移状态
整合度斜率: 0.0012
意义蓄水: 0.45

漂移检测:
  expression_drive: ↑ 0.003
  warmth_bias: ↓ 0.001
```

**依赖：** `PersonalityDrift`（如果关闭则返回提示）

---

### 1.7 `/reflect_sentinel`

查看预警状态。

**输出格式：**
```
🚨 预警状态: normal
触发信号: 0

  ✅ 所有信号正常
```

或：

```
🚨 预警状态: warning
触发信号: 3
  ⚠️ body_strain_trend
  ⚠️ buffer_temperature
  ⚠️ echo_persistence
```

**依赖：** `PredictiveSentinel`（如果关闭则返回提示）

---

### 1.8 `/reflect_shadows`

查看阴影检测结果。

**输出格式：**
```
🌑 检测到 2 个阴影:
  [echo] 敏感话题 (置信度: 0.82)
    你一直在重复提到但从未确认的记忆
  [avoidance] 冲突 (置信度: 0.65)
    你系统性回避的记忆类型
```

或：

```
🌑 未检测到阴影
```

**依赖：** `ShadowDetector`（如果关闭则返回提示）

---

### 1.9 `/reflect_diary`

手动生成日记。

**输出格式：**
```
📝 日记类型: ascending

请以小芙的身份写一篇日记，回顾最近的经历。
最近的记忆: [最近 3 条温池记忆]
当前模式: [行为模式摘要]
良心压力: 0.12
```

**依赖：** `DiaryWriter`

---

### 1.10 `/reflect_patterns`

查看行为模式。

**输出格式：**
```
📋 检测到 3 个模式:
  [cycle] express → hold → express → hold (频率: 4)
  [trend] express ↑ (最近 7 天)
  [trigger] 当 valence < -0.3 时, hold 概率 0.8
```

**依赖：** `PatternExtractor`

---

## 2. 模块 API

### 2.1 MemoryPool

```python
class MemoryPool:
    # 属性
    buffer: list[BufferEntry]    # 待确认缓冲区
    warm: list[MemoryEntry]      # 已确认温池
    cold: list[MemoryEntry]      # 模式沉淀冷池
    ghosts: list[MemoryEntry]    # 永久创伤

    # 方法
    def update_phi(self, phi: float) -> None
    def add(self, text, raw_weight, phi, tags, source_user) -> None
    def confirm_check(self) -> list[BufferEntry]
    def recall(self, query: str, k: int = 5) -> list[MemoryEntry]
    def sample_for_mode_a(self, minutes: int = 5) -> list[MemoryEntry]
    def sample_for_mode_b(self, k: int = 3) -> list[MemoryEntry]
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None
```

### 2.2 SurfaceConsumer

```python
class SurfaceConsumer:
    def consume(self, surface: dict) -> SemanticSignals
```

### 2.3 IntimacyTracker

```python
class IntimacyTracker:
    def update(self, user_id, temporal_hours, interval_seconds) -> None
    def get_intimacy(self, user_id: str, persona: str) -> float
    def get_lifecycle(self, user_id: str) -> str
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None
```

### 2.4 Superego (3 classes)

```python
class ValueAlignment:
    def record(self, action: str) -> None
    def get_score(self) -> float
    def get_trend(self) -> str
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None

class ConscienceTracker:
    def record_guard_rejected(self, risk_score, reason) -> None
    def record_cascade(self, intensity) -> None
    def record_collapse(self, count) -> None
    def get_pressure(self) -> float
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None

class IdealSelf:
    def compute_gap(self, current_personality: dict) -> float
    def get_direction(self, current_personality: dict) -> dict[str, float]
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None
```

### 2.5 ShadowDetector

```python
class ShadowDetector:
    def detect(self) -> list[dict]
    # 返回: [{"tag": str, "evidence": str, "confidence": float, "suggestion": str}]
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None
```

### 2.6 PredictiveSentinel

```python
class PredictiveSentinel:
    def update(self, signals: SemanticSignals) -> None
    def check(self) -> dict
    # 返回: {"level": str, "triggered_count": int, "triggered_signals": list[str]}
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None
```

### 2.7 PersonalityDrift

```python
class PersonalityDrift:
    def update(self, signals: SemanticSignals) -> None
    def get_drift_status(self) -> dict
    def check_drift(self) -> list[dict]
    def to_dict(self) -> dict
    def from_dict(self, data: dict) -> None
```

### 2.8 PromptInjector

```python
class PromptInjector:
    def build_context(self, user_id, persona, current_personality=None) -> str
    # 返回: 组装好的注入文本，包含 [印象] [日记] [关系] [超我] [阴影] [理想] sections
```

### 2.9 PersonaAnalyzer

```python
class PersonaAnalyzer:
    def __init__(self, llm_callable) -> None
    async def analyze(self, persona_text: str) -> PersonaAnalysisResult

class PersonaAnalysisResult:
    persona_id: str
    labels: dict[str, str]           # 5 轴标签
    personality: dict                # 13 维参数
    confidence: float
    source: str                      # "llm" | "rule"

def save_report(data_dir: Path, result: PersonaAnalysisResult) -> None
def load_report(data_dir: Path) -> PersonaAnalysisResult | None
```

### 2.10 label_mapper

```python
LABEL_OPTIONS: dict[str, list[str]]
# mbti: 16 types, attachment: 4 types, emotion_style: 3 types,
# conflict_style: 4 types, time_focus: 3 types

def labels_to_personality(labels: dict[str, str]) -> dict[str, dict[str, float]]
# 输入: 5 轴标签
# 输出: {"deep": {5 dims}, "surface": {6 dims}}

def personality_to_labels(personality: dict) -> dict[str, str]
# 输入: 13 维参数
# 输出: 最接近的 5 轴标签
```

---

## 3. 数据持久化格式

### 3.1 spirit_data.json

```json
{
  "memory_pool": {
    "buffer": [...],
    "warm": [...],
    "cold": [...],
    "ghosts": [...]
  },
  "intimacy": {
    "users": {
      "user_id": {
        "persona_id": {
          "temporal_depth": 0.5,
          "interaction_freq": 0.3,
          ...
        }
      }
    }
  },
  "alignment": {"score": 0.85, "history": [...]},
  "conscience": {"pressure": 0.12, "events": [...]},
  "reservoir": {"level": 0.45},
  "patterns": {"patterns": [...]},
  "buffer_signals": {"momentum": {...}, ...},
  "shadow": {"shadows": [...]},
  "life_sim": {"last_mode_b": 0.0, ...},
  "diary": {"entries": [...]},
  "drift": {"trends": {...}},
  "sentinel": {"level": "normal", ...},
  "narrative": {"arcs": [...]},
  "counterfactual": {"ghosts": [...]}
}
```

### 3.2 persona_report.json

```json
{
  "persona_id": "小芙",
  "labels": {
    "mbti": "ENFP",
    "attachment": "焦虑型",
    "emotion_style": "表达型",
    "conflict_style": "顺应型",
    "time_focus": "活在当下"
  },
  "personality": {
    "deep": {
      "expression_drive": 0.75,
      "perception_acuity": 0.85,
      "boundary_permeability": 0.90,
      "inner_coherence": 0.75,
      "relational_gravity": 0.35
    },
    "surface": {
      "warmth_bias": 0.90,
      "directness": 0.75,
      "curiosity": 0.75,
      "patience": 0.75,
      "intimacy_pull": 0.80,
      "autonomy_guard": 0.35
    }
  },
  "confidence": 0.85,
  "analyzed_at": "2026-06-02T21:30:00",
  "source": "llm"
}
```
