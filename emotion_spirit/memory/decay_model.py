"""Dual-axis decay model -- power law (memory) + exponential (thermal).

memory_decay: R = t^(-b), b ~ 0.27 (Murre & Dros 2015)
thermal_decay: T = T0 * e^(-t/tau), tau = BASE_TAU * (1 + 2*mass) (McGaugh 2000)

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md section 3.2
"""

from __future__ import annotations

import math

__all__ = ["DecayModel"]


class DecayModel:
    """Dual-axis decay functions for the unified memory system."""

    # Power law exponent for memory decay (Ebbinghaus modern revision)
    MEMORY_DECAY_EXPONENT: float = 0.27  # Murre & Dros 2015

    # Base thermal decay time constant (seconds)
    THERMAL_BASE_TAU: float = 2 * 3600  # 2 hours

    @staticmethod
    def clamp(value: float, lo: float, hi: float) -> float:
        """Restrict value to [lo, hi]."""
        return max(lo, min(hi, value))

    def memory_retention(
        self,
        elapsed_hours: float,
        initial_weight: float,
    ) -> float:
        """Power law memory decay: R = W0 * max(t, 0.01)^(-b).

        Args:
            elapsed_hours: Hours since memory creation (or last recall).
            initial_weight: The emotional_weight at creation (or last recall).

        Returns:
            Current retention value (emotional_weight after decay).
        """
        t = max(elapsed_hours, 0.01)  # Avoid division by zero at t=0
        return initial_weight * t ** (-self.MEMORY_DECAY_EXPONENT)

    def thermal_decay(
        self,
        elapsed_seconds: float,
        initial_temp: float,
        mass: float,
        is_ghost: bool = False,
    ) -> float:
        """Exponential thermal decay: T = T0 * e^(-t/tau).

        tau = BASE_TAU * (1 + 2*mass), so higher mass -> slower cooling.
        Ghost memories have zero thermal decay (tau = infinity).

        Args:
            elapsed_seconds: Seconds since last temperature update.
            initial_temp: The temperature at last update.
            mass: Emotional mass [0, 1] -- higher mass slows cooling.
            is_ghost: If True, thermal decay is zero (permanent retention).

        Returns:
            Current temperature after decay.
        """
        if is_ghost:
            return initial_temp

        tau = self.THERMAL_BASE_TAU * (1 + 2 * mass)
        return initial_temp * math.exp(-elapsed_seconds / tau)
