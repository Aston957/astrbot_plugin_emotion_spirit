# emotion_spirit v3.0 理论依据

> **目的**: 解释 emotion_spirit 每个机制背后的理论来源, 帮助 maintainer 理解设计意图, 避免无根据的"重构".
> **范围**: v3.0 收尾涉及的所有理论, 涵盖 Phase 0.5-3.0C + Phase 4 (C1-C5).
> **面向**: Maintainer + 对 AI 情感建模感兴趣的研究者.

---

## 1. 心理学基础

### 1.1 弗洛伊德人格结构 (Id / Ego / Superego)

emotion_spirit 整体架构的隐喻来源。SylannEngine (sylanne_core 已内嵌于 v3.0) 处理 Id (即时情感, ms ~ hr), emotion_spirit v3.0 处理 Ego (长期记忆 + 人格演化, hr ~ month) + Superego (价值对齐 + 良心压力, 贯穿).

**Source**: Freud, S. (1923). *Das Ich und das Es* (The Ego and the Id).

### 1.2 荣格分析心理学 (阴影 / 投射 / 自性)

`ShadowDetector` 模块的实现基础。识别用户的"回声模式" (用户反复说但自己没意识到) / "回避模式" (用户避免讨论的话题) / "确认偏差" (用户只接受符合预期人格的信息).

**Source**: Jung, C. G. (1968). *The Archetypes and the Collective Unconscious*. Princeton University Press.

### 1.3 依恋理论 (Bowlby + Ainsworth)

`IntimacyTracker` 6 维亲密度 (warmth / trust / dependence / security / familiarity / longing) 的设计来源。每个关系独立的人格参数 (`RelationshipPersonality`) 来自 Bowlby 的"内部工作模型" (Internal Working Model, IWM) 概念: 每个人对不同对象有不同 IWM, 不应一视同仁.

**Sources**:
- Bowlby, J. (1969). *Attachment and Loss, Vol. 1: Attachment*. Basic Books.
- Ainsworth, M. D. S., et al. (1978). *Patterns of Attachment*. Lawrence Erlbaum.
- Mikulincer, M., & Shaver, P. R. (2007). *Attachment in Adulthood*. Guilford Press.

### 1.4 大五人格 (OCEAN)

`KnowledgeBase` 13 维人格参数的设计来源。Phase 1.5 引入 11 维 (5 深层 Embodiment Five: warmth / stability / curiosity / creativity / self_reflect + 6 表层 Sylanne Six: social_anxiety / expression_needs / connection_circulation / emotional_depth / repair_heat). Phase 3 增 2 维 (perception_acuity + directness). v1.7 拆 autonomy_strength → autonomy_strength + exploration_openness (ISTJ 跟 ENTP 区分更细). v1.7.2 +gossip_tendency (HEXACO H + E 维度支撑).

**当前 13 维 (代码真值)** = 5 deep (expression_drive, perception_acuity, boundary_permeability, inner_coherence, relational_gravity) + 8 surface (warmth_bias, directness, curiosity, patience, intimacy_pull, relational_autonomy, exploration_openness, gossip_tendency).

**Sources**:
- McCrae, R. R., & Costa, P. T. (1992). *Revised NEO Personality Inventory (NEO-PI-R)*. Psychological Assessment Resources.
- McCrae, R. R. (2009). *The five-factor model of personality traits*. Corsini Encyclopedia of Psychology.

### 1.5 PAD 情绪模型 (Russell-Mehrabian-Fontaine)

`EmotionClassifier` 的核心算法。3 维: valence (正负) / arousal (激动) / dominance (支配). 概率分布 (7 类情绪) 跟 PAD 互为正交表征, 不损失信息.

**Sources**:
- Russell, J. A., & Mehrabian, A. (1977). *Evidence for a three-factor theory of emotions*. Journal of Research in Personality, 11(3), 273-294.
- Fontaine, J. R., Scherer, K. R., Roesch, E. B., & Ellsworth, P. C. (2007). *The world of emotions is not two-dimensional*. Psychological Science, 18(12), 1050-1057.
- Juslin, P. N., & Laukka, P. (2003). *Communication of emotions in vocal expression and music performance*. Psychological Bulletin, 129(5), 770-814.

