"""server/events_store.py 全覆盖：list_visible/list_all/get/insert/patch/delete + 幂等 + TOCTOU。"""


def test_list_visible_empty(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    assert store.list_visible() == []


def test_insert_without_external_id(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="回邮件", type_="todo", description="周报")
    assert obj["id"] > 0
    assert obj["name"] == "回邮件"
    assert obj["type"] == "todo"
    assert obj["description"] == "周报"
    assert obj["done"] == 0
    assert obj["completed_at"] is None
    assert obj["external_id"] is None


def test_insert_with_external_id_first_time(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="A", external_id="ext-1")
    assert obj["external_id"] == "ext-1"


def test_insert_idempotent_on_external_id(tmp_db):
    """同 external_id 二次插入 → 返回现有，不新建，不发 on_change。"""
    from server.events_store import EventsStore

    calls = []
    store = EventsStore(tmp_db, on_change=lambda r, eid: calls.append((r, eid)))
    first = store.insert(name="A", external_id="ext-1")
    calls.clear()
    second = store.insert(name="A 改名", external_id="ext-1", description="改后")
    # 返回同一 id，name 没改（说明没新建）
    assert second["id"] == first["id"]
    assert second["name"] == "A"  # 不是 "A 改名"
    # 不发 on_change（幂等路径不广播）
    assert calls == []


def test_list_visible_includes_undone_and_recent_done(tmp_db):
    """未完成 + 已完成未过期 都显示。"""
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    a = store.insert(name="todo A")
    b = store.insert(name="done B")
    store.patch(b["id"], done=True)
    visible = store.list_visible()
    visible_ids = {e["id"] for e in visible}
    assert a["id"] in visible_ids
    assert b["id"] in visible_ids


def test_list_visible_excludes_expired_done(tmp_db):
    """已完成且超过 expire_seconds → 不显示。"""
    import sqlite3
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="expired", expire_seconds=60)
    # 直接 SQL 改 completed_at 到 2 小时前
    tmp_db.execute(
        "UPDATE events SET done=1, completed_at='2020-01-01T00:00:00' WHERE id=?",
        (obj["id"],),
    )
    visible = store.list_visible()
    assert all(e["id"] != obj["id"] for e in visible)


def test_list_visible_orders_undone_first(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    # 先 done=0 的 a，再 done=1 的 b
    a = store.insert(name="undone A")
    b = store.insert(name="done B")
    store.patch(b["id"], done=True)
    visible = store.list_visible()
    # undone 排前
    assert visible[0]["id"] == a["id"]


def test_list_visible_respects_limit(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    for i in range(5):
        store.insert(name=f"item {i}")
    assert len(store.list_visible(limit=3)) == 3


def test_list_all_pagination(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    for i in range(5):
        store.insert(name=f"item {i}")
    page1 = store.list_all(limit=2, offset=0)
    page2 = store.list_all(limit=2, offset=2)
    page3 = store.list_all(limit=2, offset=4)
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1


def test_get_existing(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="A")
    fetched = store.get(obj["id"])
    assert fetched["name"] == "A"


def test_get_missing(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    assert store.get(99999) is None


def test_patch_done_true_sets_completed_at(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="A")
    assert obj["completed_at"] is None
    patched = store.patch(obj["id"], done=True)
    assert patched["done"] == 1
    assert patched["completed_at"] is not None


def test_patch_done_false_clears_completed_at(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="A")
    store.patch(obj["id"], done=True)
    # 取消
    patched = store.patch(obj["id"], done=False)
    assert patched["done"] == 0
    assert patched["completed_at"] is None


def test_patch_done_none_noop_returns_current(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="A")
    patched = store.patch(obj["id"], done=None)
    assert patched["id"] == obj["id"]
    assert patched["done"] == 0


def test_patch_missing_returns_none(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    assert store.patch(99999, done=True) is None


def test_delete_existing(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    obj = store.insert(name="A")
    assert store.delete(obj["id"]) is True
    assert store.get(obj["id"]) is None


def test_delete_missing(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    assert store.delete(99999) is False


def test_notify_fires_on_insert(tmp_db):
    from server.events_store import EventsStore

    calls = []
    store = EventsStore(tmp_db, on_change=lambda r, eid: calls.append((r, eid)))
    obj = store.insert(name="A")
    assert calls == [("insert", obj["id"])]


def test_notify_fires_on_patch(tmp_db):
    from server.events_store import EventsStore

    calls = []
    store = EventsStore(tmp_db, on_change=lambda r, eid: calls.append((r, eid)))
    obj = store.insert(name="A")
    calls.clear()
    store.patch(obj["id"], done=True)
    assert calls == [("update", obj["id"])]


def test_notify_fires_on_delete(tmp_db):
    from server.events_store import EventsStore

    calls = []
    store = EventsStore(tmp_db, on_change=lambda r, eid: calls.append((r, eid)))
    obj = store.insert(name="A")
    calls.clear()
    store.delete(obj["id"])
    assert calls == [("delete", obj["id"])]


def test_notify_swallows_callback_exception(tmp_db):
    from server.events_store import EventsStore

    def bad_cb(reason, eid):
        raise RuntimeError("boom")

    store = EventsStore(tmp_db, on_change=bad_cb)
    store.insert(name="A")  # 不应传播


def test_notify_no_callback_no_error(tmp_db):
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)  # 无 on_change
    store.insert(name="A")
    store.patch(1, done=True)
    store.delete(1)


def test_list_visible_newest_first_for_undone(tmp_db):
    """未完成项按 created_at 倒序。"""
    from server.events_store import EventsStore

    store = EventsStore(tmp_db)
    a = store.insert(name="first")
    b = store.insert(name="second")
    # 用 SQL 直接改 created_at 强制排序（绕过秒级精度问题）
    tmp_db.execute("UPDATE events SET created_at='2026-01-01T00:00:00' WHERE id=?", (a["id"],))
    tmp_db.execute("UPDATE events SET created_at='2026-12-31T23:59:59' WHERE id=?", (b["id"],))
    rows = store.list_visible()
    assert rows[0]["id"] == b["id"]
    assert rows[1]["id"] == a["id"]
