"""panel 纯逻辑部分覆盖：_parse_iso / _make_box / SSEClient._dispatch。

PyQt 渲染 + 真实 HTTP 在 offscreen 模式下部分可测，复杂交互留给手动 E2E。
"""
import json

import pytest
from PyQt5 import QtCore

from panel.events_card import EventsCard, _parse_iso
from panel.metrics_card import MetricsCard
from panel.sse_client import SSEClient


# ---- _parse_iso ----


@pytest.mark.parametrize(
    "raw,year,month,day",
    [
        ("2026-06-04T10:30:00", 2026, 6, 4),
        ("2026-06-04T10:30:00.123456", 2026, 6, 4),
        ("2026-06-04T10:30", 2026, 6, 4),
        ("2026-06-04 10:30:00", 2026, 6, 4),
        ("2026-06-04 10:30", 2026, 6, 4),
        ("2026-06-04T10:30:00+08:00", 2026, 6, 4),
        ("2026-06-04T10:30:00Z", 2026, 6, 4),
    ],
)
def test_parse_iso_various_formats(raw, year, month, day):
    dt = _parse_iso(raw)
    assert dt is not None
    assert dt.year == year
    assert dt.month == month
    assert dt.day == day


@pytest.mark.parametrize("empty", ["", None, "garbage", "  ", "1234"])
def test_parse_iso_invalid_returns_none(empty):
    assert _parse_iso(empty) is None


# ---- metrics_card._make_box ----


def test_metrics_card_update_empty(qapp):
    card = MetricsCard()
    card.update_indicators([])


def test_metrics_card_update_with_data(qapp):
    card = MetricsCard()
    card.update_indicators(
        [
            {"id": "cpu", "label": "CPU", "value": 50, "unit": "%"},
            {"id": "mem", "label": "内存", "value": 85.5, "unit": "%"},
            {"id": "high", "label": "高", "value": 95, "unit": "%"},
        ]
    )
    # 应该有 3 个 box + 1 个 stretch = 4 个 item
    assert card._row.count() == 4


def test_metrics_card_value_invalid_falls_back_to_zero(qapp):
    card = MetricsCard()
    # unit 仍是合法 %；value 解析失败 → fallback val=0，"0%"
    box = card._make_box({"id": "x", "label": "X", "value": "not-a-number", "unit": "%"})
    from PyQt5.QtWidgets import QLabel
    labels = box.findChildren(QLabel)
    assert labels[0].text() == "0%"


def test_metrics_card_value_integer_vs_float(qapp):
    card = MetricsCard()
    box_int = card._make_box({"id": "i", "label": "I", "value": 50, "unit": "%"})
    box_float = card._make_box({"id": "f", "label": "F", "value": 50.5, "unit": "%"})
    # 找两个 QLabel 中的 value（第一个 child）
    from PyQt5.QtWidgets import QLabel
    labels_int = box_int.findChildren(QLabel)
    labels_float = box_float.findChildren(QLabel)
    assert labels_int[0].text() == "50%"
    assert labels_float[0].text() == "50.5%"


def test_metrics_card_color_thresholds(qapp):
    """< 70 绿 / 70-90 黄 / >= 90 红。"""
    card = MetricsCard()
    from PyQt5.QtWidgets import QLabel

    for val, expected in [(50, "#6bce82"), (85, "#f0c060"), (95, "#e25c5c")]:
        box = card._make_box({"id": "x", "label": "X", "value": val, "unit": "%"})
        lbl = box.findChildren(QLabel)[0]
        assert expected in lbl.styleSheet()


def test_metrics_card_missing_label_uses_id(qapp):
    card = MetricsCard()
    box = card._make_box({"id": "fallback", "value": 1})
    from PyQt5.QtWidgets import QLabel
    labels = box.findChildren(QLabel)
    assert labels[1].text() == "fallback"  # label fall back to id


# ---- events_card ----


