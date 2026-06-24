"""emotion_spirit 12 命令实现 (Phase B, P3-1 拆分后)。

12 命令 (B6.10 拆分) 分配 3 ns:
- /setup_* (4): init / relabel / switch / list
- /view_* (3): status / detail / whoami
- /reflect_* (5): drift / sentinel / shadows / diary / patterns

CommandImpl 类接收 plugin 引用访问 state, 实现从原 main.py 复制不改逻辑。
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from datetime import datetime, timezone

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

if TYPE_CHECKING:
    from main import EmotionSpiritPlugin



__all__ = [
    "CommandImpl",
]

class CommandImpl:
    """12 命令的具体实现。

    接收 plugin 引用, 所有 self._pool 等属性通过 plugin 访问。
    """

    def __init__(self, plugin: "EmotionSpiritPlugin") -> None:
        self._p = plugin

    # ═══ /setup ns (4) ═══

    async def setup_init(self, event: AstrMessageEvent) -> None:
        """初始化当前人格参数。仅 auto 模式需要手动调用。"""
        from emotion_spirit.core.label_mapper import labels_to_personality
        from emotion_spirit.regulation.persona_report_parser import parse_persona_report
        from emotion_spirit.regulation.persona_analyzer import PersonaAnalyzer, save_report

        if self._p._persona_mode == "disabled":
            yield event.plain_result("⚠️ 当前为 disabled 模式，无需初始化。请在配置中切换到 auto 模式。")
            return

        if self._p._persona_initialized:
            yield event.plain_result(
                f"✅ 人格 '{self._p._current_persona}' 已初始化\n"
                f"使用 /setup_whoami 查看标签，/view_detail 查看参数"
            )
            return

        persona_id = self._p._current_persona
        logger.info("emotion_spirit: /setup_init 开始初始化人格 '%s'", persona_id)

        # 1. 尝试 LLM 分析
        system_prompt = self._p._read_persona_prompt(persona_id)
        labels = {}
        drives = {}
        source = "default"

        if system_prompt:
            parsed = parse_persona_report(system_prompt)
            if parsed.has_labels:
                labels = parsed.labels
                drives = parsed.drives
                source = "规则解析"
                logger.info("emotion_spirit: 规则解析成功 — %s", labels)

            llm = self._p._get_llm_callable()
            if llm:
                try:
                    analyzer = PersonaAnalyzer(llm)
                    result = await analyzer.analyze(persona_id, system_prompt)
                    if result.has_labels:
                        labels = result.labels
                        drives = result.drives
                        source = "LLM 分析"
                        self._p._auto_report = result
                        save_report(result, self._p._store._dir)
                        logger.info("emotion_spirit: LLM 分析成功 — %s", labels)
                except Exception:
                    logger.warning("emotion_spirit: LLM 分析失败，使用规则解析结果", exc_info=True)

        if not labels:
            labels = self._p._get_default_labels()
            source = "默认值"

        # 2. 应用标签
        self._p._labels = labels
        self._p._parsed_drives = drives
        self._p._update_baseline()

        # 3. 重新初始化 superego 模块
        from emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
        from emotion_spirit.regulation.superego_guard import SuperegoGuard
        self._p._alignment = ValueAlignment(persona_id)
        self._p._value_resistance = ValueResistance(persona_id)
        self._p._ideal = IdealSelf(persona_id, labels)
        self._p._superego_guard = SuperegoGuard(
            self._p._conscience, self._p._alignment, self._p._ideal, persona_id,
        )
        self._p._personas_cache = self._p._scan_all_personas()

        # 4. 标记已初始化
        self._p._persona_initialized = True

        # 4.5 持久化 persona namespace
        self._p._store.set("persona", {
            "initialized": True,
            "persona_id": persona_id,
            "labels": labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._p._store.save()

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

        deep = personality.get("deep", {})
        if deep:
            sorted_dims = sorted(deep.items(), key=lambda x: x[1], reverse=True)
            core = [d for d, v in sorted_dims[:5]]
            peripheral = [d for d, v in sorted_dims[5:]]
            lines.append("")
            lines.append(f"核心维度 ({', '.join(core)})")
            lines.append(f"边缘维度 ({', '.join(peripheral)})")

        lines.append("")
        lines.append("💡 使用 /view_detail 查看完整 13 维参数")

        yield event.plain_result("\n".join(lines))

    async def setup_relabel(
        self, event: AstrMessageEvent, confirm: str = "", *labels: str
    ) -> None:
        """两阶段调整人格标签。"""
        if self._p._persona_mode == "disabled":
            yield event.plain_result("⚠️ disabled 模式不支持 relabel。请在配置中切换到 auto 模式。")
            return
        if not self._p._persona_initialized:
            yield event.plain_result("⚠️ 未初始化，无法调整标签。请先 /setup_init")
            return

        # 阶段 1: 警告
        if not confirm:
            self._p._relabel_pending = True
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
                "  /setup_relabel confirm <mbti> <attachment> <emotion_style> <conflict_style> <time_focus>\n\n"
                "示例: /setup_relabel confirm INFP 焦虑型 表达型 顺应型 活在当下"
            )
            yield event.plain_result(warn_msg)
            return

        if confirm != "confirm":
            yield event.plain_result("❌ 第二个参数必须为 'confirm'")
            return

        if not getattr(self._p, '_relabel_pending', False):
            yield event.plain_result("❌ 请先调用 /setup_relabel 查看警告")
            return

        if len(labels) != 5:
            yield event.plain_result(f"❌ 需要 5 个标签参数，得到 {len(labels)} 个")
            return

        new_labels = self._p._validate_labels(labels)
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
        self._p._labels = new_labels
        self._p._update_baseline()
        self._p._reset_superego_modules()

        if self._p._auto_report:
            from emotion_spirit.regulation.persona_analyzer import save_report
            save_report(self._p._auto_report, self._p._store._dir)

        self._p._store.set("persona", {
            "initialized": True,
            "persona_id": self._p._current_persona,
            "labels": self._p._labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._p._store.save()

        self._p._relabel_pending = False
        logger.warning(
            "emotion_spirit: /setup_relabel 执行 — persona=%s new_labels=%s",
            self._p._current_persona, new_labels,
        )

        from emotion_spirit.core.label_mapper import labels_to_personality
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
            f"💡 使用 /view_detail 查看完整 13 维参数"
        )
        yield event.plain_result(result)

    async def setup_switch(
        self, event: AstrMessageEvent, persona_id: str = ""
    ) -> None:
        """切换到指定人格。"""
        from emotion_spirit.regulation.persona_report_parser import parse_persona_report

        if not persona_id:
            yield event.plain_result(
                "❓ 用法: /setup_switch <persona_id>\n"
                "使用 /setup_list 查看可用人格"
            )
            return

        if persona_id not in self._p._personas_cache:
            system_prompt = self._p._read_persona_prompt(persona_id)
            if not system_prompt:
                yield event.plain_result(f"❌ 未找到人格: {persona_id}")
                return

            parsed = parse_persona_report(system_prompt)
            self._p._personas_cache[persona_id] = {
                "labels": parsed.labels,
                "drives": parsed.drives,
                "traits": parsed.traits,
                "has_report": parsed.has_labels,
            }

        old_persona = self._p._current_persona
        self._p._current_persona = persona_id

        cached = self._p._personas_cache[persona_id]
        if cached.get("labels"):
            self._p._labels = cached["labels"]
            self._p._parsed_drives = cached.get("drives", {})
        else:
            self._p._labels = self._p._get_default_labels()
            self._p._parsed_drives = {}
        self._p._update_baseline()

        from emotion_spirit.regulation.superego import ValueAlignment, IdealSelf, ValueResistance
        from emotion_spirit.regulation.superego_guard import SuperegoGuard
        self._p._alignment = ValueAlignment(self._p._current_persona)
        self._p._value_resistance = ValueResistance(self._p._current_persona)
        self._p._ideal = IdealSelf(self._p._current_persona, self._p._labels)
        self._p._superego_guard = SuperegoGuard(
            self._p._conscience, self._p._alignment, self._p._ideal, self._p._current_persona,
        )

        if self._p._persona_initialized:
            self._p._reset_superego_modules()

        self._p._persona_initialized = True
        self._p._store.set("persona", {
            "initialized": True,
            "persona_id": self._p._current_persona,
            "labels": self._p._labels,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        })
        self._p._store.save()

        yield event.plain_result(
            f"✅ 已切换人格: {old_persona} → {persona_id}\n"
            f"使用 /setup_whoami 查看标签，/view_detail 查看完整参数"
        )

    async def setup_list(self, event: AstrMessageEvent) -> None:
        """列出所有可用人格。"""
        self._p._personas_cache = self._p._scan_all_personas()

        lines = [f"🎭 人格列表 (模式: {self._p._persona_mode})"]
        lines.append("")

        if self._p._personas_cache:
            lines.append("── AstrBot 人格 ──")
            for persona_id, info in self._p._personas_cache.items():
                current_mark = " ← 当前" if persona_id == self._p._current_persona else ""
                has_report = "✅" if info.get("has_report") else "❌"
                lines.append(f"  【{persona_id}】{current_mark} 报告: {has_report}")
                if info.get("labels"):
                    lbl = info["labels"]
                    lines.append(f"    MBTI: {lbl.get('mbti', '?')} | 依恋: {lbl.get('attachment', '?')}")

        if not self._p._personas_cache:
            lines.append("📭 未检测到任何人格")

        lines.append("💡 使用 /setup_switch <名称> 切换人格")
        lines.append("💡 使用 /view_detail <名称> 查看完整参数")
        yield event.plain_result("\n".join(lines))

    # ═══ /view ns (3) ═══

    async def view_status(self, event: AstrMessageEvent) -> None:
        """查看 emotion_spirit 状态。"""
        pool = self._p._pool
        user_id = event.get_sender_id()
        lifecycle = self._p._intimacy.get_lifecycle(user_id)
        intimacy = self._p._intimacy.get_intimacy(user_id, self._p._current_persona)
        alignment = self._p._alignment.get_score()
        trend = self._p._alignment.get_trend()
        pressure = self._p._conscience.get_pressure()
        breakdown = self._p._conscience.get_pressure_breakdown()
        reservoir = self._p._reservoir.level
        engine_status = "已连接" if self._p._engine else "未连接"

        mode_names = {"auto": "自动读取", "disabled": "已禁用"}
        mode_display = mode_names.get(self._p._persona_mode, self._p._persona_mode)

        pressure_breakdown = ""
        if breakdown.get("by_type"):
            items = sorted(breakdown["by_type"].items(), key=lambda x: x[1], reverse=True)
            pressure_breakdown = ", ".join(f"{t}: {s:.2f}" for t, s in items[:3])

        safety_info = f"安全级别: {self._p._safety_level}"
        if self._p._safety_note:
            safety_info += f" | {self._p._safety_note}"

        features = []
        features.append("阴影:ON" if self._p._enable_shadow else "阴影:OFF")
        features.append("预警:ON" if self._p._enable_sentinel else "预警:OFF")
        features.append("叙事:ON" if self._p._enable_narrative else "叙事:OFF")
        if self._p._enable_life:
            features.append(f"生活:{self._p._life_mode}")
        else:
            features.append("生活:OFF")

        init_status = ""
        if self._p._persona_mode == "auto":
            init_status = " (已初始化)" if self._p._persona_initialized else " (未初始化，发送 /setup_init)"

        status = (
            f"📊 emotion_spirit 状态\n"
            f"人格模式: {mode_display}\n"
            f"当前人格: {self._p._current_persona}{init_status}\n"
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

    async def view_detail(self, event: AstrMessageEvent, persona_name: str = "") -> None:
        """查看人格的完整 13 维参数。"""
        from emotion_spirit.core.label_mapper import labels_to_personality

        if persona_name:
            labels = None
            if self._p._auto_report and self._p._auto_report.persona_id == persona_name:
                labels = self._p._auto_report.labels
            elif persona_name in self._p._personas_cache:
                labels = self._p._personas_cache[persona_name].get("labels", {})

            if not labels:
                yield event.plain_result(f"❌ 未找到人格 '{persona_name}' 或其标签数据")
                return
        else:
            labels = self._p._labels
            persona_name = self._p._current_persona

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

        if self._p._parsed_drives:
            lines.append("")
            lines.append("驱动力 (从报告解析):")
            for drive, val in self._p._parsed_drives.items():
                bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                lines.append(f"  {drive}: {bar} {val:.2f}")

        yield event.plain_result("\n".join(lines))

    async def view_whoami(self, event: AstrMessageEvent) -> None:
        """查看当前人格标签 (5 轴标签概览)。"""
        mode_names = {"auto": "自动读取", "disabled": "已禁用"}
        mode_display = mode_names.get(self._p._persona_mode, self._p._persona_mode)

        lines = [f"🎭 人格状态 — 模式: {mode_display}"]
        lines.append(f"   当前人格: {self._p._current_persona}")
        lines.append("")

        if not self._p._labels or not any(self._p._labels.values()):
            lines.append("⚠️ 未加载任何标签")
        else:
            lines.append("5 轴标签:")
            label_names = {
                "mbti": "MBTI", "attachment": "依恋风格",
                "emotion_style": "情绪策略", "conflict_style": "冲突风格",
                "time_focus": "时间取向",
            }
            for key, value in self._p._labels.items():
                lines.append(f"  {label_names.get(key, key)}: {value}")

            if self._p._auto_report:
                src = "LLM 分析" if self._p._auto_report.source == "llm" else "规则推断"
                lines.append(f"\n  📊 来源: {src} (置信度: {self._p._auto_report.confidence:.0%})")

        lines.append("\n💡 使用 /view_detail 查看完整 13 维参数")
        yield event.plain_result("\n".join(lines))

    # ═══ /reflect ns (5) ═══

    async def reflect_drift(self, event: AstrMessageEvent) -> None:
        """查看人格漂移状态。"""
        status = self._p._drift.get_drift_status()
        drifts = self._p._drift.check_drift()

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

    async def reflect_sentinel(self, event: AstrMessageEvent) -> None:
        """查看预警状态。"""
        if not self._p._sentinel:
            yield event.plain_result("⚠️ 预警系统已关闭，请在配置中启用 enable_sentinel")
            return
        result = self._p._sentinel.check()

        lines = [f"🚨 预警状态: {result['level']}"]
        lines.append(f"触发信号: {result['triggered_count']}")

        if result["triggered_signals"]:
            for sig in result["triggered_signals"]:
                lines.append(f"  ⚠️ {sig}")
        else:
            lines.append("  ✅ 所有信号正常")

        yield event.plain_result("\n".join(lines))

    async def reflect_shadows(self, event: AstrMessageEvent) -> None:
        """查看阴影检测。"""
        if not self._p._shadow:
            yield event.plain_result("⚠️ 阴影检测已关闭，请在配置中启用 enable_shadow_detector")
            return
        shadows = self._p._shadow.detect()

        if not shadows:
            yield event.plain_result("🌑 未检测到阴影")
            return

        lines = [f"🌑 检测到 {len(shadows)} 个阴影:"]
        for s in shadows[:5]:
            lines.append(f"  [{s['evidence']}] {s['tag']} (置信度: {s['confidence']:.2f})")
            lines.append(f"    {s['suggestion']}")

        yield event.plain_result("\n".join(lines))

    async def reflect_diary(self, event: AstrMessageEvent) -> None:
        """手动生成日记。"""
        diary_type = self._p._diary.determine_diary_type()
        prompt = self._p._diary.build_diary_prompt(diary_type)
        yield event.plain_result(f"📝 日记类型: {diary_type}\n\n{prompt}")

    async def reflect_patterns(self, event: AstrMessageEvent) -> None:
        """查看行为模式。"""
        self._p._patterns.extract()
        patterns = self._p._patterns.get_patterns()

        if not patterns:
            yield event.plain_result("📋 未检测到模式")
            return

        lines = [f"📋 检测到 {len(patterns)} 个模式:"]
        for p in patterns[:5]:
            lines.append(f"  [{p.pattern_type}] {', '.join(p.tags)} (次数: {p.count})")

        yield event.plain_result("\n".join(lines))

    # ═══ /view 扩展命令 ═══

    async def view_memory(self, event: AstrMessageEvent) -> None:
        """显示当前用户 buffer/warm/cold 条目摘要。"""
        pool = self._p._pool
        user_id = event.get_sender_id()

        # 按用户过滤条目
        user_buffer = [e for e in pool.buffer if e.source_user == user_id]
        user_warm = [e for e in pool.warm if e.source_user == user_id]
        user_cold = [e for e in pool.cold if e.source_user == user_id]
        user_ghosts = [e for e in pool.ghosts if e.source_user == user_id]

        lines = ["🧠 记忆池状态"]
        lines.append(f"缓冲池: {len(pool.buffer)} 条 (你: {len(user_buffer)})")
        lines.append(f"温池: {len(pool.warm)} 条 (你: {len(user_warm)})")
        lines.append(f"冷池: {len(pool.cold)} 条 (你: {len(user_cold)})")
        lines.append(f"幽灵: {len(pool.ghosts)} 条 (你: {len(user_ghosts)})")

        # 显示最近的 buffer 条目
        if user_buffer:
            lines.append(f"\n📝 最近 buffer 条目 (最多 5 条):")
            for e in sorted(user_buffer, key=lambda x: x.created_at, reverse=True)[:5]:
                text_preview = e.text[:40] + "..." if len(e.text) > 40 else e.text
                lines.append(f"  [{e.tier}] {text_preview} (权重: {e.weight:.2f})")

        # 显示最近的 warm 条目
        if user_warm:
            lines.append(f"\n🔥 最近 warm 条目 (最多 3 条):")
            for e in sorted(user_warm, key=lambda x: x.created_at, reverse=True)[:3]:
                text_preview = e.text[:40] + "..." if len(e.text) > 40 else e.text
                lines.append(f"  {text_preview} (权重: {e.weight:.2f})")

        yield event.plain_result("\n".join(lines))

    async def view_force(self, event: AstrMessageEvent) -> None:
        """三元力学状态 + 13 维→力映射。"""
        from emotion_spirit.regulation.force_dynamics import ForceDynamics

        # 获取当前人格
        personality = self._p._parsed_drives
        if not personality:
            yield event.plain_result("⚠️ 未初始化人格，请先发送 /setup_init")
            return

        # 计算力学状态
        body_state = self._p._consumer._latest_body if hasattr(self._p._consumer, '_latest_body') else None
        pressure = self._p._conscience.get_pressure()
        force = ForceDynamics().compute(personality, body_state, pressure)

        lines = ["⚡ 三元力学状态"]
        lines.append(f"自然 (natural):   {force.natural:.3f}")
        lines.append(f"社会 (social):    {force.social:.3f}")
        lines.append(f"个体 (individual): {force.individual:.3f}")

        # 找出主导力
        forces = {"自然": force.natural, "社会": force.social, "个体": force.individual}
        dominant = max(forces, key=forces.get)
        lines.append(f"\n主导力: {dominant} ({forces[dominant]:.3f})")

        # 13 维到力的映射
        from emotion_spirit.regulation.force_dynamics import DIM_FORCE
        lines.append(f"\n📊 13 维→力映射:")
        dim_groups = {"natural": [], "social": [], "individual": []}
        for dim, force_type in DIM_FORCE.items():
            if dim in personality:
                dim_groups[force_type].append((dim, personality[dim]))

        for force_type, dims in dim_groups.items():
            if dims:
                dims_str = ", ".join(f"{d}={v:.2f}" for d, v in dims[:3])
                lines.append(f"  {force_type}: {dims_str}")

        yield event.plain_result("\n".join(lines))
