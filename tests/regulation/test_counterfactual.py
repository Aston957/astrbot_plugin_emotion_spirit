"""Tests for counterfactual.py"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.memory_pool import MemoryPool, MemoryEntry
from emotion_spirit.regulation.counterfactual import Counterfactual


def test_ghost_decay():
    pool = MemoryPool()
    # Add a ghost with high sensitivity
    ghost = MemoryEntry(
        id="ghost_0", text="hurt", emotional_weight=0.9,
        phi_at_creation=0.5, tags=["hurt"], tier="ghost",
        is_ghost=True, ghost_sensitivity_shift=0.5,
    )
    pool.ghosts.append(ghost)

    cf = Counterfactual(pool)
    digested = cf.check_ghost_decay(repair_count=3)
    # sensitivity_shift *= (1 - 3 * 0.1) = 0.5 * 0.7 = 0.35 > 0.05, not digested
    assert len(digested) == 0
    assert ghost.ghost_sensitivity_shift < 0.5  # Reduced


def test_ghost_fully_digested():
    pool = MemoryPool()
    ghost = MemoryEntry(
        id="ghost_0", text="old hurt", emotional_weight=0.5,
        phi_at_creation=0.5, tags=["hurt"], tier="ghost",
        is_ghost=True, ghost_sensitivity_shift=0.04,
    )
    pool.ghosts.append(ghost)

    cf = Counterfactual(pool)
    digested = cf.check_ghost_decay(repair_count=1)
    # 0.04 * (1 - 0.1) = 0.036 < 0.05 → digested
    assert len(digested) == 1
    assert len(pool.ghosts) == 0
    assert len(pool.cold) == 1


def test_ghost_resonance():
    pool = MemoryPool()
    ghost = MemoryEntry(
        id="ghost_0", text="hurt", emotional_weight=0.8,
        phi_at_creation=0.5, tags=["hurt", "betrayal"], tier="ghost",
        is_ghost=True,
    )
    pool.ghosts.append(ghost)

    cf = Counterfactual(pool)
    new_entry = MemoryEntry(
        id="new_0", text="new hurt", emotional_weight=0.5,
        phi_at_creation=0.5, tags=["hurt"],
    )
    boost = cf.ghost_resonance(new_entry)
    assert boost > 0  # "hurt" overlaps


def test_ghost_resonance_no_match():
    pool = MemoryPool()
    ghost = MemoryEntry(
        id="ghost_0", text="hurt", emotional_weight=0.8,
        phi_at_creation=0.5, tags=["hurt"], tier="ghost",
        is_ghost=True,
    )
    pool.ghosts.append(ghost)

    cf = Counterfactual(pool)
    new_entry = MemoryEntry(
        id="new_0", text="happy", emotional_weight=0.5,
        phi_at_creation=0.5, tags=["joy"],
    )
    boost = cf.ghost_resonance(new_entry)
    assert boost == 0  # No overlap


def test_serialization():
    pool = MemoryPool()
    cf = Counterfactual(pool)
    cf.record_counterfactual("ghost_0", {"earlier": "test", "different": "test", "witness": "test"})
    data = cf.to_dict()
    cf2 = Counterfactual(pool)
    cf2.from_dict(data)
    assert len(cf2._processed_ghosts) == 1


if __name__ == "__main__":
    test_ghost_decay()
    test_ghost_fully_digested()
    test_ghost_resonance()
    test_ghost_resonance_no_match()
    test_serialization()
    print("All counterfactual tests passed!")
