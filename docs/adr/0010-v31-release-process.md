# ADR-0010: v3.1 release 流程 — 5-phase alpha/beta/stable 标准化

* Status: ✅ Accepted
* Date: 2026-06-15
* Deciders: emotion_spirit team
* Follow-up to: [ADR-0009](0009-v301-patch-lesson.md)(multi-file change checklist)
* Supersedes: (none)

## Context and Problem Statement

emotion_spirit 历史上的 release 流程是"**ad-hoc**":
- v2.0.0v1 (2026-06-09) → v2.0.0v2 (2026-06-10):在 1 天内合并,无 alpha/beta 阶段
- v3.0.0 (2026-06-12):9 阶段合并,无 alpha/beta
- v3.0.1 (2026-06-13):**直接 commit 到 main**,导致 4 个后续 commit 全 fail(per [[emotion-spirit-v301-astrbot-v425-patch]])

**当前问题**:
- **没有 alpha 阶段** → 大改动(性能优化、breaking change)直接进 main
- **没有 beta 阶段** → bug 暴露晚(merge 后才发现)
- **没有 patch 流程** → v3.0.1 跟 v3.0 几乎同时 push,无法回滚
- **没有 release manager 角色** → 谁负责发版模糊
- **没有 release 模板** → 每次 release 重新发明轮子

**v3.1 计划** (per `docs/emotion-spirit-v31-design.md`):
- 2026-07-15:alpha.1 (MemoryPool v2 索引优化)
- 2026-08-01:alpha.2 (Deprecation + Telemetry)
- 2026-08-15:beta.1 (Phase 5+ Dream Generator)
- 2026-09-01:stable v3.1.0
- 2026-10-15:v3.1.1 (E2E + PyPI)

**5 个里程碑**,每个 2 周左右,但**没有标准化流程**。如果不写 ADR,每个里程碑可能再次 ad-hoc 走老路(直接 push main)。

## Decision Drivers

* **预防 v3.0.1 类事故** — 在 alpha/beta 阶段就发现 + 修
* **可回滚** — 每个 phase 都是独立 tag,失败能 revert
* **节奏感** — 团队(1 人)能按 calendar 推进,不被 release 流程拖垮
* **轻量级** — 不引入繁重 release management(branching 模型 / MR / 审批流程)
* **可测试** — alpha/beta 阶段有明确的"go / no-go"判据

## Considered Options

* **A**: 直接 main + ad-hoc patch(沿用 v3.0 模式)
  * 优点:简单
  * 缺点:重复 v3.0.1 失败模式

