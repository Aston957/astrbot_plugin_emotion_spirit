"""emotion_spirit — Sylanne Engine 之上的长期记忆、人格演化与超我调控。

显式 import 所有 @register 装饰模块 (Phase B P3-7 衔接)。
import emotion_spirit 触发 28 模块装饰器注册, 确保 registry.build(config) 拿到 28 个 ModuleSpec。
B6 plugin_factory.py 依赖此副作用。
"""
from . import (
    store, knowledge, label_mapper, emotion_classifier, surface_consumer,
    memory_pool, buffer_signals, intimacy, relationship_personality, superego,
    superego_guard, meaning_reservoir, pattern_extractor, shadow_detector,
    life_simulator, diary_writer, prompt_injector, personality_drift,
    predictive_sentinel, narrative_identity, counterfactual, persona_analyzer,
    persona_profiles, persona_report_parser, social_graph, topic_privacy,
    bot_decision, trend_utils, force_dynamics,
)
