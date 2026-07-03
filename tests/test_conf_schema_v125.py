"""Tests for _conf_schema.json v1.2.5 fields"""
import json
from pathlib import Path


def test_conf_schema_has_segmented_reply_block():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))
    assert "segmented_reply" in schema


def test_segmented_reply_has_v125_new_fields():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))
    seg = schema["segmented_reply"]["items"]
    assert "enable_deliberate_silence" in seg
    assert seg["enable_deliberate_silence"]["default"] == False
    assert "silent_threshold" in seg
    assert abs(seg["silent_threshold"]["default"] - 0.5) < 0.001
    assert "silent_cooldown_turns" in seg
    assert seg["silent_cooldown_turns"]["default"] == 2
    assert "max_consecutive_silence" in seg
    assert seg["max_consecutive_silence"]["default"] == 3


def test_segmented_reply_default_unchanged():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))
    items = schema["segmented_reply"]["items"]
    assert items["enable"]["default"] == False
    assert abs(items["default_max_part_chars"]["default"] - 48) < 0.001