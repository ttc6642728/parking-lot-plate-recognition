# -*- coding: utf-8 -*-
"""停车场车位状态 DAO。"""

from __future__ import annotations

from db.database import query_one, exec_sql


class ParkingLotDAO:
    TABLE = "parking_lot"

    @classmethod
    def get_status(cls) -> dict:
        row = query_one(f"SELECT * FROM {cls.TABLE} WHERE id = 1")
        if row is None:
            return {"total_spots": 0, "used_spots": 0}
        return row

    @classmethod
    def set_total(cls, total: int) -> None:
        exec_sql(
            f"UPDATE {cls.TABLE} SET total_spots = ? WHERE id = 1",
            (total,),
        )

    @classmethod
    def inc_used(cls, delta: int = 1) -> None:
        """调整已用车位。"""
        exec_sql(
            f"UPDATE {cls.TABLE} "
            "SET used_spots = MAX(0, used_spots + ?) "
            "WHERE id = 1",
            (delta,),
        )

    @classmethod
    def is_full(cls) -> bool:
        row = cls.get_status()
        return row["used_spots"] >= row["total_spots"]