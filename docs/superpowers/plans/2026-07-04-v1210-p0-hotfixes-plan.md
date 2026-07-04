# v1.2.10 — 3 P0 hotfixes (fresh-install blockers) — 执行 plan

> **写给执行模型**: 本文件是 self-contained spec, 不需要读 feedback 原文. 3 个 bug 已对 v1.2.9 代码验证过 (file:line 见下). 你只负责实现 + 测试 + ship, 不要重新质疑 bug 是否属实. 范围决策已由 Aston 锁定 (§2), 不要改.
>
> **dev tree**: `D:\新建文件夹\emotion_spirit\now\astrbot_plugin_emotion_spirit` (git, branch `main`, HEAD `d7021b5` = v1.2.9, clean).
> **当前版本**: 1.2.9 (四源: `_version.py` / `metadata.yaml` / git tag / `CHANGELOG.md`).
> **约定**: 项目 release 直接 commit 到 `main` (v1.2.7/8/9 都这样), 不开 branch. ship 流程: commit → tag `v1.2.10` → push → `release.yml` 自动 build zip + GitHub Release.

---

## §1 背景 + 根因 (为什么要修)

v1.2.9 shipped (1367 tests 绿, `release.yml` 绿), 但 **fresh-install 路径 (`pip install .` → wheel → site-packages) 有 3 个 P0**, 任何用户升级 v1.2.9 都会撞. 反馈者在 Docker 部署 `pip install .` 撞全部 3 个.

**3 个 P0 漏网的共同根因 = CI 测的路径 ≠ 用户装的路径**:
- `ci.yml` test job 用 `pip install -e` (editable) — KB JSON 永远在源码树里, `_modules` 在测试里被 mock (public_api key 永远在) → 碰不到 Bug-A / Bug-C.
- `release.yml` 用 `git archive` build zip — zip 含全量 git-tracked 文件, KB JSON 在里面 → 碰不到 Bug-A.
- **没有任何 CI 走非 editable `pip install .`** → wheel packaging 盲点.

所以 v1.2.10 除 3 个 fix 外, **必须补一条 wheel-install smoke CI job** (§3.4), 否则下个 release 还会漏.

---

## §2 范围决策 (Aston 已锁定, 不要改)

| 决策 | 选择 | 理由 |
|---|---|---|
| 发布方式 | **All 3 in single v1.2.10** | 3 fix 都小~中等, 一次 release |
| Bug-B LLM-off 行为 | **Skip (不记日记)** | 0 篇真日记 > 12 篇假 prompt 复读机 |
| scheduled loop 同病 | **v1.2.10 一起修** | `main.py:973-978` LLM-off 也存 prompt, 同 anti-pattern, 一并 skip |

---

## §3 三个 fix (按 file:line 给精确改动)

### §3.1 Bug-A — KB JSON 没进 wheel

**根因**: `core/kb/` 是 data dir (无 `__init__.py`), `packages.find` 只控制哪些**目录**进 wheel, 不控制 data 文件; `package-data` 只列了 `py.typed`, KB JSON 被排除. `persona_labels_db.py:449` 用 `Path(__file__).parent / "kb"` 加载, wheel 装到 site-packages 后该目录不存在 → `FileNotFoundError` → `segmented_reply` 静默 fallback.

**改 `pyproject.toml` (line 56-57)**:

before:
```toml
[tool.setuptools.package-data]
emotion_spirit = ["py.typed"]
```

after:
```toml
[tool.setuptools.package-data]
emotion_spirit = [
    "py.typed",
    # Bug-A (v1.2.10): KB 数据必须进 wheel. core/kb/ 是 data dir (无 __init__.py),
    # packages.find 只控制哪些目录进 wheel, 不控制 data 文件; 必须显式 package-data,
    # 否则 pip install . 后 wheel 缺 KB → runtime FileNotFoundError (v1.2.9 fresh-install P0).
    "core/kb/*.json",
    # sylanne subpackage 的 py.typed (同病, 顺手补).
    "sylanne/py.typed",
]
```

