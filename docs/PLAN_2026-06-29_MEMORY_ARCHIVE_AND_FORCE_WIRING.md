# PLAN 2026-06-29 — Memory 归档 + 力学 ghost 接线

> **写给执行者（小模型 / 下一个 session）**: 本 plan 是经过对**当前真实代码**只读审计后写的。审计结论（见 §0）纠正了若干 memory 里**方向都反了**的旧记录。**执行时以代码为准,不要以 memory 为准**。代码不在仓库根时先 `cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"`。
>
> 两个 Phase 可独立执行、独立 commit。Phase 1 是低风险文件搬移，Phase 2 是动 main.py 装配代码（有回归风险，必须跑测试）。**先做 Phase 1**。

---

## §0. 代码真相快照（2026-06-29 只读审计,已复核）

跑下面 3 条命令对齐当前状态（任何对不上就停手,先问）:

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git rev-parse HEAD              # 应 = fc85442... (docs post-ship)
git rev-list -n1 v1.1.0         # 应 = 652b58b... (v1.1.0 tag 目标)
git status --porcelain          # 工作树应只有 UPDATE_HANDBOOK.md staged (A)
```

**关键真相**(memory 与代码冲突点，整理/接线时一律认代码):

| 事实 | source |
|---|---|
| v1.1.0 已 ship，tag → 652b58b，CI 5/5 绿，**0 用户、未上架市场** | git + ship memory 一致 |
| 力学 `force_dynamics`+`body_state` **活着**（`regulation/`，非 memory 错记的 `core/`），已 `@register`，被 `emotion_spirit/__init__.py:42` import 触发注册 | `regulation/force_dynamics.py:134` `@register`；`__init__.py:42` |
| 但 `main.py` 里 `force_dynamics` 命中数 = **0** → 是 **ghost module**（被 factory build，main.py 从不消费） | `grep -c force_dynamics main.py` = 0 |
| `@register` 模块共 **48**（43 instantiable + 5 utility marker=provides=[]) | 审计 agent 清单 §1 |
| main.py 有 **11** 条 `TODO(tech-debt)` DI 双轨注释（不是 13）。其中 **3 条真有 @register**(dream_generator/diary_writer/reflex_learner)，**8 条 TODO 文案是假的**——bridge 3 个+output 2 个+agents 2 个组件**压根没 @register** | main.py:298/302/306/337/341/352/418 + bridge/ agents/ 无 `@register` |
| `emotion_classifier.classify_*` / `bot_decision` 都**没有 force_state 接入 slot**——力学的"接入 emotion_classifier 作动态权重"是 memory 旧设想，代码里没钩子 | `output/emotion_classifier.py` / `output/bot_decision.py` |
| LifeSimulatorV2 是裸类、无 @register（只 v1 stub `LifeSimulator` 有），靠 `configure(llm_caller=...)` 二次注入 | `regulation/life_simulator.py:174`; `main.py:322-331` |

**总体判断**: 这插件真正债务不是"代码缺"，是"**接线缺 + ghost 多**"。21 个 ghost module（build 了不用）、11 处双轨（用且手 new）、8 条假 TODO（说已 register 实际没）。整理 memory / 接线 / 排路线图都按这个真相。

---

# Phase 1 — Memory 归档 (低风险, 可回滚)

> 目的: 把旧版本号体系(v1.0.3/v2/v3 + Phase 3.0×)的 memory 搬到 `memory/archive/`，主索引只留指针。**不删任何文件**（归档不是删除）。新增一个"代码真相"总文件置顶。所有旧 memory 里**方向反了**的条目就地改对。

### P1-1 建 archive 目录

```bash
mkdir -p "C:/Users/Aston/.claude/projects/C--Users-Aston/memory/archive"
```

### P1-2 判定归档清单

把以下 memory **移到** `archive/`（旧版本号体系 / 已被代码超越的 Phase 记录）。判定标准:**这条 memory 描述的版本号或状态，是否还指导"从 v1.1.0 起"的当前工作? 不指导→归档。**

**归这些** (它们属于 v1.0.3/v2/v3 旧体系或已被代码超越):
- `emotion-spirit-v12-design.md` —— 这是**旧** v1.2(情绪轨迹)。轨迹已在 v1.1.0 发布。归档，并在文件头加注:"此为旧 v1.2(轨迹),已并入 v1.1.0。新 v1.2 = DI 双轨，见 [[emotion-spirit-update-handbook]]"
- `emotion-spirit-v17.md`、`emotion-spirit-v111.md`、`emotion-spirit-v103.md` —— 旧版本号决策
- `emotion-spirit-phase-3-progress.md`、`emotion-spirit-phase-30a-plan.md`、`emotion-spirit-phase-30c-*.md`、`emotion-spirit-phase-b-progress.md`、`emotion-spirit-phase25.md`、`phase2-design.md` —— Phase 体系记录(已完成)
- `emotion-spirit-v3-merger-plan.md`、`emotion-spirit-v301-astrbot-v425-patch.md`、`emotion-spirit-plan4-complete.md`、`unified-memory-brainstorm-complete.md` —— v3 体系已废
- `emotion-spirit-phase-4-launch-*.md`、`emotion-spirit-persona-kb-regen-plan.md`、`emotion-spirit-release-zip.md`、`emotion-spirit-secret-leak.md`、`emotion-spirit-debt-cleanup-*.md`、`emotion-spirit-ecosystem-eval-*.md`、`emotion-spirit-framework-review.md`、`emotion-spirit-abc-completion-report-directive.md`、`emotion-spirit-session-2026-06-{15,23,24,28}.md`、`emotion-spirit-next-session-2026-06.md`、`emotion-spirit-conf-schema-gap-analysis.md`、`emotion-spirit-progress.md`、`development-report.md`、`verification-complete.md`、`memory-index-summary.md`、`emotion-spirit-v110c-tech-debt-cleanup.md`、`emotion-spirit-workflows.md`

**留主索引**(当前/持久有用的):
- `MEMORY.md`(索引本身,要改,见 P1-4)
- `emotion-spirit-update-handbook.md` ⭐(置顶,刚建)
- `astrbot-local-setup.md`、`astrbot-plugin-ui-pages.md`(基础设施,仍指导本地跑)
- `three-force-framework.md`、`steppenwolf-and-decisions.md`、`dream-generator-design.md`、`emotion-spirit-direction.md`、`sylannengine-architecture.md`、`emotion-spirit-architecture-framework.md`、`emotion-spirit-development-history.md`、`autonomy-guard-design-issue.md`(理论/架构/史,仍参考价值)
- `emotion-spirit-v110-runtime-2026-06-28.md`、`emotion-spirit-v110-ship-2026-06-28.md`、`emotion-spirit-v110-ship-prep2-2026-06-28.md`(ship 闭环,刚校准过的,仍准)
- `parallellovecomedy-*`(另一个项目,不动)

**执行**: `mv` 上列归档条目到 `archive/`。一次一个确认,不要批量通配(mv 错难撤)。

### P1-3 就地修方向反了的 memory

归档搬移前/后,打开以下文件**改对**(只改错的具体句,别通篇重写):

1. **`emotion-spirit-phase-3-progress.md`** 第6节/任何"三元力学在/不在"的判定:把"力学已实现"标真;把任何"v3→v1 把力学叠掉"的句子改对——真实是**代码 force_dynamics/body_state 活着,被叠掉的是 main.py 接线**。然后该文件本就要归档。
2. **`dream-generator-design.md`** 头部:加一句"✅ DreamGenerator 已实现(regulation/dream_generator.py)并于 main.py:381 接入主循环。本文档保留作设计参考"。
3. **`emotion-spirit-development-history.md`**:任一"力学叠掉"句改对为"力学代码保留、main.py 接线在 v1.2 重接"。

> 注意:`emotion-spirit-v12-design.md` 已在 P1-2 归档清单。归档时加文件头注说明新旧 v1.2 区别，**不要改它的设计内容**(已做完的轨迹设计,原样留作历史)。

### P1-4 改主索引 MEMORY.md

- 删除所有归档掉的条目对应行(它们 mv 走了,索引行也要去)。
- 在索引顶部加一个 **ARCHIVE 指针** 块:
  ```
  ## 已归档 (旧版本号体系 v1.0.3/v2/v3 + Phase 体系) — 见 memory/archive/
  旧 v1.2=轨迹(已并入 v1.1.0)/ v1.0.3/v1.1.1/v1.7 决策 / Phase 2-4 记录 / v3 大合并 / ecosystem eval / ship-prep session
  新工作认 [[emotion-spirit-update-handbook]] + [[emotion-spirit-current-truth]]
  ```
- 保留 P1-2"留主索引"那些行。

### P1-5 新建 `emotion-spirit-current-truth.md`(代码真相总文件)

放 `memory/`。内容=本 plan §0 的真相表 + 当前版本路线骨架(v1.2 DI+力学接线 / v1.3 力学叙事 / v1.4 / v2.0 Steppenwolf,按你 2026-06-29 的选择)。frontmatter `type: project`。这文件是"之后每个 session 一开局读的真相锚"。

### P1 验证

```bash
ls "C:/Users/Aston/.claude/projects/C--Users-Aston/memory/" | wc -l   # 应明显少于之前(归档走了)
ls "C:/Users/Aston/.claude/projects/C--Users-Aston/memory/archive/" | wc -l  # 归档数对得上 P1-2 清单
grep "emotion-spirit-current-truth" "C:/Users/Aston/.claude/projects/C--Users-Aston/memory/MEMORY.md"  # 有指针
```
**不通过处理**: mv 错位 → `git status` 看(虽然是 ~/.claude 不一定 git,但 ls 能对照)→ mv 回去。

---

# Phase 2 — 力学 ghost 接线 + diary 双轨清 + ForceState 入日记 (动 main.py, 有回归风险)

> 目的: 把 `force_dynamics` / `body_state` 从 ghost module 接进 main.py 主装配；顺势把 `diary_writer` 双轨清掉(从 `self._modules` 取而非手 new);把 ForceState 情感基调注入日记。**三种活的修法同一套**（都是从 `self._modules` 取、删手 new），所以并到 v1.2。不碰其余 10 条 TODO(留下一份 plan)。

### P2-D 决策记录 (2026-06-29 已与用户确认，执行者不要再改主意)

| 决策 | 选择 | 实操含义 |
|---|---|---|
| D1 ForceState 怎么用 | **入日记作情感基调** | diary prompt 加一段 ForceState 描述 |
| D2 暴露哪个 API | **`from_labels` + 现有 labels** | `get_current_force_state(labels)` 调 `force_state_from_labels(labels)` |
| D3 8 条假 TODO | **不碰** | v1.2 只清力学2 + diary_writer(它在11条里且真有@register) |
| D4 v1.2 范围边界 | **顺手清 diary 双轨** | 既然 diary 要消费 ForceState,顺势把它从手 new 切到 factory 取 |
| D5 暴露方法名修正 | **无 `force_state_from_persona_id`,只有 `compute(personality)` 或 `force_state_from_labels(labels)`** | 见 force_dynamics.py:173 / :311 (审计 agent 清单里 `from_persona_id` 笔误,代码不存在) |

### P2-0 读前置(动手前必做)

读这几处，确认接线点没变（变了就停，先问）:
- `main.py:265-292`（`self._modules` 取数模式）
- `main.py:282` (diary 先取 self._modules) + `main.py:912-926` (diary 调用点) + `main.py:1363/1424-1427` (diary 手 new 覆盖那行)
- `emotion_spirit/regulation/force_dynamics.py` 全文(`compute(personality, body_state=None, conscience_pressure=0.0)`@:173 总入口;`force_state_from_labels(labels)`@:311 便捷入口;**不存在 `force_state_from_persona_id`**)
- `emotion_spirit/regulation/body_state.py` 全文(BodyState dataclass + BodyStateModule @register,无 LLM)
- `emotion_spirit/output/diary_writer.py:40-64`(`_emotion_block` 展示函数,trajectory/velocity/ambiguity 在此格式化——ForceState 基调注入的同构落点)

### P2-1 接 force_dynamics / body_state 进 self._modules 取用

在 `main.py` 装配区(约 265-292 附近,紧跟其他 `self._modules[...]` 取数之后)加:

```python
# 三元力学 (force_dynamics/body_state): 已 @register, 从 factory 取用, 不手 new。
# 力学是纯计算模块, 无 llm_caller 二次注入需求 (不同于 DreamGenerator/diary)。
# v1.2: 从 ghost (build 但 main 不消费) 接入。
self._force_dynamics = self._modules.get("force_dynamics")
self._body_state = self._modules.get("body_state")
```

**不要** 加 `from emotion_spirit.regulation.force_dynamics import ForceDynamics` + 手 new (那正是 ghost 来源)。它们已在 `self._modules`。

### P2-2 暴露 force_state 取用 API (用 from_labels + 现有 labels, D2 已定)

加方法,用 `force_state_from_labels`(不是 plan 旧错的 from_persona_id):

```python
def get_current_force_state(self, labels: dict[str, str] | None = None) -> "ForceState | None":
    """三元力学当前 ForceState (v1.2 接线 + 入日记消费; v1.3 叙事层继续用)。

    Args:
        labels: 5 轴标签 dict。None → 用 self._labels (默认人格)。
    Returns:
        ForceState (3 权重) 或 None (force_dynamics 未装配时)。
    """
    if self._force_dynamics is None:
        return None
    use = labels if labels is not None else getattr(self, "_labels", None)
    if not use:
        return None
    return self._force_dynamics.force_state_from_labels(use)
