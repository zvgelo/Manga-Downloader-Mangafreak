"""
Smoke tests for scraper.py using a fake Selenium driver — no real browser.
WebDriverWait is replaced with an immediate variant so the explicit waits run
deterministically without polling delays.
"""

import pytest
from selenium.common.exceptions import TimeoutException

import scraper
from models import Chapter
from settings import Settings

SETTINGS = Settings(page_timeout=1)


class ImmediateWait:
    """Stand-in for WebDriverWait: evaluates the condition once."""

    def __init__(self, driver, timeout):
        self._driver = driver

    def until(self, method):
        result = method(self._driver)
        if not result:
            raise TimeoutException()
        return result


class FakeImg:
    def __init__(self, src):
        self._src = src

    def get_attribute(self, name):
        return self._src if name == "src" else None


class FakeDriver:
    def __init__(self, images=None, rows=None):
        self._images = images or []
        self._rows = rows or []
        self.url = None

    def get(self, url):
        self.url = url

    def find_elements(self, by, value):
        return list(self._images)

    def find_element(self, by, value):
        return object()  # truthy presence for get_chapters' wait

    def execute_script(self, script):
        return list(self._rows)


@pytest.fixture(autouse=True)
def _immediate_wait(monkeypatch):
    monkeypatch.setattr(scraper, "WebDriverWait", ImmediateWait)


def test_get_chapter_images_dedupes_and_preserves_order():
    imgs = [FakeImg("https://ww2.mangafreak.me/mangas/a/1.jpg"),
            FakeImg("https://ww2.mangafreak.me/mangas/a/2.jpg"),
            FakeImg("https://ww2.mangafreak.me/mangas/a/1.jpg")]  # duplicate
    driver = FakeDriver(images=imgs)

    urls = scraper.get_chapter_images(driver, Chapter("Chapter 1", "u"), SETTINGS)

    assert urls == ["https://ww2.mangafreak.me/mangas/a/1.jpg",
                    "https://ww2.mangafreak.me/mangas/a/2.jpg"]
    assert driver.url == "u"


def test_get_chapter_images_returns_empty_when_none_render():
    driver = FakeDriver(images=[])
    assert scraper.get_chapter_images(driver, Chapter("Chapter 1", "u"), SETTINGS) == []


def test_get_chapters_builds_models_from_script_rows():
    rows = [{"title": "Chapter 1", "url": "c1"},
            {"title": "Chapter 2", "url": "c2"}]
    driver = FakeDriver(rows=rows)

    chapters = scraper.get_chapters(driver, "series-url", SETTINGS)

    assert [(c.title, c.url) for c in chapters] == [("Chapter 1", "c1"),
                                                    ("Chapter 2", "c2")]
    assert driver.url == "series-url"
