"""Tests for config.py"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.config import (
    MEMORY_POOL_CONFIG,
    INTIMACY_CONFIG,
    EMA_ALPHA,
    BUFFER_POOL_CONFIG,
    SUPEREGO_CONFIG,
)


def test_buffer_pool_config():
    assert BUFFER_POOL_CONFIG["max"] == 30
    assert BUFFER_POOL_CONFIG["ttl_hours"] == 24
    assert BUFFER_POOL_CONFIG["confirm_phi_threshold"] == 0.4
    assert 0 < BUFFER_POOL_CONFIG["meaning_gate_base"] < 1
    assert 0 < BUFFER_POOL_CONFIG["meaning_gate_phi_weight"] < 1


def test_memory_pool_config():
    assert MEMORY_POOL_CONFIG["warm_max"] == 500
    assert MEMORY_POOL_CONFIG["cold_max"] == 2000
    assert MEMORY_POOL_CONFIG["ghost_max"] == 50
    assert MEMORY_POOL_CONFIG["warm_to_cold_ttl_hours"] == 240


def test_intimacy_weights_sum():
    weights = INTIMACY_CONFIG["weights"]
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"weights sum to {total}"


def test_ema_alpha():
    assert 0 < EMA_ALPHA["phi"] < 1
    assert 0 < EMA_ALPHA["chi"] < 1
    assert 0 < EMA_ALPHA["sync_order"] < 1


def test_superego_config():
    assert "resistance_context_modifiers" in SUPEREGO_CONFIG
    assert "tension_type_weights" in SUPEREGO_CONFIG
    assert SUPEREGO_CONFIG["guard_reflex_conscience_multiplier"] == 0.30
    assert SUPEREGO_CONFIG["cascade_conscience_multiplier"] == 0.50
    assert SUPEREGO_CONFIG["alignment_base_relief"] == 0.12  # v2: ACT guilt value-orienting signal
    assert SUPEREGO_CONFIG["pressure_decay_rate_per_hour"] == 0.08  # v2: Roberts 元分析; 半衰期≈8.3h
    assert "simple" in SUPEREGO_CONFIG["repair_relief"]
    assert SUPEREGO_CONFIG["reinforcement_rate"] == 0.01


if __name__ == "__main__":
    test_buffer_pool_config()
    test_memory_pool_config()
    test_intimacy_weights_sum()
    test_ema_alpha()
    test_superego_config()
    print("All config tests passed!")
