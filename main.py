import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

from config import KINDLE_H, KINDLE_W, SPLIT_THRESHOLD
from ebook_prompts import (pick_dpi, pick_format, pick_grayscale,
                           pick_kindle_settings, pick_split)
from metadata import enrich_chapter_titles
from service import DownloadService
from settings import Settings
from to_ebook import build_ebooks
from ui import RichDownloadObserver

CHAPTER_HELP = """
  Format examples (chapters are 1-based):
    all         → all chapters
    5           → chapter 5 only
    1-3         → chapters 1, 2, 3
    1,3,7       → chapters 1, 3 and 7
    1-3,7,10    → chapters 1, 2, 3, 7 and 10
"""

SINGLE_RE = re.compile(r"^\d+$")
RANGE_RE  = re.compile(r"^(\d+)-(\d+)$")


def clear():
    print("\033[2J\033[H", end="")


def header(title=""):
    clear()
    print("=" * 50)
    print("  Manga Downloader")
    if title:
        print(f"  {title}")
    print("=" * 50)
    print()


def parse_chapter_choice(choice, total):
    choice = choice.strip().lower()
    if choice == "all":
        return list(range(total))

    indices = set()
    for part in choice.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"Empty segment in '{choice}'")

        range_match  = RANGE_RE.match(part)
        single_match = SINGLE_RE.match(part)

        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start > end:
                raise ValueError(f"Range {start}-{end}: start must be ≤ end")
            if start < 1 or end > total:
                raise ValueError(f"Range {start}-{end} out of bounds (available: 1-{total})")
            indices.update(range(start - 1, end))
        elif single_match:
            n = int(part)
            if n < 1 or n > total:
                raise ValueError(f"Chapter {n} out of bounds (available: 1-{total})")
            indices.add(n - 1)
        else:
            raise ValueError(f"Cannot parse '{part}' — expected a number or range like 1-3")

    if not indices:
        raise ValueError("No chapters selected")

    return sorted(indices)


def main():
    service  = DownloadService(Settings())
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manga")
    os.makedirs(base_dir, exist_ok=True)

    try:
        # --- search ---
        header()
        query = input("Search manga: ")

        header(f"Searching: {query}")
        print("  Loading...")
        results = service.search(query)

        if not results:
            print("  No results found.")
            sys.exit(1)

        # --- pick manga ---
        header(f"Results for: {query}")
        for i, r in enumerate(results, 1):
            lines = r.menu_lines
            print(f"  {i}. {lines[0]}")
            for line in lines[1:]:
                print(f"     {line}")
            print()

        while True:
            raw = input(f"Select manga (1-{len(results)}): ").strip()
            try:
                index = int(raw) - 1
                if index < 0 or index >= len(results):
                    print(f"  Out of range — enter a number between 1 and {len(results)}.")
                else:
                    break
            except ValueError:
                print(f"  Invalid input '{raw}' — enter a single number, e.g. 1")

        manga_title = results[index].title
        manga_slug  = re.sub(r'[^\w\s-]', '', manga_title).strip().replace(' ', '_')
        manga_dir   = os.path.join(base_dir, manga_slug)
        os.makedirs(manga_dir, exist_ok=True)

        # --- list chapters ---
        header(f"{manga_title}  |  Loading chapters...")
        print("  Please wait...")
        chapters = service.list_chapters(results[index].series_url)

        enrich_chapter_titles(manga_title, chapters)

        total = len(chapters)

        header(f"{manga_title}  |  {total} chapters")
        for idx, ch in enumerate(chapters, 1):
            print(f"  {idx:>3}.  {ch.title}")
        print()

        # --- pick chapters ---
        print(CHAPTER_HELP)
        while True:
            choice = input("Which chapters to download? ").strip()
            try:
                indices = parse_chapter_choice(choice, total)
                break
            except ValueError as e:
                print(f"\n  Error: {e}")
                print(CHAPTER_HELP)

        selected   = [chapters[i] for i in indices]
        grayscale  = pick_grayscale()
        n_selected = len(selected)

        # --- download ---
        header(f"{manga_title}  |  Downloading {n_selected} chapter(s)")
        observer = RichDownloadObserver(grayscale=grayscale)
        service.download(selected, manga_dir, manga_slug, grayscale, observer)
    finally:
        service.close()

    print()
    print("  Done.")

    # --- ebook ---
    answer = input("\nCreate ebook from downloaded chapters? (y/N) ").strip().lower()
    if answer == 'y':
        fmt = pick_format()
        if fmt == 'pdf':
            dpi, gs = 100, False
            fk, kw, kh, margin = False, KINDLE_W, KINDLE_H, 0.0
        else:
            dpi = pick_dpi(default=100)
            gs  = pick_grayscale()
            fk, kw, kh, margin = pick_kindle_settings()
        total_pdfs = len(list(Path(manga_dir).glob('*.pdf')))
        split = pick_split(total_pdfs) if total_pdfs > SPLIT_THRESHOLD else None
        build_ebooks(Path(manga_dir), dpi=dpi, grayscale=gs, fmt=fmt, split=split,
                     fit_kindle=fk, kindle_w=kw, kindle_h=kh, margin_pct=margin)
        print("\nDone.")


if __name__ == '__main__':
    main()
