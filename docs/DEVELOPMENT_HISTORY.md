# emotion_spirit 插件开发全史 — Phase 视角

> **从 Phase 1 起步到 2026-06-14 v3.0.1 + R1-R3 治理完善的完整 Phase 历程**
> 生成日期:2026-06-14

> **📜 视角说明**:这是**Phase 视角**的完整开发史(按 Phase 0/0.5 → 1.5/2/2.5/3/4/A-I/5+ 排列)。
> 如果你想看**版本视角**(按 v1.0 → v1.7 → v2.0 → v3.0.1 排列),见:
> → [`DEVELOPMENT_HISTORY_BY_VERSION.md`](DEVELOPMENT_HISTORY_BY_VERSION.md)(备份,671 行)
>
> **两个版本都保留**:因为不同场景适合不同视角——
> - **Phase 视角**(本文件)适合看"项目为什么这么分阶段"
> - **版本视角**(备份)适合看"每个 release 改了什么 bug"
>
> 两个版本内容上互相覆盖,主要差异在组织方式。

---

## 0. 前置背景(Phase 0 / 0.5,简要)

emotion_spirit 在 Phase 1 之前已经有 1 个基础版本(v1.0.x),但**当时还未采用 Phase 路线图**。
2026-Q1 完成的奠基性工作:

**Phase 0 — Superego + 叙事层** (v1.0.2v3):
- 11 维人格 + 66 个 personality-colored 模板
- Action → Dimension 映射
- Tension 分类 + Superego Guard + Diary Writer
- 173/173 测试

**Phase 0.5 — persona 持久化** (v1.0.3 + v1.0.4):
- 修复"重启归零"bug
- "persona namespace" 单一真相源 schema
- `/spirit_relabel` 命令 + 删 manual 模式
- (后来成为 [[emotion-spirit-v103]] / ADR-0004)

**关键决定**:Phase 0/0.5 期间没有"Phase 路线图"概念,只是迭代修 bug + 加功能。
从 Phase 1 开始,正式采用**有编号的 Phase 路线图**作为开发节奏框架。

---

## 1. Phase 1 — 稳定运行 + 观察(2026-Q1)

**计划目标**:让 v1.0.x 在真实环境跑 1-2 周,收集稳定性数据。

**实际结果**:**🚫 跳过**,直接进 Phase 1.5。

**跳过原因**:
- 用户基数小(0 外部用户,只有开发者自己用)
- 1-2 周观察样本量不足,数据没统计意义
- 紧迫的下一个需求是"情绪表示升级"(v1.1.1),优先级更高
- 当时没人监督/催进度,观察期的"延迟价值"难以量化

**教训**:
- "观察 Phase" 在低用户基数下是 anti-pattern
- 只有在 **有真实流量 + 有用户反馈渠道** 时,观察 Phase 才有 ROI
- 后续 Phase 4 Launch 后也面临类似决策(2-4 周用户反馈等待)——但这次 R1-R3 + ADR 流程**强制做观察**,不是直接跳

---

## 2. Phase 1.5 — 情绪表示层(v1.1.1 → v1.3)

**目标**:从单一字符串升级为**概率分布 + 派生数据 + 动态表示**。

### 2.1 v1.1.1(per [[emotion-spirit-v111]])— 概率分布

**决策**:**数据驱动 + 最小必要公开 + 隐私边界 + 严格规则一致性**。

**实现**:
- PAD 概率分布(7 类:joy / sadness / anger / fear / surprise / disgust / neutral)
- 9 → 11 字段 API
- `emotion_ambiguity` = `1 - max(p)`(情绪模糊度)
- `emotion_velocity` = 帧间差分(情绪变化速度)
- 概率分布而非单值,反映"我不确定我现在是什么心情"

**测试**:254/254

### 2.2 v1.2(per [[emotion-spirit-v12-design]])— 3 个新字段

**新增**:
- `ambiguity`(情绪模糊度,独立于 v1.1.1 重新定义)
- `velocity`(情绪变化速度)
- `trajectory`(8 帧环形缓冲,情绪轨迹)

