# -*- coding: utf-8 -*-
"""
数据模型：与数据库表一一对应的 dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id:        int
    username:  str
    role:      str
    real_name: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class ParkingRecord:
    id:           int
    plate_no:     str
    vehicle_type: str
    spot_no:      str
    entry_time:   datetime
    exit_time:    Optional[datetime] = None
    duration_sec: Optional[int]      = None
    fee:          Optional[float]    = None
    member_flag:  int                = 0
    operator_id:  Optional[int]      = None
    note:         Optional[str]      = None
    created_at:   Optional[str]      = None


@dataclass
class Member:
    id:         int
    plate_no:   str
    name:       Optional[str] = None
    phone:      Optional[str] = None
    valid_from: str = ""
    valid_to:   str = ""
    discount:   float = 1.0
    created_at: Optional[str] = None


@dataclass
class Blacklist:
    id:         int
    plate_no:   str
    reason:     Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class ParkingLot:
    id:          int   = 1
    total_spots: int   = 0
    used_spots:  int   = 0

    @property
    def remaining(self) -> int:
        return max(0, self.total_spots - self.used_spots)