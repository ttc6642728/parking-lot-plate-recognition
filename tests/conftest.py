# -*- coding: utf-8 -*-
"""
pytest 公共配置。

要点：
1. 把项目根目录加入 sys.path，保证 `import core / db / ui` 可用；
2. 每个用例使用独立的临时 SQLite 文件，绝不污染 db/parking.db；
3. 在导入 PyQt5 之前先加载 onnxruntime（DLL 加载顺序要求，详见下方说明）。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# ⚠ 必须早于任何 PyQt5 导入。
#   PyQt5 先加载时，onnxruntime 会报 "DLL load failed ... 初始化例程失败"，
#   导致 HyperLPR3 静默降级，相关用例会 skip 掉。
# ---------------------------------------------------------------------------
try:
    import onnxruntime  # noqa: F401
except Exception:
    pass

import pytest  # noqa: E402


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """提供一个初始化好表结构 + 默认数据的临时数据库。"""
    import db.database as dbmod

    dbmod.close_conn()
    # 关键：在 init_database() 之前改掉模块级 DB_FILE
    monkeypatch.setattr(dbmod, "DB_FILE", tmp_path / "test.db")
    dbmod.init_database()
    try:
        yield dbmod
    finally:
        dbmod.close_conn()


@pytest.fixture(autouse=True)
def _reset_auth_state():
    """AuthManager 是单例，用例之间必须清掉登录态，避免互相影响。"""
    import auth.auth_manager as am

    if am.AuthManager._instance is not None:
        am.AuthManager._instance.current_user = None
    yield
    if am.AuthManager._instance is not None:
        am.AuthManager._instance.current_user = None
