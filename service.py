"""
Frontend-agnostic download core.

DownloadService owns the browser lifecycle and the producer/consumer/retry
pipeline, and reports progress through a DownloadObserver. It performs no
terminal I/O (no input()/print()), so the same instance can back a CLI, a GUI,
or a web request. A frontend constructs it with a Settings object, calls
search() / list_chapters() / download(), and renders the observer events.
"""

from __future__ import annotations

from concurrent.futures import (FIRST_COMPLETED, ThreadPoolExecutor,
                                 as_completed, wait)
from queue import Queue
from threading import Thread

from browser import create_driver
from downloader import download_chapter, is_downloaded
from events import DownloadObserver
from logger import get_logger
from models import Chapter, SearchResult
from scraper import get_chapter_images, get_chapters, search_manga
from settings import DEFAULT_SETTINGS, Settings

log = get_logger(__name__)


class DownloadService:
    def __init__(self, settings: Settings = DEFAULT_SETTINGS, driver_factory=create_driver):
        self.settings = settings
        self._driver_factory = driver_factory
        self._driver = None

    # ── browser lifecycle ────────────────────────────────────────────────────
    def _ensure_driver(self):
        if self._driver is None:
            self._driver = self._driver_factory(headless=True)
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.quit()
            self._driver = None

    # ── read operations ──────────────────────────────────────────────────────
    def search(self, query: str) -> list[SearchResult]:
        return search_manga(self._ensure_driver(), query, self.settings)

    def list_chapters(self, series_url: str) -> list[Chapter]:
        return get_chapters(self._ensure_driver(), series_url, self.settings)

    # ── download pipeline ──────────────────────────────────────────────────────
    def download(self, selected: list[Chapter], manga_dir: str, manga_slug: str,
                 grayscale: bool = False, observer: DownloadObserver | None = None) -> None:
        observer = observer or DownloadObserver()
        s = self.settings
        n_selected = len(selected)

        primary = self._ensure_driver()
        pool_drivers = [primary] + [self._driver_factory(headless=True)
                                    for _ in range(s.browser_workers - 1)]
        browser_pool: Queue = Queue()
        for d in pool_drivers:
            browser_pool.put(d)

        url_queue: Queue = Queue(maxsize=s.url_queue_size)

        def _fetch_chapter_urls(chapter: Chapter) -> list[str]:
            drv = browser_pool.get()
            try:
                return get_chapter_images(drv, chapter, s)
            finally:
                browser_pool.put(drv)

        def _produce():
            try:
                with ThreadPoolExecutor(max_workers=s.browser_workers) as url_exec:
                    future_map: dict = {}
                    for num, chapter in enumerate(selected, 1):
                        if is_downloaded(manga_dir, manga_slug, chapter.title):
                            observer.fetch_skipped(chapter.title, num)
                            continue
                        observer.fetch_started(chapter.title, num)
                        future_map[url_exec.submit(_fetch_chapter_urls, chapter)] = (chapter, num)

                    for fut in as_completed(future_map):
                        chapter, num = future_map[fut]
                        try:
                            url_queue.put((chapter, fut.result(), num))
                        except Exception as e:
                            log.exception("Error fetching '%s': %s", chapter.title, e)
                            observer.fetch_failed(chapter.title, num)
            finally:
                url_queue.put(None)

        # start the observer before the producer so total/state is set before
        # any fetch_* event is emitted from the producer thread
        observer.start(n_selected)
        producer = Thread(target=_produce, daemon=True)
        producer.start()
        try:
            with ThreadPoolExecutor(max_workers=s.chapter_workers) as executor:
                futures: dict = {}
                retry_counts: dict = {}

                while True:
                    item = url_queue.get()
                    if item is None:
                        break
                    chapter, image_urls, num = item
                    fut = executor.submit(download_chapter, manga_dir, manga_slug,
                                          chapter.title, image_urls, grayscale,
                                          observer=observer, settings=s)
                    futures[fut] = (chapter, image_urls, num)

                pending = set(futures)
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for fut in done:
                        chapter, image_urls, num = futures[fut]
                        if exc := fut.exception():
                            retries = retry_counts.get(chapter.title, 0)
                            if retries < s.max_chapter_retries:
                                retries += 1
                                retry_counts[chapter.title] = retries
                                log.warning("Retrying '%s' (attempt %d): %s",
                                            chapter.title, retries, exc)
                                observer.fetch_retry(chapter.title, num, retries,
                                                     s.max_chapter_retries)
                                new_fut = executor.submit(
                                    download_chapter, manga_dir, manga_slug,
                                    chapter.title, image_urls, grayscale,
                                    observer=observer, settings=s)
                                futures[new_fut] = (chapter, image_urls, num)
                                pending.add(new_fut)
                            else:
                                log.error("Chapter '%s' failed after %d retries: %s",
                                          chapter.title, s.max_chapter_retries, exc)
                                observer.chapter_failed(chapter.title, num)
        finally:
            observer.stop()
            producer.join()
            # keep the primary driver alive for reuse; close() disposes it
            for d in pool_drivers:
                if d is not primary:
                    d.quit()
