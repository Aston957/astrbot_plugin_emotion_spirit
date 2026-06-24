"""Tests for migration registry."""
from emotion_spirit.migrations.registry import (
    register_migration,
    get_migrations,
    get_latest_version,
)


def test_register_single_migration():
    """Register a single migration, retrieve via get_migrations."""
    @register_migration(from_version=1, to_version=2)
    def my_migration(config):
        return config

    migrations = get_migrations()
    # Filter to only this test's migration (other tests may have registered too)
    matching = [m for m in migrations if m[2] == "my_migration"]
    assert len(matching) == 1
    assert matching[0][0] == 1
    assert matching[0][1] == 2


def test_get_latest_version_returns_max_to_version():
    """get_latest_version returns the max to_version among registered rules."""
    @register_migration(from_version=10, to_version=11)
    def another_migration(config):
        return config

    assert get_latest_version() >= 11


def test_to_version_must_equal_from_plus_one():
    """Decorating with non-sequential versions raises ValueError."""
    import pytest
    with pytest.raises(ValueError, match="to_version must equal from_version \\+ 1"):
        register_migration(from_version=5, to_version=10)(lambda c: c)


def test_get_migrations_sorted_by_from_version():
    """get_migrations returns rules sorted by from_version ascending."""
    @register_migration(from_version=20, to_version=21)
    def late_migration(config):
        return config
    @register_migration(from_version=15, to_version=16)
    def mid_migration(config):
        return config

    all_migrations = get_migrations()
    from_versions = [m[0] for m in all_migrations]
    assert from_versions == sorted(from_versions)
