from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from downloader import chapter_number, chapter_title as _chapter_title
from logger import get_logger

log = get_logger(__name__)

_API     = "https://api.mangadex.org"
_CDN     = "https://uploads.mangadex.org/covers"
_TIMEOUT = 10


@dataclass
class MangaMetadata:
    title: str
    author: str = ""
    artist: str = ""
    year: Optional[int] = None
    description: str = ""
    manga_id: str = field(default="", repr=False)


def _search(title: str, limit: int = 6) -> list[dict]:
    r = requests.get(
        f"{_API}/manga",
        params={"title": title, "limit": limit, "includes[]": ["author", "artist", "cover_art"]},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("data", [])


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
    cover_file = next((r["attributes"]["fileName"] for r in rels
                       if r["type"] == "cover_art" and r.get("attributes")), None)

    return MangaMetadata(
        title=title,
        author=author,
        artist=artist,
        year=attrs.get("year"),
        description=desc,
        manga_id=manga["id"],
    )


_LANG_PRIORITY = ["en", "pl"]


def _fetch_all_chapter_titles(manga_id: str) -> dict[str, str]:
    """
    Fetch {chapter_number: best_title} for a manga.
    Prefers English; falls back through _LANG_PRIORITY, then any non-empty title.
    """
    # chapter_num → {lang: title}
    by_chapter: dict[str, dict[str, str]] = {}
    offset = 0
    limit  = 500
    while True:
        try:
            r = requests.get(
                f"{_API}/manga/{manga_id}/feed",
                params={
                    "order[chapter]": "asc",
                    "limit":          limit,
                    "offset":         offset,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data    = r.json()
            results = data.get("data", [])
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


def _pick_manga_id(manga_title: str, prompt: str) -> Optional[str]:
    """Search MangaDex for manga_title and return chosen manga ID, or None if skipped."""
    print(f"  Searching MangaDex for '{manga_title}'...")
    try:
        results = _search(manga_title)
    except Exception as e:
        log.warning("MangaDex search failed: %s", e)
        print(f"  Search failed: {e}")
        return None

    if not results:
        print("  No MangaDex results found.")
        return None

    print()
    for i, manga in enumerate(results, 1):
        a = manga["attributes"]
        t = a["title"].get("en") or next(iter(a["title"].values()), "")
        print(f"  {i}. {t}  ({a.get('year', '?')}, {a.get('status', '')})")
    print(f"  {len(results) + 1}. Skip")

    while True:
        raw = input(f"  {prompt} (1-{len(results) + 1}): ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(results):
                return results[n - 1]["id"]
            if n == len(results) + 1:
                return None
        print(f"  Enter a number between 1 and {len(results) + 1}.")


def enrich_chapter_titles(manga_title: str, chapters: list) -> None:
    """
    For chapters without a subtitle, fetch the title from MangaDex and update
    ch.title in-place (e.g. "Chapter 5" → "Chapter 5 - Blue Vortex").
    No-ops silently if all chapters already have titles or user skips.
    """
    missing = [i for i, ch in enumerate(chapters) if not _chapter_title(ch.title)]
    if not missing:
        return

    print(f"\n  {len(missing)} chapter(s) missing titles.")
    if input("  Fetch titles from MangaDex? (Y/n) ").strip().lower() == 'n':
        return

    manga_id = _pick_manga_id(manga_title, "Select matching manga")
    if not manga_id:
        return

    print("  Fetching chapter titles...", end="", flush=True)
    title_map = _fetch_all_chapter_titles(manga_id)
    print(f" {len(title_map)} found.")

    if not title_map:
        print("  No titles available on MangaDex.")
        return

    updated = 0
    for i in missing:
        ch  = chapters[i]
        num = chapter_number(ch.title)
        if num in title_map:
            ch.title = f"{ch.title} - {title_map[num]}"
            updated += 1

    print(f"  Updated {updated}/{len(missing)} chapter title(s).")


def pick_metadata(manga_title: str) -> Optional[MangaMetadata]:
    """
    Search MangaDex for manga_title, let user pick a result.
    Returns MangaMetadata or None if skipped / not found.
    """
    print("\nFetch metadata from MangaDex? (author, cover, description)")
    if input("  Fetch metadata? (Y/n) ").strip().lower() == 'n':
        return None

    print("  Searching MangaDex...")
    try:
        results = _search(manga_title)
    except Exception as e:
        log.warning("MangaDex search failed: %s", e)
        print(f"  Search failed: {e}")
        return None

    if not results:
        print("  No results found.")
        return None

    print()
    for i, manga in enumerate(results, 1):
        a = manga["attributes"]
        t = a["title"].get("en") or next(iter(a["title"].values()), "")
        print(f"  {i}. {t}  ({a.get('year', '?')}, {a.get('status', '')})")
    print(f"  {len(results) + 1}. Skip")

    while True:
        raw = input(f"  Select (1-{len(results) + 1}): ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(results):
                print("  Downloading metadata...")
                meta = _parse(results[n - 1])
                print(f"  Author: {meta.author}")
                if meta.artist and meta.artist != meta.author:
                    print(f"  Artist: {meta.artist}")
                print(f"  Year:   {meta.year}")
                return meta
            if n == len(results) + 1:
                return None
        print(f"  Enter a number between 1 and {len(results) + 1}.")
