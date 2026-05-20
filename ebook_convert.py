import shutil
import subprocess
from pathlib import Path

import pymupdf

from logger import get_logger

log = get_logger(__name__)


def convert_to_mobi(epub_path: Path, metadata=None):
    ebook_convert = shutil.which('ebook-convert')
    if not ebook_convert:
        print("\nCalibre not found — cannot convert to MOBI automatically.")
        print("  Install Calibre: https://calibre-ebook.com")
        print(f'  Or run manually: ebook-convert "{epub_path.name}" '
              f'"{epub_path.with_suffix(".mobi").name}"')
        return

    mobi_path = epub_path.with_suffix('.mobi')

    cmd = [ebook_convert, str(epub_path), str(mobi_path),
           '--output-profile', 'kindle_pw3',
           '--mobi-keep-original-images',
           '--margin-top', '0', '--margin-bottom', '0',
           '--margin-left', '0', '--margin-right', '0',
           '--chapter-mark', 'none']

    if metadata and getattr(metadata, 'author', ''):
        cmd += ['--authors', metadata.author]

    print("Converting to MOBI via Calibre...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = mobi_path.stat().st_size / 1024 / 1024
        print(f"Saved: {mobi_path} ({size_mb:.1f} MB)")
        print(f"  Transfer via USB to Kindle documents/ folder")
    else:
        log.error("ebook-convert failed:\n%s", result.stderr)
        print("MOBI conversion failed — see manga_downloader.log")
        print(f"  {result.stderr.splitlines()[-1] if result.stderr else ''}")


def merge_to_pdf(manga_dir: Path, pdfs: list, title_suffix: str = "") -> Path:
    """Merge chapter PDFs into a single PDF with bookmarks as table of contents."""
    slug = manga_dir.name + (f"_{title_suffix.replace(' ', '_')}" if title_suffix else "")
    output_path = manga_dir.parent / f"{slug}.pdf"
    manga_title = manga_dir.name.replace('_', ' ')
    if title_suffix:
        manga_title = f"{manga_title} {title_suffix}"

    print(f"\nMerging {len(pdfs)} chapters into PDF...")
    merged = pymupdf.open()
    toc = []
    current_page = 0

    manga_prefix = manga_dir.name.replace('_', ' ') + ' '
    for pdf_path in pdfs:
        chapter_name = pdf_path.stem.replace('_', ' ')
        if chapter_name.startswith(manga_prefix):
            chapter_name = chapter_name[len(manga_prefix):]
        doc = pymupdf.open(str(pdf_path))
        toc.append([1, chapter_name, current_page + 1])
        merged.insert_pdf(doc)
        current_page += len(doc)
        doc.close()

    merged.set_toc(toc)
    merged.set_metadata({'title': manga_title})
    merged.save(str(output_path))
    merged.close()

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Saved: {output_path} ({size_mb:.1f} MB)  |  {len(pdfs)} chapters in TOC")
    return output_path
