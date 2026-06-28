# Plan: emotion_spirit 技术债务 + 框架债务清理

## Context (为什么做这个)

经过 v1.0.0 → v1.1.0A → v1.1.0B → v1.1.0C → 2026-06-28 多轮快速迭代,插件累计了技术债和框架债。本次 (2026-06-28 session) 做了 schema 重排 (llm_tier 拆分 + 5 provider_id 真接进代码 + diary LLM 落地) 后,审计发现债务分两类:

1. **框架债** — 偏离了原 KB硬编码表 + @register DI + 功能分层 的设计原则
2. **技术债** — flaky 测试、死代码、漂移、文档不同步等

本 plan 目标: **把债务一次性清干净**,清完后才能 ship v1.1.0 (含 54 个未推送 commits)。

执行人: 小模型 (按本 plan 一步步执行,每步可独立验证)。

---

## 工作目录 (双仓库)

- **插件端 (生产,边改边验)**: `D:\astrbot\data\plugins\astrbot_plugin_emotion_spirit\`
- **源码端 (要 ship 的,最终对齐)**: `D:\新建文件夹\emotion_spirit\now\astrbot_plugin_emotion_spirit\`
- **AstrBot 运行**: `D:/python/python.exe -m astrbot.cli run` (在 `D:/astrbot`), WebUI http://localhost:6185, PID 动态
- **Python**: `D:/python/python.exe` (3.13, 必须)

**铁律**:
1. **改在插件端**, 改完逐文件 `cp` 同步回源码端
2. **每步做完跑相关测试**, 不堆到最后
3. **每步可独立 commit**, commit message 反映净变化
4. **secret scan** pre-commit 必过 (memory 提过 v2.0.0v1 secret leak 教训)
5. **改 migration 规则时**必须加新测试, 幂等

---

## 审计结论 (本 plan 的依据)

### 偏离信号清单

| # | 信号 | 严重度 | 是否真债 | 处理 |
|---|------|--------|----------|------|
| F1 | main.py 1559 行, 15+ 处直接 `self._xxx = SomeClass(...)` 绕过 @register DI | 中 | **半债** | 见 §F1 分析 |
| F2 | output→regulation/memory import 看似反向 | 低 | **假阳性** | 全是 TYPE_CHECKING 或正向依赖, 不动 |
| F3 | `data/cmd_config.json` 在源码端存在 | 高 | **待验证** | §E1 确认未入 git |
| T1 | `test_suggest_project_for_high_extraversion` flaky | 中 | **真债** | §T1 修 |
| T2 | diary_writer.py:218 `should_write()` 死方法 | 低 | **真债** | §T2 删 |
| T3 | diary LLM 耗时 33s (M2.7 reasoning) | 低 | **非债** | §T3 文档提示 |
| T4 | egg-info PKG-INFO:261 引用 manual_personas | 低 | **真债** | §T4 |
| T5 | 插件端 vs 源码端漂移 | 中 | **流程债** | §T5 sync 脚本 |
| T6 | `_feature_provider_id` 帮助方法在 main.py, 调用点使用 assistant `self._p._get_llm_callable` 不优雅 | 低 | **小债** | 保留, 不动 |

### §F1 分析 (DI 双轨并存)

**现状**:
- 全插件 48 个 `@register`, 但 main.py 里有 15+ 处 `self._xxx = SomeClass(self._modules["..."], ...)` 直接实例化
- 双轨的组件: `EngineManager`, `HotPoolForwarder`, `PersonalityBridge`, `RealtimeDispatch`, `RhythmLearner`, `SelfCore`, `ReflexLearnerStore`, `ReflexLearner`, `DreamGenerator`, `LifeAgent`, `ConscienceTracker`, `DiaryWriter` (本次新接线)

**为什么是半债不是全债**:
- `register()` 的 `_build_one` 用 `inspect.signature` + `param_wire` + `config_keys` 自动 wire, **能注入任何 init 参数包括 `llm_caller`** (只要把它列 config_keys 并在 build_modules 配置 params 里提供)
- 但 v1.1.0A/B 加的 RealtimeDispatch/RhythmLearner/SelfCore/DreamGenerator 当时为赶进度没纳入 DI, 后续也没补
- diary_writer 虽 @register 了 (provides=["DiaryWriter"]), 但 main.py 手 new 因为要传 `llm_caller` 和 `llm_enabled`

**决策**:
- **不建议本次大改 DI** — 风险高, 工作量大 (每个手 new 组件要适配 DI 形参匹配规则 + 调 build_modules 配置)
- **本次只做"标记债务"**: 在 main.py 每个 "手 new 应该走 DI 的组件" 加 `# TODO(tech-debt): 应该走 @register DI, 见 plan-2026-06-28-debt-cleanup` 注释, 让未来清理有锚点
- **真正接入 DI 留作 v1.2 工作** (单独 spec)

