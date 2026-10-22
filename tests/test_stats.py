# -*- coding: utf-8 -*-
"""统计口径与 DAO 返回类型测试。

回归重点：
1. daily_stats 必须让"车次"（按入场）与"营收"（按出场）对齐到同一天，
   早期界面上一处按入场算车次、另一处按出场算营收，两个数字始终对不上；
2. query_all / query_one 必须返回 dict，否则 UI 层调用 .get() 会崩。
"""

from datetime import datetime, timedelta

from db.dao import ParkingRecordDAO


def _today():
    """返回 (start, end, base)，时间全部落在今天，避免跨午夜导致断言不稳。"""
    day = datetime.now().strftime("%Y-%m-%d")
    start = f"{day} 00:00:00"
    end = f"{day} 23:59:59"
    base = datetime.strptime(f"{day} 01:00:00", "%Y-%m-%d %H:%M:%S")
    return start, end, base


def test_query_returns_dict(temp_db):
    """sqlite3.Row 没有 .get()，数据出口必须统一转 dict。"""
    _, _, base = _today()
    ParkingRecordDAO.insert_entry("京A12345", "小型车", "A001", base)
    row = ParkingRecordDAO.list_all(limit=1)[0]

    assert isinstance(row, dict)
    assert row.get("plate_no") == "京A12345"


def test_daily_stats_counts_and_revenue_aligned(temp_db):
    start, end, base = _today()
    rid = ParkingRecordDAO.insert_entry("京A11111", "小型车", "A001", base)
    ParkingRecordDAO.update_exit(rid, base + timedelta(hours=2), 7200, 6.0)

    rows = ParkingRecordDAO.daily_stats(start, end)

    assert len(rows) == 1
    assert rows[0]["cnt"] == 1
    assert rows[0]["revenue"] == 6.0


def test_daily_stats_pending_vehicle_has_zero_revenue(temp_db):
    """在场未结算的车：计入车次，但营收为 0。"""
    start, end, base = _today()
    ParkingRecordDAO.insert_entry("京A22222", "小型车", "A001", base)

    rows = ParkingRecordDAO.daily_stats(start, end)

    assert rows[0]["cnt"] == 1
    assert rows[0]["revenue"] == 0


def test_daily_stats_totals_match_summary(temp_db):
    """界面汇总用的 total(cnt) 与 total(revenue) 必须来自同一份数据。"""
    start, end, base = _today()
    for i in range(3):
        rid = ParkingRecordDAO.insert_entry(
            f"京A3330{i}", "小型车", f"A00{i}", base + timedelta(minutes=i))
        ParkingRecordDAO.update_exit(
            rid, base + timedelta(hours=3), 10800, 6.0)

    rows = ParkingRecordDAO.daily_stats(start, end)

    assert sum(int(r["cnt"]) for r in rows) == 3
    assert round(sum(float(r["revenue"]) for r in rows), 2) == 18.0


def test_daily_stats_empty_range(temp_db):
    rows = ParkingRecordDAO.daily_stats(
        "2000-01-01 00:00:00", "2000-01-02 00:00:00")
    assert rows == []


def test_sum_revenue_only_counts_settled(temp_db):
    start, end, base = _today()
    ParkingRecordDAO.insert_entry("京A44444", "小型车", "A001", base)

    assert ParkingRecordDAO.sum_revenue(start, end) == 0.0
