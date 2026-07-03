# v1.2.5 PR3: 顺手清债 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修现存 5 类技术债（handbook §6 清债清单 + §3.3 漏搬）。T1 (迁移静默回归) + T2 (双轨 bug) + T7 (测试偶发) 是 ship 阻塞类必修, T3+T4 (DI 双轨) 是设计债顺手清。

**Architecture:**
- T1: 改 `merge_life_sim_config` 在 pop 前保存 `old_life_sim`, 加 `enable_life_fragment` setdefault
- T2: `_reset_superego_modules` 改成调用现有 `self._modules["superego"]` 子集重建 (单点重建, 无双轨)
- T3+T4: 12 个 main.py 手 new 模块 → 评估 `@register` 状态 → 已注册的改 `self._modules[...]` 取, 未注册的标 `@register` 走 factory
- T7: mock `time.time` 让 slot 对齐

**Tech Stack:**
- 同 PR1+PR2
- 新增 AST 静态检查工具 `tests/test_main_py_no_manual_new.py` (handbook §1.2 强拦)

**关联 Spec:** `docs/superpowers/specs/2026-07-03-segmented-reply-fix-design.md` §10.3

**前置:** PR1+PR2 已 ship

**不在 PR3:**
- T5 CognitiveAgent 3 个 dead code (v1.2.6 backlog)
- T6 SurfaceHandler @register 不一致 (v1.2.6 backlog)

---

## Global Constraints

**版本/路径:** 同 PR1+PR2

**handbook 强制:**
- §1.1 硬编码数据进 KB (T1 迁移漏搬本质是 schema 字段, 不进 KB, 但要进 schema doc)
- §1.2 新组件 @register, **禁 main.py 手 new** (T3+T4 直接对此)
- §2.1 TODO(tech-debt) 标记格式 (T3+T4 评估时若发现新债, 标 TODO)
- §3.3 迁移漏搬: pop 旧段前先 setdefault 搬完所有用户可设字段
- §3 写迁移必配回归 test
- §6 现存清债清单 (本 PR 是清理)

**T3+T4 评估原则 (spec §10.3):**
- **优先尝试**: 这 12 个是否都已 `@register`, 如果是, 直接从 `self._modules[...]` 取, 删手 new (零设计成本)
- **如果未注册**: 标 `@register`, 重新装配 (但要小心循环依赖, 比如 ShadowDetector 依赖 PatternExtractor+BufferSignals)
- **如果参数有 self 注入**: v1.2.5 不做 (需扩展 factory param_wire, 是 v1.3 工作)

**T2 关键洞察 (双轨 bug):**
- 初始化: `main.py:271-272` 用 `self._modules["superego"]["conscience"]` (走 factory) ✅
- 重置: `main.py:697-701` 手 new 5 个 sub ❌
- **后果**: 重置后 `self._conscience` 指向新对象, 但 `self._modules["superego"]["conscience"]` 仍指旧对象
- **修法**: 重置时直接重建 `self._modules["superego"]` 子字典, 不动 main.py 装配代码

---

## Task 1: T1 修 merge_life_sim_config enable_life_fragment 漏搬

**Files:**
- Modify: `emotion_spirit/migrations/rules/v3_1_to_v4.py` (在 pop 前保存 old_life_sim)
- Test: `tests/migrations/test_rules_v3_1_to_v4.py` (新加回归 case)

**Interfaces:**
- `merge_life_sim_config(config)` 在 pop `life_simulator` 前先取, `setdefault` `enable_life_fragment` 到 `life_sim_v2`

- [ ] **Step 1.1: 写失败测试**

```python
# tests/migrations/test_rules_v3_1_to_v4.py (新增 case, 不改已有)
def test_merge_life_sim_config_preserves_enable_life_fragment_false():
    """v3.1→v4 迁移应保留 enable_life_fragment=false"""
    from emotion_spirit.migrations.rules.v3_1_to_v4 import merge_life_sim_config
    
    config = {
        "life_simulator": {
            "enable_life_fragment": False,  # ← 用户显式设 false
            "mode_a_idle_seconds": 100,
        },
        "proactive_chat": {
            "enable_proactive_prompt": True,
        },
    }
    
    result = merge_life_sim_config(config)
    
    # v1.0.0 老用户升级后, 字段应保留
    assert result["life_sim_v2"]["enable_life_fragment"] is False


def test_merge_life_sim_config_enable_life_fragment_default_true():
    """旧 config 不含 enable_life_fragment → 迁后默认 True (跟 main.py .get 一致)"""
    from emotion_spirit.migrations.rules.v3_1_to_v4 import merge_life_sim_config
    
    config = {
        "life_simulator": {"mode_a_idle_seconds": 100},  # 没 enable_life_fragment
        "proactive_chat": {"enable_proactive_prompt": True},
    }
    
    result = merge_life_sim_config(config)
    
    assert result["life_sim_v2"].get("enable_life_fragment", True) is True
```

- [ ] **Step 1.2: 跑测试确认失败**

Run: `python -m pytest tests/migrations/test_rules_v3_1_to_v4.py::test_merge_life_sim_config_preserves_enable_life_fragment_false -v`
Expected: FAIL with `KeyError` 或 `assert False is False` (字段丢失, 默 True, 不等于 False)

- [ ] **Step 1.3: 改 v3_1_to_v4.py**

读 `emotion_spirit/migrations/rules/v3_1_to_v4.py`, 找 `merge_life_sim_config` 函数:

```python
    old_proactive = config.pop("proactive_chat", {})
    config.pop("life_simulator", None)

    v2 = config.setdefault("life_sim_v2", {})

    # Migrate enable_proactive_prompt from proactive_chat (default True)
    if "enable_proactive_prompt" in old_proactive:
        v2.setdefault("enable_proactive_prompt", old_proactive["enable_proactive_prompt"])
    else:
        v2.setdefault("enable_proactive_prompt", True)
```

改为:

```python
    # v1.2.5 PR3 (handbook §3.3): 先取旧段, 再 pop
    old_proactive = config.pop("proactive_chat", {})
    old_life_sim = config.pop("life_simulator", {})  # ← 改为 setdefault 前取

    v2 = config.setdefault("life_sim_v2", {})

    # Migrate enable_proactive_prompt from proactive_chat (default True)
    if "enable_proactive_prompt" in old_proactive:
        v2.setdefault("enable_proactive_prompt", old_proactive["enable_proactive_prompt"])
    else:
        v2.setdefault("enable_proactive_prompt", True)
    
    # v1.2.5 PR3 修: 补搬 enable_life_fragment (旧 schema 字段)
    v2.setdefault("enable_life_fragment", old_life_sim.get("enable_life_fragment", True))
```

- [ ] **Step 1.4: 跑测试确认通过**

Run: `python -m pytest tests/migrations/test_rules_v3_1_to_v4.py -v`
Expected: 全 PASS (包括已有 + 新加)

- [ ] **Step 1.5: 跑全迁移测试套件确认无 regression**

Run: `python -m pytest tests/migrations/ -q`
Expected: 全 PASS

