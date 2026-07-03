"""emotion_spirit — 3072 组合 persona-labels KB loader (Phase 3.0C.1)。

数据层 loader: 加载 plugin 内 emotion_spirit/core/kb/persona_labels_db.json
(~2.6 MB, 3072 entries), in-memory 缓存, 提供 baseline 查询 + 渐进式注册 API。

注意: 本模块**不加 @register** (loader 是数据查询, 不是 plugin module)。
3.0C.1 范围: loader 骨架 + 4 组合 stub + register/export API。Task 2 加
force_state_from_persona_id() 主入口。

路径覆盖: 支持 EMOTION_SPIRIT_PERSONA_KB_PATH 环境变量, 缺省 = plugin 内默认路径
(测试可临时指向 tmp_path)。

KB 重生成: tools/regenerate_kb.py (开发时跑这个脚本可重新算 3072 baseline 写 JSON)

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
from typing import TYPE_CHECKING, Any

from ..utils.knowledge import KnowledgeBase

if TYPE_CHECKING:
    from ..regulation.body_state import BodyState
    from ..regulation.force_dynamics import ForceState

logger = logging.getLogger(__name__)

# === persona_id 编码常量 (Phase 3.0C.2a spec §3.2) ===
# 5 段: <MBTI>-<attachment 2字母>-<emotion 2字母>-<conflict 2字母>-<time 2字母>
# 全部 2 字母 (MBTI 段除外, 3-4 字母原样), 位置解析消歧 AV 冲突 (段 2 vs 段 4)

MBTI_TYPES: frozenset[str] = frozenset({
    "INFP", "ENFP", "INFJ", "ENFJ", "INTJ", "ENTJ", "INTP", "ENTP",
    "ISFP", "ESFP", "ISFJ", "ESFJ", "ISTP", "ESTP", "ISTJ", "ESTJ",
})

ATTACH_CODES: dict[str, str] = {
    "SE": "安全型",  # Secure
    "AP": "焦虑型",  # Anxious-Preoccupied
    "AV": "回避型",  # Avoidant
    "DS": "混乱型",  # Disorganized
}

EMOTION_CODES: dict[str, str] = {
    "EX": "表达型",  # Expressive
    "IH": "内敛型",  # Inhibited
    "ST": "稳定型",  # Stable
    "VO": "易变型",  # Volatile
}

CONFLICT_CODES: dict[str, str] = {
    "CO": "合作型",   # Cooperative
    "CP": "竞争型",   # Competitive
    "AV": "回避型",   # Avoidant (跟 attachment AV 同字母, 靠位置区分)
    "CM": "妥协型",   # Compromise
}

TIME_CODES: dict[str, str] = {
    "PR": "活在当下",  # Present
    "PA": "关注过去",  # Past
    "FU": "着眼未来",  # Future
}

# 13 dim baseline 必备 key 集合 (与 3.0A KnowledgeBase.ALL_PERSONALITY_DIMS 一致)
REQUIRED_DIMS: frozenset[str] = frozenset({
    "warmth_bias", "boundary_permeability", "relational_gravity",
    "expression_drive", "gossip_tendency", "directness",
    "inner_coherence", "patience", "intimacy_pull",
    "curiosity", "perception_acuity", "relational_autonomy", "exploration_openness",
})

# 默认路径: plugin 内 emotion_spirit/core/kb/persona_labels_db.json
# 跟 plugin 一起分发, git clone / pip install 即用, 无需用户额外配置.
# 历史: 2026-06-08 KB 在外部 mega-paper-kb sibling, 2026-06-09 cleanup 后搬入 plugin
# (commit 5d28c13 修外部路径, 后续 commit 移到 plugin 内 core/kb/ 永久存放)
# env var EMOTION_SPIRIT_PERSONA_KB_PATH 仍可覆盖默认路径 (开发/部署灵活)
_DEFAULT_DB_PATH = (
    Path(__file__).parent  # emotion_spirit/core/
    / "kb"                 # emotion_spirit/core/kb/
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


# ════════════════════════════════════════════════════════════════════════════
# Phase 3.0C.2a — 主入口 API (force_state_from_persona_id) + 解析 API
# ════════════════════════════════════════════════════════════════════════════


def parse_persona_id(persona_id: str) -> dict[str, str] | None:
    """解析 persona_id → 5-key labels dict (中文标签)。None = 解析失败。

    Args:
        persona_id: 5 段命名, e.g. "INFP-AV-EX-CO-PR"
            - 段 1: MBTI (16 合法类型)
            - 段 2: attachment (SE/AP/AV/DS)
            - 段 3: emotion_style (EX/IH/ST/VO)
            - 段 4: conflict_style (CO/CP/AV/CM)
            - 段 5: time_focus (PR/PA/FU)

    Returns:
        dict 含 mbti/attachment/emotion_style/conflict_style/time_focus (中文)
        或 None (任何一段非法)

    Note:
        AV 在段 2 (attachment) 和段 4 (conflict_style) 都合法, 靠位置解析消歧
        (spec §3.2 显式标注, memory 8 spec 偏离 #7)。
    """
    if not persona_id or not isinstance(persona_id, str):
        return None
    parts = persona_id.split("-")
    if len(parts) != 5:
        return None
    mbti, attach, emo, conf, time = parts
    if mbti not in MBTI_TYPES:
        return None
    if attach not in ATTACH_CODES:
        return None
    if emo not in EMOTION_CODES:
        return None
    if conf not in CONFLICT_CODES:
        return None
    if time not in TIME_CODES:
        return None
    return {
        "mbti": mbti,
        "attachment": ATTACH_CODES[attach],
        "emotion_style": EMOTION_CODES[emo],
        "conflict_style": CONFLICT_CODES[conf],
        "time_focus": TIME_CODES[time],
    }


def force_state_from_persona_id(
    persona_id: str,
    *,
    body_state: "BodyState | None" = None,
    conscience_pressure: float = 0.0,
) -> "ForceState":
    """3.0C 主入口: 走 KB → 27-sum fallback → 中性 fallback。

    Args:
        persona_id: 5 段命名 (见 parse_persona_id)
        body_state: 3.0B BodyState, 透传到 ForceDynamics.compute()
        conscience_pressure: 3.0B 良心压力, ∈ [0, 1]

    Returns:
        ForceState (3 权重, sum=1.0)

    Raises:
        ValueError: conscience_pressure 不在 [0, 1]

    Fallback 路径 (3 个, 全部走 ForceDynamics.compute()):
        - 路径 A (kb_hit): persona_id 存在 KB → 直接用 KB baseline (13-dim)
        - 路径 B (kb_fallback_labels): persona_id 合法但不在 KB → 27-sum
          (parse_persona_id → labels → KnowledgeBase.compute_baseline_from_labels)
        - 路径 C (kb_fallback_neutral): persona_id 解析失败 → 中性 baseline (0.5 × 13)

    Spec deviation (vs plan §Step 2.1):
        Plan 假设 `ForceDynamics.compute(labels=...)` 存在, 实际 API 是
        `ForceDynamics.compute(personality: dict[str, float])` (13-dim)。
        Plan 引入的 `_baseline_override` 注入机制不需要——baseline 直接
        当 personality 传。spec §4.1 描述的行为完全可达, 实现更简洁。
    """
    # 延迟 import 避免循环依赖 (force_dynamics imports knowledge, body_state)
    from ..regulation.force_dynamics import ForceDynamics

    # 校验 conscience_pressure (跟 ForceDynamics.compute 一致)
    if not (0.0 <= conscience_pressure <= 1.0):
        raise ValueError(
            f"conscience_pressure 必须在 [0, 1]: 收到 {conscience_pressure}"
        )

    fd = ForceDynamics()
    labels = parse_persona_id(persona_id)
    if labels is None:
        # 路径 C: 解析失败 → 中性 baseline
        _STATS["kb_fallback_neutral"] += 1
        logger.error(
            f"persona_id {persona_id!r} malformed, using neutral baseline (0.5 × 13)"
        )
        neutral_baseline = {dim: 0.5 for dim in REQUIRED_DIMS}
        return fd.compute(
            personality=neutral_baseline,
            body_state=body_state,
            conscience_pressure=conscience_pressure,
        )

    # persona_id 合法: 查 KB
    baseline = get_baseline_for_persona(persona_id)
    if baseline is None:
        # 路径 B: 不在 KB → 27-sum fallback (KnowledgeBase 27-sum 公式)
        _STATS["kb_fallback_labels"] += 1
        logger.warning(
            f"persona_id {persona_id!r} not in KB, using 27-sum fallback"
        )
        baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    else:
        # 路径 A: KB 命中
        _STATS["kb_hit"] += 1

    # baseline 现在是 13-dim dict, 直接当 personality 传给 compute()
    return fd.compute(
        personality=baseline,
        body_state=body_state,
        conscience_pressure=conscience_pressure,
    )


def force_state_from_persona_id_with_conscience(
    persona_id: str,
    conscience_tracker,
    *,
    body_state: "BodyState | None" = None,
) -> "ForceState":
    """3.0C 便捷方法, 跟 3.0B force_state_with_conscience 对标 (spec §9.5)。

    Args:
        persona_id: 5 段命名 (见 parse_persona_id)
        conscience_tracker: 接受 3 种类型:
            - ConscienceTracker 实例: 调 .get_pressure() 读压力
            - float: 直接当 conscience_pressure
            - None: 压力=0
        body_state: 3.0B BodyState, 透传到 ForceDynamics.compute()

    Returns:
        ForceState (3 权重, sum=1.0)

    Raises:
        TypeError: conscience_tracker 不是上述 3 种类型

    设计: 避免 caller 误传 scalar (3.0B 偏离 E 教训), 内部 auto-normalize
    conscience_tracker.get_pressure() 到 [0, 1] (defensive, 实际 3.0B 已修)。
    """
    # 解析 conscience_tracker → pressure
    if conscience_tracker is None:
        pressure = 0.0
    elif isinstance(conscience_tracker, (int, float)):
        pressure = float(conscience_tracker)
    elif hasattr(conscience_tracker, "get_pressure") and callable(
        conscience_tracker.get_pressure
    ):
        # 假定 ConscienceTracker 实例 (duck typing, 避免硬依赖 3.0B)
        # 内部: get_pressure() 返 [0, 1] 已 (3.0B spec 偏离 E 已修),
        # 但仍 clip 防御
        raw_pressure = conscience_tracker.get_pressure()
        pressure = max(0.0, min(1.0, float(raw_pressure)))
    else:
        raise TypeError(
            f"conscience_tracker must be ConscienceTracker, float, or None; "
            f"got {type(conscience_tracker).__name__}"
        )

    return force_state_from_persona_id(
        persona_id,
        body_state=body_state,
        conscience_pressure=pressure,
    )


# v1.2.5: KB 加载缓存
_kb_cache: dict[str, dict] = {}


def _cached_load(filename: str) -> dict:
    """v1.2.5: 通用 KB 加载 + 缓存 (类似现有 export_persona_labels_db)"""
    if filename in _kb_cache:
        return _kb_cache[filename]

    kb_dir = Path(__file__).parent / "kb"
    filepath = kb_dir / filename
    if not filepath.exists():
        raise FileNotFoundError(f"KB file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    _kb_cache[filename] = data
    return data


def get_silence_tendency_weights() -> dict:
    """v1.2.5 PR1: 加载沉默公式加权系数 (KB)"""
    return _cached_load("silence_tendency_weights.json")


def get_defense_deltas() -> dict:
    """v1.2.5 PR2: 加载防御事件回写 delta (KB)"""
    return _cached_load("defense_deltas.json")


__all__ = [
    "REQUIRED_DIMS",
    "DB_PATH",
    "MBTI_TYPES",
    "ATTACH_CODES",
    "EMOTION_CODES",
    "CONFLICT_CODES",
    "TIME_CODES",
    "get_persona_labels_db",
    "get_baseline_for_persona",
    "get_persona_entry",
    "register_persona_baseline",
    "bulk_register_persona_baselines",
    "export_persona_labels_db",
    "list_persona_ids",
    "get_kb_stats",
    "reset_cache",
    "parse_persona_id",
    "force_state_from_persona_id",
    "force_state_from_persona_id_with_conscience",
    "get_silence_tendency_weights",
    "get_defense_deltas",
]
