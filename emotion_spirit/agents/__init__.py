"""Multi-agent cognitive architecture for emotion_spirit."""

from .memory_agent import MemoryAgent
from .personality_agent import PersonalityAgent
from .relationship_agent import RelationshipAgent
from .life_agent import LifeAgent

__all__ = ["MemoryAgent", "PersonalityAgent", "RelationshipAgent", "LifeAgent"]
