"""emotion_spirit — Sylanne Engine 之上的长期记忆、人格演化与超我调控。

AstrBot 插件入口 (Phase B, P3-1 拆分后)。
- 28 模块装配: emotion_spirit.plugin_factory.build()
- 12 命令: emotion_spirit.command_router.CommandRouter (3 ns)
- 3 公开 API: emotion_spirit.public_api.PublicAPI
- 12 命令实现: emotion_spirit.commands.CommandImpl
- 重 Surface 消费: emotion_spirit.surface_handler.SurfaceHandler
- 旧 /spirit_* 命令: spirit_*_legacy 兼容层 (1-2 版本期)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .emotion_spirit.core.plugin_factory import build as build_modules
from .emotion_spirit.output.command_router import CommandRouter
from .emotion_spirit.output.public_api import PublicAPI
from .emotion_spirit.output.commands import CommandImpl
from .emotion_spirit.output.surface_handler import SurfaceHandler

# 兼容层: 这些直接 import 不动, 减少 commands.py 的依赖耦合
from .emotion_spirit.regulation.persona_analyzer import save_report, load_report
from .emotion_spirit.regulation.persona_report_parser import parse_persona_report


def _legacy_redirect(old_name: str, new_name: str, new_attr: str):
    """生成旧 /spirit_* 命令的兼容方法, 带 deprecation 警告 + 转发到新 ns handler.

    用法 (类体中):
        spirit_init_legacy = _legacy_redirect("spirit_init", "setup_init", "setup_init")

    Args:
        old_name: 旧命令名 (e.g. "spirit_init")
        new_name: 提示文案中的新命令名 (e.g. "setup_init")
        new_attr: self._cmd 上对应的新方法名 (e.g. "setup_init" 或 "view_whoami")
                 当 new_name 与 new_attr 不一致时, 提示文案与实际 handler 路由解耦。
    """
    @filter.command(old_name)
    async def legacy(self, event: AstrMessageEvent, *args, **kwargs):
        yield event.plain_result(f"⚠️ /{old_name} 已废弃, 请用 /{new_name}")
        new_handler = getattr(self._cmd, new_attr)
        async for r in new_handler(event, *args, **kwargs):
            yield r
    return legacy


class EmotionSpiritPlugin(Star):
    """emotion_spirit — 自我层 + 超我反思层 (Phase B, P3-1 拆分后 ~470 行)。"""

    def __init__(self, context: Context, config: dict[str, Any] | None = None) -> None:
        super().__init__(context)
        self._config = config or {}
        self._engine: Any = None

        # 数据目录
        data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"

        # ═══ 1. plugin_factory.build() 装配 28 模块 (走 L2 工厂) ═══
        # 必须先于 _setup_persona_state, 因为后者的 labels 传给 factory
        self._modules = build_modules(
            build_modules_default_config(str(data_dir), self._config)
        )

        # ═══ 2. 公开 API 网关 ═══
        self._public_api = PublicAPI(self._modules)

        # ═══ 3. persona 状态 (在 setup_persona_state 中用 _modules 初始化) ═══
        self._setup_persona_state()

        # ═══ 4. 命令路由器 (3 ns) ═══
        self._router = CommandRouter()
        self._cmd = CommandImpl(self)
        self._setup_commands()

        # ═══ 5. Surface 处理器 ═══
        self._surface_handler = SurfaceHandler(self, self._modules)

        # v1.1.1: 公开 API 缓存层 (signals 缓存, 旧 API 兼容)
        self._latest_signals: dict[str, Any] = {}
        # session_id → 最近的用户消息文本
        self._last_texts: dict[str, str] = {}
        # 注入队列 (engine.inject 需要 async, listener 是 sync)
        self._inject_queue: list[tuple[str, str, float, str]] = []
        # 安全层状态 (由 SurfaceHandler 更新, on_llm_request 读取)
        self._safety_level: str = "normal"
        self._safety_note: str | None = None
        self._repair_advice: str | None = None

    # ═══ Persona State Setup ═══

    def _setup_persona_state(self) -> None:
        """初始化 persona 状态 (在 _modules 装配后调用)。"""
        from .emotion_spirit.regulation.persona_analyzer import PersonaAnalysisResult
        from .emotion_spirit.regulation.superego import ValueAlignment, ConscienceTracker, IdealSelf, ValueResistance
        from .emotion_spirit.regulation.superego_guard import SuperegoGuard

        self._store = self._modules["store"]

        self._persona_mode = self._config.get("persona_mode", "disabled")
        self._current_persona = (
            self._config.get("auto_source", "")
            or self._detect_default_persona()
        )

        self._parsed_drives: dict[str, float] = {}
        self._labels: dict[str, str] = {}
        self._auto_report: PersonaAnalysisResult | None = None
        self._persona_initialized: bool = False
        self._relabel_pending: bool = False

        if self._persona_mode == "auto":
            if not self._current_persona:
                self._current_persona = self._detect_default_persona()
            logger.info(
                "emotion_spirit: auto 模式, 人格 '%s' 待初始化 (发送 /setup_init)",
                self._current_persona,
            )
        elif self._persona_mode == "disabled":
            self._labels = self._get_default_labels()
            logger.info("emotion_spirit: disabled 模式, 使用 Sylanne 默认行为")
        else:
            self._persona_mode = "disabled"
            self._labels = self._get_default_labels()
            logger.info("emotion_spirit: 未知模式, 回退到 disabled")

        self._update_baseline()

        # ═══ 功能开关 ═══
        toggles = self._config.get("feature_toggles", {})
        self._enable_shadow = toggles.get("enable_shadow_detector", True)
        self._enable_sentinel = toggles.get("enable_sentinel", True)
        self._enable_narrative = toggles.get("enable_narrative", True)
        self._enable_life = toggles.get("life_simulator_mode", "both") and toggles.get("enable_life_simulator", True)
        self._life_mode = toggles.get("life_simulator_mode", "both")
        self._enable_surface_logging = toggles.get("enable_surface_logging", False)

        # Phase 1 组件 (从 _modules 拿)
        self._consumer = self._modules["surface_consumer"]
        self._pool = self._modules["memory_pool"]
        self._intimacy = self._modules["intimacy"]
        self._conscience = self._modules["superego"]["conscience"]
        self._alignment = self._modules["superego"]["alignment"]
        self._value_resistance = self._modules["superego"]["resistance"]
        self._ideal = self._modules["superego"]["ideal"]
        self._superego_guard = self._modules["superego_guard"]
        self._baseline_personality: dict[str, dict[str, float]] = {}
        self._interaction_count: int = 0

        # Phase 2 组件
        self._reservoir = self._modules["meaning_reservoir"]
        self._buffer_signals = self._modules["buffer_signals"]
        self._patterns = self._modules["pattern_extractor"]
        self._shadow = self._modules.get("shadow_detector") if self._enable_shadow else None
        self._life_sim = self._modules.get("life_simulator") if self._enable_life else None
        self._diary = self._modules["diary_writer"]
        self._injector = self._modules["prompt_injector"]
        self._drift = self._modules["personality_drift"]
        self._sentinel = self._modules.get("predictive_sentinel") if self._enable_sentinel else None
        self._narrative = self._modules.get("narrative_identity") if self._enable_narrative else None
        self._counterfactual = self._modules["counterfactual"]

        # Phase 2.0: 社交智能
        self._social_graph = self._modules["social_graph"]
        self._topic_privacy = self._modules["topic_privacy"]
        self._decision = self._modules["bot_decision"]

        # Phase 2.5: 关系人格
        self._relationship_personality = self._modules["relationship_personality"]

        # Phase 1 观察期: Surface 日志记录器
        self._surface_logger: Any = None
        if self._enable_surface_logging:
            try:
                from verification.surface_logger import SurfaceLogger as _SL
                log_dir = Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit" / "surface_logs"
                self._surface_logger = _SL(
                    output_dir=str(log_dir),
                    anonymize=True,
                    max_age_days=7,
                )
                logger.info("emotion_spirit: Surface 日志已启用 → %s", log_dir)
            except Exception:
                logger.warning("emotion_spirit: Surface 日志初始化失败", exc_info=True)

        # 多人格支持
        self._personas_cache: dict[str, dict[str, Any]] = self._scan_all_personas()

    def _setup_commands(self) -> None:
        """注册 12 命令到 3 ns。"""
        setup = self._router.namespace("setup")
        setup.command("init", help_text="初始化人格")(self._cmd.setup_init)
        setup.command("relabel", help_text="重置 5 轴标签")(self._cmd.setup_relabel)
        setup.command("switch", help_text="切换 persona")(self._cmd.setup_switch)
        setup.command("list", help_text="列出所有 persona")(self._cmd.setup_list)

        view = self._router.namespace("view")
        view.command("status", help_text="状态总览")(self._cmd.view_status)
        view.command("detail", help_text="11 维参数详情")(self._cmd.view_detail)
        view.command("whoami", help_text="当前 persona")(self._cmd.view_whoami)

        reflect = self._router.namespace("reflect")
        reflect.command("drift", help_text="漂移趋势")(self._cmd.reflect_drift)
        reflect.command("sentinel", help_text="预测预警")(self._cmd.reflect_sentinel)
        reflect.command("shadows", help_text="阴影检测")(self._cmd.reflect_shadows)
        reflect.command("diary", help_text="日记查看")(self._cmd.reflect_diary)
        reflect.command("patterns", help_text="模式识别")(self._cmd.reflect_patterns)

    # ═══ Persona Management (kept in main.py for now) ═══

    def _get_default_labels(self) -> dict[str, str]:
        return {
            "mbti": "ISTJ",
            "attachment": "安全型",
            "emotion_style": "混合型",
            "conflict_style": "合作型",
            "time_focus": "活在当下",
        }

    def _update_baseline(self) -> None:
        from .emotion_spirit.memory.persona_profiles import get_personality_params
        self._baseline_personality = get_personality_params(self._labels)
        self._interaction_count = 0
        logger.info("emotion_spirit: baseline personality updated from labels")

    @staticmethod
    def _validate_labels(labels: tuple[str, ...]) -> dict[str, str] | None:
        if len(labels) != 5:
            return None
        mbti, attachment, emotion_style, conflict_style, time_focus = labels
        from .emotion_spirit.core.label_mapper import LABEL_OPTIONS
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
            "mbti": mbti, "attachment": attachment,
            "emotion_style": emotion_style, "conflict_style": conflict_style,
            "time_focus": time_focus,
        }

    def _scan_all_personas(self) -> dict[str, dict[str, Any]]:
        personas_cache: dict[str, dict[str, Any]] = {}
        try:
            import sqlite3
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

    def _read_persona_prompt(self, persona_id: str) -> str | None:
        try:
            import sqlite3
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
        try:
            import json
            config_path = Path(get_astrbot_data_path()) / "cmd_config.json"
            if not config_path.exists():
                return "xiaofu"
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
            default_persona = config.get("provider_settings", {}).get("default_personality", "")
            if default_persona:
                logger.info("emotion_spirit: 从 AstrBot 配置检测到默认人格: %s", default_persona)
                return default_persona
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
            logger.info("emotion_spirit: 未检测到默认人格，使用 xiaofu")
            return "xiaofu"
        except Exception:
            logger.debug("emotion_spirit: 检测默认人格失败", exc_info=True)
            return "xiaofu"

    def _get_llm_callable(self) -> Any:
        try:
            provider = self.context.get_using_provider()
            if provider and hasattr(provider, "text_chat"):
                async def _llm(system_prompt: str, user_prompt: str) -> str:
                    resp = await provider.text_chat(
                        prompt=user_prompt, system_prompt=system_prompt,
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
            self._migrate_old_spirit_data()

    def _reset_superego_modules(self) -> None:
        from .emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
        from .emotion_spirit.regulation.superego_guard import SuperegoGuard

        self._conscience = ConscienceTracker()
        self._alignment = ValueAlignment(self._current_persona)
        self._value_resistance = ValueResistance(self._current_persona)
        self._ideal = IdealSelf(self._current_persona, self._labels)
        self._superego_guard = SuperegoGuard(
            self._conscience, self._alignment, self._ideal, self._current_persona,
        )

        for key in ("conscience", "alignment", "ideal_self", "value_resistance", "superego_guard", "persona_report"):
            self._store.set(key, None)

        report_path = self._store._dir / "persona_report.json"
        if report_path.exists():
            report_path.unlink()

        self._store.save()
        logger.info("emotion_spirit: 超我层已重置（13 维 baseline 已用新 labels 重推）")

    def _migrate_old_spirit_data(self) -> None:
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
        if not labels:
            labels = self._get_default_labels()
            logger.warning(
                "emotion_spirit: 检测到老数据但无 persona 配置, 使用默认 labels (ISTJ-安全型)。"
                "请用 /setup_relabel 调整为正确 persona。"
            )
        self._store.set("persona", {
            "initialized": True,
            "persona_id": self._current_persona or "unknown",
            "labels": labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._store.save()
        self._persona_initialized = True
        self._labels = labels
        logger.info("emotion_spirit: 老数据迁移完成，persona = %s", labels)

    # ═══ 生命周期 ═══

    async def initialize(self) -> None:
        self._store.load()
        self._load_persistent_data()
        self._load_persona_state()
        if self._persona_initialized:
            self._update_baseline()
            from .emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
            from .emotion_spirit.regulation.superego_guard import SuperegoGuard
            self._alignment = ValueAlignment(self._current_persona)
            self._value_resistance = ValueResistance(self._current_persona)
            self._ideal = IdealSelf(self._current_persona, self._labels)
            self._superego_guard = SuperegoGuard(
                self._conscience, self._alignment, self._ideal, self._current_persona,
            )

        asyncio.get_event_loop().call_later(2.0, self._connect_engine_sync)
        asyncio.get_event_loop().call_later(3.0, lambda: asyncio.ensure_future(self._verify_llm_chain()))

        logger.info(
            "emotion_spirit initialized: mode=%s persona=%s buffer=%d warm=%d cold=%d ghosts=%d",
            self._persona_mode, self._current_persona,
            len(self._pool.buffer), len(self._pool.warm),
            len(self._pool.cold), len(self._pool.ghosts),
        )

    async def _verify_llm_chain(self) -> None:
        llm = self._get_llm_callable()
        if not llm:
            return
        try:
            result = await llm("回复 OK 即可。", "测试")
            logger.info("emotion_spirit: [LLM验证] 调用成功 — %s", result[:50] if result else "(空)")
        except Exception as e:
            logger.warning("emotion_spirit: [LLM验证] 调用失败 — %s: %s", type(e).__name__, e)

    def _connect_engine_sync(self) -> None:
        try:
            from sylanne_core import get_engine
            self._engine = get_engine()
            self._engine.on(self._on_surface)
            logger.info("emotion_spirit: SylannEngine 连接成功, 监听器已注册")
        except (ImportError, RuntimeError) as e:
            if not hasattr(self, '_retry_count'):
                self._retry_count = 0
            self._retry_count += 1
            if self._retry_count < 3:
                logger.info("emotion_spirit: SylannEngine 尚未就绪, %d 秒后重试...", 5 * self._retry_count)
                asyncio.get_event_loop().call_later(5.0 * self._retry_count, self._connect_engine_sync)
            else:
                logger.warning("emotion_spirit: SylannEngine 不可用 (%s)", e)
                self._engine = None

    async def terminate(self) -> None:
        if self._engine is not None:
            try:
                self._engine.off(self._on_surface)
            except Exception:
                pass
        self._save_all()
        logger.info("emotion_spirit terminated: data saved")

    # ═══ SylannEngine Surface 监听器 (sync callback) ═══

    def _on_surface(self, session_id: str, surface: dict[str, Any]) -> None:
        try:
            self._consume_surface(session_id, surface)
        except Exception:
            logger.warning("emotion_spirit: _on_surface 异常", exc_info=True)

    def _consume_surface(self, session_id: str, surface: dict[str, Any]) -> None:
        """委托给 SurfaceHandler 处理。"""
        self._surface_handler.consume(session_id, surface, self._latest_signals)
        # 同步安全层状态
        self._safety_level = self._surface_handler.safety_level
        self._safety_note = self._surface_handler.safety_note
        self._repair_advice = self._surface_handler.repair_advice

    # ═══ LLM 请求注入 ═══

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: Any) -> None:
        user_id = event.get_sender_id()
        text = event.message_str

        self._last_texts[user_id] = text
        if len(self._last_texts) > 100:
            oldest = list(self._last_texts.keys())[:50]
            for k in oldest:
                del self._last_texts[k]

        if self._engine is not None:
            try:
                session_key = event.unified_msg_origin
                surface = await self._engine.process(session_key, text)
                self._consume_surface(user_id, surface)
            except Exception:
                logger.warning("emotion_spirit: engine.process 失败", exc_info=True)

        await self._flush_inject_queue()

        if self._persona_mode == "disabled":
            return
        if self._persona_mode == "auto" and not self._persona_initialized:
            return

        current_personality = {
            "deep": self._consumer.consume({}).personality_deep or {},
            "surface": self._consumer.consume({}).personality_surface or {},
        }
        current_personality = self._relationship_personality.apply_to_layers(
            current_personality, user_id,
        )
        tone = self._intimacy.get_relationship_tone(user_id)
        if tone:
            self._relationship_personality.apply_tone(user_id, tone)
        segment = self._intimacy.get_segment(user_id)
        self._injector.set_intimacy_segment(user_id, segment)
        gossip_tendency = current_personality.get("surface", {}).get("gossip_tendency", 0.4)
        context = self._injector.build_context(
            user_id=user_id,
            persona=self._current_persona,
            current_personality=current_personality,
            safety_level=self._safety_level,
            safety_note=self._safety_note,
            repair_advice=self._repair_advice,
            gossip_tendency=gossip_tendency,
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

    # ═══ 旧 /spirit_* 命令兼容层 (1-2 版本期) ═══
    # 通过 _legacy_redirect 工厂统一生成, 12 个旧命令均带 deprecation 警告 + 转发。
    # - old_name: 旧 /spirit_* 命令名
    # - new_name: 提示给用户的新 /ns_sub 命令名 (用于 deprecation 警告文案)
    # - new_attr: self._cmd 上对应的新方法名
    # 注意: spirit_persona 的 new_name="setup_whoami" 是历史 typo (新方法实际在 view_whoami),
    # 保留此文案以避免改变已发布 deprecation 警告的语义, 仅在内部路由到正确 handler。

    spirit_init_legacy = _legacy_redirect("spirit_init", "setup_init", "setup_init")
    spirit_relabel_legacy = _legacy_redirect("spirit_relabel", "setup_relabel", "setup_relabel")
    spirit_switch_legacy = _legacy_redirect("spirit_switch", "setup_switch", "setup_switch")
    spirit_personas_legacy = _legacy_redirect("spirit_personas", "setup_list", "setup_list")
    spirit_status_legacy = _legacy_redirect("spirit_status", "view_status", "view_status")
    spirit_detail_legacy = _legacy_redirect("spirit_detail", "view_detail", "view_detail")
    spirit_persona_legacy = _legacy_redirect("spirit_persona", "setup_whoami", "view_whoami")
    spirit_drift_legacy = _legacy_redirect("spirit_drift", "reflect_drift", "reflect_drift")
    spirit_sentinel_legacy = _legacy_redirect("spirit_sentinel", "reflect_sentinel", "reflect_sentinel")
    spirit_shadows_legacy = _legacy_redirect("spirit_shadows", "reflect_shadows", "reflect_shadows")
    spirit_diary_legacy = _legacy_redirect("spirit_diary", "reflect_diary", "reflect_diary")
    spirit_patterns_legacy = _legacy_redirect("spirit_patterns", "reflect_patterns", "reflect_patterns")

    # ═══ 内部方法: 持久化 ═══

    def _load_persistent_data(self) -> None:
        from .emotion_spirit.memory.memory_pool import MemoryPool
        from .emotion_spirit.output.buffer_signals import BufferSignals
        from .emotion_spirit.regulation.pattern_extractor import PatternExtractor
        from .emotion_spirit.regulation.shadow_detector import ShadowDetector
        from .emotion_spirit.regulation.life_simulator import LifeSimulator
        from .emotion_spirit.output.diary_writer import DiaryWriter
        from .emotion_spirit.regulation.personality_drift import PersonalityDrift
        from .emotion_spirit.output.predictive_sentinel import PredictiveSentinel
        from .emotion_spirit.output.narrative_identity import NarrativeIdentity
        from .emotion_spirit.regulation.counterfactual import Counterfactual
        from .emotion_spirit.output.prompt_injector import PromptInjector

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

        reservoir_data = self._store.get("reservoir")
        if reservoir_data:
            self._reservoir.from_dict(reservoir_data)
        patterns_data = self._store.get("patterns")
        signals_data = self._store.get("buffer_signals")
        shadow_data = self._store.get("shadow")
        life_sim_data = self._store.get("life_sim")
        diary_data = self._store.get("diary")
        drift_data = self._store.get("drift")
        sentinel_data = self._store.get("sentinel")
        narrative_data = self._store.get("narrative")
        cf_data = self._store.get("counterfactual")

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
            buffer_signals=self._buffer_signals,
        )

    def _save_if_dirty(self) -> None:
        self._store.set("memory_pool", self._pool.to_dict())
        self._store.set("intimacy", self._intimacy.to_dict())
        self._store.set("alignment", self._alignment.to_dict())
        self._store.set("conscience", self._conscience.to_dict())
        self._store.set("ideal_self", self._ideal.to_dict())
        self._store.set("value_resistance", self._value_resistance.to_dict())
        self._store.set("superego_guard", self._superego_guard.to_dict())
        self._store.save()

    def _save_all(self) -> None:
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

    # ═══ 公开 API (v1.1.1 + v1.2 扩展) — 保持向后兼容结构 ═══
    # 注: PublicAPI 网关提供 flat 结构 (B6.10), 这里保留 nested "pad"/"distribution" 结构
    # 因为现有集成测试 (test_emotion_integration.py) 期望 nested 结构。

    async def get_emotion_state(
        self, session_key: str, include_trajectory: bool = False,
    ) -> dict | None:
        """统一情绪状态 API (v1.1.1 9 字段 + v1.2 +ambiguity +velocity = 11 字段)。"""
        from .emotion_spirit.output.emotion_classifier import render_description

        signals = self._latest_signals.get(session_key)
        if signals is None:
            return None

        # 懒渲染 description (每次调用都重新计算, < 1μs)
        description = render_description(
            signals.pad_distribution, signals.pad_intensity
        )

        state = {
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
            # v1.2 新增 2 字段
            "emotion_ambiguity": signals.emotion_ambiguity,
            "emotion_velocity": signals.emotion_velocity,
        }

        # v1.7.2 Phase A: trajectory 作为可选字段
        if include_trajectory:
            state["emotion_trajectory"] = [
                {"valence": v, "arousal": a, "dominance": d, "timestamp": t}
                for v, a, d, t in signals.emotion_trajectory
            ]

        return state

    async def get_body_state(self, session_key: str) -> dict | None:
        """身体生理状态 API (v1.1.1 重命名自 get_emotion_values, 4 字段)。"""
        signals = self._latest_signals.get(session_key)
        if signals is None:
            return None

        return {
            "warmth": signals.valence_warmth,
            "pulse": signals.connection_circulation,
            "expression": signals.needs_expression,
            "repair": signals.valence_repair_heat,
        }


def build_modules_default_config(data_dir: str, config: dict | None) -> dict:
    """构造 plugin_factory.build() 的默认 config。"""
    from .emotion_spirit.core.plugin_factory import default_config
    persona_id = (config or {}).get("auto_source", "") or ""
    return default_config(data_dir=data_dir, persona_id=persona_id, labels={})
