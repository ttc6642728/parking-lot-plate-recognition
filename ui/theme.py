# -*- coding: utf-8 -*-
"""
统一视觉主题（Design Tokens + 全局 QSS）

为什么单独抽一个模块：
    原来配色、字号、圆角散落在 config.QSS 和各页面的 setStyleSheet 里，
    改一处要翻 8 个文件，且颜色值互相不统一（#2d8cf0 / #1f2d3d / #ed4014）。
    这里把"设计令牌"收敛成一份：改 Color.primary 就能整站换肤。

用法：
    from ui.theme import Color, QSS, apply_shadow, styled
    app.setStyleSheet(QSS)

注意：
    Qt 的 QSS 不支持 CSS 变量，也没有 box-shadow。
    → 颜色用 string.Template 在导入时注入；
    → 阴影用 QGraphicsDropShadowEffect（见 apply_shadow）。
"""

from __future__ import annotations

import string

from PyQt5.QtCore    import Qt
from PyQt5.QtGui     import QColor, QFont, QFontDatabase
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QWidget


# ---------------------------------------------------------------------------
# 设计令牌
# ---------------------------------------------------------------------------
class Color:
    """全站配色。命名按用途而非色相，换肤时只改值不改名。"""

    # 品牌主色（深蓝，商务 / 科技感，投影仪下也够醒目）
    primary      = "#2563EB"
    primary_dark = "#1D4ED8"
    primary_deep = "#1A3FB0"
    primary_soft = "#EFF4FF"
    accent       = "#06B6D4"

    # 中性色
    page      = "#F4F6FB"
    card      = "#FFFFFF"
    border    = "#E6EAF2"
    border_hi = "#C9D5E8"
    text      = "#111C2E"
    text2     = "#475569"
    muted     = "#7C8AA0"
    faint     = "#AEB9CB"

    # 语义色
    success      = "#10B981"
    success_soft = "#ECFDF5"
    warning      = "#F59E0B"
    warning_soft = "#FFFBEB"
    danger       = "#EF4444"
    danger_soft  = "#FEF2F2"

    # 侧边栏（深色，与白色工作区形成层次）
    sb_top   = "#0E1A2B"
    sb_bot   = "#17253C"
    sb_text  = "#93A4BD"
    sb_active = "#FFFFFF"


class Metrics:
    """尺寸规范。改这里，所有卡片 / 控件跟着变。"""
    radius_card   = 12
    radius_input  = 7
    radius_button = 7
    page_margin   = 26
    card_padding  = 18
    gap           = 16
    table_row_h   = 40


FONT_UI   = '"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", "JetBrains Mono", monospace'