---

## 实施步骤 (按顺序, 每步独立 commit)

### §T1 修 flaky 测试 (低风险, 先做)

**文件**: `tests/regulation/test_project_manager.py`

**问题**: `test_suggest_project_for_high_extraversion` 断言 `assert project.category in ("physical", "creative")`, 但 `suggest_project` 在 extraversion 高时从候选随机抽样, 偶发返回 "intellectual", 触发断言失败。

**修法** (二选一, **推荐 B**):
- A) 放宽断言: `assert project.category in ("physical", "creative", "intellectual")` — 简单但弱化测试语义
- B) 看 `suggest_project` 源码, 理解 extraversion 高时**应该**返回哪几个 category, 把断言改成匹配真实意图, 并加注释说明为什么这些 category 都合规

**执行**:
1. Read `tests/regulation/test_project_manager.py` 找到 `test_suggest_project_for_high_extraversion`
2. Read `emotion_spirit/regulation/project_manager.py` 找 `suggest_project` 和 category 映射
3. 修断言 (B 方案), 加注释
4. 跑 `D:/python/python.exe -m pytest tests/regulation/test_project_manager.py -v` 5 次确认稳定
5. cp 到源码端
6. Commit: `fix(test): stabilize flaky test_suggest_project_for_high_extraversion assertion`

### §T2 删 should_write 死方法

**文件**: `emotion_spirit/output/diary_writer.py` (line 218-232 区域)

**问题**: `should_write(self) -> bool` 方法用 `DIARY_CONFIG["schedule_hours"]` 判断是否该写日记, 但本次 session 用 main.py `_schedule_diary_generation_loop` 接管了定时调度, `should_write` **没人调** (grep 验证过)。

**执行**:
1. `grep -rn "should_write" D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/` 确认 0 调用点 (只在 def 处)
2. 删 `should_write` 整个方法 (约 15 行)
3. 检查 `DIARY_CONFIG["schedule_hours"]` 是否还被其他代码读 — 若只剩 should_write 用, 保留 `DIARY_CONFIG` (硬编码 fallback 仍有用, main.py 读的是 config["diary"]["schedule_hours"], DIARY_CONFIG 是兜底)
4. 跑 `D:/python/python.exe -m pytest tests/test_diary_writer.py -v`
5. cp 到源码端
6. Commit: `refactor(diary): remove dead should_write method (scheduler moved to main.py)`

### §T3 diary 耗时 - 文档提示 (非代码改)

**文件**: `_conf_schema.json`, `README.md`, `docs/user-guide.md` (若有)

**问题**: 用户配 `diary.diary_provider_id = minimax/MiniMax-M2.7` (reasoning 模型), 生成日记 ~33s, 不是 bug 但体验上意料外。

**修法** (只加 hint, 不改代码):
1. `_conf_schema.json` 的 `diary.diary_provider_id` 字段 hint 加一句: "(reasoning 类模型生成较慢, 30s+ 正常; 若需快速可用 flash 类模型)"
2. README 配置表 diary 段加同样提示
3. cp 到源码端
4. Commit: `docs(diary): note that reasoning models take 30s+ for diary generation`

### §T4 清 egg-info PKG-INFO manual_personas

**文件**: `astrbot_plugin_emotion_spirit.egg-info/PKG-INFO` (line 261)

**问题**: PKG-INFO 是 `pip install -e .` 构建产物, 历史 commit 把 manual_personas 写进 README, 后 README 删了它 (本次 §E2 已删), 但 PKG-INFO 没重生所以还有引用。

