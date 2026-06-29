"""RealtimeDispatch — 分段回复计划生成器 (从 Sylanne 1.4.7 吸收核心)。

职责:
  1. 首句提取: 从文本中提取第一个完整句子
  2. 文本分段: 按字符数 + 标点将长回复拆分为多条消息
  3. 分段计划: 生成 [{text, delay_before_seconds}] 计划
  4. 中断断点: 记录被中断回复的已发/未发部分
  5. 对话恢复: 长时间间隔后的恢复提示
  6. 主动沉默: 受伤/消化/满足时选择不说
  7. 呼吸节奏: 4 种模式控制回复长短交替

设计原则:
  - 纯数据结构输出, 不涉及 async/IO
  - 不负责实际消息发送 (那是宿主插件的事)
  - 与 RhythmLearner 配合调整分段参数

来源: Sylanne 1.4.7 sylanne_alpha/realtime_dispatch.py
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..core.registry import register

__all__ = [
    "RealtimeDispatch",
    "DeliberateSilence",
    "BreathingRhythmController",
    "SegmentedPart",
    "InterruptedBreakpoint",
]


# ═══ 数据结构 ═══

@dataclass
class SegmentedPart:
    """分段回复的一个片段。"""
    text: str
    delay_before_seconds: float = 0.0


@dataclass
class InterruptedBreakpoint:
    """被中断的回复断点。"""
    full_text: str
    sent_parts: list[str]
    unsent_parts: list[str]
    input_epoch: int = 0
    reason: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


# ═══ 首句提取 ═══

_DELIMITERS = frozenset("。！？!?；;")
_DELIMITER_PATTERN = re.compile(r'[。！？!?；;\n]')


def extract_first_sentence(text: str) -> str:
    """从文本中提取第一个完整句子。

    以中英文句末标点或换行符为分隔。连续标点视为同一句。

    Args:
        text: 输入文本。

    Returns:
        第一个完整句子 (含标点), 找不到则返回空字符串。
    """
    for i, ch in enumerate(text):
        if ch in _DELIMITERS and i > 0:
            # 连续标点视为同一句
            if i + 1 < len(text) and text[i + 1] in _DELIMITERS:
                continue
            return text[: i + 1]
        if ch == "\n" and i > 0:
            return text[:i]
    return ""


# ═══ 文本分段 ═══

# 默认分段正则: 按中英文标点或换行切分
_DEFAULT_SPLIT_PATTERN = re.compile(r'.*?[。？！~…\n]+|.+$', re.DOTALL | re.MULTILINE)


def segment_text(text: str, max_part_chars: int = 48) -> list[str]:
    """按标点和字符数将文本切分为多段。

    先按标点切分, 再对超长段按字符数二次切分。

    Args:
        text: 要切分的文本。
        max_part_chars: 单段最大字符数。

    Returns:
        切分后的文本列表。
    """
    if not text or not text.strip():
        return []

    # 第一步: 按标点切分
    raw_segments = _DEFAULT_SPLIT_PATTERN.findall(text)
    segments = [s.strip() for s in raw_segments if s.strip()]

    if not segments:
        return [text]

    # 第二步: 对超长段按字符数二次切分
    result: list[str] = []
    for seg in segments:
        if len(seg) <= max_part_chars:
            result.append(seg)
        else:
            # 按 max_part_chars 切分, 尽量在标点处断
            sub_parts = _split_long_segment(seg, max_part_chars)
            result.extend(sub_parts)

    return result if result else [text]


def _split_long_segment(text: str, max_chars: int) -> list[str]:
    """对超长段按字符数切分, 尽量在标点处断。"""
    parts: list[str] = []
    remaining = text

    while len(remaining) > max_chars:
        # 在 max_chars 范围内找最后一个标点
        cut_pos = max_chars
        for i in range(max_chars - 1, max_chars // 2, -1):
            if i < len(remaining) and remaining[i] in _DELIMITERS:
                cut_pos = i + 1
                break

        parts.append(remaining[:cut_pos])
        remaining = remaining[cut_pos:]

    if remaining:
        parts.append(remaining)

    return parts


def build_segmented_parts(
    full_text: str,
    max_part_chars: int = 48,
    chars_per_second: float = 7.5,
) -> list[dict[str, Any]]:
    """生成分段发送计划。

    Args:
        full_text: 完整回复文本。
        max_part_chars: 单段最大字符数。
        chars_per_second: 打字速度 (字符/秒), 用于计算段间延迟。

    Returns:
        [{text, delay_before_seconds}] 列表。
        第一段 delay=0, 后续段按文本长度计算打字延迟。
    """
    parts = segment_text(full_text, max_part_chars)
    if not parts:
        return []

    result: list[dict[str, Any]] = []
    for i, text in enumerate(parts):
        delay = 0.0 if i == 0 else len(text) / max(chars_per_second, 1.0)
        result.append({
            "text": text,
            "delay_before_seconds": round(delay, 2),
        })

    return result


# ═══ 中断断点管理 ═══

class BreakpointStore:
    """中断断点存储 (per-session)。"""

    def __init__(self, max_per_session: int = 10) -> None:
        self._breakpoints: dict[str, list[InterruptedBreakpoint]] = {}
        self._max_per_session = max_per_session

    def record(
        self,
        session_key: str,
        full_text: str,
        sent_parts: list[str],
        unsent_parts: list[str],
        input_epoch: int = 0,
        reason: str = "",
    ) -> None:
        """记录一个中断断点。"""
        bp = InterruptedBreakpoint(
            full_text=full_text,
            sent_parts=sent_parts,
            unsent_parts=unsent_parts,
            input_epoch=input_epoch,
            reason=reason,
        )
        bps = self._breakpoints.setdefault(session_key, [])
        bps.append(bp)
        # 限制存储大小
        if len(bps) > self._max_per_session:
            self._breakpoints[session_key] = bps[-self._max_per_session:]

    def get_unsent_parts(self, session_key: str) -> list[str]:
        """获取最近一次中断的未发送部分。"""
        bps = self._breakpoints.get(session_key, [])
        if not bps:
            return []
        return bps[-1].unsent_parts

    def get_latest(self, session_key: str) -> InterruptedBreakpoint | None:
        """获取最近一次中断断点。"""
        bps = self._breakpoints.get(session_key, [])
        return bps[-1] if bps else None

    def clear(self, session_key: str) -> None:
        """清除指定 session 的所有断点。"""
        self._breakpoints.pop(session_key, None)

    def to_dict(self) -> dict[str, Any]:
        """序列化。"""
        return {
            k: [
                {
                    "full_text": bp.full_text,
                    "sent_parts": bp.sent_parts,
                    "unsent_parts": bp.unsent_parts,
                    "input_epoch": bp.input_epoch,
                    "reason": bp.reason,
                    "timestamp": bp.timestamp,
                }
                for bp in v
            ]
            for k, v in self._breakpoints.items()
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """反序列化。"""
        for k, v in data.items():
            self._breakpoints[k] = [
                InterruptedBreakpoint(**bp) for bp in v
            ]


# ═══ 对话恢复提示 ═══

def build_resumption_hint(
    last_time: float,
    now: float | None = None,
) -> str | None:
    """构建对话中断恢复提示。

    当距上次对话超过 2 小时时, 生成恢复提示。

    Args:
        last_time: 上次对话的 Unix 时间戳。
        now: 当前时间戳, 默认为 time.time()。

    Returns:
        恢复提示字符串, 不需要恢复时返回 None。
    """
    if now is None:
        now = time.time()

    gap_seconds = now - last_time
    if gap_seconds <= 7200:  # 2 小时
        return None

    gap_hours = int(gap_seconds / 3600)
    if gap_hours < 24:
        return f"[对话恢复] 距上次对话已过{gap_hours}小时。可以自然地问候或提及时间间隔来重新衔接对话。"
    else:
        gap_days = gap_hours // 24
        return f"[对话恢复] 距上次对话已过{gap_days}天。可以自然地问候或提及这段时间的感受来衔接对话。"


# ═══ 主动沉默 ═══

class DeliberateSilence:
    """主动沉默决策: 某些情况下故意不回复或延迟回复。

    三种沉默原因:
      - hurt: 受伤但不想表达 (tension 高 + valence 负)
      - digesting: 在消化信息 (void_pressure 高 + valence 正)
      - content: 满足无需言语 (tension 低)
    """

    def should_be_silent(
        self,
        valence: float,
        tension: float,
        void_pressure: float = 0.0,
    ) -> tuple[bool, str]:
        """判断是否应该主动沉默。

        Args:
            valence: 情绪效价 [-1, 1]。
            tension: 情绪张力 [0, 1]。
            void_pressure: 空虚压力 [0, 5]。

        Returns:
            (是否沉默, 原因) 元组。
        """
        if tension > 0.7 and valence < -0.3:
            return True, "hurt"
        if void_pressure > 3.0 and valence > 0:
            return True, "digesting"
        if tension < -0.5:
            return True, "content"
        return False, ""

    def get_minimal_response(self, reason: str) -> str | None:
        """沉默时的极简回复 (可选)。

        Returns:
            极简回复文本, 或 None (完全不回复)。
        """
        responses = {
            "hurt": "……",
            "digesting": None,
            "content": "嗯。",
        }
        return responses.get(reason)


# ═══ 呼吸节奏控制器 ═══

class BreathingRhythmController:
    """根据情绪张力和话题密度动态调整回复长短交替模式。

    模拟人类对话中的"呼吸感" — 紧张时长短交替加快,
    平静时节奏舒缓, 情绪渐强时回复渐长, 收尾时渐短。

    四种呼吸模式:
      - calm: 短-中-短 (平静对话)
      - intense: 长-短-长-短 (高张力交替)
      - building: 渐长 (情绪积累)
      - winding: 渐短 (对话收尾)

    使用方式:
      每次生成回复前调用 next_length_factor() 获取长度倍率,
      将基础回复长度乘以该倍率得到目标长度。
    """

    PATTERNS: dict[str, list[float]] = {
        "calm": [0.8, 1.0, 0.6],
        "intense": [1.2, 0.5, 1.5, 0.4],
        "building": [0.6, 0.8, 1.0, 1.2],
        "winding": [1.2, 1.0, 0.8, 0.6],
    }

    def __init__(self) -> None:
        self._current_pattern: str = "calm"
        self._pattern_index: int = 0

    def select_pattern(self, tension: float, valence: float) -> str:
        """根据情绪张力和效价选择呼吸模式。

        Args:
            tension: 情绪张力 [0, 1]。
            valence: 情绪效价 [-1, 1]。

        Returns:
            模式名称。
        """
        if tension > 0.6:
            return "intense"
        elif tension > 0.3 and valence < 0:
            return "building"
        elif valence > 0.5:
            return "winding"
        return "calm"

    def next_length_factor(self, tension: float, valence: float) -> float:
        """返回下一条回复的长度倍率。

        Args:
            tension: 情绪张力 [0, 1]。
            valence: 情绪效价 [-1, 1]。

        Returns:
            长度倍率 [0.4, 1.5]。
        """
        pattern_name = self.select_pattern(tension, valence)
        if pattern_name != self._current_pattern:
            self._current_pattern = pattern_name
            self._pattern_index = 0

        pattern = self.PATTERNS[self._current_pattern]
        factor = pattern[self._pattern_index % len(pattern)]
        self._pattern_index += 1
        return factor

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_pattern": self._current_pattern,
            "pattern_index": self._pattern_index,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._current_pattern = data.get("current_pattern", "calm")
        self._pattern_index = data.get("pattern_index", 0)


# ═══ 主调度器 (组合以上组件) ═══

@register(
    name="realtime_dispatch",
    provides=["RealtimeDispatch"],
    depends_on=[],
)
class RealtimeDispatch:
    """即时聊天调度器 — 组合分段、中断、沉默、呼吸。

    纯数据结构输出, 不涉及 async/IO。
    实际消息发送由宿主插件负责。
    """

    def __init__(self) -> None:
        self._breakpoints = BreakpointStore()
        self._silence = DeliberateSilence()
        self._breathing = BreathingRhythmController()

    # ── 分段 ──

    def segment_text(self, text: str, max_part_chars: int = 48) -> list[str]:
        """文本分段。"""
        return segment_text(text, max_part_chars)

    def build_segmented_parts(
        self,
        full_text: str,
        max_part_chars: int = 48,
        chars_per_second: float = 7.5,
    ) -> list[dict[str, Any]]:
        """生成分段发送计划。"""
        return build_segmented_parts(full_text, max_part_chars, chars_per_second)

    def extract_first_sentence(self, text: str) -> str:
        """提取首句。"""
        return extract_first_sentence(text)

    # ── 中断 ──

    def record_interrupted_reply_breakpoint(
        self,
        session_key: str,
        full_text: str,
        sent_parts: list[str],
        unsent_parts: list[str],
        input_epoch: int = 0,
        reason: str = "",
    ) -> None:
        """记录中断断点。"""
        self._breakpoints.record(
            session_key, full_text, sent_parts, unsent_parts,
            input_epoch, reason,
        )

    def get_unsent_parts(self, session_key: str) -> list[str]:
        """获取最近一次中断的未发送部分。"""
        return self._breakpoints.get_unsent_parts(session_key)

    def get_latest_breakpoint(self, session_key: str) -> InterruptedBreakpoint | None:
        """获取最近一次中断断点。"""
        return self._breakpoints.get_latest(session_key)

    def clear_breakpoints(self, session_key: str) -> None:
        """清除断点。"""
        self._breakpoints.clear(session_key)

    # ── 对话恢复 ──

    def build_resumption_hint(self, last_time: float, now: float | None = None) -> str | None:
        """构建对话恢复提示。"""
        return build_resumption_hint(last_time, now)

    # ── 主动沉默 ──

    def should_be_silent(
        self,
        valence: float,
        tension: float,
        void_pressure: float = 0.0,
    ) -> tuple[bool, str]:
        """判断是否应该主动沉默。"""
        return self._silence.should_be_silent(valence, tension, void_pressure)

    def get_minimal_response(self, reason: str) -> str | None:
        """获取沉默时的极简回复。"""
        return self._silence.get_minimal_response(reason)

    # ── 呼吸节奏 ──

    def next_length_factor(self, tension: float, valence: float) -> float:
        """获取下一条回复的长度倍率。"""
        return self._breathing.next_length_factor(tension, valence)

    def select_breathing_pattern(self, tension: float, valence: float) -> str:
        """获取当前呼吸模式名称。"""
        return self._breathing.select_pattern(tension, valence)

    # ── 序列化 ──

    def to_dict(self) -> dict[str, Any]:
        return {
            "breakpoints": self._breakpoints.to_dict(),
            "breathing": self._breathing.to_dict(),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        if "breakpoints" in data:
            self._breakpoints.from_dict(data["breakpoints"])
        if "breathing" in data:
            self._breathing.from_dict(data["breathing"])
