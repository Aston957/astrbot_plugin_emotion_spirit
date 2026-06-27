"""Emotion x personality -> social tendency and activity preference adaptation.

v1.1.0C Phase 0 — Task 1: Core Adaptation Module.

This module provides the personality-driven plan adaptation primitives used by
LifeSimulatorV2 (T3) and the activity engine (T4-T9). It maps the current
emotional state together with the user's personality vector and current
suppression load into:

* a discrete social tendency (seek / neutral / avoid)
* a discrete replacement activity category (social / creative / physical /
  intellectual / rest)
* a 7-dimensional activity preference vector

All three functions are stateless and dependency-free at runtime, which keeps
them easy to embed into LLM prompts and to unit-test in isolation.
"""

from __future__ import annotations

from typing import Any

from ..core.registry import register


__all__ = [
    "EMOTION_ACTIVITY_BIAS",
    "COLLAPSE_SOCIAL_MOD",
    "compute_social_tendency",
    "select_adaptation_activity",
    "derive_activity_preferences",
]


# Emotion → activity bias (literature: Bower 1981, Eich 2000)
EMOTION_ACTIVITY_BIAS: dict[str, dict[str, float]] = {
    "happy":     {"social": +0.3, "creative": +0.2, "physical": +0.1},
    "calm":      {"intellectual": +0.2, "rest": +0.1, "routine": +0.1},
    "anxious":   {"social": -0.2, "rest": +0.2, "creative": +0.1},
    "sad":       {"social": -0.3, "rest": +0.3, "creative": +0.2},
    "angry":     {"social": +0.1, "physical": +0.3, "rest": -0.2},
    "speechless":{"social": -0.1, "intellectual": +0.2, "rest": +0.1},
    "excited":   {"social": +0.4, "physical": +0.2, "creative": +0.1},
}

# Collapse archetype → social tendency modifier
COLLAPSE_SOCIAL_MOD = {
    "volcanic": +0.3,   # wants to vent
    "collapse": +0.3,   # wants comfort
    "freeze":   -0.3,   # shuts down
    "drift":     0.0,   # neutral
    "cold":     -0.3,   # intellectualizes alone
}


@register(
    name="adaptation_engine",
    provides=["AdaptationEngine", "compute_social_tendency", "select_adaptation_activity", "derive_activity_preferences"],
    depends_on=[],
)
class _AdaptationMarker:
    """Marker class for adaptation engine module."""
    pass


def _classify_emotion(valence: float) -> str:
    """Map valence → emotion label for bias lookup."""
    if valence > 0.3:
        return "happy"
    if valence > 0.1:
        return "excited"
    if valence > -0.1:
        return "calm"
    if valence > -0.3:
        return "speechless"
    if valence > -0.5:
        return "anxious"
    return "sad"


def compute_social_tendency(
    emotion_state: dict,
    personality: dict[str, float],
    suppression_level: float = 0.0,
    collapse_archetype: str | None = None,
) -> str:
    """Compute social tendency: 'seek' | 'neutral' | 'avoid'.

    Literature-backed (Gray 1990, PMC11995024 2024):
    - Extraversion → BAS drive (r=.21) → approach motivation
    - Neuroticism → BIS drive (r=-.45) → avoidance motivation
    - Collapse archetype modulates social tendency (Walker 2013 4F model)
    - Suppression dampens social signal (Gross & John 2003)
    """
    E = personality.get("extraversion", 0.5)
    O = personality.get("openness", 0.5)
    N = personality.get("neuroticism", 0.5)
    A = personality.get("agreeableness", 0.5)
    C = personality.get("conscientiousness", 0.5)

    # BAS: extraversion is main driver (DeYoung 2010)
    bas = 0.45 * E + 0.25 * O + 0.15 * (1 - N) + 0.15 * (1 - A)
    # BIS: neuroticism is main driver (Corr 2016)
    bis = 0.50 * N + 0.20 * A + 0.15 * C + 0.15 * (1 - E)

    valence = emotion_state.get("valence", 0.0)
    arousal = emotion_state.get("arousal", 0.0)
    tension = emotion_state.get("tension", 0.0)

    social_signal = valence * 0.3 + (bas - bis) * 1.5 + arousal * 0.2 - tension * 0.2

    # Collapse archetype modulation
    if collapse_archetype:
        social_signal += COLLAPSE_SOCIAL_MOD.get(collapse_archetype, 0.0)

    # Suppression dampening (Gross & John 2003)
    social_signal -= suppression_level * 0.2

    if social_signal > 0.2:
        return "seek"
    if social_signal < -0.2:
        return "avoid"
    return "neutral"


def derive_activity_preferences(personality: dict[str, float]) -> dict[str, float]:
    """Derive 7 activity preferences from 13-dim personality (zero new dimensions).

    Literature:
    - Energy → expression_drive + warmth_bias (DeYoung 2010)
    - Chronotype → exploration_openness + curiosity (PMC11150537)
    - Social → intimacy_pull + relational_gravity (Meta-analysis)
    - Creative → exploration_openness + curiosity (Noba)
    - Physical → expression_drive + directness (Gray 1990)
    - Intellectual → perception_acuity + inner_coherence (Carver 2010)
    - Rest → patience + boundary_permeability (Gross 2003)
    """
    def bias(trait_a: str, trait_b: str, w_a: float = 0.3, w_b: float = 0.2) -> float:
        return 0.5 + w_a * personality.get(trait_a, 0.5) + w_b * personality.get(trait_b, 0.5)

    return {
        "energy": bias("expression_drive", "warmth_bias"),
        "chronotype_score": bias("exploration_openness", "curiosity"),
        "social": bias("intimacy_pull", "relational_gravity"),
        "creative": bias("exploration_openness", "curiosity"),
        "physical": bias("expression_drive", "directness"),
        "intellectual": bias("perception_acuity", "inner_coherence"),
        "rest": bias("patience", "boundary_permeability"),
    }


def select_adaptation_activity(
    emotion_state: dict,
    personality: dict[str, float],
    tendency: str,
) -> str:
    """Select replacement activity category based on emotion x personality x tendency.

    Returns category name: "social" | "creative" | "physical" | "intellectual" | "rest"
    """
    prefs = derive_activity_preferences(personality)
    valence = emotion_state.get("valence", 0.0)
    emotion = _classify_emotion(valence)
    biases = EMOTION_ACTIVITY_BIAS.get(emotion, {})

    # Combine personality preference + emotion bias
    combined: dict[str, float] = {}
    for cat in ("social", "creative", "physical", "intellectual", "rest"):
        combined[cat] = prefs.get(cat, 0.0) + biases.get(cat, 0.0)

    # Tendency modifier: seek → boost social, avoid → boost rest
    if tendency == "seek":
        combined["social"] += 0.3
    elif tendency == "avoid":
        combined["rest"] += 0.3

    return max(combined, key=combined.get)
