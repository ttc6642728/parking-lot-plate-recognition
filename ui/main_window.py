# -*- coding: utf-8 -*-
"""
主窗口：左侧深色导航 + 顶部信息条 + 右侧内容栈。

视觉结构：
    ┌──────────┬────────────────────────────────┐
    │ 品牌     │ 面包屑            时钟 / 状态  │  ← topBar
    │ ──────── ├────────────────────────────────┤
    │ 导航     │                                │
    │  ...     │        QStackedWidget          │
    │ ──────── │        （各功能页）             │
    │ 用户卡片 │                                │
    └──────────┴────────────────────────────────┘

导航图标由 ui/icons.py 现画；页面标题由各页自己的 PageHeader 承担，
顶部条只放"你在哪 / 现在几点"，避免和页面标题重复。
"""

from __future__ import annotations

from PyQt5.QtCore    import Qt as QtQt, QSize, QTimer, QDateTime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QListWidget, QStackedWidget, QListWidgetItem,
    QHBoxLayout, QVBoxLayout, QLabel, QStatusBar, QMessageBox, QFrame,
    QPushButton, QSizePolicy,
)

from auth    import get_auth, get_current_user
from config  import APP_TITLE
from ui.icons import icon as _icon, pixmap as _pixmap
from ui.theme import Color
from ui.components import make_button

# 注意：必须从子模块直接导入。
# 若写成 `from ui import xxx`，会与 ui/__init__.py 形成循环导入导致启动失败。
from ui.recognize_widget  import RecognizeWidget
from ui.entry_widget      import EntryWidget
from ui.exit_widget       import ExitWidget
from ui.record_widget     import RecordWidget
from ui.member_widget     import MemberWidget
from ui.blacklist_widget  import BlacklistWidget
from ui.stats_widget      import StatsWidget
from utils.constants import ROLE_ADMIN
from utils.logger import get_logger

logger = get_logger()

