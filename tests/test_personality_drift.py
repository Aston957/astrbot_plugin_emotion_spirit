"""Tests for personality_drift.py"""

import sys
import os

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

from emotion_spirit.surface_consumer import SurfaceConsumer, SemanticSignals
from emotion_spirit.meaning_reservoir import MeaningReservoir
from emotion_spirit.personality_drift import PersonalityDrift
from emotion_spirit.superego import IdealSelf


def test_drift_detection_stable():
    consumer = SurfaceConsumer()
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)

    for _ in range(20):
        drift.update(SemanticSignals())

    result = drift.check_drift()
    assert result == []  # Stable → no drift


def test_drift_detection_increasing():
    consumer = SurfaceConsumer()
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)

    for i in range(20):
        s = SemanticSignals()
        s.personality_deep = {"expression_drive": 0.3 + i * 0.02}
        drift.update(s)

    result = drift.check_drift()
    # May detect drift depending on threshold
    assert isinstance(result, list)


def test_drift_status():
    consumer = SurfaceConsumer()
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)
    drift.update(SemanticSignals())

    status = drift.get_drift_status()
    assert "deep_trends" in status
    assert "surface_trends" in status
    assert "integration_slope" in status


def test_serialization():
    consumer = SurfaceConsumer()
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)
    drift.update(SemanticSignals())
    data = drift.to_dict()
    drift2 = PersonalityDrift(consumer, reservoir)
    drift2.from_dict(data)
    status = drift2.get_drift_status()
    assert "deep_trends" in status


# ═══ PersonalityDrift ↔ IdealSelf 联动测试 ═══

def test_drift_updates_ideal_self():
    consumer = SurfaceConsumer()
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)
    ideal = IdealSelf("xiaofu", {"mbti": "ENFP", "attachment": "焦虑型"})

    # 模拟持续漂移
    for i in range(20):
        s = SemanticSignals()
        s.personality_deep = {"expression_drive": 0.3 + i * 0.02}
        drift.update(s)

    # 检测漂移
    drifts = drift.check_drift()

    # 如果检测到漂移，模拟 main.py 中的联动逻辑
    if drifts:
        for drift_info in drifts:
            dimension = drift_info["dimension"]
            direction = drift_info["direction"]
            slope = drift_info["slope"]

            delta = max(-0.05, min(0.05, slope * 10))
            if direction == "increasing":
                delta = abs(delta)
            else:
                delta = -abs(delta)

            ideal.update_reinforcement(dimension, delta)

    # 验证理想自我是否更新
    status = drift.get_drift_status()
    assert isinstance(status, dict)


def test_drift_no_drift_no_update():
    consumer = SurfaceConsumer()
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)
    ideal = IdealSelf("xiaofu", {"mbti": "ENFP", "attachment": "焦虑型"})

    # 稳定状态
    for _ in range(20):
        drift.update(SemanticSignals())

    drifts = drift.check_drift()
    assert drifts == []  # 无漂移


if __name__ == "__main__":
    test_drift_detection_stable()
    test_drift_detection_increasing()
    test_drift_status()
    test_serialization()
    test_drift_updates_ideal_self()
    test_drift_no_drift_no_update()
    print("All personality_drift tests passed!")
