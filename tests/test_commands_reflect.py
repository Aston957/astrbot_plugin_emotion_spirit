"""tests/test_commands_reflect.py — /reflect_force_current + history tracking 测试 (v1.2.5 PR1 Task 10)."""

import sys
import os
import types
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.output.segmented_reply_coordinator import (
    SegmentedReplyCoordinator,
    SilenceTendency,
)


class TestGetHistoryEmpty:
    """空历史返回零统计."""

    def test_empty_history(self):
        coord = SegmentedReplyCoordinator()
        history = coord.get_history()
        assert history["silence_count_7d"] == 0
        assert history["silence_dominant_reason"] == "none"
        assert history["segment_count_7d"] == 0
        assert history["avg_segment_count"] == 0.0
        assert history["avg_delay_seconds"] == 0.0


class TestSilenceHistory:
    """沉默历史记录与统计."""

    def test_record_and_query(self):
        coord = SegmentedReplyCoordinator()
        tendency = SilenceTendency(score=0.7, reason="过载引发沉默倾向")
        coord.record_silence_event("user_a", tendency=tendency)
        coord.record_silence_event("user_a", tendency=tendency)
        coord.record_silence_event(
            "user_a",
            tendency=SilenceTendency(score=0.3, reason="能量耗尽引发沉默倾向"),
        )
        history = coord.get_history()
        assert history["silence_count_7d"] == 3
        assert history["silence_dominant_reason"] == "过载引发沉默倾向"

    def test_old_records_filtered(self):
        """超过 7 天的记录被过滤."""
        coord = SegmentedReplyCoordinator()
        old_tendency = SilenceTendency(score=0.5, reason="社交场合引发沉默倾向")
        # 直接注入过期条目
        coord._silence_history.append({
            "user_id": "user_b",
            "reason": "社交场合引发沉默倾向",
            "timestamp": time.time() - 8 * 24 * 3600,
        })
        coord.record_silence_event("user_b", tendency=old_tendency)
        history = coord.get_history()
        assert history["silence_count_7d"] == 1


class TestSegmentHistory:
    """分段历史记录与统计."""

    def test_record_and_query(self):
        coord = SegmentedReplyCoordinator()
        coord.record_segment_event("user_a", num_segments=3, total_delay=1.5)
        coord.record_segment_event("user_a", num_segments=5, total_delay=2.5)
        history = coord.get_history()
        assert history["segment_count_7d"] == 2
        assert abs(history["avg_segment_count"] - 4.0) < 0.01
        assert abs(history["avg_delay_seconds"] - 2.0) < 0.01

    def test_old_records_filtered(self):
        """超过 7 天的记录被过滤."""
        coord = SegmentedReplyCoordinator()
        coord._segment_history.append({
            "user_id": "user_b",
            "num_segments": 10,
            "total_delay": 5.0,
            "timestamp": time.time() - 8 * 24 * 3600,
            })
        coord.record_segment_event("user_b", num_segments=2, total_delay=0.5)
        history = coord.get_history()
        assert history["segment_count_7d"] == 1
        assert history["avg_segment_count"] == 2.0


class TestCombinedHistory:
    """混合沉默 + 分段统计."""

    def test_mixed_stats(self):
        coord = SegmentedReplyCoordinator()
        for i in range(5):
            coord.record_silence_event(
                f"user_{i}",
                tendency=SilenceTendency(score=0.6, reason="节奏张力引发沉默倾向"),
            )
        for i in range(3):
            coord.record_segment_event(
                f"user_{i}", num_segments=4, total_delay=1.2,
            )
        history = coord.get_history()
        assert history["silence_count_7d"] == 5
        assert history["segment_count_7d"] == 3
        assert history["silence_dominant_reason"] == "节奏张力引发沉默倾向"


class TestSerializationRoundTrip:
    """to_dict / from_dict 包含历史."""

    def test_roundtrip(self):
        coord = SegmentedReplyCoordinator()
        coord.record_silence_event(
            "user_x",
            tendency=SilenceTendency(score=0.8, reason="过载引发沉默倾向"),
        )
        coord.record_segment_event("user_x", num_segments=3, total_delay=0.9)
        data = coord.to_dict()
        assert "silence_history" in data
        assert "segment_history" in data
        assert len(data["silence_history"]) == 1
        assert len(data["segment_history"]) == 1

        coord2 = SegmentedReplyCoordinator()
        coord2.from_dict(data)
        assert len(coord2._silence_history) == 1
        assert len(coord2._segment_history) == 1