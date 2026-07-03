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

**进度**: 步骤 1-2 ✅ 已完成(`utils/tone_extractor.py` 已建, main.py:1305 已调 `extract_bot_emotion`, `tests/test_tone_extractor.py` 已建)。剩余步骤 3-7 抽 SegmentedReplyOrchestrator。

**步骤**:
1. ✅ `_extract_bot_emotion` → `utils/tone_extractor.py`(纯函数 `extract_bot_emotion(text) -> (tone, weight)`)
2. ✅ `main.py`: `from emotion_spirit.utils import extract_bot_emotion` + 调用
3. `_on_segmented_reply_v2`(main.py:1358-1480, ~123 行)→ 抽到 `emotion_spirit/output/segmented_reply_orchestrator.py`:
   ```python
   @register(name="segmented_reply_orchestrator", provides=["SegmentedReplyOrchestrator"],
             depends_on=["defense_modulator", "segmented_reply_coordinator", "force_dynamics", "body_state", "intimacy"])
   class SegmentedReplyOrchestrator:
       async def handle(self, event, response, bot_text, user_id, seg_config,
                        signals, context, personality, labels, force_state): ...
   ```

### 4.A 状态归属表(关键 — 决定薄壳能否成立)

`_on_segmented_reply_v2` 读 6 类状态。抽组件后必须分清「组件 depends_on 自取」vs「main 薄壳取了传参」, 否则参数爆炸或违反 §1.3 分层(output/ 不能反向调 main 私有方法):

| 状态 | 归属 | 理由 |
|---|---|---|
| `force_state` | **main 传参** | `get_current_force_state`(main.py:978) 是 main 私有方法, 依赖 `self._labels`。force_dynamics 虽 @register, 但 `force_state_from_labels` 需 labels 快照 → labels 走参数, force_state 由 main 算好传 |
| `signals` | **main 传参** | `self._latest_signals.get(user_id)` 运行时快照, 非 @register |
| `body_state` | **depends_on 自取** | @register 模块, 组件内 `self._body_state.default()` |
| `intimacy` | **depends_on 自取** | @register 模块(需 user_id + persona 参数, 但模块本身注入) |
| `context` | **main 传参** | `_build_context`(main.py:1482) 是 main 私有方法(8 行)。处置见 4.B: 下沉 utils 纯函数 |
| `personality` | **main 传参** | `_get_current_personality_dict`(main.py:962) 是 main 私有方法 |

`handle` 签名 10 参: `event, response, bot_text, user_id, seg_config, signals, context, personality, labels, force_state` — 全是「运行时上下文/当次快照」, 无 @register 模块混入(depends_on 5 个自取), 薄壳 on_llm_response 只负责「取这些 + 调 handle」, 不实现编排。

### 4.B main.py 私有方法处置(三个被编排逻辑用的私有方法)

- `get_current_force_state`(978): **保留 main**(依赖 self._labels + self._force_dynamics), main 算好 force_state 传参
- `_build_context`(1482, 8 行 social_audience/authority_present): **下沉 `utils/context_builder.py`** 纯函数 `build_context(event) -> dict`, main + orchestrator 都从 utils import(避免 output/ 反向依赖 main)
- `_get_current_personality_dict`(962): **保留 main**, main 取了传参(personality 是 per-user/per-persona 快照, 不该组件持有)

### 4.C 死分支处置(§5 anti-pattern)

`_on_segmented_reply_v2:1386-1390` 有:
```python
personality = (
    self._get_personality_for_user(user_id)
    if hasattr(self, "_get_personality_for_user")
    else self._get_current_personality_dict()
)
```
`_get_personality_for_user` **main.py 全文无定义**(grep 确认), hasattr 永远 False — 死分支(同 HP-2 conscience 死代码病, §5 明令禁止 hasattr 掩盖未注入依赖)。抽组件时**删 hasattr, 直接用 `self._get_current_personality_dict()`**, main 传 personality 参数。

### 4.D event/response 副作用契约

orchestrator.handle 内合法直接副作用(运行时对象, 非 @register 依赖, 由 main 薄壳传入):
- `await event.send(MessageChain([Plain(...)]))` — 分段发送
- `response.completion_text = ""` + `response.result_chain = None` — 清空(Bug 12b)

§1.6 规则 3「薄壳」不禁止组件对传入对象副作用, 只禁止 main 自己实现编排逻辑。

