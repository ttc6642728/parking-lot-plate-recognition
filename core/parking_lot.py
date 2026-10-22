# -*- coding: utf-8 -*-
"""
停车场车位状态管理（封装 DAO + 业务规则）：

- 车位已满 → 入场拦截
- 自动分配车位号
- 入场 / 出场增减 used_spots
"""

from __future__ import annotations

from typing import Tuple

from db.dao import ParkingLotDAO, ParkingRecordDAO
from utils.logger import get_logger

logger = get_logger()


class ParkingLotManager:
    """单例风格，直接使用类方法。"""

    # ------------------------------------------------------------------
    @classmethod
    def status(cls) -> dict:
        return ParkingLotDAO.get_status()

    @classmethod
    def is_full(cls) -> bool:
        return ParkingLotDAO.is_full()

    @classmethod
    def remaining(cls) -> int:
        s = cls.status()
        return max(0, s["total_spots"] - s["used_spots"])

    @classmethod
    def total(cls) -> int:
        return cls.status()["total_spots"]

    @classmethod
    def used(cls) -> int:
        return cls.status()["used_spots"]

    # ------------------------------------------------------------------
    @classmethod
    def allocate_spot(cls) -> Tuple[str, bool]:
        """分配车位号（A001 起递增）。

        返回 (spot_no, success)；无可用车位时返回 ("", False)。
        """
        # 已占用 spot_no 集合（包含未出场）
        used_rows = ParkingRecordDAO.search(only_unpaid=True, limit=10000)
        # 注意：search() 返回 dict 列表，取值用 ["spot_no"]
        used = {r["spot_no"] for r in used_rows}

        total = cls.total()
        for i in range(1, total + 1):
            spot = f"A{i:03d}"
            if spot not in used:
                return spot, True

        return "", False

    # ------------------------------------------------------------------
    @classmethod
    def on_entry_success(cls) -> None:
        ParkingLotDAO.inc_used(+1)

    @classmethod
    def on_exit_success(cls) -> None:
        ParkingLotDAO.inc_used(-1)