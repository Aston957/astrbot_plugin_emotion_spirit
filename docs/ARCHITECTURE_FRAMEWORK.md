# emotion_spirit 插件架构 — BFS 探索文档

> **范围**:当前 main 分支(2026-06-14,commit `8a3bbd0` 之后),post-R3 状态
> **目的**:用 BFS 风格(广度优先)梳理框架——先看 6 个功能层的全貌,再逐层深入到模块,最后评估
> **不涉及**:`main.py`(AstrBot 插件入口,44K bytes,44KB 主要是 message handler 路由)
> **生成日期**:2026-06-14

---

## §0 第一层:6 个功能层 + 联系(BFS Root)

### 0.1 6 个功能层

```
emotion_spirit/                          # 总根: 5 个 root 文件 + 6 个子包
├── core/           (7 modules)         ← L0 核心: 配置 + 标签 + 注册 + 工厂
├── memory/         (13 modules)        ← L1 记忆: 记忆池 + 关系 + 隐私
├── regulation/     (13 modules)        ← L2 调控: 超我 + 力学 + 漂移 + 模拟
├── output/         (16 modules)        ← L3 输出: prompt 注入 + 命令 + 决策
├── bridge/         (4 modules)         ← 桥接: Sylanne 引擎对接 (L3 ↔ Sylanne)
├── migrations/     (5 modules)         ← 配置迁移: @register_migration + Runner + State
└── sylanne/        (46 modules)        ← 内嵌 SylannEngine 引擎
    ├── (13 top-level) algebra / engine / expression / ...
    └── compute/   (33 sub-modules)   HDC / 伤痕 / 虚空 / 自创生 / ...
```

> **注**:ADR-0001 提到 4 层架构(`core / bridge / extensions / interfaces`),但实际目录有 6 个。原因是:
> - `memory/` + `regulation/` + `output/` 是 L1-L3 的"核心 3 层"细粒度拆分
> - `bridge/` 是"桥接"独立层(Sylanne 集成需要单独管理)
> - `sylanne/` 是"内嵌扩展"层(从外部 SylannEngine fork 进来,per ADR-0003/0008)
> - `interfaces/` 没有独立目录,实现在根 `__init__.py`(对外暴露 API + v1.x redirect)

### 0.2 6 层的"一句话定位"

| 层 | 定位 | 核心问题 | 依赖方向 |
|---|---|---|---|
| `core/` | 基础设施 | 标签是什么?模块怎么注册? | 最底层,无业务依赖 |
| `memory/` | 长期记忆 | bot 记得什么?跟谁有什么关系? | 依赖 core,被 regulation + output 读 |
| `regulation/` | 内在调控 | bot 内心怎么处理?有没有挣扎? | 依赖 memory,被 output 读 |
| `output/` | 对外表现 | bot 怎么说话?什么时候说话? | 依赖 memory + regulation |
| `bridge/` | 引擎桥接 | Sylanne 引擎怎么接进来? | 依赖 memory + regulation,被 output 调 |
| `migrations/` | 配置迁移 | 老配置怎么升级到新 schema? | 独立,被 main.py 调用 |
| `sylanne/` | 计算引擎 | 即时情感怎么算? | 独立,只通过 bridge 对接 |

### 0.3 层间调用关系图

```
                ┌───────────────────────┐
                │  AstrBot 外部入口      │
                │  (main.py ~44KB)      │
                └──────────┬────────────┘
                           │
                ┌──────────▼────────────┐
                │  output/  (L3 表现)   │  ← 用户最终看到
                │  16 modules           │
                └──┬────────────┬───────┘
                   │            │
        ┌──────────▼─┐      ┌───▼──────────┐
        │ regulation/ │      │   bridge/    │
        │ (L2 调控)  │      │ (Sylanne 桥) │
        │ 13 modules │      │  4 modules   │
        └──────┬─────┘      └───┬──────────┘
               │                │
        ┌──────▼─────────────────▼──────┐
        │       memory/  (L1 记忆)        │  ← 数据层
        │       13 modules               │
        └──────────────┬─────────────────┘
                       │
                ┌──────▼─────┐
                │  core/     │  ← 基础设施
                │  7 modules │
                └────────────┘
                       │
                ┌──────▼──────────────────┐
                │  Sylanne (sylanne/)     │  ← 计算引擎(独立)
                │  46 modules             │
                └─────────────────────────┘
```

**关键调用方向**(单向,无循环):
- `core ← memory ← regulation ← output`
- `bridge` 横切 memory + regulation,被 output 调
- `sylanne` 独立,通过 `bridge/` 对接

### 0.4 模块数量统计

| 层 | 模块数 | LOC 估计(平均) | 总 LOC 估计 |
|---|---|---|---|
| core/ | 7 | ~500 | ~3.5K |
| memory/ | 13 | ~800 | ~10.4K |
| regulation/ | 13 | ~600 | ~7.8K |
| output/ | 16 | ~500 | ~8.0K |
| bridge/ | 4 | ~400 | ~1.6K |
| migrations/ | 5 | ~200 | ~1.5K |
| sylanne/(top) | 13 | ~1000 | ~13K |
| sylanne/compute/ | 33 | ~400 | ~13K |
| **总计** | **99** | | **~57K** |
| root 5 文件 | 5 | varies | ~3K |
| **总文件** | **104** | | **~60K** |

