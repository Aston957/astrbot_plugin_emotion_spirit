"""RealtimeDispatch 测试。"""

import sys, os, types, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.output.realtime_dispatch import (
    RealtimeDispatch, DeliberateSilence, BreathingRhythmController,
    extract_first_sentence, segment_text, build_segmented_parts,
    build_resumption_hint, BreakpointStore, InterruptedBreakpoint,
)


class TestExtractFirstSentence:
    def test_chinese_period(self):
        assert extract_first_sentence("你好吗？我很好。") == "你好吗？"
    def test_chinese_exclamation(self):
        assert extract_first_sentence("太好了！谢谢。") == "太好了！"
    def test_newline(self):
        assert extract_first_sentence("第一行\n第二行") == "第一行"
    def test_no_delimiter(self):
        assert extract_first_sentence("没有标点的文本") == ""
    def test_empty(self):
        assert extract_first_sentence("") == ""
    def test_consecutive_punctuation(self):
        assert extract_first_sentence("真的吗？！我不信。") == "真的吗？！"


class TestSegmentText:
    def test_short_text(self):
        assert segment_text("短文本") == ["短文本"]
    def test_empty_text(self):
        assert segment_text("") == []
    def test_long_text(self):
        text = "第一句话。第二句话。第三句话。"
        result = segment_text(text, max_part_chars=20)
        assert len(result) >= 1


class TestBuildSegmentedParts:
    def test_single_part(self):
        parts = build_segmented_parts("短文本")
        assert len(parts) == 1
        assert parts[0]["delay_before_seconds"] == 0.0
    def test_multiple_parts(self):
        text = "第一段话。第二段话。第三段话。"
        parts = build_segmented_parts(text, max_part_chars=10)
        assert len(parts) >= 2
        assert parts[0]["delay_before_seconds"] == 0.0


class TestBuildResumptionHint:
    def test_no_hint_short_gap(self):
        assert build_resumption_hint(time.time() - 3600, time.time()) is None
    def test_hint_long_gap(self):
        hint = build_resumption_hint(time.time() - 10800, time.time())
        assert hint is not None


class TestDeliberateSilence:
    def test_hurt(self):
        ds = DeliberateSilence()
        silent, reason = ds.should_be_silent(-0.5, 0.8)
        assert silent and reason == "hurt"
    def test_digesting(self):
        ds = DeliberateSilence()
        silent, reason = ds.should_be_silent(0.3, 0.2, void_pressure=4.0)
        assert silent and reason == "digesting"
    def test_content(self):
        ds = DeliberateSilence()
        silent, reason = ds.should_be_silent(0.5, -0.6)
        assert silent and reason == "content"
    def test_not_silent(self):
        ds = DeliberateSilence()
        assert ds.should_be_silent(0.0, 0.3)[0] is False
    def test_minimal_response(self):
        ds = DeliberateSilence()
        assert ds.get_minimal_response("hurt") == "……"
        assert ds.get_minimal_response("digesting") is None


class TestBreathingRhythmController:
    def test_calm_pattern(self):
        bc = BreathingRhythmController()
        assert bc.select_pattern(0.1, 0.0) == "calm"
    def test_intense_pattern(self):
        bc = BreathingRhythmController()
        assert bc.select_pattern(0.7, 0.0) == "intense"
    def test_building_pattern(self):
        bc = BreathingRhythmController()
        assert bc.select_pattern(0.4, -0.3) == "building"
    def test_winding_pattern(self):
        bc = BreathingRhythmController()
        assert bc.select_pattern(0.1, 0.6) == "winding"
    def test_pattern_cycle(self):
        bc = BreathingRhythmController()
        factors = [bc.next_length_factor(0.1, 0.0) for _ in range(6)]
        assert factors[0] == factors[3]
    def test_serialization(self):
        bc = BreathingRhythmController()
        bc.next_length_factor(0.1, 0.0)
        data = bc.to_dict()
        bc2 = BreathingRhythmController()
        bc2.from_dict(data)
        assert bc2._current_pattern == bc._current_pattern


class TestBreakpointStore:
    def test_record_and_get(self):
        store = BreakpointStore()
        store.record("s1", "full", ["sent"], ["unsent"], reason="test")
        bp = store.get_latest("s1")
        assert bp.full_text == "full"
    def test_get_unsent_parts(self):
        store = BreakpointStore()
        store.record("s1", "full", ["p1"], ["p2", "p3"])
        assert store.get_unsent_parts("s1") == ["p2", "p3"]
    def test_clear(self):
        store = BreakpointStore()
        store.record("s1", "full", [], [])
        store.clear("s1")
        assert store.get_latest("s1") is None
    def test_serialization(self):
        store = BreakpointStore()
        store.record("s1", "full", ["s"], ["u"])
        data = store.to_dict()
        store2 = BreakpointStore()
        store2.from_dict(data)
        assert store2.get_latest("s1").full_text == "full"


class TestRealtimeDispatch:
    def test_segment_text(self):
        rd = RealtimeDispatch()
        assert rd.segment_text("短文本") == ["短文本"]
    def test_build_segmented_parts(self):
        rd = RealtimeDispatch()
        assert len(rd.build_segmented_parts("第一段。第二段。")) >= 1
    def test_extract_first_sentence(self):
        rd = RealtimeDispatch()
        assert rd.extract_first_sentence("你好？我好。") == "你好？"
    def test_interrupted_breakpoint(self):
        rd = RealtimeDispatch()
        rd.record_interrupted_reply_breakpoint("s1", "full", ["sent"], ["unsent"])
        assert rd.get_unsent_parts("s1") == ["unsent"]
        rd.clear_breakpoints("s1")
        assert rd.get_unsent_parts("s1") == []
    def test_resumption_hint(self):
        rd = RealtimeDispatch()
        assert rd.build_resumption_hint(time.time() - 3600, time.time()) is None
        assert rd.build_resumption_hint(time.time() - 10800, time.time()) is not None
    def test_deliberate_silence(self):
        rd = RealtimeDispatch()
        assert rd.should_be_silent(-0.5, 0.8)[0] is True
    def test_breathing(self):
        rd = RealtimeDispatch()
        assert 0.5 <= rd.next_length_factor(0.1, 0.0) <= 1.5
    def test_serialization(self):
        rd = RealtimeDispatch()
        rd.record_interrupted_reply_breakpoint("s1", "full", [], [])
        rd.next_length_factor(0.1, 0.0)
        data = rd.to_dict()
        rd2 = RealtimeDispatch()
        rd2.from_dict(data)
        assert rd2.get_latest_breakpoint("s1") is not None
