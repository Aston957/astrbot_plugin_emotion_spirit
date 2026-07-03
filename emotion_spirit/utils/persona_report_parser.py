"""人格报告解析器 — 从 AstrBot persona system_prompt 自动提取人格参数。

混合解析策略:
  1. 规则解析: 提取结构化数据 (Markdown 表格、YAML 块)
  2. 关键词推断: 从描述文本推断标签
  3. 兜底: 解析失败时返回 None，由调用方决定是否使用预设

这是初始化阶段的"基调"设定，后续由演化系统接管。
"""

from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger


# ═══ 正则模式 ═══

# Markdown 表格行: | key | value |
_RE_TABLE_ROW = re.compile(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|")

# YAML 块
_RE_YAML_BLOCK = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)

# YAML 键值对: key: value
_RE_YAML_KV = re.compile(r"(\w+)\s*:\s*(.+)")

# MBTI 模式 (4 个字母)
_RE_MBTI = re.compile(r"\b([EI][NS][FT][PJ])\b", re.IGNORECASE)

# 驱动力模式: curiosity | 7 / 10
_RE_DRIVE = re.compile(r"\|\s*(\w+)\s*\|\s*(\d+(?:\.\d+)?)\s*/\s*10\s*\|")

# 数值模式: | key | 0.20 |
_RE_NUMERIC = re.compile(r"\|\s*(\w+)\s*\|\s*(\d+(?:\.\d+)?)\s*\|")


# ═══ 关键词映射表 ═══

# 依恋类型推断
_ATTACHMENT_KEYWORDS: dict[str, list[str]] = {
    "焦虑型": ["焦虑", "在意", "在乎", "敏感", "怕被冷落", "怕被敷衍", "依赖", "撒娇", "敏感"],
    "回避型": ["回避", "独立", "保持距离", "不依赖", "独处", "需要空间"],
    "安全型": ["安全", "稳定", "信任", "平衡", "自在"],
    "混乱型": ["混乱", "矛盾", "不稳定", "忽冷忽热"],
}

# 情绪策略推断
_EMOTION_STYLE_KEYWORDS: dict[str, list[str]] = {
    "表达型": ["直接表达", "情绪都在脸上", "不藏事", "说出来", "表达感受", "哭笑闹"],
    "压抑型": ["压抑", "藏", "憋", "不说", "内敛"],
    "混合型": ["混合", "有时表达有时压抑"],
}

# 冲突风格推断
_CONFLICT_STYLE_KEYWORDS: dict[str, list[str]] = {
    "攻击型": ["攻击", "吵架", "尖锐", "指责", "批评"],
    "回避型": ["回避冲突", "逃避", "不说", "忍让", "沉默"],
    "顺应型": ["顺应", "撒娇", "妥协", "让步", "哄", "道歉", "原谅"],
    "合作型": ["合作", "沟通", "协商", "一起解决", "商量"],
}

# 时间取向推断
_TIME_FOCUS_KEYWORDS: dict[str, list[str]] = {
    "活在过去": ["过去", "回忆", "怀念", "以前"],
    "活在当下": ["当下", "现在", "此刻", "今天"],
    "活在未来": ["未来", "计划", "目标", "以后"],
}

# 9-A: 否定语境下的时间取向排除词
_TIME_FOCUS_NEGATIONS: dict[str, list[str]] = {
    "活在未来": [r"不.*未来", r"没有.*未来", r"不是.*未来"],
}


# ═══ 解析结果数据类 ═══


__all__ = [
    "ParsedPersona",
    "PersonaReportParser",
    "parse_persona_report",
    "get_labels_from_report",
    "get_drives_from_report",
]

class ParsedPersona:
    """解析后的人格参数。"""

    def __init__(
        self,
        labels: dict[str, str] | None = None,
        drives: dict[str, float] | None = None,
        hot_pool_params: dict[str, float] | None = None,
        traits: list[str] | None = None,
        raw_mbti: str | None = None,
    ) -> None:
        self.labels = labels or {}
        self.drives = drives or {}
        self.hot_pool_params = hot_pool_params or {}
        self.traits = traits or []
        self.raw_mbti = raw_mbti  # 直接从报告提取的 MBTI

    @property
    def has_labels(self) -> bool:
        return bool(self.labels)

    @property
    def has_drives(self) -> bool:
        return bool(self.drives)

    def __repr__(self) -> str:
        return (
            f"ParsedPersona(labels={self.labels}, drives={self.drives}, "
            f"traits={self.traits})"
        )


# ═══ 主解析器 ═══

