"""UnifiedEntry -- self-contained memory entity.

Each memory is a self-contained individual that manages its own
temperature, emotional weight, and reconsolidation state.

The pool (UnifiedMemory) manages collective state; the entry
manages "what happens to me."

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md section 3.1.1
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..core.utils import clamp as _clamp

__all__ = ["UnifiedEntry"]


@dataclass
class UnifiedEntry:
    """Unified memory entry -- self-contained event entity.

    Identity fields (immutable): id, text, tags, entities, source_user, privacy, created_at
    Self-state (mutable, managed by self): temperature, emotional_weight, mass, tier, etc.
    """

    # -- Identity (immutable) --
    id: str
    text: str
    tags: list[str]
    entities: dict           # {"person": ["bob"], "place": [...]}
    source_user: str
    privacy: str             # "private" / "circle" / "public"
    created_at: float

    # -- Self-state (mutable) --
    temperature: float       # Current temperature [0, 1]
    emotional_weight: float  # Emotional weight [0, 1]
    mass: float              # Emotional mass (affects cooling speed) [0, 1]
    tier: str                # "buffer" / "warm" / "cold" / "ghost"
    is_ghost: bool
    recall_count: int
    last_recalled: float
    peak_temperature: float

    # -- Social associations --
    participants: set[str] = field(default_factory=set)  # 记忆归属者 (说话人+群组)
    mentioned: set[str] = field(default_factory=set)     # 被提及的人

    # -- Memory compression --
    impression: str | None = field(default=None)  # 压缩印象 (warm→cold 时生成)
    compression: float = field(default=0.0)       # 压缩程度 [0, 1]

    # -- Reconsolidation state --
    _is_labile: bool = field(default=False)
    _lability_deadline: float = field(default=0.0)

    # -- Vector space (PAD 三维) --
    vector: tuple[float, float, float] = field(default=(0.0, 0.0, 0.0))

    # -- Cascade tracking --
    cascade_generation: int = field(default=0)

    # -- Bug-F memory_type classification (v1.3.0 rc.3) --
    # bot_reply / bot_ephemeral_state / bot_long_term_fact / user_fact
    memory_type: str = field(default="bot_reply")

    # -- Ghost tracking --
    ghost_sensitivity_shift: float = field(default=0.0)  # Counterfactual ghost sensitivity
    _ticks_above_ghost_threshold: int = field(default=0)

    def on_recall(self, personality: dict[str, float]) -> None:
        """Recall event: raise temperature + open reconsolidation window.

        Nader et al. (2000): recall makes memory labile.
        Schiller et al. (2010): window ~6h, personality-dependent.
        """
        self.temperature = _clamp(self.temperature + 0.3, 0, 1)
        self.emotional_weight = _clamp(self.emotional_weight + 0.1, 0, 1)
        self.last_recalled = time.time()
        self.recall_count += 1

        # Open reconsolidation window (personality-dependent duration)
        self._is_labile = True
        window_hours = 6 * (
            (1 + 0.5 * personality.get("neuroticism", 0.5))
            * (1 - 0.3 * personality.get("openness", 0.5))
            * (1 + 0.3 * personality.get("conscientiousness", 0.5))
            * (1 - 0.3 * personality.get("extraversion", 0.5))
        )
        self._lability_deadline = time.time() + _clamp(window_hours, 2, 16) * 3600

    def on_reconsolidation_update(self, signal_type: str, intensity: float) -> None:
        """During lability window, external signals can modify emotional content.

        Positive signals (validation) -> weight decreases (trauma repair)
        Negative signals (betrayal) -> weight increases (wound deepens)
        """
        if not self._is_labile or time.time() > self._lability_deadline:
            self._is_labile = False
            return

        valence_shifts = {
            "validation": -0.2,
            "reinforcement": 0.1,
            "contradiction": 0.2,
            "betrayal": 0.4,
            "revelation": 0.3,
        }
        shift = valence_shifts.get(signal_type, 0) * intensity
        self.emotional_weight = _clamp(self.emotional_weight + shift, 0, 1)
        self._is_labile = False  # Reconsolidated

        # Reconsolidation changes emotional weight → update vector (dominance)
        self.recompute_vector()

    def on_inject(self, signal_type: str, intensity: float) -> None:
        """External signal: adjust temperature based on signal type."""
        effects = {
            "contradiction": 0.5,
            "reinforcement": 0.3,
            "revelation": 0.8,
            "betrayal": 1.0,
            "validation": -0.4,
        }
        delta = effects.get(signal_type, 0) * intensity
        self.temperature = _clamp(self.temperature + delta, 0, 1)
        self.peak_temperature = max(self.peak_temperature, self.temperature)

    # Privacy → numeric normalization (class-level, not a dataclass field)
    _PRIVACY_NORM: ClassVar[dict[str, float]] = {"private": 0.0, "circle": 0.5, "public": 1.0}

    @staticmethod
    def compute_vector(
        valence: float,
        arousal: float,
        emotional_weight: float,
        mass: float = 0.0,
        privacy: str = "private",
    ) -> tuple[float, float, float]:
        """Compute PAD vector from existing fields.

        Dominance = emotional_weight (direct measure of control/salience).
        mass and privacy kept for API compatibility but not used in dominance.

        Args:
            valence: Upstream pad_valence [-1, 1], mapped to [0, 1].
            arousal: Entry arousal [0, 1].
            emotional_weight: Emotional weight [0, 1].

        Returns:
            (valence, arousal, dominance) in [0, 1]^3.
        """
        v = _clamp((valence + 1.0) / 2.0, 0.0, 1.0)
        a = _clamp(arousal, 0.0, 1.0)
        d = _clamp(emotional_weight, 0.0, 1.0)
        return (v, a, d)

    def recompute_vector(self) -> None:
        """Recompute dominance from current emotional_weight.

        Called after reconsolidation and decay when weight changes.
        Valence and arousal are preserved (not re-derived).
        """
        v, a, _ = self.vector
        self.vector = (v, a, _clamp(self.emotional_weight, 0.0, 1.0))

    def compute_decay_factor(
        self,
        partner_intimacy: float = 0.0,
        personality: dict[str, float] | None = None,
    ) -> float:
        """情境衰减因子 — 人格 + 关系 + 情感权重联合调制衰减速度。

        文献支撑:
        - neuroticism=0.30 (Gross & John 2003): 放大负面, 加速正面遗忘
        - openness=0.15 (Schiller et al. 2010): 更容易释怀
        - conscientiousness=0.10: 记忆更系统化
        - extraversion=0.10: 正面记忆社交强化
        - agreeableness=0.10: 更容易原谅
        - partner_intimacy (Mikulincer & Shaver 2007): 亲密关系减缓遗忘

        Returns:
            factor ∈ [0.3, 2.0]: <1 减缓衰减, >1 加速衰减
        """
        if personality is None:
            personality = {}

        # 情感权重: 高情感 → 慢衰减
        factor_emotion = 1.0 - 0.5 * self.emotional_weight

        # 神经质-效价交互: valence 从 vector[0] 获取
        valence = self.vector[0]  # [0,1], 0.5=neutral
        neuroticism = personality.get("neuroticism", 0.5)
        openness = personality.get("openness", 0.5)
        # 负面记忆(valence<0.5): neuroticism 减缓衰减
        # 正面记忆(valence>0.5): neuroticism 加速衰减
        valence_neuro = 1.0 + 0.3 * neuroticism * (0.5 - valence) * 2
        valence_open = 1.0 - 0.15 * openness * abs(valence - 0.5) * 2
        factor_valence = valence_neuro * valence_open

        # 亲密关系: 减缓衰减
        factor_partner = 1.0 - 0.3 * partner_intimacy

        # 人格因子
        c = personality.get("conscientiousness", 0.5)
        e = personality.get("extraversion", 0.5)
        a = personality.get("agreeableness", 0.5)
        factor_personality = 1.0 - 0.1 * (c + e + a - 1.5)  # 中性=1.0

        factor = factor_emotion * factor_valence * factor_partner * factor_personality
        return _clamp(factor, 0.3, 2.0)

    # -- Memory compression --

    @staticmethod
    def generate_impression(entry: "UnifiedEntry") -> str:
        """Generate a compressed impression from tags + entities + valence.

        Used when warm → cold transition: important details preserved as impression.
        Ghost entries never get compressed.
        """
        emotion = entry.tags[0] if entry.tags else "某件事"
        people = ", ".join(entry.entities.get("person", []))
        valence_word = "正面" if entry.vector[0] > 0.5 else "负面"

        if people:
            return f"关于{people}的{emotion}，感觉{valence_word}"
        return f"{emotion}，感觉{valence_word}"

    def compress_to_impression(self) -> None:
        """Compress this entry: generate impression, set compression=1.0.

        Called during warm → cold transition. Ghost entries are never compressed.
        """
        if self.is_ghost:
            return
        self.impression = self.generate_impression(self)
        self.compression = 1.0

    def get_display_text(self) -> str:
        """Return the appropriate text based on compression level.

        - compression < 0.5: full text
        - compression >= 0.5: impression (if available)
        - ghost: always full text
        """
        if self.is_ghost or self.compression < 0.5:
            return self.text
        return self.impression if self.impression else self.text

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "entities": self.entities,
            "source_user": self.source_user,
            "privacy": self.privacy,
            "created_at": self.created_at,
            "temperature": round(self.temperature, 6),
            "emotional_weight": round(self.emotional_weight, 6),
            "mass": round(self.mass, 6),
            "tier": self.tier,
            "is_ghost": self.is_ghost,
            "recall_count": self.recall_count,
            "last_recalled": self.last_recalled,
            "peak_temperature": round(self.peak_temperature, 6),
            "vector": [round(v, 6) for v in self.vector],
            "cascade_generation": self.cascade_generation,
            "ghost_sensitivity_shift": round(self.ghost_sensitivity_shift, 6),
            "participants": list(self.participants),
            "mentioned": list(self.mentioned),
            "impression": self.impression,
            "compression": round(self.compression, 6),
            "memory_type": self.memory_type,  # v1.3.0 rc.3 Bug-F
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnifiedEntry:
        """Deserialize from dict."""
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        # JSON stores vector as list; convert to tuple
        if "vector" in filtered and isinstance(filtered["vector"], list):
            filtered["vector"] = tuple(filtered["vector"])
        # JSON stores sets as lists; convert back
        if "participants" in filtered and isinstance(filtered["participants"], list):
            filtered["participants"] = set(filtered["participants"])
        if "mentioned" in filtered and isinstance(filtered["mentioned"], list):
            filtered["mentioned"] = set(filtered["mentioned"])
        return cls(**filtered)
