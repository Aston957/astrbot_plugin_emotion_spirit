"""Tests for plugin_factory (Phase B, P3-1 main.py 拆分)。

plugin_factory.build() 装配 28 模块, 返回 dict[name, instance]。
走 ModuleRegistry + 手动装配 (混合) 因为 registry 还在演进中。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_plugin_factory_build_returns_requested_modules():
    """plugin_factory.build() 返回 dict 包含所有 requested enabled 模块。"""
    from emotion_spirit.core.plugin_factory import build, default_config

    # 用 default_config() 拿全配置, 再 disable 不要的模块 (B6.x 全 28 模块走 registry.build)
    config = default_config(data_dir="/tmp/test_pf_1", persona_id="INFP-A", labels={})
    config["modules"]["counterfactual"]["enabled"] = False
    config["modules"]["life_simulator"]["enabled"] = False
    config["modules"]["prompt_injector"]["enabled"] = False
    config["modules"]["narrative_identity"]["enabled"] = False
    config["modules"]["predictive_sentinel"]["enabled"] = False
    config["modules"]["diary_writer"]["enabled"] = False
    config["modules"]["shadow_detector"]["enabled"] = False
    config["modules"]["buffer_signals"]["enabled"] = False
    config["modules"]["pattern_extractor"]["enabled"] = False
    config["modules"]["persona_analyzer"]["enabled"] = False
    config["modules"]["bot_decision"]["enabled"] = False
    config["modules"]["social_graph"]["enabled"] = False
    config["modules"]["topic_privacy"]["enabled"] = False
    # knowledge, persona_report_parser 等已移入 utils/ (不再 @register)
    # 不从 factory 配置中启用/禁用
    config["modules"]["superego"]["enabled"] = False
    config["modules"]["superego_guard"]["enabled"] = False
    config["modules"]["meaning_reservoir"]["enabled"] = False
    config["modules"]["personality_drift"]["enabled"] = False
    config["modules"]["relationship_personality"]["enabled"] = False
    # v1.2.1 DI cleanup 新模块 (deps 依赖上面禁用的模块, 测试不构建它们)
    config["modules"]["life_simulator_v2"]["enabled"] = False
    config["modules"]["self_core"]["enabled"] = False
    config["modules"]["realtime_dispatch"]["enabled"] = False
    config["modules"]["rhythm_learner"]["enabled"] = False
    config["modules"]["hotpool_forwarder"]["enabled"] = False
    config["modules"]["engine_manager"]["enabled"] = False
    config["modules"]["personality_bridge"]["enabled"] = False
    config["modules"]["command_router"]["enabled"] = False
    config["modules"]["segmented_reply_coordinator"]["enabled"] = False
    config["modules"]["segmented_reply_orchestrator"]["enabled"] = False  # v1.2.7: depends on disabled
    config["modules"]["defense_modulator"]["enabled"] = False  # v1.2.5 PR2: depends on disabled
    modules = build(config)
    assert "store" in modules
    assert "memory_pool" in modules
    assert "intimacy" in modules


def test_plugin_factory_can_disable_module():
    """config 中 enabled=False 跳过该模块。"""
    from emotion_spirit.core.plugin_factory import build, default_config

    config = default_config(data_dir="/tmp/test_pf_2", persona_id="INFP-A", labels={})
    config["modules"]["bot_decision"]["enabled"] = False
    modules = build(config)
    assert "bot_decision" not in modules
    # 启用的还在
    assert "store" in modules


def test_plugin_factory_default_config_lists_all_35():
    """default_config() 列出所有有 provides 的模块 (utility 不在内)。

    历史增量(便于追踪):
    Phase 3.0B Task 3: 25 → 26 (+body_state, 25 instantiable + 1 body_state = 26
    - 4 utility = 26. 等价: 30 总 - 4 utility = 26 instantiable)。
    Phase 0 Task 3: 26 → 30 (+dream_generator, +reflex_learner, +reflex_learner_store, +memory_sampler)
    - 等价: 34 总 - 4 utility = 30 instantiable。
    Phase 0 Task 5: 30 → 34 (+cascade_engine, +decay_model, +suppression, +collapse_archetype_selector)
    - 等价: 39 总 - 5 utility = 34 instantiable。
    v1.1.0C T1: 34 → 35 (+adaptation_engine) — 等价: 40 总 - 5 utility = 35 instantiable。
    v1.1.0 (LifeSimulatorV2 + agents + diary): 35 → 43 (+life_simulator_v2 + diary_writer
    + cognitive_agent + memory_agent + personality_agent + relationship_agent + self_core + event_bus)
    — 等价: 48 总 - 5 utility = 43 instantiable。

    不再硬编码 35 — 用 expected_count 动态比对, 跟
    test_instantiable_modules_derives_from_registry 一致。
    """
    from emotion_spirit.core.registry import ModuleRegistry
    from emotion_spirit.core.plugin_factory import default_config

    expected_count = sum(1 for s in ModuleRegistry.get_all().values() if s.provides)
    cfg = default_config(data_dir="data")
    enabled = [name for name, m in cfg["modules"].items() if m.get("enabled", True)]
    # utility 模块 provides=[] (纯算法/工具), 不应由 factory 装配.
    # main.py 实际启用的子集 不影响此处: factory 默认装配所有有 provides 的模块,
    # 调用方可按需禁用 (e.g. bot_decision) 而不破坏工厂契约.
    assert len(enabled) == expected_count
    # utility 模块不应在 enabled (它们 provides=[])
    assert "emotion_classifier" not in enabled
    assert "label_mapper" not in enabled
    assert "persona_profiles" not in enabled
    assert "trend_utils" not in enabled
    assert "knowledge" not in enabled
    assert "decay_model" not in enabled
    assert "persona_report_parser" not in enabled
    assert "adaptation_engine" not in enabled
    assert "emotion_predictor" not in enabled
    assert "energy_model" not in enabled
    assert "user_activity_detector" not in enabled
    assert "collapse_archetype" not in enabled


def test_instantiable_modules_derives_from_registry():
    """default_config() 跟 registry 同步: 所有 provides>0, 加新模块自动出现 (B6.x.x I1)。

    Phase 3.0B Task 3: 25 → 26 (+body_state).
    Phase 0 Task 3: 26 → 30 (+dream_generator, +reflex_learner, +reflex_learner_store, +memory_sampler).
    Phase 0 Task 5: 30 → 34 (+cascade_engine, +decay_model, +suppression, +collapse_archetype_selector).
    v1.1.0C T1: 34 → 35 (+adaptation_engine).
    v1.1.0: 35 → 43 (+life_simulator_v2 + diary_writer + agents + event_bus).
    """
    from emotion_spirit.core.registry import ModuleRegistry, register
    from emotion_spirit.core.plugin_factory import default_config

    # 1. 长度动态 (utility 不算)
    expected_count = sum(1 for s in ModuleRegistry.get_all().values() if s.provides)
    cfg = default_config(data_dir="data")
    enabled = [n for n, m in cfg["modules"].items() if m.get("enabled", True)]
    assert len(enabled) == expected_count

    # 2. 每个都在 registry 里有 spec 且 provides 非空
    for name in enabled:
        spec = ModuleRegistry.get_all().get(name)
        assert spec is not None, f"{name} 不在 registry"
        assert spec.provides, f"{name} provides 应非空"

    # 3. 临时 register 一个新模块, 验证自动出现
    saved = dict(ModuleRegistry.get_all())
    try:
        @register(name="_test_instantiable_xxx", provides=["_TestClass"], depends_on=[])
        class _TestInstantiableClass:
            def __init__(self) -> None:
                pass

        cfg2 = default_config(data_dir="data")
        enabled2 = [n for n, m in cfg2["modules"].items() if m.get("enabled", True)]
        assert "_test_instantiable_xxx" in enabled2, (
            f"新模块应自动出现在 default_config, got {enabled2}"
        )
        assert len(enabled2) == expected_count + 1  # + 1 临时
    finally:
        # 恢复 registry, 清掉临时 class
        ModuleRegistry._registry.clear()
        for name, spec in saved.items():
            ModuleRegistry._registry[name] = spec


def test_plugin_factory_passes_data_dir_to_store():
    """data_dir 参数传给 SpiritStore。"""
    from emotion_spirit.core.plugin_factory import build, default_config

    config = default_config(data_dir="/tmp/test_emotion_spirit_data", persona_id="INFP-A", labels={})
    modules = build(config)
    store = modules["store"]
    # SpiritStore 内部应使用 data_dir
    assert str(store._dir) == "/tmp/test_emotion_spirit_data" or str(store._dir).endswith("test_emotion_spirit_data")


def test_plugin_factory_builds_superego_components():
    """superego 模块分解为 4 sub-components (alignment/conscience/resistance/ideal)。"""
    from emotion_spirit.core.plugin_factory import build, default_config

    config = default_config(data_dir="data", persona_id="test_persona", labels={})
    modules = build(config)
    # superego 应有 alignment/conscience/resistance/ideal sub-keys
    assert "superego" in modules
    se = modules["superego"]
    assert "alignment" in se
    assert "conscience" in se
    assert "resistance" in se
    assert "ideal" in se