4. `main.py`: `self._segmented_orchestrator = self._modules["segmented_reply_orchestrator"]`(装配)
5. `on_llm_response` 改薄壳: 取 bot_text/tone + 写 memory/intimacy/reflex(留 main) + 取 6 状态 + `await self._segmented_orchestrator.handle(...)` 委托
6. 验证 `on_llm_response` < 50 行(test_main_py_no_long_orchestration: 当前 allowlist 标 64 行, 抽后应可移出 allowlist 压到 < 50; test_on_llm_response_bounded 当前 ≤70, 抽后收紧到 ≤50)
7. 跑 `pytest tests/` + on_llm_response 回归(分段 send + 沉默 + 清 llm_resp 时序不破坏, R5)

**注意**: depends_on 5 个(defense_modulator/coordinator/force_dynamics/body_state/intimacy)确认 param_wire 映射。main.py 装配后, 原 self._defense_modulator 等引用保留(其他地方可能用)。`_build_context` 下沉 utils 后, main.py:1482 改 `from emotion_spirit.utils import build_context`。

---

## 任务 5: 8 幽灵接通

**规约**: §1.2 规则 4(显式 depends_on)+ §1.5(生命周期持久化)

**关键认知(2026-07-03 补足)**: 4 组件(environment_context/personality_feedback/project_manager/recovery_tracker)**已是完整实现, 不是空壳** — 缺的是「在 LifeSimulatorV2 正确方法里调用它们」(调用编排), 不是「实现接通逻辑」。adaptation 工具已在 `adapt_plan`(526)+`generate_plan_llm`(599)接通。所以本任务实际是接线, 非写算法。

**步骤**:
1. 4 工具(adaptation/emotion_predictor/energy_model/user_activity_detector)已在任务 1 挪 utils/。**adaptation 已接通**(见 5.A 表), 剩 emotion_predictor + energy_model + user_activity_detector 待接
2. 4 组件保留 @register(已在 regulation/), **已是完整实现**:
   - `environment_context`: ✅ `get_season_bias/get_weather_bias/get_day_bias` 已实现(无状态, 不需持久化, 每次从 datetime 重建)
   - `personality_feedback`: ✅ `apply_activity_effect` 已实现。接法见 5.B(只读输出给 compose, 不直接改 dict)。加 `config_keys={"feedback_rate"}` 配置
   - `project_manager`: ✅ `suggest_project`+`inject_into_plan`+`to_dict/from_dict` 已实现(持久化已有, §1.5 已满足)
   - `recovery_tracker`: ✅ `start_recovery`+`advance_stage`+`adapt_plan_for_recovery`+`to_dict/from_dict` 已实现(持久化已有)
3. `life_simulator.py` LifeSimulatorV2 @register 加 `depends_on=[..., "environment_context", "personality_feedback", "project_manager", "recovery_tracker"]` + param_wire
4. `LifeSimulatorV2.__init__` 加 4 组件参数注入
5. ~~import 3 工具~~ → **修正**: adaptation 已 import(adapt_plan:526, generate_plan_llm:599)。只补 `from ..utils.emotion_predictor import EmotionPredictor` + `from ..utils.energy_model import EnergyModel`
6. **接通契约表(见 5.A)** — 替代原「实现接通逻辑」模糊指令
7. `main.py` **on_llm_request**(非 on_message_receive — 该方法不存在, 见 5.C): 接 `user_activity_detector.detect_plan` 检测用户文本
8. `main.py` _persist_modules(1645): 加 `project_manager` + `recovery_tracker` 持久化(environment_context/personality_feedback 无状态/配置态, **不持久化**)
9. `main.py` _load_life_and_v2_data(1627): 加 project_manager + recovery_tracker 恢复
10. 跑 `pytest tests/` + 新测试(接通逻辑) + test_registry_liveness(4 组件接通后不再是幽灵)

### 5.A 接通契约表(7 幽灵逐个 — 替代原步骤 6 模糊指令)

