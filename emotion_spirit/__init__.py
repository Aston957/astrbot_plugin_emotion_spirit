"""emotion_spirit — Sylanne Engine 之上的长期记忆、人格演化与超我调控。

显式 import 所有 @register 装饰模块 (Phase B P3-7 衔接)。
import emotion_spirit 触发 48 模块装饰器注册, 确保 registry.build(config) 拿到 48 个 ModuleSpec。
B6 plugin_factory.py 依赖此副作用。

Phase 3.0B Task 3: +body_state (29 → 30)
Phase 3.0C Task 4.4: +persona_labels_db (loader, 不加 @register, 故 registry count 仍 30;
                                  import 副作用保证 future L2 DI 可达 force_state_from_persona_id)
Phase 0 Task 3: +dream_generator, +reflex_learner, +reflex_learner_store, +memory_sampler (30 → 34)
Phase 0 Task 5: +cascade_engine, +decay_model, +suppression,
                 +collapse_archetype, +collapse_archetype_selector (34 → 39)
v1.1.0C: +activity_history, +adaptation, +project_manager, +recovery_tracker,
         +personality_feedback, +user_activity_detector, +energy_model,
         +environment_context, +emotion_predictor (39 → 48)

Spec deviation (vs plan Step 4.4):
- Plan 期望 30 → 31 (additive), 实际仍 30。persona_labels_db 是数据 loader, 不是
  plugin module — 不应加 @register (Step 1.1 决策), 也不能空挂一个 fake spec。
- registry test 期望保持 39 modules / 34 instantiable (实际值, 不需改)。
- 加 import 的实际价值: 模块在 import emotion_spirit 时被 hot-load, Phase 4 L2 DI
  接入时 force_state_from_persona_id / force_state_from_persona_id_with_conscience
  已经被模块系统知道, 不需要 re-import。
"""
import sys
import warnings
import importlib.abc
import importlib.util

from . import store  # root helper (stays at root, not migrated)
from .core import knowledge, label_mapper, persona_labels_db, plugin_factory
from .memory import (
    memory_pool, intimacy, relationship_personality,
    persona_profiles, social_graph, topic_privacy, meaning_reservoir,
    cascade_engine, decay_model, suppression,
    memory_sampler, reflex_learner,
    activity_history,
)
from .regulation import (
    superego, superego_guard, pattern_extractor, shadow_detector,
    life_simulator, personality_drift, counterfactual, persona_analyzer,
    persona_report_parser, force_dynamics, body_state, dream_generator,
    collapse_archetype,
    adaptation, project_manager, recovery_tracker,
    personality_feedback, user_activity_detector,
    energy_model, environment_context, emotion_predictor,
)
from .output import (
    emotion_classifier, surface_consumer, diary_writer, prompt_injector,
    predictive_sentinel, narrative_identity, bot_decision, trend_utils,
    buffer_signals, realtime_dispatch, rhythm_learner,
    command_router, segmented_reply_coordinator,
)
from .bridge import (
    engine_manager, hotpool_forwarder, personality_bridge,
)
from .agents import (
    self_core, life_agent,
)

# Phase 4 C2: 暴露 PEP 440 合法 version (per code review I3)
from ._version import __version__

# v1.2.2 B3-fix: 顶层门面 re-export (L3 output 对外门面, 提升到顶层不破坏依赖方向)
from .output.public_api import PublicAPI  # noqa: F401


