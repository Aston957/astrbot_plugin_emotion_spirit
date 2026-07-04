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
import inspect
import json
import time
from datetime import date, datetime, timezone, timedelta  # Bug 13 注意: datetime 是类, 不是模块. 用 date.today() / date.fromtimestamp(), 不要写 datetime.date.X
from pathlib import Path
from typing import Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# persona_id 的 sentinel(占位符)值集合 — 表示"还没真正选过人格"
# 出现这些值时,_load_persona_state 视为"未初始化",让 /setup_init 走正常路径
_SENTINEL_PERSONA_IDS = frozenset({"default", "unknown", ""})

# Bug-F (v1.2.11 → v1.3.0 rc.3): bot ephemeral state 判定 token 列表.
# bot "我刚到/我准备出门" 等短期 state → 标 memory_type=bot_ephemeral_state (仍入 pool 记录,
# 但召回时过滤, 不注入 system_prompt). 旧法 token filter "不入 pool" 治标不治本 (v1.3.0 改标类型).
# 判定: bot_text[:200] 含任一 token → 判定为 ephemeral.
_EPHEMERAL_BOT_TOKENS = frozenset({
    "我刚", "我到", "我准备", "我马上", "我现在", "我这就",
    "我正", "我去", "我出门", "我回来", "我走", "我出发",
    "等会儿", "马上", "待会", "稍等", "一会儿",
})

from emotion_spirit.core.plugin_factory import build as build_modules
from emotion_spirit.output.command_router import CommandRouter
from emotion_spirit.output.public_api import PublicAPI
from emotion_spirit.output.commands import CommandImpl
from emotion_spirit.output.surface_handler import SurfaceHandler

# parse_persona_report: 在 _setup_persona_state() 用 (line 507)
from emotion_spirit.utils import parse_persona_report, extract_bot_emotion, build_context
# 注意: save_report/load_report 不在 main.py 导入 — commands.py 内部直接
#       from emotion_spirit.regulation.persona_analyzer import save_report (line 41, 241)


def _ns_command(name: str, cmd_attr: str, desc: str = ""):
    """把 CommandImpl.{cmd_attr} 方法注册为 AstrBot /{name} 命令 (Phase 4 post-merge ns 化).

    用法 (类体中):
        setup_init_cmd = _ns_command("setup_init", "setup_init", "初始化当前人格参数...")

    Args:
        name: AstrBot 命令名 (e.g. "setup_init", "view_status", "reflect_drift")
        cmd_attr: self._cmd 上对应的方法名 (CommandImpl 类)
        desc: 命令描述,显示在 /help 列表和 dashboard 命令面板

    Note (v4.26.1 兼容性):
    - 必须加 *args 接收 CommandFilter 注入的位置参数 (v4.26.1 validate 后通过 _orig_args 注入)
    - 给每个 handler 唯一 __name__,避免 12 个 CommandFilter 共享同一个 _handler
      导致 cmd_attr 闭包永远是第一个命令
    """
    async def _ns_handler(self, event: AstrMessageEvent, *args, **kwargs):
        handler = getattr(self._cmd, cmd_attr)
        # v4.26.1: CommandFilter 通过 *args 传参; 兜底兼容旧版 parsed_params
        if args:
            args_tuple = args
        else:
            parsed = event.get_extra("parsed_params") or {}
            first_arg = parsed.get("args")
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
    # Patch A (v1.2.11): 覆盖 __signature__ 为 (self, event), 屏蔽 *args/**kwargs.
    # AstrBot 4.26.x CommandFilter.init_handler_md 用 inspect.signature 解析 handler,
    # 把 *args/**kwargs 误识别成必填命名参数 → 18 命令全 404 (不带参数 "必要参数缺失",
    # 带参数 TypeError: _empty() takes no arguments).
    # 覆盖后框架只看到 (self, event); _ns_handler 运行时仍从 *args 接 CommandFilter
    # 传参 (函数定义不变, test_ns_handler_accepts_varargs 守护). AstrBot 修了之后本覆盖是 no-op.
    # 用户反馈: 2026-07-04-emotion-spirit-v1210-feedback.md §3.
    _ns_handler.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("event", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ]
    )
    return filter.command(name, desc=desc)(_ns_handler)