| 幽灵 | 接通点(LifeSimulatorV2 方法) | 调用 | 输出去向 |
|---|---|---|---|
| adaptation | ✅ 已接 `adapt_plan`(509)+`generate_plan_llm`(583) | `compute_social_tendency`/`select_adaptation_activity`/`derive_activity_preferences` | adapt_plan: cancel/keep 事件; generate_plan_llm: pref_text 进 prompt |
| environment_context | `generate_plan_template`(253) 重排 | `get_season_bias()` + `get_day_bias()` 合并到 `PERSONALITY_ACTIVITY_BIAS` 的 weight 计算 | 影响模板活动选择排序 |
| energy_model | `generate_plan_template`(253) 重排 | `get_energy_level(personality, slot)` → `apply_energy_bias(category_weights, energy)` | 能量高→physical/social, 低→rest/intellectual |
| emotion_predictor | `generate_daily_plan`(350) 末尾 | `EmotionPredictor().predict_mood_trajectory(plan, current_mood)` + `suggest_adjustment(trajectory)` | adjustment 建议进 `build_schedule_context`(421) 输出, 给 compose prompt |
| personality_feedback | `adapt_plan`(509) 末尾 | `compute_feedback`(只读版, 见 5.B): 算反馈值, 不改 dict | 反馈值进 `build_schedule_context` 输出给 compose, LLM 整合, **不写 personality_drift** |
| project_manager | `generate_daily_plan`(350) 生成 plan 后 | `suggest_project`(每日首次, 若 active 项目 < N) + `inject_into_plan(plan)` | 多日项目事件进 plan.events(category="project") |
| recovery_tracker | `adapt_plan`(509) 开头 + 触发链(见 5.D) | `adapt_plan_for_recovery(plan)`(若 active) | 替换当天事件为恢复阶段活动(category="recovery") |

### 5.B personality_feedback 接法(只读输出给 compose — 避免 personality_drift 双写)

**决策(2026-07-03 用户拍板)**: 只读, 不直接改 personality dict。

`PersonalityFeedback.apply_activity_effect` 现实现是**直接改传入 dict**(`personality[trait] = clamp(...)`)。但 main.py 已有 `personality_drift` 模块专管人格漂移 → 直接接通 = 双轨人格(§5 反模式)。

**接法**:
- 新增只读方法 `compute_feedback(personality: dict, activity_category: str) -> dict[str, float]`: 返回各 trait 的 delta(不修改原 dict)
- `adapt_plan` 末尾: 累加当天各活动 category 的反馈, 调 `compute_feedback` 收集 delta
- delta 进 `build_schedule_context`(421) 输出: "今天活动让你倾向 {trait:+delta}" → 给 compose prompt, LLM 整合
- **不调** `apply_activity_effect`(直接改 dict 的旧路径), **不写** personality_drift
- 旧 `apply_activity_effect` 标 deprecated 或删(仅此一处用)

### 5.C user_activity_detector 接 main.py(修正: on_message_receive 不存在)

**事实修正**: plan 原写"main.py on_message_receive 接 user_activity_detector", 但 main.py **只有 `@filter.on_llm_request`(1215)+`@filter.on_llm_response`(1290)两个钩子, 无 on_message_receive**(grep 确认)。

**接法**: 在 `on_llm_request`(1215)钩子内, 取 user text 调 `user_activity_detector.detect_plan`:
- `on_llm_request` 已能拿 event + user message text
- 检测结果(joint/busy/wish)存 `self._latest_user_activity[user_id]`(运行时快照)
- `LifeSimulatorV2.adapt_plan` 或 `generate_daily_plan` 读取该快照, 调 `user_activity_detector.inject_into_plan(plan, detected)` 把用户活动塞进 plan
- 不新增 AstrBot 钩子(用已存在的 on_llm_request)

### 5.D recovery_tracker 触发链(原 plan 缺, 补足)

collapse → recovery 的时序 plan 原未画, 补:
1. **触发**: `memory_pool.py:410` 算 `_collapse_archetype` 时(current-truth §4 记的 collapse 触发点), 同步调 `recovery_tracker.start_recovery(archetype)`
   - 实际实现(v1.2.7 落实): 通过 `surface_handler.py:283` 中转(非原 plan 设想的 main.py 中转) — surface_handler 持 recovery_tracker 引用, collapse 后调 `rc.start_recovery(pool._collapse_archetype)`。**v1.2.8 债 2**: 把 `_collapse_archetype` 私有访问改为 `memory_pool.get_collapse_archetype()` 公开方法
2. **应用**: 下次 `LifeSimulatorV2.adapt_plan`(509) 开头, 若 `recovery_tracker._active_recovery` 非 None, 调 `adapt_plan_for_recovery(plan)` 替换当天事件
3. **推进**: 每日 `generate_daily_plan`(350) 生成新 plan 时, 调 `recovery_tracker.advance_stage()`(一天一阶段, 对应 RECOVERY_TRAJECTORIES 的 2-7 天恢复期)
4. **完成**: `advance_stage` 超过 trajectory 长度自动清 `_active_recovery`(已实现, recovery_tracker:84)

