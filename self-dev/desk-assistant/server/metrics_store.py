"""server/metrics_store.py — metrics 表 CRUD。

只存"最新值"，写入即覆盖（INSERT OR REPLACE）。读取按 (position, id) 排序。
任何变更后调用 on_change(metric_id) 回调（一般连到 SSE 广播）。
"""
import logging
import threading
from datetime import datetime

from db import row_to_dict

log = logging.getLogger(__name__)


class MetricsStore:
    def __init__(self, conn, on_change=None):
        """:param conn: 已 init_schema 的 sqlite3.Connection
        :param on_change: callable(metric_id: str) -> None，每次写入触发
        """
        self._conn = conn
        self._lock = threading.RLock()
        self._on_change = on_change

    def list_all(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, label, value, unit, type, position, updated_at "
                "FROM metrics ORDER BY position, id"
            ).fetchall()
        return [row_to_dict(r) for r in rows]

    def get(self, metric_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT id, label, value, unit, type, position, updated_at "
                "FROM metrics WHERE id = ?",
                (metric_id,),
            ).fetchone()
        return row_to_dict(row)

    def put(self, metric_id, label, value, unit="", type_="progress", position=0):
        """创建或全量覆盖。返回写入后的对象。"""
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO metrics "
                "(id, label, value, unit, type, position, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (metric_id, label, float(value), unit, type_, int(position), now),
            )
        self._notify(metric_id)
        return self.get(metric_id)

    def delete(self, metric_id):
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM metrics WHERE id = ?", (metric_id,)
            )
            deleted = cur.rowcount > 0
        if deleted:
            self._notify(metric_id)
        return deleted

    def _notify(self, metric_id):
        if self._on_change is None:
            return
        try:
            self._on_change(metric_id)
        except Exception:
            log.exception("metrics on_change failed for id=%s", metric_id)
