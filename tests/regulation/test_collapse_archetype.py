"""Tests for collapse_archetype.py — 5 collapse behavioral archetypes."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.regulation.collapse_archetype import CollapseArchetype, CollapseArchetypeSelector


def _personality(**overrides):
    defaults = {"neuroticism": 0.5, "extraversion": 0.5, "openness": 0.5,
                "agreeableness": 0.5, "conscientiousness": 0.5}
    defaults.update(overrides)
    return defaults


def test_compute_bas_bis_basic():
    """BAS and BIS are computed from personality."""
    sel = CollapseArchetypeSelector()
    bas, bis = sel.compute_bas_bis(_personality())
    assert 0 <= bas <= 1
    assert 0 <= bis <= 1


def test_high_extraversion_high_bas():
    """High extraversion -> higher BAS."""
    sel = CollapseArchetypeSelector()
    bas_high, _ = sel.compute_bas_bis(_personality(extraversion=0.9))
    bas_low, _ = sel.compute_bas_bis(_personality(extraversion=0.1))
    assert bas_high > bas_low


def test_high_neuroticism_high_bis():
    """High neuroticism -> higher BIS."""
    sel = CollapseArchetypeSelector()
    _, bis_high = sel.compute_bas_bis(_personality(neuroticism=0.9))
    _, bis_low = sel.compute_bas_bis(_personality(neuroticism=0.1))
    assert bis_high > bis_low


def test_select_volcano():
    """High BAS -> VOLCANO."""
    sel = CollapseArchetypeSelector()
    p = _personality(extraversion=0.9, openness=0.8, neuroticism=0.1, agreeableness=0.3)
    archetype = sel.select(p)
    assert archetype == CollapseArchetype.VOLCANO


def test_select_collapse():
    """High BIS + high agreeableness -> COLLAPSE."""
    sel = CollapseArchetypeSelector()
    p = _personality(neuroticism=0.8, agreeableness=0.8, extraversion=0.3)
    archetype = sel.select(p)
    assert archetype == CollapseArchetype.COLLAPSE


def test_select_freeze():
    """High BIS + low extraversion -> FREEZE."""
    sel = CollapseArchetypeSelector()
    p = _personality(neuroticism=0.9, extraversion=0.2, agreeableness=0.4)
    archetype = sel.select(p)
    assert archetype == CollapseArchetype.FREEZE


def test_select_cold():
    """High conscientiousness + low neuroticism -> COLD."""
    sel = CollapseArchetypeSelector()
    p = _personality(conscientiousness=0.8, neuroticism=0.2, extraversion=0.5)
    archetype = sel.select(p)
    assert archetype == CollapseArchetype.COLD


def test_select_drift_default():
    """Default -> DRIFT."""
    sel = CollapseArchetypeSelector()
    p = _personality(neuroticism=0.4, extraversion=0.5, agreeableness=0.4,
                     conscientiousness=0.4, openness=0.5)
    archetype = sel.select(p)
    assert archetype == CollapseArchetype.DRIFT


def test_get_prompt_volcano():
    """VOLCANO archetype has a prompt."""
    sel = CollapseArchetypeSelector()
    prompt = sel.get_prompt(CollapseArchetype.VOLCANO)
    assert "情绪崩溃" in prompt
    assert len(prompt) > 20


def test_get_prompt_all_archetypes():
    """All 5 archetypes have prompts."""
    sel = CollapseArchetypeSelector()
    for arch in CollapseArchetype:
        prompt = sel.get_prompt(arch)
        assert len(prompt) > 20


def test_archetype_is_enum():
    """CollapseArchetype is an enum with 5 members."""
    assert len(CollapseArchetype) == 5