class EmotionSpiritPlugin(Star):
    """emotion_spirit — 自我层 + 超我反思层。"""

    def __init__(self, context: Context, config: dict[str, Any] | None = None) -> None:
        super().__init__(context)
        self._config = config or {}
        self._engine: Any = None

        # 数据目录 (v1.2.4: 缓存为实例属性, 消除重复 Path 构建)
        _base = Path(get_astrbot_data_path())
        self._data_dir = _base / "plugin_data" / "emotion_spirit"
        self._astrbot_db = _base / "data_v4.db"

        # 跑 config migration (必须在 build_modules 之前, 否则老 config 升级后
        # build_modules 用的是旧 schema 字段, 整个 plugin 用错配置跑)
        self._config = self._run_config_migration_and_reload(self._config)

        data_dir = self._data_dir

        # ═══ 1. plugin_factory.build() 装配 28 模块 (走 L2 工厂) ═══
        # 必须先于 _setup_persona_state, 因为后者的 labels 传给 factory
        self._modules = build_modules(
            build_modules_default_config(str(data_dir), self._config)
        )

        # ═══ 2. 公开 API 网关 ═══
        # Bug-C (v1.2.10): PublicAPI 是 facade (吃整个 modules dict),
        # 不走 @register — factory 只注入单个 dep, 无路径传整个 instances dict
        # (v1.2.5 PR3 T3 漏加 @register → KeyError). 手 new, 同
        # CommandImpl/SurfaceHandler/LifeAgent 第 4 处 (v1.3 factory param_wire 扩展).
        self._public_api = PublicAPI(self._modules)

        # ═══ 3. persona 状态 (在 setup_persona_state 中用 _modules 初始化) ═══
        self._setup_persona_state()

        # ═══ 4. 命令路由器 (3 ns) — v1.2.1 DI 接线, factory 自动 wire (无依赖)
        self._router = self._modules["command_router"]
        # CommandImpl 需 plugin 自身引用, 暂留手 new — 见 UPDATE_HANDBOOK §6 清债清单
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
        # Bug-B (v1.2.10): superego reflection 队列 (sync consume 推, async worker 消费).
        self._diary_reflection_queue: list[tuple[str, list[str], str]] = []  # (tension, conflict_values, user_id)
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
        data_dir = self._data_dir

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
            data_dir = self._data_dir
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
        self._init_persona_config()
        self._init_feature_toggles()
        self._init_modules_phase1()
        self._init_social_and_mechanics()
        self._init_life_and_agents()
        self._init_logging_and_cache()

    def _init_persona_config(self) -> None:
        """Persona 配置 + 模式 (L222-250)。"""
        from emotion_spirit.regulation.persona_analyzer import PersonaAnalysisResult

        self._store = self._modules["store"]
        self._persona_mode = self._config.get("persona_mode", "disabled")
        self._current_persona = (
            self._config.get("auto_source", "") or self._detect_default_persona()
        )
        self._parsed_drives: dict[str, float] = {}
        self._labels: dict[str, str] = {}
        self._auto_report: PersonaAnalysisResult | None = None
        self._persona_initialized: bool = False
        self._relabel_pending: bool = False

        if self._persona_mode == "auto":
            if not self._current_persona:
                self._current_persona = self._detect_default_persona()
            logger.info("emotion_spirit: auto 模式, 人格 '%s' 待初始化", self._current_persona)
        elif self._persona_mode == "disabled":
            self._labels = self._get_default_labels()
            logger.info("emotion_spirit: disabled 模式, 使用 Sylanne 默认行为")
        else:
            self._persona_mode = "disabled"
            self._labels = self._get_default_labels()
            logger.info("emotion_spirit: 未知模式, 回退到 disabled")
        self._update_baseline()

    def _init_feature_toggles(self) -> None:
        """功能开关 (L253-266)。"""
        toggles = self._config.get("feature_toggles", {})
        self._enable_shadow = toggles.get("enable_shadow_detector", True)
        self._enable_sentinel = toggles.get("enable_sentinel", True)
        self._enable_narrative = toggles.get("enable_narrative", True)
        self._enable_surface_logging = toggles.get("enable_surface_logging", False)
        life_sim_cfg = self._config.get("life_simulator", {})
        proactive_cfg = self._config.get("proactive_chat", {})
        self._enable_life_fragment = life_sim_cfg.get("enable_life_fragment", True)
        self._enable_proactive_prompt = proactive_cfg.get("enable_proactive_prompt", True)
        self._enable_life = self._enable_life_fragment or self._enable_proactive_prompt

    def _init_modules_phase1(self) -> None:
        """Phase 1 核心组件 (L268-291)。"""
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

    def _init_social_and_mechanics(self) -> None:
        """社交 + 三元力学 + Bridge (L293-313)。"""
        self._social_graph = self._modules["social_graph"]
        self._topic_privacy = self._modules["topic_privacy"]
        self._decision = self._modules["bot_decision"]
        self._force_dynamics = self._modules.get("force_dynamics")
        self._body_state = self._modules.get("body_state")
        self._engine_manager = self._modules["engine_manager"]
        self._hotpool_forwarder = self._modules["hotpool_forwarder"]
        self._personality_bridge = self._modules["personality_bridge"]
        self._engine_manager.set_forwarder(self._hotpool_forwarder)
        self._decision.configure_proactive_deps(memory_pool=self._pool, life_simulator=self._life_sim)

    def _init_life_and_agents(self) -> None:
        """LifeSim + Agent + Reflex + Dream (L315-357)。"""
        if self._life_sim is not None:
            self._life_sim.configure(llm_caller=self._get_llm_callable("life_sim"))

        self._life_sim_v2 = self._modules["life_simulator_v2"]
        self._life_sim_v2._use_llm_polish = self._config.get("life_sim_v2", {}).get("use_llm_polish", False)
        self._life_sim_v2.configure(llm_caller=self._get_llm_callable("life_sim"))
        self._last_plan_date: str = ""

        self._realtime_dispatch = self._modules["realtime_dispatch"]
        self._rhythm_learner = self._modules["rhythm_learner"]
        self._segmented_coordinator = self._modules["segmented_reply_coordinator"]
        # v1.2.5 PR2 §4: 压抑/崩溃/沉默 三防御子系统与力学的耦合调制器
        # L1: compute_defense_states 统一三子读 force_state
        # L2: apply_event 防御事件触发后回写 force_state
        self._defense_modulator = self._modules["defense_modulator"]
        # v1.2.7: 分段回复编排器 (从 _on_segmented_reply_v2 抽出, §1.2 规则 3)
        self._segmented_orchestrator = self._modules["segmented_reply_orchestrator"]

        from emotion_spirit.agents.memory_agent import MemoryAgent
        from emotion_spirit.agents.personality_agent import PersonalityAgent
        from emotion_spirit.agents.relationship_agent import RelationshipAgent

        self._self_core = self._modules["self_core"]
        self._self_core.register(MemoryAgent(self._pool, self._shadow))
        self._self_core.register(PersonalityAgent(self._superego_guard, self._drift))
        self._self_core.register(RelationshipAgent(self._intimacy, self._social_graph))
        self._setup_v110c_agents()
        self._last_bot_reply_time: dict[str, float] = {}

        self._reflex_store = self._modules["reflex_learner_store"]
        self._reflex_learner = self._modules["reflex_learner"]
        self._self_core.set_store(self._reflex_store)
        self._dream_generator = self._modules["dream_generator"]
        self._dream_generator.configure(llm_caller=self._get_llm_callable("dream"))

        self._relationship_personality = self._modules["relationship_personality"]

    def _init_logging_and_cache(self) -> None:
        """Surface 日志 + 人格缓存 (L359-375)。"""
        self._surface_logger: Any = None
        if self._enable_surface_logging:
            try:
                from verification.surface_logger import SurfaceLogger as _SL
                log_dir = self._data_dir / "surface_logs"
                self._surface_logger = _SL(output_dir=str(log_dir), anonymize=True, max_age_days=7)
                logger.info("emotion_spirit: Surface 日志已启用 → %s", log_dir)
            except Exception:
                logger.warning("emotion_spirit: Surface 日志初始化失败", exc_info=True)
        self._personas_cache = self._scan_all_personas()

    # ── v1.1.0C helpers ────────────────────────────────────────────────────

    def _setup_v110c_agents(self) -> None:
        """Register v1.1.0C agents on SelfCore.

        Currently adds LifeAgent. Called once from __init__ after
        ``self._self_core`` and ``self._life_sim_v2`` are both ready.

        v1.1.0C Tech-Debt Cleanup (Item 3): extracted from the monolithic
        __init__ to keep the lifecycle steps clearly named.
        v1.2.1: LifeAgent 仍手 new — 依赖 self_core.bus (EventBus), factory param_wire
        无法表达 "self_core.bus", 同 MemoryAgent/PersonalityAgent/RelationshipAgent 一起手 new。
        """
        from emotion_spirit.agents.life_agent import LifeAgent

        self._life_agent = LifeAgent(self._life_sim_v2)
        self._self_core.register(self._life_agent)

    def _get_v110c_adaptation_context(self, user_id: str) -> dict[str, Any]:
        """Build the v1.1.0C adaptation context for ``on_llm_request``.

        Returns a dict with two keys:
          - ``suppression_level`` (float in [0, 1])
          - ``collapse_archetype`` (str | None)

        Extracted from the inline logic in on_llm_request so the surface
        construction in main.py stays readable. Failures degrade silently
        to neutral defaults — the rest of the pipeline is never blocked
        by a v1.1.0C bookkeeping call.
        """
        suppression_level = 0.0
        collapse_archetype = getattr(self._pool, "_collapse_archetype", None)

        try:
            sup_mod = self._modules.get("suppression")
            signals = self._latest_signals.get(user_id)
            if sup_mod and signals:
                ctx = {
                    "authority_present": 0,
                    "social_audience": 0,
                }
                suppression_level = sup_mod.compute(
                    personality=self._baseline_personality.get("deep", {}),
                    context=ctx,
                    conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0,
                    relationship_intimacy=self._intimacy.get_intimacy(
                        user_id, self._current_persona,
                    ),
                )
        except Exception:
            logger.warning(
                "emotion_spirit: v1.1.0C adaptation context failed",
                exc_info=True,
            )

        return {
            "suppression_level": suppression_level,
            "collapse_archetype": collapse_archetype,
        }

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
        reflect.command("force_current", help_text="力平衡 + 沉默/分段历史")(self._cmd.reflect_force_current)

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
        from emotion_spirit.utils import get_personality_params
        self._baseline_personality = get_personality_params(self._labels)
        self._interaction_count = 0
        logger.info("emotion_spirit: baseline personality updated from labels")

        # v1.3.0 rc.2 §1.7: ConscienceTracker 轴心耦合 — 从 13维 personality 算衰减率/阈值/倍率
        # labels 变 → personality 变 → 轴心参数变. 防止 _conscience 用默认参数.
        if hasattr(self, "_conscience") and self._conscience is not None:
            # rc.4: 传全 13 维 (deep 5 + surface 8), 不是只传 deep.
            # KB conscience_params.json weights 引用 9 维 (3 deep + 6 surface),
            # 只传 deep 会让 surface 维度取 0.5 兜底 → 参数没人格化 (Bug-G rc.3 仍饱和根因).
            deep = self._baseline_personality.get("deep", {})
            surface = self._baseline_personality.get("surface", {})
            full_personality = {**deep, **surface}  # 13 维
            if full_personality:
                self._conscience.set_personality(full_personality)
                logger.info(
                    "emotion_spirit: conscience set_personality dims=%d acute_decay=%.3f chronic_decay=%.3f threshold=%.3f",
                    len(full_personality),
                    self._conscience._acute_decay_rate_per_min,
                    self._conscience._chronic_decay_rate_per_hour,
                    self._conscience._collapse_threshold,
                )

    @staticmethod
    def _validate_labels(labels: tuple[str, ...]) -> dict[str, str] | None:
        if len(labels) != 5:
            return None
        mbti, attachment, emotion_style, conflict_style, time_focus = labels
        from emotion_spirit.utils import LABEL_OPTIONS
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
            rows = []
            with self._get_persona_db_cursor() as cursor:
                if cursor is not None:
                    cursor.execute("SELECT persona_id, system_prompt FROM personas")
                    rows = cursor.fetchall()
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

    @staticmethod
    def _get_persona_db_cursor():
        """上下文管理器: 打开 AstrBot personas 数据库游标。

        v1.2.3-clean(TD-2): 消除 _read_persona_prompt / _list_available_personas
        等方法的重复 sqlite3.connect / close 代码。
        用法: with self._get_persona_db_cursor() as cursor: ...
        """
        import contextlib
        import sqlite3
        from pathlib import Path

        @contextlib.contextmanager
        def _cursor():
            db_path = Path(get_astrbot_data_path()) / "data_v4.db"
            if not db_path.exists():
                yield None
                return
            conn = sqlite3.connect(str(db_path))
            try:
                yield conn.cursor()
            finally:
                conn.close()
        return _cursor()

    def _read_persona_prompt(self, persona_id: str) -> str | None:
        try:
            with self._get_persona_db_cursor() as cursor:
                if cursor is None:
                    return None
                cursor.execute(
                    "SELECT system_prompt FROM personas WHERE persona_id = ?",
                    (persona_id,),
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception:
            logger.debug("persona_report_parser: 读取数据库失败", exc_info=True)
            return None

    def _list_available_personas(self) -> list[str]:
        """返回 AstrBot 数据库中可用的 persona_id 列表。"""
        try:
            with self._get_persona_db_cursor() as cursor:
                if cursor is None:
                    return []
                cursor.execute("SELECT persona_id FROM personas")
                return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception:
            logger.debug("emotion_spirit: 读取 persona 列表失败", exc_info=True)
            return []

    def _detect_default_persona(self) -> str:
        try:
            config_path = Path(get_astrbot_data_path()) / "cmd_config.json"
            if not config_path.exists():
                return "xiaofu"
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
            default_persona = config.get("provider_settings", {}).get("default_personality", "")
            if default_persona:
                logger.info("emotion_spirit: 从 AstrBot 配置检测到默认人格: %s", default_persona)
                return default_persona
            with self._get_persona_db_cursor() as cursor:
                if cursor is not None:
                    cursor.execute("SELECT persona_id FROM personas LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        logger.info("emotion_spirit: 从数据库检测到人格: %s", row[0])
                        return row[0]
            logger.info("emotion_spirit: 未检测到默认人格，使用 xiaofu")
            return "xiaofu"
        except Exception:
            logger.debug("emotion_spirit: 检测默认人格失败", exc_info=True)
            return "xiaofu"

    # ─── 分级 LLM provider 映射表 ───
    _FEATURE_PROVIDER_MAP: dict[str, tuple[str, str]] = {
        # feature  → (config_section, provider_id_field)
        "engine":   ("sylanne",     "engine_provider_id"),
        "analyzer": ("sylanne",     "analyzer_provider_id"),
        "life_sim": ("life_sim_v2", "life_sim_provider_id"),
        "dream":    ("dream",       "dream_provider_id"),
        "diary":    ("diary",       "diary_provider_id"),
    }

    def _feature_provider_id(self, feature: str) -> str | None:
        """按 feature 名从对应配置段读 provider_id。"""
        mapping = self._FEATURE_PROVIDER_MAP.get(feature)
        if not mapping:
            return None
        section, field = mapping
        return self._config.get(section, {}).get(field) or None

    def _get_llm_callable(self, feature: str | None = None) -> Any:
        """按 feature 取分级 LLM provider；对应 provider_id 空则回退全局。

        feature 取值: "engine" | "life_sim" | "dream" | "analyzer" | "diary" | None

        采用 lazy 解析: 返回的闭包在被 await 时才查 provider。
        这样避开"插件 build_modules 早于 provider 加载"的时序问题 ——
        启动时 provider 还没注册, 立即查会拿到 None; 延迟到实际调用时 provider 已就绪。
        """
        ctxt = self.context
        feature_name = feature

        def _resolve_provider() -> Any:
            provider = None
            if feature_name:
                pid = self._feature_provider_id(feature_name)
                if pid:
                    try:
                        provider = ctxt.get_provider_by_id(pid)
                    except Exception:
                        logger.debug("emotion_spirit: get_provider_by_id(%s) 失败, 回退全局", pid)
                        provider = None
            if not provider:
                provider = ctxt.get_using_provider()
            return provider

        async def _llm(system_prompt: str, user_prompt: str) -> str:
            provider = _resolve_provider()
            if not provider or not hasattr(provider, "text_chat"):
                logger.warning(
                    "emotion_spirit: LLM provider 不可用 (feature=%s, provider=%s)",
                    feature_name,
                    type(provider).__name__ if provider else "None",
                )
                raise RuntimeError(f"LLM provider unavailable for feature={feature_name}")
            resp = await provider.text_chat(
                prompt=user_prompt, system_prompt=system_prompt,
            )
            return resp.completion_text

        return _llm

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
        """加载 persona 状态,处理持久化与 config 的优先级。

        v1.2.11 (Patch B, 用户反馈 §4.3): B5 改 conditional.
        原 v1.2.2-fix(B5): config.auto_source 显式时, 无论 saved 是否已初始化
        都强制 reset (initialized=False + labels={}) 走 LLM 路径. 但 LLM 不可用
        (无 API key / free tier 用尽 / 厂商 outage) 时这条路径死掉, saved labels
        永远读不到, 18 命令全报"无标签数据" (用户手动注入 spirit_data.json 的
        ENFJ labels workaround 也被 B5 清空).

        现行 (v1.2.11): saved 已初始化 → 信任 saved, 跳过 B5 (LLM 可用/不可用都安全).
        saved 未初始化 (sentinel / labels 空) → 走 B5 (config.auto_source 显式 +
        可用 → 触发 LLM). 用户改 config.auto_source 想重新分析 → 发 /setup_init
        (或清 saved 让它重新走 B5).

        语义变更: 原 B5 "config 永远优先 + 强制 LLM" → "saved 优先, config 退化为
        首次引导". LLM 可用场景也不再每次启动重新 LLM (避免重复调用, labels 已落盘).
        """
        persona_data = self._store.get("persona", {})
        if self._is_persona_initialized(persona_data):
            # saved 已初始化 → 信任 saved, 跳过 B5 (LLM 不可用场景的核心修复).
            saved_persona_id = persona_data.get("persona_id", "")
            self._persona_initialized = True
            self._labels = dict(persona_data.get("labels", {}))
            if saved_persona_id:
                self._current_persona = saved_persona_id
            logger.info(
                "emotion_spirit: persona 已恢复 — id=%s labels=%s",
                self._current_persona, list(self._labels.keys()),
            )
            return

        # saved 未初始化 (sentinel / labels 空) → B5: config.auto_source 显式 +
        # 在可用列表 → 触发 LLM 分析 (首次引导).
        config_persona = self._config.get("auto_source", "")
        if config_persona and config_persona not in _SENTINEL_PERSONA_IDS:
            available = self._list_available_personas()
            if config_persona in available:
                logger.info(
                    "emotion_spirit: config.auto_source='%s' (saved 未初始化) "
                    "触发 LLM 分析",
                    config_persona,
                )
                self._current_persona = config_persona
                self._persona_initialized = False
                self._labels = {}
                return
            logger.warning(
                "emotion_spirit: config.auto_source='%s' 不在可用列表 %s,忽略",
                config_persona, available,
            )

        self._persona_initialized = False
        self._labels = {}
        self._migrate_old_spirit_data()

    def _rebuild_superego_subdict(self) -> None:
        """v1.2.5 PR3: 单点重建 _modules["superego"] 子字典 + 同步 self._xxx 引用.

        被 initialize() 和 _reset_superego_modules() 共用, 避免双轨 bug.
        调用前必须保证 self._conscience 已存在 (factory 已装配).
        """
        from emotion_spirit.regulation.superego import (
            ValueAlignment, IdealSelf, ValueResistance,
        )
        from emotion_spirit.regulation.superego_guard import SuperegoGuard

        # 保留现有 conscience 引用 (factory 装配的原对象)
        # initialize() 时 _conscience 已在 _init_modules_phase1 取好
        # _reset_superego_modules() 会重造 conscience, 覆盖 self._conscience 后再调用本方法
        new_alignment = ValueAlignment(self._current_persona)
        new_ideal = IdealSelf(self._current_persona, self._labels)
        new_value_resistance = ValueResistance(self._current_persona)
        new_guard = SuperegoGuard(
            self._conscience, new_alignment, new_ideal, self._current_persona,
        )

        self._modules["superego"] = {
            "conscience": self._conscience,
            "alignment": new_alignment,
            "ideal_self": new_ideal,
            "value_resistance": new_value_resistance,
            "superego_guard": new_guard,
        }

        # 同步更新 self._xxx 引用 (跟 _modules["superego"][...] 同对象)
        self._alignment = new_alignment
        self._ideal = new_ideal
        self._value_resistance = new_value_resistance
        self._superego_guard = new_guard

    def _reset_superego_modules(self) -> None:
        """v1.2.5 PR3 T2: 重置超我层 (走 _modules["superego"] 子字典, 避免双轨).

        修法: 新建 conscience, 重建 _modules["superego"], 同步 self._xxx 引用.
        """
        from emotion_spirit.regulation.superego.conscience import ConscienceTracker

        # 新建 conscience (重置必须重造), 通过 local 变量避免 self._xxx = ClassName() 直赋
        new_conscience = ConscienceTracker()
        # v1.3.0 rc.2 §1.7: 新 conscience 立刻从 baseline personality 算轴心参数, 防止默认参数状态
        if hasattr(self, "_baseline_personality"):
            deep = self._baseline_personality.get("deep", {})
            surface = self._baseline_personality.get("surface", {})
            full_personality = {**deep, **surface}  # rc.4: 13 维
            if full_personality:
                new_conscience.set_personality(full_personality)
        self._conscience = new_conscience

        # 单点重建 superego 子字典, 同步 self._xxx 引用
        self._rebuild_superego_subdict()

        # 清持久化 (保留原行为)
        for key in self._modules["superego"].keys():
            self._store.set(key, None)
        self._store.set("persona_report", None)

        report_path = self._store._dir / "persona_report.json"
        if report_path.exists():
            report_path.unlink()

        self._store.save()
        logger.info("emotion_spirit: 超我层已重置（13 维 baseline 已用新 labels 重推）")

    def _migrate_old_spirit_data(self) -> None:
        """迁移旧数据到新的 persona 持久化格式。

        v1.2.2-fix(B6): 无论是不是 sentinel, 都留 initialized=False,
        让 /setup_init 能真正走 LLM 分析路径, 避免 ISTJ 默认值锁死。
        """
        labels = self._get_default_labels()
        is_sentinel = self._current_persona in _SENTINEL_PERSONA_IDS

        if is_sentinel:
            logger.warning(
                "emotion_spirit: 检测到旧数据且 persona 为占位符 %r,"
                "labels 暂用 ISTJ 默认值 (mbti=%s),"
                "persona_initialized 留 False,等待 /setup_init 或 /setup_switch",
                self._current_persona, labels.get("mbti"),
            )
        else:
            logger.warning(
                "emotion_spirit: 检测到旧数据且 persona='%s',"
                "labels 暂用 ISTJ 默认值,但 initialized 留 False,"
                "请运行 /setup_init 获取真实人格分析",
                self._current_persona,
            )
        # 统一留 False, 强制走 /setup_init LLM 路径
        self._labels = labels
        self._persona_initialized = False

    # ═══ 生命周期 ═══

    async def initialize(self) -> None:
        self._store.load()
        self._load_persistent_data()
        self._load_persona_state()
        if self._persona_initialized:
            self._update_baseline()
            # v1.2.5 PR3 T2 扩展: initialize() 也走 _modules["superego"] 单点重建, 避免双轨
            self._rebuild_superego_subdict()

        # 注册 Web API 端点 (migration re-run)
        self._setup_web_apis()

        asyncio.get_running_loop().call_later(2.0, self._connect_engine_sync)
        asyncio.get_running_loop().call_later(3.0, lambda: asyncio.ensure_future(self._verify_llm_chain()))

        # v1.1.0A: 2am 日程生成定时器
        asyncio.ensure_future(self._schedule_plan_generation_loop())

        # diary 定时生成 (按 diary.schedule_hours)
        asyncio.ensure_future(self._schedule_diary_generation_loop())

        # Bug-B (v1.2.10): superego reflection 队列后台 worker
        asyncio.ensure_future(self._drain_diary_reflection_loop())

        logger.info(
            "emotion_spirit initialized: mode=%s persona=%s buffer=%d warm=%d cold=%d ghosts=%d",
            self._persona_mode, self._current_persona,
            len(self._pool.buffer), len(self._pool.warm),
            len(self._pool.cold), len(self._pool.ghosts),
        )

        # v1.2.3: RhythmLearner 注入 persona 的亲密度门控 + 混合率 (顺手补漏接线)
        if hasattr(self, '_rhythm_learner'):
            seg_cfg = self._config.get("segmented_reply", {})
            intimacy_gate = seg_cfg.get("intimacy_gate", 0.6)
            blend = seg_cfg.get("blend", 0.6)
            self._rhythm_learner.set_personality_params(intimacy_gate, blend)
            logger.debug(
                "emotion_spirit: rhythm_learner 已注入 personality_params "
                "(intimacy_gate=%.2f, blend=%.2f)",
                intimacy_gate, blend,
            )

    async def _schedule_plan_generation_loop(self) -> None:
        """每天 2am 生成第二天的日程计划。"""
        from emotion_spirit.core.config import LIFE_SIM_V2_CONFIG

        while True:
            try:
                now = datetime.now()
                target_hour = LIFE_SIM_V2_CONFIG.get("plan_generate_hour", 2)
                # 计算下一个 2am 的时间
                target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)
                wait_seconds = (target - now).total_seconds()
                logger.info("emotion_spirit: 日程生成定时器，下次触发 %s (%.0f 秒后)", target, wait_seconds)
                await asyncio.sleep(wait_seconds)

                # 检查今天是否已经生成过
                today_str = date.today().isoformat()  # Bug 13 修: datetime.date.today() -> date.today()
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
                    user_activity=(
                        self._latest_user_activity
                        if hasattr(self, '_latest_user_activity') else None
                    ),
                )
                self._last_plan_date = today_str

                # v1.2.9 HP-3: suppression L2 定期回写 (每天 1 次, 慢变量)
                try:
                    defense_states = self._defense_modulator.compute_defense_states(
                        personality=personality,
                        signals=None,  # schedule loop 无实时 signals
                        body_state=self._body_state.default() if hasattr(self, "_body_state") else None,
                        intimacy_level=0.5,  # schedule loop 无特定 user
                        context={},
                        force_state=(
                            self._force_dynamics.force_state_from_labels(self._labels)
                            if hasattr(self, "_force_dynamics") and hasattr(self, "_labels")
                            else None
                        ),
                        conscience_pressure=self._conscience.get_pressure() if hasattr(self, "_conscience") else 0.0,
                    )
                    self._defense_modulator.apply_event("suppression", intensity=defense_states.suppression_level)
                    logger.debug("emotion_spirit: suppression L2 回写 level=%.3f", defense_states.suppression_level)
                except Exception:
                    logger.debug("emotion_spirit: suppression L2 回写失败", exc_info=True)

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

    async def _schedule_diary_generation_loop(self) -> None:
        """按 diary.schedule_hours 定时生成日记（LLM 或 prompt-only）。"""

        while True:
            try:
                diary_cfg = self._config.get("diary", {})
                schedule_str = diary_cfg.get("schedule_hours", "14,22")
                try:
                    target_hours = [int(h.strip()) for h in schedule_str.split(",") if h.strip()]
                except ValueError:
                    target_hours = [14, 22]

                # 找下一个触发时间
                now = datetime.now()
                candidates = []
                for h in target_hours:
                    t = now.replace(hour=h, minute=0, second=0, microsecond=0)
                    if now >= t:
                        t += timedelta(days=1)
                    candidates.append(t)
                next_target = min(candidates)
                wait_seconds = (next_target - now).total_seconds()
                logger.info(
                    "emotion_spirit: 日记定时器，下次触发 %s (%.0f 秒后)",
                    next_target.strftime("%Y-%m-%d %H:%M"), wait_seconds,
                )
                await asyncio.sleep(wait_seconds)

                # 防重复: 同一小时的同一天不重复生成
                today_hour_key = f"{date.today().isoformat()}-{next_target.hour}"
                last_diary_key = getattr(self, "_last_diary_key", "")
                if last_diary_key == today_hour_key:
                    logger.debug("emotion_spirit: 日记 %s 已生成，跳过", today_hour_key)
                    continue

                # 生成日记
                if self._diary is not None:
                    llm_enabled = diary_cfg.get("enable_diary_llm", False)
                    if llm_enabled:
                        text = await self._diary.generate_diary_llm()
                        if text:
                            diary_type = self._diary.determine_diary_type()
                            self._diary.record_diary(text, diary_type)
                            logger.info("emotion_spirit: LLM 日记已生成 (%s, %d 字)", diary_type, len(text))
                        else:
                            logger.warning("emotion_spirit: LLM 日记生成返回空，跳过")
                    else:
                        # Bug-B (v1.2.10): LLM-off 不再存 prompt 模板 (复读机), 跳过.
                        # 0 篇真日记 > 假 prompt. (与 surface_handler reflection 一致.)
                        logger.debug("emotion_spirit: diary LLM 未启用, 跳过定时日记 (v1.2.10 Bug-B)")

                    self._last_diary_key = today_hour_key
                    self._save_if_dirty()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("emotion_spirit: 日记定时生成失败", exc_info=True)
                await asyncio.sleep(120)

    # ── Bug-B (v1.2.10): superego reflection LLM worker ──────────────

    async def _process_one_reflection(self, tension: str, conflict_values: list[str], user_id: str) -> None:
        """Bug-B (v1.2.10): 处理 1 个 superego reflection 队列项 → LLM 生成日记正文."""
        if self._diary is None:
            return
        try:
            prompt = self._diary.build_superego_reflection_prompt(tension, conflict_values)
            text = await self._diary.generate_reflection_llm(prompt)
            if text:
                self._diary.record_diary(text, "superego_reflection", user_id=user_id)
                self._save_if_dirty()
                logger.info(
                    "emotion_spirit: superego reflection LLM 日记已生成 (user=%s, %d 字)",
                    user_id[:8], len(text),
                )
        except Exception:
            logger.warning("emotion_spirit: superego reflection 生成失败", exc_info=True)

    async def _drain_diary_reflection_loop(self) -> None:
        """Bug-B (v1.2.10): 后台消费 superego reflection 队列 (mirror _schedule_diary_generation_loop)."""
        while True:
            try:
                if self._diary_reflection_queue:
                    tension, conflict_values, user_id = self._diary_reflection_queue.pop(0)
                    await self._process_one_reflection(tension, conflict_values, user_id)
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("emotion_spirit: superego reflection drain 异常", exc_info=True)
                await asyncio.sleep(10)

    def _get_current_personality_dict(self) -> dict[str, Any]:
        """获取当前人格参数 dict (可能是嵌套或 flat, 消费方需自行 flatten).

        Bug 14 修 (PR3 T9): 之前 type hint 撒谎说 dict[str, float], 实际 shape
        取决于 persona_profiles.get_personality_params(), 返回嵌套 dict 如
        {"deep": {"expression_drive": 0.15, ...}, "surface": {...}}.
        所有消费方必须先用 _flatten_personality() 拍平或按 layer 访问.
        """
        try:
            from emotion_spirit.utils import get_personality_params
            return get_personality_params(self._labels)
        except Exception:
            # fallback 保持 flat shape (历史兼容性), v1.2.6 再全局统一
            return {"openness": 0.5, "extraversion": 0.5, "agreeableness": 0.5,
                    "neuroticism": 0.5, "conscientiousness": 0.5}

    def get_current_force_state(self, labels: dict[str, str] | None = None):
        """三元力学当前 ForceState (v1.2 接线 + 入日记消费; v1.3 叙事层继续用)。

        Args:
            labels: 5 轴标签 dict。None → 用 self._labels (默认人格)。
        Returns:
            ForceState (3 权重) 或 None (force_dynamics 未装配 / labels 不可用)。
        """
        if getattr(self, "_force_dynamics", None) is None:
            return None
        use = labels if labels is not None else getattr(self, "_labels", None)
        if not use:
            return None
        return self._force_dynamics.force_state_from_labels(use)

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
            yesterday = date.today() - timedelta(days=1)
            events = []
            for entry in self._pool.buffer + self._pool.warm:
                if "life_event" in entry.tags:
                    entry_date = date.fromtimestamp(entry.created_at)  # Bug 13 同类错模式: datetime.date.fromtimestamp -> date.fromtimestamp
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
            # 探测 provider 是否已就绪 (避开 lazy 闭包, 直接查)
            pid = self._feature_provider_id("engine")
            provider = None
            if pid:
                try:
                    provider = self.context.get_provider_by_id(pid)
                except Exception:
                    provider = None
            if not provider:
                provider = self.context.get_using_provider()
            if not provider or not hasattr(provider, "text_chat"):
                self._retry_count = getattr(self, '_retry_count', 0) + 1
                if self._retry_count < 3:
                    logger.info("emotion_spirit: LLM provider 不可用, %d 秒后重试...", 5 * self._retry_count)
                    asyncio.get_running_loop().call_later(5.0 * self._retry_count, self._connect_engine_sync)
                else:
                    logger.warning("emotion_spirit: LLM provider 不可用, SylannEngine 降级")
                    self._engine = None
                return

            # 使用 SylanneEngine.shared() 获取或创建共享实例
            # llm callable 用 lazy 版本 (运行时才解析 provider, 支持 engine 切换)
            llm = self._get_llm_callable("engine")
            asyncio.ensure_future(self._start_engine_shared(llm))

        except (ImportError, RuntimeError) as e:
            logger.warning("emotion_spirit: SylannEngine 初始化失败 (%s)", e)
            self._engine = None

    async def _start_engine_shared(self, llm) -> None:
        """通过 SylanneEngine.shared() 获取共享引擎并注册监听器。"""
        try:
            from emotion_spirit.sylanne import SylanneEngine, SylanneConfig

            data_dir = str(self._data_dir / "sylanne_sessions")
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
                data_dir = str(self._data_dir / "sylanne_sessions")
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

    # ═══ v1.2.4: 拆分后的 on_llm_request 子方法 ═══

    def _observe_rhythm_and_dream(self, user_id: str, text: str) -> None:
        """RhythmLearner 观察 + 睡眠剥夺梦境触发。"""
        if hasattr(self, '_rhythm_learner') and self._rhythm_learner:
            try:
                intimacy = self._intimacy.get_intimacy(user_id, self._current_persona)
                self._rhythm_learner.observe_user_message(user_id, text, datetime.now().timestamp(), intimacy)
            except Exception:
                pass

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

    async def _run_engine_and_agents(self, event: AstrMessageEvent, user_id: str, text: str) -> Any:
        """Engine surface 处理 + Agent PRE cycle + 注入队列。"""
        self._last_texts[user_id] = text
        if len(self._last_texts) > 100:
            oldest = list(self._last_texts.keys())[:50]
            for k in oldest:
                del self._last_texts[k]

        surface = await self._engine_manager.process_async(event.unified_msg_origin, text)
        if surface is not None:
            self._consume_surface(user_id, surface)

        signals = self._latest_signals.get(user_id)
        v110c_ctx = self._get_v110c_adaptation_context(user_id)
        surface_with_phase = {
            "_phase": "pre",
            "intimacy_gravity": self._intimacy.get_intimacy(user_id, self._current_persona),
            "user_text": text,
            "safety_level": self._safety_level,
            "emotion_delta": getattr(signals, 'emotion_velocity', 0.0) if signals else 0.0,
            "cascade_active": self._pool.cascade_active(),
            "boundary_pressure": 0.0,
            "suppression_level": v110c_ctx["suppression_level"],
            "collapse_archetype": v110c_ctx["collapse_archetype"],
            "has_interaction": True,
            "user_id": user_id,
        }
        composed = await self._self_core.run_cycle(user_id, surface_with_phase, "pre")
        await self._flush_inject_queue()
        return composed

    async def _inject_life_event(self, user_id: str) -> str:
        """LifeSimulator 生活片段生成, 返回注入文本 (空串=无事件)。"""
        if self._life_sim is None:
            return ""
        try:
            signals = self._latest_signals.get(user_id)
            if signals is None:
                return ""
            personality_dict = {
                **(signals.personality_deep or {}),
                **(signals.personality_surface or {}),
            }
            event_a = self._life_sim.check_mode_a(signals, personality_dict) if self._enable_life_fragment else None
            event_b = event_a or (self._life_sim.check_mode_b(signals, personality_dict) if self._enable_proactive_prompt else None)
            if not event_b:
                return ""
            life_event = await self._life_sim.generate_life_prose(
                event_b,
                persona_desc=self._current_persona.get("label", "") if self._current_persona else "",
                personality=personality_dict,
            )
            if life_event is None:
                return ""
            consumed = self._life_sim.consume_life_event()
            if consumed is None:
                return ""
            parts = [f"[生活片段] 你刚才{consumed.text}"]
            if consumed.mood and consumed.mood != "neutral":
                parts.append(f"（心情: {consumed.mood}）")
            if consumed.wants_to_share:
                parts.append("这件事你想分享给朋友")
            return "，".join(parts) + "。"
        except Exception:
            logger.debug("emotion_spirit: life_sim tick error", exc_info=True)
            return ""

    # ═══ LLM 请求注入 ═══

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: Any) -> None:
        """LLM 请求前: 观察节奏/梦境/引擎/Agent/生活片段/context 注入。"""
        user_id = event.get_sender_id()
        text = event.message_str

        # 1. 观察节奏 + 梦境
        self._observe_rhythm_and_dream(user_id, text)

        # 2. Engine surface + Agent PRE cycle
        composed = await self._run_engine_and_agents(event, user_id, text)

        # 3. 生活片段
        life_event = await self._inject_life_event(user_id)

        # 3b. v1.2.7: user_activity_detector — 检测用户文本中的活动/计划
        if hasattr(self, '_latest_signals'):
            if not hasattr(self, '_latest_user_activity'):
                self._latest_user_activity: dict[str, Any] = {}
            try:
                from emotion_spirit.utils import UserActivityDetector
                detector = UserActivityDetector()
                self._latest_user_activity[user_id] = detector.detect_plan(text)
            except Exception:
                pass

        if self._persona_mode == "disabled":
            return
        if self._persona_mode == "auto" and not self._persona_initialized:
            return

        # 4. 构建注入 context
        current_personality = {
            "deep": self._consumer.consume({}).personality_deep or {},
            "surface": self._consumer.consume({}).personality_surface or {},
        }
        current_personality = self._relationship_personality.apply_to_layers(current_personality, user_id)
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
        if life_event:
            context = f"{life_event}\n\n{context}" if context else life_event
        if hasattr(self, '_life_sim_v2') and self._life_sim_v2._current_plan:
            schedule_ctx = self._life_sim_v2.build_schedule_context()
            if schedule_ctx:
                context = f"[今日日程] {schedule_ctx}\n\n{context}" if context else f"[今日日程] {schedule_ctx}"
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
            logger.debug("emotion_spirit inject: user=%s context_len=%d", user_id[:8], len(context))
            if req.system_prompt:
                req.system_prompt = f"{context}\n\n{req.system_prompt}"
            else:
                req.system_prompt = context

    # ═══ LLM 回复处理 ═══

    @filter.on_llm_response(desc="处理 LLM 回复，更新记忆和亲密度")
    async def on_llm_response(self, event: AstrMessageEvent, response: Any) -> None:
        """Bot 回复后: 写入 MemoryPool + 更新 IntimacyTracker + 委托编排器.

        v1.2.7: 分段回复编排委托 SegmentedReplyOrchestrator (输出编排 → @register 组件).
        v1.2.8: 副作用 + 状态收集抽 helper, on_llm_response 薄壳化 (< 55 行).
        """
        try:
            bot_text = getattr(response, "completion_text", "") or ""
            if not bot_text:
                return
            user_id = event.get_sender_id()
            tone, weight = extract_bot_emotion(bot_text)

            # 1. 写 memory + 更新 intimacy + reflex learn (v1.2.8: 抽 _apply_bot_reply_effects)
            self._apply_bot_reply_effects(user_id, bot_text, tone, weight)

            # 2. 分段回复 (v1.2.7: 委托 SegmentedReplyOrchestrator; v1.2.8: 状态收集抽 helper)
            seg_config = self._config.get("segmented_reply", {})
            if seg_config.get("enable", False) and hasattr(self, '_segmented_orchestrator'):
                if self._config.get("provider_settings", {}).get("streaming_response", False):
                    logger.info("emotion_spirit: streaming_response=True, skipping segmented_reply")
                else:
                    state = self._collect_segmented_state(user_id, event)
                    try:
                        await self._segmented_orchestrator.handle(
                            event=event, response=response, bot_text=bot_text, user_id=user_id,
                            seg_config=seg_config, signals=state["signals"], context=state["context"],
                            personality=state["personality"], current_persona=self._current_persona,
                            labels=self._labels, force_state=state["force_state"],
                            conscience_pressure=state["conscience_pressure"],
                        )
                    except Exception:
                        logger.warning(
                            "emotion_spirit: segmented_reply failed, falling back to AstrBot default",
                            exc_info=True,
                        )

            logger.info(
                "emotion_spirit on_llm_response: user=%s tone=%s weight=%.2f len=%d",
                user_id[:8], tone, weight, len(bot_text),
            )
        except Exception:
            logger.warning("emotion_spirit: on_llm_response error", exc_info=True)

    def _apply_bot_reply_effects(self, user_id: str, bot_text: str, tone: str, weight: float) -> None:
        """Bot 回复副作用: 写 memory + 更新 intimacy + reflex learn (v1.2.8: 从 on_llm_response 抽出).

        v1.3.0 rc.3 (Bug-F): 用 memory_type 标记 (替 v1.2.11 token filter "不入 pool").
        bot ephemeral state (含 "我刚到/我准备" 等词) → memory_type="bot_ephemeral_state"
        (仍入 pool 记录, 但召回时过滤, 不污染上下文). 其他 bot reply → "bot_reply".
        """
        head = bot_text[:200]
        if any(tok in head for tok in _EPHEMERAL_BOT_TOKENS):
            memory_type = "bot_ephemeral_state"
            logger.debug(
                "emotion_spirit: ephemeral bot-state tagged user=%s head=%r",
                user_id[:8], head[:50],
            )
        else:
            memory_type = "bot_reply"

        self._pool.add_for_user(
            user_id=user_id, text=bot_text[:500], raw_weight=weight,
            phi=0.4, tags=["bot_reply", tone], source_user="bot",
            memory_type=memory_type,  # v1.3.0 rc.3 Bug-F
        )
        self._intimacy.update(
            user_id, interval_seconds=0,
            vulnerability_delta=0.05 if tone == "warm" else 0.0,
        )
        import time as _time_mod
        gap = _time_mod.time() - self._last_bot_reply_time.get(user_id, 0.0)
        from emotion_spirit.memory.reflex_learner import compute_behavior
        self._reflex_learner.learn(compute_behavior(gap))
        self._last_bot_reply_time[user_id] = _time_mod.time()

    def _collect_segmented_state(self, user_id: str, event) -> dict:
        """收集分段回复编排所需运行时状态 (v1.2.8: 从 on_llm_response 抽出, 薄壳化).

        返回 force_state/signals/context/personality/conscience_pressure 快照。
        body_state/intimacy 由 orchestrator depends_on 自取, 不在此收集 (§4.A 状态归属)。
        """
        return {
            "force_state": (
                self.get_current_force_state(self._labels)
                if hasattr(self, "_force_dynamics") else None
            ),
            "signals": (
                self._latest_signals.get(user_id)
                if hasattr(self, "_latest_signals") else None
            ),
            "context": build_context(event),
            "personality": self._get_current_personality_dict(),
            "conscience_pressure": (
                self._conscience.get_pressure()
                if hasattr(self, "_conscience") else 0.0
            ),
        }

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
    view_diary_cmd = _ns_command("view_diary", "view_diary", "查看历史日记（最近 N 篇）。")
    reflect_patterns_cmd = _ns_command("reflect_patterns", "reflect_patterns", "查看行为模式。")
    reflect_force_current_cmd = _ns_command("reflect_force_current", "reflect_force_current", "查看当前力平衡 + 沉默/分段历史。")

    # ═══ 内部方法: 持久化 ═══

    def _load_persistent_data(self) -> None:
        """加载持久化数据 (v1.2.4: 拆为 3 个子方法)。"""
        self._load_core_data()
        self._load_phase2_data()
        self._load_life_and_v2_data()
        # v1.2.7 HP-4: force_dynamics offset 恢复
        if hasattr(self, '_force_dynamics') and self._force_dynamics:
            fd_offset = self._store.get("force_dynamics_offset", None)
            if fd_offset:
                self._force_dynamics.restore_offset(fd_offset)

    def _load_core_data(self) -> None:
        """核心模块恢复: pool/intimacy/superego (L1458-1479)。"""
        from emotion_spirit.memory.memory_pool import MemoryPool

        pool_data = self._store.get("memory_pool")
        if pool_data:
            self._pool = MemoryPool.from_dict(pool_data)
        for key, attr in [
            ("intimacy", "_intimacy"), ("alignment", "_alignment"),
            ("conscience", "_conscience"), ("ideal_self", "_ideal"),
            ("value_resistance", "_value_resistance"), ("superego_guard", "_superego_guard"),
        ]:
            data = self._store.get(key)
            if data and hasattr(self, attr):
                getattr(self, attr).from_dict(data)

    def _load_phase2_data(self) -> None:
        """Phase 2 模块恢复: patterns/shadow/diary/drift/sentinel/narrative/counterfactual (L1481-1546)。"""
        from emotion_spirit.output.buffer_signals import BufferSignals
        from emotion_spirit.regulation.pattern_extractor import PatternExtractor
        from emotion_spirit.regulation.shadow_detector import ShadowDetector
        from emotion_spirit.regulation.life_simulator import LifeSimulator
        from emotion_spirit.regulation.personality_drift import PersonalityDrift
        from emotion_spirit.output.predictive_sentinel import PredictiveSentinel
        from emotion_spirit.output.narrative_identity import NarrativeIdentity
        from emotion_spirit.regulation.counterfactual import Counterfactual
        from emotion_spirit.output.prompt_injector import PromptInjector

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

        # v1.2.5 PR3 T4: 9 个 memory/output 模块走 self._modules 装配, 删手 new
        self._patterns = self._modules["pattern_extractor"]
        if patterns_data:
            self._patterns.from_dict(patterns_data)
        self._buffer_signals = self._modules["buffer_signals"]
        if signals_data:
            self._buffer_signals.from_dict(signals_data)
        if self._enable_shadow:
            self._shadow = self._modules["shadow_detector"]
            if shadow_data:
                self._shadow.from_dict(shadow_data)
        if self._enable_life:
            self._life_sim = self._modules["life_simulator"]
            if life_sim_data:
                self._life_sim.from_dict(life_sim_data)
            self._life_sim.configure(llm_caller=self._get_llm_callable("life_sim"))

        diary_cfg = self._config.get("diary", {})
        self._diary.configure(llm_caller=self._get_llm_callable("diary"), llm_enabled=diary_cfg.get("enable_diary_llm", False))
        self._diary.configure_force_dynamics(self._force_dynamics, getattr(self, "_labels", None))
        if diary_data:
            self._diary.from_dict(diary_data)

        self._drift = self._modules["personality_drift"]
        if drift_data:
            self._drift.from_dict(drift_data)
        if self._enable_sentinel:
            self._sentinel = self._modules["predictive_sentinel"]
            if sentinel_data:
                self._sentinel.from_dict(sentinel_data)
        if self._enable_narrative:
            self._narrative = self._modules["narrative_identity"]
            if narrative_data:
                self._narrative.from_dict(narrative_data)
        self._counterfactual = self._modules["counterfactual"]
        if cf_data:
            self._counterfactual.from_dict(cf_data)

        self._injector = self._modules["prompt_injector"]

    def _load_life_and_v2_data(self) -> None:
        """v2/reflex/dream/coordinator 状态恢复 (L1547-1565)。"""
        life_sim_v2_data = self._store.get("life_sim_v2")
        if life_sim_v2_data and hasattr(self, '_life_sim_v2'):
            self._life_sim_v2.from_dict(life_sim_v2_data)
        saved_plan_date = self._store.get("last_plan_date")
        if saved_plan_date:
            self._last_plan_date = saved_plan_date
        reflex_data = self._store.get("reflex_deltas")
        if reflex_data:
            self._reflex_store.from_dict(reflex_data)
        dream_data = self._store.get("dream_state")
        if dream_data:
            self._dream_generator.from_dict(dream_data)
        coord_data = self._store.get("segmented_coordinator")
        if coord_data and hasattr(self, '_segmented_coordinator'):
            self._segmented_coordinator.from_dict(coord_data)
        # v1.2.8: project_manager + recovery_tracker 恢复 (走 LifeSimulatorV2 公开接口, 不伸手私有)
        lsv2 = getattr(self, '_life_sim_v2', None)
        if lsv2 and hasattr(lsv2, 'restore_extensions'):
            lsv2.restore_extensions({
                "project_manager": self._store.get("project_manager"),
                "recovery_tracker": self._store.get("recovery_tracker"),
            })

    def _persist_modules(self) -> None:
        """统一所有模块持久化 (v1.2.2 B7-fix: 合并 _save_if_dirty/_save_all 两路径)。

        高频调用 (_save_if_dirty) 和低频调用 (_save_all/terminate) 共用此方法,
        避免"两保存路径分叉"导致 diary/reservoir/patterns 等 >=8 个模块只在
        terminate 时才写 storage。
        """
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
        # v1.2.7 HP-4: force_dynamics offset 持久化
        if hasattr(self, '_force_dynamics'):
            self._store.set("force_dynamics_offset", self._force_dynamics.get_cumulative_offset())
        # v1.1.0A: LifeSimulator v2 (adapt_plan 会修改 plan 状态)
        if hasattr(self, '_life_sim_v2'):
            self._store.set("life_sim_v2", self._life_sim_v2.to_dict())
            self._store.set("last_plan_date", self._last_plan_date)
        # v1.1.0B: ReflexLearner + DreamGenerator
        if hasattr(self, '_reflex_store'):
            self._store.set("reflex_deltas", self._reflex_store.to_dict())
        if hasattr(self, '_dream_generator') and hasattr(self._dream_generator, 'to_dict'):
            self._store.set("dream_state", self._dream_generator.to_dict())
        # v1.2.3: SegmentedReplyCoordinator 状态 (ignored_rate deque)
        if hasattr(self, '_segmented_coordinator'):
            self._store.set("segmented_coordinator", self._segmented_coordinator.to_dict())
        # v1.2.8: project_manager + recovery_tracker 持久化 (走 LifeSimulatorV2 公开接口)
        lsv2 = getattr(self, '_life_sim_v2', None)
        if lsv2 and hasattr(lsv2, 'persist_extensions'):
            for key, data in lsv2.persist_extensions().items():
                if data is not None:
                    self._store.set(key, data)

    def _save_if_dirty(self) -> None:
        self._persist_modules()
        self._store.save()

    def _save_all(self) -> None:
        self._persist_modules()
        self._store.save()

    # ═══ 公开 API (v1.1.1 + v1.2 扩展) — 保持向后兼容结构 ═══
    # 注: PublicAPI 网关提供 flat 结构 (B6.10), 这里保留 nested "pad"/"distribution" 结构
    # 因为现有集成测试 (test_emotion_integration.py) 期望 nested 结构。

    async def get_emotion_state(
        self, session_key: str, include_trajectory: bool = False,
    ) -> dict | None:
        """统一情绪状态 API (v1.1.1 9 字段 + v1.2 +ambiguity +velocity = 11 字段)。"""
        from emotion_spirit.utils import render_description

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
