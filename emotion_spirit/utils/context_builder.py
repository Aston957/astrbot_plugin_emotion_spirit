"""context_builder — 纯函数构建上下文 dict。

v1.2.7: 从 main.py._build_context 抽出, 无状态纯函数.

被 SegmentedReplyOrchestrator 和 main.py 共同 import (不违反 §1.3 分层).
"""


def build_context(event) -> dict:
    """构建上下文 dict, 含 social_audience + authority_present.

    Args:
        event: AstrBot AstrMessageEvent (需有 get_group_id 方法).

    Returns:
        dict: {"social_audience": float, "authority_present": float}
    """
    context = {}
    if hasattr(event, "get_group_id") and event.get_group_id():
        context["social_audience"] = 0.5
    else:
        context["social_audience"] = 0.0
    context["authority_present"] = 0.0  # v1.3 真实解析
    return context