# -*- coding: utf-8 -*-
"""
黑名单管理：新增 / 删除。

界面：左侧录入卡（车牌 + 原因），右侧名单列表。
黑名单是"预警"而非"阻断"，所以列表页用红色标记车牌，提示操作员留意。
"""

from __future__ import annotations

from PyQt5.QtCore    import Qt as QtQt
from PyQt5.QtGui     import QColor
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
)

from auth            import get_current_user
from db.dao          import BlacklistDAO
from ui.components   import (
    Card, PageHeader, add_form_row, form_layout, h_line, make_button,
)
from ui.theme        import Color
from utils.constants import ROLE_ADMIN
from utils.logger    import get_logger

logger = get_logger()

COLUMNS = ["ID", "车牌", "原因", "添加时间"]
KEYS    = ["id", "plate_no", "reason", "created_at"]


class BlacklistWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = PageHeader(
            "黑名单",
            "记录需重点关注的车辆，入场登记时会弹出预警提示",
        )

        self.plate_edit = QLineEdit()
        self.plate_edit.setObjectName("plateInput")
        self.plate_edit.setPlaceholderText("如 京A12345")

        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText("如 欠缴停车费 / 逃费记录")

        form = form_layout()
        add_form_row(form, "车牌", self.plate_edit)
        add_form_row(form, "原因", self.reason_edit)

        self.add_btn = make_button("加入黑名单", "check", "primary")
        self.add_btn.clicked.connect(self.on_add)
        self.del_btn = make_button("移出黑名单", "trash", "danger")
        self.del_btn.clicked.connect(self.on_delete)

        user = get_current_user()
        is_admin = user and user.role == ROLE_ADMIN
        if not is_admin:
            for b in (self.add_btn, self.del_btn):
                b.setEnabled(False)
                b.setToolTip("仅管理员可维护黑名单")

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addWidget(self.add_btn, 1)
        btn_row.addWidget(self.del_btn)

        form_card = Card("新增记录")
        form_card.setFixedWidth(330)
        form_card.add_layout(form)
        form_card.body.addSpacing(6)
        form_card.add_layout(btn_row)
        form_card.body.addSpacing(4)
        form_card.add(h_line())

        tip = QLabel("黑名单只做预警，不阻断入场流程。\n"
                     "如需禁止进入，请配合入口人工核验。")
        tip.setObjectName("hintLabel")
        tip.setWordWrap(True)
        form_card.add(tip)
        form_card.body.addStretch()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)

        hh = self.table.horizontalHeader()
        hh.setMinimumSectionSize(46)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table_card = Card("黑名单列表", hint="共 0 条")
        self.table_card.add(self.table, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        body.addWidget(form_card, 0)
        body.addWidget(self.table_card, 1)

        root = QVBoxLayout(self)
        m = 26
        root.setContentsMargins(m, m - 4, m, m)
        root.setSpacing(16)
        root.addWidget(header)
        root.addLayout(body, 1)

    def refresh(self):
        rows = BlacklistDAO.list_all()
        self.table.setRowCount(0)
        for r in rows:
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            for c, k in enumerate(KEYS):
                v = r.get(k)
                item = QTableWidgetItem("" if v is None else str(v))
                item.setTextAlignment(QtQt.AlignCenter)
                if c == 1:
                    item.setForeground(QColor(Color.danger))
                self.table.setItem(idx, c, item)
        self.table_card.hint_label.setText(f"共 {len(rows)} 条")

    def on_add(self):
        plate = self.plate_edit.text().strip().upper()
        if not plate:
            QMessageBox.warning(self, "提示", "请输入车牌")
            return
        try:
            BlacklistDAO.add(plate, self.reason_edit.text().strip())
            QMessageBox.information(self, "成功", "已加入黑名单")
            self.plate_edit.clear()
            self.reason_edit.clear()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def on_delete(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, "提示", "请先选择一行")
            return
        bid = int(self.table.item(r, 0).text())
        ans = QMessageBox.question(self, "确认", "确定要删除该记录？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        BlacklistDAO.delete(bid)
        self.refresh()
