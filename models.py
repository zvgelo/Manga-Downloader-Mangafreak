"""
Domain models — plain, serializable data objects shared across the core.

These intentionally hold no Selenium WebElements: every result is materialized
to a dataclass so it can be passed between threads, cached, serialized to JSON,
or handed to a future GUI/web backend without depending on a live browser
session still sitting on a particular page.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """One manga card from a search results page."""
    title: str                                  # h3 — used for slug & metadata lookup
    series_url: str                             # link to the series page (chapter list)
    display_lines: list[str] = field(default_factory=list)  # full card text, for menus
    cover_url: str = ""

    @property
    def menu_lines(self) -> list[str]:
        """Lines to render in a selection menu (falls back to the title)."""
        return self.display_lines or [self.title]


@dataclass
class Chapter:
    """A single chapter. `title` is mutable — enrich_chapter_titles updates it."""
    title: str
    url: str
