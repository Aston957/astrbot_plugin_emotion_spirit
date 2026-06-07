"""emotion_spirit 公开 API 网关 (Phase B, P3-1)。

3 个公开 API: get_emotion_state, get_body_state, get_emotion_trajectory。
从 main.py 搬到这, main.py 瘦身。

设计 (B6.8 决策):
- 走 surface_consumer.consume_for_session() (v1.7.2 B6 新增) 复用 EMA 缓存
- emotion_trajectory 是 signals 属性 (SurfaceConsumer 内部维护 deque)
- include_trajectory 默认 False, 与 v1.7.2 兼容 (替代 get_emotion_trajectory 独立 API)
"""
from __future__ import annotations
from typing import Any


class PublicAPI:
    """3 个公开 API 的统一网关。

    依赖:
    - surface_consumer: SurfaceConsumer 实例 (提供 consume_for_session)
    """

    def __init__(self, modules: dict[str, Any]) -> None:
        self._modules = modules

    def _get_signals(self, session_key: str) -> Any | None:
        """从 surface_consumer 读取最近一次 signals。"""
        consumer = self._modules.get("surface_consumer")
        if consumer is None:
            return None
        # 优先用 v1.7.2 新增的 consume_for_session
        if hasattr(consumer, "consume_for_session"):
            return consumer.consume_for_session(session_key)
        # 回退到 main.py 注入的 _latest_signals (向后兼容)
        latest = self._modules.get("_latest_signals", {})
        if isinstance(latest, dict):
            return latest.get(session_key)
        return None

    async def get_emotion_state(
        self, session_key: str, include_trajectory: bool = False,
    ) -> dict | None:
        """统一情绪状态 API (v1.1.1 9 字段 + v1.2 +ambiguity +velocity = 11 字段)。

        Args:
            session_key: 通常是 event.unified_msg_origin 或 session_id
            include_trajectory: v1.7.2 Phase A 新增。True 时在返回 dict 中加
                emotion_trajectory 字段 (list of {valence/arousal/dominance/timestamp})。
                默认 False 保持向后兼容; 替代了原独立 API get_emotion_trajectory。

        Returns:
            None if no signals for session_key, else dict with:
            - pad_valence / pad_arousal / pad_dominance (float)
            - pad_primary / pad_secondary (str)
            - pad_distribution (dict[str, float])
            - pad_intensity (float)
            - pad_label (str, 向后兼容)
            - emotion_ambiguity (float, v1.2) 分布 Shannon 熵 [0, 1]
            - emotion_velocity (dict | None, v1.2) {valence, arousal, dominance, dt}
            - emotion_trajectory (list[dict], v1.7.2, 仅 include_trajectory=True)
        """
        signals = self._get_signals(session_key)
        if signals is None:
            return None

        state = {
            "pad_valence": signals.pad_valence,
            "pad_arousal": signals.pad_arousal,
            "pad_dominance": signals.pad_dominance,
            "pad_primary": signals.pad_primary,
            "pad_secondary": signals.pad_secondary,
            "pad_distribution": dict(signals.pad_distribution),
            "pad_intensity": signals.pad_intensity,
            "pad_label": signals.pad_primary,  # 向后兼容: pad_label == pad_primary
            # v1.2 新增 2 字段
            "emotion_ambiguity": signals.emotion_ambiguity,
            "emotion_velocity": signals.emotion_velocity,
        }

        # v1.7.2 Phase A: trajectory 作为可选字段
        if include_trajectory:
            state["emotion_trajectory"] = [
                {"valence": v, "arousal": a, "dominance": d, "timestamp": t}
                for v, a, d, t in signals.emotion_trajectory
            ]

        return state

    async def get_body_state(self, session_key: str) -> dict | None:
        """身体生理状态 API (v1.1.1 重命名自 get_emotion_values, 4 字段)。

        Returns:
            None if no signals for session_key, else dict with:
            - warmth (signals.valence_warmth)
            - pulse (signals.connection_circulation)
            - expression (signals.needs_expression)
            - repair (signals.valence_repair_heat)
        """
        signals = self._get_signals(session_key)
        if signals is None:
            return None

        return {
            "pad_valence": signals.pad_valence,
            "pad_arousal": signals.pad_arousal,
            "pad_dominance": signals.pad_dominance,
            "pad_label": signals.pad_primary,  # 兼容
            "warmth": signals.valence_warmth,
            "pulse": signals.connection_circulation,
            "expression": signals.needs_expression,
            "repair": signals.valence_repair_heat,
        }
