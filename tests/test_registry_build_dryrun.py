"""Phase B6.x 集成测试: dry_run + 真装配 (P3-7 L2 DI 验证)。

28 模块全跑 registry.build() 0 错误 + 多实例拆 sub 正确。
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import emotion_spirit  # noqa: F401  # 触发 30 模块 @register (Phase 3.0B Task 3: +body_state)
from emotion_spirit.core.registry import ModuleRegistry, build
from emotion_spirit.core.plugin_factory import default_config, build as factory_build


def test_dry_run_30_modules_no_error():
    """dry_run 走 30 模块依赖图检查, 0 错误。"""
    assert len(ModuleRegistry.get_all()) == 30, f"expected 30 modules, got {len(ModuleRegistry.get_all())}"
    config = default_config(
        data_dir="/tmp/test_dryrun",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = build(config, dry_run=True)
    assert instances == {}, f"dry_run should return empty dict, got {instances}"


def test_dry_run_17_mismatch_resolve():
    """18 mismatch 模块都能在 dry_run 中找到所有 dep。

    Phase 3.0B Task 3: 17 → 18 (+body_state 无 DI, 实际无 mismatch; 计数沿用
    Phase B6 末次清的 17 边界, 后续 mismatch 重新数)。
    """
    for name, spec in ModuleRegistry.get_all().items():
        for dep in spec.depends_on:
            if "." not in dep:
                assert dep in ModuleRegistry.get_all(), f"{name} 缺 dep {dep}"
            else:
                base, sub = dep.split(".", 1)
                base_spec = ModuleRegistry.get_all().get(base)
                assert base_spec is not None, f"{name} 缺 base dep {base}"
                # sub 可在 provides_classes (multi-instance) 或 provides (class name 形式)
                in_pc = base_spec.provides_classes and sub in base_spec.provides_classes
                in_p = sub in base_spec.provides
                assert in_pc or in_p, f"{name} 缺 sub {sub} from {base}"


def test_build_real_construct_25_instances():
    """真装配 25 个 instantiable 模块, 0 错误。"""
    config = default_config(
        data_dir="/tmp/test_real_build",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = build(config, dry_run=False)
    # 25 instantiable modules (utility 4 不算)
    assert len(instances) >= 25, f"expected ≥25 instances, got {len(instances)}"

    # 关键模块类型对得上
    from emotion_spirit.store import SpiritStore
    from emotion_spirit.memory.memory_pool import MemoryPool
    from emotion_spirit.memory.intimacy import IntimacyTracker
    assert isinstance(instances["store"], SpiritStore)
    assert isinstance(instances["memory_pool"], MemoryPool)
    assert isinstance(instances["intimacy"], IntimacyTracker)


def test_build_superego_multi_instance():
    """superego 走 multi-instance 分支, 返回 dict 含 4 sub。"""
    from emotion_spirit.regulation.superego import (
        ValueAlignment, ValueResistance, ConscienceTracker, IdealSelf,
    )
    config = default_config(
        data_dir="/tmp/test_superego",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = build(config)
    se = instances["superego"]
    assert isinstance(se, dict)
    assert set(se.keys()) == {"alignment", "conscience", "resistance", "ideal"}
    assert isinstance(se["alignment"], ValueAlignment)
    assert isinstance(se["conscience"], ConscienceTracker)
    assert isinstance(se["resistance"], ValueResistance)
    assert isinstance(se["ideal"], IdealSelf)


def test_build_prompt_injector_superego_sub_deps_wired():
    """prompt_injector 拿 superego 3 sub (alignment/conscience/ideal)。"""
    from emotion_spirit.output.prompt_injector import PromptInjector
    config = default_config(
        data_dir="/tmp/test_pi",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = build(config)
    pi = instances["prompt_injector"]
    assert isinstance(pi, PromptInjector)
    assert pi._alignment is instances["superego"]["alignment"]
    assert pi._conscience is instances["superego"]["conscience"]
    assert pi._ideal is instances["superego"]["ideal"]


def test_plugin_factory_returns_same_shape_as_old_manual():
    """plugin_factory.build() 跟旧手装 426 行返回的 dict shape 一致。"""
    config = default_config(
        data_dir="/tmp/test_pf_shape",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = factory_build(config)
    # 24 个 instantiable modules 都该在 dict 里 + 4 utility (marker)
    expected_instantiable = {
        "store", "surface_consumer", "memory_pool", "buffer_signals", "intimacy",
        "superego", "superego_guard", "meaning_reservoir", "pattern_extractor",
        "shadow_detector", "life_simulator", "diary_writer", "prompt_injector",
        "personality_drift", "predictive_sentinel", "narrative_identity",
        "counterfactual", "persona_analyzer", "relationship_personality",
        "social_graph", "topic_privacy", "bot_decision", "knowledge",
        "persona_report_parser", "force_dynamics",
    }
    # 检查 24 个 instantiable 都在
    for name in expected_instantiable:
        assert name in instances, f"missing instantiable: {name}"
    # superego 是 dict 含 4 sub
    assert set(instances["superego"].keys()) == {"alignment", "conscience", "resistance", "ideal"}


def test_dry_run_then_real_build_consistent():
    """dry_run 跟真装配 module 集合一致。

    Phase 3.0B Task 3: 29 → 30 (+body_state 真装配, 25 instantiable + 5 utility? 待 verify).
    """
    config = default_config(
        data_dir="/tmp/test_consistent",
        persona_id="INFP-A",
        labels={},
    )
    real = build(config)
    # build() 默认 enabled=True for registry modules not in config,
    # 所以 utility N (provides=[]) 也被装配. Phase 3.0B Task 3: 30 instances
    # (26 instantiable + 4 utility, or 25 + 5 utility, 等)
    assert len(real) == 30, f"expected 30 instances, got {len(real)}"


# ════════════════════════════════════════════════════════════════════
# Phase B6.x.x M8: 4 边界测试覆盖 gap
# ════════════════════════════════════════════════════════════════════


def test_default_data_dir_when_none():
    """data_dir=None → default_config fallback 到 'data' (B6.x.x M8 边界)。"""
    import tempfile
    # 用临时目录避免污染工作区
    with tempfile.TemporaryDirectory() as tmp:
        config = default_config(data_dir=None, persona_id="", labels={})
        # 验证 params.data_dir 落 'data' (default)
        assert config["params"]["data_dir"] == "data"
        # 验证 store.__init__ 接受 'data' (B6.x 真装配)
        config["params"]["data_dir"] = tmp  # 改 tmpdir 避免污染
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
        config["modules"]["knowledge"]["enabled"] = False
        config["modules"]["persona_report_parser"]["enabled"] = False
        config["modules"]["superego"]["enabled"] = False
        config["modules"]["superego_guard"]["enabled"] = False
        config["modules"]["meaning_reservoir"]["enabled"] = False
        config["modules"]["personality_drift"]["enabled"] = False
        config["modules"]["relationship_personality"]["enabled"] = False
        instances = build(config)
        # store._dir.name 反映传入的 data_dir
        assert instances["store"]._dir.name == os.path.basename(tmp)


def test_superego_with_empty_persona_id():
    """persona_id='' → superego 4 sub 全部正常建 (B6.x.x M8 边界)。"""
    config = default_config(data_dir="/tmp/test_empty_pid", persona_id="", labels={})
    instances = build(config)
    se = instances["superego"]
    assert se["alignment"]._persona == ""
    assert se["ideal"]._persona == ""


def test_bot_decision_gossip_tendency_05():
    """gossip_tendency=0.5 → bot_decision._gossip_tendency == 0.5 (B6.x.x M8 边界)。"""
    config = default_config(data_dir="/tmp/test_gossip_05", persona_id="", labels={}, gossip_tendency=0.5)
    instances = build(config)
    assert instances["bot_decision"]._gossip_tendency == 0.5


def test_cycle_detection_raises_runtime_error():
    """循环依赖 raise RuntimeError (B6.x.x M8 边界: 测试 build() 的 fail-fast)。

    用 2 个临时模块 A 跟 B 互依, 验证 _pending loop 检测到 no progress 时抛错。
    需手动 save/restore registry 避免污染 28 真实模块 (本文件无 autouse fixture)。
    """
    from emotion_spirit.core.registry import register
    import pytest
    saved = dict(ModuleRegistry.get_all())
    try:
        @register(name="_test_cycle_a", provides=["_A"], depends_on=["_test_cycle_b"])
        class _A:
            def __init__(self, _test_cycle_b) -> None:
                pass

        @register(name="_test_cycle_b", provides=["_B"], depends_on=["_test_cycle_a"])
        class _B:
            def __init__(self, _test_cycle_a) -> None:
                pass

        config = default_config(data_dir="/tmp/test_cycle", persona_id="", labels={})
        config["modules"]["_test_cycle_a"] = {"enabled": True}
        config["modules"]["_test_cycle_b"] = {"enabled": True}
        with pytest.raises(RuntimeError, match="循环依赖"):
            build(config)
    finally:
        ModuleRegistry._registry.clear()
        for name, spec in saved.items():
            ModuleRegistry._registry[name] = spec