### 1.6 复合情绪 (Compound Emotions)

7 类情绪概率分布的理论基础。emotion_spirit 用 7 个基本情绪 (joy / sadness / anger / fear / surprise / disgust / neutral) + 概率分布, 而不是 single label.

**Source**: Li, S., et al. (2017). *RAF-DB: Real-world Affective Faces Database*. (RAF-DB compound emotion labels).

---

## 2. 神经科学 / 认知科学基础

### 2.1 整合信息理论 (Integrated Information Theory, IIT)

`MemoryPool` 的 Φ 门控 (Phase 2) 灵感来源。一条消息的 Φ (整合信息) 决定是否值得进入温池. Φ 高 = 消息携带大量新信息, 值得记住; Φ 低 = 重复或无意义, 走遗忘曲线.

**Source**: Tononi, G. (2004). *An information integration theory of consciousness*. BMC Neuroscience, 5(1), 42.

### 2.2 艾宾浩斯遗忘曲线 (Ebbinghaus Forgetting Curve)

`MemoryPool` 自然衰减 + `IntimacyTracker` 强化机制. 记忆随时间指数衰减, 被召回 (提到 / 关联) 时强化 (跟 SylannEngine 的 recall 信号挂钩).

**Source**: Ebbinghaus, H. (1885). *Über das Gedächtnis* (Memory: A Contribution to Experimental Psychology).

### 2.3 情绪双稳态 (Bistable Emotion)

`PersonalityDrift` 的"停滞" / "循环" 弧生成来源. 情绪系统在两个稳态间切换, 而非单调变化. 实证支持: PNAS 2014.

**Source**: Kuppens, P., & Verduyn, P. (2017). *Emotion dynamics and mood disorders*. Psychological Inquiry, 28(2-3), 158-162.

---

## 3. LLM Agent 基础

### 3.1 LangChain Memory 抽象 (Phase 2 启发)

`MemoryPool` 4 层设计 (缓冲池 / 温池 / 冷池 / 幽灵) 受 LangChain ConversationBufferMemory / ConversationSummaryMemory / VectorStoreMemory 的层级抽象启发, 但 emotion_spirit 加了"幽灵"层 (永久创伤, 不可遗忘) + Φ 门控.

**Source**: Chase, H. (2022). *LangChain Documentation*. (4-tier memory design)

### 3.2 Persona 系统 (Phase 2.5 亲密度分化)

`PersonaProfile` + `RelationshipPersonality` 的"per-relationship 独立人格"灵感来源. LangChain 跟其他 LLM 框架的 persona 多是全局共享, emotion_spirit 选择 per-relationship 独立, 因为 IWM (Bowlby) 在真实心理学中就是 per-object 的.

### 3.3 Tool/Function Calling (Phase 2 钩子)

`on_llm_request()` / `on_llm_response()` 钩子设计跟 OpenAI Function Calling / Anthropic Tool Use 抽象对齐. emotion_spirit 在 `on_llm_request` 阶段修改 `request.system_prompt` 注入情感上下文, 不修改 `request.prompt` (避免污染历史).

**Sources**:
- OpenAI (2023). *Function Calling and Other API Updates*. Blog post.
- Anthropic (2024). *Tool Use (Function Calling) Documentation*.

### 3.4 Prompt Injection Best Practices

`PromptInjector` 的 6 sections 设计 (印象 / 日记 / 关系 / 超我 / 阴影 / 理想) 来自 Anthropic Claude / OpenAI GPT 的 system_prompt 设计经验. 关键决策: 不污染历史 (`extra_user_content_parts` vs `request.prompt`), ephemeral context 走 `system_prompt`.

**Sources**:
- Anthropic (2024). *Claude Prompt Engineering Documentation*.
- OpenAI (2024). *GPT Best Practices*.

---

