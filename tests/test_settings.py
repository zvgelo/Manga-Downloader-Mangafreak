import dataclasses

import pytest

from settings import DEFAULT_SETTINGS, Settings


def test_defaults_present():
    s = Settings()
    assert s.browser_workers == 4
    assert s.chapter_workers == 4
    assert s.image_workers == 5
    assert s.max_retries == 5
    assert s.page_w == 210 and s.page_h == 297
    assert s.manga_base_url.startswith("https://")


def test_default_singleton_matches_fresh_instance():
    assert DEFAULT_SETTINGS == Settings()


def test_is_frozen():
    s = Settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.image_workers = 99


def test_override_via_constructor():
    s = Settings(image_workers=10, min_image_size=1)
    assert s.image_workers == 10
    assert s.min_image_size == 1
    # untouched fields keep defaults
    assert s.chapter_workers == 4


def test_replace_produces_modified_copy():
    base = Settings()
    tuned = dataclasses.replace(base, max_chapter_retries=5)
    assert tuned.max_chapter_retries == 5
    assert base.max_chapter_retries == 2  # original untouched
