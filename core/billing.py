# -*- coding: utf-8 -*-
"""
计费模块：

- 小型车 2 元/小时
- 大型车 4 元/小时
- 不足 1 小时按 1 小时计
- 会员折扣（在 config.MEMBER_DISCOUNT 中调整）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from config import (
    SMALL_CAR_RATE, LARGE_CAR_RATE,
    MEMBER_DISCOUNT, MIN_BILLING_HOURS,
)
from utils.time_utils import hours_for_billing


def compute_fee(vehicle_type: str,
                entry_time: datetime,
                exit_time: datetime,
                member_flag: int = 0,
                member_discount: Optional[float] = None) -> Tuple[float, int, int]:
    """
    返回 (fee, hours, duration_seconds)

    member_discount:
        None  → 使用 config.MEMBER_DISCOUNT（全局默认折扣）
        0~1   → 使用传入值（通常来自 members.discount 字段）
        其他  → 视为非法，回退到全局默认

    ⚠ 早期版本默认值是 1.0，会被 `0 < d <= 1` 判定为合法而直接乘 1.0，
      导致会员折扣完全失效。这里改用 None 表示"未指定"。
    """
    duration = max(0, int((exit_time - entry_time).total_seconds()))
    hours    = hours_for_billing(entry_time, exit_time, MIN_BILLING_HOURS)

    if vehicle_type == "大型车":
        rate = LARGE_CAR_RATE
    else:
        rate = SMALL_CAR_RATE

    base = rate * hours
    if member_flag:
        d = MEMBER_DISCOUNT if member_discount is None else member_discount
        if not (0 < d <= 1.0):
            d = MEMBER_DISCOUNT
        base *= d

    return round(base, 2), hours, duration