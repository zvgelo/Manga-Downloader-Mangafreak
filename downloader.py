from fpdf import FPDF
from logger import get_logger
from pathlib import Path
from PIL import Image
import os
import re
import shutil
import time
import requests

log = get_logger(__name__)

HEADERS = {"Referer": "https://ww2.mangafreak.me/"}

PAGE_W = 210  # mm A4 width
PAGE_H = 297  # mm A4 height


def chapter_number(chapter_text):
    m = re.search(r'Chapter\s+([\d.]+)', chapter_text, re.IGNORECASE)
    return m.group(1) if m else re.sub(r'\W+', '_', chapter_text).strip('_')


def pdf_path(manga_dir, manga_slug, chapter_text):
    ch_num = chapter_number(chapter_text)
    return os.path.join(manga_dir, f"{manga_slug}_Chapter_{ch_num}.pdf"), ch_num


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

    if aspect > PAGE_W / PAGE_H:
        w = PAGE_W;  h = PAGE_W / aspect;   x = 0;              y = (PAGE_H - h) / 2
    else:
        h = PAGE_H;  w = PAGE_H * aspect;   x = (PAGE_W - w) / 2;  y = 0

    # Pass PIL Image (not path) — fixes fpdf2 grayscale JPEG tiling bug
    pdf.image(img, x, y, w=w, h=h)


def download_chapter(manga_dir, manga_slug, chapter_text, image_urls, grayscale=False):
    path, ch_num = pdf_path(manga_dir, manga_slug, chapter_text)

    if os.path.exists(path):
        print(f"  Skipping {chapter_text} — already downloaded")
        return

    mode_label = " [grayscale]" if grayscale else ""
    print(f"  Downloading {chapter_text}{mode_label}...")

    chapter_dir = os.path.join(manga_dir, f"Chapter_{ch_num}")
    os.makedirs(chapter_dir, exist_ok=True)

    image_paths = []
    for idx, url in enumerate(image_urls):
        ext = url.split(".")[-1]
        img_path = os.path.join(chapter_dir, f"{idx + 1:03d}.{ext}")
        for attempt in range(5):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=60)
                resp.raise_for_status()
                with open(img_path, "wb") as f:
                    f.write(resp.content)
                break
            except requests.RequestException as e:
                if attempt == 4:
                    log.error("Failed to download image after 5 attempts: %s — %s", url, e)
                    raise
                log.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
                time.sleep(2 ** attempt)
        image_paths.append(img_path)

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

        pdf.output(path)
        shutil.rmtree(chapter_dir)
        spreads = pdf_pages - len(image_paths)
        extra = f" (+{spreads} from spreads)" if spreads else ""
        print(f"  Saved: {os.path.basename(path)} ({pdf_pages} pages{extra})")
    except Exception as e:
        log.exception("Failed to create PDF for '%s': %s", chapter_text, e)
        shutil.rmtree(chapter_dir, ignore_errors=True)
        raise


def is_downloaded(manga_dir, manga_slug, chapter_text):
    path, _ = pdf_path(manga_dir, manga_slug, chapter_text)
    return os.path.exists(path)
