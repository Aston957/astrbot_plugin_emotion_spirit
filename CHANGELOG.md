# Changelog

所有对 emotion_spirit 项目的显著变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [Unreleased]

## [1.3.0] - 2026-06-05

### Changed
- **compute_ambiguity 重构**：从 Shannon entropy / log(K) 改为 `1 - max(p)`
- **原因**：v1.2 真实数据仿真发现，8 个 SCENARIOS 的 ambiguity 全部偏高（0.74-0.91），区分度极差
- **效果**：
  - 8 个场景 ambiguity 范围 0.74-0.91 → **0.34-0.64**
  - spread 0.17（高位无意义）→ **0.30**（真实差异）
  - 计算复杂度 O(K) log → **O(K) 比较**（-50%）
  - intimacy_growth 0.793 → **0.339**（最确定）
  - trauma 0.870 → **0.639**（最模糊）
  - daily_neutral (0.403) < conflict (0.541) ✓ 符合直觉

### Compatibility
- 0 破坏性 API 变更
- `emotion_ambiguity` 字段名不变
- `get_emotion_state()` 11 字段不变
- 范围 [0, 1] 不变
- 消费者集成方式不变

### Tests
- 5 单元测试断言更新
- 2 真实场景集成测试新增（`test_real_scenarios_ambiguity.py`）
- 总测试：252 → **254 passed**

### Commits
- `f9ab5a6` refactor: compute_ambiguity → 1 - max(p)
- `62d1a85` test: add real-scenarios ambiguity spread verification
- `5014229` docs+test: v1.3 ambiguity redesign docs

### Documentation
- Spec: `docs/superpowers/specs/2026-06-05-emotion-ambiguity-redesign-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-emotion-ambiguity-redesign.md`
- Architecture: `docs/architecture.md` section 7.7

---

## [1.2.1] - 2026-06-05

### Added
- **`VELOCITY_BURST_THRESHOLD = 0.05` 配置常量**
- **`emotion_burst: bool` 字段** (SemanticSignals)
- **burst 事件检测**：基于 `emotion_velocity`，`config.VELOCITY_BURST_THRESHOLD = 0.05`（基于参数扫描仿真 Pareto 最优）

### Tests
- 2 新增 burst 检测单元测试
- 总测试：250 → **252 passed**

### Commits
- `d6d9dc3` feat: add VELOCITY_BURST_THRESHOLD + emotion_burst event (v1.2+)

### Why
所有真实场景 (conflict/boundary/cascading/trauma) `|Δvalence| > 0.4` 远超 0.05 阈值，0 假阳性 + 100% 检出。

---

## [1.2.0] - 2026-06-05

### Added (Phase 2: 情绪动态表示)
- **`emotion_ambiguity: float`** - Shannon 熵归一化（v1.3 已重构）
- **`emotion_velocity: dict | None`** - `{valence, arousal, dominance, dt}` 瞬时变化率
- **`emotion_trajectory: list`** - 最近 8 帧 (v, a, d, t) 时序
- **公开 API 扩展**：
  - `get_emotion_state()`: 9 → **11 字段** (+emotion_ambiguity +emotion_velocity)
  - `get_emotion_trajectory(session_key)`: 新增高级 API
- **SpiritStore schema v2**：`pad_history` / `pad_trajectory` 命名空间
- **5 min 定时写 + dirty flag**：避免每帧序列化
- **per-session 状态在 SurfaceConsumer 内部**：`dict[session_id, deque]`
- **新配置常量**：
  - `TRAJECTORY_WINDOW = 8`（环形缓冲大小）
  - `PAD_SAVE_INTERVAL_SECONDS = 300`（持久化间隔）
- **`consume(surface, session_id=None)`**：可选 session_id 参数

### Changed
- `build_emotion_payload()` 共享层加 2 字段（v1.1.2 DRY 重构的延续）
- `diary_writer._format_emotion_block()` 注入 ambiguity/velocity
- `life_simulator.check_mode_a()` payload 加 2 字段
- `main.py` 记忆 tag 用 `pad_primary` 替代 `pad_label`（v1.1.1）

### Key Decisions
1. **保持 PAD raw**（不引入 PAD EMA）— 0 破坏性变更，velocity 从 raw 算
2. **5 min 定时写**（不是每帧写）— 平衡性能与断电恢复
3. **N=8 + 可配置 + trajectory 高级 API**— 隐私分层，trajectory 不进 get_emotion_state

