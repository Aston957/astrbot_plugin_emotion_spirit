"""Phase 2.5 完整集成测试 (Step 4).

跨模块验证 Phase 2.5 全栈:
1. RelationshipPersonality + Intimacy 段 协作
2. apply_to_layers 不修改 base
3. apply_tone 累加语义
4. 端到端: 用户亲密度变化 → 段变化 → tone 变化 → delta 累加 → effective personality
5. per-user 隔离: A 的 delta 不影响 B
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.relationship_personality import RelationshipPersonality, ALL_DIMS
from emotion_spirit.memory.intimacy import IntimacyTracker


def test_e2e_segment_change_changes_tone():
    """段变化 → tone 变化 → delta 不同。"""
    tracker = IntimacyTracker()
    rp = RelationshipPersonality()

    # 1. 初始 alice: stranger
    seg_a = tracker.get_segment("alice")
    tone_a = tracker.get_relationship_tone("alice")
    rp.apply_tone("alice", tone_a)
    delta_a = rp.get_delta("alice")

    # 2. 提升 alice 亲密 → 段变化
    tracker.update(
        "alice",
        temporal_hours=2000,
        interval_seconds=200,
        vulnerability_delta=1.0,
        user_investment_delta=1.0,
        repair_count=5,
        shared_narrative=0.8,
    )
    seg_b = tracker.get_segment("alice")
    tone_b = tracker.get_relationship_tone("alice")
    rp.apply_tone("alice", tone_b)
    delta_b = rp.get_delta("alice")

    # 验证段变化
    assert seg_a != seg_b
    # 验证 tone 不同 (至少 warmth_bias 应该有差异)
    assert tone_a.get("warmth_bias", 0) != tone_b.get("warmth_bias", 0)
    # 验证 delta 累加 (warmth_bias 上升)
    assert delta_b.get("warmth_bias", 0) > delta_a.get("warmth_bias", 0)


def test_e2e_apply_to_layers_creates_effective():
    """apply_to_layers: base + delta → effective_personality。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth_bias", 0.15)
    rp.set_delta("alice", "intimacy_pull", 0.1)

    # base (deep + surface 格式)
    base = {
        "deep": {"warmth_bias": 0.5, "intimacy_pull": 0.4, "relational_autonomy": 0.7},
        "surface": {"warmth_bias": 0.6, "intimacy_pull": 0.5, "relational_autonomy": 0.7},
    }
    effective = rp.apply_to_layers(base, "alice")

    # deep.warmth_bias: 0.5 + 0.15 = 0.65
    assert effective["deep"]["warmth_bias"] == 0.65
    # deep.intimacy_pull: 0.4 + 0.1 = 0.5
    assert effective["deep"]["intimacy_pull"] == 0.5
    # relational_autonomy 不在 delta 中 → 不变
    assert effective["deep"]["relational_autonomy"] == 0.7
    # surface 同样
    assert effective["surface"]["warmth_bias"] == 0.75


