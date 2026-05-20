import config
import os
import re
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from pathlib import Path
from queue import Queue
from threading import Thread

from rich.live import Live

sys.stdout.reconfigure(line_buffering=True)

from browser import create_driver
from downloader import download_chapter, is_downloaded
from logger import get_logger
from scraper import search_manga, get_manga_title, get_chapters, get_chapter_images
from ebook_prompts import (pick_dpi, pick_kindle_settings, pick_format,
                           pick_grayscale, pick_split)
from to_ebook import build_ebooks
from config import SPLIT_THRESHOLD, KINDLE_W, KINDLE_H
from ui import build_download_ui

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
            raise ValueError(f"Cannot parse '{part}' — expected a number or range like 1-3")

    if not indices:
        raise ValueError("No chapters selected")

    return sorted(indices)


def main():
    driver  = create_driver(headless=True)
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

    selected   = [chapters[i] for i in indices]
    grayscale  = pick_grayscale()
    n_selected = len(selected)

    # --- download ---
    header(f"{manga_title}  |  Downloading {n_selected} chapter(s)")

    console, fetch_log, dl_prog, layout = build_download_ui()

    # browser pool for parallel URL collection
    all_drivers  = [driver] + [create_driver(headless=True)
                                for _ in range(config.BROWSER_WORKERS - 1)]
    browser_pool: Queue = Queue()
    for _d in all_drivers:
        browser_pool.put(_d)

    url_queue: Queue = Queue(maxsize=config.URL_QUEUE_SIZE)

    def _fetch_chapter_urls(chapter: dict) -> list[str]:
        _drv = browser_pool.get()
        try:
            return get_chapter_images(_drv, chapter)
        finally:
            browser_pool.put(_drv)

    def _produce():
        try:
            with ThreadPoolExecutor(max_workers=config.BROWSER_WORKERS) as url_exec:
                future_map: dict = {}
                for num, chapter in enumerate(selected, 1):
                    title = chapter["title"]
                    if is_downloaded(manga_dir, manga_slug, title):
                        fetch_log.set(title,
                            f"  [dim][{num}/{n_selected}] ⊘  {title}[/dim]")
                        continue
                    fetch_log.set(title,
                        f"  [{num}/{n_selected}] [cyan]↓[/cyan]  {title}")
                    future_map[url_exec.submit(_fetch_chapter_urls, chapter)] = (chapter, num)

                for fut in as_completed(future_map):
                    chapter, num = future_map[fut]
                    try:
                        url_queue.put((chapter, fut.result(), num))
                    except Exception as e:
                        log.exception("Error fetching '%s': %s", chapter["title"], e)
                        fetch_log.set(chapter["title"],
                            f"  [red][{num}/{n_selected}] ✗  {chapter['title']}[/red]")
        finally:
            url_queue.put(None)

    def _make_done(title: str, n: int):
        def _cb():
            fetch_log.set(title,
                f"  [{n}/{n_selected}] [bold green]✓[/bold green]  {title}")
        return _cb

    producer = Thread(target=_produce, daemon=True)
    producer.start()

    with Live(layout, console=console, refresh_per_second=8, transient=False):
        with ThreadPoolExecutor(max_workers=config.CHAPTER_WORKERS) as executor:
            futures: dict = {}
            retry_counts: dict = {}

            while True:
                item = url_queue.get()
                if item is None:
                    break
                chapter, image_urls, num = item
                fut = executor.submit(download_chapter, manga_dir, manga_slug,
                                      chapter["title"], image_urls, grayscale,
                                      progress=dl_prog,
                                      on_done=_make_done(chapter["title"], num))
                futures[fut] = (chapter, image_urls, num)

            pending = set(futures)
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    chapter, image_urls, num = futures[fut]
                    if exc := fut.exception():
                        retries = retry_counts.get(chapter["title"], 0)
                        if retries < config.MAX_CHAPTER_RETRIES:
                            retries += 1
                            retry_counts[chapter["title"]] = retries
                            log.warning("Retrying '%s' (attempt %d): %s",
                                        chapter["title"], retries, exc)
                            fetch_log.set(chapter["title"],
                                f"  [{num}/{n_selected}]"
                                f" [yellow]↻ retry {retries}/{config.MAX_CHAPTER_RETRIES}[/yellow]"
                                f"  {chapter['title']}")
                            new_fut = executor.submit(
                                download_chapter, manga_dir, manga_slug,
                                chapter["title"], image_urls, grayscale,
                                progress=dl_prog,
                                on_done=_make_done(chapter["title"], num))
                            futures[new_fut] = (chapter, image_urls, num)
                            pending.add(new_fut)
                        else:
                            log.error("Chapter '%s' failed after %d retries: %s",
                                      chapter["title"], config.MAX_CHAPTER_RETRIES, exc)
                            fetch_log.set(chapter["title"],
                                f"  [{num}/{n_selected}] [bold red]✗[/bold red]"
                                f"  {chapter['title']}")
                            dl_prog.console.print(
                                f"  [red]✗ {chapter['title']} failed permanently[/red]"
                                f"  [dim](see manga_downloader.log)[/dim]")

    producer.join()
    for _d in all_drivers:
        _d.quit()

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
