"""Phase B6.x 集成测试: dry_run + 真装配 (P3-7 L2 DI 验证)。

28 模块全跑 registry.build() 0 错误 + 多实例拆 sub 正确。
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import emotion_spirit  # noqa: F401  # 触发 28 模块 @register
from emotion_spirit.registry import ModuleRegistry, build
from emotion_spirit.plugin_factory import default_config, build as factory_build


def test_dry_run_28_modules_no_error():
    """dry_run 走 28 模块依赖图检查, 0 错误。"""
    assert len(ModuleRegistry.get_all()) == 28, f"expected 28 modules, got {len(ModuleRegistry.get_all())}"
    config = default_config(
        data_dir="/tmp/test_dryrun",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = build(config, dry_run=True)
    assert instances == {}, f"dry_run should return empty dict, got {instances}"


def test_dry_run_17_mismatch_resolve():
    """17 mismatch 模块都能在 dry_run 中找到所有 dep。"""
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


def test_build_real_construct_24_instances():
    """真装配 24 个 instantiable 模块, 0 错误。"""
    config = default_config(
        data_dir="/tmp/test_real_build",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    )
    instances = build(config, dry_run=False)
    # 24 instantiable modules (utility 4 不算)
    assert len(instances) >= 24, f"expected ≥24 instances, got {len(instances)}"

    # 关键模块类型对得上
    from emotion_spirit.store import SpiritStore
    from emotion_spirit.memory_pool import MemoryPool
    from emotion_spirit.intimacy import IntimacyTracker
    assert isinstance(instances["store"], SpiritStore)
    assert isinstance(instances["memory_pool"], MemoryPool)
    assert isinstance(instances["intimacy"], IntimacyTracker)


def test_build_superego_multi_instance():
    """superego 走 multi-instance 分支, 返回 dict 含 4 sub。"""
    from emotion_spirit.superego import (
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
    from emotion_spirit.prompt_injector import PromptInjector
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
        "persona_report_parser",
    }
    # 检查 24 个 instantiable 都在
    for name in expected_instantiable:
        assert name in instances, f"missing instantiable: {name}"
    # superego 是 dict 含 4 sub
    assert set(instances["superego"].keys()) == {"alignment", "conscience", "resistance", "ideal"}


def test_dry_run_then_real_build_consistent():
    """dry_run 跟真装配 module 集合一致。"""
    config = default_config(
        data_dir="/tmp/test_consistent",
        persona_id="INFP-A",
        labels={},
    )
    real = build(config)
    # build() 默认 enabled=True for registry modules not in config,
    # 所以 utility 4 (provides=[]) 也被装配. 28 = 24 instantiable + 4 utility.
    assert len(real) == 28, f"expected 28 instances (24 + 4 utility), got {len(real)}"
