"""§1.2 规则 1+2+4: @register 活性 — 每个 @register 模块必须被消费."""

from __future__ import annotations

from emotion_spirit.core.registry import ModuleRegistry


def test_every_register_is_consumed():
    """每个 @register 模块 (非 utility) 应被 main.py 或某 @register 模块取用."""
    import emotion_spirit  # noqa: F401 — trigger all @register side effects

    known_consumed = {
        # main.py 直接取的
        "store", "memory_pool", "intimacy", "superego", "superego_guard",
        "meaning_reservoir", "pattern_extractor", "shadow_detector",
        "life_simulator", "diary_writer", "prompt_injector",
        "personality_drift", "predictive_sentinel", "narrative_identity",
        "counterfactual", "persona_analyzer", "relationship_personality",
        "social_graph", "topic_privacy", "bot_decision",
        "force_dynamics", "defense_modulator",
        "surface_consumer", "buffer_signals",
        "life_simulator_v2", "reflex_learner", "reflex_learner_store",
        "dream_generator", "memory_sampler", "cascade_engine",
        "suppression", "collapse_archetype", "collapse_archetype_selector",
        # bridge
        "engine_manager", "hotpool_forwarder", "personality_bridge",
        # output
        "realtime_dispatch", "rhythm_learner",
        "command_router", "segmented_reply_coordinator",
        "segmented_reply_orchestrator",  # v1.2.7: 从 _on_segmented_reply_v2 抽出
        # agents
        "self_core",
        # v1.1.0C
        "activity_history", "project_manager", "recovery_tracker",
        "personality_feedback", "environment_context",
        "body_state",
    }

    registry = ModuleRegistry.get_all()
    for name, spec in registry.items():
        if not spec.provides:
            continue  # utility 模块 (provides=[])
        # 检查 known_consumed 或 depends_on 链
        if name in known_consumed:
            continue
        # 检查是否有其他模块 depends_on 它
        depended = [n for n, s in registry.items() if name in s.depends_on]
        if depended:
            continue
        # 没有 consumer — 幽灵
        assert False, f"{name} 无 consumer (幽灵模块)"


def test_no_hidden_manual_new():
    """main.py 不应手 new 已 @register 的类 (双轨闸)."""
    import ast
    from pathlib import Path

    main_path = Path(__file__).parent.parent / "main.py"
    source = main_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # 查找所有 self._xxx = SomeClass( 模式
    assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        class_name = node.value.func.id
                        assignments.append((target.attr, class_name))

    # 已知允许的 hand-new:
    # CommandImpl 需 plugin 引用 (框架限制)
    # MemoryAgent/PersonalityAgent/RelationshipAgent/LifeAgent (factory 限制)
    # SurfaceHandler
    allowed = {"_cmd", "_surface_handler", "_life_agent", "_public_api",
               "_router"}
    violations = [(attr, cls) for attr, cls in assignments
                  if attr not in allowed and cls[0].isupper()]
    assert not violations, f"main.py 可能有双轨手 new: {violations}"


def test_public_api_is_facade_not_registered():
    """Bug-C (v1.2.10): PublicAPI 是 facade, 不应 @register.

    PublicAPI.__init__ 吃整个 modules dict, factory 的 depends_on 单 dep 注入模型
    不适用 (会 TypeError). 防 v1.2.5 PR3 T3 半截 @register 重演.
    手 new 走 test_no_hidden_manual_new 的 allowed 列表 (已含 _public_api).
    """
    import emotion_spirit  # noqa: F401 — trigger @register side effects
    registry = ModuleRegistry.get_all()
    assert "public_api" not in registry, (
        "PublicAPI 不应 @register (facade 吃整个 modules dict, factory 注入不了) — "
        "见 main.py self._public_api = PublicAPI(self._modules) 手 new"
    )