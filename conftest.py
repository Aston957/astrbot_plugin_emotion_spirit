"""测试 root conftest (Phase 4 C4 cleanup).

main.py 现在用绝对导入 (`from emotion_spirit.X`), emotion_spirit 是已 installed 的
package (per C2 packaging), 无需合成包 hack。main.py 在测试中可直接被 import。
"""
