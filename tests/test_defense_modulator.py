"""Tests for DefenseModulator (v1.2.5 PR2 §4)"""
import pytest
from unittest.mock import MagicMock
from emotion_spirit.regulation.defense_modulator import DefenseStates


def test_defense_states_default_values():
    """缺省全 0.0/''/{}"""
    s = DefenseStates()
    assert s.suppression_level == 0.0
    assert s.collapse_tendency == 0.0
    assert s.silence_tendency == 0.0
    assert s.silence_reason == ""
    assert s.silence_components == {}


def test_defense_states_with_values():
    """传值正确保存"""
    s = DefenseStates(
        suppression_level=0.5,
        collapse_tendency=0.3,
        silence_tendency=0.7,
        silence_reason="void_hurt_withdrawing",
        silence_components={"hurt_void": 0.6},
    )
    assert s.suppression_level == 0.5
    assert s.collapse_tendency == 0.3
    assert s.silence_tendency == 0.7
    assert s.silence_reason == "void_hurt_withdrawing"
    assert s.silence_components == {"hurt_void": 0.6}


def test_defense_states_suppression_clamped():
    """suppression_level > 1.0 应被 clamp 到 1.0"""
    s = DefenseStates(suppression_level=1.5)
    assert s.suppression_level == 1.0


def test_defense_states_collapse_clamped():
    """collapse_tendency < 0.0 应被 clamp 到 0.0"""
    s = DefenseStates(collapse_tendency=-0.5)
    assert s.collapse_tendency == 0.0


def test_defense_states_silence_clamped():
    """silence_tendency 越界应 clamp"""
    s = DefenseStates(silence_tendency=1.5)
    assert s.silence_tendency == 1.0
    s = DefenseStates(silence_tendency=-0.5)
    assert s.silence_tendency == 0.0


# === Task 4: KB defense_deltas.json + loader ===

def test_defense_deltas_kb_loads():
    """KB defense_deltas.json 应能被加载"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    assert deltas["_version"] >= 1
    assert "silence" in deltas
    assert "collapse" in deltas
    assert "suppression" in deltas


def test_defense_deltas_silence_clamped():
    """silence.delta 必在 [-1, 1]"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    for axis in ["individual", "natural", "social"]:
        assert -1.0 <= deltas["silence"][axis] <= 1.0


def test_defense_deltas_have_source_doc():
    """每个事件类型应有 _doc 字段 (handbook §1.1 文献背书)"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    for event in ["silence", "collapse", "suppression"]:
        assert "_doc" in deltas[event], f"{event} 缺 _doc 字段"


# === Task 5: DefenseModulator.compute_defense_states (L1) ===

def test_compute_defense_states_combines_three_defenses():
    """DefenseModulator.compute_defense_states 应合并三子"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator

    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.5)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.4, 0.6, 0.2))

    # 真 Coordinator 实例 (避免 mock silence_tendency 整个逻辑)
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator
    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}

    # 需要 mock coordinator 的 compute_silence_tendency
    from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(
        score=0.4, reason="test", components={}
    ))
    dm._segmented_coordinator = coordinator

    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)

    states = dm.compute_defense_states(
        personality=personality,
        signals=signals,
        body_state=None,
        intimacy_level=0.5,
        context={"social_audience": 0.0, "authority_present": 0.0},
        force_state={"natural": 0.5, "social": 0.5, "individual": 0.5},
    )

    assert states.suppression_level == 0.5
    assert states.collapse_tendency == 0.2
    assert states.silence_tendency == 0.4


def test_compute_defense_states_passes_force_state_to_all():
    """三子都应收到 force_state (L1)"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency

    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.5)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.5, 0.5, 0.0))

    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="test", components={}))
    dm._segmented_coordinator = coordinator

    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)
    test_force_state = {"natural": 0.7, "social": 0.3, "individual": 0.9}

    dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=test_force_state,
    )

    # 三子都应被调, 且收到 force_state
    dm._suppression.compute.assert_called_once()
    call_kwargs = dm._suppression.compute.call_args.kwargs
    assert call_kwargs.get("force_state") == test_force_state

    dm._collapse_selector.compute_bas_bis.assert_called_once()
    assert dm._collapse_selector.compute_bas_bis.call_args.kwargs.get("force_state") == test_force_state

    coordinator.compute_silence_tendency.assert_called_once()
    assert coordinator.compute_silence_tendency.call_args.kwargs.get("force_state") == test_force_state


def test_compute_defense_states_returns_defense_states_instance():
    """返回值必须是 DefenseStates 实例"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator, DefenseStates
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency

    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.0)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.0, 0.0, 0.0))

    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="", components={}))
    dm._segmented_coordinator = coordinator

    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)

    states = dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
    )
    assert isinstance(states, DefenseStates)


def test_compute_defense_states_without_force_state():
    """不传 force_state → 三子都不应传 force_state (向后兼容)"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency

    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.0)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.0, 0.0, 0.0))

    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="", components={}))
    dm._segmented_coordinator = coordinator

    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)

    dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
    )

    # 不传 force_state 时, kwargs 应不含 force_state
    call_kwargs = dm._suppression.compute.call_args.kwargs
    assert "force_state" not in call_kwargs or call_kwargs.get("force_state") is None


# === HP-2 + DO-4: conscience_pressure 参数 (v1.2.7) ===

def test_compute_defense_states_accepts_conscience_pressure():
    """conscience_pressure 参数应传给 suppression.compute (替代旧 hasattr 分支)"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency

    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.5)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.4, 0.6, 0.2))

    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="", components={}))
    dm._segmented_coordinator = coordinator

    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)

    dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
        conscience_pressure=0.75,
    )

    # suppression.compute 应收到 conscience_pressure=0.75
    dm._suppression.compute.assert_called_once()
    call_kwargs = dm._suppression.compute.call_args.kwargs
    assert call_kwargs.get("conscience_pressure") == 0.75


