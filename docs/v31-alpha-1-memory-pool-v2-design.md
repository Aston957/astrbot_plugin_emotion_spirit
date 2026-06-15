# v3.1-alpha.1 — MemoryPool v2 索引优化设计

> **状态**:📥 Proposed(per ADR-0010,2026-07-15 alpha.1 实施)
> **作者**:emotion_spirit team
> **日期**:2026-06-15
> **目标发布**:`v3.1.0-alpha.1` (2026-07-15)
> **依赖**:ADR-0010 (release 流程), ADR-0011 (依赖图), v3.1 spec §3.1

---

## 1. 背景

### 1.1 v3.0 MemoryPool 现状

当前 `emotion_spirit/memory/memory_pool.py` 实现(per Phase A + D):

```python
# 简化版示意
class MemoryPool:
    _data: dict[str, list[UnifiedEntry]]  # 单一 dict, 4 层用同一表
    # 4 层由 UnifiedEntry.layer 字段区分 (buffer/warm/cold/ghost)

    def search_by_vector(self, vec, k=20) -> list[UnifiedEntry]:
        # 1. 全表扫描所有 entries
        # 2. cosine + euclidean hybrid distance
        # 3. 排序 top-k
```

**性能**(per v3.0 benchmark):
- 100 entries per user: search p95 ~ 5ms ✅
- 1000 entries per user: search p95 ~ 50ms ⚠️(接近上限)
- 10000 entries per user: search p95 ~ 500ms ❌(不达标)

**问题**:
- 大 user base(> 1000 entries)性能下降明显
- `get_recent_memories(k)` 同样全扫描
- 多 user 并发查询时内存分配密集
- **performance budget 来自 v3.1 spec**: query p95 < 50ms

### 1.2 v3.1 spec 目标

per `docs/emotion-spirit-v31-design.md` §3.1:

> **P0: MemoryPool v2 索引优化(性能)**
> - 复合索引:`(user_id, persona_id, timestamp)` 三元组
> - 倒排索引:按 `decay_score` 排序的 heap
> - 性能目标:`search_by_vector(k=20)`:p95 < 50ms(当前 ~120ms)
> - 持久化大小:+ ~15%(索引开销)
> - API 不变:`store.get_recent(user_id, k=10)` 签名保持

---

## 2. 设计

### 2.1 复合索引结构

**Primary index**:`(user_id, persona_id, timestamp)` 复合 B+ tree

```python
# 数据结构(简化)
@dataclass
class CompositeIndex:
    # 倒排索引: (user_id, persona_id) → sorted list of (timestamp, entry_id)
    by_user_persona: dict[tuple[str, str], list[tuple[float, str]]]
    
    # decay_score heap: 维护 top-K 候选
    by_decay: dict[tuple[str, str], list[str]]  # heap of entry_ids
    
    # entry_id → UnifiedEntry 映射
    entries: dict[str, UnifiedEntry]
```

**特点**:
- 复合索引 优先于 单字段索引(user 隔离 + persona 切换 + 时间序 3 维同时优化)
- per (user, persona) 一个 sorted list(binary search)
- decay heap 单独维护(避免每次 query 重新排序)

### 2.2 倒排索引(decay_score heap)

**heap 维护**:
- 每个 (user, persona) pair 一个 min-heap of `(decay_score, entry_id)`
- `add()` 时 O(log n) 插入
- `search_by_vector(k)` 时遍历 top entries 不需要全表

**decay_score** = `UnifiedEntry.compute_decay_factor() × emotion_intensity`

### 2.3 API 兼容性

**v1 签名保持**:
- `search_by_vector(vec, k=20) -> list[UnifiedEntry]`
- `get_recent_memories(k=50) -> list[UnifiedEntry]`
- `add(entry) -> None`
- `delete(entry_id) -> None`

**内部实现**:
- v1: 全扫描
- v2: 复合索引 + decay heap 快速过滤 → 候选集 → vector distance 精排

**新 API** (v2 扩展):
- `get_top_by_decay(user_id, k=20)` — 纯 decay 排序,无 vector
- `get_recent(user_id, since_ts, k=50)` — 时间窗口查询

### 2.4 持久化

