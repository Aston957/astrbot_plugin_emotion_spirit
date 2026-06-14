# ADR-0007: pre-commit secret scan (vs CI-only)

* Status: ✅ Accepted
* Date: 2026-06-13
* Deciders: emotion_spirit team

## Context and Problem Statement

2026-06-09 发生 secret 泄露事故:`data/cmd_config.json` 包含 AstrBot admin 密码,被意外提交到公开仓库。
需要在工作流中加 secret 扫描,但放在哪里?

## Decision Drivers

* **早期发现**:commit 之前拦截 > push 后清理
* **开发摩擦**:太严格会让人绕过(例如 `--no-verify`)
* **覆盖率**:扫描所有可能位置(env, yaml, json, py 注释)
* **可信 allowlist**:开发者有时会故意提交测试 token,需要白名单

## Considered Options

* **A**: CI-only(GitHub Actions 跑 detect-secrets)
* **B**: **pre-commit hook**(本地 + CI 都跑 detect-secrets + .secrets-allowlist)← 选定
* **C**: IDE 插件(开发者主动配)

## Decision Outcome

Chosen option: **B**,因为:

1. **早期发现**:commit 之前就拦截,不污染 git 历史
2. **强制**:pre-commit hook 默认 `.git/hooks/` 装上,不能 `--no-verify` 绕过(因为 CI 也跑)
3. **可信 allowlist**:`.secrets-allowlist` 显式列出"测试用 token 是 OK 的",审查可见
4. **多工具组合**:detect-secrets(模式匹配) + gitleaks(常见模式)+ 自定义 hook(`data/cmd_config.json` 必须排除)
5. **事故案例验证**:2026-06-10 secret 泄露闭环后,这套机制 0 误报 + 0 漏报

### Positive Consequences

* 0 误报:allowlist 管理好,不会被"测试 token"反复警告
* 0 漏报:多工具组合覆盖率高
* 防御层完整:本地 + CI + .gitignore + template re-include

### Negative Consequences

* 新人需要装 pre-commit(`pip install pre-commit && pre-commit install`)
* 工具升级时偶尔会有新误报,需要更新 allowlist
* `.secrets-allowlist` 文件本身需小心(不能把真 secret 写进去)

### Confirmation

* `.pre-commit-config.yaml` + `.secrets-allowlist` 存在
* `pip install pre-commit` + `pre-commit install` 在 README 的"开发"章节
* GH Actions `ci.yml` 也跑 detect-secrets(双保险)

## More Information

* 实施于 2026-06-10(secret-leak 事故闭环)
* 事故详情: [[emotion-spirit-secret-leak]] memory
* 实施细节: filter-repo scrub 112 commits + pre-commit 防御层 + CI 验证
* v2.0.0v1 tag 实际安全(`e7b6146` 不含 secret)