def test_events_card_update_empty(qapp):
    card = EventsCard()
    card.update_events([])


def test_events_card_update_with_events(qapp):
    card = EventsCard()
    card.update_events(
        [
            {
                "id": 1,
                "name": "A",
                "done": 0,
                "created_at": "2026-06-04T10:00:00",
            },
            {
                "id": 2,
                "name": "B done",
                "done": 1,
                "created_at": "2026-06-04T11:00:00",
                "completed_at": "2026-06-04T12:00:00",
            },
        ]
    )
    assert card._inner_layout.count() == 2


def test_events_card_truncate_to_display_limit(qapp):
    card = EventsCard()
    events = [{"id": i, "name": f"e{i}", "done": 0, "created_at": "2026-06-04T10:00:00"} for i in range(150)]
    card.update_events(events)
    # 截到 DEFAULT_DISPLAY_LIMIT (100)
    assert card._inner_layout.count() == 100


def test_events_card_row_uses_name_then_external_id_then_id(qapp):
    """回退链：name → external_id → id。"""
    card = EventsCard()
    box = card._make_row(
        {"id": 99, "external_id": "ext-z", "name": "", "done": 0, "created_at": "2026-06-04T10:00:00"}
    )
    from PyQt5.QtWidgets import QLabel
    labels = box.findChildren(QLabel)
    # 第一个 label 是时间，第二个是文本
    text_lbl = [l for l in labels if l.text() != "" and ":" not in l.text()][0]
    # name 是空，fallback 到 external_id "ext-z"
    assert text_lbl.text() == "ext-z"


def test_events_card_done_styling(qapp):
    card = EventsCard()
    done_row = card._make_row(
        {"id": 1, "name": "A", "done": 1, "created_at": "2026-06-04T10:00:00"}
    )
    undone_row = card._make_row(
        {"id": 2, "name": "B", "done": 0, "created_at": "2026-06-04T10:00:00"}
    )
    from PyQt5.QtWidgets import QLabel
    done_text = [l for l in done_row.findChildren(QLabel) if l.text() == "A"][0]
    undone_text = [l for l in undone_row.findChildren(QLabel) if l.text() == "B"][0]
    # v3.2 样式大改：done 状态用 objectName 区分（不走 inline styleSheet）
    assert done_text.objectName() == "EventName"
    assert done_text.property("done") == "true"
    assert undone_text.property("done") == "false"


def test_events_card_toggle_signal(qapp):
    card = EventsCard()
    captured = []
    card.toggle_requested.connect(lambda eid, checked: captured.append((eid, checked)))
    row = card._make_row(
        {"id": 42, "name": "A", "done": 0, "created_at": "2026-06-04T10:00:00"}
    )
    from PyQt5.QtWidgets import QCheckBox
    cb = row.findChild(QCheckBox)
    cb.setChecked(True)
    # clicked 信号会自动发出吗？需要 trigger
    cb.clicked.emit(True)
    assert captured == [(42, True)]


# ---- SSEClient._dispatch ----


def _make_sse_client_for_dispatch():
    """绕过 QNetworkAccessManager 直接构造一个用于 _dispatch 的实例。"""
    c = SSEClient.__new__(SSEClient)
    c.buffer = bytearray()
    c._frame_count = 0
    c._emitted = []

    class FakeSignal:
        def __init__(self):
            self.calls = []

        def emit(self, name, data):
            self.calls.append((name, data))

    sig = FakeSignal()
    c.sse_event = sig
    return c, sig


def test_sse_dispatch_simple_event(qapp):
    c, sig = _make_sse_client_for_dispatch()
    frame = b"event: metrics.changed\ndata: {\"id\":\"cpu\"}\n"
    c._dispatch(frame)
    assert sig.calls == [("metrics.changed", {"id": "cpu"})]


def test_sse_dispatch_default_event_name(qapp):
    c, sig = _make_sse_client_for_dispatch()
    frame = b"data: {\"x\":1}\n"
    c._dispatch(frame)
    assert sig.calls == [("message", {"x": 1})]