---

## §1 第二层:`core/` 基础设施(7 modules)

`core/` 是**最底层**,所有其他层都依赖它。包含配置常量、注册表、工厂、标签映射等"无业务含义"的基础设施。

### 1.1 `core/__init__.py` — 子包初始化

**功能**:子包 docstring + import 副作用。

**设计**:没有公开类,只是命名空间。

**联系**:无。

### 1.2 `core/config.py` — 配置常量

**功能**:**所有数值参数集中定义**(PERSONA_DIM=12, DECAY_HALF_LIFE_DAYS=30, 等)。

**设计**:
- 单一真相源:全插件所有"魔法数字"都从这里 import
- 修改一个值会全局生效
- 避免 "改一个参数要搜全项目" 的痛点

**联系**:
- **被** `memory/decay_model.py`, `regulation/force_dynamics.py`, `regulation/life_simulator.py` 等所有"需要调参" 的模块 import

### 1.3 `core/knowledge.py` — 知识库

**功能**:**集中所有声明性数据**(per-user 默认值、persona 模板常量、错误码定义等)。

**设计**:
- 跟 `config.py` 区分:`config.py` 是"参数",`knowledge.py` 是"数据"
- 数据可以是 dict / list / Enum
- 修改知识不影响代码逻辑

**联系**:
- **被** `memory/persona_profiles.py`, `regulation/persona_analyzer.py`, `output/emotion_classifier.py` 等

### 1.4 `core/label_mapper.py` — 标签映射器

**功能**:**人类可读标签 ↔ SylannEngine 12 维参数**双向转换。

**设计**:
- 输入:"INFP" / "焦虑型" 等字符串标签
- 输出:12 维 ndarray(personality vector)
- 双向:12 维 → 字符串(用于显示)

**联系**:
- **用** `knowledge.py`(标签 → 默认 12 维的映射)
- **用** `persona_labels_db.py`(3072 组合的精细映射)
- **被** `memory/persona_profiles.py`(初始化 persona), `regulation/persona_analyzer.py`(分析 user 输入)

### 1.5 `core/persona_labels_db.py` — 3072 组合 persona KB

**功能**:**3072 KB persona baseline 加载器**(16 MBTI × 6 emotion × 4 conflict × 8 time = 3072 entries)。

**设计**:
- 数据存在 `emotion_spirit/core/kb/persona_labels_db.json`(2.74 MB,入 git)
- per [[emotion-spirit-persona-kb-regen-plan]]: 之前在外部路径,KB 重建 + ship 进 plugin
- 不加 `@register` 装饰(不是 plugin module,是 data loader)

**联系**:
- **用** `label_mapper.py`(精细映射需要基础映射)
- **被** `force_state_from_persona_id_with_conscience()` 等"用 persona_id 推导力状态"的接口

### 1.6 `core/plugin_factory.py` — 插件工厂(薄包装)

**功能**:`registry.build(config)` 的 thin wrapper,提供 default config。

**设计**:
- 调用方不直接用 `registry.build`,而是 `plugin_factory.create_default()`
- 屏蔽"必须先建 config 对象"的繁琐

**联系**:
- **用** `core/registry.py`
- **被** `main.py`(AstrBot 启动时调)

### 1.7 `core/registry.py` — 模块注册表 + DI 工厂

**功能**:**所有 @register 装饰模块的注册表 + 依赖注入工厂**。

**设计**:
- 30 个 ModuleSpec 注册(由根 `__init__.py` 触发 import 副作用)
- `registry.build(config)` 按 config 顺序实例化 30 个模块
- 26 个 instantiable,4 个 helper-only

**联系**:
- **被** `core/plugin_factory.py`
- **被** `main.py`(模块系统接入)

### 1.8 `core/` 总结

`core/` 体现了"**配置 + 数据 + 注册 + 工厂**"的 DI 模式。所有其他层都从这里 import 常量,所有模块都通过 `registry` 实例化。

---

## §2 第二层:`memory/` 长期记忆(13 modules)

`memory/` 是**数据层**——bot 记得什么,跟谁有什么关系。Phase D "unified architecture" 把记忆系统重构为 flat + participant 过滤。

### 2.1 `memory/__init__.py` — 子包初始化

**功能**:namespace 初始化,无业务逻辑。

### 2.2 `memory/memory_pool.py` — 记忆池管理器(核心)

**功能**:**四层记忆池(flat 存储 + participant 过滤)**。
- **buffer**(热):最近 1 小时
- **warm**(温):最近 1 周
- **cold**(冷):1 周 ~ 1 年
- **ghost**(幽灵):已"消化"但仍可被反事实召回

**设计**:
- flat 存储(所有层共用一个表,不再分文件)
- participant 过滤(支持 multi-user 场景,只 recall 相关 user)
- CRUD + 搜索 + 衰减全在内部

