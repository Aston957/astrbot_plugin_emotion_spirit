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
from typing import Any, Optional

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

    # ═══ silence tendency 计算 (v1.2.5 PR1 §3.2) ═══

    def compute_silence_tendency(
        self,
        session_key: str,
        personality: dict,
        force_state: Optional[Any] = None,
        body_state: Optional[Any] = None,
        signals: Optional[Any] = None,
        intimacy_level: float = 0.5,
        context: Optional[dict] = None,
    ) -> SilenceTendency:
        """计算沉默倾向分数 (6 factor 人格加权算法, 系数全部从 KB 读取).

        Args:
            session_key: 会话标识 (预留, 未来可用于 per-session 缓存).
            personality: Big Five 人格 dict {extraversion, neuroticism,
                        agreeableness, openness, conscientiousness}.
            force_state: ForceState 或 dict {natural, social, individual}.
            body_state: BodyState 或 dict {energy, arousal}.
            signals: SemanticSignals 对象或 dict, 提供 rhythm_strain,
                     hot_pool_pressure, pad_valence, pad_arousal.
            intimacy_level: 亲密度 [0, 1], 0=陌生人, 1=最亲密.
            context: dict {social_audience, authority_present}.

        Returns:
            SilenceTendency(score, reason, components).
        """
        from ..core.persona_labels_db import get_silence_tendency_weights

        weights = get_silence_tendency_weights()
        factors_cfg = weights["factors"]
        intimacy_cfg = weights["intimacy_modifier"]
        context_cfg = weights["context_modifier"]
        force_cfg = weights["force_modifier"]

        # --- Helper: extract value from obj/dict/None ---
        def _get_val(obj, key, default=0.5):
            if obj is None:
                return default
            if hasattr(obj, key):
                return float(getattr(obj, key))
            if isinstance(obj, dict):
                return float(obj.get(key, default))
            return default

        # --- Extract personality (Big Five) with defaults ---
        E = float(personality.get("extraversion", 0.5))
        N = float(personality.get("neuroticism", 0.5))
        A_val = float(personality.get("agreeableness", 0.5))
        O = float(personality.get("openness", 0.5))
        C = float(personality.get("conscientiousness", 0.5))

        # --- Extract signal values ---
        rhythm_strain = _get_val(signals, "rhythm_strain", 0.5)
        hot_pool_pressure = _get_val(signals, "hot_pool_pressure", 0.0)
        pad_valence = _get_val(signals, "pad_valence", 0.5)
        sig_arousal = _get_val(signals, "pad_arousal", 0.5)

        ctx = context or {}
        social_audience_val = float(ctx.get("social_audience", 0.0))
        authority_present = float(ctx.get("authority_present", 0.0))

        # --- Extract body state ---
        energy = _get_val(body_state, "energy", 0.5)
        body_arousal_val = _get_val(body_state, "arousal", 0.5)
        # Prefer signals arousal if available, else fall back to body arousal
        arousal = sig_arousal if signals is not None else body_arousal_val

        # --- Extract force state ---
        def _get_force(key):
            if force_state is None:
                return 0.33
            if hasattr(force_state, key):
                return float(getattr(force_state, key))
            if isinstance(force_state, dict):
                return float(force_state.get(key, 0.33))
            return 0.33

        f_natural = _get_force("natural")
        f_social = _get_force("social")
        f_individual = _get_force("individual")

        # --- Compute 6 factor raw scores ---
        pm = {}  # personality_modifiers index
        for name in factors_cfg:
            pm[name] = factors_cfg[name]["personality_modifiers"]

        tension_stress = rhythm_strain * (1 + pm["tension_stress"]["neuroticism"] * N)

        hurt_void = (
            hot_pool_pressure
            * (1 - pad_valence)
            * (1 + pm["hurt_void"]["extraversion_reverse"] * (1 - E))
            * (1 + pm["hurt_void"]["neuroticism"] * N)
            * (1 + pm["hurt_void"]["agreeableness_reverse"] * (1 - A_val))
        )

        satisfaction_quiet = (
            hot_pool_pressure
            * pad_valence
            * (1 + pm["satisfaction_quiet"]["extraversion_reverse"] * (1 - E))
        )

        exhaustion_val = (1 - energy) * (1 + pm["exhaustion"]["conscientiousness"] * C)

        overload = arousal * (1 + pm["overload"]["neuroticism"] * N)

        social_audience_factor = social_audience_val * (
            1 + pm["social_audience"]["extraversion_reverse"] * (1 - E)
        )

        # --- Weighted base score ---
        w_ten = factors_cfg["tension_stress"]["weight_in_sum"]
        w_hurt = factors_cfg["hurt_void"]["weight_in_sum"]
        w_sat = factors_cfg["satisfaction_quiet"]["weight_in_sum"]
        w_exh = factors_cfg["exhaustion"]["weight_in_sum"]
        w_ovr = factors_cfg["overload"]["weight_in_sum"]
        w_soc = factors_cfg["social_audience"]["weight_in_sum"]

        weighted_factors = {
            "tension_stress": w_ten * tension_stress,
            "hurt_void": w_hurt * hurt_void,
            "satisfaction_quiet": w_sat * satisfaction_quiet,
            "exhaustion": w_exh * exhaustion_val,
            "overload": w_ovr * overload,
            "social_audience": w_soc * social_audience_factor,
        }

        base_score = sum(weighted_factors.values())

        # --- Modifiers ---
        im_cfg = intimacy_cfg["personality_modifiers"]
        intimacy_mod = (
            (1 + intimacy_cfg["base_coefficient"] * intimacy_level)
            * (1 + im_cfg["agreeableness"] * A_val)
            * (1 + im_cfg["neuroticism"] * N)
            * (1 + im_cfg["openness_reverse"] * O)
        )

        context_mod = 1 + context_cfg["authority_present_coefficient"] * authority_present

        force_mod_raw = (
            1
            + force_cfg["social_coefficient"] * f_social
            + force_cfg["natural_coefficient"] * f_natural
            + force_cfg["individual_coefficient"] * f_individual
        )
        fr = force_cfg.get("range", [0.5, 1.5])
        force_mod = max(fr[0], min(fr[1], force_mod_raw))

        # --- Final score ---
        score = base_score * intimacy_mod * context_mod * force_mod
        score = max(0.0, min(1.0, score))

        # --- Dominant factor ---
        dominant = max(weighted_factors, key=weighted_factors.get)
        reason_map = {
            "tension_stress": "节奏张力引发沉默倾向",
            "hurt_void": "受伤/空洞引发沉默倾向",
            "satisfaction_quiet": "满足性静默",
            "exhaustion": "能量耗尽引发沉默倾向",
            "overload": "过载引发沉默倾向",
            "social_audience": "社交场合引发沉默倾向",
        }
        reason = reason_map.get(dominant, f"{dominant} 引发沉默倾向")

        # --- Components dict ---
        components = {
            "tension_stress": round(tension_stress, 4),
            "hurt_void": round(hurt_void, 4),
            "satisfaction_quiet": round(satisfaction_quiet, 4),
            "exhaustion": round(exhaustion_val, 4),
            "overload": round(overload, 4),
            "social_audience": round(social_audience_factor, 4),
            "intimacy_modifier": round(intimacy_mod, 4),
            "context_modifier": round(context_mod, 4),
            "force_modifier": round(force_mod, 4),
            "dominant_factor": dominant,
        }

        return SilenceTendency(
            score=round(score, 4),
            reason=reason,
            components=components,
        )

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