"""Flask app 端到端测试：所有 REST + SSE 端点。

注：app.py 模块顶层就 get_connection + init_schema + 创建 stores，
直接 import 会拿到生产 db 的 conn + stores。fixture 把它们替换为 tmp_db 上的实例。
"""
import pytest


@pytest.fixture
def app_module(tmp_db_path, monkeypatch):
    """让 server.app 的 conn + hub + stores 全部指向 tmp_db_path。

    必须在 import server.app 之后 monkeypatch（否则模块层会拉起生产 conn）。
    monkeypatch 自动 teardown：测试结束恢复原始 conn / hub / stores。
    """
    import server.app as app_mod
    from server.db import get_connection, init_schema
    from server.events_store import EventsStore
    from server.metrics_store import MetricsStore
    from server.sse_hub import SseHub

    # 关掉 import 时建的生产 db conn（测试进程内有效，不影响 launcher 起的 server）
    try:
        app_mod.conn.close()
    except Exception:
        pass

    new_conn = get_connection(str(tmp_db_path))
    init_schema(new_conn)
    new_hub = SseHub()
    new_metrics = MetricsStore(
        new_conn,
        on_change=lambda mid: new_hub.push("metrics.changed", {"id": mid}),
    )
    new_events = EventsStore(
        new_conn,
        on_change=lambda reason, eid: new_hub.push(
            "events.changed", {"reason": reason, "id": eid}
        ),
    )
    monkeypatch.setattr(app_mod, "conn", new_conn)
    monkeypatch.setattr(app_mod, "hub", new_hub)
    monkeypatch.setattr(app_mod, "metrics", new_metrics)
    monkeypatch.setattr(app_mod, "events", new_events)
    app_mod.app.config["TESTING"] = True
    yield app_mod
    new_conn.close()


# ---- /api/metrics ----


def test_list_metrics_empty(app_module):
    client = app_module.app.test_client()
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert r.get_json() == []