**联系**:
- **用** `core/config.py`(DECAY_HALF_LIFE_DAYS)
- **用** `memory/unified_entry.py`(记忆实体)
- **用** `memory/decay_model.py`(时间衰减)
- **用** `memory/cascade_engine.py`(级联传播)
- **用** `memory/suppression.py`(压抑系统)
- **用** `memory/collapse_archetype.py`(崩溃模式)
- **用** `memory/memory_sampler.py`(采样)
- **被** `regulation/`(读取记忆), `output/buffer_signals.py`(从 buffer 计算信号), `bridge/hotpool_forwarder.py`(Sylanne inject 双写)

### 2.3 `memory/unified_entry.py` — 记忆实体

**功能**:**自包含记忆条目**(含 content / metadata / decay 状态 / access 计数 / embedding 引用)。

**设计**:
- 一个对象 = 一条记忆的所有信息
- `compute_decay_factor()` 实时算衰减
- 序列化友好(可写盘)

**联系**:
- **被** `memory_pool.py`(CRUD), `cascade_engine.py`(级联), `memory_sampler.py`(采样)

### 2.4 `memory/decay_model.py` — 双轴衰减

**功能**:**Ebbinghaus 衰减模型**(幂律 + 指数双轴)。
- 记忆衰减:幂律(前期快后期慢)
- 情感衰减:指数(均匀)

**设计**:
- 纯函数,无状态
- 输入时间 + 重要性,输出当前激活度

**联系**:
- **被** `memory_pool.py`, `unified_entry.py`

### 2.5 `memory/cascade_engine.py` — 级联引擎

**功能**:**倒排索引 + 混合相关性级联传播**。
- 一条新记忆可能触发相关旧记忆的"重新激活"
- 实现"联想"机制

**设计**:
- 倒排索引按关键词 / tag / entity
- 触发时级联更新关联记忆的访问时间

**联系**:
- **用** `memory_pool.py`(读 + 写)
- **用** `unified_entry.py`

### 2.6 `memory/memory_sampler.py` — 记忆采样器

**功能**:**人格加权多层采样 + 向量相似检索**。

**设计**:
- 采样的"广度 vs 深度"由 personality drift 决定
- 向量相似用 cosine 距离

**联系**:
- **用** `memory_pool.py`, `unified_entry.py`, `core/config.py`
- **被** `output/prompt_injector.py`(组装 prompt 时采样记忆)

### 2.7 `memory/intimacy.py` — 亲密度追踪

**功能**:**6 维不对称亲密度**(信任 / 亲密 / 熟悉 / 依赖 / 承诺 / 激情)+ 5 个插入点调制。

**设计**:
- 不对称:A → B 的亲密度跟 B → A 独立
- 5 插入点:消息触发、命令触发、时间流逝、共同事件、冲突事件

**联系**:
- **用** `core/config.py`
- **被** `memory/relationship_personality.py`, `regulation/pattern_extractor.py`, `output/buffer_signals.py`

### 2.8 `memory/relationship_personality.py` — 关系人格

**功能**:**per-user 13 维人格微调**(Phase 2.5)+ 4 段 tone 映射(陌生/初识/熟络/亲密)。

**设计**:
- 跟 bot 全局人格(12 维)不同,关系人格是 per-user 微调
- 4 段 tone 连续映射亲密度分数

**联系**:
- **用** `intimacy.py`
- **被** `output/prompt_injector.py`(组装 prompt 时取 tone)

### 2.9 `memory/persona_profiles.py` — 人格映射

**功能**:**标签 → Sylanne 12 维 + 价值观映射**。

**设计**:
- 输入:persona_id
- 输出:12 维 ndarray + 价值权重

**联系**:
- **用** `core/label_mapper.py`, `core/persona_labels_db.py`
- **被** `regulation/force_dynamics.py`(用 12 维做力学)

### 2.10 `memory/social_graph.py` — 用户间关系图

**功能**:**per-session 内部 SocialGraph**(Phase 2.0)+ 关系方向 + 强度。

**设计**:
- **关键设计**:bot **不感知**用户之间的关系
- SocialGraph 只用于"我跟你说'张三'时,你知道张三是谁"
- 不跨用户泄露

**联系**:
- **用** `intimacy.py`
- **被** `memory/topic_privacy.py`

### 2.11 `memory/topic_privacy.py` — 话题隐私

**功能**:**话题级隐私边界管理**(CPM 理论)。

**设计**:
- 每个话题有 privacy level(public / semi-private / private)
- private 话题在 prompt 注入时被过滤

**联系**:
- **用** `social_graph.py`(判断"这个 user 是否听过这个话题")
- **被** `output/prompt_injector.py`(过滤注入)

### 2.12 `memory/meaning_reservoir.py` — 意义蓄水池

**功能**:**积累高 Φ 时刻的意义**,供低 Φ 时的 Mode B 使用。

**设计**:
- Φ(整合度) = 自我 / 世界 / 他者 的契合度
- 高 Φ 时刻有"深层意义",被存入 reservoir
- 低 Φ 时刻可从 reservoir 取意义做"自我安慰"

**联系**:
- **用** `memory_pool.py`
- **被** `regulation/life_simulator.py`(Mode B 触发)

### 2.13 `memory/suppression.py` — 压抑系统