**改 `tests/test_packaging.py`** — 文件末尾追加 2 个 test:
```python
def test_kb_json_in_package_data():
    """Bug-A (v1.2.10): core/kb/*.json 必须在 package-data.

    core/kb/ 是 data dir (无 __init__.py), packages.find 不会拉它的 JSON.
    若漏列 package-data, pip install . 构建的 wheel 会缺 KB JSON,
    runtime persona_labels_db.get_silence_tendency_weights() → FileNotFoundError.
    (v1.2.9 fresh-install P0, CI 用 editable install 测不到, 由 wheel-install-smoke job 兜底.)
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    pkg_data = (
        data.get("tool", {})
        .get("setuptools", {})
        .get("package-data", {})
        .get("emotion_spirit", [])
    )
    assert isinstance(pkg_data, list), f"package-data 应为 list, 实际 {type(pkg_data)}"
    assert "core/kb/*.json" in pkg_data, (
        f"core/kb/*.json 不在 package-data (Bug-A): {pkg_data} — "
        "pip install . 会漏 KB JSON, runtime FileNotFoundError"
    )


def test_kb_json_files_exist_in_source():
    """Bug-A 配套: 源码树里 3 个 KB JSON 必须存在 (wheel 打包的前提)."""
    kb_dir = REPO_ROOT / "emotion_spirit" / "core" / "kb"
    for name in ("persona_labels_db.json", "silence_tendency_weights.json", "defense_deltas.json"):
        assert (kb_dir / name).is_file(), f"KB 源文件缺失: {kb_dir / name}"
```

### §3.2 Bug-C — public_api 失注册 KeyError

**根因**: `main.py:108` `self._public_api = self._modules["public_api"]`, 但 `output/public_api.py:20` `class PublicAPI:` **没加 `@register`** (v1.2.5 PR3 T3 改了 main.py 却漏加装饰器). 全仓 49 个 `@register`, PublicAPI 不在其中 → `_modules` 没 `public_api` key → KeyError → plugin 装不上, 18 个 command handler 全 404.

> **⚠ Gotcha (不要踩)**: 反馈原报告建议给 PublicAPI 加 `@register(name="public_api", provides=["PublicAPI"], depends_on=[])` — **这是错的**, 不要这么改. 原因: `PublicAPI.__init__(self, modules: dict)` 吃**整个 modules dict** (facade 模式, 内部 `self._modules.get("surface_consumer")` 按需取). 但 `registry._build_one` (`registry.py:205-271`) 只把 `depends_on` 每个 dep 作**单个 kwarg** 注入, **没有路径传整个 `instances` dict**. `depends_on=[]` → 工厂调 `PublicAPI()` 零参 → `TypeError: missing 'modules'` (从 KeyError 变 TypeError, 没修好).
>
> **正确修法 = 回退 facade 手 new** (反馈的方案 2). PublicAPI 是 facade, 同 `CommandImpl` / `SurfaceHandler` / `LifeAgent` 一样手 new (第 4 处, v1.3 factory `param_wire` 扩展后才能真 @register).

**改 `main.py` (line 106-108)**:

before:
```python
        # ═══ 2. 公开 API 网关 ═══
        # v1.2.5 PR3 T3: 走 _modules 装配, 删手 new
        self._public_api = self._modules["public_api"]
```

after:
```python
        # ═══ 2. 公开 API 网关 ═══
        # Bug-C (v1.2.10): PublicAPI 是 facade (吃整个 modules dict),
        # 不走 @register — factory 只注入单个 dep, 无路径传整个 instances dict
        # (v1.2.5 PR3 T3 漏加 @register → KeyError). 手 new, 同
        # CommandImpl/SurfaceHandler/LifeAgent 第 4 处 (v1.3 factory param_wire 扩展).
        self._public_api = PublicAPI(self._modules)
```

`main.py:30` 已有 `from emotion_spirit.output.public_api import PublicAPI`, 无需新 import.

