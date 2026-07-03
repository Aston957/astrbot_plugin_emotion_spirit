"""emotion_spirit 人格分析器 (Phase C, P3-6 拆 3 类)。

3 个独立类:
- LLMAnalyzer: 调用 LLM 解析 persona report, 失败抛异常 (caller 决定 fallback)
- RuleBasedAnalyzer: 基于 system_prompt 模式匹配, 无 LLM 依赖
- PersonaAnalyzerWithFallback: LLM 优先, 失败 fallback 到 RuleBased

向后兼容:
- 旧 PersonaAnalyzer(llm) 仍是 PersonaAnalyzerWithFallback 的别名
- save_report / load_report helper 保留
- @register 装饰器保留 (ModuleRegistry 元数据)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from astrbot.api import logger

from ..core.registry import register


# ═══ LLM Prompt ═══

_SYSTEM_PROMPT = """\
你是一个心理学人格分析专家。请从以下人格描述中提取 5 个维度的标签。

维度和可选值:
1. mbti (MBTI 十六型人格): {mbti_options}
2. attachment (依恋风格): {attachment_options}
3. emotion_style (情绪策略): {emotion_style_options}
4. conflict_style (冲突风格): {conflict_style_options}
5. time_focus (时间取向): {time_focus_options}

要求:
- 严格从上述可选值中选择，不要创造新值
- 如果描述中没有明确提到某个维度，根据整体描述推断最可能的值
- 返回严格的 JSON 格式，不要添加任何额外文字