**功能**:**动态压抑水平计算**。
- 某些记忆被压抑(类似 Freud 压抑理论)
- 压抑水平由 emotion intensity + 个人差异决定

**设计**:
- 压抑 = access count 减少
- 反事实模拟时可"解除压抑"

**联系**:
- **用** `memory_pool.py`
- **被** `regulation/counterfactual.py`

### 2.14 `memory/` 总结

`memory/` 是"**bot 知道什么**"的完整建模。`memory_pool` 是中心,所有其他模块都通过它读写。隐私相关(`topic_privacy`)和心理相关(`meaning_reservoir`, `suppression`)反映了项目的**心理学深度**。

---

## §3 第二层:`regulation/` 内在调控(13 modules)

`regulation/` 是**bot 内心世界**的建模。超我(良心)、力学(自然/社会/个体)、漂移(长期变化)、模拟(假想场景)都在这里。

### 3.1 `regulation/__init__.py`

### 3.2 `regulation/superego.py` — 超我反思层

**功能**:**价值抵抗 + 价值对齐 + 良心事件 + 理想自我**(4 个 sub module 内部)。

**设计**:
- 4 sub-module 在 1 文件:ValueResistance / ValueAlignment / ConscienceTracker / IdealSelf
- 866 行,最大单文件之一

**联系**:
- **用** `core/config.py`, `core/knowledge.py`
- **被** `regulation/superego_guard.py`(软干预), `output/prompt_injector.py`(注入)

### 3.3 `regulation/superego_guard.py` — 超我防护

**功能**:**软干预决策 + 修复建议**。
- 当 superego 检测到"行为偏离价值",guard 给出"软修复"
- 不强制改写,只是建议

**设计**:
- 输入:当前行为 + 价值偏差
- 输出:repair suggestion(语气调整 / 内容调整 / 跳过)

**联系**:
- **用** `superego.py`
- **被** `output/prompt_injector.py`(在 prompt 末尾加"注意事项")

### 3.4 `regulation/force_dynamics.py` — 三元力学引擎

**功能**:**Phase 3.0A 三元力学**(自然 3 / 社会 4 / 个体 5,共 12 维)。

**设计**:
- `ForceState` + `ForceDynamics` 数据结构
- 算法 H:per-dim 极化 × 跨人方差
- `STD_FLOOR` 防退化

**理论**:per [[three-force-framework]]

**联系**:
- **用** `core/config.py`, `memory/persona_profiles.py`
- **被** `output/prompt_injector.py`(注入力学状态), `bridge/personality_bridge.py`

### 3.5 `regulation/body_state.py` — 身体状态

**功能**:**hormone / energy / arousal 三字段**(Phase 3.0B Task 3)。
- hormone:激素水平(影响情绪反应)
- energy:能量(影响活跃度)
- arousal:唤醒度(影响响应速度)

**设计**:
- 纯函数 100% 向后兼容
- 被 force_dynamics 用作 intensity 调制

**联系**:
- **被** `force_dynamics.py`, `output/predictive_sentinel.py`

### 3.6 `regulation/life_simulator.py` — 自主生活模拟

**功能**:**Mode A(对话驱动)+ Mode B(自主保底)双模式**。
- Mode A:bot 跟 user 聊天时,基于对话内容生成"生活事件"
- Mode B:无对话时,自动生成"保底事件"(避免记忆空)

**设计**:
- 7 种 LifeEvent 类型(birthday / season_change / mood_shift / etc.)
- LLM 生成内容 + 事件类型决定 raw_weight

**联系**:
- **用** `memory/meaning_reservoir.py`(Mode B 来源)
- **被** `output/diary_writer.py`, `output/bot_decision.py`

### 3.7 `regulation/personality_drift.py` — 人格漂移检测

**功能**:**追踪 Sylanne personality 12 维的长期趋势**。
- 计算 EMA(指数移动平均)
- 检测"人格在某个方向上漂移"

**设计**:
- 共享 `output/trend_utils.py` 的 EMA 工具
- 漂移达阈值时触发"内省"事件

**联系**:
- **用** `output/trend_utils.py`
- **被** `output/predictive_sentinel.py`

### 3.8 `regulation/pattern_extractor.py` — 冷池模式提取

**功能**:**从温池 / 冷池记忆中提取行为模式**。
- 循环模式(每天同时间问候)
- 趋势模式(用户最近越来越多负面)
- 触发模式(某关键词必触发某情绪)
- 回避模式(用户从不谈某话题)

**联系**:
- **用** `memory/memory_pool.py`, `memory/intimacy.py`
- **被** `output/buffer_signals.py`

### 3.9 `regulation/shadow_detector.py` — 阴影检测

**功能**:**基于荣格构想——阴影 = 未被符号化的情感模式**。
- bot 内心有"没说出来"的东西
- 检测并标记

**设计**:
- "未被符号化"= 多次出现但 prompt_injector 没注入过
- 跟 `suppression` 不同:suppression 是压抑,shadow 是"盲点"

**联系**:
- **用** `memory/memory_pool.py`
- **被** `output/prompt_injector.py`(标注 shadow 提醒)