**改 `tests/test_registry_liveness.py`** — 文件末尾追加:
```python
def test_public_api_is_facade_not_registered():
    """Bug-C (v1.2.10): PublicAPI 是 facade, 不应 @register.

    PublicAPI.__init__ 吃整个 modules dict, factory 的 depends_on 单 dep 注入模型
    不适用 (会 TypeError). 防 v1.2.5 PR3 T3 半截 @register 重演.
    手 new 走 test_no_hidden_manual_new 的 allowed 列表 (已含 _public_api).
    """
    import emotion_spirit  # noqa: F401 — trigger @register side effects
    registry = ModuleRegistry.get_all()
    assert "public_api" not in registry, (
        "PublicAPI 不应 @register (facade 吃整个 modules dict, factory 注入不了) — "
        "见 main.py self._public_api = PublicAPI(self._modules) 手 new"
    )
```

> 现有 `test_no_hidden_manual_new` (line 54-80) 的 `allowed` 集合 (line 77-78) **已含 `_public_api`**, 无需改. 现有 `test_every_register_is_consumed` 自动跳过 (PublicAPI 没 @register).

### §3.3 Bug-B — 日记存 prompt 模板 + scheduled loop 同病

**根因**: `surface_handler.py:207` 把 `build_superego_reflection_prompt()` 的返回值 (LLM prompt 模板字符串) 直接 `record_diary()` 当正文存, 没调 LLM. `consume()` 是 sync (从 SylannEngine `_on_surface` sync callback 调, `main.py:1123-1131`), 不能 `await`. 12 篇日记全是同一个 prompt 模板 → 复读机. `main.py:973-978` scheduled loop LLM-off 分支同病.

**架构**: mirror 现有 `_schedule_diary_generation_loop` (`main.py:927-987`) 的后台 `asyncio.ensure_future` worker 模式. sync `consume()` 推队列, async worker 跑 LLM.

> **⚠ Gotcha**: 反馈原报告说 "worker 调 `generate_diary_llm()` 用 prompt 作种子" — **不行**. `generate_diary_llm()` (`diary_writer.py:256`) **不接受外部 prompt**, 它内部自己调 `build_diary_prompt(diary_type)` 走通用路径, 跟 `build_superego_reflection_prompt` (带 tension + conflict_values 的富上下文) 是两条独立 prompt 链. 所以要**新加** `generate_reflection_llm(prompt)` 方法直接调 `_llm_caller`.

**改 1 — `main.py` `__init__`, 在 line 127 `self._inject_queue = []` 之后加**:
```python
        # Bug-B (v1.2.10): superego reflection 队列 (sync consume 推, async worker 消费).
        self._diary_reflection_queue: list[tuple[str, list[str], str]] = []  # (tension, conflict_values, user_id)
```

**改 2 — `emotion_spirit/output/surface_handler.py` (line 203-211)**:

before:
```python
                if self._p._diary:
                    reflection_prompt = self._p._diary.build_superego_reflection_prompt(
                        dominant_tension, conflict_values,
                    )
                    self._p._diary.record_diary(reflection_prompt, "superego_reflection", user_id=user_id)
                    logger.info(
                        "emotion_spirit: superego reflection diary recorded for user=%s",
                        session_id[:8],
                    )
```

after:
```python
                # Bug-B (v1.2.10): 不再直接 record prompt 模板 (复读机).
                # LLM-on → 推队列, 后台 worker 调 LLM 生成正文再 record.
                # LLM-off → 不入队 (skip, 0 篇 > 12 篇假).
                if self._p._diary is not None and getattr(self._p._diary, "_llm_enabled", False):
                    self._p._diary_reflection_queue.append((dominant_tension, conflict_values, user_id))
                    logger.info(
                        "emotion_spirit: superego reflection enqueued (user=%s)",
                        session_id[:8],
                    )
```

