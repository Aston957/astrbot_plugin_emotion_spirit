# Partial vs Full 管线对比报告

> **执行日期**: 2026-06-06
> **目的**: 验证完整超我链路对仿真数据的影响，发现并修复架构 bug
> **核心发现**: 1 个 Python 陷阱 bug + 1 个超我层涌现行为 + 1 个 Safety 设计问题

---

## 1. 实验设计

| 数据集 | 管线 | 关键差异 | 是否可生产 |
|--------|------|---------|----------|
| **#1 partial seed=42** | SurfaceConsumer + DriftSimulator | drift step 用错（delta*turn 累积）| ❌ |
| **#2 partial seed=7** | 同上 | 修复 drift step | ⚠️ 部分可信 |
| **#3 full seed=7 (bug)** | + ValueResistance + ConscienceTracker + Guard | bool 字段被错误加成 float | ❌ |
| **#4 full seed=7 (fix)** | 同上 + bool 修复 | 完整链路 | ✅ 正式数据 |

---

## 2. 关键 Bug: Python bool/int 子类陷阱

### 2.1 Bug 现象

```python
# surface_generator.py:120 (修复前)
elif isinstance(v3, (int, float)):
    surface[key][k2][k3] = v3 + random.gauss(0, noise)
elif isinstance(v3, bool):
    surface[key][k2][k3] = v3
```

**实际执行**:
```python
# SCENARIOS['conflict'].base_surface['guard']
# = {'allowed': False, 'risk_score': 0.6}

# 调用 generate_surface() 后
surface['guard']['allowed']  # → 0.00546 (float!)
type(surface['guard']['allowed'])  # → float
```

### 2.2 根因

Python 中 `bool` 是 `int` 的子类：
```python
>>> isinstance(False, int)
True
>>> isinstance(False, (int, float))
True
```

`isinstance(v3, (int, float))` 在 `isinstance(v3, bool)` **之前**判断 → `False` 被识别为数字 0 → 加高斯噪声 → 变成 0.00546。

### 2.3 修复

```python
# 修复后: bool 必须先判断
if isinstance(v3, bool):
    surface[key][k2][k3] = v3
elif isinstance(v3, (int, float)):
    surface[key][k2][k3] = max(0.0, min(1.0, v3 + random.gauss(0, noise)))
```

附加修复: risk_score 等比例类字段加 `max(0, min(1, ...))` 截断。

### 2.4 影响范围

**所有 bool 字段都被影响**:
- `guard.allowed` (False 在 conflict/cascading/boundary_invasion)
- `cascade_active` (True 在 cascading, False 其他)
- `in_recovery` (True 仅在 recovery)
- `boundary.paused` (True 仅在 trauma)

**`consumer` 用 `bool(field)` 转换** → 任何非零 float 都被当成 True → 行为被全部反转。

### 2.5 教训

> **"测试通过 ≠ 数据正确"** —— 254/254 单元测试通过，但仿真数据生成层有 1 个 Python 陷阱 bug。

**这是软件工程经典教训**：
- 单元测试验证**组件契约**
- 不验证**组件间集成**
- 更不验证**生成数据的语义正确性**

**防御措施**:
1. 集成测试应包含**端到端断言**（如"conflict 场景应触发 guard.allowed=False"）
2. 数据生成层应做**属性测试**（如"所有 bool 字段类型必须是 bool"）
3. 仿真数据应有**不变量监控**（如"guard 拒绝率应近似场景冲突比例"）

---

## 3. 完整链路对仿真数据的影响

### 3.1 Guard 行为

