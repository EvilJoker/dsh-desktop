"""server/metrics_store.py 全覆盖：list_all/get/put/delete/_notify。"""


def test_list_all_empty(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    assert store.list_all() == []


def test_put_and_list_all(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    obj = store.put("cpu", label="CPU", value=77.0, unit="%", type_="progress", position=2)
    assert obj["id"] == "cpu"
    assert obj["value"] == 77.0
    assert obj["label"] == "CPU"
    assert obj["unit"] == "%"
    assert obj["type"] == "progress"
    assert obj["position"] == 2
    assert "updated_at" in obj


def test_put_overwrites(tmp_db):
    """同 id 二次 put → INSERT OR REPLACE 覆盖。"""
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    store.put("cpu", "CPU", 50.0)
    store.put("cpu", "CPU 改", 88.0, unit="%", position=1)
    rows = store.list_all()
    assert len(rows) == 1
    assert rows[0]["value"] == 88.0
    assert rows[0]["label"] == "CPU 改"


def test_list_all_sorted_by_position_then_id(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    store.put("z", "Z", 0, position=1)
    store.put("a", "A", 0, position=0)
    store.put("m", "M", 0, position=0)
    rows = store.list_all()
    assert [r["id"] for r in rows] == ["a", "m", "z"]


def test_get_existing(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    store.put("cpu", "CPU", 50.0)
    obj = store.get("cpu")
    assert obj["id"] == "cpu"
    assert obj["value"] == 50.0


def test_get_missing(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    assert store.get("nope") is None


def test_delete_existing(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    store.put("cpu", "CPU", 50.0)
    assert store.delete("cpu") is True
    assert store.get("cpu") is None


def test_delete_missing(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)
    assert store.delete("nope") is False


def test_notify_fires_on_put(tmp_db):
    from server.metrics_store import MetricsStore

    calls = []
    store = MetricsStore(tmp_db, on_change=lambda mid: calls.append(mid))
    store.put("cpu", "CPU", 1.0)
    assert calls == ["cpu"]


def test_notify_fires_on_delete(tmp_db):
    from server.metrics_store import MetricsStore

    calls = []
    store = MetricsStore(tmp_db, on_change=lambda mid: calls.append(mid))
    store.put("cpu", "CPU", 1.0)
    calls.clear()
    store.delete("cpu")
    assert calls == ["cpu"]


def test_notify_skipped_when_delete_missing(tmp_db):
    from server.metrics_store import MetricsStore

    calls = []
    store = MetricsStore(tmp_db, on_change=lambda mid: calls.append(mid))
    store.delete("nope")
    assert calls == []


def test_notify_swallows_callback_exception(tmp_db):
    """callback 抛错被 try/except 吞 + log。"""
    from server.metrics_store import MetricsStore

    def bad_cb(_):
        raise RuntimeError("boom")

    store = MetricsStore(tmp_db, on_change=bad_cb)
    # 不应传播异常
    store.put("cpu", "CPU", 1.0)


def test_notify_no_callback_no_error(tmp_db):
    from server.metrics_store import MetricsStore

    store = MetricsStore(tmp_db)  # 无 on_change
    store.put("cpu", "CPU", 1.0)
