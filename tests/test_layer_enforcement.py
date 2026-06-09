"""Tests for 4-layer enforcement (Phase B, P3-3 A+集成测试)。

装饰器 + 集成测试, 覆盖 90% 漏检率, 比纯 A 强, 比 mypy B 便宜。
"""

import sys
import os
from dataclasses import dataclass, field

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══ 单元测试: per_user_only 装饰器 ═══

def test_per_user_only_requires_user_id():
    """漏传 user_id → 抛 TypeError。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str) -> float:
            return 0.5

    with pytest.raises(TypeError, match="requires user_id"):
        Fake().get()


def test_per_user_only_rejects_empty_user_id():
    """user_id="" → 抛。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str):
            return user_id

    with pytest.raises(TypeError, match="user_id"):
        Fake().get(user_id="")


def test_per_user_only_rejects_none_user_id():
    """user_id=None → 抛。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str):
            return user_id

    with pytest.raises(TypeError, match="user_id"):
        Fake().get(user_id=None)


def test_per_user_only_rejects_non_string_user_id():
    """user_id=42 (int) → 抛 (类型校验)。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str):
            return user_id

    with pytest.raises(TypeError, match="user_id"):
        Fake().get(user_id=42)


def test_per_user_only_accepts_positional_user_id():
    """位置参数 user_id 也接受 (向后兼容现有 caller)。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str, persona: str = "default") -> float:
            return 0.5

    # 位置参数 (现有 caller 风格)
    assert Fake().get("alice", "xiaofu") == 0.5


def test_per_user_only_accepts_kwarg_user_id():
    """kwargs user_id 也接受。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str, persona: str = "default") -> float:
            return 0.7

    assert Fake().get(user_id="alice") == 0.7


def test_per_user_only_preserves_other_args():
    """装饰器不影响其他参数 (persona) 透传。"""
    from emotion_spirit.layer import per_user_only

    class Fake:
        @per_user_only
        def get(self, user_id: str, persona: str = "default", other: int = 0):
            return (user_id, persona, other)

    assert Fake().get("alice", "bob", 42) == ("alice", "bob", 42)
    assert Fake().get(user_id="alice", persona="bob", other=99) == ("alice", "bob", 99)


# ═══ 单元测试: global_only 装饰器 ═══

def test_global_only_rejects_user_id_param():
    """@global_only 装饰的方法定义时不能有 user_id 参数 → 抛。"""
    from emotion_spirit.layer import global_only

    with pytest.raises(TypeError, match="is global-only"):

        class Bad:
            @global_only
            def bad(self, user_id: str):
                pass


def test_global_only_allows_no_user_id():
    """@global_only 装饰的方法没有 user_id 参数 → 正常。"""
    from emotion_spirit.layer import global_only

    class Good:
        @global_only
        def fine(self) -> dict:
            return {"pressure": 0.5}

    g = Good()
    assert g.fine() == {"pressure": 0.5}


def test_global_only_rejects_user_id_as_kwarg_only():
    """@global_only 装饰的方法即使只把 user_id 做成 kwarg-only 也抛。"""
    from emotion_spirit.layer import global_only

    with pytest.raises(TypeError, match="is global-only"):

        class BadKwarg:
            @global_only
            def bad(self, *, user_id: str):
                pass


# ═══ 集成测试: IntimacyTracker 强制 user_id ═══

def test_intimacy_get_intimacy_requires_user_id():
    """IntimacyTracker.get_intimacy (Layer 2) 强制 user_id。"""
    from emotion_spirit.memory.intimacy import IntimacyTracker
    tracker = IntimacyTracker()
    with pytest.raises(TypeError, match="requires user_id"):
        tracker.get_intimacy()


def test_intimacy_get_segment_requires_user_id():
    """IntimacyTracker.get_segment (Layer 2) 强制 user_id。"""
    from emotion_spirit.memory.intimacy import IntimacyTracker
    tracker = IntimacyTracker()
    with pytest.raises(TypeError, match="requires user_id"):
        tracker.get_segment()


def test_intimacy_get_relationship_tone_requires_user_id():
    """IntimacyTracker.get_relationship_tone (Layer 2) 强制 user_id。"""
    from emotion_spirit.memory.intimacy import IntimacyTracker
    tracker = IntimacyTracker()
    with pytest.raises(TypeError, match="requires user_id"):
        tracker.get_relationship_tone()


def test_intimacy_get_lifecycle_requires_user_id():
    """IntimacyTracker.get_lifecycle (Layer 2) 强制 user_id。"""
    from emotion_spirit.memory.intimacy import IntimacyTracker
    tracker = IntimacyTracker()
    with pytest.raises(TypeError, match="requires user_id"):
        tracker.get_lifecycle()


def test_intimacy_get_intimacy_accepts_user_id():
    """get_intimacy(user_id) 正常工作 (向后兼容)。"""
    from emotion_spirit.memory.intimacy import IntimacyTracker
    tracker = IntimacyTracker()
    score = tracker.get_intimacy("alice")
    assert 0.0 <= score <= 1.0


# ═══ 集成测试: ConscienceTracker / PersonalityDrift 强制 global ═══

def test_conscience_get_pressure_breakdown_is_global():
    """ConscienceTracker.get_pressure_breakdown 是 global_only, 不接受 user_id。"""
    from emotion_spirit.regulation.superego import ConscienceTracker
    ct = ConscienceTracker()
    breakdown = ct.get_pressure_breakdown()
    assert "pressure" in breakdown
    assert "by_type" in breakdown
    assert "alignment_relief_24h" in breakdown
    assert "dominant_tension" in breakdown


def test_personality_drift_update_is_global():
    """PersonalityDrift.update 是 global_only, 不接受 user_id。"""
    from emotion_spirit.regulation.personality_drift import PersonalityDrift

    # 类定义已成功 (global_only 在 import 时检查)
    # update 方法签名确认无 user_id
    import inspect
    sig = inspect.signature(PersonalityDrift.update)
    assert "user_id" not in sig.parameters


# ═══ 集成测试: 跨层访问保护 ═══

def test_layer_violation_error_is_runtime_error():
    """LayerViolationError 是 RuntimeError 子类。"""
    from emotion_spirit.layer import LayerViolationError
    assert issubclass(LayerViolationError, RuntimeError)
    # 可正常 raise + catch
    with pytest.raises(LayerViolationError):
        raise LayerViolationError("test")


def test_layer_2_has_no_layer_3_reference():
    """关系层 IntimacyTracker 不持有 Layer 3 (ConscienceTracker) 引用。

    架构层强制: Layer 2 不知道 Layer 3 内部状态。
    """
    from emotion_spirit.memory.intimacy import IntimacyTracker
    intimacy = IntimacyTracker()
    # 关键: 不允许 _conscience 字段
    assert not hasattr(intimacy, "_conscience")
    # 其他 Layer 3 模块名
    for forbidden in ("_superego", "conscience", "_value_resistance"):
        assert not hasattr(intimacy, forbidden), (
            f"IntimacyTracker 不应持有 {forbidden} 引用"
        )


# ═══ 集成测试: 现有 caller 不漏传 user_id (回归保护) ═══

def test_phase25_integration_caller_style():
    """现有 Phase 2.5 caller 风格 (位置参数) 仍工作。"""
    from emotion_spirit.memory.intimacy import IntimacyTracker
    tracker = IntimacyTracker()
    # 模拟 test_phase25_integration.py 的用法
    seg = tracker.get_segment("alice")
    tone = tracker.get_relationship_tone("alice")
    assert seg in ("stranger", "acquaintance", "friend", "inner_circle")
    assert isinstance(tone, dict)
