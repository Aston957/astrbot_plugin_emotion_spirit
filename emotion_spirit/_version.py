# emotion_spirit/_version.py
# Single source of truth for the package version (PEP 440 compliant).
# pyproject.toml reads this via `dynamic = ["version"]` + `attr: ...`.
#
# Versioning policy: standard SemVer (MAJOR.MINOR.PATCH). This is the
# canonical "2.0.0" release, superseding the experimental v2.0.0v1/v2
# pre-releases from Phase 4 Launch. `metadata.yaml` and git tags use
# the same string; tests/test_packaging.py checks base version consistency.
__version__ = "2.0.0"