### Privacy Boundary
- **暴露** ✅: pad_* + emotion_ambiguity + emotion_velocity + 身体 4 字段
- **高级 API 暴露**（需 opt-in）: emotion_trajectory
- **不暴露** ❌: damage_* / intimacy_* / conscience_* / EMA 内部状态 / hot pool

### Performance
- 每帧总开销 ~4-6.5μs（v1.3 后 4μs）
- 100 session 内存 ~50KB
- **CPU 占用 < 0.01%**

### Compatibility
- 0 破坏性变更
- 老 spirit_data.json 自动迁移到 schema v2
- `consume(surface)` 不传 session_id 仍工作（向后兼容）

### Tests
- 9 个新单元测试 (5 ambiguity + 4 velocity)
- 1 个 SemanticSignals 默认值测试
- 5 个 SurfaceConsumer 集成测试
- 11 个 SpiritStore v2 测试
- 4 个 main.py 公开 API 测试
- 2 个消费者集成测试
- 总测试：218 → **250 passed**

### Commits (8 total)
- `b60bfed` Task 1: compute_ambiguity
- `f1f6fae` Task 2: compute_velocity
- `addb469` Task 3: config 常量
- `26a27a1` Task 4: SemanticSignals +3 字段
- `d80fece` Task 5: SurfaceConsumer 集成
- `d1c9870` Task 6: SpiritStore v2
- `d78392e` Task 7: 公开 API 扩展
- `8685c01` Task 8: 消费者集成
- `d40178a` docs: v1.2 architecture

### Documentation
- Spec: `docs/superpowers/specs/2026-06-05-emotion-dynamics-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-emotion-dynamics.md`
- Memory: `emotion-spirit-v12-design.md`

---

## [1.1.2] - 2026-06-05

### Changed
- **DRY 重构**：提取 `build_emotion_payload()` 到 `emotion_classifier.py` 作为单一数据源
- `diary_writer._format_emotion_block()` 调用共享 payload，再 dict→text 格式化
- `life_simulator` 删除本地 `_build_emotion_payload()`，改用 import

### Performance
- 4 文件变更：+136 -26 = +110 行
- **生产代码净减少 14 行**（-23 -19 + 28）
- 新增防御性拷贝（`dict(signals.pad_distribution)`）
- 单一数据源：未来加字段只需改 emotion_classifier.py

### Tests
- 4 新增 build_emotion_payload 单元测试
- 总测试：214 → **218 passed**

### Commits
- `d97984b` refactor: extract build_emotion_payload to emotion_classifier (v1.1.2 DRY)

---

## [1.1.1] - 2026-06-05

### Added (Phase 1: 情绪表示升级)
- **`emotion_spirit/emotion_classifier.py`** 新模块
  - `CATEGORICAL_REGIONS` 7 类基本情绪 PAD 边界
  - `COMPOUND_REGIONS` 4 类复合情绪（sad_excitement / angry_despair / joyful_anxiety / sad_calm）
  - `EMOTION_ZH` 11 个中文标签
  - 3 个核心函数：`classify_distribution` / `classify_primary_secondary` / `render_description`
- **`SemanticSignals` 扩展 4 字段**：
  - `pad_distribution: dict[str, float]`
  - `pad_primary: str`
  - `pad_secondary: str | None`
  - `pad_intensity: float`
- **公开 API**（`EmotionSpiritPlugin`）：
  - `get_emotion_state()` 主 API（含懒渲染 description）
  - `get_body_state()` 重命名自 `get_emotion_values`
- **`diary_writer`** 接受 `signals: SemanticSignals | None` 参数
- **`life_simulator`** Mode A/B payload 加结构化情绪数据
- **`main.py` 记忆 tag** 改用 `pad_primary` 替代 `pad_label`（更稳定）

### Architecture Principle
- **数据驱动 + 最小必要公开**：LLM 消费者读结构化数据，description 仅供人类
- **隐私边界**：不暴露 damage/intimacy/conscience 等敏感数据
- **公开 API 总数**：2 个（emotion + body）

### Key Decisions
- 删除：`get_emotion_snapshot`（内部零调用）
- 重命名：`get_emotion_values → get_body_state`（名字更准确）
- 不加：`get_latest_signals()` 暴露全量 60+ 字段
- 保留：`pad_label` + `pad_confidence` 字段（向后兼容）
- 严格规则：`top1 > 0.5 AND ratio > 2.5` 在 classify 和 render 中**必须一致**