**保持**:
- PAD raw 数值(API 稳定,下游不用改)
- 定时写持久化(避免每次都 flush 磁盘)

**trajectory 高级 API**:支持"看 bot 过去 8 帧怎么变化的"。

### 2.3 v1.3 — 清理

小版本,合并 v1.1 + v1.2 边角 case。

**Phase 1.5 总结**:
- 11 维人格保持不变
- 情绪从 string → 概率分布 → 11 字段
- 7 维 emotion vector + 4 个派生字段
- 测试:254/254

---

## 3. Phase 2.0 — Per-user 记忆视图(2026-Q1)

**目标**:bot 跟每个用户有**独立的"关系记忆"**(per [[phase2-design]])。

**5 理论支柱**:
1. Bowlby(依恋理论)
2. Roberts(人格发展)
3. Mehrabian & Russell(PAD 三维情绪)
4. McAdams(人格与身份)
5. Lodi-Smith & DeYoung(社会人格学)

**实现**:
- `MemoryPool` 加 `user_id` 二级索引
- `buffer_signals` per-user 独立
- `SocialGraph`(per-session 内部,不跨用户泄露)
- `TopicPrivacy`(话题级隐私控制)
- per-user recall API

**设计原则**:
- **互不污染**:user A 的记忆不会影响 user B
- **互不影响**:user A 的亲密度演化不影响 user B
- **per-session 隔离**:bot 不会"知道"用户之间的关系

**测试**:23 个新增。

---

## 4. Phase 2.5 — 关系人格微调(per [[emotion-spirit-phase25]])

**目标**:亲密度分化 + 关系人格**独立演化**。

**实现**:
- per-user 模式识别
- 亲密度独立演化(每关系 6 维:信任/亲密/熟悉/依赖/承诺/激情)
- `RelationshipPersonality`(per-relationship 的人格微调)
- **4 段 tone 映射**:陌生 / 初识 / 熟络 / 亲密
- Bowlby 内部工作模型 per-relationship

**意义**:
- bot 跟 user A 熟了,会**自动调整**表达方式
- 跟 user B 刚认识,会**更正式**
- 4 段 tone 不是硬编码,而是基于亲密度分数连续映射

**Phase 2 + 2.5 总结**:
- per-user 记忆 + per-relationship 人格 = 完整"关系层"
- 4 层架构的"关系记忆"层完成
- 详见 4-layer architecture 哲学(per [[emotion-spirit-direction-v2]])

---

## 5. Phase 3.0 — 三元力学(3 子阶段, 2026-06-06 → 06-08)

Phase 3 是项目的**理论高峰**——把"bot 内心世界"显式化。

### 5.1 Phase 3.0A(per [[emotion-spirit-phase-30a-plan]] / [[emotion-spirit-phase-3-progress]])

**理论**(per [[three-force-framework]]):
- 3 力决策:自然 / 社会 / 个体
- 决策 = 力竭后的落点
- 指导 Phase 3 内在生命设计

**实现**:
- `ForceState` + `ForceDynamics`(力学状态 + 动力学)
- `DIM_FORCE` 12 维分类(自然 3 / 社会 4 / 个体 5)
- 算法 H:per-dim 极化 × 跨人方差
- `STD_FLOOR` 防退化(避免所有维度都收敛到 0)

**理论**:
- Fleeson(人格状态)
- van Geert(动态系统)

**测试**:473 → 485。

### 5.2 Phase 3.0B — body_state + conscience_pressure

**实现**:
- `body_state`(hormone / energy / arousal)调制 intensity
- `conscience_pressure` 调制(Tangney guilt → self-focus)
- pure-function 100% 向后兼容

**意义**:
- bot 不只是"逻辑推理",还有"身体状态"(疲倦、激素、唤醒度)
- 内疚/羞耻会导致 self-focus,影响后续行为

### 5.3 Phase 3.0C(per [[emotion-spirit-phase-30c-preflight]] / [[-implementation]])

**规模**:**3072 KB persona baseline**
- 16 MBTI × 6 emotion × 4 conflict × 8 time = 3072 entries