def test_sse_dispatch_multiline_data(qapp):
    c, sig = _make_sse_client_for_dispatch()
    # 多行 data: 合并为一个 JSON
    frame = b"event: e\ndata: {\"a\":\ndata: 1}\n"
    c._dispatch(frame)
    # 多行 data 应该被连接（用 \n）然后 json.loads
    assert sig.calls == [("e", {"a": 1})]


def test_sse_dispatch_comment_only_skipped(qapp):
    """只有注释（: 开头）行没有 data → 不 emit。"""
    c, sig = _make_sse_client_for_dispatch()
    frame = b": keepalive\n"
    c._dispatch(frame)
    assert sig.calls == []


def test_sse_dispatch_bad_json_logs_warning(qapp, caplog):
    c, sig = _make_sse_client_for_dispatch()
    frame = b"data: {bad json}\n"
    import logging
    with caplog.at_level(logging.WARNING, logger="panel"):
        c._dispatch(frame)
    assert sig.calls == []
    assert any("bad SSE frame" in rec.message for rec in caplog.records)


def test_sse_dispatch_non_dict_logs_warning(qapp, caplog):
    c, sig = _make_sse_client_for_dispatch()
    frame = b"data: [1,2,3]\n"
    import logging
    with caplog.at_level(logging.WARNING, logger="panel"):
        c._dispatch(frame)
    assert sig.calls == []
    assert any("not dict" in rec.message for rec in caplog.records)


def test_sse_dispatch_data_with_leading_space(qapp):
    """data: 后空格 / 无空格都支持。"""
    c, sig = _make_sse_client_for_dispatch()
    frame1 = b"data: {\"k\":1}\n"      # 无前导空格
    frame2 = b"data:  {\"k\":2}\n"     # 双空格
    c._dispatch(frame1)
    c._dispatch(frame2)
    assert sig.calls == [("message", {"k": 1}), ("message", {"k": 2})]


# ---- config.py: load_openclaw_token ----


def test_load_openclaw_token_missing_path(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("panel.config.OPENCLAW_CONFIG_PATH", tmp_path / "nope.json")
    from panel.config import load_openclaw_token

    assert load_openclaw_token() is None


def test_load_openclaw_token_valid(qapp, monkeypatch, tmp_path):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text('{"gateway":{"auth":{"token":"abc123"}}}', encoding="utf-8")
    monkeypatch.setattr("panel.config.OPENCLAW_CONFIG_PATH", cfg)
    from panel.config import load_openclaw_token

    assert load_openclaw_token() == "abc123"


def test_load_openclaw_token_missing_token_field(qapp, monkeypatch, tmp_path):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text('{"gateway":{"auth":{}}}', encoding="utf-8")
    monkeypatch.setattr("panel.config.OPENCLAW_CONFIG_PATH", cfg)
    from panel.config import load_openclaw_token

    assert load_openclaw_token() is None


def test_load_openclaw_token_invalid_json(qapp, monkeypatch, tmp_path, caplog):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr("panel.config.OPENCLAW_CONFIG_PATH", cfg)
    from panel.config import load_openclaw_token
    import logging

    with caplog.at_level(logging.WARNING, logger="panel"):
        result = load_openclaw_token()
    assert result is None
    assert any("openclaw config" in rec.message for rec in caplog.records)


def test_load_openclaw_token_non_dict(qapp, monkeypatch, tmp_path, caplog):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text('"a string, not an object"', encoding="utf-8")
    monkeypatch.setattr("panel.config.OPENCLAW_CONFIG_PATH", cfg)
    from panel.config import load_openclaw_token
    import logging

    with caplog.at_level(logging.WARNING, logger="panel"):
        result = load_openclaw_token()
    assert result is None
    assert any("expected object" in rec.message for rec in caplog.records)
