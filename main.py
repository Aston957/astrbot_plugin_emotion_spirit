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
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# persona_id 的 sentinel(占位符)值集合 — 表示"还没真正选过人格"
# 出现这些值时,_load_persona_state 视为"未初始化",让 /setup_init 走正常路径
_SENTINEL_PERSONA_IDS = frozenset({"default", "unknown", ""})

from emotion_spirit.core.plugin_factory import build as build_modules
from emotion_spirit.output.command_router import CommandRouter
from emotion_spirit.output.public_api import PublicAPI
from emotion_spirit.output.commands import CommandImpl
from emotion_spirit.output.surface_handler import SurfaceHandler

# 兼容层: 这些直接 import 不动, 减少 commands.py 的依赖耦合
from emotion_spirit.regulation.persona_analyzer import save_report, load_report
from emotion_spirit.regulation.persona_report_parser import parse_persona_report


def _ns_command(name: str, cmd_attr: str, desc: str = ""):
    """把 CommandImpl.{cmd_attr} 方法注册为 AstrBot /{name} 命令 (Phase 4 post-merge ns 化).

    用法 (类体中):
        setup_init_cmd = _ns_command("setup_init", "setup_init", "初始化当前人格参数...")

    Args:
        name: AstrBot 命令名 (e.g. "setup_init", "view_status", "reflect_drift")
        cmd_attr: self._cmd 上对应的方法名 (CommandImpl 类)
        desc: 命令描述,显示在 /help 列表和 dashboard 命令面板

    Note (v4.25.5 兼容性):
    - 不在签名里放 *args/**kwargs(v4.25.5 CommandFilter 会把 validate 后的 kwargs 当作必填)
    - 给每个 handler 唯一 __name__,避免 12 个 CommandFilter 共享同一个 _handler
      导致 cmd_attr 闭包永远是第一个命令
    """
    async def _ns_handler(self, event: AstrMessageEvent):
        handler = getattr(self._cmd, cmd_attr)
        # 从 v4.25.5 校验后的 parsed_params 读第一个用户参数
        parsed = event.get_extra("parsed_params") or {}
        first_arg = parsed.get("args")
        # 'args' 缺失或为 typing.Any(没传用户参数)→ 不传位置参数
        if first_arg is None or first_arg is Any:
            args_tuple: tuple = ()
        elif isinstance(first_arg, str):
            args_tuple = (first_arg,)
        else:
            args_tuple = (str(first_arg),)
        async for r in handler(event, *args_tuple):
            yield r

    # 关键: 在 @filter.command 应用前重命名,让每个 handler 在 star_handlers_registry 里独立
    _ns_handler.__name__ = f"_ns_handler_{cmd_attr}"
    # 同时把 desc 写到 __doc__,register/star_handler.py:63 优先从 docstring 取 desc
    if desc:
        _ns_handler.__doc__ = desc
    return filter.command(name, desc=desc)(_ns_handler)


