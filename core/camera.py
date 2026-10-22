# -*- coding: utf-8 -*-
"""
摄像头管理：OpenCV VideoCapture 的封装。

比裸用 cv2.VideoCapture 多做三件事，都是踩过坑才加的：

1. **显式选后端**
   Windows 上 OpenCV 默认后端在部分机器上打开极慢或直接失败。
   DSHOW（DirectShow）打开快、兼容性最好，所以优先尝试，失败再退回默认。

2. **open() 时真的读一帧**
   `isOpened()` 返回 True 不代表能拿到画面：虚拟摄像头、被其他程序独占的设备、
   驱动异常都可能"打开成功但读不到帧"。只检查 isOpened 会让人以为摄像头正常，
   实际画面永远是黑的。这里必须读到一帧才算打开成功。

3. **把失败原因说清楚**
   只弹一句"无法打开摄像头"没法排查。记录 last_error，并用 probe_devices()
   列出实际存在的设备号，用户能据此判断是"没插摄像头"还是"被占用"。
"""

from __future__ import annotations

import os
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config import CAMERA_BACKEND
from utils.logger import get_logger

logger = get_logger()

_IS_WINDOWS = (os.name == "nt")

# 名字 → OpenCV 后端常量
_BACKENDS = {
    "dshow":   cv2.CAP_DSHOW,
    "msmf":    cv2.CAP_MSMF,
    "default": cv2.CAP_ANY,
}


class Camera:
    """本地摄像头 / 视频文件 / RTSP 都可。"""

    # 连续读不到多少帧就认为设备已断开（约 1 秒）
    MAX_READ_FAILS = 25

    def __init__(self, source: int | str = 0, backend: str = CAMERA_BACKEND):
        self.source = source
        self.backend = (backend or "auto").lower()
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False

        self.last_error: str = ""        # 最近一次失败的具体原因
        self.last_backend: str = ""      # 实际生效的后端名
        self._fail_count = 0

    # ------------------------------------------------------------------
    # 后端选择
    # ------------------------------------------------------------------
    def _backend_candidates(self) -> List[Tuple[str, int]]:
        """按优先级返回 [(后端名, 常量), ...]。"""
        if self.backend in _BACKENDS:
            return [(self.backend, _BACKENDS[self.backend])]
        if _IS_WINDOWS:
            # DSHOW 打开快；MSMF 对某些新驱动更稳；最后兜底交给 OpenCV
            return [("dshow", cv2.CAP_DSHOW),
                    ("msmf",  cv2.CAP_MSMF),
                    ("default", cv2.CAP_ANY)]
        return [("default", cv2.CAP_ANY)]

    # ------------------------------------------------------------------
    def open(self) -> bool:
        """打开设备并**验证能读到帧**。失败时把原因写进 last_error。"""
        self.release()
        self.last_error = ""

        # 视频文件 / RTSP 不是"设备"，不需要按设备后端去试
        is_device = isinstance(self.source, int)

        attempts: list[str] = []
        for name, api in (self._backend_candidates() if is_device
                          else [("default", cv2.CAP_ANY)]):
            cap = None
            try:
                cap = cv2.VideoCapture(self.source, api)
                if not cap.isOpened():
                    attempts.append(f"{name}: 设备打不开")
                    cap.release()
                    continue

                # 关键：真的读一帧，确认不是"打开成功但没画面"
                ok, frame = cap.read()
                if not ok or frame is None or getattr(frame, "size", 0) == 0:
                    attempts.append(f"{name}: 打开成功但读不到画面")
                    cap.release()
                    continue

                # 部分设备第一帧是黑的，再给一次机会
                if not frame.any():
                    time.sleep(0.15)
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        attempts.append(f"{name}: 画面全黑且无法重试")
                        cap.release()
                        continue

                self.cap = cap
                self.last_backend = name
                self.is_running = True
                self._fail_count = 0
                h, w = frame.shape[:2]
                logger.info(f"打开摄像头成功：source={self.source} "
                            f"backend={name} {w}x{h}")
                return True

            except Exception as e:                       # 驱动异常等
                attempts.append(f"{name}: {type(e).__name__}")
                logger.warning(f"摄像头后端 {name} 异常：{e}")
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass

        self.is_running = False
        self.last_error = self._explain_failure(attempts, is_device)
        logger.error(f"无法打开摄像头：{self.source} —— {self.last_error}")
        return False

    def _explain_failure(self, attempts: list[str], is_device: bool) -> str:
        """把底层报错翻译成人能看懂的排查建议。"""
        detail = "；".join(attempts) if attempts else "无可用后端"

        if not is_device:
            return f"无法打开视频源 {self.source}（{detail}）"

        if any("读不到画面" in a for a in attempts):
            return (f"设备 {self.source} 能打开但取不到画面，通常是**被其他程序占用**"
                    f"（微信 / 腾讯会议 / QQ / 浏览器视频页）。"
                    f"请关掉这些程序后重试。（{detail}）")

        return (f"没找到可用的摄像头设备 {self.source}。请检查：\n"
                f"· 摄像头是否插好、是否被物理遮挡或禁用；\n"
                f"· Windows「设置 → 隐私 → 相机」是否允许桌面应用访问相机；\n"
                f"· 若为笔记本，是否有相机快捷键（Fn + F8 之类）处于关闭状态。\n"
                f"（{detail}）")

    # ------------------------------------------------------------------
    def read(self) -> Optional[np.ndarray]:
        if not self.cap or not self.cap.isOpened():
            return None
        ok, frame = self.cap.read()
        if not ok or frame is None or getattr(frame, "size", 0) == 0:
            self._fail_count += 1
            return None
        self._fail_count = 0
        return frame

    def is_healthy(self) -> bool:
        """连续读帧失败是否还在可接受范围内（用于判断设备是否掉线）。"""
        return self._fail_count < self.MAX_READ_FAILS

    def release(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.is_running = False
        self._fail_count = 0

    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    # ------------------------------------------------------------------
    @staticmethod
    def probe_devices(max_index: int = 3) -> List[int]:
        """
        探测本机可用的设备号（0 ~ max_index-1）。

        ⚠ 每次探测都要真正建立一次采集管线，单个设备约 1~2 秒，
           所以只在打开失败时调用，且不要给出很大的 max_index。
        """
        found: List[int] = []
        for i in range(max(0, max_index)):
            cap = None
            try:
                api = cv2.CAP_DSHOW if _IS_WINDOWS else cv2.CAP_ANY
                cap = cv2.VideoCapture(i, api)
                if cap.isOpened():
                    ok, frame = cap.read()
                    if ok and frame is not None and getattr(frame, "size", 0) > 0:
                        found.append(i)
            except Exception:
                pass
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
        return found
