# ADR-0008: 重命名 `sylanne_core` → `sylanne`(R3 实施)

* Status: ✅ Accepted
* Date: 2026-06-14
* Deciders: emotion_spirit team
* Supersedes: [ADR-0003](0003-embed-sylanne-core.md)(部分)

## Context and Problem Statement

emotion_spirit v3.0 (per [ADR-0003](0003-embed-sylanne-core.md)) 把 SylannEngine 46 模块内嵌为 `emotion_spirit/sylanne_core/`。这导致两个问题:

1. **Namespace 冲突风险**:如果用户同时装外部 `sylanne-1.4.7` 插件(其内部用 `sylanne_alpha` 命名空间),理论上可能跟 `emotion_spirit.sylanne_core` 共享某些 Python 名字(`SylanneEngine`, `SylanneConfig` 等),造成 import 歧义
2. **命名冗长**:`sylanne_core` 中的 `_core` 后缀没有信息量(emotion_spirit 包里所有东西都是 core),徒增打字成本

需要决定:保持 `sylanne_core` 还是重命名?

## Decision Drivers

* **物理隔离**:内嵌模块跟外部 Sylanne 插件不应该共享任何命名空间
* **简洁**:import 路径越短越好(常用 import `from emotion_spirit.sylanne import SylanneEngine`)
* **向后兼容**:不破坏已发布 v3.0.0v1 / v3.0.1 的用户
* **测试覆盖**:必须验证重命名不引入 regression

## Considered Options

* **A**: 保持 `sylanne_core`,只加文档警告不要同装外部 sylanne
* **B**: 保留 `sylanne_core` 作为 alias,新增 `sylanne` 为主路径
* **C**: 直接重命名 `sylanne_core` → `sylanne`,删除旧路径 ← 选定

## Decision Outcome

Chosen option: **C**,因为:

1. **物理隔离**:`sylanne` 跟外部 `sylanne_alpha` 名字空间无任何重叠,根本性解决冲突
2. **简洁**:从 13 字符(`sylanne_core`)减到 7 字符(`sylanne`)
3. **v3.0 用户数极少**:私仓 0 外部用户,0 breaking-change 实际影响
4. **测试覆盖**:861 tests(含 5 个 namespace 隔离测试)全部通过

### Positive Consequences

* 跟外部 Sylanne 插件物理隔离,无 namespace 冲突
* import 路径短 6 字符(13 → 7)
* 强制清理 v3.0 历史包袱(把 `_core` 后缀当作"待定"标记去掉)

### Negative Consequences

* 任何外部代码写 `emotion_spirit.sylanne_core` 会立即失败(0 用户受影响,按评估报告)
* `git log` 显示 1 个 rename commit(影响 blame 历史,可用 `git log --follow` 跟踪)
* 必须更新所有 docs/ADRs/metadata 里的 `sylanne_core` 引用

### Confirmation

* `python -m pytest tests/` → **861 passed, 0 failed**
* `tests/test_namespace_isolation.py` 验证:
  - `emotion_spirit.sylanne` 可导入
  - `emotion_spirit.sylanne_core` 不可导入(legacy 路径已删)
  - 跟外部 `sylanne_alpha` 无冲突

## More Information

* 实施于 2026-06-14,R3 阶段
* commit: 即将提交
* 涉及文件: ~15 个 .py 文件 + 1 个 tests 目录 + 3 个 docs
* 测试: 856 → 861 tests(+5 namespace 隔离)
* 相关: [[emotion-spirit-ecosystem-eval-2026-06-13]] R3 建议
* 后续: R2 (v3.1+ spec) 将基于" `sylanne` 是稳定的公共 API"这一前提