输出格式:
{{"mbti": "XXXX", "attachment": "X型", "emotion_style": "X型", "conflict_style": "X型", "time_focus": "X"}}
"""

_USER_PROMPT_TEMPLATE = "以下是人格描述文本，请分析并返回 5 轴标签:\n\n{text}"


# ═══ 数据类 ═══


__all__ = [
    "PersonaAnalysisResult",
    "LLMAnalyzer",
    "RuleBasedAnalyzer",
    "PersonaAnalyzerWithFallback",
    "save_report",
    "load_report",
]

@dataclass
class PersonaAnalysisResult:
    """人格分析结果 (P3-6: 拆 3 类后的 5 字段 dataclass)。"""
    persona_id: str
    labels: dict[str, str]
    drives: dict[str, float]
    source: str  # "llm" | "rule_based"
    confidence: float = 0.0

    @property
    def has_labels(self) -> bool:
        return bool(self.labels) and any(self.labels.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "labels": self.labels,
            "drives": self.drives,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonaAnalysisResult:
        return cls(
            persona_id=data.get("persona_id", ""),
            labels=data.get("labels", {}),
            drives=data.get("drives", {}),
            source=data.get("source", "rule_based"),
            confidence=data.get("confidence", 0.0),
        )


# ═══ 分析器类 ═══

# 类型别名: async (system_prompt, user_prompt) -> str
LLMCallable = Callable[[str, str], Awaitable[str]]


class LLMAnalyzer:
    """LLM 优先分析器。调用 llm_callable 解析, 失败抛异常 (caller 决定 fallback)。"""

    def __init__(self, llm: LLMCallable) -> None:
        """初始化 LLMAnalyzer。

        Args:
            llm: 异步 callable, 接受 (system_prompt, user_prompt) 返回 str
        """
        self._llm = llm

    async def analyze(self, persona_id: str, system_prompt: str) -> PersonaAnalysisResult:
        """调用 LLM 解析 persona。LLM 失败抛异常 (caller 决定 fallback)。"""
        from ..utils import parse_persona_report
        from ..utils.label_mapper import LABEL_OPTIONS

        if not system_prompt:
            logger.warning("LLMAnalyzer: system_prompt 为空")
            return PersonaAnalysisResult(
                persona_id=persona_id,
                labels={},
                drives={},
                source="llm",
                confidence=0.0,
            )

        # 构建 prompt
        system_msg = _SYSTEM_PROMPT.format(
            mbti_options=", ".join(LABEL_OPTIONS["mbti"]),
            attachment_options=", ".join(LABEL_OPTIONS["attachment"]),
            emotion_style_options=", ".join(LABEL_OPTIONS["emotion_style"]),
            conflict_style_options=", ".join(LABEL_OPTIONS["conflict_style"]),
            time_focus_options=", ".join(LABEL_OPTIONS["time_focus"]),
        )
        user_msg = _USER_PROMPT_TEMPLATE.format(text=system_prompt[:3000])

        # 调用 LLM (失败抛异常)
        response = await self._llm(system_msg, user_msg)

        # 尝试从 LLM 响应提取 labels: 优先 JSON 解析, fallback 走 parse_persona_report
        labels = self._parse_llm_response(response)
        if not labels:
            parsed = parse_persona_report(response)
            labels = parsed.labels

        drives = {}
        if labels:
            # drives 走 persona_report_parser 解析 system_prompt (3 维: curiosity/expression/connection)
            try:
                parsed_full = parse_persona_report(system_prompt)
                drives = parsed_full.drives
            except Exception:
                drives = {}

        if labels:
            logger.info(
                "LLMAnalyzer: LLM 分析成功 — persona=%s labels=%s",
                persona_id, labels,
            )
            return PersonaAnalysisResult(
                persona_id=persona_id,
                labels=labels,
                drives=drives,
                source="llm",
                confidence=0.85,
            )
        else:
            # LLM 成功但 labels 为空 — 返回空 result, source 仍记 llm
            logger.warning("LLMAnalyzer: LLM 返回无法解析 labels — persona=%s", persona_id)
            return PersonaAnalysisResult(
                persona_id=persona_id,
                labels={},
                drives={},
                source="llm",
                confidence=0.0,
            )

    def _parse_llm_response(self, raw: str) -> dict[str, str] | None:
        """解析 LLM 返回的 JSON (兼容 markdown 代码块)。"""
        if not raw:
            return None
        # 尝试直接解析
        try:
            data = json.loads(raw.strip())
            if isinstance(data, dict) and "mbti" in data:
                return self._validate_labels(data)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        import re
        json_match = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1).strip())
                if isinstance(data, dict) and "mbti" in data:
                    return self._validate_labels(data)
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _validate_labels(labels: dict[str, str]) -> dict[str, str]:
        """验证标签值是否在 LABEL_OPTIONS 范围内, 不在的用默认值。"""
        from ..utils.label_mapper import LABEL_OPTIONS

        defaults = {
            "mbti": "ISTJ",
            "attachment": "安全型",
            "emotion_style": "混合型",
            "conflict_style": "合作型",
            "time_focus": "活在当下",
        }
        validated = {}
        for key, default in defaults.items():
            value = labels.get(key, "")
            if value in LABEL_OPTIONS.get(key, []):
                validated[key] = value
            else:
                validated[key] = default
        return validated


class RuleBasedAnalyzer:
    """规则分析器。无 LLM 依赖, 基于 system_prompt 模式匹配 (走 persona_report_parser)。"""

    async def analyze(self, persona_id: str, system_prompt: str) -> PersonaAnalysisResult:
        """基于 system_prompt 模式匹配提取 labels 和 drives。"""
        from ..utils import parse_persona_report

        parsed = parse_persona_report(system_prompt)
        logger.info(
            "RuleBasedAnalyzer: 规则解析 — persona=%s labels=%s",
            persona_id, parsed.labels,
        )
        return PersonaAnalysisResult(
            persona_id=persona_id,
            labels=parsed.labels,
            drives=parsed.drives,
            source="rule_based",
            confidence=0.5,
        )


@register(
    name="persona_analyzer",
    provides=["PersonaAnalyzer"],
    depends_on=[],
    config_keys={"llm", "fallback"},
)
class PersonaAnalyzerWithFallback:
    """LLM 优先 + 失败 fallback 到 RuleBased。

    用法:
        analyzer = PersonaAnalyzerWithFallback(llm=some_llm)
        result = await analyzer.analyze(persona_id, system_prompt)
    """

    def __init__(
        self,
        llm: LLMCallable | None = None,
        fallback: RuleBasedAnalyzer | None = None,
    ) -> None:
        """初始化。

        Args:
            llm: 异步 callable 或 None (None 时直接走 fallback)
            fallback: RuleBasedAnalyzer 实例或 None (默认新建)
        """
        self._llm: LLMAnalyzer | None = LLMAnalyzer(llm) if llm is not None else None
        self._fallback: RuleBasedAnalyzer = fallback or RuleBasedAnalyzer()

    def configure(self, llm: LLMCallable | None = None) -> None:
        """Post-build LLM 注入。由 main.py 在 context ready 后调用。"""
        if llm is not None:
            self._llm = LLMAnalyzer(llm)

    async def analyze(self, persona_id: str, system_prompt: str) -> PersonaAnalysisResult:
        """先试 LLM, 失败 (异常或无 labels) fallback 到 RuleBased。"""
        if self._llm is not None:
            try:
                result = await self._llm.analyze(persona_id, system_prompt)
                if result.has_labels:
                    return result
                # LLM 成功但无 labels, 也走 fallback
                logger.warning(
                    "PersonaAnalyzerWithFallback: LLM 无 labels, 走 RuleBased — persona=%s",
                    persona_id,
                )
            except Exception:
                logger.warning(
                    "PersonaAnalyzerWithFallback: LLM 失败, 走 RuleBased — persona=%s",
                    persona_id, exc_info=True,
                )
        return await self._fallback.analyze(persona_id, system_prompt)


# ═══ 向后兼容别名 ═══

# 旧 PersonaAnalyzer(llm) 仍是 PersonaAnalyzerWithFallback 的别名
PersonaAnalyzer = PersonaAnalyzerWithFallback


# ═══ 持久化 helper ═══

_REPORT_FILE = "persona_report.json"


def save_report(result: PersonaAnalysisResult, data_dir: Path) -> None:
    """保存分析结果到 data 目录。"""
    path = data_dir / _REPORT_FILE
    try:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        logger.info("persona_analyzer: 报告已保存到 %s", path)
    except OSError:
        logger.warning("persona_analyzer: 保存报告失败", exc_info=True)


def load_report(data_dir: Path) -> PersonaAnalysisResult | None:
    """从 data 目录加载分析结果。"""
    path = data_dir / _REPORT_FILE
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PersonaAnalysisResult.from_dict(data)
    except (json.JSONDecodeError, OSError):
        logger.warning("persona_analyzer: 加载报告失败", exc_info=True)
        return None