**实施**:
- 64-combo probe + 5 lit points(MAD=0.1573)
- 5 task + Step 3(3 spec 偏离修)+ Step 4(3072 narrative 回测)
- 18 commits on 30c-task2
- N/S curiosity literature override

**测试**:591 → 611。

**Phase 3 总结**:
- bot 现在有"内心世界"(力学平衡)
- 3072 种 persona 行为模式覆盖主流人格
- 为 Phase 5+(力学河流 / Steppenwolf)打基础

---

## 6. Phase 4 — Launch(v2.0.0, 2026-06-06 → 06-10)

**目标**:**把 v1.x → v2.0 稳定发布**,加 public API 稳定承诺 + 完整 release infra。

### 6.1 框架审视(2026-06-06)

per [[emotion-spirit-framework-review]] / [[verification-complete]]:
- **7 决议 + 3 plan**
- 验证套件 D+C+A 三阶段全部通过,**8.85/10** 评分

### 6.2 v2.0.0v1(2026-06-09, per [[emotion-spirit-phase-4-launch-design]] / [[-complete]])

8 commits in main:
- **C1**: ConscienceTracker B2 滑动窗口 P95(+9 tests, 600 总)
- **C2**: pyproject.toml + requirements + metadata v2.0(+3 tests, 603)
- **C3**: public_api `__all__` + public_api_stable.md + v1 deprecation(+6 tests, 609)
- **C4**:**4 层 dir 重构**(37 modules relocated, +3 tests, 612)
- **C5**: 厚 README + 5 mockup + theory.md(23 篇文献)
- **C5.5**: pre-existing debt fix
- **C6**: CHANGELOG + URL fix
- post-merge: 命令 ns 化 + commands.py v2 path 修复

**测试**:591 → 612。
**结构**:30 modules(6 core + 7 memory + 11 regulation + 13 output)。

### 6.3 Secret Leak 事故(2026-06-09, per [[emotion-spirit-secret-leak]])

**事故**:`data/cmd_config.json` 含 AstrBot admin 密码,被意外提交到公开仓库。

**修复**(24 小时内闭环):
1. `filter-repo` scrub 112 commits
2. pre-commit secret scanner 防御层(`scripts/check_secrets.py`, 8 模式)
3. `.secrets-allowlist` 显式白名单
4. README "Security" 章节
5. v2.0.0v1 tag 验证安全(`e7b6146` 不含 secret)

**教训**:
- `data/` 目录必须 template 入 git,真 config 排除
- pre-commit 不能省(任何时候省,迟早出事)
- tag SHA 是法律证据(可以用来证明"事故前的 release 是安全的")

### 6.4 v2.0.0v2(2026-06-10)

合并 v1 + v2(secret scanner / pre-commit / scrub / slim zip / metadata 统一)。

**关键调整**:
- `metadata.yaml` `version: "2.0.0"` 统一
- `release.yml` `--prefix=astrbot_plugin_emotion_spirit/` 修正
- v2.0.0v1 → v2.0.0v2 → v3.0.0 序列清晰

### 6.5 Slim Release Zip(per [[emotion-spirit-release-zip]])

- `.gitattributes` export-ignore 排除:tests / verification / output / tools / docs / conftest / dev-requirements / `__pycache__` / .pytest_cache / *.egg-info
- GitHub Actions on tag push 自动 build + attach
- **16.7 MB → 234 KB** 压缩后 / 3.26 MB 解压后

### 6.6 Persona KB Regen(per [[emotion-spirit-persona-kb-regen-plan]])

(A) KB 重建:commit `5d28c13` / `01ba01b` 修外部 mega-paper-kb 路径
(B) KB ship 进 plugin:commit `13e7b56` / `d639640` 解决 release blocker

**位置**:`emotion_spirit/core/kb/persona_labels_db.json`(2.74 MB,入 git)

**Phase 4 总结**:
- 4 层目录 + public API 稳定 + 完整 release infra
- 一次安全事故 24 小时闭环
- v2.0.0 = "可发布 / 可安装 / 可追踪 / 可审计" 的基线

---

## 7. Phase A-I — v3.0 大合并(2026-06-12, per [[emotion-spirit-v3-merger-plan]])

