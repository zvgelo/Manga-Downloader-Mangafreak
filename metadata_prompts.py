"""
Interactive MangaDex pickers — CLI frontend layer.

These wrap MangaDexClient with terminal prompts. All MangaDex data access lives
in metadata.py and stays free of input()/print(), so a GUI can reuse the client
and replace just this module.
"""

from __future__ import annotations

from typing import Optional

from logger import get_logger
from metadata import (MangaDexClient, MangaMetadata, apply_chapter_titles,
                      chapters_missing_titles)

log = get_logger(__name__)


def _print_candidates(results: list[MangaMetadata]) -> None:
    print()
    for i, m in enumerate(results, 1):
        print(f"  {i}. {m.title}  ({m.year or '?'}, {m.status})")
    print(f"  {len(results) + 1}. Skip")


def _prompt_choice(prompt: str, n: int) -> Optional[int]:
    """Ask the user to pick 1..n (or n+1 = Skip). Returns 0-based index or None."""
    while True:
        raw = input(f"  {prompt} (1-{n + 1}): ").strip()
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= n:
                return k - 1
            if k == n + 1:
                return None
        print(f"  Enter a number between 1 and {n + 1}.")


def pick_metadata(manga_title: str,
                  client: MangaDexClient | None = None) -> Optional[MangaMetadata]:
    """
    Search MangaDex for manga_title, let the user pick a result.
    Returns MangaMetadata or None if skipped / not found.
    """
    client = client or MangaDexClient()

    print("\nFetch metadata from MangaDex? (author, cover, description)")
    if input("  Fetch metadata? (Y/n) ").strip().lower() == 'n':
        return None

    print("  Searching MangaDex...")
    try:
        results = client.search(manga_title)
    except Exception as e:
        log.warning("MangaDex search failed: %s", e)
        print(f"  Search failed: {e}")
        return None

    if not results:
        print("  No results found.")
        return None

    _print_candidates(results)
    idx = _prompt_choice("Select", len(results))
    if idx is None:
        return None

    meta = results[idx]
    print("  Downloading metadata...")
    print(f"  Author: {meta.author}")
    if meta.artist and meta.artist != meta.author:
        print(f"  Artist: {meta.artist}")
    print(f"  Year:   {meta.year}")
    return meta


def enrich_chapter_titles(manga_title: str, chapters: list,
                          client: MangaDexClient | None = None) -> None:
    """
    For chapters without a subtitle, fetch the title from MangaDex and update
    ch.title in-place. No-ops silently if all chapters already have titles,
    the user skips, or MangaDex returns nothing.
    """
    client = client or MangaDexClient()

    missing = chapters_missing_titles(chapters)
    if not missing:
        return

    print(f"\n  {len(missing)} chapter(s) missing titles.")
    if input("  Fetch titles from MangaDex? (Y/n) ").strip().lower() == 'n':
        return

    print(f"  Searching MangaDex for '{manga_title}'...")
    try:
        results = client.search(manga_title)
    except Exception as e:
        log.warning("MangaDex search failed: %s", e)
        print(f"  Search failed: {e}")
        return

    if not results:
        print("  No MangaDex results found.")
        return

    _print_candidates(results)
    idx = _prompt_choice("Select matching manga", len(results))
    if idx is None:
        return

    print("  Fetching chapter titles...", end="", flush=True)
    title_map = client.fetch_chapter_titles(results[idx].manga_id)
    print(f" {len(title_map)} found.")

    if not title_map:
        print("  No titles available on MangaDex.")
        return

    updated = apply_chapter_titles(chapters, missing, title_map)
    print(f"  Updated {updated}/{len(missing)} chapter title(s).")
