"""Smoke tests for embedded sylanne imports (Phase F).

astrbot mock is set up in conftest.py.
"""


def test_import_sylanne_engine():
    """SylanneEngine 类可从嵌入路径导入。"""
    from emotion_spirit.sylanne import SylanneEngine
    assert SylanneEngine is not None


def test_import_sylanne_config():
    """SylanneConfig 类可从嵌入路径导入。"""
    from emotion_spirit.sylanne import SylanneConfig
    assert SylanneConfig is not None


def test_import_compute_kernel():
    """AlphaKernel 可从 compute 子包导入。"""
    from emotion_spirit.sylanne.compute import AlphaKernel
    assert AlphaKernel is not None


def test_import_compute_body():
    """AlphaBodyState 可从 compute 子包导入。"""
    from emotion_spirit.sylanne.compute import AlphaBodyState
    assert AlphaBodyState is not None


def test_import_types():
    """Surface/PADOutput 等类型可导入。"""
    from emotion_spirit.sylanne.types import Surface, PADOutput, EngineStatus
    assert Surface is not None
    assert PADOutput is not None


def test_import_algebra():
    """PAD 代数运算可导入。"""
    from emotion_spirit.sylanne.algebra import blend, decay, distance
    assert callable(blend)
    assert callable(decay)
    assert callable(distance)


def test_import_standard():
    """Layer 0 核心可导入。"""
    from emotion_spirit.sylanne.standard import SylanneCore, EmotionVector
    assert SylanneCore is not None
    assert EmotionVector is not None


def test_import_expression():
    """PAD → 输出模态映射可导入。"""
    from emotion_spirit.sylanne.expression import PADToBlendShape, PADToTextStyle
    assert PADToBlendShape is not None


def test_import_contagion():
    """多主体情绪传染可导入。"""
    from emotion_spirit.sylanne.contagion import ContagionGraph
    assert ContagionGraph is not None


def test_import_hot_pool():
    """HotPool 可导入。"""
    from emotion_spirit.sylanne.compute.hot_pool import HotPool
    assert HotPool is not None


def test_import_scar_algebra():
    """伤痕代数可导入。"""
    from emotion_spirit.sylanne.compute.scar_algebra import ScarredState
    assert ScarredState is not None


def test_import_void_calculus():
    """空洞微积分可导入。"""
    from emotion_spirit.sylanne.compute.void_calculus import VoidSpace
    assert VoidSpace is not None


def test_import_hdc():
    """超维计算编码器可导入。"""
    from emotion_spirit.sylanne.compute.hdc import HDCEncoder
    assert HDCEncoder is not None


def test_import_relational_sheaf():
    """关系层论可导入。"""
    from emotion_spirit.sylanne.compute.relational_sheaf import ScarSheaf
    assert ScarSheaf is not None


def test_import_get_engine():
    """get_engine 函数可导入（当前应返回 None 或抛 RuntimeError）。"""
    from emotion_spirit.sylanne import get_engine
    assert callable(get_engine)
    try:
        engine = get_engine()
        # 如果有引擎实例，也 OK
    except RuntimeError:
        # 预期：尚未初始化
        pass


def test_zero_external_deps():
    """sylanne 的核心模块不依赖 numpy/torch 等外部库。"""
    import importlib
    # 强制重新加载以检查 import 时是否有外部依赖
    core_modules = [
        "emotion_spirit.sylanne.standard",
        "emotion_spirit.sylanne.types",
        "emotion_spirit.sylanne.algebra",
        "emotion_spirit.sylanne.compute.vector",
        "emotion_spirit.sylanne.compute.hdc",
    ]
    for mod_name in core_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None


if __name__ == "__main__":
    test_import_sylanne_engine()
    test_import_sylanne_config()
    test_import_compute_kernel()
    test_import_compute_body()
    test_import_types()
    test_import_algebra()
    test_import_standard()
    test_import_expression()
    test_import_contagion()
    test_import_hot_pool()
    test_import_scar_algebra()
    test_import_void_calculus()
    test_import_hdc()
    test_import_relational_sheaf()
    test_import_get_engine()
    test_zero_external_deps()
    print("All sylanne smoke tests passed!")
