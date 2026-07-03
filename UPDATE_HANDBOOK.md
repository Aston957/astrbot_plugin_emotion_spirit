# emotion_spirit 更新手册 (Update Handbook)

> 本文件给**每个后续 session / 开发者**看。它不是宣言，是一份「要改这个插件时必须符合什么，以及违反了会被什么拦下」的可执行规约。
> **进 release zip** — 用户下载也会看到，所以保持措辞中性、不写 internal-only 的敏感细节（密码、内部 server 地址、未公开路线图）。
> 仓库内更深的开发文档在 `docs/`（不进 zip），那里放实验/历史/report。
>
> 当前版本: **v1.2.5** (正式 release, PR1+PR2+PR3 已 ship) | schema version: v4 | 状态: v1.2.5 正式 release 完成 (PR1 tag → `v1.2.5-rc.1`, PR2 tag → `v1.2.5-rc.2`, PR3 tag → `v1.2.5`). v1.2.6 backlog / v1.3 力学叙事层待规划。

---

## 0. 一句话总纲

**规则只有能被自动拦下才算规则。** 一条规约如果只能靠人记住，必将会被忘掉。所以本手册每一条都尽量绑定到一个会拦下你的钩子（pre-commit hook / 测试 / CI check / 运行时装饰器）。「应该」不算规约，「违反即 CI 红或 TypeError」才算。

---

## 1. 框架规则三件套

### 1.1 硬编码数据 → 进 KB，不进代码

**规则**：任何「可复用、可调、被多个 persona 共享的事实数据」——人格标签、标签映射、默认词库、阈值表——不写死在 `.py` 里，写进 KB。

**真实落法**：
- KB 文件：`emotion_spirit/core/kb/persona_labels_db.json`（2.74 MB，进 git 但 `.gitattributes` 标 `-diff`， regenerate 不爆 git log）
- Loader / API：`emotion_spirit/core/persona_labels_db.py`
  - `get_persona_labels_db()` 全量加载 + 缓存
  - `get_persona_labels(persona_id)` 单查
  - `export_persona_labels_db(path)` in-memory → JSON
- 再生脚本：`tools/regenerate_kb.py`（改了 KB 源要重跑这个，不是手编 JSON）

**违反会被什么拦下**：
- 目前**无自动拦截** —— 这是「应该」类，靠 review。建议未来加一个 lint：`grep` 出现在 `.py` 里、形如 `{"label": "...", "..."}` 的超过 N 项的 dict 字面量，标红提醒「这是不是该进 KB」。
- 间接拦：KB 改了但没重跑 `regenerate_kb.py` → 下次 KB regen 你的手改被覆盖。

**清债候选**：搜 main.py / 业务层里时长超过 ~10 项的硬编码映射表，逐个评估进 KB。

---

### 1.2 新功能组件 → `@register` + factory，禁止 main.py 手 `new`

**规则**：任何带 `__init__`、被装配进系统的功能组件，一律走 `@register` 自注册 + `plugin_factory.build()` 自动装配。**不在 main.py 里手实例化**。

**真实落法**：
- 注册装饰器：`emotion_spirit/core/registry.py` 的 `@register(provides=..., depends_on=..., param_wire=..., config_keys=...)`
- 模块规格：`ModuleSpec`（provides / depends_on / param_wire / config_keys / provides_classes）
- 自动 wire：`build()` 用 `inspect.signature` + `param_wire` 按依赖图装配，**加新模块不动 main.py**
- 入口：`main.py:95` 早已用 `build_modules()` = `plugin_factory.build()` 装配 28 模块

**当前违反样本（技术债现场）**：`grep -n "TODO(tech-debt): 本组件已 @register" main.py` 会列出 **12+ 处** —— 这些组件**已被 factory 装配了一份**（在 `self._modules` 里），main.py 又**手 `new` 了第二份**自己用。这就是「DI 双轨」。示例：`main.py:298` (engine_manager)、`:302` (hotpool_forwarder)、`:306` (personality_bridge)、`:337` (realtime_dispatch) 等。

**违反会被什么拦下**：
- 目前**无自动拦截** —— TODO 注释是人工提醒，不是 CI gate。
- 建议清单检查（可脚本化）：`grep -nE "self\._\w+ = [A-Z]\w*\(" main.py` 列出所有「main.py 里手 new 大写类」的位置，逐个对照该类是否已 `@register`。已 register 的就是违反。

