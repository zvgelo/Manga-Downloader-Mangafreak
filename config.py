# Static catalogs and presentation constants.
# Runtime-tunable knobs (concurrency, retries, timeouts, network, PDF size) now
# live in settings.py as the injectable `Settings` dataclass.

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

# ── Progress bars (rich UI) ─────────────────────────────────────────────────────
BAR_NAME_WIDTH      = 32    # chapter name column width (chars)
BAR_BAR_WIDTH       = 20    # rich BarColumn fill width (chars)
MAX_PROGRESS_TASKS  = 15    # max rows in download panel before oldest completed scrolls off
