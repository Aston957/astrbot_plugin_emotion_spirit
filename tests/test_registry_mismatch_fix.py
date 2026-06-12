"""Tests for 17/28 mismatch modules @register fix (Phase B6.x)。

每个 mismatch 模块单独 1 测试, 验证 build() 后实例化成功 + wire 正确。
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build_with_defaults():
    """Helper: 装配 28 模块用 default config。"""
    from emotion_spirit.core.plugin_factory import default_config
    from emotion_spirit.core.registry import build
    return build(default_config(
        data_dir="/tmp/test_emotion_spirit_b6x",
        persona_id="INFP-A",
        labels={"EI": "I", "SN": "N", "TF": "F", "JP": "P"},
    ))


# ═══ 1. buffer_signals (1 参 pool) ═══
def test_buffer_signals_param_name_pool_wired():
    """buffer_signals: param name 'pool' 跟 dep 'memory_pool' 不一致, 用 param_wire。"""
    from emotion_spirit.output.buffer_signals import BufferSignals
    instances = _build_with_defaults()
    bs = instances["buffer_signals"]
    assert isinstance(bs, BufferSignals)
    assert bs._pool is instances["memory_pool"]


# ═══ 2. counterfactual (1 参 pool) ═══
def test_counterfactual_param_name_pool_wired():
    """counterfactual: param name 'pool' 跟 dep 'memory_pool' 不一致。"""
    from emotion_spirit.regulation.counterfactual import Counterfactual
    instances = _build_with_defaults()
    cf = instances["counterfactual"]
    assert isinstance(cf, Counterfactual)
    assert cf._pool is instances["memory_pool"]


# ═══ 3. pattern_extractor (1 参 pool) ═══
def test_pattern_extractor_param_name_pool_wired():
    """pattern_extractor: param name 'pool' 跟 dep 'memory_pool' 不一致。"""
    from emotion_spirit.regulation.pattern_extractor import PatternExtractor
    instances = _build_with_defaults()
    pe = instances["pattern_extractor"]
    assert isinstance(pe, PatternExtractor)
    assert pe._pool is instances["memory_pool"]


# ═══ 4. life_simulator (5 参) ═══
def test_life_simulator_5_deps_wired():
    """life_simulator: 5 参 (consumer/pool/intimacy/signals/reservoir), 4 dep wire。"""
    from emotion_spirit.regulation.life_simulator import LifeSimulator
    instances = _build_with_defaults()
    ls = instances["life_simulator"]
    assert isinstance(ls, LifeSimulator)
    assert ls._consumer is instances["surface_consumer"]
    assert ls._memory is instances["memory_pool"]
    assert ls._intimacy is instances["intimacy"]
    assert ls._signals is instances["buffer_signals"]
    assert ls._reservoir is instances["meaning_reservoir"]


# ═══ 5. shadow_detector (3 参) ═══
def test_shadow_detector_3_deps_wired():
    """shadow_detector: 3 参 pool/signals/patterns, 3 dep 全 wire。"""
    from emotion_spirit.regulation.shadow_detector import ShadowDetector
    instances = _build_with_defaults()
    sd = instances["shadow_detector"]
    assert isinstance(sd, ShadowDetector)
    assert sd._pool is instances["memory_pool"]
    assert sd._signals is instances["buffer_signals"]
    assert sd._patterns is instances["pattern_extractor"]


# ═══ 6. predictive_sentinel (6 参) ═══
def test_predictive_sentinel_6_deps_wired():
    """predictive_sentinel: 6 参, 含 superego 3 sub (alignment/conscience/ideal)。"""
    from emotion_spirit.output.predictive_sentinel import PredictiveSentinel
    instances = _build_with_defaults()
    ps = instances["predictive_sentinel"]
    assert isinstance(ps, PredictiveSentinel)
    assert ps._consumer is instances["surface_consumer"]
    assert ps._buffer_signals is instances["buffer_signals"]
    assert ps._reservoir is instances["meaning_reservoir"]
    assert ps._conscience is instances["superego"]["conscience"]
    assert ps._alignment is instances["superego"]["alignment"]
    assert ps._ideal is instances["superego"]["ideal"]


# ═══ 7. prompt_injector (8 参, 含 superego 3 sub) ═══
def test_prompt_injector_superego_sub_deps_wired():
    """prompt_injector: 8 参, 含 superego 3 sub。"""
    from emotion_spirit.output.prompt_injector import PromptInjector
    instances = _build_with_defaults()
    pi = instances["prompt_injector"]
    assert isinstance(pi, PromptInjector)
    assert pi._pool is instances["memory_pool"]
    assert pi._intimacy is instances["intimacy"]
    assert pi._alignment is instances["superego"]["alignment"]
    assert pi._conscience is instances["superego"]["conscience"]
    assert pi._ideal is instances["superego"]["ideal"]
    assert pi._shadow is instances["shadow_detector"]
    assert pi._diary is instances["diary_writer"]
    assert pi._buffer_signals is instances["buffer_signals"]


# ═══ 8. narrative_identity (5 参) ═══
def test_narrative_identity_5_deps_wired():
    """narrative_identity: 5 参 pool/patterns/drift/signals/diary。"""
    from emotion_spirit.output.narrative_identity import NarrativeIdentity
    instances = _build_with_defaults()
    ni = instances["narrative_identity"]
    assert isinstance(ni, NarrativeIdentity)
    assert ni._pool is instances["memory_pool"]
    assert ni._patterns is instances["pattern_extractor"]
    assert ni._drift is instances["personality_drift"]
    assert ni._signals is instances["buffer_signals"]
    assert ni._diary is instances["diary_writer"]


# ═══ 9. diary_writer (5 参, 含 superego 2 sub) ═══
def test_diary_writer_5_deps_wired():
    """diary_writer: 5 参 pool/patterns/signals/alignment/conscience。"""
    from emotion_spirit.output.diary_writer import DiaryWriter
    instances = _build_with_defaults()
    dw = instances["diary_writer"]
    assert isinstance(dw, DiaryWriter)
    assert dw._pool is instances["memory_pool"]
    assert dw._patterns is instances["pattern_extractor"]
    assert dw._signals is instances["buffer_signals"]
    assert dw._alignment is instances["superego"]["alignment"]
    assert dw._conscience is instances["superego"]["conscience"]


# ═══ 10. personality_drift (2 参) ═══
def test_personality_drift_2_deps_wired():
    """personality_drift: 2 参 consumer/reservoir。"""
    from emotion_spirit.regulation.personality_drift import PersonalityDrift
    instances = _build_with_defaults()
    pd = instances["personality_drift"]
    assert isinstance(pd, PersonalityDrift)
    assert pd._consumer is instances["surface_consumer"]
    assert pd._reservoir is instances["meaning_reservoir"]


# ═══ 11. persona_analyzer (config_keys: llm) ═══
def test_persona_analyzer_llm_from_config():
    """persona_analyzer: llm/fallback 从 config["params"] 注入。"""
    from emotion_spirit.regulation.persona_analyzer import PersonaAnalyzerWithFallback
    instances = _build_with_defaults()
    pa = instances["persona_analyzer"]
    assert isinstance(pa, PersonaAnalyzerWithFallback)


# ═══ 12. store (config_keys: data_dir) ═══
def test_store_data_dir_from_config():
    """store: data_dir 从 config["params"] 注入。"""
    from emotion_spirit.store import SpiritStore
    instances = _build_with_defaults()
    s = instances["store"]
    assert isinstance(s, SpiritStore)
    assert "test_emotion_spirit_b6x" in str(s._dir)


# ═══ 13. superego (multi-instance 4 sub) ═══
def test_superego_multi_instance_4_sub():
    """superego: 4 sub (alignment/conscience/resistance/ideal) 通过 provides_classes。"""
    from emotion_spirit.regulation.superego import (
        ValueAlignment, ValueResistance, ConscienceTracker, IdealSelf,
    )
    instances = _build_with_defaults()
    se = instances["superego"]
    assert isinstance(se, dict)
    assert set(se.keys()) == {"alignment", "conscience", "resistance", "ideal"}
    assert isinstance(se["alignment"], ValueAlignment)
    assert isinstance(se["conscience"], ConscienceTracker)
    assert isinstance(se["resistance"], ValueResistance)
    assert isinstance(se["ideal"], IdealSelf)


# ═══ 14. superego_guard (3 dep 全 superego sub) ═══
def test_superego_guard_3_sub_deps_wired():
    """superego_guard: conscience/alignment/ideal 来自 superego sub。"""
    from emotion_spirit.regulation.superego_guard import SuperegoGuard
    instances = _build_with_defaults()
    sg = instances["superego_guard"]
    assert isinstance(sg, SuperegoGuard)
    assert sg._conscience is instances["superego"]["conscience"]
    assert sg._alignment is instances["superego"]["alignment"]
    assert sg._ideal is instances["superego"]["ideal"]


# ═══ 15. bot_decision (config_keys: gossip_tendency) ═══
def test_bot_decision_config_keys_injected():
    """bot_decision: gossip_tendency 从 config["params"] 注入。"""
    from emotion_spirit.output.bot_decision import BotDecisionMaker
    instances = _build_with_defaults()
    bd = instances["bot_decision"]
    assert isinstance(bd, BotDecisionMaker)
    assert bd._social_graph is instances["social_graph"]
    assert bd._topic_privacy is instances["topic_privacy"]
    assert bd._gossip_tendency == 0.0


# ═══ 16. topic_privacy (无参, 删 extra dep) ═══
def test_topic_privacy_no_extra_dep():
    """topic_privacy: 无参, 不应声明 social_graph 依赖。"""
    from emotion_spirit.memory.topic_privacy import TopicPrivacy
    instances = _build_with_defaults()
    tp = instances["topic_privacy"]
    assert isinstance(tp, TopicPrivacy)


# Note: predictive_sentinel 是 test_predictive_sentinel_6_deps_wired (test 6) 唯一覆盖的 mismatch #6 模块。
#       test 6 已包含所有 4 param_wire + 3 superego sub dep wired 验证, 不再需要 placeholder。
