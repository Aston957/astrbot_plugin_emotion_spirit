"""PersonalityBridge 测试。"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.bridge.personality_bridge import PersonalityBridge


class TestPersonalityBridge:
    def test_map_5d_to_12d_basic(self):
        emb = {
            "expression_drive": 0.7,
            "perception_acuity": 0.6,
            "boundary_permeability": 0.5,
            "inner_coherence": 0.8,
            "relational_gravity": 0.4,
        }
        result = PersonalityBridge.map_5d_to_12d(emb)
        assert result["perception_acuity"] == 0.6
        assert result["boundary_permeability"] == 0.5
        assert result["inner_coherence"] == 0.8
        assert result["relational_gravity"] == 0.4
        assert "relational_autonomy" in result
        assert "exploration_openness" in result
        assert 0.0 <= result["relational_autonomy"] <= 1.0
        assert 0.0 <= result["exploration_openness"] <= 1.0

    def test_map_5d_to_12d_defaults(self):
        result = PersonalityBridge.map_5d_to_12d({})
        assert result["perception_acuity"] == 0.5

    def test_map_5d_to_12d_clamping(self):
        extreme = {"expression_drive": 2.0, "perception_acuity": -1.0}
        result = PersonalityBridge.map_5d_to_12d(extreme)
        for v in result.values():
            assert 0.0 <= v <= 1.0

    def test_map_12d_to_5d_basic(self):
        p12d = {
            "relational_autonomy": 0.8,
            "exploration_openness": 0.6,
            "perception_acuity": 0.5,
            "boundary_permeability": 0.4,
            "inner_coherence": 0.7,
            "relational_gravity": 0.3,
        }
        result = PersonalityBridge.map_12d_to_5d(p12d)
        assert result["perception_acuity"] == 0.5
        assert result["boundary_permeability"] == 0.4
        assert "expression_drive" in result

    def test_map_12d_to_5d_uses_surface_expression_drive(self):
        p12d = {"expression_drive": 0.9, "relational_autonomy": 0.2, "exploration_openness": 0.3}
        result = PersonalityBridge.map_12d_to_5d(p12d)
        assert result["expression_drive"] == 0.9

    def test_roundtrip_consistency(self):
        original = {
            "expression_drive": 0.6,
            "perception_acuity": 0.7,
            "boundary_permeability": 0.4,
            "inner_coherence": 0.8,
            "relational_gravity": 0.3,
        }
        p12d = PersonalityBridge.map_5d_to_12d(original)
        back = PersonalityBridge.map_12d_to_5d(p12d)
        assert abs(back["perception_acuity"] - original["perception_acuity"]) < 0.01
        assert abs(back["boundary_permeability"] - original["boundary_permeability"]) < 0.01
        assert abs(back["inner_coherence"] - original["inner_coherence"]) < 0.01
        assert abs(back["relational_gravity"] - original["relational_gravity"]) < 0.01

    def test_merge_deep_surface(self):
        deep = {"relational_autonomy": 0.8, "perception_acuity": 0.6}
        surface = {"warmth_bias": 0.7, "expression_drive": 0.5}
        merged = PersonalityBridge.merge_deep_surface(deep, surface)
        assert merged["relational_autonomy"] == 0.8
        assert merged["warmth_bias"] == 0.7

    def test_merge_deep_surface_overrides(self):
        deep = {"perception_acuity": 0.3}
        surface = {"perception_acuity": 0.9}
        merged = PersonalityBridge.merge_deep_surface(deep, surface)
        assert merged["perception_acuity"] == 0.9
