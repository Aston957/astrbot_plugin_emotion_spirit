# emotion_spirit Public API (v1.2.3)

> **稳定 API** = 跨 minor 版本保证不破坏。v1.0 引入的 API 在 v1.x 全程稳定。
> **Internal API** = 可能在任意 minor 版本变更。仅 codebase 内部使用。
>
> **版本**: v1.2.3 (PEP 440, per `emotion_spirit/_version.py`)
> **维护**: 每次 minor 版本更新需同步检查, 新 stable API 需经过 1 个 minor 版本 deprecation 周期

## Stable (公共契约)

跨 minor 版本 (v1.0 → v1.1 → v1.x) 保证不破坏。变更需 major 版本。

### 情绪与身体状态

| 中文 | English | 入口 | 引入版本 |
|------|---------|------|----------|
| 获取情绪状态 | Get emotion state | `PublicAPI.get_emotion_state(session_key)` | v1.0 |
| 获取身体状态 | Get body state | `PublicAPI.get_body_state(session_key)` | v1.0 |
| 情绪轨迹 | Emotion trajectory | `PublicAPI.get_emotion_state(session_key, include_trajectory=True)` | v1.7.2 |

### 模块注册 (AstrBot 插件装配)

| 中文 | English | 入口 | 引入版本 |
|------|---------|------|----------|
| 注册模块 | Register module | `@register_module("name")` | v1.0 |

### 三元力学

| 中文 | English | 入口 | 引入版本 |
|------|---------|------|----------|
| 力学状态 | Force state | `ForceDynamics().compute(personality, body_state, conscience_pressure)` | v1.0 |
| 人格 baseline | Persona baseline | `persona_labels_db.get_baseline(persona_id)` | v1.0 |

### ConscienceTracker

| 中文 | English | 入口 | 引入版本 |
|------|---------|------|----------|
| ConscienceTracker 压力 | ConscienceTracker pressure | `ConscienceTracker.get_pressure()` | v1.0 |
| ConscienceTracker 原始压力 | ConscienceTracker raw pressure | `ConscienceTracker._raw_pressure` (read-only 诊断用) | v1.0 |
| 压力窗口配置 | Window size | env var `EMOTION_SPIRIT_PRESSURE_WINDOW` (默认 200) | v1.0 |

**语义说明**:
- `get_pressure()` 返回 `min(1.0, raw / P95(sliding_window))` (滑动窗口 P95 分位归一化)
- **契约**: 返回值 ∈ [0, 1] (ForceDynamics 消费契约)
- **语义**: "持续 50 次小冲突" 跟 "持续 1 次大冲突" 有差异

### 其他 Stable API

| 中文 | English | 入口 | 引入版本 |
|------|---------|------|----------|
| 兼容垫片 | compat shim | `from emotion_spirit import _v1_compat` | v1.0 |
| import redirect | import redirect | 自动 (via `_DeprecatedImportFinder`) | v1.0 |

## Internal (codebase 内部用)

可能在任意 minor 版本变更。仅 codebase 内部使用, 不保证跨 minor 稳定。

### 力学内部 API

| 中文 | English | 入口 | 备注 |
|------|---------|------|------|
| 直接读 raw pressure | Read raw pressure | `tracker._raw_pressure` | 内部诊断用, 跟 `_raw_pressure` 等同 |
| 27-sum fallback | 27-sum fallback | `compute_baseline_from_labels(labels, fallback=True)` | Phase 3.0A 27-sum 算法 fallback |

### 仿真内部 API

| 中文 | English | 入口 | 备注 |
|------|---------|------|------|
| DriftSimulator | DriftSimulator | `life_simulator.DriftSimulator` | Phase 1.5 仿真器, 推 v2.1 public |
| CounterfactualSimulator | CounterfactualSimulator | `counterfactual.CounterfactualSimulator` | Phase 2.5 推 v2.1 public |
| PersonaAnalyzer | PersonaAnalyzer | `persona_analyzer.PersonaAnalyzer` | LLM 调用, 推 v2.1 public |
| PatternExtractor | PatternExtractor | `pattern_extractor.PatternExtractor` | 行为模式提取 |

### 装饰器内部

| 中文 | English | 入口 | 备注 |
|------|---------|------|------|
| register_superego_signals | register_superego_signals | `superego.register_superego_signals` | module-level signal registration |
| register_surface_consumer | register_surface_consumer | `surface_consumer.register_surface_consumer` | module-level signal registration |
| register_surface_handler | register_surface_handler | `surface_handler.register_surface_handler` | module-level signal registration |
| register_body_state | register_body_state | `body_state.register_body_state` | module-level signal registration |
| register_command | register_command | `commands.register_command` | module-level signal registration |

### 存储 / 工具内部

| 中文 | English | 入口 | 备注 |
|------|---------|------|------|
| JSON store | JSON store | `store.load / store.save` | 内部持久化, 推 v2.1 external API |
| TrendUtils | TrendUtils | `trend_utils.TrendUtils` | EMA 工具, 内部用 |
| BufferSignals | BufferSignals | `buffer_signals.BufferSignals` | 缓冲池信号, 内部用 |

