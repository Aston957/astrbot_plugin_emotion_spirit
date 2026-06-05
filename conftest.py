"""测试配置：让 main.py 的相对导入能正常工作。

main.py 顶层有 `from .emotion_spirit.store import ...` 等相对导入，
这要求 main 必须是某个包的一部分。直接 `from main import ...` 会失败。

解决：在 sys.modules 中注入一个合成的包，把 main.py 作为子模块加载。
"""

import sys
import importlib.util
from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent
_PKG_NAME = "_emotion_spirit_plugin_for_tests"


def _ensure_main_module() -> None:
    if "main" in sys.modules:
        return

    # 1. 创建/获取合成包
    if _PKG_NAME not in sys.modules:
        synthetic = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(
                _PKG_NAME, loader=None, is_package=True,
            )
        )
        synthetic.__path__ = [str(_PLUGIN_DIR)]
        sys.modules[_PKG_NAME] = synthetic

    # 2. 把 emotion_spirit 子包也注册到合成包名下
    if "emotion_spirit" in sys.modules:
        sys.modules[f"{_PKG_NAME}.emotion_spirit"] = sys.modules["emotion_spirit"]

    # 3. 加载 main.py
    main_path = _PLUGIN_DIR / "main.py"
    spec = importlib.util.spec_from_file_location(
        "main", main_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec for {main_path}")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = _PKG_NAME
    sys.modules["main"] = module
    spec.loader.exec_module(module)


_ensure_main_module()
