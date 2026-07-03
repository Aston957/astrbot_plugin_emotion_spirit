# v1.2.6 架构审计报告

> **日期**: 2026-07-03
> **范围**: 只读审计(不改代码)
> **前置**: v1.2.5 ship (`a35d689`, 58 modules, 1348 tests)
> **规约依据**: handbook 六件套(§1.1-§1.6, 本次审计同期补强)
> **目的**: 产出债清单 + 规约依据,供 v1.2.7 清债按图索骥

---

## 1. 模块活性审计(58 @register)

三层活性:
- **直接在跑**(main.py 取用): ~36
- **间接在跑**(被 depends_on): 4(force_dynamics / suppression / collapse_archetype_selector / memory_sampler)
- **候选空转 21** → 核实:

| 类 | 数量 | 模块 |
|---|---|---|
| 真幽灵(零消费) | 9 | activity_history / adaptation_engine / emotion_predictor / energy_model / environment_context / personality_feedback / project_manager / recovery_tracker / user_activity_detector |
| 无状态误用(_ModuleMarker 或无状态类) | 7 | emotion_classifier / label_mapper / persona_profiles / trend_utils / decay_model / knowledge / persona_report_parser |
| 真双轨(有状态 + import new) | 1 | persona_analyzer |
| 真在跑(假阳性) | 3 | body_state / life_simulator / cascade_engine |
| 待核 | 1 | collapse_archetype |

**修正**: 第一轮"36% 候选空转"(grep name= 误差)→ 实际 ~24% 真有问题(9 幽灵 + 7 误用 + 1 双轨 = 17/58)。

---

## 2. 8 幽灵分类 + 接通分配

8 幽灵 = v1.1.0C "生活模拟扩展"子系统(为 LifeSimulatorV2 设计,未接通 → 零消费)。

| 模块 | 性质 | 处置 | 接通归属 |
|---|---|---|---|
| adaptation | `_AdaptationMarker`(纯函数) | utils/ | LifeSimulatorV2 import |
| emotion_predictor | 无状态类 | utils/ | LifeSimulatorV2 import |
| energy_model | 无状态类 | utils/ | LifeSimulatorV2 import |
| environment_context | 有状态(环境) | @register | LifeSimulatorV2 depends_on |
| personality_feedback | 有状态(配置) | @register + config_keys | LifeSimulatorV2 depends_on |
| project_manager | 有状态(多日项目) | @register + §1.5 持久化 | LifeSimulatorV2 depends_on |
| recovery_tracker | 有状态(跨天恢复) | @register + §1.5 持久化 | LifeSimulatorV2 depends_on |
| user_activity_detector | 无状态类(正则) | utils/ | **main.py 入口**(检测用户文本) |

**接通后**: LifeSimulatorV2 从简化版升级为完整生活模拟扩展(7 幽灵接入);user_activity_detector 进 main.py 入口(on_message_receive 检测用户活动)。

---

## 3. Q1 — main.py 219 行编排审计

`on_llm_response`(1291)+ `_on_segmented_reply_v2`(1387)+ `_extract_bot_emotion`(1356)= ~219 行。

违反 §1.2 规则 3(薄壳:main 只调用不实现):
- **_extract_bot_emotion**(28行,关键词匹配 warm/apologetic/curious): 功能逻辑 → 抽 utils/(纯函数工具)
- **_on_segmented_reply_v2**(121行,编排超 50 行上限): 抽 @register 功能组件(`SegmentedReplyOrchestrator`, output/ 层)

抽成判定(§1.6 规则 5): 输出编排(调 DefenseModulator+coordinator+send,非认知轴)→ @register 组件,不是 agent。

抽后 on_llm_response 变薄壳(~20 行:取 text + 调组件 + 委托)。

---

## 4. Q2 — 分层合理性

| 发现 | 结论 | 处置 |
|---|---|---|
| regulation 24 臃肿 | 积债(8 幽灵 + 2 该挪 utils/),非兜底 | 清完剩 ~13 真调节 |
| 跨层依赖(life_simulator/counterfactual/dream_generator → memory/output) | **显式合规**(depends_on + param_wire + __init__ 注入,无双轨) | 不动(合规反馈回路) |
| agent 双轨 | = 编排双轨(Q1 覆盖) | Q1 处置 |
| agent @register 不一致 | self_core 注册,4 agent 手 new | §1.6 规则 4 债(TODO) |

---

## 5. Q3 — agents 事件流