## Deprecated (v1.x, 内部卫生用)

v1.x API, codebase 内部 deprecation. 触发 `DeprecationWarning`. 将随 v2.1 删除 (届时所有 v1 调用点都应已迁移). v1.x 用户过渡: 不需要 (v1 无外部用户, spec §1.3).

### API 字段重命名

| 中文 | English | 替代 | 移除版本 |
|------|---------|------|----------|
| `_pressure` 字段 | `_pressure` field | `_raw_pressure` (raw 真相) | v2.1 |
| `pad_label` 单字段 | `pad_label` field | `pad_primary` (alias 仍兼容) | v2.1 |

### Import Path 重命名 (C3 `_DeprecatedImportFinder` 自动 redirect)

`emotion_spirit.{module}` → `emotion_spirit.{layer}.{module}` (C4 后生效, 自动 redirect + DeprecationWarning)

| Deprecated import | Current path |
|------------------------|-----------|
| `emotion_spirit.registry` | `emotion_spirit.core.registry` |
| `emotion_spirit.config` | `emotion_spirit.core.config` |
| `emotion_spirit.knowledge` | `emotion_spirit.core.knowledge` |
| `emotion_spirit.persona_labels_db` | `emotion_spirit.core.persona_labels_db` |
| `emotion_spirit.label_mapper` | `emotion_spirit.core.label_mapper` |
| `emotion_spirit.plugin_factory` | `emotion_spirit.core.plugin_factory` |
| `emotion_spirit.persona_profiles` | `emotion_spirit.memory.persona_profiles` |
| `emotion_spirit.memory_pool` | `emotion_spirit.memory.memory_pool` |
| `emotion_spirit.intimacy` | `emotion_spirit.memory.intimacy` |
| `emotion_spirit.relationship_personality` | `emotion_spirit.memory.relationship_personality` |
| `emotion_spirit.social_graph` | `emotion_spirit.memory.social_graph` |
| `emotion_spirit.topic_privacy` | `emotion_spirit.memory.topic_privacy` |
| `emotion_spirit.meaning_reservoir` | `emotion_spirit.memory.meaning_reservoir` |
| `emotion_spirit.superego` | `emotion_spirit.regulation.superego` |
| `emotion_spirit.superego_guard` | `emotion_spirit.regulation.superego_guard` |
| `emotion_spirit.body_state` | `emotion_spirit.regulation.body_state` |
| `emotion_spirit.force_dynamics` | `emotion_spirit.regulation.force_dynamics` |
| `emotion_spirit.personality_drift` | `emotion_spirit.regulation.personality_drift` |
| `emotion_spirit.shadow_detector` | `emotion_spirit.regulation.shadow_detector` |
| `emotion_spirit.pattern_extractor` | `emotion_spirit.regulation.pattern_extractor` |
| `emotion_spirit.life_simulator` | `emotion_spirit.regulation.life_simulator` |
| `emotion_spirit.persona_analyzer` | `emotion_spirit.regulation.persona_analyzer` |
| `emotion_spirit.persona_report_parser` | `emotion_spirit.regulation.persona_report_parser` |
| `emotion_spirit.counterfactual` | `emotion_spirit.regulation.counterfactual` |
| `emotion_spirit.bot_decision` | `emotion_spirit.output.bot_decision` |
| `emotion_spirit.emotion_classifier` | `emotion_spirit.output.emotion_classifier` |
| `emotion_spirit.prompt_injector` | `emotion_spirit.output.prompt_injector` |
| `emotion_spirit.surface_consumer` | `emotion_spirit.output.surface_consumer` |
| `emotion_spirit.surface_handler` | `emotion_spirit.output.surface_handler` |
| `emotion_spirit.diary_writer` | `emotion_spirit.output.diary_writer` |
| `emotion_spirit.command_router` | `emotion_spirit.output.command_router` |
| `emotion_spirit.commands` | `emotion_spirit.output.commands` |
| `emotion_spirit.narrative_identity` | `emotion_spirit.output.narrative_identity` |
| `emotion_spirit.predictive_sentinel` | `emotion_spirit.output.predictive_sentinel` |
| `emotion_spirit.public_api` | `emotion_spirit.output.public_api` |
| `emotion_spirit.buffer_signals` | `emotion_spirit.output.buffer_signals` |
| `emotion_spirit.trend_utils` | `emotion_spirit.output.trend_utils` |

## 历史与版本

| 版本 | 日期 | 状态 | 备注 |
|------|------|------|------|
| **v1.0.0** | **2026-06-24** | **✅ Released** | 首个正式版本, 109 modules, 886 tests |

## 维护协议

- **每次 minor 版本 (v1.x)**: 同步检查本表, 新 stable API 加 1 个 minor 版本 deprecation 周期
- **每次 major 版本 (v2.0)**: deprecated API 删除, internal API 重新审视
- **Patch 版本 (v1.0.x)**: 不变更本表
- **变更需走 PR**: 修改本表视为 API 变更, 需 maintainer 2 人 review
