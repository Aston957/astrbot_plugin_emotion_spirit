# PLAN 2026-06-30 — v1.2.2: install-feedback 9 bugs 修复 + CI 防回归

> 来源: 用户安装反馈 `now/2026-06-30-emotion-spirit-v121-install-feedback.md` (2026-06-30 更新版, 含 B7-B9)
> 作者: Aston (本 session)
> 前置: v1.2.1 已 ship (tag `be79fdf`, 56 modules, DI 双轨=0)
> **范围 (2026-06-30 用户拍板)**: v1.2.2 **只修 B1-B9 + CI**, 分段回复功能**挪到 v1.2.3** (隔离行为变更的风险)。
>       见同目录 `PLAN_2026-06-30_v123_segmented_reply.md`
>
> **用户已拍板的决策** (2026-06-30):
> - Bug 2 → **走 `find()`** (删手维护白名单, 一劳永逸)
> - Bug 4 → **方案 A** (`_ns_handler` 加 `*args, **kwargs`); 但 v4.26.1 CommandFilter 行为仍须本机 POC 验证
> - Bug 6 → **前者** (迁移不调 LLM, 只把非 sentinel 也留 `initialized=False`, 让 /setup_init 重跑)
>
> **2026-06-30 新增 B7-B9** (本 session 核实全部存在, 详见 §7-§9):
> - Bug 7: `_save_if_dirty` 漏存 diary (实际漏 ≥8 个模块, 系统性两路径分叉)
> - Bug 8: 无 `/view_diary` 命令 (`get_recent_diary` 现成未暴露)
> - Bug 9: `parse_persona_report` 误判 (tie-breaking 系统性偏向 INTJ 轴 + 否定语境无力)

---

## §0 执行顺序与依赖

```
阶段 1 (静态, 无运行期风险)
  Bug 2  pyproject packages 漏 4 子包   → 先修, 否则连 Wheel 都装不上
  Bug 3  PublicAPI 顶层导出缺 + README  → 顺手
  ── 回归: python -m build --wheel + pip install + python -c "from emotion_spirit import PublicAPI" ──

阶段 2 (阻塞链, 一起修, 单修 B4 无意义)
  Bug 4  _ns_handler 吞参 → 12 命令全瘫
  Bug 5  持久化 persona 覆盖 auto_source
  Bug 6  _migrate_old_spirit_data 用 ISTJ 锁死 + 短路 /setup_init
  ── 三者形成死循环: B4 让 /setup_relabel 死, B5/B6 让 /setup_init 假成功 ──

阶段 3 (文档, 阶段 1 修法落地)
  Bug 1  README 方式 1 补 pip install 步骤 + slim zip 命名

阶段 4 (持久化与命令补全, 独立于阶段 2, 可并行)
  Bug 7  _save_if_dirty 漏存 diary (+ 一堆模块) → 合并 _persist_modules 治本
  Bug 8  加 /view_diary 命令 (暴露现成 get_recent_diary)
  ── B8 不依赖 B4: 即使 B4 修好传参, 没 view_diary 命令就是没有 ──

阶段 5 (人格解析, 规则缺陷, 需决策修法深度)
  Bug 9  parse_persona_report tie-breaking 偏置 + 否定语境无力
  ── 选项: 仅补关键词表(治标) / 加 LLM 二次校验(治本, 但与 B6 决策"不调 LLM"需协调) ──

阶段 6 — ❌ **挪到 v1.2.3** (分段回复是行为变更, 隔离单独发版; v1.2.2 保持纯修复)

阶段 7 (CI 防回归)
  Test  wheel smoke test + packages 完整性 + _ns_handler 传参 + diary 持久化 + view_diary
```

**拆 PR 建议**: 阶段 1+3 (打包/文档), 阶段 2 (命令链阻塞), 阶段 4 (持久化+view_diary), 阶段 5 (解析器, 单独因决策点), 阶段 7 并入各 PR。

---

## §1 阶段 1 — 静态修复