**目标**:**合并 9 个独立子项目**到单一 v3.0 仓库。Phase 1-4 的成果(per-user 记忆 / 力学 / public API)+ 大量新功能。

**为什么叫 "Phase A-I"**:跟 Phase 1-4 的数字编号不同,v3.0 采用字母编号(per ADR-0005),反映"大合并"性质。

### 7.1 9 阶段(按依赖深度排序)

| Phase | 内容 | 模块数 |
|---|---|---|
| **A** | 统一记忆系统 | 7 |
| **B** | Bridge + Output | 6 |
| **C** | 向量记忆空间 | (vector ops) |
| **D** | 记忆系统重构 | (refactor) |
| **E** | 生产流程接入 | (integration) |
| **F** | **sylanne_core 内嵌** | **46** |
| **G** | LLM LifeSimulator | (event types) |
| **H** | on_llm_response 钩子 | (hooks) |
| **I** | 集成测试 + 版本发布 | (release) |

### 7.2 关键模块

- `UnifiedEntry`: 自包含记忆实体 + 情境衰减
- `DecayModel`: 双轴衰减(Ebbinghaus)
- `CascadeEngine`: 倒排索引级联传播
- `CollapseArchetype`: 5 种崩溃行为模式
- `SuppressionState`: 动态压抑系统
- `MemorySampler`: 人格加权多层采样
- `EngineManager` + `PersonalityBridge` + `HotPoolForwarder`
- `RealtimeDispatch` + `RhythmLearner` + `BotDecision`(proactive_chat 适配)

### 7.3 排序原则(per ADR-0005)

**A→B→C→D→E→F→G→H→I 依赖深度排序**,理由:
- A 阶段产出"统一记忆",后续所有阶段都依赖
- B 阶段产出"Bridge 层",C/G/H 阶段都依赖
- C 阶段产出"向量空间",D 阶段的重构和 G 阶段的 LifeSimulator 都用
- F 阶段(sylanne_core 内嵌)放在中段,让 v3.0.0 中段可以测试"新旧两套"
- I 阶段(发布)放最后,所有功能稳定后再发版

### 7.4 统计

- 模块:**104 个**(58 core + 46 sylanne)
- LOC:**54,682**
- 测试:**856 passed, 0 failures**
- 0 第三方运行时依赖

---

## 8. v3.0.1 兼容期(2026-06-13, per [[emotion-spirit-v301-astrbot-v425-patch]])

**触发**:AstrBot 在 v4.14 → v4.25 跨 11 个版本,v3.0.0 出现 **10 个不兼容 bug**。

### 8.1 一次性修复

v3.0.1(2026-06-13):
1. Python 3.13 namespace package install
2. handler 签名变更
3. desc 字段类型
4. 持久化 sentinel
5. ...(6 个其他)

### 8.2 CI Matrix 引入(commit `a53795c`)

测 3 个 AstrBot 版本(4.9.2 / 4.14.6 / 4.25.5)+ Python 3.11 + 3.13:
- 5 个有效 matrix 组合
- exclude:Python 3.11 + AstrBot 4.25.5(4.25 需要 Python ≥3.12)
- fail-fast: false(一个挂了不影响其他)

**这是 R0**(原 4-plugin 评估的 R1),不是新的 R1。

---

## 9. 2026-06-13 评估 + Re-scope

### 9.1 原始 directive(per [[emotion-spirit-ecosystem-eval-directive]])

2026-06-10 用户指令:**下次 session 评估整个 AstrBot 插件生态**(emotion_spirit + sylannengine + 姐妹插件)。10 个评估维度。

### 9.2 4-plugin 评估 + Re-scope

第一次评估发现 4 个 plugin:
- emotion_spirit(活跃)
- proactive_chat(快照)
- sylannengine(快照)
- sylanne(快照)

总分 6/10(emotion_spirit 9/10,被其他 3 个拉低)。

**用户在 2026-06-13 重新指示**:**只评估 emotion_spirit**,其他 3 个不管。

### 9.3 单 plugin 深度评估(per [[emotion-spirit-ecosystem-eval-2026-06-13]])

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

## 10. 2026-06-14 R1-R3 实施期

