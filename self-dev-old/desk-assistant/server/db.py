"""server/db.py — SQLite 连接 + 表结构初始化。

设计约定：
- 数据库文件：~/.desk-assistant/state.db（首次启动自动建库建表）
- metrics 表：只存最新值（INSERT OR REPLACE）
- events 表：积累式，最多 1w 条（超过自动滚动删除最老 100 条）
- 详见 docs/metrics_events_数据库设计.md
"""
import logging
import os
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".desk-assistant" / "state.db"
# 测试/调试时切到独立库，避免污染生产 state.db。
# 用法：DESK_ASSISTANT_DB=state_test.db python server/app.py
DB_ENV_VAR = "DESK_ASSISTANT_DB"


def resolve_db_path(env_value=None) -> Path:
    """根据环境变量决定用哪个 db 文件。

    优先级：环境变量 > DEFAULT_DB_PATH。
    env_value 为 None 时从 OS 环境读；为 str 时直接用。
    仅允许文件名（必须在 ~/.desk-assistant/ 下），防止任意路径注入。
    """
    raw = env_value if env_value is not None else os.environ.get(DB_ENV_VAR)
    if not raw:
        return DEFAULT_DB_PATH
    # 只接受纯文件名：拒绝绝对路径、含路径分隔符（防止 subdir/db 形式）、含 ..
    if os.sep in raw or "/" in raw or "\\" in raw:
        raise ValueError("DESK_ASSISTANT_DB must be a bare filename, not a path: %r" % raw)
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("DESK_ASSISTANT_DB must be a filename, not a path: %r" % raw)
    if not all(c.isalnum() or c in "._-" for c in candidate.name):
        raise ValueError("invalid db filename: %r" % raw)
    return Path.home() / ".desk-assistant" / candidate.name

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metrics (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT NOT NULL DEFAULT '',
    type        TEXT NOT NULL DEFAULT 'progress',
    position    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id    TEXT UNIQUE,
    type           TEXT NOT NULL DEFAULT 'todo',
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    content        TEXT NOT NULL DEFAULT '',
    source         TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    done           INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0,1)),
    completed_at   TEXT,
    expire_seconds INTEGER NOT NULL DEFAULT 21600 CHECK (expire_seconds >= 0)
);

CREATE INDEX IF NOT EXISTS idx_events_done_completed
    ON events(done, completed_at);

CREATE INDEX IF NOT EXISTS idx_events_created
    ON events(created_at DESC);

-- 1w 上限滚动删除：超过 10000 条时一次删最老的 100 条（amortized 优化）
CREATE TRIGGER IF NOT EXISTS trim_events_after_insert
AFTER INSERT ON events
WHEN (SELECT COUNT(*) FROM events) > 10000
BEGIN
    DELETE FROM events WHERE id IN (
        SELECT id FROM events ORDER BY created_at ASC LIMIT 100
    );
END;
"""


def get_connection(db_path=None):
    """打开一个 SQLite 连接，自动建目录 + 行为友好的默认配置。

    - check_same_thread=False：Flask threaded=True 跨线程必需
    - timeout=30：默认锁等待延长，避免短暂繁忙立刻报错
    - row_factory=Row：查询结果可按列名访问
    - PRAGMA busy_timeout=5000：BEGIN 时遇锁等 5s
    - PRAGMA journal_mode=WAL：写性能 + 并发读写
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        isolation_level=None,
        check_same_thread=False,
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()
    if mode and str(mode[0]).lower() != "wal":
        log.warning("journal_mode fell back to %s (expected wal)", mode[0])
    return conn


def init_schema(conn):
    """幂等建表 + 索引 + 触发器。重复调用安全。"""
    conn.executescript(SCHEMA_SQL)


def row_to_dict(row):
    """把 sqlite3.Row 转成普通 dict（便于 jsonify）。"""
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}
