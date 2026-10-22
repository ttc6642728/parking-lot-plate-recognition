# -*- coding: utf-8 -*-
"""
程序入口：
    1. 初始化日志
    2. 初始化数据库（首次启动自动建库 + 创建默认账号）
    3. 启动 PyQt5 应用 → 打开登录窗口

运行：
    python main.py
"""

import sys
import traceback

# 修复 Windows 控制台中文乱码
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ---------------------------------------------------------------------------
# ⚠ 必须在导入 PyQt5 之前先加载 onnxruntime
#
# 实测（Windows + Python 3.12 + onnxruntime 1.27）：
#   · 先 import onnxruntime，再 import PyQt5  → 正常
#   · 先 import PyQt5，再 import onnxruntime  → 报
#     "DLL load failed while importing onnxruntime_pybind11_state:
#      动态链接库(DLL)初始化例程失败"
#   用 os.add_dll_directory 指定 onnxruntime/capi 也无效 ——
#   不是找不到 DLL，而是两个库的 CRT / 全局初始化冲突。
#
# 顺序一旦反了，HyperLPR3 会静默降级到内置管线，识别率明显下降且不易察觉，
# 所以这里显式前置加载，宁可在启动时多花约 1 秒。
# ---------------------------------------------------------------------------
try:
    import onnxruntime  # noqa: F401
except Exception as _e:      # 未安装或环境不支持时不影响主流程
    print(f"[提示] onnxruntime 预加载失败（将只使用内置识别管线）：{_e}")

from PyQt5.QtCore     import Qt
from PyQt5.QtWidgets  import QApplication, QMessageBox

from config import APP_TITLE, ORG_NAME
from ui.theme import QSS
from utils.logger import get_logger
from db.database import init_database
from ui.login_window import LoginWindow


def _excepthook(exc_type, exc_value, exc_tb):
    """全局异常钩子，避免崩溃静默。"""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(msg)
    try:
        QMessageBox.critical(None, "程序异常", msg)
    except Exception:
        pass


def main() -> int:
    # 0) 全局异常钩子
    sys.excepthook = _excepthook

    # 1) 初始化日志
    logger = get_logger()
    logger.info("=" * 60)
    logger.info("系统启动：车牌识别与停车场管理系统")

    # 2) 初始化数据库（首次启动会建表 + 创建默认账号）
    try:
        init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败：{e}")
        QMessageBox.critical(None, "启动失败", f"数据库初始化失败：\n{e}")
        return 1

    # 3) 启动 Qt 应用
    # 高 DPI 必须在 QApplication 实例化之前设置，否则 Windows 125%/150% 缩放下
    # 整个界面会被系统位图拉伸，中文发虚、圆角出现毛边。
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName(ORG_NAME)
    app.setStyleSheet(QSS)

    login = LoginWindow()
    login.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())