"""v1.2 ForceState 注入验证脚本 (非 pytest, 一次性手动跑)。

目的: 直接验证 _format_force_state_block + build_diary_prompt() 真的把 ForceState
注入了 diary prompt。绕开 AstrBot + LLM 路径, 0 重启, 秒级确证。

用法: python tests/manual_v12_force_state_injection.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# 加 src 到 path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from emotion_spirit.output.diary_writer import (
    DiaryWriter,
    _format_force_state_block,
)
from emotion_spirit.regulation.force_dynamics import ForceDynamics


def make_diary_with(force_dynamics, labels):
    """构造一个最小可用的 DiaryWriter 实例 (mock 非核心依赖)。"""
    diary = DiaryWriter(
        pool=MagicMock(warm_for=lambda uid: []),
        patterns=MagicMock(get_patterns=lambda: []),
        signals=MagicMock(),
        alignment=MagicMock(get_score=lambda: 0.0),
        conscience=MagicMock(get_pressure=lambda: 0.0),
    )
    diary.configure_force_dynamics(force_dynamics, labels)
    return diary


def main():
    print("=" * 70)
    print("v1.2 ForceState 注入验证")
    print("=" * 70)

    # 1. 直接调 helper 函数
    print("\n[1] _format_force_state_block() 直接调用 (force_dynamics=None 应返空):")
    out = _format_force_state_block(None, {"mbti": "ENFP"})
    print(f"  -> {repr(out)}")
    assert out == "", f"FAIL: None force_dynamics 应返空, got {out!r}"
    print("  [OK] None force_dynamics 返空 (无注入)")

    print("\n[2] _format_force_state_block() 直接调用 (labels=None 应返空):")
    fd = ForceDynamics()
    out = _format_force_state_block(fd, None)
    print(f"  -> {repr(out)}")
    assert out == "", f"FAIL: None labels 应返空, got {out!r}"
    print("  [OK] None labels 返空 (无注入)")

    # 2. 真实计算 (5 个测试 labels — 全部 KB valid)
    # 注意: emotion_style 合法值 = 压抑型/表达型/波动型/稳定型 (无"混合型"/"内敛型")
    #       time_focus   合法值 = 活在过去/活在当下/活在未来 (无"着眼未来")
    #       mbti 4-letter OK (compute_baseline_from_labels 特殊处理)
    test_labels = [
        ("ENFP-小芙(production)", {"mbti": "ENFP", "attachment": "焦虑型",
                                    "emotion_style": "表达型", "conflict_style": "合作型",
                                    "time_focus": "活在当下"}),
        ("ISTJ(default)", {"mbti": "ISTJ", "attachment": "安全型",
                           "emotion_style": "稳定型", "conflict_style": "合作型",
                           "time_focus": "活在当下"}),
        ("INFP", {"mbti": "INFP", "attachment": "安全型",
                  "emotion_style": "稳定型",
                  "conflict_style": "回避型", "time_focus": "活在未来"}),
    ]

    print("\n[3] _format_force_state_block() 真实 ForceState 计算:")
    for name, labels in test_labels:
        out = _format_force_state_block(fd, labels)
        print(f"  [{name}] {out}")
        assert out, f"FAIL: {name} 应有输出"
        assert "力学基调" in out, f"FAIL: 缺 '力学基调' 关键字"
    print("  [OK] 3 个 persona labels 全部产出 ForceState 行")

    # 3. build_diary_prompt() 端到端拼装
    print("\n[4] build_diary_prompt() 端到端 (ENFP, 无 signals):")
    diary = make_diary_with(fd, test_labels[0][1])
    prompt = diary.build_diary_prompt("停滞型")
    print("--- prompt start ---")
    print(prompt)
    print("--- prompt end ---")
    assert "力学基调" in prompt, "FAIL: prompt 缺 '力学基调' 行"
    assert "三元力学基调" in prompt, "FAIL: prompt 缺 '三元力学基调' 引导句"
    print("  [OK] prompt 含 ForceState 注入")

    # 4. 验证缺 force_dynamics 时的零回归
    print("\n[5] build_diary_prompt() 无 force_dynamics 注入 (回归测试):")
    diary_no_fd = DiaryWriter(
        pool=MagicMock(warm_for=lambda uid: []),
        patterns=MagicMock(get_patterns=lambda: []),
        signals=MagicMock(),
        alignment=MagicMock(get_score=lambda: 0.0),
        conscience=MagicMock(get_pressure=lambda: 0.0),
    )
    # 不调 configure_force_dynamics
    prompt_no_fd = diary_no_fd.build_diary_prompt("停滞型")
    assert "力学基调" not in prompt_no_fd, "FAIL: 无 fd 时不应有 ForceState 行"
    print("  [OK] 无 fd 注入 -> prompt 无 ForceState 行 (零回归路径 OK)")

    # 5. 验证 build_superego_reflection_prompt 也注入
    print("\n[6] build_superego_reflection_prompt() 端到端 (ENFP):")
    refl_prompt = diary.build_superego_reflection_prompt(
        tension_type="guilt",
        conflict_values=["relational_autonomy", "exploration_openness"],
    )
    assert "力学基调" in refl_prompt, "FAIL: 反思 prompt 缺 ForceState"
    print("  [OK] 反思 prompt 也含 ForceState 注入")

    print("\n" + "=" * 70)
    print("[PASS] 全部 6 项验证通过 -- v1.2 ForceState 注入工作正常, 无回归")
    print("=" * 70)


if __name__ == "__main__":
    main()