**清债做法**（v1.2 计划，见 `docs/` 内 [[emotion-spirit-v12-design]]）：把 12 个手 new 的组件改成从 `self._modules` 取，删手 new。改完对应 TODO 一起删。

---

### 1.3 功能层划分 → 用 `layer.py` 装饰器，违反即 TypeError

**规则**：per-user 数据（某用户的亲密度、人格 shadow）方法标 `@per_user_only`；全局共享数据（KB、persona 列表）方法标 `@global_only`。**不许跨层访问**（Layer 2 业务层直接动 Layer 3 数据层的 per-user 状态）。

**真实落法**：`emotion_spirit/layer.py`
- `@per_user_only` —— 用 `inspect.signature.bind` **运行时强制** caller 传非空 `str user_id`，否则 `TypeError`
- `@global_only` —— 运行时拒绝方法定义带 `user_id` 参数
- 异常：`LayerViolationError(RuntimeError)`

**违反会被什么拦下**：**运行时立刻 TypeError** —— 这是本手册里唯一一条**已有强拦截**的框架规则。它是「可拦式规约」的标准样本：不用人记，挂了装饰器就生效。

**八层结构**（修订时别破坏分层）：
```
emotion_spirit/
  agents/      ← 自主智能体 (CognitiveAgent / EventBus / SelfCore / LifeAgent ...)
  bridge/      ← LLM 桥 (engine_manager / hotpool_forwarder / personality_bridge)
  core/        ← 核心+DI (registry / plugin_factory / knowledge / kb / persona_labels_db)
  memory/      ← 记忆系统 (intimacy / activity_history / decay_model / reflex_learner ...)
  regulation/  ← 调节 (dream_generator / superego_guard)
  output/      ← 输出 (diary_writer / realtime_dispatch / rhythm_learner)
  sylanne/     ← sylanne namespace 核心
  migrations/  ← 配置迁移 (registry / runner / rules/)
```

---

## 2. 技术债管理

### 2.1 TODO 标记格式

**规则**：发现债但本轮不清的，写 `# TODO(tech-debt): <现状> → <应该> (见 <文件/issue>)`。这样 `grep -rn "TODO(tech-debt)"` 能拉出全文债清单。

**真实落法**：main.py 内 12 个 `TODO(tech-debt): 本组件已 @register ... 应走 plugin_factory DI` 就是这个格式。

**违反会被什么拦下**：目前无拦截（TODO 不会让 CI 红）。但**约定值得遵守**：不写 TODO 直接堆手 new，等于把债藏起来。

### 2.2 何时清债

- **ship 阻塞类**（会让 CI 红 / 用户 crash / Release 发不出）：必须当轮清。
- **静默回归类**（用户开关被悄悄翻转 / 数据被丢但不报错，见 §3）：上架市场**之前**必须清（因为 0 用户期没影响，但一有用户就兑现）。
- **整洁度类**（命名 / 注释 / 双轨 DI）：可挂，但每个带版本变更的 release 都回扫一次。

---

## 3. 迁移纪律（schema 升级）

**背景**：迁移是**一次性、不可回溯**的。某字段在某次 `config.pop()` 里丢了，这个值从用户配置里**永久消失**，未来任何 rule 都补不回来——因为值本身没了。

### 3.1 真实现状：一个已知漏搬（2026-06-29 确认）

`emotion_spirit/migrations/rules/v3_1_to_v4.py` 的 `merge_life_sim_config`：
```python
config.pop("life_simulator", None)   # 旧段整段删
v2 = config.setdefault("life_sim_v2", {})
# 只搬了 enable_proactive_prompt
# ❌ enable_life_fragment 没搬 → 升级后兜默认 True
```
`main.py:259` 用 `life_sim_cfg.get("enable_life_fragment", True)` 兜默认。后果：v1.0.0 用户若显式设过 `enable_life_fragment=false`，升级后**被悄悄重开**。

**当前影响 = 0**（未上架、0 用户）。但要在**上架前**修。

### 3.2 迁移规则

