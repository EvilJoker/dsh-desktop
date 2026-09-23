"""共享 fixture：临时 db、QApplication 单例。"""
import os
import sys
import tempfile

import pytest
from PyQt5 import QtWidgets


# 必须强制 offscreen：用户 shell 经常把 QT_QPA_PLATFORM 设成 xcb（桌面环境），
# 会导致 setFocus/processEvents 走真 X server 拿不到焦点事件，
# 进而让 QApplication.focusWidget() 一直返回 None → 依赖焦点的 panel 测试失败。
# 强制覆盖 setdefault（仅影响测试 session；生产 panel 启动走 main() 不经此处）。
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    """测试 session 内的 QApplication 单例（Qt 不允许重复创建）。"""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app
    # session 级不主动 quit，避免后续测试出问题


@pytest.fixture
def tmp_db_path(tmp_path):
    """每个测试一个独立 sqlite 文件路径，测试结束自动清理。"""
    return tmp_path / "test.db"


@pytest.fixture
def tmp_db(tmp_db_path):
    """打开一个已 init_schema 的 db 连接，测试结束自动关闭。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from server.db import get_connection, init_schema

    conn = get_connection(str(tmp_db_path))
    init_schema(conn)
    yield conn
    conn.close()
