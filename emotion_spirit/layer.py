"""4 层架构代码层强制 (Phase B, P3-3)。

装饰器:
  - per_user_only: 强制 caller 提供非空 string user_id
  - global_only: 拒绝方法定义包含 user_id 参数

异常: LayerViolationError (RuntimeError 子类)

设计选择: 装饰器使用 inspect.signature.bind 同时支持位置参数和 kwargs
(向后兼容现有 caller: tracker.get_intimacy("alice", "xiaofu"))
而非把 user_id 强制为 kwarg-only (会破坏所有现有 caller)。
"""
from __future__ import annotations

import inspect
from functools import wraps



__all__ = [
    "LayerViolationError",
    "per_user_only",
    "global_only",
]

class LayerViolationError(RuntimeError):
    """跨层访问错误 (Layer 2 → Layer 3 等)。"""
    pass


def per_user_only(method):
    """per-user 方法标记: 强制 caller 提供非空 string user_id。

    支持位置参数和 kwargs 调用方式:
        @per_user_only
        def get(self, user_id: str, persona: str = "default") -> float: ...

        obj.get("alice")           # OK
        obj.get("alice", "xiaofu") # OK
        obj.get(user_id="alice")   # OK
        obj.get()                  # TypeError
        obj.get("")                # TypeError
        obj.get(None)              # TypeError
        obj.get(42)                # TypeError
    """
    sig = inspect.signature(method)

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        # bind 失败也抛 TypeError — 区分"缺 user_id"和"其他参数错"
        try:
            bound = sig.bind(self, *args, **kwargs)
        except TypeError as bind_err:
            # 试图在缺 user_id 的情况下给出友好错误信息
            try:
                probe = sig.bind_partial(self, *args, **kwargs)
            except TypeError:
                raise bind_err
            if "user_id" not in probe.arguments:
                raise TypeError(
                    f"{method.__name__} requires user_id (per-user only)"
                ) from bind_err
            raise
        bound.apply_defaults()
        if "user_id" not in bound.arguments:
            raise TypeError(
                f"{method.__name__} requires user_id (per-user only)"
            )
        user_id = bound.arguments["user_id"]
        if not isinstance(user_id, str) or not user_id:
            raise TypeError(
                f"{method.__name__} requires non-empty str user_id (got {user_id!r})"
            )
        return method(self, *args, **kwargs)

    return wrapper


def global_only(method):
    """global-only 方法标记: 拒绝方法定义包含 user_id 参数。

    在类定义时检查, 如果方法签名有 user_id 参数, 抛 TypeError。
    """
    sig = inspect.signature(method)
    if "user_id" in sig.parameters:
        raise TypeError(
            f"{method.__name__} is global-only, no user_id allowed"
        )
    return method
