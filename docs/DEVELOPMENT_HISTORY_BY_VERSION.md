# emotion_spirit 插件开发全史 (版本视角)

> **从 v0.0 概念到 v3.0.1 + R1-R3 治理完善的完整时间线**
> 生成日期:2026-06-14

> **📜 视角说明**:这是**版本视角**的完整开发史(按 v1.0 → v1.7 → v2.0 → v3.0.1 排列)。
> 如果你想看**Phase 视角**(按 Phase 0/0.5 → 1.5/2/2.5/3/4/A-I/5+ 排列),见:
> → [`DEVELOPMENT_HISTORY.md`](DEVELOPMENT_HISTORY.md)(**主文档,17 章节,Phase 视角**)
>
> **两个版本都保留**:因为不同场景适合不同视角——
> - **版本视角**(本文件)适合看"每个 release 改了什么 bug"
> - **Phase 视角**(主文档)适合看"项目为什么这么分阶段"
>
> 两个版本内容上互相覆盖,主要差异在组织方式。

---

## 0. 起源与定位 (2026 早期)

### 0.1 动机

emotion_spirit 诞生于一个明确的问题:**AstrBot 生态的情感计算插件都太"反应式"**。

市面上的 LLM bot(包括早期 AstrBot 默认)都是"用户说什么,bot 立刻回应什么"的模式。bot 没有"自己今天过得怎么样"的连续人格,没有"对用户的长期记忆演化",更没有"自己内心的挣扎和成长"。

设计者希望构建一个**有连续人格的 LLM bot**:
- bot 知道自己是谁(11 维人格,5 轴 MBTI 标签)
- bot 记得跟每个用户发生过什么(per-user 记忆)
- bot 有自己的内心世界(力学平衡 / 梦境 / 价值观压力)
- bot 在长期演化中**会变**,不只是响应

### 0.2 哲学

- **3 力决策**:自然 / 社会 / 个体,决策 = 力竭后的落点(per [[three-force-framework]])
- **人格层次**:1 内核 + 2 关系 + 3 内在生命(v2 加 4 社交智能)
- **4 层架构**:core / bridge / extensions / interfaces(per ADR-0001)
- **0 第三方依赖**:只依赖 AstrBot 自身,其他全是 in-house
- **per-session 隔离**:bot 不会"知道"用户之间的关系(per [[sylannengine-architecture]])

### 0.3 上下游

```
AstrBot (D:\astrbot\)
└── emotion_spirit v3.0.1 (active, embeds sylanne 46 modules)
    ├── SylannEngine 嵌入 (per ADR-0003 / 0008)
    │   (原 SylannEngine 上游 Ayleovelle 仓库)
    └── 姐妹插件 (历史依赖, 现已独立)
```

---

## 1. v1.0 - v1.7 演化期 (2026-Q1)

### v1.0 (2026 早期) — 第一版"能跑"

**目标**:把"有连续人格"这个抽象想法落到代码。

**做了什么**:
- main.py 单一文件,~500 行
- 11 维人格参数 + 简单 LLM 调用包装
- per-user 配置字典(内存)

**踩的坑**:
- 人格状态不持久化,重启后归零
- 命名混乱(`_persona_initialized` vs `_labels` vs `_dimensions`)
- 测试 0 个

### v1.0.2v3 — Phase 0 完成(Superego + 叙事)

**目标**:bot 感知行为是否符人格,产生"内心独白"。

**实现**:
- 11 维人格 → 66 个 personality-colored 模板
- Action → Dimension 映射(每行为关联 1-2 维度)
- Tension 分类(高/中/低)
- Superego Guard(行为合规检查)
- Diary Writer(每日日记)

**理论**:
- Kagan(价值观层次)
- Tangney 2002(Shame/Guilt 区分)
- Lazarus(评价理论)
- Weiner(归因理论)

**测试**:173/173,模块 ~10 个。

### v1.0.3(per [[emotion-spirit-v103]]) — Persona 持久化

**问题**:重启 AstrBot 后 auto 模式人格回到"未初始化"。

**根因**:`_persona_initialized` 和 `_labels` 只在内存,`SpiritStore` 虽有 dirty-flag + 原子写入,但从未保存这两个字段。