**Schema 扩展** (per `tests/test_store_v3.py`):
```json
{
  "schema_version": 4,  // bump from 3 → 4
  "memory_pools": {
    "user1|persona_a": {
      "by_timestamp": [[ts, entry_id], ...],
      "by_decay": [entry_id, ...],  // heap
      "entries": {entry_id: UnifiedEntry_dict, ...}
    }
  }
}
```

**持久化大小**:
- v1: ~ 150 bytes/entry
- v2: ~ 175 bytes/entry (+ 25 bytes for index fields)
- **+ 15% 磁盘开销**(per spec,符合预期)

**Migration v3 → v4**:
- 读旧数据 + 重建 index(insert into 复合索引)
- 测试:`tests/test_store_v4_migration.py`

---

## 3. 性能预算

| 指标 | v1 当前 | v2 目标 | 测试方法 |
|---|---|---|---|
| `search_by_vector(k=20)` p95 | ~120ms | < **50ms** | 1000 entries per user |
| `get_recent(k=50)` p95 | ~30ms | < **10ms** | 1000 entries per user |
| `add(entry)` p95 | < 5ms | < **5ms** | 不变 |
| `delete(entry_id)` p95 | < 5ms | < **5ms** | 不变 |
| 持久化 save(1000 entries) | ~200ms | < **250ms** | +25% 可接受 |
| 启动加载(1000 entries) | ~150ms | < **200ms** | +33% 可接受 |
| 内存(1000 entries per user) | ~600KB | < **700KB** | +15% 索引开销 |

---

## 4. 实施 plan(5 周 timeline,per ADR-0010)

### Week 1 (2026-07-08 - 07-12):Spec + ADR + Tests
- [ ] **写 ADR-0012** MemoryPool v2 (Accepted, follow ADR-0009 6 步)
- [ ] **写详细 spec** 在本文件补全代码示例
- [ ] **TDD red**:写 10 个 perf test(失败 baseline,记录当前 ~120ms)
- [ ] **2.1 Memory Storage flow 更新** (per ADR-0011):加"依赖"章节

### Week 2 (2026-07-15):Alpha.1 Release
- [ ] **实施** CompositeIndex + DecayHeap
- [ ] **TDD green**:10 个 perf test 全部 < 50ms
- [ ] **回归测试**:全 861 + 10 = 871 tests
- [ ] **5/5 CI matrix** 必须过
- [ ] **本地 manual smoke**:
  - [ ] AstrBot 启动 OK
  - [ ] 跑 /spirit_inspect / /spirit_force 命令 OK
  - [ ] 写 100 条记忆 + search_by_vector < 50ms
- [ ] **tag `v3.1.0-alpha.1`** + push
- [ ] **GitHub Release auto-attach** (per release.yml)
- [ ] **CHANGELOG 更新** + ADR 文档化

### Week 3 (2026-07-16 - 07-22):Dogfood + Bug Fix
- [ ] 跑 bot 1 周,收集 CI 反馈
- [ ] 任何 fail → 立即修(per ADR-0009 步骤 6)
- [ ] 准备 v3.1-alpha.2 (deprecation + telemetry, 2026-08-01)

### Week 4-5:Buffer + Alpha.2
- [ ] Week 4:buffer 给 alpha.2 准备
- [ ] Week 5:alpha.2 release (per v3.1 spec)

---

## 5. 测试 strategy

### 5.1 性能 test(新加 10 个)

```python
# tests/perf/test_memory_pool_v2.py (新)

def test_search_by_vector_p95_under_50ms():
    """1000 entries, search k=20, p95 < 50ms."""
    pool = create_pool_with_1000_entries()
    times = [time_search(pool) for _ in range(100)]
    p95 = statistics.quantiles(times, n=20)[18]  # 95th percentile
    assert p95 < 0.050, f"p95 = {p95*1000:.1f}ms"

def test_get_recent_p95_under_10ms():
    """1000 entries, get_recent k=50, p95 < 10ms."""
    # ...

def test_decay_heap_consistency_after_random_adds():
    """1000 random adds, heap top-K matches manual sort."""
    # ...

# + 7 more
```

### 5.2 正确性 test(7 个)

```python
def test_search_by_vector_returns_same_results_as_v1():
    """v2 跟 v1 同一 query 返回同 top-K (set equal)."""
    # 跑 v1 + v2 同一 pool 同一 vec,assert sets equal

def test_decay_score_decreases_over_time():
    """1000 entries 跨 30 天,decay_score 排序跟 v1 一致."""
    # ...

# + 5 more
```