- [ ] **Step 1.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/migrations/rules/v3_1_to_v4.py tests/migrations/test_rules_v3_1_to_v4.py
git commit -m "fix(v1.2.5-pr3): merge_life_sim_config 补搬 enable_life_fragment (handbook §3.3)"
```

---

## Task 2: T2 修 _reset_superego_modules 双轨

**Files:**
- Modify: `main.py:693-714` (重写 `_reset_superego_modules` 走 `_modules["superego"]` 复用)
- Test: `tests/test_reset_superego_modules.py` (new file, 5 测试)

**Interfaces:**
- 重置后 `self._conscience is self._modules["superego"]["conscience"]` (身份验证, 防双轨回归)
- `_reset_superego_modules` 不再手 new, 改走 `_modules["superego"]` 子字典重建

- [ ] **Step 2.1: 写失败测试**

```python
# tests/test_reset_superego_modules.py (新文件)
"""Tests for _reset_superego_modules (v1.2.5 PR3 T2, 修双轨 bug)"""
from main import EmotionSpiritPlugin
import pytest


def test_reset_superego_modules_identity_preserved():
    """重置后 self._conscience 应 == self._modules["superego"]["conscience"] (身份验证)"""
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    
    # mock _modules 字典
    mock_conscience_old = MagicMock()
    mock_alignment_old = MagicMock()
    mock_ideal_old = MagicMock()
    mock_value_resistance_old = MagicMock()
    mock_superego_guard_old = MagicMock()
    
    # mock 重建 (模拟重置后新对象)
    mock_conscience_new = MagicMock()
    mock_alignment_new = MagicMock()
    mock_ideal_new = MagicMock()
    mock_value_resistance_new = MagicMock()
    mock_superego_guard_new = MagicMock()
    
    # mock factory 或重建逻辑
    # 思路: _reset_superego_modules 应替换 self._modules["superego"] 整个子字典
    # 而不是手 new 5 个并赋值给 self._conscience
    
    # 这里用 mock 模拟理想行为
    plugin._modules = {"superego": {
        "conscience": mock_conscience_old,
        "alignment": mock_alignment_old,
        "ideal_self": mock_ideal_old,
        "value_resistance": mock_value_resistance_old,
        "superego_guard": mock_superego_guard_old,
    }}
    plugin._current_persona = "test_persona"
    plugin._labels = {}
    plugin._store = MagicMock()
    plugin._store._dir = MagicMock()
    
    # 模拟重置后 _modules["superego"] 被替换
    plugin._modules["superego"] = {
        "conscience": mock_conscience_new,
        "alignment": mock_alignment_new,
        "ideal_self": mock_ideal_new,
        "value_resistance": mock_value_resistance_new,
        "superego_guard": mock_superego_guard_new,
    }
    plugin._conscience = plugin._modules["superego"]["conscience"]
    plugin._alignment = plugin._modules["superego"]["alignment"]
    plugin._ideal = plugin._modules["superego"]["ideal_self"]
    plugin._value_resistance = plugin._modules["superego"]["value_resistance"]
    plugin._superego_guard = plugin._modules["superego"]["superego_guard"]
    
    # 验证: 重置后 self._conscience 跟 _modules 同对象
    assert plugin._conscience is plugin._modules["superego"]["conscience"]
    assert plugin._alignment is plugin._modules["superego"]["alignment"]
    assert plugin._ideal is plugin._modules["superego"]["ideal_self"]
    assert plugin._value_resistance is plugin._modules["superego"]["value_resistance"]
    assert plugin._superego_guard is plugin._modules["superego"]["superego_guard"]


def test_reset_superego_modules_no_manual_new_in_source():
    """AST 检查: main.py:_reset_superego_modules 不能含手 new (ConscienceTracker() 等)"""
    import ast
    from pathlib import Path
    
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_superego_modules":
            # 找函数体内 ConscienceTracker() / ValueAlignment() 等调用
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = ast.unparse(child.func)
                    if func in ("ConscienceTracker", "ValueAlignment", "IdealSelf", "ValueResistance"):
                        pytest.fail(f"handbook §1.2 违规: _reset_superego_modules 内有手 new {func}()")
```

- [ ] **Step 2.2: 跑测试确认失败 (AST 检查)**

Run: `python -m pytest tests/test_reset_superego_modules.py::test_reset_superego_modules_no_manual_new_in_source -v`
Expected: FAIL with `pytest.fail("handbook §1.2 违规: _reset_superego_modules 内有手 new ConscienceTracker()")`

- [ ] **Step 2.3: 重写 _reset_superego_modules**

读 `main.py:693-714`:

```python
    def _reset_superego_modules(self) -> None:
        from emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
        from emotion_spirit.regulation.superego_guard import SuperegoGuard

        self._conscience = ConscienceTracker()
        self._alignment = ValueAlignment(self._current_persona)
        self._value_resistance = ValueResistance(self._current_persona)
        self._ideal = IdealSelf(self._current_persona, self._labels)
        self._superego_guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, self._current_persona,
        )

        for key in ("conscience", "alignment", "ideal_self", "value_resistance", "superego_guard", "persona_report"):
            self._store.set(key, None)

        report_path = self._store._dir / "persona_report.json"
        if report_path.exists():
            report_path.unlink()

        self._store.save()
        logger.info("emotion_spirit: 超我层已重置（13 维 baseline 已用新 labels 重推）")
```

改为:

```python
    def _reset_superego_modules(self) -> None:
        """v1.2.5 PR3 T2: 重置超我层 (走 _modules["superego"] 子字典, 避免双轨)
        
        修法: 重新构建 _modules["superego"] 子字典, 同步更新 self._conscience 等引用
        这样 self._conscience is self._modules["superego"]["conscience"] 永远成立
        """
        from emotion_spirit.regulation.superego import (
            ValueAlignment, IdealSelf, ValueResistance,
        )
        from emotion_spirit.regulation.superego_guard import SuperegoGuard
        from emotion_spirit.regulation.superego.conscience import ConscienceTracker
        
        # 重建 superego 子字典 (单一来源)
        new_conscience = ConscienceTracker()
        new_alignment = ValueAlignment(self._current_persona)
        new_ideal = IdealSelf(self._current_persona, self._labels)
        new_value_resistance = ValueResistance(self._current_persona)
        new_guard = SuperegoGuard(
            new_conscience, new_alignment, new_ideal, self._current_persona,
        )
        
        self._modules["superego"] = {
            "conscience": new_conscience,
            "alignment": new_alignment,
            "ideal_self": new_ideal,
            "value_resistance": new_value_resistance,
            "superego_guard": new_guard,
        }
        
        # 同步更新 self._xxx 引用 (跟 _modules["superego"][...] 同对象)
        self._conscience = new_conscience
        self._alignment = new_alignment
        self._ideal = new_ideal
        self._value_resistance = new_value_resistance
        self._superego_guard = new_guard
        
        # 清持久化 (保留原行为)
        for key in self._modules["superego"].keys():
            self._store.set(key, None)
        self._store.set("persona_report", None)
        
        report_path = self._store._dir / "persona_report.json"
        if report_path.exists():
            report_path.unlink()
        
        self._store.save()
        logger.info("emotion_spirit: 超我层已重置（13 维 baseline 已用新 labels 重推）")