**执行** (二选一):
- **A 推荐**: `cd D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit && D:/python/python.exe -m pip install -e . --no-deps` 重生 PKG-INFO
- B 手动 `sed -i '/manual_personas/d' astrbot_plugin_emotion_spirit.egg-info/PKG-INFO` (治标)

**还要做**: 检查 `astrbot_plugin_emotion_spirit.egg-info/` 是否应该 `.gitignore` — 构建产物本不该入 git
1. `cat .gitignore` 看是否含 `*.egg-info`
2. 若无, 加 `*.egg-info/` 到 .gitignore
3. `git rm -r --cached astrbot_plugin_emotion_spirit.egg-info/` (从 git 移除但保留本地)
4. Commit: `chore: gitignore egg-info build artifact (stale manual_personas ref auto-resolves)`

### §T5 写 sync 脚本防漂移

**问题**: 插件端 (`D:/astrbot/data/plugins/...`) 和源码端 (`D:/新建文件夹/...`) 长期不同步, 每 session 末手动 cp 易漏。

**修法**: 写一个 `tools/sync_plugin_to_source.py` 脚本 (放源码端 `tools/` 目录, 若无则建)

**脚本功能**:
- 列出要同步的文件清单 (whitelist)
- 对每个文件 `diff` 插件端 vs 源码端
- 输出有差异的文件列表
- 参数 `--apply` 执行 `cp` 覆盖

**whitelist 文件** (从历次 session 同步过的):
```
main.py
README.md
_conf_schema.json
emotion_spirit/output/commands.py
emotion_spirit/output/diary_writer.py
emotion_spirit/migrations/rules/v3_0_to_v3_1.py
tests/migrations/__init__.py
tests/migrations/test_split_llm_tier.py
```
(后续加新文件改在脚本里维护)

**执行**:
1. `mkdir -p D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit/tools/`
2. 写 `tools/sync_plugin_to_source.py` (Python 脚本, 用 `difflib` + `shutil`)
3. 跑一次 `D:/python/python.exe tools/sync_plugin_to_source.py` (无 --apply, 只 diff) 确认 0 差异 (此时两仓库应一致)
4. Commit: `chore(tools): add sync_plugin_to_source.py drift checker`

### §F1-a 标注 DI 双轨债 (仅加注释, 不真改)

**文件**: `main.py`

**问题**: 见 §F1 分析。本次不真改 DI 接入, 只加注释锚点。

**执行**:
对 main.py 里每个"应该走 @register DI 但手 new" 的组件, 在 `self._xxx = SomeClass(...)` 上一行加注释:
```python
# TODO(tech-debt): 本组件已 @register (见 emotion_spirit/<path>), 应走 plugin_factory DI
# 而非 main.py 手 new。本次 (2026-06-28) 保留手 new 因 llm_caller 运行时注入和
# init 顺序问题。v1.2 改走 DI。见 plan-2026-06-28-debt-cleanup §F1。
self._dream_generator = DreamGenerator(self._pool, MemorySampler(self._pool))
```

**要标注的组件** (grep 找到行号):
- EngineManager (main.py:298)
- HotPoolForwarder (main.py:299)
- PersonalityBridge (main.py:300)
- RealtimeDispatch (main.py:328)
- RhythmLearner (main.py:329)
- SelfCore (main.py:337)
- ReflexLearnerStore (main.py:347)
- ReflexLearner (main.py:348)
- DreamGenerator (main.py:354)
- LifeAgent (main.py:391)
- DiaryWriter (main.py:1383) — 本次新接线, 也加注释

**执行**:
1. 逐行加注释 (锚点 + v1.2 路标)
2. 跑测试确认注释不影响 (只改注释不会 break)
3. cp main.py 到源码端
4. Commit: `docs(tech-debt): anchor DI dual-track debt for v1.2 cleanup (§F1 of debt plan)`

### §E1 验证 secret 安全 + git 状态

**文件**: 整个源码端

**问题**: `D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit/data/cmd_config.json` (7862 bytes) 在源码端目录里。memory [[emotion-spirit-secret-leak]] 提过 v2.0.0v1 含 admin 密码的 scrub 事件。本次必须确认这个文件没被 git tracked。

