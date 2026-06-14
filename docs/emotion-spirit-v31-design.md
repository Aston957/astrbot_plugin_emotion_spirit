# emotion_spirit v3.1+ 公开 spec

> 状态:**📥 Proposed**(2026-06-14)
> 目标发布:v3.1.0
> 计划时间:Q3 2026(3-4 个月后)

## 1. 背景

emotion_spirit 当前稳定版 v3.0.1(2026-06-13)。v3.0 期间完成 9 阶段合并(Phase A-I),
产出 104 模块 + 856 tests。本 spec 描述 v3.0 → v3.1 方向。

**v3.0 推后清单**(从 9 阶段合并中 deferred):
- Phase 5+ 实施(Dream Generator 已有 design,待实施)
- MemoryPool 性能优化(flat 4-tier 索引待补)
- Telemetry / 真实使用信号(无)
- API 演化政策(无 deprecation 机制)
- v3.0.1 patch 临时兼容(AstrBot v4.25 修了 10 bug,但 E2E 覆盖待补)

## 2. v3.1 Goals

| 优先级 | 目标 | 价值 |
|--------|------|------|
| 🥇 P0 | MemoryPool v2 索引优化 | 性能,query p95 < 50ms |
| 🥇 P0 | API deprecation policy | 可维护性,提前 N+1 版本警告 |
| 🥈 P1 | Telemetry opt-in | 真实使用数据,反哺 Roadmap |
| 🥈 P1 | Phase 5+ Dream Generator 实施 | 新功能(已有 design) |
| 🥉 P2 | E2E + mutation testing | 测试可信度,防"100% pass 但漏 bug" |
| 🥉 P2 | PyPI 公开发布 | 突破"私仓 0 用户"瓶颈 |

## 3. 详细设计

### 3.1 MemoryPool v2(性能)

**现状**:v3.0 MemoryPool 是 flat 4-tier(`buffer / warm / cold / ghost`),按 `user_id` 索引。
**问题**:大用户量(>1000)时,`search_by_vector` 和 `get_recent_memories` 变慢。
**v3.1 改动**:
- 复合索引:`(user_id, persona_id, timestamp)` 三元组
- 倒排索引:按 `decay_score` 排序的 heap
- API 不变:`store.get_recent(user_id, k=10)` 签名保持

**性能目标**:
- `search_by_vector(k=20)`:p95 < 50ms(当前 ~120ms)
- `get_recent_memories(k=50)`:p95 < 30ms
- 持久化大小:+ ~15%(索引开销)

**测试**:现有 856 tests 不变,新增 ~10 性能基准测试(`tests/perf/test_memory_pool_v2.py`)。

### 3.2 API Deprecation Policy(可维护性)

**现状**:v2.0 → v3.0 有 breaking changes,但无 deprecation warning。
**v3.1 政策**:
- N+1 版本 deprecate:在 v3.1 标记 `@deprecated(since="3.1", remove_in="3.2")` 的 API,会在 v3.2 移除
- `@deprecated` 装饰器自动 warning(import 时 + 调用时各一次)
- `interfaces/` 模块的所有公开函数纳入治理范围
- 首次 deprecation 应用:1-2 个真要淘汰的 API(候选:`auto_pilot` 命令、`/spirit_relabel` 命令)

**测试**:deprecation 触发 warning 计数,2 版本后真正删除时跑全 suite 验证无 regression。

### 3.3 Telemetry Opt-in(真实使用)

**现状**:完全无 telemetry,不知道谁在用、用什么功能。
**v3.1 设计**:
- 配置项:`telemetry.enabled: false`(默认关)
- 上报内容(完全匿名):
  - emotion_spirit 版本(如 `3.1.0`)
  - Python 版本(如 `3.11.9`)
  - AstrBot 版本(如 `4.25.5`)
  - 平台(aiocqhttp / telegram / qq_official)
  - 启动时间(UTC ISO 8601)
- **不上报**:user_id、消息内容、persona 数据、任何 PII
- 上报方式:本地统计(写入 `data/telemetry.json`),不发外部服务器(v3.1 阶段;v3.2 考虑可选上报到中央)

**测试**:
- `telemetry.enabled: false` 时 0 上报
- `telemetry.enabled: true` 时写入 JSON 文件,可读可清
- 配置文件 schema 验证:`_conf_schema.json` 加 `telemetry` 段

**Opt-in 决策理由**:
- 默认关,避免隐私争议
- 收集的数据无法 reverse 出原始 user
- 数据存本地,用户可读可清,无暗箱

### 3.4 Phase 5+ Dream Generator(新功能)

**现状**:Design 写完(per [[dream-generator-design]] memory),实施待。
**v3.1 范围**:
- 2 种梦境模式:深度睡眠(慢节奏) + 睡眠剥夺(快节奏,带情绪加工)
- 13 维人格调制:梦境内容受当前 persona 维度影响
- 用户可配置:`dream.schedule: "22:00-06:00"`(睡眠窗口)
- 梦境产物 → MemoryPool(写入 `is_dream=True` 标记的记忆)

**依赖**:
- MemoryPool v2 索引必须先完成(梦境检索用)
- 持久化:`spirit_dreams.jsonl` 每行一条梦境记录

**测试**:~15 个新 test,覆盖梦境触发 / 内容生成 / 记忆写入 / 时间窗口。