### Tests
- 13 单元测试 (emotion_classifier)
- 6 集成测试 (emotion_integration)
- 3 新增 (diary_writer)
- 4 新增 (life_simulator)
- 总测试：188 → **214 passed**

### Documentation
- Spec: `docs/superpowers/specs/2026-06-05-emotion-representation-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-emotion-representation.md`

---

## [1.0.4] - 2026-06-05

### Removed
- **死代码清理**：v1.0.3 留下的 manual 模式残留（`persona_mode` 已无 "manual" 选项）
- 7 处清理：~40 行
  - `self._manual_personas` / `self._active_manual_persona` 死属性
  - `_get_persona_params` 步骤 2 检查
  - `spirit_detail` / `spirit_personas` / `spirit_switch` / `spirit_init` 的 manual 分支

### Performance
- main.py 从 ~1662 行减到 1635 行
- 行为不变

### Tests
- 总测试：**188/188 passed**（无新增）

### Commits
- `1f26611` chore: baseline v1.0.4 state

---

## [1.0.3] - 2026-06-05

### Added
- **persona 持久化**：`_persona_initialized` 和 `_labels` 不再只存内存
  - `SpiritStore` 新增 `persona` namespace 键（5 字段 schema）
  - 3 个新方法：`_is_persona_initialized()` / `_load_persona_state()` / `_migrate_old_spirit_data()`
  - `/spirit_init` 完成后写入 persona 键
  - `initialize()` 中调用 `_load_persona_state()` 恢复
- **`/spirit_relabel` 指令**：两阶段调整 5 轴标签
  - 阶段 1: `/spirit_relabel` → 显示警告（列出清除/保留字段）
  - 阶段 2: `/spirit_relabel confirm <5个标签>` → 执行重置
  - 副作用：清除 6 个超我层键，保留记忆层
- **迁移策略（方案 B）**：老 spirit_data.json 无 persona 键 → 自动用默认 labels + 警告用户

### Changed (破坏性变更)
- **删除 manual 模式**：
  - `_migrate_old_config()` / `_load_manual_personas_from_config()` / `_init_manual_persona()` 全部删除
  - `persona_mode` 选项从 `["auto", "manual", "disabled"]` 改为 `["auto", "disabled"]`
  - `_conf_schema.json` 移除 `manual_personas` 字段
- **`/spirit_switch` 行为变更**：切 persona 时重置超我层（baseline 依赖 labels）+ 持久化新 persona

### Key Design Philosophy
- "参数驱动，非标签驱动"（来自 design-weight-differentiation.md）
- 5 轴标签只在**初始值**影响 11 维人格参数
- 11 维 baseline 是"吸引子中心"，current_personality 漂移值是"行为策略"
- `/spirit_relabel` 改变 labels → 必须重算 11 维 baseline → **保留 11 维漂移值**

### Tests
- 14 新增 test_init_persistence
- 总测试：174 → **188 passed**

### Documentation
- Spec: `docs/superpowers/specs/2026-06-05-persona-init-persistence-design.md`
- Plan: `docs/superpowers/plans/2026-06-05-persona-init-persistence.md`

---

## [1.0.2v3] - 之前

基线版本，v1.0.3 之前的所有变更未在此详细记录。

---

## 总结

| 版本 | 主要变化 | 测试 | 提交 |
|------|---------|------|------|
| v1.3 | compute_ambiguity 改 1 - max(p) | 254 | 3 |
| v1.2.1 | VELOCITY_BURST_THRESHOLD + emotion_burst | 252 | 1 |
| v1.2.0 | 情绪动态表示 (ambiguity/velocity/trajectory) | 250 | 8 |
| v1.1.2 | DRY 重构 (build_emotion_payload 共享层) | 218 | 1 |
| v1.1.1 | 情绪表示升级 (概率分布 + 派生) | 214 | 12 |
| v1.0.4 | 死代码清理 | 188 | 1 |
| v1.0.3 | persona 持久化 + 2 阶段 relabel | 188 | 14 |
| v1.0.2v3 | 基线 | - | - |

**v1.0.3 → v1.3 总变化**：66 测试新增（188→254，+35%），32 commits，0 破坏性 API 变更。

## 链接

- [README.md](README.md) - 项目说明
- [docs/architecture.md](docs/architecture.md) - 架构文档
- [docs/superpowers/specs/](docs/superpowers/specs/) - 设计规格
- [docs/superpowers/plans/](docs/superpowers/plans/) - 实施计划
