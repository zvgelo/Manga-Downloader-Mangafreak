from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import requests

from logger import get_logger

log = get_logger(__name__)

_API   = "https://api.mangadex.org"
_CDN   = "https://uploads.mangadex.org/covers"
_TIMEOUT = 10


@dataclass
class MangaMetadata:
    title: str
    author: str = ""
    artist: str = ""
    year: Optional[int] = None
    description: str = ""


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
    )


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