# ---------------------------------------------------------------------------
# QSS 模板
# ---------------------------------------------------------------------------
_QSS_TEMPLATE = """
/* ===================== 基础 ===================== */
QWidget {
    font-family: $font_ui;
    font-size: 13px;
    color: $text;
}
QMainWindow { background: $page; }
QDialog     { background: $page; }
QWidget#pageRoot { background: $page; }

QToolTip {
    background: $text;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ===================== 侧边栏 ===================== */
QWidget#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 $sb_top, stop:1 $sb_bot);
}
QLabel#brandName {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 700;
}
QLabel#brandMark {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $primary, stop:1 $accent);
    border-radius: 10px;
}
QLabel#brandSub {
    color: #64748B;
    font-size: 10px;
}
QLabel#navSection {
    color: #55657E;
    font-size: 10px;
    font-weight: 600;
    padding-left: 22px;
}
QListWidget#navList {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#navList::item {
    height: 42px;
    margin: 3px 12px;
    padding-left: 10px;
    border-radius: 8px;
    color: $sb_text;
    font-size: 13px;
}
QListWidget#navList::item:hover {
    background: rgba(255, 255, 255, 0.07);
    color: #E2E8F0;
}
QListWidget#navList::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $primary, stop:1 #3B7BF5);
    color: $sb_active;
    font-weight: 600;
}
QListWidget#navList::item:disabled {
    color: #3E4C60;
}

QFrame#userCard {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
}
QLabel#avatar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $primary, stop:1 $accent);
    color: #FFFFFF;
    border-radius: 17px;
    font-size: 14px;
    font-weight: 700;
}
QLabel#userName  { color: #E8EEF8; font-size: 13px; font-weight: 600; }
QLabel#userRole  { color: #7C8BA3; font-size: 11px; }
QLabel#roleBadge {
    background: rgba(37, 99, 235, 0.22);
    color: #9DBBFF;
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}

QPushButton#logoutBtn {
    background: rgba(239, 68, 68, 0.12);
    color: #FCA5A5;
    border: 1px solid rgba(239, 68, 68, 0.22);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}
QPushButton#logoutBtn:hover {
    background: $danger;
    color: #FFFFFF;
    border-color: $danger;
}

/* ===================== 顶部信息条 ===================== */
QWidget#topBar {
    background: $card;
    border-bottom: 1px solid $border;
}
QLabel#crumbRoot { color: $faint; font-size: 12px; }
QLabel#crumbSep  { color: #D4DCE9; font-size: 12px; }
QLabel#crumbNow  { color: $text; font-size: 12px; font-weight: 600; }
QLabel#clockLabel {
    color: $text2;
    font-size: 12px;
    font-family: $font_mono;
}
QLabel#liveDot {
    color: $success;
    font-size: 13px;
    font-weight: 700;
}
QLabel#liveText { color: $muted; font-size: 11px; }

/* ===================== 页面标题 ===================== */
QLabel#pageTitle {
    font-size: 22px;
    font-weight: 700;
    color: $text;
}
QLabel#pageSub {
    font-size: 12px;
    color: $muted;
}

/* ===================== 卡片 ===================== */
QFrame#card {
    background: $card;
    border: 1px solid $border;
    border-radius: $radius_card;
}
QFrame#cardFlat {
    background: $card;
    border: 1px solid $border;
    border-radius: $radius_card;
}
QFrame#statCard {
    background: $card;
    border: 1px solid $border;
    border-radius: $radius_card;
}
QLabel#cardTitle {
    font-size: 14px;
    font-weight: 700;
    color: $text;
}
QLabel#cardHint {
    font-size: 11px;
    color: $muted;
}
QLabel#cardDivider {
    background: $border;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

/* ===================== 按钮 ===================== */
QPushButton {
    background: #FFFFFF;
    color: $text2;
    border: 1px solid $border;
    border-radius: $radius_button;
    padding: 7px 16px;
    min-height: 20px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    border-color: $border_hi;
    background: #F8FAFF;
    color: $primary;
}
QPushButton:pressed {
    background: #ECF2FF;
    border-color: $primary;
}
QPushButton:disabled {
    background: #F5F7FB;
    color: $faint;
    border-color: $border;
}

QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $primary, stop:1 #3B7BF5);
    color: #FFFFFF;
    border: 1px solid $primary_dark;
    font-weight: 600;
}
QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $primary_dark, stop:1 $primary);
    border-color: $primary_deep;
    color: #FFFFFF;
}
QPushButton#primaryBtn:pressed { background: $primary_deep; }
QPushButton#primaryBtn:disabled {
    background: #C3D2EE;
    border-color: #C3D2EE;
    color: #F6F9FF;
}

QPushButton#dangerBtn {
    background: $danger_soft;
    color: $danger;
    border: 1px solid #FBD5D1;
}
QPushButton#dangerBtn:hover {
    background: $danger;
    color: #FFFFFF;
    border-color: $danger;
}
QPushButton#dangerBtn:disabled {
    background: #F7F8FA;
    color: $faint;
    border-color: $border;
}

QPushButton#ghostBtn {
    background: transparent;
    border: 1px solid $border;
    color: $muted;
}
QPushButton#ghostBtn:hover {
    border-color: $primary;
    color: $primary;
    background: $primary_soft;
}

QPushButton#camBtn:checked {
    background: $danger_soft;
    color: $danger;
    border-color: #FBD5D1;
}
QPushButton#linkBtn {
    background: transparent;
    border: none;
    color: $primary;
    padding: 4px 6px;
    font-size: 12px;
}
QPushButton#linkBtn:hover { color: $primary_dark; }

/* ===================== 输入控件 ===================== */
QLineEdit, QComboBox, QDateTimeEdit, QDateEdit, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    border: 1px solid $border;
    border-radius: $radius_input;
    padding: 6px 10px;
    min-height: 20px;
    color: $text;
    selection-background-color: $primary;
    selection-color: #FFFFFF;
}
QLineEdit:hover, QComboBox:hover, QDateTimeEdit:hover,
QDateEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: $border_hi;
}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus,
QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: $primary;
    background: #FCFDFF;
}
QLineEdit:disabled, QComboBox:disabled, QDateTimeEdit:disabled,
QDateEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #F7F9FC;
    color: $faint;
    border-color: $border;
}

QLineEdit#plateInput {
    font-family: $font_mono;
    font-size: 16px;
    font-weight: 700;
    padding: 8px 12px;
    border: 2px solid $border;
    border-radius: 8px;
}
QLineEdit#plateInput:focus {
    border-color: $primary;
    background: $primary_soft;
}

QComboBox::drop-down {
    width: 22px;
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: $primary_soft;
    selection-color: $primary;
}
QComboBox QAbstractItemView::item {
    height: 28px;
    padding-left: 8px;
    border-radius: 5px;
    color: $text2;
}

QDateTimeEdit::up-button, QDateTimeEdit::down-button,
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 15px;
    border: none;
    background: transparent;
}
QDateTimeEdit::drop-down, QDateEdit::drop-down {
    width: 20px;
    border: none;
    background: transparent;
}

QCheckBox {
    spacing: 7px;
    color: $text2;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid $border_hi;
    border-radius: 4px;
    background: #FFFFFF;
}
QCheckBox::indicator:hover { border-color: $primary; }
QCheckBox::indicator:checked {
    background: $primary;
    border-color: $primary;
}

/* ===================== 表单标签 ===================== */
QLabel#fieldLabel {
    color: $text2;
    font-size: 12px;
    font-weight: 500;
    padding-right: 4px;
}
QLabel#valueLabel {
    color: $text;
    font-size: 13px;
    font-weight: 600;
}
QLabel#valueMono {
    color: $text;
    font-size: 13px;
    font-weight: 600;
    font-family: $font_mono;
}
QLabel#mutedLabel  { color: $muted; font-size: 12px; }
QLabel#amountLabel {
    color: $danger;
    font-size: 26px;
    font-weight: 800;
    font-family: $font_mono;
}
QLabel#hintLabel {
    color: $muted;
    font-size: 12px;
    background: $page;
    border: 1px dashed $border;
    border-radius: 8px;
    padding: 10px 12px;
}

/* ===================== 车牌展示 ===================== */
QLabel#plateBadge {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2B62E8, stop:1 $primary_deep);
    color: #FFFFFF;
    border: 2px solid #7BA0F5;
    border-radius: 9px;
    font-size: 30px;
    font-weight: 800;
    padding: 12px 10px;
}
QLabel#plateBadgeEmpty {
    background: #F4F6FB;
    color: $faint;
    border: 2px dashed $border_hi;
    border-radius: 9px;
    font-size: 22px;
    font-weight: 700;
    padding: 14px 10px;
}

/* ===================== 指标卡 ===================== */
QLabel#statValue {
    font-size: 25px;
    font-weight: 800;
    color: $text;
    font-family: $font_mono;
}
QLabel#statValueAccent {
    font-size: 25px;
    font-weight: 800;
    color: $primary;
    font-family: $font_mono;
}
QLabel#statLabel {
    font-size: 11px;
    color: $muted;
}
QLabel#statUnit {
    font-size: 12px;
    color: $muted;
    font-weight: 500;
}

/* ===================== 状态徽章 ===================== */
QLabel#chipSuccess {
    background: $success_soft;
    color: #0F9D70;
    border: 1px solid #B9EBD8;
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#chipWarn {
    background: $warning_soft;
    color: #B45309;
    border: 1px solid #FDE6B8;
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#chipDanger {
    background: $danger_soft;
    color: $danger;
    border: 1px solid #FBD5D1;
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#chipInfo {
    background: $primary_soft;
    color: $primary_dark;
    border: 1px solid #D3E0FB;
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* ===================== 图像显示区 ===================== */
QLabel#imageCanvas {
    background: #0B1220;
    color: #6B7C93;
    font-size: 13px;
    border: 1px solid #1E293B;
    border-radius: 10px;
}

/* ===================== 表格 ===================== */
QTableWidget {
    background: #FFFFFF;
    border: none;
    gridline-color: #F1F4FA;
    outline: none;
    selection-background-color: $primary_soft;
    selection-color: $text;
    alternate-background-color: #FAFCFF;
}
QTableWidget::item {
    padding: 4px 8px;
    border: none;
    border-bottom: 1px solid #F4F6FB;
}
QTableWidget::item:selected {
    background: $primary_soft;
    color: $primary_dark;
    font-weight: 600;
}
QHeaderView::section {
    background: #F7F9FD;
    color: $muted;
    font-size: 11px;
    font-weight: 700;
    border: none;
    border-bottom: 1px solid $border;
    padding: 9px 8px;
}
QTableCornerButton::section {
    background: #F7F9FD;
    border: none;
    border-bottom: 1px solid $border;
}

/* ===================== 列表 ===================== */
QListWidget#historyList {
    background: #FBFCFF;
    border: 1px solid $border;
    border-radius: 9px;
    outline: none;
    padding: 4px;
}
QListWidget#historyList::item {
    height: 32px;
    padding-left: 8px;
    border-radius: 6px;
    color: $text2;
    font-size: 12px;
}
QListWidget#historyList::item:hover { background: #F1F5FD; }
QListWidget#historyList::item:selected {
    background: $primary_soft;
    color: $primary;
    font-weight: 600;
}

/* ===================== 进度条 ===================== */
QProgressBar {
    background: #EEF1F7;
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: rgba(0, 0, 0, 0);
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $primary, stop:1 $accent);
    border-radius: 4px;
}
QProgressBar#warnBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #F59E0B, stop:1 #F97316);
}
QProgressBar#dangerBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #EF4444, stop:1 #F97316);
}

/* ===================== 滚动条 ===================== */
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #CFD8E6;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #AEBCCF; }
QScrollBar:horizontal {
    background: transparent;
    height: 9px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #CFD8E6;
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover { background: #AEBCCF; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ===================== 状态栏 ===================== */
QStatusBar {
    background: #FFFFFF;
    border-top: 1px solid $border;
    color: $muted;
    font-size: 11px;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $muted; font-size: 11px; }

/* ===================== 兼容旧版 GroupBox ===================== */
QGroupBox {
    background: $card;
    border: 1px solid $border;
    border-radius: $radius_card;
    margin-top: 12px;
    padding: 18px 16px 14px 16px;
    font-weight: 700;
    color: $text;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 6px;
    color: $text;
    background: $card;
}

/* ===================== 登录页 ===================== */
QWidget#loginRoot { background: $page; }
QWidget#loginPanel {
    background: $card;
}
QFrame#loginCard {
    background: $card;
    border: 1px solid $border;
    border-radius: 16px;
}
QLabel#loginTitle {
    font-size: 21px;
    font-weight: 800;
    color: $text;
}
QLabel#loginSub {
    font-size: 12px;
    color: $muted;
}
QLabel#loginBrandMark {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $primary, stop:1 $accent);
    border-radius: 12px;
}
QLabel#loginError {
    background: $danger_soft;
    color: $danger;
    border: 1px solid #FBD5D1;
    border-radius: 7px;
    padding: 8px 10px;
    font-size: 12px;
}
QFrame#loginBanner {
    background: qlineargradient(x1:0, y1:0, x2:0.6, y2:1,
                                stop:0 #0F1E36, stop:0.55 #17325C, stop:1 #1E4B8F);
    border-radius: 16px;
}
QLabel#bannerTitle { color: #FFFFFF; font-size: 22px; font-weight: 800; }
QLabel#bannerDesc  { color: #A8C0E0; font-size: 12px; }
QLabel#bannerPoint { color: #C7D8F0; font-size: 12px; }
QLabel#bannerBadge {
    background: rgba(255, 255, 255, 0.10);
    color: #D6E4FA;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 11px;
}
"""


