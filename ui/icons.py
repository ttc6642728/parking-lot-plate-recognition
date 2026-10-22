# -*- coding: utf-8 -*-
"""
界面图标：全部用 QPainter 现画，不依赖任何 png / 图标字体。

理由：
    · 项目要能离线跑、拷到别人电脑上直接交作业；
    · 引入 QtAwesome / FontAwesome 会多一个第三方依赖；
    · 图标字体在 Windows 上跨版本渲染差异大（缺字形就变方块）。

所有图标在 24x24 的逻辑坐标里绘制，再由 _render() 按目标尺寸缩放，
因此 16px（导航）和 40px（登录页 logo）都清晰。
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui  import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from ui.theme import Color

_VIEW = 24.0          # 逻辑画布边长


# ---------------------------------------------------------------------------
# 各图标的绘制过程
# ---------------------------------------------------------------------------
def _scan(p: QPainter) -> None:
    """扫描框 + 中线：车牌识别。"""
    L = 5.0
    for sx, sy, dx, dy in ((1, 1, 1, 1), (1, -1, 1, -1),
                           (-1, 1, -1, 1), (-1, -1, -1, -1)):
        cx = 12 + sx * 8.5
        cy = 12 + sy * 8.5
        p.drawLine(QPointF(cx, cy), QPointF(cx + dx * L, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * L))
    p.drawLine(QPointF(8.6, 12), QPointF(15.4, 12))


def _entry(p: QPainter) -> None:
    """向下箭头 + 底托：驶入。"""
    p.drawLine(QPointF(12, 3.8), QPointF(12, 14.5))
    p.drawLine(QPointF(8.2, 10.6), QPointF(12, 14.6))
    p.drawLine(QPointF(15.8, 10.6), QPointF(12, 14.6))
    p.drawLine(QPointF(5, 19.4), QPointF(19, 19.4))


def _exit(p: QPainter) -> None:
    """向上箭头 + 顶托：驶出。"""
    p.drawLine(QPointF(12, 14.6), QPointF(12, 3.9))
    p.drawLine(QPointF(8.2, 7.9), QPointF(12, 3.9))
    p.drawLine(QPointF(15.8, 7.9), QPointF(12, 3.9))
    p.drawLine(QPointF(5, 19.4), QPointF(19, 19.4))


def _record(p: QPainter) -> None:
    """清单：停车记录。"""
    path = QPainterPath()
    path.addRoundedRect(QRectF(3.6, 4.2, 16.8, 15.6), 2.6, 2.6)
    p.drawPath(path)
    for y in (8.6, 12.0, 15.4):
        p.drawLine(QPointF(7.4, y), QPointF(16.6, y))


def _member(p: QPainter) -> None:
    """人像：会员。"""
    p.drawEllipse(QPointF(12, 8.6), 3.4, 3.4)
    path = QPainterPath()
    path.moveTo(4.9, 19.6)
    path.arcTo(QRectF(4.9, 13.2, 14.2, 12.8), 180, -180)
    p.drawPath(path)


def _blacklist(p: QPainter) -> None:
    """禁止符：黑名单。"""
    p.drawEllipse(QPointF(12, 12), 8.1, 8.1)
    d = 8.1 / math.sqrt(2)
    p.drawLine(QPointF(12 - d, 12 - d), QPointF(12 + d, 12 + d))


def _stats(p: QPainter) -> None:
    """柱状图：数据统计。"""
    p.drawLine(QPointF(4.2, 19.6), QPointF(19.8, 19.6))
    for x, top in ((7.0, 13.0), (12.0, 7.4), (17.0, 10.6)):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x - 1.5, top, 3.0, 19.4 - top), 1.2, 1.2)
        p.fillPath(path, p.pen().color())


def _plate(p: QPainter) -> None:
    """车牌：品牌标识。"""
    path = QPainterPath()
    path.addRoundedRect(QRectF(2.6, 6.6, 18.8, 10.8), 2.2, 2.2)
    p.drawPath(path)
    p.drawLine(QPointF(6.4, 12.0), QPointF(9.8, 12.0))
    p.drawLine(QPointF(12.0, 9.4), QPointF(12.0, 14.6))
    p.drawLine(QPointF(14.2, 12.0), QPointF(17.6, 12.0))


def _user(p: QPainter) -> None:
    """单人：登录用户名。"""
    _member(p)


def _lock(p: QPainter) -> None:
    """锁：登录密码。"""
    path = QPainterPath()
    path.addRoundedRect(QRectF(4.6, 10.6, 14.8, 9.6), 2.4, 2.4)
    p.drawPath(path)
    arc = QPainterPath()
    arc.moveTo(8.2, 10.4)
    arc.arcTo(QRectF(8.2, 4.2, 7.6, 8.0), 0, 180)
    p.drawPath(arc)


def _eye(p: QPainter) -> None:
    """睁眼：显示密码。"""
    path = QPainterPath()
    path.moveTo(2.6, 12.0)
    path.quadTo(12.0, 4.4, 21.4, 12.0)
    path.quadTo(12.0, 19.6, 2.6, 12.0)
    p.drawPath(path)
    p.drawEllipse(QPointF(12.0, 12.0), 3.1, 3.1)


def _eye_off(p: QPainter) -> None:
    """闭眼 + 斜杠：隐藏密码。"""
    _eye(p)
    p.drawLine(QPointF(4.2, 19.8), QPointF(19.8, 4.2))


def _camera(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(2.8, 6.8, 18.4, 13.0), 2.6, 2.6)
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 13.3), 3.3, 3.3)
    p.drawLine(QPointF(8.4, 6.6), QPointF(9.6, 4.2))
    p.drawLine(QPointF(9.6, 4.2), QPointF(14.4, 4.2))
    p.drawLine(QPointF(14.4, 4.2), QPointF(15.6, 6.6))


def _image(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(3.0, 4.6, 18.0, 14.8), 2.4, 2.4)
    p.drawPath(path)
    p.drawEllipse(QPointF(8.4, 9.4), 1.7, 1.7)
    poly = QPainterPath()
    poly.moveTo(4.6, 17.6)
    poly.lineTo(9.8, 12.2)
    poly.lineTo(14.0, 16.2)
    poly.lineTo(16.4, 13.8)
    poly.lineTo(19.4, 17.6)
    p.drawPath(poly)


def _search(p: QPainter) -> None:
    p.drawEllipse(QPointF(10.6, 10.6), 6.4, 6.4)
    p.drawLine(QPointF(15.4, 15.4), QPointF(20.2, 20.2))


def _export(p: QPainter) -> None:
    p.drawLine(QPointF(12, 4.0), QPointF(12, 14.0))
    p.drawLine(QPointF(8.4, 10.4), QPointF(12, 14.2))
    p.drawLine(QPointF(15.6, 10.4), QPointF(12, 14.2))
    p.drawLine(QPointF(5.0, 19.4), QPointF(19.0, 19.4))


def _refresh(p: QPainter) -> None:
    path = QPainterPath()
    path.arcMoveTo(QRectF(4.6, 4.6, 14.8, 14.8), 55)
    path.arcTo(QRectF(4.6, 4.6, 14.8, 14.8), 55, 285)
    p.drawPath(path)
    p.drawLine(QPointF(17.6, 3.4), QPointF(17.9, 8.0))
    p.drawLine(QPointF(17.9, 8.0), QPointF(13.4, 7.4))


def _check(p: QPainter) -> None:
    p.drawLine(QPointF(4.6, 12.6), QPointF(9.8, 17.8))
    p.drawLine(QPointF(9.8, 17.8), QPointF(19.4, 6.2))


def _trash(p: QPainter) -> None:
    p.drawLine(QPointF(4.4, 7.0), QPointF(19.6, 7.0))
    p.drawLine(QPointF(9.2, 7.0), QPointF(9.2, 4.4))
    p.drawLine(QPointF(9.2, 4.4), QPointF(14.8, 4.4))
    p.drawLine(QPointF(14.8, 4.4), QPointF(14.8, 7.0))
    path = QPainterPath()
    path.moveTo(6.4, 7.0)
    path.lineTo(7.4, 19.8)
    path.lineTo(16.6, 19.8)
    path.lineTo(17.6, 7.0)
    p.drawPath(path)


_DRAWERS = {
    "scan": _scan, "entry": _entry, "exit": _exit, "record": _record,
    "member": _member, "blacklist": _blacklist, "stats": _stats,
    "plate": _plate, "user": _user, "lock": _lock, "camera": _camera,
    "image": _image, "search": _search, "export": _export,
    "eye": _eye, "eye_off": _eye_off,
    "refresh": _refresh, "check": _check, "trash": _trash,
}


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def pixmap(name: str, size: int = 20,
           color: str = Color.muted, width: float = 1.9) -> QPixmap:
    """把指定图标画成 QPixmap（2x 超采样，高分屏不糊）。"""
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(ratio)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    # QPixmap 设了 devicePixelRatio 之后，painter 的坐标已经是"逻辑像素"，
    # 不能再自己乘 ratio —— 否则会放大一倍、只画出图标左上四分之一。
    p.scale(size / _VIEW, size / _VIEW)

    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    drawer = _DRAWERS.get(name)
    if drawer is not None:
        drawer(p)
    p.end()
    return pm


def icon(name: str, size: int = 20,
         color: str = Color.muted,
         active: str | None = None) -> QIcon:
    """
    生成 QIcon。

    active 给导航用：选中时 QListWidget 会取 QIcon.Selected 模式的图，
    于是图标能和"选中态白色文字"一起变白，不会灰白撞色。
    """
    ic = QIcon()
    ic.addPixmap(pixmap(name, size, color), QIcon.Normal, QIcon.Off)
    if active:
        ic.addPixmap(pixmap(name, size, active), QIcon.Selected, QIcon.Off)
        ic.addPixmap(pixmap(name, size, active), QIcon.Active, QIcon.Off)
    return ic
