---
date: 2026-06-04
status: design-approved
target: 把 server 端 state.json 全量存储替换为 SQLite，metrics/events 独立表 + 新 REST 接口
---

# Metrics & Events SQLite 数据库设计

## 1. 目标

把当前 `state.json` 全量快照模型替换为 SQLite 两表结构：

- **metrics**：只存最新值（写入即覆盖），保持指标轻量
- **events**：积累式存储（最多 1w 条，超过自动滚动删除最老的），UI 端按条件过滤展示

不考虑旧 API 兼容。state.json 整个抛弃。

## 2. 数据库 Schema

文件位置：`~/.desk-assistant/state.db`（与原 state.json 同目录，server 首次启动自动建库建表）

### 2.1 `metrics` 表

```sql
CREATE TABLE metrics (
    id          TEXT PRIMARY KEY,                       -- "cpu" / "mem" / "todo_count"
    label       TEXT NOT NULL,                          -- 显示名 "CPU"
    value       REAL NOT NULL,                          -- 数值；progress 类型 0-100
    unit        TEXT DEFAULT '',                        -- "%" / "" / "GB"
    type        TEXT NOT NULL DEFAULT 'progress',       -- progress | number
    position    INTEGER NOT NULL DEFAULT 0,             -- 排序权重（小在前）
    updated_at  TEXT NOT NULL                           -- ISO8601
);
```

写入语义：`INSERT OR REPLACE INTO metrics(...) VALUES(...)` — 同 id 直接覆盖。

读取：`SELECT * FROM metrics ORDER BY position, id`

### 2.2 `events` 表

```sql
CREATE TABLE events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id    TEXT UNIQUE,                         -- 写入方可选指定，用于幂等去重
    type           TEXT NOT NULL DEFAULT 'todo',        -- 事件类型枚举（todo / alert / reminder / system / ...）
    name           TEXT NOT NULL,                       -- 标题/主显示
    description    TEXT NOT NULL DEFAULT '',            -- 一句话补充说明
    content        TEXT NOT NULL DEFAULT '',            -- 详细内容（可较长，如 markdown）
    source         TEXT NOT NULL DEFAULT '',            -- "cron" / "cli" / "openclaw" / "user"
    created_at     TEXT NOT NULL,                       -- ISO8601
    done           INTEGER NOT NULL DEFAULT 0,          -- 0/1
    completed_at   TEXT,                                -- ISO8601 或 NULL
    expire_seconds INTEGER NOT NULL DEFAULT 21600       -- 完成后保留秒数，默认 6h
);

CREATE INDEX idx_events_done_completed ON events(done, completed_at);
CREATE INDEX idx_events_created       ON events(created_at DESC);
CREATE INDEX idx_events_type          ON events(type);
```

字段语义：

- **`type`**：事件分类，由写入方指定。建议枚举：`todo`（默认）/ `alert` / `reminder` / `system` / `chat` 等。前端按 type 渲染不同样式或图标。
- **`name`**：主标题，必填。前端列表的"那行字"。
- **`description`**：一句话补充。可选，前端可作为副标题或 tooltip。
- **`content`**：详细内容（可长）。点开后展示，列表里不显示，避免拉伸。

### 2.3 1w 上限滚动删除（触发器）

```sql
CREATE TRIGGER trim_events_after_insert
AFTER INSERT ON events
WHEN (SELECT COUNT(*) FROM events) > 10000
BEGIN
    DELETE FROM events WHERE id IN (
        SELECT id FROM events ORDER BY created_at ASC LIMIT 100
    );
END;
```

**为什么一次删 100 而不是 1**：amortized 优化。高频插入时每条都触发删除会拖慢写入；按批清理性能更好，最坏情况短暂溢出 100 条可接受（远低于 1w 上限）。

### 2.4 展示过滤查询（核心 SQL）

```sql
SELECT id, external_id, type, name, description, content,
       source, created_at, done, completed_at, expire_seconds
FROM events
WHERE done = 0
   OR (
        done = 1
        AND completed_at IS NOT NULL
        AND (strftime('%s','now') - strftime('%s', completed_at)) < expire_seconds
   )
ORDER BY done ASC,           -- 未完成在前
         created_at DESC     -- 同状态内按新到旧
LIMIT 200;
```

server 返回最多 200 条，panel 端再截前 100 条显示。

## 3. REST 接口（全新设计）

### 3.1 Metrics

| 方法 | 路径 | Body / 返回 | 用途 |
| --- | --- | --- | --- |
| `GET` | `/api/metrics` | `[{id,label,value,unit,type,position,updated_at}, ...]` | 全量拉取（按 position 排序） |
| `PUT` | `/api/metrics/{id}` | `{label, value, unit?, type?, position?}` → 写入后对象 | 创建或覆盖 |
| `DELETE` | `/api/metrics/{id}` | 204 | 删除一项 |

### 3.2 Events

| 方法 | 路径 | Body / 返回 | 用途 |
| --- | --- | --- | --- |
| `GET` | `/api/events` | 默认过滤后最多 200 条 | panel 列表源 |
| `GET` | `/api/events?all=true&limit=200&offset=0` | 全量分页 | 历史回看 / 调试 |
| `POST` | `/api/events` | `{name, type?, description?, content?, source?, external_id?, expire_seconds?}` → `{id, ...}` | 创建；`external_id` 已存在返回现有，不重复插入；`name` 必填，其他可选 |
| `PATCH` | `/api/events/{id}` | `{done?: bool}` → 新对象 | 勾选 / 取消勾选；`done=true` 自动补 `completed_at=now`，`done=false` 清掉 |
| `DELETE` | `/api/events/{id}` | 204 | 主动删除 |

