import threading
from unittest.mock import MagicMock
from ui import FetchLog


# ── ordering ──────────────────────────────────────────────────────────────────

def test_new_entries_appear_in_insertion_order():
    log = FetchLog()
    log.set("a", "A")
    log.set("b", "B")
    log.set("c", "C")
    assert list(log._entries.keys()) == ["a", "b", "c"]


def test_updated_entry_moves_to_end():
    log = FetchLog()
    log.set("a", "A")
    log.set("b", "B")
    log.set("a", "A2")  # update "a" → should move to end
    assert list(log._entries.keys()) == ["b", "a"]


def test_updated_entry_value_is_new():
    log = FetchLog()
    log.set("ch1", "fetching")
    log.set("ch1", "done")
    assert log._entries["ch1"] == "done"


def test_set_twice_keeps_one_entry():
    log = FetchLog()
    log.set("ch1", "v1")
    log.set("ch1", "v2")
    assert len(log._entries) == 1


# ── maxlen eviction ───────────────────────────────────────────────────────────

def test_oldest_evicted_when_maxlen_exceeded():
    log = FetchLog(maxlen=3)
    log.set("a", "A")
    log.set("b", "B")
    log.set("c", "C")
    log.set("d", "D")  # "a" should be evicted
    assert "a" not in log._entries
    assert list(log._entries.keys()) == ["b", "c", "d"]


def test_maxlen_of_one():
    log = FetchLog(maxlen=1)
    log.set("a", "A")
    log.set("b", "B")
    assert list(log._entries.keys()) == ["b"]


def test_update_does_not_evict_when_within_maxlen():
    log = FetchLog(maxlen=3)
    log.set("a", "A")
    log.set("b", "B")
    log.set("a", "A2")  # update, not new — still 2 entries
    assert len(log._entries) == 2


# ── rendering ─────────────────────────────────────────────────────────────────

def _render(log, height):
    """Collect all lines yielded by __rich_console__."""
    console = MagicMock()
    options = MagicMock()
    options.height = height
    return list(log.__rich_console__(console, options))


def test_empty_log_yields_waiting_message():
    log = FetchLog()
    lines = _render(log, height=10)
    assert len(lines) == 1
    assert "Waiting" in lines[0].plain


def test_render_shows_all_entries_when_height_large():
    log = FetchLog()
    for i in range(5):
        log.set(str(i), f"line {i}")
    lines = _render(log, height=10)
    assert len(lines) == 5


def test_render_clips_to_height_showing_newest():
    log = FetchLog()
    for i in range(10):
        log.set(str(i), f"line {i}")
    lines = _render(log, height=3)
    assert len(lines) == 3
    # last 3 entries: 7, 8, 9
    assert "line 7" in lines[0].plain
    assert "line 9" in lines[2].plain


def test_render_newest_at_bottom_after_update():
    log = FetchLog()
    log.set("a", "line a")
    log.set("b", "line b")
    log.set("a", "line a updated")  # moves "a" to end
    lines = _render(log, height=10)
    assert "line b"         in lines[0].plain
    assert "line a updated" in lines[1].plain


# ── thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_sets_do_not_raise():
    log = FetchLog(maxlen=100)
    errors = []

    def worker(n):
        try:
            for i in range(50):
                log.set(f"key-{n}-{i}", f"value {n} {i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(log._entries) <= 100
