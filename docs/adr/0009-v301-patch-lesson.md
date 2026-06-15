# ADR-0009: v3.0.1 patch 教训 — multi-file change checklist

* Status: ✅ Accepted
* Date: 2026-06-15
* Deciders: emotion_spirit team
* Supersedes: (none)
* Follow-up to: [ADR-0007](0007-pre-commit-secret-scan.md) (defense 之后补规划)

## Context and Problem Statement

2026-06-13 提交的 `c3f6440 v3.0.1 patch: AstrBot v4.25.5 compatibility` 是修复 AstrBot v4.25 引入的 10 个 breaking-change bug。patch 修改了 3 个文件:

```
.gitignore | 73 ++++++++++++----------
README.md  | 160 ++++++------------------------------------
main.py    | 93 ++++++++++++++++-------
3 files changed, 173 insertions(+), 153 deletions(-)
```

但 patch 同时**bump 了版本号**(`_version.py` 从 `"3.0.0"` → `"3.0.1"`,`metadata.yaml` 同步),这是正确的。然而 patch 改版本号时,**忘了同步 4 个引用位置**:

1. `tests/test_v300_integration.py:201` — `__version__ == "3.0.0"` 硬编码
2. `tests/test_v300_integration.py:211` — `meta["version"] == "3.0.0"` 硬编码
3. `public_api_stable.md:1` — 标题 `(v3.0.0)`
4. `public_api_stable.md:7` — `**版本**: v3.0.0`
5. `emotion_spirit/sylanne/__init__.py:102` — `__version__ = "3.0.0"`(sylanne 子模块自己的版本号)

外加 1 个 test 因为 `__new__` 跳过 `__init__` 后没设 `_config` 触发 AttributeError。

**后果**:
- `c3f6440` 之后 4 个 commit(`#8 #9 #10 #11`) CI **全部失败**
- 5/5 matrix combo 跑通 install 但在 "Run tests" 步骤 fail
- 4 个 test 失败
- 项目"亮红灯"3 天(2026-06-13 → 2026-06-15)

**根因**:**multi-file change 没有 checklist 流程**。patch 作者在改版本号时,没系统地"扫一遍所有引用位置"。

## Decision Drivers

* **预防胜于检测**:测试可以检测 fail,但不能预防写错
* **标准化**:任何 v3.0.x → v3.0.y 的版本号 bump 都要走同一流程
* **轻量级**:不应该加繁重 PR review(项目只有 1 人维护)
* **可执行**:checklist 应该是具体的"在 X 文件里改 Y 字符串",不是抽象原则
* **可追溯**:失败时能 5 分钟定位"checklist 哪一步漏了"

## Considered Options

* **A**: 严格 PR review 流程(每 patch 必须 2 人 review)
  * 优点: 多视角
  * 缺点: 1 人项目不现实
* **B**: ADR + multi-file change checklist(选定)
  * 优点: 文档化决策 + 可执行清单
  * 缺点: 需要维护 checklist
* **C**: 自动化脚本(grep 旧版本号 → fail)
  * 优点: 自动化
  * 缺点: 仅能检测硬编码字符串,不能检测其他类型的多文件依赖
* **D**: 什么都不做,继续靠测试发现 fail
  * 优点: 0 成本
  * 缺点: 现状(3 天红灯)

## Decision Outcome

Chosen option: **B(ADR + multi-file change checklist)**,因为:

1. 跟 R1 ADR 仓库策略一致(每次重要变更先写 ADR)
2. checklist 形式可执行 + 可追溯
3. 跟 C(自动化)互补 — checklist 列出"检查什么",自动化负责"批量扫"

**Multi-file change checklist**(v3.0.9 适用):

```
[ ] 1. 写 ADR 在 docs/adr/000X-*.md 描述:
       - 改动的动机(为什么改)
       - 影响的文件清单(预期)
       - 影响范围(版本号、API、test、docs)

[ ] 2. 版本号变更时 (MAJOR.MINOR.PATCH bump), grep "3.0.X" 在以下位置:
       - emotion_spirit/_version.py
       - emotion_spirit/sylanne/__init__.py (内嵌 sylanne 自己也有版本)
       - metadata.yaml
       - public_api_stable.md
       - CHANGELOG.md (Unreleased 段)
       - README.md
       - tests/test_v300_integration.py (TestVersionConsistency 2 个 assert)
       - tests/test_public_api_markers.py (一致性测试)
       - docs/superpowers/specs/*.md (spec 文档)

[ ] 3. main.py 改动时, 跑全 suite 验证:
       - python -m pytest tests/ (Windows 本地)
       - 启动 AstrBot + 跑 1-2 个命令 (手动 smoke test)
       - 检查 `__new__` 风格的 test fixture 是否需要更新 attribute 列表

[ ] 4. 写 commit message 时包含:
       - "fix(scope): ..." 描述
       - body 列出 "Files changed" + "Tests added" + "Verification commands run"

[ ] 5. commit 前跑:
       - python -m pytest tests/ (本地 baseline)
       - 检查 secret scanner: pre-commit run --all-files

[ ] 6. push 后立刻:
       - 看 CI run 1 分钟内是否启动
       - 如果 5 分钟内 fail,立即修(不推迟)
```

