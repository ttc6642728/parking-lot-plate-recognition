# -*- coding: utf-8 -*-
"""
OCR 识别（pytesseract）。
针对车牌场景做了些预处理以提升识别率。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

from config import TESSERACT_CMD, TESSERACT_LANG, TESSDATA_DIR
from utils.logger import get_logger

logger = get_logger()


# 中文字符：直辖市/省简称 + 字母 + 字母/数字
_PLATE_CHARS_RE = re.compile(
    r"[" + "".join([
            "京", "沪", "津", "渝", "冀", "豫", "云", "辽", "黑", "湘",
            "皖", "鲁", "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋",
            "蒙", "陕", "吉", "闽", "贵", "粤", "青", "藏", "川", "宁",
            "琼",
        ]) + r"]"
    r"|[A-Z]|[0-9]"
)


def _preprocess_for_ocr(plate_img: np.ndarray) -> np.ndarray:
    """
    针对车牌的预处理：
    - 放大（车牌区域通常较小）
    - 转灰度
    - 自适应阈值二值化
    """
    if plate_img is None or plate_img.size == 0:
        return plate_img

    h, w = plate_img.shape[:2]
    # 拉大
    scale = 2.0 if max(h, w) < 120 else 1.0
    if scale != 1.0:
        plate_img = cv2.resize(
            plate_img, (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_CUBIC,
        )

    if len(plate_img.shape) == 3:
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = plate_img

    # 自适应阈值
    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10,
    )
    return bw


class OcrRecognizer:
    """pytesseract 简单封装（含环境自检）。"""

    def __init__(self, tesseract_cmd: str = TESSERACT_CMD,
                 lang: str = TESSERACT_LANG,
                 tessdata_dir: str = TESSDATA_DIR):
        self.tesseract_cmd = tesseract_cmd
        self.lang          = lang
        self.available     = False

        # 1) 告诉 Tesseract 去哪找语言数据（tessdata）
        if tessdata_dir and Path(tessdata_dir).exists():
            os.environ.setdefault("TESSDATA_PREFIX", tessdata_dir)

        try:
            import pytesseract
            if tesseract_cmd and tesseract_cmd != "tesseract":
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

            v = pytesseract.get_tesseract_version()

            # 真实自检：能报版本 ≠ 能识别。
            # 常见坑：tessdata 路径含中文时空闲版本正常，但识别时才抛
            # "filesystem error: Cannot convert character sequence"。
            probe = np.full((40, 120), 255, dtype=np.uint8)
            pytesseract.image_to_string(probe, config="--psm 7", lang=lang)

            self.available = True
            logger.info(f"Tesseract 就绪，版本：{v}，语言：{lang}")
        except Exception as e:
            self.available = False
            logger.warning(f"Tesseract 不可用：{e}")
            logger.warning(f"  → 请检查：{tesseract_cmd} 是否存在且能运行")
            logger.warning("  → 若提示 Illegal byte sequence，说明安装路径含中文，"
                           "请改装到纯英文路径")

    # ------------------------------------------------------------------
    def recognize(self, plate_img: np.ndarray) -> Tuple[str, float]:
        """返回 (text, confidence)。"""
        if plate_img is None or plate_img.size == 0:
            return "", 0.0
        if not self.available:
            # Tesseract 不可用 → 直接返回空，交由上层演示模式兜底
            return "", 0.0

        import pytesseract

        processed = _preprocess_for_ocr(plate_img)

        # 1) 优先用车牌白名单字符
        try:
            data = pytesseract.image_to_data(
                processed,
                config="--psm 7 -c tessedit_char_whitelist="
                       + "ABCDEFGHJKLMNPQRSTUVWXYZ"
                       "0123456789"
                       "京沪津渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼",
                lang=self.lang,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            logger.warning(f"OCR 失败：{e}")
            return "", 0.0

        text = "".join(data.get("text", [])).strip()
        # 取字符位置平均置信度
        confs = [int(c) for c in data.get("conf", []) if c not in ("", "-1")]
        conf  = (sum(confs) / len(confs) / 100.0) if confs else 0.0

        # 2) 兜底：如果没识别到，尝试完整 image_to_string
        if not text:
            try:
                text = pytesseract.image_to_string(
                    processed,
                    config="--psm 7",
                    lang=self.lang,
                ).strip()
            except Exception:
                pass

        # 过滤非车牌字符
        chars = _PLATE_CHARS_RE.findall(text.upper())
        text  = "".join(chars)

        return text, float(conf)