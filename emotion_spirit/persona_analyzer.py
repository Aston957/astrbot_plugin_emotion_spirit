"""LLM 人格分析器 — 从 AstrBot 人格文本提取 5 轴标签。

与 persona_report_parser 的区别:
  - persona_report_parser: 规则 + 关键词推断（快速，不需要 LLM）
  - persona_analyzer: LLM 深度分析（更准确，需要 LLM 调用）

流程:
  1. 读取 AstrBot 人格的 system_prompt
  2. 发给 LLM，要求返回 5 轴标签 JSON
  3. 用 label_mapper.labels_to_personality() 将标签转为 13 维
  4. 返回结果，可存入 data/persona_report.json

使用方式:
  analyzer = PersonaAnalyzer(llm_callable)
  result = await analyzer.analyze(system_prompt)
  # result.labels, result.personality, result.confidence
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from astrbot.api import logger

from .label_mapper import LABEL_OPTIONS, labels_to_personality


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

@dataclass
class PersonaAnalysisResult:
    """人格分析结果。"""
    persona_id: str
    labels: dict[str, str]
    personality: dict[str, dict[str, float]]
    confidence: float
    analyzed_at: str = ""
    source: str = "llm"  # "llm" | "fallback"

    def __post_init__(self) -> None:
        if not self.analyzed_at:
            self.analyzed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "labels": self.labels,
            "personality": self.personality,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonaAnalysisResult:
        return cls(
            persona_id=data.get("persona_id", ""),
            labels=data.get("labels", {}),
            personality=data.get("personality", {}),
            confidence=data.get("confidence", 0.0),
            analyzed_at=data.get("analyzed_at", ""),
            source=data.get("source", "unknown"),
        )


# ═══ 分析器 ═══

# 类型别名: async (system_prompt, user_prompt) -> str
LLMCallable = Callable[[str, str], Awaitable[str]]


from .registry import register


@register(name="persona_analyzer", provides=["PersonaAnalyzer"], depends_on=[])
class PersonaAnalyzer:
    """使用 LLM 从人格文本提取 5 轴标签并推导 13 维参数。"""

    def __init__(self, llm: LLMCallable) -> None:
        self._llm = llm

    async def analyze(self, persona_id: str, system_prompt: str) -> PersonaAnalysisResult:
        """分析人格文本，返回标签和参数。

        如果 LLM 调用失败，回退到 persona_report_parser 的规则推断。
        """
        if not system_prompt:
            logger.warning("persona_analyzer: system_prompt 为空")
            return self._fallback_result(persona_id, "")

        # 构建 prompt
        system_msg = _SYSTEM_PROMPT.format(
            mbti_options=", ".join(LABEL_OPTIONS["mbti"]),
            attachment_options=", ".join(LABEL_OPTIONS["attachment"]),
            emotion_style_options=", ".join(LABEL_OPTIONS["emotion_style"]),
            conflict_style_options=", ".join(LABEL_OPTIONS["conflict_style"]),
            time_focus_options=", ".join(LABEL_OPTIONS["time_focus"]),
        )
        user_msg = _USER_PROMPT_TEMPLATE.format(text=system_prompt[:3000])  # 截断避免 token 过长

        try:
            # 调用 LLM
            raw_response = await self._llm(system_msg, user_msg)
            labels = self._parse_llm_response(raw_response)

            if labels:
                # 验证所有标签都在可选值内
                labels = self._validate_labels(labels)
                personality = labels_to_personality(labels)
                logger.info(
                    "persona_analyzer: LLM 分析成功 — persona=%s labels=%s",
                    persona_id, labels,
                )
                return PersonaAnalysisResult(
                    persona_id=persona_id,
                    labels=labels,
                    personality=personality,
                    confidence=0.85,
                    source="llm",
                )
            else:
                logger.warning("persona_analyzer: LLM 返回无法解析，回退到规则推断")
                return self._fallback_result(persona_id, system_prompt)

        except Exception:
            logger.warning("persona_analyzer: LLM 调用失败，回退到规则推断", exc_info=True)
            return self._fallback_result(persona_id, system_prompt)

    def _parse_llm_response(self, raw: str) -> dict[str, str] | None:
        """解析 LLM 返回的 JSON。"""
        # 尝试直接解析
        try:
            data = json.loads(raw.strip())
            if isinstance(data, dict) and "mbti" in data:
                return data
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        import re
        json_match = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1).strip())
                if isinstance(data, dict) and "mbti" in data:
                    return data
            except json.JSONDecodeError:
                pass

        return None

    def _validate_labels(self, labels: dict[str, str]) -> dict[str, str]:
        """验证标签值是否在可选范围内，不在范围内的用默认值替换。"""
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
                if value:
                    logger.debug(
                        "persona_analyzer: 标签 %s='%s' 不在可选范围内，使用默认 '%s'",
                        key, value, default,
                    )
        return validated

    def _fallback_result(self, persona_id: str, system_prompt: str) -> PersonaAnalysisResult:
        """回退到 persona_report_parser 的规则推断。"""
        from .persona_report_parser import parse_persona_report

        if system_prompt:
            parsed = parse_persona_report(system_prompt)
            labels = parsed.labels if parsed.has_labels else self._default_labels()
        else:
            labels = self._default_labels()

        personality = labels_to_personality(labels)

        logger.info("persona_analyzer: 使用规则推断回退 — persona=%s labels=%s", persona_id, labels)

        return PersonaAnalysisResult(
            persona_id=persona_id,
            labels=labels,
            personality=personality,
            confidence=0.5,
            source="fallback",
        )

    @staticmethod
    def _default_labels() -> dict[str, str]:
        return {
            "mbti": "ISTJ",
            "attachment": "安全型",
            "emotion_style": "混合型",
            "conflict_style": "合作型",
            "time_focus": "活在当下",
        }


# ═══ 持久化 ═══

_REPORT_FILE = "persona_report.json"


def save_report(result: PersonaAnalysisResult, data_dir: Path) -> None:
    """保存分析结果到 data 目录。"""
    path = data_dir / _REPORT_FILE
    try:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            f.flush()
            import os
            os.fsync(f.fileno())
        import os
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