### Bug 2: pyproject.toml `[tool.setuptools].packages` 漏 4 子包 🔴

**真相** (已 grep 验证):
- 源码有 12 个 `__init__.py` (见 `find emotion_spirit -name __init__.py`)
- pyproject.toml:48-57 只列 8 个, 漏:
  - `emotion_spirit.regulation.superego` (5 文件, `__init__.py:40` `from .regulation import superego` 必触发 ImportError)
  - `emotion_spirit.agents` (8 文件, `__init__.py:57` `from .agents import self_core, life_agent`)
  - `emotion_spirit.migrations` (5 文件, main.py:135 `from emotion_spirit.migrations import run_migrations`)
  - `emotion_spirit.migrations.rules` (子目录)

**修法** (最小改动): 在 packages 列表插入 4 行:
```toml
packages = [
  "emotion_spirit",
  "emotion_spirit.core",
  "emotion_spirit.memory",
  "emotion_spirit.regulation",
  "emotion_spirit.regulation.superego",   # ← 加
  "emotion_spirit.output",
  "emotion_spirit.bridge",
  "emotion_spirit.agents",                 # ← 加
  "emotion_spirit.migrations",             # ← 加
  "emotion_spirit.migrations.rules",       # ← 加
  "emotion_spirit.sylanne",
  "emotion_spirit.sylanne.compute",
]
```

**修法** (长期, 推荐, 符合 handbook §0 "规则只有能被自动拦下才算规则"):
- 删掉手维护白名单 → setuptools `find()` 自动发现
- **并**写 `tests/test_packaging.py::test_setuptools_packages_complete` (反馈文档 Bug 2 已给完整代码), CI 拦住未来漏列

**决策点** (留给 session 拍板): 走最小补 4 行, 还是直接换 find()?
- 推荐 find() — 避免下次新增子包又漏 (v1.2.1 已经加了一堆模块, 这次是漏列, 下次还会)
- 但 find() 需确认不误收 `tests/` `tools/` `verification/` 等非包目录 (这些在 emotion_spirit/ 外, find 默认不收, 安全)

### Bug 3: PublicAPI 无顶层导出 + README Quick Start 失效 🟡

**真相** (已 grep 验证):
- `emotion_spirit/__init__.py` 通读无 `PublicAPI`、无 `__all__`
- `PublicAPI` 实际在 `emotion_spirit/output/public_api.py`, main.py:30 是 `from emotion_spirit.output.public_api import PublicAPI`
- 反馈文档说 `_DeprecatedImportFinder._REDIRECTS` 是**空 dict** —— **这是文档作者看错了**; `__init__.py:73-116` 已填 38 条 mapping (含 `emotion_spirit.public_api → emotion_spirit.output.public_api`, line 113)。但 redirect 只改 import path, 不暴露顶层名字, 所以 `from emotion_spirit import PublicAPI` 依旧 ImportError, **Bug 3 主结论成立**

**修法** (推荐): `emotion_spirit/__init__.py` 末尾加顶层 re-export:
```python
# 顶层门面 re-export (L3 output 对外门面, 提升到顶层不破坏分层)
from .output.public_api import PublicAPI  # noqa: F401
```
PublicAPI 本就是 L3 output 层的对外门面, 提升到顶层 re-export 合规, 不破坏 sylanne→bridge→output 的依赖方向。

**同步**: README §"快速开始" 改成 `from emotion_spirit import PublicAPI` 即可用 (修完后), 删掉过时的 `_v1_compat` 表述。

---

## §2 阶段 2 — 命令链阻塞修复 (B4/B5/B6, 必须一起)

### Bug 4: `_ns_handler` 吞掉 12 个命令的参数 🔴