按 **R1 → R3 → R2** 顺序执行(先文档,再实施,最后 spec)。

### 10.1 R1 — ADR 仓库(commit `c4dc308`)

按 MADR 3.0 模板写了 7 份 ADR + 1 索引:
- **ADR-0001**: 4 层目录结构
- **ADR-0002**: 不使用 `requires_plugins`
- **ADR-0003**: 内嵌 SylannEngine
- **ADR-0004**: persona_id default sentinel
- **ADR-0005**: v3.0 Phase A-I 实施顺序
- **ADR-0006**: v1.7 autonomy_guard 拆分
- **ADR-0007**: pre-commit secret scan

**意义**:把散落在 commit / memory / spec 里的设计决策,**集中到 single source of truth**。

### 10.2 R3 — `sylanne_core` → `sylanne` 重命名(commit `8be17d8`)

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

### 10.3 R2 — v3.1+ 公开 spec(commit `d21bb6c`)

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

### 10.4 修 pyproject(commit `5330e05`)

v3.0 加 bridge + R3 加 sylanne 后,`pyproject.toml` 的 `[tool.setuptools].packages` 列表没跟上,加 3 个缺失包。

**本地 CI 模拟**(3/5 个 combo):
- Python 3.11 + AstrBot 4.14.6:✅ 861/861
- Python 3.11 + AstrBot 4.9.2:✅ 861/861
- Python 3.11 + AstrBot 4.25.5(ignore-requires-python):✅ 861/861
- Python 3.13:本地无,跳过(matrix 已正确 exclude 3.11+4.25.5)

---

## 11. Phase 5+ — 远期(未启动,per [[development-report]] §Phase 5+ 候选)

> **核心原则**:Phase 5+ 启动前必须先收集 2-4 周真实用户反馈。当前 0 用户使用,做太多 Phase 5+ 等于盲改。
> 2026-06-10 修订:原 Phase 4 "荒原狼式动态人格" 全部下移到 Phase 5+,Phase 4 改为 Launch(发布工程)。

### 11.1 候选子项目

| 子项目 | 描述 | 前置 |
|---|---|---|
| **5.1 力学河流**(Force Current) | bot 感知"此刻是哪个力主导",叙事色彩随力学平衡**连续漂移**;narrative 模板按"主力"分层(自然色/社会色/个体色);`/reflect_force_current` 命令 | Phase 3.0A ✅ 已就位 |
| **5.2 内心独白**(Inner Monologue) | 多个力同时发声,用户感受"有内心挣扎的人";prompt_injector 注入 "natural says ..." / "social says ..." / "individual says ..." | 5.1 |
| **5.3 Steppenwolf 多人格** | bot 在长期演化中分化出多个稳定人格簇(IFS Parts 风);12 维 + 3 力学 → 聚类 N 个"人格质心";触发器:特定 user_id / 话题 / 情绪 → 切换主导人格 | 5.2 + 大量真实运行数据 |
| **5.4 力学记忆**(Force Memory) | bot 记"上次这种情境我偏向了社会力" → 影响下次决策;Episodic memory 但维度是 force_state 而非 PAD | 5.1 |

### 11.2 Phase 5+ 跟 v3.1+ 的关系

**v3.1+ P1 已经包含 Phase 5+ 的子集**:
- **Dream Generator**(per [[dream-generator-design]])是 v3.1 P1,2026-08-15 beta.1
- **5.1 力学河流**没明确排进 v3.1,但跟 MemoryPool v2 性能优化有协同(力学状态持久化)

**Phase 5+ 完整版**(5.1-5.4 全部)可能要 v3.2+ 才推进。

### 11.3 理论来源

- **5.1**: 力学平衡的视觉化 → 叙事理论
- **5.2**: 内在对话 → Hermans 对话自我
- **5.3**: 多人格 → Schwartz IFS / Assagioli 心理综合 / 黑塞《荒原狼》
- **5.4**: 力学记忆 → McAdams 叙事身份

---

## 12. 关键设计决策的演变(跨 Phase)

