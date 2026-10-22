# -*- coding: utf-8 -*-
"""
入场登记：
    1) 选择/识别车牌 → 自动填写车牌号
    2) 选择车辆类型
    3) 自动分配车位
    4) 入场时间 = 现在
    5) 判断是否会员 / 黑名单
    6) 写入停车记录 + 占用车位

界面：左表单右车位看板。车位看板给"剩余 / 总数 + 占用进度条"，
值班人员扫一眼就知道还能不能放车进来。
"""

from __future__ import annotations

from PyQt5.QtCore    import Qt as QtQt
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit,
    QComboBox, QMessageBox, QProgressBar, QSizePolicy,
)

from auth            import get_current_user
from core            import (BlacklistChecker, ParkingLotManager,
                             PlateRecognizer, validate_plate)
from db.dao          import ParkingRecordDAO, MemberDAO
from ui.components   import (
    Card, PageHeader, add_form_row, field_label, form_layout, h_line,
    make_button, repolish,
)
from ui.theme        import Color
from utils.constants import VEHICLE_TYPES
from utils.logger import get_logger
from utils.time_utils import now as now_dt

logger = get_logger()


class EntryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recognizer = PlateRecognizer.shared()
        self._build_ui()

    def _build_ui(self):
        header = PageHeader(
            "入场登记",
            "录入车牌后自动分配空闲车位，并写入入场时间",
        )

        # ---------- 左：车辆信息表单 ----------
        self.plate_edit = QLineEdit()
        self.plate_edit.setObjectName("plateInput")
        self.plate_edit.setPlaceholderText("如 京A12345")
        self.plate_edit.setMaxLength(10)

        self.recog_btn = make_button("识别", "scan")
        self.recog_btn.clicked.connect(self.on_recognize)

        plate_row = QWidget()
        pr = QHBoxLayout(plate_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(8)
        pr.addWidget(self.plate_edit, 1)
        pr.addWidget(self.recog_btn)

        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItems(VEHICLE_TYPES)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("备注（可选）")

        form = form_layout()
        add_form_row(form, "车牌号", plate_row)
        add_form_row(form, "车辆类型", self.vehicle_combo)
        add_form_row(form, "备注", self.note_edit)

        self.entry_btn = make_button("确认入场", "entry", "primary")
        self.entry_btn.setMinimumHeight(44)
        self.entry_btn.clicked.connect(self.on_entry)

        form_card = Card("车辆信息", hint="识别后自动填充车牌")
        form_card.setFixedWidth(520)
        form_card.add_layout(form)
        form_card.body.addSpacing(6)
        form_card.add(self.entry_btn)

        flow = QLabel("识别或输入车牌 → 确认入场，系统自动分配车位并写入入场时间；"
                      "会员车辆出场时自动按折扣结算。")
        flow.setObjectName("hintLabel")
        flow.setWordWrap(True)
        form_card.add(flow)
        form_card.body.addStretch()

        # ---------- 右：车位看板 ----------
        lot_card = Card("车位状态", hint="实时")
        lot_card.setFixedWidth(330)

        cap = QLabel("剩余车位")
        cap.setObjectName("statLabel")

        self.remain_label = QLabel("—")
        self.remain_label.setObjectName("statValueAccent")
        self.remain_label.setStyleSheet("font-size:34px;")
        unit = QLabel("个")
        unit.setObjectName("statUnit")

        remain_row = QHBoxLayout()
        remain_row.setContentsMargins(0, 0, 0, 0)
        remain_row.setSpacing(5)
        remain_row.addWidget(self.remain_label)
        remain_row.addWidget(unit, 0, QtQt.AlignBottom)
        remain_row.addStretch()

        self.usage_bar = QProgressBar()
        self.usage_bar.setRange(0, 100)
        self.usage_bar.setValue(0)
        self.usage_bar.setTextVisible(False)
        self.usage_bar.setFixedHeight(7)

        self.total_label  = self._metric_row("总车位")
        self.used_label   = self._metric_row("已占用")
        self.rate_label   = self._metric_row("使用率")

        self.refresh_btn = make_button("刷新车位状态", "refresh", "ghost")
        self.refresh_btn.clicked.connect(self.refresh_status)

        lot_card.add(cap)
        lot_card.add_layout(remain_row)
        lot_card.add(self.usage_bar)
        lot_card.body.addSpacing(2)
        lot_card.add(self.total_label[0])
        lot_card.add(self.used_label[0])
        lot_card.add(self.rate_label[0])
        lot_card.body.addSpacing(4)
        lot_card.add(h_line())
        lot_card.add(self.refresh_btn)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(16)
        rl.addWidget(lot_card)
        rl.addStretch()

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        body.addWidget(form_card, 0, QtQt.AlignTop)
        body.addWidget(right, 0, QtQt.AlignTop)
        body.addStretch()

        root = QVBoxLayout(self)
        m = 26
        root.setContentsMargins(m, m - 4, m, m)
        root.setSpacing(16)
        root.addWidget(header)
        root.addLayout(body)
        root.addStretch()

        self.refresh_status()

    # ------------------------------------------------------------------
    def _metric_row(self, caption: str) -> tuple[QWidget, QLabel]:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        key = QLabel(caption)
        key.setObjectName("mutedLabel")
        h.addWidget(key)
        h.addStretch()

        val = QLabel("—")
        val.setObjectName("valueMono")
        h.addWidget(val)
        return row, val

    def _tip(self, text: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(8)

        dot = QLabel("•")
        dot.setStyleSheet(f"color:{Color.primary}; font-weight:700;")
        h.addWidget(dot, 0, QtQt.AlignTop)

        lb = QLabel(text)
        lb.setObjectName("mutedLabel")
        lb.setWordWrap(True)
        h.addWidget(lb, 1)
        return row

    # ------------------------------------------------------------------
    def on_recognize(self):
        from PyQt5.QtWidgets import QFileDialog
        from utils.image_utils import load_image
        from config import IMAGES_DIR
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
        result = self.recognizer.recognize(img, draw_on_image=False)
        if result.best_plate:
            self.plate_edit.setText(result.best_plate)
            detail = (f"识别到车牌：{result.best_plate}\n"
                      f"引擎：{result.engine}　"
                      f"置信度：{result.confidence_of_best:.1%}")
            if result.note:
                detail += f"\n\n注意：{result.note}"
            QMessageBox.information(self, "识别结果", detail)
        else:
            QMessageBox.warning(self, "提示", "未识别到车牌，请手动输入")

    # ------------------------------------------------------------------
    def refresh_status(self):
        total = ParkingLotManager.total()
        used  = ParkingLotManager.used()
        free  = total - used
        rate  = (used / total * 100) if total else 0

        self.remain_label.setText(str(free))
        self.total_label[1].setText(f"{total} 个")
        self.used_label[1].setText(f"{used} 个")
        self.rate_label[1].setText(f"{rate:.0f}%")
        self.usage_bar.setValue(int(round(rate)))

        # 车位紧张时换色，比纯数字更快被注意到
        if rate >= 90:
            self.remain_label.setStyleSheet(
                f"font-size:34px; color:{Color.danger};"
            )
            self.usage_bar.setObjectName("dangerBar")
        elif rate >= 70:
            self.remain_label.setStyleSheet(
                f"font-size:34px; color:{Color.warning};"
            )
            self.usage_bar.setObjectName("warnBar")
        else:
            self.remain_label.setStyleSheet(
                f"font-size:34px; color:{Color.primary};"
            )
            self.usage_bar.setObjectName("")
        repolish(self.usage_bar)

    # ------------------------------------------------------------------
    def on_entry(self):
        plate = self.plate_edit.text().strip().upper()
        if not plate:
            QMessageBox.warning(self, "提示", "请输入或识别车牌号")
            return

        # 车牌格式软校验：不硬拦（避免影响演示），但要让操作员确认
        if not validate_plate(plate):
            ans = QMessageBox.question(
                self, "车牌格式提示",
                f"“{plate}” 不是标准车牌格式\n"
                "（应为：省份简称 + 字母 + 5~6 位字母数字，如 京A8X3K7）。\n\n"
                "仍要按此车牌登记入场吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return

        if ParkingLotManager.is_full():
            QMessageBox.warning(self, "提示", "停车场已满，禁止入场！")
            logger.info(f"入场被拦截（已满）：{plate}")
            return

        # 是否已在场
        existing = ParkingRecordDAO.list_unpaid_by_plate(plate)
        if existing:
            QMessageBox.warning(
                self, "提示",
                f"车牌 {plate} 已在场（车位 {existing['spot_no']}），请勿重复入场。",
            )
            return

        # 会员
        today_str = now_dt().strftime("%Y-%m-%d")
        member_row = MemberDAO.is_member_valid(plate, today_str)
        member_flag = 1 if member_row else 0

        # 黑名单
        warn = BlacklistChecker.warn(plate)
        if warn:
            QMessageBox.warning(self, "⚠ 黑名单预警", warn)

        # 分配车位
        spot, ok = ParkingLotManager.allocate_spot()
        if not ok:
            QMessageBox.warning(self, "提示", "无可用车位，请稍后再试。")
            return

        user = get_current_user()
        operator_id = user.user_id if user else None
        entry_time = now_dt()
        vehicle_type = self.vehicle_combo.currentText()

        rec_id = ParkingRecordDAO.insert_entry(
            plate_no=plate,
            vehicle_type=vehicle_type,
            spot_no=spot,
            entry_time=entry_time,
            member_flag=member_flag,
            operator_id=operator_id,
            note=self.note_edit.text().strip(),
        )
        ParkingLotManager.on_entry_success()

        logger.info(f"入场：{plate} → {spot}（rec_id={rec_id}）")
        QMessageBox.information(
            self, "入场成功",
            f"车牌：{plate}\n车位：{spot}\n入场时间：{entry_time:%Y-%m-%d %H:%M:%S}"
        )

        self.plate_edit.clear()
        self.note_edit.clear()
        self.refresh_status()
