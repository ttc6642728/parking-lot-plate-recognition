# -*- coding: utf-8 -*-
"""车位分配与计数测试。

回归重点：allocate_spot 在无车位时曾返回 3 元组
("", False, "no_spot")，而调用方按 2 元组解包，直接 ValueError 崩溃。
"""

from datetime import datetime, timedelta

from core import ParkingLotManager
from db.dao import ParkingLotDAO, ParkingRecordDAO


def test_allocate_first_spot(temp_db):
    spot, ok = ParkingLotManager.allocate_spot()
    assert ok is True
    assert spot == "A001"


def test_allocate_skips_occupied(temp_db):
    ParkingRecordDAO.insert_entry("京A12345", "小型车", "A001", datetime.now())
    spot, ok = ParkingLotManager.allocate_spot()
    assert ok is True
    assert spot == "A002"


def test_allocate_returns_two_tuple_when_full(temp_db):
    """核心回归：满位时必须返回 2 元组，调用方可安全解包。"""
    ParkingLotDAO.set_total(1)
    ParkingRecordDAO.insert_entry("京A12345", "小型车", "A001", datetime.now())

    result = ParkingLotManager.allocate_spot()

    assert isinstance(result, tuple)
    assert len(result) == 2, f"返回值元组长度应为 2，实际 {len(result)}"
    spot, ok = result
    assert spot == ""
    assert ok is False


def test_entry_exit_updates_used_spots(temp_db):
    before = ParkingLotManager.used()
    ParkingLotManager.on_entry_success()
    assert ParkingLotManager.used() == before + 1
    ParkingLotManager.on_exit_success()
    assert ParkingLotManager.used() == before


def test_used_spots_never_negative(temp_db):
    ParkingLotDAO.inc_used(-5)
    assert ParkingLotManager.used() == 0


def test_is_full(temp_db):
    ParkingLotDAO.set_total(1)
    assert ParkingLotManager.is_full() is False
    ParkingLotManager.on_entry_success()
    assert ParkingLotManager.is_full() is True


def test_count_in_lot_matches_records(temp_db):
    now = datetime.now()
    ParkingRecordDAO.insert_entry("京A00001", "小型车", "A001", now)
    ParkingRecordDAO.insert_entry("京A00002", "小型车", "A002", now)
    rid = ParkingRecordDAO.insert_entry("京A00003", "小型车", "A003", now)
    ParkingRecordDAO.update_exit(rid, now + timedelta(hours=1), 3600, 2.0)

    assert ParkingRecordDAO.count_in_lot() == 2