# ═══ Phase 4 C3: v1.x import path redirect ═══
class _DeprecatedImportFinder(importlib.abc.MetaPathFinder):
    """Redirect v1.x import paths to v2.0 paths, with DeprecationWarning.

    C3 阶段 REDIRECTS 空: v1 path 还能 import, hook 静默 no-op。
    C4 实施时填 37 module mapping, 那时 redirect 才生效 (填在下方 _REDIRECTS)。
    """

    _REDIRECTS: dict[str, str] = {
        # C4 实施: 37 module mapping (v1.x → v2.0 path, 触发 DeprecationWarning)
        # L0 core
        "emotion_spirit.registry": "emotion_spirit.core.registry",
        "emotion_spirit.config": "emotion_spirit.core.config",
        "emotion_spirit.knowledge": "emotion_spirit.core.knowledge",
        "emotion_spirit.persona_labels_db": "emotion_spirit.core.persona_labels_db",
        "emotion_spirit.label_mapper": "emotion_spirit.core.label_mapper",
        "emotion_spirit.plugin_factory": "emotion_spirit.core.plugin_factory",
        # L1 memory
        "emotion_spirit.persona_profiles": "emotion_spirit.memory.persona_profiles",
        "emotion_spirit.memory_pool": "emotion_spirit.memory.memory_pool",
        "emotion_spirit.intimacy": "emotion_spirit.memory.intimacy",
        "emotion_spirit.relationship_personality": "emotion_spirit.memory.relationship_personality",
        "emotion_spirit.social_graph": "emotion_spirit.memory.social_graph",
        "emotion_spirit.topic_privacy": "emotion_spirit.memory.topic_privacy",
        "emotion_spirit.meaning_reservoir": "emotion_spirit.memory.meaning_reservoir",
        # L2 regulation
        "emotion_spirit.superego": "emotion_spirit.regulation.superego",
        "emotion_spirit.superego_guard": "emotion_spirit.regulation.superego_guard",
        "emotion_spirit.body_state": "emotion_spirit.regulation.body_state",
        "emotion_spirit.force_dynamics": "emotion_spirit.regulation.force_dynamics",
        "emotion_spirit.personality_drift": "emotion_spirit.regulation.personality_drift",
        "emotion_spirit.shadow_detector": "emotion_spirit.regulation.shadow_detector",
        "emotion_spirit.pattern_extractor": "emotion_spirit.regulation.pattern_extractor",
        "emotion_spirit.life_simulator": "emotion_spirit.regulation.life_simulator",
        "emotion_spirit.persona_analyzer": "emotion_spirit.regulation.persona_analyzer",
        "emotion_spirit.persona_report_parser": "emotion_spirit.regulation.persona_report_parser",
        "emotion_spirit.counterfactual": "emotion_spirit.regulation.counterfactual",
        # L3 output
        "emotion_spirit.bot_decision": "emotion_spirit.output.bot_decision",
        "emotion_spirit.emotion_classifier": "emotion_spirit.output.emotion_classifier",
        "emotion_spirit.prompt_injector": "emotion_spirit.output.prompt_injector",
        "emotion_spirit.surface_consumer": "emotion_spirit.output.surface_consumer",
        "emotion_spirit.surface_handler": "emotion_spirit.output.surface_handler",
        "emotion_spirit.diary_writer": "emotion_spirit.output.diary_writer",
        "emotion_spirit.command_router": "emotion_spirit.output.command_router",
        "emotion_spirit.commands": "emotion_spirit.output.commands",
        "emotion_spirit.narrative_identity": "emotion_spirit.output.narrative_identity",
        "emotion_spirit.predictive_sentinel": "emotion_spirit.output.predictive_sentinel",
        "emotion_spirit.public_api": "emotion_spirit.output.public_api",
        "emotion_spirit.buffer_signals": "emotion_spirit.output.buffer_signals",
        "emotion_spirit.trend_utils": "emotion_spirit.output.trend_utils",
    }

    def find_spec(self, name, path, target=None):
        new_name = self._REDIRECTS.get(name)
        if new_name is None:
            return None
        warnings.warn(
            f"importing from '{name}' is deprecated, use '{new_name}' instead",
            DeprecationWarning,
            stacklevel=3,
        )
        return importlib.util.find_spec(new_name)


sys.meta_path.insert(0, _DeprecatedImportFinder())
