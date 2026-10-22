# -*- coding: utf-8 -*-
"""
报表导出：把 DataFrame / list[dict] 导出为 .xlsx / .csv。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def export_to_excel(rows: Iterable[dict], columns: list[str],
                    file_path: str | Path,
                    sheet_name: str = "Sheet1") -> str:
    """导出为 Excel (.xlsx)，返回写入的文件路径。"""
    df = pd.DataFrame(rows, columns=columns)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, sheet_name=sheet_name[:31])
    return str(path)


def export_to_csv(rows: Iterable[dict], columns: list[str],
                  file_path: str | Path,
                  encoding: str = "utf-8-sig") -> str:
    """导出为 CSV（默认 utf-8-sig，Excel 打开不乱码）。"""
    df = pd.DataFrame(rows, columns=columns)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=encoding)
    return str(path)