# ── Network ───────────────────────────────────────────────────────────────────
MANGA_BASE_URL    = "https://ww2.mangafreak.me"
MANGA_IMG_REFERER = "https://ww2.mangafreak.me/"

# ── Concurrency ───────────────────────────────────────────────────────────────
BROWSER_WORKERS = 4    # parallel browser instances for URL collection
CHAPTER_WORKERS = 4    # parallel chapter downloads
IMAGE_WORKERS   = 5    # parallel image downloads per chapter
URL_QUEUE_SIZE  = 10   # chapters buffered between Selenium and download workers

# ── Scraper ───────────────────────────────────────────────────────────────────
PAGE_LOAD_WAIT = 3     # seconds to wait for chapter page to render

# ── Retry ─────────────────────────────────────────────────────────────────────
MAX_RETRIES         = 5   # per-image retries inside a chapter
RETRY_BACKOFF       = 2   # base seconds — sleep = RETRY_BACKOFF ** attempt
MIN_IMAGE_SIZE      = 2048  # bytes — smaller files treated as corrupt/error response
MAX_CHAPTER_RETRIES = 2   # whole-chapter retries after all-image retries exhausted

# ── PDF page size (A4, mm) ────────────────────────────────────────────────────
PAGE_W = 210
PAGE_H = 297

# ── Kindle ────────────────────────────────────────────────────────────────────
KINDLE_W              = 1072
KINDLE_H              = 1448
KINDLE_DEFAULT_MARGIN = 15.0

KINDLE_PRESETS = [
    ("Kindle basic 11th gen 2022  (6\")",      1072, 1448),
    ("Kindle Paperwhite / Oasis   (6.8\")",    1264, 1680),
    ("Kindle Scribe               (10.2\")",   1860, 2480),
]

# ── Ebook export ──────────────────────────────────────────────────────────────
SPLIT_THRESHOLD = 30

FORMAT_OPTIONS = [
    ("epub",      "EPUB only      — universal format, all readers"),
    ("mobi",      "MOBI only      — Kindle USB transfer"),
    ("epub+mobi", "EPUB + MOBI    — both files"),
    ("pdf",       "PDF only       — merged single file, no re-encoding"),
]

DPI_PRESETS = [
    (150, "High    — best quality, ~15 MB/chapter"),
    (100, "Medium  — recommended for Kindle email"),
    (72,  "Low     — smallest file, ~4 MB/chapter"),
]

# ── Progress bars ─────────────────────────────────────────────────────────────
BAR_NAME_WIDTH = 32    # chapter name column width (chars)
BAR_BAR_WIDTH  = 20    # rich BarColumn fill width (chars)
