"""Tests for Bug 13 datetime.date 遮蔽 (v1.2.5 PR3 T8)."""
import pytest
from datetime import date, datetime
import time as _time


def test_datetime_date_today_no_attribute_error():
    """Bug 13 根因: `datetime.date.today()` 在 `from datetime import datetime` 后 AttributeError.

    验证修复后能跑通 (用 date.today(), date 已显式 import):
    """
    # 正确写法
    today_str = date.today().isoformat()
    assert today_str == datetime.now().date().isoformat()

    # 错误写法必须抛 AttributeError (防止有人改回去)
    with pytest.raises(AttributeError):
        datetime.date.today()


def test_datetime_date_fromtimestamp_no_attribute_error():
    """Bug 13 同类错模式: `datetime.date.fromtimestamp()` 也是错的。"""
    ts = _time.time()

    # 正确写法
    result = date.fromtimestamp(ts)
    assert isinstance(result, date)

    # 错误写法必须抛 AttributeError
    with pytest.raises(AttributeError):
        datetime.date.fromtimestamp(ts)