**设计**:**"persona namespace" 单一真相源**
```json
{
  "persona": {
    "initialized": true,
    "persona_id": "xiaofu",
    "labels": {"mbti": "INFP", "attachment": "焦虑型", ...},
    "initialized_at": "2026-06-05T10:30:00+00:00",
    "schema_version": 1
  }
}
```

**配套改动**:
- 删除 manual 模式(简单化)
- 新增 `/spirit_relabel` 命令(两阶段调整,避免运行时切换)
- main.py 减 27 行

**ADR 化**(后视):这就是今天的 [[emotion-spirit-direction|ADR-0004]] persona_id default sentinel 模式。

### v1.0.4 — 清理 + schema 修复

小版本清理,修 v1.0.3 边界 bug。

### v1.1.1(per [[emotion-spirit-v111]]) — 情绪表示升级

**目标**:从单一字符串升级为概率分布 + 派生数据。

**决策**:**数据驱动 + 最小必要公开 + 隐私边界 + 严格规则一致性**。

**实现**:
- PAD 概率分布(7 类)
- 9→11 字段 API
- `emotion_ambiguity` = `1 - max(p)`
- `emotion_velocity` = 帧间差分
- 概率分布而非单值,反映"我不确定我现在是什么心情"

**测试**:254/254。

### v1.2(per [[emotion-spirit-v12-design]]) — 3 个新字段

**新增字段**:
- `ambiguity`(情绪模糊度)
- `velocity`(情绪变化速度)
- `trajectory`(8 帧环形缓冲,情绪轨迹)

**保持**:
- PAD raw 数值(API 稳定)
- 定时写持久化(避免每次都 flush)

**trajectory 高级 API**:支持"看 bot 过去 8 帧怎么变化的"。

### v1.3 — 进一步清理

小版本,合并 v1.1 + v1.2 边角 case,测试 254/254。

### v1.7(per [[emotion-spirit-v17]] / [[autonomy-guard-design-issue]]) — autonomy_guard 拆分

**问题**:ISTJ 和 ENTP 在 11 维里,**autonomy_guard 触顶 1.0** 无法区分。

**根因**:该维度实际耦合了 2 个不同概念:
1. `relational_autonomy` — 关系中保护边界的能力
2. `exploration_openness` — 主动探索新事物的开放程度

**决策**:**拆成 2 维**(per ADR-0006):
- 11 维 → 12 维
- 跟 Big Five 的"agreeableness 逆向"和"openness"对齐
- v1.7 提供 `_v1_compat.py` 兼容旧数据

**理论**:MBTI 区分 I/E + J/P;Big Five 把 agreeableness 和 openness 分两轴。

### v1.x 总结

| 维度 | 数值 |
|---|---|
| 模块数 | ~20 |
| 测试 | ~300 |
| LOC | ~5K |
| 阶段 | Phase 0 / 0.5 / 1.5 完成 |
| 关键成就 | 情绪概率分布 / 12 维人格 / persona 持久化 |

---

## 2. Phase 2.0 - 2.5 关系层(2026-06)

### Phase 2.0(per [[phase2-design]]) — Per-user 记忆

**目标**:bot 跟每个用户有独立的"关系记忆"。

**实现**:
- `MemoryPool` 加 `user_id` 二级索引
- `buffer_signals` per-user 独立
- `SocialGraph`(per-session 内部,不跨用户泄露)
- `TopicPrivacy`(话题级隐私控制)
- per-user recall API

**5 理论支柱**:
- Bowlby(依恋理论)
- Roberts(人格发展)
- Mehrabian & Russell(PAD)
- McAdams(人格与身份)
- Lodi-Smith & DeYoung(社会人格学)

**测试**:23 个新增测试。

### Phase 2.5(per [[emotion-spirit-phase25]]) — 关系人格微调

**目标**:亲密度分化 + 关系人格独立演化。

**实现**:
- per-user 模式识别
- 亲密度独立演化(每关系 6 维:信任/亲密/熟悉/依赖/承诺/激情)
- `RelationshipPersonality`(per-relationship 的人格微调)
- 4 段 tone 映射:陌生/初识/熟络/亲密
- Bowlby 内部工作模型 per-relationship

**意义**:这是 4 层架构的"关系记忆"层完成。

---

## 3. Phase 3.0 三元力学(2026-06-06 → 06-08)

