# -*- coding: utf-8 -*-
"""
数据统计与可视化：
    - 选择起止日期
    - 按天统计车流与营收
    - matplotlib 画图（车流柱状图、营收折线图）
    - 导出 Excel/CSV

布局：顶部四个指标卡（一眼看结论），下面是趋势图。
图表配色沿用主题色，避免默认蓝橙和整站风格打架。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PyQt5.QtCore    import Qt as QtQt, QDate
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QDateEdit, QFileDialog,
    QMessageBox,
)

from db.dao          import ParkingRecordDAO, ParkingLotDAO
from ui.components   import Card, PageHeader, StatCard, make_button
from ui.theme        import Color
from utils.exporter  import export_to_excel, export_to_csv
from utils.logger    import get_logger

logger = get_logger()


def _setup_chinese_font() -> None:
    """
    matplotlib 默认字体（DejaVu Sans）不含中文字形，
    不设置的话图表标题/坐标轴上的中文会全部渲染成方框。
    """
    import matplotlib
    from matplotlib import font_manager

    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei", "SimHei", "PingFang SC",
                 "Heiti SC", "WenQuanYi Micro Hei", "Noto Sans CJK SC"):
        if name in available:
            matplotlib.rcParams["font.sans-serif"] = [name]
            break
    # 负号也要单独指定，否则 -1 会显示成方块
    matplotlib.rcParams["axes.unicode_minus"] = False


class StatsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = PageHeader(
            "数据统计与可视化",
            "按天统计车流与营收，支持导出 Excel / CSV",
        )

        # ---------- 指标卡 ----------
        self.stat_cnt     = StatCard("区间总车次", "0", "次", Color.primary)
        self.stat_revenue = StatCard("区间总营收", "0", "元", Color.warning)
        self.stat_avg     = StatCard("日均车次", "0", "次", Color.accent)
        self.stat_rate    = StatCard("车位使用率", "0", "%", Color.success)

        cards = QHBoxLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(12)
        for c in (self.stat_cnt, self.stat_revenue,
                  self.stat_avg, self.stat_rate):
            cards.addWidget(c, 1)

        # ---------- 图表卡 ----------
        self.from_edit = QDateEdit()
        self.from_edit.setCalendarPopup(True)
        self.from_edit.setDisplayFormat("yyyy-MM-dd")
        self.from_edit.setDate(QDate.currentDate().addDays(-6))
        self.from_edit.setFixedWidth(122)
        self.from_edit.dateChanged.connect(self.refresh)

        self.to_edit = QDateEdit()
        self.to_edit.setCalendarPopup(True)
        self.to_edit.setDisplayFormat("yyyy-MM-dd")
        self.to_edit.setDate(QDate.currentDate())
        self.to_edit.setFixedWidth(122)
        self.to_edit.dateChanged.connect(self.refresh)

        self.refresh_btn = make_button("刷新", "refresh")
        self.refresh_btn.clicked.connect(self.refresh)

        self.export_xlsx_btn = make_button("导出 Excel", "export")
        self.export_xlsx_btn.clicked.connect(self.on_export_excel)

        self.export_csv_btn = make_button("导出 CSV", "export")
        self.export_csv_btn.clicked.connect(self.on_export_csv)

        chart_card = Card("车流与营收趋势", hint="双轴对比")

        ctl = QHBoxLayout()
        ctl.setContentsMargins(0, 0, 0, 0)
        ctl.setSpacing(6)
        for cap, w in (("从", self.from_edit), ("至", self.to_edit)):
            lb = QLabel(cap)
            lb.setObjectName("fieldLabel")
            ctl.addWidget(lb)
            ctl.addWidget(w)
        ctl.addSpacing(6)
        ctl.addWidget(self.refresh_btn)
        ctl.addWidget(self.export_xlsx_btn)
        ctl.addWidget(self.export_csv_btn)
        chart_card.add_row(ctl)

        from matplotlib.backends.backend_qt5agg import (
            FigureCanvasQTAgg as FigureCanvas,
        )
        from matplotlib.figure import Figure
        _setup_chinese_font()
        self.fig = Figure(figsize=(8, 4), dpi=100,
                          facecolor=Color.card)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumHeight(300)
        chart_card.add(self.canvas, 1)

        root = QVBoxLayout(self)
        m = 26
        root.setContentsMargins(m, m - 4, m, m)
        root.setSpacing(16)
        root.addWidget(header)
        root.addLayout(cards)
        root.addWidget(chart_card, 1)

    # ------------------------------------------------------------------
    def refresh(self):
        # 停车场状态
        st = ParkingLotDAO.get_status()
        used, total = st["used_spots"], st["total_spots"]
        rate = (used / total * 100) if total else 0

        start = self.from_edit.date().toString("yyyy-MM-dd") + " 00:00:00"
        end   = self.to_edit.date().toString("yyyy-MM-dd") + " 23:59:59"
        # 车流与营收来自同一条 SQL，保证两个数字口径一致
        rows = ParkingRecordDAO.daily_stats(start, end)
        total_cnt  = sum(int(r["cnt"]) for r in rows)
        total_reve = sum(float(r["revenue"]) for r in rows)
        rows = self._fill_days(rows)          # 图表用补齐后的连续日期

        days = max(1, self.from_edit.date().daysTo(self.to_edit.date()) + 1)
        avg = total_cnt / days

        self.stat_cnt.set_value(f"{total_cnt}")
        self.stat_revenue.set_value(f"{total_reve:.0f}")
        self.stat_avg.set_value(f"{avg:.1f}")
        self.stat_rate.set_value(f"{rate:.0f}")

        self.stat_rate.set_value(
            f"{rate:.0f}",
            Color.danger if rate >= 90 else (
                Color.warning if rate >= 70 else Color.success
            ),
        )

        self._plot(rows)

    # ------------------------------------------------------------------
    def _fill_days(self, rows) -> list[dict]:
        """
        补齐区间内没有记录的日期。

        daily_stats 只返回"有数据的天"，直接画会导致 10-11 和 10-13 相邻，
        看起来像连续两天，趋势图会骗人。这里按日历补齐，空缺填 0。
        """
        by_day = {}
        for r in rows:
            key = str(r["date"])[:10]
            by_day[key] = {"cnt": int(r["cnt"]), "revenue": float(r["revenue"])}

        d0 = self.from_edit.date().toPyDate()
        d1 = self.to_edit.date().toPyDate()
        out = []
        day = d0
        while day <= d1:
            key = day.strftime("%Y-%m-%d")
            v = by_day.get(key, {"cnt": 0, "revenue": 0.0})
            out.append({"date": key, "cnt": v["cnt"], "revenue": v["revenue"]})
            day += timedelta(days=1)
        return out

    def _plot(self, rows):
        self.fig.clear()
        self.fig.patch.set_facecolor(Color.card)

        ax1 = self.fig.add_subplot(111)
        ax1.set_facecolor(Color.card)

        # 统一的"轻"坐标系：只留左、下轴线
        for side in ("top", "right"):
            ax1.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax1.spines[side].set_color(Color.border)
        ax1.tick_params(colors=Color.muted, labelsize=8, length=0)

        if not rows:
            ax1.text(0.5, 0.5, "所选区间暂无数据", ha="center", va="center",
                     transform=ax1.transAxes, fontsize=12,
                     color=Color.faint)
            ax1.set_xticks([])
            ax1.set_yticks([])
            for side in ("left", "bottom"):
                ax1.spines[side].set_visible(False)
            self.fig.tight_layout()
            self.canvas.draw()
            return

        dates    = [str(r["date"])[5:] for r in rows]   # 只留 MM-DD，横轴不挤
        counts   = [int(r["cnt"]) for r in rows]
        revenues = [float(r["revenue"]) for r in rows]

        x = list(range(len(dates)))
        ax1.bar(x, counts, color=Color.primary, width=0.5,
                label="车流（次）", zorder=3)
        ax1.set_xticks(x)
        # 天数少的时候横着放得下，没必要斜着看
        rot = 40 if len(dates) > 10 else 0
        ax1.set_xticklabels(dates, rotation=rot,
                            ha="right" if rot else "center")
        ax1.set_ylabel("车流（次）", color=Color.text2, fontsize=9)
        ax1.grid(axis="y", linestyle="--", linewidth=0.8,
                 color="#EEF1F7", zorder=0)
        ax1.set_axisbelow(True)

        ax2 = ax1.twinx()
        ax2.plot(x, revenues, color=Color.warning, marker="o",
                 markersize=4, linewidth=2, label="营收（元）", zorder=4)
        ax2.set_ylabel("营收（元）", color=Color.text2, fontsize=9)
        ax2.tick_params(colors=Color.muted, labelsize=8, length=0)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_color(Color.border)
        for side in ("left", "bottom"):
            ax2.spines[side].set_visible(False)

        # 顶部留白，避免柱子顶到卡片边缘
        ax1.set_ylim(0, max(counts) * 1.25 if max(counts) else 1)

        handles1, labels1 = ax1.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(handles1 + handles2, labels1 + labels2,
                   loc="upper left", frameon=False, fontsize=8,
                   ncol=2, handlelength=1.6)

        self.fig.tight_layout()
        self.canvas.draw()

    # ------------------------------------------------------------------
    def _rows_export(self) -> list[dict]:
        start = self.from_edit.date().toString("yyyy-MM-dd") + " 00:00:00"
        end   = self.to_edit.date().toString("yyyy-MM-dd") + " 23:59:59"
        rows = ParkingRecordDAO.daily_stats(start, end)
        return [{"日期": r["date"],
                 "车流（次）": r["cnt"],
                 "营收（元）": r["revenue"]} for r in rows]

    def on_export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Excel", "stats.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        cols = ["日期", "车流（次）", "营收（元）"]
        out = export_to_excel(self._rows_export(), cols, path)
        QMessageBox.information(self, "导出完成", f"已导出：{out}")

    def on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 CSV", "stats.csv", "CSV (*.csv)",
        )
        if not path:
            return
        cols = ["日期", "车流（次）", "营收（元）"]
        out = export_to_csv(self._rows_export(), cols, path)
        QMessageBox.information(self, "导出完成", f"已导出：{out}")