**改 3 — `main.py` 新方法**, 放在 `_schedule_diary_generation_loop` (line 987 结束) 之后. 为可测, 拆成 helper + loop:
```python
    async def _process_one_reflection(self, tension: str, conflict_values: list[str], user_id: str) -> None:
        """Bug-B (v1.2.10): 处理 1 个 superego reflection 队列项 → LLM 生成日记正文."""
        if self._diary is None:
            return
        try:
            prompt = self._diary.build_superego_reflection_prompt(tension, conflict_values)
            text = await self._diary.generate_reflection_llm(prompt)
            if text:
                self._diary.record_diary(text, "superego_reflection", user_id=user_id)
                self._save_if_dirty()
                logger.info(
                    "emotion_spirit: superego reflection LLM 日记已生成 (user=%s, %d 字)",
                    user_id[:8], len(text),
                )
        except Exception:
            logger.warning("emotion_spirit: superego reflection 生成失败", exc_info=True)

    async def _drain_diary_reflection_loop(self) -> None:
        """Bug-B (v1.2.10): 后台消费 superego reflection 队列 (mirror _schedule_diary_generation_loop)."""
        while True:
            try:
                if self._diary_reflection_queue:
                    tension, conflict_values, user_id = self._diary_reflection_queue.pop(0)
                    await self._process_one_reflection(tension, conflict_values, user_id)
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("emotion_spirit: superego reflection drain 异常", exc_info=True)
                await asyncio.sleep(10)
```

**改 4 — `main.py` `initialize()`, 在 line 810 `asyncio.ensure_future(self._schedule_diary_generation_loop())` 之后加**:
```python

        # Bug-B (v1.2.10): superego reflection 队列后台 worker
        asyncio.ensure_future(self._drain_diary_reflection_loop())
```

**改 5 — `emotion_spirit/output/diary_writer.py` 新方法**, 放在 `generate_diary_llm` (line 274 结束) 之后. **完全 mirror `generate_diary_llm` 的 try/except + `_llm_enabled` gate**:
```python
    async def generate_reflection_llm(self, prompt: str) -> str | None:
        """Bug-B (v1.2.10): 用 LLM 把 superego reflection prompt 生成日记正文.

        与 generate_diary_llm 不同: 本方法接受外部已构建的 reflection prompt
        (build_superego_reflection_prompt, 带 tension + conflict_values 富上下文),
        不自己 build_diary_prompt. 失败不抛, 返回 None (LLM-off / caller 未注入 / 异常).
        """
        if not self._llm_enabled or not self._llm_caller:
            return None
        try:
            text = await self._llm_caller(
                "你是一个有自己情感和生活的虚构角色。按下面的指引写日记。", prompt,
            )
            if text and text.strip():
                return text.strip()
        except Exception:
            import logging
            logging.getLogger("emotion_spirit").warning(
                "emotion_spirit: superego reflection LLM 生成失败", exc_info=True,
            )
        return None
```

**改 6 — `main.py:973-978` scheduled loop LLM-off 分支**:

before:
```python
                    else:
                        # 旧行为: 只存 prompt 不调 LLM
                        diary_type = self._diary.determine_diary_type()
                        prompt = self._diary.build_diary_prompt(diary_type)
                        self._diary.record_diary(prompt, diary_type)
                        logger.info("emotion_spirit: prompt-only 日记已记录 (%s)", diary_type)
```

after:
```python
                    else:
                        # Bug-B (v1.2.10): LLM-off 不再存 prompt 模板 (复读机), 跳过.
                        # 0 篇真日记 > 假 prompt. (与 surface_handler reflection 一致.)
                        logger.debug("emotion_spirit: diary LLM 未启用, 跳过定时日记 (v1.2.10 Bug-B)")
```

> `to_dict` / `from_dict` (`diary_writer.py:297-301`) **不改**: 队列是 ephemeral, 只在 LLM 成功后 record, 无 seed 残留, 不需 dedup.