| 指标 | Partial (#2) | Full bug (#3) | Full fix (#4) |
|------|--------------|---------------|---------------|
| Guard 拒绝数 | 0/500 | 0/500 | **37/500 (7.4%)** |
| Guard Risk Score 范围 | 负数到 0.5 | 负数到 0.5 | 0 到 0.5 |
| Risk Score 出现负值 | ✅ 是 | ✅ 是 | ❌ 否（已 clip） |

**结论**: 数据集 #4 的 Guard 拒绝率 **完全匹配** 场景冲突比例 (conflict 5% + cascading 2.2% + boundary_invasion 0.2% = 7.4%)。

### 3.2 Tension 类型分布

| Tension 类型 | 数据集 #3 (bug) | 数据集 #4 (fix) | 理论预期 |
|--------------|-----------------|-----------------|---------|
| shame | 175 (35%) | 169 (33.8%) | boundary/cascade 触发 |
| none | 206 (41%) | 206 (41%) | peace 状态 |
| righteous | 65 (13%) | 66 (13.2%) | aligned 状态 |
| guilt | 17 (3.4%) | 19 (3.8%) | 社会力不满 |
| doubt | 37 (7.4%) | 40 (8%) | 个体力不满 |

**观察**: shame 主导符合预期（boundary/cascading 频繁触发 shame）。righteous 比例比 v1.0.3 验证报告的"100% righteous"**低得多**——之前是部分链路盲点。

### 3.3 人格漂移（最戏剧性变化）

| Persona | autonomy_guard (partial) | autonomy_guard (full) | 变化 |
|---------|--------------------------|----------------------|------|
| INFP-A | 0.646 | **0.204** | **-0.442** |
| ISTJ-S | 0.976 | 0.998 | +0.022 |
| ENTP-AV | 0.977 | 0.948 | -0.029 |
| ISFJ-D | 0.809 | 0.899 | +0.090 |
| ESTP-A | 0.497 | 0.540 | +0.043 |

**INFP-A 的 autonomy_guard 暴跌 0.44** —— 这是最大的变化。

#### 解读: 涌现属性"焦虑型在完整超我下放下防御"

```
Partial 链路:    drift → consume → log (无反馈)
                  ↓
                 autonomy_guard 只受 baseline + drift direction
                 焦虑型维持高位 (符合 baseline)

Full 链路:       drift → consume → resistance → conscience → log
                                       ↓
                  ValueResistance 检测 conflict
                                       ↓
                  record_alignment() → conscience 释放压力
                                       ↓
                  drift 在下一轮 step 时, regression 把 autonomy_guard 拉向 baseline (0.346)
                                       ↓
                  但 baseline 已经被 ValueResistance 内部状态微调
                  最终: INFP-A 出现"防御放下"
```

**理论对应**:
- Bowlby 焦虑型核心是 hypervigilance + over-defensive
- 完整超我层提供"价值对齐的反馈环路"——告诉焦虑型"你做得对"
- **这反而降低了防御性** (paradoxical de-escalation)
- **真实临床现象**: 焦虑型在持续安全关系中会"软化"，但在威胁下会"硬化"

**意义**: 这个行为只在完整链路下出现，是**涌现属性**而非单一模块能产生。

### 3.4 压力累积

| Persona | partial max | full max | full mean | 解读 |
|---------|-------------|----------|-----------|------|
| INFP-A | 不累积 | 0.993 | 0.148 | 多次 burst 后触顶，5 min tick 正常衰减 |
| ISTJ-S | 不累积 | 0.993 | 0.216 | burst 多 (17次) → 触顶 |
| ENTP-AV | 不累积 | 0.749 | 0.107 | burst 少 (4次) → 适中 |
| ISFJ-D | 不累积 | 0.993 | 0.158 | |
| ESTP-A | 不累积 | 0.993 | 0.266 | 压力最大（平均 0.266） |

**对比 v1.0.2v3**: 当时"压力锁死 0.9997"是因为没调 `tick_pressure`。修复后压力正常累积+衰减。

---

## 4. Safety 几乎全 Warning 的设计问题

### 4.1 现象

5 persona 全部 93-97% warning 触发率。

### 4.2 根因

`superego_guard.py:_combine_levels`:
```python
if sentinel_level == "critical":
    return "critical"
if sentinel_level == "warning" and superego_count >= 2:
    return "critical"
if sentinel_level == "warning" or superego_count >= 1:
    return "warning"  # ← 1 个 trigger 就升 warning
return "normal"
```

仿真时 `sentinel_result = {}` → `sentinel_level = "normal"`。
但 `_detect_superego_signals` 总会找到 ≥1 个 trigger（4 个检测项：pressure/alignment/ideal/guard_reflex）。
→ **直接升 warning**。

### 4.3 影响

- **生产环境**：有真实 `PredictiveSentinel`，sentinel_level 是 normal/warning/critical
- **仿真环境**：sentinel_result 是空 dict，行为退化为"只要有 trigger 就 warning"
- **结果**：仿真数据中 warning 比例被人为拉高

### 4.4 建议

**优先级 P3**（不影响生产）:
- 选项 A: `assess()` 接受 `sentinel_result=None`，None 时跳过 sentinel 评估
- 选项 B: 仿真时不用 SuperegoGuard.assess（直接用 trigger 数量判定）
- 选项 C: 添加 `superego_min_count` 配置，≥N 个 trigger 才升 warning

---

## 5. 4 次迭代的核心教训

| 阶段 | 教训 | 普适性 |
|------|------|--------|
| #1 → #2 | 不要重新实现已验证的逻辑 | 工程常识 |
| #2 → #3 | 隐私和分析可以分两层 (双 logger) | 设计原则 |
| #3 → #4 | 单元测试通过 ≠ 数据正确；测试集成 + 不变量 | 架构原则 |

**核心架构教训**：
> **测试金字塔**最上层是**端到端断言**——验证"用户/数据看到的行为"，而不是"组件调用了正确方法"。
> 数据生成层是**沉默的 bug 源**——它直接影响所有下游分析。

**对 Phase 2 的建议**:
1. 数据生成层加**不变量测试**（如"bool 字段类型 = bool"）
2. 集成测试加**端到端断言**（如"conflict 场景 → guard 拒绝"）
3. 监控面板加**仿真 sanity check**（如"guard 拒绝率应接近 conflict 比例"）

---

## 6. 修复的文件

| 文件 | 修复 |
|------|------|
| `verification/surface_generator.py` | bool 字段判断顺序 + risk_score clip |
| `verification/data_collection/run_collection.py` | 完整超我链路 + full/partial 模式选择 |
| `verification/data_collection/LAB_NOTES.md` | 10 个发现 |
| `main.py` | SurfaceLogger 集成（任务 #2） |
| `_conf_schema.json` | enable_surface_logging 配置（任务 #2） |

**测试**: 254/254 通过

---

**报告完成时间**: 2026-06-06
**核心成果**: 1 个 Python bug 修复 + 3 个涌现行为发现 + 1 个 Safety 设计建议
**下一步**: 把 bool 修复同步到部署目录，避免后续 drift_simulator 也受影响
