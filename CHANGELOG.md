# Changelog

所有对 emotion_spirit 项目的显著变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [Unreleased]

## [2.0.0v1] - 2026-06-09

> **里程碑**: Phase 3 闭环 + Phase 4 Launch 收尾 (5 commits + 1 debt cleanup, 591→612 tests, 0 回归)
> **PEP 440**: `2.0.0.post1` (per `emotion_spirit/_version.py`)
> **Branch**: `phase-4-launch` (基于 `30c-task2` @ `823be4f`)

### Added (Phase 4 C1-C5 + C5.5)

#### C1: ConscienceTracker B2 滑动窗口 P95 归一化 (commit 525b191)
- `self._pressure` → `self._raw_pressure` (raw 累加器, 无上限, 累加器是真相源)
- 加 `self._window: deque[float]`, 默认 200 帧 (env var `EMOTION_SPIRIT_PRESSURE_WINDOW` 可调)
- `get_pressure()` 实施 P95 分位归一化, 冷启动 (< 10 帧) 返回 raw (degraded)
- 修 3.0B 偏离 E (conscience_pressure 范围)
- **8 新 tests** (591→599), 0 回归

#### C2: Plugin Packaging (commit 26f3aaa)
- `pyproject.toml`: setuptools >=80, python >=3.11, 0 第三方依赖 (除 astrbot)
- `requirements.txt` + `dev-requirements.txt`
- `metadata.yaml`: version 1.0.2v3 → 2.0.0v1, 新增 repo URL
- 新增 `LICENSE` (MIT) + `emotion_spirit/py.typed` (PEP 561 marker)
- `emotion_spirit/_version.py` (PEP 440 真相源, `__version__ = "2.0.0.post1"`)
- `emotion_spirit/__init__.py` 暴露 `__version__` (Python 惯例)
- `.gitignore` 加 `*.egg-info/` / `build/` / `dist/`
- **3 新 tests** (599→602), 0 回归
- **PEP 440 偏离** (per spec §12.2 C2 偏离 #1): `version = "2.0.0v1"` 字面被 pip 拒绝, 实施 `dynamic = ["version"]` + `attr = "emotion_spirit._version.__version__"` 绕过

#### C3: Public API Markers (commit 27d4daa)
- 38 modules 加 `__all__` (AST-aligned 实际 class/def 名, per spec §12.2 C3 偏离 #2)
- `public_api_stable.md` (中英双栏 stable/internal/deprecated 三表)
- `emotion_spirit/_v1_compat.py` 兼容垫片 (含 `DeprecationWarning`)
- `emotion_spirit/__init__.py` 加 `_DeprecatedImportFinder` hook (C3 阶段 REDIRECTS 空, C4 填)
- `pyproject.toml` `filterwarnings` 配 `ignore::DeprecationWarning:emotion_spirit`
- **6 新 tests** (602→608), 0 回归
- **Module count 偏离** (per spec §12.2 C3 偏离 #1): 39 → 38 (排除 `_version.py` C2 + `_v1_compat.py` C3)

#### C4: 4-Layer Dir Restructure (commit 985bf3f)
- 37 modules `git mv` 到 `emotion_spirit/{core|memory|regulation|output}/` (`store.py` 留根)
- 29 test files `git mv` 到 `tests/{core|memory|regulation|output}/`
- 4 sub-package `__init__.py` 含 `__all__` (L0=6, L1=7, L2=11, L3=13)
- `tools/migrate_v1_imports_to_v2.py` 全局替换 import path (4 categories: from-form + import-form + module-internal `from .X` + string literal)
- `pyproject.toml` `packages` list 扩展到 5
- `_DeprecatedImportFinder.REDIRECTS` 填 37 mapping (C3 留空 → C4 填)
- `emotion_spirit/core/persona_labels_db.py` KB path 修复 (4→5 levels up after migration)
- `.gitignore` 调 `!emotion_spirit/output/`
- **3 新 tests** (608→611), 0 回归
- **依赖方向严格单向**: `L0 ← L1 ← L2 ← L3` (test_layer_dependency_no_reverse enforce)
- **spec 偏离** (per spec §12.2 C4 偏离): 37 modules vs spec 38; 30 test files vs spec 39; migration 4 categories 扩展; AST test 替代 substring; KB path fix

#### C5: Marketing Materials (commit 95b0ddb)
- 厚 `README.md` (283 行中英双段, v2.0 视角重写, 5 mockup 引用, 4 sub-package 路径, 14 维人格, 12 命令表)
- `docs/theory.md` (218 行, 8 章节理论依据, 23 篇参考文献)
- `public_api_stable.md` 完善 (163 行, 7 stable + 12 internal + 37 deprecated redirect mapping + 维护协议)
- `docs/mockups/5 HTML` (chat-transcript-intimacy / chat-transcript-trauma / spirit-status-output / personality-timeline / architecture-diagram)
- 0 新 tests (612 不变, 内容生产)

#### C5.5: Pre-existing Tech Debt Cleanup (commit b0123ab)
- `main.py` 29 处 `from .emotion_spirit.X` 双重 prefix 相对导入 → `from emotion_spirit.X` 绝对导入
- `conftest.py` 删 `_ensure_main_module()` 合成包 hack (`_emotion_spirit_plugin_for_tests`), 简化为 4 行 docstring
- 0 新 tests, 0 回归 (612/612)
- 修复: emotion_spirit 是已 installed package (per C2 packaging), 绝对导入在 production + test 双 work, 无需 hack
- **spec 偏离** (per spec §12.2 C4 偏离 #6): C4 spec review 发现, 推到 C6 前清理, user 2026-06-09 选 "C5 inline 一起修" 提前清理

### Changed

#### v1.x ConscienceTracker 语义变更 (per Phase 4 C1)
- **v1.x**: `ConscienceTracker.get_pressure()` 返回 `min(1.0, max(0.0, raw))` (hard-clip)
- **v2.0**: 返回 `min(1.0, raw / P95(sliding_window))` (滑动窗口 P95 分位归一化)
- **契约保持**: 返回值仍 ∈ [0, 1] (ForceDynamics 消费契约不变)
- **语义变化**: "持续 50 次小冲突" 跟 "持续 1 次大冲突" 现在有差异 (v1.x 完全 clip 后无差异)
- **稳定性**: 跨会话可比, 极端事件不主导归一化

#### v1.x Import Path 自动 Redirect (per Phase 4 C3+C4)
- `emotion_spirit.{module}` → `emotion_spirit.{layer}.{module}` (37 mappings, C4 实施)
- 触发 `DeprecationWarning` (codebase 内部卫生, 不视为用户过渡, v1 无外部用户)
- `_v1_compat.py` 提供 v1 字段 shim (`_conscience_pressure_old` 同样 DeprecationWarning)

#### 4 层目录重构 (per Phase 4 C4)
- 38 modules 从平铺结构迁到 4 sub-packages: `core` (L0 基础) / `memory` (L1 状态) / `regulation` (L2 调控) / `output` (L3 输出)
- 依赖方向严格单向, 跟"基础-状态-调控-输出"4 层 mental model 对应
- `test_layer_dependency_no_reverse` enforce

### Compatibility

- **0 破坏性 API 变更** (PublicAPI 7 stable API 跨 minor 稳定)
- `__version__` 暴露: `python -c "import emotion_spirit; print(emotion_spirit.__version__)"` 返回 `2.0.0.post1`
- `pip install -e .[dev]` 干净 (per C2 pyproject + LICENSE)
- `python -c "import emotion_spirit; from emotion_spirit.regulation.superego import ConscienceTracker; print(ConscienceTracker().get_pressure())"` 正常返回 [0, 1]
- 内部迁移工具: `python tools/migrate_v1_imports_to_v2.py` (一次性, 留在 tools/)
- 旧 import path 仍可导入 (自动 redirect + DeprecationWarning)
- AstrBot 4.9.2+ 兼容 (跟 v1.x 相同)

### Tests
- **总测试数**: 591 (Phase 3 闭环) → **612** (v2.0.0v1) (+21: C1 +8, C2 +3, C3 +6, C4 +3, C5 +0, C5.5 +0)
- **回归**: 0 (all phases)
- **新增覆盖**: 滑动窗口 P95 归一化, modern packaging, `__all__` markers, 4 层依赖方向, 真实 quantile 数学
- **新测试文件**: `tests/regulation/test_conscience_tracker_quantile.py` (C1, 9 tests), `tests/test_packaging.py` (C2, 3 tests), `tests/test_public_api_markers.py` (C3, 6 tests), `tests/test_dir_structure.py` (C4, 3 tests)

### Spec Deviations

- C2 偏离 3 条 (PEP 440 / test 扩展 / packages 暂列 1)
- C3 偏离 5 条 (module count / `__all__` AST-aligned / version test / `_v1_compat` skip / test rearrange)
- C4 偏离 6 条 (37 vs 38 modules / 30 vs 39 tests / migration 4 categories / AST test / KB path fix / pre-existing debt 推迟)
- 3 关闭: 3.0B 偏离 E (conscience_pressure 范围, per C1)

### Phase 4 Launch Commit Chain

| Commit | SHA (first 7) | 描述 |
|--------|--------------|------|
| C1 | `525b191` | feat(conscience_tracker): quantile-normalized pressure |
| C2 | `26f3aaa` | chore(packaging): pyproject.toml + requirements + metadata v2.0 |
| C3 | `27d4daa` | feat(public_api): `__all__` markers + public_api_stable.md + v1 deprecation warnings |
| C4 | `985bf3f` | refactor: 4-layer dir restructure (37 modules relocated) |
| C5 | `95b0ddb` | docs(marketing): 厚 README + 3 受众文档 + 5 mockup + theory.md |
| C5.5 | `b0123ab` | fix(import): replace double-prefix relative imports with absolute (debt cleanup) |
| C6 | `e7b6146` | chore(release): CHANGELOG v2.0.0v1 section |
| post-merge | `e1abf1a` | fix(command-ns): 命令 ns 化 + commands.py v2 path 修复 (v2.0.0v1 patch) |

### Out of Scope (推 Phase 3.5+ 或 v2.1+)
- 3.0B 偏离 D (body_state 跟 personality 分离的 spec 化)
- 3.0B 偏离 F (DriftSimulator Part E 跳过)
- 3.0C 偏离 D (30→30 而非 31)
- 3.0C 偏离 G (D 等级 94.3% 提升)
- 3.0C 偏离 H (M8 spec deviation)
- 力学河流 (multi-timestep ForceState snapshot)
- 内心独白 (multi-force simultaneous voice)
- Steppenwolf 漂移叙事
- GUI 调参 / override baseline 持久化
- **PyPI 发布** (本 spec 仅 AstrBot-native)
- **i18n framework** (中英双段已够)
- **数据持久化路径迁移** (AstrBot handbook §8 推荐 `data/plugin_data/<name>/`, emotion_spirit 继续自管 JSON, 推 Phase 3.5+ 评估)

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