- **`from_version == to_version - 1`** —— `registry.register_migration` 已 hard-check，违反即 `ValueError` 引导你写成正确步长。
- **重复 from_version 会都跑** —— `get_migrations()` 按 `from_version` 升序稳定排序，两条 3→4（`split_llm_tier` 在 v3_0_to_v3_1.py、`merge_life_sim_config` 在 v3_1_to_v4.py）会**串行都执行**，import 顺序决定先后。加新 rule 时注意别让两条同 from 的 rule 互相 `pop` 对方需要的段。
- **`pop` 旧段前先 `setdefault` 搬完所有用户可设字段** —— setdefault 幂等，多跑无害；但 pop 是删，删了就没了。
- **新 schema 必须给字段正式登记** —— 加新字段就在目标段的默认值兜底里 `setdefault` 它，并在 schema doc 写明。**别让某字段只在 main.py 的 `.get(key, default)` 里活着**——那就是 `enable_life_fragment` 的病根。
- **写迁移必配回归 test** —— `tests/migrations/test_rules_v*.py` 每个 rule 都有对应 test。新 rule 没测试 = CI 不会帮你抓漏搬。

### 3.3 enable_life_fragment 这条塞进哪版

按与用户约定（2026-06-29）：**下一个带 schema 变更的版本（v1.2 / v2.x）顺手修**。具体做法：
1. `merge_life_sim_config` 里加 `v2.setdefault("enable_life_fragment", old_life_sim.get("enable_life_fragment", True))`（需先 `old_life_sim = config.get("life_simulator", {})` 在 pop 前）
2. `life_sim_v2` schema doc 补 `enable_life_fragment` 字段说明
3. `tests/migrations/test_rules_v3_1_to_v4.py` 加 case：旧 config 含 `enable_life_fragment=false` → 迁后 `life_sim_v2.enable_life_fragment == False`

如果是 v1.1.x patch 就先不碰 schema，这条挂到下次带 schema 变更的 release。

---

## 4. ship / 版本纪律

### 4.1 版本号三源互比（已有强拦）

**规则**：tag / `_version.py` / `metadata.yaml.version` 三处必须一致；一致性测试**禁止钉死字面量**，必须做两源互比 + SemVer regex（否则第一次 bump 必破）。

**真实落法**：
- `tests/test_packaging.py` —— `TestVersionConsistency` 做两源互比 + SemVer，bump-proof
- `.github/workflows/release.yml:36-64` —— CI 跑 `tag == metadata == _version` 交叉检查
- 文件：`_version.py`、`metadata.yaml` 两处

**违反会被什么拦下**：**CI 直接红** —— bump 漏一处，release.yml 的 Verify version consistency 失败，release 不发。这是已生效的强拦。

### 4.2 release zip 内容由 `.gitattributes` 决定（已有强拦）

**规则**：进 zip 的唯一真相源是 `.gitattributes` 的 `export-ignore` 列表。`git archive` / `release.yml` 据此构建 slim zip。

**当前进 zip 的**：`main.py` + `emotion_spirit/` + `data/` + `metadata.yaml` + `_conf_schema.json` + `pyproject.toml` + `requirements.txt` + `README.md` + `LICENSE` + **本文件 (UPDATE_HANDBOOK.md)**
**被 export-ignore 掉的**：`tests/` `docs/` `tools/` `scripts/` `verification/` `output/` `conftest.py` `CHANGELOG.md` `STRUCTURE_REPORT.md` `public_api_stable.md` `dev-requirements.txt` `.github/`

**违反会被什么拦下**：
- **本文件会进 zip**（不在 export-ignore 列表）—— 所以写手册时措辞要中性感、不带 internal-only 细节。
- 想加新开发者-only 文件 → 别忘了在 `.gitattributes` 加 `export-ignore`，否则它会发给用户。
- 想强制保留某资产 → confirm 它**不在** export-ignore 里 + release.yml 的 `Verify zip contents` 会对内容做 sanity check。

### 4.3 带 secret 的资产永不进 zip（已有强拦 + 血教训）

**规则**：`data/cmd_config.json` 是 **AstrBot 平台级运行时配置**（含 admin 密码/白名单），**绝不进 zip**。任何「必须含 X」的 sanity check 都要先问「X 真的是插件资产吗」。

**真实落法**：
- `.gitignore` 拦未 tracked
- `git rm --cached` 让已 tracked 脱离
- `scripts/check_secrets.py` —— pre-commit hook（`.git/hooks/pre-commit` 调它）
- `release.yml` 对 zip 做 require-EXCLUDE 校验（不是 require-INCLUDE）

**违反会被什么拦下**：**pre-commit hook 三道闸**（.gitignore / git rm --cached / check_secrets.py），commit 阶段就拦。历史血教训见 `docs/` 内 secret-leak 记录。

