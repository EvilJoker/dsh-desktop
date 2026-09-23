"""server/sse_hub.py — SSE 订阅者管理 + 瘦事件广播。

设计：
- 每个 SSE 长连接调 subscribe() 拿一个独立 queue.Queue
- store 层变更时调 push(event_name, payload) 广播给所有订阅者
- 订阅者循环从自己的 queue 取事件 yield 给 HTTP 流
- 队列满时丢弃（订阅者太慢）；客户端下一次主动拉 REST 会补齐

线程安全：subscribe/unsubscribe/push 互斥；put_nowait 是 queue 本身线程安全。
"""
import logging
import queue
import threading

log = logging.getLogger(__name__)

# 单个订阅者最多缓冲的事件数；超出丢最新一条
QUEUE_MAXSIZE = 64


class SseHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = []  # list[queue.Queue]

    def subscribe(self):
        """新增订阅者；返回一个独立队列。"""
        q = queue.Queue(maxsize=QUEUE_MAXSIZE)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        """连接关闭时清理订阅者。"""
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def push(self, event_name, payload):
        """向所有订阅者投递 (event_name, payload) 二元组。

        - event_name：SSE 的 event: 字段值，如 "metrics.changed"
        - payload：可 JSON 序列化的 dict
        """
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait((event_name, payload))
            except queue.Full:
                log.warning(
                    "SSE subscriber queue full, dropping event=%s payload=%s",
                    event_name, payload,
                )
