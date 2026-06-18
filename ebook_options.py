"""
Ebook export options — pure data model and validation rules.

This module holds the resolved option bundle (`EbookOptions`) plus the
validation/parsing rules shared by the CLI prompts (ebook_prompts.py), the
to_ebook.py argparse layer, and any future GUI form. It performs no I/O, so the
same rules back a terminal prompt and a GUI widget identically.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import KINDLE_H, KINDLE_W

# ── valid ranges (shared by every frontend) ───────────────────────────────────
DPI_MIN, DPI_MAX             = 50, 300
MARGIN_MIN, MARGIN_MAX       = 0.0, 40.0
KINDLE_SIZE_MIN, KINDLE_SIZE_MAX = 200, 5000
SPLIT_CUSTOM_MIN             = 5


@dataclass
class EbookOptions:
    """Fully-resolved ebook build options handed to to_ebook.build_ebooks."""
    fmt: str
    dpi: int = 150
    grayscale: bool = False
    split: int | None = None
    fit_kindle: bool = False
    kindle_w: int = KINDLE_W
    kindle_h: int = KINDLE_H
    margin_pct: float = 0.0


# ── pure validators / parsers ─────────────────────────────────────────────────

def valid_dpi(n: int) -> bool:
    return DPI_MIN <= n <= DPI_MAX


def clamp_margin(value: float) -> float:
    return max(MARGIN_MIN, min(MARGIN_MAX, value))


def valid_custom_split(n: int, total: int) -> bool:
    return SPLIT_CUSTOM_MIN <= n <= total


def parse_kindle_size(raw: str) -> tuple[int, int] | None:
    """
    Parse a 'WxH' string (accepts x / × / , / whitespace separators) into a
    validated (width, height) pixel tuple, or None if invalid / out of range.
    """
    raw = raw.strip().lower()
    for sep in ('x', '×', ','):
        if sep in raw:
            parts = raw.split(sep, 1)
            break
    else:
        parts = raw.split()
    try:
        w, h = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None
    if KINDLE_SIZE_MIN <= w <= KINDLE_SIZE_MAX and KINDLE_SIZE_MIN <= h <= KINDLE_SIZE_MAX:
        return w, h
    return None
