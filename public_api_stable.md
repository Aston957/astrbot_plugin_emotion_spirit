# emotion_spirit Public API (v2.0.0v1)

> 稳定 API = 跨 minor 版本保证不破坏。v2.0 引入的 API 在 v2.x 全程稳定。
> Internal API = 可能在任意 minor 版本变更。仅 codebase 内部使用。
> Deprecated = v1.x API, codebase 内部 deprecation, 不视为用户过渡。

## Stable (公共契约)

| 中文 | English | 入口 | 引入版本 |
|------|---------|------|----------|
| 获取情绪状态 | Get emotion state | `PublicAPI.get_emotion_state(session_key)` | v1.0 |
| 获取身体状态 | Get body state | `PublicAPI.get_body_state(session_key)` | v1.0 |
| 情绪轨迹 | Emotion trajectory | `PublicAPI.get_emotion_state(session_key, include_trajectory=True)` | v1.7.2 |
| 注册模块 | Register module | `@register_module("name")` | v1.0 |
| 力学状态 | Force state | `ForceDynamics().compute(personality, body_state, conscience_pressure)` | v3.0 |
| 人格 baseline | Persona baseline | `persona_labels_db.get_baseline(persona_id)` | v3.0 |
| ConscienceTracker 压力 | ConscienceTracker pressure | `ConscienceTracker.get_pressure()` | v1.0 (语义 v2.0 改) |

## Internal (codebase 内部用)

| 中文 | English | 入口 |
|------|---------|------|
| 直接读 raw pressure | Read raw pressure | `tracker._raw_pressure` |
| 27-sum fallback | 27-sum fallback | `compute_baseline_from_labels(labels, fallback=True)` |
| DriftSimulator | DriftSimulator | `life_simulator.DriftSimulator` |

## Deprecated (v1.x, 内部卫生用)

| 中文 | English | 替代 | 移除版本 |
|------|---------|------|----------|
| `_pressure` 字段 | `_pressure` field | `_raw_pressure` (raw 真相) | v2.1 |
| `emotion_spirit.public_api` import | `emotion_spirit.public_api` import | `emotion_spirit.output.public_api` | v2.1 |