* **B**: 严格 GitFlow(master / develop / feature/* / release/* / hotfix/*)
  * 优点:工业标准
  * 缺点:1 人项目过重,branch 切换 cognitive overhead 大

* **C**: 5-phase alpha/beta/stable on main branch(选定)
  * 优点:轻量 + 明确 + 可回滚
  * 缺点:不是 industry standard(对 future contributor 需 onboarding)

* **D**: Feature flags 替代 release branch
  * 优点:无 branch 切换
  * 缺点:需要 runtime 切换机制(emotion_spirit 没这基础)

## Decision Outcome

Chosen option: **C(5-phase alpha/beta/stable on main branch)**,因为:

1. **跟 v3.1 spec 已经写的 5 里程碑对齐** — alpha.1 / alpha.2 / beta.1 / stable / v3.1.1
2. **1 人项目友好** — 不需要多 branch 维护
3. **每个 phase = 1 个 git tag** — 可回滚 / 可比较
4. **main 始终可发布** — alpha/beta 在 main 上,但有 tag 标识"未 stable"

### Release 流程

```
[main] ──┬─ (开发) ──► alpha.1 (tag) ──► alpha.2 (tag) ──► beta.1 (tag) ──► v3.1.0 (tag) ──► v3.1.1 (tag)
         │      │
         │      └─ 每次 commit: 跑 ADR-0009 6 步 checklist
         │
         └─ 任何 regression → 回滚到上一 tag + 在 [Unreleased] 段记
```

### Phase 详细规则

#### alpha.1 / alpha.2(每 2-4 周)

- **目的**:大改动首次集成,内部测试,允许有 minor bug
- **CI 要求**:5/5 matrix combo 通过
- **tag 格式**:`v3.1.0-alpha.1` / `v3.1.0-alpha.2`
- **可发布?**:❌ 不推荐生产用(per [v3.1 spec §兼容性承诺](emotion-spirit-v31-design.md))
- **回滚决策**:任何 1 个 CI fail → 立即 revert + 在 [Unreleased] 段 +1 修复 commit

#### beta.1(2-4 周,2026-08-15)

- **目的**:功能完成,bug 收敛,接近 stable
- **CI 要求**:5/5 通过 + 5/5 单独跑通过(无 flake)
- **tag 格式**:`v3.1.0-beta.1`
- **可发布?**:🟡 早期采用者(开发者自己)
- **特殊**:首次对外宣传("v3.1 beta 已出,2 周内 stable")

#### stable v3.1.0(2026-09-01)

- **目的**:生产就绪
- **CI 要求**:5/5 通过 + manual smoke test(AstrBot 启动 + 跑命令)
- **tag 格式**:`v3.1.0`
- **可发布?**:✅
- **特殊**:GitHub Release 自动 attach(已有 release.yml)
- **触发条件**:
  - 5 天内无 critical bug
  - 文档(v3.1 release notes)就位
  - 至少 1 个真用户用 beta 1 周无问题

#### patch v3.1.x(每发现 critical bug 触发)

- **目的**:critical bug 修复
- **CI 要求**:5/5 通过 + regression test 必须
- **tag 格式**:`v3.1.1` / `v3.1.2`
- **流程**:
  1. 写 regression test(必须 fail without fix)
  2. 写 fix
  3. 跑全 suite
  4. ADR 记录(per ADR-0009 教训,不能 silent patch)
  5. tag + push

### 每次 release 的强制 checklist(扩展 ADR-0009)

```
[ ] 1. 写 ADR 描述本次 release 范围 (per ADR-0009 步骤 1)
[ ] 2. 版本号 bump 同步 6 个位置 (per ADR-0009 步骤 2)
       - _version.py, sylanne/__init__.py, metadata.yaml
       - public_api_stable.md, CHANGELOG.md, README.md
       - test_version_* assert, test_public_api_md assert
[ ] 3. 跑全 suite + 5/5 单独跑(无 flake)
[ ] 4. pre-commit secret scan 通过
[ ] 5. 写 CHANGELOG [Unreleased] → 移到版本段 + 写 release notes
[ ] 6. push + 监控 CI 5 分钟内无 fail
[ ] 7. tag + GitHub Release auto-attach (release.yml)
[ ] 8. (stable + patch 额外) manual smoke test:
       - AstrBot 启动 OK
       - 跑 /spirit_inspect 命令 OK
       - 数据持久化 OK(关掉 + 重启)
[ ] 9. (v3.1.0 stable 额外) 跟 beta 期间用户确认无 regression
[ ] 10. (v3.1.1+ patch 额外) regression test 必须 + ADR
```

## Specific v3.1 Timeline(per v3.1 spec)

| Date | Tag | 内容 | 状态 |
|---|---|---|---|
| 2026-07-15 | `v3.1.0-alpha.1` | MemoryPool v2 索引优化 | 📥 Planned |
| 2026-08-01 | `v3.1.0-alpha.2` | API deprecation policy + Telemetry opt-in | 📥 Planned |
| 2026-08-15 | `v3.1.0-beta.1` | Phase 5+ Dream Generator | 📥 Planned |
| 2026-09-01 | `v3.1.0` | stable | 📥 Planned |
| 2026-10-15 | `v3.1.1` | E2E + PyPI | 📥 Planned |

每个 tag 之间 2-4 周,**有充足时间在 main 上 dogfood + 修 bug**。

## Consequences

### Positive

* **预防 v3.0.1 类事故** — alpha/beta 阶段有 buffer
* **节奏感** — calendar 化的 release 让 1 人项目能推进
* **可回滚** — 每个 tag 独立,任何 phase 失败能 revert 到上一 tag
* **文档化强制** — 每次 release 必须写 ADR,防 silent patch(per [[emotion-spirit-secret-leak]])
* **CI 验证** — 5/5 matrix 强制,防 Linux/Win 差异

### Negative

* **Calendar 压力** — 错过日期会拖延,需要 owner 跟进
* **不是 industry standard** — 新 contributor 可能不熟悉 alpha/beta on main
* **alpha/beta 期间不推荐生产用** — 0 外部用户无所谓,但未来 contributor 需知道
* **tag 增多** — 5 个 tag 比 1 个 stable 多 5×

### Confirmation

* v3.1-alpha.1 (2026-07-15) 是**首次验证** 流程
* v3.1.0 stable (2026-09-01) 是**首次**完整 5-phase
* v3.2 release 时**复盘本 ADR**,看哪些 step 需调整

## Real-world Application

**v3.0 / v3.0.1 缺此流程的代价**(per [[emotion-spirit-session-2026-06-15]]):
- v3.0.1 直接 push main → 4 个后续 commit fail
- 用户用了 3 天才意识到事故
- 修复 4 个 test + 1 个 flake,共 ~6 行代码改动
- **没有 alpha 阶段做内部发现** — Windows 本地测过 ≠ Linux CI 测过

**v3.1 按本 ADR 跑后的预期效果**:
- MemoryPool v2 在 alpha.1 阶段被发现
- Deprecation 在 alpha.2 阶段被外部模拟
- Dream Generator 在 beta.1 阶段被 dogfood
- v3.1.0 stable 应该是"已经稳定过"的代码,不是"刚发布的代码"

## Why / How to apply

**Why**: v3.0.1 事故 + 0 外部用户窗口 = **现在是最适合建立 release 流程的时机**。等到 100 个用户时再补,代价 100×。

**How to apply**:
- 任何 v3.1.x release → 跑本文 10 步 checklist
- 任何未来 release(v3.2 / v3.3 / v4.0)→ 复盘本 ADR,有调整写新 ADR
- alpha/beta 期间在 README 加 "⚠️ alpha/beta, not for production" 警告
- tag 推送用 `git tag -a v3.1.0-alpha.1 -m "..."` 形式,带 release notes

## Related

* [ADR-0009](0009-v301-patch-lesson.md) — multi-file change checklist(本 ADR 的依据)
* [ADR-0007](0007-pre-commit-secret-scan.md) — secret scan 防御
* [ADR-0001](0001-four-layer-directory.md) — 4 层目录(决定 release 影响范围)
* `docs/emotion-spirit-v31-design.md` — v3.1 完整 spec(本 ADR 的 timeline 来源)
* `docs/reports/2026-06-15-session-summary.md` — 2026-06-14/15 session 总结(v3.1 起点)
* [[emotion-spirit-v301-astrbot-v425-patch]] — v3.0.1 事故复盘(本 ADR 教训来源)
* [[emotion-spirit-secret-leak]] — 历史 secret 闭环(强调"必须 ADR"原则)
