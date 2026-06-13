# emotion_spirit/_version.py
# Single source of truth for the package version (PEP 440 compliant).
# pyproject.toml reads this via `dynamic = ["version"]` + `attr: ...`.
#
# Versioning policy: standard SemVer (MAJOR.MINOR.PATCH).
# v3.0.0: SylannEngine 内嵌 + 统一记忆 + LLM LifeSimulator + on_llm_response
# v3.0.1: AstrBot v4.25.5 compatibility (10 patches: loading, handler, persona)
# `metadata.yaml` and git tags use the same string.
__version__ = "3.0.1"
