# -*- coding: utf-8 -*-
"""
出场结算：
    1) 输入或识别车牌
    2) 在数据库查找最近一次未出场记录
    3) 调用 billing.compute_fee 计算时长与费用
    4) 写入出场时间 / 时长 / 费用
    5) 释放车位（used_spots - 1）

界面：左边查车，右边是一张"结算单"——把最终要收多少钱放在最显眼的位置。
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore    import Qt as QtQt
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QMessageBox,
)

from core            import PlateRecognizer, ParkingLotManager, compute_fee
from db.dao          import ParkingRecordDAO, MemberDAO
from ui.components   import (
    Card, PageHeader, PlateBadge, add_form_row, chip, field_label,
    form_layout, h_line, make_button, set_chip, value_label,
)
from ui.theme        import Color
from utils.logger    import get_logger
from utils.time_utils import duration_str, fmt_dt, now as now_dt, parse_dt

logger = get_logger()


class ExitWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recognizer = PlateRecognizer.shared()
        self._build_ui()

    def _build_ui(self):
        header = PageHeader(
            "出场结算",
            "查询在场记录 → 自动计算停车时长与应收费用 → 释放车位",
        )

        # ---------- 左：车牌输入 ----------
        self.plate_edit = QLineEdit()
        self.plate_edit.setObjectName("plateInput")
        self.plate_edit.setPlaceholderText("如 京A12345")
        self.plate_edit.setMaxLength(10)
        self.plate_edit.returnPressed.connect(self.on_query)

        self.recog_btn = make_button("识别", "scan")
        self.recog_btn.clicked.connect(self.on_recognize)

        plate_row = QWidget()
        pr = QHBoxLayout(plate_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(8)
        pr.addWidget(self.plate_edit, 1)
        pr.addWidget(self.recog_btn)

        form = form_layout()
        add_form_row(form, "车牌号", plate_row)

        self.query_btn = make_button("查询在场记录", "search", "primary")
        self.query_btn.setMinimumHeight(42)
        self.query_btn.clicked.connect(self.on_query)

        query_card = Card("车辆查询", hint="支持识别或手动输入")
        query_card.setFixedWidth(360)
        query_card.add_layout(form)
        query_card.body.addSpacing(4)
        query_card.add(self.query_btn)
        query_card.body.addSpacing(6)
        query_card.add(h_line())

        tip = QLabel("提示：仅「已入场且未结算」的车辆才能出场。\n"
                     "会员车辆按会员折扣自动计算费用。")
        tip.setObjectName("hintLabel")
        tip.setWordWrap(True)
        query_card.add(tip)

        # ---------- 右：结算单 ----------
        bill_card = Card("结算单")

        self.plate_badge = PlateBadge()
        self.plate_badge.clear_plate("待查询")

        self.status_chip = chip("等待查询", "info")

        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(8)
        chip_row.addWidget(self.status_chip)
        chip_row.addStretch()

        self.spot_label     = value_label("—", mono=True)
        self.entry_label    = value_label("—")
        self.duration_label = value_label("—")
        self.member_label   = value_label("—")

        info = form_layout()
        add_form_row(info, "车位",       self.spot_label)
        add_form_row(info, "入场时间",   self.entry_label)
        add_form_row(info, "停车时长",   self.duration_label)
        add_form_row(info, "会员",       self.member_label)

        # 金额区：整张卡片的视觉重心
        self.fee_label = QLabel("¥ —")
        self.fee_label.setObjectName("amountLabel")
        self.fee_label.setAlignment(QtQt.AlignRight | QtQt.AlignVCenter)

        fee_cap = QLabel("应收费用")
        fee_cap.setObjectName("fieldLabel")

        fee_row = QHBoxLayout()
        fee_row.setContentsMargins(0, 0, 0, 0)
        fee_row.setSpacing(8)
        fee_row.addWidget(fee_cap)
        fee_row.addStretch()
        fee_row.addWidget(self.fee_label)

        self.hours_label = QLabel("")
        self.hours_label.setObjectName("mutedLabel")
        self.hours_label.setAlignment(QtQt.AlignRight)

        self.settle_btn = make_button("确认出场并结算", "check", "primary")
        self.settle_btn.setMinimumHeight(44)
        self.settle_btn.setEnabled(False)
        self.settle_btn.clicked.connect(self.on_settle)

        bill_card.add(self.plate_badge)
        bill_card.add_layout(chip_row)
        bill_card.body.addSpacing(4)
        bill_card.add_layout(info)
        bill_card.body.addSpacing(6)
        bill_card.add(h_line())
        bill_card.body.addSpacing(2)
        bill_card.add_layout(fee_row)
        bill_card.add(self.hours_label)
        bill_card.body.addSpacing(6)
        bill_card.add(self.settle_btn)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        body.addWidget(query_card, 0, QtQt.AlignTop)
        body.addWidget(bill_card, 1, QtQt.AlignTop)
        body.addStretch()

        root = QVBoxLayout(self)
        m = 26
        root.setContentsMargins(m, m - 4, m, m)
        root.setSpacing(16)
        root.addWidget(header)
        root.addLayout(body)
        root.addStretch()

        self._current_record = None

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
            self.on_query()
        else:
            QMessageBox.warning(self, "提示", "未识别到车牌，请手动输入")

    # ------------------------------------------------------------------
    def on_query(self):
        plate = self.plate_edit.text().strip().upper()
        if not plate:
            QMessageBox.warning(self, "提示", "请输入车牌号")
            return

        rec = ParkingRecordDAO.list_unpaid_by_plate(plate)
        if rec is None:
            QMessageBox.information(self, "提示",
                                    f"车牌 {plate} 当前不在场内。")
            self._reset_form()
            self.plate_badge.clear_plate("未在场")
            set_chip(self.status_chip, "不在场内", "warn")
            return

        self._current_record = rec
        self.plate_badge.set_plate(rec["plate_no"])
        set_chip(self.status_chip, "在场 · 待结算", "success")

        entry_time, exit_time, fee, hours, _secs = self._calc(rec)
        discount = self._member_discount(rec)

        self.spot_label.setText(rec["spot_no"])
        self.entry_label.setText(fmt_dt(entry_time))
        self.duration_label.setText(duration_str(entry_time, exit_time))
        if rec["member_flag"]:
            if discount is not None and discount < 1.0:
                self.member_label.setText(f"是（{discount * 10:g} 折）")
            else:
                self.member_label.setText("是（无折扣）")
        else:
            self.member_label.setText("否")

        self.fee_label.setText(f"¥ {fee:g}")
        self.hours_label.setText(f"计费 {hours} 小时（不足 1 小时按 1 小时计）")
        self.settle_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def _member_discount(self, rec) -> Optional[float]:
        """取该车牌的会员折扣；非会员或折扣非法返回 None（走全局默认）。"""
        if not rec.get("member_flag"):
            return None
        m = MemberDAO.find_by_plate(rec["plate_no"])
        if not m:
            return None
        try:
            d = float(m.get("discount") or 1.0)
        except (TypeError, ValueError):
            return None
        return d if 0 < d <= 1.0 else None

    def _calc(self, rec):
        """统一结算计算入口，避免查询与确认两处逻辑漂移。"""
        entry_time = parse_dt(rec["entry_time"]) or now_dt()
        exit_time  = now_dt()
        fee, hours, secs = compute_fee(
            vehicle_type=rec["vehicle_type"],
            entry_time=entry_time,
            exit_time=exit_time,
            member_flag=rec["member_flag"],
            member_discount=self._member_discount(rec),
        )
        return entry_time, exit_time, fee, hours, secs

    # ------------------------------------------------------------------
    def on_settle(self):
        if self._current_record is None:
            QMessageBox.warning(self, "提示", "请先查询在场记录")
            return

        rec = self._current_record
        entry_time, exit_time, fee, hours, secs = self._calc(rec)

        ParkingRecordDAO.update_exit(rec["id"], exit_time, secs, fee)
        ParkingLotManager.on_exit_success()

        logger.info(f"出场：{rec['plate_no']}，费用 {fee} 元")
        QMessageBox.information(
            self, "出场成功",
            f"车牌：{rec['plate_no']}\n"
            f"停车时长：{duration_str(entry_time, exit_time)}\n"
            f"应收费用：{fee} 元\n"
            f"车位已释放。",
        )

        self._reset_form()
        self.plate_edit.clear()
        set_chip(self.status_chip, "已结算", "success")
        self.plate_badge.clear_plate("已结算")

    def _reset_form(self):
        self._current_record = None
        for l in (self.entry_label, self.duration_label,
                  self.member_label, self.spot_label):
            l.setText("—")
        self.fee_label.setText("¥ —")
        self.hours_label.setText("")
        self.settle_btn.setEnabled(False)