**真相** (已读 main.py:40-76 验证):
- `main.py:56` 签名 `async def _ns_handler(self, event: AstrMessageEvent)` —— **没有 `*args`**
- **且 line 51-52 注释主动写明** "不在签名里放 *args/**kwargs (v4.25.5 CommandFilter 会把 validate 后的 kwargs 当作必填)" —— 这是**作者针对 v4.25.5 的故意兼容决策, 但对 v4.26.1 已失效**
- 后果: `parsed_params` 空 → `first_arg` 必 None → `args_tuple=()` → `handler(event)` → `setup_switch(event, persona_id="")` 默认空串 → "用法错误"

**关键不确定性** (session 必须先验证再定方案):
- AstrBot v4.26.1 的 `CommandFilter` 参数注入机制到底是什么? 反馈文档说 "通过 `validate_and_convert_params` 的 `_orig_args` 路径按位置注入到 `*args`", 但这是反馈作者观察, 需在本机 AstrBot 实测确认 (feedback 文档给了验证脚本, 见 Bug 4 §验证方法)
- **优先级**: 先在本机 AstrBot v4.26.1 跑反馈给的 `handler_params` 验证脚本, 看 `_ns_handler` 注册出来的 `CommandFilter.handler_params` 是不是 `{}`

**修法候选** (验证后二选一):
- (A) 最小改动: `main.py:56` 加 `*args`:
  ```python
  async def _ns_handler(self, event: AstrMessageEvent, *args, **kwargs):
      handler = getattr(self._cmd, cmd_attr)
      async for r in handler(event, *args, **kwargs):
          yield r
  ```
  风险: 反馈文档 line 52 说这会让 v4.25.5 把 kwargs 当必填。需确认本机版本 ≥ 要求版本。
- (B) 兜底 (不拦于 CommandFilter 版本): 走原始消息字符串:
  ```python
  async def _ns_handler(self, event: AstrMessageEvent):
      handler = getattr(self._cmd, cmd_attr)
      msg = event.get_message_str().strip()
      cmd_name = _ns_handler.__name__.replace("_ns_handler_", "")
      if msg.startswith(f"/{cmd_name}"):
          msg = msg[len(f"/{cmd_name}"):].strip()
      args = msg.split() if msg else []
      async for r in handler(event, *args):
          yield r
  ```
  优点: 与 CommandFilter 版本解耦, 但破坏了原工程"走 parsed_params"的设计意图, 且对带空格的 persona 名 (如 "广濑爱贵" 无空格 OK, 但 "张 三" 会断)。**注意 persona 名一般无空格, B 方案够用**。

**测试**: `tests/test_commands.py::test_ns_command_passes_args` (反馈文档给了 parametrize 模板), 验证 `/setup_switch 广濑爱贵` 不再 "用法错误"。

### Bug 5: 持久化 persona 永远覆盖 `auto_source` 🟡

**真相** (已读 main.py:647-678 验证):
- `_load_persona_state` (文档误记为 `_setup_persona_state`, 真名 `_load_persona_state`, line 647): 持久化已初始化 + saved 非 sentinel → 直接走 line 667-670 "持久化赢", `auto_source` 被无视
- 只有 saved 是 sentinel + config 非 sentinel 时 config 才赢 (line 654-658)
- Sylanne 迁移用户 saved="小芙" (非 sentinel) → 永远锁死小芙, auto_source 无效

**修法** (需配合 B4 修好, 否则 /setup_switch 也切不动):
- 让 `auto_source` 显式指定 + 当前可用 persona 列表含它 → config 赢, 且重置 `_persona_initialized=False` 触发 /setup_init 走 LLM
- 反馈文档 Bug 5 §建议修法给了完整代码 (`if config_persona: available = self._list_available_personas() ...`)
- **需确认**: `self._list_available_personas()` 方法是否存在? grep 验证。若没有需补 (扫 `personas/` 目录)

**注意 handbook 反模式** (current-truth §5): 不要在 `_load_persona_state` 用 `perceived.get(key, default) or default` 于 bool/str 字段。修法代码需避免此模式。

### Bug 6: `_migrate_old_spirit_data` 用 ISTJ 锁死非 sentinel persona + 短路 /setup_init 🔴

