"""Tests for RelationshipPersonality (Phase 2.5 Step 1).

理论依据: Bowlby 内部工作模型 per-relationship
- 同一个 bot 对不同 user 可以有不同"面"
- 11 维 base personality 不变, per-user delta 累加
- 每次读时合成 effective_personality (base + delta_for_user)

API:
- get_delta(user_id) → dict[dim, delta_value]
- set_delta(user_id, dim, value) → 累加 (或按 dim 策略)
- apply_to(base_personality, user_id) → effective_personality
- 序列化: to_dict / from_dict
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.relationship_personality import RelationshipPersonality


# ═══ 基础 API ═══

def test_get_delta_default_empty():
    """新 user 的 delta 应为空 (无微调)。"""
    rp = RelationshipPersonality()
    delta = rp.get_delta("alice")
    assert delta == {}


def test_set_and_get_delta_single_dim():
    """set_delta + get_delta 应返回该 dim 的值。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.1)
    assert rp.get_delta("alice")["warmth"] == 0.1


def test_set_delta_accumulates():
    """同 dim 多次 set 应累加 (非覆盖)。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.05)
    rp.set_delta("alice", "warmth", 0.05)
    assert abs(rp.get_delta("alice")["warmth"] - 0.1) < 1e-9


def test_set_delta_clamped_to_range():
    """delta 范围 [-0.3, 0.3]: 微调不应剧烈改变人格。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.5)  # 超出上限
    delta = rp.get_delta("alice")["warmth"]
    assert delta <= 0.3
    rp.set_delta("alice", "expression_drive", -0.5)  # 超出下限
    assert rp.get_delta("alice")["expression_drive"] >= -0.3


# ═══ per-user 隔离 ═══

def test_per_user_delta_isolation():
    """alice 的 delta 不影响 bob。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.2)
    rp.set_delta("bob", "warmth", -0.1)
    assert rp.get_delta("alice")["warmth"] == 0.2
    assert rp.get_delta("bob")["warmth"] == -0.1


def test_multiple_dims_per_user():
    """一个 user 可以有多个 dim 的 delta。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.1)
    rp.set_delta("alice", "expression_drive", -0.05)
    rp.set_delta("alice", "intimacy_pull", 0.15)
    delta = rp.get_delta("alice")
    assert delta["warmth"] == 0.1
    assert delta["expression_drive"] == -0.05
    assert delta["intimacy_pull"] == 0.15


# ═══ apply_to (合成 effective personality) ═══

def test_apply_to_combines_base_and_delta():
    """apply_to(base, user_id) 应返回 base + delta 的合成。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.2)
    base = {"personality": {"warmth": {"baseline": 0.5, "current": 0.5}}}
    effective = rp.apply_to(base, "alice")
    # current = 0.5 + 0.2 = 0.7
    assert effective["personality"]["warmth"]["current"] == 0.7
    # baseline 不被修改
    assert effective["personality"]["warmth"]["baseline"] == 0.5


def test_apply_to_no_delta_returns_base_unchanged():
    """无 delta 时, effective 应等于 base (无副作用)。"""
    rp = RelationshipPersonality()
    base = {"personality": {"warmth": {"baseline": 0.5, "current": 0.5}}}
    effective = rp.apply_to(base, "unknown_user")
    assert effective == base


def test_apply_to_does_not_mutate_base():
    """apply_to 必须返回新 dict, 不能修改 base。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.2)
    base = {"personality": {"warmth": {"baseline": 0.5, "current": 0.5}}}
    base_copy = {"personality": {"warmth": {"baseline": 0.5, "current": 0.5}}}
    _ = rp.apply_to(base, "alice")
    # base 不变
    assert base == base_copy


def test_apply_to_clamps_current_to_0_1():
    """apply 后的 current 应 clamp 到 [0, 1]。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.3)
    base = {"personality": {"warmth": {"baseline": 0.9, "current": 0.9}}}
    effective = rp.apply_to(base, "alice")
    # 0.9 + 0.3 = 1.2 → clamp 到 1.0
    assert effective["personality"]["warmth"]["current"] == 1.0


# ═══ 序列化 ═══

def test_serialization_round_trip():
    """to_dict + from_dict 保留所有 user 的 delta。"""
    rp1 = RelationshipPersonality()
    rp1.set_delta("alice", "warmth", 0.15)
    rp1.set_delta("bob", "expression_drive", -0.1)
    data = rp1.to_dict()

    rp2 = RelationshipPersonality.from_dict(data)
    assert rp2.get_delta("alice")["warmth"] == 0.15
    assert rp2.get_delta("bob")["expression_drive"] == -0.1


# ═══ 调整 delta (反向操作) ═══

def test_adjust_delta_for_unspecified_user():
    """get_delta 返回的 dict 是 copy, 修改不影响内部状态。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth", 0.1)
    d1 = rp.get_delta("alice")
    d1["warmth"] = 0.5  # 修改 copy
    d2 = rp.get_delta("alice")
    # 内部状态不变
    assert d2["warmth"] == 0.1


if __name__ == "__main__":
    test_get_delta_default_empty()
    test_set_and_get_delta_single_dim()
    test_set_delta_accumulates()
    test_set_delta_clamped_to_range()
    test_per_user_delta_isolation()
    test_multiple_dims_per_user()
    test_apply_to_combines_base_and_delta()
    test_apply_to_no_delta_returns_base_unchanged()
    test_apply_to_does_not_mutate_base()
    test_apply_to_clamps_current_to_0_1()
    test_serialization_round_trip()
    test_adjust_delta_for_unspecified_user()
    print("All RelationshipPersonality tests passed!")