**执行**:
1. `cd D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit`
2. `git ls-files data/cmd_config.json` — 输出为空表示未 tracked (好); 有路径表示 tracked (要 `git rm --cached`)
3. 同时 `git ls-files | grep -i "config.json\|secret\|password\|\.env"` 扫所有敏感文件
4. 若有 cmd_config.json tracked: `git rm --cached data/cmd_config.json` + 加 .gitignore
5. 确认 `.pre-commit-config.yaml` 存在 (memory 说 b6ed66c 加过 secret scanner)
6. Commit (若有改动): `security: ensure cmd_config.json not tracked (prevent secret leak v2)`

### §V 全套测试 + AstrBot 重启验证 (每步都做, 最后总验)

**每步做完**:
- 跑该步相关测试 (plan 里指定)

**全部清完后**:
```bash
# 1. 插件端全套
cd D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit
D:/python/python.exe -m pytest tests/ -q
# 期望: 106+ passed, 0 failed (本次基线 106)

# 2. 源码端全套
cd D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit
D:/python/python.exe -m pytest -q
# 期望: 和插件端一致 (或更多, 因 integration/ 可能有)

# 3. sync 脚本 0 差异
D:/python/python.exe tools/sync_plugin_to_source.py
# 期望: All files in sync

# 4. AstrBot 重启无报错
tasklist | grep python  # 找 PID
taskkill //PID <pid> //F
cd D:/astrbot && nohup D:/python/python.exe -m astrbot.cli run > astrbot.log 2>&1 &
sleep 10
grep -i "emotion_spirit.*init\|error\|traceback" D:/astrbot/astrbot.log | tail -10
# 期望: emotion_spirit initialized 正常, 无 Traceback

# 5. WebUI 核对
# 打开 http://localhost:6185 → emotion_spirit 配置 → 确认 15 段正常 (llm_tier 已删, sylanne/diary 新建)
```

---

## 执行顺序 (强约束)

1. **§T1** flaky 测试 → commit
2. **§T2** 删 should_write → commit
3. **§T3** diary 文档提示 → commit
4. **§T4** egg-info + .gitignore → commit
5. **§T5** sync 脚本 → commit
6. **§F1-a** DI 双轨注释 → commit
7. **§E1** secret 验证 → commit (若有改动)
8. **§V** 全套验证 (不 commit)
9. **然后才** ship (task 9: push 54 commits + tag + release + 提交市场)

---

## 不做 (明确 out of scope)

- 真正把 main.py 手 new 组件改走 @register DI — 留 v1.2 (§F1 只加注释锚点)
- 推 git / 打 tag / 发 release — 本 plan 清完债后才 ship
- 仪表盘独立 WebUI — 跟本次无关
- Phase 5+ / v3.1+ 新功能
- 推 sylanne_mode 配置项 (用户明确锁死 lite)

---

## 风险与回退

- **flaky 测试断言放宽可能弱化语义** — §T1 优先 B 方案 (理解真实意图再改), 不盲目放宽
- **删 should_write 可能有隐藏调用点** — §T2 删前必须 grep 0 调用点 (plan 已指定 grep 命令)
- **重生 PKG-_INFO 需 pip install -e .** — 若环境有问题 fallback 用 sed 删行
- **git rm --cached 若误删** — `git checkout HEAD -- <file>` 恢复 (但前提是未 commit)
- **secret scanner 卡 commit** — 若 pre-commit 拦截, 看 [[emotion-spirit-secret-leak]] 处理历史, 不要 --no-verify 绕过

---

## 验证总清单 (清完后逐项 ✅)

- [ ] §T1: 跑 project_manager 测试 5 次全过
- [ ] §T2: grep should_write 0 命中; diary_writer 测试过
- [ ] §T3: schema + README 含耗时提示
- [ ] §T4: PKG-INFO 无 manual_personas; .gitignore 含 *.egg-info/
- [ ] §T5: tools/sync_plugin_to_source.py 跑出 0 差异
- [ ] §F1-a: main.py 11 个组件有 TODO 注释锚点
- [ ] §E1: git ls-files data/cmd_config.json 输出空; .pre-commit-config.yaml 存在
- [ ] §V: 插件端 106+ passed; 源码端一致; AstrBot 重启无 Traceback; WebUI 15 段正常

清完这 7 项 + 验证全 ✅, 即可进 task 9 ship v1.1.0。