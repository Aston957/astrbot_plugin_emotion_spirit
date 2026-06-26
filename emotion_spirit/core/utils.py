"""Shared utility functions for emotion_spirit."""
from __future__ import annotations
from typing import Any

__all__ = ["clamp", "safe_float"]


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi] range."""
    return max(lo, min(hi, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to finite float, with fallback."""
    try:
        f = float(value)
        import math
        if not math.isfinite(f):
            return default
        return f
    except (TypeError, ValueError):
        return default
