# v1.2.7 清债 plan(给执行模型)

> **日期**: 2026-07-03
> **前置**: v1.2.6 审计完成(commit `5927b9e`,报告 `docs/v126_audit_report.md`)
> **规约**: handbook 六件套(§1.1-§1.6,每条绑钩子)
> **范围**: 按审计报告 §7 清债清单 + 实现可拦测试
> **执行指南**: 每步 TDD(先写/跑测试)→ 改代码 → 跑测试全绿才下一步。遇到不确定/规约冲突,**停下问**,别擅自决定。

---

## 执行顺序(按依赖)

1. utils/ 层 + 11 工具挪入(后续任务依赖)
2. HP-2 + DO-4 conscience 源统一
3. Q3 删事件机制
4. Q1 编排抽(依赖 1)
5. 8 幽灵接通(依赖 1)
6. HP-4 offset 持久化
7. DO-3 方法内 import
8. DO-5 spec drift 标注
9. collapse_archetype 待核
10. 可拦测试(每步同步,最后补全)

---

## 任务 1: utils/ 层 + 11 工具挪入

**规约**: §1.2 规则 1(纯函数不 @register)+ §1.3(utils/ 层)

**11 工具**(7 无状态误用 + 4 幽灵工具):
- 7 无状态误用: `emotion_classifier`(output/)/ `label_mapper`(core/)/ `persona_profiles`(memory/)/ `trend_utils`(output/)/ `decay_model`(memory/)/ `knowledge`(core/)/ `persona_report_parser`(regulation/)
- 4 幽灵工具: `adaptation`(regulation/)/ `emotion_predictor`(regulation/)/ `energy_model`(regulation/)/ `user_activity_detector`(regulation/)

**步骤**:
1. 建 `emotion_spirit/utils/` 目录 + `__init__.py`(统一导出: `from .emotion_classifier import ...` 等)
2. 逐个挪 11 文件到 `utils/`(git mv 保留历史)
3. 每个文件: 删 `@register` + `_ModuleMarker`/`_AdaptationMarker` 空壳类(纯函数模块不注册)
4. 全仓更新 import 路径: `from emotion_spirit.output.emotion_classifier import X` → `from emotion_spirit.utils import X`(用 `__init__.py` 统一导出)
5. 跑 `pytest tests/` 回归(改 import 后全绿)

**注意**: knowledge 是 KB 类(KnowledgeBase),被多处 import 类方法用。挪 utils/ + 取消 @register 后,确认 force_dynamics 等仍能 import KnowledgeBase 用类方法。

---

## 任务 2: HP-2 + DO-4 conscience 源统一

**规约**: §1.4 类型契约(后续可加 ConsciencePressure 类型)+ §1.2 规则 4(显式传参)

**步骤**:
1. `defense_modulator.py`: `compute_defense_states` 加参数 `conscience_pressure: float = 0.0`(向后兼容默认 0.0)
2. 删 `defense_modulator.py:94` 的 `hasattr(self, "_conscience")` 死分支,改用 `conscience_pressure` 参数
3. `main.py` schedule loop caller(HP-3 suppression 回写处): 传 `conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0`
4. `main.py:399`: `conscience_pressure=getattr(signals, "body_criticality", 0.0)` → `conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0`
5. 跑 `test_suppression*` + `test_life_simulator*` 回归 —— **关键验证**: suppression 值会变(body_criticality → conscience.get_pressure),life_simulator 输出不应退化。若退化,停下报告(可能要调 suppression 公式权重)

---

## 任务 3: Q3 删事件机制

**规约**: §1.6 规则 3(协作走 LLM 整合不用事件)

**步骤**:
1. 删 `emotion_spirit/agents/event_bus.py`(EventBus + AgentEvent + 4 事件类型 BoundaryBreached/ShadowDetected/LifeEventReady/RelationshipChanged)
2. 删 `emotion_spirit/agents/base.py` 的 `emit` 方法 + `_bus` 引用(CognitiveAgent 不再持 bus)
3. 删 4 agent 的 `emit` 调用:
   - `memory_agent.py:74` `self.emit(ShadowDetected(...))` → 删
   - `personality_agent.py:86` `self.emit(BoundaryBreached(...))` → 删
   - `relationship_agent.py:104` `self.emit(RelationshipChanged(...))` → 删
   - `life_agent.py:130` `self.emit(LifeEventReady(...))` → 删
4. 删 4 agent `__init__` 的 `bus` 参数 + `super().__init__(bus)` 调用
5. `main.py:328-330 + 370`: 注册 agent 时删 bus 传参(`MemoryAgent(self._self_core.bus, ...)` → `MemoryAgent(...)`)
6. 跑 `pytest tests/` 回归(agent 主循环应仍运转,composed 仍进 prompt)

**注意**: 删 emit 后,agent 的 act 方法里 emit 调用删除,但 act 的其他逻辑(调组件)保留。确认 agent 主循环(run_cycle perceive→gate→act→compose)不破坏。

---

## 任务 4: Q1 编排抽

