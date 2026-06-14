# ADR-0005: v3.0 Phase A-I 实施顺序

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

emotion_spirit v3.0 (Phase A-I, 2026-Q2) 是一个 9 阶段的合并工程,涉及 ~50K 新增 LOC、104 模块、~800 测试。
需要决定:9 个阶段按什么顺序实施?

## Decision Drivers

* **依赖关系**:Memory → Bridge → Vector → Refactor → Integrate → ...
* **可测试性**:每阶段完成都应可独立验证
* **风险分散**:高风险阶段(向量化、整合)放在可回滚位置

## Considered Options

按依赖深度排序(选定):
* **A → 统一记忆** → 后续阶段才有 memory 可用
* **B → Bridge 层** → 引擎/输出桥接
* **C → 向量空间** → 在统一记忆基础上做相似度检索
* **D → 重构** → 利用 C 阶段的接口清理遗留
* **E → 接入** → 公开 API 稳定化
* **F → sylanne_core 内嵌** → 跟外部 Sylanne 解耦
* **G → LifeSimulator** → 在 memory + bridge 之上做高级功能
* **H → on_llm_response hook** → AstrBot 集成
* **I → 集成 + 发布** → v2.0.0v1 → v3.0.0v1 single release

替代方案:按风险排序(从低到高)、按测试密度排序、按代码量排序都被否,因为不满足"每阶段可独立验证"。

## Decision Outcome

Chosen option: **A→B→C→D→E→F→G→H→I 依赖深度排序**,因为:

1. A 阶段产出"统一记忆",后续所有阶段都依赖
2. B 阶段产出"Bridge 层",C/G/H 阶段都依赖
3. C 阶段产出"向量空间",D 阶段的重构和 G 阶段的 LifeSimulator 都用
4. F 阶段(sylanne_core 内嵌)放在中段,让 v3.0.0 中段可以测试"新旧两套"
5. I 阶段(发布)放最后,所有功能稳定后再发版

### Positive Consequences

* 每阶段完成后,测试可独立跑(818 → 856 tests 跨阶段累积)
* 任何阶段出问题可 git revert,不影响其他阶段
* 阶段命名 A-I 让 review 容易定位(每 PR 编号对应阶段)

### Negative Consequences

* 跨阶段并行机会少(团队小,目前 1 人,反而不是问题)
* 用户/外部贡献者必须看完整 9 阶段才能理解 v3.0

### Confirmation

* v3.0.0 release commit 历史显示 9 个独立 phase commit
* `CHANGELOG.md` 3.0.0 段按 Phase A-I 顺序记录
* `emotion-spirit-v3-merger-plan` memory 验证每阶段状态

## More Information

* 实施于 v3.0 (2026-Q2, 2026-06-12)
* 详见 [[emotion-spirit-v3-merger-plan]] — 完整 9 阶段 plan
* 相关: 9 阶段产生 104 模块 + 818 → 856 tests + 54,682 LOC