## 4. 三元力学 (Three-Force Dynamics, Phase 3)

### 4.1 社会生态学 (Bronfenbrenner)

`natural / social / individual` 3 维灵感来源. Bronfenbrenner 提出微观 / 中观 / 宏观系统 (microsystem / mesosystem / macrosystem), emotion_spirit 简化为 3 维:
- natural: 自然本能 (mimicry, 生理反应, 进化适应)
- social: 社会规范 (道德, 关系, 群体压力)
- individual: 个体理性 (自我价值, 长期目标, 自主决策)

**Source**: Bronfenbrenner, U. (1979). *The Ecology of Human Development*. Harvard University Press.

### 4.2 道德基础理论 (Moral Foundations Theory)

social 维度的细化来源. Haidt 提出 6 大道德基础 (care / fairness / loyalty / authority / sanctity / liberty), emotion_spirit 简化进 social 维度.

**Source**: Haidt, J. (2007). *The New Synthesis in Moral Psychology*. Science, 316(5827), 998-1002.

### 4.3 自我决定理论 (Self-Determination Theory, SDT)

individual 维度的细化来源. Deci & Ryan 提出 3 大基本心理需求 (autonomy / competence / relatedness), emotion_spirit 用 individual 维度覆盖 autonomy + competence.

**Source**: Deci, E. L., & Ryan, R. M. (2000). *The "What" and "Why" of Goal Pursuits*. Contemporary Educational Psychology, 25(1), 68-81.

### 4.4 算法 H (Phase 3 力学计算)

`ForceDynamics.compute()` 的 5 fixture × 8 场景仿真 + P95 分位 baseline 来源. 5 fixture = 5 种典型人格代表 (INFP / ISTJ / ENTP / ISFJ / ESTP), 8 场景 = 8 种典型对话场景 (亲密度增长 / 创伤消化 / 工作压力 / 家庭冲突 / 自我反思 / 群体讨论 / 道德抉择 / 创造性表达). 27-sum fallback 应对 KB miss.

**Source**: emotion_spirit 内部 spec (`docs/superpowers/specs/2026-06-07-emotion-spirit-phase-30a-three-force-engine.md`).

---

## 5. Phase 4 C1 ConscienceTracker B2 算法

### 5.1 滑动窗口分位归一化

Phase 4 C1 改造 ConscienceTracker 哲学基础: 累加器是真相源 (raw, 无上限), 消费时归一化. 算法选择 P95 滑动窗口:

- **累加器保留 raw**: 反映真实心理动能累积, 不被 hard clip 掩盖
- **P95 滑动窗口**: 给极端事件留 5% headroom, 不让单一极端事件主导归一化
- **冷启动 (< 10 帧) 返回 raw**: 避免冷启动期归一化不稳定
- **极低压力 (P95 < 0.01) 返回 0.0**: 避免除零

**Source**: 内部 spec (`docs/superpowers/specs/2026-06-08-phase-4-launch-design.md` §4.2-4.4).

### 5.2 v1.x Hard-Clip 的问题

v1.x ConscienceTracker 用 `min(1.0, max(0.0, raw))` hard-clip. 后果: "持续 50 次小冲突" 跟 "持续 1 次大冲突" 在 `_pressure=1.0` 之后**完全无差异**, 下游 ForceDynamics 区分不了. Phase 4 C1 修.

**Deviation E 关闭**: spec §12.2 (C1 偏离, 2026-06-09).

---

## 6. 4 层目录结构的心理模型

### 6.1 认知分层 (Perception / Memory / Decision / Output)

`core / memory / regulation / output` 4 层架构灵感来源. 跟认知心理学的"感知-记忆-决策-输出"分层对齐:
- L0 core = 感知 (基础 registry + config + knowledge)
- L1 memory = 记忆 (4 层记忆池 + 亲密度 + 关系)
- L2 regulation = 决策 (三元力学 + ConscienceTracker + BodyState)
- L3 output = 输出 (BotDecision + PublicAPI + 各种 writer)

