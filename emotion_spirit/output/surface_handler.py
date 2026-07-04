"""emotion_spirit Surface 处理器 (Phase B, P3-1 拆分)。

从 main.py 拆出 _consume_surface + _on_surface (B6.10)。
委托 plugin 访问 state, 不重写逻辑。
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING

from astrbot.api import logger

if TYPE_CHECKING:
    from main import EmotionSpiritPlugin



__all__ = [
    "SurfaceHandler",
]

class SurfaceHandler:
    """Surface 消费者 - 处理 SylannEngine 回调。

    接收 plugin 引用访问 state, latest_signals 字典由 plugin 持有。
    """

    def __init__(self, plugin: "EmotionSpiritPlugin", modules: dict[str, Any]) -> None:
        self._p = plugin
        self._modules = modules
        # 安全层状态 (每次 consume 后更新)
        self.safety_level: str = "normal"
        self.safety_note: str | None = None
        self.repair_advice: str | None = None

    def consume(
        self,
        session_id: str,
        surface: dict[str, Any],
        latest_signals: dict[str, Any],
    ) -> None:
        """处理 surface 回调, 更新所有 plugin 状态。

        Args:
            session_id: session ID
            surface: SylannEngine surface dict
            latest_signals: plugin._latest_signals 字典引用 (缓存 signals)
        """
        signals = self._p._consumer.consume(surface)

        # v1.1.1: 缓存最近一次 signals 供公开 API 读取
        latest_signals[session_id] = signals

        text = self._p._last_texts.get(session_id, "")
        user_id = session_id  # _resolve_user_id 是 no-op

        # Phase 1: 基础更新 (per-user)
        raw_weight = signals.damage_open + signals.valence_volatility + signals.cascade_intensity
        self._p._pool.add_for_user(
            user_id=user_id,
            text=text,
            raw_weight=raw_weight,
            phi=signals.phi_smoothed,
            tags=[signals.pad_primary, signals.decision_action],
            source_user=session_id,
        )
        confirmed = self._p._pool.confirm_check_for_user(user_id)

        logger.debug(
            "emotion_spirit surface: user=%s action=%s phi=%.3f weight=%.3f "
            "buffer=%d warm=%d confirmed=%d",
            session_id[:8], signals.decision_action, signals.phi_smoothed,
            raw_weight, len(self._p._pool.buffer_for(user_id)),
            len(self._p._pool.warm_for(user_id)), len(confirmed),
        )
        self._p._intimacy.update(
            session_id,
            temporal_hours=signals.relational_duration / 3600,
            interval_seconds=signals.relational_interval,
        )
        self._p._alignment.record(signals.decision_action)

        # ═══ 价值抵抗计算 ═══
        context = {
            "body_criticality": signals.body_criticality,
            "cascade_active": signals.cascade_active,
            "boundary_paused": signals.boundary_paused,
            "guard_risk_score": signals.guard_risk_score,
            "intimacy": self._p._intimacy.get_intimacy(
                session_id, self._p._current_persona,
            ) if session_id else 0.5,
        }
        current_personality = {
            "deep": signals.personality_deep or {},
            "surface": signals.personality_surface or {},
        }
        # PersonalityBridge: 5D Embodiment → 12D 映射 (如果 SylannEngine 提供 5D)
        if hasattr(self._p, '_personality_bridge') and self._p._personality_bridge:
            deep_5d = current_personality.get("deep", {})
            if deep_5d and len(deep_5d) <= 6:  # 5D 格式 (expression_drive 等)
                mapped_12d = self._p._personality_bridge.map_5d_to_12d(deep_5d)
                current_personality["deep"] = mapped_12d
        self._p._interaction_count += 1
        self._p._value_resistance._baseline_personality = self._p._baseline_personality
        self._p._value_resistance._interaction_count = self._p._interaction_count
        stress_level = min(1.0, signals.body_criticality + (0.5 if signals.cascade_active else 0.0))
        resistance_result = self._p._value_resistance.compute(
            action=signals.decision_action,
            context=context,
            current_personality=current_personality,
            stress_level=stress_level,
        )

        # ═══ 良心事件记录 ═══
        # v1.3.0 rc.2: 本轮走选项 C, record_* suppression_level 默认 0.0 (不动时序).
        # TODO(下一 rc, Bug-F?): 把 self._p._suppression_level 计算 (下方 line 145)
        #   前移到本块之前, 让 6 个 record_* 调用都能拿到真实 suppression_level.
        if resistance_result.conflict_values:
            self._p._conscience.record_value_conflict(
                resistance=resistance_result.resistance,
                conflict_values=resistance_result.conflict_values,
                tension_type=resistance_result.tension_type or "guilt",
                behavioral_shift=resistance_result.behavioral_shift,
                conscience_impact=resistance_result.conscience_impact,
            )
        elif resistance_result.aligned_values:
            for value_name in resistance_result.aligned_values:
                self._p._conscience.record_alignment(value_name, signals.decision_action)

        if not signals.guard_allowed:
            self._p._conscience.record_guard_reflex(
                signals.guard_risk_score, signals.decision_reason,
            )

        if signals.cascade_active:
            self._p._conscience.record_cascade(signals.cascade_intensity)

        self._p._conscience.record_collapse(signals.collapse_count)

        # ═══ 压抑系统 (SuppressionState) ═══
        from emotion_spirit.memory.suppression import SuppressionState
        if not hasattr(self._p, '_suppression'):
            self._p._suppression = SuppressionState()
        intimacy = self._p._intimacy.get_intimacy(session_id, self._p._current_persona) if session_id else 0.5
        conscience_pressure = self._p._conscience.get_pressure()
        suppression_context = {
            "authority_present": 0,
            "social_audience": 0,
        }
        self._p._suppression_level = self._p._suppression.compute(
            personality=current_personality.get("deep", {}),
            context=suppression_context,
            conscience_pressure=conscience_pressure,
            relationship_intimacy=intimacy,
        )

        # Phase 2: 演化层更新
        self._p._reservoir.accumulate(signals.phi_smoothed, raw_weight)
        self._p._drift.update(signals)
        if self._p._sentinel:
            self._p._sentinel.update(signals)
        if self._p._life_sim:
            self._p._life_sim.on_user_message()

        # ═══ PersonalityDrift ↔ IdealSelf 联动 ═══
        drifts = self._p._drift.check_drift()
        if drifts:
            for drift_info in drifts:
                dimension = drift_info["dimension"]
                direction = drift_info["direction"]
                slope = drift_info["slope"]

                delta = max(-0.05, min(0.05, slope * 10))
                if direction == "increasing":
                    delta = abs(delta)
                else:
                    delta = -abs(delta)

                self._p._ideal.update_reinforcement(dimension, delta)

        # ═══ 超我安全层: sentinel → superego_guard 链 ═══
        sentinel_result = self._p._sentinel.check() if self._p._sentinel else None
        current_personality = {
            "deep": signals.personality_deep or {},
            "surface": signals.personality_surface or {},
        }
        intervention = self._p._superego_guard.assess(sentinel_result, current_personality)
        self.safety_level = intervention.level
        self.safety_note = intervention.safety_note
        self.repair_advice = intervention.repair_advice

        if intervention.level == "critical":
            logger.warning(
                "emotion_spirit safety: user=%s level=%s reason=%s",
                session_id[:8], intervention.level, intervention.log_reason,
            )

            breakdown = self._p._conscience.get_pressure_breakdown()
            dominant_tension = breakdown.get("dominant_tension")
            if dominant_tension in ["guilt", "shame"]:
                recent_events = self._p._conscience.get_recent(hours=24)
                conflict_values: list[str] = []
                for event in recent_events:
                    if hasattr(event, "conflict_values") and event.conflict_values:
                        conflict_values.extend(event.conflict_values)
                conflict_values = list(set(conflict_values))[:5]

                # Bug-B (v1.2.10): 不再直接 record prompt 模板 (复读机).
                # LLM-on → 推队列, 后台 worker 调 LLM 生成正文再 record.
                # LLM-off → 不入队 (skip, 0 篇 > 12 篇假).
                if self._p._diary is not None and getattr(self._p._diary, "_llm_enabled", False):
                    self._p._diary_reflection_queue.append((dominant_tension, conflict_values, user_id))
                    logger.info(
                        "emotion_spirit: superego reflection enqueued (user=%s)",
                        session_id[:8],
                    )

        # 模式提取 (每 100 条) (Phase 2.0: per-user)
        user_warm = self._p._pool.warm_for(user_id)
        if len(user_warm) % 100 == 0 and len(user_warm) > 0:
            self._p._patterns.extract(user_id=user_id)

        # 幽灵共振 (Phase 2.0: per-user)
        if user_warm:
            boost = self._p._counterfactual.ghost_resonance(user_warm[-1], user_id=user_id)
            if boost > 0:
                user_warm[-1].emotional_weight = min(
                    1.0, user_warm[-1].emotional_weight + boost,
                )

        # 良心事件 → inject 队列
        if not signals.guard_allowed and self._p._engine:
            self._p._inject_queue.append((
                session_id, "validation",
                signals.guard_risk_score, "conscience",
            ))
            logger.info(
                "emotion_spirit guard_rejected: user=%s risk=%.3f reason=%s",
                session_id[:8], signals.guard_risk_score, signals.decision_reason,
            )

        # 级联事件日志
        if signals.cascade_active:
            logger.info(
                "emotion_spirit cascade: user=%s intensity=%.3f",
                session_id[:8], signals.cascade_intensity,
            )

        # Phase 1 观察期: Surface 数据落盘 (CSV)
        if self._p._surface_logger is not None:
            try:
                turn = self._p._interaction_count
                self._p._surface_logger.log(
                    session_id=session_id,
                    turn=turn,
                    personality=current_personality,
                    action=signals.decision_action,
                    resistance=resistance_result.resistance,
                    tension_type=resistance_result.tension_type or "",
                    conflict_values=resistance_result.conflict_values or None,
                    aligned_values=resistance_result.aligned_values or None,
                    pressure=self._p._conscience.get_pressure(),
                    alignment_score=self._p._alignment.get_score(),
                    safety_level=self.safety_level,
                    phi_smoothed=signals.phi_smoothed,
                    body_criticality=signals.body_criticality,
                    cascade_active=signals.cascade_active,
                    guard_allowed=signals.guard_allowed,
                    guard_risk_score=signals.guard_risk_score,
                )
            except Exception:
                logger.debug("emotion_spirit: surface log failed", exc_info=True)

        # MemoryPool decay tick (Phase D: 统一到 MemoryPool, 情境衰减)
        intimacy = self._p._intimacy.get_intimacy(session_id, self._p._current_persona) if session_id else 0.0
        self._p._pool.tick(
            personality=current_personality.get("deep", {}),
            partner_intimacy=intimacy,
        )

        # 记忆崩溃检测 (Phase D+ CollapseArchetype 集成)
        # v1.2.9 HP-3: 边沿检测 + L2 回写 (修 v1.2.8 bug: collapse 持续期间不重复 trigger_recovery)
        was_collapse = self._p._pool.check_collapse(personality=current_personality.get("deep", {}))
        archetype = self._p._pool.get_collapse_archetype()
        curr_collapse = was_collapse and bool(archetype)
        prev_collapse = getattr(self._p, "_prev_collapse_active", False)
        if curr_collapse and not prev_collapse:
            # 本 tick 刚触发崩溃 (False→True 边沿) → recovery + L2 回写各一次
            lsv2 = getattr(self._p, '_life_sim_v2', None)
            if lsv2 and hasattr(lsv2, 'trigger_recovery'):
                lsv2.trigger_recovery(archetype)
            dm = getattr(self._p, '_defense_modulator', None)
            if dm and hasattr(dm, 'apply_event'):
                dm.apply_event("collapse", intensity=1.0)
                logger.info("emotion_spirit: collapse L2 回写 (archetype=%s)", archetype)
        self._p._prev_collapse_active = curr_collapse

        self._p._save_if_dirty()
