# emotion_spirit/_version.py
# Single source of truth for the package version (PEP 440 compliant).
# pyproject.toml reads this via `dynamic = ["version"]` + `attr: ...`.
#
# 注: 内部 release label 是 "2.0.0v1" (Phase 4 Launch), 但 PEP 440 不接受 "v"
# 后缀 (pip 会拒绝 install)。这里用 `2.0.0.post1` 等价表达 — 它就是
# "2.0.0 的第 1 个 post-release", 对应我们的 "v2.0.0v1"。
# `metadata.yaml` 和 git tag 仍使用 `2.0.0v1` 字符串 (用户/文档可见的
# label), 验证时由 tests/test_packaging.py 检查 base version 一致性。
__version__ = "2.0.0.post1"
