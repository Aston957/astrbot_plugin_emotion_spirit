# ADR-0011: workflow 依赖图 — 18 flow 治理视图

* Status: ✅ Accepted
* Date: 2026-06-15
* Deciders: emotion_spirit team
* Follow-up to: [ADR-0001](0001-four-layer-directory.md)(层次视图), [ADR-0010](0010-v31-release-process.md)(release 流程)
* Related: [`docs/../WORKFLOWS_2026-06-15.md`](../WORKFLOWS_2026-06-15.md)(18 flow 详细)

## Context and Problem Statement

emotion_spirit 项目已有 3 个互补的架构视图:
- **层次视图** (`ARCHITECTURE_FRAMEWORK.md`):6 层 + 71 modules,看代码组织
- **历史视图** (`DEVELOPMENT_HISTORY.md`):Phase + 版本时间线,看演变
- **决策视图** (`docs/adr/`):10 份 ADR,看为什么

但**功能运行视图**缺失。WORKFLOWS_2026-06-15.md 列出 18 flow 但**没正式记录 flow 之间的依赖关系**:
- 哪些 flow 强依赖其他 flow
- 哪些 flow 可独立替换
- 哪些 flow 是 critical path
- 哪些 flow 是"装饰性"功能(可失败)

**问题**:
- 加新功能时不知道"会 break 哪些现有 flow"
- 重构某 flow 时不知道"会触发哪些下游"
- 评估 release 风险时没有"flow 风险图"
- 0 外部用户 + 1 人维护 = 错误"很难被早期发现"

## Decision Drivers

* **预防**> 检测 — 文档化依赖能在设计阶段发现 ripple effects
* **可演进** — flow 之间应该有清晰边界,允许独立替换
* **可读** — 18 flow 的依赖图应该 1-2 张图能讲清楚
* **0 外部用户窗口** — 现在 0 用户,容易 experiment 视图

## Considered Options

* **A**: 无依赖图,继续用 WORKFLOWS 文档
  * 优点:0 文档
  * 缺点:加功能时靠 grep + 直觉,易漏

* **B**: 引入 flow 依赖图作为强制 ADR 内容(选定)
  * 优点:每次新增/修改 flow 必更依赖图
  * 缺点:文档维护成本

* **C**: 工具生成依赖图(从 import + 函数名静态分析)
  * 优点:自动
  * 缺点:复杂 / 过工程

* **D**: 仅在 ARCHITECTURE_FRAMEWORK 提一句
  * 优点:集中
  * 缺点:被埋没

## Decision Outcome

Chosen option: **B(引入 flow 依赖图作为强制 ADR 内容)**,因为:

1. **跟现有 ADR 仓库策略一致** — 每次重要变更先 ADR
2. **18 flow 当前不算多** — 依赖图能 1-2 张图讲清楚
3. **可演进** — 每次 v3.x release 复盘依赖图
4. **0 外部用户 = 0 breaking 代价** = 现在是最适合建立的时机

## Flow 依赖图(18 flow 当前状态)

```
[外部触发]
  用户消息 ─────────────► [1.1 Message Receive] ──► LLM call ──► bot reply
  用户命令 ─────────────► [1.2 Command]
  /setup_init ───────────► [1.3 Persona Init]
  AstrBot 启动 ──────────► [1.4 Persona Restart]
  外部调度(proactive) ──► [1.5 Proactive Chat]
                                   │
                                   ▼
                          [2.1 Memory Storage] ◄──── [4.1 on_llm_response]
                                   │                       │
                          ┌────────┼────────┐              │
                          ▼        ▼        ▼              │
                    [2.2 Force] [2.3 Super] [2.5 Drift]     │
                     Dynamics    Check                       │
                          │        │        │              │
                          └────────┼────────┘              │
                                   ▼                       │
                            [1.1 prompt 注入] ◄─────────────┘

[后台]
  定时 ──► [3.1 Diary Writer] ──► [2.1 Memory]
  定时 ──► [3.2 Life Simulator] ──► [2.1 Memory]
  消息长度 ──► [3.3 Realtime Dispatch] ──► 3.4 读 rhythm
  每消息 ──► [3.4 Rhythm Learner]
  睡眠 ──► [3.5 Dream Generator] (planned)

[Admin]
  每 bot 回复 ──► [4.1 on_llm_response] ──► [2.1 Memory]
  启动 ──► [4.2 Migration] ──► [1.4 Persona Restart]
  启动 ──► [4.3 Telemetry] (planned, opt-in)
```

## 关键依赖类别(governance)

每对依赖有不同"治理强度":

| 依赖类型 | 例子 | 治理 |
|---|---|---|
| **强同步** | 1.1 → 2.1(每次消息都写) | 任何改动需 regression test |
| **异步可选** | 1.5 → 2.4(BotDecision 外部) | 改动可不影响 1.1,需测 2.4 stub |
| **装饰性** | 3.1 / 3.5(可失败不影响主流程) | 改动可不测主流程 |
| **Admin 一次性** | 4.2 / 4.3(启动跑一次) | 改动需测启动流程 |

