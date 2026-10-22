# -*- coding: utf-8 -*-
"""
统一日志封装：
- 优先使用 loguru（结构更友好）；
- 若未安装，则自动回退到标准 logging，依然能写入 logs/app.log。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from config import LOG_FILE


def _build_std_logging() -> logging.Logger:
    """标准库 logging 实现，作为 loguru 不可用时的兜底。"""
    logger = logging.getLogger("parking_app")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:                       # 避免重复绑定
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 文件
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def get_logger():
    """返回一个 logger-like 对象，info/warning/error 三个方法即可。"""
    try:
        from loguru import logger as _logger  # type: ignore
        # 移除默认 handler，添加自定义
        _logger.remove()
        _logger.add(sys.stdout,
                    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                           "<level>{level: <7}</level> | {message}",
                    level="INFO")
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _logger.add(str(LOG_FILE),
                    encoding="utf-8",
                    format="{time:YYYY-MM-DD HH:mm:ss} | "
                           "{level: <7} | {message}",
                    level="INFO",
                    rotation="5 MB",
                    retention="14 days")
        return _logger
    except ImportError:
        return _build_std_logging()