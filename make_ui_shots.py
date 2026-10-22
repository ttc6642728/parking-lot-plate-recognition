# -*- coding: utf-8 -*-
"""
界面截图脚本（开发辅助，不参与业务）。

用途：改完 UI 后不用一张张点菜单，直接渲染成 png 检查布局。

    python _ui_shots.py

输出：docs/shots/*.png

两个坑（都踩过）：
  1. 不能用 QT_QPA_PLATFORM=offscreen —— 该平台下 Qt 字体库为空
     （QFontDatabase.families() == 0），截出来所有文字都不见了。
     改用 WA_DontShowOnScreen：走真实渲染管线，但窗口不显示在屏幕上。
  2. 截图要用"有数据"的库，否则表格和图表全是空的，看不出实际观感。
     这里用临时库灌样例，不碰项目里的 db/parking.db。
"""

import sys
import pathlib
import sqlite3
import tempfile
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 与 main.py 保持一致的加载顺序：先 onnxruntime 再 PyQt5
try:
    import onnxruntime  # noqa: F401
except Exception as e:
    print(f"[warn] onnxruntime 预加载失败：{e}")

from PyQt5.QtCore    import Qt
from PyQt5.QtWidgets import QApplication

from config      import APP_TITLE, ORG_NAME
from ui.theme    import QSS
from auth        import get_auth

OUT = ROOT / "docs" / "shots"
OUT.mkdir(parents=True, exist_ok=True)


def seed_temp_db() -> pathlib.Path:
    """建一个带样例数据的临时库，供截图使用。"""
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="ui_shot_"))
    db_path = tmpdir / "shot.db"

    import db.database as database
    database.DB_FILE = db_path
    database.init_database()

    now = datetime.now()

    def t(**kw):
        return (now + timedelta(**kw)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    conn.executemany(
        """INSERT INTO parking_records
           (plate_no, vehicle_type, spot_no, entry_time, exit_time,
            duration_sec, fee, member_flag, operator_id, note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [
            ("京A12345", "小型车", "A-01", t(hours=-2),  None, None, None, 1, 1, "会员车辆"),
            ("沪B88888", "小型车", "A-02", t(minutes=-40), None, None, None, 1, 1, ""),
            ("粤C3Q8L1", "小型车", "A-03", t(days=-1), t(days=-1, hours=3), 10800, 6.0, 1, 1, ""),
            ("冀T15888", "大型车", "B-01", t(days=-2), t(days=-2, hours=5), 18000, 20.0, 0, 1, ""),
            ("苏D66666", "小型车", "A-04", t(days=-3), t(days=-3, hours=2), 7200, 4.0, 0, 1, ""),
            ("浙E12321", "小型车", "A-05", t(days=-4), t(days=-4, hours=8), 28800, 16.0, 0, 1, ""),
            ("京A12345", "小型车", "A-06", t(days=-6), t(days=-6, hours=1), 3600, 2.0, 1, 1, ""),
        ],
    )
    conn.execute("UPDATE parking_lot SET used_spots = 2 WHERE id = 1")
    conn.executemany(
        """INSERT INTO members
           (plate_no, name, phone, valid_from, valid_to, discount)
           VALUES (?,?,?,date('now','localtime','-30 days'),
                   date('now','localtime','+300 days'),?)""",
        [
            ("京A12345", "张伟", "13800138001", 0.5),
            ("沪B88888", "李娜", "13900139002", 0.8),
            ("粤C3Q8L1", "王强", "13700137003", 0.9),
        ],
    )
    conn.executemany(
        "INSERT INTO blacklist (plate_no, reason) VALUES (?,?)",
        [
            ("冀T15888", "欠缴停车费"),
            ("苏D66666", "历史逃费记录"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName(ORG_NAME)
    app.setStyleSheet(QSS)

    seed_temp_db()
    ok = get_auth().authenticate("admin", "admin123")
    print("login:", ok)

    # ---- 登录页 ----
    from ui.login_window import LoginWindow
    login = LoginWindow()
    login.setAttribute(Qt.WA_DontShowOnScreen, True)
    login.show()
    app.processEvents()
    login.grab().save(str(OUT / "01-login.png"))
    print("saved 01-login.png")

    # ---- 主窗口各页 ----
    from ui.main_window import MainWindow, NAV_ITEMS
    win = MainWindow()
    win.resize(1260, 800)
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.show()
    app.processEvents()

    # 截图文件名用英文：README 会大量引用，中文名在 URL 里是百分号编码
    SLUG = {
        "车牌识别": "recognition", "入场登记": "entry", "出场结算": "exit",
        "停车记录": "records", "会员管理": "members",
        "黑名单": "blacklist", "数据统计": "stats",
    }
    for i, (name, _ic) in enumerate(NAV_ITEMS):
        win.nav.setCurrentRow(i)
        app.processEvents()
        app.processEvents()
        fname = f"{i + 2:02d}-{SLUG.get(name, 'page')}.png"
        win.grab().save(str(OUT / fname))
        print("saved", fname)

    # ---- 识别成功态：验证蓝色号牌块 / 置信度条 / 历史记录的真实观感 ----
    from types import SimpleNamespace
    win.nav.setCurrentRow(0)
    rec = win.widget_map["车牌识别"]
    rec._apply_result(
        SimpleNamespace(
            success=True, best_plate="京A12345", engine="HyperLPR3",
            confidence_of_best=0.962, elapsed_ms=134, note="",
            message="", image=None,
        ),
        "图片：sample.jpg",
    )
    app.processEvents()
    win.grab().save(str(OUT / "09-recognition-success.png"))
    print("saved 09-recognition-success.png")

    print("done ->", OUT)


if __name__ == "__main__":
    main()