### 4.4 ship 流程 checklist（每轮发版跑一遍）

1. `_version.py` + `metadata.yaml` 同步 bump（两源互比测试会抓漏）
2. 本地全套 `pytest`（Windows 上允许 `test_periodic_save_dirty_only` 概率性 1/3 fail，CI ubuntu 不红）
3. pre-commit secret scan 过
4. `git fetch origin && git rev-list HEAD..origin/main` 确认无 remote-only commit（有则 rebase，**绝不 force 覆盖**）
5. push 走 proxy（本机直连 GitHub 不通）：`git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 push origin main`
6. 打 tag `v*` 触发 `release.yml` 自动 build slim zip + 发 Release
7. **到 https://github.com/Aston957/astrbot_plugin_emotion_spirit/actions 验 Release 真出了**（这步 AI 做不了，必须人看）
8. 若 ship-prep 修复在打 tag 之后才进 main → tag 已过时，需 force 重打 tag 指向新 commit（已用过一次：v1.1.0 54bc65b → 652b58b；v1.2.5 PR1 `830b600` → `3dd9c7d` → `99ef2fa` force 重打 3 次）。**优先选打新 patch tag**，force 重打是最后手段且会改变已下载用户的语义。

### 4.5 ship 阻塞常见模式（v1.2.5 PR1 血教训 4 条）

下面 4 条是 v1.2.5 PR1 ship 时**连续撞**的 4 个 release 阻塞，**每个都强制修了新 commit 才 ship**。下个 PR ship 前先扫一遍这 4 条，能省 30 分钟 + 3 个 force retag。

#### 4.5.1 Plan 必须跟 release workflow 协同设计

**症状**：plan 说 "PR1 用 `v1.2.5-rc.1` tag"，但 `.github/workflows/release.yml` 的 `Verify version consistency` 步骤写死 `TAG_VERSION == PY_BASE`，对 rc suffix 直接红。

**根因**：plan 跟 release.yml 是**两份独立设计**，没人协同 review。release.yml 设计时只考虑了 `v1.0.0` → `1.0.0` 一对一，没考虑 prerelease suffix 场景。

**预防**：
- **Plan ship 章节 + release.yml 一起 review**，确认 tag 命名规则两边都覆盖
- 若 plan 用 rc tag，release.yml 必须支持 `TAG_BASE` 比较（剥掉 `-rc.N` / `-beta.N` / `-alpha.N` 后缀）
- **真实落法（已 ship v1.2.5 PR1 830b600）**：
  ```bash
  TAG_BASE=$(echo "${TAG_VERSION}" | sed -E 's/-(rc|beta|alpha)\.[0-9]+$//')
  # 比较 TAG_BASE 而非 TAG_VERSION
  ```

#### 4.5.2 CI flake 用产品代码 fallback > 测试 mock time

**症状**：`test_v2_full_lifecycle` 在本地 5 跑 5 PASS，CI 5 矩阵格里 1 格（Python 3.11 × AstrBot 4.14.6）持续红。

**根因**：`build_schedule_context(now=time.time())` 默认查**当前时段**的 planned 事件。CI runner 跑得稍慢/早，plan 生成时段（morning）跟 context 查询时段（night）错配 → 返回空字符串 → `assert context` 失败。

**预防**：
- **产品代码 fallback > 测试 mock time**：让 `build_schedule_context` 在 `current_events` 为空但 `all_planned` 不空时，自动 fallback 展示今日全部计划（按时段顺序）。这样 CI 永远不因时段错配失败，**用户体验也更好**（用户查不在活动时段也能看到今天的全部安排）。
- **真实落法（已 ship v1.2.5 PR1 3dd9c7d）**：
  ```python
  if current_events:
      # 正常路径
      ...
  else:
      # Fallback: 当前时段无 planned 事件 → 展示今日全部 planned
      all_planned = [e for e in self._current_plan.events if e.status == "planned"]
      if all_planned:
          all_planned.sort(key=lambda e: _SLOT_ORDER.get(e.time_slot, 99))
          activities = ", ".join(f"{e.time_slot}{e.activity}" for e in all_planned)
          parts.append(f"今天计划: {activities}")
  ```
- mock time 是 test-side fix，**只让测试 PASS**；产品代码 fallback 是 behavior fix，**让所有 caller 受益**。

#### 4.5.3 gh CLI 在 GitHub Actions runner 上不可靠