### Positive Consequences

* **预防 80% multi-file drift**:版本号、API、test 同步是最高频错误源
* **5 分钟定位**:fail 时能立刻查 checklist 看哪步漏了
* **Onboarding 友好**:新贡献者看 ADR 知道流程
* **轻量级**:不增加 review 负担

### Negative Consequences

* **实施成本**:维护 checklist 需要纪律
* **不覆盖所有情况**:只能防"已知模式",新问题仍需 R1 ADR
* **可能冗余**:简单 patch(单文件)不需要完整 6 步

### Confirmation

* ADR 文档化 ✓
* 集成到 PR template(如果引入 PR)
* 未来 multi-file commit 引用本 checklist
* 验证:v3.1-alpha.1 (MemoryPool v2) 是第一个按本 checklist 跑的 release

## Detailed Checklist (备查)

### 版本号 bump checklist(最常用)

```bash
# 1. 找所有引用旧版本的位置
OLD="3.0.0"   # 当前
NEW="3.0.1"   # 目标

# 必须改:
emotion_spirit/_version.py
emotion_spirit/sylanne/__init__.py
metadata.yaml
public_api_stable.md
CHANGELOG.md
README.md

# 应该改 (但不一定):
docs/superpowers/specs/*.md
docs/superpowers/plans/*.md
docs/superpowers/reports/*.md

# 自动检测遗漏:
git grep "$OLD" 2>/dev/null
```

### main.py 改动 checklist

```bash
# 1. 检查所有装饰器 + 跟装饰器相关的测试
grep -n "@filter\." main.py

# 2. 找用了 __new__ 跳过 __init__ 的 test
grep -rn "EmotionSpiritPlugin.__new__" tests/

# 3. 找依赖 _config / _store / _persona_initialized 的内部方法
grep -n "self\._config\|self\._store\|self\._persona" main.py

# 4. 跑全 test suite
python -m pytest tests/ -v
```

### pre-commit 检查清单

```bash
# 1. secret scan
pre-commit run --all-files

# 2. pyproject.toml packages 列表
# (v3.0 加 bridge, R3 加 sylanne → 漏包 = wheel build 错)
grep -A 12 "tool.setuptools" pyproject.toml | head -15

# 3. .gitattributes export-ignore
git check-attr -a output/ verification/ tests/ | head
```

## Real-world Application

**本次 c3f6440 patch 失败 5 个位置**:
- `[X]` `_version.py` 改了 ✓
- `[X]` `metadata.yaml` 改了 ✓
- `[X]` `tests/test_v300_integration.py` 应该改但**没改** ❌
- `[X]` `public_api_stable.md` 应该改但**没改** ❌
- `[X]` `emotion_spirit/sylanne/__init__.py` 应该改但**没改** ❌
- `[X]` `tests/test_init_persistence.py` test fixture 应该更新但**没更新** ❌

**使用本 checklist 的预期结果**:
- 步骤 2 的 grep `$OLD` 立刻找到 5 个遗漏位置
- 步骤 3 的 `__new__` 检查发现 test_t2 缺 `_config`
- 整个 patch 在 push 前就修好,CI 0 fail

## Why / How to apply

**Why**:这次事故**3 天红灯 + 4 个 commit 失败 + 1 个本可避免的 _config bug**,完全是**没系统化扫"该改的地方"** 导致。

**How to apply**:
- 下次任何 multi-file change(more than 1 file) → 跑本 checklist
- 简单单文件 patch(1 file ≤ 10 lines)可以跳过完整流程
- 每次 v3.0.x → v3.0.y 强制用"版本号 bump checklist"
- 任何"`__new__` 风格的 test" 在 main.py 改动时强制跑 check

## Related

* [ADR-0001](0001-four-layer-directory.md) — 4 层目录(决定 test 在哪)
* [ADR-0003](0003-embed-sylanne-core.md) — sylanne 内嵌(因此 sylanne 自己有版本号)
* [ADR-0007](0007-pre-commit-secret-scan.md) — 防御层,本 ADR 是规划层
* [ADR-0008](0008-rename-sylanne-core-to-sylanne.md) — 重命名 R3 跟本 ADR 同一类 multi-file change, 本可以避免 v3.0.1 事故
* [[emotion-spirit-v301-astrbot-v425-patch]] — 失败的 patch
* [[emotion-spirit-secret-leak]] — 早期事故,本 ADR 是其变体
