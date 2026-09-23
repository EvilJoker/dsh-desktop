"""panel/events_card.py — 事件卡片：复选框 + 时间 + 文本，可滚动。

新数据契约（server 端 SQLite events 表）：
    {
        "id": int,                  # 数据库主键，PATCH /api/events/<id>
        "external_id": str | None,
        "type": str,                # "todo" / "alert" / "reminder" / ...
        "name": str,                # 主标题（列表展示）
        "description": str,         # 副标题/提示（可选）
        "content": str,             # 详细内容（列表不展示）
        "source": str,
        "created_at": str,          # ISO8601
        "done": int,                # 0/1
        "completed_at": str | None,
        "expire_seconds": int,
    }

server 已按"未处理 OR 已完成未过期"过滤后返回，前端只显示前 100 条；
不再做客户端过期过滤。
"""
from datetime import datetime

from PyQt5 import QtCore, QtWidgets

DEFAULT_DISPLAY_LIMIT = 100  # 前端最多展示 100 条


def _parse_iso(s):
    """Python 3.6 没有 datetime.fromisoformat，多格式 strptime 兜底。"""
    if not s:
        return None
    s = str(s).strip()
    for tz_marker in ("+", "Z"):
        if tz_marker in s and s.rfind(tz_marker) > 10:
            s = s[: s.rfind(tz_marker)]
            break
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


class EventsCard(QtWidgets.QFrame):
    """接收 events 列表（server 端已过滤），渲染滚动事件列表（复选框 + 时间 + 文本）。

    用法：
        card = EventsCard()
        card.toggle_requested.connect(on_user_toggle)  # 用户勾选 → (event_id:int, checked:bool)
        card.update_events(events)  # events: list[dict]，见模块 docstring 的契约
    """

    # 用户勾选/取消勾选时发出。Panel 接到信号 → PATCH /api/events/<event_id>。
    toggle_requested = QtCore.pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EventsCard")
        # 样式走 theme.GLOBAL_QSS（#EventsCard 选择器），不再 setStyleSheet

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        title = QtWidgets.QLabel("事件 / EVENTS")
        title.setObjectName("CardTitle")
        outer.addWidget(title)

        # 滚动容器（右侧垂直滚动条）
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("EventScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self._inner = QtWidgets.QWidget()
        self._inner.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        self._inner_layout = QtWidgets.QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(4)
        # AlignTop：内容少时贴顶；不加 stretch，内容多时自然撑出滚动条
        self._inner_layout.setAlignment(QtCore.Qt.AlignTop)
        scroll.setWidget(self._inner)
        outer.addWidget(scroll, 1)
        # 不加 stretch 的话，title QLabel 默认 Preferred sizePolicy 会被 QVBoxLayout
        # 拉成全高，文字（默认 AlignVCenter）显示在 card 中间。加 stretch(1) 顶在顶部。
        outer.addStretch(1)

    def update_events(self, events):
        """events: server 返回的 list[dict]，已按业务规则过滤过。前端再截 N 条。"""
        self._clear()
        if not events:
            empty = QtWidgets.QLabel("(无事件)")
            empty.setObjectName("Empty")
            self._inner_layout.addWidget(empty)
            return
        for ev in events[:DEFAULT_DISPLAY_LIMIT]:
            self._inner_layout.addWidget(self._make_row(ev))

    def _clear(self):
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    @staticmethod
    def _fmt_short_time(iso_str):
        dt = _parse_iso(iso_str)
        if dt is None:
            return ""
        return dt.strftime("%H:%M")

    def _make_row(self, event):
        done = bool(event.get("done"))
        name = str(event.get("name") or event.get("external_id") or event.get("id") or "")
        event_id = int(event.get("id") or 0)
        ts_str = self._fmt_short_time(
            event.get("created_at") or event.get("completed_at") or ""
        )

        row = QtWidgets.QWidget()
        # 走 QSS 透明（v3.2 之前用 setStyleSheet("background: transparent;")）
        row.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        cb = QtWidgets.QCheckBox()
        cb.setChecked(done)
        cb.setCursor(QtCore.Qt.PointingHandCursor)
        # 样式走 theme.GLOBAL_QSS（QCheckBox::indicator）
        # 用 clicked 而非 stateChanged：clicked 只在用户点击时发出，
        # setChecked() 不会触发，避免 SSE 重渲染 → setChecked → 信号 → PATCH → SSE 的死循环。
        cb.clicked.connect(
            lambda checked, eid=event_id: self.toggle_requested.emit(eid, checked)
        )
        h.addWidget(cb)

        time_lbl = QtWidgets.QLabel(ts_str)
        time_lbl.setObjectName("EventTime")
        time_lbl.setFixedWidth(40)
        h.addWidget(time_lbl)

        text_lbl = QtWidgets.QLabel(name)
        text_lbl.setObjectName("EventName")
        # 用 property 区分 done 状态，QSS 用 [done="true"] 选择器
        text_lbl.setProperty("done", "true" if done else "false")
        text_lbl.setWordWrap(True)
        h.addWidget(text_lbl, 1)

        return row
