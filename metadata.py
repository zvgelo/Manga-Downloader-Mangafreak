"""
MangaDex data access — pure, no terminal I/O.

`MangaDexClient` wraps the MangaDex REST API and returns plain dataclasses, so
it can back a CLI prompt (see metadata_prompts.py), a GUI, or a test with a
fake HTTP transport. The interactive pickers live in metadata_prompts.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from downloader import chapter_number, chapter_title
from logger import get_logger

log = get_logger(__name__)

_API     = "https://api.mangadex.org"
_CDN     = "https://uploads.mangadex.org/covers"
_TIMEOUT = 10

_LANG_PRIORITY = ["en", "pl"]


@dataclass
class MangaMetadata:
    title: str
    author: str = ""
    artist: str = ""
    year: Optional[int] = None
    description: str = ""
    status: str = ""
    manga_id: str = field(default="", repr=False)


def _clean_description(text: str) -> str:
    text = text.split('\n___')[0]                            # cut at MangaDex horizontal rule
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)   # strip markdown links
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)   # strip bold/italic
    # cut trailing "Links:" / "Source:" block (after markdown is stripped)
    text = re.split(r'\n+\s*(Links?|Sources?|Notes?)\s*:', text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.sub(r'\n{3,}', '\n\n', text)                   # collapse blank lines
    return text.strip()


def _parse(manga: dict) -> MangaMetadata:
    attrs = manga["attributes"]
    rels  = manga["relationships"]

    title  = attrs["title"].get("en") or next(iter(attrs["title"].values()), "")
    desc   = _clean_description((attrs.get("description") or {}).get("en", ""))
    author = next((r["attributes"]["name"] for r in rels
                   if r["type"] == "author" and r.get("attributes")), "")
    artist = next((r["attributes"]["name"] for r in rels
                   if r["type"] == "artist" and r.get("attributes")), "")

    return MangaMetadata(
        title=title,
        author=author,
        artist=artist,
        year=attrs.get("year"),
        description=desc,
        status=attrs.get("status") or "",
        manga_id=manga["id"],
    )


class MangaDexClient:
    """Pure MangaDex data access. Methods return dataclasses / plain dicts and
    perform no terminal I/O, so any frontend can drive them."""

    def __init__(self, http=requests, timeout: float = _TIMEOUT):
        self._http = http
        self._timeout = timeout

    def search(self, title: str, limit: int = 6) -> list[MangaMetadata]:
        """Search MangaDex by title; return parsed candidates (may be empty)."""
        r = self._http.get(
            f"{_API}/manga",
            params={"title": title, "limit": limit,
                    "includes[]": ["author", "artist", "cover_art"]},
            timeout=self._timeout,
        )
        r.raise_for_status()
        return [_parse(m) for m in r.json().get("data", [])]

    def fetch_chapter_titles(self, manga_id: str) -> dict[str, str]:
        """
        Fetch {chapter_number: best_title} for a manga.
        Prefers English; falls back through _LANG_PRIORITY, then any non-empty title.
        Paginates the feed; logs and stops on transport errors.
        """
        # chapter_num → {lang: title}
        by_chapter: dict[str, dict[str, str]] = {}
        offset = 0
        limit  = 500
        while True:
            try:
                r = self._http.get(
                    f"{_API}/manga/{manga_id}/feed",
                    params={
                        "order[chapter]": "asc",
                        "limit":          limit,
                        "offset":         offset,
                    },
                    timeout=self._timeout,
                )
                r.raise_for_status()
                results = r.json().get("data", [])
                for ch in results:
                    attrs = ch["attributes"]
                    num   = (attrs.get("chapter") or "").strip()
                    title = (attrs.get("title")   or "").strip()
                    lang  = (attrs.get("translatedLanguage") or "").strip()
                    if num and title and lang:
                        by_chapter.setdefault(num, {})[lang] = title
                if len(results) < limit:
                    break
                offset += limit
            except Exception as e:
                log.warning("MangaDex chapter feed failed (offset=%d): %s", offset, e)
                break

        titles: dict[str, str] = {}
        for num, lang_map in by_chapter.items():
            for lang in _LANG_PRIORITY:
                if lang in lang_map:
                    titles[num] = lang_map[lang]
                    break
        return titles


# ── pure enrichment helpers (no I/O) ──────────────────────────────────────────

def chapters_missing_titles(chapters: list) -> list[int]:
    """Indices of chapters that carry only a number, no subtitle."""
    return [i for i, ch in enumerate(chapters) if not chapter_title(ch.title)]


def apply_chapter_titles(chapters: list, indices: list[int],
                         title_map: dict[str, str]) -> int:
    """
    Append MangaDex titles to ch.title in-place for the given indices
    (e.g. "Chapter 5" → "Chapter 5 - Blue Vortex"). Returns the count updated.
    """
    updated = 0
    for i in indices:
        ch  = chapters[i]
        num = chapter_number(ch.title)
        if num in title_map:
            ch.title = f"{ch.title} - {title_map[num]}"
            updated += 1
    return updated
