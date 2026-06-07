"""emotion_spirit 插件工厂 (Phase B, P3-1)。

装配 28 个模块, 返回 dict[name, instance]。
走 ModuleRegistry 的元数据 + 手动装配 (混合 L2):
- ModuleRegistry.get_all() 提供模块元数据 (name + deps)
- 手动装配: 复杂模块 (constructor 多参 / 需要 persona_id + labels) 显式连线
- 简单模块 (无依赖 + 无参) 走 registry.build()

main.py 用 build(config) 替代手写 28 行 init。
"""
from __future__ import annotations
from typing import Any

from .registry import ModuleRegistry


# 24 个有 provides 的模块 (utility 4: emotion_classifier/label_mapper/persona_profiles/trend_utils 不实例化)
_INSTANTIABLE_MODULES = [
    "store",
    "surface_consumer",
    "memory_pool",
    "buffer_signals",
    "intimacy",
    "superego",
    "superego_guard",
    "meaning_reservoir",
    "pattern_extractor",
    "shadow_detector",
    "life_simulator",
    "diary_writer",
    "prompt_injector",
    "personality_drift",
    "predictive_sentinel",
    "narrative_identity",
    "counterfactual",
    "persona_analyzer",
    "relationship_personality",
    "social_graph",
    "topic_privacy",
    "bot_decision",
    "knowledge",
    "persona_report_parser",
]