```

> ⚠ 若 `self._labels` 在 main.py 里的真实命名/赋值时机不同(确认: main.py:240/244 有 `self._labels = self._get_default_labels()`)——好。若为 None 或时机晚于此方法首次被调→该方法返 None,diary 走"无基调"分支,零回归。

### P2-3 清 diary_writer 双轨 (D4 已定: 顺势清)

main.py 的 diary 双轨: `:282` 取 `self._modules["diary_writer"]` 进 `self._diary`, 然后 `:1424-1427` 又**手 new 覆盖** `self._diary = DiaryWriter(self._pool, self._patterns, self._buffer_signals, self._alignment, self._conscience)`。

**清法**:
1. 删 `main.py:1424-1427` 那段手 new (含 TODO 注释 1424 ——本条正是 D3 允许碰的那个真有 @register 的)。
2. `:282` 保留(那条本就对)。
3. **关键**: 手 new 那段给的构造参是 `self._pool, self._patterns, self._buffer_signals, self._alignment, self._conscience` —— 删手 new 后, factory build 出来的 diary 要有等价依赖。**核对**: diary_writer @register 的 ModuleSpec depends_on 是 `[memory_pool, buffer_signals, pattern_extractor, superego.alignment, superego.conscience]`(审计 §1),param_wire 把这些 wire 进 `__init__`。所以 factory build 的 diary 已等价。**验证**: build 后 `self._diary._llm_caller` 是否被 set? main.py 原手 new 之后还有 `.configure(llm_caller=...)` 吗? grep `self._diary.configure\|diary.*configure` main.py —— 若有, 配置也要跟从 `self._modules` 取的那份补上(因为 factory build 时没有 llm_caller, 见 §0 真相 LifeSimulatorV2)。
4. 若 diary 没被 `.configure(llm_caller=...)` 注入 LLM, 则**原手 new 版也是无 LLM 的**(={`/diary` 直接记 prompt 才是 enable_diary_llm=true 时?  见 main.py:912-918: 它调 `generate_diary_llm()` 需 LLM)——这点务必 grep 确认, 否则切 DI 后日记 LLM 会坏。

> 这是 v1.2 唯一**有真实行为风险**(日记 LLM 可能丢注入)的点。执行者: 如果 grep 发现 main.py 原本就给 diary `.configure(llm_caller=...)` 了, 则切 DI 后要照样配; 如果发现原本手 new 版没配 LLM(即原版日记 LLM 其实也没真跑通), 那切 DI 不会让它变坏, 但要在 commit 里记"已知 diary LLM 注入现状=未配"。

### P2-4 ForceState 入日记作情感基调 (D1 已定)

在 `diary_writer.py:_emotion_block`(或它的调用链)加一段 ForceState 基调。**两种实现, 选低风险那种**:

**方案 A (改 diary_writer 类, 推荐)**: 给 diary_writer 加 `configure_force_dynamics(force_dynamics)` 注入(模仿它已有的 `configure(llm_caller, llm_enabled)` 模式), `_emotion_block` 末尾追加一段:
```python
# v1.2: 三元力学情感基调 (force_state_from_labels → dominant 描述)
if self._force_dynamics is not None:
    fs = self._force_dynamics.force_state_from_labels(<labels>)  # labels 来源: diary 上下文或默认
    lines.append(f"  - 力学基调 (三元主导): {fs.dominant} (nat={fs.natural:.2f} soc={fs.social:.2f} ind={fs.individual:.2f})")
