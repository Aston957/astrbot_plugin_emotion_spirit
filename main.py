"""emotion_spirit — Sylanne Engine 之上的长期记忆、人格演化与超我调控。

AstrBot 插件入口。
通过 SylannEngine 的 get_engine() 获取共享引擎，消费 Surface 输出。
使用 engine.on() 注册监听器，使用 engine.inject() 回写热池。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .emotion_spirit.store import SpiritStore
from .emotion_spirit.surface_consumer import SurfaceConsumer
from .emotion_spirit.emotion_classifier import render_description
from .emotion_spirit.memory_pool import MemoryPool
from .emotion_spirit.intimacy import IntimacyTracker
from .emotion_spirit.superego import ValueAlignment, ConscienceTracker, IdealSelf, ValueResistance
from .emotion_spirit.superego_guard import SuperegoGuard
from .emotion_spirit.meaning_reservoir import MeaningReservoir
from .emotion_spirit.pattern_extractor import PatternExtractor
from .emotion_spirit.shadow_detector import ShadowDetector
from .emotion_spirit.buffer_signals import BufferSignals
from .emotion_spirit.life_simulator import LifeSimulator
from .emotion_spirit.diary_writer import DiaryWriter
from .emotion_spirit.prompt_injector import PromptInjector
from .emotion_spirit.personality_drift import PersonalityDrift
from .emotion_spirit.predictive_sentinel import PredictiveSentinel
from .emotion_spirit.narrative_identity import NarrativeIdentity
from .emotion_spirit.counterfactual import Counterfactual
from .emotion_spirit.persona_report_parser import parse_persona_report
from .emotion_spirit.persona_analyzer import (
    PersonaAnalyzer,
    PersonaAnalysisResult,
    save_report,
    load_report,
)
from .emotion_spirit.label_mapper import labels_to_personality


class EmotionSpiritPlugin(Star):
    """emotion_spirit — 自我层 + 超我反思层。

    集成方式:
    - engine.on(listener): 注册 Surface 监听器，每次 process() 后自动回调
    - engine.inject(): 回写热池 (反事实、良心事件等)
    - @filter.on_llm_request(): 注入 prompt 上下文
    """

    def __init__(self, context: Context, config: dict[str, Any] | None = None) -> None:
        super().__init__(context)
        self._config = config or {}
        self._engine: Any = None  # SylannEngine 实例

        # 数据目录
        from pathlib import Path
        data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
        self._store = SpiritStore(data_dir)

        # ═══ 人格管理系统 ═══
        self._persona_mode = self._config.get("persona_mode", "disabled")
        self._current_persona = self._config.get("auto_source", "") or self._detect_default_persona()

        # 标签系统
        self._parsed_drives: dict[str, float] = {}
        self._labels: dict[str, str] = {}
        self._auto_report: PersonaAnalysisResult | None = None
        self._persona_initialized: bool = False  # /spirit_init 后才为 True
        self._relabel_pending: bool = False  # /spirit_relabel 阶段 1 标志

        if self._persona_mode == "auto":
            # auto 模式: 只检测 persona_id，不解析标签，等待 /spirit_init
            if not self._current_persona:
                self._current_persona = self._detect_default_persona()
            logger.info("emotion_spirit: auto 模式，人格 '%s' 待初始化（发送 /spirit_init）", self._current_persona)
        elif self._persona_mode == "disabled":
            self._labels = self._get_default_labels()
            logger.info("emotion_spirit: disabled 模式，使用 Sylanne 默认行为")
        else:
            # 未知模式，回退到 disabled
            self._persona_mode = "disabled"
            self._labels = self._get_default_labels()
            logger.info("emotion_spirit: 未知模式，回退到 disabled")

        self._update_baseline()

        # ═══ 功能开关 ═══
        toggles = self._config.get("feature_toggles", {})
        self._enable_shadow = toggles.get("enable_shadow_detector", True)
        self._enable_sentinel = toggles.get("enable_sentinel", True)
        self._enable_narrative = toggles.get("enable_narrative", True)
        self._enable_life = toggles.get("enable_life_simulator", True)
        self._life_mode = toggles.get("life_simulator_mode", "both")

        # Phase 1 组件
        self._consumer = SurfaceConsumer()
        self._pool = MemoryPool()
        self._intimacy = IntimacyTracker()
        self._conscience = ConscienceTracker()
        self._alignment = ValueAlignment(self._current_persona)
        self._value_resistance = ValueResistance(self._current_persona)
        self._ideal = IdealSelf(self._current_persona, self._labels)
        self._baseline_personality: dict[str, dict[str, float]] = {}
        self._interaction_count: int = 0

        # Phase 2 组件
        self._reservoir = MeaningReservoir()
        self._patterns = PatternExtractor(self._pool)
        self._buffer_signals = BufferSignals(self._pool)
        self._shadow = ShadowDetector(self._pool, self._buffer_signals, self._patterns) if self._enable_shadow else None
        self._life_sim = LifeSimulator(
            self._consumer, self._pool, self._intimacy,
            self._buffer_signals, self._reservoir,
        ) if self._enable_life else None
        self._diary = DiaryWriter(
            self._pool, self._patterns, self._buffer_signals,
            self._alignment, self._conscience,
        )
        self._injector = PromptInjector(
            self._pool, self._intimacy, self._alignment,
            self._conscience, self._ideal, self._shadow, self._diary,
        )
        self._drift = PersonalityDrift(self._consumer, self._reservoir)
        self._sentinel = PredictiveSentinel(
            self._consumer, self._buffer_signals, self._reservoir,
            self._conscience, self._alignment, self._ideal,
        ) if self._enable_sentinel else None
        self._superego_guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, self._current_persona,
        )
        self._narrative = NarrativeIdentity(
            self._pool, self._patterns, self._drift,
            self._buffer_signals, self._diary,
        ) if self._enable_narrative else None
        self._counterfactual = Counterfactual(self._pool)

        # 注入队列 (engine.inject 需要 async, listener 是 sync)
        self._inject_queue: list[tuple[str, str, float, str]] = []
        # session_id → 最近的用户消息文本
        self._last_texts: dict[str, str] = {}
        # 安全层状态 (由 _consume_surface 更新, on_llm_request 读取)
        self._safety_level: str = "normal"
        self._safety_note: str | None = None
        self._repair_advice: str | None = None

        # 多人格支持: 扫描并缓存所有人格参数
        self._personas_cache: dict[str, dict[str, Any]] = self._scan_all_personas()

        # v1.1.1: 最近一次 surface 的 SemanticSignals（公开 API 缓存层）
        self._latest_signals: dict[str, Any] = {}

    def _save_plugin_config(self) -> None:
        """将当前配置持久化到 AstrBot 配置文件。"""
        try:
            import json
            from pathlib import Path
            config_dir = Path(get_astrbot_data_path()) / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "astrbot_plugin_emotion_spirit_config.json"
            config_path.write_text(
                json.dumps(self._config, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("emotion_spirit: 配置已持久化到 %s", config_path)
        except Exception:
            logger.warning("emotion_spirit: 配置持久化失败", exc_info=True)

    def _init_auto_persona(self) -> None:
        """Auto 模式初始化: 尝试加载缓存报告，否则异步分析。"""
        # 1. 尝试加载已缓存的报告
        cached = load_report(self._store._dir)
        if cached and cached.persona_id == self._current_persona:
            self._auto_report = cached
            self._labels = cached.labels
            logger.info("emotion_spirit: 从缓存加载人格报告 — %s", cached.labels)
            return

        # 2. 同步回退解析（LLM 需要在 initialize 中异步调用）
        system_prompt = self._read_persona_prompt(self._current_persona)
        if system_prompt:
            parsed = parse_persona_report(system_prompt)
            if parsed.has_labels:
                self._labels = parsed.labels
                self._parsed_drives = parsed.drives
                logger.info("emotion_spirit: 同步回退解析成功 — %s", parsed.labels)
                return

        # 3. 使用默认值
        self._labels = self._get_default_labels()
        logger.info("emotion_spirit: 使用默认标签")

    async def _run_persona_analysis(self) -> None:
        """异步运行 LLM 人格分析（在 initialize 中调用）。"""
        if self._persona_mode != "auto":
            return

        system_prompt = self._read_persona_prompt(self._current_persona)
        if not system_prompt:
            return

        llm = self._get_llm_callable()
        if not llm:
            logger.info("emotion_spirit: LLM 不可用，跳过异步分析")
            return

        analyzer = PersonaAnalyzer(llm)
        result = await analyzer.analyze(self._current_persona, system_prompt)

        # 保存报告
        save_report(result, self._store._dir)

        # 更新当前状态
        self._auto_report = result
        self._labels = result.labels

        logger.info(
            "emotion_spirit: 异步分析完成 — persona=%s labels=%s source=%s confidence=%.2f",
            result.persona_id, result.labels, result.source, result.confidence,
        )

    def _get_llm_callable(self) -> Any:
        """获取 LLM 调用函数（桥接 AstrBot provider）。"""
        try:
            provider = self.context.get_using_provider()
            if provider and hasattr(provider, "text_chat"):
                async def _llm(system_prompt: str, user_prompt: str) -> str:
                    resp = await provider.text_chat(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                    )
                    return resp.completion_text
                return _llm
            else:
                logger.warning(
                    "emotion_spirit: LLM provider 不可用 (get_using_provider=%s, has_text_chat=%s)",
                    type(provider).__name__ if provider else "None",
                    hasattr(provider, "text_chat") if provider else False,
                )
        except Exception:
            logger.warning("emotion_spirit: 获取 LLM provider 失败", exc_info=True)
        return None

    async def _verify_llm_chain(self) -> None:
        """验证 LLM 调用链是否正常工作。"""
        llm = self._get_llm_callable()
        if not llm:
            logger.warning("emotion_spirit: [LLM验证] 无法获取 LLM callable，跳过验证")
            return

        try:
            result = await llm("回复 OK 即可。", "测试")
            logger.info(
                "emotion_spirit: [LLM验证] 调用成功 — 返回: %s (长度: %d)",
                result[:50] if result else "(空)", len(result) if result else 0,
            )
        except Exception as e:
            logger.warning(
                "emotion_spirit: [LLM验证] 调用失败 — %s: %s",
                type(e).__name__, e,
            )

    def _update_baseline(self) -> None:
        """从当前标签推导基线人格参数并保存。"""
        from .emotion_spirit.persona_profiles import get_personality_params
        self._baseline_personality = get_personality_params(self._labels)
        self._interaction_count = 0
        logger.info("emotion_spirit: baseline personality updated from labels")

    @staticmethod
    def _validate_labels(labels: tuple[str, ...]) -> dict[str, str] | None:
        """验证 5 轴标签的合法性。

        Args:
            labels: 5 个标签值的元组 (mbti, attachment, emotion_style, conflict_style, time_focus)

        Returns:
            合法的 labels 字典；非法时返回 None。
        """
        if len(labels) != 5:
            return None

        mbti, attachment, emotion_style, conflict_style, time_focus = labels

        # 验证每个字段
        from .emotion_spirit.label_mapper import LABEL_OPTIONS
        if mbti not in LABEL_OPTIONS["mbti"]:
            return None
        if attachment not in LABEL_OPTIONS["attachment"]:
            return None
        if emotion_style not in LABEL_OPTIONS["emotion_style"]:
            return None
        if conflict_style not in LABEL_OPTIONS["conflict_style"]:
            return None
        if time_focus not in LABEL_OPTIONS["time_focus"]:
            return None

        return {
            "mbti": mbti,
            "attachment": attachment,
            "emotion_style": emotion_style,
            "conflict_style": conflict_style,
            "time_focus": time_focus,
        }

    @staticmethod
    def _is_persona_initialized(persona_data: dict) -> bool:
        """判定 persona 是否已初始化。

        判定规则（全部满足才算已初始化）：
        1. persona 键存在（非空 dict）
        2. persona.initialized == True
        3. persona.labels 非空
        """
        return (
            bool(persona_data) and
            persona_data.get("initialized", False) and
            bool(persona_data.get("labels"))
        )

    def _load_persona_state(self) -> None:
        """从 SpiritStore 加载 persona 状态。

        触发时机：initialize() 中。
        副作用：填充 self._persona_initialized, self._labels, self._current_persona。
        """
        persona_data = self._store.get("persona", {})

        if self._is_persona_initialized(persona_data):
            self._persona_initialized = True
            self._labels = dict(persona_data.get("labels", {}))
            saved_persona_id = persona_data.get("persona_id")
            if saved_persona_id:
                self._current_persona = saved_persona_id
            logger.info(
                "emotion_spirit: persona 已恢复 — id=%s labels=%s",
                self._current_persona, list(self._labels.keys()),
            )
        else:
            self._persona_initialized = False
            self._labels = {}
            # 检测到老数据无 persona 键 → 触发迁移
            self._migrate_old_spirit_data()

    def _reset_superego_modules(self) -> None:
        """重置超我层模块到初始状态（保留 11 维 baseline 推算的模块实例，但清空运行时状态）。

        清除：
        - ConscienceTracker 压力历史
        - ValueAlignment 对齐历史
        - IdealSelf 强化数据
        - ValueResistance 互动计数和强化
        - SuperegoGuard 干预历史
        - SpiritStore 中 6 个超我层键
        - persona_report.json

        保留：
        - 11 维 current_personality 漂移值（Kagan 行为策略）
        - MemoryPool, IntimacyTracker, MeaningReservoir, DiaryWriter, PersonalityDrift
        """
        from .emotion_spirit.superego import ValueAlignment, IdealSelf, ValueResistance
        from .emotion_spirit.superego_guard import SuperegoGuard
        from .emotion_spirit.persona_analyzer import save_report

        # 重建超我模块实例（用当前 labels 和 persona_id）
        self._conscience = ConscienceTracker()
        self._alignment = ValueAlignment(self._current_persona)
        self._value_resistance = ValueResistance(self._current_persona)
        self._ideal = IdealSelf(self._current_persona, self._labels)
        self._superego_guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, self._current_persona,
        )

        # 清除 SpiritStore 中 6 个超我层键
        for key in ("conscience", "alignment", "ideal_self", "value_resistance", "superego_guard", "persona_report"):
            self._store.set(key, None)

        # 删除 persona_report.json
        report_path = self._store._dir / "persona_report.json"
        if report_path.exists():
            report_path.unlink()

        # 立即写盘
        self._store.save()
        logger.info("emotion_spirit: 超我层已重置（11 维 baseline 已用新 labels 重推）")

    def _migrate_old_spirit_data(self) -> None:
        """从老 spirit_data.json 推导 persona 状态。

        触发条件：spirit_data.json 存在但无 persona 键。
        策略（方案 B）：
        1. 尝试从 config.manual_personas 读取（schema 过渡期兼容）
        2. 兜底：使用默认 labels (ISTJ-安全型)
        3. 写入新 persona namespace
        """
        # 1. 尝试从 config 读 manual_personas
        labels: dict[str, str] | None = None
        manual_list = self._config.get("manual_personas", [])
        if isinstance(manual_list, list) and manual_list:
            first = manual_list[0]
            if isinstance(first, dict):
                raw_labels = first.get("labels", {})
                if isinstance(raw_labels, dict) and any(raw_labels.values()):
                    labels = {
                        "mbti": raw_labels.get("mbti", "ISTJ"),
                        "attachment": raw_labels.get("attachment", "安全型"),
                        "emotion_style": raw_labels.get("emotion_style", "混合型"),
                        "conflict_style": raw_labels.get("conflict_style", "合作型"),
                        "time_focus": raw_labels.get("time_focus", "活在当下"),
                    }

        # 2. 兜底：使用默认值
        if not labels:
            labels = self._get_default_labels()
            logger.warning(
                "emotion_spirit: 检测到老数据但无 persona 配置，使用默认 labels (ISTJ-安全型)。"
                "请用 /spirit_relabel 调整为正确 persona。"
            )

        # 3. 写入新 schema
        self._store.set("persona", {
            "initialized": True,
            "persona_id": self._current_persona or "unknown",
            "labels": labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._store.save()
        # 同步到内存
        self._persona_initialized = True
        self._labels = labels
        logger.info("emotion_spirit: 老数据迁移完成，persona = %s", labels)

    def _get_default_labels(self) -> dict[str, str]:
        """获取默认标签 (ISTJ 安全型)。"""
        return {
            "mbti": "ISTJ",
            "attachment": "安全型",
            "emotion_style": "混合型",
            "conflict_style": "合作型",
            "time_focus": "活在当下",
        }

    def _read_persona_prompt(self, persona_id: str) -> str | None:
        """从 AstrBot 数据库读取 persona 的 system_prompt。"""
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path(get_astrbot_data_path()) / "data_v4.db"
            if not db_path.exists():
                return None

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT system_prompt FROM personas WHERE persona_id = ?",
                (persona_id,),
            )
            row = cursor.fetchone()
            conn.close()

            return row[0] if row else None

        except Exception:
            logger.debug("persona_report_parser: 读取数据库失败", exc_info=True)
            return None

    def _detect_default_persona(self) -> str:
        """从 AstrBot 配置自动检测默认人格 ID。"""
        try:
            import json
            from pathlib import Path

            config_path = Path(get_astrbot_data_path()) / "cmd_config.json"
            if not config_path.exists():
                return "xiaofu"

            # 读取配置 (处理 BOM)
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)

            # 从 provider_settings.default_personality 读取
            default_persona = config.get("provider_settings", {}).get("default_personality", "")
            if default_persona:
                logger.info("emotion_spirit: 从 AstrBot 配置检测到默认人格: %s", default_persona)
                return default_persona

            # 如果没有配置，尝试从数据库读取第一个人格
            import sqlite3
            db_path = Path(get_astrbot_data_path()) / "data_v4.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT persona_id FROM personas LIMIT 1")
                row = cursor.fetchone()
                conn.close()
                if row:
                    logger.info("emotion_spirit: 从数据库检测到人格: %s", row[0])
                    return row[0]

            # 最终回退
            logger.info("emotion_spirit: 未检测到默认人格，使用 xiaofu")
            return "xiaofu"

        except Exception:
            logger.debug("emotion_spirit: 检测默认人格失败", exc_info=True)
            return "xiaofu"

    def _scan_all_personas(self) -> dict[str, dict[str, Any]]:
        """扫描数据库中所有人格，解析报告并缓存参数。"""
        personas_cache: dict[str, dict[str, Any]] = {}
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path(get_astrbot_data_path()) / "data_v4.db"
            if not db_path.exists():
                return personas_cache

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT persona_id, system_prompt FROM personas")
            rows = cursor.fetchall()
            conn.close()

            for persona_id, system_prompt in rows:
                if not system_prompt:
                    continue

                # 解析人格报告
                parsed = parse_persona_report(system_prompt)

                personas_cache[persona_id] = {
                    "labels": parsed.labels,
                    "drives": parsed.drives,
                    "traits": parsed.traits,
                    "has_report": bool(parsed.has_labels),
                }

                logger.info(
                    "emotion_spirit: 扫描人格 %s — labels=%s has_report=%s",
                    persona_id, parsed.labels, parsed.has_labels,
                )

        except Exception:
            logger.debug("emotion_spirit: 扫描人格失败", exc_info=True)

        return personas_cache


    def _get_persona_params(self, persona_id: str) -> dict[str, dict[str, float]]:
        """获取指定人格的 11 维参数。"""
        from .emotion_spirit.label_mapper import labels_to_personality, _BASELINE

        # 1. 检查 auto_report 缓存
        if self._auto_report and self._auto_report.persona_id == persona_id:
            return self._auto_report.personality

        # 2. 检查 personas_cache
        if persona_id in self._personas_cache:
            cached = self._personas_cache[persona_id]
            if cached.get("labels"):
                return labels_to_personality(cached["labels"])

        # 3. 从数据库解析
        system_prompt = self._read_persona_prompt(persona_id)
        if system_prompt:
            parsed = parse_persona_report(system_prompt)
            if parsed.has_labels:
                self._personas_cache[persona_id] = {
                    "labels": parsed.labels,
                    "drives": parsed.drives,
                    "traits": parsed.traits,
                    "has_report": True,
                }
                return labels_to_personality(parsed.labels)

        # 4. 回退到基线
        return dict(_BASELINE)

    async def initialize(self) -> None:
        """加载持久化数据并注册 SylannEngine 监听器。"""
        self._store.load()
        self._load_persistent_data()

        # 加载 persona 状态（重启后恢复）
        self._load_persona_state()
        if self._persona_initialized:
            # 用恢复的 labels 重建超我模块
            self._update_baseline()
            from .emotion_spirit.superego import ValueAlignment, IdealSelf, ValueResistance
            from .emotion_spirit.superego_guard import SuperegoGuard
            self._alignment = ValueAlignment(self._current_persona)
            self._value_resistance = ValueResistance(self._current_persona)
            self._ideal = IdealSelf(self._current_persona, self._labels)
            self._superego_guard = SuperegoGuard(
                self._conscience, self._alignment, self._ideal, self._current_persona,
            )

        # 延迟连接 SylannEngine (因为字母序加载, SylannEngine 可能还没初始化)
        asyncio.get_event_loop().call_later(2.0, self._connect_engine_sync)

        # auto 模式不再自动运行 LLM 分析，等待用户 /spirit_init
        # LLM 调用链验证 (所有模式都执行，用于调试)
        asyncio.get_event_loop().call_later(3.0, lambda: asyncio.ensure_future(self._verify_llm_chain()))

        logger.info(
            "emotion_spirit initialized: mode=%s persona=%s buffer=%d warm=%d cold=%d ghosts=%d",
            self._persona_mode, self._current_persona,
            len(self._pool.buffer), len(self._pool.warm),
            len(self._pool.cold), len(self._pool.ghosts),
        )
        logger.info(
            "emotion_spirit features: shadow=%s sentinel=%s narrative=%s life=%s(%s)",
            self._enable_shadow, self._enable_sentinel,
            self._enable_narrative, self._enable_life, self._life_mode,
        )

    def _connect_engine_sync(self) -> None:
        """延迟连接 SylannEngine (在事件循环中调用)。"""
        try:
            from sylanne_core import get_engine
            self._engine = get_engine()
            self._engine.on(self._on_surface)
            logger.info("emotion_spirit: SylannEngine 连接成功，监听器已注册")
        except (ImportError, RuntimeError) as e:
            # 再试一次 (5 秒后)
            if not hasattr(self, '_retry_count'):
                self._retry_count = 0
            self._retry_count += 1
            if self._retry_count < 3:
                logger.info("emotion_spirit: SylannEngine 尚未就绪，%d 秒后重试...", 5 * self._retry_count)
                asyncio.get_event_loop().call_later(5.0 * self._retry_count, self._connect_engine_sync)
            else:
                logger.warning("emotion_spirit: SylannEngine 不可用 (%s)，将通过 on_llm_request 获取 Surface", e)
                self._engine = None

    async def terminate(self) -> None:
        """注销监听器并持久化数据。"""
        if self._engine is not None:
            try:
                self._engine.off(self._on_surface)
            except Exception:
                pass
        self._save_all()
        logger.info("emotion_spirit terminated: data saved")

    # ═══ SylannEngine Surface 监听器 (sync callback) ═══

    def _on_surface(self, session_id: str, surface: dict[str, Any]) -> None:
        """SylannEngine 回调 — 每次 process() 后自动调用。

        这是 sync 函数 (engine.on 不 await 回调)。
        需要 inject 时，将请求排入队列，由 on_llm_request 异步处理。
        """
        try:
            self._consume_surface(session_id, surface)
        except Exception:
            logger.warning("emotion_spirit: _on_surface 异常", exc_info=True)

    def _consume_surface(self, session_id: str, surface: dict[str, Any]) -> None:
        """消费 Surface，更新所有状态。"""
        signals = self._consumer.consume(surface)

        # v1.1.1: 缓存最近一次 signals 供公开 API 读取
        self._latest_signals[session_id] = signals

        # 获取最近的用户消息文本
        text = self._last_texts.get(session_id, "")

        # Phase 1: 基础更新
        self._pool.update_phi(signals.phi_smoothed)
        raw_weight = signals.damage_open + signals.valence_volatility + signals.cascade_intensity
        self._pool.add(
            text=text,
            raw_weight=raw_weight,
            phi=signals.phi_smoothed,
            tags=[signals.pad_label, signals.decision_action],
            source_user=session_id,
        )
        confirmed = self._pool.confirm_check()

        # 日志: Surface 消费
        logger.debug(
            "emotion_spirit surface: user=%s action=%s phi=%.3f weight=%.3f "
            "buffer=%d warm=%d confirmed=%d",
            session_id[:8], signals.decision_action, signals.phi_smoothed,
            raw_weight, len(self._pool.buffer), len(self._pool.warm), len(confirmed),
        )
        self._intimacy.update(
            session_id,
            temporal_hours=signals.relational_duration / 3600,
            interval_seconds=signals.relational_interval,
        )
        self._alignment.record(signals.decision_action)

        # ═══ 价值抵抗计算 (替代简单的 guard 拦截) ═══
        context = {
            "body_criticality": signals.body_criticality,
            "cascade_active": signals.cascade_active,
            "boundary_paused": signals.boundary_paused,
            "guard_risk_score": signals.guard_risk_score,
            "intimacy": self._intimacy.get_intimacy(
                session_id, self._current_persona,
            ) if session_id else 0.5,
        }
        current_personality = {
            "deep": signals.personality_deep or {},
            "surface": signals.personality_surface or {},
        }
        self._interaction_count += 1
        self._value_resistance._baseline_personality = self._baseline_personality
        self._value_resistance._interaction_count = self._interaction_count
        stress_level = min(1.0, signals.body_criticality + (0.5 if signals.cascade_active else 0.0))
        resistance_result = self._value_resistance.compute(
            action=signals.decision_action,
            context=context,
            current_personality=current_personality,
            stress_level=stress_level,
        )

        # ═══ 良心事件记录 ═══
        if resistance_result.conflict_values:
            self._conscience.record_value_conflict(
                resistance=resistance_result.resistance,
                conflict_values=resistance_result.conflict_values,
                tension_type=resistance_result.tension_type or "guilt",
                behavioral_shift=resistance_result.behavioral_shift,
                conscience_impact=resistance_result.conscience_impact,
            )
        elif resistance_result.aligned_values:
            for value_name in resistance_result.aligned_values:
                self._conscience.record_alignment(value_name, signals.decision_action)

        # guard 反射仍记录，但降权
        if not signals.guard_allowed:
            self._conscience.record_guard_reflex(
                signals.guard_risk_score, signals.decision_reason,
            )

        # 级联仍记录，但降权
        if signals.cascade_active:
            self._conscience.record_cascade(signals.cascade_intensity)

        # 坍缩仍记录
        self._conscience.record_collapse(signals.collapse_count)

        # Phase 2: 演化层更新
        self._reservoir.accumulate(signals.phi_smoothed, raw_weight)
        self._drift.update(signals)
        if self._sentinel:
            self._sentinel.update(signals)
        if self._life_sim:
            self._life_sim.on_user_message()

        # ═══ PersonalityDrift ↔ IdealSelf 联动 ═══
        # 当漂移检测到持续变化时，微调理想自我目标
        drifts = self._drift.check_drift()
        if drifts:
            for drift_info in drifts:
                dimension = drift_info["dimension"]
                direction = drift_info["direction"]
                slope = drift_info["slope"]

                # 计算强化值：正向漂移增加理想值，负向漂移降低理想值
                # 使用 slope 的符号和幅度，限制在 [-0.05, 0.05] 范围内
                delta = max(-0.05, min(0.05, slope * 10))
                if direction == "increasing":
                    delta = abs(delta)
                else:
                    delta = -abs(delta)

                # 更新理想自我
                self._ideal.update_reinforcement(dimension, delta)

        # ═══ 超我安全层: sentinel → superego_guard 链 ═══
        sentinel_result = self._sentinel.check() if self._sentinel else None
        current_personality = {
            "deep": signals.personality_deep or {},
            "surface": signals.personality_surface or {},
        }
        intervention = self._superego_guard.assess(sentinel_result, current_personality)
        self._safety_level = intervention.level
        self._safety_note = intervention.safety_note
        self._repair_advice = intervention.repair_advice

        if intervention.level == "critical":
            logger.warning(
                "emotion_spirit safety: user=%s level=%s reason=%s",
                session_id[:8], intervention.level, intervention.log_reason,
            )

            # ═══ 超我反思日记联动 ═══
            breakdown = self._conscience.get_pressure_breakdown()
            dominant_tension = breakdown.get("dominant_tension")
            if dominant_tension in ["guilt", "shame"]:
                # 提取冲突价值观
                recent_events = self._conscience.get_recent(hours=24)
                conflict_values: list[str] = []
                for event in recent_events:
                    if hasattr(event, "conflict_values") and event.conflict_values:
                        conflict_values.extend(event.conflict_values)
                conflict_values = list(set(conflict_values))[:5]

                # 生成反思日记
                from .emotion_spirit.diary_writer import DiaryWriter
                if self._diary:
                    reflection_prompt = self._diary.build_superego_reflection_prompt(
                        dominant_tension, conflict_values,
                    )
                    self._diary.record_diary(reflection_prompt, "superego_reflection")
                    logger.info(
                        "emotion_spirit: superego reflection diary recorded for user=%s",
                        session_id[:8],
                    )

        # 模式提取 (每 100 条)
        if len(self._pool.warm) % 100 == 0 and len(self._pool.warm) > 0:
            self._patterns.extract()

        # 幽灵共振
        if self._pool.warm:
            boost = self._counterfactual.ghost_resonance(self._pool.warm[-1])
            if boost > 0:
                self._pool.warm[-1].emotional_weight = min(
                    1.0, self._pool.warm[-1].emotional_weight + boost,
                )

        # 良心事件 → inject 队列
        if not signals.guard_allowed and self._engine:
            self._inject_queue.append((
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

        self._save_if_dirty()

    # ═══ LLM 请求注入 ═══

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: Any) -> None:
        """LLM 请求前:
        1. 如果 SylannEngine 不可用，主动调用 engine.process() 获取 Surface
        2. 注入 emotion_spirit 上下文到 system_prompt
        3. 处理 inject 队列
        """
        user_id = event.get_sender_id()
        text = event.message_str

        # 保存最近的用户消息 (供 _on_surface 回调使用)
        self._last_texts[user_id] = text
        if len(self._last_texts) > 100:
            # 只保留最近 100 个 session
            oldest = list(self._last_texts.keys())[:50]
            for k in oldest:
                del self._last_texts[k]

        # 如果 engine 可用但还没收到回调 (可能是因为其他插件还没调用 process)
        # 主动调用一次确保数据更新
        if self._engine is not None:
            try:
                session_key = event.unified_msg_origin
                surface = await self._engine.process(session_key, text)
                # _on_surface 会被 engine 自动回调，但为了确保数据即时可用
                # 这里也直接消费一次 (idempotent — EMA 平滑器会正确处理重复)
                self._consume_surface(user_id, surface)
            except Exception:
                logger.warning("emotion_spirit: engine.process 失败", exc_info=True)

        # 处理 inject 队列
        await self._flush_inject_queue()

        # 未初始化时跳过 superego 注入 (disabled 模式或 auto 模式未 /spirit_init)
        if self._persona_mode == "disabled":
            return
        if self._persona_mode == "auto" and not self._persona_initialized:
            return

        # 构建注入上下文
        current_personality = {
            "deep": self._consumer.consume({}).personality_deep or {},
            "surface": self._consumer.consume({}).personality_surface or {},
        }
        context = self._injector.build_context(
            user_id=user_id,
            persona=self._current_persona,
            current_personality=current_personality,
            safety_level=self._safety_level,
            safety_note=self._safety_note,
            repair_advice=self._repair_advice,
        )
        if context:
            logger.debug(
                "emotion_spirit inject: user=%s context_len=%d", user_id[:8], len(context),
            )
            if req.system_prompt:
                req.system_prompt = f"{context}\n\n{req.system_prompt}"
            else:
                req.system_prompt = context

    async def _flush_inject_queue(self) -> None:
        """处理排队的 inject 请求。"""
        if not self._engine or not self._inject_queue:
            return
        while self._inject_queue:
            session_id, influence_type, intensity, target = self._inject_queue.pop(0)
            try:
                await self._engine.inject(
                    session_id=session_id,
                    source="emotion_spirit",
                    influence_type=influence_type,
                    intensity=intensity,
                    target_dimension=target,
                )
            except Exception:
                logger.warning("emotion_spirit: engine.inject 失败", exc_info=True)

    # ═══ 指令 ═══

    @filter.command("spirit_relabel")
    async def spirit_relabel(self, event: AstrMessageEvent, confirm: str = "", *labels: str) -> None:
        """两阶段调整人格标签。
        阶段 1: /spirit_relabel → 显示警告
        阶段 2: /spirit_relabel confirm <5个标签> → 执行重置
        """
        # 模式检查
        if self._persona_mode == "disabled":
            yield event.plain_result("⚠️ disabled 模式不支持 relabel。请在配置中切换到 auto 模式。")
            return
        if not self._persona_initialized:
            yield event.plain_result("⚠️ 未初始化，无法调整标签。请先 /spirit_init")
            return

        # 阶段 1: 警告
        if not confirm:
            self._relabel_pending = True
            warn_msg = (
                "⚠️ 即将调整人格标签\n\n"
                "将清除超我层数据:\n"
                "  ❌ ConscienceTracker (压力历史)\n"
                "  ❌ ValueAlignment (对齐历史)\n"
                "  ❌ IdealSelf (理想自我基线)\n"
                "  ❌ ValueResistance (互动计数/强化)\n"
                "  ❌ SuperegoGuard (干预历史)\n"
                "  ❌ persona_report.json\n\n"
                "将保留:\n"
                "  ✅ MemoryPool (对话记忆)\n"
                "  ✅ IntimacyTracker (亲密度)\n"
                "  ✅ MeaningReservoir (意义蓄水)\n"
                "  ✅ DiaryWriter (日记)\n"
                "  ✅ PersonalityDrift (人格漂移)\n\n"
                "⚠️ 后果: 之前的\"灵魂痕迹\"会被清空。bot 不会忘记你们聊过什么,\n"
                "但会失去对那些对话的\"内心评判\"和\"理想自省\"。\n\n"
                "发送新标签以执行:\n"
                "  /spirit_relabel confirm <mbti> <attachment> <emotion_style> <conflict_style> <time_focus>\n\n"
                "示例: /spirit_relabel confirm INFP 焦虑型 表达型 顺应型 活在当下"
            )
            yield event.plain_result(warn_msg)
            return

        # 阶段 2: 执行
        if confirm != "confirm":
            yield event.plain_result("❌ 第二个参数必须为 'confirm'")
            return

        if not getattr(self, '_relabel_pending', False):
            yield event.plain_result("❌ 请先调用 /spirit_relabel 查看警告")
            return

        if len(labels) != 5:
            yield event.plain_result(f"❌ 需要 5 个标签参数，得到 {len(labels)} 个")
            return

        new_labels = self._validate_labels(labels)
        if not new_labels:
            yield event.plain_result(
                "❌ 标签值不合法。合法值:\n"
                "  mbti: INFP/ENFP/ISTJ/...\n"
                "  attachment: 安全型/焦虑型/回避型/混乱型\n"
                "  emotion_style: 表达型/压抑型/混合型\n"
                "  conflict_style: 攻击型/回避型/顺应型/合作型\n"
                "  time_focus: 活在过去/活在当下/活在未来"
            )
            return

        # 执行重置
        self._labels = new_labels
        self._update_baseline()  # 重新推 11 维 baseline
        self._reset_superego_modules()

        # 写 persona_report.json（如果有 LLM 分析结果）
        if self._auto_report:
            from .emotion_spirit.persona_analyzer import save_report
            save_report(self._auto_report, self._store._dir)

        # 持久化 persona namespace
        self._store.set("persona", {
            "initialized": True,
            "persona_id": self._current_persona,
            "labels": self._labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._store.save()

        # 清空 pending
        self._relabel_pending = False

        # 日志：记录破坏性操作
        logger.warning(
            "emotion_spirit: /spirit_relabel 执行 — persona=%s new_labels=%s",
            self._current_persona, new_labels,
        )

        # 返回结果
        from .emotion_spirit.label_mapper import labels_to_personality
        personality = labels_to_personality(new_labels)
        deep = personality.get("deep", {})
        sorted_dims = sorted(deep.items(), key=lambda x: x[1], reverse=True)
        core = [d for d, v in sorted_dims[:5]]
        peripheral = [d for d, v in sorted_dims[5:]]

        result = (
            f"✅ 人格标签已更新\n"
            f"新标签: {new_labels}\n"
            f"核心维度: {core}\n"
            f"边缘维度: {peripheral}\n\n"
            f"💡 使用 /spirit_detail 查看完整 11 维参数"
        )
        yield event.plain_result(result)

    @filter.command("spirit_status")
    async def spirit_status(self, event: AstrMessageEvent) -> None:
        """查看 emotion_spirit 状态。"""
        pool = self._pool
        user_id = event.get_sender_id()
        lifecycle = self._intimacy.get_lifecycle(user_id)
        intimacy = self._intimacy.get_intimacy(user_id, self._current_persona)
        alignment = self._alignment.get_score()
        trend = self._alignment.get_trend()
        pressure = self._conscience.get_pressure()
        breakdown = self._conscience.get_pressure_breakdown()
        reservoir = self._reservoir.level
        engine_status = "已连接" if self._engine else "未连接"

        mode_names = {"auto": "自动读取", "disabled": "已禁用"}
        mode_display = mode_names.get(self._persona_mode, self._persona_mode)

        # 压力分解
        pressure_breakdown = ""
        if breakdown.get("by_type"):
            items = sorted(breakdown["by_type"].items(), key=lambda x: x[1], reverse=True)
            pressure_breakdown = ", ".join(f"{t}: {s:.2f}" for t, s in items[:3])

        # 安全级别
        safety_info = f"安全级别: {self._safety_level}"
        if self._safety_note:
            safety_info += f" | {self._safety_note}"

        # 功能开关状态
        features = []
        features.append("阴影:ON" if self._enable_shadow else "阴影:OFF")
        features.append("预警:ON" if self._enable_sentinel else "预警:OFF")
        features.append("叙事:ON" if self._enable_narrative else "叙事:OFF")
        if self._enable_life:
            features.append(f"生活:{self._life_mode}")
        else:
            features.append("生活:OFF")

        init_status = ""
        if self._persona_mode == "auto":
            init_status = " (已初始化)" if self._persona_initialized else " (未初始化，发送 /spirit_init)"

        status = (
            f"📊 emotion_spirit 状态\n"
            f"人格模式: {mode_display}\n"
            f"当前人格: {self._current_persona}{init_status}\n"
            f"SylannEngine: {engine_status}\n"
            f"缓冲池: {len(pool.buffer)} 条\n"
            f"温池: {len(pool.warm)} 条\n"
            f"冷池: {len(pool.cold)} 条\n"
            f"幽灵: {len(pool.ghosts)} 条\n"
            f"关系: {lifecycle} (亲密度: {intimacy:.2f})\n"
            f"价值对齐: {alignment:.2f} 对齐趋势: {trend:+.2f}\n"
            f"良心压力: {pressure:.2f} ({pressure_breakdown})\n"
            f"意义蓄水: {reservoir:.2f}\n"
            f"{safety_info}\n"
            f"功能: {' / '.join(features)}"
        )
        yield event.plain_result(status)

    @filter.command("spirit_drift")
    async def spirit_drift(self, event: AstrMessageEvent) -> None:
        """查看人格漂移状态。"""
        status = self._drift.get_drift_status()
        drifts = self._drift.check_drift()

        lines = ["📈 人格漂移状态"]
        lines.append(f"整合度斜率: {status['integration_slope']:.4f}")
        lines.append(f"意义蓄水: {status['reservoir_level']:.2f}")
        lines.append(f"漂移次数: {status['drift_count']}")

        if drifts:
            lines.append("\n检测到的漂移:")
            for d in drifts[:5]:
                lines.append(f"  {d['dimension']}: {d['direction']} (slope={d['slope']:.4f})")
        else:
            lines.append("\n未检测到漂移")

        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_sentinel")
    async def spirit_sentinel(self, event: AstrMessageEvent) -> None:
        """查看预警状态。"""
        if not self._sentinel:
            yield event.plain_result("⚠️ 预警系统已关闭，请在配置中启用 enable_sentinel")
            return
        result = self._sentinel.check()

        lines = [f"🚨 预警状态: {result['level']}"]
        lines.append(f"触发信号: {result['triggered_count']}")

        if result["triggered_signals"]:
            for sig in result["triggered_signals"]:
                lines.append(f"  ⚠️ {sig}")
        else:
            lines.append("  ✅ 所有信号正常")

        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_shadows")
    async def spirit_shadows(self, event: AstrMessageEvent) -> None:
        """查看阴影检测。"""
        if not self._shadow:
            yield event.plain_result("⚠️ 阴影检测已关闭，请在配置中启用 enable_shadow_detector")
            return
        shadows = self._shadow.detect()

        if not shadows:
            yield event.plain_result("🌑 未检测到阴影")
            return

        lines = [f"🌑 检测到 {len(shadows)} 个阴影:"]
        for s in shadows[:5]:
            lines.append(f"  [{s['evidence']}] {s['tag']} (置信度: {s['confidence']:.2f})")
            lines.append(f"    {s['suggestion']}")

        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_diary")
    async def spirit_diary(self, event: AstrMessageEvent) -> None:
        """手动生成日记。"""
        diary_type = self._diary.determine_diary_type()
        prompt = self._diary.build_diary_prompt(diary_type)
        yield event.plain_result(f"📝 日记类型: {diary_type}\n\n{prompt}")

    @filter.command("spirit_patterns")
    async def spirit_patterns(self, event: AstrMessageEvent) -> None:
        """查看行为模式。"""
        self._patterns.extract()
        patterns = self._patterns.get_patterns()

        if not patterns:
            yield event.plain_result("📋 未检测到模式")
            return

        lines = [f"📋 检测到 {len(patterns)} 个模式:"]
        for p in patterns[:5]:
            lines.append(f"  [{p.pattern_type}] {', '.join(p.tags)} (次数: {p.count})")

        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_persona")
    async def spirit_persona(self, event: AstrMessageEvent) -> None:
        """查看当前人格标签（5 轴标签概览）。"""
        mode_names = {"auto": "自动读取", "disabled": "已禁用"}
        mode_display = mode_names.get(self._persona_mode, self._persona_mode)

        lines = [f"🎭 人格状态 — 模式: {mode_display}"]
        lines.append(f"   当前人格: {self._current_persona}")
        lines.append("")

        if not self._labels or not any(self._labels.values()):
            lines.append("⚠️ 未加载任何标签")
        else:
            lines.append("5 轴标签:")
            label_names = {
                "mbti": "MBTI", "attachment": "依恋风格",
                "emotion_style": "情绪策略", "conflict_style": "冲突风格",
                "time_focus": "时间取向",
            }
            for key, value in self._labels.items():
                lines.append(f"  {label_names.get(key, key)}: {value}")

            # 显示来源
            if self._auto_report:
                src = "LLM 分析" if self._auto_report.source == "llm" else "规则推断"
                lines.append(f"\n  📊 来源: {src} (置信度: {self._auto_report.confidence:.0%})")

        lines.append("\n💡 使用 /spirit_detail 查看完整 11 维参数")
        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_detail")
    async def spirit_detail(self, event: AstrMessageEvent, persona_name: str = "") -> None:
        """查看人格的完整 11 维参数。用法: /spirit_detail [人格名]"""
        from .emotion_spirit.label_mapper import labels_to_personality

        # 确定要查看的人格
        if persona_name:
            # 查看指定人格
            labels = None
            if self._auto_report and self._auto_report.persona_id == persona_name:
                labels = self._auto_report.labels
            elif persona_name in self._personas_cache:
                labels = self._personas_cache[persona_name].get("labels", {})

            if not labels:
                yield event.plain_result(f"❌ 未找到人格 '{persona_name}' 或其标签数据")
                return
        else:
            # 查看当前人格
            labels = self._labels
            persona_name = self._current_persona

        if not labels or not any(labels.values()):
            yield event.plain_result("⚠️ 无标签数据，无法生成参数")
            return

        personality = labels_to_personality(labels)

        lines = [f"🔬 人格详情: {persona_name}"]
        lines.append("")
        lines.append("标签:")
        label_names = {
            "mbti": "MBTI", "attachment": "依恋风格",
            "emotion_style": "情绪策略", "conflict_style": "冲突风格",
            "time_focus": "时间取向",
        }
        for key, value in labels.items():
            lines.append(f"  {label_names.get(key, key)}: {value}")

        lines.append("")
        lines.append("深层参数 (deep):")
        for dim, val in personality["deep"].items():
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            lines.append(f"  {dim}: {bar} {val:.2f}")

        lines.append("")
        lines.append("表层参数 (surface):")
        for dim, val in personality["surface"].items():
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            lines.append(f"  {dim}: {bar} {val:.2f}")

        # 显示驱动力 (如果有)
        if self._parsed_drives:
            lines.append("")
            lines.append("驱动力 (从报告解析):")
            for drive, val in self._parsed_drives.items():
                bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                lines.append(f"  {drive}: {bar} {val:.2f}")

        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_personas")
    async def spirit_personas(self, event: AstrMessageEvent) -> None:
        """列出所有可用人格（AstrBot 数据库 + 手动配置）。"""
        # 重新扫描数据库
        self._personas_cache = self._scan_all_personas()

        lines = [f"🎭 人格列表 (模式: {self._persona_mode})"]
        lines.append("")

        # Auto 模式: 展示 AstrBot 数据库中的人格
        if self._personas_cache:
            lines.append("── AstrBot 人格 ──")
            for persona_id, info in self._personas_cache.items():
                current_mark = " ← 当前" if persona_id == self._current_persona else ""
                has_report = "✅" if info.get("has_report") else "❌"
                lines.append(f"  【{persona_id}】{current_mark} 报告: {has_report}")
                if info.get("labels"):
                    lbl = info["labels"]
                    lines.append(f"    MBTI: {lbl.get('mbti', '?')} | 依恋: {lbl.get('attachment', '?')}")

        if not self._personas_cache:
            lines.append("📭 未检测到任何人格")

        lines.append("💡 使用 /spirit_switch <名称> 切换人格")
        lines.append("💡 使用 /spirit_detail <名称> 查看完整参数")
        yield event.plain_result("\n".join(lines))

    @filter.command("spirit_switch")
    async def spirit_switch(self, event: AstrMessageEvent, persona_id: str = "") -> None:
        """切换到指定人格。用法: /spirit_switch <persona_id>"""
        if not persona_id:
            yield event.plain_result(
                "❓ 用法: /spirit_switch <persona_id>\n"
                "使用 /spirit_personas 查看可用人格"
            )
            return

        # 检查是否在 AstrBot 数据库中
        if persona_id not in self._personas_cache:
            system_prompt = self._read_persona_prompt(persona_id)
            if not system_prompt:
                yield event.plain_result(f"❌ 未找到人格: {persona_id}")
                return

            parsed = parse_persona_report(system_prompt)
            self._personas_cache[persona_id] = {
                "labels": parsed.labels,
                "drives": parsed.drives,
                "traits": parsed.traits,
                "has_report": parsed.has_labels,
            }

        old_persona = self._current_persona
        self._current_persona = persona_id

        cached = self._personas_cache[persona_id]
        if cached.get("labels"):
            self._labels = cached["labels"]
            self._parsed_drives = cached.get("drives", {})
        else:
            self._labels = self._get_default_labels()
            self._parsed_drives = {}
        self._update_baseline()

        # 更新依赖人格的组件
        from .emotion_spirit.superego import ValueAlignment, IdealSelf, ValueResistance
        from .emotion_spirit.superego_guard import SuperegoGuard
        self._alignment = ValueAlignment(self._current_persona)
        self._value_resistance = ValueResistance(self._current_persona)
        self._ideal = IdealSelf(self._current_persona, self._labels)
        self._superego_guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, self._current_persona,
        )

        # 切换 persona 后重置超我层（baseline 依赖 labels）
        if self._persona_initialized:
            self._reset_superego_modules()

        # 标记已初始化
        self._persona_initialized = True

        # 持久化新 persona
        self._store.set("persona", {
            "initialized": True,
            "persona_id": self._current_persona,
            "labels": self._labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._store.save()

        yield event.plain_result(
            f"✅ 已切换人格: {old_persona} → {persona_id}\n"
            f"使用 /spirit_persona 查看标签，/spirit_detail 查看完整参数"
        )

    @filter.command("spirit_init")
    async def spirit_init(self, event: AstrMessageEvent) -> None:
        """初始化当前人格参数。仅 auto 模式需要手动调用。"""
        from .emotion_spirit.label_mapper import labels_to_personality

        if self._persona_mode == "disabled":
            yield event.plain_result("⚠️ 当前为 disabled 模式，无需初始化。请在配置中切换到 auto 模式。")
            return

        if self._persona_initialized:
            yield event.plain_result(
                f"✅ 人格 '{self._current_persona}' 已初始化\n"
                f"使用 /spirit_persona 查看标签，/spirit_detail 查看参数"
            )
            return

        persona_id = self._current_persona
        logger.info("emotion_spirit: /spirit_init 开始初始化人格 '%s'", persona_id)

        # 1. 尝试 LLM 分析
        system_prompt = self._read_persona_prompt(persona_id)
        labels = {}
        drives = {}
        source = "default"

        if system_prompt:
            # 先尝试同步规则解析
            parsed = parse_persona_report(system_prompt)
            if parsed.has_labels:
                labels = parsed.labels
                drives = parsed.drives
                source = "规则解析"
                logger.info("emotion_spirit: 规则解析成功 — %s", labels)

            # 再尝试 LLM 分析（更准确）
            llm = self._get_llm_callable()
            if llm:
                try:
                    analyzer = PersonaAnalyzer(llm)
                    result = await analyzer.analyze(persona_id, system_prompt)
                    if result.has_labels:
                        labels = result.labels
                        drives = result.drives
                        source = "LLM 分析"
                        self._auto_report = result
                        # 缓存报告
                        save_report(result, self._store._dir)
                        logger.info("emotion_spirit: LLM 分析成功 — %s", labels)
                except Exception:
                    logger.warning("emotion_spirit: LLM 分析失败，使用规则解析结果", exc_info=True)

        if not labels:
            labels = self._get_default_labels()
            source = "默认值"

        # 2. 应用标签
        self._labels = labels
        self._parsed_drives = drives
        self._update_baseline()

        # 3. 重新初始化 superego 模块
        from .emotion_spirit.superego import ValueAlignment, IdealSelf, ValueResistance
        from .emotion_spirit.superego_guard import SuperegoGuard
        self._alignment = ValueAlignment(persona_id)
        self._value_resistance = ValueResistance(persona_id)
        self._ideal = IdealSelf(persona_id, labels)
        self._superego_guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, persona_id,
        )
        self._personas_cache = self._scan_all_personas()

        # 4. 标记已初始化
        self._persona_initialized = True

        # 4.5 持久化 persona namespace
        self._store.set("persona", {
            "initialized": True,
            "persona_id": persona_id,
            "labels": labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._store.save()

        # 5. 构建结果
        personality = labels_to_personality(labels)
        label_names = {
            "mbti": "MBTI", "attachment": "依恋风格",
            "emotion_style": "情绪策略", "conflict_style": "冲突风格",
            "time_focus": "时间取向",
        }

        lines = [f"✅ 人格初始化完成: {persona_id}"]
        lines.append(f"📊 来源: {source}")
        lines.append("")
        lines.append("标签:")
        for key, value in labels.items():
            lines.append(f"  {label_names.get(key, key)}: {value}")

        if drives:
            lines.append("")
            lines.append("驱动力:")
            for drive, val in drives.items():
                bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                lines.append(f"  {drive}: {bar} {val:.2f}")

        # 核心/边缘维度
        deep = personality.get("deep", {})
        if deep:
            sorted_dims = sorted(deep.items(), key=lambda x: x[1], reverse=True)
            core = [d for d, v in sorted_dims[:5]]
            peripheral = [d for d, v in sorted_dims[5:]]
            lines.append("")
            lines.append(f"核心维度 ({', '.join(core)})")
            lines.append(f"边缘维度 ({', '.join(peripheral)})")

        lines.append("")
        lines.append("💡 使用 /spirit_detail 查看完整 11 维参数")

        yield event.plain_result("\n".join(lines))

    # ═══ 内部方法 ═══

    def _load_persistent_data(self) -> None:
        """加载所有持久化数据。"""
        # Phase 1
        pool_data = self._store.get("memory_pool")
        if pool_data:
            self._pool = MemoryPool.from_dict(pool_data)
        intimacy_data = self._store.get("intimacy")
        if intimacy_data:
            self._intimacy.from_dict(intimacy_data)
        alignment_data = self._store.get("alignment")
        if alignment_data:
            self._alignment.from_dict(alignment_data)
        conscience_data = self._store.get("conscience")
        if conscience_data:
            self._conscience.from_dict(conscience_data)
        ideal_data = self._store.get("ideal_self")
        if ideal_data:
            self._ideal.from_dict(ideal_data)
        value_resistance_data = self._store.get("value_resistance")
        if value_resistance_data:
            self._value_resistance.from_dict(value_resistance_data)
        superego_guard_data = self._store.get("superego_guard")
        if superego_guard_data:
            self._superego_guard.from_dict(superego_guard_data)

        # Phase 2
        reservoir_data = self._store.get("reservoir")
        if reservoir_data:
            self._reservoir.from_dict(reservoir_data)
        patterns_data = self._store.get("patterns")
        if patterns_data:
            self._patterns.from_dict(patterns_data)
        signals_data = self._store.get("buffer_signals")
        if signals_data:
            self._buffer_signals.from_dict(signals_data)
        shadow_data = self._store.get("shadow")
        if shadow_data and self._shadow:
            self._shadow.from_dict(shadow_data)
        life_sim_data = self._store.get("life_sim")
        if life_sim_data and self._life_sim:
            self._life_sim.from_dict(life_sim_data)
        diary_data = self._store.get("diary")
        if diary_data:
            self._diary.from_dict(diary_data)
        drift_data = self._store.get("drift")
        if drift_data:
            self._drift.from_dict(drift_data)
        sentinel_data = self._store.get("sentinel")
        if sentinel_data and self._sentinel:
            self._sentinel.from_dict(sentinel_data)
        narrative_data = self._store.get("narrative")
        if narrative_data and self._narrative:
            self._narrative.from_dict(narrative_data)
        cf_data = self._store.get("counterfactual")
        if cf_data:
            self._counterfactual.from_dict(cf_data)

        # 重建引用 (from_dict 后 pool/signal 可能已变)
        self._patterns = PatternExtractor(self._pool)
        if patterns_data:
            self._patterns.from_dict(patterns_data)
        self._buffer_signals = BufferSignals(self._pool)
        if signals_data:
            self._buffer_signals.from_dict(signals_data)
        if self._enable_shadow:
            self._shadow = ShadowDetector(self._pool, self._buffer_signals, self._patterns)
            if shadow_data:
                self._shadow.from_dict(shadow_data)

        # 重建持有 pool 引用的模块（pool 被 from_dict 替换后旧引用失效）
        if self._enable_life:
            self._life_sim = LifeSimulator(
                self._consumer, self._pool, self._intimacy,
                self._buffer_signals, self._reservoir,
            )
            if life_sim_data:
                self._life_sim.from_dict(life_sim_data)
        self._diary = DiaryWriter(
            self._pool, self._patterns, self._buffer_signals,
            self._alignment, self._conscience,
        )
        if diary_data:
            self._diary.from_dict(diary_data)
        self._drift = PersonalityDrift(self._consumer, self._reservoir)
        if drift_data:
            self._drift.from_dict(drift_data)
        if self._enable_sentinel:
            self._sentinel = PredictiveSentinel(
                self._consumer, self._buffer_signals, self._reservoir,
                self._conscience, self._alignment, self._ideal,
            )
            if sentinel_data:
                self._sentinel.from_dict(sentinel_data)
        if self._enable_narrative:
            self._narrative = NarrativeIdentity(
                self._pool, self._patterns, self._drift,
                self._buffer_signals, self._diary,
            )
            if narrative_data:
                self._narrative.from_dict(narrative_data)
        self._counterfactual = Counterfactual(self._pool)
        if cf_data:
            self._counterfactual.from_dict(cf_data)
        self._injector = PromptInjector(
            self._pool, self._intimacy, self._alignment,
            self._conscience, self._ideal, self._shadow, self._diary,
        )

    def _save_if_dirty(self) -> None:
        """仅在数据变更时持久化。"""
        self._store.set("memory_pool", self._pool.to_dict())
        self._store.set("intimacy", self._intimacy.to_dict())
        self._store.set("alignment", self._alignment.to_dict())
        self._store.set("conscience", self._conscience.to_dict())
        self._store.set("ideal_self", self._ideal.to_dict())
        self._store.set("value_resistance", self._value_resistance.to_dict())
        self._store.set("superego_guard", self._superego_guard.to_dict())
        self._store.save()

    def _save_all(self) -> None:
        """持久化所有数据。"""
        self._store.set("memory_pool", self._pool.to_dict())
        self._store.set("intimacy", self._intimacy.to_dict())
        self._store.set("alignment", self._alignment.to_dict())
        self._store.set("conscience", self._conscience.to_dict())
        self._store.set("ideal_self", self._ideal.to_dict())
        self._store.set("value_resistance", self._value_resistance.to_dict())
        self._store.set("superego_guard", self._superego_guard.to_dict())
        self._store.set("reservoir", self._reservoir.to_dict())
        self._store.set("patterns", self._patterns.to_dict())
        self._store.set("buffer_signals", self._buffer_signals.to_dict())
        if self._shadow:
            self._store.set("shadow", self._shadow.to_dict())
        if self._life_sim:
            self._store.set("life_sim", self._life_sim.to_dict())
        self._store.set("diary", self._diary.to_dict())
        self._store.set("drift", self._drift.to_dict())
        if self._sentinel:
            self._store.set("sentinel", self._sentinel.to_dict())
        if self._narrative:
            self._store.set("narrative", self._narrative.to_dict())
        self._store.set("counterfactual", self._counterfactual.to_dict())

    # ═══ 公开 API（v1.1.1）═══

    async def get_emotion_state(self, session_key: str) -> dict | None:
        """统一情绪状态 API（v1.1.1 主 API，9 字段）。

        Args:
            session_key: 通常是 event.unified_msg_origin 或 session_id

        Returns:
            None if no signals for session_key, else dict with:
            - pad: {valence, arousal, dominance}
            - distribution: dict[str, float]
            - primary: str
            - secondary: str | None
            - intensity: float
            - description: str  # 懒计算，每次调用都重新渲染
            - label: str (向后兼容)
        """
        signals = self._latest_signals.get(session_key)
        if signals is None:
            return None

        # 懒渲染 description（每次调用都重新计算，< 1μs）
        description = render_description(
            signals.pad_distribution, signals.pad_intensity
        )

        return {
            "pad": {
                "valence": signals.pad_valence,
                "arousal": signals.pad_arousal,
                "dominance": signals.pad_dominance,
            },
            "distribution": dict(signals.pad_distribution),
            "primary": signals.pad_primary,
            "secondary": signals.pad_secondary,
            "intensity": signals.pad_intensity,
            "description": description,
            "label": signals.pad_label,  # 向后兼容
        }

    async def get_body_state(self, session_key: str) -> dict | None:
        """身体生理状态 API（v1.1.1 重命名自 get_emotion_values，4 字段）。

        Returns:
            None if no signals for session_key, else dict with:
            - warmth, pulse, expression, repair (各 1 浮点)
        """
        signals = self._latest_signals.get(session_key)
        if signals is None:
            return None

        return {
            "warmth": signals.valence_warmth,
            "pulse": signals.connection_circulation,
            "expression": signals.needs_expression,
            "repair": signals.valence_repair_heat,
        }
        self._store.save()