**规约**: §1.2 规则 3(薄壳 50 行)+ §1.6 规则 5(输出编排 → @register 组件)

**步骤**:
1. `_extract_bot_emotion`(main.py:1356-1383,28 行关键词匹配)→ 抽到 `utils/tone_extractor.py`(纯函数 `extract_bot_emotion(text) -> (tone, weight)`)
2. `main.py`: `from emotion_spirit.utils import extract_bot_emotion` + 调用
3. `_on_segmented_reply_v2`(main.py:1387-1508,121 行)→ 抽到 `emotion_spirit/output/segmented_reply_orchestrator.py`:
   ```python
   @register(name="segmented_reply_orchestrator", provides=["SegmentedReplyOrchestrator"],
             depends_on=["defense_modulator", "segmented_reply_coordinator", "force_dynamics", "body_state", "intimacy"])
   class SegmentedReplyOrchestrator:
       async def handle(self, event, response, bot_text, user_id, seg_config, ...): ...
   ```
4. `main.py`: `self._segmented_orchestrator = self._modules["segmented_reply_orchestrator"]`(装配)
5. `on_llm_response` 改薄壳: 取 bot_text + 调组件写 memory/intimacy/reflex + `await self._segmented_orchestrator.handle(...)` 委托
6. 验证 `on_llm_response` < 50 行(test_main_py_no_long_orchestration)
7. 跑 `pytest tests/` + on_llm_response 回归

**注意**: SegmentedReplyOrchestrator 依赖 defense_modulator/coordinator/force_dynamics/body_state/intimacy,确认 depends_on 完整 + param_wire 映射。main.py 装配后,原 self._defense_modulator 等引用保留(其他地方可能用)。

---

## 任务 5: 8 幽灵接通

**规约**: §1.2 规则 4(显式 depends_on)+ §1.5(生命周期持久化)

**步骤**:
1. 4 工具(adaptation/emotion_predictor/energy_model/user_activity_detector)已在任务 1 挪 utils/
2. 4 组件保留 @register(已在 regulation/):
   - `environment_context`: 已 @register(确认)
   - `personality_feedback`: @register + 加 `config_keys` (feedback_rate)
   - `project_manager`: @register + 加 `to_dict()/from_dict()`(持久化 _projects,§1.5)
   - `recovery_tracker`: @register + 加 `to_dict()/from_dict()`(持久化恢复进度,§1.5)
3. `life_simulator.py` @register 加 `depends_on=[..., "environment_context", "personality_feedback", "project_manager", "recovery_tracker"]` + param_wire
4. `LifeSimulator.__init__` 加 4 组件参数注入
5. `life_simulator.py` import 3 工具: `from ..utils import compute_social_tendency, predict_mood_trajectory, get_energy_level` 等(adaptation/emotion_predictor/energy_model)
6. LifeSimulator 实现接通逻辑:
   - adaptation: 算社交倾向 + 活动偏好
   - emotion_predictor: 预测情绪轨迹
   - energy_model: 算能量(昼夜)
   - environment_context: 算环境偏置(季节/星期)
   - personality_feedback: 算活动→人格反馈(输出给 compose,LLM 整合,不直接写 personality_drift)
   - project_manager: 追踪多日项目
   - recovery_tracker: 追踪崩溃后恢复
7. `main.py` on_message_receive: 接 `user_activity_detector`(从 utils import,检测用户文本活动 → 写 memory 或传 LifeSimulator)
8. `main.py` _persist_modules: 加 `project_manager` + `recovery_tracker` 持久化(`self._store.set("project_manager", self._project_manager.to_dict())` 等)
9. `main.py` _load_state: 加恢复
10. 跑 `pytest tests/` + 新测试(接通逻辑)

**注意**: 接通逻辑是 v1.2.7 最大工作量。参考 v1.1.0C 设计文档(adaptation docstring 写"used by LifeSimulatorV2 T3 + activity engine T4-T9")。若接通逻辑复杂,可分步: 先接 4 组件(depends_on + 注入 + 简单调用),再接 3 工具(import + 调用),最后完善逻辑。

---

## 任务 6: HP-4 offset 持久化

**规约**: §1.5 生命周期

**步骤**:
1. `force_dynamics.py`: 加 `restore_offset(offset: dict)` 方法(get_cumulative_offset 已有)
2. `main.py` _persist_modules(1668 附近): 加 `self._store.set("force_dynamics_offset", self._force_dynamics.get_cumulative_offset())`
3. `main.py` _load_state(_store.load 后): 加 `fd_offset = self._store.get("force_dynamics_offset", None); if fd_offset: self._force_dynamics.restore_offset(fd_offset)`
4. 跑 `test_force_dynamics*` + 加 round-trip 测试(shift → get → restore → get 一致)

---

## 任务 7: DO-3 方法内 import

**规约**: 琐碎风格(PEP 8)

**步骤**:
1. `defense_modulator.py:139` `from ..core.persona_labels_db import get_defense_deltas` 移到文件顶部 import 区
2. 删 `apply_event` 内的 import
3. 跑测试

