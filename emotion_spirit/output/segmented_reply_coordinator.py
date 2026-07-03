"""SegmentedReplyCoordinator — 分段回复协调器.

v1.2.3 新建。桥接现成但未连线的分段回复引擎 (RealtimeDispatch/RhythmLearner/
DeliberateSilence/BreathingRhythmController) 到 main.py 的回复链路。

设计原则 (与 realtime_dispatch.py docstring 对齐):
1. 引擎层 (output) 纯数据结构输出, 不涉及 async/IO —— Coordinator 也不碰 async/yield
2. 实际消息发送 (async sleep + yield) 归 main.py 宿主层
3. 模块新增走现有 @register + DI, 零新架构概念
"""

from dataclasses import dataclass, field

import logging


@dataclass(frozen=True)
class SilenceTendency:
    """沉默倾向 (v1.2.5 PR1 §2.2)

    score: 0.0 (必说) - 1.0 (必沉默), 连续值
    reason: 触发原因字符串, 用于日志 + /reflect_force_current
    components: 各因子贡献, 可观测性
    """
    score: float
    reason: str
    components: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")
import time
from collections import deque
from typing import Any

from emotion_spirit.core.registry import register

logger = logging.getLogger(__name__)

# 默认配置常量
_DEFAULT_MAX_PART_CHARS: int = 48
_DEFAULT_CHARS_PER_SECOND: float = 7.5
_DEFAULT_MAX_DELAY_SECONDS: float = 2.0
_DEFAULT_IGNORED_WINDOW_TURNS: int = 10
_DEFAULT_BLEND: float = 0.6
_DEFAULT_INTIMACY_GATE: float = 0.6
_DEFAULT_IGNORED_SECONDS: float = 7200.0


