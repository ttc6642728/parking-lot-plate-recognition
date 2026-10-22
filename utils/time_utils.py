# -*- coding: utf-8 -*-
"""
时间工具：格式化、解析、时长计算。
"""

from datetime import datetime, timedelta
from typing import Union


_FMT = "%Y-%m-%d %H:%M:%S"


def fmt_dt(dt: Union[datetime, None]) -> str:
    """datetime → 'YYYY-MM-DD HH:MM:SS'，None 返回空串。"""
    if dt is None:
        return ""
    return dt.strftime(_FMT)


def parse_dt(s: Union[str, None]) -> Union[datetime, None]:
    """'YYYY-MM-DD HH:MM:SS' → datetime，失败返回 None。"""
    if not s:
        return None
    try:
        return datetime.strptime(s, _FMT)
    except ValueError:
        return None


def duration_seconds(start: datetime, end: datetime) -> int:
    """时长（秒）。"""
    return max(0, int((end - start).total_seconds()))


def duration_str(start: datetime, end: datetime) -> str:
    """把时长格式化成 'X 小时 Y 分 Z 秒'。"""
    secs = duration_seconds(start, end)
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    if h > 0:
        return f"{h} 小时 {m} 分 {s} 秒"
    if m > 0:
        return f"{m} 分 {s} 秒"
    return f"{s} 秒"


def hours_for_billing(start: datetime, end: datetime,
                      min_hours: int = 1) -> int:
    """计费时长：不足 min_hours 统一按 min_hours 计。"""
    secs = duration_seconds(start, end)
    hours = max(1, (secs + 3599) // 3600)   # 向上取整
    return max(hours, min_hours)


def now() -> datetime:
    return datetime.now()


def add_seconds(dt: datetime, seconds: int) -> datetime:
    return dt + timedelta(seconds=seconds)