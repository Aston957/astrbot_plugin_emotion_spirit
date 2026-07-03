"""§1.6 规则 3: agents/ 内无 EventBus / AgentEvent / emit / subscribe (v1.2.7 删后守护)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / "emotion_spirit" / "agents"


def test_no_event_bus_in_agents():
    """agents/ 目录禁止 EventBus 类和 AgentEvent 基类."""
    for py_file in AGENTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        assert "class EventBus" not in source, f"{py_file.name} 含 EventBus 类"
        assert "class AgentEvent" not in source, f"{py_file.name} 含 AgentEvent 类"


def test_no_emit_in_agents():
    """agent 文件不应有 emit 方法或 self.emit 调用."""
    for py_file in AGENTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        assert "def emit" not in source, f"{py_file.name} 含 emit 方法"
        assert "self.emit(" not in source, f"{py_file.name} 含 self.emit 调用"


def test_no_subscribe_in_agents():
    """agent 文件不应有 subscribe 方法或调用."""
    for py_file in AGENTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        assert "def subscribe" not in source, f"{py_file.name} 含 subscribe 方法"
        assert ".subscribe(" not in source, f"{py_file.name} 含 subscribe 调用"


def test_no_event_bus_module():
    """event_bus.py 文件应已删除."""
    event_bus_path = AGENTS_DIR / "event_bus.py"
    assert not event_bus_path.exists(), "event_bus.py 应已删除"


def test_base_no_bus_param():
    """CognitiveAgent.__init__ 不应有 bus 参数."""
    base_path = AGENTS_DIR / "base.py"
    source = base_path.read_text(encoding="utf-8")
    assert "def __init__(self, bus)" not in source, "CognitiveAgent.__init__ 应无 bus 参数"