@register(
    name="segmented_reply_coordinator",
    provides=["SegmentedReplyCoordinator"],
    depends_on=["rhythm_learner", "realtime_dispatch"],
)
class SegmentedReplyCoordinator:
    """分段回复协调器。

    在 LLM 生成整条回复后:

    1. 计算 ignored_rate (per-session deque, D8)
    2. 用 RhythmLearner 调制分段参数 (max_part, cps)
    3. 用 BreathingRhythmController 调长度因子
    4. 判断是否该主动沉默 (DeliberateSilence)
    5. 用 RealtimeDispatch.build_segmented_parts 生成发送计划

    输出纯数据 (list[{text, delay_before_seconds}]), 不碰 I/O。
    """

    def __init__(
        self,
        rhythm_learner: Any = None,
        realtime_dispatch: Any = None,
    ) -> None:
        # factory 通过 depends_on 注入依赖
        self._rhythm = rhythm_learner
        self._dispatch = realtime_dispatch

        # per-session: {session_key: deque[float]} — 每轮 bot 回复的时间戳
        self._reply_times: dict[str, deque[float]] = {}
        # per-session: {session_key: deque[float]} — 每轮用户消息到达的时间戳
        self._user_times: dict[str, deque[float]] = {}
        # 窗口大小 (轮数)
        self._window: int = _DEFAULT_IGNORED_WINDOW_TURNS

    # ═══ 主入口 ═══

    def plan(
        self,
        full_text: str,
        session_key: str,
        expression_drive: float = 0.5,
        rhythm_strain: float = 0.5,
        pad_valence: float = 0.5,
        hot_pool_pressure: float = 0.0,
        config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """生成分段发送计划。

        Args:
            full_text: LLM 生成的完整回复文本。
            session_key: 会话标识。
            expression_drive: 表达驱力 (SemanticSignals.affect_expression_drive).
            rhythm_strain: 节奏张力 (D9, 来自 signals.rhythm_strain).
            pad_valence: 价态 (D11, 来自 signals.pad_valence).
            hot_pool_pressure: 空洞压抑 (D10, 来自 signals.hot_pool_pressure).
            config: 分段回复配置字典 (来自 _conf_schema.json).
                    缺项回退默认值。

        Returns:
            [{text, delay_before_seconds}] 列表。空列表 = 不应该回复 (主动沉默)。
        """
        cfg = config or {}

        # 1. 计算 ignored_rate (D8)
        ignored_seconds = cfg.get("behavior_ignored_seconds", _DEFAULT_IGNORED_SECONDS)
        ignored_rate = self._ignored_rate(session_key, ignored_seconds)

        # 2. 用 RhythmLearner 调制分段参数
        max_part, cps = self._rhythm.get_rhythm_params(
            session_key,
            default_max_part=cfg.get("default_max_part_chars", _DEFAULT_MAX_PART_CHARS),
            default_cps=cfg.get("default_chars_per_second", _DEFAULT_CHARS_PER_SECOND),
            blend=cfg.get("blend", _DEFAULT_BLEND),
            expression_drive=expression_drive,
            recent_ignored_rate=ignored_rate,
        )

        # 3. 用 BreathingRhythmController 调长度因子 (D9)
        length_factor = self._dispatch.next_length_factor(
            tension=rhythm_strain,
            valence=pad_valence,
        )
        max_part = max(12, int(max_part * length_factor))

        # 4. 判断是否该主动沉默 (D10)
        enable_silence = cfg.get("enable_deliberate_silence", False)
        if enable_silence:
            silent, reason = self._dispatch.should_be_silent(
                valence=pad_valence,
                tension=rhythm_strain,
                void_pressure=hot_pool_pressure,
            )
            if silent:
                logger.debug(
                    "emotion_spirit: 主动沉默 — %s (valence=%.2f, tension=%.2f, void=%.2f)",
                    reason, pad_valence, rhythm_strain, hot_pool_pressure,
                )
                minimal = self._dispatch.get_minimal_response(reason)
                if minimal:
                    return [{"text": minimal, "delay_before_seconds": 0.0}]
                return []

        # 5. 生成分段发送计划
        plan = self._dispatch.build_segmented_parts(full_text, max_part, cps)

        # D7: 段间延迟上限兜底
        max_delay = cfg.get("max_delay_seconds", _DEFAULT_MAX_DELAY_SECONDS)
        for part in plan:
            part["delay_before_seconds"] = min(
                part.get("delay_before_seconds", 0.0),
                max_delay,
            )

        return plan

    # ═══ per-session ignored_rate 计算 (D8) ═══

    def record_bot_reply(self, session_key: str) -> None:
        """记录 bot 回复时刻。"""
        if session_key not in self._reply_times:
            self._reply_times[session_key] = deque(maxlen=self._window)
        self._reply_times[session_key].append(time.time())

    def record_user_message(self, session_key: str) -> None:
        """记录用户消息到达时刻。"""
        if session_key not in self._user_times:
            self._user_times[session_key] = deque(maxlen=self._window)
        self._user_times[session_key].append(time.time())

    def _ignored_rate(self, session_key: str, ignored_seconds: float) -> float:
        """计算近期被忽略率。

        统计最近 self._window 次交互中, bot 回复后用户超过 ignored_seconds
        才回应的比例。
        """
        reply_deque = self._reply_times.get(session_key)
        user_deque = self._user_times.get(session_key)
        if not reply_deque or not user_deque or len(reply_deque) < 2:
            return 0.0

        # 配对: 检查每次 bot 回复后, 最近一次用户消息是否在 ignored_seconds 内
        ignored_count = 0
        total = 0
        # 按时间顺序对齐: 取最近 min(len) 对
        replies = sorted(reply_deque)[-self._window:]
        users = sorted(user_deque)[-self._window:]

        # 对每个 bot 回复, 找之后最近的一条用户消息
        user_idx = 0
        for r_time in replies:
            next_user = None
            while user_idx < len(users):
                if users[user_idx] > r_time:
                    next_user = users[user_idx]
                    break
                user_idx += 1
            if next_user is None:
                continue
            total += 1
            if next_user - r_time > ignored_seconds:
                ignored_count += 1

        if total == 0:
            return 0.0
        return ignored_count / total

    # ═══ 序列化 ═══

    def to_dict(self) -> dict[str, Any]:
        """序列化 ignored_rate 状态 (与 BreakpointStore 同档)."""
        return {
            "reply_times": {k: list(v) for k, v in self._reply_times.items()},
            "user_times": {k: list(v) for k, v in self._user_times.items()},
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """反序列化恢复状态。"""
        self._reply_times = {
            k: deque(v, maxlen=self._window)
            for k, v in data.get("reply_times", {}).items()
        }
        self._user_times = {
            k: deque(v, maxlen=self._window)
            for k, v in data.get("user_times", {}).items()
        }