def test_put_and_list_metrics(app_module):
    client = app_module.app.test_client()
    r = client.put(
        "/api/metrics/cpu",
        json={"label": "CPU", "value": 77.5, "unit": "%"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == "cpu"
    assert body["value"] == 77.5
    assert body["unit"] == "%"

    r = client.get("/api/metrics")
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 1
    assert rows[0]["id"] == "cpu"


def test_put_metric_missing_label(app_module):
    client = app_module.app.test_client()
    r = client.put("/api/metrics/cpu", json={"value": 50})
    assert r.status_code == 400
    assert "missing" in r.get_json()["error"]


def test_put_metric_missing_value(app_module):
    client = app_module.app.test_client()
    r = client.put("/api/metrics/cpu", json={"label": "CPU"})
    assert r.status_code == 400


def test_put_metric_invalid_value_type(app_module):
    client = app_module.app.test_client()
    r = client.put(
        "/api/metrics/cpu",
        json={"label": "CPU", "value": "not-a-number"},
    )
    assert r.status_code == 400


def test_put_metric_no_json_body(app_module):
    client = app_module.app.test_client()
    r = client.put("/api/metrics/cpu", data="not json")
    assert r.status_code == 400
    assert "JSON" in r.get_json()["error"]


def test_delete_metric_existing(app_module):
    client = app_module.app.test_client()
    client.put("/api/metrics/cpu", json={"label": "CPU", "value": 1})
    r = client.delete("/api/metrics/cpu")
    assert r.status_code == 204
    r = client.get("/api/metrics")
    assert r.get_json() == []


def test_delete_metric_missing(app_module):
    client = app_module.app.test_client()
    r = client.delete("/api/metrics/nope")
    assert r.status_code == 404


# ---- /api/events ----


def test_list_events_empty(app_module):
    client = app_module.app.test_client()
    r = client.get("/api/events")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_events_with_all_param(app_module):
    client = app_module.app.test_client()
    client.post("/api/events", json={"name": "A"})
    r = client.get("/api/events?all=true&limit=10&offset=0")
    assert r.status_code == 200
    assert len(r.get_json()) == 1


def test_list_events_limit_negative(app_module):
    client = app_module.app.test_client()
    r = client.get("/api/events?limit=-1")
    assert r.status_code == 400


def test_list_events_limit_non_int(app_module):
    client = app_module.app.test_client()
    r = client.get("/api/events?limit=abc")
    assert r.status_code == 400


def test_list_events_offset_negative(app_module):
    client = app_module.app.test_client()
    r = client.get("/api/events?offset=-1")
    assert r.status_code == 400


def test_create_event(app_module):
    client = app_module.app.test_client()
    r = client.post(
        "/api/events",
        json={
            "name": "回邮件",
            "type": "todo",
            "description": "周报相关",
            "source": "test",
            "external_id": "ext-1",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["name"] == "回邮件"
    assert body["external_id"] == "ext-1"


def test_create_event_missing_name(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", json={"type": "todo"})
    assert r.status_code == 400
    assert "name" in r.get_json()["error"]


def test_create_event_empty_name(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", json={"name": ""})
    assert r.status_code == 400


def test_create_event_no_body(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", data="not json")
    assert r.status_code == 400


def test_create_event_idempotent(app_module):
    client = app_module.app.test_client()
    r1 = client.post("/api/events", json={"name": "A", "external_id": "dup"})
    r2 = client.post("/api/events", json={"name": "B", "external_id": "dup"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.get_json()["id"] == r2.get_json()["id"]


def test_create_event_invalid_type(app_module):
    client = app_module.app.test_client()
    r = client.post(
        "/api/events",
        json={"name": "A", "expire_seconds": "abc"},
    )
    assert r.status_code == 400


def test_patch_event(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", json={"name": "A"})
    eid = r.get_json()["id"]
    r = client.patch(f"/api/events/{eid}", json={"done": True})
    assert r.status_code == 200
    body = r.get_json()
    assert body["done"] == 1
    assert body["completed_at"] is not None


def test_patch_event_invalid_done_type(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", json={"name": "A"})
    eid = r.get_json()["id"]
    r = client.patch(f"/api/events/{eid}", json={"done": "yes"})
    assert r.status_code == 400


def test_patch_event_no_body(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", json={"name": "A"})
    eid = r.get_json()["id"]
    r = client.patch(f"/api/events/{eid}", data="not json")
    assert r.status_code == 400


def test_patch_event_missing(app_module):
    client = app_module.app.test_client()
    r = client.patch("/api/events/99999", json={"done": True})
    assert r.status_code == 404


def test_delete_event_existing(app_module):
    client = app_module.app.test_client()
    r = client.post("/api/events", json={"name": "A"})
    eid = r.get_json()["id"]
    r = client.delete(f"/api/events/{eid}")
    assert r.status_code == 204
    r = client.get("/api/events")
    assert r.get_json() == []


def test_delete_event_missing(app_module):
    client = app_module.app.test_client()
    r = client.delete("/api/events/99999")
    assert r.status_code == 404


# ---- /events (SSE) ----


def test_sse_hello_frame(app_module):
    client = app_module.app.test_client()
    r = client.get("/events", buffered=False)
    # 流式：读前几个字节确认 hello 帧
    chunks = []
    for chunk in r.response:
        chunks.append(chunk.decode("utf-8", errors="replace"))
        if len(chunks) > 1:
            break
    text = "".join(chunks)
    assert "event: hello" in text
    assert '"protocol": 1' in text


def test_sse_pushes_on_event_insert(app_module):
    """POST event → SSE 收到 events.changed。"""
    import queue
    import threading

    # 在后台线程跑 SSE 流，把 chunks 存进 queue
    client = app_module.app.test_client()
    received = queue.Queue()

    def consume():
        r = client.get("/events", buffered=False)
        for chunk in r.response:
            received.put(chunk.decode("utf-8", errors="replace"))
            if received.qsize() > 3:
                break

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    # 等连接建立
    import time
    time.sleep(0.3)
    # POST 一个 event
    client.post("/api/events", json={"name": "SSE test"})
    # 等推送
    time.sleep(0.5)
    # 看队列里有没有 events.changed
    found = False
    while not received.empty():
        text = received.get_nowait()
        if "events.changed" in text:
            found = True
            break
    assert found, "SSE 没收到 events.changed"


# ---- bad-request 覆盖 ----


def test_metrics_bad_request_helper(app_module):
    """直接验证 _bad_request helper 返回正确结构。"""
    with app_module.app.test_request_context():
        body, status = app_module._bad_request("oops")
    assert status == 400
    assert body.get_json() == {"error": "oops"}


def test_metrics_not_found_helper(app_module):
    with app_module.app.test_request_context():
        body, status = app_module._not_found("missing")
    assert status == 404
    assert body.get_json() == {"error": "missing"}


def test_sse_pack_helper(app_module):
    packed = app_module._sse_pack("test.evt", {"k": 1})
    assert packed.startswith("event: test.evt\ndata: ")
    assert packed.endswith("\n\n")
    assert '"k": 1' in packed


def test_sse_pack_helper_none_data(app_module):
    packed = app_module._sse_pack("test.evt", None)
    assert "data: \n" in packed
