"""Static scan: 在 emotion_spirit/ 和 tests/ 里找可能的 dim 名称错位 (P0-1e)。

v1.7.2 13 维权威集合 (来自 label_mapper.ALL_PERSONALITY_DIMS):
    深层 5: expression_drive / perception_acuity / boundary_permeability /
            inner_coherence / relational_gravity
    表层 8: warmth_bias / directness / curiosity / patience /
            intimacy_pull / relational_autonomy / exploration_openness /
            gossip_tendency

Deprecated dims (历史遗留, 必须替换):
    warmth → warmth_bias
    autonomy / autonomy_guard → relational_autonomy + exploration_openness (v1.7 拆分)
    narrative_coherence / conscience_pressure / shadow_suppression /
    value_resistance / drift_pull → 不是 personality dim, 应在别处

用法:
    python tools/check_dim_consistency.py

退出码:
    0 — 无 deprecated dim 引用
    1 — 发现 deprecated dim 引用 (打印前 20 条)
"""
import re
import sys
from pathlib import Path

# v1.7.2 权威 13 维 — 跟 emotion_spirit/label_mapper.py 同步
AUTHORITY_DIMS = {
    "expression_drive", "perception_acuity", "boundary_permeability",
    "inner_coherence", "relational_gravity",
    "warmth_bias", "directness", "curiosity", "patience",
    "intimacy_pull", "relational_autonomy", "exploration_openness",
    "gossip_tendency",
}

# v1.7 前错名 / 已删除维度 — 若发现引用即报警
DEPRECATED_DIMS = {
    "warmth",  # 应是 warmth_bias
    "autonomy",  # autonomy_guard 已删, 拆为 RA + EO
    "autonomy_guard",  # v1.7 删除
    "conscience_pressure",  # 不是 personality dim
    "shadow_suppression",  # 不是 personality dim
    "narrative_coherence",  # 不是 personality dim
    "value_resistance",  # 不是 personality dim
    "drift_pull",  # 不是 personality dim
}

# 形如 "dim_name": 0.5 的字段引用 — 主要发力点
DIM_LIKE_PATTERN = re.compile(r'["\']([a-z_]+)["\']\s*:\s*[-+]?[0-9.]+')

# 跳过的文件名 — 这些文件测试 SylannEngine Surface schema (connection.warmth /
# boundary.autonomy 等)，是 namespace 内的合法字段名，不是 personality dim 错位。
IGNORE_FILENAMES = {
    "test_surface_consumer.py",  # Surface schema 测试数据
}


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    """扫一个文件, 返回 (line_no, dim_name, context_snippet) 警告列表。"""
    warnings = []
    try:
        text = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return warnings

    for line_no, line in enumerate(text.splitlines(), 1):
        # 跳过注释和 docstring 行 (粗略, 不解析 AST)
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        for match in DIM_LIKE_PATTERN.finditer(line):
            dim = match.group(1)
            if dim in DEPRECATED_DIMS:
                warnings.append((line_no, dim, line.strip()[:80]))
    return warnings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "emotion_spirit",
        root / "tests",
        root / "main.py",
    ]

    all_warnings: list[tuple[Path, int, str, str]] = []
    for target in targets:
        if not target.exists():
            continue
        if target.is_file():
            files = [target]
        else:
            files = list(target.rglob("*.py"))
        for f in files:
            if "__pycache__" in f.parts:
                continue
            if f.name in IGNORE_FILENAMES:
                continue
            warnings = scan_file(f)
            for line_no, dim, ctx in warnings:
                all_warnings.append((f.relative_to(root), line_no, dim, ctx))

    if all_warnings:
        print(f"[WARN] Found {len(all_warnings)} deprecated dim references:")
        for path, line_no, dim, ctx in all_warnings[:20]:
            print(f"  {path}:{line_no}  dim='{dim}'  | {ctx}")
        if len(all_warnings) > 20:
            print(f"  ... and {len(all_warnings) - 20} more")
        return 1
    print(f"[OK] No deprecated dim references found (scanned {len(targets)} targets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