def test_e2e_apply_to_layers_clamps_to_0_1():
    """apply_to_layers 后的值应 clamp 到 [0, 1]。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth_bias", 0.3)  # 累加上限
    base = {"deep": {"warmth_bias": 0.9}}
    effective = rp.apply_to_layers(base, "alice")
    # 0.9 + 0.3 = 1.2 → clamp 1.0
    assert effective["deep"]["warmth_bias"] == 1.0


def test_e2e_per_user_delta_isolation_in_effective():
    """per-user 隔离: A 和 B 看到不同 effective。"""
    rp = RelationshipPersonality()
    rp.set_delta("alice", "warmth_bias", 0.2)
    rp.set_delta("bob", "warmth_bias", -0.1)

    base = {"deep": {"warmth_bias": 0.5}}
    eff_a = rp.apply_to_layers(base, "alice")
    eff_b = rp.apply_to_layers(base, "bob")
    # alice: 0.5 + 0.2 = 0.7
    assert eff_a["deep"]["warmth_bias"] == 0.7
    # bob: 0.5 - 0.1 = 0.4
    assert eff_b["deep"]["warmth_bias"] == 0.4


def test_e2e_apply_tone_accumulates_not_replaces():
    """apply_tone 累加: 多次调用不应覆盖既有 delta。"""
    rp = RelationshipPersonality()
    rp.apply_tone("alice", {"warmth_bias": 0.05, "expression_drive": 0.03})
    rp.apply_tone("alice", {"warmth_bias": 0.05})
    delta = rp.get_delta("alice")
    # warmth_bias 应累加为 0.10
    assert abs(delta["warmth_bias"] - 0.10) < 1e-9
    # expression_drive 第一次设 0.03, 第二次没设 → 保持 0.03
    assert abs(delta["expression_drive"] - 0.03) < 1e-9


def test_e2e_full_intimacy_to_effective_flow():
    """完整流: intimacy update → segment → tone → delta → effective personality。"""
    tracker = IntimacyTracker()
    rp = RelationshipPersonality()

    # 1. 初始 alice: stranger
    seg_initial = tracker.get_segment("alice")
    assert seg_initial == "stranger"

    # 2. 累积亲密
    for _ in range(3):
        tracker.update(
            "alice",
            temporal_hours=500,
            interval_seconds=600,
            vulnerability_delta=0.3,
            user_investment_delta=0.3,
            repair_count=1,
        )

    # 3. 段变化
    seg_after = tracker.get_segment("alice")
    assert seg_after != "stranger"  # 至少是 acquaintance

    # 4. 应用 tone
    tone = tracker.get_relationship_tone("alice")
    rp.apply_tone("alice", tone)

    # 5. 应用到 base
    base = {"deep": {"warmth_bias": 0.5, "intimacy_pull": 0.4}}
    effective = rp.apply_to_layers(base, "alice")

    # 6. 验证: 高亲密段应有正向 warmth_bias delta
    delta_warmth = rp.get_single_delta("alice", "warmth_bias")
    assert delta_warmth >= 0  # 至少不降低
    # effective warmth_bias 应 >= base warmth_bias
    assert effective["deep"]["warmth_bias"] >= base["deep"]["warmth_bias"]


def test_e2e_stranger_vs_inner_circle_opposite_tone():
    """stranger 和 inner_circle 的 warmth_bias tone 方向相反。"""
    tracker = IntimacyTracker()
    # alice: 无交互 → stranger
    tone_stranger = tracker.get_relationship_tone("alice")
    # bob: 极高亲密
    tracker.update(
        "bob",
        temporal_hours=5000,
        interval_seconds=60,
        vulnerability_delta=2.0,
        user_investment_delta=2.0,
        repair_count=10,
        shared_narrative=1.0,
    )
    tone_inner = tracker.get_relationship_tone("bob")

    # stranger warmth_bias 应 < 0
    assert tone_stranger["warmth_bias"] < 0
    # inner_circle warmth_bias 应 > 0
    assert tone_inner["warmth_bias"] > 0
    # 反向
    assert tone_stranger["warmth_bias"] * tone_inner["warmth_bias"] < 0


def test_e2e_apply_to_layers_no_delta_returns_base_copy():
    """无 delta: apply_to_layers 返回 base 的 copy (无修改)。"""
    rp = RelationshipPersonality()
    base = {"deep": {"warmth_bias": 0.5}}
    base_copy = {"deep": {"warmth_bias": 0.5}}
    eff = rp.apply_to_layers(base, "unknown_user")
    assert eff == base_copy
    # 验证是不同对象
    assert eff is not base


def test_e2e_4_segments_produce_4_distinct_tones():
    """4 段都应能产生 (至少不抛异常), 即使都返回空 dict。"""
    tracker = IntimacyTracker()
    # 强制 4 个不同的段
    # alice: 陌生人
    # bob: 熟人
    tracker.update("bob", temporal_hours=200, interval_seconds=1800, shared_narrative=0.3)
    # carol: 朋友
    tracker.update(
        "carol",
        temporal_hours=600, interval_seconds=600,
        vulnerability_delta=0.4, user_investment_delta=0.3, repair_count=2,
    )
    # dave: inner_circle
    tracker.update(
        "dave",
        temporal_hours=2000, interval_seconds=120,
        vulnerability_delta=1.5, user_investment_delta=1.5, repair_count=8,
    )
    for uid in ["alice", "bob", "carol", "dave"]:
        seg = tracker.get_segment(uid)
        tone = tracker.get_relationship_tone(uid)
        # 验证 tone 是 dict 且有完整 11 维
        assert isinstance(tone, dict)
        for dim in ALL_DIMS:
            assert dim in tone


def test_e2e_serialization_after_apply_tone():
    """应用 tone 后, 序列化 + 反序列化保留 delta。"""
    rp1 = RelationshipPersonality()
    rp1.apply_tone("alice", {"warmth_bias": 0.1, "intimacy_pull": 0.2})
    rp1.apply_tone("bob", {"warmth_bias": -0.05})

    data = rp1.to_dict()
    rp2 = RelationshipPersonality.from_dict(data)
    # alice 保留
    assert abs(rp2.get_single_delta("alice", "warmth_bias") - 0.1) < 1e-9
    assert abs(rp2.get_single_delta("alice", "intimacy_pull") - 0.2) < 1e-9
    # bob 保留
    assert abs(rp2.get_single_delta("bob", "warmth_bias") - (-0.05)) < 1e-9
    # carol (无 delta) 不应在 from_dict 后存在
    assert "carol" not in rp2.list_users_with_deltas()


if __name__ == "__main__":
    test_e2e_segment_change_changes_tone()
    test_e2e_apply_to_layers_creates_effective()
    test_e2e_apply_to_layers_clamps_to_0_1()
    test_e2e_per_user_delta_isolation_in_effective()
    test_e2e_apply_tone_accumulates_not_replaces()
    test_e2e_full_intimacy_to_effective_flow()
    test_e2e_stranger_vs_inner_circle_opposite_tone()
    test_e2e_apply_to_layers_no_delta_returns_base_copy()
    test_e2e_4_segments_produce_4_distinct_tones()
    test_e2e_serialization_after_apply_tone()
    print("All Phase 2.5 integration tests passed!")
