"""Tests for split_llm_tier migration (v3→v4)."""
import copy
import pytest

from emotion_spirit.migrations.registry import reset_registry, get_latest_version

# 必须在 import rule 之后 registry 才有内容
from emotion_spirit.migrations.rules.v3_0_to_v3_1 import split_llm_tier


# 故意不设 autouse reset_registry fixture:
# 本文件的 test 全部调 split_llm_tier 函数 (直接 import, 走函数体不走 registry),
# 不需要 reset. 如果 reset 了, 反倒让后续 test (e.g. test_integration.py)
# 看不见 v3_0_to_v3_1 的 @register_migration 注册, runner 跑不出 split_life_simulator_modes.


class TestSplitLlmTier:
    """split_llm_tier: llm_tier → 各功能段 + diary_schedule → diary."""

    def test_full_llm_tier_migrates_to_new_sections(self):
        """完整 llm_tier 配置 → 正确分发到 4 个新段。"""
        config = {
            "llm_tier": {
                "engine_provider_id": "provider_a",
                "life_sim_provider_id": "provider_b",
                "analyzer_provider_id": "provider_c",
                "dream_provider_id": "provider_d",
                "reflection_provider_id": "provider_e",
            }
        }
        result = split_llm_tier(copy.deepcopy(config))

        assert result["sylanne"]["engine_provider_id"] == "provider_a"
        assert result["sylanne"]["analyzer_provider_id"] == "provider_c"
        assert result["life_sim_v2"]["life_sim_provider_id"] == "provider_b"
        assert result["dream"]["dream_provider_id"] == "provider_d"
        assert result["diary"]["diary_provider_id"] == "provider_e"
        assert "llm_tier" not in result

    def test_empty_llm_tier_no_empty_sections(self):
        """空 llm_tier → 不创建空段。"""
        config = {"llm_tier": {}}
        result = split_llm_tier(copy.deepcopy(config))

        # llm_tier 删除了（即使空的也删）
        assert "llm_tier" not in result
        # 不应创建空的 sylanne 段 (因为没迁任何值)
        assert "sylanne" not in result or not result.get("sylanne", {})

    def test_diary_schedule_merges_into_diary(self):
        """diary_schedule.schedule_hours → diary.schedule_hours + 旧段删除。"""
        config = {
            "diary_schedule": {"schedule_hours": "10,18"},
        }
        result = split_llm_tier(copy.deepcopy(config))

        assert result["diary"]["schedule_hours"] == "10,18"
        assert "diary_schedule" not in result
        assert result["diary"]["enable_diary_llm"] is False

    def test_idempotent(self):
        """跑两次结果一致。"""
        config = {
            "llm_tier": {
                "engine_provider_id": "p1",
                "dream_provider_id": "p2",
            },
            "diary_schedule": {"schedule_hours": "14,22"},
        }
        first = split_llm_tier(copy.deepcopy(config))
        second = split_llm_tier(copy.deepcopy(first))

        assert first == second

    def test_reflection_maps_to_diary_provider(self):
        """reflection_provider_id → diary.diary_provider_id 映射。"""
        config = {
            "llm_tier": {
                "reflection_provider_id": "cheap_model",
            }
        }
        result = split_llm_tier(copy.deepcopy(config))

        assert result["diary"]["diary_provider_id"] == "cheap_model"
        assert "llm_tier" not in result

    def test_partial_config_only_migrates_existing_keys(self):
        """部分配置（只有 engine_provider_id）→ 只迁存在的键。"""
        config = {
            "llm_tier": {
                "engine_provider_id": "p_engine",
            }
        }
        result = split_llm_tier(copy.deepcopy(config))

        assert result["sylanne"]["engine_provider_id"] == "p_engine"
        # analyzer 没迁过来（源不存在）
        assert "analyzer_provider_id" not in result.get("sylanne", {})
        # life_sim_v2 / dream / diary 没创建空段
        assert "life_sim_provider_id" not in result.get("life_sim_v2", {})
        assert "dream_provider_id" not in result.get("dream", {})

    def test_no_llm_tier_no_diary_schedule(self):
        """没有任何旧字段 → diary 段仍创建默认值。"""
        config = {}
        result = split_llm_tier(copy.deepcopy(config))

        assert result["diary"]["enable_diary_llm"] is False
        assert "llm_tier" not in result
        assert "diary_schedule" not in result