**注意**: 接通是 v1.2.7 最大工作量但**非写算法**(组件已实现)。分步: (1) LifeSimulatorV2 depends_on 4 组件 + 注入(空调用); (2) 接通契约表逐个接(每接一个跑测试); (3) recovery 触发链最后接(跨 memory_pool/main/life_simulator 三方)。R3 风险: 接通后 life_simulator 输出可能退化, 跑回归。personality_feedback 只读方案已规避 R7(双写人格)。

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

**已完成 (7.5/10)**:
- [x] utils/ 层建立, 11 工具集中(取消 @register)
- [x] Q3 事件机制删除(agent 主循环仍运转)
- [x] HP-2/HP-4/DO-3/DO-4 清完
- [x] DO-5 spec drift 标注
- [x] collapse_archetype 核实(非幽灵, 6+ 消费者)
- [x] 9 个可拦测试实现(test_kb_centralization / registry_liveness / main_py_no_long_orchestration / layer_dependencies / type_contracts / lifecycle_pairs / agent_no_impl / no_event_bus / agent_no_direct_call + tone_extractor)

**待完成 (2.5/10)**:
- [ ] Task 4 后半: SegmentedReplyOrchestrator 抽出(按 4.A 状态归属表 + 4.B 私有方法处置 + 4.C 死分支删 + 4.D event/response 契约)
- [ ] Task 5: 8 幽灵接通(按 5.A 接通契约表逐个 + 5.B feedback 只读 + 5.C on_llm_request 入口 + 5.D recovery 触发链)
- [ ] `pytest tests/` 全绿(当前 1350 passed, Task 4/5 完成后预期 +N 接通测试; 允许 Win 概率性 test_periodic_save_dirty_only flake)
- [ ] on_llm_response < 50 行(test_main_py_no_long_orchestration allowlist 移出 + test_on_llm_response_bounded 收紧到 ≤50)
- [ ] module count 调整后确认(58 → 47 @register, 删事件不算模块, 接通 4 组件已算)
- [ ] handbook §6 更新"v1.2.7 已清的债"
- [ ] `docs/CHANGELOG.md` v1.2.7 entry

---

## 风险

| # | 风险 | 处置 |
|---|---|---|
| R1 | 挪 11 工具改 import 路径多, 回归 | ✅ 已完成: 每挪一个跑测试, 小步推进 |
| R2 | 删事件机制改 agents/ 多文件 | ✅ 已完成: 先删 event_bus + emit, 跑测试确认主循环不破坏, 再删 bus 参数 |
| R3 | LifeSimulatorV2 接 7 幽灵(接通逻辑复杂) | **修正认知**: 非写算法(组件已实现), 是接线。分步: (1) depends_on+注入(空调用); (2) 5.A 契约表逐个接; (3) 5.D recovery 触发链最后接 |
| R4 | DO-4 conscience 源变更, suppression 值变, life_simulator 退化 | ✅ 已完成: 跑回归未退化(1350 passed) |
| R5 | SegmentedReplyOrchestrator 抽出后, on_llm_response 时序变 | 跑 on_llm_response 回归(分段 send + 沉默 + 清 llm_resp); 按 4.A 状态归属表确保 6 状态全传入 |
| R6 | test_type_contracts 初期难写(类型契约刚引入) | ✅ 已完成: conscience_pressure + force_state dict 两样本 |
| R7 | personality_feedback 直接改 dict → 与 personality_drift 双写人格 | **已规避(5.B)**: 只读 compute_feedback 输出给 compose, 不改 dict 不写 drift |
| R8 | _build_context 下沉 utils 改 main.py import | 纯函数化 build_context(event), main.py:1482 + orchestrator 都 import; 跑 _build_context 回归 |
| R9 | recovery 触发链跨 memory_pool/main/life_simulator 三方 | 5.D 分步: 先 main 中转 start_recovery, 再 adapt_plan 调 adapt_plan_for_recovery, 最后 generate_daily_plan 调 advance_stage; 每步跑测试 |

---

## 相关

- `docs/v126_audit_report.md` — v1.2.6 审计报告(本 plan 依据)
- `UPDATE_HANDBOOK.md` — 六件套规约(§1.1-§1.6)
- `docs/superpowers/plans/2026-07-03-v126-l2-scaffolding-plan.md` — 原 L2 脚手架 plan(deferred v1.2.8+)