def default_config(
    *,
    data_dir: str | None = None,
    persona_id: str = "",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """默认配置: 24 个有 provides 的模块全部 enabled, utility 4 跳过。

    Args:
        data_dir: SpiritStore 数据目录 (必填, 除非 store disabled)
        persona_id: superego/ideal/alignment 的 persona 标识
        labels: IdealSelf 的 5 轴标签

    Returns:
        形如 {"modules": {name: {"enabled": bool}}, "params": {...}}
    """
    modules: dict[str, Any] = {}
    for name in _INSTANTIABLE_MODULES:
        modules[name] = {"enabled": True}

    return {
        "modules": modules,
        "params": {
            "data_dir": data_dir or "data",
            "persona_id": persona_id,
            "labels": labels or {},
        },
    }


def build(config: dict[str, Any]) -> dict[str, Any]:
    """装配所有 enabled 模块, 返回 dict[name, instance]。

    Args:
        config: 形如 {
            "modules": {"name": {"enabled": bool}},
            "params": {"data_dir": str, "persona_id": str, "labels": dict}
        }

    Returns:
        dict[module_name, instance]:
        - 简单模块直接是 instance (如 memory_pool, intimacy)
        - 复杂模块如 superego 是 dict[str, instance] 含 alignment/conscience/resistance/ideal
        - 复杂模块如 prompt_injector 是 instance
    """
    modules_cfg = config.get("modules", {})
    params = config.get("params", {})
    data_dir = params.get("data_dir", "data")
    persona_id = params.get("persona_id", "")
    labels = params.get("labels", {})

    # 检查哪些模块 enabled
    enabled = {
        name for name in _INSTANTIABLE_MODULES
        if modules_cfg.get(name, {}).get("enabled", True)
    }

    out: dict[str, Any] = {}

    # ═══ 1. 无依赖 + 无参模块 (按字母序) ═══
    if "counterfactual" in enabled and "memory_pool" in enabled:
        from .memory_pool import MemoryPool
        from .counterfactual import Counterfactual
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        out["counterfactual"] = Counterfactual(out["memory_pool"])

    if "diary_writer" in enabled and "memory_pool" in enabled:
        from .memory_pool import MemoryPool
        from .pattern_extractor import PatternExtractor
        from .buffer_signals import BufferSignals
        from .superego import ValueAlignment, ConscienceTracker
        from .diary_writer import DiaryWriter
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        if "buffer_signals" not in out:
            out["buffer_signals"] = BufferSignals(out["memory_pool"])
        if "pattern_extractor" not in out:
            out["pattern_extractor"] = PatternExtractor(out["memory_pool"])
        if "superego" not in out:
            out["superego"] = _build_superego(persona_id, labels)
        out["diary_writer"] = DiaryWriter(
            out["memory_pool"],
            out["pattern_extractor"],
            out["buffer_signals"],
            out["superego"]["alignment"],
            out["superego"]["conscience"],
        )

    if "intimacy" in enabled:
        from .intimacy import IntimacyTracker
        out["intimacy"] = IntimacyTracker()

    if "knowledge" in enabled:
        from .knowledge import KnowledgeBase
        out["knowledge"] = KnowledgeBase()

    if "meaning_reservoir" in enabled:
        from .meaning_reservoir import MeaningReservoir
        out["meaning_reservoir"] = MeaningReservoir()

    if "persona_analyzer" in enabled:
        from .persona_analyzer import PersonaAnalyzer
        out["persona_analyzer"] = PersonaAnalyzer(llm=None)  # 实际 LLM 由 caller 注入

    if "persona_report_parser" in enabled:
        from .persona_report_parser import PersonaReportParser
        out["persona_report_parser"] = PersonaReportParser()

    if "relationship_personality" in enabled:
        from .relationship_personality import RelationshipPersonality
        out["relationship_personality"] = RelationshipPersonality()

    if "social_graph" in enabled:
        from .social_graph import SocialGraph
        out["social_graph"] = SocialGraph()

    if "store" in enabled:
        from .store import SpiritStore
        out["store"] = SpiritStore(data_dir)

    if "surface_consumer" in enabled:
        from .surface_consumer import SurfaceConsumer
        out["surface_consumer"] = SurfaceConsumer()

    if "topic_privacy" in enabled:
        from .topic_privacy import TopicPrivacy
        out["topic_privacy"] = TopicPrivacy()  # 无参

    if "bot_decision" in enabled:
        from .bot_decision import BotDecisionMaker
        if "social_graph" not in out:
            from .social_graph import SocialGraph
            out["social_graph"] = SocialGraph()
        if "topic_privacy" not in out:
            from .topic_privacy import TopicPrivacy
            out["topic_privacy"] = TopicPrivacy()
        out["bot_decision"] = BotDecisionMaker(
            social_graph=out["social_graph"],
            topic_privacy=out["topic_privacy"],
            gossip_tendency=0.0,
        )

    # ═══ 2. buffer_signals (1 依赖) ═══
    if "buffer_signals" in enabled and "memory_pool" in enabled:
        from .memory_pool import MemoryPool
        from .buffer_signals import BufferSignals
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        out["buffer_signals"] = BufferSignals(out["memory_pool"])

    # ═══ 3. pattern_extractor (1 依赖) ═══
    if "pattern_extractor" in enabled and "memory_pool" in enabled:
        from .memory_pool import MemoryPool
        from .pattern_extractor import PatternExtractor
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        out["pattern_extractor"] = PatternExtractor(out["memory_pool"])

    # ═══ 4. shadow_detector (3 依赖) ═══
    if "shadow_detector" in enabled:
        from .memory_pool import MemoryPool
        from .buffer_signals import BufferSignals
        from .pattern_extractor import PatternExtractor
        from .shadow_detector import ShadowDetector
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        if "buffer_signals" not in out:
            out["buffer_signals"] = BufferSignals(out["memory_pool"])
        if "pattern_extractor" not in out:
            out["pattern_extractor"] = PatternExtractor(out["memory_pool"])
        out["shadow_detector"] = ShadowDetector(
            out["memory_pool"],
            out["buffer_signals"],
            out["pattern_extractor"],
        )

    # ═══ 5. life_simulator (5 依赖) ═══
    if "life_simulator" in enabled:
        from .memory_pool import MemoryPool
        from .buffer_signals import BufferSignals
        from .meaning_reservoir import MeaningReservoir
        from .intimacy import IntimacyTracker
        from .surface_consumer import SurfaceConsumer
        from .life_simulator import LifeSimulator
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        if "buffer_signals" not in out:
            out["buffer_signals"] = BufferSignals(out["memory_pool"])
        if "meaning_reservoir" not in out:
            out["meaning_reservoir"] = MeaningReservoir()
        if "intimacy" not in out:
            out["intimacy"] = IntimacyTracker()
        if "surface_consumer" not in out:
            out["surface_consumer"] = SurfaceConsumer()
        out["life_simulator"] = LifeSimulator(
            out["surface_consumer"],
            out["memory_pool"],
            out["intimacy"],
            out["buffer_signals"],
            out["meaning_reservoir"],
        )

    # ═══ 6. personality_drift (2 依赖) ═══
    if "personality_drift" in enabled:
        from .surface_consumer import SurfaceConsumer
        from .meaning_reservoir import MeaningReservoir
        from .personality_drift import PersonalityDrift
        if "surface_consumer" not in out:
            out["surface_consumer"] = SurfaceConsumer()
        if "meaning_reservoir" not in out:
            out["meaning_reservoir"] = MeaningReservoir()
        out["personality_drift"] = PersonalityDrift(
            out["surface_consumer"],
            out["meaning_reservoir"],
        )

    # ═══ 7. predictive_sentinel (6 依赖) ═══
    if "predictive_sentinel" in enabled:
        from .surface_consumer import SurfaceConsumer
        from .buffer_signals import BufferSignals
        from .pattern_extractor import PatternExtractor
        from .shadow_detector import ShadowDetector
        from .memory_pool import MemoryPool
        from .meaning_reservoir import MeaningReservoir
        from .superego import ValueAlignment, ConscienceTracker
        from .superego import IdealSelf
        from .predictive_sentinel import PredictiveSentinel
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        if "buffer_signals" not in out:
            out["buffer_signals"] = BufferSignals(out["memory_pool"])
        if "pattern_extractor" not in out:
            out["pattern_extractor"] = PatternExtractor(out["memory_pool"])
        if "shadow_detector" not in out:
            out["shadow_detector"] = ShadowDetector(
                out["memory_pool"],
                out["buffer_signals"],
                out["pattern_extractor"],
            )
        if "meaning_reservoir" not in out:
            out["meaning_reservoir"] = MeaningReservoir()
        if "surface_consumer" not in out:
            out["surface_consumer"] = SurfaceConsumer()
        if "superego" not in out:
            out["superego"] = _build_superego(persona_id, labels)
        out["predictive_sentinel"] = PredictiveSentinel(
            out["surface_consumer"],
            out["buffer_signals"],
            out["meaning_reservoir"],
            out["superego"]["conscience"],
            out["superego"]["alignment"],
            out["superego"]["ideal"],
        )

    # ═══ 8. narrative_identity (5 依赖) ═══
    if "narrative_identity" in enabled:
        from .memory_pool import MemoryPool
        from .buffer_signals import BufferSignals
        from .pattern_extractor import PatternExtractor
        from .personality_drift import PersonalityDrift
        from .surface_consumer import SurfaceConsumer
        from .meaning_reservoir import MeaningReservoir
        from .diary_writer import DiaryWriter
        from .superego import ValueAlignment, ConscienceTracker
        from .narrative_identity import NarrativeIdentity
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        if "buffer_signals" not in out:
            out["buffer_signals"] = BufferSignals(out["memory_pool"])
        if "pattern_extractor" not in out:
            out["pattern_extractor"] = PatternExtractor(out["memory_pool"])
        if "personality_drift" not in out:
            sc = out.get("surface_consumer")
            if sc is None:
                sc = SurfaceConsumer()
                out["surface_consumer"] = sc
            mr = out.get("meaning_reservoir")
            if mr is None:
                mr = MeaningReservoir()
                out["meaning_reservoir"] = mr
            out["personality_drift"] = PersonalityDrift(sc, mr)
        if "diary_writer" not in out:
            if "surface_consumer" not in out:
                from .surface_consumer import SurfaceConsumer
                out["surface_consumer"] = SurfaceConsumer()
            if "meaning_reservoir" not in out:
                out["meaning_reservoir"] = MeaningReservoir()
            if "superego" not in out:
                out["superego"] = _build_superego(persona_id, labels)
            out["diary_writer"] = DiaryWriter(
                out["memory_pool"],
                out["pattern_extractor"],
                out["buffer_signals"],
                out["superego"]["alignment"],
                out["superego"]["conscience"],
            )
        out["narrative_identity"] = NarrativeIdentity(
            out["memory_pool"],
            out["pattern_extractor"],
            out["personality_drift"],
            out["buffer_signals"],
            out["diary_writer"],
        )

    # ═══ 9. prompt_injector (8 依赖, 含 superego 3 sub) ═══
    if "prompt_injector" in enabled:
        from .memory_pool import MemoryPool
        from .buffer_signals import BufferSignals
        from .pattern_extractor import PatternExtractor
        from .shadow_detector import ShadowDetector
        from .intimacy import IntimacyTracker
        from .relationship_personality import RelationshipPersonality
        from .surface_consumer import SurfaceConsumer
        from .meaning_reservoir import MeaningReservoir
        from .diary_writer import DiaryWriter
        from .superego import ValueAlignment, ConscienceTracker, IdealSelf
        from .prompt_injector import PromptInjector
        if "memory_pool" not in out:
            out["memory_pool"] = MemoryPool()
        if "buffer_signals" not in out:
            out["buffer_signals"] = BufferSignals(out["memory_pool"])
        if "pattern_extractor" not in out:
            out["pattern_extractor"] = PatternExtractor(out["memory_pool"])
        if "shadow_detector" not in out:
            out["shadow_detector"] = ShadowDetector(
                out["memory_pool"],
                out["buffer_signals"],
                out["pattern_extractor"],
            )
        if "intimacy" not in out:
            out["intimacy"] = IntimacyTracker()
        if "relationship_personality" not in out:
            out["relationship_personality"] = RelationshipPersonality()
        if "superego" not in out:
            out["superego"] = _build_superego(persona_id, labels)
        if "diary_writer" not in out:
            out["diary_writer"] = DiaryWriter(
                out["memory_pool"],
                out["pattern_extractor"],
                out["buffer_signals"],
                out["superego"]["alignment"],
                out["superego"]["conscience"],
            )
        out["prompt_injector"] = PromptInjector(
            out["memory_pool"],
            out["intimacy"],
            out["superego"]["alignment"],
            out["superego"]["conscience"],
            out["superego"]["ideal"],
            out["shadow_detector"],
            out["diary_writer"],
            buffer_signals=out["buffer_signals"],
        )

    # ═══ 10. superego (4 components) + superego_guard ═══
    if "superego" in enabled and "superego" not in out:
        out["superego"] = _build_superego(persona_id, labels)

    if "superego_guard" in enabled:
        from .superego_guard import SuperegoGuard
        if "superego" not in out:
            out["superego"] = _build_superego(persona_id, labels)
        out["superego_guard"] = SuperegoGuard(
            out["superego"]["conscience"],
            out["superego"]["alignment"],
            out["superego"]["ideal"],
            persona=persona_id,
        )

    return out


def _build_superego(persona_id: str, labels: dict[str, str]) -> dict[str, Any]:
    """构建 superego 4 个 sub-components。"""
    from .superego import ValueAlignment, ConscienceTracker, IdealSelf, ValueResistance
    return {
        "alignment": ValueAlignment(persona_id),
        "conscience": ConscienceTracker(),
        "resistance": ValueResistance(persona_id),
        "ideal": IdealSelf(persona_id, labels),
    }
