# -*- coding: utf-8 -*-
"""
可复用界面组件。

之前每个页面各写各的布局：标题字号靠手写 setStyleSheet、按钮颜色靠
objectName 碰运气、间距靠 addSpacing 拍脑袋，于是 8 个页面 8 种观感。
这里把"标题区 / 卡片 / 指标卡 / 车牌展示 / 表单行 / 状态徽章"统一实现，
页面只负责往里填内容。

约定：
    · 所有间距、圆角、颜色都取自 ui.theme，页面里不要再写十六进制色值；
    · 卡片内容用 card.body 这个 QVBoxLayout 承载。
"""

from __future__ import annotations

from PyQt5.QtCore    import QSize, Qt as QtQt
from PyQt5.QtGui     import QFont
from PyQt5.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QSizePolicy,
)

from ui.icons import icon as _icon
from ui.theme import Color, Metrics, apply_shadow


# ---------------------------------------------------------------------------
# 页面标题
# ---------------------------------------------------------------------------
class PageHeader(QWidget):
    """页面标题 + 说明文字 + 可选右上角操作区。"""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        col.addWidget(self.title_label)

        self.sub_label = QLabel(subtitle)
        self.sub_label.setObjectName("pageSub")
        self.sub_label.setVisible(bool(subtitle))
        col.addWidget(self.sub_label)

        row.addLayout(col)
        row.addStretch()

        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        row.addLayout(self.actions)

    def add_action(self, widget: QWidget) -> QWidget:
        self.actions.addWidget(widget)
        return widget


# ---------------------------------------------------------------------------
# 卡片
# ---------------------------------------------------------------------------
class Card(QFrame):
    """
    白底圆角卡片，可选标题行。

        card = Card("识别结果", hint="双引擎仲裁")
        card.add(some_widget)
        card.add_layout(layout, 1)
    """

    def __init__(self, title: str = "", hint: str = "", parent=None,
                 padding: int = None, divider: bool = False):
        super().__init__(parent)
        self.setObjectName("card")
        pad = Metrics.card_padding if padding is None else padding

        outer = QVBoxLayout(self)
        outer.setContentsMargins(pad, pad, pad, pad)
        outer.setSpacing(12)

        self.head = QHBoxLayout()
        self.head.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setVisible(bool(title))
        self.head.addWidget(self.title_label)

        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("cardHint")
        self.hint_label.setVisible(bool(hint))
        self.head.addWidget(self.hint_label)
        self.head.addStretch()

        if title or hint:
            outer.addLayout(self.head)

        if divider:
            outer.addWidget(h_line())

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        outer.addLayout(self.body, 1)

    # -- 内容挂载 ---------------------------------------------------------
    def add(self, widget: QWidget, stretch: int = 0):
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout, stretch: int = 0):
        self.body.addLayout(layout, stretch)
        return layout

    def add_row(self, layout):
        self.head.addLayout(layout)
        return layout


class StatCard(QFrame):
    """指标卡：左侧色条 + 标签 + 大号数值。"""

    def __init__(self, label: str, value: str = "—", unit: str = "",
                 color: str = Color.primary, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 16, 12)
        row.setSpacing(12)

        self.bar = QFrame()
        self.bar.setFixedWidth(3)
        self.bar.setStyleSheet(
            f"background:{color}; border:none; border-radius:1px;"
        )
        row.addWidget(self.bar)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        self.label = QLabel(label)
        self.label.setObjectName("statLabel")
        col.addWidget(self.label)

        val_row = QHBoxLayout()
        val_row.setContentsMargins(0, 0, 0, 0)
        val_row.setSpacing(4)
        self.value = QLabel(value)
        self.value.setObjectName(
            "statValueAccent" if color == Color.primary else "statValue"
        )
        if color != Color.primary:
            self.value.setStyleSheet(f"color:{color};")
        val_row.addWidget(self.value)
        self.unit = QLabel(unit)
        self.unit.setObjectName("statUnit")
        self.unit.setVisible(bool(unit))
        val_row.addWidget(self.unit, 0, QtQt.AlignBottom)
        val_row.addStretch()
        col.addLayout(val_row)

        row.addLayout(col, 1)
        apply_shadow(self, blur=14, dy=3, alpha=22)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value.setText(str(text))
        if color:
            self.value.setStyleSheet(f"color:{color};")


