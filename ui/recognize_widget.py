# -*- coding: utf-8 -*-
"""
车牌识别模块：
    - 模式切换：图片识别 / 摄像头实时识别
    - 调用 PlateRecognizer
    - 显示状态：识别中 / 识别成功 / 未检测到车牌

界面分两栏：
    左 = 图像工作区（工具条 + 画布 + 状态）
    右 = 结果面板（车牌号牌 + 置信度 + 引擎信息 + 历史）
这样"看画面"和"看结果"视线不来回跳，也不用在一堆控件里找车牌号。
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import Qt as QtQt, QSize, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox,
    QFileDialog, QMessageBox, QListWidget, QProgressBar, QSizePolicy,
)

from config  import (
    IMAGES_DIR, DEMO_MODE, CAMERA_INDEX, CAMERA_BACKEND, CAMERA_MIN_CONFIDENCE,
)
from core    import PlateRecognizer, Camera
from ui.components import (
    Card, PageHeader, PlateBadge, chip, h_line, set_chip, make_button, repolish,
)
from ui.icons import icon as _icon
from ui.theme import Color
from utils.image_utils import bgr2qpixmap, load_image
from utils.logger    import get_logger

logger = get_logger()


class _CameraWorker(QThread):
    """
    摄像头采集线程。

    为什么必须单独开线程：
      cv2.VideoCapture.open() 在 Windows 上要 1~2 秒，若放在主线程，
      点下按钮后界面直接假死，用户看到的就是"点了没反应/打不开"。
      读帧同理，30fps 的 read 也不该占用 UI 线程。

    线程里只做"打开 + 读帧"，识别交给另一个线程池，
    否则识别一慢（0.2~1.5 秒）画面就跟着卡。
    """

    frame_ready = pyqtSignal(object)     # np.ndarray
    failed      = pyqtSignal(str)

    def __init__(self, camera: Camera, parent=None):
        super().__init__(parent)
        self.camera = camera
        self._running = False

    def run(self):
        # 打开失败：把具体原因（占用 / 找不到设备）交给界面提示
        if not self.camera.open():
            self.failed.emit(self.camera.last_error or "无法打开摄像头")
            return

        self._running = True
        fails = 0
        while self._running:
            frame = self.camera.read()
            if frame is None:
                fails += 1
                if fails > Camera.MAX_READ_FAILS:
                    self.failed.emit(
                        "摄像头画面中断：设备可能被拔出，或被其他程序抢占了"
                    )
                    break
                self.msleep(30)
                continue
            fails = 0
            self.frame_ready.emit(frame)
            self.msleep(33)          # ~30fps，避免空转把 CPU 吃满
        self.camera.release()

    def stop(self):
        self._running = False
        if not self.wait(3000):
            self.terminate()
            self.wait(500)


class RecognizeWidget(QWidget):
    # 识别在子线程完成后，用信号把结果送回主线程（Qt 自动排队，线程安全）
    _result_signal = pyqtSignal(object, str)
    # 后台探测摄像头设备后回传提示文本
    _probe_signal  = pyqtSignal(str)
    # 后台探测引擎状态后回传 dict
    _engine_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recognizer = PlateRecognizer.shared()
        self.camera     = Camera(CAMERA_INDEX, CAMERA_BACKEND)
        self.current_plate = ""
        self.current_img  = None

        # 采集线程 + 识别线程池（单线程，保证识别任务串行，不会堆积）
        self._cam_worker: _CameraWorker | None = None
        self._pool = ThreadPoolExecutor(max_workers=1)
        self._recognizing = False
        self._pending_desc = ""
        self._last_recog_ts = 0.0
        self._cam_ready = False
        self._capturing = False
        self._closing = False
        self._overlay_box = None
        self._overlay_until = 0.0
        self._engines_ready = False

        self._result_signal.connect(self._on_async_result)
        self._probe_signal.connect(self._on_probe_done)
        self._engine_signal.connect(self._on_engine_status)

        self._build_ui()

        # 后台预热模型。
        # 首次 recognize() 会现场加载 YOLO(约 10s) + Tesseract + 模板 OCR +
        # ONNX 引擎，合计 15~20 秒。不预热的话，用户点开摄像头后第一次识别
        # 界面就冻住了，和"打不开"没有区别。
        QTimer.singleShot(400, self._start_warmup)

    def _start_warmup(self):
        if getattr(self, "_warmup_started", False):
            return
        self._warmup_started = True
        threading.Thread(target=self.recognizer.warmup, daemon=True).start()

    # ------------------------------------------------------------------
    def _build_ui(self):
        header = PageHeader(
            "车牌识别",
            "图片文件与摄像头实时识别 · 深度学习 / 模板匹配双引擎仲裁",
        )

        # ---------- 左：图像工作区 ----------
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["图片识别", "摄像头实时识别"])
        self.mode_combo.setFixedWidth(142)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.img_btn = make_button("选择图片", "image", "primary")
        self.img_btn.clicked.connect(self.on_pick_image)

        self.cam_btn = make_button("打开摄像头", "camera", "normal")
        self.cam_btn.setObjectName("camBtn")
        self.cam_btn.setCheckable(True)
        self.cam_btn.clicked.connect(self.on_toggle_camera)
        self.cam_btn.setIcon(_icon("camera", 15, Color.text2))

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)
        mode_cap = QLabel("识别模式")
        mode_cap.setObjectName("fieldLabel")
        toolbar.addWidget(mode_cap)
        toolbar.addWidget(self.mode_combo)
        toolbar.addStretch()
        toolbar.addWidget(self.img_btn)
        toolbar.addWidget(self.cam_btn)

        self.img_label = QLabel()
        self.img_label.setObjectName("imageCanvas")
        self.img_label.setAlignment(QtQt.AlignCenter)
        self.img_label.setMinimumSize(560, 360)
        self.img_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.img_label.setText("请选择图片文件，或开启摄像头")

        self.status_chip = chip("就绪", "info")
        self.status_detail = QLabel("等待操作")
        self.status_detail.setObjectName("mutedLabel")

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(10)
        status_row.addWidget(self.status_chip)
        status_row.addWidget(self.status_detail, 1)

        work_card = Card(padding=14)
        work_card.body.setSpacing(10)
        work_card.add_layout(toolbar)
        work_card.add(self.img_label, 1)
        work_card.add_layout(status_row)

        # ---------- 右：结果面板 ----------
        result_card = Card("识别结果", hint="实时")

        self.plate_badge = PlateBadge()

        conf_head = QHBoxLayout()
        conf_head.setContentsMargins(0, 0, 0, 0)
        conf_head.setSpacing(6)
        conf_cap = QLabel("置信度")
        conf_cap.setObjectName("fieldLabel")
        conf_head.addWidget(conf_cap)
        conf_head.addStretch()
        self.conf_value = QLabel("—")
        self.conf_value.setObjectName("valueMono")
        conf_head.addWidget(self.conf_value)

        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setTextVisible(False)
        self.conf_bar.setFixedHeight(7)

        self.meta_label = QLabel("尚未识别")
        self.meta_label.setObjectName("mutedLabel")
        self.meta_label.setWordWrap(True)

        self.conflict_chip = chip("引擎结果有分歧", "warn")
        self.conflict_chip.hide()

        result_card.add(self.plate_badge)
        result_card.body.addWidget(h_line())
        result_card.add_layout(conf_head)
        result_card.add(self.conf_bar)
        result_card.add(self.meta_label)
        result_card.add(self.conflict_chip)

        # 引擎状态
        self.engine_label = QLabel("引擎状态：检测中…")
        self.engine_label.setStyleSheet(
            f"color:{Color.muted}; font-size:11px; line-height:150%;"
        )
        self.engine_label.setWordWrap(True)
        result_card.add(self.engine_label)

        # 历史
        hist_card = Card("识别历史", hint="本次运行")
        self.history = QListWidget()
        self.history.setObjectName("historyList")
        self.history.setMinimumHeight(140)
        hist_card.add(self.history, 1)

        self.history_empty = QLabel("暂无识别记录")
        self.history_empty.setObjectName("mutedLabel")
        self.history_empty.setAlignment(QtQt.AlignCenter)
        hist_card.add(self.history_empty)

        right_panel = QWidget()
        right_panel.setFixedWidth(344)
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(16)
        rl.addWidget(result_card)
        rl.addWidget(hist_card, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        body.addWidget(work_card, 1)
        body.addWidget(right_panel, 0)

        root = QVBoxLayout(self)
        m = 26
        root.setContentsMargins(m, m - 4, m, m)
        root.setSpacing(16)
        root.addWidget(header)
        root.addLayout(body, 1)

        # 延时刷新引擎状态（避免初始化卡顿）
        QTimer.singleShot(300, self._refresh_engine_status)

        self._on_mode_changed(0)

    # ------------------------------------------------------------------
    def _refresh_engine_status(self):
        """
        刷新"引擎状态"面板。

        探测需要把 Tesseract 初始化起来（1~2 秒），放主线程会让刚进页面
        就卡一下，所以整体丢到后台线程，完成后用信号回填。
        同时这里顺带完成模型预热——状态探测与预热本来就是同一件事。
        """
        threading.Thread(target=self._refresh_engine_status_bg, daemon=True).start()

    def _refresh_engine_status_bg(self):
        try:
            self.recognizer.warmup()
        except Exception:
            pass
        try:
            data = self.recognizer.status()
        except Exception:
            data = {"loaded": False, "deep": False,
                    "tesseract": False, "template": False}
        self._engine_signal.emit(data)

    def _on_engine_status(self, data: dict):
        deep_ok = bool(data.get("deep"))
        tmpl_ok = bool(data.get("template"))
        tess_ok = bool(data.get("tesseract"))

        def dot(ok, text, warn_if_false=False):
            color = Color.success if ok else (
                Color.warning if warn_if_false else Color.faint
            )
            return (f"<span style='color:{color};'>●</span> "
                    f"<span style='color:{Color.text2};'>{text}</span>")

        parts = [
            dot(deep_ok, "深度引擎", warn_if_false=True),
            dot(tmpl_ok, "内置OCR"),
            dot(tess_ok, "Tesseract"),
        ]
        html = "　".join(parts)

        if DEMO_MODE:
            html += (f"<br/><span style='color:{Color.warning};'>"
                     f"⚠ 演示模式已开启，识别结果非真实所得</span>")

        self.engine_label.setText(html)

        tips = []
        if not deep_ok:
            tips.append("HyperLPR3 不可用：仅使用内置模板 OCR")
        if not tmpl_ok:
            tips.append("内置 OCR 不可用：可能缺少中文字体")
        if not tess_ok:
            tips.append("Tesseract 未启用：不影响使用")
        self.engine_label.setToolTip("\n".join(tips))

        self._engines_ready = True
        logger.info(f"引擎状态：深度={deep_ok} 内置OCR={tmpl_ok} Tesseract={tess_ok}")

    def _on_mode_changed(self, idx: int):
        is_image = (idx == 0)
        self.img_btn.setEnabled(is_image)
        # 摄像头按钮保持可用：图片模式下点它会自动切到摄像头模式再打开。
        # 之前这里跟着模式禁用，用户在图片模式下点一下毫无反应，
        # 很容易误判成"摄像头打不开"。
        self.cam_btn.setEnabled(True)
        if is_image:
            # 切回图片模式必须真正关闭设备，否则句柄一直被占着，
            # 别的程序（以及下次自己重新打开）都拿不到画面。
            if self.cam_btn.isChecked() or self._cam_worker is not None:
                self._close_camera()
            self.img_label.setText("请选择图片文件，或开启摄像头")
            set_chip(self.status_chip, "就绪", "info")
            self.status_detail.setText("图片模式：支持 jpg / png / bmp")
            self.cam_btn.setToolTip("点击将切换到摄像头模式并打开设备")
        else:
            self.img_label.setText("摄像头未开启")
            set_chip(self.status_chip, "就绪", "info")
            self.status_detail.setText("摄像头模式：点击「打开摄像头」开始")
            self.cam_btn.setToolTip("")

    # ------------------------------------------------------------------
    def on_pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择车牌图片", str(IMAGES_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not path:
            return
        img = load_image(path)
        if img is None:
            QMessageBox.warning(self, "提示", "图片读取失败")
            return

        self.current_img = img
        self._recognize_and_show(img, source_desc=f"图片：{Path(path).name}")

    # ------------------------------------------------------------------
    # 摄像头
    # ------------------------------------------------------------------
    def on_toggle_camera(self):
        if self.cam_btn.isChecked():
            # 图片模式下直接点"打开摄像头"：自动切模式，省一步操作
            if self.mode_combo.currentIndex() == 0:
                self.mode_combo.setCurrentIndex(1)
            self._open_camera()
        else:
            self._close_camera()

    def _open_camera(self):
        if self._cam_worker is not None:
            return
        # 打开是异步的：先给用户"正在打开"的反馈，界面不冻结
        self.cam_btn.setEnabled(False)
        self.cam_btn.setText("正在打开…")
        repolish(self.cam_btn)
        set_chip(self.status_chip, "连接中", "info")
        self.status_detail.setText("正在打开摄像头，请稍候…")
        self.img_label.setText("正在打开摄像头…")

        self._capturing = True
        # 每次重新创建实例，避免复用上一次已 release 的句柄
        self.camera = Camera(CAMERA_INDEX, CAMERA_BACKEND)
        self._cam_worker = _CameraWorker(self.camera, self)
        self._cam_worker.frame_ready.connect(self._on_cam_frame)
        self._cam_worker.failed.connect(self._on_cam_failed)
        self._cam_worker.finished.connect(self._on_cam_thread_finished)
        self._cam_worker.start()

    def _close_camera(self, reset_button: bool = True):
        self._capturing = False
        worker, self._cam_worker = self._cam_worker, None
        if worker is not None:
            worker.stop()
        try:
            self.camera.release()
        except Exception:
            pass
        self._cam_ready = False
        self._overlay_box = None
        if reset_button:
            self.cam_btn.setChecked(False)
            self.cam_btn.setText("打开摄像头")
            self.cam_btn.setEnabled(True)
            repolish(self.cam_btn)
            # 主动关闭（而非切回图片模式）时，状态栏要跟着复位，
            # 否则会一直停在"采集中"，看起来像还没关掉。
            if self.mode_combo.currentIndex() != 0:
                set_chip(self.status_chip, "就绪", "info")
                self.status_detail.setText("摄像头已关闭")
                self.img_label.setText("摄像头未开启")

    def _on_cam_frame(self, frame: np.ndarray):
        # 关闭瞬间线程队列里可能还有一两帧在途。不拦掉的话，
        # 关闭之后按钮会被残留帧重新改回"关闭摄像头"。
        if self._closing or not self._capturing:
            return
        if not self._cam_ready:
            # 收到第一帧才算真正打开成功
            self._cam_ready = True
            self.cam_btn.setText("关闭摄像头")
            self.cam_btn.setEnabled(True)
            repolish(self.cam_btn)
            set_chip(self.status_chip, "采集中", "success")
            self.status_detail.setText(
                f"摄像头已开启（设备 {CAMERA_INDEX}），每秒识别一次"
            )
            logger.info(f"摄像头画面就绪：backend={self.camera.last_backend}")

        self._show_frame(self._decorate(frame))

        # 控制识别频率：每 1 秒提交一次，且同一时刻只允许一个任务在跑
        now = time.time()
        if now - self._last_recog_ts > 1.0 and not self._recognizing:
            self._last_recog_ts = now
            # 模型还在加载时先只显示画面。
            # 此时提交识别只会在后台排队等加载锁，结果迟迟不出来，
            # 又变成"打开了但没反应"的错觉。
            if self._engines_ready or self.recognizer.status().get("loaded"):
                self._submit_recognize(frame, "摄像头")

    def _decorate(self, frame: np.ndarray) -> np.ndarray:
        """在实时画面上叠加最近一次识别到的车牌框（约 1 秒后消失）。"""
        if self._overlay_box is None or time.time() > self._overlay_until:
            return frame
        x1, y1, x2, y2 = [int(v) for v in self._overlay_box]
        out = frame.copy()
        cv2.rectangle(out, (x1, y1), (x2, y2), (80, 220, 120), 2)
        return out

    def _on_cam_failed(self, msg: str):
        logger.error(f"摄像头打开失败：{msg}")
        self._close_camera()
        self.img_label.setText("摄像头未开启")
        set_chip(self.status_chip, "设备异常", "danger")
        self.status_detail.setText("摄像头打开失败，详见提示")
        QMessageBox.warning(self, "摄像头打开失败", msg)
        # 设备探测要 1~2 秒，放后台做，别让弹窗关掉后界面又卡一下
        threading.Thread(target=self._probe_devices_bg, daemon=True).start()

    def _probe_devices_bg(self):
        try:
            found = Camera.probe_devices(3)
        except Exception:
            found = []
        if found:
            text = f"本机可用摄像头编号：{found}（可在 config.CAMERA_INDEX 指定）"
        else:
            text = "未检测到可用摄像头，请确认设备已连接且未被其他程序占用"
        logger.info(f"摄像头探测结果：{text}")
        self._probe_signal.emit(text)

    def _on_probe_done(self, text: str):
        self.status_detail.setText(text)

    def _on_cam_thread_finished(self):
        # 线程自然退出（失败或掉线）后清引用，允许重新打开
        if self._cam_worker is not None and not self._cam_worker.isRunning():
            self._cam_worker = None

    # ------------------------------------------------------------------
    # 识别：统一走后台线程，界面永不冻结
    # ------------------------------------------------------------------
    def _submit_recognize(self, img: np.ndarray, source_desc: str):
        if self._recognizing or self._closing:
            return
        self._recognizing = True
        self._pending_desc = source_desc
        try:
            fut = self._pool.submit(self.recognizer.recognize, img, True)
        except Exception as e:
            self._recognizing = False
            logger.error(f"提交识别任务失败：{e}")
            return
        fut.add_done_callback(self._recognize_done)

    def _recognize_done(self, fut):
        """在识别线程中执行：只 emit 信号，不碰任何 UI。"""
        try:
            result = fut.result()
        except Exception as e:
            logger.exception(f"识别任务异常：{e}")
            result = None
        try:
            self._result_signal.emit(result, self._pending_desc)
        except RuntimeError:
            # 退程序时底层 C++ 对象可能已销毁，忽略即可
            pass

    def _on_async_result(self, result, source_desc: str):
        """主线程：渲染识别结果。"""
        self._recognizing = False
        if self._closing:
            return
        # 摄像头已关闭后才回来的结果直接丢掉，否则界面关掉了还在跳识别结果
        if source_desc == "摄像头" and not self._capturing:
            return
        if result is None:
            set_chip(self.status_chip, "识别异常", "danger")
            self.status_detail.setText("识别任务出错，详见 logs/app.log")
            self.img_btn.setEnabled(self.mode_combo.currentIndex() == 0)
            return

        # 摄像头模式的拒识：
        # 镜头对着空房间时，内置管线会把噪点拼成 "宁TTTTTF" 这类格式合法的
        # 乱码并当成识别成功——在实时场景里这比"未识别"更误导人。
        if source_desc == "摄像头" and result.success:
            if (result.engine == "内置管线"
                    and result.confidence_of_best < CAMERA_MIN_CONFIDENCE):
                result.success = False
                result.message = "画面中未检测到可信车牌，请把车牌对准取景框"

        self._apply_result(result, source_desc)

        if source_desc.startswith("图片"):
            self.img_btn.setEnabled(True)
            img = result.image if result.image is not None else self.current_img
            if img is not None:
                self._show_frame(img)
        elif result.success and result.boxes:
            # 实时画面标出车牌位置，下一秒自然被新帧覆盖
            self._overlay_box = result.boxes[0].box
            self._overlay_until = time.time() + 1.0

    # ------------------------------------------------------------------
    def _recognize_and_show(self, img: np.ndarray, source_desc: str):
        set_chip(self.status_chip, "识别中", "info")
        self.status_detail.setText("正在分析图像…")
        self.plate_badge.clear_plate("识别中…")
        self.img_btn.setEnabled(False)
        self._submit_recognize(img, source_desc)

    # ------------------------------------------------------------------
    def shutdown(self):
        """窗口关闭时释放摄像头与线程池。"""
        if self._closing:
            return
        self._closing = True
        self._close_camera()
        try:
            # 取消还在排队、尚未开始的识别任务；正在跑的那个会自己结束
            self._pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:            # Python 3.8 没有 cancel_futures
            try:
                self._pool.shutdown(wait=False)
            except Exception:
                pass
        except Exception:
            pass

    def closeEvent(self, e):
        self.shutdown()
        super().closeEvent(e)

    def _apply_result(self, result, source_desc: str):
        plate = result.best_plate
        # 只有识别成功才记下当前车牌。被拒识的结果（如摄像头对空画面的乱码）
        # 绝不能留在 current_plate 里——后面的"填入入场"会把它带进业务。
        self.current_plate = plate if result.success else ""

        if result.success and plate:
            engine = result.engine or "—"
            conf = result.confidence_of_best

            self.plate_badge.set_plate(plate)
            set_chip(self.status_chip, "识别成功", "success")
            self.status_detail.setText(f"{engine} · {result.elapsed_ms:.0f} ms")
            self.conf_value.setText(f"{conf:.1%}")
            self.conf_bar.setValue(int(round(conf * 100)))
            self.meta_label.setText(
                f"引擎 {engine}　耗时 {result.elapsed_ms:.0f} ms"
                f"　来源 {source_desc}"
            )
            self.meta_label.setToolTip(result.note or "")
            self.conflict_chip.setVisible(bool(result.note))
            if result.note:
                self.conflict_chip.setToolTip(result.note)

            self.history.insertItem(0, f"{plate}　·　{engine}　{conf:.0%}")
            self.history_empty.setVisible(False)
        else:
            self.plate_badge.clear_plate("未识别")
            set_chip(self.status_chip, "未识别", "warn")
            self.status_detail.setText("请调整角度 / 光线后重试，或手动输入车牌")
            self.conf_value.setText("—")
            self.conf_bar.setValue(0)
            self.meta_label.setText(result.message or "未检测到有效车牌")
            self.meta_label.setToolTip(result.note or "")
            self.conflict_chip.hide()

            if result.note:
                self.history.insertItem(0, f"未识别　·　{result.note[:24]}")

    def _show_frame(self, frame: np.ndarray):
        pix = bgr2qpixmap(frame)
        if pix is None:
            return
        w = max(1, self.img_label.width() - 2)
        h = max(1, self.img_label.height() - 2)
        pix = pix.scaled(w, h, QtQt.KeepAspectRatio,
                         QtQt.SmoothTransformation)
        self.img_label.setPixmap(pix)
