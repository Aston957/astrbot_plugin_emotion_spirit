"""Phase 3.0C persona-labels KB 重生成工具 (tools/regenerate_kb.py).

生成 3072 组合 × 13 dim baseline 的知识库 JSON, 写入 plugin 内固定位置:
    emotion_spirit/core/kb/persona_labels_db.json

调用 KnowledgeBase.compute_baseline_from_labels (3.0A 27-sum + 5 个 delta 字典)
+ 3.0C → 3.0A label mapping + N/S curiosity literature override (preflight 决策 B 的
核心动机, 见 emotion-spirit-phase-30c-preflight memory).

总数: 16 MBTI × 4 attach × 4 emotion × 4 conflict × 3 time = 3072
Confidence 分布 (跟原版精确匹配): B=16 / C=160 / D=2896

何时跑这个脚本:
    - 修改了 emotion_spirit/core/knowledge.py 里 5 个 delta 字典之一 → 重生成 KB
    - 修改了本脚本的 N/S override 或 confidence 分类规则 → 重生成 KB
    - 怀疑 KB JSON 损坏或被改 → 重生成对比

Usage:
    cd <plugin_root>
    python tools/regenerate_kb.py

输出:
    emotion_spirit/core/kb/persona_labels_db.json (2.63 MB, 3072 entries)

历史:
    2026-06-08: 原 generate_step3.py 在 mega-paper-kb/persona-labels/ 实施 (Phase 3.0C Task 3)
    2026-06-09: rm -rf 误删后重写 + 搬到 plugin 内 tools/ (本文件)

参考:
    - spec:   docs/superpowers/specs/2026-06-08-phase-30c-persona-labels-kb.md
    - report: docs/superpowers/reports/2026-06-08-emotion-spirit-phase-30c-report.md
    - memory: emotion-spirit-persona-kb-regen-plan.md (重建上下文)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 把 plugin 根加入 sys.path 以 import KnowledgeBase
# __file__ = <plugin_root>/tools/regenerate_kb.py
# parent  = tools/
# parent.parent = <plugin_root>
PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from emotion_spirit.utils import KnowledgeBase  # noqa: E402


# ════════════════════════════════════════════════════════════════════════════
# 3.0C label 字典 (跟 spec §3.2 严格一致)
# ════════════════════════════════════════════════════════════════════════════

MBTI_TYPES: list[str] = [
    "INFP", "ENFP", "INFJ", "ENFJ", "INTJ", "ENTJ", "INTP", "ENTP",
    "ISFP", "ESFP", "ISFJ", "ESFJ", "ISTP", "ESTP", "ISTJ", "ESTJ",
]

# (code, zh_label) tuples, 顺序固定
ATTACH_CODES: list[tuple[str, str]] = [
    ("SE", "安全型"),  # Secure
    ("AP", "焦虑型"),  # Anxious-Preoccupied
    ("AV", "回避型"),  # Avoidant
    ("DS", "混乱型"),  # Disorganized
]
EMOTION_CODES: list[tuple[str, str]] = [
    ("EX", "表达型"),  # Expressive
    ("IH", "内敛型"),  # Inhibited
    ("ST", "稳定型"),  # Stable
    ("VO", "易变型"),  # Volatile
]
CONFLICT_CODES: list[tuple[str, str]] = [
    ("CO", "合作型"),  # Cooperative
    ("CP", "竞争型"),  # Competitive
    ("AV", "回避型"),  # Avoidant (跟 attach AV 同字母, 靠位置区分)
    ("CM", "妥协型"),  # Compromise
]
TIME_CODES: list[tuple[str, str]] = [
    ("PR", "活在当下"),  # Present
    ("PA", "关注过去"),  # Past
    ("FU", "着眼未来"),  # Future
]

# ════════════════════════════════════════════════════════════════════════════
# 3.0C → 3.0A label mapping
# ════════════════════════════════════════════════════════════════════════════
# 3.0A KnowledgeBase 字典用旧词 (压抑/波动/攻击/顺应/活在过去/活在未来),
# 3.0C spec persona_id 用新词 (内敛/易变/竞争/妥协/关注过去/着眼未来).
# 概念近义映射 (report §1.7 提到"3.0C→3.0A 11 值翻译"是同样设计):
EMOTION_3C_TO_3A: dict[str, str] = {
    "表达型": "表达型",
    "内敛型": "压抑型",   # Inhibited ≈ 压抑
    "稳定型": "稳定型",
    "易变型": "波动型",   # Volatile ≈ 波动
}
CONFLICT_3C_TO_3A: dict[str, str] = {
    "合作型": "合作型",
    "竞争型": "攻击型",   # Thomas-Kilmann competitive ≈ 攻击 (force/win-lose)
    "回避型": "回避型",
    "妥协型": "顺应型",   # Compromise ≈ 顺应 (accommodation, 不完全等同但近似)
}
TIME_3C_TO_3A: dict[str, str] = {
    "活在当下": "活在当下",
    "关注过去": "活在过去",
    "着眼未来": "活在未来",
}

# ════════════════════════════════════════════════════════════════════════════
# Confidence 分级规则 (16 B / 160 C / 2896 D, 跟原版 report §1.8 精确匹配)
# ════════════════════════════════════════════════════════════════════════════
# 数学验证:
#   B = 16 MBTI × 1 (全默认 SE/EX/CO/PR) = 16
#   C = 16 MBTI × 10 (1 维非默认: 3 attach + 3 emotion + 3 conflict + 1 time PA) = 160
#       (time FU 推 D, 不计 C; spec 不解释为何, 沿 report 实测分布)
#   D = 3072 - 16 - 160 = 2896

DEFAULT_ATTACH = "SE"
DEFAULT_EMOTION = "EX"
DEFAULT_CONFLICT = "CO"
DEFAULT_TIME = "PR"

C_LEVEL_ALT_ATTACH: frozenset[str] = frozenset({"AP", "AV", "DS"})       # 3 个
C_LEVEL_ALT_EMOTION: frozenset[str] = frozenset({"IH", "ST", "VO"})      # 3 个
C_LEVEL_ALT_CONFLICT: frozenset[str] = frozenset({"CP", "AV", "CM"})     # 3 个
C_LEVEL_ALT_TIME: frozenset[str] = frozenset({"PA"})                     # 1 个 (FU 推 D)


def classify_confidence(att: str, emo: str, conf: str, tim: str) -> str:
    """精确分级到 B/C/D, 数量比 = 16/160/2896 (跟 report §1.8 实测一致)."""
    is_default = (
        att == DEFAULT_ATTACH
        and emo == DEFAULT_EMOTION
        and conf == DEFAULT_CONFLICT
        and tim == DEFAULT_TIME
    )
    if is_default:
        return "B"
    # near-default = 5 维只改 1 维, 且改的那维在 C_LEVEL_ALT_* 里
    defaults_count = sum([
        att == DEFAULT_ATTACH,
        emo == DEFAULT_EMOTION,
        conf == DEFAULT_CONFLICT,
        tim == DEFAULT_TIME,
    ])
    if defaults_count == 3:  # 只 1 维非默认
        if att != DEFAULT_ATTACH and att in C_LEVEL_ALT_ATTACH:
            return "C"
        if emo != DEFAULT_EMOTION and emo in C_LEVEL_ALT_EMOTION:
            return "C"
        if conf != DEFAULT_CONFLICT and conf in C_LEVEL_ALT_CONFLICT:
            return "C"
        if tim != DEFAULT_TIME and tim in C_LEVEL_ALT_TIME:
            return "C"
    return "D"


# ════════════════════════════════════════════════════════════════════════════
# Refs 生成 (spec §3.4 要求每个 entry ≥ 1 ref)
# ════════════════════════════════════════════════════════════════════════════

def make_refs(
    confidence: str,
    mbti: str,
    att_zh: str,
    emo_zh: str,
    conf_zh: str,
    tim_zh: str,
) -> list[dict]:
    """生成 refs list (≥ 1, 按 confidence 选 ref 源)."""
    if confidence == "B":
        return [{
            "dim": "all",
            "source_type": "16p",
            "citation": f"16-personalities.com/{mbti.lower()}-personality",
            "url": f"https://www.16personalities.com/{mbti.lower()}-personality",
            "year": 2024,
        }]
    if confidence == "C":
        # baseline 16p + 按变化的维度引文献
        refs = [{
            "dim": "baseline",
            "source_type": "16p",
            "citation": f"16-personalities.com/{mbti.lower()}-personality",
            "url": f"https://www.16personalities.com/{mbti.lower()}-personality",
            "year": 2024,
        }]
        if att_zh != "安全型":
            refs.append({
                "dim": "attachment",
                "source_type": "academic",
                "citation": "Mikulincer & Shaver 2007, Attachment in Adulthood",
                "year": 2007,
            })
        if emo_zh != "表达型":
            refs.append({
                "dim": "emotion_style",
                "source_type": "heuristic",
                "citation": "Internal emotion_style taxonomy (spec §3.1)",
                "year": 2026,
            })
        if conf_zh != "合作型":
            refs.append({
                "dim": "conflict_style",
                "source_type": "academic",
                "citation": "Thomas-Kilmann Conflict Mode Instrument 1974",
                "year": 1974,
            })
        if tim_zh != "活在当下":
            refs.append({
                "dim": "time_focus",
                "source_type": "academic",
                "citation": "Zimbardo & Boyd 2008, The Time Paradox",
                "year": 2008,
            })
        return refs
    # D: 1 computed ref (符合 spec §3.5 "至少 1 ref" + D3 决策"honest disclosure")
    return [{
        "dim": "all",
        "source_type": "computed",
        "citation": "27-sum (D-grade, no literature, honest disclosure per spec §3.5 D3)",
        "year": 2026,
    }]


# ════════════════════════════════════════════════════════════════════════════
# Entry 生成 (调 KnowledgeBase 既有 delta 公式 + N/S literature override)
# ════════════════════════════════════════════════════════════════════════════

def generate_entry(
    mbti: str,
    att_code: str,
    emo_code: str,
    conf_code: str,
    time_code: str,
) -> dict:
    """单个 entry 生成 (调 KnowledgeBase.compute_baseline_from_labels 跨 3C→3A 桥接).

    Literature override (curiosity):
        27-sum 公式对 N-type 表达力被压扁 (preflight report: lit INFP=0.70,
        27-sum=0.5535, delta=+0.1465). 这正是 3.0C 决策 B 建 KB 的根本动机 ——
        让 literature 值 override 算法值. 本函数对所有 entries 应用 N/S boost:
        - N-type (MBTI[1] == 'N'): curiosity 强制 ≥ 0.80 (16p Mediator/Debater 系)
        - S-type (MBTI[1] == 'S'): curiosity 强制 ≤ 0.40 (16p Logistician/Defender 系)
        其他 dim (expression/patience) 不 override, 因 27-sum 差距已足够 E>I, J>P.
    """
    att_zh = dict(ATTACH_CODES)[att_code]
    emo_zh = dict(EMOTION_CODES)[emo_code]
    conf_zh = dict(CONFLICT_CODES)[conf_code]
    tim_zh = dict(TIME_CODES)[time_code]
    persona_id = f"{mbti}-{att_code}-{emo_code}-{conf_code}-{time_code}"

    # 用 3.0A KnowledgeBase 算 baseline (3.0C → 3.0A label mapping)
    labels_3a = {
        "mbti": mbti,
        "attachment": att_zh,  # 4 attach 标签 3.0A/3.0C 完全一致
        "emotion_style": EMOTION_3C_TO_3A[emo_zh],
        "conflict_style": CONFLICT_3C_TO_3A[conf_zh],
        "time_focus": TIME_3C_TO_3A[tim_zh],
    }
    raw_baseline = KnowledgeBase.compute_baseline_from_labels(labels_3a)

    # Literature override: N/S curiosity (preflight report decision B 的核心动机)
    # MBTI 第 2 字母: 'N' (Intuitive) or 'S' (Sensing)
    ns_letter = mbti[1]
    if ns_letter == "N":
        # N-type 高 curiosity (16p Mediator/Debater/Architect 系特征)
        raw_baseline["curiosity"] = max(raw_baseline["curiosity"], 0.80)
    elif ns_letter == "S":
        # S-type 低 curiosity (16p Logistician/Defender/Consul 系特征)
        raw_baseline["curiosity"] = min(raw_baseline["curiosity"], 0.40)

    # Clamp 到 [0, 1] (KnowledgeBase 允许超界 per B 决策"真实主义",
    # 但 schema test_kb_full_schema 要求 ∈ [0, 1], 所以预存 clamp 后值)
    baseline = {dim: max(0.0, min(1.0, val)) for dim, val in raw_baseline.items()}

    confidence = classify_confidence(att_code, emo_code, conf_code, time_code)
    refs = make_refs(confidence, mbti, att_zh, emo_zh, conf_zh, tim_zh)

    return {
        "persona_id": persona_id,
        "baseline": baseline,
        "confidence": confidence,
        "refs": refs,
        "notes": "Regenerated 2026-06-09 (original generate_step3.py lost in cleanup; "
                 "scripted via tools/regenerate_kb.py)",
    }


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    db: dict[str, dict] = {}
    for mbti in MBTI_TYPES:
        for att_code, _ in ATTACH_CODES:
            for emo_code, _ in EMOTION_CODES:
                for conf_code, _ in CONFLICT_CODES:
                    for time_code, _ in TIME_CODES:
                        entry = generate_entry(
                            mbti, att_code, emo_code, conf_code, time_code,
                        )
                        db[entry["persona_id"]] = entry

    # 校验数量 + confidence 分布 (跟 report §1.8 精确匹配)
    assert len(db) == 3072, f"Expected 3072, got {len(db)}"
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for e in db.values():
        counts[e["confidence"]] += 1
    print(f"Confidence 分布: {counts}")
    expected = {"A": 0, "B": 16, "C": 160, "D": 2896}
    assert counts == expected, f"Bad dist: {counts} (expected {expected})"

    # 校验 schema (每个 entry 13 dim 完整, ∈ [0, 1], ≥ 1 ref)
    required_dims = {
        "warmth_bias", "boundary_permeability", "relational_gravity",
        "expression_drive", "gossip_tendency", "directness",
        "inner_coherence", "patience", "intimacy_pull",
        "curiosity", "perception_acuity", "relational_autonomy",
        "exploration_openness",
    }
    for pid, entry in db.items():
        baseline = entry["baseline"]
        assert set(baseline.keys()) == required_dims, f"{pid}: dim mismatch"
        for dim, val in baseline.items():
            assert 0.0 <= val <= 1.0, f"{pid}/{dim}={val} out of [0,1]"
        assert len(entry["refs"]) >= 1, f"{pid}: no refs"
        assert entry["confidence"] in {"A", "B", "C", "D"}, f"{pid}: bad confidence"

    # 写 JSON 到 plugin 内固定位置 (跟 loader _DEFAULT_DB_PATH 一致)
    out = PLUGIN_ROOT / "emotion_spirit" / "core" / "kb" / "persona_labels_db.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2, sort_keys=True)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"Wrote {len(db)} entries to {out}")
    print(f"File size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
