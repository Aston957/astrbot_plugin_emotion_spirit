"""Bot 回复文本 → 情绪标签/权重提取 (纯函数, v1.2.7 从 main.py 抽出)."""

from __future__ import annotations


def extract_bot_emotion(text: str) -> tuple[str, float]:
    """从 bot 回复文本规则提取情绪标签和权重。

    Args:
        text: Bot 生成的回复文本。

    Returns:
        (tone, weight) 元组。
    """
    text_lower = text.lower()

    # 温暖类
    warm_words = ["哈哈", "笑", "开心", "高兴", "❤", "🥰", "😊", "喜欢", "棒", "好的呀"]
    if any(w in text_lower for w in warm_words):
        return "warm", 0.5

    # 抱歉类
    apologetic_words = ["抱歉", "不好意思", "对不起", "sorry", "遗憾"]
    if any(w in text_lower for w in apologetic_words):
        return "apologetic", 0.3

    # 好奇类
    if "？" in text or "?" in text:
        return "curious", 0.3

    # 详细回复
    if len(text) > 200:
        return "detailed", 0.5

    return "neutral", 0.3