import sys
from pathlib import Path

from config import (
    KINDLE_W, KINDLE_H, KINDLE_DEFAULT_MARGIN, KINDLE_PRESETS,
    FORMAT_OPTIONS, SPLIT_THRESHOLD, DPI_PRESETS,
)
from ebook_options import (
    DPI_MAX, DPI_MIN, EbookOptions, clamp_margin, parse_kindle_size,
    valid_custom_split, valid_dpi,
)


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
            if valid_custom_split(n, total):
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
    print(f"  Or enter a custom value ({DPI_MIN}-{DPI_MAX})")
    while True:
        raw = input("Select quality: ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(DPI_PRESETS):
                return DPI_PRESETS[n - 1][0]
            if valid_dpi(n):
                return n
        print(f"  Enter 1-{len(DPI_PRESETS)} or a number between {DPI_MIN} and {DPI_MAX}.")


def _pick_custom_kindle_size() -> tuple[int, int]:
    while True:
        raw = input("  Enter width×height in pixels (e.g. 1072x1448): ")
        size = parse_kindle_size(raw)
        if size:
            return size
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
        margin = clamp_margin(float(raw)) if raw else KINDLE_DEFAULT_MARGIN
    except ValueError:
        margin = KINDLE_DEFAULT_MARGIN

    return True, kw, kh, margin


def prompt_split_if_large(total_pdfs: int) -> int | None:
    """Offer volume splitting only when the chapter count is large."""
    return pick_split(total_pdfs) if total_pdfs > SPLIT_THRESHOLD else None


def prompt_ebook_options(total_pdfs: int, default_dpi: int = 150) -> EbookOptions:
    """
    Fully-interactive assembly of EbookOptions (format → quality/Kindle → split).

    This is the single place the interactive build rules live, so callers don't
    re-implement the per-format defaults. Metadata is fetched separately by the
    caller (it depends on the chosen format).
    """
    fmt = pick_format()
    if fmt == 'pdf':
        return EbookOptions(fmt=fmt, dpi=default_dpi, grayscale=False,
                            split=prompt_split_if_large(total_pdfs))

    dpi = pick_dpi(default=default_dpi)
    gs  = pick_grayscale()
    fk, kw, kh, margin = pick_kindle_settings()
    return EbookOptions(fmt=fmt, dpi=dpi, grayscale=gs,
                        fit_kindle=fk, kindle_w=kw, kindle_h=kh, margin_pct=margin,
                        split=prompt_split_if_large(total_pdfs))