```
然后 main.py 切 DI 给 diary 调 `self._diary.configure_force_dynamics(self._force_dynamics)`。labels 传哪: 看 diary 上下文有没有 persona labels, 没有就用默认(返的 ForceState 是默认人格基调, 仍合法)。

**方案 B (不改 diary_writer 类, main.py 调用点拼)**: 在 main.py:925 调 `build_diary_prompt` 后、`record_diary` 前, 把 ForceState 基调字符串拼进 prompt。diary_writer API 完全不动 (最贴"v1.2 不动 diary API"), 但 prompt 拼接散在 main.py 不如方案 A 干净。

> **推荐方案 A** —— 它跟 diary 已有的 `configure(...)` 模式同构, 测试好写, 且 diary 本就是"接状态类输入做 prompt"的组件。但 A 动了 diary_writer 类, 你若对动念犹豫走 B 也可接受。**不要** 两方案混做。

### P2-5 测试 (必须, 否则不算完成)

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- 期望: 全绿（力学已被 register 多时，build 已含它，main.py 取用不破坏行为，因为**现在没消费**——和之前唯一区别是多了两个 `self._` 引用）。
- 若红: 多半是 `self._modules` 里没 "force_dynamics"/"body_state" key（即 factory 没 build 它们）。排查: `grep -n "force_dynamics\|body_state" emotion_spirit/core/plugin_factory.py emotion_spirit/__init__.py` 确认 import 链触发 @register。若确实没 build → 这是新发现，记进 commit，**不要**硬补 @register(spec 已存,问题在触发)。
- 允许的已知红: `test_periodic_save_dirty_only` Win 概率性（见 ship memory，与本次无关，单独跑能过就当过）。

### P2-6 静态扫描

```bash
# 确认力学不再是 ghost (应有命中)
grep -c "force_dynamics\|ForceDynamics\|body_state\|BodyState" main.py   # 应 > 0 (P2-1/P2-2 加的引用)
# 确认没漏装手 new
grep -nE "ForceDynamics\(|BodyState\(|BodyStateModule\(" main.py        # 应 0 (我们用 factory 实例不手 new)
# 确认 diary 双轨清了 (手 new 那行应消失)
grep -n "self._diary = DiaryWriter(" main.py                            # 应 0 (手 new 已删, 只留 :282 的 factory 取)
# 确认 diary LLM 注入没丢 (若原版有 configure)
grep -n "self._diary.configure\|diary.*configure.*llm" main.py          # 若原版有, 这里应有; 若原版无, 记清现状
```

### P2 验证总闸

- [ ] `pytest` 全绿(允许 periodic_save 已知红); **特别看日记相关 test**(test_diary* / test integration 含 diary) 不回归
- [ ] `grep force_dynamics main.py` > 0 且无手 new
- [ ] diary 手 new 那行 (`self._diary = DiaryWriter(`) 已删
- [ ] diary LLM 注入现状已确认(grep 结果记进 commit)
- [ ] commit message 写明 "v1.2: wire force_dynamics/body_state out of ghost + clean diary dual-track + ForceState into diary prompt"
- [ ] 若选方案 B(P2-4) 动了 main.py prompt 拼接, commit 写清

---

## §9. 不要做的(界限)

- **不要** 在 Phase 1 删任何 memory 文件——"归档"=mv 到 archive/，不是删除。删除丢历史。
- **不要** 改 `emotion-spirit-update-handbook.md` 本体——它是已 ship 的规约,本次只往它不归档的引用。
- **不要** 动 emotion_classifier / bot_decision 的 `classify_*` / `__init__` 签名去硬塞 force 参数。它们没 slot，改 API 是 v1.3+ 工作。v1.2 力学消费点是**日记**(D1 已定),不是 classifier/bot_decision。
- **不要** 一刀切那 8 条假 TODO(它们代表还需补 @register spec 的 7 个组件 —— engine_manager/hotpool_forwarder/personality_bridge/realtime_dispatch/rhythm_learner/self_core/life_agent,是单独一批,见 handbook §1.2 清债清单)。Phase 2 只清力学2 + diary_writer 1 (D3/D4 已定)。
- **不要** 用 `force_state_from_persona_id` —— 它**不存在**于代码(D5 已修)。用 `force_state_from_labels(labels)` 或 `compute(personality)`。
- **不要** 切 diary 双轨时**不动 LLM 注入** —— diary 若原本 `.configure(llm_caller=...)` 过,切 DI 后必须照样配,否则日记 LLM 会坏(P2-3 第3步红线)。grep 确认现状记进 commit。
- **不要** force commit/push。每 Phase 改完跑测试、看结果、停。push 走 proxy:`git -c http.proxy=http://127.0.0.1:10809 push`(直连不通,见 handbook §4.4)。
- **不要** 动 git tag v1.1.0。本 plan 不发版,纯整理+接线。

## §10. 完成后

- Phase 1 完成:告诉我归档数 + 留主索引数 + current-truth 文件已建。
- Phase 2 完成:贴 pytest 最后几行 + grep 结果(force_dynamics 命中/diary 手 new 删除/diary LLM 注入现状) + commit hash。我会核对是否真消除力学 ghost + 真清 diary 双轨 + diary LLM 没坏。
- 两个 Phase 都过 → v1.2 剩余的 8 条假 TODO(7 个组件补 @register spec)可作为下一份 plan。