**Source**: Anderson, J. R. (2007). *How Can the Human Mind Occur in the Physical Universe?*. Oxford University Press. (ACT-R cognitive architecture)

### 6.2 严格单向依赖

L0 ← L1 ← L2 ← L3 严格单向依赖, 跟 ACT-R 的模块化设计原则一致. 反向依赖 = 循环 = 系统不收敛. `test_layer_dependency_no_reverse` enforce.

---

## 7. v3.0 收尾偏离记录 (Phase 4 累积)

完整 16 条偏离记录在 spec §12.2. 关键 4 条理论相关:

1. **C1 滑动窗口 P95 算法**: 内部 spec 决策, 不在外部文献, 但数学上等同 order statistics 估计
2. **C2 PEP 440 偏离**: 跟 Python 生态对齐, 跟学术无关
3. **C3 AST-aligned `__all__`**: 跟 Python typing best practice 一致
4. **C4 4 层依赖反向检测**: 跟软件工程 modular design 原则一致

---

## 8. 完整参考文献

(17 篇核心 + 5 篇 v3.0 引用)

1. Anderson, J. R. (2007). *How Can the Human Mind Occur in the Physical Universe?* Oxford University Press.
2. Ainsworth, M. D. S., et al. (1978). *Patterns of Attachment*. Lawrence Erlbaum.
3. Bowlby, J. (1969). *Attachment and Loss, Vol. 1: Attachment*. Basic Books.
4. Bronfenbrenner, U. (1979). *The Ecology of Human Development*. Harvard University Press.
5. Deci, E. L., & Ryan, R. M. (2000). *The "What" and "Why" of Goal Pursuits*. Contemporary Educational Psychology.
6. Ebbinghaus, H. (1885). *Über das Gedächtnis*.
7. Fontaine, J. R., et al. (2007). *The world of emotions is not two-dimensional*. Psychological Science.
8. Freud, S. (1923). *Das Ich und das Es* (The Ego and the Id).
9. Haidt, J. (2007). *The New Synthesis in Moral Psychology*. Science.
10. Jung, C. G. (1968). *The Archetypes and the Collective Unconscious*. Princeton University Press.
11. Juslin, P. N., & Laukka, P. (2003). *Communication of emotions in vocal expression and music performance*. Psychological Bulletin.
12. Kuppens, P., & Verduyn, P. (2017). *Emotion dynamics and mood disorders*. Psychological Inquiry.
13. Li, S., et al. (2017). *RAF-DB: Real-world Affective Faces Database*.
14. McCrae, R. R., & Costa, P. T. (1992). *Revised NEO Personality Inventory (NEO-PI-R)*. PAR.
15. McCrae, R. R. (2009). *The five-factor model of personality traits*. Corsini Encyclopedia.
16. Mikulincer, M., & Shaver, P. R. (2007). *Attachment in Adulthood*. Guilford Press.
17. Russell, J. A., & Mehrabian, A. (1977). *Evidence for a three-factor theory of emotions*. J. Research in Personality.
18. Tononi, G. (2004). *An information integration theory of consciousness*. BMC Neuroscience.

v3.0 引用 (Phase 3 + 4):
19. emotion_spirit. (2026-06-07). *Phase 3.0A Three-Force Engine Spec*. `docs/superpowers/specs/2026-06-07-emotion-spirit-phase-30a-three-force-engine.md`
20. emotion_spirit. (2026-06-07). *Phase 3.0C Persona Labels KB Spec*. `docs/superpowers/specs/2026-06-07-emotion-spirit-phase-30c-persona-labels-kb.md`
21. emotion_spirit. (2026-06-08). *Phase 4 Launch Design Spec*. `docs/superpowers/specs/2026-06-08-phase-4-launch-design.md`
22. emotion_spirit. (2026-06-08). *Phase 4 Launch Plan*. `docs/superpowers/plans/2026-06-08-phase-4-launch.md`
23. emotion_spirit. (2026-06-08). *Phase 3.0C Implementation Report*. `docs/superpowers/reports/2026-06-08-emotion-spirit-phase-30c-report.md`