| 组件 | 状态 | 证据 |
|---|---|---|
| agent 主循环(perceive/gate/act/compose) | ✅ 运转 | run_cycle 被 main.py:1173 调,composed.flags/carried 进 prompt |
| 事件机制(EventBus + 4 事件 + emit) | ❌ 空转 | 全仓 0 个 `.subscribe()` 调用 |

**处置**: v1.2.6 决定**删事件机制**(LLM 整合替代,0 用户未验证事件价值),v1.2.7 执行删除(event_bus.py + AgentEvent + 4 事件类型 + base.py emit + 4 agent emit 调用 + bus 参数)。§1.6 规则 3 改为"协作走 LLM 整合不用事件"。

---

## 6. agent 集合明确(§1.6 规则 2)

接通 8 幽灵后,各 agent 包装的组件集合:

| Agent | 集合(包装的组件) |
|---|---|
| MemoryAgent | memory_pool + shadow_detector |
| PersonalityAgent | superego_guard + personality_drift |
| RelationshipAgent | intimacy + social_graph |
| LifeAgent | life_simulator_v2(内部含 7 幽灵: adaptation/emotion_predictor/energy_model/environment_context/personality_feedback/project_manager/recovery_tracker) |

---

## 7. v1.2.7 清债清单(按六件套规约)

| 债 | 规约依据 | 处置 |
|---|---|---|
| 9 幽灵 | §1.2 规则 2(活性) | 8 接通(4 工具挪 utils/ + 4 组件 @register)+ collapse_archetype 待核 |
| 7 无状态误用 | §1.2 规则 1 + §1.3(utils/) | 取消 @register,挪 utils/(含 8 幽灵的 4 工具,共 11 个工具集中 utils/) |
| persona_analyzer 双轨 | §1.2 规则 4 | 改走 factory(commands.py self._modules 取) |
| Q1 _extract_bot_emotion | §1.2 规则 3 | 抽 utils/ |
| Q1 _on_segmented_reply_v2 | §1.2 规则 3 | 抽 @register(SegmentedReplyOrchestrator) |
| Q3 事件机制 | §1.6 规则 3 | 删(EventBus + AgentEvent + 4 事件 + emit) |
| agent 手 new | §1.6 规则 4 | 扩 factory param_wire 支持 bus 注入,agent @register(TODO,或推 v1.3) |
| HP-2 conscience 死代码 | §1.4 | compute_defense_states 加 conscience_pressure 参数(caller 传) |
| HP-4 offset 不持久化 | §1.5 | force_dynamics to_dict/from_dict + main.py persist |
| DO-3 方法内 import | 琐碎 | 顶部 import |
| DO-4 conscience 源错配 | §1.4 | main.py:399 统一 conscience.get_pressure() |
| DO-5 spec drift | 文档 | v1.2.5 spec 加 drift 注记 |
| LifeSimulatorV2 接 7 幽灵 | §1.2 规则 4 | depends_on 4 组件 + import 3 工具 + 调用逻辑 |
| user_activity_detector 接 main.py | §1.2 规则 3 | main.py on_message 入口调 |

**可拦测试**(v1.2.7 实现,防回归):
- test_kb_centralization.py(§1.1)
- test_registry_liveness.py(§1.2 规则 1+2+4)
- test_main_py_no_long_orchestration.py(§1.2 规则 3,50 行上限)
- test_layer_dependencies.py(§1.3 core 元层)
- test_type_contracts.py(§1.4)
- test_lifecycle_pairs.py(§1.5)
- test_agent_no_impl.py / test_no_event_bus.py / test_agent_no_direct_call.py(§1.6)

---

## 8. v1.3 backlog

- **agent @register**(扩 factory param_wire 支持 bus)→ §1.6 规则 4
- **agent 集合动态变化**(config 驱动 / 情境激活)→ 依赖 agent @register
- **L2 脚手架完善**(HP-3 三子全接 + HP-4 offset 持久化 + DO-2 拆 compute_silence_only)→ 原 v1.2.6 plan(deferred 到 v1.2.8+)
- **力学 L3 fixpoint**(compute 读 offset,L2 真正生效)→ v1.3 核心

---

## 9. 审计总结

`✶ Insight`: 审计最大收获不是发现多少债,而是**分清"债 vs 合规"**:
- 跨层依赖看着像债,实际合规(显式 depends_on 反馈回路)
- 8 幽灵看着像"regulation 臃肿",实际是"v1.1.0C 扩展未接通"(可复活)
- agent 事件空转看着像"agent 系统坏",实际是"主循环有效果,协作机制该删"

规约(六件套)给了判定标准,让审计能区分"真债"(该清)和"合规"(不动),而不是"看着乱就清"。v1.2.7 清债按规约 + 本报告执行,清完有可拦测试防回归。