### 3.10 `regulation/counterfactual.py` — 反事实模拟

**功能**:**为幽灵提供替代路径**。
- 模拟"如果当时我没压抑会怎样"
- 给用户"另一种可能性"的叙事

**联系**:
- **用** `memory/suppression.py`, `memory/memory_pool.py`
- **被** `output/narrative_identity.py`

### 3.11 `regulation/persona_analyzer.py` — 人格分析器

**功能**:**Phase C 拆 3 类分析器**(输入分析 / 状态分析 / 漂移分析)。

**联系**:
- **用** `core/label_mapper.py`, `memory/persona_profiles.py`
- **被** `output/command_router.py`(`/spirit_inspect` 命令)

### 3.12 `regulation/persona_report_parser.py` — 报告解析器

**功能**:**从 AstrBot persona system_prompt 自动提取人格参数**。

**联系**:
- **被** `persona_analyzer.py`

### 3.13 `regulation/collapse_archetype.py` — 崩溃原型

**功能**:**5 种行为模式 for emotional breakdown**。
- freeze / flight / fight / fawn / fold
- 情感过载时的应对

**联系**:
- **用** `memory/memory_pool.py`
- **被** `output/predictive_sentinel.py`(检测即将崩溃)

### 3.14 `regulation/` 总结

`regulation/` 是"**bot 怎么处理自己**"。`force_dynamics` + `body_state` 是物理基础,`superego` + `shadow_detector` 是心理基础,`life_simulator` + `counterfactual` 是"假想场景"。

---

## §4 第二层:`output/` 对外表现(16 modules)

`output/` 是**用户最终看到的东西**。prompt 注入、命令响应、自主决策都在这里。

### 4.1 `output/__init__.py`

### 4.2 `output/prompt_injector.py` — Prompt 组装器(核心)

**功能**:**把记忆 + 关系 + 超我 + 阴影组装为注入文本**。
- 输出 6 个 section 注入 LLM context

**设计**:
- 6 sections:人设/记忆/关系/超我/力学/注意事项
- 6th section(注意事项)由 superego_guard 提供

**联系**:
- **用** `memory/memory_pool.py`, `memory/topic_privacy.py`, `memory/relationship_personality.py`, `regulation/superego.py`, `regulation/force_dynamics.py`, `regulation/shadow_detector.py`
- **被** `main.py`(组装 prompt)

### 4.3 `output/emotion_classifier.py` — 情绪分类器

**功能**:**emotion_spirit 独立实现**的 7 类情绪分类(不用 LLM)。

**联系**:
- **用** `core/knowledge.py`
- **被** `output/buffer_signals.py`

### 4.4 `output/surface_consumer.py` — Surface 消费者

**功能**:**解析 Sylanne Surface ~60 字段 → SemanticSignals**。
- Sylanne 输出 ~60 字段,我们只关心其中 8-10 个
- 解析 + 提取 + 标准化

**联系**:
- **用** `bridge/engine_manager.py`(获取 Surface)
- **被** `output/buffer_signals.py`

### 4.5 `output/buffer_signals.py` — 缓冲池信号

**功能**:**从 memory_pool 的缓冲池计算 6 维信号**。
- 信号 1:情感均值
- 信号 2:情感方差
- 信号 3:最近活动
- ... 6 个

**联系**:
- **用** `memory/memory_pool.py`, `memory/intimacy.py`, `regulation/pattern_extractor.py`, `output/surface_consumer.py`
- **被** `output/predictive_sentinel.py`

### 4.6 `output/surface_handler.py` — Surface 处理器

**功能**:**emotion_spirit 自己的 Surface 处理逻辑**(跟 Sylanne 的 bridge 一起用)。

**联系**:
- **被** `main.py`

### 4.7 `output/command_router.py` — 命令路由器

**功能**:**Phase B P3-1 路由器**,接收命令 → 路由到具体命令。

**联系**:
- **用** `output/commands.py`
- **被** `main.py`

### 4.8 `output/commands.py` — 12 命令实现

**功能**:**12 个 AstrBot 命令**(`/spirit_inspect`, `/spirit_relabel`, `/spirit_force`, 等)。

**联系**:
- **被** `command_router.py`

### 4.9 `output/bot_decision.py` — bot 自主决策接口

**功能**:**bot 自主决定是否说话 / 说什么**。
- proactive_chat 适配(per [[emotion-spirit-plan4-complete]])
- 何时主动发起对话

**联系**:
- **用** `regulation/life_simulator.py`
- **被** `main.py`(`on_llm_response` 钩子)

### 4.10 `output/diary_writer.py` — 日记生成器

**功能**:**每天 14:00 / 22:00 生成日记**(bot 视角)。

**联系**:
- **用** `regulation/life_simulator.py`
- **被** `main.py`(定时器)

### 4.11 `output/narrative_identity.py` — 叙事身份

**功能**:**月度叙事弧生成**(bot 的"人生故事")。

**联系**:
- **用** `regulation/counterfactual.py`
- **被** `main.py`

### 4.12 `output/predictive_sentinel.py` — 预测性预警

