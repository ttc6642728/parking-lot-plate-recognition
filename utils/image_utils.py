# -*- coding: utf-8 -*-
"""
图像 / OpenCV 与 PyQt 之间的互转工具。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

# PyQt5 只在需要时再 import，避免仅使用图像工具时硬性依赖
def _qimage_or_none():
    try:
        from PyQt5.QtGui import QImage, QPixmap
        return QImage, QPixmap
    except ImportError:
        return None, None


# ----------------------------------------------------------------------
# OpenCV BGR <-> QImage / QPixmap
# ----------------------------------------------------------------------
def bgr2qpixmap(frame: np.ndarray):
    """OpenCV BGR → QPixmap。"""
    QImage, QPixmap = _qimage_or_none()
    if QImage is None:
        return None
    if frame is None or frame.size == 0:
        return None
    if len(frame.shape) == 2:                               # 灰度
        h, w = frame.shape
        qimg = QImage(frame.data, w, h, w, QImage.Format_Grayscale8)
    else:
        h, w, ch = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def qpixmap2bgr(pixmap):
    """QPixmap → OpenCV BGR ndarray。"""
    if pixmap is None:
        return None
    QImage, _ = _qimage_or_none()
    qimg = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.bits()
    ptr.setsize(qimg.byteCount())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


# ----------------------------------------------------------------------
# 基础绘制
# ----------------------------------------------------------------------
def draw_text(img: np.ndarray, text: str,
              org: tuple = (10, 30),
              color: tuple = (0, 255, 0),
              scale: float = 0.8, thickness: int = 2) -> np.ndarray:
    """在图像上绘制文字。"""
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)
    return img


def draw_box(img: np.ndarray, box, label: str = "",
             color: tuple = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """绘制矩形框 (x1,y1,x2,y2) 与标签。"""
    x1, y1, x2, y2 = [int(v) for v in box]
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    if label:
        cv2.putText(img, label, (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)
    return img


# ----------------------------------------------------------------------
# 安全裁剪
# ----------------------------------------------------------------------
def crop_safe(img: np.ndarray, box) -> np.ndarray | None:
    """安全裁剪：超出边界的 box 自动夹紧；图像为空返回 None。"""
    if img is None or img.size == 0:
        return None
    h, w = img.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1 = max(0, min(w - 1, x1))
    x2 = max(0, min(w,     x2))
    y1 = max(0, min(h - 1, y1))
    y2 = max(0, min(h,     y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return img[y1:y2, x1:x2].copy()


def imread(path: str | Path, flags=cv2.IMREAD_COLOR):
    """
    读取图片（BGR）。

    ⚠ 重要：cv2.imread 在 Windows 上对含中文/非 ASCII 的路径会静默返回 None。
    这里改用 np.fromfile + cv2.imdecode 规避，保证中文路径也能读图。
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = np.fromfile(str(p), dtype=np.uint8)
        img = cv2.imdecode(data, flags)
        return img
    except Exception:
        return None


def imwrite(path: str | Path, img: np.ndarray) -> bool:
    """保存图片（同样规避中文路径问题）。"""
    if img is None or img.size == 0:
        return False
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ext = p.suffix or ".png"
    try:
        ok, buf = cv2.imencode(ext, img)
        if not ok:
            return False
        buf.tofile(str(p))
        return True
    except Exception:
        return False


def load_image(path: str | Path):
    """读取图片（BGR），失败返回 None。兼容旧调用名。"""
    return imread(path)