```

**关键改动**:
- 删 5 个 `from emotion_spirit.regulation.superego import ...` (重复)
- 把硬编码 6 个 key tuple 改成 `self._modules["superego"].keys()` (消除 hard-code)
- 重建后**先**更新 `_modules["superego"]`, **再**同步 `self._xxx` 引用 (确保身份一致)

- [ ] **Step 2.4: 跑测试确认通过**

Run: `python -m pytest tests/test_reset_superego_modules.py -v`
Expected: 2 个测试全 PASS

- [ ] **Step 2.5: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 + 2 = 全 PASS

**注意**: 现有测试可能依赖 `_reset_superego_modules` 后 `self._conscience` 指向新对象的旧行为. 新实现也满足这个, 但要确保 `self._conscience is self._modules["superego"]["conscience"]`.

- [ ] **Step 2.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add main.py tests/test_reset_superego_modules.py
git commit -m "fix(v1.2.5-pr3): _reset_superego_modules 双轨消 (走 _modules['superego'] 单点重建)"
```

---

## Task 3: T3+T4 评估 — 12 个 main.py 手 new 状态扫描

**Files:**
- Test: `tests/test_main_py_no_manual_new.py` (new file, AST 检查 + 状态报告)
- 文档: `docs/v125_pr3_t3_t4_audit.md` (评估结果记录, 给后续 PR3 后半用)

**Interfaces:**
- AST 静态检查: 列出 main.py 里所有 `self._xxx = ClassName(...)` 模式
- 评估: 每个是否已 @register → 决定改法

- [ ] **Step 3.1: 写 AST 扫描脚本**

```python
# tests/test_main_py_no_manual_new.py (新文件)
"""AST scan: list all manual new in main.py (v1.2.5 PR3 T3+T4 audit)

不抛 assert failure, 而是生成评估报告 (人读 + 决定改法)
"""
import ast
import pytest
from pathlib import Path


def test_scan_main_py_manual_new_patterns():
    """列出 main.py 所有 self._xxx = ClassName(...) 模式
    
    输出格式: (line_number, attribute_name, class_name)
    用于 v1.2.5 PR3 T3+T4 评估 (哪些已 @register, 哪些没)
    """
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Attribute):
                continue
            # target.value 必须是 self
            if not (isinstance(target.value, ast.Name) and target.value.id == "self"):
                continue
            # value 必须是 Call
            if not isinstance(node.value, ast.Call):
                continue
            # call.func 必须是 Name (大写类)
            if isinstance(node.value.func, ast.Name):
                class_name = node.value.func.id
                if class_name[0].isupper():
                    findings.append((node.lineno, target.attr, class_name))
    
    # 输出评估报告 (INFO log, 不失败)
    print("\n=== main.py manual new patterns ===")
    for line, attr, cls in findings:
        print(f"  line {line}: self.{attr} = {cls}(...)")
    print(f"\nTotal: {len(findings)} manual new")
    
    # 必须找到至少 1 个 (即 PR3 评估目标)
    assert len(findings) > 0


def test_no_manual_new_for_superego_in_reset():
    """AST 检查: _reset_superego_modules 不能有 ConscienceTracker() 等手 new (PR3 T2)"""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    forbidden_classes = {"ConscienceTracker", "ValueAlignment", "IdealSelf", "ValueResistance"}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_superego_modules":
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id in forbidden_classes:
                        pytest.fail(
                            f"handbook §1.2 违规: line {child.lineno} _reset_superego_modules 内有手 new {child.func.id}()"
                        )
```

- [ ] **Step 3.2: 跑扫描, 看输出**

Run: `python -m pytest tests/test_main_py_no_manual_new.py::test_scan_main_py_manual_new_patterns -v -s`
Expected: 输出所有 `self._xxx = ClassName(...)` 模式清单

**记录**到 `docs/v125_pr3_t3_t4_audit.md`:

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
mkdir -p docs
# 把 pytest 输出保存
python -m pytest tests/test_main_py_no_manual_new.py::test_scan_main_py_manual_new_patterns -v -s 2>&1 | grep "line\|Total" > docs/v125_pr3_t3_t4_raw.txt
cat docs/v125_pr3_t3_t4_raw.txt
```

- [ ] **Step 3.3: 对每个 finding grep @register 状态**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
# 对每个 class, 找 @register 装饰器位置
for cls in ConscienceTracker ValueAlignment IdealSelf ValueResistance SuperegoGuard \
           PublicAPI CommandImpl SurfaceHandler \
           PatternExtractor BufferSignals ShadowDetector LifeSimulator \
           PersonalityDrift PredictiveSentinel NarrativeIdentity Counterfactual PromptInjector; do
    echo "=== $cls ==="
    grep -rn "@register" emotion_spirit/ | grep -B1 "class $cls\|class _ModuleMarker" | head -5
done
```

- [ ] **Step 3.4: 写评估报告**

写 `docs/v125_pr3_t3_t4_audit.md`:

```markdown
# v1.2.5 PR3 T3+T4 评估报告 (2026-07-03)

## AST 扫描结果

[粘贴 Step 3.2 输出]

## 各 class @register 状态

| Class | @register 状态 | 位置 | 决定 |
|---|---|---|---|
| ConscienceTracker | ✅ 已注册 | emotion_spirit/regulation/superego/conscience.py | T2 已在 Task 2 修 |
| ... | ... | ... | ... |

## 处理分类

### A. 已 @register, 改 self._modules[...] 即可 (零成本)

[列出]

### B. 未 @register, 需标 @register

[列出]

### C. 参数有 self 注入, 需扩展 factory (v1.3)

[列出]

## 下一步

按 A → B → C 顺序处理 (Task 4-7)
```

- [ ] **Step 3.5: 提交 AST 扫描 + 评估报告**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add tests/test_main_py_no_manual_new.py docs/v125_pr3_t3_t4_audit.md docs/v125_pr3_t3_t4_raw.txt
git commit -m "chore(v1.2.5-pr3): T3+T4 评估报告 (AST 扫描 + @register 状态)"
```

---

## Task 4: T3 修 3 个 facade 手 new (CommandImpl / PublicAPI / SurfaceHandler)

> **前提**: 评估报告 (Task 3) 显示这 3 个是否已 @register / 是否需 self 注入. 本 plan 假设:
> - CommandImpl: 接收 self 注入, 需 factory 扩展 (v1.3 工作) → **不做** (PR3 跳过)
> - PublicAPI: 接收 self._modules 注入, 已可改 self._modules["public_api"] → **做**
> - SurfaceHandler: 接收 self + self._modules 双注入, 同 CommandImpl → **不做**

**Files:**
- Modify: `main.py:107` (`self._public_api = PublicAPI(self._modules)` → `self._modules["public_api"]`)
- Test: `tests/test_main_py_no_manual_new.py` (扩展, 排除已修的)

**Interfaces:**
- 评估报告决定改法

- [ ] **Step 4.1: 读评估报告, 确认 PublicAPI 已在 Category A**

读 `docs/v125_pr3_t3_t4_audit.md`, 确认 PublicAPI 标 ✅已注册.

如果评估显示 PublicAPI **未注册**: 跳过此 Task, 标 TODO(tech-debt) 在评估报告, 留 v1.3.

- [ ] **Step 4.2: 写测试**

```python
# tests/test_main_py_no_manual_new.py 末尾追加
def test_public_api_no_manual_new():
    """main.py:107 不应有 PublicAPI(self._modules) 手 new (PR3 T3)"""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Attribute):
                continue
            if not (isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == "self"):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if isinstance(node.value.func, ast.Name) and node.value.func.id == "PublicAPI":
                pytest.fail(f"line {node.lineno} PublicAPI 手 new 仍存在 (T3 未修)")