**功能**:**从 body_state + 共振场信号 + 超我数据检测早期预警**。
- 用户即将崩溃
- bot 即将被压抑
- 关系即将恶化

**联系**:
- **用** `regulation/body_state.py`, `regulation/personality_drift.py`, `regulation/collapse_archetype.py`, `output/buffer_signals.py`
- **被** `main.py`

### 4.13 `output/realtime_dispatch.py` — 即时分段回复

**功能**:**分段回复计划生成器**(从 Sylanne 1.4.7 吸收核心)。
- bot 长回复时分段,避免一次性输出太多
- 打断检测

**联系**:
- **被** `main.py`

### 4.14 `output/rhythm_learner.py` — 节奏学习

**功能**:**自适应节奏同步**(从 Sylanne 1.4.7 吸收核心)。
- 学习用户消息频率,匹配 bot 响应节奏

**联系**:
- **被** `main.py`

### 4.15 `output/public_api.py` — 公开 API 网关

**功能**:**emotion_spirit 对外暴露的稳定 API**。
- 其他插件可以 import 这里的函数
- v1.0.0 标志 "public API stable"

**联系**:
- **被** `main.py`, 外部插件

### 4.16 `output/trend_utils.py` — EMA 趋势工具

**功能**:**EMA 工具**(供 `drift`, `sentinel`, `buffer_signals` 共享)。

**联系**:
- **被** `personality_drift.py`, `buffer_signals.py`, `predictive_sentinel.py`

### 4.17 `output/` 总结

`output/` 是"**bot 怎么输出**"的完整实现。`prompt_injector` 是核心(把内部状态翻译给 LLM),`commands` 是用户主动交互入口,`bot_decision` + `diary_writer` + `narrative_identity` 是 bot 主动行为。

---

## §5 第二层:`bridge/` Sylanne 桥接(4 modules)

`bridge/` 是**Sylanne 内嵌引擎跟 emotion_spirit 主体的接口层**。让两侧互相不认识也能协作。

### 5.1 `bridge/__init__.py`

### 5.2 `bridge/engine_manager.py` — SylannEngine 生命周期

**功能**:**封装 SylannEngine 初始化、消息处理、信号注入、状态读取**。

**设计**:
- 引擎**可选**:可降级为纯 emotion_spirit 模式
- `process()` 返回 Surface dict
- `inject()` 双写:HotPool + MemoryPool

**联系**:
- **用** `emotion_spirit.sylanne`(`from ..sylanne import get_engine`)
- **被** `output/surface_consumer.py`

### 5.3 `bridge/hotpool_forwarder.py` — HotPool 转发器

**功能**:**Sylanne inject() 信号 → MemoryPool 转发**。
- 当 Sylanne 想"记住"某情绪事件,我们写进 MemoryPool

**联系**:
- **用** `memory/memory_pool.py`
- **被** `engine_manager.py`

### 5.4 `bridge/personality_bridge.py` — 人格桥

**功能**:**5D Embodiment ↔ 12D personality 双向映射**。
- Sylanne 用 5D,我们用 12D
- 桥接维度差异

**联系**:
- **用** `regulation/force_dynamics.py`
- **被** `engine_manager.py`

### 5.5 `bridge/` 总结

`bridge/` 只有 4 个模块,体现了"**集成层要轻**"的设计哲学。引擎变化不应污染 emotion_spirit 主体,所以单独抽出来。

---

## §5.5 第二层:`migrations/` 配置迁移(5 modules)

`migrations/` 是**配置迁移框架**，用于自动将老 config 迁移到新 schema。采用 Registry 模式，`@register_migration` 装饰器注册迁移规则。

### 5.5.1 模块列表

| 模块 | 功能 |
|---|---|
| `__init__.py` | 公开 API 入口 |
| `registry.py` | `@register_migration` 装饰器 + `get_migrations()` + `get_latest_version()` |
| `state.py` | `MigrationState` 持久化到 `data/migrations.json`（原子写盘） |
| `runner.py` | `run_migrations()` 主逻辑，fail-soft 单条规则失败不阻塞 |
| `rules/v3_0_to_v3_1.py` | v3.0→v3.1 迁移规则 (2 条: split_modes + rename) |

### 5.5.2 核心 API

```python
@register_migration(from_version=1, to_version=2)
def my_rule(config: dict) -> dict:
    return config

state = MigrationState(data_dir).load_or_init()
new_config, new_state = run_migrations(config, state)
```

### 5.5.3 设计决策

- **Registry 模式**: 可扩展，加新规则只追加代码
- **Fail-soft**: 单条规则失败不阻塞其他规则
- **写盘顺序**: config 先写，state 后写（幂等）
- **集成点**: `main.py __init__` 中在 `build_modules()` 之前运行

---

## §6 第二层:`sylanne/` 内嵌 SylannEngine(46 modules)

`sylanne/` 是**从外部 SylannEngine fork 进来**的引擎实现(per ADR-0003/0008)。共 46 模块,其中 13 顶层 + 33 子模块(`compute/`)。

### 6.1 顶层模块(13)

