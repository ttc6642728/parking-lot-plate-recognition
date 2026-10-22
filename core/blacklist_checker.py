# -*- coding: utf-8 -*-
"""
黑名单匹配工具。
"""

from __future__ import annotations

from typing import Optional

from db.dao import BlacklistDAO
from utils.logger import get_logger

logger = get_logger()


class BlacklistChecker:
    @staticmethod
    def match(plate_no: str) -> Optional[dict]:
        if not plate_no:
            return None
        return BlacklistDAO.contains(plate_no)

    @staticmethod
    def warn(plate_no: str) -> Optional[str]:
        row = BlacklistChecker.match(plate_no)
        if not row:
            return None
        msg = f"⚠ 黑名单车辆：{plate_no} ({row.get('reason') or '无'})"
        logger.warning(msg)
        return msg