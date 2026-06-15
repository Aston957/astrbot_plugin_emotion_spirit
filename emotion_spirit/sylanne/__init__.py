"""Sylanne-Core: Affective computation engine SDK.

Text in, structured emotional state out. Designed as an AstrBot plugin dependency.

Quick start (standalone)::

    from emotion_spirit.sylanne import SylanneEngine, SylanneConfig

    engine = SylanneEngine(data_dir="./data", llm=my_llm_fn)
    await engine.start()
    surface = await engine.process("user_123", "你好")
    print(surface["decision"]["action"])  # "express", "listen", "hold", etc.
    await engine.shutdown()

Quick start (embedded)::

    from emotion_spirit.sylanne import get_engine
    engine = get_engine()  # pre-configured by plugin main.py
    surface = await engine.process(session_id, text)
"""

from __future__ import annotations

from .algebra import blend, compose, decay, distance, drift, normalize, project, threshold
from .bridge import layer0_to_interchange, state_to_pad, surface_to_layer0
from .compute.hot_pool import HotPool, Influence, InfluenceType
from .compute.pad_interop import PADProjector, PADVector
from .config import DimensionProfile, SylanneConfig, build_profile
from .contagion import ContagionEvent, ContagionGraph, GroupDynamics, InfluenceFilter
from .engine import SharedEngineConflictError, SylanneEngine
from .expression import (
    BlendShapeProfile,
    MotorCommand,
    PADToBlendShape,
    PADToMotor,
    PADToProsody,
    PADToTextStyle,
    ProsodyParams,
    TextStyle,
)
from .schema import SYLANNE_SCHEMA
from .schema import validate as validate_schema
from .standard import EmotionVector, SylanneCore, SylanneState, SylanneStimulus
from .types import EngineStatus, HealthStatus, PADOutput, Surface

__all__ = [
    # Engine & config
    "SylanneEngine",
    "SylanneConfig",
    "SylanneCore",
    "SylanneStimulus",
    "SylanneState",
    "EmotionVector",
    "DimensionProfile",
    "build_profile",
    # Hot pool
    "HotPool",
    "Influence",
    "InfluenceType",
    # PAD interop
    "PADVector",
    "PADProjector",
    "PADOutput",
    # Schema
    "SYLANNE_SCHEMA",
    "validate_schema",
    # Types
    "Surface",
    "EngineStatus",
    "HealthStatus",
    # Bridge
    "state_to_pad",
    "surface_to_layer0",
    "layer0_to_interchange",
    # Algebra
    "blend",
    "decay",
    "project",
    "threshold",
    "normalize",
    "distance",
    "drift",
    "compose",
    # Contagion
    "ContagionGraph",
    "ContagionEvent",
    "GroupDynamics",
    "InfluenceFilter",
    # Expression
    "PADToBlendShape",
    "PADToMotor",
    "PADToTextStyle",
    "PADToProsody",
    "BlendShapeProfile",
    "MotorCommand",
    "TextStyle",
    "ProsodyParams",
    # Shared engine
    "SharedEngineConflictError",
    "get_engine",
]
__version__ = "3.0.1"


def get_engine() -> SylanneEngine:
    """获取共享引擎实例（兼容旧 API）。

    推荐使用 SylanneEngine.shared() 直接获取。
    """
    instances = SylanneEngine.list_shared()
    if not instances:
        raise RuntimeError(
            "SylannEngine 尚未初始化。请使用 SylanneEngine.shared(data_dir, llm) 创建。"
        )
    # 返回第一个共享实例
    first = instances[0]
    key = first["data_dir"]
    engine = SylanneEngine._shared_instances.get(key)
    if engine is None:
        raise RuntimeError("SylannEngine 共享实例已释放。")
    return engine