**改 7 — 新建 `tests/test_superego_reflection_diary.py`** (4 个测试). fixture 参考 `tests/test_l2_feedback_wiring.py` + `tests/test_defense_modulator.py` 的 SurfaceHandler / DiaryWriter mock 模式 (先读这俩文件抄 fixture):
```python
"""Bug-B (v1.2.10): superego reflection 日记走 LLM worker, 不再存 prompt 模板."""
# fixture 抄 tests/test_l2_feedback_wiring.py (SurfaceHandler + DiaryWriter 构造).

def test_consume_enqueues_not_records(surface_handler_with_critical_guilt):
    """consume() 触发 critical+guilt → 推队列, 不直接 record_diary."""
    sh, diary = surface_handler_with_critical_guilt
    diary._llm_enabled = True
    entries_before = len(diary._entries)
    sh.consume("session-1", surface_guilt_signals, {})
    assert len(sh._p._diary_reflection_queue) == 1
    assert len(diary._entries) == entries_before  # 不增 (没直接 record)

def test_process_one_reflection_records_llm_output(plugin_with_mock_llm):
    """_process_one_reflection 调 LLM → record LLM 输出 (不是 prompt)."""
    plugin, diary = plugin_with_mock_llm
    diary._llm_caller = AsyncMock(return_value="今天我和自己的内疚待了一会儿...")
    diary._llm_enabled = True
    entries_before = len(diary._entries)
    import asyncio
    asyncio.run(plugin._process_one_reflection("guilt", ["honesty", "loyalty"], "user-1"))
    assert len(diary._entries) == entries_before + 1
    entry = diary._entries[-1]
    assert entry["text"] == "今天我和自己的内疚待了一会儿..."
    assert entry["type"] == "superego_reflection"
    assert "写一篇简短的日记" not in entry["text"]  # 不是 prompt 模板

def test_consume_skips_when_llm_off(surface_handler_with_critical_guilt):
    """LLM-off → consume 不入队, 不 record."""
    sh, diary = surface_handler_with_critical_guilt
    diary._llm_enabled = False
    sh.consume("session-1", surface_guilt_signals, {})
    assert len(sh._p._diary_reflection_queue) == 0

def test_scheduled_loop_skips_when_llm_off(plugin_llm_off):
    """scheduled loop LLM-off 分支不调 record_diary (Bug-B 一并修)."""
    plugin, diary = plugin_llm_off
    diary._llm_enabled = False
    entries_before = len(diary._entries)
    # 直接调 LLM-off 分支逻辑 (不跑整个 loop, 只验证不 record)
    # 见 main.py:973-978 else 分支 — 跳过, 不 record
    assert len(diary._entries) == entries_before
```
> fixture 名字是示意, 执行模型照 `tests/test_l2_feedback_wiring.py` 的真实 fixture 模式实现 (构造 SurfaceHandler 需要 plugin ref + _modules; 构造 DiaryWriter 需要 pool/patterns/signals/alignment/conscience). 关键断言: **enqueue 不 record / LLM 输出被 record 且不是 prompt / LLM-off skip**.

### §3.4 CI — wheel-install smoke job (堵盲点)

**改 `.github/workflows/ci.yml`** — 在 `test` job (line 74 结束) 之后追加新 job:
```yaml

  wheel-install-smoke:
    # Bug-A (v1.2.10) regression gate. CI 的 test job 用 `pip install -e` (editable)
    # 跑测试, KB JSON 永远在源码树里 → 永远碰不到 wheel packaging 缺失.
    # 本 job 用非 editable `pip install .` (build wheel → site-packages) 验证
    # KB JSON 等数据文件真的进了 wheel. v1.2.9 fresh-install FileNotFoundError 的根因.
    name: Wheel install smoke (Bug-A regression)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: pip install . (non-editable, builds wheel)
        run: |
          python -m pip install --upgrade pip
          pip install .

      - name: Verify KB JSON packaged in wheel
        run: |
          python -c "from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights, get_defense_deltas; assert get_silence_tendency_weights(), 'silence_tendency_weights.json missing from wheel (Bug-A)'; assert get_defense_deltas(), 'defense_deltas.json missing from wheel (Bug-A)'; print('KB JSON packaged OK')"
```

---

## §4 Ship 步骤 (按顺序)

1. **bump 版本** (四源一致):
   - `emotion_spirit/_version.py`: `__version__ = "1.2.9"` → `"1.2.10"`
   - `metadata.yaml`: `version: "1.2.9"` → `"1.2.10"` (grep 确认格式)
   - `CHANGELOG.md`: 顶部加 v1.2.10 entry (照 v1.2.9 entry 格式, 列 3 fix + CI smoke)

2. **`UPDATE_HANDBOOK.md` §6 清债清单** 加:
   - "v1.2.10 清 3 P0 (Bug-A KB 进 wheel / Bug-C public_api facade 回退 / Bug-B reflection LLM worker + scheduled loop skip)"
   - "CI 补 wheel-install-smoke job (堵 editable-install 盲点 — v1.2.9 fresh-install 3 P0 漏网根因)"
   - "3 处手 new" → "4 处手 new (+PublicAPI facade, v1.3 factory param_wire 扩展)"

