# v1.2.5 PR3 T3+T4 评估报告 (2026-07-03)

## AST 扫描结果 (17 个手 new, 不是 plan 估的 12)

| Line | Pattern | 评估分类 |
|---|---|---|
| 107 | `self._public_api = PublicAPI(self._modules)` | **A. ✅ 已注册, 可改** |
| 115 | `self._cmd = CommandImpl(self)` | **C. ❌ self 注入, 需扩 factory** |
| 119 | `self._surface_handler = SurfaceHandler(self)` | **C. ❌ self 注入, 需扩 factory** |
| 369 | `self._life_agent = LifeAgent(self._self_core.bus, self._life_sim_v2)` | **C. ❌ self 注入 (`self_core.bus`), 需扩 factory** |
| 783-786 | `self._alignment/_value_resistance/_ideal/_superego_guard = ...` (initialize) | **T2 扩展: 同样双轨 bug, 需修** |
| 1595 | `self._patterns = PatternExtractor(self._pool)` | **A. ✅ 已注册, 可改** |
| 1598 | `self._buffer_signals = BufferSignals(...)` | **A. ✅ 已注册, 可改** |
| 1602 | `self._shadow = ShadowDetector(self._pool, self._patterns, self._buffer_signals)` | **A. ✅ 已注册, 可改** |
| 1606 | `self._life_sim = LifeSimulator(self._pool, ...)` | **A. ✅ 已注册, 可改** |
| 1617 | `self._drift = PersonalityDrift(self._pool)` | **A. ✅ 已注册, 可改** |
| 1621 | `self._sentinel = PredictiveSentinel(self._consumer, self._pool, ...)` | **A. ✅ 已注册, 可改** |
| 1625 | `self._narrative = NarrativeIdentity(self._pool, self._diary, ...)` | **A. ✅ 已注册, 可改** |
| 1628 | `self._counterfactual = Counterfactual(self._pool, ...)` | **A. ✅ 已注册, 可改** |
| 1632 | `self._injector = PromptInjector(self._pool, ...)` | **A. ✅ 已注册, 可改** (prompt_injector.py 实际是 @register) |

> 注: my 初版 audit 报告 PromptInjector/ShadowDetector/LifeSimulator/PredictiveSentinel/NarrativeIdentity "无 @register" 是 bug — 它们用 snake_case 名字, 我 grep 时 case 敏感出错. 实际全 ✅ 已注册.

## 处理分类

### A. 已 @register, 改 self._modules[...] 即可 (9 个, PR3 Task 4+5 修)

| Class | @register 名字 | main.py 当前 | 改后 |
|---|---|---|---|
| PublicAPI | `public_api` | `PublicAPI(self._modules)` | `self._modules["public_api"]` |
| PatternExtractor | `pattern_extractor` | `PatternExtractor(self._pool)` | `self._modules["pattern_extractor"]` |
| BufferSignals | `buffer_signals` | `BufferSignals(...)` | `self._modules["buffer_signals"]` |
| ShadowDetector | `shadow_detector` | `ShadowDetector(self._pool, self._patterns, self._buffer_signals)` | `self._modules["shadow_detector"]` |
| LifeSimulator | `life_simulator` | `LifeSimulator(self._pool, ...)` | `self._modules["life_simulator"]` |
| PersonalityDrift | `personality_drift` | `PersonalityDrift(self._pool)` | `self._modules["personality_drift"]` |
| PredictiveSentinel | `predictive_sentinel` | `PredictiveSentinel(self._consumer, self._pool, ...)` | `self._modules["predictive_sentinel"]` |
| NarrativeIdentity | `narrative_identity` | `NarrativeIdentity(self._pool, self._diary, ...)` | `self._modules["narrative_identity"]` |
| Counterfactual | `counterfactual` | `Counterfactual(self._pool, ...)` | `self._modules["counterfactual"]` |
| PromptInjector | `prompt_injector` | `PromptInjector(self._pool, ...)` | `self._modules["prompt_injector"]` |

注: PublicAPI 算 Task 4 (1 个 facade), 其他 9 个算 Task 5 (T4). 共 10 个改.

### B. 未 @register, 需标 @register (0 个)

所有 17 个都已 @register. ✅

### C. 参数有 self 注入, 需扩展 factory (3 个, 留 v1.3)

| Class | 注入需求 | 备注 |
|---|---|---|
| CommandImpl | `self` (整个 plugin) | 4 个 @register 候选, current-truth 已列 |
| SurfaceHandler | `self` (整个 plugin) | 同上 |
| LifeAgent | `self._self_core.bus` (属性提取) | current-truth 已列, 需 factory `param_wire` 扩 `dep.attr` |

### T2 扩展: initialize() 也双轨 (PR3 顺手修)

main.py:783-786 (`initialize()` 方法) 跟 `_reset_superego_modules` 同模式手 new 4 个 superego sub.
后果: `initialize()` 重跑后 `self._conscience/_alignment/...` 跟 `_modules["superego"]` 不一致.
修法: PR3 T2 扩 — 抽 `_rebuild_superego_subdict()` helper, `_reset_superego_modules` 和 `initialize()` 都调.

## 范围决策

### PR3 必做 (3 类)
1. **T2 扩展**: initialize() 双轨消 (顺手修, 不留技术债)
2. **T3 (1 个)**: PublicAPI 改 self._modules
3. **T4 (9 个)**: PatternExtractor + BufferSignals + ShadowDetector + LifeSimulator + PersonalityDrift + PredictiveSentinel + NarrativeIdentity + Counterfactual + PromptInjector

### v1.3 留 (3 个 C 类)
- CommandImpl / SurfaceHandler / LifeAgent: 需 factory `param_wire` 扩 self 注入 / 属性提取, 是 v1.3 工作

### v1.2.6 backlog
- T5 CognitiveAgent 3 个 dead code (不在 main.py 17 列表里, 是 agents/ 内的, 不在本评估范围)
- T6 SurfaceHandler @register 一致性 (实际已 register, T6 待重新评估)
