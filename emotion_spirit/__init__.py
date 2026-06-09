"""emotion_spirit — Sylanne Engine 之上的长期记忆、人格演化与超我调控。

显式 import 所有 @register 装饰模块 (Phase B P3-7 衔接)。
import emotion_spirit 触发 30 模块装饰器注册, 确保 registry.build(config) 拿到 30 个 ModuleSpec。
B6 plugin_factory.py 依赖此副作用。

Phase 3.0B Task 3: +body_state (29 → 30)
Phase 3.0C Task 4.4: +persona_labels_db (loader, 不加 @register, 故 registry count 仍 30;
                                  import 副作用保证 future L2 DI 可达 force_state_from_persona_id)

Spec deviation (vs plan Step 4.4):
- Plan 期望 30 → 31 (additive), 实际仍 30。persona_labels_db 是数据 loader, 不是
  plugin module — 不应加 @register (Step 1.1 决策), 也不能空挂一个 fake spec。
- registry test 期望保持 30 modules / 26 instantiable (实际值, 不需改)。
- 加 import 的实际价值: 模块在 import emotion_spirit 时被 hot-load, Phase 4 L2 DI
  接入时 force_state_from_persona_id / force_state_from_persona_id_with_conscience
  已经被模块系统知道, 不需要 re-import。
"""
import sys
import warnings
import importlib
import importlib.abc
import importlib.util

from . import (
    store, knowledge, label_mapper, emotion_classifier, surface_consumer,
    memory_pool, buffer_signals, intimacy, relationship_personality, superego,
    superego_guard, meaning_reservoir, pattern_extractor, shadow_detector,
    life_simulator, diary_writer, prompt_injector, personality_drift,
    predictive_sentinel, narrative_identity, counterfactual, persona_analyzer,
    persona_profiles, persona_report_parser, social_graph, topic_privacy,
    bot_decision, trend_utils, force_dynamics, body_state,
    persona_labels_db,  # Phase 3.0C Task 4.4: loader 模块, 不 @register
)

# Phase 4 C2: 暴露 PEP 440 合法 version (per code review I3)
from ._version import __version__


# ═══ Phase 4 C3: v1.x import path redirect ═══
class _DeprecatedImportFinder(importlib.abc.MetaPathFinder):
    """Redirect v1.x import paths to v2.0 paths, with DeprecationWarning.

    C3 阶段 REDIRECTS 空: v1 path 还能 import, hook 静默 no-op。
    C4 实施时填 38 mapping, 那时 redirect 才生效。
    """

    _REDIRECTS: dict[str, str] = {
        # C3 阶段空, C4 才填
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