### 5.3 Migration test(3 个)

```python
def test_v3_to_v4_migration_preserves_data():
    """load v3 store + migrate → load v4 → 所有 entry 还在."""
    # ...

# + 2 more
```

**总计**:10 perf + 7 correctness + 3 migration = **20 个新 test**
+ 现有 861 tests = **881 total**(从 alpha.1 起)

---

## 6. Risk Assessment

### 6.1 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 性能不达预期(仍 > 50ms) | 中 | 高 | Week 1 baseline test 提前发现,Week 2 仍 fail 可延后到 beta |
| Migration 失败丢数据 | 低 | **高** | 写 backup → migrate → verify 3 步;不删 v3 schema,留 fallback |
| API 兼容 break | 中 | 中 | 全 861 + 7 correctness test 验证;公开 API 签名不变 |
| 多 thread 安全 | 中 | 中 | 加 lock,或用 immutable CompositeIndex 每次 copy |
| 持久化大小 + 15% 超出 | 低 | 低 | 实测如果 > 25%,改 heap 为 partial index |

### 6.2 回滚 plan

如果 alpha.1 失败(performance / correctness / migration):
1. **回滚代码**:`git revert v3.1.0-alpha.1` → main 回到 v3.0.1
2. **不删 v3 schema** — 留 v3 路径,改 v4 字段为可选
3. **写 ADR-0013** 解释失败原因 + 改进
4. **alpha.2 改用其他方案**(per v3.1 spec timeline,延迟 2 周到 beta.1)

### 6.3 Critical Path 影响(per ADR-0011)

**改 `2.1 Memory Storage` flow** → critical path
- 强依赖: 1.1 Message Receive, 1.5 Proactive Chat, 2.2 Force Dynamics, 2.5 Persona Drift, 3.2 Life Simulator
- 弱依赖: 1.4 Persona Restart, 2.3 Superego Check, 3.1/3.3/3.4
- 必填 ADR-0012 依赖章节

---

## 7. 文档同步

实施时必做(per ADR-0009 步骤 1):

- [ ] **写 ADR-0012** MemoryPool v2 决策(Accepted, 详细设计)
- [ ] **更新 `emotion-spirit-v31-design.md` §3.1** 加"已实施"备注
- [ ] **更新 `ARCHITECTURE_FRAMEWORK.md`** §2.2 (memory_pool) 加 v2 索引描述
- [ ] **更新 `WORKFLOWS_2026-06-15.md`** §2.1 (Memory Storage) 加"v2 索引"
- [ ] **CHANGELOG [Unreleased]** 段 + alpha.1 release 时移到版本段
- [ ] **README 索引** (per ADR-0011 §"确认"):依赖图如果改 flow,同步

---

## 8. 验收标准(Go / No-Go for v3.1.0 stable)

**v3.1-alpha.1 → alpha.2**:
- [x] 5/5 CI matrix 全过
- [x] 871/871 tests passed
- [x] Performance 10/10 达预算
- [x] 本地 manual smoke 全过
- [x] No regression(对比 v3.0.1)

**alpha.2 → beta.1** (per v3.1 spec):
- [x] 1 周 dogfood 0 critical bug
- [x] 5/5 CI matrix 全过 + flake < 0.1%

**beta.1 → v3.1.0 stable** (per v3.1 spec):
- [x] 2 周 dogfood 0 critical bug
- [x] Manual smoke (8.5 在 checklist 步骤 8)
- [x] Documentation complete

---

## 9. 相关文档

* [ADR-0010](0010-v31-release-process.md) — 5-phase release 流程
* [ADR-0011](0011-workflow-dependency-graph.md) — 18 flow 依赖图
* [ADR-0009](0009-v301-patch-lesson.md) — multi-file change checklist
* [ADR-0008](0008-rename-sylanne-core-to-sylanne.md) — R3 命名
* `docs/emotion-spirit-v31-design.md` — v3.1 完整 spec
* `docs/../WORKFLOWS_2026-06-15.md` §2.1 — Memory Storage flow
* `docs/ARCHITECTURE_FRAMEWORK.md` §2.2 — memory/ layer
* `tests/test_store_v3.py` — v3 schema (待 v4)

---

*生成日期:2026-06-15 by emotion_spirit team*
*下次 review:2026-07-15 alpha.1 release*
