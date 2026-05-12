import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

from browser import create_driver
from logger import get_logger
from scraper import search_manga, get_manga_title, get_chapters, get_chapter_images
from downloader import download_chapter
from to_ebook import (build_ebooks, convert_to_azw3,
                      pick_dpi, pick_format, pick_grayscale, pick_split,
                      SPLIT_THRESHOLD)

log = get_logger(__name__)


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
            raise ValueError(f"Cannot parse '{part}' — expected a number or a range like 1-3")

    if not indices:
        raise ValueError("No chapters selected")

    return sorted(indices)


driver = create_driver(headless=True)
base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manga")
os.makedirs(base_dir, exist_ok=True)

# --- search ---
header()
query = input("Search manga: ")

header(f"Searching: {query}")
print("  Loading...")
results = search_manga(driver, query)

if not results:
    print("  No results found.")
    driver.quit()
    sys.exit(1)

# --- pick manga ---
header(f"Results for: {query}")
for i, r in enumerate(results, 1):
    print(f"  {i}. {r.text.splitlines()[0]}")
    for line in r.text.splitlines()[1:]:
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

manga_title = get_manga_title(results[index])
manga_slug  = re.sub(r'[^\w\s-]', '', manga_title).strip().replace(' ', '_')
manga_dir   = os.path.join(base_dir, manga_slug)
os.makedirs(manga_dir, exist_ok=True)

# --- list chapters ---
header(f"{manga_title}  |  Loading chapters...")
print("  Please wait...")
chapters = get_chapters(driver, results[index])
total = len(chapters)

header(f"{manga_title}  |  {total} chapters")
for idx, ch in enumerate(chapters, 1):
    print(f"  {idx:>3}.  {ch['title']}")
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

selected = [chapters[i] for i in indices]

# --- grayscale option ---
grayscale = pick_grayscale()

# --- download ---
header(f"{manga_title}  |  Downloading {len(selected)} chapter(s)")
for num, chapter in enumerate(selected, 1):
    print(f"  [{num}/{len(selected)}] {chapter['title']}")
    try:
        image_urls = get_chapter_images(driver, chapter)
        download_chapter(manga_dir, manga_slug, chapter["title"], image_urls,
                         grayscale=grayscale)
    except Exception as e:
        log.exception("Error processing chapter '%s': %s", chapter["title"], e)
        print(f"  Error: {chapter['title']} failed — skipping (see manga_downloader.log)")

driver.quit()
print()
print("  Done.")

# --- ebook ---
answer = input("\nCreate ebook from downloaded chapters? (y/N) ").strip().lower()
if answer == 'y':
    fmt = pick_format()
    dpi = pick_dpi(default=100)
    gs  = pick_grayscale()
    total_pdfs = len(list(Path(manga_dir).glob('*.pdf')))
    split = pick_split(total_pdfs) if total_pdfs > SPLIT_THRESHOLD else None
    build_ebooks(Path(manga_dir), dpi=dpi, grayscale=gs, fmt=fmt, split=split)
    print("\nDone.")
