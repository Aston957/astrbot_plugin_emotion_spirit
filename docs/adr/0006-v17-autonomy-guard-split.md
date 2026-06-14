# ADR-0006: v1.7 autonomy_guard 拆分 (11→12 维)

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

emotion_spirit 早期版本用单一 `autonomy_guard` 维度(0-1)表示"自主防御"。
v1.5 测试发现:ISTJ 和 ENTP 两个截然不同的人,在 `autonomy_guard` 维度上**触顶 1.0** 无法区分。

调研后发现,该维度实际耦合了两个不同概念:
1. **关系性自主** (relational autonomy):在关系中保护自己边界的能力
2. **探索开放性** (exploration openness):主动探索新事物的开放程度

需要决定:保持 1 维,还是拆成 2 维?

## Decision Drivers

* **理论清晰性**:MBTI / Big Five 都把"自主"和"开放"分两轴
* **人格区分度**:ISTJ 关系自主高 + 探索开放低 vs ENTP 两者都高
* **下游代码兼容性**:拆分会破坏现有使用 `autonomy_guard` 的代码

## Considered Options

* **A**: 保持 1 维 `autonomy_guard`,改算法
* **B**: 拆成 2 维 `relational_autonomy` + `exploration_openness` ← 选定
* **C**: 拆成 3 维(再加 `boundary_clarity`)

## Decision Outcome

Chosen option: **B**,因为:

1. 2 维恰好对应 Big Five 的"agreeableness 逆向"和"openness",理论扎实
2. 3 维会引入"边界清晰度",但跟"关系性自主"重叠 70%,得不偿失
3. v1.7 提供 `_v1_compat.py` 兼容旧代码,无 breaking 升级路径
4. 总人格维度从 11 → 12,数据模型轻量增加

### Positive Consequences

* ISTJ/ENTP 在 12 维空间清晰可分
* 与 Big Five 五因子模型一致,理论可解释
* 未来 v2.0 的人格画像更精准

### Negative Consequences

* 多 1 维,所有 12 维相关的下游(画像生成、prompt 注入)需更新
* 旧数据(11 维)的 `autonomy_guard` 字段需在 v1.7 启动时迁移

### Confirmation

* `_v1_compat.py` 提供 `get_v17_traits(v11_traits) -> v12_traits` 兼容层
* 启动时检测旧字段,自动迁移到新字段
* 单元测试: 已知 ISTJ/ENTP 样本在新维度空间分离度 > 0.3

## More Information

* 实施于 v1.7 (2026-Q1)
* 详见 [[emotion-spirit-v17]] memory — ISTJ/ENTP 区分
* 相关: [[autonomy-guard-design-issue]] memory — 拆分前的问题记录
* 解决了 2026-Q1 框架审视中提出的疑问