| 模块 | 功能 |
|---|---|
| `__init__.py` | 公共 API 入口(SylanneEngine, SylanneConfig 等) |
| `algebra.py` | Affective Algebra(SPEC §7 代数运算) |
| `adapter.py` | Surface adapter(内核输出 → SPEC Surface dict) |
| `assessor.py` | LLM 文本情绪评估 |
| `bridge.py` | Layer 0 ↔ Full Engine 自然变换 |
| `config.py` | 配置 dataclass |
| `contagion.py` | 多 Agent 情绪传染协议 |
| `engine.py` | 公共入口 `SylanneEngine` |
| `expression.py` | PAD 状态 → 输出模态(blend / motor / prosody / text) |
| `interchange_validator.py` | interchange 格式验证 |
| `schema.py` | 序列化验证(零依赖) |
| `standard.py` | Layer 0 最小情感计算核 |
| `types.py` | 类型定义(Surface, PADOutput, EngineStatus) |

### 6.2 `sylanne/compute/` 子模块(33)

按"计算脊柱"7 层分类:

| 类别 | 模块 |
|---|---|
| **L1 HDC** | `hdc.py`(超维计算编码器) |
| **L2 预测编码** | `predictive_coding.py`(预测编码门控) |
| **L3 伤痕-空洞** | `scar_algebra.py`, `void_calculus.py`, `void_scar_engine.py`(伤痕 + 空洞 + 耦合) |
| **L4 关系层论** | `relational_sheaf.py`, `social_field.py`(Sheaf Theory) |
| **L5 异构图** | `hgt.py`, `hgt_numpy.py`(MoE-HGT 异构图 Transformer) |
| **L6 自创生** | `autopoiesis.py`, `body.py`, `personality.py`(自创生边界 + 双向人格) |
| **L7 相变** | `phase_transition.py`(相变表达触发) |

**横向工具**:
- `attention.py`(身体注意力)
- `bounded_dict.py`(LRU + TTL)
- `cascade_engine.py` (注:同名 memory/ 也有,但是不同概念)
- `codec.py`(序列化)
- `computation_spine.py`(统一计算脊柱)
- `coupling_dynamics.py`(耦合动力学)
- `emergence.py`(涌现检测)
- `host.py`(会话宿主)
- `hot_pool.py`(热池 + 人格坍缩)
- `importer.py`(旧版数据导入)
- `kernel.py`(调度器)
- `pad_interop.py`(PAD 互操作)
- `prompt_surface.py`(Prompt 表面)
- `resonance_field.py`(Simplicial 共振场,核心)
- `resonance_integration.py`(共振集成, ComputationSpine 替代)
- `runtime.py`(文件持久化)
- `shadow_memory.py`(影子记忆)
- `utils.py`(异步工具)
- `vector.py`(向量工具)
- `workset.py`(工作集)

### 6.3 `sylanne/` 总结

`sylanne/` 是**计算引擎实现**。理论上不依赖 emotion_spirit 主体,通过 `bridge/` 对接。R3 把它重命名(原 `sylanne_core` → `sylanne`),物理隔离外部 Sylanne 插件。

---

## §7 根目录文件(5 个)

### 7.1 `emotion_spirit/__init__.py` — 根包初始化

**功能**:
- 显式 import 所有 30 个 `@register` 装饰模块(触发 DI 注册)
- 触发 v1.x 兼容层(`_DeprecatedImportFinder` meta_path hook)
- 暴露 `__version__`

**设计**:
- 单一副作用入口:任何 `import emotion_spirit` 都会触发完整注册
- 37 个 v1.x redirect 映射(v1 路径 → v2 路径 + DeprecationWarning)

### 7.2 `emotion_spirit/_version.py`

**功能**:`__version__ = "1.0.0"`,PEP 440 兼容。

**设计**:`pyproject.toml` 用 `dynamic = ["version"]` 从这里 attr 读。

### 7.3 `emotion_spirit/_v1_compat.py` — v1.x 兼容垫片

**功能**:**v1.x API 的薄包装 + DeprecationWarning**。

**设计**:
- v2.1 删除(届时所有 v1 调用点都应已迁移)
- 当前 v1 path 还能 import,hook 静默 no-op

### 7.4 `emotion_spirit/layer.py` — 4 层装饰器

**功能**:**强制层间访问**的 2 个装饰器:
- `@per_user_only`: 强制 caller 提供 `user_id` 参数
- `@global_only`: 拒绝方法定义包含 `user_id` 参数
- 异常: `LayerViolationError`

**设计**:
- 用 `inspect.signature.bind` 支持位置参数 + kwargs
- 不强制 `user_id` 为 kwarg-only(否则破坏现有 caller)

### 7.5 `emotion_spirit/store.py` — JSON 持久化

**功能**:**跨会话数据存储**,4 个 typed NS 访问器:
- `persona` namespace
- `pad_history` namespace(v1.2 schema v2)
- `pad_trajectory` namespace
- `memory_pools`(per-user)+ `social_graph`(schema v3)

**设计**:
- 存储在 AstrBot `data/plugin_data/emotion_spirit/` 目录(不是插件自身目录)
- 旧 API(`store.get(key)`, `store.set(key, val)`)仍向后兼容

---

## §8 第三层评估总结

### 8.1 框架质量评估