### Phase 3.0A(per [[emotion-spirit-phase-30a-plan]] / [[emotion-spirit-phase-3-progress]]) — 三元力学引擎原型

**理论**(per [[three-force-framework]]):
- 3 力决策:自然 / 社会 / 个体
- 决策 = 力竭后的落点
- 指导 Phase 3 内在生命设计

**实现**:
- `ForceState` + `ForceDynamics`
- `DIM_FORCE` 12 维分类(自然 3 / 社会 4 / 个体 5)
- 算法 H:per-dim 极化 × 跨人方差
- `STD_FLOOR` 防退化

**理论**:
- Fleeson(人格状态)
- van Geert(动态系统)

**测试**:473 → 485。

### Phase 3.0B — body_state + conscience_pressure

**实现**:
- `body_state`(hormone / energy / arousal)调制 intensity
- `conscience_pressure` 调制(Tangney guilt → self-focus)
- pure-function 100% 向后兼容

### Phase 3.0C(per [[emotion-spirit-phase-30c-preflight]] / [[-implementation]]) — 3072 KB persona baseline

**规模**:16 MBTI × 6 emotion × 4 conflict × 8 time = **3072 entries**

**实施**:
- 64-combo probe + 5 lit points(MAD=0.1573)
- 5 task + Step 3(3 spec 偏离修)+ Step 4(3072 narrative 回测)
- 18 commits on 30c-task2
- N/S curiosity literature override

**测试**:591 → 611。

---

## 4. v2.0.0 Launch 期(2026-06-09 → 06-10)

### 4.1 框架审视(per [[emotion-spirit-framework-review]] / [[verification-complete]])

2026-06-06 做了 1 次整体框架审视:
- **7 决议 + 3 plan**
- 验证套件 D+C+A 三阶段全部通过,**8.85/10** 评分

### 4.2 v2.0.0v1(per [[emotion-spirit-phase-4-launch-design]] / [[-complete]])

2026-06-09,v2.0.0v1 single release(8 commits in main):
- **C1**: ConscienceTracker B2 滑动窗口 P95
- **C2**: pyproject.toml + requirements + metadata v2.0
- **C3**: public_api `__all__` + public_api_stable.md + v1 deprecation
- **C4**: **4 层 dir 重构**(37 modules relocated)
- **C5**: 厚 README + 5 mockup + theory.md(23 篇文献)
- **C5.5**: pre-existing debt fix
- **C6**: CHANGELOG + URL fix
- post-merge: 命令 ns 化 + commands.py v2 path 修复

**测试**:591 → 612。
**结构**:30 modules(6 core + 7 memory + 11 regulation + 13 output)。

### 4.3 Secret Leak 事故(per [[emotion-spirit-secret-leak]])

**事故**:2026-06-09 `data/cmd_config.json` 含 AstrBot admin 密码,被意外提交到公开仓库。

**修复**(2026-06-10,1 天内闭环):
1. `filter-repo` scrub 112 commits
2. pre-commit secret scanner 防御层
3. `.secrets-allowlist` 显式白名单
4. README "Security" 章节
5. v2.0.0v1 tag 验证安全(`e7b6146` 不含 secret)

**教训**:`data/` 目录必须 template 入 git,真 config 排除。pre-commit 不能省。

### 4.4 v2.0.0v2(2026-06-10)

合并 v1 + v2(secret scanner / pre-commit / scrub / slim zip / metadata 统一)。

**关键调整**:
- `metadata.yaml` `version: "2.0.0"` 统一(合并时修)
- `release.yml` `--prefix=astrbot_plugin_emotion_spirit/` 修正(原配错)
- v2.0.0v1 → v2.0.0v2 → v3.0.0 序列清晰

### 4.5 Slim Release Zip(per [[emotion-spirit-release-zip]])

- `.gitattributes` export-ignore 排除:tests / verification / output / tools / docs / conftest / dev-requirements / __pycache__ / .pytest_cache / *.egg-info
- GitHub Actions on tag push 自动 build + attach
- **16.7 MB → 234 KB** 压缩后 / 3.26 MB 解压后

### 4.6 Persona KB Regen(per [[emotion-spirit-persona-kb-regen-plan]])

(A) KB 重建:commit `5d28c13` / `01ba01b` 修外部 mega-paper-kb 路径
(B) KB ship 进 plugin:commit `13e7b56` / `d639640` 解决 release blocker

