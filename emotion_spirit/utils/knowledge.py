"""emotion_spirit 知识库 — 集中所有声明性数据 (Phase B, P3-2)。

Step 1: label_mapper 全量迁移 (thresholds + 5 persona baseline + 5 轴 delta, 155 项)
Step 2: emotion + narrative + tension (后续 task)
Step 3: 删旧字段 (后续 task)

所有 persona/情绪/叙事/threshold 的"事实性数据"统一在此调用, 不再散在 6 个文件。
算法逻辑仍留在原模块, 但数据查询走 KnowledgeBase.X 路径。
"""
from __future__ import annotations
from typing import Any



__all__ = [
    "KnowledgeBase",
]

class KnowledgeBase:
    """统一知识库 — 声明性数据 + 查询 API。"""

    # ═══ 1. 13 维 personality (含 gossip_tendency) ═══
    PERSONALITY_DIMS_DEEP: frozenset[str] = frozenset({
        "expression_drive", "perception_acuity", "boundary_permeability",
        "inner_coherence", "relational_gravity",
    })
    PERSONALITY_DIMS_SURFACE: frozenset[str] = frozenset({
        "warmth_bias", "directness", "curiosity", "patience",
        "intimacy_pull", "relational_autonomy", "exploration_openness",
        "gossip_tendency",
    })
    ALL_PERSONALITY_DIMS: frozenset[str] = (
        PERSONALITY_DIMS_DEEP | PERSONALITY_DIMS_SURFACE
    )

    # ═══ 2. (deleted Phase 3.0A) PERSONA_BASELINES → compute_baseline_from_labels ═══
    # 5 persona 硬编码 baseline 已删除, 改走 5 标签等权公式动态计算 (单一数据源原则)。
    # 查询: KnowledgeBase.compute_baseline_from_labels({...labels...})
    # 5 fixture (INFP-A/ISTJ-S/ENTP-AV/ISFJ-D/ESTP-A) 见 tests/conftest.py (Task 2 加)

    # ═══ 3. 5 轴标签 delta (按类型) ═══
    MBTI_LETTER_DELTAS: dict[str, dict[str, float]] = {
        "I": {"expression_drive": -0.10, "warmth_bias": -0.05, "intimacy_pull": -0.10, "exploration_openness": -0.05, "gossip_tendency": -0.10},
        "E": {"expression_drive": +0.15, "warmth_bias": +0.10, "intimacy_pull": +0.10, "exploration_openness": +0.05, "gossip_tendency": +0.10},
        "N": {"curiosity": +0.15, "perception_acuity": +0.05, "boundary_permeability": +0.10, "exploration_openness": +0.20},
        "S": {"curiosity": -0.10, "perception_acuity": -0.05, "inner_coherence": +0.05, "exploration_openness": -0.15},
        "F": {"warmth_bias": +0.20, "relational_gravity": +0.15, "intimacy_pull": +0.15, "relational_autonomy": -0.05, "gossip_tendency": +0.05},
        "T": {"warmth_bias": -0.10, "directness": +0.10, "inner_coherence": +0.05, "relational_autonomy": +0.10},
        "P": {"boundary_permeability": +0.15, "patience": -0.10, "relational_autonomy": -0.05},
        "J": {"inner_coherence": +0.05, "patience": +0.05, "relational_autonomy": +0.05},
    }
    ATTACHMENT_DELTAS: dict[str, dict[str, float]] = {
        "安全型": {"boundary_permeability": +0.10, "inner_coherence": +0.10, "intimacy_pull": +0.05, "relational_autonomy": +0.05, "exploration_openness": +0.10, "curiosity": +0.05, "perception_acuity": +0.05},
        "焦虑型": {"boundary_permeability": +0.25, "inner_coherence": -0.20, "intimacy_pull": +0.30, "relational_autonomy": -0.15, "exploration_openness": -0.05, "expression_drive": +0.15, "gossip_tendency": +0.10},
        "回避型": {"boundary_permeability": -0.20, "inner_coherence": +0.10, "intimacy_pull": -0.20, "relational_autonomy": +0.20, "exploration_openness": -0.15, "gossip_tendency": -0.05},
        "混乱型": {"boundary_permeability": +0.10, "inner_coherence": -0.30, "intimacy_pull": +0.20, "relational_autonomy": -0.10, "exploration_openness": +0.05},
    }
    EMOTION_STYLE_DELTAS: dict[str, dict[str, float]] = {
        "压抑型": {"expression_drive": -0.20, "warmth_bias": -0.05, "relational_autonomy": +0.10},
        "表达型": {"expression_drive": +0.20, "warmth_bias": +0.10, "relational_autonomy": -0.05, "gossip_tendency": +0.05, "curiosity": +0.03},
        "波动型": {"inner_coherence": -0.15, "relational_autonomy": -0.05},
        "稳定型": {"inner_coherence": +0.10, "relational_autonomy": +0.05, "perception_acuity": +0.05},
    }
    CONFLICT_STYLE_DELTAS: dict[str, dict[str, float]] = {
        "攻击型": {"directness": +0.15, "relational_autonomy": +0.10, "relational_gravity": -0.10, "gossip_tendency": +0.05},
        "顺应型": {"warmth_bias": +0.10, "relational_autonomy": -0.05, "directness": -0.10},
        "合作型": {"warmth_bias": +0.05, "directness": +0.05, "relational_autonomy": 0.0, "perception_acuity": +0.03},
        "回避型": {"boundary_permeability": -0.10, "relational_autonomy": +0.05, "relational_gravity": -0.05},
    }
    TIME_FOCUS_DELTAS: dict[str, dict[str, float]] = {
        "活在过去": {"relational_gravity": +0.10, "patience": +0.10, "exploration_openness": -0.10},
        "活在当下": {"patience": +0.05, "relational_gravity": +0.05},
        "活在未来": {"exploration_openness": +0.15, "patience": -0.05, "relational_autonomy": -0.05, "curiosity": +0.05},
    }

    # ═══ 4. 数值阈值 ═══
    THRESHOLDS: dict[str, Any] = {
        "intimacy_segments": (0.65, 0.40, 0.15, 0.0),
        "lifecycle_intimate_intimacy": 0.75,
        "lifecycle_intimate_repair": 5,
        "lifecycle_close_intimacy": 0.5,
        "lifecycle_close_repair": 2,
        "lifecycle_acquaintance_intimacy": 0.2,
        "lifecycle_acquaintance_temporal": 168,
        "buffer_capacity": 30,
        "buffer_dwell_seconds": 86400,
        "buffer_7d_window": 7 * 86400,
        "confirmation_history_max": 200,
        "recent_expired_max": 50,
        "warm_max": 100,
        "cold_max": 50,
        "delta_clamp": (-0.3, +0.3),
        "deep_regression_rate": 0.005,
        "surface_regression_rate": 0.010,
        "trajectory_window": 8,
        "pad_save_interval_seconds": 300,
    }

    # ═══ 统一查询 API ═══

    @classmethod
    def get_delta_for_label(cls, label_type: str, label_value: str) -> dict[str, float]:
        """查 5 轴标签的 dim delta。"""
        delta_map = {
            "mbti": cls.MBTI_LETTER_DELTAS,
            "attachment": cls.ATTACHMENT_DELTAS,
            "emotion_style": cls.EMOTION_STYLE_DELTAS,
            "conflict_style": cls.CONFLICT_STYLE_DELTAS,
            "time_focus": cls.TIME_FOCUS_DELTAS,
        }
        if label_type not in delta_map:
            raise KeyError(f"未知标签类型: {label_type}")
        if label_value not in delta_map[label_type]:
            valid_values = list(delta_map[label_type].keys())
            raise KeyError(
                f"未知 label_value: '{label_value}' (类型 {label_type}, 合法值: {valid_values})"
            )
        return dict(delta_map[label_type][label_value])

    @classmethod
    def get_threshold(cls, name: str) -> Any:
        """查数值阈值。"""
        if name not in cls.THRESHOLDS:
            raise KeyError(f"未知阈值: {name}")
        return cls.THRESHOLDS[name]

    @classmethod
    def compute_baseline_from_labels(cls, labels: dict[str, str]) -> dict[str, float]:
        """5 标签 (任意组合) → 13-dim baseline (5 label 加权, 允许 > 1.0)。

        公式: baseline[dim] = 0.5 + Σ (delta_i × LABEL_WEIGHTS[i]) for label i affecting dim

        MBTI 特殊处理: "INFP" 等 4 字母组合, 逐字母从 MBTI_LETTER_DELTAS 取 delta,
        每字母都按 mbti 整体权重 (0.25) 计 (不再除以 4)。

        Args:
            labels: 任意子集 5 标签值, e.g. {"mbti": "INFP", "attachment": "安全型", ...}
                    缺 label 时跳过 (该 label 不贡献), 不会用 default。

        Returns:
            13-dim baseline dict (dim → float)
            允许 > 1.0 / < 0.0 (B 决策, 真实主义, 不 clamp)
            缺 label 不影响的 dim = 0.5 (中性)

        Raises:
            KeyError: 未知 label_type (strict mode, 不 silently skip)。
                     未知 label_value 由 get_delta_for_label 抛出。
                     MBTI 不存在的字母被忽略 (向后兼容 labels_to_personality 行为)。
        """
        baseline = {dim: 0.5 for dim in cls.ALL_PERSONALITY_DIMS}
        for label_type, label_value in labels.items():
            if label_type not in cls.LABEL_WEIGHTS:
                raise KeyError(
                    f"未知 label_type: '{label_type}' (合法: {list(cls.LABEL_WEIGHTS.keys())})"
                )
            weight = cls.LABEL_WEIGHTS[label_type]
            if label_type == "mbti":
                # MBTI 4 字母组合, 逐字母应用 deltas
                for letter in label_value.upper():
                    if letter in cls.MBTI_LETTER_DELTAS:
                        for dim, delta in cls.MBTI_LETTER_DELTAS[letter].items():
                            baseline[dim] += delta * weight
            else:
                deltas = cls.get_delta_for_label(label_type, label_value)
                for dim, delta in deltas.items():
                    baseline[dim] += delta * weight
        return baseline

    @classmethod
    def get_cross_persona_std(cls, dim: str) -> float:
        """查 13 维跨人方差 (B 纯文献)。

        统一 API 风格 — 未知 dim 抛 KeyError, 与 get_threshold / get_delta_for_label / get_narrative_template 一致。
        """
        if dim not in cls.DIM_CROSS_PERSONA_STD:
            raise KeyError(
                f"未知 dim: {dim} (13 维: {list(cls.DIM_CROSS_PERSONA_STD.keys())})"
            )
        return cls.DIM_CROSS_PERSONA_STD[dim]

    # ═══ 5. 情绪区域 (emotion_classifier 迁移) ═══
    CATEGORICAL_REGIONS: dict[str, dict[str, tuple[float, float]]] = {
        "joy": {"valence": (0.3, 1.0), "arousal": (0.3, 0.7), "dominance": (0.4, 1.0)},
        "anger": {"valence": (-1.0, -0.2), "arousal": (0.6, 1.0), "dominance": (0.6, 1.0)},
        "sadness": {"valence": (-1.0, -0.2), "arousal": (0.0, 0.4), "dominance": (0.0, 0.4)},
        "fear": {"valence": (-1.0, -0.2), "arousal": (0.5, 1.0), "dominance": (0.0, 0.4)},
        "surprise": {"valence": (-1.0, 1.0), "arousal": (0.7, 1.0), "dominance": (0.0, 1.0)},
        "disgust": {"valence": (-1.0, -0.4), "arousal": (0.3, 0.6), "dominance": (0.4, 1.0)},
        "neutral": {"valence": (-0.2, 0.2), "arousal": (0.3, 0.5), "dominance": (0.0, 1.0)},
    }
    COMPOUND_REGIONS: dict[str, dict[str, Any]] = {
        "sad_excitement": {"valence": (-0.8, -0.2), "arousal": (0.6, 1.0), "dominance": (0.0, 0.4), "primary": "sadness", "secondary": "excitement"},
        "angry_despair": {"valence": (-1.0, -0.4), "arousal": (0.7, 1.0), "dominance": (0.5, 1.0), "primary": "anger", "secondary": "despair"},
        "joyful_anxiety": {"valence": (0.2, 0.8), "arousal": (0.6, 1.0), "dominance": (0.3, 0.7), "primary": "joy", "secondary": "anxiety"},
        "sad_calm": {"valence": (-0.6, -0.1), "arousal": (0.0, 0.4), "dominance": (0.0, 0.4), "primary": "sadness", "secondary": "calm"},
    }
    EMOTION_ZH: dict[str, str] = {
        "joy": "喜悦", "anger": "愤怒", "sadness": "悲伤", "fear": "恐惧",
        "surprise": "惊讶", "disgust": "厌恶", "neutral": "平静",
        "excitement": "激动", "despair": "绝望", "anxiety": "紧张", "calm": "宁静",
    }

    # ═══ 6. 叙事模板 (persona_profiles 迁移, 66 条) ═══
    NARRATIVE_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
        "relational_gravity": {
            "high": {"violation": "你最近好像忽略了那些你在乎的人", "alignment": "你一直在用心对待身边的人", "advice": "试着主动联系一个你想念的人"},
            "low": {"violation": "你和人之间的距离好像变远了", "alignment": "你最近在试着靠近别人", "advice": "也许该给自己一个和人连接的机会"},
        },
        "intimacy_pull": {
            "high": {"violation": "你好像在回避亲密感", "alignment": "你最近在敞开心扉", "advice": "试着对一个人说出你真实的想法"},
            "low": {"violation": "你最近有点太封闭了", "alignment": "你最近保持着合适的距离", "advice": "不需要勉强自己, 但可以试着打开一点点"},
        },
        "warmth_bias": {
            "high": {"violation": "你最近对人的温暖减少了", "alignment": "你最近在用温暖待人", "advice": "试着对身边的人表达你的关心"},
            "low": {"violation": "你最近有点太冷淡了", "alignment": "你最近保持着冷静", "advice": "也许可以给身边的人一点温度"},
        },
        "expression_drive": {
            "high": {"violation": "你最近说的话太多了", "alignment": "你最近表达很清晰", "advice": "有时候听比说更重要"},
            "low": {"violation": "你最近有点压抑了", "alignment": "你最近保持着安静", "advice": "也许该对一个人说出你的想法"},
        },
        "directness": {
            "high": {"violation": "你最近说话太直接了", "alignment": "你最近表达很直接", "advice": "有时候委婉一点更有效"},
            "low": {"violation": "你最近太绕弯子了", "alignment": "你最近说话委婉", "advice": "也许该直接说出来了"},
        },
        "curiosity": {
            "high": {"violation": "你最近太爱追问了", "alignment": "你最近对新事物很感兴趣", "advice": "也许该停下来欣赏眼前的事物"},
            "low": {"violation": "你最近对新事物没兴趣", "alignment": "你最近专注在手头的事", "advice": "也许可以试一下新的东西"},
        },
        "patience": {
            "high": {"violation": "你最近太能忍了", "alignment": "你最近很有耐心", "advice": "有些事该说'不'了"},
            "low": {"violation": "你最近太急躁了", "alignment": "你最近节奏很快", "advice": "慢一点, 让事情自然发生"},
        },
        "boundary_permeability": {
            "high": {"violation": "你的边界被侵犯了", "alignment": "你最近能维护自己的边界", "advice": "有些事可以拒绝"},
            "low": {"violation": "你最近太封闭了", "alignment": "你最近边界清晰", "advice": "也许可以开放一点, 让人进来"},
        },
        "inner_coherence": {
            "high": {"violation": "你最近有点分裂", "alignment": "你最近内在很一致", "advice": "也许该停下来听一下自己"},
            "low": {"violation": "你最近内在不一致", "alignment": "你最近很稳定", "advice": "也许该重新审视自己的方向"},
        },
        "relational_autonomy": {
            "high": {"violation": "你最近太独立了", "alignment": "你最近有清晰的边界", "advice": "也许可以接受一下别人的帮助"},
            "low": {"violation": "你最近太依赖了", "alignment": "你最近在适度依赖", "advice": "也许该学会说'不'了"},
        },
        "exploration_openness": {
            "high": {"violation": "你最近太爱尝试了", "alignment": "你最近对新输入很开放", "advice": "也许该停下来反思"},
            "low": {"violation": "你最近太保守了", "alignment": "你最近很稳定", "advice": "也许可以试一下新的方向"},
        },
    }

    # ═══ 7. 变体选择规则 ═══
    VARIANT_KEY: dict[str, tuple[str, float]] = {
        "relational_gravity": ("warmth_bias", 0.5),
        "intimacy_pull": ("warmth_bias", 0.5),
        "warmth_bias": ("intimacy_pull", 0.3),
        "expression_drive": ("directness", 0.7),
        "inner_coherence": ("directness", 0.7),
        "curiosity": ("perception_acuity", 0.7),
        "perception_acuity": ("curiosity", 0.6),
        "directness": ("expression_drive", 0.5),
        "patience": ("warmth_bias", 0.5),
        "relational_autonomy": ("intimacy_pull", 0.3),
        "exploration_openness": ("curiosity", 0.5),
        "boundary_permeability": ("relational_autonomy", 0.6),
    }

    # ═══ 8. Tension 倾向 (superego 迁移, dim → guilt/doubt/shame) ═══
    # v1.7.2 Phase B Step 2: 共享 dim 重新分类 (Tangney 2002 shame-guilt theory)
    # - boundary_permeability: 旧 doubt → 新 shame (自我/自主 维度)
    # - directness: 旧 doubt → 新 shame (自我/自主 维度)
    # - patience: 旧 shame → 新 righteous (新增 "righteous" 类别)
    # - 加 value_resistance → value_conflict (Phase 1.5 superego 扩展)
    # - 加 gossip_tendency → righteous (HEXACO H 反向 + E 正向)
    # 数据漂移见 tests/test_knowledge_base.py parity xfail tests
    TENSION_INCLINATION: dict[str, str] = {
        "warmth_bias": "guilt", "intimacy_pull": "guilt",
        "relational_gravity": "guilt", "expression_drive": "guilt",
        "relational_autonomy": "shame", "boundary_permeability": "shame",
        "directness": "shame",
        "curiosity": "doubt", "perception_acuity": "doubt",
        "inner_coherence": "doubt", "exploration_openness": "doubt",
        "patience": "righteous", "value_resistance": "value_conflict",
        "gossip_tendency": "righteous",
    }

    # ═══ 9. 五标签等权 (Phase 3.0A) ═══
    # 依据: 5 label 各自的解释力近似平均, MBTI/time_focus 微调 (用户定)
    LABEL_WEIGHTS: dict[str, float] = {
        "mbti": 0.25,
        "attachment": 0.20,
        "emotion_style": 0.20,
        "conflict_style": 0.20,
        "time_focus": 0.15,
    }

    # ═══ 10. 跨人方差 (Phase 3.0A, B 纯文献) ═══
    # 13 维 std (跨人格典型方差), 用于 force_dynamics 算法 H 归一化。
    # 数值依据: HEXACO/Big5/Attachment 文献元分析 + 5 persona 经验校准
    DIM_CROSS_PERSONA_STD: dict[str, float] = {
        "warmth_bias": 0.20,
        "patience": 0.19,
        "boundary_permeability": 0.18,
        "relational_gravity": 0.20,
        "intimacy_pull": 0.22,
        "expression_drive": 0.20,
        "gossip_tendency": 0.22,
        "inner_coherence": 0.19,
        "curiosity": 0.20,
        "perception_acuity": 0.17,
        "directness": 0.20,
        "relational_autonomy": 0.25,
        "exploration_openness": 0.20,
    }

    # ═══ 11. 三元力学映射 (Phase 3.0A, Task 3) ═══
    # 13 维 → 3 force 映射。force_dynamics 算法 H 用。
    # 设计: three-force-framework memory §2.1
    # - 自然 (3 dim): warmth_bias, patience, boundary_permeability (前道德本能)
    # - 社会 (4 dim): relational_gravity, intimacy_pull, expression_drive, gossip_tendency
    # - 个体 (6 dim): inner_coherence, curiosity, perception_acuity, directness,
    #                 relational_autonomy, exploration_openness (自觉 + 独立判断)
    # 13 维全覆盖, 0 dim 缺失, 0 dim 重复
    DIM_FORCE: dict[str, str] = {
        # 自然
        "warmth_bias": "natural",
        "patience": "natural",
        "boundary_permeability": "natural",
        # 社会
        "relational_gravity": "social",
        "intimacy_pull": "social",
        "expression_drive": "social",
        "gossip_tendency": "social",
        # 个体
        "inner_coherence": "individual",
        "curiosity": "individual",
        "perception_acuity": "individual",
        "directness": "individual",
        "relational_autonomy": "individual",
        "exploration_openness": "individual",
    }

    # ═══ get_narrative_template API (Step 2 新增) ═══
    @classmethod
    def get_narrative_template(cls, dim: str, level: str, scene: str) -> str:
        """查叙事模板。"""
        if dim not in cls.NARRATIVE_TEMPLATES:
            raise KeyError(f"未知 dim: {dim}")
        if level not in cls.NARRATIVE_TEMPLATES[dim]:
            raise KeyError(f"未知 level: {level}")
        if scene not in cls.NARRATIVE_TEMPLATES[dim][level]:
            raise KeyError(f"未知 scene: {scene}")
        return cls.NARRATIVE_TEMPLATES[dim][level][scene]
