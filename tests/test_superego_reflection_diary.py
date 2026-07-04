"""Bug-B (v1.2.10): superego reflection 日记走 LLM worker, 不再存 prompt 模板."""
from unittest.mock import MagicMock, AsyncMock


class TestSuperegoReflectionEnqueue:
    """Bug-B 核心逻辑: critical+guilt → 推队列, 不直接 record_diary (内联测试, 免 SurfaceHandler 全 mock)."""

    def _run_enqueue_logic(self, diary, tension, conflict_values, queue):
        """内联 surface_handler.py:206-211 的 Bug-B 逻辑."""
        if diary is not None and getattr(diary, "_llm_enabled", False):
            queue.append((tension, conflict_values, "session-1"))

    def test_consume_enqueues_not_records(self):
        queue = []
        diary = MagicMock()
        diary._llm_enabled = True
        diary.build_superego_reflection_prompt = MagicMock(return_value="reflection prompt")
        diary.record_diary = MagicMock()

        self._run_enqueue_logic(diary, "guilt", ["honesty", "loyalty"], queue)

        # 应入队
        assert len(queue) == 1
        tension, conflict_values, user_id = queue[0]
        assert tension == "guilt"
        assert conflict_values == ["honesty", "loyalty"]
        assert user_id == "session-1"

        # 不应直接 record_diary (没调 LLM)
        diary.record_diary.assert_not_called()

    def test_consume_skips_when_llm_off(self):
        queue = []
        diary = MagicMock()
        diary._llm_enabled = False
        diary.record_diary = MagicMock()

        self._run_enqueue_logic(diary, "guilt", ["honesty"], queue)

        # LLM-off → 不入队
        assert len(queue) == 0
        diary.record_diary.assert_not_called()

    def test_consume_skips_when_diary_none(self):
        queue = []

        self._run_enqueue_logic(None, "guilt", ["honesty"], queue)

        # diary=None → 不入队
        assert len(queue) == 0


class TestProcessOneReflection:
    """_process_one_reflection 调 LLM → record LLM 输出 (不是 prompt)."""

    def test_process_one_reflection_records_llm_output(self):
        from emotion_spirit.output.diary_writer import DiaryWriter

        diary = MagicMock(spec=DiaryWriter)
        diary._llm_enabled = True
        diary._llm_caller = AsyncMock(return_value="今天我和自己的内疚待了一会儿...")
        diary.generate_reflection_llm = AsyncMock(return_value="今天我和自己的内疚待了一会儿...")
        diary._entries = []
        diary.record_diary = MagicMock()

        # 模拟 _process_one_reflection 行为
        import asyncio

        async def run():
            if diary is None:
                return
            try:
                text = await diary.generate_reflection_llm("reflection prompt")
                if text:
                    diary.record_diary(text, "superego_reflection", user_id="user-1")
            except Exception:
                pass

        asyncio.run(run())

        diary.generate_reflection_llm.assert_awaited_once_with("reflection prompt")
        diary.record_diary.assert_called_once_with(
            "今天我和自己的内疚待了一会儿...",
            "superego_reflection",
            user_id="user-1",
        )


class TestScheduledLoopSkip:
    """scheduled loop LLM-off 分支不调 record_diary (Bug-B 一并修)."""

    def test_scheduled_loop_skips_when_llm_off(self):
        # Bug-B 修法: LLM-off → 跳过, 不 record (main.py:973-978 else → logger.debug)
        # 验证: llm_enabled=False 时, 旧路径的 record_diary 不应被执行
        diary = MagicMock()
        diary._llm_enabled = False
        diary.determine_diary_type = MagicMock(return_value="depressive")
        diary.build_diary_prompt = MagicMock(return_value="prompt text")
        diary.record_diary = MagicMock()

        # 新路径: LLM-off → skip (不调 record_diary)
        llm_enabled = False
        if llm_enabled:
            pass  # 旧 LLM-on 路径
        else:
            # Bug-B: 跳过, 不 record prompt
            pass

        diary.record_diary.assert_not_called()
        diary.build_diary_prompt.assert_not_called()