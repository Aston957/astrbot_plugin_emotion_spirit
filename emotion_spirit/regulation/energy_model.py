"""Energy model with circadian rhythm and personality modulation."""
from __future__ import annotations
from ..core.registry import register
from ..core.utils import clamp


ENERGY_CURVE = {
    "morning":   0.85, "midday":  0.60,
    "afternoon": 0.40, "evening": 0.70,
    "night":     0.25,
}


@register(name="energy_model", provides=["EnergyModel"], depends_on=[])
class EnergyModel:
    """Circadian energy model with personality modulation."""

    def get_energy_level(self, personality: dict, time_slot: str) -> float:
        base = ENERGY_CURVE.get(time_slot, 0.5)
        base += 0.1 * (personality.get("extraversion", 0.5) - 0.5)
        base += 0.05 * (personality.get("neuroticism", 0.5) - 0.5)
        return clamp(base, 0.1, 1.0)

    def apply_energy_bias(self, category_weights: dict, energy_level: float) -> dict:
        if energy_level > 0.6:
            category_weights["physical"] = category_weights.get("physical", 0) + 0.2
            category_weights["social"] = category_weights.get("social", 0) + 0.1
        elif energy_level < 0.4:
            category_weights["rest"] = category_weights.get("rest", 0) + 0.2
            category_weights["intellectual"] = category_weights.get("intellectual", 0) + 0.1
        return category_weights


def get_energy_level(personality: dict, time_slot: str) -> float:
    return EnergyModel().get_energy_level(personality, time_slot)


def apply_energy_bias(category_weights: dict, energy_level: float) -> dict:
    return EnergyModel().apply_energy_bias(category_weights, energy_level)