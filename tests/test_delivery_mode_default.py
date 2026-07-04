"""Bug-E/H (v1.3.0 rc.3): delivery_mode 默认 event_send 守护.

Bug-H (framework reply preservation) 让 append 模式不可用 (bot 不回复).
v1.3.0 rc.3 默认改 event_send (保回复, 失表情包, 等 framework send_delayed API).
"""
from __future__ import annotations

import json
from pathlib import Path

_SCHEMA = Path(__file__).resolve().parent.parent / "_conf_schema.json"


def test_delivery_mode_default_is_event_send():
    """delivery_mode 默认应为 event_send (Bug-H 让 append 不可用)."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    seg_items = schema.get("segmented_reply", {}).get("items", {})
    dm = seg_items.get("delivery_mode", {})
    assert dm.get("default") == "event_send", (
        "delivery_mode 默认应为 event_send — Bug-H (framework) 让 append 不可用 (bot 不回复). "
        "等 AstrBot 修 Bug-H + 加 send_delayed API 后可改回 append."
    )
    assert "event_send" in dm.get("options", [])
    assert "append" in dm.get("options", [])  # append 保留 (接口, 待 framework 修)