---

## 任务 8: DO-5 spec drift 标注

**规约**: 文档(防未来 session 读 spec 被误导)

**步骤**:
1. `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` 头加"实现 drift 注记(v1.2.6 回扫)"段
2. 列 drift:
   - `config_keys={"segmented_reply"}` → 无(无所谓)
   - `self._conscience.pressure` → hasattr fallback(❌ 更差,HP-2/DO-4 修)
   - `force_dynamics.apply_defense_delta` 硬编码 → DefenseModulator.apply_event + KB(✅ 更好)
   - `silence_components: dict = None` → field(default_factory=dict)(✅ 更好)
   - 三子 L2 全接 → 实际只接 silence(Q3 删事件 + v1.2.8 L2 脚手架)
3. 标"spec 反映设计意图,实现以代码为准; drift 已在 v1.2.6/v1.2.7 收敛"

---

## 任务 9: collapse_archetype 待核

**步骤**:
1. `grep -n "from .collapse_archetype import\|from ..regulation.collapse_archetype import" emotion_spirit/`
2. 若 collapse_archetype_selector import 它(定义 Archetype enum): collapse_archetype 保留(被 selector 用,非幽灵)
3. 若无人 import: collapse_archetype 是幽灵(删 or 评估接通)
4. 记结论

---

## 任务 10: 可拦测试(每步同步,最后补全)

**规约**: 六件套每条绑钩子

**测试清单**:
- `tests/test_kb_centralization.py`(§1.1): AST 扫 .py,单 dict/list 字面量 > 10 项 → CI 红
- `tests/test_registry_liveness.py`(§1.2): @register 装饰目标有状态(AST)+ 每个 @register 被自我 _modules 取 + 扫隐式 import new
- `tests/test_main_py_no_long_orchestration.py`(§1.2 规则 3): main.py 单方法 > 50 行 → CI 红(已有 test_main_py_no_manual_new,补充)
- `tests/test_layer_dependencies.py`(§1.3): AST 扫 import,core 不依赖业务层
- `tests/test_type_contracts.py`(§1.4): 扫跨子系统参数裸 float + 易错配(初期可只标 conscience_pressure 类)
- `tests/test_lifecycle_pairs.py`(§1.5): 有状态 @register 模块必须有 to_dict/from_dict 配对 + reset 一致性
- `tests/test_agent_no_impl.py`(§1.6 规则 1): AST 扫 agent 方法体无算法实现
- `tests/test_no_event_bus.py`(§1.6 规则 3): agents/ 内无 EventBus/AgentEvent/emit/subscribe
- `tests/test_agent_no_direct_call.py`(§1.6 规则 2): agent 不互相 import/调

**实现**: 每个任务完成后,同步写对应可拦测试。最后跑全套 `pytest tests/` 全绿。

---

## DoD

- [ ] `pytest tests/` 全绿(1348 + 新测试,允许 Win 概率性 test_periodic_save_dirty_only flake)
- [ ] utils/ 层建立,11 工具集中(取消 @register)
- [ ] 8 幽灵接通(7 LifeSimulatorV2 + 1 main.py)
- [ ] Q3 事件机制删除(agent 主循环仍运转)
- [ ] Q1 main.py 薄壳(单方法 < 50 行)
- [ ] HP-2/HP-4/DO-3/DO-4 清完
- [ ] collapse_archetype 核实
- [ ] 9 个可拦测试实现 + 全绿
- [ ] module count 调整后确认(删事件不算模块,接通 4 组件已算)
- [ ] handbook §6 更新"v1.2.7 已清的债"
- [ ] `docs/CHANGELOG.md` v1.2.7 entry

---

## 风险

| # | 风险 | 处置 |
|---|---|---|
| R1 | 挪 11 工具改 import 路径多,回归 | 每挪一个跑测试,小步推进 |
| R2 | 删事件机制改 agents/ 多文件 | 先删 event_bus + emit,跑测试确认主循环不破坏,再删 bus 参数 |
| R3 | LifeSimulatorV2 接 7 幽灵(接通逻辑复杂) | 分步:先 depends_on + 注入(空调用),再逐个接通逻辑 |
| R4 | DO-4 conscience 源变更,suppression 值变,life_simulator 退化 | 跑 life_simulator 回归,若退化停下报告(调公式权重) |
| R5 | SegmentedReplyOrchestrator 抽出后,on_llm_response 时序变 | 跑 on_llm_response 回归(分段 send + 沉默 + 清 llm_resp) |
| R6 | test_type_contracts 初期难写(类型契约刚引入) | 先写 conscience_pressure 一个样本,后续扩展 |

---

## 相关

- `docs/v126_audit_report.md` — v1.2.6 审计报告(本 plan 依据)
- `UPDATE_HANDBOOK.md` — 六件套规约(§1.1-§1.6)
- `docs/superpowers/plans/2026-07-03-v126-l2-scaffolding-plan.md` — 原 L2 脚手架 plan(deferred v1.2.8+)
