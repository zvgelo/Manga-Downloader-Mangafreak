"""
Integration test for download_chapter exercising the full settings + observer
plumbing: a fake network returns a real (small) JPEG, the PDF is built and
verified, and a recording observer captures the emitted events.
"""

import io

import pytest
from PIL import Image

import downloader
from events import DownloadObserver
from settings import Settings


class RecordingObserver(DownloadObserver):
    def __init__(self):
        self.events = []

    def download_started(self, key, total_images):
        self.events.append(("download_started", key, total_images))

    def image_downloaded(self, key):
        self.events.append(("image_downloaded", key))

    def build_started(self, key, total_pages):
        self.events.append(("build_started", key, total_pages))

    def page_built(self, key):
        self.events.append(("page_built", key))

    def chapter_saved(self, key, filename, pages, spreads):
        self.events.append(("chapter_saved", key, filename, pages, spreads))

    def message(self, text):
        self.events.append(("message", text))


@pytest.fixture
def fake_jpeg(monkeypatch):
    buf = io.BytesIO()
    Image.new("RGB", (100, 150), "white").save(buf, "JPEG")
    data = buf.getvalue()

    class FakeResp:
        content = data
        def raise_for_status(self):
            pass

    monkeypatch.setattr(downloader.requests, "get", lambda *a, **k: FakeResp())
    return data


# small min_image_size so the tiny test JPEG passes validation
SETTINGS = Settings(min_image_size=10, max_retries=1)


def test_builds_pdf_and_emits_events(tmp_path, fake_jpeg):
    obs = RecordingObserver()
    downloader.download_chapter(
        str(tmp_path), "Test", "Chapter 1",
        ["http://x/1.jpg", "http://x/2.jpg"],
        grayscale=False, observer=obs, settings=SETTINGS,
    )

    out = tmp_path / "Test_Chapter_1.pdf"
    assert out.exists()

    kinds = [e[0] for e in obs.events]
    assert kinds[0] == "download_started"
    assert kinds.count("image_downloaded") == 2
    assert "build_started" in kinds
    assert kinds[-1] == "chapter_saved"
    saved = obs.events[-1]
    assert saved[2] == "Test_Chapter_1.pdf"   # filename
    assert saved[3] == 2                        # pages


def test_chapter_dir_cleaned_up(tmp_path, fake_jpeg):
    downloader.download_chapter(
        str(tmp_path), "Test", "Chapter 1", ["http://x/1.jpg"],
        observer=None, settings=SETTINGS,
    )
    # the per-chapter scratch dir is removed after a successful build
    assert not (tmp_path / "Chapter_1").exists()


def test_chapter_dir_cleaned_up_on_download_failure(tmp_path, monkeypatch):
    # a failure during the image-download phase must still remove the scratch dir
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(downloader, "_fetch_image", boom)

    with pytest.raises(RuntimeError):
        downloader.download_chapter(
            str(tmp_path), "Test", "Chapter 1", ["http://x/1.jpg"],
            settings=SETTINGS,
        )

    assert not (tmp_path / "Chapter_1").exists()
    assert not (tmp_path / "Test_Chapter_1.pdf").exists()


def test_empty_urls_raises(tmp_path):
    with pytest.raises(ValueError):
        downloader.download_chapter(str(tmp_path), "Test", "Chapter 1", [],
                                    settings=SETTINGS)


def test_already_downloaded_emits_message_and_skips(tmp_path, fake_jpeg):
    # first build creates the PDF
    downloader.download_chapter(str(tmp_path), "Test", "Chapter 1",
                                ["http://x/1.jpg"], settings=SETTINGS)
    # second call should detect it and skip via a message event
    obs = RecordingObserver()
    downloader.download_chapter(str(tmp_path), "Test", "Chapter 1",
                                ["http://x/1.jpg"], observer=obs, settings=SETTINGS)
    assert obs.events == [("message", "Skipping Chapter 1 — already downloaded")]