| 决策 | Phase 0 | Phase 1.5 | Phase 2.x | Phase 3.0 | Phase 4 | Phase A-I | 现在 |
|------|---------|-----------|-----------|-----------|---------|-----------|------|
| 人格维度数 | 11 | 11 | 11 | 12(v1.7 拆分) | 12 | 12 | 12 |
| 情绪表示 | string | **probability**(7 类) | probability | probability | probability | probability | probability |
| 持久化 | 内存 | persona namespace | SpiritStore v1 | SpiritStore | SpiritStore | **SpiritStore v2/3**(pad history/trajectory/memory_pool) | SpiritStore v3 |
| 目录结构 | 1 层 | 1 层 | 1 层 | 1 层 | **4 层** | 4 层 | 4 层 |
| 公开 API | 混乱 | 混乱 | 混乱 | 混乱 | **stable** | stable | stable |
| Sylanne 集成 | 外部依赖 | 外部依赖 | 外部依赖 | 外部依赖 | 外部依赖 | **嵌入**(`sylanne_core`) | 嵌入(重命名 `sylanne`) |
| 秘密管理 | 无 | 无 | 无 | 无 | **template re-included + scanner** | scanner | scanner + ADR-0007 |
| 文档分散度 | 散落 | 散落 | 散落 | 散落 | 散落 | 散落 | **ADR 集中** |
| 测试 | 173 | 254 | 300+ | 611 | 612 | **856** | **861** |
| 理论支柱 | 4 | 5 | 10 | 12 | 12 | 12 | 12+ |

---

## 13. 当前状态快照(2026-06-24)

### 13.1 数字

| 指标 | 数值 |
|---|---|
| 版本 | v1.0.0 |
| LOC | 54,682+ |
| 模块 | 109(58 core + 46 sylanne + 5 migrations) |
| 测试 | **886 passed, 0 failures** |
| Git commits | 152+(main 上 7 个新:migration framework) |
| 第三方运行时依赖 | 0(只依赖 AstrBot) |
| Python 兼容性 | 3.11 / 3.13 |
| AstrBot 兼容性 | 4.9.2 / 4.14.6 / 4.25.5 |
| 文档 | 12 份 ADR + 4 docs + theory + 23 理论来源 |
| 外部用户 | 0(私仓) |

### 13.2 Git 状态

```
5330e05  fix(pyproject): add missing sub-packages (2026-06-14)
d21bb6c  docs: add v3.1+ public spec (R2, 2026-06-14)
8be17d8  refactor: rename sylanne_core → sylanne (R3, 2026-06-14)
c4dc308  docs: add ADR repository (R1, 2026-06-14)
72fe647  docs: fix stale command refs (2026-06-12)
```

**v3.0.0 tag**:`bfe222b`(2026-06-12 全面 README 更新前)
**最新 commit**:`5330e05`(2026-06-14)

### 13.3 评估快照(per 2026-06-13 评估,加 R1-R3 后估算)

| 维度 | 评估时 | 现在 |
|---|---|---|
| Documentation | 8/10 | **9/10**(+ADR 仓库) |
| Roadmap Clarity | 7/10 | **8/10**(+v3.1 spec) |
| Code Architecture | 8/10 | **9/10**(+sylanne 物理隔离) |
| **综合** | **8/10** | **8.5/10** |

---

## 14. 未来路线图(per v3.1 spec)

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

## 15. 关键教训(贯穿全程)

### 15.1 Phase 路线图治理

- **"观察 Phase" 在低用户基数下是 anti-pattern** — Phase 1 跳过的教训
- **数字 vs 字母编号** — Phase 0/0.5/1/1.5/2/2.5/3/3A/3B/3C/4 是数字(迭代);Phase A-I 是字母(大合并)
- **"完整做 9 阶段" 比 "并行做 9 阶段" 风险低** — 字母编号反映"序列化"性质
- **强制做观察(Phase 4 后 2-4 周)** — 用 R1-R3 + ADR 流程强制,不让"直接跳"再发生

### 15.2 文档治理

- **0 外部用户 = 0 breaking 代价** — v3.0 → R3 重命名 0 用户影响,正是私仓项目的优势
- **散落决策 → 集中 ADR** — R1 之后,新决策必须先写 ADR 再实施
- **spec 先行,代码后跟** — v3.0 Phase A-I 按依赖深度排序,每阶段可独立 revert

