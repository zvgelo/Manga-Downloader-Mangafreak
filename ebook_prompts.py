import sys
from pathlib import Path


KINDLE_W = 1072
KINDLE_H = 1448

KINDLE_PRESETS = [
    ("Kindle basic 11th gen 2022  (6\")",        1072, 1448),
    ("Kindle Paperwhite / Oasis   (6.8\")",       1264, 1680),
    ("Kindle Scribe               (10.2\")",      1860, 2480),
]
KINDLE_DEFAULT_MARGIN = 15.0

FORMAT_OPTIONS = [
    ("epub",      "EPUB only      — universal format, all readers"),
    ("mobi",      "MOBI only      — Kindle USB transfer"),
    ("epub+mobi", "EPUB + MOBI    — both files"),
    ("pdf",       "PDF only       — merged single file, no re-encoding"),
]

SPLIT_THRESHOLD = 30

DPI_PRESETS = [
    (150, "High    — best quality, ~15 MB/chapter"),
    (100, "Medium  — recommended for Kindle email"),
    (72,  "Low     — smallest file, ~4 MB/chapter"),
]


def pick_manga_folder() -> Path:
    manga_base = Path(__file__).parent / 'manga'
    folders = sorted([f for f in manga_base.iterdir() if f.is_dir()], key=lambda p: p.name)
    if not folders:
        print("No manga folders found in manga/")
        sys.exit(1)
    print("Available manga:")
    for i, folder in enumerate(folders, 1):
        pdfs = list(folder.glob('*.pdf'))
        print(f"  {i}. {folder.name.replace('_', ' ')} ({len(pdfs)} chapters)")
    while True:
        raw = input(f"\nSelect manga (1-{len(folders)}): ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(folders):
                return folders[idx]
            print(f"  Out of range — enter a number between 1 and {len(folders)}.")
        except ValueError:
            print("  Invalid input — enter a number.")


def pick_format() -> str:
    print("\nOutput format:")
    for i, (key, label) in enumerate(FORMAT_OPTIONS, 1):
        print(f"  {i}. {label}")
    while True:
        raw = input(f"Select format (1-{len(FORMAT_OPTIONS)}): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(FORMAT_OPTIONS):
            return FORMAT_OPTIONS[int(raw) - 1][0]
        print(f"  Enter a number between 1 and {len(FORMAT_OPTIONS)}.")


def pick_split(total: int) -> int | None:
    print(f"\nSplit into volumes?")
    print(f"  {total} chapters detected. Large ebooks can be slow on Kindle.")
    raw = input("  Split into volumes? (y/N) ").strip().lower()
    if raw != 'y':
        return None
    presets = [10, 20, 30]
    print("\n  Chapters per volume:")
    for i, n in enumerate(presets, 1):
        vols = -(-total // n)
        print(f"    {i}. {n} chapters  ({vols} volumes)")
    print(f"    Or enter a custom number (5-{total})")
    while True:
        raw = input("  Chapters per volume: ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(presets):
                return presets[n - 1]
            if 5 <= n <= total:
                return n
        print(f"  Enter 1-{len(presets)} or a number between 5 and {total}.")


def pick_grayscale() -> bool:
    print("\nGrayscale mode?")
    print("  Reduces file size ~40%, ideal for B&W manga and Kindle.")
    raw = input("  Use grayscale? (Y/n) ").strip().lower()
    return raw != 'n'


def pick_dpi(default: int = None) -> int:
    print("\nImage quality (DPI):")
    for i, (dpi, label) in enumerate(DPI_PRESETS, 1):
        marker = " *" if dpi == default else ""
        print(f"  {i}. {label}  ({dpi} dpi){marker}")
    print("  Or enter a custom value (50-300)")
    while True:
        raw = input("Select quality: ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(DPI_PRESETS):
                return DPI_PRESETS[n - 1][0]
            if 50 <= n <= 300:
                return n
        print(f"  Enter 1-{len(DPI_PRESETS)} or a number between 50 and 300.")


def _pick_custom_kindle_size() -> tuple[int, int]:
    while True:
        raw = input("  Enter width×height in pixels (e.g. 1072x1448): ").strip().lower()
        for sep in ('x', '×', ','):
            if sep in raw:
                parts = raw.split(sep, 1)
                break
        else:
            parts = raw.split()
        try:
            w, h = int(parts[0]), int(parts[1])
            if 200 <= w <= 5000 and 200 <= h <= 5000:
                return w, h
        except (ValueError, IndexError):
            pass
        print("  Invalid — enter e.g. 1072x1448")


def pick_kindle_settings() -> tuple[bool, int, int, float]:
    """Returns (fit_kindle, kindle_w, kindle_h, margin_pct)."""
    print("\nFit to Kindle screen?")
    print("  Resizes pages to prevent blank overflow pages. Recommended for MOBI.")
    raw = input("  Fit to Kindle? (Y/n) ").strip().lower()
    if raw == 'n':
        return False, KINDLE_W, KINDLE_H, 0.0

    print("\nKindle model:")
    for i, (name, w, h) in enumerate(KINDLE_PRESETS, 1):
        print(f"  {i}. {name}  ({w}×{h})")
    print(f"  {len(KINDLE_PRESETS) + 1}. Custom size")
    while True:
        raw = input(f"  Select model (1-{len(KINDLE_PRESETS) + 1}): ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(KINDLE_PRESETS):
                _, kw, kh = KINDLE_PRESETS[n - 1]
                break
            if n == len(KINDLE_PRESETS) + 1:
                kw, kh = _pick_custom_kindle_size()
                break
        print(f"  Enter a number between 1 and {len(KINDLE_PRESETS) + 1}.")

    print(f"\nMargin (prevents blank continuation pages on Kindle):")
    print(f"  Default: {KINDLE_DEFAULT_MARGIN:.0f}%")
    raw = input(f"  Margin % (Enter for {KINDLE_DEFAULT_MARGIN:.0f}%): ").strip()
    try:
        margin = float(raw) if raw else KINDLE_DEFAULT_MARGIN
        margin = max(0.0, min(40.0, margin))
    except ValueError:
        margin = KINDLE_DEFAULT_MARGIN

    return True, kw, kh, margin