**位置**:`emotion_spirit/core/kb/persona_labels_db.json`(2.74 MB,入 git)

---

## 5. v3.0.0 大合并期(2026-06-12)

### 5.1 v3.0 Merger(per [[emotion-spirit-v3-merger-plan]])

**Phase A-I 9 阶段合并**:
- A: 统一记忆系统(7 modules)
- B: Bridge + Output(6 modules)
- C: 向量记忆空间
- D: 记忆系统重构
- E: 生产流程接入
- F: **sylanne_core 内嵌**(46 modules)
- G: LLM LifeSimulator
- H: on_llm_response 钩子
- I: 集成测试 + 版本发布

**Per ADR-0005**:**A→B→C→D→E→F→G→H→I 依赖深度排序**,每阶段可独立验证 + 独立 revert。

**关键模块**:
- `UnifiedEntry`: 自包含记忆实体 + 情境衰减
- `DecayModel`: 双轴衰减(Ebbinghaus)
- `CascadeEngine`: 倒排索引级联传播
- `CollapseArchetype`: 5 种崩溃行为模式
- `SuppressionState`: 动态压抑系统
- `MemorySampler`: 人格加权多层采样
- `EngineManager` + `PersonalityBridge` + `HotPoolForwarder`
- `RealtimeDispatch` + `RhythmLearner` + `BotDecision`(proactive_chat 适配)

**统计**:
- 模块:104 个(58 core + 46 sylanne)
- LOC:54,682
- 测试:**856 passed, 0 failures**
- 0 第三方运行时依赖

---

## 6. v3.0.1 兼容期(2026-06-13)

### 6.1 AstrBot v4.25 兼容(per [[emotion-spirit-v301-astrbot-v425-patch]])

AstrBot 在 v4.14 → v4.25 跨 11 个版本,v3.0.0 出现 **10 个不兼容 bug**:
1. Python 3.13 namespace package install
2. handler 签名变更
3. desc 字段类型
4. 持久化 sentinel
5. ...(6 个其他)

### 6.2 一次性修复

v3.0.1(2026-06-13):
- 修 10 个 bug
- CI matrix:测 3 个 AstrBot 版本(4.9.2 / 4.14.6 / 4.25.5)
- Python 3.11 + 3.13 matrix
- exclude:Python 3.11 + AstrBot 4.25.5(4.25 需要 Python ≥3.12)
- 5 个有效 matrix 组合, fail-fast: false

**CI Matrix commit `a53795c`**:这是 R0,评估报告里的 R1(原 4-plugin 评估),不是新 R1。

---

## 7. 生态评估 → Re-scope(2026-06-13)

### 7.1 原始 directive(per [[emotion-spirit-ecosystem-eval-directive]])

2026-06-10 用户指令:**下次 session 评估整个 AstrBot 插件生态**(emotion_spirit + sylannengine + 姐妹插件)。10 个评估维度。

### 7.2 4-plugin 评估 + Re-scope

第一次评估发现 4 个 plugin:
- emotion_spirit(活跃)
- proactive_chat(快照)
- sylannengine(快照)
- sylanne(快照)

总分 6/10(emotion_spirit 9/10,被其他 3 个拉低)。

**用户在 2026-06-13 重新指示**:**只评估 emotion_spirit**,其他 3 个不管。

### 7.3 单 plugin 深度评估(per [[emotion-spirit-ecosystem-eval-2026-06-13]])

**综合 8/10**,10 维度:
1. Code Architecture 8/10
2. AstrBot Compatibility 9/10
3. Internal Modularity 8/10
4. Security 9/10
5. Release Infrastructure 9/10
6. Test Coverage 9/10
7. Documentation 8/10
8. API Stability 8/10
9. Real-world Usage **4/10**(私仓 0 外部用户)
10. Roadmap Clarity 7/10(v3.1+ 缺 spec)

**Top 5 推荐**:
- R1: 建 ADR 仓库
- R2: 写 v3.1+ 公开 spec
- R3: sylanne namespace 重命名
- R4: E2E + mutation testing
- R5: PyPI + AstrBot plugin 列表

---

## 8. R1-R3 实施期(2026-06-14)

### 8.1 R1 — ADR 仓库(commit `c4dc308`)

