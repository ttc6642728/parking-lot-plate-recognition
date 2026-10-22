# -*- coding: utf-8 -*-
"""
停车记录查询 / 增删改：
    - 表格展示
    - 条件查询（车牌 / 时间段 / 在场/出场）
    - 导出 Excel / CSV
    - 仅管理员可增删改

布局：顶部一条筛选栏（横排比竖排省地方，表格能占到更大宽度），
下面一整块表格卡片，行数显示在卡片标题右侧。
"""

from __future__ import annotations

from PyQt5.QtCore    import Qt as QtQt, QDateTime
from PyQt5.QtGui     import QColor
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QDateTimeEdit,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog,
)

from auth            import get_current_user
from core            import ParkingLotManager
from db.dao          import ParkingRecordDAO
from ui.components   import Card, PageHeader, make_button
from ui.theme        import Color
from utils.constants import ROLE_ADMIN
from utils.exporter  import export_to_excel, export_to_csv
from utils.logger    import get_logger

logger = get_logger()

COLUMNS = ["ID", "车牌", "类型", "车位", "入场时间", "出场时间",
           "时长(秒)", "费用(元)", "会员", "操作员", "备注"]
COLUMN_KEYS = ["id", "plate_no", "vehicle_type", "spot_no", "entry_time",
               "exit_time", "duration_sec", "fee", "member_flag",
               "operator_id", "note"]

class RecordWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        header = PageHeader(
            "停车记录",
            "按车牌与时间段检索出入记录，支持导出 Excel / CSV",
        )

        # ---- 筛选栏 ----
        self.plate_edit = QLineEdit()
        self.plate_edit.setPlaceholderText("车牌（支持模糊）")
        self.plate_edit.setFixedWidth(146)
        self.plate_edit.returnPressed.connect(self.refresh)

        self.start_edit = QDateTimeEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.start_edit.setFixedWidth(172)

        self.end_edit = QDateTimeEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setDateTime(QDateTime.currentDateTime())
        self.end_edit.setFixedWidth(172)

        self.unpaid_chk = QCheckBox("仅看在场的")
        self.unpaid_chk.stateChanged.connect(self.refresh)

        self.search_btn = make_button("查询", "search", "primary")
        self.search_btn.clicked.connect(self.refresh)

        self.export_xlsx_btn = make_button("导出 Excel", "export")
        self.export_xlsx_btn.clicked.connect(self.on_export_excel)

        self.export_csv_btn = make_button("导出 CSV", "export")
        self.export_csv_btn.clicked.connect(self.on_export_csv)

        self.delete_btn = make_button("删除选中", "trash", "danger")
        self.delete_btn.clicked.connect(self.on_delete)
        user = get_current_user()
        if user is None or user.role != ROLE_ADMIN:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("仅管理员可删除记录")

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)
        for cap, w in (("车牌", self.plate_edit),
                       ("从", self.start_edit),
                       ("到", self.end_edit)):
            lb = QLabel(cap)
            lb.setObjectName("fieldLabel")
            row1.addWidget(lb)
            row1.addWidget(w)
        row1.addSpacing(6)
        row1.addWidget(self.unpaid_chk)
        row1.addStretch()
        row1.addWidget(self.search_btn)

        self.count_label = QLabel("共 0 条记录")
        self.count_label.setObjectName("mutedLabel")

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)
        row2.addWidget(self.count_label)
        row2.addStretch()
        row2.addWidget(self.export_xlsx_btn)
        row2.addWidget(self.export_csv_btn)
        row2.addWidget(self.delete_btn)

        filter_card = Card(padding=14)
        filter_card.body.setSpacing(10)
        filter_card.add_layout(row1)
        filter_card.add_layout(row2)

        # ---- 表格 ----
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self._apply_column_width()

        # 空状态遮罩：QTableWidget 自身没有 placeholder 概念
        self.empty_tip = QLabel("没有符合条件的记录", self.table.viewport())
        self.empty_tip.setAlignment(QtQt.AlignCenter)
        self.empty_tip.setStyleSheet(
            f"color:{Color.faint}; font-size:13px; background:transparent;"
        )
        self.empty_tip.hide()

        table_card = Card(padding=12)
        table_card.add(self.table, 1)

        root = QVBoxLayout(self)
        m = 26
        root.setContentsMargins(m, m - 4, m, m)
        root.setSpacing(16)
        root.addWidget(header)
        root.addWidget(filter_card)
        root.addWidget(table_card, 1)

    def _apply_column_width(self):
        """
        列宽策略：除"备注"外全部按内容自适应。
        原来是数值列 Stretch，11 列一挤，"入场时间"就被截成 "2026-10-10 13…"，
        时间显示不全在记录页是硬伤，所以宁可让表格横向滚动。
        """
        hh = self.table.horizontalHeader()
        hh.setMinimumSectionSize(42)
        hh.setStretchLastSection(False)
        for i in range(len(COLUMNS) - 1):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        # 备注列吸收剩余宽度；列多时允许横向滚动，但时间列必须是完整的
        hh.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)

    # ------------------------------------------------------------------
    def refresh(self):
        plate = self.plate_edit.text().strip()
        start = self.start_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        end   = self.end_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        only_unpaid = self.unpaid_chk.isChecked()

        rows = ParkingRecordDAO.search(
            plate_no=plate or None,
            start=start, end=end,
            only_unpaid=only_unpaid,
            limit=5000,
        )

        self.table.setRowCount(0)
        for r in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            values = [r.get(k) for k in COLUMN_KEYS]
            values[8] = "是" if r.get("member_flag") else "否"

            # 未结算记录没有出场时间：显示"在场"，比空白更直观
            in_lot = r.get("exit_time") is None
            if in_lot:
                values[5] = "在场"

            for col, val in enumerate(values):
                if val is None:
                    val = ""
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(QtQt.AlignCenter)
                if in_lot and col == 5:
                    item.setForeground(QColor(Color.success))
                elif col in (0, 7):
                    item.setForeground(QColor(Color.text2))
                self.table.setItem(row_idx, col, item)
        self.table.scrollToTop()

        self.count_label.setText(f"共 {len(rows)} 条记录")
        self._sync_empty_tip()

    def _sync_empty_tip(self):
        self.empty_tip.setGeometry(self.table.viewport().rect())
        self.empty_tip.setVisible(self.table.rowCount() == 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync_empty_tip()

    # ------------------------------------------------------------------
    def on_export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Excel", "parking_records.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        rows = self._rows_as_dict()
        out = export_to_excel(rows, COLUMNS, path)
        QMessageBox.information(self, "导出完成", f"已导出：{out}")

    def on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 CSV", "parking_records.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        rows = self._rows_as_dict()
        out = export_to_csv(rows, COLUMNS, path)
        QMessageBox.information(self, "导出完成", f"已导出：{out}")

    def _rows_as_dict(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount()):
            item = {}
            for c, key in enumerate(COLUMN_KEYS):
                cell = self.table.item(r, c)
                item[COLUMNS[c]] = cell.text() if cell else ""
            out.append(item)
        return out

    # ------------------------------------------------------------------
    def on_delete(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, "提示", "请先选择一条记录")
            return
        rec_id = int(self.table.item(r, 0).text())
        ans = QMessageBox.question(
            self, "确认删除",
            f"确定要删除记录 #{rec_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return

        rec = ParkingRecordDAO.get(rec_id)
        ParkingRecordDAO.delete(rec_id)

        # 删除的是"在场未结算"记录时，必须同步释放车位，
        # 否则 used_spots 只增不减，车位会被永久占死。
        if rec and rec.get("exit_time") is None:
            ParkingLotManager.on_exit_success()
            logger.info(f"删除在场记录 #{rec_id}，已释放车位 {rec.get('spot_no')}")

        logger.info(f"删除记录 #{rec_id}")
        self.refresh()