| 维度 | 评分 | 理由 |
|---|---|---|
| **分层清晰度** | 9/10 | 6 层职责明确,无循环依赖(`core ← memory ← regulation ← output` 单向) |
| **模块粒度** | 8/10 | 平均 ~600 LOC,合理;少数大文件(`superego.py` 866 行)可拆 |
| **命名一致性** | 9/10 | 顶层公开 API 一致;内部命名遵循 `<concern>_<role>` 模式 |
| **DI 完整性** | 9/10 | 30 ModuleSpec 注册,`registry.build(config)` 工厂模式 |
| **桥接隔离** | 9/10 | `bridge/` 4 模块,引擎可选降级;R3 sylanne 物理隔离 |
| **持久化设计** | 8/10 | 4 NS typed accessor;v1/v2/v3 schema 升级路径清晰 |
| **公开 API 治理** | 8/10 | v1.x redirect + DeprecationWarning;`output/public_api.py` 集中 |
| **心理学深度** | 9/10 | 12+ 理论,每个有对应模块(per [[emotion-spirit-direction]]) |
| **代码复用** | 8/10 | `output/trend_utils.py` 共享给 3 模块;但仍有重复(如 5 类 EMA 计算) |
| **测试覆盖** | 9/10 | 861 tests,5 namespace 隔离(R3 后);单元 + 集成覆盖完整 |
| **文档完整性** | 8/10 | 4 docs + 8 ADR;部分模块缺少 docstring 详细设计说明 |
| **总评** | **8.5/10** | 跟单 plugin 评估一致 |

### 8.2 强项

1. **0 第三方依赖**——所有功能 in-house,降低 supply chain 风险
2. **DI 模式**——30 模块统一注册,易测试 + 易扩展
3. **桥接隔离**——Sylanne 引擎可降级,bot 永远能跑
4. **持久化分层**——v1/v2/v3 schema 都有迁移路径
5. **心理学扎根**——理论→模块 1:1 映射,不是"挂着理论名"

### 8.3 弱项 + 改进方向

| 弱项 | 改进方向 | 优先级 |
|---|---|---|
| `superego.py` 866 行单文件,4 sub-module 混在一起 | 拆 4 文件:`value_resistance.py`, `value_alignment.py`, `conscience_tracker.py`, `ideal_self.py` | P1 (v3.1) |
| `sylanne/compute/` 33 个子模块,无 README 导航 | 加 `compute/README.md` 索引 + 7 层分类 | P2 |
| `output/buffer_signals.py` 的 6 维信号缺乏 unit test 边界 | 加 6 个边界 test(0/负值/极大值) | P2 |
| 部分模块 docstring 只说"是什么",不说"为什么" | 按 ADR 格式加 "Context / Decision / Alternatives" | P3 |
| 没有 E2E test | 引入 `pytest-astropy` 风格 mock AstrBot | P2 (per R4) |
| `core/knowledge.py` 数据 vs `core/config.py` 参数的边界模糊 | 明确"知识"标准(可热更新 vs 编译时常量) | P3 |

### 8.4 整体架构哲学总结

```
emotion_spirit 框架的 5 个核心原则:

1. 单向依赖 (无循环)
   core ← memory ← regulation ← output
   bridge 横切, sylanne 独立

2. 物理隔离 (而不是逻辑)
   - R3 sylanne rename 防 namespace 冲突
   - bridge/ 4 模块单独管理引擎集成
   - decorator (@per_user_only) 强制层间访问

3. 降级优先 (永远能跑)
   - Sylanne 引擎可降级为纯 emotion_spirit 模式
   - 公开 API 保留 v1.x 兼容层
   - Schema 升级有 v1/v2/v3 迁移路径

4. 理论扎根 (每个模块有依据)
   - 12+ 心理学理论 → 12+ 模块
   - 不是"理论装饰",是真有功能实现

5. DI 模式 (测试 + 扩展友好)
   - 30 ModuleSpec 统一注册
   - registry.build(config) 工厂
   - import 副作用触发完整注册
```

### 8.5 给新成员的"5 分钟理解"路径

```
1. 读本文 §0(6 层 + 联系图)               → 2 分钟
2. 读 core/layer.py(理解装饰器)            → 1 分钟
3. 读 core/registry.py(理解 DI)            → 1 分钟
4. 读 memory/memory_pool.py(理解核心数据)   → 1 分钟
5. 读 output/prompt_injector.py(理解输出)   → 1 分钟
   ─────────────────────────
   总计 5 分钟,可达 80% 框架理解
```

---

## Related

- [[emotion-spirit-direction-v2]] — 4 层架构哲学
- [[emotion-spirit-ecosystem-eval-2026-06-13]] — 单 plugin 评估
- [[emotion-spirit-progress]] — 当前状态
- `docs/DEVELOPMENT_HISTORY.md` — Phase 视角开发全史
- `docs/architecture.md` — 早期架构文档
- `docs/adr/` — 8 份 ADR(架构决策)
- `docs/adr/0001-four-layer-directory.md` — ADR-0001 4 层架构
- `docs/adr/0003-embed-sylanne-core.md` — ADR-0003 内嵌 Sylanne
