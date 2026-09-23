"""server/sse_hub.py 全覆盖：subscribe/unsubscribe/push + 队列满 drop。"""
import queue
import threading

import pytest

from server.sse_hub import QUEUE_MAXSIZE, SseHub


def test_subscribe_returns_independent_queue():
    hub = SseHub()
    q1 = hub.subscribe()
    q2 = hub.subscribe()
    assert q1 is not q2
    assert q1.maxsize == QUEUE_MAXSIZE
    # 互不影响
    q1.put_nowait(("a", {"id": 1}))
    assert q1.qsize() == 1
    assert q2.qsize() == 0


def test_unsubscribe_removes_queue():
    hub = SseHub()
    q = hub.subscribe()
    assert len(hub._subscribers) == 1
    hub.unsubscribe(q)
    assert len(hub._subscribers) == 0


def test_unsubscribe_missing_queue_no_error():
    """取消不存在的订阅 → 静默 no-op。"""
    hub = SseHub()
    q = hub.subscribe()
    hub.unsubscribe(q)  # 第一次删
    hub.unsubscribe(q)  # 第二次已不在，ValueError 被吞


def test_push_delivers_to_all_subscribers():
    hub = SseHub()
    qs = [hub.subscribe() for _ in range(3)]
    hub.push("metrics.changed", {"id": "cpu"})
    for q in qs:
        event, payload = q.get_nowait()
        assert event == "metrics.changed"
        assert payload == {"id": "cpu"}


def test_push_drops_oldest_when_queue_full(caplog):
    """队列满时 put_nowait 抛 Full，被 try/except 吞 + log.warning。"""
    hub = SseHub()
    q = hub.subscribe()
    # 把队列填满
    for i in range(QUEUE_MAXSIZE):
        q.put_nowait(("x", {"i": i}))
    with caplog.at_level("WARNING", logger="server.sse_hub"):
        hub.push("drop.test", {"id": 99})
    # 队列里仍是满的（新的被 drop）
    assert q.qsize() == QUEUE_MAXSIZE
    assert any("dropping event" in rec.message for rec in caplog.records)


def test_push_isolates_subscribers():
    """一个订阅者抛 Full 也不影响其他。"""
    hub = SseHub()
    q_full = hub.subscribe()
    q_ok = hub.subscribe()
    for i in range(QUEUE_MAXSIZE):
        q_full.put_nowait(("x", {"i": i}))
    hub.push("evt", {"k": "v"})
    # q_ok 收到
    assert q_ok.get_nowait() == ("evt", {"k": "v"})


def test_concurrent_subscribe_and_push():
    """线程安全：并发 subscribe/unsubscribe/push 不死锁不丢。"""
    hub = SseHub()
    subs = []

    def adder():
        for _ in range(50):
            subs.append(hub.subscribe())

    def pusher():
        for i in range(50):
            hub.push("evt", {"i": i})

    threads = [threading.Thread(target=adder) for _ in range(3)]
    threads += [threading.Thread(target=pusher) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 50*3 = 150 个订阅者
    assert len(subs) == 150
    # 至少部分订阅者收到事件
    received = sum(1 for q in subs if not q.empty())
    assert received > 0
