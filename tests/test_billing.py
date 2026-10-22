# -*- coding: utf-8 -*-
"""计费规则测试。

重点覆盖曾经的 bug：会员折扣参数默认值为 1.0，
恰好满足 `0 < d <= 1` 的合法性判断，导致折扣被乘 1.0 而完全失效。
"""

from datetime import datetime, timedelta

import pytest

from config import LARGE_CAR_RATE, MEMBER_DISCOUNT, SMALL_CAR_RATE
from core.billing import compute_fee

T0 = datetime(2026, 1, 1, 8, 0, 0)


def _fee(vehicle="小型车", hours=1.0, member=0, discount=None):
    end = T0 + timedelta(hours=hours)
    return compute_fee(vehicle, T0, end, member_flag=member,
                       member_discount=discount)


def test_small_car_rate():
    fee, hours, secs = _fee("小型车", 3)
    assert hours == 3
    assert secs == 3 * 3600
    assert fee == round(SMALL_CAR_RATE * 3, 2)


def test_large_car_rate():
    fee, hours, _ = _fee("大型车", 2)
    assert fee == round(LARGE_CAR_RATE * 2, 2)


def test_minimum_one_hour():
    fee, hours, _ = _fee("小型车", 0.1)
    assert hours == 1
    assert fee == SMALL_CAR_RATE


def test_partial_hour_rounds_up():
    """超 1 小时零 1 秒应按 2 小时计。"""
    _, hours, _ = _fee("小型车", 1 + 1 / 3600)
    assert hours == 2


def test_zero_duration_still_bills_minimum():
    fee, hours, secs = compute_fee("小型车", T0, T0)
    assert secs == 0
    assert hours == 1
    assert fee == SMALL_CAR_RATE


def test_non_member_no_discount():
    fee, _, _ = _fee("小型车", 3)
    assert fee == 6.0


def test_member_explicit_discount_applied():
    fee, _, _ = _fee("小型车", 3, member=1, discount=0.8)
    assert fee == 4.8


def test_member_default_discount_applied():
    """回归用例：不传 discount 时必须回退到 config.MEMBER_DISCOUNT。"""
    fee, _, _ = _fee("小型车", 3, member=1)
    assert fee == round(6.0 * MEMBER_DISCOUNT, 2)
    assert fee < 6.0, "会员折扣未生效"


@pytest.mark.parametrize("bad_discount", [0, -0.5, 1.5, None])
def test_illegal_discount_falls_back(bad_discount):
    if bad_discount is None:
        pytest.skip("None 表示走默认值，由上一个用例覆盖")
    fee, _, _ = _fee("小型车", 3, member=1, discount=bad_discount)
    assert fee == round(6.0 * MEMBER_DISCOUNT, 2)
