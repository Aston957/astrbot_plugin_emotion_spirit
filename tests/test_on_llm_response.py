"""Tests for _extract_bot_emotion (Phase H on_llm_response).

_extract_bot_emotion 是 staticmethod，纯规则无外部依赖。
直接复制逻辑测试，不导入 main.py (避免 astrbot 框架 mock)。
"""


def _extract_bot_emotion(text: str) -> tuple[str, float]:
    """从 bot 回复文本规则提取情绪标签和权重。复制自 main.py。"""
    text_lower = text.lower()

    warm_words = ["哈哈", "笑", "开心", "高兴", "❤", "🥰", "😊", "喜欢", "棒", "好的呀"]
    if any(w in text_lower for w in warm_words):
        return "warm", 0.5

    apologetic_words = ["抱歉", "不好意思", "对不起", "sorry", "遗憾"]
    if any(w in text_lower for w in apologetic_words):
        return "apologetic", 0.3

    if "？" in text or "?" in text:
        return "curious", 0.3

    if len(text) > 200:
        return "detailed", 0.5

    return "neutral", 0.3


class TestExtractBotEmotion:
    """_extract_bot_emotion 规则测试。"""

    def test_warm_haha(self):
        tone, weight = _extract_bot_emotion("哈哈好的呀❤")
        assert tone == "warm"
        assert weight == 0.5

    def test_warm_emoji(self):
        tone, weight = _extract_bot_emotion("我很高兴🥰")
        assert tone == "warm"

    def test_warm_like(self):
        tone, weight = _extract_bot_emotion("我喜欢这个")
        assert tone == "warm"

    def test_apologetic(self):
        tone, weight = _extract_bot_emotion("不好意思，我不太确定")
        assert tone == "apologetic"
        assert weight == 0.3

    def test_apologetic_sorry(self):
        tone, weight = _extract_bot_emotion("sorry 我不知道")
        assert tone == "apologetic"

    def test_curious_chinese(self):
        tone, weight = _extract_bot_emotion("你觉得呢？")
        assert tone == "curious"
        assert weight == 0.3

    def test_curious_english(self):
        tone, weight = _extract_bot_emotion("What do you think?")
        assert tone == "curious"

    def test_detailed(self):
        long_text = "这是一个很长的回复" * 30
        tone, weight = _extract_bot_emotion(long_text)
        assert tone == "detailed"
        assert weight == 0.5

    def test_neutral(self):
        tone, weight = _extract_bot_emotion("好的")
        assert tone == "neutral"
        assert weight == 0.3

    def test_empty(self):
        tone, weight = _extract_bot_emotion("")
        assert tone == "neutral"
        assert weight == 0.3

    def test_priority_warm_over_curious(self):
        """warm 优先级高于 curious (先检查)。"""
        tone, _ = _extract_bot_emotion("哈哈你觉得呢？")
        assert tone == "warm"

    def test_priority_apologetic_over_curious(self):
        """apologetic 优先级高于 curious。"""
        tone, _ = _extract_bot_emotion("不好意思，你觉得呢？")
        assert tone == "apologetic"
