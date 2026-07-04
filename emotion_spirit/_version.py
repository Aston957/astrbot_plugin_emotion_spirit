# emotion_spirit/_version.py
# Single source of truth for the package version (PEP 440 compliant).
# pyproject.toml reads this via `dynamic = ["version"]` + `attr: ...`.
#
# Versioning policy: standard SemVer (MAJOR.MINOR.PATCH).
# `metadata.yaml` and git tags use the same string.
__version__ = "1.2.10"