**症状**：cleanup step 用 `gh release delete <tag> --yes`，但 log 显示 "Using release 348423945 for tag v1.2.5-rc.1" → 说明 cleanup **没真删掉**，旧 release 还在 → softprops finalize 撞 `already_exists`。

**根因**：GitHub Actions 默认 `GITHUB_TOKEN` 对 `gh` CLI 子命令的支持有限。`gh release delete` 需要显式 `id_token: write` 或其他权限才能稳定运行，但 standard `contents: write` 不够。

**预防**：
- **永远用 `curl` + REST API，不用 `gh` CLI 在 workflow 里做 destructive 操作**
- REST API 直接 DELETE `/repos/{owner}/{repo}/releases/tags/{tag}`，稳定可靠
- **真实落法（已 ship v1.2.5 PR1 99ef2fa）**：
  ```yaml
  - name: Clean up previous release for this tag (force-retag safe)
    env:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    run: |
      TAG="${GITHUB_REF#refs/tags/}"
      # Delete published release (REST API, 比 gh CLI 在 runner 上更可靠)
      curl -s -o /dev/null -w "%{http_code}" \
        -X DELETE \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/${GITHUB_REPOSITORY}/releases/tags/${TAG}"
      # Delete all drafts for this tag (list API + filter + delete each)
      DRAFT_IDS=$(curl -s \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        "https://api.github.com/repos/${GITHUB_REPOSITORY}/releases" \
        | python3 -c "import json,sys; rs=json.load(sys.stdin); print('\n'.join(str(r['id']) for r in rs if r.get('tag_name')==\"${TAG}\" and r.get('draft')))")
      for RID in ${DRAFT_IDS}; do
        curl -s -o /dev/null \
          -X DELETE \
          -H "Authorization: token ${GITHUB_TOKEN}" \
          "https://api.github.com/repos/${GITHUB_REPOSITORY}/releases/${RID}"
      done
  ```

#### 4.5.4 Force retag 必须 workflow 自动清理（不能依赖手工）

**症状**：force 重打 tag 时旧 release 还在 → softprops 试图 update existing release → finalize 撞 `already_exists` → 3 次 retry 全失败 → release workflow 红。

**根因**：softprops `action-gh-release@v2` 的 finalize 步骤对 existing release 处理有 bug —— 它 retry 时还是撞 already_exists，没 fallback 到 create-new。

**预防**：
- **Force retag 必须在 workflow 里 hardcoded 自动 cleanup**，**绝不依赖手工 `gh release delete`**（手工可能漏 draft, draft 会 shadow published release）
- cleanup step 必须放在 `Create GitHub Release` 步骤**之前**，且能删 published + draft 两种 release
- **真实落法**：见 §4.5.3 的 cleanup step 模板
- **Force retag 决策树**：
  1. 打新 patch tag（`v1.2.5-rc.2`）— 跟现有 `v1.2.5-rc.1` 共存，无 cleanup 风险
  2. 必须 force 重打同一 tag（如 PR ship-prep fix 在打 tag 后才进 main） → **必须** workflow 里硬编码 cleanup step + curl REST API

---

