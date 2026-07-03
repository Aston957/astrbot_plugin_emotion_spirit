"""SegmentedReplyOrchestrator — 分段回复编排器.

v1.2.7: 从 main.py._on_segmented_reply_v2 抽出. 负责分段发送计划 + 沉默判定 + 发送执行.

规约:
- §1.2 规则 3: 输出编排 → @register 组件, main.py 薄壳委托
- §1.2 规则 4: depends_on 5 组件 (defense_modulator / segmented_reply_coordinator /
  force_dynamics / body_state / intimacy)
- §4.D: event/response 副作用合法 (组件直接 send + 清 completion_text)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from emotion_spirit.core.registry import register

logger = logging.getLogger(__name__)


@register(
    name="segmented_reply_orchestrator",
    provides=["SegmentedReplyOrchestrator"],
    depends_on=[
        "defense_modulator",
        "segmented_reply_coordinator",
        "force_dynamics",
        "body_state",
        "intimacy",
    ],
)
class SegmentedReplyOrchestrator:
    """分段回复编排器.

    通过 depends_on 取 body_state 等有状态组件; 运行时上下文由 main.py 传入参数.
    """

    def __init__(
        self,
        defense_modulator: Any,
        segmented_reply_coordinator: Any,
        force_dynamics: Any,
        body_state: Any,
        intimacy: Any,
    ) -> None:
        self._defense_modulator = defense_modulator
        self._coordinator = segmented_reply_coordinator
        self._force_dynamics = force_dynamics
        self._body_state = body_state
        self._intimacy = intimacy

    async def handle(
        self,
        event: Any,
        response: Any,
        bot_text: str,
        user_id: str,
        seg_config: dict,
        signals: Any | None,
        context: dict,
        personality: dict[str, Any],
        current_persona: str,
        labels: dict[str, str] | None,
        force_state: Any | None,
        conscience_pressure: float = 0.0,
    ) -> None:
        """分段回复主体逻辑.

        Args:
            event: AstrBot AstrMessageEvent (用于 send).
            response: LLM 响应对象 (清 completion_text).
            bot_text: Bot 回复原文.
            user_id: 用户标识.
            seg_config: segmented_reply 配置 dict.
            signals: 运行时信号快照 (main.py 取 self._latest_signals).
            context: 上下文 dict (build_context 纯函数产出).
            personality: 当前人格参数 dict (main.py 取 self._get_current_personality_dict()).
            current_persona: 当前 persona ID (main.py self._current_persona).
            labels: 5 轴标签 dict (main.py self._labels).
            force_state: 三元力学 ForceState (main.py get_current_force_state).
            conscience_pressure: ConscienceTracker.get_pressure() as float (HP-2 已修).
        """
        try:
            # --- 1. 读 depends_on 组件的状态 (depends_on 必注入, 无需 hasattr 守卫) ---
            body_state = self._body_state.default()
            intimacy_level = self._intimacy.get_intimacy(user_id, current_persona)

            # --- 2. 沉默判定 (L1: 走 DefenseModulator 统一入口) ---
            from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency

            defense_states = self._defense_modulator.compute_defense_states(
                personality=personality,
                signals=signals,
                body_state=body_state,
                intimacy_level=intimacy_level,
                context=context,
                force_state=force_state,
                conscience_pressure=conscience_pressure,
            )
            silence_tendency_obj = SilenceTendency(
                score=defense_states.silence_tendency,
                reason=defense_states.silence_reason,
                components=defense_states.silence_components,
            )
            should_silent, reason, _ = self._coordinator.should_be_silent(
                user_id, silence_tendency_obj, seg_config
            )

            # --- 3. 沉默触发 (S1) ---
            if should_silent and seg_config.get("enable_deliberate_silence", False):
                self._coordinator.record_silence_event(
                    user_id, tendency=silence_tendency_obj,
                    full_text=bot_text, force_state=force_state,
                )
                # L2: 防御事件回写 force_state
                self._defense_modulator.apply_event(
                    "silence", intensity=silence_tendency_obj.score
                )
                response.completion_text = ""
                response.result_chain = None
                logger.debug(
                    "emotion_spirit: deliberate silence triggered reason=%s score=%.2f",
                    reason, silence_tendency_obj.score,
                )
                return

            # --- 4. 生成分段计划 ---
            plan = self._coordinator.plan(
                full_text=bot_text,
                session_key=user_id,
                expression_drive=(
                    getattr(signals, "affect_expression_drive", 0.5) if signals else 0.5
                ),
                rhythm_strain=(
                    getattr(signals, "rhythm_strain", 0.5) if signals else 0.5
                ),
                pad_valence=(
                    getattr(signals, "pad_valence", 0.5) if signals else 0.5
                ),
                hot_pool_pressure=(
                    getattr(signals, "hot_pool_pressure", 0.0) if signals else 0.0
                ),
                config=seg_config,
            )

            if not plan:
                return

            # --- 5. 逐段 send (F4: 先发首段无延迟) ---
            try:
                from astrbot.core.message.components import Plain
                from astrbot.core.message.message_event_result import MessageChain

                await event.send(MessageChain([Plain(plan[0]["text"])]))
                for part in plan[1:]:
                    delay = part.get("delay_before_seconds", 0.0)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    await event.send(MessageChain([Plain(part["text"])]))
            except Exception:
                logger.warning(
                    "emotion_spirit: segmented_reply send failed, "
                    "some segments may be missing",
                    exc_info=True,
                )

            # --- 6. 清空 llm_resp (Bug 12b 修复) ---
            response.completion_text = ""
            response.result_chain = None

            # --- 7. 推进冷却计数 ---
            self._coordinator.record_response_event(user_id)

            # --- 8. 记录分段历史 ---
            total_delay = sum(p.get("delay_before_seconds", 0.0) for p in plan)
            self._coordinator.record_segment_event(
                user_id, num_segments=len(plan), total_delay=total_delay,
            )

        except Exception:
            logger.warning(
                "emotion_spirit: segmented_reply failed, "
                "falling back to AstrBot default",
                exc_info=True,
            )