import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from fpdf import FPDF
from logger import get_logger
from pathlib import Path
from PIL import Image
import os
import pymupdf
import re
import shutil
import time
import requests

log = get_logger(__name__)

_HEADERS      = {"Referer": config.MANGA_IMG_REFERER}
_MARKUP_RE    = re.compile(r'\[/?[^\]]*\]')   # strip rich markup for plain fallback


def _bar_desc(phase: str, chapter_text: str, grayscale: bool) -> str:
    """Fixed-width task description with rich colour markup."""
    suffix = " [gs]" if grayscale else ""
    name = (chapter_text + suffix)[:config.BAR_NAME_WIDTH]
    color = "cyan" if phase == "↓" else "yellow"
    return f"[bold {color}]{phase}[/bold {color}]  {name:<{config.BAR_NAME_WIDTH}}"


def chapter_number(chapter_text: str) -> str:
    m = re.search(r'Chapter\s+([\d.]+)', chapter_text, re.IGNORECASE)
    return m.group(1) if m else re.sub(r'\W+', '_', chapter_text).strip('_')


def chapter_title(chapter_text: str) -> str:
    """Filesystem-safe title slug, e.g. 'Uzumaki_Naruto'. Empty if not parseable."""
    m = re.search(r'Chapter\s+[\d.]+\s*[-–]\s*(.+)', chapter_text, re.IGNORECASE)
    if not m:
        return ""
    slug = re.sub(r'[^\w]', '_', m.group(1).strip())
    return re.sub(r'_+', '_', slug).strip('_')


def pdf_path(manga_dir, manga_slug, chapter_text):
    ch_num = chapter_number(chapter_text)
    title  = chapter_title(chapter_text)
    name   = f"{manga_slug}_Chapter_{ch_num}" + (f"_-_{title}" if title else "")
    return os.path.join(manga_dir, f"{name}.pdf"), ch_num


def _open(img_path: str, grayscale: bool) -> Image.Image:
    """Open image, optionally converting to grayscale."""
    img = Image.open(img_path)
    if grayscale and img.mode != 'L':
        return img.convert('L')
    return img


def _row_brightness(img_gray, row):
    row_img = img_gray.crop((0, row, img_gray.width, row + 1))
    return sum(img_gray.crop((0, row, img_gray.width, row + 1)).getdata()) / img_gray.width


def _find_content_height(img_gray):
    h = img_gray.height
    for row in range(h - 1, h // 3, -5):
        if _row_brightness(img_gray, row) > 8:
            return row + 1
    return h


def split_spread(img_path: str, grayscale: bool) -> list[str]:
    """
    Handles two cases:
    1. Landscape spread (ratio > 1.2): split into portrait columns.
    2. Portrait with large black bottom padding hiding a landscape composite:
       crop padding, then split columns.
    Returns list of paths (original if single page, slices otherwise).
    """
    img = Image.open(img_path)
    w, h = img.size
    ratio = w / h

    if ratio > 1.2:
        n = max(2, min(4, round(ratio / 0.7)))
        return _slice_columns(img, img_path, n, 0, h, grayscale)

    gray = img.convert('L')
    content_h = _find_content_height(gray)
    if (h - content_h) / h > 0.25 and w / content_h > 1.2:
        n = max(2, min(4, round((w / content_h) / 0.7)))
        log.warning("Composite image %s → %d panels", img_path, n)
        return _slice_columns(img, img_path, n, 0, content_h, grayscale)

    return [img_path]


def _slice_columns(img, img_path, n, y_start, y_end, grayscale):
    w = img.width
    panel_w = w // n
    slices = []
    for i in range(n):
        panel = img.crop((i * panel_w, y_start, (i + 1) * panel_w, y_end))
        if grayscale:
            panel = panel.convert('L')
        slice_path = str(img_path).replace(Path(img_path).suffix, f'_s{i}.jpg')
        panel.save(slice_path, 'JPEG', quality=95)
        slices.append(slice_path)
    return slices


def add_image_to_pdf(pdf: FPDF, img_path: str, grayscale: bool):
    """
    Add image to current PDF page fitting within A4 with correct aspect ratio.
    Passes PIL Image to fpdf2 to avoid the grayscale JPEG tiling bug.
    """
    img = _open(img_path, grayscale)
    img_w, img_h = img.size
    aspect = img_w / img_h

    pw, ph = config.PAGE_W, config.PAGE_H
    if aspect > pw / ph:
        w = pw;  h = pw / aspect;  x = 0;          y = (ph - h) / 2
    else:
        h = ph;  w = ph * aspect;  x = (pw - w) / 2;  y = 0

    # Pass PIL Image (not path) — fixes fpdf2 grayscale JPEG tiling bug
    pdf.image(img, x, y, w=w, h=h)


def _fetch_image(idx, url, chapter_dir):
    ext = url.split(".")[-1].split("?")[0]   # strip query strings
    img_path = os.path.join(chapter_dir, f"{idx + 1:03d}.{ext}")
    for attempt in range(config.MAX_RETRIES):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=60)
            resp.raise_for_status()
            with open(img_path, "wb") as f:
                f.write(resp.content)

            # Validate: minimum size
            size = os.path.getsize(img_path)
            if size < config.MIN_IMAGE_SIZE:
                raise ValueError(f"Image too small ({size} B) — likely an error response")

            # Validate: PIL can fully decode the image
            with Image.open(img_path) as img:
                img.load()

            return img_path
        except Exception as e:
            if os.path.exists(img_path):
                os.unlink(img_path)
            if attempt == config.MAX_RETRIES - 1:
                log.error("Failed after %d attempts: %s — %s", config.MAX_RETRIES, url, e)
                raise
            log.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
            time.sleep(config.RETRY_BACKOFF ** attempt)