### 15.3 工程实践

- **editable install ≠ 安装测试** — `pip install -e .` 隐藏 packages 列表漏洞,直到 `python -m build` 才暴露
- **pre-commit 不能省** — 2026-06-09 secret leak 闭环后,0 误报 + 0 漏报
- **tag SHA 是法律证据** — v2.0.0v1 tag `e7b6146` 验证"不含 secret"成为官方安全锚点

### 15.4 架构哲学

- **4 层目录 + 装饰器强制** — `@per_user_only` / `@global_only` 在 `emotion_spirit/layer.py` 强制层间访问
- **物理隔离优于逻辑隔离** — R3 重命名比"加 namespace 检查"更可靠
- **deprecation 比 breaking 友好** — v3.1 spec 把"先 warning 后删除"作为 API 演化政策
- **0 依赖哲学** — 不引第三方库,所有功能 in-house 实现

### 15.5 0 用户的优势

私仓 + 0 外部用户 = 治理自由度:
- 自由做 breaking refactor(R3 重命名)
- 自由合并 v1 + v2(v2.0.0 合并)
- 自由 re-scope 评估报告(2026-06-13 改方向)
- 自由推后 Phase 5+(等真实反馈再做)

### 15.6 心理学理论的"用而不过"

emotion_spirit 用了 12+ 个心理学理论(Kagan / Tangney / Bowlby / Fleeson / van Geert / Schwartz IFS / Hermans / 等):
- **不空谈理论** — 每个理论都有对应模块(如 Bowlby → RelationshipPersonality)
- **不堆理论** — 拒绝"理论越多越好"诱惑(per "不做的边界"列表)
- **理论是工具,不是目的** — bot 体验好才是目的

---

## 16. 时间线一图概览(Phase 视角)

```
2026-Q1
  │
  ├── Phase 0    Superego + 叙事层 (v1.0.2v3)         ✅
  ├── Phase 0.5  persona 持久化 (v1.0.3 + v1.0.4)    ✅
  ├── Phase 1    稳定运行 + 观察                       🚫 跳过
  │
  ├── Phase 1.5  情绪表示层 (v1.1.1 → v1.3)           ✅ 254 tests
  │
  ├── Phase 2.0  Per-user 记忆视图                     ✅
  ├── Phase 2.5  关系人格微调                          ✅
  │
  ├── Phase 3.0A 三元力学引擎原型                     ✅ 485 tests
  ├── Phase 3.0B body_state + conscience_pressure     ✅
  ├── Phase 3.0C 3072 KB persona baseline             ✅ 611 tests
  │
2026-06-06
  └── 框架审视 7 决议 + 3 plan
        │
2026-06-09
  ├── Phase 4 Launch (v2.0.0v1, 8 commits)            ✅ 612 tests
  └── Secret leak 事故 ⚠️
        │
2026-06-10
  ├── Secret leak CLOSED ✅
  ├── v2.0.0v2 final (secret scanner + pre-commit)
  ├── slim release zip infra
  └── KB regen + ship
        │
2026-06-12
  └── Phase A-I v3.0 大合并 (9 阶段, 104 modules)    ✅ 856 tests
        │
2026-06-13
  ├── v3.0.1 兼容 patch (AstrBot v4.25 10 bug)        ✅
  ├── CI matrix (commit a53795c, 5 combos)
  ├── 4-plugin 评估 → re-scoped to 1 plugin
  └── 单 plugin 评估 (8/10, R1-R5 推荐)
        │
2026-06-14 (今天)
  ├── R1: ADR 仓库 (7 份 + 索引)                      ✅ commit c4dc308
  ├── R3: sylanne_core → sylanne 重命名                ✅ commit 8be17d8
  ├── R2: v3.1+ 公开 spec                             ✅ commit d21bb6c
  └── pyproject 修复 + 本地 CI 模拟                    ✅ commit 5330e05
        │
2026-07-15 → 2026-09-01
  └── v3.1-alpha.1 → v3.1.0 stable
        │
Phase 5+ 远期 (待启动)
  ├── 5.1 力学河流
  ├── 5.2 内心独白
  ├── 5.3 Steppenwolf 多人格
  ├── 5.4 力学记忆
  └── Dream Generator (v3.1 P1)
```

