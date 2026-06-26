"""配置常量 — 所有数值参数集中定义。"""

from __future__ import annotations


__all__ = [
    "EMA_ALPHA",
    "BUFFER_POOL_CONFIG",
    "MEMORY_POOL_CONFIG",
    "UNIFIED_MEMORY_CONFIG",
    "INTIMACY_CONFIG",
    "DIARY_CONFIG",
    "SENTINEL_CONFIG",
    "SUPEREGO_CONFIG",
    "SAFETY_CONFIG",
    "TRAJECTORY_WINDOW",
    "PAD_SAVE_INTERVAL_SECONDS",
    "VELOCITY_BURST_THRESHOLD",
    "RHYTHM_LEARNER_CONFIG",
    "REALTIME_DISPATCH_CONFIG",
    "LIFE_SIM_V2_CONFIG",
    "REFLEX_LEARNER_CONFIG",
    "DREAM_CONFIG",
]


# ═══ EMA 平滑系数 ═══
EMA_ALPHA: dict[str, float] = {
    "phi": 0.05,
    "chi": 0.05,
    "sync_order": 0.10,
    "body_integration": 0.10,
    "body_criticality": 0.10,
}


# ═══ 缓冲池 (替代原热池) ═══
BUFFER_POOL_CONFIG: dict[str, int | float] = {
    "max": 30,
    "ttl_hours": 24,
    "confirm_phi_threshold": 0.4,
    "meaning_gate_base": 0.3,
    "meaning_gate_phi_weight": 0.7,
    "noise_threshold": 0.05,
    "intensity_override_threshold": 0.7,
    "bypass_ghost_weight": 0.9,
    "bypass_cold_phi": 0.7,
    "bypass_cold_weight": 0.8,
}


# ═══ 记忆池 ═══
MEMORY_POOL_CONFIG: dict[str, int | float] = {
    "warm_max": 500,
    "cold_max": 2000,
    "ghost_max": 50,
    "warm_to_cold_ttl_hours": 240,
    "cold_to_expire_ttl_hours": 720,
    "recall_boost": 0.05,
    "ebbinghaus_base_stability": 24.0,
}


# ═══ 统一记忆系统 ═══
UNIFIED_MEMORY_CONFIG: dict[str, int | float] = {
    "buffer_max": 30,
    "warm_max": 100,
    "cold_max": 500,
    "ghost_max": 50,
    "buffer_to_warm_temp": 0.5,
    "buffer_max_age_hours": 48,
    "warm_to_cold_temp": 0.2,
    "warm_ttl_hours": 72,
    "cold_weight_threshold": 0.05,
    "noise_threshold": 0.05,
    "ghost_temp_threshold": 0.9,
    "ghost_weight_threshold": 0.8,
    "ghost_ticks_required": 10,
    "cascade_relevance_threshold": 0.2,
    "cascade_hot_threshold": 0.7,
    "cascade_activation_count": 3,
}


# ═══ 亲密度 ═══
INTIMACY_CONFIG: dict[str, float | dict] = {
    "dimensions": [
        "temporal_depth",
        "interaction_freq",
        "vulnerability_exposure",
        "repair_history",
        "shared_narrative",
        "user_investment",
    ],
    "weights": {
        "temporal_depth": 0.20,
        "interaction_freq": 0.20,
        "vulnerability_exposure": 0.15,
        "repair_history": 0.15,
        "shared_narrative": 0.15,
        "user_investment": 0.15,
    },
    "modulation": {
        "alpha": 0.3,
        "beta": 0.3,
        "gamma": 0.1,
        "epsilon": 0.3,
    },
    "vulnerability_half_life_days": 14,
    "user_investment_half_life_days": 30,
}


# ═══ LifeSimulator v2 ═══
LIFE_SIM_V2_CONFIG: dict[str, int | float | bool] = {
    "plan_generate_hour": 2,
    "events_per_day_min": 3,
    "events_per_day_max": 5,
    "adaptation_threshold": 0.3,
    "enable_proactive_prompt": True,
    "sleep_start_hour": 23,
    "sleep_end_hour": 7,
}


# ═══ 日记 ═══
DIARY_CONFIG: dict[str, int | str] = {
    "schedule_hours": [14, 22],
    "max_recent_entries": 10,
    "llm_model": "default",
}


# ═══ 预警 ═══
SENTINEL_CONFIG: dict[str, int] = {
    "warning_threshold": 3,
    "critical_threshold": 5,
    "ema_window_days": 7,
    "long_trend_window_days": 30,
}