## Critical Path(用户最关心)

**日常对话** = 1.1 → 2.1 → 2.2 / 2.3 → 1.1 reply → 4.1 → 2.1

任何这个路径上的 flow 改动 = **最高风险**,必须:
1. 跑全 861 tests
2. 5/5 CI matrix
3. local manual smoke test
4. ADR 描述(per ADR-0009)

## Flow 替换 / 退役规则

替换某 flow 时(比如 v3.1 的 3.5 Dream Generator 实现细节改变):
- **保留 API 表面**(per `output.public_api`)
- **deprecation warning** 1 个 minor 版本(per v3.1 spec §API deprecation)
- **写 ADR** 描述替换 + 兼容性承诺

退役某 flow 时(比如某 decorative 功能):
- **deprecate flag** 1 个 minor 版本
- **写 ADR** 描述退役 + 替代方案
- **从依赖图删除**(commit 时同步)

## 每次新 flow 必填的 ADR 章节

按本 ADR 规范,新 flow 的 ADR 必须包含:

```markdown
## 触发
- 何时跑(具体函数 / 装饰器 / 条件)
- 谁触发(用户 / 定时 / 外部)

## 输入 → 输出
- 输入类型(从哪读)
- 输出类型(写到哪)
- 失败行为(降级 / 跳过 / 报错)

## 依赖
- 强依赖:列具体 flow 名
- 弱依赖:列具体 flow 名
- 不依赖(可独立)

## Critical Path 影响
- 主路径(true / false)
- 装饰性(true / false)
- 失败影响(用户感知 / 静默)
```

## Confirmation

* 本 ADR + 依赖图作为未来 flow 设计的**必填章节**
* v3.1 release 时复盘 — 看依赖图是否还反映真实状态
* v3.2 release 时如果 flow 数 > 30,考虑拆出独立 `docs/FLOWS_INDEX.md`

## Consequences

### Positive

* **预防 ripple effect** — 改动某 flow 前看依赖图,提前评估风险
* **Onboarding 友好** — 新人 1 张图了解项目运行时序
* **release 风险评估** — 5-phase release 时(critical path 在 alpha 就过,decorative 在 beta)
* **可演进** — flow 增减时同步图,保持真实

### Negative

* **文档维护成本** — 每次新 flow 必更图
* **图可能过时** — 如果忘记更,误导比没有更糟
* **复杂度增长** — v3.2+ flow 数 > 30 时,1 张图不够

### Confirmation

* v3.1-alpha.1 (2026-07-15) 首次按此规范(新 flow "MemoryPool v2 索引"必填依赖章节)
* v3.1.0 stable (2026-09-01) 时复盘依赖图

## Why / How to apply

**Why**: WORKFLOWS 2026-06-15 写了 18 flow 但没记录依赖关系,加新 flow 时需 grep + 直觉,易漏。**依赖图是"读 WORKFLOWS 时的"先看哪"指南"**。

**How to apply**:
- 任何新 flow 必填"依赖"章节(per 本 ADR §"每次新 flow 必填")
- 任何 flow 改动 commit 必在 message 引用"流图受影响"
- 每月 (或每次 release) 复盘依赖图,删/加/改

## Real-world Application

**v3.1-alpha.1 MemoryPool v2 索引** (2026-07-15 计划):
- 改 `2.1 Memory Storage` flow 内部(per v3.1 spec §3.1)
- 依赖图影响: 1.1 (read), 1.5 (read), 2.2 (read), 2.5 (read) — 强依赖,需 regression
- 依赖图不动: 3.1, 3.2, 3.3, 3.4, 3.5 — 弱依赖,只需 smoke test
- ADR-0012 必含"依赖"章节

**v3.1-alpha.2 API deprecation** (2026-08-01 计划):
- 新增 deprecation warning 装饰器
- 影响 flow: 1.2 Command, 2.x Internal(任何用户调 public API 处)
- 必填 deprecation 政策(per v3.1 spec §3.2)

## Related

* [ADR-0001](0001-four-layer-directory.md) — 4 层目录(代码组织视图)
* [ADR-0009](0009-v301-patch-lesson.md) — multi-file change checklist
* [ADR-0010](0010-v31-release-process.md) — 5-phase release 流程
* `docs/ARCHITECTURE_FRAMEWORK.md` — 层次视图(代码)
* `docs/DEVELOPMENT_HISTORY.md` — 历史视图(时间)
* `docs/../WORKFLOWS_2026-06-15.md` — 18 flow 详细列表
* `docs/reports/2026-06-15-session-summary.md` — 2026-06-15 session 总结
