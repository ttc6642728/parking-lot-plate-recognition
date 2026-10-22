# -*- coding: utf-8 -*-
"""停车记录 DAO。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from db.database import query_all, query_one, exec_sql


class ParkingRecordDAO:
    TABLE = "parking_records"

    # ------------------------------------------------------------------
    # 写入 / 修改
    # ------------------------------------------------------------------
    @classmethod
    def insert_entry(cls, plate_no: str, vehicle_type: str,
                     spot_no: str, entry_time: datetime,
                     member_flag: int = 0,
                     operator_id: Optional[int] = None,
                     note: str = "") -> int:
        cur = exec_sql(
            f"INSERT INTO {cls.TABLE}("
            "  plate_no, vehicle_type, spot_no, entry_time,"
            "  member_flag, operator_id, note"
            ") VALUES(?,?,?,?,?,?,?)",
            (plate_no, vehicle_type, spot_no,
             entry_time.strftime("%Y-%m-%d %H:%M:%S"),
             member_flag, operator_id, note),
        )
        return cur.lastrowid

    @classmethod
    def update_exit(cls, record_id: int, exit_time: datetime,
                    duration_sec: int, fee: float) -> None:
        exec_sql(
            f"UPDATE {cls.TABLE} "
            "SET exit_time = ?, duration_sec = ?, fee = ? "
            "WHERE id = ?",
            (exit_time.strftime("%Y-%m-%d %H:%M:%S"),
             duration_sec, fee, record_id),
        )

    @classmethod
    def update_fields(cls, record_id: int, **fields) -> None:
        """通用更新（仅支持白名单字段，避免 SQL 注入）。"""
        allowed = {"plate_no", "vehicle_type", "spot_no",
                   "entry_time", "exit_time", "duration_sec",
                   "fee", "member_flag", "operator_id", "note"}
        cols = []
        vals = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k in ("entry_time", "exit_time") and isinstance(v, datetime):
                v = v.strftime("%Y-%m-%d %H:%M:%S")
            cols.append(f"{k} = ?")
            vals.append(v)
        if not cols:
            return
        vals.append(record_id)
        sql = f"UPDATE {cls.TABLE} SET {', '.join(cols)} WHERE id = ?"
        exec_sql(sql, tuple(vals))

    @classmethod
    def delete(cls, record_id: int) -> None:
        exec_sql(f"DELETE FROM {cls.TABLE} WHERE id = ?", (record_id,))

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @classmethod
    def get(cls, record_id: int) -> Optional[dict]:
        return query_one(
            f"SELECT * FROM {cls.TABLE} WHERE id = ?",
            (record_id,),
        )

    @classmethod
    def list_all(cls, limit: int = 1000) -> list[dict]:
        return query_all(
            f"SELECT * FROM {cls.TABLE} ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    @classmethod
    def list_unpaid_by_plate(cls, plate_no: str) -> Optional[dict]:
        """车牌未结算（在场）的最近一条记录。"""
        return query_one(
            f"SELECT * FROM {cls.TABLE} "
            "WHERE plate_no = ? AND exit_time IS NULL "
            "ORDER BY entry_time DESC LIMIT 1",
            (plate_no,),
        )

    @classmethod
    def search(cls, plate_no: Optional[str] = None,
               start: Optional[str] = None, end: Optional[str] = None,
               only_unpaid: bool = False,
               limit: int = 1000) -> list[dict]:
        """条件查询。"""
        where = []
        params: list = []
        if plate_no:
            where.append("plate_no LIKE ?")
            params.append(f"%{plate_no}%")
        if start:
            where.append("entry_time >= ?")
            params.append(start)
        if end:
            where.append("entry_time <= ?")
            params.append(end)
        if only_unpaid:
            where.append("exit_time IS NULL")
        sql = f"SELECT * FROM {cls.TABLE}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return query_all(sql, tuple(params))

    @classmethod
    def count_in_lot(cls) -> int:
        row = query_one(
            f"SELECT COUNT(*) AS c FROM {cls.TABLE} WHERE exit_time IS NULL"
        )
        return int(row["c"]) if row else 0

    @classmethod
    def sum_revenue(cls, start: str, end: str) -> float:
        row = query_one(
            f"SELECT COALESCE(SUM(fee), 0) AS s FROM {cls.TABLE} "
            "WHERE exit_time IS NOT NULL AND exit_time BETWEEN ? AND ?",
            (start, end),
        )
        return float(row["s"]) if row else 0.0

    @classmethod
    def count_by_date(cls, start: str, end: str) -> list[dict]:
        """按入场日期分组统计车流。"""
        return query_all(
            f"SELECT substr(entry_time, 1, 10) AS date, "
            "       COUNT(*) AS cnt, "
            "       COALESCE(SUM(fee), 0) AS revenue "
            f"FROM {cls.TABLE} "
            "WHERE entry_time BETWEEN ? AND ? "
            "GROUP BY substr(entry_time, 1, 10) "
            "ORDER BY date ASC",
            (start, end),
        )

    @classmethod
    def daily_stats(cls, start: str, end: str) -> list[dict]:
        """
        按天统计车流与营收，两条口径对齐到同一个日期轴上。

        口径说明：
            车流 cnt     —— 按 **entry_time** 统计当天入场车次
            营收 revenue —— 按 **exit_time** 统计当天结算金额

        ⚠ 早期版本在界面上一处用 count_by_date（按入场）算车次，
          另一处用 sum_revenue（按出场）算营收，导致两个数字对不上；
          跨天停车时费用还会被算到错误的日期。
          这里用 FULL JOIN 的等价写法把两张汇总表按日期对齐。
        """
        sql = f"""
            SELECT d.date                        AS date,
                   COALESCE(e.cnt, 0)            AS cnt,
                   ROUND(COALESCE(x.revenue, 0), 2) AS revenue
              FROM (
                    SELECT substr(entry_time, 1, 10) AS date
                      FROM {cls.TABLE}
                     WHERE entry_time BETWEEN ? AND ?
                    UNION
                    SELECT substr(exit_time, 1, 10) AS date
                      FROM {cls.TABLE}
                     WHERE exit_time IS NOT NULL
                       AND exit_time BETWEEN ? AND ?
                   ) AS d
              LEFT JOIN (
                    SELECT substr(entry_time, 1, 10) AS date,
                           COUNT(*)                  AS cnt
                      FROM {cls.TABLE}
                     WHERE entry_time BETWEEN ? AND ?
                     GROUP BY substr(entry_time, 1, 10)
                   ) AS e ON e.date = d.date
              LEFT JOIN (
                    SELECT substr(exit_time, 1, 10) AS date,
                           SUM(COALESCE(fee, 0))    AS revenue
                      FROM {cls.TABLE}
                     WHERE exit_time IS NOT NULL
                       AND exit_time BETWEEN ? AND ?
                     GROUP BY substr(exit_time, 1, 10)
                   ) AS x ON x.date = d.date
             ORDER BY d.date ASC
        """
        return query_all(sql, (start, end, start, end, start, end, start, end))