def test_compute_defense_states_default_conscience_pressure():
    """不传 conscience_pressure → 默认 0.0"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator, SilenceTendency

    dm = DefenseModulator.__new__(DefenseModulator)
    dm._suppression = MagicMock()
    dm._suppression.compute = MagicMock(return_value=0.0)
    dm._collapse_selector = MagicMock()
    dm._collapse_selector.compute_bas_bis = MagicMock(return_value=(0.0, 0.0, 0.0))

    coordinator = SegmentedReplyCoordinator.__new__(SegmentedReplyCoordinator)
    coordinator._consecutive_silence_count = {}
    coordinator._turns_since_last_silence = {}
    coordinator.compute_silence_tendency = MagicMock(return_value=SilenceTendency(score=0.0, reason="", components={}))
    dm._segmented_coordinator = coordinator

    personality = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "conscientiousness": 0.5}
    signals = MagicMock(rhythm_strain=0.5, pad_valence=0.5, hot_pool_pressure=0.0)

    dm.compute_defense_states(
        personality=personality, signals=signals, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
    )

    dm._suppression.compute.assert_called_once()
    call_kwargs = dm._suppression.compute.call_args.kwargs
    # 默认应传 0.0 (不依赖 hasattr)
    assert call_kwargs.get("conscience_pressure") == 0.0


def test_compute_defense_states_no_hasattr_branch():
    """DefenseModulator 不应有 _conscience 属性或 hasattr 分支"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    # 不应有 _conscience
    assert not hasattr(dm, "_conscience"), "HP-2: DefenseModulator 不应有 _conscience 属性"


# === Task 6: DefenseModulator.apply_event (L2) + force_dynamics.shift() ===

def test_apply_event_silence_modifies_force_state():
    """apply_event("silence", 0.5) 应调 force_dynamics.shift() with silence delta * 0.5"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    dm._force_dynamics.shift = MagicMock()

    dm.apply_event("silence", intensity=0.5)

    dm._force_dynamics.shift.assert_called_once()
    call_kwargs = dm._force_dynamics.shift.call_args.kwargs
    # KB: silence.individual=-0.05, * intensity=0.5 = -0.025
    assert abs(call_kwargs["individual_delta"] - (-0.025)) < 0.001
    # KB: silence.natural=0.03, * 0.5 = 0.015
    assert abs(call_kwargs["natural_delta"] - 0.015) < 0.001


def test_apply_event_collapse_modifies_force_state():
    """apply_event("collapse", 1.0) 应调 shift() with collapse delta"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    dm._force_dynamics.shift = MagicMock()

    dm.apply_event("collapse", intensity=1.0)

    dm._force_dynamics.shift.assert_called_once()
    call_kwargs = dm._force_dynamics.shift.call_args.kwargs
    # KB: collapse.individual=0.05, collapse.natural=-0.08, collapse.social=0.03
    assert abs(call_kwargs["individual_delta"] - 0.05) < 0.001
    assert abs(call_kwargs["natural_delta"] - (-0.08)) < 0.001
    assert abs(call_kwargs["social_delta"] - 0.03) < 0.001


def test_apply_event_suppression_modifies_force_state():
    """apply_event("suppression", 0.7) 应调 shift() with suppression delta"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()
    dm._force_dynamics.shift = MagicMock()

    dm.apply_event("suppression", intensity=0.7)

    dm._force_dynamics.shift.assert_called_once()
    call_kwargs = dm._force_dynamics.shift.call_args.kwargs
    # KB: suppression.individual=0.04, suppression.social=-0.02, suppression.natural=0.0
    assert abs(call_kwargs["individual_delta"] - 0.028) < 0.001  # 0.04 * 0.7
    assert abs(call_kwargs["social_delta"] - (-0.014)) < 0.001  # -0.02 * 0.7


def test_apply_event_invalid_type_raises():
    """defense_type 不是 silence/collapse/suppression 应抛 ValueError"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    dm = DefenseModulator.__new__(DefenseModulator)
    dm._force_dynamics = MagicMock()

    with pytest.raises(ValueError, match="defense_type must be"):
        dm.apply_event("invalid_type", intensity=0.5)


# === Task 7: main.py 集成 DefenseModulator ===

def test_defense_modulator_in_module_registry():
    """defense_modulator 必须在 ModuleRegistry 里 (@register 生效)"""
    from emotion_spirit.core.registry import ModuleRegistry
    all_modules = ModuleRegistry.get_all()
    assert "defense_modulator" in all_modules
    # 提供 DefenseModulator class
    spec = all_modules["defense_modulator"]
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    assert spec.module_class is DefenseModulator
    # 4 个依赖都注册
    for dep in ["force_dynamics", "suppression", "collapse_archetype_selector", "segmented_reply_coordinator"]:
        assert dep in spec.depends_on, f"missing dep: {dep}"


def test_defense_modulator_factory_can_instantiate():
    """plugin_factory.build() 应能实例化 DefenseModulator (验证 __init__ + DI 装配)"""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    # 实例化 (传 4 个 None, 验证 __init__ 签名)
    instance = DefenseModulator(None, None, None, None)
    assert isinstance(instance, DefenseModulator)
    # 验证 4 个 deps 都被存为下划线属性
    assert instance._force_dynamics is None
    assert instance._suppression is None
    assert instance._collapse_selector is None
    assert instance._segmented_coordinator is None
