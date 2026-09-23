"""server/events_store.py — events 表 CRUD + 过滤查询。

- 写入即追加，最多 1w 条（超过由触发器滚动删最老 100 条）
- 默认过滤展示：未处理 OR (已完成且未过期)
- on_change(reason, event_id) 回调（reason ∈ insert / update / delete）
"""
import logging
import threading
from datetime import datetime

from db import row_to_dict

log = logging.getLogger(__name__)

# 默认过期时长（秒）：6 小时
DEFAULT_EXPIRE_SECONDS = 21600

# 默认列表上限：server 返回最多 200 条，panel 端再截 100 条显示
DEFAULT_VISIBLE_LIMIT = 200


class EventsStore:
    def __init__(self, conn, on_change=None):
        """:param conn: 已 init_schema 的 sqlite3.Connection
        :param on_change: callable(reason: str, event_id: int) -> None
        """
        self._conn = conn
        self._lock = threading.RLock()
        self._on_change = on_change

    def list_visible(self, limit=DEFAULT_VISIBLE_LIMIT):
        """未处理 OR (已完成且未过期)，按未完成优先 + 创建时间倒序。"""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, external_id, type, name, description, content,
                       source, created_at, done, completed_at, expire_seconds
                FROM events
                WHERE done = 0
                   OR (
                        done = 1
                        AND completed_at IS NOT NULL
                        AND (strftime('%s','now') - strftime('%s', completed_at))
                            < expire_seconds
                   )
                ORDER BY done ASC, created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [row_to_dict(r) for r in rows]

    def list_all(self, limit=200, offset=0):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, external_id, type, name, description, content,
                       source, created_at, done, completed_at, expire_seconds
                FROM events
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (int(limit), int(offset)),
            ).fetchall()
        return [row_to_dict(r) for r in rows]

    def get(self, event_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT id, external_id, type, name, description, content, "
                "source, created_at, done, completed_at, expire_seconds "
                "FROM events WHERE id = ?",
                (int(event_id),),
            ).fetchone()
        return row_to_dict(row)

    def insert(self, name, type_="todo", description="", content="",
               source="", external_id=None,
               expire_seconds=DEFAULT_EXPIRE_SECONDS):
        """新增。如 external_id 已存在则返回现有事件（幂等）。

        - name 必填：作为主标题
        - type_ 默认 'todo'：事件类型枚举
        - description / content 可选

        实现注意：用 INSERT OR IGNORE + 回查 external_id，避免 TOCTOU
        竞争下两线程都通过预检后插入二者其一抛 IntegrityError。
        """
        now = datetime.now().isoformat(timespec="seconds")
        new_id = None
        with self._lock:
            if external_id:
                cur = self._conn.execute(
                    """
                    INSERT OR IGNORE INTO events
                        (external_id, type, name, description, content,
                         source, created_at, done, completed_at, expire_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                    """,
                    (external_id, type_, name, description, content,
                     source, now, int(expire_seconds)),
                )
                if cur.rowcount == 1:
                    new_id = int(cur.lastrowid)
                else:
                    # 已存在，回查得到 id（不发 on_change）
                    row = self._conn.execute(
                        "SELECT id FROM events WHERE external_id = ?",
                        (external_id,),
                    ).fetchone()
                    if row is None:
                        return None  # 极端情况：被并发删除
                    return self.get(int(row["id"]))
            else:
                cur = self._conn.execute(
                    """
                    INSERT INTO events
                        (external_id, type, name, description, content,
                         source, created_at, done, completed_at, expire_seconds)
                    VALUES (NULL, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                    """,
                    (type_, name, description, content,
                     source, now, int(expire_seconds)),
                )
                new_id = int(cur.lastrowid)
        self._notify("insert", new_id)
        return self.get(new_id)

    def patch(self, event_id, done=None):
        """局部更新。当前只支持 done 切换；done=True 自动补 completed_at=now，
        done=False 自动清掉 completed_at。返回更新后对象；id 不存在返回 None。
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM events WHERE id = ?", (int(event_id),)
            ).fetchone()
            if row is None:
                return None
            if done is None:
                return self.get(event_id)
            if done:
                now = datetime.now().isoformat(timespec="seconds")
                self._conn.execute(
                    "UPDATE events SET done = 1, completed_at = ? WHERE id = ?",
                    (now, int(event_id)),
                )
            else:
                self._conn.execute(
                    "UPDATE events SET done = 0, completed_at = NULL "
                    "WHERE id = ?",
                    (int(event_id),),
                )
        self._notify("update", int(event_id))
        return self.get(event_id)

    def delete(self, event_id):
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM events WHERE id = ?", (int(event_id),)
            )
            deleted = cur.rowcount > 0
        if deleted:
            self._notify("delete", int(event_id))
        return deleted

    def _notify(self, reason, event_id):
        if self._on_change is None:
            return
        try:
            self._on_change(reason, event_id)
        except Exception:
            log.exception("events on_change failed reason=%s id=%s",
                          reason, event_id)
