"""RhythmLearner 测试。"""

import sys, os, types, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.output.rhythm_learner import RhythmLearner, RhythmProfile


class TestRhythmProfile:
    def test_observe_short_text(self):
        p = RhythmProfile()
        p.observe("hi", time.time())
        assert len(p._msg_lengths) == 1
    def test_observe_empty_text(self):
        p = RhythmProfile()
        p.observe("", time.time())
        assert len(p._msg_lengths) == 0
    def test_confidence_below_minimum(self):
        p = RhythmProfile()
        for i in range(5):
            p.observe(f"msg {i}", time.time() + i)
        assert p.confidence == 0.0
    def test_confidence_above_minimum(self):
        p = RhythmProfile()
        for i in range(10):
            p.observe(f"message {i} content", time.time() + i * 2)
        assert p.confidence > 0.0
    def test_avg_part_chars(self):
        p = RhythmProfile()
        for i in range(10):
            p.observe("x" * 20, time.time() + i * 2)
        assert abs(p.avg_part_chars - 20.0) < 1.0
    def test_serialization(self):
        p = RhythmProfile()
        for i in range(10):
            p.observe(f"msg {i}", time.time() + i * 2)
        data = p.to_dict()
        p2 = RhythmProfile.from_dict(data)
        assert p2.confidence == p.confidence


class TestRhythmLearner:
    def test_is_intimate(self):
        rl = RhythmLearner(intimacy_threshold=0.6)
        assert rl.is_intimate(0.7) is True
        assert rl.is_intimate(0.5) is False
    def test_observe_with_low_intimacy(self):
        rl = RhythmLearner(intimacy_threshold=0.6)
        rl.observe_user_message("s1", "hello", time.time(), intimacy_score=0.3)
        assert rl.profile("s1") is None
    def test_observe_with_high_intimacy(self):
        rl = RhythmLearner(intimacy_threshold=0.6)
        for i in range(10):
            rl.observe_user_message("s1", f"msg {i}", time.time() + i * 2, intimacy_score=0.8)
        assert rl.profile("s1") is not None
    def test_tempo_always_recorded(self):
        rl = RhythmLearner(intimacy_threshold=0.6)
        rl.observe_user_message("s1", "hi", time.time(), intimacy_score=0.1)
        assert len(rl._tempo_timestamps.get("s1", [])) == 1
    def test_voice_message(self):
        rl = RhythmLearner()
        rl.observe_voice_message("s1", 10.0)
        assert rl.profile("s1") is not None
    def test_get_rhythm_params_no_profile(self):
        rl = RhythmLearner()
        assert rl.get_rhythm_params("s1") == (48, 7.5)
    def test_get_reply_length_factor_no_profile(self):
        rl = RhythmLearner()
        assert rl.get_reply_length_factor("s1") == 1.0
    def test_get_reply_length_factor_short_messages(self):
        rl = RhythmLearner()
        for i in range(10):
            rl.observe_user_message("s1", "hi", time.time() + i * 2, intimacy_score=0.8)
        assert rl.get_reply_length_factor("s1") == 0.7
    def test_get_reply_length_factor_long_messages(self):
        rl = RhythmLearner()
        for i in range(10):
            rl.observe_user_message("s1", "x" * 250, time.time() + i * 2, intimacy_score=0.8)
        assert rl.get_reply_length_factor("s1") == 1.5
    def test_session_tempo(self):
        rl = RhythmLearner()
        now = time.time()
        for i in range(5):
            rl.observe_user_message("s1", f"msg{i}", now + i * 10, intimacy_score=0.1)
        assert rl.session_tempo("s1") > 0.0
    def test_detect_breath_hold(self):
        rl = RhythmLearner()
        now = time.time()
        for i in range(5):
            rl.observe_user_message("s1", f"msg{i}", now + i * 10, intimacy_score=0.1)
        assert rl.detect_breath_hold(now + 50, now + 55, "s1") is False
        assert rl.detect_breath_hold(now + 50, now + 200, "s1") is True
    def test_serialization(self):
        rl = RhythmLearner(intimacy_threshold=0.5)
        for i in range(10):
            rl.observe_user_message("s1", f"msg {i}", time.time() + i * 2, intimacy_score=0.8)
        data = rl.to_dict()
        rl2 = RhythmLearner.from_dict(data)
        assert rl2._intimacy_threshold == 0.5
        assert rl2.profile("s1") is not None
