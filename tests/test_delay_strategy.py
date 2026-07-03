"""Tests for TypingDelayStrategy (v1.2.5 PR1 §5)."""
from emotion_spirit.output.segmented_reply_coordinator import TypingDelayStrategy


class TestTypingDelayStrategy:
    """Unit tests for TypingDelayStrategy.compute_delay()."""

    def test_typing_delay_short_text_short_delay(self):
        """Short text should produce delay proportional to text length."""
        strategy = TypingDelayStrategy()
        config = {"default_chars_per_second": 10.0, "max_delay_seconds": 5.0}
        delay = strategy.compute_delay("hi", config)
        # 2 chars / 10 cps = 0.2s
        assert 0.0 < delay < 1.0, f"Expected short delay, got {delay}"
        assert abs(delay - 0.2) < 0.01

    def test_typing_delay_long_text_capped(self):
        """Long text should be capped at max_delay_seconds."""
        strategy = TypingDelayStrategy()
        config = {"default_chars_per_second": 10.0, "max_delay_seconds": 0.5}
        long_text = "x" * 100  # 100 chars / 10 cps = 10s, capped at 0.5s
        delay = strategy.compute_delay(long_text, config)
        assert delay == 0.5

    def test_typing_delay_zero_cps_fallback_to_max(self):
        """Zero or negative cps should fall back to max_delay_seconds."""
        strategy = TypingDelayStrategy()
        config = {"default_chars_per_second": 0.0, "max_delay_seconds": 2.0}
        delay = strategy.compute_delay("hello world", config)
        assert delay == 2.0

    def test_typing_delay_no_config_uses_defaults(self):
        """Empty config should use built-in defaults (7.5 cps, 2.0s max)."""
        strategy = TypingDelayStrategy()
        delay = strategy.compute_delay("hello", {})
        # 5 chars / 7.5 cps ≈ 0.667s
        assert 0.5 < delay < 1.0, f"Expected ~0.667s delay, got {delay}"
        assert abs(delay - (5 / 7.5)) < 0.01

    def test_typing_delay_max_delay_never_exceeded(self):
        """Edge case: ensure max_delay is never exceeded even with very long text."""
        strategy = TypingDelayStrategy()
        config = {"default_chars_per_second": 7.5, "max_delay_seconds": 2.0}
        very_long = "x" * 1000  # would be 133s without cap
        delay = strategy.compute_delay(very_long, config)
        assert delay == 2.0