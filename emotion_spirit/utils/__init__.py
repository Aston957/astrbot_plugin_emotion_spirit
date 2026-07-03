"""emotion_spirit utils — 无状态纯函数工具, 跨层共享。

不 @register(import 即可)。统一 export 供全仓消费。

v1.2.7: 11 工具从原所在层集中到 utils/(emotion_classifier / label_mapper / persona_profiles /
trend_utils / decay_model / knowledge / persona_report_parser / adaptation /
emotion_predictor / energy_model / user_activity_detector)
"""

from __future__ import annotations

from .adaptation import (
    COLLAPSE_SOCIAL_MOD,
    EMOTION_ACTIVITY_BIAS,
    compute_social_tendency,
    derive_activity_preferences,
    select_adaptation_activity,
)
from .decay_model import DecayModel
from .emotion_classifier import (
    build_emotion_payload,
    classify_distribution,
    classify_primary_secondary,
    compute_ambiguity,
    compute_velocity,
    render_description,
)
from .emotion_predictor import EmotionPredictor
from .energy_model import EnergyModel, apply_energy_bias, get_energy_level
from .knowledge import KnowledgeBase
from .persona_profiles import (
    DIMENSION_DISPLAY,
    get_intimacy_modulation,
    get_intimacy_weights,
    get_labels_from_config,
    get_narrative,
    get_personality_from_labels,
    get_personality_params,
    get_value_behaviors,
)
from .persona_report_parser import (
    ParsedPersona,
    PersonaReportParser,
    get_drives_from_report,
    get_labels_from_report,
    parse_persona_report,
)
from .trend_utils import EMASmoother, TrendDetector
from .user_activity_detector import UserActivityDetector
from .tone_extractor import extract_bot_emotion
from .context_builder import build_context

# re-export label_mapper items (used by consumers outside utils)
from .label_mapper import (  # noqa: F401
    ALL_PERSONALITY_DIMS,
    LABEL_OPTIONS,
    PERSONALITY_DIMS_DEEP,
    PERSONALITY_DIMS_SURFACE,
    _BASELINE,
    clamp,
    get_label_options,
    labels_to_personality,
    personality_to_labels,
)

__all__ = [
    # adaptation
    "COLLAPSE_SOCIAL_MOD",
    "EMOTION_ACTIVITY_BIAS",
    "compute_social_tendency",
    "derive_activity_preferences",
    "select_adaptation_activity",
    # decay_model
    "DecayModel",
    # emotion_classifier
    "build_emotion_payload",
    "classify_distribution",
    "classify_primary_secondary",
    "compute_ambiguity",
    "compute_velocity",
    "render_description",
    # emotion_predictor
    "EmotionPredictor",
    # energy_model
    "EnergyModel",
    "apply_energy_bias",
    "get_energy_level",
    # knowledge
    "KnowledgeBase",
    # label_mapper
    "ALL_PERSONALITY_DIMS",
    "LABEL_OPTIONS",
    "PERSONALITY_DIMS_DEEP",
    "PERSONALITY_DIMS_SURFACE",
    "_BASELINE",
    "clamp",
    "get_label_options",
    "labels_to_personality",
    "personality_to_labels",
    # persona_profiles
    "DIMENSION_DISPLAY",
    "get_intimacy_modulation",
    "get_intimacy_weights",
    "get_labels_from_config",
    "get_narrative",
    "get_personality_from_labels",
    "get_personality_params",
    "get_value_behaviors",
    # persona_report_parser
    "ParsedPersona",
    "PersonaReportParser",
    "get_drives_from_report",
    "get_labels_from_report",
    "parse_persona_report",
    # trend_utils
    "EMASmoother",
    "TrendDetector",
    # user_activity_detector
    "UserActivityDetector",
    "extract_bot_emotion",
    "build_context",
]