按 MADR 3.0 模板写了 7 份 ADR + 1 索引:
- **ADR-0001**: 4 层目录结构
- **ADR-0002**: 不使用 `requires_plugins`
- **ADR-0003**: 内嵌 SylannEngine
- **ADR-0004**: persona_id default sentinel
- **ADR-0005**: v3.0 Phase A-I 实施顺序
- **ADR-0006**: v1.7 autonomy_guard 拆分
- **ADR-0007**: pre-commit secret scan

**意义**:把散落在 commit / memory / spec 里的设计决策,**集中到 single source of truth**。

### 8.2 R3 — `sylanne_core` → `sylanne` 重命名(commit `8be17d8`)

**动机**:
- 物理隔离外部 `sylanne-1.4.7` 插件
- 路径短 6 字符(`sylanne_core` → `sylanne`)
- v3.0 私仓 0 外部用户,无 breaking 代价

**实施**:
- `emotion_spirit/sylanne_core/` → `emotion_spirit/sylanne/`
- `tests/sylanne_core/` → `tests/sylanne/`
- 15 个 .py 文件 import 更新
- 5 个 namespace 隔离测试(`tests/test_namespace_isolation.py`)
- ADR-0008 记录决策(supersedes 部分 ADR-0003)

**统计**:66 files changed, 227 insertions, 71 deletions,**856 → 861 tests**,0 regression。

### 8.3 R2 — v3.1+ 公开 spec(commit `d21bb6c`)

**`docs/emotion-spirit-v31-design.md`**(218 lines),6 大目标按 P0/P1/P2 排序:
- **P0**: MemoryPool v2 索引优化(性能)
- **P0**: API deprecation policy(可维护性)
- **P1**: Telemetry opt-in(真实使用)
- **P1**: Phase 5+ Dream Generator(新功能)
- **P2**: E2E + mutation testing
- **P2**: PyPI 公开发布

**Timeline**:
- alpha.1(2026-07-15)— MemoryPool v2
- alpha.2(2026-08-01)— Deprecation + Telemetry
- beta.1(2026-08-15)— Phase 5+
- stable(2026-09-01)— v3.1.0
- v3.1.1(2026-10-15)— E2E + PyPI

**兼容性承诺**:配置 / 数据 / 公开 API 100% 保持(只新增不删除)。

### 8.4 修 pyproject(commit `5330e05`)

v3.0 加 bridge + R3 加 sylanne 后,`pyproject.toml` 的 `[tool.setuptools].packages` 列表没跟上,加 3 个缺失包。

**本地 CI 模拟**(3/5 个 combo):
- Python 3.11 + AstrBot 4.14.6:✅ 861/861
- Python 3.11 + AstrBot 4.9.2:✅ 861/861
- Python 3.11 + AstrBot 4.25.5(ignore-requires-python):✅ 861/861
- Python 3.13:本地无,跳过(matrix 已正确 exclude 3.11+4.25.5)

---

## 9. 关键设计决策的演变

| 决策 | v1.0 | v1.7 | v2.0 | v3.0 | 现在 |
|------|------|------|------|------|------|
| 人格维度数 | 11 | **12**(autonomy 拆分) | 12 | 12 | 12 |
| 情绪表示 | string | probability(7 类) | probability | probability | probability |
| 持久化 | 内存 | persona namespace | SpiritStore | SpiritStore v2/3 | SpiritStore v3 |
| 目录结构 | 1 层 | 1 层 | **4 层** | 4 层 | 4 层 |
| 公开 API | 混乱 | 混乱 | **stable** | stable | stable |
| Sylanne 集成 | 外部依赖 | 外部依赖 | 外部依赖 | **嵌入**(`sylanne_core`) | 嵌入(重命名 `sylanne`) |
| 秘密管理 | 无 | 无 | template re-included | pre-commit scanner | pre-commit scanner |
| 文档分散度 | 散落 | 散落 | 散落 | 散落 | **ADR 集中** |
| 测试 | 0 | 254 | 612 | 856 | 861 |

---

## 10. 当前状态快照(2026-06-14)

### 10.1 数字

