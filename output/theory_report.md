# 理论分析验证报告

**通过率**: 12/12 (100%)


## ✅ D-1: S曲线不动点

- **found**: [0.0, 0.499, 0.5, 0.501, 1.0]
- **expected**: [0.0, 0.5, 1.0]
- **结果**: 通过


## ✅ D-2: S曲线单调性

- **min_derivative**: 0.0
- **结果**: 通过


## ✅ D-3: S曲线端点

- **f0**: 0.0
- **f1**: 1.0
- **f05**: 0.5
- **结果**: 通过


## ✅ D-4: S曲线区分度增益

- **linear_ratio**: 0.994
- **s_curve_ratio**: 1.03
- **gain**: 1.036
- **结果**: 通过


## ✅ D-5: Top-K 核心维度区分度

- **core_dims**: [('boundary_permeability', 0.5625), ('curiosity', 0.5625), ('expression_drive', 0.5135), ('perception_acuity', 0.5135), ('warmth_bias', 0.5135)]
- **peripheral_dims**: [('directness', 0.1512), ('inner_coherence', 0.1501), ('relational_gravity', 0.1501), ('patience', 0.1501), ('intimacy_pull', 0.1498), ('autonomy_guard', 0.1488)]
- **core_mean**: 0.5331
- **peripheral_mean**: 0.15
- **ratio**: 3.55
- **结果**: 通过


## ✅ D-6: 基线引力衰减趋向0

- **values**: {'0': 0.3, '100': 0.290323, '1000': 0.225, '3000': 0.15, '10000': 0.069231, '100000': 0.008738}
- **结果**: 通过


## ✅ D-7: 基线引力半衰期

- **a0**: 0.3
- **a3000**: 0.15
- **ratio**: 0.5
- **结果**: 通过


## ✅ D-8: 基线引力方向

- **above_baseline**: {'deviation': 0.3, 'gravity': 0.09, 'effect': 'weight decreases (pulls toward baseline)'}
- **below_baseline**: {'deviation': -0.3, 'gravity': -0.09, 'effect': 'weight increases (pulls toward baseline)'}
- **at_baseline**: {'deviation': 0.0, 'gravity': 0.0, 'effect': 'no gravity'}
- **结果**: 通过


## ✅ D-9: 压力指数衰减

- **decay_rate**: 0.08
- **half_life_hours**: 8.3
- **expected_half_life**: ~8.3h
- **p_8h**: 0.5132
- **p_24h**: 0.1352
- **p_48h**: 0.0183
- **结果**: 通过


## ✅ D-10: EMA 收敛时间常量

- **alpha_fast**: 0.039
- **alpha_slow**: 0.004
- **tau_fast**: 25.6
- **tau_slow**: 250.0
- **结果**: 通过


## ✅ D-11: tension 分类映射

- **tension_map**: {'relational_gravity': 'guilt', 'intimacy_pull': 'guilt', 'warmth_bias': 'guilt', 'expression_drive': 'guilt', 'inner_coherence': 'doubt', 'curiosity': 'doubt', 'perception_acuity': 'doubt', 'directness': 'doubt', 'boundary_permeability': 'doubt', 'autonomy_guard': 'shame', 'patience': 'shame'}
- **checks**: {'autonomy_guard_is_shame': True, 'relational_gravity_is_guilt': True, 'inner_coherence_is_doubt': True, 'all_dims_covered': True, 'only_valid_types': True}
- **结果**: 通过


## ✅ D-12: EMA slope 方向

- **increasing_slope**: 0.1
- **decreasing_slope**: -0.1
- **stable_slope**: 0.0
- **结果**: 通过
