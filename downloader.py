from fpdf import FPDF
from logger import get_logger
import os
import re
import shutil
import time
import requests

log = get_logger(__name__)

HEADERS = {"Referer": "https://ww2.mangafreak.me/"}


def chapter_number(chapter_text):
    m = re.search(r'Chapter\s+([\d.]+)', chapter_text, re.IGNORECASE)
    return m.group(1) if m else re.sub(r'\W+', '_', chapter_text).strip('_')


def pdf_path(manga_dir, manga_slug, chapter_text):
    ch_num = chapter_number(chapter_text)
    return os.path.join(manga_dir, f"{manga_slug}_Chapter_{ch_num}.pdf"), ch_num


def download_chapter(manga_dir, manga_slug, chapter_text, image_urls):
    path, ch_num = pdf_path(manga_dir, manga_slug, chapter_text)

    if os.path.exists(path):
        print(f"  Skipping {chapter_text} — already downloaded")
        return

    print(f"  Downloading {chapter_text}...")

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
        for img_path in image_paths:
            pdf.add_page()
            pdf.image(img_path, 0, 0, w=210, h=297)
        pdf.output(path)
        shutil.rmtree(chapter_dir)
        print(f"  Saved: {os.path.basename(path)} ({len(image_paths)} pages)")
    except Exception as e:
        log.exception("Failed to create PDF for '%s': %s", chapter_text, e)
        shutil.rmtree(chapter_dir, ignore_errors=True)
        raise


def is_downloaded(manga_dir, manga_slug, chapter_text):
    path, _ = pdf_path(manga_dir, manga_slug, chapter_text)
    return os.path.exists(path)