# (名称, 图标名) —— 顺序即导航顺序
NAV_ITEMS = [
    ("车牌识别", "scan"),
    ("入场登记", "entry"),
    ("出场结算", "exit"),
    ("停车记录", "record"),
    ("会员管理", "member"),
    ("黑名单",   "blacklist"),
    ("数据统计", "stats"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1260, 800)
        self.setMinimumSize(1080, 700)

        # ---- 页面栈 ----
        self.stack = QStackedWidget()
        self.widget_map = {
            "车牌识别":  RecognizeWidget(self),
            "入场登记":  EntryWidget(self),
            "出场结算":  ExitWidget(self),
            "停车记录":  RecordWidget(self),
            "会员管理":  MemberWidget(self),
            "黑名单":     BlacklistWidget(self),
            "数据统计":  StatsWidget(self),
        }
        for name, _icon_name in NAV_ITEMS:
            self.stack.addWidget(self.widget_map[name])

        # ---- 中央布局 ----
        central = QWidget()
        central.setObjectName("pageRoot")
        central.setAttribute(QtQt.WA_StyledBackground, True)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_topbar())
        right.addWidget(self.stack, 1)
        h.addLayout(right, 1)
        self.setCentralWidget(central)

        # ---- 状态栏 ----
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("欢迎使用车牌识别与停车场管理系统")
        self.statusBar().addPermanentWidget(self._build_status_right())

        # 默认进入车牌识别
        self.nav.setCurrentRow(0)
        self.apply_role_permissions()

    # ------------------------------------------------------------------
    def closeEvent(self, e):
        """
        关闭主窗前释放子页面占用的资源。

        车牌识别页持有一个摄像头采集线程和一个线程池，不主动停掉的话，
        退出时会报 "QThread: Destroyed while thread is still running"，
        而且摄像头句柄要等进程结束才释放，下次启动可能打不开设备。
        """
        for w in self.widget_map.values():
            shutdown = getattr(w, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    pass
        super().closeEvent(e)

    # ------------------------------------------------------------------
    # 左侧导航
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setAttribute(QtQt.WA_StyledBackground, True)
        side.setFixedWidth(224)

        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_brand())
        lay.addSpacing(6)

        section = QLabel("功能导航")
        section.setObjectName("navSection")
        lay.addWidget(section)
        lay.addSpacing(4)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFocusPolicy(QtQt.NoFocus)
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setVerticalScrollBarPolicy(QtQt.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(QtQt.ScrollBarAlwaysOff)

        for name, icon_name in NAV_ITEMS:
            item = QListWidgetItem(
                _icon(icon_name, 18, Color.sb_text, active="#FFFFFF"), name
            )
            item.setData(QtQt.UserRole, name)
            self.nav.addItem(item)

        self.nav.currentRowChanged.connect(self.on_nav_changed)
        lay.addWidget(self.nav, 1)

        lay.addSpacing(8)
        lay.addWidget(self._build_user_card())
        lay.addSpacing(10)

        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.setObjectName("logoutBtn")
        self.logout_btn.setCursor(QtQt.PointingHandCursor)
        self.logout_btn.setMinimumHeight(34)
        self.logout_btn.setIcon(_icon("exit", 15, "#FCA5A5"))
        self.logout_btn.setIconSize(QSize(15, 15))
        self.logout_btn.clicked.connect(self.on_logout)

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(12, 0, 12, 14)
        wl.addWidget(self.logout_btn)
        lay.addWidget(wrap)

        return side

    def _build_brand(self) -> QWidget:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(18, 20, 18, 18)
        h.setSpacing(11)

        mark = QLabel()
        mark.setObjectName("brandMark")
        mark.setFixedSize(38, 38)
        mark.setAlignment(QtQt.AlignCenter)
        mark.setPixmap(_pixmap("plate", 22, "#FFFFFF", width=2.0))
        h.addWidget(mark)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)

        name = QLabel("车牌识别系统")
        name.setObjectName("brandName")
        col.addWidget(name)

        sub = QLabel("PARKING  MANAGEMENT")
        sub.setObjectName("brandSub")
        col.addWidget(sub)

        h.addLayout(col)
        h.addStretch()
        return box

    def _build_user_card(self) -> QWidget:
        user = get_current_user()
        name = user.username if user else "未登录"
        role = user.role if user else "—"
        role_cn = "管理员" if role == ROLE_ADMIN else "操作员"

        card = QFrame()
        card.setObjectName("userCard")

        h = QHBoxLayout(card)
        h.setContentsMargins(11, 10, 11, 10)
        h.setSpacing(10)

        avatar = QLabel(name[:1].upper() if name else "?")
        avatar.setObjectName("avatar")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(QtQt.AlignCenter)
        h.addWidget(avatar)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        user_label = QLabel(name)
        user_label.setObjectName("userName")
        col.addWidget(user_label)

        badge = QLabel(role_cn)
        badge.setObjectName("roleBadge")
        badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        col.addWidget(badge)

        h.addLayout(col, 1)

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(12, 0, 12, 0)
        wl.addWidget(card)
        return wrap

    # ------------------------------------------------------------------
    # 顶部信息条
    # ------------------------------------------------------------------
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setAttribute(QtQt.WA_StyledBackground, True)
        bar.setFixedHeight(52)

        h = QHBoxLayout(bar)
        h.setContentsMargins(26, 0, 26, 0)
        h.setSpacing(8)

        root = QLabel("管理后台")
        root.setObjectName("crumbRoot")
        h.addWidget(root)

        sep = QLabel("/")
        sep.setObjectName("crumbSep")
        h.addWidget(sep)

        self.crumb_now = QLabel(NAV_ITEMS[0][0])
        self.crumb_now.setObjectName("crumbNow")
        h.addWidget(self.crumb_now)

        h.addStretch()

        dot = QLabel("●")
        dot.setObjectName("liveDot")
        h.addWidget(dot)

        live = QLabel("系统运行中")
        live.setObjectName("liveText")
        h.addWidget(live)

        h.addSpacing(14)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("clockLabel")
        h.addWidget(self.clock_label)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        return bar

    def _tick_clock(self):
        self.clock_label.setText(
            QDateTime.currentDateTime().toString("yyyy-MM-dd  HH:mm:ss")
        )

    def _build_status_right(self) -> QWidget:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 4, 0)
        h.setSpacing(14)

        for text in (f"版本 v1.0", "SQLite · 本地存储"):
            lb = QLabel(text)
            lb.setStyleSheet(f"color:{Color.faint}; font-size:11px;")
            h.addWidget(lb)
        return box

    # ------------------------------------------------------------------
    def on_nav_changed(self, idx: int):
        if idx < 0:
            return
        self.stack.setCurrentIndex(idx)
        if 0 <= idx < len(NAV_ITEMS):
            self.crumb_now.setText(NAV_ITEMS[idx][0])

    # ------------------------------------------------------------------
    def apply_role_permissions(self):
        """操作员不能：停车记录增删改、会员管理、黑名单"""
        user = get_current_user()
        if user is None:
            return
        if user.role != ROLE_ADMIN:
            for name in ("停车记录", "会员管理", "黑名单"):
                item = self._item_of(name)
                if item is None:
                    continue
                flags = item.flags()
                try:
                    flags &= ~QtQt.ItemFlag.ItemIsEnabled
                except AttributeError:
                    # 兼容旧版 PyQt5
                    flags &= ~QtQt.ItemIsEnabled
                item.setFlags(flags)
                item.setToolTip("仅管理员可访问")

    def _item_of(self, name: str):
        for i in range(self.nav.count()):
            if self.nav.item(i).text() == name:
                return self.nav.item(i)
        return None

    def _row_of(self, name: str) -> int:
        for i in range(self.nav.count()):
            if self.nav.item(i).text() == name:
                return i
        return -1

    # ------------------------------------------------------------------
    def on_logout(self):
        ans = QMessageBox.question(self, "确认退出", "确定要退出登录？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        get_auth().logout()
        # 重新打开登录窗口
        from ui.login_window import LoginWindow
        self.login = LoginWindow()
        self.login.show()
        self.close()
