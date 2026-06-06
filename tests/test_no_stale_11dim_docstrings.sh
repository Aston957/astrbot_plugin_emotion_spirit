#!/bin/bash
# 验证 emotion_spirit/ 和 main.py 中无 "11 维" / "11维" / "11-dim" / "11dim" 字符串残留
# P0-1c cleanup: 13 维权威集合已确立, 不应再有 11 维文档
#
# 例外 (历史 changelog, 不应改):
# - emotion_spirit/label_mapper.py:9: "原 11 维 autonomy_guard 已删除 (Phase 1.7 design review 决策)"
# - emotion_spirit/relationship_personality.py:34: "之前 hardcoded 11 维 (含 warmth/...)"

set -e

cd "$(dirname "$0")/.."

# 检查 .py 文件 + _conf_schema.json (用户可见的 hint 也应准确)
matches=$(grep -rn "11 维\|11维\|11-dim\|11dim" \
    --include="*.py" \
    --include="_conf_schema.json" \
    emotion_spirit/ main.py _conf_schema.json 2>/dev/null \
    | grep -v "label_mapper.py:9:.*原 11 维 autonomy_guard 已删除" \
    | grep -v "relationship_personality.py:34:.*之前 hardcoded 11 维" || true)

if [ -n "$matches" ]; then
    count=$(echo "$matches" | wc -l)
    echo "[FAIL] Found $count stale '11 维' references:"
    echo "$matches"
    exit 1
fi

echo "[OK] No stale '11 维' references found in source"