class PersonaReportParser:
    """从 AstrBot persona system_prompt 自动解析人格参数。"""

    def parse(self, system_prompt: str) -> ParsedPersona:
        """解析 system_prompt，返回 ParsedPersona。

        解析优先级:
        1. 结构化数据 (表格、YAML)
        2. 关键词推断
        3. 返回 None (由调用方决定是否使用预设)
        """
        if not system_prompt:
            return ParsedPersona()

        result = ParsedPersona()

        # Step 1: 提取结构化数据
        self._extract_from_tables(system_prompt, result)
        self._extract_from_yaml(system_prompt, result)

        # Step 2: 如果 MBTI 还没找到，用正则扫描全文
        if not result.raw_mbti:
            mbti_match = _RE_MBTI.search(system_prompt)
            if mbti_match:
                result.raw_mbti = mbti_match.group(1).upper()

        # Step 3: 设置 MBTI 标签
        if result.raw_mbti:
            result.labels["mbti"] = result.raw_mbti.upper()

        # Step 4: 关键词推断缺失的标签
        self._infer_missing_labels(system_prompt, result)

        # Step 5: 如果是叙事风格报告，提取更多信息
        if not result.traits or not result.drives:
            self._extract_from_narrative(system_prompt, result)

        # Step 6: 规范化驱动力 (0-10 → 0-1)
        self._normalize_drives(result)

        logger.info(
            "persona_report_parser: parsed labels=%s drives=%s traits=%s",
            result.labels, result.drives, result.traits,
        )

        return result

    # ═══ 结构化数据提取 ═══

    def _extract_from_tables(self, text: str, result: ParsedPersona) -> None:
        """从 Markdown 表格提取数据。"""
        for match in _RE_TABLE_ROW.finditer(text):
            key = match.group(1).strip().lower()
            value = match.group(2).strip()

            # 基本信息表
            if key == "mbti":
                mbti_match = _RE_MBTI.search(value)
                if mbti_match:
                    result.raw_mbti = mbti_match.group(1).upper()

            # 驱动力表: | curiosity | 7 / 10 |
            drive_match = _RE_DRIVE.search(match.group(0))
            if drive_match:
                drive_name = drive_match.group(1).strip().lower()
                drive_value = float(drive_match.group(2))
                result.drives[drive_name] = drive_value

        # 单独扫描驱动力表 (可能不在标准表格行中)
        for drive_match in _RE_DRIVE.finditer(text):
            drive_name = drive_match.group(1).strip().lower()
            drive_value = float(drive_match.group(2))
            result.drives[drive_name] = drive_value

        # 扫描数值表 (热池参数)
        for num_match in _RE_NUMERIC.finditer(text):
            key = num_match.group(1).strip().lower()
            value = float(num_match.group(2))
            # 只收集已知的热池参数
            if key in {
                "pressure_capacity", "eruption_threshold",
                "release_normal", "warm_flow_speed",
                "suppression_tendency", "suppression_multiplier",
                "ruminate_depth",
            }:
                result.hot_pool_params[key] = value

    def _extract_from_yaml(self, text: str, result: ParsedPersona) -> None:
        """从 YAML 块提取数据。"""
        yaml_blocks = _RE_YAML_BLOCK.findall(text)
        for block in yaml_blocks:
            for kv_match in _RE_YAML_KV.finditer(block):
                key = kv_match.group(1).strip()
                value = kv_match.group(2).strip().strip("'\"")

                if key == "mbti_hint":
                    mbti_match = _RE_MBTI.search(value)
                    if mbti_match:
                        result.raw_mbti = mbti_match.group(1).upper()

                elif key == "traits":
                    # 解析列表: ["开朗", "细腻", "感性", "偶尔emo"]
                    traits = self._parse_yaml_list(value)
                    result.traits = traits

                elif key == "speech_style":
                    # 保存供后续推断使用
                    pass

                elif key == "emotional_range":
                    # 保存供后续推断使用
                    pass

    def _parse_yaml_list(self, value: str) -> list[str]:
        """解析 YAML 列表: ["a", "b", "c"] → ["a", "b", "c"]"""
        # 去掉方括号
        value = value.strip("[]")
        # 按逗号分割，去掉引号
        items = []
        for item in value.split(","):
            item = item.strip().strip("'\"")
            if item:
                items.append(item)
        return items

    # ═══ 叙事风格报告处理 ═══

    def _extract_from_narrative(self, text: str, result: ParsedPersona) -> None:
        """从叙事风格的报告中提取信息。"""
        text_lower = text.lower()

        # 提取性格特征 (从描述性词语)
        trait_patterns = [
            r"性格[是为：:]\s*([^，。,.]+)",
            r"是一个[的]?\s*([^，。,.]+)的?人",
            r"特点[是为：:]\s*([^，。,.]+)",
            r"他[是为]?\s*([^，。,.]+)",
        ]
        for pattern in trait_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # 清理并添加特征
                traits = [t.strip() for t in re.split(r"[、，,]", match) if t.strip()]
                for trait in traits:
                    if 2 <= len(trait) <= 6 and trait not in result.traits:
                        result.traits.append(trait)

        # 从行为描述中提取更准确的特征
        behavior_traits = {
            "沉默寡言": [r"不太.*说话", r"沉默", r"安静", r"话少"],
            "内向": [r"独处", r"一个人", r"不太.*社交", r"不喜欢.*社交"],
            "专注": [r"专注", r"认真", r"投入", r"沉迷"],
            "固执": [r"固执", r"坚持", r"不妥协", r"死磕"],
            "幽默": [r"幽默", r"搞笑", r"调侃", r"吐槽"],
            "敏感": [r"敏感", r"在意", r"在乎", r"注意.*细节"],
        }
        for trait, patterns in behavior_traits.items():
            for pattern in patterns:
                if re.search(pattern, text) and trait not in result.traits:
                    result.traits.append(trait)
                    break

        # 提取驱动力 (从行为描述)
        drive_patterns = {
            "curiosity": [r"好奇", r"探索", r"尝试新", r"喜欢.*新", r"研究", r"沉迷"],
            "expression": [r"表达", r"说出来", r"直接", r"坦率", r"吐槽", r"喃喃自语"],
            "connection": [r"连接", r"关系", r"在乎", r"在意", r"朋友", r"队友", r"室友"],
        }
        for drive, patterns in drive_patterns.items():
            if drive not in result.drives:
                score = 0.5  # 默认中等
                for pattern in patterns:
                    if re.search(pattern, text):
                        score = 0.7  # 有相关描述
                        break
                result.drives[drive] = score

        # 推断 MBTI (如果没有明确提到)
        if "mbti" not in result.labels:
            result.labels["mbti"] = self._infer_mbti_from_narrative(text)

    def _infer_mbti_from_narrative(self, text: str) -> str:
        """从叙事描述中推断 MBTI (v1.2.2 B9-fix: 不偏向 INTJ 轴 + 否定词预处理)。"""
        text_lower = text.lower()

        # 9-A: 否定词预处理 — 检测 "而不是/不是/没/不" 后的词，抵消被否定项
        negation_patterns = [
            r"而不是\s*(\S+)",
            r"不是\s*(\S+)",
            r"不\s*(\S+)",
            r"没\s*(\S+)",
        ]
        negated_words: set[str] = set()
        for pattern in negation_patterns:
            for match in re.findall(pattern, text_lower):
                negated_words.add(match)

        # E vs I (外向 vs 内向) — v1.2.2: 补 "开朗", tie 时倾向 E
        e_patterns = [r"社交", r"朋友多", r"喜欢.*聚会", r"外向", r"健谈", r"开朗", r"活泼", r"热情"]
        i_patterns = [r"独处", r"一个人", r"内向", r"安静", r"沉默", r"不太.*社交", r"孤僻"]

        e_score = sum(1 for p in e_patterns if re.search(p, text_lower))
        i_score = sum(1 for p in i_patterns if re.search(p, text_lower))
        # 9-A: tie-breaking 不偏向 I，倾向 E(中文 prompt 描述外向更常见)
        if e_score == i_score:
            ei = "E"
        else:
            ei = "E" if e_score > i_score else "I"

        # N vs S (直觉 vs 感觉) — tie 时倾向 N(日常描述中 N 更常见)
        n_patterns = [r"想象", r"创意", r"直觉", r"未来", r"可能性", r"灵感", r"抽象"]
        s_patterns = [r"细节", r"实际", r"现实", r"具体", r"经验", r"务实"]

        n_score = sum(1 for p in n_patterns if re.search(p, text_lower))
        s_score = sum(1 for p in s_patterns if re.search(p, text_lower))
        if n_score == s_score:
            ns = "N"
        else:
            ns = "N" if n_score > s_score else "S"

        # F vs T (情感 vs 思考) — 9-A: 否定词预处理 + tie 时倾向 F
        f_patterns = [r"情感", r"感受", r"在乎.*感受", r"共情", r"体贴", r"直觉.*感受", r"感性"]
        t_patterns = [r"逻辑", r"理性", r"分析", r"思考", r"客观", r"理智"]

        f_score = sum(1 for p in f_patterns if re.search(p, text_lower))
        t_score = sum(1 for p in t_patterns if re.search(p, text_lower))
        # 9-A: 如果被否定的词匹配某方模式，从该方扣分
        for word in negated_words:
            for p in t_patterns:
                if re.search(p, word):
                    t_score -= 1
            for p in f_patterns:
                if re.search(p, word):
                    f_score -= 1
        # tie-breaking 不偏向 T，倾向 F(中文日常描述情感远多于理性)
        if f_score == t_score:
            ft = "F"
        else:
            ft = "F" if f_score > t_score else "T"

        # P vs J (知觉 vs 判断) — tie 时倾向 P
        p_patterns = [r"灵活", r"随性", r"自由", r" spontaneous", r"拖延", r"随机应变", r"不.*计划"]
        j_patterns = [r"计划", r" organized", r"有条理", r"准时", r" deadline", r"安排", r"规划"]

        p_score = sum(1 for p in p_patterns if re.search(p, text_lower))
        j_score = sum(1 for p in j_patterns if re.search(p, text_lower))
        if p_score == j_score:
            pj = "P"
        else:
            pj = "P" if p_score > j_score else "J"

        return ei + ns + ft + pj

    # ═══ 关键词推断 ═══

    def _infer_missing_labels(self, text: str, result: ParsedPersona) -> None:
        """从描述文本推断缺失的标签。"""
        text_lower = text.lower()

        # 依恋类型
        if "attachment" not in result.labels:
            result.labels["attachment"] = self._infer_by_keywords(
                text_lower, _ATTACHMENT_KEYWORDS, default="安全型",
            )

        # 情绪策略
        if "emotion_style" not in result.labels:
            result.labels["emotion_style"] = self._infer_by_keywords(
                text_lower, _EMOTION_STYLE_KEYWORDS, default="混合型",
            )

        # 冲突风格
        if "conflict_style" not in result.labels:
            result.labels["conflict_style"] = self._infer_by_keywords(
                text_lower, _CONFLICT_STYLE_KEYWORDS, default="合作型",
            )

        # 时间取向 (9-A: 否定语境特殊处理)
        if "time_focus" not in result.labels:
            time_focus = self._infer_by_keywords(
                text_lower, _TIME_FOCUS_KEYWORDS, default="活在当下",
            )
            # 9-A: 如果推断为"活在未来"但存在否定语境(如"不活在未来")，回退到"活在当下"
            if time_focus == "活在未来":
                for neg_pattern in _TIME_FOCUS_NEGATIONS.get("活在未来", []):
                    if re.search(neg_pattern, text_lower):
                        time_focus = "活在当下"
                        break
            result.labels["time_focus"] = time_focus

    def _infer_by_keywords(
        self,
        text: str,
        keyword_map: dict[str, list[str]],
        default: str,
    ) -> str:
        """根据关键词匹配推断标签值。

        策略: 统计每个候选值的关键词命中次数，选最高的。
        """
        scores: dict[str, int] = {}
        for label_value, keywords in keyword_map.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[label_value] = score

        if not scores:
            return default

        return max(scores, key=scores.get)

    # ═══ 驱动力规范化 ═══

    def _normalize_drives(self, result: ParsedPersona) -> None:
        """将驱动力规范化到 0-1 范围。"""
        if not result.drives:
            return
        normalized = {}
        for key, value in result.drives.items():
            # 如果值 > 1，假设是 0-10 范围，需要除以 10
            # 如果值 <= 1，已经是 0-1 范围，直接使用
            if value > 1.0:
                normalized[key] = round(min(1.0, max(0.0, value / 10.0)), 4)
            else:
                normalized[key] = round(min(1.0, max(0.0, value)), 4)
        result.drives = normalized


# ═══ 便捷函数 ═══

def parse_persona_report(system_prompt: str) -> ParsedPersona:
    """便捷函数: 解析人格报告。"""
    parser = PersonaReportParser()
    return parser.parse(system_prompt)


def get_labels_from_report(system_prompt: str) -> dict[str, str]:
    """便捷函数: 从人格报告提取标签。"""
    parsed = parse_persona_report(system_prompt)
    return parsed.labels


def get_drives_from_report(system_prompt: str) -> dict[str, float]:
    """便捷函数: 从人格报告提取驱动力 (已规范化到 0-1)。"""
    parsed = parse_persona_report(system_prompt)
    return parsed.drives