**真相** (已读 main.py:702-731 + commands.py:37-52 验证):
- `_migrate_old_spirit_data`: 非 sentinel persona 走 line 721-730 → **写 `initialized: True` + ISTJ defaults**
- `commands.py:47` setup_init `if self._p._persona_initialized: return` → **LLM 路径 (57-84) 根本不执行**, 返回假成功
- 死循环: B5 让 saved 不对 → B6 用 ISTJ 锁 → /setup_init 被 B6 短路 → /setup_relabel 被 B4 吞参 → 只能手编 spirit_data.json

**修法** (推荐反馈文档 Bug 6 的"更优雅"方案 — 一 步到位, 但需评估启动期调 LLM 的代价):
```python
def _migrate_old_spirit_data(self) -> None:
    if self._current_persona in _SENTINEL_PERSONA_IDS:
        self._persona_initialized = False
        return
    try:
        system_prompt = self._read_persona_prompt(self._current_persona)
        llm = self._get_llm_callable("analyzer")
        if llm and system_prompt:
            from emotion_spirit.regulation.persona_analyzer import PersonaAnalyzer
            analyzer = PersonaAnalyzer(llm)
            result = analyzer.analyze(self._current_persona, system_prompt)
            # 写真实 labels + initialized=True
            ...
            return
    except Exception:
        logger.warning(...)
    # LLM 失败 fallback — 关键: 仍留 initialized=False, 让 /setup_init 可重跑
    self._labels = self._get_default_labels()
    self._persona_initialized = False
```

**决策点** (session 拍板):
- _migrate_old_spirit_data 是**同步**方法, 若改异步调 LLM 会牵动调用链 (它在 `_load_persona_state` 同步路径里)
- 偏保守方案: 迁移**不调 LLM**, 只把非 sentinel 也留 `initialized=False` (反馈文档 Bug 6 的"最小改动"方案), 用户显式 `/setup_init` 触发 LLM
- 推荐**最小改动**方案 — 启动期调 LLM 有失败/延时风险, 且 /setup_init 本来就是设计入口; B4 修好后 /setup_switch 也能重触 LLM 分析

**测试**: `tests/test_migration.py::test_migration_does_not_lock_non_sentinel_persona_with_fallback` (反馈文档给了模板)

---

## §3 阶段 3 — 文档 (Bug 1)

### Bug 1: slim zip 安装后须 pip install, README 未说明 🔴(文档)

**真相** (已验): main.py:28 `from emotion_spirit.core.plugin_factory import build` 把 emotion_spirit 当顶级包, AstrBot 插件加载器 (`star_manager.py:_import_plugin_with_dependency_recovery`) 只把插件目录加 sys.path, 不会把内部 `emotion_spirit/` 提为顶级包 → `No module named 'emotion_spirit'`

**修法**: README §安装 方式 1 补 pip install 步骤 (反馈文档 Bug 1 给了完整 markdown)。slim zip 名保留 (含 wheel 机制说明), 或改名 `*-source.zip`。

---

## §4 阶段 4 — 持久化漏存 (Bug 7) + view_diary 命令缺失 (Bug 8)

> 独立于阶段 2 的命令链修复, 可并行。B8 不依赖 B4 (即使 B4 修好传参, 没 view_diary 命令就是没有)。

### Bug 7: `_save_if_dirty` 漏存 diary (实际漏 ≥8 个模块) 🔴

**真相** (已读 main.py:1460-1504 验证):
- `_save_if_dirty` (1460-1477, 每命令后高频调用) 只存: memory_pool / intimacy / alignment / conscience / ideal_self / value_resistance / superego_guard / life_sim_v2 / last_plan_date / reflex_deltas / dream_state
- `_save_all` (1479+, 仅 terminate 低频) 才完整存, 多了: **reservoir / patterns / buffer_signals / shadow / life_sim / diary / drift / sentinel / narrative / counterfactual**
- **漏存的不只 diary, 而是 ≥8 个模块** — 反馈只点了 diary (因日记丢失最可感), 实际是系统性"两保存路径分叉"
- 后果: 普通命令流程下这些模块状态只在内存; docker restart 强 kill 时 terminate 没机会跑 → 全丢

