"""
Runtime settings — a single, injectable configuration object.

Unlike the module-level constants in `config.py` (which are static catalogs:
Kindle presets, format/DPI option lists, rich-UI widths), `Settings` holds the
knobs a frontend may want to tune per run (concurrency, retries, timeouts).
A GUI can build a `Settings(...)` from form fields and hand it to the core
without touching any module globals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # ── Network ──────────────────────────────────────────────────────────────
    manga_base_url: str = "https://ww2.mangafreak.me"
    manga_img_referer: str = "https://ww2.mangafreak.me/"

    # ── Concurrency ──────────────────────────────────────────────────────────
    browser_workers: int = 4    # parallel browser instances for URL collection
    chapter_workers: int = 4    # parallel chapter downloads
    image_workers: int = 5      # parallel image downloads per chapter
    url_queue_size: int = 10    # chapters buffered between Selenium and downloaders

    # ── Scraper ──────────────────────────────────────────────────────────────
    page_timeout: float = 30    # max seconds to wait for a page element

    # ── Retry ────────────────────────────────────────────────────────────────
    max_retries: int = 5         # per-image retries inside a chapter
    retry_backoff: float = 2     # base seconds — sleep = retry_backoff ** attempt
    min_image_size: int = 2048   # bytes — smaller files treated as corrupt
    max_chapter_retries: int = 2 # whole-chapter retries after image retries exhausted

    # ── PDF page size (A4, mm) ───────────────────────────────────────────────
    page_w: float = 210
    page_h: float = 297


DEFAULT_SETTINGS = Settings()