| 指标 | 数值 |
|---|---|
| 版本 | v3.0.1 + R1-R3 治理完善 |
| LOC | 54,682 |
| 模块 | 104(58 core + 46 sylanne) |
| 测试 | **861 passed, 0 failures** |
| Git commits | 145+(main 上 4 个新:R1 / R2 / R3 / pyproject fix) |
| 第三方运行时依赖 | 0(只依赖 AstrBot) |
| Python 兼容性 | 3.11 / 3.13 |
| AstrBot 兼容性 | 4.9.2 / 4.14.6 / 4.25.5 |
| 文档 | 8 份 ADR + 4 docs + theory + 23 理论来源 |
| 外部用户 | 0(私仓) |

### 10.2 Git 状态

```
5330e05  fix(pyproject): add missing sub-packages (2026-06-14)
d21bb6c  docs: add v3.1+ public spec (R2, 2026-06-14)
8be17d8  refactor: rename sylanne_core → sylanne (R3, 2026-06-14)
c4dc308  docs: add ADR repository (R1, 2026-06-14)
72fe647  docs: fix stale command refs (2026-06-12)
```

**v3.0.0 tag**:`bfe222b`(2026-06-12 全面 README 更新前)
**最新 commit**:`5330e05`(2026-06-14)

### 10.3 评估快照(per 2026-06-13 评估,加 R1-R3 后估算)

| 维度 | 评估时 | 现在 |
|---|---|---|
| Documentation | 8/10 | **9/10**(+ADR 仓库) |
| Roadmap Clarity | 7/10 | **8/10**(+v3.1 spec) |
| Code Architecture | 8/10 | **9/10**(+sylanne 物理隔离) |
| **综合** | **8/10** | **8.5/10** |

---

## 11. 未来路线图(per v3.1 spec)

### 短期(2026-07 → 08)

- **v3.1-alpha.1** (2026-07-15): MemoryPool v2 索引优化
- **v3.1-alpha.2** (2026-08-01): API deprecation policy + Telemetry opt-in
- **v3.1-beta.1** (2026-08-15): Phase 5+ Dream Generator

### 中期(2026-09 → 10)

- **v3.1.0** (2026-09-01): stable 发布
- **v3.1.1** (2026-10-15): E2E + mutation + PyPI

### 远期(2027+)

- **v3.2**: Steppenwolf 多人格(原 Phase 4 / 5.3)
- **v4.0**: SylannEngine v2 channel + i18n + 远程 RBAC

---

## 12. 关键教训(贯穿全程)

### 12.1 文档治理

- **0 外部用户 = 0 breaking 代价**:v3.0 → R3 重命名 0 用户影响,正是私仓项目的优势
- **散落决策 → 集中 ADR**:R1 之后,新决策必须先写 ADR 再实施
- **spec 先行,代码后跟**:v3.0 Phase A-I 按依赖深度排序,每阶段可独立 revert

### 12.2 工程实践

- **editable install ≠ 安装测试**:`pip install -e .` 隐藏 packages 列表漏洞,直到 `python -m build` 才暴露
- **pre-commit 不能省**:2026-06-09 secret leak 闭环后,0 误报 + 0 漏报
- **tag SHA 是法律证据**:v2.0.0v1 tag `e7b6146` 验证"不含 secret"成为官方安全锚点

### 12.3 架构哲学

- **4 层目录 + 装饰器强制**:`@per_user_only` / `@global_only` 在 `emotion_spirit/layer.py` 强制层间访问
- **物理隔离优于逻辑隔离**:R3 重命名比"加 namespace 检查"更可靠
- **deprecation 比 breaking 友好**:v3.1 spec 把"先 warning 后删除"作为 API 演化政策

### 12.4 0 用户的优势

私仓 + 0 外部用户 = 治理自由度:
- 自由做 breaking refactor(R3 重命名)
- 自由合并 v1 + v2(v2.0.0 合并)
- 自由 re-scope 评估报告(2026-06-13 改方向)
- 自由推后 Phase 5+(等真实反馈再做)

---

## 13. 时间线一图概览