**修法 (治本, 反馈"更优雅"方案)**: 合并两路径为单一 `_persist_modules`:
```python
def _persist_modules(self) -> None:
    """统一所有模块持久化, _save_if_dirty 和 _save_all 共用, 避免漏存。"""
    self._store.set("memory_pool", self._pool.to_dict())
    self._store.set("intimacy", self._intimacy.to_dict())
    self._store.set("alignment", self._alignment.to_dict())
    self._store.set("conscience", self._conscience.to_dict())
    self._store.set("ideal_self", self._ideal.to_dict())
    self._store.set("value_resistance", self._value_resistance.to_dict())
    self._store.set("superego_guard", self._superego_guard.to_dict())
    self._store.set("reservoir", self._reservoir.to_dict())
    self._store.set("patterns", self._patterns.to_dict())
    self._store.set("buffer_signals", self._buffer_signals.to_dict())
    if self._shadow:
        self._store.set("shadow", self._shadow.to_dict())
    if self._life_sim:
        self._store.set("life_sim", self._life_sim.to_dict())
    self._store.set("diary", self._diary.to_dict())
    self._store.set("drift", self._drift.to_dict())
    if self._sentinel:
        self._store.set("sentinel", self._sentinel.to_dict())
    if self._narrative:
        self._store.set("narrative", self._narrative.to_dict())
    self._store.set("counterfactual", self._counterfactual.to_dict())
    if hasattr(self, "_life_sim_v2"):
        self._store.set("life_sim_v2", self._life_sim_v2.to_dict())
        self._store.set("last_plan_date", self._last_plan_date)
    if hasattr(self, "_reflex_store"):
        self._store.set("reflex_deltas", self._reflex_store.to_dict())
    if hasattr(self, "_dream_generator"):
        self._store.set("dream_state", self._dream_generator.to_dict())

def _save_if_dirty(self) -> None:
    self._persist_modules()
    self._store.save()

def _save_all(self) -> None:
    self._persist_modules()
    self._store.save()
```

**注意 handbook 反模式** (current-truth §5): 各模块 `to_dict()` 已是自身职责, 这里只是调聚合, 不引入 .get 用法问题。但需确认每个 `self._xxx` 在 `_save_if_dirty` 调用时机都已初始化 (有些可能 None, 故用 if 守卫)。

**测试**: `tests/test_persistence.py::test_diary_persists_after_command` (反馈 B7 给了模板) + 新增 `test_all_modules_persist_in_dirty_path` (枚举所有应存 key, 防 ≥8 模块再漏)。

### Bug 8: 没有 `/view_diary` 命令 (`get_recent_diary` 现成未暴露) 🟡

**真相** (已 grep 验证):
- `diary_writer.py:292` 有 `get_recent_diary(days: int = 3) -> list[dict]` (现成)
- `commands.py` 只有 `reflect_diary` (line 564, 只生成当篇), **无 `view_diary`**
- `main.py` 无 `view_diary_cmd` 注册 (grep 无 `view_diary_cmd`)
- 用户试 `/view_diary` `/diary_history` 全 "用法错误"

**修法** (反馈 B8 给了完整实现):
1. `commands.py` 加 `view_diary(self, event, days: str = "3")` (反馈给了完整代码, 调 `diary.get_recent_diary(days_int)`)
2. `main.py` 类体加 `view_diary_cmd = _ns_command("view_diary", "view_diary", "查看历史日记（最近 N 篇）。")`
3. **注意**: 依赖阶段 2 的 B4 修好 — `view_diary(event, days="3")` 的 `days` 参数要靠 `_ns_handler` 传进去; B4 不修则 `/view_diary 7` 的 7 传不进 (但 `/view_diary` 无参仍可用默认 3)

