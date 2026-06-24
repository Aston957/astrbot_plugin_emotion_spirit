"""Migration registry — @register_migration decorator + get_migrations."""
from typing import Callable

_REGISTRY: list[tuple[int, int, str, Callable[[dict], dict]]] = []


def register_migration(from_version: int, to_version: int):
    """Decorator to register a config migration rule.

    Args:
        from_version: 源 schema 版本号
        to_version: 目标 schema 版本号 (必须 = from_version + 1)

    Returns:
        Decorator that wraps the function and appends it to the registry.

    Raises:
        ValueError: If to_version != from_version + 1
    """
    if to_version != from_version + 1:
        raise ValueError(
            f"to_version must equal from_version + 1, got {from_version} -> {to_version}"
        )

    def decorator(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        _REGISTRY.append((from_version, to_version, fn.__name__, fn))
        return fn
    return decorator


def get_migrations() -> list[tuple[int, int, str, Callable]]:
    """Return all registered migrations sorted by from_version ascending."""
    return sorted(_REGISTRY, key=lambda x: x[0])


def get_latest_version() -> int:
    """Return the highest to_version among registered rules (= current schema version).

    Returns 0 if no rules are registered.
    """
    if not _REGISTRY:
        return 0
    return max(m[1] for m in _REGISTRY)


def reset_registry() -> None:
    """Clear the registry. Only for tests."""
    _REGISTRY.clear()