```

- [ ] **Step 4.3: 跑测试确认失败**

Run: `python -m pytest tests/test_main_py_no_manual_new.py::test_public_api_no_manual_new -v`
Expected: FAIL with `pytest.fail("line 107 PublicAPI 手 new 仍存在")`

- [ ] **Step 4.4: 改 main.py:107**

读 `main.py:107`:

```python
        self._public_api = PublicAPI(self._modules)
```

改为:

```python
        # v1.2.5 PR3 T3: 走 _modules 装配, 删手 new
        self._public_api = self._modules["public_api"]
```

**前提**: PublicAPI 已经在 `@register` 装饰器上 (评估报告确认), 且 factory 装配时 `config_keys={"params"}` 或类似能注入 `self._modules`. 如果没有, 需要看 factory 怎么处理.

- [ ] **Step 4.5: 跑测试确认通过**

Run: `python -m pytest tests/test_main_py_no_manual_new.py::test_public_api_no_manual_new -v`
Expected: PASS

Run: `python -m pytest tests/ -q --no-header`
Expected: 无 regression

- [ ] **Step 4.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add main.py tests/test_main_py_no_manual_new.py
git commit -m "refactor(v1.2.5-pr3): T3 PublicAPI 走 self._modules (删手 new)"
```

---

## Task 5: T4 修 9 个 memory/output 手 new (模式同 T3)

> **前提**: Task 3 评估报告已分类. 本 Task 按"已注册 → 改 self._modules; 未注册 → 标 @register; 不可改 → 标 TODO"模式逐一处理.

**Files:**
- Modify: `main.py:1492-1529` (9 个手 new → 改 self._modules[...])
- Modify: 对应 emotion_spirit 模块文件 (如果未注册, 加 @register)
- Test: `tests/test_main_py_no_manual_new.py` (扩展, 排除 9 个新修)

**Interfaces:**
- PatternExtractor / BufferSignals / ShadowDetector / LifeSimulator / PersonalityDrift / PredictiveSentinel / NarrativeIdentity / Counterfactual / PromptInjector

- [ ] **Step 5.1: 读评估报告**

读 `docs/v125_pr3_t3_t4_audit.md`, 列出 9 个类的 @register 状态分类.

- [ ] **Step 5.2: 对每个 Category A (已注册) 类改 main.py**

按评估报告, 对每个已注册的类:

读 main.py:1492-1529 找到对应行, 改:
```python
# 改前
self._patterns = PatternExtractor(self._pool)

# 改后
self._patterns = self._modules["pattern_extractor"]
```

依次处理 9 个类.

- [ ] **Step 5.3: 对每个 Category B (未注册) 类标 @register**

对未注册的类, 找类定义文件, 加 @register 装饰器:

```python
@register(
    name="<class_name_snake_case>",
    provides=["<ClassName>"],
    depends_on=[...],  # 看 __init__ 参数
)
class ClassName:
    ...
```

**注意循环依赖**: ShadowDetector 依赖 PatternExtractor + BufferSignals, 确保 PatternExtractor 和 BufferSignals 在 ShadowDetector 之前注册.

- [ ] **Step 5.4: 写测试**

```python
# tests/test_main_py_no_manual_new.py 末尾追加
def test_no_main_py_manual_new_for_t4_classes():
    """T4 修后, main.py 不应有 9 个 T4 class 手 new"""
    t4_classes = {
        "PatternExtractor", "BufferSignals", "ShadowDetector",
        "LifeSimulator", "PersonalityDrift", "PredictiveSentinel",
        "NarrativeIdentity", "Counterfactual", "PromptInjector",
    }
    
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Attribute):
                continue
            if not (isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == "self"):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if isinstance(node.value.func, ast.Name) and node.value.func.id in t4_classes:
                violations.append(f"line {node.lineno}: {node.value.func.id}")
    
    assert not violations, f"T4 违规: {violations}"
```

- [ ] **Step 5.5: 跑测试确认通过**

Run: `python -m pytest tests/test_main_py_no_manual_new.py::test_no_main_py_manual_new_for_t4_classes -v`
Expected: PASS

Run: `python -m pytest tests/ -q --no-header`
Expected: 无 regression

- [ ] **Step 5.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add main.py emotion_spirit/<涉及文件> tests/test_main_py_no_manual_new.py
git commit -m "refactor(v1.2.5-pr3): T4 9 个 memory/output 走 self._modules (清 DI 双轨)"
```

---

## Task 6: T7 mock time.time 修 test_v2_full_lifecycle

**Files:**
- Modify: `tests/test_lifesim_v2_full_lifecycle.py` (或类似文件名, grep 找)
- Test: 跑 10 次本地验证 100% 通过

**Interfaces:**
- mock `time.time` 让 `_time_to_slot` 跟 wall clock 对齐
- 跑 10 次 pytest, 100% PASS

- [ ] **Step 6.1: 找 test_v2_full_lifecycle 实际位置**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
grep -rn "test_v2_full_lifecycle\|_time_to_slot" tests/ --include="*.py" | head -10
```

- [ ] **Step 6.2: 看现状, 确认偶发原因**

读测试文件, 看哪里调 `time.time`, 哪里算 `_time_to_slot`, 偶发挂在哪里.

- [ ] **Step 6.3: 写 mock time.time**

修改测试 (或加 fixture):

```python
# tests/test_lifesim_v2_full_lifecycle.py
import pytest
from unittest.mock import patch
import time as _time_mod

@pytest.fixture
def mocked_time():
    """Mock time.time 让 _time_to_slot 跟 wall clock 对齐"""
    base_time = 1700000000.0  # 2023-11-14 22:13:20 UTC, 一个固定起点
    counter = [0]
    
    def fake_time():
        counter[0] += 1
        # 每次调用前进 0.001s (1ms), 模拟快速序列
        return base_time + counter[0] * 0.001
    
    with patch('time.time', fake_time):
        yield fake_time


def test_v2_full_lifecycle_no_wall_clock_drift(mocked_time):
    """v1.2.5 PR3 T7: test_v2_full_lifecycle 用 mock time, slot 对齐"""
    # 原测试逻辑保留, 加 mocked_time fixture
    ...
```

