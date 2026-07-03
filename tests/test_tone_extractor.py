"""Tests for utils/tone_extractor.py (v1.2.7 Q1)."""

from __future__ import annotations

from emotion_spirit.utils import extract_bot_emotion


class TestExtractBotEmotion:
    """_extract_bot_emotion → utils/tone_extractor.py 纯函数测试."""

    def test_warm(self):
        assert extract_bot_emotion("哈哈真好笑") == ("warm", 0.5)

    def test_apologetic(self):
        assert extract_bot_emotion("抱歉，我理解错了") == ("apologetic", 0.3)

    def test_curious(self):
        assert extract_bot_emotion("你为什么这么想？") == ("curious", 0.3)

    def test_detailed(self):
        long_text = "这是一段非常长的回复。" * 20
        assert extract_bot_emotion(long_text) == ("detailed", 0.5)

    def test_neutral(self):
        assert extract_bot_emotion("好的") == ("neutral", 0.3)

    def test_empty(self):
        assert extract_bot_emotion("") == ("neutral", 0.3)