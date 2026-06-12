"""RhythmLearner — 自适应节奏同步 (从 Sylanne 1.4.7 吸收核心)。

真实关系中不存在被动镜像 — 双方都在刻意调整。
频率更高的一方在被忽略时会感到失落, 刻意放慢,
压力在沉默中积累直到爆发。

核心机制:
  - RhythmProfile: 从单个用户学习到的节奏特征画像
  - RhythmLearner: 按会话的节奏学习器, 带亲密度门控
  - Tempo Clock: 交互频率追踪 + 突变检测
  - Breath Hold: 用户停顿超过正常间隔时检测

与 Sylanne 版本的区别:
  - 用 intimacy_score: float 替代 engine_observation: dict
  - 去除 plugin 实例依赖
  - 保持 per-session 隔离

来源: Sylanne 1.4.7 sylanne_alpha/rhythm_learner.py
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any


def _median(data: list[float]) -> float:
    """计算中位数 (避免 statistics 模块被 verification/ 同名文件遮蔽)。"""
    if not data:
        return 0.0
    s = sorted(data)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0

__all__ = [
    "RhythmLearner",
    "RhythmProfile",
]

_MAX_SAMPLES = 60
_MIN_SAMPLES_FOR_PROFILE = 8
_DEFAULT_CHARS_PER_SECOND = 7.5
_DEFAULT_MAX_PART_CHARS = 48


class RhythmProfile:
    """从单个用户学习到的节奏特征画像。

    追踪用户的消息长度分布和消息间隔分布,
    从中推导出用户的"打字速度"和"偏好消息长度"。
    只有采样数足够时 (>=8) 才产生有效画像。
    """

    __slots__ = (
        "_msg_lengths",
        "_inter_msg_gaps",
        "_last_msg_time",
        "_chars_per_second",
        "_avg_part_chars",
        "_confidence",
    )

    def __init__(self) -> None:
        self._msg_lengths: deque[int] = deque(maxlen=_MAX_SAMPLES)
        self._inter_msg_gaps: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._last_msg_time: float = 0.0
        self._chars_per_second: float = _DEFAULT_CHARS_PER_SECOND
        self._avg_part_chars: float = _DEFAULT_MAX_PART_CHARS
        self._confidence: float = 0.0

    def observe(self, text: str, timestamp: float) -> None:
        """记录一条用户消息, 更新节奏画像。"""
        length = len(text.strip())
        if length < 1:
            return
        self._msg_lengths.append(length)

        if self._last_msg_time > 0 and timestamp > self._last_msg_time:
            gap = timestamp - self._last_msg_time
            if 0.3 < gap < 120.0:
                self._inter_msg_gaps.append(gap)
        self._last_msg_time = timestamp

        self._recompute()

    def _recompute(self) -> None:
        """重新计算画像参数。"""
        n = len(self._msg_lengths)
        if n < _MIN_SAMPLES_FOR_PROFILE:
            self._confidence = 0.0
            return

        self._confidence = min(
            1.0,
            (n - _MIN_SAMPLES_FOR_PROFILE) / (_MAX_SAMPLES - _MIN_SAMPLES_FOR_PROFILE),
        )

        sorted_lengths = sorted(self._msg_lengths)
        p50_idx = len(sorted_lengths) // 2
        self._avg_part_chars = float(sorted_lengths[p50_idx])

        if len(self._inter_msg_gaps) >= 3:
            sorted_gaps = sorted(self._inter_msg_gaps)
            median_gap = sorted_gaps[len(sorted_gaps) // 2]
            median_len = self._avg_part_chars
            if median_gap > 0.1:
                self._chars_per_second = max(2.0, min(20.0, median_len / median_gap))

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def avg_part_chars(self) -> float:
        return self._avg_part_chars

    @property
    def chars_per_second(self) -> float:
        return self._chars_per_second

    def to_dict(self) -> dict[str, Any]:
        return {
            "msg_lengths": list(self._msg_lengths),
            "inter_msg_gaps": list(self._inter_msg_gaps),
            "last_msg_time": self._last_msg_time,
            "chars_per_second": self._chars_per_second,
            "avg_part_chars": self._avg_part_chars,
            "confidence": self._confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RhythmProfile:
        p = cls()
        for v in data.get("msg_lengths", []):
            p._msg_lengths.append(int(v))
        for v in data.get("inter_msg_gaps", []):
            p._inter_msg_gaps.append(float(v))
        p._last_msg_time = float(data.get("last_msg_time", 0.0))
        p._chars_per_second = float(
            data.get("chars_per_second", _DEFAULT_CHARS_PER_SECOND)
        )
        p._avg_part_chars = float(data.get("avg_part_chars", _DEFAULT_MAX_PART_CHARS))
        p._confidence = float(data.get("confidence", 0.0))
        return p


class RhythmLearner:
    """按会话的节奏学习器, 带亲密度门控。

    只有当关系达到足够亲密度时才开始学习用户节奏 —
    这是"刻意同步"的体现: 不是对所有人都调整,
    而是对亲密的人才愿意调整自己的节奏。

    与 Sylanne 版本的区别:
      - 用 intimacy_score: float 替代 engine_observation: dict
      - 亲密度判断简化为单一数值比较
    """

    __slots__ = (
        "_profiles",
        "_intimacy_threshold",
        "_default_blend",
        "_tempo_timestamps",
        "_last_tempo",
        "_tempo_shift",
    )

    def __init__(self, intimacy_threshold: float = 0.6) -> None:
        self._profiles: dict[str, RhythmProfile] = {}
        self._intimacy_threshold = intimacy_threshold
        self._default_blend = 0.6
        self._tempo_timestamps: dict[str, deque] = {}
        self._last_tempo: dict[str, float] = {}
        self._tempo_shift: dict[str, bool] = {}

    def set_personality_params(self, intimacy_threshold: float, blend_rate: float) -> None:
        """设置人格驱动的节奏学习参数。"""
        self._intimacy_threshold = intimacy_threshold
        self._default_blend = blend_rate

    def is_intimate(self, intimacy_score: float) -> bool:
        """判断亲密度是否达到学习阈值。

        Args:
            intimacy_score: 亲密度分数 [0, 1]。

        Returns:
            是否达到阈值。
        """
        return intimacy_score >= self._intimacy_threshold

    def observe_user_message(
        self,
        session_key: str,
        text: str,
        timestamp: float,
        intimacy_score: float,
    ) -> None:
        """观察一条用户消息。只有亲密度足够时才学习。

        Args:
            session_key: 会话标识。
            text: 用户消息文本。
            timestamp: 消息时间戳。
            intimacy_score: 当前亲密度 [0, 1]。
        """
        # 始终记录 tempo (不受亲密度门控)
        self._record_tempo(session_key, timestamp)

        if not self.is_intimate(intimacy_score):
            return

        if session_key not in self._profiles:
            if len(self._profiles) >= 200:
                oldest_key = next(iter(self._profiles))
                del self._profiles[oldest_key]
            self._profiles[session_key] = RhythmProfile()
        self._profiles[session_key].observe(text, timestamp)

    def observe_voice_message(
        self,
        session_key: str,
        duration_seconds: float,
    ) -> None:
        """观察一条语音消息, 按时长换算为等效字符数后记录。

        1 秒 ≈ 5 个字符的信息量。
        """
        if duration_seconds <= 0:
            return
        equivalent_chars = int(duration_seconds * 5)

        if session_key not in self._profiles:
            if len(self._profiles) >= 200:
                oldest_key = next(iter(self._profiles))
                del self._profiles[oldest_key]
            self._profiles[session_key] = RhythmProfile()

        profile = self._profiles[session_key]
        if equivalent_chars >= 1:
            profile._msg_lengths.append(equivalent_chars)
            profile._recompute()

    def get_rhythm_params(
        self,
        session_key: str,
        default_max_part: int = 48,
        default_cps: float = 7.5,
        blend: float = 0.6,
        expression_drive: float = 0.5,
        recent_ignored_rate: float = 0.0,
    ) -> tuple[int, float]:
        """获取调制后的分段参数 — 刻意同步。

        与被动学习不同, 这是一个有意识的决策:
          - 高 expression_drive → 主动加速向用户节奏靠拢
          - 高 ignored_rate → 刻意放慢 (退缩)
          - blend 被驱力 (想同步) 和退缩 (被忽略) 共同调制

        Args:
            session_key: 会话标识。
            default_max_part: 默认最大分段字符数。
            default_cps: 默认打字速度。
            blend: 基础混合比例。
            expression_drive: 表达驱力 [0, 1]。
            recent_ignored_rate: 近期被忽略率 [0, 1]。

        Returns:
            (max_part_chars, chars_per_second) 元组。
        """
        profile = self._profiles.get(session_key)
        if profile is None or profile.confidence < 0.1:
            return default_max_part, default_cps

        drive_factor = min(1.0, expression_drive * 1.5)
        withdrawal_factor = min(0.8, recent_ignored_rate * 2.0)
        sync_intent = drive_factor - withdrawal_factor
        effective_blend = max(0.0, blend * profile.confidence * max(0.1, sync_intent))

        if effective_blend < 0.05:
            slowdown = 1.0 + withdrawal_factor * 0.5
            return int(default_max_part * slowdown), default_cps / slowdown

        learned_part = max(12, min(120, int(profile.avg_part_chars)))
        learned_cps = profile.chars_per_second

        blended_part = int(
            default_max_part * (1 - effective_blend) + learned_part * effective_blend
        )
        blended_cps = (
            default_cps * (1 - effective_blend) + learned_cps * effective_blend
        )

        return max(12, min(120, blended_part)), max(2.0, min(20.0, blended_cps))

    def get_reply_length_factor(self, session_key: str) -> float:
        """统计用户近 20 条消息的平均字符长度, 返回回复长度倍率因子。

        规则:
          - 用户消息短 (<30 字) → 0.7 (回复精炼)
          - 用户消息长 (>200 字) → 1.5 (回复详尽)
          - 中间线性插值, 最终 clamp 到 [0.5, 2.0]
        """
        profile = self._profiles.get(session_key)
        if profile is None or len(profile._msg_lengths) == 0:
            return 1.0

        recent = list(profile._msg_lengths)[-20:]
        avg_len = sum(recent) / len(recent)

        if avg_len <= 30.0:
            factor = 0.7
        elif avg_len >= 200.0:
            factor = 1.5
        else:
            factor = 0.7 + (avg_len - 30.0) / (200.0 - 30.0) * (1.5 - 0.7)

        return max(0.5, min(2.0, factor))

    def profile(self, session_key: str) -> RhythmProfile | None:
        """获取指定 session 的节奏画像。"""
        return self._profiles.get(session_key)

    # ── Tempo Clock ──

    def _record_tempo(self, session_key: str, timestamp: float) -> None:
        """记录一次交互时间戳并更新 tempo 状态。"""
        if session_key not in self._tempo_timestamps:
            self._tempo_timestamps[session_key] = deque(maxlen=300)
        self._tempo_timestamps[session_key].append(timestamp)

        new_tempo = self._session_tempo(session_key)
        last = self._last_tempo.get(session_key, 0.0)
        if last > 0.0 and new_tempo > 0.0:
            ratio = new_tempo / last
            self._tempo_shift[session_key] = ratio > 2.0 or ratio < 0.5
        else:
            self._tempo_shift[session_key] = False
        if new_tempo > 0.0:
            self._last_tempo[session_key] = new_tempo

    def _session_tempo(self, session_key: str) -> float:
        """指定会话最近 5 分钟内的交互频率 (次/分钟)。"""
        timestamps = self._tempo_timestamps.get(session_key)
        if not timestamps:
            return 0.0
        now = timestamps[-1]
        window_start = now - 300.0
        count = sum(1 for t in timestamps if t >= window_start)
        if count <= 1:
            return 0.0
        earliest_in_window = min(t for t in timestamps if t >= window_start)
        span_minutes = (now - earliest_in_window) / 60.0
        if span_minutes < 0.01:
            return 0.0
        return count / span_minutes

    def session_tempo(self, session_key: str) -> float:
        """获取指定会话的 tempo。"""
        return self._session_tempo(session_key)

    def session_tempo_shift(self, session_key: str) -> bool:
        """指定会话是否发生 tempo 突变。"""
        return self._tempo_shift.get(session_key, False)

    # ── Breath Hold Detection ──

    def detect_breath_hold(
        self,
        last_message_time: float,
        now: float,
        session_key: str = "",
    ) -> bool:
        """当用户停顿超过正常间隔 2 倍时返回 True。

        正常间隔从 tempo_clock 的历史中位数计算。
        """
        timestamps = self._tempo_timestamps.get(session_key) if session_key else None
        if not timestamps:
            all_ts = [t for dq in self._tempo_timestamps.values() for t in dq]
            if len(all_ts) < 2:
                return False
            timestamps = sorted(all_ts)
        else:
            if len(timestamps) < 2:
                return False
            timestamps = sorted(timestamps)

        gaps = [
            timestamps[i + 1] - timestamps[i]
            for i in range(len(timestamps) - 1)
            if timestamps[i + 1] - timestamps[i] > 0.1
        ]
        if not gaps:
            return False

        normal_interval = _median(gaps)
        current_gap = now - last_message_time
        return current_gap > normal_interval * 2.0

    # ── 序列化 ──

    def to_dict(self) -> dict[str, Any]:
        return {
            "intimacy_threshold": self._intimacy_threshold,
            "profiles": {k: v.to_dict() for k, v in self._profiles.items()},
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        intimacy_threshold: float = 0.6,
    ) -> RhythmLearner:
        threshold = float(data.get("intimacy_threshold", intimacy_threshold))
        learner = cls(intimacy_threshold=threshold)
        profiles = data.get("profiles", data)
        for k, v in profiles.items():
            if k == "intimacy_threshold":
                continue
            if isinstance(v, dict):
                learner._profiles[k] = RhythmProfile.from_dict(v)
        return learner
