# -*- coding: utf-8 -*-
"""
会员管理：
    - 新增 / 修改 / 删除 会员
    - 续期

界面：左侧编辑卡（表单一栏排完），右侧会员列表；点表格行回填表单。
"""

from __future__ import annotations

from PyQt5.QtCore    import Qt as QtQt, QDate
from PyQt5.QtGui     import QColor
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QDateEdit,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox,
)

from auth            import get_current_user
from db.dao          import MemberDAO
from ui.components   import (
    Card, PageHeader, add_form_row, form_layout, h_line, make_button,
)
from ui.theme        import Color
from utils.constants import ROLE_ADMIN
from utils.logger    import get_logger

logger = get_logger()

COLUMNS = ["ID", "车牌", "姓名", "电话", "有效起始", "有效截止", "折扣"]
KEYS    = ["id", "plate_no", "name", "phone", "valid_from", "valid_to", "discount"]


class MemberWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = PageHeader(
            "会员管理",
            "登记会员车牌与有效期，会员车辆出场自动按折扣计费",
        )

        # ---- 左：表单 ----
        self.plate_edit = QLineEdit()
        self.plate_edit.setObjectName("plateInput")
        self.plate_edit.setPlaceholderText("如 京A12345")

        self.name_edit  = QLineEdit()
        self.name_edit.setPlaceholderText("车主姓名")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("联系电话")

        self.from_edit = QDateEdit()
        self.from_edit.setCalendarPopup(True)
        self.from_edit.setDisplayFormat("yyyy-MM-dd")
        self.from_edit.setDate(QDate.currentDate())

        self.to_edit = QDateEdit()
        self.to_edit.setCalendarPopup(True)
        self.to_edit.setDisplayFormat("yyyy-MM-dd")
        self.to_edit.setDate(QDate.currentDate().addYears(1))

        self.discount_spin = QDoubleSpinBox()
        self.discount_spin.setRange(0.1, 1.0)
        self.discount_spin.setSingleStep(0.1)
        self.discount_spin.setDecimals(1)
        self.discount_spin.setValue(0.8)
        self.discount_spin.setSuffix("")

        form = form_layout()
        add_form_row(form, "车牌", self.plate_edit)
        add_form_row(form, "姓名", self.name_edit)
        add_form_row(form, "电话", self.phone_edit)
        add_form_row(form, "生效日期", self.from_edit)
        add_form_row(form, "到期日期", self.to_edit)
        add_form_row(form, "折扣", self.discount_spin)

        self.add_btn = make_button("新增会员", "check", "primary")
        self.add_btn.clicked.connect(self.on_add)
        self.update_btn = make_button("更新选中")
        self.update_btn.clicked.connect(self.on_update)
        self.delete_btn = make_button("删除", "trash", "danger")
        self.delete_btn.clicked.connect(self.on_delete)

        user = get_current_user()
        is_admin = user and user.role == ROLE_ADMIN
        if not is_admin:
            for b in (self.add_btn, self.update_btn, self.delete_btn):
                b.setEnabled(False)
                b.setToolTip("仅管理员可编辑会员信息")

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addWidget(self.update_btn, 1)
        btn_row.addWidget(self.delete_btn)

        form_card = Card("会员信息", hint="点击右侧列表可回填")
        form_card.setFixedWidth(330)
        form_card.add_layout(form)
        form_card.body.addSpacing(6)
        form_card.add(self.add_btn)
        form_card.add_layout(btn_row)
        form_card.body.addSpacing(4)
        form_card.add(h_line())

        tip = QLabel("折扣范围 0.1 ~ 1.0；1.0 表示不打折。\n"
                     "到期后该车牌不再享受会员价，但记录保留。")
        tip.setObjectName("hintLabel")
        tip.setWordWrap(True)
        form_card.add(tip)
        form_card.body.addStretch()

        # ---- 右：表格 ----
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self.table.cellClicked.connect(self._on_row_clicked)

        hh = self.table.horizontalHeader()
        hh.setMinimumSectionSize(46)
        # 不要开 stretchLastSection：它和 ResizeToContents 同时生效时，
        # 最后一列会被拉伸两次，总宽超过视口 → 出现横向滚动条 + 末列被切。
        hh.setStretchLastSection(False)
        for i in range(len(COLUMNS)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        # 只让"姓名"列吸收剩余宽度：日期、电话按内容撑开，才不会被截成 "2026-09…"
        hh.setSectionResizeMode(2, QHeaderView.Stretch)

        self.table_card = Card("会员列表", hint="共 0 位")
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

    # ------------------------------------------------------------------
    def _on_row_clicked(self, row, _col):
        self.plate_edit.setText(self.table.item(row, 1).text())
        self.name_edit.setText(self.table.item(row, 2).text())
        self.phone_edit.setText(self.table.item(row, 3).text())
        self.from_edit.setDate(QDate.fromString(self.table.item(row, 4).text(),
                                                "yyyy-MM-dd"))
        self.to_edit.setDate(QDate.fromString(self.table.item(row, 5).text(),
                                              "yyyy-MM-dd"))
        try:
            self.discount_spin.setValue(float(self.table.item(row, 6).text()))
        except Exception:
            pass

    # ------------------------------------------------------------------
    def refresh(self):
        rows = MemberDAO.list_all()
        self.table.setRowCount(0)
        for r in rows:
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            for c, k in enumerate(KEYS):
                v = r.get(k)
                item = QTableWidgetItem("" if v is None else str(v))
                item.setTextAlignment(QtQt.AlignCenter)
                if c == 1:
                    item.setForeground(QColor(Color.primary))
                self.table.setItem(idx, c, item)
        self.table_card.hint_label.setText(f"共 {len(rows)} 位")

    # ------------------------------------------------------------------
    def on_add(self):
        plate = self.plate_edit.text().strip().upper()
        if not plate:
            QMessageBox.warning(self, "提示", "请输入车牌")
            return
        try:
            MemberDAO.add(
                plate_no=plate,
                name=self.name_edit.text().strip(),
                phone=self.phone_edit.text().strip(),
                valid_from=self.from_edit.date().toString("yyyy-MM-dd"),
                valid_to=self.to_edit.date().toString("yyyy-MM-dd"),
                discount=self.discount_spin.value(),
            )
            QMessageBox.information(self, "成功", "会员已添加")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def on_update(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, "提示", "请先选择一行")
            return
        member_id = int(self.table.item(r, 0).text())
        try:
            MemberDAO.update(
                member_id,
                plate_no=self.plate_edit.text().strip().upper(),
                name=self.name_edit.text().strip(),
                phone=self.phone_edit.text().strip(),
                valid_from=self.from_edit.date().toString("yyyy-MM-dd"),
                valid_to=self.to_edit.date().toString("yyyy-MM-dd"),
                discount=self.discount_spin.value(),
            )
            QMessageBox.information(self, "成功", "会员信息已更新")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def on_delete(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, "提示", "请先选择一行")
            return
        member_id = int(self.table.item(r, 0).text())
        ans = QMessageBox.question(self, "确认", "确定要删除该会员？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        MemberDAO.delete(member_id)
        self.refresh()