## 4. SSE 推送（瘦事件）

只推「发生了什么变化」，不推完整数据。panel 收到通知后**自己拉 REST**取最新。

### 4.1 帧格式

```text
event: hello
data: {"protocol":1}

event: metrics.changed
data: {"id":"cpu"}

event: events.changed
data: {"reason":"insert","id":123}     // "insert" | "update" | "delete"

: keepalive                            // 注释行心跳，每 15s 一次（无事件时）
```

### 4.2 连接生命周期

1. 客户端 `GET /events`（`Accept: text/event-stream`）建立长连接
2. server 立即推 `event: hello` 帧（客户端确认连上）
3. 之后任意 store 写入 → server 推对应 `*.changed` 帧
4. 若 15 秒无事件 → server 推 `: keepalive\n\n`（注释行，客户端忽略，仅用于保活和探测断开）

### 4.3 客户端行为

- **panel 在 `hello` 时**：立即调 `GET /api/metrics` + `GET /api/events` 拉初始数据
- **panel 在 `*.changed` 时**：用 150ms debounce 合并 → 调对应 REST 拉取
  - 防止 100 次/秒批量 POST 时 panel 触发 100 次 GET 拖垮 server

### 4.4 为什么不在 SSE 里塞完整列表

events 上限 1w 条，每次插入都全推会撑爆推送通道。瘦事件 + 客户端拉取是经典分离，server 推送负担恒定（每事件几十字节）。

## 5. 错误响应统一格式

所有 4xx / 5xx 响应统一为：

```json
{ "error": "<人类可读的简短说明>" }
```

典型错误码：

| 状态 | 触发 |
| --- | --- |
| 400 | JSON body 缺失/类型错；必填字段缺失；`limit/offset` 非整数或负数 |
| 404 | metric_id / event_id 不存在 |
| 413 | 请求体超过 `MAX_CONTENT_LENGTH = 64 KB`（防 OOM） |
| 500 | 内部异常（如 events insert 极端并发删除） |

POST 成功返回 201；PUT/PATCH/GET 成功返回 200；DELETE 成功返回 204（无 body）。

## 6. 文件结构变化

```text
desk-assistant/server/
├── app.py              路由重写：去 /api/state，加 metrics/events
├── db.py               新增：sqlite 连接、建表、迁移
├── metrics_store.py    新增：CRUD + 变更通知
├── events_store.py     新增：CRUD + 过滤查询 + 变更通知
├── sse_hub.py          新增：订阅者管理 + 瘦事件广播
└── state.py            删除（旧的 JSON 文件 store）

desk-assistant/panel/
├── main.py             改：SSE 收到瘦事件 → 调 REST 拉数据 → 派发到 Card
├── metrics_card.py     不变（接口仍是 update_indicators(list)）
├── events_card.py      改：toggle_requested 信号 payload 改为 (event_id:int, checked:bool)
└── chat_card.py        不变

~/.desk-assistant/
├── state.db            新增（首次 server 启动自动创建）
└── state.json          删除
```

## 7. panel 端关键改造

1. **删** `_current_state` 缓存：不再持有全量 state；按需拉 REST
2. **SSE 收到** `metrics.changed` → 调 `GET /api/metrics` → `metrics_card.update_indicators()`
3. **SSE 收到** `events.changed` → 调 `GET /api/events` → `events_card.update_events()`
4. **events_card.toggle_requested** 改为 emit `(event_id:int, checked:bool)`，Panel 收到调 `PATCH /api/events/{event_id}`，不再做深拷贝合成新 state

## 8. 实施顺序

```text
[1] server/db.py + metrics_store + events_store （单独可测，pytest）
        ↓
[2] server/sse_hub + app.py 切换路由
        ↓
[3] panel/main.py + events_card 切换信号
        ↓
[4] rm ~/.desk-assistant/state.json，冷启动验证空 DB → 写入 → SSE → 渲染 全链路
```

每步独立可验证。第 1 步用 pytest 验单元行为，第 2 步用 curl 验 HTTP + curl -N 验 SSE，第 3-4 步用 UI 验完整链路。

## 9. 数据迁移

state.json **不迁移**，直接抛弃。server 启动时检测 state.db 不存在则建空库建表。如果用户之前 state.json 里有有效事件，需要保留可一次性手动迁移：

```bash
# 一次性脚本（非默认执行）
python3 -c "
import json, sqlite3
from datetime import datetime
state = json.load(open('~/.desk-assistant/state.json'))
con = sqlite3.connect('~/.desk-assistant/state.db')
for t in state.get('todos', []):
    con.execute('INSERT INTO events(external_id,text,done,created_at,completed_at) VALUES(?,?,?,?,?)',
                (t.get('id'), t['text'], 1 if t.get('done') else 0,
                 t.get('created_at') or state.get('updated_at'),
                 t.get('completed_at')))
con.commit()
"
```

但因当前 events 数量少，建议直接抛弃。

## 10. 风险与权衡

| 风险 | 缓解 |
| --- | --- |
| SQLite 写并发 | server 单进程访问，无并发问题；多写入方走 HTTP POST 由 server 串行 |
| 触发器删 100 条引起短暂卡顿 | 高频插入场景下可观测；1w 上限本身已是宽松，正常使用触发频次低 |
| SSE 通知 + 客户端拉取的二次往返延迟 | 局域网毫秒级，可忽略；换来推送通道极简 |
| state.json 抛弃后无法离线读 | 用户已确认接受；调试时用 `sqlite3 state.db` 直接查 |

## 11. 后续可扩展点（不在本次范围）

- metrics 时序化（新增 metric_samples 表）
- events 标签/分类
- 软删除（status: active/archived）
- 多写入方鉴权
- 备份/导出
