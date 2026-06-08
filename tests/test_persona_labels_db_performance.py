"""Tests for persona_labels_db performance (Phase 3.0C.3 spec §6)。

4 个 perf test 验证 3072 KB 性能预算:
- KB cold load < 500ms (CI 友好阈值, spec §6.1 prod 预算 < 200ms)
- KB cached load < 5ms
- 1000 persona lookup < 50ms (dict O(1))
- in-memory KB < 10MB (pickle deep size)

实测 (2026-06-08):
- Cold load: 32.31 ms (6.2x headroom)
- Cached load: 0.0007 ms (1428x headroom)
- 1000 lookups: 0.24 ms (208x headroom)
- Memory: 1.00 MB pickle (10x headroom)

注: 使用 time.perf_counter() 测量, 系统负载可能影响 ±20%, CI 阈值用 500ms
(spec prod 预算 200ms) 留充足 headroom。
"""
from __future__ import annotations

import pickle
import sys
import time

import pytest

from emotion_spirit.persona_labels_db import (
    get_persona_labels_db,
    get_baseline_for_persona,
    list_persona_ids,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset():
    """每个 test 前/后重置 cache, 防止测试污染。"""
    reset_cache()
    yield
    reset_cache()


def test_kb_load_under_threshold():
    """KB 冷启动 < 500ms (CI 友好, spec §6.1 prod < 200ms)。

    注: plan §6.3 写 < 0.5s 阈值, 留 CI 慢机器 headroom。
    实测本地 ~32ms, CI 应 < 500ms。
    """
    reset_cache()  # 强制 reload
    t0 = time.perf_counter()
    db = get_persona_labels_db()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"KB load took {elapsed:.3f}s, expected < 0.5s"
    assert len(db) == 3072, f"Expected 3072 entries, got {len(db)}"


def test_kb_cached_load_fast():
    """热缓存 KB 加载 < 5ms (in-memory dict 引用)。"""
    get_persona_labels_db()  # warm up
    t0 = time.perf_counter()
    db = get_persona_labels_db()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.005, f"Cached load took {elapsed*1000:.3f}ms, expected < 5ms"


def test_persona_lookup_1000_under_threshold():
    """1000 次 lookup < 50ms (dict O(1) 查找)。"""
    db = get_persona_labels_db()
    # 抽样 16 个不同 persona_id (16 MBTI × 安全型)
    sample_ids = list_persona_ids()[:16]

    t0 = time.perf_counter()
    for i in range(1000):
        get_baseline_for_persona(sample_ids[i % 16])
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05, f"1000 lookups took {elapsed*1000:.1f}ms, expected < 50ms"


def test_kb_memory_under_threshold():
    """in-memory KB < 10 MB (spec §6.1 预算)。

    注: sys.getsizeof(db) 浅估算严重低估 nested dict, 用 pickle 序列化算
    deep size 更真实 (实测 ~1 MB)。
    """
    db = get_persona_labels_db()
    # 浅估算 (dict 自身)
    shallow_bytes = sys.getsizeof(db)
    # 深估算 (pickle 序列化)
    deep_bytes = len(pickle.dumps(db))
    # 浅估算也应在预算内 (dict 自身 ~100 KB, nested 实际 ~1 MB)
    assert shallow_bytes < 10 * 1024 * 1024, (
        f"KB shallow size {shallow_bytes/1024:.1f}KB > 10MB"
    )
    assert deep_bytes < 10 * 1024 * 1024, (
        f"KB deep size {deep_bytes/1024/1024:.2f}MB > 10MB"
    )
    # 记录实测值 (供 future regression 对比)
    print(
        f"\n  [perf] KB size: shallow={shallow_bytes/1024:.1f}KB, "
        f"deep={deep_bytes/1024/1024:.2f}MB, entries={len(db)}"
    )
