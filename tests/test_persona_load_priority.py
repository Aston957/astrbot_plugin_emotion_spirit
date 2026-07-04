"""Patch B (v1.2.11): _load_persona_state B5 conditional 守护.

原 v1.2.2-fix(B5): config.auto_source 显式时, 无论 saved 是否已初始化都强制
reset (initialized=False + labels={}) 走 LLM. 但 LLM 不可用 (无 API key /
free tier 用尽 / 厂商 outage) 时这条路径死掉, saved labels 永远读不到,
18 命令全报"无标签数据". v1.2.11 改 conditional: saved 已初始化 → 信任 saved;
saved 未初始化 → 走 B5.

4 case 覆盖 (用户反馈 §4.3):
- case 1: saved 初始化 + config 空 → 信任 saved
- case 2: saved 初始化 + config 显式 + 可用 → 信任 saved (核心修复: 不再重置!)
- case 3: saved sentinel + config 显式 + 可用 → B5 触发 (initialized=False)
- case 4: saved sentinel + config 空 → fallback sentinel

构造模式复用 test_init_persistence.test_t2: __new__ 跳过 __init__ (避免跑
build_modules 48 模块装配), 注入 store/config, 调 _load_persona_state().

用户反馈: 2026-07-04-emotion-spirit-v1210-feedback.md §4.
"""
from __future__ import annotations

import tempfile

from emotion_spirit.store import SpiritStore
from main import EmotionSpiritPlugin


_SAVED_LABELS = {
    "mbti": "ENFJ",
    "attachment": "焦虑型",
    "emotion_style": "表达型",
    "conflict_style": "顺应型",
    "time_focus": "活在当下",
}


def _saved_persona(persona_id: str = "广濑爱贵", labels: dict | None = None) -> dict:
    """构造已初始化的 saved persona (initialized=True + labels 非空)."""
    return {
        "initialized": True,
        "persona_id": persona_id,
        "labels": labels if labels is not None else dict(_SAVED_LABELS),
        "initialized_at": "2026-07-04T10:00:00+00:00",
        "schema_version": 1,
    }


def _make_plugin(store: SpiritStore, config: dict) -> EmotionSpiritPlugin:
    """__new__ 跳过 __init__, 注入 store/config, 返回调 _load_persona_state 前的 plugin."""
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._store = store
    plugin._config = config
    plugin._persona_initialized = False
    plugin._labels = {}
    plugin._current_persona = ""
    return plugin


def test_case1_saved_initialized_config_empty_trusts_saved():
    """case 1: saved 已初始化 + config 无 auto_source → 信任 saved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.set("persona", _saved_persona())
        plugin = _make_plugin(store, config={})
        plugin._load_persona_state()
        assert plugin._persona_initialized is True
        assert plugin._labels == _SAVED_LABELS
        assert plugin._current_persona == "广濑爱贵"


def test_case2_saved_initialized_config_explicit_trusts_saved_no_reset():
    """case 2 (核心修复): saved 已初始化 + config.auto_source 显式 + 可用 → 仍信任 saved.

    原 B5 会 reset (initialized=False, labels={}); v1.2.11 跳过 B5.
    这是 LLM 不可用用户 (手动注入 spirit_data.json labels) 的痛点修复 —
    用户反馈文档 §4.1 的灾难场景: B5 清空 labels → 18 命令全报"无标签数据".
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.set("persona", _saved_persona())
        plugin = _make_plugin(store, config={"auto_source": "广濑爱贵"})
        plugin._list_available_personas = lambda: ["广濑爱贵", "其他"]
        plugin._load_persona_state()
        # 关键: 不重置 (原 B5 会把这俩清空)
        assert plugin._persona_initialized is True, (
            "saved 已初始化时不应被 B5 重置 (LLM 不可用用户依赖 saved labels)"
        )
        assert plugin._labels == _SAVED_LABELS, "labels 不应被 B5 清空"
        assert plugin._current_persona == "广濑爱贵"


def test_case3_saved_sentinel_config_explicit_triggers_b5():
    """case 3: saved 未初始化 + config.auto_source 显式 + 可用 → B5 触发 LLM (首次引导)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        # saved 是 sentinel (initialized=False / labels 空)
        store.set("persona", {"initialized": False, "persona_id": "default", "labels": {}})
        plugin = _make_plugin(store, config={"auto_source": "广濑爱贵"})
        plugin._list_available_personas = lambda: ["广濑爱贵"]
        plugin._load_persona_state()
        assert plugin._persona_initialized is False
        assert plugin._labels == {}
        assert plugin._current_persona == "广濑爱贵"


def test_case4_saved_sentinel_config_empty_falls_back():
    """case 4: saved 未初始化 + config 无 auto_source → fallback sentinel (走 _migrate)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.set("persona", {"initialized": False, "persona_id": "default", "labels": {}})
        plugin = _make_plugin(store, config={})
        # _migrate_old_spirit_data 做迁移, 测试环境 mock 避免副作用 (本 case 只验证 fallback 走到它)
        migrated = {"called": False}
        plugin._migrate_old_spirit_data = lambda: migrated.__setitem__("called", True)
        plugin._load_persona_state()
        assert plugin._persona_initialized is False
        assert plugin._labels == {}
        assert migrated["called"] is True, "saved sentinel + config 空 应 fallback 到 _migrate_old_spirit_data"