# ═══ 超我 ═══
SUPEREGO_CONFIG: dict[str, float | dict] = {
    "resistance_context_modifiers": {
        "body_criticality_boost": 0.15,
        "cascade_reduction": 0.70,
        "intimacy_reach_out_reduction": 0.30,
    },
    "tension_type_weights": {
        "anxious_profiles_guilt_bias": 0.6,
        "avoidant_profiles_doubt_bias": 0.6,
        "righteous_threshold": 0.3,
    },
    "pressure_decay_rate_per_hour": 0.08,  # v2: Roberts 元分析; "睡一觉好一半" 时间尺度; 半衰期≈8.3h
    "guard_reflex_conscience_multiplier": 0.30,
    "cascade_conscience_multiplier": 0.50,
    "alignment_base_relief": 0.12,  # v2: ACT guilt 是 value-orienting signal; 对齐行为应有意义减压
    "conscience_impact_coef": 0.15,  # v2: 突发式冲突下平衡压力 ~0.4; Tangney: guilt 是温和行为信号
    "repair_relief": {
        "simple": 0.08,
        "substantial": 0.15,
        "transformative": 0.25,
    },
    "reinforcement_rate": 0.01,
    "reinforcement_max": 0.30,
    # 权重分化参数 (B: S曲线 + Top-K + 基线引力)
    "weight_differentiation": {
        "top_k": 5,              # 核心维度数量 (ACT: 3-5)
        "noncore_ratio": 0.3,    # v2: Schwartz 价值观理论; 价值-注意力研究 2-5x; HEXACO facet 不均匀
        "anchor_base": 0.3,      # 基线锚定基础强度 (Roberts & DelVecchio)
        "anchor_decay": 3000,    # 锚定衰减半衰期 (交互次数)
        "stress_multiplier": 1.5, # 压力加成系数 (Bowlby)
    },
}


# ═══ 安全层 ═══
SAFETY_CONFIG: dict[str, float | int | bool | dict] = {
    "enabled": True,
    # Sentinel 超我信号阈值
    "pressure_rise_threshold": 0.6,
    "pressure_rise_baseline_hours": 24,
    "conflict_cluster_count": 3,
    "conflict_cluster_window_hours": 1,
    "alignment_decline_threshold": -0.3,
    "ideal_drift_threshold": 0.4,
    "guard_reflex_count": 2,
    "guard_reflex_window_hours": 1,
    # Prompt 调整参数
    "conscience_threshold_normal": 0.15,
    "conscience_threshold_warning": 0.08,
    "conscience_threshold_critical": 0.0,
    "alignment_show_count_normal": 3,
    "alignment_show_count_warning": 1,
    "alignment_show_count_critical": 1,
    # 修复建议参数
    "repair_max_values": 2,
    # critical 级别节流 (24h 内最多触发次数)
    "critical_max_per_day": 3,
}

# v1.2: 情绪动态表示配置
TRAJECTORY_WINDOW: int = 8                 # trajectory 环形缓冲大小（最近 N 帧）
PAD_SAVE_INTERVAL_SECONDS: int = 300       # pad_history/trajectory 持久化间隔（5 min）
VELOCITY_BURST_THRESHOLD: float = 0.05     # 情绪突变阈值（|Δvalence| 或 |Δarousal| > 此值记为 burst）


# ═══ 节律学习器 ═══
RHYTHM_LEARNER_CONFIG: dict[str, float] = {
    "intimacy_threshold": 0.6,           # 开始学习的亲密度阈值
    "default_blend": 0.6,                # 默认混合比例
    "default_max_part_chars": 48,        # 默认单段最大字符数
    "default_chars_per_second": 7.5,     # 默认打字速度
    "max_profiles": 200,                 # 最大 profile 数量
}


# ═══ 即时分段回复 ═══
REALTIME_DISPATCH_CONFIG: dict[str, float | int] = {
    "max_part_chars": 48,                # 单段最大字符数
    "chars_per_second": 7.5,             # 打字速度 (字符/秒)
    "resumption_gap_hours": 2,           # 对话恢复间隔 (小时)
    "max_breakpoints_per_session": 10,   # 每 session 最大断点数
}


# ═══ ReflexLearner ═══
REFLEX_LEARNER_CONFIG: dict[str, float] = {
    "learning_rate": 0.01,
    "delta_min": -0.2,
    "delta_max": 0.2,
    "behavior_engaged_seconds": 300.0,
    "behavior_ignored_seconds": 7200.0,
}


# ═══ Dream Generator ═══
DREAM_CONFIG: dict[str, float | int] = {
    "deep_sleep_llm_enabled": True,
    "sleep_deprivation_base_chance": 0.1,
    "dream_rounds_per_3h": 1,
}