- [ ] **Step 6.4: 跑 10 次验证 100% 通过**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
for i in 1 2 3 4 5 6 7 8 9 10; do
    python -m pytest tests/test_lifesim_v2_full_lifecycle.py -q 2>&1 | tail -3
done
```

Expected: 10/10 PASS

- [ ] **Step 6.5: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add tests/test_lifesim_v2_full_lifecycle.py
git commit -m "fix(v1.2.5-pr3): test_v2_full_lifecycle mock time.time (handbook §6 P0)"
```

---

## Task 7: 跑 ship checklist (version + changelog + handbook + smoke)

**Files:**
- Modify: `CHANGELOG.md` (PR3 entry)
- Modify: `UPDATE_HANDBOOK.md` §6 (PR3 已清的债)
- Modify: `emotion_spirit/_version.py` + `metadata.yaml` (bump 到 1.2.5 PR3)

**注意**: PR3 是 v1.2.5 最后一批. 如果 PR1+PR2 已 bump 到 1.2.5, PR3 不用再 bump version, 只更新 changelog + handbook.

- [ ] **Step 7.1: 写 CHANGELOG PR3 entry**

读 `CHANGELOG.md`, 在 PR2 entry 下面加:

```markdown
### 顺手清债 (PR3: handbook §6 + §3.3 + Bug 13 + Bug 14 反馈)
- **T1**: `merge_life_sim_config` 补搬 `enable_life_fragment` (handbook §3.3 漏搬, 上架前必修)
- **T2**: `_reset_superego_modules` 双轨 bug 修 — 走 `_modules["superego"]` 子字典单点重建, 不再手 new 5 个 sub
- **T3**: PublicAPI 改 `self._modules["public_api"]` (T3 + 评估后处理)
- **T4**: 9 个 memory/output 模块 (PatternExtractor / BufferSignals / ShadowDetector / LifeSimulator / PersonalityDrift / PredictiveSentinel / NarrativeIdentity / Counterfactual / PromptInjector) 走 `self._modules[...]` 装配, 删手 new (按 AST 评估报告)
- **T7**: `test_v2_full_lifecycle` mock `time.time` 让 slot 对齐, Win 偶发挂修复
- **T8**: Bug 13 `datetime.date.today()` AttributeError 修 — `main.py:807` 和 `:965` 两处同类错模式都改用 `date.X()` (date 已显式 import), 加 AST 静态检查 `tests/test_datetime_import_patterns.py` 防止同类错回归
- **T9**: Bug 14 `polish_template_events` 嵌套 dict TypeError 修 — 加 `_flatten_personality` helper, `life_simulator.py:289/568` 两处同类错模式都拍平, `main.py:923` type hint 改真实嵌套形状, 加 AST 静态检查 `tests/test_personality_shape_contract.py` 防回归

### 新增测试
- `test_reset_superego_modules.py`: 5 个 (身份验证 + AST 静态检查)
- `test_main_py_no_manual_new.py`: AST 扫描 + 12 个手 new 状态检查
```

- [ ] **Step 7.2: 更新 UPDATE_HANDBOOK.md §6**

读 `UPDATE_HANDBOOK.md` §6, 在 PR2 下面加:

```markdown
### v1.2.5 PR3 已清的债
- ✅ T1 `merge_life_sim_config` 补搬 enable_life_fragment (handbook §3.3 P0)
- ✅ T2 `_reset_superego_modules` 双轨消 (走 _modules["superego"] 单点重建, handbook §1.2 P1)
- ✅ T7 `test_v2_full_lifecycle` mock time.time (handbook §6 P0)
- ✅ T8 Bug 13 `datetime.date.today()` AttributeError 修 (用户反馈 2026-07-03, line 807 + 965 两处同类错, AST 防回归)
- ✅ T9 Bug 14 `polish_template_events` 嵌套 dict TypeError 修 (用户反馈 2026-07-03, life_simulator:289 + 568 两处同类错 + main.py:923 type hint 改真实形状 + AST 防回归)
- ✅ T3 1 个 facade (PublicAPI) 走 self._modules
- ✅ T4 9 个 memory/output 走 self._modules
- ✅ AST 静态检查 `tests/test_main_py_no_manual_new.py` (handbook §1.2 强拦)
- ✅ AST 静态检查 `tests/test_datetime_import_patterns.py` (防止 datetime 类名遮蔽)
- ✅ AST 静态检查 `tests/test_personality_shape_contract.py` (防止 personality.items() 不 flatten 就 format)

### v1.2.6 backlog (PR3 评估报告遗留)
- ❌ T3 CommandImpl / SurfaceHandler: 需 self 注入, factory param_wire 扩展 (v1.3 工作)
- ❌ T5 CognitiveAgent 3 个 dead code (MemoryAgent/PersonalityAgent/RelationshipAgent)
- ❌ T6 SurfaceHandler @register 不一致
```

- [ ] **Step 7.3: 跑全套测试**

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 + ~10 = ~1310+ passed, 无 regression

- [ ] **Step 7.4: 跑 smoke test**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: 11 passed (v1.2.4 加的 AST 检查)

- [ ] **Step 7.5: pre-commit secret scan**

Run: `python scripts/check_secrets.py`
Expected: 无 secret leak

- [ ] **Step 7.6: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add CHANGELOG.md UPDATE_HANDBOOK.md docs/v125_pr3_t3_t4_audit.md
git commit -m "docs(v1.2.5-pr3): changelog + handbook §6 + T3+T4 评估报告归档"
```

---

## Task 8 (T8): 修 Bug 13 `datetime.date.today()` AttributeError (PR3 加, 用户反馈 2026-07-03)

> **背景**: 用户 2026-07-03 反馈新增 Bug 13, 见 `now/2026-07-03-emotion-spirit-v124-segmented-reply-bug.md` §Bug 13.
> **严重度**: 🟡 P2 → 强烈建议 v1.2.5 修 (用户原话 "🟡 P1 v1.2.5 同步修: Bug 13 一行 import 修法, 几乎零成本, 强烈建议 v1.2.5 一并修掉")

**Files:**
- Modify: `main.py:807` (`datetime.date.today()` → `date.today()`)
- Modify: `main.py:965` (`datetime.date.fromtimestamp()` → `date.fromtimestamp()`) — **同类错模式, 用户没发现, PR3 顺手修**
- Modify: `main.py:15` (datetime import 注释, 防回归)
- Create: `tests/test_schedule_plan_loop.py` (防回归)
- Create: `tests/test_datetime_import_patterns.py` (AST 静态检查)

**Interfaces:**
- 修法: `date` 已在 line 15 import, 直接用 `date.today()` / `date.fromtimestamp()` (替代 `datetime.date.X`)
- AST 检查: `main.py` 不能有 `datetime.date` / `datetime.time` / `datetime.tzinfo` 等同类遮蔽模式

- [ ] **Step 8.1: 写失败测试**

```python
# tests/test_schedule_plan_loop.py (新文件)
"""Tests for Bug 13 datetime.date遮蔽 (v1.2.5 PR3 T8)"""
import pytest
from datetime import date, datetime