# ---------------------------------------------------------------------------
# 车牌展示
# ---------------------------------------------------------------------------
class PlateBadge(QLabel):
    """
    仿车牌的蓝色号牌块。

    没有识别结果时显示虚框占位，避免右侧出现一块刺眼的大红字。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(QtQt.AlignCenter)
        self.setMinimumHeight(84)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.clear_plate()

    def _apply_spacing(self, px: int) -> None:
        f = QFont(self.font())
        # QSS 不支持 letter-spacing，只能走 QFont
        f.setLetterSpacing(QFont.AbsoluteSpacing, px)
        self.setFont(f)

    def set_plate(self, plate: str) -> None:
        self.setObjectName("plateBadge")
        self.setText(plate)
        self._restyle()
        self._apply_spacing(5)

    def clear_plate(self, text: str = "等待识别") -> None:
        self.setObjectName("plateBadgeEmpty")
        self.setText(text)
        self._restyle()
        self._apply_spacing(3)

    def _restyle(self) -> None:
        # objectName 变了必须重新 polish，否则 QSS 不会重新匹配
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def h_line() -> QFrame:
    """1px 分隔线。"""
    ln = QFrame()
    ln.setObjectName("cardDivider")
    ln.setFixedHeight(1)
    ln.setStyleSheet(f"background:{Color.border}; border:none;")
    return ln


def field_label(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("fieldLabel")
    return lb


def value_label(text: str = "—", mono: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("valueMono" if mono else "valueLabel")
    return lb


_CHIP_OBJECT = {
    "info": "chipInfo", "success": "chipSuccess",
    "warn": "chipWarn", "danger": "chipDanger",
}


def repolish(widget: QWidget) -> None:
    """
    改完 objectName 必须重新 polish。
    Qt 的 QSS 只在属性变化 / polish 时重新匹配，光改 objectName 不会换样式。
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def chip(text: str, kind: str = "info") -> QLabel:
    """状态徽章。kind: info / success / warn / danger"""
    lb = QLabel(text)
    lb.setObjectName(_CHIP_OBJECT.get(kind, "chipInfo"))
    lb.setAlignment(QtQt.AlignCenter)
    lb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return lb


def set_chip(lb: QLabel, text: str, kind: str = "info") -> None:
    """原地切换徽章文案与配色（成功 / 警告 / 失败）。"""
    lb.setText(text)
    lb.setObjectName(_CHIP_OBJECT.get(kind, "chipInfo"))
    repolish(lb)


def form_layout(label_width: int = 76) -> QFormLayout:
    """统一行距 / 标签对齐的表单布局。"""
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setVerticalSpacing(11)
    form.setHorizontalSpacing(10)
    form.setLabelAlignment(QtQt.AlignLeft | QtQt.AlignVCenter)
    form.setFormAlignment(QtQt.AlignLeft | QtQt.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    return form


def add_form_row(form: QFormLayout, label: str, widget: QWidget) -> QWidget:
    form.addRow(field_label(label), widget)
    return widget


def mark_primary(btn: QPushButton) -> QPushButton:
    btn.setObjectName("primaryBtn")
    btn.setCursor(QtQt.PointingHandCursor)
    return btn


def mark_danger(btn: QPushButton) -> QPushButton:
    btn.setObjectName("dangerBtn")
    btn.setCursor(QtQt.PointingHandCursor)
    return btn


def mark_ghost(btn: QPushButton) -> QPushButton:
    btn.setObjectName("ghostBtn")
    btn.setCursor(QtQt.PointingHandCursor)
    return btn


def make_button(text: str, icon_name: str = "", kind: str = "normal",
                size: int = 15) -> QPushButton:
    """
    统一按钮工厂。
    kind: primary / danger / ghost / normal
    """
    btn = QPushButton(text)
    btn.setCursor(QtQt.PointingHandCursor)
    btn.setMinimumHeight(34)

    if icon_name:
        color = "#FFFFFF" if kind == "primary" else (
            Color.danger if kind == "danger" else Color.muted
        )
        btn.setIcon(_icon(icon_name, size, color))
        btn.setIconSize(QSize(size, size))

    if kind == "primary":
        mark_primary(btn)
    elif kind == "danger":
        mark_danger(btn)
    elif kind == "ghost":
        mark_ghost(btn)
    return btn


def page_root() -> tuple[QWidget, QVBoxLayout]:
    """
    页面根容器：统一外边距。

    返回 (widget, layout)，页面把自己的内容 add 到 layout 上即可。
    """
    w = QWidget()
    w.setObjectName("pageRoot")
    w.setAttribute(QtQt.WA_StyledBackground, True)
    lay = QVBoxLayout(w)
    m = Metrics.page_margin
    lay.setContentsMargins(m, m - 4, m, m)
    lay.setSpacing(Metrics.gap)
    return w, lay


def h_box(*widgets, spacing: int = 8) -> QHBoxLayout:
    """横向布局速写：widget 依次排列，传 None 则表示此处加一个弹簧。"""
    h = QHBoxLayout()
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(spacing)
    for w in widgets:
        if w is None:
            h.addStretch()
        else:
            h.addWidget(w)
    return h


def max_width(widget: QWidget, width: int) -> QWidget:
    widget.setMaximumWidth(width)
    return widget
