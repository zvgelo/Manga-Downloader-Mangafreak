"""
Orchestration tests for DownloadService using fakes — no Selenium, no network.
Scraper calls and download_chapter are monkeypatched so we can assert the
producer/consumer pipeline drives the observer correctly.
"""

import service
from events import DownloadObserver
from models import Chapter, SearchResult
from settings import Settings


class FakeDriver:
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


class RecordingObserver(DownloadObserver):
    def __init__(self):
        self.calls = []

    def start(self, total):
        self.calls.append(("start", total))

    def stop(self):
        self.calls.append(("stop",))

    def fetch_skipped(self, key, num):
        self.calls.append(("fetch_skipped", key, num))

    def fetch_started(self, key, num):
        self.calls.append(("fetch_started", key, num))

    def chapter_failed(self, key, num):
        self.calls.append(("chapter_failed", key, num))


def _make_service(monkeypatch, settings):
    drivers = []

    def factory(headless=True):
        d = FakeDriver()
        drivers.append(d)
        return d

    svc = service.DownloadService(settings, driver_factory=factory)
    return svc, drivers


def test_search_and_list_delegate(monkeypatch):
    svc, drivers = _make_service(monkeypatch, Settings())
    monkeypatch.setattr(service, "search_manga",
                        lambda drv, q, s: [SearchResult("Naruto", "u")])
    monkeypatch.setattr(service, "get_chapters",
                        lambda drv, url, s: [Chapter("Chapter 1", "c1")])

    assert svc.search("naruto")[0].title == "Naruto"
    assert svc.list_chapters("u")[0].title == "Chapter 1"
    # both reused the single lazily-created driver
    assert len(drivers) == 1


def test_download_happy_path(monkeypatch):
    settings = Settings(browser_workers=2, chapter_workers=2)
    svc, drivers = _make_service(monkeypatch, settings)

    monkeypatch.setattr(service, "is_downloaded", lambda *a: False)
    monkeypatch.setattr(service, "get_chapter_images", lambda drv, ch, s: ["img1", "img2"])

    downloaded = []
    monkeypatch.setattr(service, "download_chapter",
                        lambda *a, **k: downloaded.append(a[2]))  # a[2] = title

    obs = RecordingObserver()
    selected = [Chapter("Chapter 1", "c1"), Chapter("Chapter 2", "c2")]
    svc.download(selected, "/tmp/manga", "Test", grayscale=False, observer=obs)

    assert obs.calls[0] == ("start", 2)
    assert obs.calls[-1] == ("stop",)
    assert {c[1] for c in obs.calls if c[0] == "fetch_started"} == {"Chapter 1", "Chapter 2"}
    assert set(downloaded) == {"Chapter 1", "Chapter 2"}
    # extra (non-primary) driver was disposed; primary kept for reuse
    assert sum(d.quit_called for d in drivers) == 1


def test_download_skips_already_downloaded(monkeypatch):
    settings = Settings(browser_workers=1, chapter_workers=1)
    svc, drivers = _make_service(monkeypatch, settings)

    monkeypatch.setattr(service, "is_downloaded",
                        lambda md, ms, title: title == "Chapter 1")
    monkeypatch.setattr(service, "get_chapter_images", lambda drv, ch, s: ["img"])
    monkeypatch.setattr(service, "download_chapter", lambda *a, **k: None)

    obs = RecordingObserver()
    selected = [Chapter("Chapter 1", "c1"), Chapter("Chapter 2", "c2")]
    svc.download(selected, "/tmp/manga", "Test", observer=obs)

    skipped = [c for c in obs.calls if c[0] == "fetch_skipped"]
    started = [c for c in obs.calls if c[0] == "fetch_started"]
    assert skipped == [("fetch_skipped", "Chapter 1", 1)]
    assert started == [("fetch_started", "Chapter 2", 2)]


def test_download_permanent_failure_after_retries(monkeypatch):
    settings = Settings(browser_workers=1, chapter_workers=1, max_chapter_retries=2)
    svc, drivers = _make_service(monkeypatch, settings)

    monkeypatch.setattr(service, "is_downloaded", lambda *a: False)
    monkeypatch.setattr(service, "get_chapter_images", lambda drv, ch, s: ["img"])

    def always_fail(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(service, "download_chapter", always_fail)

    obs = RecordingObserver()
    svc.download([Chapter("Chapter 1", "c1")], "/tmp/manga", "Test", observer=obs)

    assert ("chapter_failed", "Chapter 1", 1) in obs.calls