def _palette_map() -> dict:
    out = {}
    for cls in (Color, Metrics):
        for k, v in vars(cls).items():
            if k.startswith("_") or not isinstance(v, (str, int)):
                continue
            out[k.lower()] = str(v) if not isinstance(v, int) else f"{v}px"
    out["font_ui"]   = FONT_UI
    out["font_mono"] = FONT_MONO
    return out


QSS = string.Template(_QSS_TEMPLATE).substitute(_palette_map())


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def apply_shadow(widget: QWidget,
                 blur: int = 22,
                 dy: int = 6,
                 color: str = "#8FA3BF",
                 alpha: int = 38) -> QGraphicsDropShadowEffect:
    """
    给控件加投影。

    ⚠ 只给"叶子级"容器用（指标卡、登录卡片）。
      给包含 QTableWidget 的大容器加阴影会让整棵子树走离屏渲染，
      滚动时明显掉帧。
    """
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setColor(c)
    widget.setGraphicsEffect(eff)
    return eff


def styled(widget: QWidget) -> QWidget:
    """让纯 QWidget 也响应 QSS 的 background / border-radius。"""
    widget.setAttribute(Qt.WA_StyledBackground, True)
    return widget


def pick_ui_font(size: int = 10, weight: int = QFont.Normal) -> QFont:
    """挑一个系统里真实存在的中文字体，避免渲染成方框。"""
    families = {f.family() for f in QFontDatabase().families()}
    for name in ("Microsoft YaHei UI", "Microsoft YaHei",
                 "PingFang SC", "Noto Sans CJK SC", "SimHei"):
        if name in families:
            return QFont(name, size, weight)
    return QFont("", size, weight)
