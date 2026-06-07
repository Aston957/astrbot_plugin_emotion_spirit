"""Tests for plugin_factory (Phase B, P3-1 main.py 拆分)。

plugin_factory.build() 装配 28 模块, 返回 dict[name, instance]。
走 ModuleRegistry + 手动装配 (混合) 因为 registry 还在演进中。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_plugin_factory_build_returns_requested_modules():
    """plugin_factory.build() 返回 dict 包含所有 requested enabled 模块。"""
    from emotion_spirit.plugin_factory import build, default_config

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
    config["modules"]["knowledge"]["enabled"] = False
    config["modules"]["persona_report_parser"]["enabled"] = False
    config["modules"]["superego"]["enabled"] = False
    config["modules"]["superego_guard"]["enabled"] = False
    config["modules"]["meaning_reservoir"]["enabled"] = False
    config["modules"]["personality_drift"]["enabled"] = False
    config["modules"]["relationship_personality"]["enabled"] = False
    modules = build(config)
    assert "store" in modules
    assert "memory_pool" in modules
    assert "intimacy" in modules


def test_plugin_factory_can_disable_module():
    """config 中 enabled=False 跳过该模块。"""
    from emotion_spirit.plugin_factory import build, default_config

    config = default_config(data_dir="/tmp/test_pf_2", persona_id="INFP-A", labels={})
    config["modules"]["bot_decision"]["enabled"] = False
    modules = build(config)
    assert "bot_decision" not in modules
    # 启用的还在
    assert "store" in modules


def test_plugin_factory_default_config_lists_all_24():
    """default_config() 列出 24 个有 provides 的模块 (utility 4 不在内)。"""
    from emotion_spirit.plugin_factory import default_config

    cfg = default_config(data_dir="data")
    enabled = [name for name, m in cfg["modules"].items() if m.get("enabled", True)]
    # 24 = 28 - 4 utility (emotion_classifier/label_mapper/persona_profiles/trend_utils)
    # utility 模块 provides=[] (纯算法/工具), 不应由 factory 装配.
    # main.py 实际启用的子集 (19) 不影响此处: factory 默认装配所有 24 个有 provides 的模块,
    # 调用方可按需禁用 (e.g. bot_decision) 而不破坏工厂契约.
    assert len(enabled) == 24
    # utility 模块不应在 enabled (它们 provides=[])
    assert "emotion_classifier" not in enabled
    assert "label_mapper" not in enabled
    assert "persona_profiles" not in enabled
    assert "trend_utils" not in enabled


def test_plugin_factory_passes_data_dir_to_store():
    """data_dir 参数传给 SpiritStore。"""
    from emotion_spirit.plugin_factory import build, default_config

    config = default_config(data_dir="/tmp/test_emotion_spirit_data", persona_id="INFP-A", labels={})
    modules = build(config)
    store = modules["store"]
    # SpiritStore 内部应使用 data_dir
    assert str(store._dir) == "/tmp/test_emotion_spirit_data" or str(store._dir).endswith("test_emotion_spirit_data")


def test_plugin_factory_builds_superego_components():
    """superego 模块分解为 4 sub-components (alignment/conscience/resistance/ideal)。"""
    from emotion_spirit.plugin_factory import build, default_config

    config = default_config(data_dir="data", persona_id="test_persona", labels={})
    modules = build(config)
    # superego 应有 alignment/conscience/resistance/ideal sub-keys
    assert "superego" in modules
    se = modules["superego"]
    assert "alignment" in se
    assert "conscience" in se
    assert "resistance" in se
    assert "ideal" in se