def download_chapter(manga_dir, manga_slug, chapter_text, image_urls,
                     grayscale=False, progress=None, on_done=None):
    path, ch_num = pdf_path(manga_dir, manga_slug, chapter_text)

    def _out(markup: str) -> None:
        if progress:
            progress.console.print(markup)
        else:
            print(_MARKUP_RE.sub('', markup))

    if is_downloaded(manga_dir, manga_slug, chapter_text):
        _out(f"  [dim]Skipping {chapter_text} — already downloaded[/dim]")
        return

    chapter_dir = os.path.join(manga_dir, f"Chapter_{ch_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    task = (progress.add_task(_bar_desc("↓", chapter_text, grayscale), total=len(image_urls))
            if progress is not None else None)
    try:
        # Phase 1: download images
        with ThreadPoolExecutor(max_workers=config.IMAGE_WORKERS) as executor:
            future_to_idx = {
                executor.submit(_fetch_image, idx, url, chapter_dir): idx
                for idx, url in enumerate(image_urls)
            }
            results = {}
            for future in as_completed(future_to_idx):
                results[future_to_idx[future]] = future.result()
                if task is not None:
                    progress.advance(task)
        image_paths = [results[i] for i in range(len(image_urls))]

        # Phase 2: build PDF
        if task is not None:
            progress.update(task,
                            description=_bar_desc("→", chapter_text, grayscale),
                            total=len(image_paths),
                            completed=0)
        try:
            pdf = FPDF()
            pdf_pages = 0
            for img_path in image_paths:
                for page_path in split_spread(img_path, grayscale):
                    pdf.add_page()
                    add_image_to_pdf(pdf, page_path, grayscale)
                    pdf_pages += 1
                    if page_path != img_path:
                        os.unlink(page_path)
                if task is not None:
                    progress.advance(task)

            pdf.output(path)

            # Verify PDF: page count and file integrity
            with pymupdf.open(path) as _doc:
                saved_pages = len(_doc)
            if saved_pages != pdf_pages:
                raise RuntimeError(
                    f"PDF page mismatch: built {pdf_pages}, saved {saved_pages}")

            shutil.rmtree(chapter_dir)
            spreads = pdf_pages - len(image_paths)
            extra = f" (+{spreads} from spreads)" if spreads else ""
            _out(f"  [bold green]✓[/bold green] [green]{os.path.basename(path)}[/green]"
                 f"  [dim]({pdf_pages} pages{extra})[/dim]")
            if on_done:
                on_done()
        except Exception as e:
            log.exception("Failed to create PDF for '%s': %s", chapter_text, e)
            shutil.rmtree(chapter_dir, ignore_errors=True)
            raise
    finally:
        if task is not None:
            progress.remove_task(task)


def is_downloaded(manga_dir, manga_slug, chapter_text) -> bool:
    path, ch_num = pdf_path(manga_dir, manga_slug, chapter_text)
    if os.path.exists(path):
        return True
    # backward compat: old filename without title suffix
    old = os.path.join(manga_dir, f"{manga_slug}_Chapter_{ch_num}.pdf")
    return os.path.exists(old)
