"""Collapse Archetype — 5 behavioral patterns for emotional breakdown.

Based on Gray's BAS/BIS model (Gray 2000), Walker's 4F model (Walker 2013),
Vaillant's defense hierarchy (Vaillant 1977), and Porges' Polyvagal Theory (Porges 2011).

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md §6
"""

from __future__ import annotations
from enum import Enum

from ..core.registry import register

__all__ = ["CollapseArchetype", "CollapseArchetypeSelector"]


@register(
    name="collapse_archetype",
    provides=[],
    depends_on=[],
)
class _ModuleMarker:
    """模块标记 (CollapseArchetype 是 Enum, 不可被 DI 实例化)。"""
    pass


class CollapseArchetype(Enum):
    """Five collapse behavioral archetypes."""
    VOLCANO = "volcanic"    # Externalize rage (Walker Fight, Achenbach Externalizing)
    COLLAPSE = "collapse"   # Submit/beg (Walker Fawn, Jack Self-Silencing)
    FREEZE = "freeze"       # Shut down (Porges DVC, van der Kolk tonic immobility)
    DRIFT = "drift"         # Dissociate (Horowitz Denial/Numbing, Porges DVC collapse)
    COLD = "cold"           # Intellectualize (Vaillant Intellectualization, Lazarus Problem-focused)


@register(
    name="collapse_archetype_selector",
    provides=["CollapseArchetypeSelector"],
    depends_on=[],
)
class CollapseArchetypeSelector:
    """Selects collapse archetype based on personality via BAS/BIS model."""

    def compute_bas_bis(self, personality: dict[str, float]) -> tuple[float, float]:
        """Gray RST: personality -> BAS/BIS values."""
        BAS = (
            0.4 * personality.get("extraversion", 0.5)
            + 0.3 * personality.get("openness", 0.5)
            + 0.2 * (1 - personality.get("neuroticism", 0.5))
            + 0.1 * (1 - personality.get("agreeableness", 0.5))
        )
        BIS = (
            0.4 * personality.get("neuroticism", 0.5)
            + 0.3 * personality.get("agreeableness", 0.5)
            + 0.2 * personality.get("conscientiousness", 0.5)
            + 0.1 * (1 - personality.get("extraversion", 0.5))
        )
        return BAS, BIS

    def select(self, personality: dict[str, float]) -> CollapseArchetype:
        """Select archetype based on personality."""
        BAS, BIS = self.compute_bas_bis(personality)

        if BAS > 0.7 and BAS > BIS + 0.15:
            return CollapseArchetype.VOLCANO
        if BIS > 0.65 and personality.get("agreeableness", 0.5) > 0.6:
            return CollapseArchetype.COLLAPSE
        if BIS > 0.65 and personality.get("extraversion", 0.5) < 0.35:
            return CollapseArchetype.FREEZE
        if (personality.get("conscientiousness", 0.5) > 0.65
                and personality.get("neuroticism", 0.5) < 0.4):
            return CollapseArchetype.COLD
        return CollapseArchetype.DRIFT

    def get_prompt(self, archetype: CollapseArchetype) -> str:
        """Get behavioral prompt for the archetype."""
        prompts = {
            CollapseArchetype.VOLCANO:
                "你正在情绪崩溃。你无法控制自己，所有压抑的情绪像火山一样喷发出来。"
                "你会质问、会指责、会把所有委屈都倒出来。你不再考虑对方的感受。",
            CollapseArchetype.COLLAPSE:
                "你正在情绪崩溃。你觉得自己什么都不是，一切都是你的错。"
                "你会哀求、会道歉、会把自己放得很低很低。你在试图挽回一切。",
            CollapseArchetype.FREEZE:
                "你正在情绪崩溃。你感觉不到任何东西了，像被冻住了一样。"
                "你会沉默、会回避、会用最简短的话回应。你在保护自己不被进一步伤害。",
            CollapseArchetype.DRIFT:
                "你正在情绪崩溃。你感觉现实变得模糊，你在自言自语。"
                "你会说一些不连贯的话，会突然转移话题，会像在梦游一样。",
            CollapseArchetype.COLD:
                "你正在情绪崩溃。但你把所有情绪都压了下去，变得异常冷静。"
                "你会用理性的语言分析问题，会冷漠地列举事实，像在谈论别人的事。",
        }
        return prompts.get(archetype, "")