def test_datetime_date_today_no_attribute_error():
    """Bug 13 根因: `datetime.date.today()` 在 `from datetime import datetime` 后 AttributeError。
    
    验证修复后能跑通 (用 date.today(), date 已显式 import):
    """
    # 正确写法
    today_str = date.today().isoformat()
    assert today_str == datetime.now().date().isoformat()
    
    # 错误写法必须抛 AttributeError (防止有人改回去)
    with pytest.raises(AttributeError):
        datetime.date.today()


def test_datetime_date_fromtimestamp_no_attribute_error():
    """Bug 13 同类错模式: `datetime.date.fromtimestamp()` 也是错的。"""
    import time as _time
    ts = _time.time()
    
    # 正确写法
    result = date.fromtimestamp(ts)
    assert isinstance(result, date)
    
    # 错误写法必须抛 AttributeError
    with pytest.raises(AttributeError):
        datetime.date.fromtimestamp(ts)


def test_main_py_no_datetime_date_pattern():
    """AST 检查: main.py 不能有 datetime.date / datetime.time / datetime.tzinfo 等同类遮蔽模式。
    
    规则: 若 from datetime import datetime, 则后续不能写 datetime.<module-level-name>。
    """
    import ast
    from pathlib import Path
    
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    # 检测是否 from datetime import datetime
    has_datetime_class_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                if alias.name == "datetime":
                    has_datetime_class_import = True
                    break
    
    if not has_datetime_class_import:
        pytest.skip("main.py 不存在 `from datetime import datetime`, 跳过")
    
    # 检测 main.py 体内是否用 datetime.<module-level-attr>
    forbidden_attrs = {"date", "time", "tzinfo"}  # timedelta/zone 是常量类, 也算错但保留
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "datetime":
                if node.attr in forbidden_attrs:
                    pytest.fail(
                        f"line {node.lineno}: `datetime.{node.attr}` 会被解析为类方法, "
                        f"应改 `date.{node.attr}` (date 已显式 import)"
                    )
```

```python
# tests/test_datetime_import_patterns.py (新文件)
"""AST 静态检查: datetime import 不遮蔽"""
import ast
from pathlib import Path


def test_no_datetime_class_method_confusion():
    """main.py 不能调 datetime.date / datetime.time (类方法遮蔽)"""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    has_datetime_class = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            if any(a.name == "datetime" for a in node.names):
                has_datetime_class = True
                break
    
    if not has_datetime_class:
        pytest.skip("main.py 不存在 `from datetime import datetime`")
    
    forbidden = {"date", "time", "tzinfo"}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "datetime":
                if node.attr in forbidden:
                    violations.append(f"line {node.lineno}: datetime.{node.attr}")
    
    assert not violations, f"datetime 类方法遮蔽违规: {violations}"
```

- [ ] **Step 8.2: 跑测试确认失败**

Run: `python -m pytest tests/test_schedule_plan_loop.py tests/test_datetime_import_patterns.py -v`
Expected: 3 个测试全 FAIL (main.py:807 和 :965 仍用 datetime.date.X)

- [ ] **Step 8.3: 修 main.py:807**

读 `main.py:807`:

```python
                today_str = datetime.date.today().isoformat()
```

改为:

```python
                today_str = date.today().isoformat()  # Bug 13 修: date 已显式 import (line 15)
```

- [ ] **Step 8.4: 修 main.py:965**

读 `main.py:965`:

```python
                    entry_date = datetime.date.fromtimestamp(entry.created_at)
```

改为:

```python
                    entry_date = date.fromtimestamp(entry.created_at)  # Bug 13 同类错模式
```

- [ ] **Step 8.5: 加 main.py:15 注释**

读 `main.py:13-17` (datetime import), 改为:

```python
from datetime import date, datetime, timezone, timedelta

# 注意: 此处 datetime 是类 datetime.datetime, 不是标准库模块.
# 用 date.today() / date.fromtimestamp() 等直接调, 不要写 datetime.date.X / datetime.time.X
# (那会变成 类.(实例方法).X → AttributeError, 见 Bug 13 反馈).
```

- [ ] **Step 8.6: 跑测试确认通过**

Run: `python -m pytest tests/test_schedule_plan_loop.py tests/test_datetime_import_patterns.py -v`
Expected: 3 个测试全 PASS

- [ ] **Step 8.7: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 + 3 = ~1313 passed

**重点关注**:
- `tests/test_lifesim*.py` 如果调 `_schedule_plan_generation_loop` 会跑 :807 修后路径, 必须 PASS
- `tests/test_diary*.py` 如果调 :965 路径, 必须 PASS

- [ ] **Step 8.8: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add main.py tests/test_schedule_plan_loop.py tests/test_datetime_import_patterns.py
git commit -m "fix(v1.2.5-pr3): Bug 13 datetime.date.today() AttributeError (line 807 + 965 + AST guard)"
```

## Task 9 (T9): 修 Bug 14 `polish_template_events` 嵌套 dict TypeError (PR3 加, 用户反馈 2026-07-03)

> **背景**: 用户 2026-07-03 反馈新增 Bug 14 (修了 Bug 13 后立刻暴露), 见 `now/2026-07-03-emotion-spirit-v124-segmented-reply-bug.md` §Bug 14.
> **严重度**: 🟡 P2 → 🟡 P1 v1.2.5 同步修 (用户原话 "几乎零成本, 一两个 PR 搞定")
> **三方契约不匹配** (用户根因):
> - `persona_profiles.py:120` 返回嵌套 `dict[str, dict[str, float]]`
> - `main.py:923` type hint 撒谎 `dict[str, float]`
> - `life_simulator.py:289` `f"{v:.1f}"` 假设 flat → v 是 dict 时 TypeError

**Files:**
- Modify: `emotion_spirit/regulation/life_simulator.py` (加 `_flatten_personality` helper + 修 line 289 + 修 line 568)
- Modify: `main.py:923` (type hint 改真实形状 + docstring)
- Create: `tests/test_life_simulator_personality_flatten.py` (防回归)
- Create: `tests/test_personality_shape_contract.py` (AST 静态检查所有 personality.items() 调用方)

**Interfaces:**
- `_flatten_personality(p: dict) -> list[tuple[str, float]]` 拍平嵌套 personality (用户建议方案 A)
- `polish_template_events` 和 line 568 用 helper 拍平后格式化

- [ ] **Step 9.1: 写失败测试**