```
2026 早期
  │
  ├── v1.0 → v1.0.4   (persona + 持久化)
  ├── v1.1.1         (情绪概率分布)
  ├── v1.2           (3 新字段)
  └── v1.7           (autonomy_guard 拆分)
        │
2026-06-06
  ├── 框架审视 7 决议
  └── Phase A 11/11 完成 (348 tests)
        │
2026-06-07
  ├── Phase B 5/6 (387 tests)
  └── Phase 3.0A plan + spec
        │
2026-06-08
  ├── Phase 3.0A + 3.0B 闭环 (533 tests)
  └── Phase 4 Launch design (16 决策, 6 task)
        │
2026-06-09
  ├── v2.0.0v1 release (612 tests)
  └── Secret leak 事故 ⚠️
        │
2026-06-10
  ├── Secret leak CLOSED ✅
  ├── v2.0.0v2 + slim zip + KB ship
  ├── dev report Phase 0-4 全闭环
  └── 生态评估 directive
        │
2026-06-12
  ├── v3.0.0 release (856 tests, 104 modules)
  └── Phase A-I 9 阶段合并
        │
2026-06-13
  ├── v3.0.1 patch (AstrBot v4.25 兼容, 10 bug)
  ├── CI matrix (R0 ✅)
  ├── 4-plugin 评估 → re-scoped to 1 plugin
  └── 单 plugin 评估 (8/10, R1-R5 推荐)
        │
2026-06-14 (今天)
  ├── R1: ADR 仓库 (7 份 + 索引) ✅
  ├── R3: sylanne_core → sylanne 重命名 ✅
  ├── R2: v3.1+ 公开 spec ✅
  ├── pyproject 修复 + 本地 CI 模拟 ✅
  └── (待 push) 4 个新 commit
        │
2026-07-15
  └── v3.1-alpha.1: MemoryPool v2 (P0)
        │
2026-09-01
  └── v3.1.0 stable
```

---

## 14. 一句话总结

> **从 v1.0 的 500 行 main.py,经过 16 个版本、9 个 Phase、1 次安全事故、1 次生态 re-scope,到 v3.0.1 + R1-R3 治理完善的 104 模块 / 861 测试 / 8 份 ADR / 0 第三方依赖的高质量 AstrBot 插件**。

**最关键的 3 个转折点**:
1. **v1.0.3 persona 持久化** — 解决"重启归零"根本问题,确立 namespace 模式
2. **2026-06-09 secret leak 闭环** — 24 小时内从事故到防御层完整 + tag 验证,体现"危机即改进"的工程文化
3. **2026-06-13 re-scope 评估** — 从 4-plugin 评估改成 1-plugin 深度,R1-R3 实施直接体现在代码里

---

## Related

- [[emotion-spirit-ecosystem-eval-2026-06-13]] — 单 plugin 评估 + R1-R5
- [[emotion-spirit-progress]] — v3.0.0 + R1-R3 状态
- [[emotion-spirit-v3-merger-plan]] — v3.0 9 阶段
- [[emotion-spirit-v301-astrbot-v425-patch]] — v3.0.1 修复
- [[emotion-spirit-phase-4-launch-complete]] — v2.0.0v1 + v2.0.0v2
- [[emotion-spirit-secret-leak]] — 安全事故 CLOSED
- [[emotion-spirit-persona-kb-regen-plan]] — KB 重建
- [[emotion-spirit-release-zip]] — slim zip infra
- [[emotion-spirit-direction]] — 4 层架构(v1)
- [[emotion-spirit-direction-v2]] — 4 层架构(v2)
- [[emotion-spirit-v103]] — persona 持久化
- [[emotion-spirit-v111]] — 情绪概率
- [[emotion-spirit-v12-design]] — 3 新字段
- [[emotion-spirit-v17]] — autonomy 拆分
- [[emotion-spirit-phase25]] — 关系人格微调
- [[emotion-spirit-phase-3-progress]] — Phase 3 父
- [[emotion-spirit-phase-30a-plan]] — 三元力学 plan
- [[emotion-spirit-phase-30c-implementation]] — 3072 KB baseline
- [[emotion-spirit-framework-review]] — 7 决议
- [[verification-complete]] — D+C+A 验证
- [[three-force-framework]] — 三力理论
- [[steppenwolf-and-decisions]] — 多人格
- [[dream-generator-design]] — Phase 5+ 梦境
- [[sylannengine-architecture]] — 上游架构
- [[development-report]] — Phase 0-4 旧版
- `docs/adr/` — 8 份 ADR(R1 产物)
- `docs/emotion-spirit-v31-design.md` — v3.1+ spec(R2 产物)
