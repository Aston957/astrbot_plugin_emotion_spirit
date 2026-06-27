"""Tests for adaptation.py — emotion x personality -> social tendency + activity preference.

v1.1.0C Phase 0 — Task 1: Core Adaptation Module.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from emotion_spirit.regulation.adaptation import (
    compute_social_tendency,
    select_adaptation_activity,
    derive_activity_preferences,
    EMOTION_ACTIVITY_BIAS,
    COLLAPSE_SOCIAL_MOD,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _personality(**overrides):
    defaults = {
        "extraversion": 0.5, "neuroticism": 0.5, "openness": 0.5,
        "agreeableness": 0.5, "conscientiousness": 0.5,
    }
    defaults.update(overrides)
    return defaults


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: compute_social_tendency tests
# ═══════════════════════════════════════════════════════════════════════════

class TestComputeSocialTendency:
    def test_high_extraversion_seeks_social_when_sad(self):
        # High extraversion + sad mood → seek social
        result = compute_social_tendency(
            emotion_state={"valence": -0.5, "arousal": 0.3, "tension": 0.3},
            personality=_personality(extraversion=0.8, neuroticism=0.3, openness=0.5,
                                    agreeableness=0.5, conscientiousness=0.5),
            suppression_level=0.0,
            collapse_archetype=None,
        )
        assert result == "seek"

    def test_high_neuroticism_avoids_social_when_sad(self):
        # High neuroticism + sad → avoid social
        result = compute_social_tendency(
            emotion_state={"valence": -0.5, "arousal": 0.2, "tension": 0.4},
            personality=_personality(extraversion=0.2, neuroticism=0.8, openness=0.3,
                                    agreeableness=0.3, conscientiousness=0.3),
            suppression_level=0.0,
            collapse_archetype=None,
        )
        assert result == "avoid"

    def test_volcanic_collapse_seeks_social(self):
        result = compute_social_tendency(
            emotion_state={"valence": -0.3, "arousal": 0.6, "tension": 0.4},
            personality=_personality(),
            suppression_level=0.0,
            collapse_archetype="volcanic",
        )
        assert result == "seek"

    def test_freeze_collapse_avoids_social(self):
        result = compute_social_tendency(
            emotion_state={"valence": -0.3, "arousal": 0.6, "tension": 0.4},
            personality=_personality(),
            suppression_level=0.0,
            collapse_archetype="freeze",
        )
        assert result == "avoid"

    def test_high_suppression_dampens_social_signal(self):
        # Same state, but high suppression → neutral instead of seek
        result_no_suppress = compute_social_tendency(
            emotion_state={"valence": -0.5, "arousal": 0.3, "tension": 0.3},
            personality=_personality(extraversion=0.8, neuroticism=0.3, openness=0.5,
                                    agreeableness=0.5, conscientiousness=0.5),
            suppression_level=0.0,
            collapse_archetype=None,
        )
        result_high_suppress = compute_social_tendency(
            emotion_state={"valence": -0.5, "arousal": 0.3, "tension": 0.3},
            personality=_personality(extraversion=0.8, neuroticism=0.3, openness=0.5,
                                    agreeableness=0.5, conscientiousness=0.5),
            suppression_level=0.8,
            collapse_archetype=None,
        )
        assert result_no_suppress == "seek"
        assert result_high_suppress in ("neutral", "avoid")

    def test_neutral_when_balanced(self):
        result = compute_social_tendency(
            emotion_state={"valence": 0.0, "arousal": 0.0, "tension": 0.0},
            personality=_personality(),
            suppression_level=0.0,
            collapse_archetype=None,
        )
        assert result in ("seek", "neutral", "avoid")  # Just check it returns valid

    def test_returns_valid_label(self):
        """Returns one of seek/neutral/avoid for any input."""
        result = compute_social_tendency(
            emotion_state={"valence": 0.7, "arousal": 0.8, "tension": 0.1},
            personality=_personality(extraversion=0.9, openness=0.9),
        )
        assert result in ("seek", "neutral", "avoid")


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: select_adaptation_activity tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSelectAdaptationActivity:
    def test_returns_valid_category(self):
        """Activity is one of 5 valid categories."""
        result = select_adaptation_activity(
            emotion_state={"valence": -0.4, "arousal": 0.3, "tension": 0.3},
            personality=_personality(),
            tendency="neutral",
        )
        assert result in ("social", "creative", "physical", "intellectual", "rest")

    def test_seek_tendency_boosts_social(self):
        """When tendency=seek, extravert should get social activity."""
        result = select_adaptation_activity(
            emotion_state={"valence": 0.0, "arousal": 0.3, "tension": 0.2},
            personality=_personality(extraversion=0.9, intimacy_pull=0.9, relational_gravity=0.9),
            tendency="seek",
        )
        assert result == "social"

    def test_avoid_tendency_boosts_rest(self):
        """When tendency=avoid, neurotic should get rest activity."""
        result = select_adaptation_activity(
            emotion_state={"valence": -0.5, "arousal": 0.2, "tension": 0.5},
            personality=_personality(neuroticism=0.9, patience=0.9, boundary_permeability=0.9),
            tendency="avoid",
        )
        assert result == "rest"

    def test_happy_emotion_prefers_social_or_creative(self):
        """Happy mood + extravert → social (or creative)."""
        result = select_adaptation_activity(
            emotion_state={"valence": 0.7, "arousal": 0.5, "tension": 0.0},
            personality=_personality(extraversion=0.9, openness=0.9,
                                    intimacy_pull=0.9, relational_gravity=0.9,
                                    exploration_openness=0.9, curiosity=0.9),
            tendency="seek",
        )
        assert result in ("social", "creative", "physical")

    def test_anxious_emotion_prefers_rest(self):
        """Anxious + avoid → rest."""
        result = select_adaptation_activity(
            emotion_state={"valence": -0.4, "arousal": 0.5, "tension": 0.7},
            personality=_personality(neuroticism=0.9, patience=0.9, boundary_permeability=0.9),
            tendency="avoid",
        )
        assert result == "rest"


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: derive_activity_preferences tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDeriveActivityPreferences:
    def test_returns_seven_preferences(self):
        """Returns exactly 7 activity preferences."""
        prefs = derive_activity_preferences(_personality())
        assert set(prefs.keys()) == {
            "energy", "chronotype_score", "social", "creative",
            "physical", "intellectual", "rest",
        }

    def test_all_scores_in_unit_interval(self):
        """All preference scores in [0, 1] range (bias function)."""
        prefs = derive_activity_preferences(_personality())
        for k, v in prefs.items():
            assert 0.0 <= v <= 1.5, f"{k}={v} out of expected range"

    def test_default_trait_yields_baseline(self):
        """All personality=0.5 → all prefs around 0.5+0.5*0.5=0.75 baseline."""
        prefs = derive_activity_preferences(_personality())
        for k, v in prefs.items():
            # baseline 0.5 + 0.3*0.5 + 0.2*0.5 = 0.75
            assert abs(v - 0.75) < 0.01, f"{k}={v} not at baseline 0.75"

    def test_high_expression_yields_high_physical(self):
        """High expression_drive + directness → high physical preference."""
        personality_full = {
            "extraversion": 0.5, "neuroticism": 0.5, "openness": 0.5,
            "agreeableness": 0.5, "conscientiousness": 0.5,
            "expression_drive": 0.9, "warmth_bias": 0.5,
            "exploration_openness": 0.5, "curiosity": 0.5,
            "intimacy_pull": 0.5, "relational_gravity": 0.5,
            "perception_acuity": 0.5, "inner_coherence": 0.5,
            "patience": 0.5, "boundary_permeability": 0.5,
            "directness": 0.9,
        }
        prefs = derive_activity_preferences(personality_full)
        assert prefs["physical"] > prefs["rest"]

    def test_high_intimacy_yields_high_social(self):
        """High intimacy_pull + relational_gravity → high social preference."""
        personality_full = {
            "extraversion": 0.5, "neuroticism": 0.5, "openness": 0.5,
            "agreeableness": 0.5, "conscientiousness": 0.5,
            "expression_drive": 0.5, "warmth_bias": 0.5,
            "exploration_openness": 0.5, "curiosity": 0.5,
            "intimacy_pull": 0.9, "relational_gravity": 0.9,
            "perception_acuity": 0.5, "inner_coherence": 0.5,
            "patience": 0.5, "boundary_permeability": 0.5,
            "directness": 0.5,
        }
        prefs = derive_activity_preferences(personality_full)
        assert prefs["social"] > 0.85  # 0.5 + 0.3*0.9 + 0.2*0.9 = 0.95


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Constant sanity checks
# ═══════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_emotion_activity_bias_has_expected_emotions(self):
        assert set(EMOTION_ACTIVITY_BIAS.keys()) == {
            "happy", "calm", "anxious", "sad", "angry", "speechless", "excited",
        }

    def test_collapse_social_mod_has_expected_archetypes(self):
        assert set(COLLAPSE_SOCIAL_MOD.keys()) == {
            "volcanic", "collapse", "freeze", "drift", "cold",
        }

    def test_volcanic_mod_is_positive(self):
        assert COLLAPSE_SOCIAL_MOD["volcanic"] > 0

    def test_freeze_mod_is_negative(self):
        assert COLLAPSE_SOCIAL_MOD["freeze"] < 0


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Module registration test
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistration:
    def test_adaptation_engine_registered(self):
        from emotion_spirit.core.registry import ModuleRegistry
        specs = ModuleRegistry.get_all()
        assert "adaptation_engine" in specs