## 5. 每个新 session 的 30 秒上手

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git status --porcelain           # 工作树干净?
git rev-parse HEAD               # 当前 commit
git rev-list --left-right --count HEAD...origin/main   # 0/0?
git tag -l                       # 现有 tag
grep -rn "TODO(tech-debt)" main.py  # 当前债清单
pytest -x 2>&1 | tail -5         # 测试基线
```
然后读本文件 + 你要碰的那层的现有代码模式。**不照本文件的规约改代码 = 积债。**

---

## 6. 现存清债清单（2026-07-03 快照, v1.2.5 PR1 后）

| 债 | 类型 | 影响 | 何时清 |
|---|---|---|---|
| CognitiveAgent 4 子类仍手 new (MemoryAgent/PersonalityAgent/RelationshipAgent/LifeAgent) | 框架债务 | 当前 0 用户无影响；清爽度 | **v1.2.6 backlog** |
| factory `param_wire` 只能 `dep_name → param_name` 1:1,不能表达 `self_core.bus` 属性提取 | 框架底层限制 | 阻断上面 4 个 Agent 进 DI | **v1.2.6 backlog** |
| `CommandImpl` / `SurfaceHandler` 仍手 new (需 plugin 自身注入) | 设计债 | 0 用户无影响 | **v1.2.6 backlog** |
| `test_periodic_save_dirty_only` Win 概率性 fail | 测试维护 | 仅 Win 本地，CI 不红 | 可挂 |
| 硬编码映射表是否该进 KB（无 lint） | 框架债务 | 潜在 | 有空回扫 |
| `_reset_superego_modules` 手 new 5 个 superego sub-classes | 设计债 | ✅ **v1.2.5 PR3 已清** | 见 PR3 提交 `be3afa5` / `d2fa561` |
| `merge_life_sim_config` 漏搬 `enable_life_fragment` | 迁移静默回归 | ✅ **v1.2.5 PR3 已清** | 见 PR3 提交 `55dc010` |
| `test_v2_full_lifecycle` wall clock 跟 `_time_to_slot` 偶发不对齐 | ✅ **v1.2.5 PR1 已清** (commit `3dd9c7d`) | 已 ship | 见 §4.5.2 — 产品代码 fallback 比 mock time 更 robust |

### v1.2.5 PR1 已清的债 (2026-07-03, ✅ SHIPPED as v1.2.5-rc.1)

**主要功能 (11 commits)**:
- ✅ Bug 12: 分段回复 100% 不工作 (`_on_segmented_reply` yield 被 await → TypeError 静默吞) — 改为 `_on_segmented_reply_v2` 主动 send 投递
- ✅ Bug 12b: emotion_spirit 投递架构调整 (主动 send + 清空 `llm_resp`)
- ✅ 流式模式 (`streaming_response=true`) 跳过 emotion_spirit 分段投递, 不再与 AstrBot 流式冲突
- ✅ v1.2.4 阶段 56+v1.2.3=57 模块架构继承, 无新模块 (PR1 纯方法级)
- ✅ public_api_stable.md 同步到 v1.2.5, 无 stable API 变更
- ✅ tests: **1299 passed** (新增 38: silence_tendency 20 / delay_strategy 5 / on_llm_response_segmented 2 / conf_schema_v125 3 / commands_reflect 7 / life_simulator_fallback 1)

**Ship 阻塞 fix (4 commits, 写入 §4.5)**:
- ✅ release.yml rc/beta/alpha suffix 支持 (commit `830b600`, 见 §4.5.1)
- ✅ `build_schedule_context` fallback (commit `3dd9c7d`, 见 §4.5.2) — **提前 PR3 T7 产品侧 fix**, 测试侧 mock time 不再需要
- ✅ release.yml cleanup step (commit `e717aef` + `99ef2fa`, 见 §4.5.3 + §4.5.4) — 用 curl REST API 而非 gh CLI, force retag 不再撞 softprops

### v1.2.5 PR2 已清的债 (2026-07-03, PR2 READY → SHIP as v1.2.5-rc.2)

**主要功能 (DefenseModulator L1+L2 完整耦合)**:
- ✅ 新增 `DefenseModulator` 模块 (`@register`, 4 depends_on): 统一管理压抑/崩溃/沉默与力学的耦合
- ✅ L1 输入调制: `SuppressionState.compute()` / `CollapseArchetypeSelector.compute_bas_bis()` / `SegmentedReplyCoordinator.compute_silence_tendency()` 都接受 `force_state` 可选参数 (向后兼容 100%)
- ✅ L2 输出回写: `DefenseModulator.apply_event("silence" | "collapse" | "suppression", intensity)` 从 KB `defense_deltas.json` 读 delta, 调 `force_dynamics.shift()`
- ✅ `ForceDynamics.shift()` 新增 (累积偏移状态, v1.3 L3 fixpoint 复用)
- ✅ `CollapseArchetypeSelector.compute_bas_bis()` 3-tuple 化: 返回 `(BAS, BIS, collapse_tendency)` + 同步修 `select()` 解构
- ✅ KB `defense_deltas.json` 新增 (handbook §1.1: 系数全从 KB 读)
- ✅ main.py 集成: `_init_life_and_agents` 加 `self._defense_modulator`, `_on_segmented_reply_v2` 用 DefenseModulator 统一入口 + 沉默触发后 `apply_event("silence")`
- ✅ 模块数 57 → 58 (+DefenseModulator), `force_dynamics.compute()` 签名不变 (向后兼容 100%, handbook §1.2)

**测试**:
- `test_defense_modulator.py`: 18 个测试 (DefenseStates dataclass 5 + KB 3 + compute_defense_states 4 + apply_event 4 + main.py 集成 2)
- `test_suppression.py`: 4 个 L1 测试
- `test_collapse_archetype.py`: 5 个 L1 + 连续化测试
- `tests/regulation/test_collapse_archetype.py`: 3 处解构修复 (2-tuple → 3-tuple)
- 全测: **1326 passed**, 0 regression

### v1.2.5 PR3 已清的债 (2026-07-03, ✅ SHIPPED as v1.2.5)

**主要功能 (顺手清债 + Bug 13/14 修复)**:
- ✅ T1 `merge_life_sim_config` 补搬 `enable_life_fragment` (handbook §3.3 P0) — 提交 `55dc010`
- ✅ T2 `_reset_superego_modules` 双轨消 (走 `_modules["superego"]` 单点重建, handbook §1.2 P1) — 提交 `be3afa5`
- ✅ T2 扩展: `initialize()` 也复用 `_rebuild_superego_subdict()`, 修同样双轨 bug — 提交 `d2fa561`
- ✅ T3 + T4: main.py 10 个模块走 `self._modules[...]` 装配 (PublicAPI + 9 memory/output), 删手 new — 提交 `d2fa561`
- ✅ Bug 13 `datetime.date.today()` / `datetime.date.fromtimestamp()` AttributeError 修 (line 846 + 1004) + AST guard — 提交 `e93093c`
- ✅ Bug 14 `polish_template_events` 嵌套 dict TypeError 修 (加 `_flatten_personality()` helper) + `_get_current_personality_dict()` type hint 改真实 shape — 提交 `401ba52`
- ✅ 模块数保持 58 (PR2 已 +DefenseModulator)

**测试**:
- `test_reset_superego_modules.py`: 4 个 (AST 直赋检查 + ConscienceTracker import + modules dict 重建 + identity 同步)
- `test_main_py_no_manual_new.py`: 4 个 (AST 扫描 + T4 回退 + PublicAPI + initialize)
- `test_datetime_import_patterns.py`: 1 个 AST 静态检查
- `test_schedule_plan_loop.py`: 2 个行为测试
- `test_life_simulator_personality_flatten.py`: 6 个 (flatten helper + 集成)
- `test_personality_shape_contract.py`: 2 个 AST 静态检查
- 全测: **1348 passed**, 0 regression (仅 1 个预存 Win 概率性 `test_periodic_save_dirty_only` 可能 flake, 不在 CI 阻塞)

**Ship 决策**:
- PR3 tag: `v1.2.5` (正式 release, PR1+PR2 用 `-rc.X` 试水完成)
- 首次正式 release 自 v1.2.4, 一次过无 force retag (PR1 4 ship 阻塞 fix 全部 cover)

### v1.2.5 PR3 仍未清的债 (v1.2.6 backlog)

- (同 §6 主表) CognitiveAgent 4 子类仍手 new (MemoryAgent/PersonalityAgent/RelationshipAgent/LifeAgent) — 需 factory `param_wire` 扩展
- (同 §6 主表) factory `param_wire` 1:1 限制 (self/属性提取)
- (同 §6 主表) `CommandImpl` / `SurfaceHandler` 仍手 new (需 plugin 自身注入)
- (同 §6 主表) `test_periodic_save_dirty_only` Win 概率性 fail
- ~~(同 §6 主表) `test_v2_full_lifecycle` wall clock 偶发不对齐~~ — **v1.2.5 PR1 已清 (3dd9c7d)**
- (同 §6 主表) 硬编码映射表是否进 KB

### v1.2.1 已清的债 (供下次 session 验证不在 regression)

- ✅ main.py 12 处 DI 双轨 (v1.2 diary_writer + v1.2.1 force_dynamics/DreamGenerator/ReflexLearner(×2)/EngineManager/HotPoolForwarder/PersonalityBridge/RealtimeDispatch/RhythmLearner/SelfCore/LifeSimulatorV2)
- ✅ 7 处假 TODO(tech-debt) 注释 (TODO 文案说 @register 但实际没) — 现都补了真 @register spec
- ✅ 1 处隐藏违规: `LifeSimulatorV2` 无 @register (plan §0 提到但漏写 TODO 注释) — 已补 spec
- ✅ `ghosts=0`: force_dynamics + body_state 不再是 ghost (被 main.py 消费)

---

**这份手册本身也是规约：发现规约与代码现状不符，改代码或改手册，二选一，不许两边各说一套。**