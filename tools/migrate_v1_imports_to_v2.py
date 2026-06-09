# tools/migrate_v1_imports_to_v2.py
"""v1.x → v2.0 import path 迁移 (Phase 4 C4)。一次性脚本, 留在 tools/。

覆盖 3 类 mapping (per plan 调整 C1 + module-internal relative import 修复):
- from emotion_spirit.X import Y → from emotion_spirit.{L0|L1|L2|L3}.X import Y
- import emotion_spirit.X → import emotion_spirit.{L0|L1|L2|L3}.X
- from .X import Y (module-internal 相对导入):
    - 若 X 在同 sub-package → from .X (保持)
    - 若 X 在不同 sub-package → from ..{layer}.X
    - 若调用方在根层 (emotion_spirit/*.py) 且 X 已迁出 → from .{layer}.X

跑法: python tools/migrate_v1_imports_to_v2.py
"""
import re
from pathlib import Path

# 37 个 v1 → v2 路径 mapping (per spec §3.3)
V1_TO_V2 = {
    # L0
    "registry": "core",
    "config": "core",
    "knowledge": "core",
    "persona_labels_db": "core",
    "label_mapper": "core",
    "plugin_factory": "core",
    # L1
    "persona_profiles": "memory",
    "memory_pool": "memory",
    "intimacy": "memory",
    "relationship_personality": "memory",
    "social_graph": "memory",
    "topic_privacy": "memory",
    "meaning_reservoir": "memory",
    # L2
    "superego": "regulation",
    "superego_guard": "regulation",
    "body_state": "regulation",
    "force_dynamics": "regulation",
    "personality_drift": "regulation",
    "shadow_detector": "regulation",
    "pattern_extractor": "regulation",
    "life_simulator": "regulation",
    "persona_analyzer": "regulation",
    "persona_report_parser": "regulation",
    "counterfactual": "regulation",
    # L3
    "bot_decision": "output",
    "emotion_classifier": "output",
    "prompt_injector": "output",
    "surface_consumer": "output",
    "surface_handler": "output",
    "diary_writer": "output",
    "command_router": "output",
    "commands": "output",
    "narrative_identity": "output",
    "predictive_sentinel": "output",
    "public_api": "output",
    "buffer_signals": "output",
    "trend_utils": "output",
}


def get_file_layer(path: Path) -> str | None:
    """根据路径返回文件所在 layer: 'core'/'memory'/'regulation'/'output' 或 None (根层)。"""
    parts = path.parts
    if "emotion_spirit" not in parts:
        return None
    idx = parts.index("emotion_spirit")
    if idx + 1 < len(parts) and parts[idx + 1] in {"core", "memory", "regulation", "output"}:
        return parts[idx + 1]
    return None  # 根层 (emotion_spirit/*.py)


def migrate_text(text: str, file_layer: str | None) -> str:
    """对单文件 text 应用所有 migration mapping。"""
    new_text = text

    # 1) from emotion_spirit.X 形式: 全 codebase 都用
    for v1_module, layer in V1_TO_V2.items():
        old = f"from emotion_spirit.{v1_module}"
        new = f"from emotion_spirit.{layer}.{v1_module}"
        new_text = new_text.replace(old, new)

    # 2) import emotion_spirit.X 形式
    for v1_module, layer in V1_TO_V2.items():
        old = f"import emotion_spirit.{v1_module}"
        new = f"import emotion_spirit.{layer}.{v1_module}"
        new_text = new_text.replace(old, new)

    # 3) from .X 形式 (module-internal relative import, 只在 emotion_spirit/ 内部)
    #    按 file_layer 决定目标层前缀:
    #    - file 在根 (file_layer=None): from .layer.X (上一层是 emotion_spirit)
    #    - file 在 sub-package: 同层用 from .X, 跨层用 from ..other_layer.X
    for v1_module, layer in V1_TO_V2.items():
        old = f"from .{v1_module}"
        if file_layer is None:
            # 根层文件: "from .X" → "from .{layer}.X" (上一层是 emotion_spirit)
            new = f"from .{layer}.{v1_module}"
        elif file_layer == layer:
            # 同 sub-package: 保持 from .X
            new = f"from .{v1_module}"
        else:
            # 跨 sub-package: from ..{layer}.X
            new = f"from ..{layer}.{v1_module}"
        new_text = new_text.replace(old, new)

    # 4) String literal 形式: "emotion_spirit.X.Y" → "emotion_spirit.{layer}.X.Y"
    #    (e.g. monkeypatch.setattr("emotion_spirit.persona_labels_db.DB_PATH", ...))
    for v1_module, layer in V1_TO_V2.items():
        old = f'"emotion_spirit.{v1_module}'
        new = f'"emotion_spirit.{layer}.{v1_module}'
        new_text = new_text.replace(old, new)

    return new_text


def migrate_file(path: Path) -> int:
    """返回替换行数 (粗略统计)。"""
    text = path.read_text(encoding="utf-8")
    file_layer = get_file_layer(path)
    new_text = migrate_text(text, file_layer)
    if new_text == text:
        return 0
    # 简单 count: 跟 text 行数 diff
    old_lines = text.count("\n")
    new_lines = new_text.count("\n")
    path.write_text(new_text, encoding="utf-8")
    return abs(new_lines - old_lines) + (1 if new_text != text else 0)


def main() -> None:
    root = Path(".")
    total = 0
    file_count = 0
    for py_file in root.rglob("*.py"):
        if "/__pycache__/" in str(py_file) or "/.git/" in str(py_file):
            continue
        if "/build/" in str(py_file) or "/dist/" in str(py_file):
            continue
        if "tmp_" in py_file.name:  # 跳过 tmp 脚本
            continue
        if py_file.name == "migrate_v1_imports_to_v2.py":  # 跳过自己
            continue
        n = migrate_file(py_file)
        if n:
            print(f"{py_file}: {n} lines changed")
            total += n
            file_count += 1
    print(f"\nTotal: {total} lines changed across {file_count} files")


if __name__ == "__main__":
    main()
