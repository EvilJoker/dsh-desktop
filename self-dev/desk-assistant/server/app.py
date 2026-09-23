"""app.py — Flask server，REST + SSE。

监听 127.0.0.1:18675。

REST：
  GET  /api/metrics              所有指标（按 position,id 排序）
  PUT  /api/metrics/<id>         创建或全量覆盖；body {label, value, unit?, type?, position?}
  DELETE /api/metrics/<id>       删除（不存在返 404）

  GET  /api/events               默认过滤：未处理 OR 已完成未过期，最多 200 条
  GET  /api/events?all=true&limit=N&offset=M   全量分页
  POST /api/events               创建；body {name, type?, description?, content?, source?,
                                              external_id?, expire_seconds?}
                                 external_id 已存在则返回现有（幂等）
  PATCH /api/events/<id>         {done?: bool}
  DELETE /api/events/<id>        删除

SSE：
  GET /events                    长连接，推瘦事件：
                                   event: metrics.changed   data: {"id":"cpu"}
                                   event: events.changed    data: {"reason":"insert","id":123}
                                 客户端收到通知后调对应 REST 拉数据。

启动：python3 server/app.py
"""
import json
import logging
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, Response, jsonify, request  # noqa: E402

from db import get_connection, init_schema, resolve_db_path  # noqa: E402
from events_store import (  # noqa: E402
    DEFAULT_EXPIRE_SECONDS,
    DEFAULT_VISIBLE_LIMIT,
    EventsStore,
)
from metrics_store import MetricsStore  # noqa: E402
from sse_hub import SseHub  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app")

HOST = "127.0.0.1"
PORT = 18675
SSE_HEARTBEAT_SECS = 15

# ---- 数据层装配 ----

conn = get_connection(resolve_db_path())
init_schema(conn)
hub = SseHub()
metrics = MetricsStore(
    conn,
    on_change=lambda mid: hub.push("metrics.changed", {"id": mid}),
)
events = EventsStore(
    conn,
    on_change=lambda reason, eid: hub.push(
        "events.changed", {"reason": reason, "id": eid}
    ),
)

app = Flask(__name__)
# 限制请求体 64KB：本应用单条消息远小于此，超出直接 413（防 OOM POST 攻击）
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024


# ---- helpers ----


def _bad_request(message):
    return jsonify({"error": message}), 400


def _not_found(message="not found"):
    return jsonify({"error": message}), 404


# ---- /api/metrics ----


@app.route("/api/metrics", methods=["GET"])
def list_metrics():
    return jsonify(metrics.list_all())


@app.route("/api/metrics/<metric_id>", methods=["PUT"])
def put_metric(metric_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _bad_request("JSON object body required")
    if "label" not in body or "value" not in body:
        return _bad_request("missing required fields: label, value")
    try:
        obj = metrics.put(
            metric_id=metric_id,
            label=str(body["label"]),
            value=float(body["value"]),
            unit=str(body.get("unit", "")),
            type_=str(body.get("type", "progress")),
            position=int(body.get("position", 0)),
        )
    except (TypeError, ValueError) as e:
        return _bad_request("invalid field type: %s" % e)
    return jsonify(obj)


@app.route("/api/metrics/<metric_id>", methods=["DELETE"])
def delete_metric(metric_id):
    if not metrics.delete(metric_id):
        return _not_found("metric not found: %s" % metric_id)
    return "", 204


# ---- /api/events ----


@app.route("/api/events", methods=["GET"])
def list_events():
    want_all = request.args.get("all", "").lower() in ("1", "true", "yes")
    try:
        limit = int(request.args.get("limit", DEFAULT_VISIBLE_LIMIT))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("limit/offset must be integers")
    if limit < 0 or offset < 0:
        return _bad_request("limit/offset must be non-negative")
    if want_all:
        return jsonify(events.list_all(limit=limit, offset=offset))
    return jsonify(events.list_visible(limit=limit))


@app.route("/api/events", methods=["POST"])
def create_event():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _bad_request("JSON object body required")
    if "name" not in body or not body["name"]:
        return _bad_request("missing required field: name")
    try:
        obj = events.insert(
            name=str(body["name"]),
            type_=str(body.get("type", "todo")),
            description=str(body.get("description", "")),
            content=str(body.get("content", "")),
            source=str(body.get("source", "")),
            external_id=body.get("external_id") or None,
            expire_seconds=int(body.get("expire_seconds", DEFAULT_EXPIRE_SECONDS)),
        )
    except (TypeError, ValueError) as e:
        return _bad_request("invalid field type: %s" % e)
    if obj is None:
        # external_id 通过 INSERT OR IGNORE 但回查不到 → 极端并发删除
        return jsonify({"error": "concurrent delete"}), 500
    return jsonify(obj), 201


@app.route("/api/events/<int:event_id>", methods=["PATCH"])
def patch_event(event_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _bad_request("JSON object body required")
    done = body.get("done") if "done" in body else None
    if done is not None and not isinstance(done, bool):
        return _bad_request("done must be boolean")
    obj = events.patch(event_id, done=done)
    if obj is None:
        return _not_found("event not found: %s" % event_id)
    return jsonify(obj)


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    if not events.delete(event_id):
        return _not_found("event not found: %s" % event_id)
    return "", 204


# ---- /events (SSE) ----


def _sse_pack(event_name, data):
    body = "" if data is None else json.dumps(data, ensure_ascii=False)
    return "event: %s\ndata: %s\n\n" % (event_name, body)


@app.route("/events")
def sse_stream():
    def stream():
        q = hub.subscribe()
        try:
            yield _sse_pack("hello", {"protocol": 1})
            while True:
                try:
                    event_name, payload = q.get(timeout=SSE_HEARTBEAT_SECS)
                    yield _sse_pack(event_name, payload)
                except queue.Empty:
                    # 心跳：保活 + 让 server 知道客户端还在
                    yield ": keepalive\n\n"
                except GeneratorExit:
                    raise
                except (OSError, ValueError) as e:
                    log.warning("sse stream fatal: %s: %s", type(e).__name__, e)
                    return
                except Exception:
                    log.exception("sse stream unexpected error; closing stream")
                    return
        finally:
            hub.unsubscribe(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---- 启动 ----


if __name__ == "__main__":
    log.info("desk-assistant-server listening on http://%s:%d", HOST, PORT)
    log.info("db: %s", resolve_db_path())
    app.run(host=HOST, port=PORT, threaded=True, debug=False, use_reloader=False)
