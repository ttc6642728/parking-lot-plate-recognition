# -*- coding: utf-8 -*-
"""
登录窗口

视觉：左侧深色品牌区 + 右侧白色登录表单（左右分栏，避免原来"三个控件
堆在空白里"的松散感）。

登录失败不再弹 QMessageBox —— 弹窗会遮住输入框，输错密码必须多关一次窗。
改成表单内的内联提示条，直接看到原因并原地重试。
"""

from __future__ import annotations

from PyQt5.QtCore    import Qt as QtQt, QSize
from PyQt5.QtGui     import QPixmap
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QSizePolicy,
)

from auth    import get_auth
from config  import APP_TITLE
from ui.icons import icon as _icon, pixmap as _pixmap
from ui.theme import Color
from utils.logger import get_logger

logger = get_logger()


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("loginRoot")
        self.setAttribute(QtQt.WA_StyledBackground, True)
        self.setWindowTitle(f"{APP_TITLE} - 登录")
        self.setFixedSize(880, 520)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_banner())
        root.addWidget(self._build_form(), 1)

        self._center_on_screen()

    # ------------------------------------------------------------------
    # 左侧品牌区
    # ------------------------------------------------------------------
    def _build_banner(self) -> QWidget:
        banner = QFrame()
        banner.setObjectName("loginBanner")
        banner.setFixedWidth(354)

        lay = QVBoxLayout(banner)
        lay.setContentsMargins(34, 36, 34, 30)
        lay.setSpacing(0)

        # 品牌标识
        mark = QLabel()
        mark.setObjectName("loginBrandMark")
        mark.setFixedSize(46, 46)
        mark.setAlignment(QtQt.AlignCenter)
        mark.setPixmap(_pixmap("plate", 26, "#FFFFFF", width=2.0))
        lay.addWidget(mark)
        lay.addSpacing(20)

        title = QLabel("车牌识别\n停车场管理系统")
        title.setObjectName("bannerTitle")
        title.setWordWrap(True)
        lay.addWidget(title)
        lay.addSpacing(10)

        desc = QLabel("基于深度学习与机器视觉的\n车牌识别 / 计费结算一体化方案")
        desc.setObjectName("bannerDesc")
        desc.setWordWrap(True)
        lay.addWidget(desc)
        lay.addSpacing(26)

        for text in ("双引擎车牌识别，支持图片与摄像头",
                     "车位实时分配，出场自动计费",
                     "出入记录、会员与营收统计"):
            lay.addWidget(self._banner_point(text))
            lay.addSpacing(11)

        lay.addStretch()

        badge = QLabel("Python · OpenCV · HyperLPR3 · PyQt5")
        badge.setObjectName("bannerBadge")
        badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        lay.addWidget(badge)
        lay.addSpacing(10)

        ver = QLabel("Version 1.0 · 课程设计")
        ver.setStyleSheet("color:#7F97B8; font-size:11px;")
        lay.addWidget(ver)

        return banner

    def _banner_point(self, text: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(9)

        dot = QLabel()
        dot.setFixedSize(16, 16)
        dot.setPixmap(_pixmap("check", 13, "#5EEAD4", width=2.4))
        h.addWidget(dot, 0, QtQt.AlignTop)

        lb = QLabel(text)
        lb.setObjectName("bannerPoint")
        lb.setWordWrap(True)
        h.addWidget(lb, 1)
        return row

    # ------------------------------------------------------------------
    # 右侧表单
    # ------------------------------------------------------------------
    def _build_form(self) -> QWidget:
        panel = QWidget()
        # ⚠ 这里不能用 setStyleSheet 设背景：父控件的内联样式会级联到所有子控件，
        # 把主按钮的渐变底和白色文字一起覆盖掉（表现为"白底白字看不见"）。
        panel.setObjectName("loginPanel")
        panel.setAttribute(QtQt.WA_StyledBackground, True)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(52, 44, 52, 30)
        lay.setSpacing(0)

        title = QLabel("欢迎登录")
        title.setObjectName("loginTitle")
        lay.addWidget(title)
        lay.addSpacing(6)

        sub = QLabel("请输入账号与密码以进入管理后台")
        sub.setObjectName("loginSub")
        lay.addWidget(sub)
        lay.addSpacing(26)

        # 账号
        lay.addWidget(self._field_caption("账号"))
        lay.addSpacing(6)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")
        self.username_edit.setText("admin")
        self.username_edit.setMinimumHeight(40)
        self.username_edit.addAction(
            _icon("user", 15, Color.muted), QLineEdit.LeadingPosition
        )
        lay.addWidget(self.username_edit)
        lay.addSpacing(14)

        # 密码
        lay.addWidget(self._field_caption("密码"))
        lay.addSpacing(6)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("请输入密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setText("admin123")
        self.password_edit.setMinimumHeight(40)
        self.password_edit.returnPressed.connect(self.on_login)
        self.password_edit.addAction(
            _icon("lock", 15, Color.muted), QLineEdit.LeadingPosition
        )

        self._pwd_visible = False
        self.eye_action = self.password_edit.addAction(
            _icon("eye_off", 15, Color.muted), QLineEdit.TrailingPosition
        )
        self.eye_action.setToolTip("显示 / 隐藏密码")
        self.eye_action.triggered.connect(self._toggle_password)
        lay.addWidget(self.password_edit)
        lay.addSpacing(10)

        # 内联错误提示（默认隐藏）
        self.error_label = QLabel()
        self.error_label.setObjectName("loginError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        lay.addWidget(self.error_label)

        lay.addSpacing(10)

        self.login_btn = QPushButton("登 录")
        self.login_btn.setObjectName("primaryBtn")
        self.login_btn.setMinimumHeight(42)
        self.login_btn.setCursor(QtQt.PointingHandCursor)
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.on_login)
        lay.addWidget(self.login_btn)
        lay.addSpacing(10)

        self.exit_btn = QPushButton("退出系统")
        self.exit_btn.setObjectName("ghostBtn")
        self.exit_btn.setMinimumHeight(36)
        self.exit_btn.setCursor(QtQt.PointingHandCursor)
        self.exit_btn.clicked.connect(self.close)
        lay.addWidget(self.exit_btn)

        lay.addStretch()

        hint = QLabel("默认账号　admin / admin123　·　operator / 123456")
        hint.setObjectName("mutedLabel")
        hint.setAlignment(QtQt.AlignCenter)
        hint.setStyleSheet(
            f"color:{Color.faint}; font-size:11px;"
            f"background:{Color.page}; border:none; border-radius:6px; padding:8px;"
        )
        lay.addWidget(hint)

        return panel

    def _field_caption(self, text: str) -> QLabel:
        lb = QLabel(text)
        lb.setStyleSheet(
            f"color:{Color.text2}; font-size:12px; font-weight:600;"
        )
        return lb

    # ------------------------------------------------------------------
    def _toggle_password(self):
        self._pwd_visible = not self._pwd_visible
        self.password_edit.setEchoMode(
            QLineEdit.Normal if self._pwd_visible else QLineEdit.Password
        )
        self.eye_action.setIcon(
            _icon("eye" if self._pwd_visible else "eye_off", 15, Color.muted)
        )

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _clear_error(self):
        self.error_label.hide()

    def _center_on_screen(self):
        from PyQt5.QtWidgets import QDesktopWidget
        sc = QDesktopWidget().screenGeometry()
        self.move((sc.width() - self.width()) // 2,
                  (sc.height() - self.height()) // 2)

    # ------------------------------------------------------------------
    def on_login(self):
        self._clear_error()
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            self._show_error("请输入账号和密码")
            return

        auth = get_auth()
        if auth.authenticate(username, password):
            logger.info(f"登录成功：{username}")
            from ui.main_window import MainWindow
            self.main_window = MainWindow()
            self.main_window.show()
            self.close()
        else:
            logger.warning(f"登录失败：{username}")
            self._show_error("账号或密码错误，请重新输入")
            self.password_edit.selectAll()
            self.password_edit.setFocus()
