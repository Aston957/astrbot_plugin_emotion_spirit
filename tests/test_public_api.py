"""Tests for public_api 3 APIs (Phase B, P3-1 main.py 拆分)。

PublicAPI 暴露 3 个公开 API: get_emotion_state, get_body_state, get_emotion_trajectory。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_public_api_get_emotion_state_returns_dict():
    """get_emotion_state 返回 11 字段 dict。"""
    from emotion_spirit.output.public_api import PublicAPI

    # Mock signals
    class MockSignals:
        pad_valence = 0.7
        pad_arousal = 0.3
        pad_dominance = 0.5
        pad_primary = "joy"
        pad_secondary = "satisfaction"
        pad_distribution = {"joy": 0.6, "neutral": 0.4}
        pad_intensity = 0.8
        pad_label = "joy"
        emotion_ambiguity = 0.2
        emotion_velocity = {"valence": 0.1, "arousal": 0.0, "dominance": 0.0, "dt": 1.0}
        emotion_trajectory = [(0.7, 0.3, 0.5, 1234567890.0)]

    class MockSurfaceConsumer:
        def consume_for_session(self, session_key):
            return MockSignals()

    modules = {"surface_consumer": MockSurfaceConsumer()}
    api = PublicAPI(modules)

    import asyncio
    state = asyncio.run(api.get_emotion_state("test_session"))
    assert state is not None
    assert state["pad_valence"] == 0.7
    assert state["pad_primary"] == "joy"
    assert "emotion_ambiguity" in state
    assert "emotion_velocity" in state
    # 默认 include_trajectory=False, 不应包含
    assert "emotion_trajectory" not in state


def test_public_api_get_emotion_state_with_trajectory():
    """include_trajectory=True 时返回 trajectory 字段。"""
    from emotion_spirit.output.public_api import PublicAPI

    class MockSignals:
        pad_valence = 0.7
        pad_arousal = 0.3
        pad_dominance = 0.5
        pad_primary = "joy"
        pad_secondary = "satisfaction"
        pad_distribution = {"joy": 0.6, "neutral": 0.4}
        pad_intensity = 0.8
        pad_label = "joy"
        emotion_ambiguity = 0.2
        emotion_velocity = {"valence": 0.1, "arousal": 0.0, "dominance": 0.0, "dt": 1.0}
        emotion_trajectory = [(0.7, 0.3, 0.5, 1234567890.0)]

    class MockSurfaceConsumer:
        def consume_for_session(self, session_key):
            return MockSignals()

    modules = {"surface_consumer": MockSurfaceConsumer()}
    api = PublicAPI(modules)

    import asyncio
    state = asyncio.run(api.get_emotion_state("test_session", include_trajectory=True))
    assert state is not None
    assert "emotion_trajectory" in state
    assert len(state["emotion_trajectory"]) == 1
    assert state["emotion_trajectory"][0]["valence"] == 0.7


def test_public_api_get_body_state_returns_dict():
    """get_body_state 返回 4 字段身体状态 dict。"""
    from emotion_spirit.output.public_api import PublicAPI

    class MockSignals:
        pad_valence = 0.7
        pad_arousal = 0.3
        pad_dominance = 0.5
        pad_primary = "joy"
        pad_label = "joy"
        valence_warmth = 0.65
        connection_circulation = 0.55
        needs_expression = 0.45
        valence_repair_heat = 0.35

    class MockSurfaceConsumer:
        def consume_for_session(self, session_key):
            return MockSignals()

    modules = {"surface_consumer": MockSurfaceConsumer()}
    api = PublicAPI(modules)

    import asyncio
    state = asyncio.run(api.get_body_state("test_session"))
    assert state is not None
    assert state["pad_valence"] == 0.7
    assert state["pad_label"] == "joy"
    # body state 字段
    assert state["warmth"] == 0.65
    assert state["pulse"] == 0.55
    assert state["expression"] == 0.45
    assert state["repair"] == 0.35


def test_public_api_returns_none_when_no_signals():
    """session_key 无 signals 时返回 None。"""
    from emotion_spirit.output.public_api import PublicAPI

    class MockSurfaceConsumer:
        def consume_for_session(self, session_key):
            return None

    modules = {"surface_consumer": MockSurfaceConsumer()}
    api = PublicAPI(modules)

    import asyncio
    state = asyncio.run(api.get_emotion_state("unknown_session"))
    assert state is None

    state = asyncio.run(api.get_body_state("unknown_session"))
    assert state is None


def test_public_api_returns_none_when_no_surface_consumer():
    """modules 中无 surface_consumer 时返回 None。"""
    from emotion_spirit.output.public_api import PublicAPI

    modules: dict = {}  # 没有 surface_consumer
    api = PublicAPI(modules)

    import asyncio
    state = asyncio.run(api.get_emotion_state("any_session"))
    assert state is None