### 3.5 E2E + Mutation Testing(测试可信度,降级为 P2)

**现状**:全 861 tests 是 unit + integration,缺 AstrBot 端到端。
**v3.1 范围**:
- E2E:用 `pytest-astropy` 风格或自写 mock,模拟 AstrBot 启动 + 消息触发命令
- Mutation:引入 `mutmut`,跑 mutation score,目标 > 80%
- 接入 CI:mutation score 作为额外 check

**ROI**:P2 优先级,可在 v3.2 推后。

### 3.6 PyPI 公开发布(突破私仓,降级为 P2)

**现状**:私仓,0 外部用户(per 评估报告 4/10 Usage)。
**v3.1 范围**:
- `pyproject.toml` 已有,补 publish workflow
- 提交到 `AstrBotDevs/AstrBot-Plugins` 官方列表
- release zip 自动发布到 GitHub Release(已有 R0)

**ROI**:高,但需要先有 telemetry 数据证明稳定性,故 P2。

## 4. Non-Goals(v3.1 不做)

- v4.0 重大架构重构(留 v3.2+)
- 多用户/多租户支持(emotion_spirit 仍是 per-user 隔离)
- Web UI(GUI 调参 v2.1 推后)
- monorepo 整合(emotion_spirit + proactive_chat 等)
- emotion_spirit v3.0.x 用户的强制升级路径

## 5. Timeline

| 里程碑 | 目标日期 | 备注 |
|--------|----------|------|
| v3.1 spec 公开 | 2026-06-14(本文档) | ✅ |
| v3.1-alpha.1 (MemoryPool v2) | 2026-07-15 | P0 第一个交付 |
| v3.1-alpha.2 (Deprecation + Telemetry) | 2026-08-01 | P0+P1 |
| v3.1-beta.1 (Phase 5+ Dream Generator) | 2026-08-15 | P1 |
| v3.1.0 stable | 2026-09-01 | 全 P0+P1 |
| v3.1.1 (E2E + PyPI) | 2026-10-15 | P2 后续 |

**注意**:日期是"目标"不是"承诺",可能因实际情况调整 ±2 周。

## 6. 兼容性承诺

| 维度 | v3.0.x → v3.1.0 |
|------|-----------------|
| 配置文件 | 100% 兼容(无 schema breaking) |
| 持久化数据 | 100% 可读,按需 auto-migrate(透明) |
| 公开 API(`interfaces/`) | 100% 保持,只新增不删除(deprecated API 走 N+1 路径) |
| 命令列表 | 100% 保持(只新增,deprecation 走 warning) |
| 第三方依赖 | 锁版本(`requirements.txt` 严格 `==`) |

**例外**:内部模块(非 `interfaces/`)可以有 refactor,因为它们不是公共 API。

## 7. 跟 v3.0 / Phase 5+ 的关系

**v3.0 已完成**:
- Phase A-I 9 阶段合并
- 856 tests + 5 namespace 隔离
- 4-layer 目录结构(per ADR-0001)
- SylannEngine 嵌入 + R3 重命名(per ADR-0003, 0008)

**v3.0 → v3.1 衔接**:
- v3.0.1 是 patch,只修 compat bug
- v3.0.2/3.0.3(若有)是 micro,只修 bug
- v3.1.0 是 minor,加新功能(本文档)

**Phase 5+**:
- 是 v3.1 的子项目(per §3.4)
- 不在 v3.2+ 重复

## 8. 决策与变更

**如何提出变更**:
1. 在 memory 写 `emotion-spirit-v31-decision-XXX.md`,描述变更 + 理由
2. 评审后写新 ADR(编号递增,见 `docs/adr/`)
3. 更新本文档相应章节

**Status 流转**:
- `📥 Proposed`(本文档当前)
- `🚧 In Progress`(实施中)
- `✅ Accepted`(v3.1.0 released 后)

## 9. 风险与备选

| 风险 | 概率 | 影响 | 备选 |
|------|------|------|------|
| MemoryPool v2 索引破坏持久化数据 | 低 | 高 | 详细 migration test + 双 schema 共存 |
| Telemetry 引发用户反感 | 中 | 中 | 默认关 + 详细 docs 说明 |
| Phase 5+ Dream Generator 跟 AstrBot 上游冲突 | 中 | 中 | 推迟到 v3.2,先做 MemoryPool v2 |
| v3.1 时间线超出 Q3 | 中 | 低 | 拆 v3.1.0 + v3.1.1 多次发布 |

## 10. 下一步

- [ ] Review 本文档
- [ ] 写 `emotion-spirit-v31-decision-001-memory-pool-v2.md`
- [ ] 写 `emotion-spirit-v31-decision-002-deprecation-policy.md`
- [ ] 写 `emotion-spirit-v31-decision-003-telemetry-design.md`
- [ ] 实施 v3.1-alpha.1

## Related

- [[emotion-spirit-ecosystem-eval-2026-06-13]] — R2 推荐
- [[dream-generator-design]] — Phase 5+ 设计
- [[emotion-spirit-direction]] — 4 层架构哲学
- [[emotion-spirit-v3-merger-plan]] — v3.0 9 阶段
- [[emotion-spirit-progress]] — v3.0.0 当前状态
- `docs/adr/0008-rename-sylanne-core-to-sylanne.md` — R3 已完成