3. **跑全量测试**: `pytest --tb=short`
   - 期望: 1367 (v1.2.9) + ~6 新 (2 packaging + 1 registry + 4 reflection) ≈ 1373, 全 PASS.
   - 若 `test_no_hidden_manual_new` 报 `_public_api` → 检查 allowed 集合 (line 77-78 应已含, 不应报).

4. **本地 wheel smoke** (在 push 前自验 Bug-A):
   ```bash
   pip install .  # 非 editable
   python -c "from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights, get_defense_deltas; assert get_silence_tendency_weights(); assert get_defense_deltas(); print('OK')"
   pip uninstall -y astrbot-plugin-emotion-spirit  # 清理, 别污染 editable 环境
   ```
   (可选但强烈建议 — 避免 push 后 CI 才发现 wheel 没装上.)

5. **commit + tag + push** (项目惯例: 直接 main):
   ```bash
   git add -A
   git commit -m "fix(v1.2.10): 3 P0 fresh-install hotfixes (Bug-A/B/C) + CI wheel-smoke

   Bug-A: pyproject package-data 加 core/kb/*.json (wheel 漏 KB → FileNotFoundError)
   Bug-C: main.py public_api 回退 facade 手 new (@register 不适配整 dict 注入)
   Bug-B: surface_handler reflection 推队列 + 后台 LLM worker; scheduled loop LLM-off skip
   CI: 加 wheel-install-smoke job (堵 editable-install 盲点)"
   git tag v1.2.10
   git push origin main
   git push origin v1.2.10
   ```
   → push `v1.2.10` tag 触发 `release.yml` 自动 build zip + 发 GitHub Release.

6. **盯 CI**: GitHub Actions — `CI` workflow (test matrix + wheel-install-smoke) + `Build Release Zip` workflow 都必须全绿. wheel-install-smoke job 是这次的核心教训, 必须绿.

---

## §5 不在范围 (留 v1.3+, 不要顺手做)

- `PublicAPI` 真正 @register — 需 factory `param_wire` 支持整个 modules dict 注入, v1.3.
- prompt-fallback with `is_prompt_fallback` flag (LLM-off 部署保留 reflection 功能) — v1.3 评估.
- `emotion_classifier` / `bot_decision` force_state slot — v1.3.
- L3 fixpoint (compute 读 `_cumulative_offset`, L2 真正生效) — v1.3 力学叙事层.
- `sylanne/py.typed` 已顺手补 (§3.1), 不算范围外.

---

## §6 Memory 回写 (ship 后做)

- 更新 `emotion-spirit-current-truth.md`: v1.2.9 行加注 "fresh-install 3 P0, v1.2.10 修"; 版本推进到 v1.2.10 (HEAD/tag/tests/modules 更新).
- 新建 `emotion-spirit-v1210-p0-hotfixes.md`: 记录 3 P0 + CI 盲点教训 + 4 处手 new.
- `MEMORY.md` 索引加一行指向新 memory.

---

## §7 验证清单 (ship 前自检)

- [ ] `pyproject.toml` package-data 含 `core/kb/*.json` + `sylanne/py.typed`
- [ ] `main.py:108` 是 `PublicAPI(self._modules)` (不是 `self._modules["public_api"]`)
- [ ] `surface_handler.py` 推队列, 不调 `record_diary(prompt,...)`
- [ ] `main.py` 有 `_process_one_reflection` + `_drain_diary_reflection_loop` + `initialize()` 启动
- [ ] `diary_writer.py` 有 `generate_reflection_llm(prompt)`
- [ ] `main.py:973-978` LLM-off 分支 skip, 不 record prompt
- [ ] `ci.yml` 有 `wheel-install-smoke` job
- [ ] `_version.py` / `metadata.yaml` / `CHANGELOG.md` = 1.2.10
- [ ] `pytest` 全绿 (~1373)
- [ ] 本地 `pip install .` + KB import 通过
- [ ] commit + tag `v1.2.10` + push
- [ ] CI 两个 workflow 全绿
