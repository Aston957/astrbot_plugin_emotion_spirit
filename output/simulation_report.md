# 蒙特卡洛模拟报告

**总轮次**: 1000


**参数版本**: v2 (基于知识库研究调整)
- pressure_decay_rate=0.08/hr (半衰期~8.3h)
- alignment_base_relief=0.12
- noncore_ratio=0.3 (核心:边缘≈3.3:1)
- righteous 阈值: alignment_ratio≥0.7 且 resistance≤0.5
- _ACTION_MISALIGN: hold/explore/recover/observe 减少冲突维度

## 1. 核心/边缘区分度

验收标准: ≥3.0x (noncore_ratio=0.3)

- 平均区分度: 5.47x
- 最小区分度: 3.92x
- 最大区分度: 7.59x
- 达到 3.0x 的轮次: 0
- **验收标准**: ≥ 3.0x → ✅ 通过

## 2. 基线引力衰减

- 0-100: mean_gap=0.0971, max_gap=0.1517, n=99
- 100-500: mean_gap=0.1705, max_gap=0.2089, n=400
- 500-1k: mean_gap=0.2389, max_gap=0.2540, n=500
- 1k-5k: mean_gap=0.2528, max_gap=0.2528, n=1

## 3. 压力分布

验收标准: critical(>0.6) 占比 <10%, 均值 <0.5

- 均值: 0.1192 ✅ (目标: <0.5)
- P50: 0.0574
- P95: 0.5580
- 最大: 0.9931
- critical(>0.6)占比: 4.60% ✅ (目标: <10%)

## 4. Tension 分类分布

验收标准: 应有 guilt/doubt/shame 分布, righteous ≤ 30%

- shame: 5.8%
- guilt: 4.8%
- doubt: 5.8%
- righteous: 83.6%
- **tension 分布**: ✅ 多类型分布
- **righteous 占比**: 83.6% ❌ (目标: ≤30%)

## 5. 安全层触发分布

- normal: 0.7%
- warning: 99.3%

## 6. 人格漂移轨迹

- 初始基线距离: 0.0029
- 最终基线距离: 0.2528
- 方向变化: {'deep.expression_drive': '+0.490', 'deep.perception_acuity': '-0.015', 'deep.boundary_permeability': '+0.093', 'deep.inner_coherence': '+0.055', 'deep.relational_gravity': '+0.063', 'surface.warmth_bias': '+0.244', 'surface.directness': '+0.206', 'surface.curiosity': '-0.085', 'surface.patience': '-0.252', 'surface.intimacy_pull': '+0.398', 'surface.autonomy_guard': '+0.336'}