---

## 17. 2026-06-24 Config Migration Framework

### 背景

v3.1 配置项改造移除了 2 个老配置 (`enable_life_simulator`, `life_simulator_mode`) 并重命名了 1 个字段。需要一个通用的配置迁移框架来处理老用户的配置兼容性。

### 实施

采用 **Registry 模式**: `@register_migration(from_version, to_version)` 装饰器 + Runner + State 持久化。

**7 Tasks (TDD)**:
1. Registry (`@register_migration` 装饰器)
2. State (`MigrationState` + atomic save)
3. Runner (`run_migrations()` fail-soft)
4. Rules v3.0→v3.1 (2 条迁移规则)
5. Wire main.py + Web API endpoint
6. Integration test
7. Manual production verification

**关键发现**: AstrBot 的配置系统在 plugin 加载前就验证 schema，自动添加缺失字段。Migration framework 是**保险机制**，AstrBot 处理不了的复杂迁移才需要它。

### 数字

- 25 新 tests (4+6+6+8+1)
- 6 commits
- 885/885 tests passed

---

## 18. 一句话总结

> **从 Phase 0 的 Superego 基础,经过多个阶段的迭代开发,到 v1.0.0 正式发布的 109 模块 / 886 测试 / 12 份 ADR / 0 第三方依赖的高质量 AstrBot 插件**。

**最关键的 3 个 Phase 转折点**:
1. **Phase 1.5 情绪概率分布** — 解决"情绪是确定性单值"的根本问题,确立 PAD 框架
2. **Phase 4 Secret leak 闭环** — 24 小时内从事故到防御层完整 + tag 验证,体现"危机即改进"的工程文化
3. **2026-06-13 评估 re-scope** — 从 4-plugin 评估改成 1-plugin 深度,R1-R3 实施直接体现在代码里

---

## Related

- [[emotion-spirit-ecosystem-eval-2026-06-13]] — 单 plugin 评估 + R1-R5
- [[emotion-spirit-progress]] — v3.0.0 + R1-R3 状态
- [[emotion-spirit-v3-merger-plan]] — Phase A-I 详细规划
- [[emotion-spirit-v301-astrbot-v425-patch]] — v3.0.1 修复
- [[emotion-spirit-phase-4-launch-complete]] — Phase 4 Launch
- [[emotion-spirit-secret-leak]] — 安全事故 CLOSED
- [[emotion-spirit-persona-kb-regen-plan]] — KB 重建
- [[emotion-spirit-release-zip]] — slim zip infra
- [[emotion-spirit-direction-v2]] — 4 层架构 v2
- [[emotion-spirit-v103]] — Phase 0.5 persona 持久化
- [[emotion-spirit-v111]] — Phase 1.5 情绪概率
- [[emotion-spirit-v12-design]] — Phase 1.5 3 新字段
- [[emotion-spirit-v17]] — autonomy 拆分
- [[phase2-design]] — Phase 2.0 详细
- [[emotion-spirit-phase25]] — Phase 2.5 关系人格
- [[emotion-spirit-phase-3-progress]] — Phase 3 父
- [[emotion-spirit-phase-30a-plan]] — Phase 3.0A 力学
- [[emotion-spirit-phase-30c-implementation]] — 3072 KB baseline
- [[emotion-spirit-framework-review]] — 7 决议
- [[verification-complete]] — D+C+A 验证
- [[three-force-framework]] — 三力理论
- [[steppenwolf-and-decisions]] — Phase 5.3 多人格
- [[dream-generator-design]] — Phase 5+ 梦境
- [[sylannengine-architecture]] — 上游架构
- [[development-report]] — Phase 0-4 旧版(被本文件 supersede)
- `docs/adr/` — 8 份 ADR(R1 产物)
- `docs/emotion-spirit-v31-design.md` — v3.1+ spec(R2 产物)
