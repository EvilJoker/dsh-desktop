---
date: 2026-06-04
status: current
target: desk-assistant server (Flask) 全部 HTTP/SSE 接口契约
---

# Desk Assistant HTTP & SSE API

> 适用版本：v2（SQLite 后端，瘦事件 SSE）。  
> 监听：`127.0.0.1:18675`（默认；`server/app.py` 顶部 `HOST` / `PORT` 可改）。  
> 数据来源：`~/.desk-assistant/state.db`（生产）/ `state_test.db`（调试，详见 [§ 1.5](#15-调试库切换)）。

## 0. 约定

- **请求体**：`Content-Type: application/json`；Body ≤ 64 KB（`MAX_CONTENT_LENGTH`）。
- **响应体**：`Content-Type: application/json; charset=utf-8`（SSE 例外，详见 § 4）。
- **字符集**：UTF-8；中文字符不需要转义。
- **时间格式**：`created_at` / `updated_at` / `completed_at` 均为 ISO 8601 字符串（精确到秒，如 `2026-06-04T10:00:00`），由 server 端写入。
- **错误响应**：见 [§ 5](#5-错误响应)。

## 1. 总览

| 资源 | 路径前缀 | 操作 |
| --- | --- | --- |
| Metrics | `/api/metrics` | 列出 / 写入 / 删除 |
| Events  | `/api/events`  | 列表 / 创建 / 勾选 / 删除 |
| SSE     | `/events`      | 长连接瘦事件推送 |

### 1.1 路径参数与 id 编码

- metric id：URL 段，例如 `cpu` / `mem_pct` / `todo_count`。建议使用 ASCII + `_` + `-`。
- event id：整数主键，正文里直接 `123`。
- id 中如包含特殊字符（`/` 等）需要 percent-encode；当前 server 端未做严格白名单，按 Flask 路由规则原样匹配。

### 1.2 列表排序

- `GET /api/metrics` → `ORDER BY position ASC, id ASC`
- `GET /api/events`（默认过滤）→ `ORDER BY done ASC, created_at DESC`
- `GET /api/events?all=true` → `ORDER BY created_at DESC`

### 1.3 限流与鉴权

当前版本**无鉴权**（仅绑定 `127.0.0.1`，外网不可达）。**不要**在公网/共享网段暴露此端口。

### 1.4 体积限制

| 资源 | 上限 |
| --- | --- |
| 单条 metric | 无字段级限制（受请求体 64 KB 约束） |
| events 表行数 | 10 000 条（超出由触发器滚动删最老 100 条） |
| `GET /api/events`（默认）| 200 条 |
| `GET /api/events?all=true` | `limit` 显式传值，无内部上限（建议 ≤ 1000） |
| SSE 推送频率 | 与 store 写入一一对应；不推完整数据 |

### 1.5 调试库切换

通过 `DESK_ASSISTANT_DB` 环境变量切到测试库（仅接受 `~/.desk-assistant/` 下的纯文件名）：

```bash
DESK_ASSISTANT_DB=state_test.db /usr/bin/python3 desk-assistant/server/app.py
# → 日志输出: db: /home/<user>/.desk-assistant/state_test.db
```

**调试/测试必须使用测试库**，禁止直接打 `state.db` —— 调试期会反复增删数据、跑迁移、重置 ID，会污染生产数据。详见 `.claude/skills/desk-assistant-workflow/SKILL.md` 第 1 节。

## 2. Metrics API

### 2.1 字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | TEXT | 是（路径） | 主键，如 `cpu` / `todo_count` |
| `label` | TEXT | 是 | 显示名 |
| `value` | REAL | 是 | 数值；`type=progress` 时建议 0–100 |
| `unit` | TEXT | 否 | 单位符号，如 `%` / `GB`；默认 `""` |
| `type` | TEXT | 否 | `progress`（默认）/ `number` |
| `position` | INTEGER | 否 | 排序权重，**小在前**；默认 `0` |
| `updated_at` | TEXT | 否（响应） | ISO8601，由 server 写入 |

### 2.2 `GET /api/metrics`

列出所有指标。

- **请求**：无 body、无 query
- **响应**：`200 OK` + JSON 数组，按 `position ASC, id ASC` 排序
- **示例**：

```bash
curl -s http://127.0.0.1:18675/api/metrics
```

```json
[
  {
    "id": "cpu",
    "label": "CPU",
    "value": 77.0,
    "unit": "%",
    "type": "progress",
    "position": 0,
    "updated_at": "2026-06-04T10:00:00"
  },
  {
    "id": "mem",
    "label": "Memory",
    "value": 62.0,
    "unit": "%",
    "type": "progress",
    "position": 1,
    "updated_at": "2026-06-04T10:00:00"
  },
  {
    "id": "todo_count",
    "label": "待办",
    "value": 12.0,
    "unit": "",
    "type": "number",
    "position": 10,
    "updated_at": "2026-06-04T09:30:00"
  }
]
```

### 2.3 `PUT /api/metrics/<id>`

创建或全量覆盖。

- **必填字段**：`label`、`value`
- **可选字段**：`unit`（默认 `""`）、`type`（默认 `progress`）、`position`（默认 `0`）
- **响应**：`200 OK` + 写入后对象
- **副作用**：触发 SSE `metrics.changed`（payload `{"id": "<id>"}`）
- **示例**：

```bash
curl -s -X PUT http://127.0.0.1:18675/api/metrics/cpu \
  -H 'Content-Type: application/json' \
  -d '{"label":"CPU","value":77.5,"unit":"%","type":"progress","position":0}'
```

```json
{
  "id": "cpu",
  "label": "CPU",
  "value": 77.5,
  "unit": "%",
  "type": "progress",
  "position": 0,
  "updated_at": "2026-06-04T10:15:00"
}
```

**类型错误示例**（响应 400）：

```bash
curl -s -X PUT http://127.0.0.1:18675/api/metrics/cpu \
  -H 'Content-Type: application/json' \
  -d '{"label":"CPU","value":"not_a_number"}'
# → {"error": "invalid field type: could not convert string to float: 'not_a_number'"}
```

### 2.4 `DELETE /api/metrics/<id>`

删除一项。

- **响应**：`204 No Content`（无 body）
- **副作用**：触发 SSE `metrics.changed`
- **不存在**：响应 `404`

```bash
curl -s -X DELETE -w '%{http_code}\n' http://127.0.0.1:18675/api/metrics/cpu
# → 204
```

## 3. Events API

### 3.1 字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | 是（响应） | 自增主键 |
| `external_id` | TEXT UNIQUE | 否 | 写入方幂等键；同值重复 POST 返回现有 |
| `type` | TEXT | 否 | `todo`（默认）/ `alert` / `reminder` / `system` / ... |
| `name` | TEXT | 是 | 主标题（列表里那行字） |
| `description` | TEXT | 否 | 一句话补充；默认 `""` |
| `content` | TEXT | 否 | 详细内容（可长，列表不渲染） |
| `source` | TEXT | 否 | 写入来源标识：`cron` / `cli` / `openclaw` / `user` / ... |
| `created_at` | TEXT | 否（响应） | ISO8601 |
| `done` | INTEGER | 否 | `0` / `1`；默认 `0` |
| `completed_at` | TEXT | 否 | ISO8601；`done=1` 时由 server 写入，`done=0` 时由 server 清掉 |
| `expire_seconds` | INTEGER | 否 | 完成后保留秒数；默认 `21600`（6h） |

### 3.2 `GET /api/events`

默认过滤：未处理 **OR**（已完成且未过期），最多 200 条。

- **Query**：
  - `all=true`：返回全量分页（不再过滤）
  - `limit=N`：全量模式下的上限（默认 200）
  - `offset=M`：全量模式下的偏移（默认 0）
  - 默认模式忽略 `limit/offset` 之外的其他参数
- **响应**：`200 OK` + JSON 数组
- **示例 1：默认过滤**：

```bash
curl -s http://127.0.0.1:18675/api/events
```

```json
[
  {
    "id": 123,
    "external_id": "task-001",
    "type": "todo",
    "name": "回邮件",
    "description": "周报相关",
    "content": "",
    "source": "cron",
    "created_at": "2026-06-04T09:00:00",
    "done": 0,
    "completed_at": null,
    "expire_seconds": 21600
  }
]
```

- **示例 2：全量分页**：

```bash
curl -s 'http://127.0.0.1:18675/api/events?all=true&limit=50&offset=0'
```

### 3.3 `POST /api/events`

创建一条事件。

- **必填字段**：`name`
- **可选字段**：`type`、`description`、`content`、`source`、`external_id`、`expire_seconds`
- **响应**：`201 Created` + 新对象
- **副作用**：触发 SSE `events.changed`（payload `{"reason":"insert","id":<id>}`）
- **幂等**：`external_id` 重复时**不插入**，返回已有对象（同 201，不发 SSE）
- **示例**：

```bash
curl -s -X POST http://127.0.0.1:18675/api/events \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "回邮件",
    "type": "todo",
    "description": "周报相关",
    "source": "cron",
    "external_id": "task-001"
  }'
```

```json
{
  "id": 123,
  "external_id": "task-001",
  "type": "todo",
  "name": "回邮件",
  "description": "周报相关",
  "content": "",
  "source": "cron",
  "created_at": "2026-06-04T10:30:00",
  "done": 0,
  "completed_at": null,
  "expire_seconds": 21600
}
```

- **缺 name**：响应 `400 {"error": "missing required field: name"}`
- **非 dict body**：响应 `400 {"error": "JSON object body required"}`
- **极端并发删除**（`external_id` 预检通过但插入前被删）：响应 `500 {"error": "concurrent delete"}`

### 3.4 `PATCH /api/events/<id>`

切换完成状态。

- **Body**：`{"done": true | false}`
- **响应**：`200 OK` + 更新后对象
- **副作用**：
  - `done: true` → server 写入 `completed_at = now`（ISO8601）
  - `done: false` → server 清掉 `completed_at`
  - 触发 SSE `events.changed`（payload `{"reason":"update","id":<id>}`）
- **示例**：

```bash
curl -s -X PATCH http://127.0.0.1:18675/api/events/123 \
  -H 'Content-Type: application/json' \
  -d '{"done": true}'
```

```json
{
  "id": 123,
  "external_id": "task-001",
  "type": "todo",
  "name": "回邮件",
  "description": "周报相关",
  "content": "",
  "source": "cron",
  "created_at": "2026-06-04T10:30:00",
  "done": 1,
  "completed_at": "2026-06-04T11:00:00",
  "expire_seconds": 21600
}
```

- **不存在**：响应 `404`
- **`done` 字段类型错**：响应 `400 {"error": "done must be boolean"}`

### 3.5 `DELETE /api/events/<id>`

删除一条事件。

- **响应**：`204 No Content`
- **副作用**：触发 SSE `events.changed`（payload `{"reason":"delete","id":<id>}`）
- **不存在**：响应 `404`

```bash
curl -s -X DELETE -w '%{http_code}\n' http://127.0.0.1:18675/api/events/123
# → 204
```

### 3.6 状态机

```text
       POST                      PATCH done=true                 (now - completed_at) > expire_seconds
[不存在] ─────→ [未完成 done=0] ────────────────→ [已完成 done=1, completed_at=t] ─────────────→ [不展示]
                       ↑                                                                │
                       └────────────────── PATCH done=false ─────────────────────────────┘
```

- **不展示**：记录仍在表中（仅 `GET /api/events?all=true` 能看到），但默认过滤会排除。
- 取消勾选会清 `completed_at`，事件回到「未完成」态，再次显示在列表中。
- 物理删除由 1w 上限触发器（按 `created_at`）滚动执行，与 `done` 状态无关。

## 4. SSE（Server-Sent Events）

### 4.1 端点

- 路径：`GET /events`
- 响应：`Content-Type: text/event-stream`，长连接
- 心跳：每 15s 一行 `: keepalive\n\n`（注释行，不算事件）
- 客户端库建议：`python-sseclient` / `EventSource` (browser) / 自实现按 `event:` + `data:` 行解析

### 4.2 帧格式

```text
event: hello
data: {"protocol":1}

event: metrics.changed
data: {"id":"cpu"}

event: events.changed
data: {"reason":"insert","id":123}

: keepalive
```

### 4.3 事件清单

| event 名 | 触发时机 | payload |
| --- | --- | --- |
| `hello` | 客户端连上后立即推一次 | `{"protocol": 1}` |
| `metrics.changed` | `PUT` / `DELETE /api/metrics/<id>` | `{"id": "<metric_id>"}` |
| `events.changed` | `POST`（插入）/ `PATCH`（更新）/ `DELETE /api/events/<id>` | `{"reason": "insert" \| "update" \| "delete", "id": <event_id>}` |
| `keepalive`（注释） | 15s 无业务事件 | 空（`: keepalive\n\n`） |

注意 `events.changed` 客户端需要用 `id` 调 `GET /api/events/<id>` 或重新拉列表，不推完整数据。

### 4.4 客户端实现模式

```python
import json
from urllib import request

def watch_sse(url="http://127.0.0.1:18675/events"):
    req = request.Request(url, headers={"Accept": "text/event-stream"})
    with request.urlopen(req, timeout=None) as resp:
        event_name = None
        for raw in resp:
            line = raw.decode("utf-8").rstrip("\n")
            if not line:
                event_name = None
                continue
            if line.startswith(":"):
                # 注释/心跳
                continue
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                yield event_name, payload
```

panel 端在此之上加 150ms debounce（高频批量 POST 时把 N 次 `events.changed` 合并为 1 次 `GET /api/events`）。

### 4.5 重连建议

当前版本 server 端不发送 `id:` 字段，**不支持断点续传**。客户端断开后重连只能拿到断开之后的增量变化。重连前建议先 `GET /api/metrics` + `GET /api/events` 拉一次当前快照。

## 5. 错误响应

所有 4xx / 5xx 响应：

```json
{ "error": "人类可读的简短说明" }
```

| 状态 | 触发条件 |
| --- | --- |
| `400 Bad Request` | JSON body 缺失/非对象；必填字段缺失；字段类型错；`limit` / `offset` 非整数或负数 |
| `404 Not Found` | metric id / event id 不存在 |
| `413 Payload Too Large` | 请求体超过 64 KB（防 OOM） |
| `500 Internal Server Error` | 内部异常；典型场景：`POST` 传入的 `external_id` 通过预检但被并发删除 |

## 6. 完整调用示例

### 6.1 curl 全流程

```bash
# 1. 写指标
curl -s -X PUT http://127.0.0.1:18675/api/metrics/cpu \
  -H 'Content-Type: application/json' \
  -d '{"label":"CPU","value":42.0,"unit":"%"}'

# 2. 写事件（幂等 external_id）
curl -s -X POST http://127.0.0.1:18675/api/events \
  -H 'Content-Type: application/json' \
  -d '{"name":"回邮件","external_id":"task-001","source":"cron"}'

# 3. 列出
curl -s http://127.0.0.1:18675/api/metrics
curl -s http://127.0.0.1:18675/api/events

# 4. 勾选
curl -s -X PATCH http://127.0.0.1:18675/api/events/123 \
  -H 'Content-Type: application/json' \
  -d '{"done": true}'

# 5. 全量分页
curl -s 'http://127.0.0.1:18675/api/events?all=true&limit=100&offset=0'

# 6. 监听 SSE
curl -N http://127.0.0.1:18675/events
```

### 6.2 Python 客户端

```python
import json
from urllib import request

BASE = "http://127.0.0.1:18675"

def _http(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with request.urlopen(req, timeout=10) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)

# PUT metric
_, m = _http("PUT", "/api/metrics/cpu",
             {"label": "CPU", "value": 77.5, "unit": "%"})
print(m)

# POST event (idempotent via external_id)
_, e = _http("POST", "/api/events", {
    "name": "回邮件",
    "external_id": "task-001",
    "source": "cron",
})
print(e)
event_id = e["id"]

# PATCH done
_, e2 = _http("PATCH", f"/api/events/{event_id}", {"done": True})
print(e2["done"], e2["completed_at"])
```

### 6.3 openclaw / 外部集成

cron 任务写事件建议带 `external_id` 实现幂等：

```bash
*/5 * * * * /usr/bin/curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"name":"磁盘告警","type":"alert","source":"cron","external_id":"disk-alert-'$HOSTNAME'","expire_seconds":3600}' \
  http://127.0.0.1:18675/api/events
```

## 7. 端到端流程示意

```text
[cron / openclaw / panel]
    │
    ├── POST /api/events ───► server ──► SQLite INSERT
    │                                     │
    │                                     ▼ SSE: events.changed
    │                                     │
    └── PATCH /api/events/<id> ◄──────── panel (用户勾选)
                                       │
                                       ▼
                                SQLite UPDATE done
                                       │
                                       ▼ SSE: events.changed
```

## 8. 变更历史

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-06-04 | v2 | SQLite + 瘦事件 SSE（替代旧的 `state.json` + `state.changed` 全量推送） |