**测试**: `tests/test_commands.py::test_view_diary_returns_entries` (反馈 B8 给了模板)

---

## §5 阶段 5 — 人格解析器误判 (Bug 9)

### Bug 9: `parse_persona_report` tie-breaking 系统性偏向 INTJ 轴 + 否定语境无力 🔴

**真相** (已读 persona_report_parser.py:303-339 验证, 反馈根因准确但偏浅):
- 用户 prompt "性格开朗、善良、没有太多心机、依靠直觉和感受、而不是长时间思考、对世界保持新鲜感" 被解析为 `INTJ / 活在未来` (应为 `ENFP / 活在当下`)
- **真根因 1 (tie-breaking 偏置)**: `_infer_mbti_from_narrative` (line 303-339) 三个维度 tie 时全偏向 INTJ 轴:
  - E vs I: `ei = "E" if e_score > i_score else "I"` → tie 选 I
  - F vs T: `ft = "F" if f_score > t_score else "T"` → tie 选 T
  - P vs J: `pj = "P" if p_score > j_score else "J"` → tie 选 J
  - 任何描述模糊的人格都被默认推向 INTJ 倾向 — 不是关键词表补几个词能修
- **真根因 2 (否定语境无力)**: prompt "依靠感受**而不是**思考" 让 f_patterns(感受)+1 且 t_patterns(思考)+1 → 打平 → tie-break 选 T。规则匹配对"而不是"语义否定天生无力
- **time_focus 误判**: `_TIME_FOCUS_KEYWORDS` 活在未来=`未来/计划/目标/以后`, 字面匹配; prompt 含"未来"二字 (哪怕"不活在未来") 即命中"活在未来"。反馈根因 #2 准确

**修法选项 (决策点, 需用户拍板)**:

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| 9-A 治标 | 补关键词表 (加"开朗/外向"→E, "不分析/随性"→P 等) + tie-breaking 改成不偏向 (tie 时给默认 S/F/P 而非 I/T/J) | 纯规则, 无 LLM 依赖, 改动小 | 否定语境仍无力; 关键词表永远补不全 |
| 9-B 治标+ | 9-A + 否定词预处理 (检测"而不是/不"前后词, 抵消被否定项的 score) | 缓解否定语境 | 中文否定复杂, 规则易漏 |
| 9-C 治本 | 反馈"更稳健"方案: `parse_persona_report` 标 deprecated, `setup_init` 强制走 LLM 分析 (`needs_llm_verification=True`) | 根除误判; LLM 理解语义 | 与 B6 决策需协调: 迁移留 initialized=False, /setup_init 走 LLM (与 B6 一致, 是 B6 自然延续) |
| 9-D 折中 | 规则解析 + 低置信度时 LLM 二次校验 (反馈"最小改动"方案 `parse_persona_report_with_llm_check`) | 平衡成本与准确度 | 需置信度字段 (现 ParsedPersona 无 confidence); LLM 调用时机要定 |

**已拍板: 9-A + 9-C 组合** (2026-06-30 用户确认):

9-A (治标, 必须做) — 修规则解析器自身:
- `_infer_mbti_from_narrative` tie-breaking 改不偏向 INTJ 轴:
  - E/I tie → "X"(未知) 或更合理的默认(中文 prompt 描述外向概率更高, 倾向 "E")
  - F/T tie → "F"(中文日常 prompt 描述情感远多于理性, 统计上 F 更常见)
  - P/J tie → "P"(同理, P 更常见)
- 补关键词表: "开朗/外向/健谈"→E, "不分析/直觉/随性"→P 等
- 否定词预处理: 检测"而不是/不/没"后的词, 从对方 score 中扣减而非加

9-C (治本, 也做) — /setup_init 的 LLM 路径为权威:
- 规则结果只作"启动扫描缓存"和"切换时快速预览"的来源
- /setup_init 调 LLM 拿真实标签写入持久化, 覆盖规则的缓存
- 与 B6 决策一致: 迁移留 initialized=False → /setup_init 走 LLM → 规则误判不影响最终标签

