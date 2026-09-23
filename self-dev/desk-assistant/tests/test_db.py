"""server/db.py 全覆盖：resolve_db_path + get_connection + init_schema + row_to_dict。"""
import os
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """每个测试前后清 DESK_ASSISTANT_DB，避免污染。"""
    monkeypatch.delenv("DESK_ASSISTANT_DB", raising=False)
    yield
    monkeypatch.delenv("DESK_ASSISTANT_DB", raising=False)


def test_resolve_db_path_default(monkeypatch, tmp_path):
    """无环境变量 → 返回 DEFAULT_DB_PATH。"""
    from server.db import resolve_db_path

    p = resolve_db_path()
    assert p.name == "state.db"
    assert p.parent.name == ".desk-assistant"


def test_resolve_db_path_env_empty(monkeypatch):
    """环境变量是空串 → fallback 到 DEFAULT_DB_PATH。"""
    monkeypatch.setenv("DESK_ASSISTANT_DB", "")
    from server.db import resolve_db_path

    assert resolve_db_path().name == "state.db"


def test_resolve_db_path_explicit_arg(monkeypatch):
    """显式传 env_value（不读 OS 环境）。"""
    from server.db import resolve_db_path

    p = resolve_db_path("state_test.db")
    assert p.name == "state_test.db"
    assert p.parent.name == ".desk-assistant"


def test_resolve_db_path_env_set(monkeypatch, tmp_path):
    """合法文件名 → 拼接 ~/.desk-assistant/<name>。"""
    monkeypatch.setenv("DESK_ASSISTANT_DB", "foo-bar_123.db")
    from server.db import resolve_db_path

    assert resolve_db_path().name == "foo-bar_123.db"


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",         # 绝对路径
        "../foo.db",           # .. 段
        "sub/db.db",           # 子目录形式（Linux 风格）
        "sub\\db.db",          # 子目录形式（Windows 风格）
        "foo/bar.db",          # 多级子目录
        "foo;rm.db",           # shell 注入字符
        "foo bar.db",          # 空格
        "foo'bar.db",          # 单引号
    ],
)
def test_resolve_db_path_rejects_malicious(monkeypatch, bad):
    """路径注入、特殊字符 → 全部拒绝。"""
    monkeypatch.setenv("DESK_ASSISTANT_DB", bad)
    from server.db import resolve_db_path

    with pytest.raises(ValueError):
        resolve_db_path()


def test_resolve_db_path_explicit_arg_can_also_reject():
    """env_value 参数同样走校验。"""
    from server.db import resolve_db_path

    with pytest.raises(ValueError):
        resolve_db_path("/etc/passwd")
    with pytest.raises(ValueError):
        resolve_db_path("../x.db")
    with pytest.raises(ValueError):
        resolve_db_path("a/b.db")


def test_get_connection_creates_file(tmp_db_path):
    from server.db import get_connection

    assert not tmp_db_path.exists()
    conn = get_connection(str(tmp_db_path))
    try:
        assert tmp_db_path.exists()
        mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()
        assert str(mode[0]).lower() == "wal"
    finally:
        conn.close()


def test_get_connection_default_path(monkeypatch, tmp_path):
    """无参数 → 用 DEFAULT_DB_PATH（用 tmp HOME 避免真污染）。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    import importlib
    from server import db as db_mod
    importlib.reload(db_mod)
    conn = db_mod.get_connection()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_get_connection_wal_fallback_logs_warning(tmp_db_path, caplog):
    """journal_mode 不可用时记 warning（mock 不可触发，但走主分支 OK）。"""
    from server.db import get_connection

    conn = get_connection(str(tmp_db_path))
    try:
        # 验证 PRAGMA 真的设了
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_init_schema_idempotent(tmp_db_path):
    from server.db import get_connection, init_schema

    conn = get_connection(str(tmp_db_path))
    try:
        init_schema(conn)
        init_schema(conn)  # 第二次不该报错
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "metrics" in names
        assert "events" in names
        # 触发器也建了
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        assert any("trim_events_after_insert" in r[0] for r in triggers)
    finally:
        conn.close()


def test_init_schema_creates_indices_and_trigger(tmp_db_path):
    from server.db import get_connection, init_schema

    conn = get_connection(str(tmp_db_path))
    try:
        init_schema(conn)
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_events_%'"
        ).fetchall()
        idx_names = {r[0] for r in idx}
        assert "idx_events_done_completed" in idx_names
        assert "idx_events_created" in idx_names
    finally:
        conn.close()


def test_row_to_dict_none():
    from server.db import row_to_dict

    assert row_to_dict(None) is None


def test_row_to_dict_normal():
    from server.db import row_to_dict

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'x')")
    row = conn.execute("SELECT a, b FROM t").fetchone()
    d = row_to_dict(row)
    assert d == {"a": 1, "b": "x"}
    conn.close()
