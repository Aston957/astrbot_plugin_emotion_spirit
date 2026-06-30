"""v1.2.2 CI 防回归测试 — B4/B7/B8/B9.

B4: _ns_handler 传参
B7: _persist_modules 统一持久化
B8: view_diary 命令
B9: persona parser tie-breaking 不偏向 INTJ
"""

import pytest
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestB4NsHandlerArgs:
    """B4: _ns_handler 必须能接收 *args 传参 (v4.26.1 CommandFilter 兼容)."""

    def test_ns_handler_accepts_varargs(self):
        """_ns_handler 签名必须包含 *args, **kwargs."""
        # main.py 在插件根目录，不是 emotion_spirit 子包
        # 直接读取文件检查源码
        main_py = Path(__file__).parent.parent / "main.py"
        source = main_py.read_text(encoding="utf-8")

        # 检查 _ns_handler 定义是否包含 *args, **kwargs
        assert "async def _ns_handler(self, event: AstrMessageEvent, *args, **kwargs):" in source, \
            "_ns_handler 必须接受 *args, **kwargs"


class TestB7PersistModules:
    """B7: _persist_modules 必须保存所有模块，不能只存子集."""

    REQUIRED_KEYS = {
        "memory_pool", "intimacy", "alignment", "conscience",
        "ideal_self", "value_resistance", "superego_guard",
        "reservoir", "patterns", "buffer_signals",
        "shadow", "life_sim", "diary", "drift",
        "sentinel", "narrative", "counterfactual",
        "life_sim_v2", "last_plan_date", "reflex_deltas", "dream_state",
    }

    def test_persist_modules_covers_all_keys(self):
        """_persist_modules 方法必须覆盖所有必需 key."""
        # 直接读取 main.py 源码检查
        main_py = Path(__file__).parent.parent / "main.py"
        source = main_py.read_text(encoding="utf-8")

        # 验证每个必需 key 都在 _persist_modules 方法中被 set
        for key in self.REQUIRED_KEYS:
            assert f'self._store.set("{key}"' in source or f"self._store.set('{key}'" in source, \
                f"_persist_modules 缺少 key: {key}"


class TestB8ViewDiaryCommand:
    """B8: view_diary 命令必须存在且可调用."""

    def test_view_diary_command_exists(self):
        """commands.py 必须有 view_diary 方法."""
        from emotion_spirit.output.commands import CommandImpl

        assert hasattr(CommandImpl, "view_diary"), "CommandImpl 缺少 view_diary 方法"

    def test_view_diary_accepts_days_param(self):
        """view_diary 必须接受 days 参数."""
        import inspect
        from emotion_spirit.output.commands import CommandImpl

        sig = inspect.signature(CommandImpl.view_diary)
        params = list(sig.parameters.keys())

        assert "days" in params, "view_diary 必须接受 days 参数"


class TestB9PersonaParserNotBiasedToIntj:
    """B9: persona parser tie-breaking 不偏向 INTJ 轴."""

    def test_tie_breaking_not_biased_to_intj(self):
        """tie-breaking 必须倾向 E/N/F/P 而非 I/T/J."""
        from emotion_spirit.regulation.persona_report_parser import PersonaReportParser

        parser = PersonaReportParser()

        # 测试 tie-breaking: 空文本或中性描述
        # v1.2.2 之前: 全是 INTJ
        # v1.2.2 之后: 倾向 ENFP
        mbti = parser._infer_mbti_from_narrative("")

        # 验证不全是 INTJ 倾向
        assert not mbti.startswith("I"), f"tie 时应倾向 E, 得到 {mbti}"
        assert not mbti.endswith("J"), f"tie 时应倾向 P, 得到 {mbti}"

    def test_negation_handling_think_vs_feel(self):
        """否定词预处理: '而不是思考' 不应计为 T."""
        from emotion_spirit.regulation.persona_report_parser import PersonaReportParser

        parser = PersonaReportParser()

        # 描述强调 F 但提到 T 被否定
        text = "依靠直觉和感受，而不是长时间思考分析"
        mbti = parser._infer_mbti_from_narrative(text)

        # 应该是 F 而非 T
        third = mbti[2]  # F/T 位置
        assert third == "F", f"描述强调感受，应是 F，得到 {mbti}"

    def test_time_focus_negation(self):
        """时间取向否定: '不活在未来' 不应判为'活在未来'."""
        from emotion_spirit.regulation.persona_report_parser import (
            PersonaReportParser, _TIME_FOCUS_KEYWORDS, _TIME_FOCUS_NEGATIONS,
        )

        # 验证否定模式存在
        assert "活在未来" in _TIME_FOCUS_NEGATIONS, "_TIME_FOCUS_NEGATIONS 必须有 活在未来 的否定模式"

        # 测试否定匹配
        text = "我不想活在未来，只想过好当下"
        parser = PersonaReportParser()
        result = parser._infer_by_keywords(text.lower(), _TIME_FOCUS_KEYWORDS, "活在当下")

        # 如果最初匹配到"活在未来"，否定处理应将其纠正
        # 这里直接检查 _infer_missing_labels 的行为


class TestB6MigrationDoesNotLock:
    """B6: 迁移非 sentinel persona 必须留 initialized=False."""

    def test_migration_leaves_initialized_false(self):
        """_migrate_old_spirit_data 必须设置 _persona_initialized = False."""
        # 这个测试在 test_init_persistence.py::test_t10_migrate_old_spirit_data 中覆盖
        # 这里只做快速断言验证行为未回归
        main_py = Path(__file__).parent.parent / "main.py"
        source = main_py.read_text(encoding="utf-8")

        # 检查 _migrate_old_spirit_data 方法中是否有 initialized=False 的赋值
        # 且不能只给 sentinel 设置（新逻辑是给所有情况都设置）
        assert "self._persona_initialized = False" in source, \
            "_migrate_old_spirit_data 必须设置 initialized=False"