**两层分工**:
- 规则解析 = 快速预览/缓存填充 (启动不需 LLM, 切换不需等 LLM, 9-A 保证预览别太离谱)
- LLM 分析 = 权威写入 (setup_init 时拿真实标签写入持久化, 覆盖规则缓存)

**测试**: `tests/test_persona_parser.py::test_tie_break_does_not_bias_intj` + `test_negation_context_handled` + `test_setup_init_uses_llm_not_rules`

---

## §6 分段回复功能 — 已挪到 v1.2.3 (本文件不实施)

> **范围决策 (2026-06-30 用户拍板)**: v1.2.2 **只纯修复 B1-B9 + CI**, 分段回复是行为变更, 单独发 v1.2.3 隔离风险。
>
> 完整设计 (架构落点 / 力学信号映射 / POC X/Y/Z / 配置位 / persona 覆盖 / 顺手补 RhythmLearner.set_personality_params 漏接线 / v1.3 关系) 见:
> **`PLAN_2026-06-30_v123_segmented_reply.md`** (同目录)
>
> 已拍板的设计决策 (D5 先POC / D6 默认关 / D7 拟真打字+上限兜底 / D8 现算ignored_rate / D9 rhythm_strain / D10 hot_pool_pressure / D11 pad_valence) 全部在 v1.2.3 plan §1 决策表。

本文件 §8 风险表、§9 DoD、§10 优先级中原提到分段的部分已被 v1.2.3 取代, 以 v1.2.3 plan 为准。

---

## §7 阶段 7 — CI 防回归

按 handbook §0 "规则只有能被自动拦下才算规则":

1. **wheel smoke test** (反馈文档 §给作者建议 §2 给了 yaml):
   ```yaml
   - run: python -m build --wheel
   - run: pip install dist/*.whl
   - run: python -c "import emotion_spirit; print(emotion_spirit.__version__)"
   - run: python -c "from emotion_spirit import PublicAPI"
   ```
   拦 B1 + B2 + B3
2. **packages 完整性 test** (反馈 B2 给了完整 pytest) — 拦未来漏列子包
3. **wheel require-include sanity** (反馈 §给作者建议 §3) — release.yml 校验 wheel 含 12 个 sub-package __init__.py
4. **_ns_handler 传参 test** (反馈 B4 给了 parametrize 模板) — 拦 B4 回归
5. **migration 不锁非 sentinel test** (反馈 B6 给了模板) — 拦 B6 回归
6. **diary 持久化 test** (B7) — `test_diary_persists_after_command` + `test_all_modules_persist_in_dirty_path` (枚举所有应存 key)
7. **view_diary 命令 test** (B8) — `test_view_diary_returns_entries`
8. **persona parser tie-break test** (B9, 若选 9-A/B) — `test_tie_break_does_not_bias_intj`

---

## §8 诚实的已知风险与偏离记录 (执行时回填)

