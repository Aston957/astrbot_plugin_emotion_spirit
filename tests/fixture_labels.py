"""5 persona fixture labels (Phase 3.0A, Task 2)。

5 persona 测试 fixture labels (仅测试用, 不进 KB)。

5 persona 名字 (INFP-A / ISTJ-S / ENTP-AV / ISFJ-D / ESTP-A) 来自 Phase 3.0A 删的
KB.PERSONA_BASELINES。Labels 是基于后缀规则"猜的" (-A 安全型, -AV 回避型, -S 稳定, -D 压抑),
未来 Phase 3.0C 文献化取代。

注: 放在 fixture_labels.py (而非 conftest.py) 是因为 pytest conftest.py 有特殊
加载语义, 其他测试文件 (e.g. verification/test_gossip_tendency_simulation.py) 需要
通过 importlib 或 sys.path 加载。fixture_labels.py 是普通 Python module, 可被
任何位置 import, 降低耦合。
"""
from __future__ import annotations

INFP_A_LABELS: dict[str, str] = {
    "mbti": "INFP",
    "attachment": "安全型",
    "emotion_style": "表达型",
    "conflict_style": "合作型",
    "time_focus": "活在当下",
}
ISTJ_S_LABELS: dict[str, str] = {
    "mbti": "ISTJ",
    "attachment": "安全型",
    "emotion_style": "压抑型",
    "conflict_style": "回避型",
    "time_focus": "活在过去",
}
ENTP_AV_LABELS: dict[str, str] = {
    "mbti": "ENTP",
    "attachment": "回避型",
    "emotion_style": "表达型",
    "conflict_style": "攻击型",
    "time_focus": "活在未来",
}
ISFJ_D_LABELS: dict[str, str] = {
    "mbti": "ISFJ",
    "attachment": "焦虑型",
    "emotion_style": "稳定型",
    "conflict_style": "顺应型",
    "time_focus": "活在当下",
}
ESTP_A_LABELS: dict[str, str] = {
    "mbti": "ESTP",
    "attachment": "安全型",
    "emotion_style": "表达型",
    "conflict_style": "攻击型",
    "time_focus": "活在当下",
}

ALL_5_FIXTURE_LABELS: list[dict[str, str]] = [
    INFP_A_LABELS,
    ISTJ_S_LABELS,
    ENTP_AV_LABELS,
    ISFJ_D_LABELS,
    ESTP_A_LABELS,
]

ALL_5_FIXTURE_NAMES: list[str] = ["INFP-A", "ISTJ-S", "ENTP-AV", "ISFJ-D", "ESTP-A"]

ALL_5_FIXTURES: list[tuple[str, dict[str, str]]] = list(
    zip(ALL_5_FIXTURE_NAMES, ALL_5_FIXTURE_LABELS)
)