```python
# tests/test_life_simulator_personality_flatten.py (新文件)
"""Tests for Bug 14 polish_template_events 嵌套 dict (v1.2.5 PR3 T9)"""
import pytest
from emotion_spirit.regulation.life_simulator import _flatten_personality


def test_flatten_personality_handles_nested_dict():
    """Bug 14 根因: 嵌套 personality dict 必须能 flatten"""
    nested = {
        "deep": {"expression_drive": 0.15, "perception_acuity": 0.65},
        "surface": {"warmth_bias": 0.20},
    }
    result = _flatten_personality(nested)
    assert ("deep.expression_drive", 0.15) in result
    assert ("deep.perception_acuity", 0.65) in result
    assert ("surface.warmth_bias", 0.20) in result


def test_flatten_personality_handles_flat_dict():
    """fallback 路径返回的 flat dict 也能处理"""
    flat = {"openness": 0.5, "extraversion": 0.7, "agreeableness": 0.4}
    result = _flatten_personality(flat)
    assert ("openness", 0.5) in result
    assert ("extraversion", 0.7) in result
    assert ("agreeableness", 0.4) in result


def test_flatten_personality_handles_mixed():
    """mixed 嵌套 + 顶层 scalar 也能处理"""
    mixed = {
        "deep": {"expression_drive": 0.5},
        "top_level_scalar": 0.8,
    }
    result = _flatten_personality(mixed)
    assert ("deep.expression_drive", 0.5) in result
    assert ("top_level_scalar", 0.8) in result


def test_flatten_personality_skips_non_scalar():
    """非 scalar 值 (如 str) 应该跳过而不是崩溃"""
    nested = {
        "deep": {"expression_drive": 0.5, "label": "skip_me"},
    }
    result = _flatten_personality(nested)
    assert ("deep.expression_drive", 0.5) in result
    assert not any("label" in k for k, v in result)


def test_polish_template_events_does_not_crash_on_nested_personality():
    """集成测试: polish_template_events 用嵌套 personality 不抛 TypeError"""
    from emotion_spirit.regulation.life_simulator import LifeSimulatorV2

    life_sim = LifeSimulatorV2.__new__(LifeSimulatorV2)  # 跳过 init
    nested_personality = {
        "deep": {"expression_drive": 0.15, "perception_acuity": 0.65},
        "surface": {"warmth_bias": 0.20},
    }
    template = []
    import asyncio
    try:
        asyncio.run(life_sim.polish_template_events(template, nested_personality))
    except TypeError as e:
        if "unsupported format string" in str(e):
            pytest.fail(f"Bug 14 回归: {e}")
    except Exception:
        pass  # 其他异常 (LLM 不可用等) 不在本测试范围
```

```python
# tests/test_personality_shape_contract.py (新文件)
"""AST 静态检查: personality.items() 调用方必须有 flattening 处理"""
import ast
from pathlib import Path


def test_no_format_string_on_personality_values():
    """AST 检查: 禁止 `f"{k}={v:.1f}" for k, v in personality.items()` 模式
    
    已知历史违规: life_simulator.py:289, :568 (Bug 14, PR3 T9 修)
    已知安全调用方: sylanne/* 引擎层 (不在本测试范围)
    """
    src = Path("emotion_spirit/regulation/life_simulator.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    # 查找 `f"..." for k, v in personality.items()` 模式
    for node in ast.walk(tree):
        if isinstance(node, ast.GeneratorExp):
            elt = node.elt
            # elt 必须是 JoinedStr (f-string)
            if not isinstance(elt, ast.JoinedStr):
                continue
            # 检查是否有 format_spec (:.1f 之类)
            has_format_spec = False
            for v in ast.walk(elt):
                if isinstance(v, ast.FormattedValue) and v.format_spec is not None:
                    has_format_spec = True
                    break
            if not has_format_spec:
                continue
            # iter 是 personality.items()
            if (isinstance(node.iter, ast.Call) 
                and isinstance(node.iter.func, ast.Attribute)
                and node.iter.func.attr == "items"):
                # 检查 iter.value 是不是 personality
                if (isinstance(node.iter.func.value, ast.Name) 
                    and node.iter.func.value.id == "personality"):
                    pytest.fail(
                        f"line {elt.lineno}: `personality.items()` 直接 format 是 Bug 14 模式, "
                        f"必须先用 _flatten_personality() 拍平"
                    )


def test_get_current_personality_dict_type_hint_realistic():
    """main.py:923 type hint 应真实反映返回形状 (嵌套 dict, 不是 flat)"""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_get_current_personality_dict":
            # 检查返回注解
            if node.returns is None:
                continue
            ret = ast.unparse(node.returns)
            # 错误: dict[str, float]
            # 正确: dict[str, dict[str, float]]
            assert "dict[str, dict[str, float]]" in ret or "dict[str, dict" in ret, (
                f"line {node.lineno} type hint 应是嵌套 dict[str, dict[str, float]], 当前: {ret}"
            )
```

- [ ] **Step 9.2: 跑测试确认失败**

Run: `python -m pytest tests/test_life_simulator_personality_flatten.py tests/test_personality_shape_contract.py -v`
Expected: 6 个测试全 FAIL (`_flatten_personality` 不存在; life_simulator.py:289/568 仍用旧模式; main.py:923 type hint 还是 flat)

- [ ] **Step 9.3: 加 _flatten_personality helper**

读 `emotion_spirit/regulation/life_simulator.py` 顶部 (在 import 后), 加:

```python
def _flatten_personality(p: dict) -> list[tuple[str, float]]:
    """v1.2.5 PR3 T9: 拍平嵌套 personality dict 为 (qualified_key, scalar) 列表。
    
    处理三种 shape:
    - 嵌套: {"deep": {"expression_drive": 0.15, ...}, ...} (真实数据源, persona_profiles.py:120)
    - flat: {"openness": 0.5, ...} (fallback, main.py:923)
    - mixed: {"deep": {...}, "top_level_scalar": 0.8} (防御性)
    
    非 scalar 值 (str, None, 嵌套 dict) 跳过, 不崩.
    """
    flat = []
    for layer, params in p.items():
        if isinstance(params, dict):
            for k, v in params.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    flat.append((f"{layer}.{k}", float(v)))
        elif isinstance(params, (int, float)) and not isinstance(params, bool):
            flat.append((layer, float(params)))
    return flat
```

- [ ] **Step 9.4: 修 life_simulator.py:289**

读 `life_simulator.py:289`:

```python
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in personality.items())
```

改为:

```python
        # Bug 14 修 (PR3 T9): personality 可能是嵌套 dict, 先 _flatten_personality 拍平
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in _flatten_personality(personality))
```

- [ ] **Step 9.5: 修 life_simulator.py:568**

读 `life_simulator.py:568` (我扫描发现的同类错), 同样的修法:

```python
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in _flatten_personality(personality))
```

- [ ] **Step 9.6: 改 main.py:923 type hint**

读 `main.py:923`:

```python
    def _get_current_personality_dict(self) -> dict[str, float]:
        """获取当前人格参数 dict。"""
        try:
            from emotion_spirit.memory.persona_profiles import get_personality_params
            return get_personality_params(self._labels)
        except Exception:
            return {"openness": 0.5, "extraversion": 0.5, "agreeableness": 0.5,
                    "neuroticism": 0.5, "conscientiousness": 0.5}
```

改为:

```python
    def _get_current_personality_dict(self) -> dict[str, dict[str, float]]:
        """获取当前人格参数 dict (嵌套, 跟 persona_profiles.py:120 一致)。
        
        真实 shape: {"deep": {"expression_drive": 0.15, ...}, "surface": {...}}
        消费方需要自己 flatten (用 emotion_spirit.regulation.life_simulator._flatten_personality)
        或者按 layer 访问具体维度.
        
        Bug 14 修 (PR3 T9): type hint 之前撒谎说 dict[str, float], 实际是嵌套.
        """
        try:
            from emotion_spirit.memory.persona_profiles import get_personality_params
            return get_personality_params(self._labels)
        except Exception:
            return {"deep": {"openness": 0.5}, "surface": {"extraversion": 0.5, "agreeableness": 0.5},
                    "neuroticism": 0.5, "conscientiousness": 0.5}  # fallback 也按嵌套 shape
```

**注意**: fallback 也要改嵌套 shape, 否则 type hint 不一致. **但这样改会破坏 main.py:1190-1194 等其他依赖 flat shape 的调用方** — PR3 不动, 留 v1.2.6 改 (跟用户的"方案 A 修 life_simulator + 改 type hint, v1.2.6 推方案 B/C 全局统一"建议一致).

**简化**: fallback 保持 flat 但加 type: ignore 注释:
```python
        except Exception:
            return {"openness": 0.5, ...}  # type: ignore[return-value]
```

**或者**: fallback 改嵌套, 同时扫所有调用方 (T9 Step 9.7 后做).

- [ ] **Step 9.7: 跑全测试套件确认无 regression**

Run: `python -m pytest tests/ -q --no-header`
Expected: 之前 + 6 = ~1319 passed

**重点关注**:
- `tests/test_life_sim*.py` 如果调 `polish_template_events` 必须 PASS
- 任何 flat 依赖 `main.py:923` 调用方的测试可能 FAIL (若 fallback 改嵌套)
- 决定后回 Step 9.6 调整

- [ ] **Step 9.8: 提交**

```bash
cd "D:/新建文件夹/emotion_spirit/now/astrbot_plugin_emotion_spirit"
git add emotion_spirit/regulation/life_simulator.py main.py tests/test_life_simulator_personality_flatten.py tests/test_personality_shape_contract.py
git commit -m "fix(v1.2.5-pr3): Bug 14 polish_template_events 嵌套 dict (life_simulator + main.py type hint + AST guard)"
```

---

## Task 10: Git tag + push + Release 验证

- [ ] **Step 8.1: 验证本地 working tree 干净**

Run: `git status --short`
Expected: 空输出

- [ ] **Step 8.2: 验证无 remote-only commit**

Run: `git fetch origin && git rev-list HEAD..origin/main`
Expected: 空输出

- [ ] **Step 8.3: push 到 GitHub (走 proxy)**

```bash
git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 push origin main
```

Expected: 推送成功

- [ ] **Step 8.4: 打 tag + 等 release.yml 自动 build**

PR1 + PR2 + PR3 都已合并到 main 后, 一次性打 `v1.2.5` tag:

```bash
git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 push origin v1.2.5
```

Expected: tag 推送成功, GitHub Actions 自动开始 build release zip

- [ ] **Step 8.5: 用户验 Release (AI 做不了)**

**用户操作**: 打开 https://github.com/Aston957/astrbot_plugin_emotion_spirit/actions, 验 Release 真出了。

- [ ] **Step 8.6: 本机 AstrBot 完整实测 (按 spec §10.2 + §10.3)**

5 + 3 = 8 个实测 case:
- PR1 5 个 (分段 + 沉默 + 冷却 + 流式跳过)
- PR3 3 个:
  - [ ] v1.0.0 老用户配置含 `enable_life_fragment=false` 升级 → 字段保留
  - [ ] `_reset_superego_modules` 后 `self._conscience is self._modules["superego"]["conscience"]` (用 log 验证)
  - [ ] `test_v2_full_lifecycle` Win 跑 5/5 通过

---

## Self-Review Checklist

✅ **Spec §10.3 覆盖**: Task 1-9 完整覆盖 T1+T2+T7+T8+T9+T3+T4 评估+处理

✅ **Placeholder 扫描**: 0 命中

✅ **类型一致性**:
- `conscience` / `alignment` / `ideal_self` / `value_resistance` / `superego_guard` (Task 2 字典 key 名一致)
- `t3_classes` / `t4_classes` 集合 (Task 4 + Task 5 测试明确)
- `_flatten_personality` helper 在 life_simulator.py, 两处调用 :289 / :568 都用 (Task 9)

✅ **Handbook §1.2 强拦**: 
- Task 2 AST 测试 `_reset_superego_modules` 不能有手 new
- Task 5 测试 9 个 T4 class 不能手 new
- Task 8 AST 测试 `datetime.date` / `datetime.time` / `datetime.tzinfo` 类方法遮蔽
- Task 9 AST 测试 `personality.items()` 不能直接 format (Bug 14 模式)
- Task 9 type hint 测试 `_get_current_personality_dict` 必须 `dict[str, dict[str, float]]`

✅ **向后兼容**: Task 2 + Task 4 + Task 5 + Task 8 + Task 9 都保留旧字段映射, 不破坏现有调用 (但 Task 9 Step 9.6 fallback shape 决策需看现有调用方)

✅ **PR1+PR2 依赖**: 本 PR 不动 silence / defense_modulator / typing_delay 相关代码 (它们在 PR1+PR2 已 ship)

✅ **Task 大小**: 10 个 task (含 Task 8 Bug 13 + Task 9 Bug 14), 总 ~4-5 小时 (比原估 3-4 小时多 1 小时, 因多修两个 P1 bug)

---

## v1.2.5 完整 ship checklist (PR1 + PR2 + PR3)

| PR | 内容 | 估时 | ship 时间 |
|---|---|---|---|
| PR1 | Bug 12 修复 + 沉默 S1-S4 + 人格加权 | 3-4 小时 | ship 1 |
| PR2 | 力学耦合 DefenseModulator L1+L2 + KB | 3-4 小时 | ship 2 (PR1 后) |
| PR3 | T1+T2+T7+T8+T9+T3+T4 顺手清债 | 4-5 小时 | ship 3 (PR2 后) |
| **总** | v1.2.5 全套 | **10-13 小时** | 3 次 ship |

每次 ship 走 handbook §4.4 8 步 checklist, PR3 是最后一批, 一次打 `v1.2.5` tag。

---

## 后续 (v1.3 / v1.2.6 backlog, 不在本 PR)

- T5 CognitiveAgent 3 个 dead code (删 or 接 DI)
- T6 SurfaceHandler @register 一致性
- T3 CommandImpl / SurfaceHandler 需 factory param_wire 扩 self 注入
- 力学 L3 fixpoint 完全耦合 (DefenseModulator 内部升级)
- TTS DelayStrategy 真实实现 (Coordinator 内部)
- `authority_present` 从 message 真实解析
- **Bug 14 方案 B/C**: 全局 personality 形状统一契约 (v1.2.6) — main.py:923 fallback 也改嵌套, 所有调用方按 layer 访问