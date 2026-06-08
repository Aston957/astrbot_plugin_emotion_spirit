"""emotion_spirit — 3072 组合 persona-labels KB loader (Phase 3.0C.1)。

数据层 loader: 加载 D:\\新建文件夹\\emotion_spirit\\emotion_spirit\\knowledge-base\\
mega-paper-kb\\persona-labels\\persona_labels_db.json, in-memory 缓存, 提供
baseline 查询 + 渐进式注册 API。

注意: 本模块**不加 @register** (loader 是数据查询, 不是 plugin module)。
3.0C.1 范围: loader 骨架 + 4 组合 stub + register/export API。Task 2 加
force_state_from_persona_id() 主入口。

路径覆盖: 支持 EMOTION_SPIRIT_PERSONA_KB_PATH 环境变量, 缺省 = 默认路径
(测试可临时指向 tmp_path)。

API 列表:
- get_persona_labels_db() — 全量加载 + 缓存
- get_baseline_for_persona(persona_id) — 单 baseline dict
- get_persona_entry(persona_id) — 完整 entry (含 confidence + refs)
- register_persona_baseline(...) — in-memory 单 entry 注册
- bulk_register_persona_baselines(entries) — 批量
- export_persona_labels_db(path) — in-memory → JSON
- list_persona_ids() — 排序列表
- get_kb_stats() — 命中率统计
- reset_cache() — 测试用: 重置缓存 + stats
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 13 dim baseline 必备 key 集合 (与 3.0A KnowledgeBase.ALL_PERSONALITY_DIMS 一致)
REQUIRED_DIMS: frozenset[str] = frozenset({
    "warmth_bias", "boundary_permeability", "relational_gravity",
    "expression_drive", "gossip_tendency", "directness",
    "inner_coherence", "patience", "intimacy_pull",
    "curiosity", "perception_acuity", "relational_autonomy", "exploration_openness",
})

# 默认路径: __file__ 4 级 up → D:\\新建文件夹\\emotion_spirit\\, 然后 emotion_spirit\\knowledge-base\\...
_DEFAULT_DB_PATH = (
    Path(__file__).parent.parent.parent.parent  # 4 级 up 到 emotion_spirit 根
    / "emotion_spirit"
    / "knowledge-base"
    / "mega-paper-kb"
    / "persona-labels"
    / "persona_labels_db.json"
)
DB_PATH: Path = Path(os.environ.get("EMOTION_SPIRIT_PERSONA_KB_PATH", str(_DEFAULT_DB_PATH)))

# In-memory cache (None = 未加载)
_DB: dict[str, dict] | None = None

# 命中率计数器 (spec §9.1)
_STATS: dict[str, int] = {
    "kb_hit": 0,
    "kb_fallback_labels": 0,
    "kb_fallback_neutral": 0,
    "register_count": 0,
}


def get_persona_labels_db() -> dict[str, dict]:
    """全量加载 + 缓存 KB. 第一次调用读 JSON, 之后返 in-memory dict.

    Returns:
        dict[persona_id, entry]: entry 格式见 spec §3.4 (含 baseline/confidence/refs/notes)
        JSON 不存在 → 返空 dict, log warning (不抛错, 跟 3.0A loader 一致)。
    """
    global _DB
    if _DB is None:
        if not DB_PATH.exists():
            logger.warning(
                f"persona_labels_db.json not found at {DB_PATH}, returning empty KB"
            )
            _DB = {}
        else:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                _DB = json.load(f)
            logger.info(
                f"persona_labels_db loaded: {len(_DB)} entries from {DB_PATH}"
            )
    return _DB


def get_baseline_for_persona(persona_id: str) -> dict[str, float] | None:
    """返 baseline dict 或 None (未找到). 不抛错, 跟 3.0A `compute_baseline_from_labels` 行为一致.

    Args:
        persona_id: 5 段命名 (e.g. "INFP-SE-EX-CO-PR")

    Returns:
        baseline dict (13 dim → float) 或 None
    """
    db = get_persona_labels_db()
    entry = db.get(persona_id)
    if entry is None:
        return None
    return entry.get("baseline")


def get_persona_entry(persona_id: str) -> dict | None:
    """返完整 entry (含 confidence + refs), 不是 baseline dict.

    区别于 get_baseline_for_persona: 本函数返整个 entry (含 metadata)。
    """
    return get_persona_labels_db().get(persona_id)


def register_persona_baseline(
    persona_id: str,
    baseline: dict[str, float],
    *,
    confidence: str = "D",
    refs: list[dict] | None = None,
    notes: str = "",
) -> None:
    """注册单个 persona baseline. 不写 JSON, 只 in-memory.

    Args:
        persona_id: 5 段命名
        baseline: 13-dim dict (全部 ∈ [0, 1])
        confidence: "A" / "B" / "C" / "D" (spec §3.5)
        refs: 引用列表 (可选, 至少 1 个 if confidence ∈ {A,B,C})
        notes: 实施注记

    Raises:
        ValueError: confidence 不合法 / 缺 dim / 数值超界
    """
    if confidence not in ("A", "B", "C", "D"):
        raise ValueError(
            f"confidence must be A/B/C/D, got {confidence!r}"
        )
    missing = REQUIRED_DIMS - set(baseline.keys())
    if missing:
        raise ValueError(
            f"baseline missing dims: {missing}"
        )
    for dim, val in baseline.items():
        if not (0.0 <= val <= 1.0):
            raise ValueError(
                f"baseline[{dim!r}] = {val} not in [0, 1]"
            )
    global _DB
    if _DB is None:
        _DB = {}
    _DB[persona_id] = {
        "persona_id": persona_id,
        "baseline": dict(baseline),  # 复制, 防止外部修改污染
        "confidence": confidence,
        "refs": list(refs) if refs else [],
        "notes": notes,
    }
    _STATS["register_count"] += 1


def bulk_register_persona_baselines(entries: list[dict]) -> None:
    """批量注册. entries 格式: [{persona_id, baseline, confidence, refs, notes?}, ...]

    Args:
        entries: list of dict, 每个 dict 必含 persona_id + baseline
    """
    for entry in entries:
        register_persona_baseline(
            entry["persona_id"],
            entry["baseline"],
            confidence=entry.get("confidence", "D"),
            refs=entry.get("refs"),
            notes=entry.get("notes", ""),
        )


def export_persona_labels_db(path: Path | None = None) -> None:
    """导出 in-memory KB 到 JSON 文件. 默认路径 = DB_PATH.

    用途: 渐进式回填 (4 → 16 → ... → 3072) 时, 内存注册完后持久化。
    """
    global _DB
    if _DB is None:
        _DB = get_persona_labels_db()
    out_path = path or DB_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(_DB, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info(
        f"persona_labels_db exported: {len(_DB)} entries to {out_path}"
    )


def list_persona_ids() -> list[str]:
    """返所有 persona_id (排序). 用于 /spirit_relabel 验证 / 调试。"""
    return sorted(get_persona_labels_db().keys())


def get_kb_stats() -> dict[str, int]:
    """返 KB 命中率统计 (spec §9.1).

    Returns:
        dict 含 4 key: kb_hit, kb_fallback_labels, kb_fallback_neutral, register_count
    """
    return dict(_STATS)


def reset_cache() -> None:
    """测试用: 重置 in-memory 缓存 + stats counters.

    注意: **不**重置 DB_PATH (env var 路径), 只重置运行时缓存。
    """
    global _DB
    _DB = None
    _STATS["kb_hit"] = 0
    _STATS["kb_fallback_labels"] = 0
    _STATS["kb_fallback_neutral"] = 0
    _STATS["register_count"] = 0


__all__ = [
    "REQUIRED_DIMS",
    "DB_PATH",
    "get_persona_labels_db",
    "get_baseline_for_persona",
    "get_persona_entry",
    "register_persona_baseline",
    "bulk_register_persona_baselines",
    "export_persona_labels_db",
    "list_persona_ids",
    "get_kb_stats",
    "reset_cache",
]