class EmotionSpiritPlugin(Star):
    """emotion_spirit — 自我层 + 超我反思层 (Phase B, P3-1 拆分后 ~470 行)。"""

    def __init__(self, context: Context, config: dict[str, Any] | None = None) -> None:
        super().__init__(context)
        self._config = config or {}
        self._engine: Any = None

        # 跑 config migration (必须在 build_modules 之前, 否则老 config 升级后
        # build_modules 用的是旧 schema 字段, 整个 plugin 用错配置跑)
        self._config = self._run_config_migration_and_reload(self._config)

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

    # ═══ Config Migration ═══

    def _run_config_migration_and_reload(self, config: dict) -> dict:
        """从 cmd_config.json 读 config, 跑 migration, 写回, 返回新 config.

        即使 AstrBot 已经把 config 传给我们, 我们仍然从文件读:
        1. AstrBot 传入的 config 可能不是最新 (缓存)
        2. 写盘需要文件路径
        """
        from emotion_spirit.migrations import run_migrations, MigrationState
        config_path = (
            Path(get_astrbot_data_path())
            / "config"
            / "astrbot_plugin_emotion_spirit_config.json"
        )
        data_dir = (
            Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
        )

        if not config_path.exists():
            return config

        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                file_config = json.load(f)
            state = MigrationState(data_dir).load_or_init()
            new_config, new_state = run_migrations(file_config, state)

            # 写盘顺序: config 先, state 后. 这样如果 state.save 失败,
            # 下次启动会重跑 migration (幂等), 不会丢数据
            if new_config != file_config:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, ensure_ascii=False, indent=2)
                logger.info(
                    "Config migration applied, saved %s", config_path
                )
            new_state.save()

            # 合并: 用文件的新 config 覆盖 AstrBot 传入的
            return new_config
        except Exception as e:
            logger.warning(
                "Config migration failed: %s, using AstrBot-passed config", e
            )
            return config

    # ═══ Web API 端点 ═══

    def _setup_web_apis(self) -> None:
        """注册 Web API 端点 (本次只加 migration 端点)."""
        self.context.register_web_api(
            route="emotion_spirit/re_run_migration",
            view_handler=self._api_re_run_migration,
            methods=["POST"],
            desc="手动重跑 config migration",
        )

    async def _api_re_run_migration(self, **kwargs):
        """POST /emotion_spirit/re_run_migration — 强制重跑 migration."""
        from emotion_spirit.migrations import run_migrations, MigrationState
        from quart import jsonify as quart_jsonify
        try:
            config_path = (
                Path(get_astrbot_data_path())
                / "config"
                / "astrbot_plugin_emotion_spirit_config.json"
            )
            data_dir = (
                Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
            )
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            state = MigrationState(data_dir).load_or_init()
            new_config, new_state = run_migrations(config, state, force=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, ensure_ascii=False, indent=2)
            new_state.save()
            return quart_jsonify({
                "status": "ok",
                "config": new_config,
                "state": new_state.to_dict(),
            })
        except Exception as e:
            logger.warning("Manual re-run migration failed: %s", e)
            return quart_jsonify({"status": "error", "msg": str(e)}), 500

    # ═══ Persona State Setup ═══

    def _setup_persona_state(self) -> None:
        """初始化 persona 状态 (在 _modules 装配后调用)。"""
        from emotion_spirit.regulation.persona_analyzer import PersonaAnalysisResult
        from emotion_spirit.regulation.superego import ValueAlignment, ConscienceTracker, IdealSelf, ValueResistance
        from emotion_spirit.regulation.superego_guard import SuperegoGuard

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
        self._enable_surface_logging = toggles.get("enable_surface_logging", False)

        # v1.1.0A: life_sim_v2 配置 (合并旧 life_simulator + proactive_chat)
        life_sim_v2_cfg = self._config.get("life_sim_v2", {})
        self._enable_proactive_prompt = life_sim_v2_cfg.get("enable_proactive_prompt", True)
        self._enable_life = True  # v2 always enabled when plugin is active

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

        # Phase F: Bridge 层 (SylannEngine ↔ emotion_spirit)
        from emotion_spirit.bridge.engine_manager import EngineManager
        from emotion_spirit.bridge.hotpool_forwarder import HotPoolForwarder
        from emotion_spirit.bridge.personality_bridge import PersonalityBridge
        self._engine_manager = EngineManager()
        self._hotpool_forwarder = HotPoolForwarder(memory_pool=self._pool)
        self._personality_bridge = PersonalityBridge()
        self._engine_manager.set_forwarder(self._hotpool_forwarder)
        # configure bot_decision proactive deps
        self._decision.configure_proactive_deps(
            memory_pool=self._pool,
            life_simulator=self._life_sim,
        )

        # Phase G: LifeSimulator LLM callable 注入
        if self._life_sim is not None:
            self._life_sim.configure(llm_caller=self._get_llm_callable())

        # v1.1.0A: LifeSimulator v2 (轴心功能 — 主动日程规划)
        from emotion_spirit.regulation.life_simulator import LifeSimulatorV2
        self._life_sim_v2 = LifeSimulatorV2(
            consumer=self._consumer,
            memory=self._pool,
            intimacy=self._intimacy,
            signals=self._buffer_signals,
            reservoir=self._reservoir,
        )
        self._life_sim_v2.configure(llm_caller=self._get_llm_callable())
        self._last_plan_date: str = ""  # 防止同一天重复生成日程

        # Phase B: RealtimeDispatch + RhythmLearner
        from emotion_spirit.output.realtime_dispatch import RealtimeDispatch
        from emotion_spirit.output.rhythm_learner import RhythmLearner
        self._realtime_dispatch = RealtimeDispatch()
        self._rhythm_learner = RhythmLearner()

        # v1.1.0B: Multi-agent architecture
        from emotion_spirit.agents.self_core import SelfCore
        from emotion_spirit.agents.memory_agent import MemoryAgent
        from emotion_spirit.agents.personality_agent import PersonalityAgent
        from emotion_spirit.agents.relationship_agent import RelationshipAgent
        from emotion_spirit.agents.life_agent import LifeAgent

        self._self_core = SelfCore(llm_budget=2)
        self._self_core.register(MemoryAgent(self._self_core.bus, self._pool, self._shadow))
        self._self_core.register(PersonalityAgent(self._self_core.bus, self._superego_guard, self._drift))
        self._self_core.register(RelationshipAgent(self._self_core.bus, self._intimacy, self._social_graph))
        self._self_core.register(LifeAgent(
            self._self_core.bus,
            self._life_sim_v2,
            personality=self._baseline_personality.get("deep", {}),
        ))
        self._last_bot_reply_time: dict[str, float] = {}  # for ReflexLearner behavior signal

        # v1.1.0B: ReflexLearner (Phase 0 T3: @register 化, 从 _modules 取)
        self._reflex_store = self._modules["reflex_learner_store"]
        self._reflex_learner = self._modules["reflex_learner"]
        self._self_core.set_store(self._reflex_store)

        # v1.1.0B: DreamGenerator (Phase 0 T3: @register 化, 从 _modules 取)
        self._dream_generator = self._modules["dream_generator"]
        self._dream_generator.configure(llm_caller=self._get_llm_callable())

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
        view.command("memory", help_text="记忆池条目摘要")(self._cmd.view_memory)
        view.command("force", help_text="三元力学状态")(self._cmd.view_force)
        view.command("schedule", help_text="今天的日程")(self._cmd.view_schedule)

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
        from emotion_spirit.memory.persona_profiles import get_personality_params
        self._baseline_personality = get_personality_params(self._labels)
        self._interaction_count = 0
        logger.info("emotion_spirit: baseline personality updated from labels")

    @staticmethod
    def _validate_labels(labels: tuple[str, ...]) -> dict[str, str] | None:
        if len(labels) != 5:
            return None
        mbti, attachment, emotion_style, conflict_style, time_focus = labels
        from emotion_spirit.core.label_mapper import LABEL_OPTIONS
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
            saved_persona_id = persona_data.get("persona_id", "")
            config_persona = self._config.get("auto_source", "")
            # 优先级: 持久化是 sentinel 占位 + config 显式指定了真实 persona
            # → 视为首次启动,config 优先,让 /setup_init 走正常路径
            if (
                config_persona
                and saved_persona_id in _SENTINEL_PERSONA_IDS
                and config_persona not in _SENTINEL_PERSONA_IDS
            ):
                logger.info(
                    "emotion_spirit: config 指定 '%s' 覆盖持久化占位 %r,"
                    "使用 config 路径",
                    config_persona, saved_persona_id,
                )
                self._persona_initialized = False
                self._labels = {}
                return
            self._persona_initialized = True
            self._labels = dict(persona_data.get("labels", {}))
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
        from emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
        from emotion_spirit.regulation.superego_guard import SuperegoGuard

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
        # 关键: 如果 _current_persona 是 sentinel 占位符(说明没真正选过),
        # 不能假装"已初始化" — 否则会污染后续 restart 的 _load_persona_state 路径。
        # 保留 labels 供 /view 类参考,但 persona_initialized 留 False,等用户显式初始化。
        if self._current_persona in _SENTINEL_PERSONA_IDS:
            logger.warning(
                "emotion_spirit: 迁移完成但 _current_persona 是占位符 %r,"
                "labels 暂用 ISTJ 默认值 (mbti=%s),"
                "persona_initialized 留 False,等待 /setup_init 或 /setup_switch",
                self._current_persona, labels.get("mbti"),
            )
            self._labels = labels
            self._persona_initialized = False
            return
        self._store.set("persona", {
            "initialized": True,
            "persona_id": self._current_persona,
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
            from emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
            from emotion_spirit.regulation.superego_guard import SuperegoGuard
            self._alignment = ValueAlignment(self._current_persona)
            self._value_resistance = ValueResistance(self._current_persona)
            self._ideal = IdealSelf(self._current_persona, self._labels)
            self._superego_guard = SuperegoGuard(
                self._conscience, self._alignment, self._ideal, self._current_persona,
            )

        # 注册 Web API 端点 (migration re-run)
        self._setup_web_apis()

        asyncio.get_running_loop().call_later(2.0, self._connect_engine_sync)
        asyncio.get_running_loop().call_later(3.0, lambda: asyncio.ensure_future(self._verify_llm_chain()))

        # v1.1.0A: 2am 日程生成定时器
        asyncio.ensure_future(self._schedule_plan_generation_loop())

        logger.info(
            "emotion_spirit initialized: mode=%s persona=%s buffer=%d warm=%d cold=%d ghosts=%d",
            self._persona_mode, self._current_persona,
            len(self._pool.buffer), len(self._pool.warm),
            len(self._pool.cold), len(self._pool.ghosts),
        )

    async def _schedule_plan_generation_loop(self) -> None:
        """每天 2am 生成第二天的日程计划。"""
        from emotion_spirit.core.config import LIFE_SIM_V2_CONFIG
        import datetime

        while True:
            try:
                now = datetime.datetime.now()
                target_hour = LIFE_SIM_V2_CONFIG.get("plan_generate_hour", 2)
                # 计算下一个 2am 的时间
                target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += datetime.timedelta(days=1)
                wait_seconds = (target - now).total_seconds()
                logger.info("emotion_spirit: 日程生成定时器，下次触发 %s (%.0f 秒后)", target, wait_seconds)
                await asyncio.sleep(wait_seconds)

                # 检查今天是否已经生成过
                today_str = datetime.date.today().isoformat()
                if self._last_plan_date == today_str:
                    logger.info("emotion_spirit: 今天已生成日程，跳过")
                    continue

                # 生成日程
                personality = self._get_current_personality_dict()
                recent_memories = self._get_recent_memory_texts(limit=5)
                yesterday_events = self._get_yesterday_events()

                plan = await self._life_sim_v2.generate_daily_plan(
                    personality=personality,
                    recent_memories=recent_memories,
                    yesterday_events=yesterday_events,
                )
                self._last_plan_date = today_str
                logger.info(
                    "emotion_spirit: 日程已生成 %s, %d 个事件",
                    plan.date, len(plan.events),
                )

                # v1.1.0B: 深度睡眠梦境生成
                if hasattr(self, '_dream_generator') and self._dream_generator._llm:
                    try:
                        sleep_hours = 6.0  # 默认 6 小时睡眠
                        rounds = self._dream_generator.compute_dream_rounds(sleep_hours, personality)
                        dream_seed = plan.dream_seed or ""
                        recent_events = [e.activity for e in plan.events if e.status == "done"]
                        dream = await self._dream_generator.generate_deep_sleep_dream(
                            personality=personality,
                            dream_seed=dream_seed,
                            recent_events=recent_events,
                        )
                        if dream:
                            # 梦境写入 MemoryPool
                            self._pool.add(
                                text=f"[梦境] {dream[:200]}",
                                raw_weight=0.4,
                                phi=0.2,
                                tags=["dream", "deep_sleep"],
                                source_user="dream_generator",
                            )
                            logger.info("emotion_spirit: 深度睡眠梦境已生成 (%d 轮)", rounds)
                    except Exception:
                        logger.debug("emotion_spirit: 深度睡眠梦境生成失败", exc_info=True)

                self._save_if_dirty()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("emotion_spirit: 日程生成失败", exc_info=True)
                await asyncio.sleep(60)  # 失败后等 1 分钟重试

    def _get_current_personality_dict(self) -> dict[str, float]:
        """获取当前人格参数 dict。"""
        try:
            from emotion_spirit.memory.persona_profiles import get_personality_params
            return get_personality_params(self._labels)
        except Exception:
            return {"openness": 0.5, "extraversion": 0.5, "agreeableness": 0.5,
                    "neuroticism": 0.5, "conscientiousness": 0.5}

    def _get_recent_memory_texts(self, limit: int = 5) -> list[str]:
        """从 MemoryPool 取最近的记忆文本。"""
        try:
            entries = sorted(
                self._pool.warm + self._pool.cold,
                key=lambda e: e.created_at, reverse=True,
            )
            return [e.text[:100] for e in entries[:limit]]
        except Exception:
            return []

    def _get_yesterday_events(self) -> list[str]:
        """取昨天的生活事件。"""
        try:
            import datetime
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            events = []
            for entry in self._pool.buffer + self._pool.warm:
                if "life_event" in entry.tags:
                    entry_date = datetime.date.fromtimestamp(entry.created_at)
                    if entry_date == yesterday:
                        events.append(entry.text[:100])
            return events[:3]
        except Exception:
            return []

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
        """尝试连接 SylannEngine（使用 shared() 共享实例模式）。"""
        try:
            llm = self._get_llm_callable()
            if llm is None:
                self._retry_count = getattr(self, '_retry_count', 0) + 1
                if self._retry_count < 3:
                    logger.info("emotion_spirit: LLM provider 不可用, %d 秒后重试...", 5 * self._retry_count)
                    asyncio.get_running_loop().call_later(5.0 * self._retry_count, self._connect_engine_sync)
                else:
                    logger.warning("emotion_spirit: LLM provider 不可用, SylannEngine 降级")
                    self._engine = None
                return

            # 使用 SylanneEngine.shared() 获取或创建共享实例
            asyncio.ensure_future(self._start_engine_shared(llm))

        except (ImportError, RuntimeError) as e:
            logger.warning("emotion_spirit: SylannEngine 初始化失败 (%s)", e)
            self._engine = None

    async def _start_engine_shared(self, llm) -> None:
        """通过 SylanneEngine.shared() 获取共享引擎并注册监听器。"""
        try:
            from emotion_spirit.sylanne import SylanneEngine, SylanneConfig

            data_dir = str(Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit" / "sylanne_sessions")
            config = SylanneConfig(mode="lite")
            engine = await SylanneEngine.shared(data_dir=data_dir, llm=llm, config=config)

            self._engine = engine
            self._engine.on(self._on_surface)
            # 接通 bridge 层
            self._engine_manager.start()
            logger.info("emotion_spirit: SylannEngine 共享实例就绪, 监听器已注册")
        except Exception as e:
            logger.warning("emotion_spirit: SylannEngine.shared() 失败 (%s)", e)
            self._engine = None

    async def terminate(self) -> None:
        if self._engine is not None:
            try:
                self._engine.off(self._on_surface)
            except Exception:
                pass
            # 释放共享实例（flush 落盘 + 关闭）
            try:
                from emotion_spirit.sylanne import SylanneEngine
                data_dir = str(Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit" / "sylanne_sessions")
                await SylanneEngine.release_shared(data_dir)
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

        # RhythmLearner: 观察用户消息节奏
        if hasattr(self, '_rhythm_learner') and self._rhythm_learner:
            try:
                import time as _time
                intimacy = self._intimacy.get_intimacy(user_id, self._current_persona)
                self._rhythm_learner.observe_user_message(user_id, text, _time.time(), intimacy)
            except Exception:
                pass

        # v1.1.0B: 睡眠剥夺梦境检查 (概率触发)
        if hasattr(self, '_dream_generator'):
            try:
                personality = self._get_current_personality_dict()
                chance = self._dream_generator.compute_sleep_deprivation_chance(
                    personality=personality,
                    temperature=self._pool.mean_temperature(),
                    cascade_active=self._pool.cascade_active(),
                )
                import random as _random
                if _random.random() < chance:
                    dream = self._dream_generator.generate_sleep_deprivation_dream(personality)
                    if dream:
                        self._pool.add(
                            text=f"[梦境] {dream[:200]}",
                            raw_weight=0.3,
                            phi=0.15,
                            tags=["dream", "sleep_deprived"],
                            source_user="dream_generator",
                        )
                        logger.info("emotion_spirit: 睡眠剥夺梦境: %s", dream[:50])
            except Exception:
                logger.debug("emotion_spirit: 睡眠剥夺梦境检查失败", exc_info=True)

        self._last_texts[user_id] = text
        if len(self._last_texts) > 100:
            oldest = list(self._last_texts.keys())[:50]
            for k in oldest:
                del self._last_texts[k]

        # 通过 EngineManager 处理 (优雅降级: 无引擎时返回 None)
        surface = await self._engine_manager.process_async(
            event.unified_msg_origin, text,
        )
        if surface is not None:
            self._consume_surface(user_id, surface)

        # v1.1.0B: Run agent PRE cycle
        signals = self._latest_signals.get(user_id)

        # v1.1.0C: compute suppression_level from SuppressionState
        suppression_level = 0.0
        suppression_mod = self._modules.get("suppression")
        if suppression_mod is not None:
            try:
                personality = self._consumer.consume({}).personality_deep or {}
                suppression_level = suppression_mod.compute(
                    personality=personality,
                    context={},
                    conscience_pressure=0.0,
                    relationship_intimacy=self._intimacy.get_intimacy(
                        user_id, self._current_persona,
                    ),
                )
            except Exception:
                suppression_level = 0.0

        surface_with_phase = {
            "_phase": "pre",
            "intimacy_gravity": self._intimacy.get_intimacy(user_id, self._current_persona),
            "user_text": text,
            "safety_level": self._safety_level,
            "emotion_delta": getattr(signals, 'emotion_velocity', 0.0) if signals else 0.0,
            "cascade_active": self._pool.cascade_active(),
            "boundary_pressure": 0.0,
            "has_interaction": True,
            "user_id": user_id,
            "collapse_archetype": self._pool._collapse_archetype,
            "suppression_level": suppression_level,
        }
        composed = await self._self_core.run_cycle(user_id, surface_with_phase, "pre")

        await self._flush_inject_queue()

        # v2 (LifeSimulatorV2) handles plan injection in build_schedule_context()

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
        # v1.1.0A: 日程注入 (LifeSimulatorV2 handles plan injection)
        if hasattr(self, '_life_sim_v2') and self._life_sim_v2._current_plan:
            schedule_ctx = self._life_sim_v2.build_schedule_context()
            if schedule_ctx:
                context = f"[今日日程] {schedule_ctx}\n\n{context}" if context else f"[今日日程] {schedule_ctx}"

        # v1.1.0B: Agent PRE cycle 结果注入
        if composed:
            agent_parts = []
            if composed.flags:
                agent_parts.append(f"信号: {','.join(composed.flags)}")
            if composed.carried:
                for source, payload in composed.carried.items():
                    if source == "memory" and "recalled_memories" in payload:
                        memories = "; ".join(payload["recalled_memories"][:3])
                        agent_parts.append(f"相关记忆: {memories}")
                    elif source == "relationship" and "segment" in payload:
                        agent_parts.append(f"关系: {payload.get('segment', '')}")
                    elif source == "life" and "plan_adaptations" in payload:
                        adaptations = payload["plan_adaptations"]
                        if adaptations:
                            agent_parts.append(f"日程调整: {len(adaptations)} 项")
            if agent_parts:
                agent_ctx = "[内部状态] " + " | ".join(agent_parts)
                context = f"{agent_ctx}\n\n{context}" if context else agent_ctx

        if context:
            logger.debug(
                "emotion_spirit inject: user=%s context_len=%d", user_id[:8], len(context),
            )
            if req.system_prompt:
                req.system_prompt = f"{context}\n\n{req.system_prompt}"
            else:
                req.system_prompt = context

    # ═══ LLM 回复处理 ═══

    @filter.on_llm_response(desc="处理 LLM 回复，更新记忆和亲密度")
    async def on_llm_response(self, event: AstrMessageEvent, response: Any) -> None:
        """Bot 回复后: 写入 MemoryPool + 更新 IntimacyTracker。"""
        try:
            bot_text = getattr(response, "completion_text", "") or ""
            if not bot_text:
                return

            user_id = event.get_sender_id()

            # 1. 规则提取情绪
            tone, weight = self._extract_bot_emotion(bot_text)

            # 2. 写入 MemoryPool (source_user="bot", tags=["bot_reply", tone])
            self._pool.add_for_user(
                user_id=user_id,
                text=bot_text[:500],  # 截断避免过长
                raw_weight=weight,
                phi=0.4,  # bot 回复 phi 中等
                tags=["bot_reply", tone],
                source_user="bot",
            )

            # 3. 更新 IntimacyTracker (interaction_freq)
            self._intimacy.update(
                user_id,
                interval_seconds=0,  # bot 回复不改变间隔
                vulnerability_delta=0.05 if tone == "warm" else 0.0,
            )

            # v1.1.0B: Compute behavior signal and learn
            import time as _time_mod
            gap = _time_mod.time() - self._last_bot_reply_time.get(user_id, 0.0)
            from emotion_spirit.memory.reflex_learner import compute_behavior
            behavior = compute_behavior(gap)
            self._reflex_learner.learn(behavior)
            self._last_bot_reply_time[user_id] = _time_mod.time()

            logger.debug(
                "emotion_spirit on_llm_response: user=%s tone=%s weight=%.2f len=%d",
                user_id[:8], tone, weight, len(bot_text),
            )
        except Exception:
            logger.debug("emotion_spirit: on_llm_response error", exc_info=True)

    @staticmethod
    def _extract_bot_emotion(text: str) -> tuple[str, float]:
        """从 bot 回复文本规则提取情绪标签和权重。

        Returns:
            (tone, weight) 元组。
        """
        text_lower = text.lower()

        # 温暖类
        warm_words = ["哈哈", "笑", "开心", "高兴", "❤", "🥰", "😊", "喜欢", "棒", "好的呀"]
        if any(w in text_lower for w in warm_words):
            return "warm", 0.5

        # 抱歉类
        apologetic_words = ["抱歉", "不好意思", "对不起", "sorry", "遗憾"]
        if any(w in text_lower for w in apologetic_words):
            return "apologetic", 0.3

        # 好奇类
        if "？" in text or "?" in text:
            return "curious", 0.3

        # 详细回复
        if len(text) > 200:
            return "detailed", 0.5

        return "neutral", 0.3

    async def _flush_inject_queue(self) -> None:
        if not self._inject_queue:
            return
        while self._inject_queue:
            session_id, influence_type, intensity, target = self._inject_queue.pop(0)
            try:
                # 通过 EngineManager 注入 (同时转发到 HotPoolForwarder → MemoryPool)
                self._engine_manager.inject(
                    session_id=session_id,
                    source="emotion_spirit",
                    signal_type=influence_type,
                    intensity=intensity,
                )
            except Exception:
                logger.warning("emotion_spirit: engine.inject 失败", exc_info=True)

    # ═══ 12 个 ns 命令 (Phase 4 post-merge ns 化) ═══
    # 通过 _ns_command 工厂统一生成, 直接暴露 3 个 namespace:
    # - setup_* (4): 人格配置 (init / relabel / switch / list)
    # - view_* (3): 状态查看 (status / detail / whoami)
    # - reflect_* (5): 内省 (drift / sentinel / shadows / diary / patterns)
    # v1.x 旧 /spirit_* 入口已删 (v1 无外部用户, spec §1.3).

    setup_init_cmd = _ns_command("setup_init", "setup_init", "初始化当前人格参数。仅 auto 模式需要手动调用。")
    setup_relabel_cmd = _ns_command("setup_relabel", "setup_relabel", "两阶段调整人格标签。")
    setup_switch_cmd = _ns_command("setup_switch", "setup_switch", "切换到指定人格。")
    setup_list_cmd = _ns_command("setup_list", "setup_list", "列出所有可用人格。")
    view_status_cmd = _ns_command("view_status", "view_status", "查看 emotion_spirit 状态。")
    view_detail_cmd = _ns_command("view_detail", "view_detail", "查看人格的完整 13 维参数。")
    view_whoami_cmd = _ns_command("view_whoami", "view_whoami", "查看当前人格标签 (5 轴标签概览)。")
    view_memory_cmd = _ns_command("view_memory", "view_memory", "显示当前用户记忆池条目摘要。")
    view_force_cmd = _ns_command("view_force", "view_force", "三元力学状态 + 13 维→力映射。")
    view_schedule_cmd = _ns_command("view_schedule", "view_schedule", "查看今天的日程计划。")
    reflect_drift_cmd = _ns_command("reflect_drift", "reflect_drift", "查看人格漂移状态。")
    reflect_sentinel_cmd = _ns_command("reflect_sentinel", "reflect_sentinel", "查看预警状态。")
    reflect_shadows_cmd = _ns_command("reflect_shadows", "reflect_shadows", "查看阴影检测。")
    reflect_diary_cmd = _ns_command("reflect_diary", "reflect_diary", "手动生成日记。")
    reflect_patterns_cmd = _ns_command("reflect_patterns", "reflect_patterns", "查看行为模式。")

    # ═══ 内部方法: 持久化 ═══

    def _load_persistent_data(self) -> None:
        from emotion_spirit.memory.memory_pool import MemoryPool
        from emotion_spirit.output.buffer_signals import BufferSignals
        from emotion_spirit.regulation.pattern_extractor import PatternExtractor
        from emotion_spirit.regulation.shadow_detector import ShadowDetector
        from emotion_spirit.regulation.life_simulator import LifeSimulator
        from emotion_spirit.output.diary_writer import DiaryWriter
        from emotion_spirit.regulation.personality_drift import PersonalityDrift
        from emotion_spirit.output.predictive_sentinel import PredictiveSentinel
        from emotion_spirit.output.narrative_identity import NarrativeIdentity
        from emotion_spirit.regulation.counterfactual import Counterfactual
        from emotion_spirit.output.prompt_injector import PromptInjector

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
            self._life_sim.configure(llm_caller=self._get_llm_callable())
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
        # v1.1.0A: LifeSimulator v2 恢复
        life_sim_v2_data = self._store.get("life_sim_v2")
        if life_sim_v2_data and hasattr(self, '_life_sim_v2'):
            self._life_sim_v2.from_dict(life_sim_v2_data)
        saved_plan_date = self._store.get("last_plan_date")
        if saved_plan_date:
            self._last_plan_date = saved_plan_date

        # v1.1.0B: ReflexLearner + DreamGenerator 恢复
        reflex_data = self._store.get("reflex_deltas")
        if reflex_data:
            self._reflex_store.from_dict(reflex_data)
        dream_data = self._store.get("dream_state")
        if dream_data:
            self._dream_generator.from_dict(dream_data)
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
        # v1.1.0A: LifeSimulator v2 (adapt_plan 会修改 plan 状态)
        if hasattr(self, '_life_sim_v2'):
            self._store.set("life_sim_v2", self._life_sim_v2.to_dict())
            self._store.set("last_plan_date", self._last_plan_date)
        # v1.1.0B: ReflexLearner + DreamGenerator
        if hasattr(self, '_reflex_store'):
            self._store.set("reflex_deltas", self._reflex_store.to_dict())
        if hasattr(self, '_dream_generator'):
            self._store.set("dream_state", self._dream_generator.to_dict())
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
        # v1.1.0A: LifeSimulator v2 持久化
        self._store.set("life_sim_v2", self._life_sim_v2.to_dict())
        self._store.set("last_plan_date", self._last_plan_date)
        # v1.1.0B: ReflexLearner + DreamGenerator persistence
        if hasattr(self, '_reflex_store'):
            self._store.set("reflex_deltas", self._reflex_store.to_dict())
        if hasattr(self, '_dream_generator') and hasattr(self._dream_generator, 'to_dict'):
            self._store.set("dream_state", self._dream_generator.to_dict())

    # ═══ 公开 API (v1.1.1 + v1.2 扩展) — 保持向后兼容结构 ═══
    # 注: PublicAPI 网关提供 flat 结构 (B6.10), 这里保留 nested "pad"/"distribution" 结构
    # 因为现有集成测试 (test_emotion_integration.py) 期望 nested 结构。

    async def get_emotion_state(
        self, session_key: str, include_trajectory: bool = False,
    ) -> dict | None:
        """统一情绪状态 API (v1.1.1 9 字段 + v1.2 +ambiguity +velocity = 11 字段)。"""
        from emotion_spirit.output.emotion_classifier import render_description

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
    from emotion_spirit.core.plugin_factory import default_config
    persona_id = (config or {}).get("auto_source", "") or ""
    return default_config(data_dir=data_dir, persona_id=persona_id, labels={})