| # | 风险/偏离 | 触发条件 | 处置 |
|---|---|---|---|
| R1 | Bug 4 修法 A/B 选谁 | AstrBot v4.26.1 CommandFilter 实际行为 | 先 POC 验证再选, 不凭反馈文档断言 |
| R2 | 分段 on_llm_response 能否多段 yield | AstrBot handler 消费逻辑 | §4.4 POC, 不行走主动消息 API |
| R3 | `_migrate_old_spirit_data` 改调 LLM 是否引入启动期阻塞 | 该方法是同步路径 | 选最小改动方案 (只留 initialized=False), 不在迁移里调 LLM |
| R4 | registery count 改 56→57 | segmented_reply_coordinator 新增 | 维护 consistency + dryrun 两测试 (沿用 handbook §1.2 流程) |
| R5 | find() 方案是否误收非包目录 | Bug 2 长期修法改 find() | emotion_spirit/ 外目录默认不收, 但 POC build 一次确认 |
| R6 | persona-level segmented_reply 覆盖结构 | SegB | 需先读 persona 存储结构确定负载字段 |
| R7 | Bug 9 修法 9-A/B/C/D 选谁 | tie-breaking 偏置 + 否定语境无力的根因深度 | **已选 9-A+9-C 组合**: 修 tie-breaking 不偏向 + 否定词预处理 + /setup_init 走 LLM 为权威 |
| R8 | `_persist_modules` 合并后某些模块在 dirty 时机未初始化 | _save_if_dirty 调用早于某些模块创建 | 各 set 用 if self._xxx 守卫 (见修法代码), 测试覆盖空实例 |
| R9 | B8 的 `days` 参数依赖 B4 传参 | _ns_handler 工厂 | B4 修好后 days 可传; 未修时 /view_diary 无参仍可用默认 3 |
| R10 | B7 历史已丢的日记无法恢复 | docker restart 强 kill 前 terminate 没跑 | 修法只防未来; 历史数据无法找回, 需告知用户 |

---

## §9 完成定义 (Definition of Done)

- [ ] v1.2.2 tag, Release zip 重建 (含 README 更新)
- [ ] pytest 全绿 (现有 1241/1242 + 新增 packaging/commands/migration/segmented 测试)
- [ ] 本机 AstrBot 实测: 全新空 spirit_data.json + auto_source=广濑爱贵 → 启动后 /setup_init 调 LLM 拿到真实 ISFP 标签 (不再锁 ISTJ)
- [ ] 本机 AstrBot 实测: /setup_switch 广濑爱贵 → 正常切换 (不再 "用法错误")
- [ ] wheel `pip install` 后 `python -c "from emotion_spirit import PublicAPI"` 成功
- [ ] segmented_reply.enable=true 时 bot 回复分多条, 段间有打字延迟; enable=false 时回到旧行为
- [ ] 本机 AstrBot 实测: /reflect_diary 写日记后 docker restart, 日记仍在 spirit_data.json (B7)
- [ ] 本机 AstrBot 实测: /view_diary 与 /view_diary 7 都正常返回历史日记 (B8, 依赖 B4)
- [ ] 本机 AstrBot 实测: 广濑爱贵 prompt 解析为 ENFP/活在当下 而非 INTJ/活在未来 (B9, 或 /setup_init 走 LLM 拿真实标签)
- [ ] memory: [[emotion-spirit-current-truth]] 更新 v1.2.2 状态, 新建 [[emotion-spirit-v122-state]]

---

## §10 优先级与拆分建议

**推荐顺序** (用户可改):
1. **阶段 1+3** (打包/导出/README) — 半天, 解除新用户安装阻塞, 立即发 v1.2.2 hotfix
2. **阶段 2** (B4/B5/B6 链) — 1-2 天, 解除现有用户 persona 切换阻塞, 含 POC AstrBot CommandFilter 行为
3. **阶段 5** (CI) — 跟随 1+2 进 PR
4. **阶段 4** (分段功能) — 2-3 天, POC on_llm_response 多段 yield 是关键卡点, 可能需 v1.3 才上线 (若 AstrBot API 不支持则降级)。**这步最不确定, 建议最后做或单独探路**

**另一个排序** (若用户更看重分段功能):
先做阶段 4 的 §4.4 POC (不实现只验证 AstrBot API), 若可行则阶段 4 可与阶段 2 并行推进; 若不可行则分段功能降级进 v1.3 roadmap.

---

## Related

- 反馈原文: `now/2026-06-30-emotion-spirit-v121-install-feedback (1).md`
- [[emotion-spirit-current-truth]] — 代码真相锚 (本 plan 写入后需更新 v1.2.2 候选)
- [[emotion-spirit-update-handbook]] — §1.2 DI 规约 / §0 自动拦下规则
- 现成引擎: `emotion_spirit/output/realtime_dispatch.py` + `rhythm_learner.py` (已 @register, 56 模块成员)