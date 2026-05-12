"""
Convert downloaded manga chapters (PDFs) to a single EPUB or AZW3 ebook.

Usage:
    python to_ebook.py                               # interactive folder picker
    python to_ebook.py manga/Boruto_Two_Blue_Vortex
    python to_ebook.py manga/Boruto_Two_Blue_Vortex --dpi 100

DPI guide:
    150  high quality, ~15-20 MB/chapter  (default)
    120  good quality, ~10-12 MB/chapter
    100  decent,       ~7-8 MB/chapter    (recommended for Kindle email ≤ 50 MB)
     72  low,          ~4-5 MB/chapter
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

import pymupdf

from logger import get_logger

log = get_logger(__name__)


def natural_sort_key(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text))]


from contextlib import contextmanager

@contextmanager
def _silence_mupdf():
    """Suppress MuPDF C-level output noise (e.g. ICC profile warnings)."""
    import os
    devnull = os.open(os.devnull, os.O_WRONLY)
    old1, old2 = os.dup(1), os.dup(2)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old1, 1); os.close(old1)
        os.dup2(old2, 2); os.close(old2)


def extract_chapter_images(pdf_path: Path, images_dir: Path, prefix: str, dpi: int,
                           grayscale: bool = False):
    """Extract each PDF page as JPEG. Returns list of filenames."""
    from PIL import Image as PILImage
    from io import BytesIO

    with _silence_mupdf():
        doc = pymupdf.open(str(pdf_path))
    filenames = []
    for i, page in enumerate(doc):
        with _silence_mupdf():
            pix = page.get_pixmap(dpi=dpi)
        img_path = str(images_dir / f"{prefix}_{i + 1:03d}.jpg")
        if grayscale:
            img = PILImage.open(BytesIO(pix.tobytes("jpeg"))).convert('L')
            img.save(img_path, 'JPEG', quality=95)
        else:
            pix.save(img_path)
        filenames.append(f"{prefix}_{i + 1:03d}.jpg")
    doc.close()
    return filenames


# ── EPUB building blocks ────────────────────────────────────────────────────

CONTAINER_XML = """\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def chapter_xhtml(chapter_name: str, img_filenames: list) -> str:
    pages = "\n".join(
        f'  <div class="p"><img src="../images/{fn}" alt="{chapter_name}"/></div>'
        for fn in img_filenames
    )
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8"/>
  <title>{chapter_name}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #000; }}
    div.p {{ text-align: center; page-break-inside: avoid; }}
    div.p + div.p {{ page-break-before: always; }}
    img {{ max-width: 100%; display: block; margin: 0 auto; }}
  </style>
</head>
<body>
{pages}
</body>
</html>"""


def build_nav_xhtml(manga_title: str, toc_entries: list) -> str:
    items = "\n".join(f'      <li><a href="{href}">{name}</a></li>' for name, href in toc_entries)
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="UTF-8"/><title>{manga_title}</title></head>
<body>
  <nav epub:type="toc">
    <h1>Contents</h1>
    <ol>
{items}
    </ol>
  </nav>
</body>
</html>"""


def build_toc_ncx(manga_title: str, book_id: str, toc_entries: list) -> str:
    navpoints = ""
    for i, (name, href) in enumerate(toc_entries, 1):
        navpoints += (
            f'    <navPoint id="nav-{i}" playOrder="{i}">\n'
            f'      <navLabel><text>{name}</text></navLabel>\n'
            f'      <content src="{href}"/>\n'
            f'    </navPoint>\n'
        )
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{book_id}"/></head>
  <docTitle><text>{manga_title}</text></docTitle>
  <navMap>
{navpoints}  </navMap>
</ncx>"""


def build_content_opf(manga_title: str, book_id: str, manifest_items: list, spine_items: list) -> str:
    manifest_lines = [
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
    ]
    for item_id, href, media_type in manifest_items:
        manifest_lines.append(f'    <item id="{item_id}" href="{href}" media-type="{media_type}"/>')

    spine_lines = [f'    <itemref idref="{item}"/>' for item in spine_items]

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{book_id}</dc:identifier>
    <dc:title>{manga_title}</dc:title>
    <dc:language>ja</dc:language>
  </metadata>
  <manifest>
{"    " + chr(10) + "    ".join(manifest_lines)}
  </manifest>
  <spine toc="ncx" page-progression-direction="rtl">
{"    " + chr(10) + "    ".join(spine_lines)}
  </spine>
</package>"""


# ── Main builder ────────────────────────────────────────────────────────────

def build_epub(manga_dir: Path, dpi: int = 150, grayscale: bool = False) -> Path:
    manga_title = manga_dir.name.replace('_', ' ')
    book_id = str(uuid.uuid4())
    output_path = manga_dir.parent / f"{manga_dir.name}.epub"

    pdfs = sorted(manga_dir.glob('*.pdf'), key=lambda p: natural_sort_key(p.name))
    if not pdfs:
        print(f"No PDFs found in {manga_dir}")
        sys.exit(1)

    mode_label = "grayscale" if grayscale else "color"
    print(f"\nBuilding: {manga_title}")
    print(f"Chapters: {len(pdfs)}  |  DPI: {dpi}  |  Mode: {mode_label}\n")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        meta_inf  = tmp / 'META-INF'
        oebps     = tmp / 'OEBPS'
        images_dir = oebps / 'images'
        pages_dir  = oebps / 'pages'
        for d in (meta_inf, oebps, images_dir, pages_dir):
            d.mkdir()

        (meta_inf / 'container.xml').write_text(CONTAINER_XML, encoding='utf-8')

        manifest_items = []
        spine_items    = []
        toc_entries    = []

        for chapter_pdf in pdfs:
            chapter_name = chapter_pdf.stem.replace('_', ' ')
            prefix = re.sub(r'[^\w]', '_', chapter_pdf.stem)

            print(f"  [{pdfs.index(chapter_pdf) + 1}/{len(pdfs)}] Extracting {chapter_name}...")
            try:
                img_filenames = extract_chapter_images(chapter_pdf, images_dir, prefix, dpi,
                                                       grayscale=grayscale)
            except Exception as e:
                log.exception("Failed to extract %s: %s", chapter_pdf, e)
                print(f"  Error extracting {chapter_name} — skipping (see log)")
                continue

            # one XHTML per chapter containing all pages
            ch_id      = prefix
            xhtml_name = f"{ch_id}.xhtml"

            (pages_dir / xhtml_name).write_text(
                chapter_xhtml(chapter_name, img_filenames),
                encoding='utf-8'
            )

            for img_filename in img_filenames:
                safe_id = img_filename.replace('.jpg', '').replace('-', '_')
                manifest_items.append((f"img_{safe_id}", f"images/{img_filename}", "image/jpeg"))

            manifest_items.append((f"ch_{ch_id}", f"pages/{xhtml_name}", "application/xhtml+xml"))
            spine_items.append(f"ch_{ch_id}")
            toc_entries.append((chapter_name, f"pages/{xhtml_name}"))

        (oebps / 'nav.xhtml').write_text(build_nav_xhtml(manga_title, toc_entries), encoding='utf-8')
        (oebps / 'toc.ncx').write_text(build_toc_ncx(manga_title, book_id, toc_entries), encoding='utf-8')
        (oebps / 'content.opf').write_text(build_content_opf(manga_title, book_id, manifest_items, spine_items), encoding='utf-8')

        print(f"\nPacking EPUB...")
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', zipfile.ZIP_STORED)
            for file_path in sorted(tmp.rglob('*')):
                if file_path.is_file():
                    zf.write(str(file_path), str(file_path.relative_to(tmp)))

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Saved: {output_path} ({size_mb:.1f} MB)")
    return output_path


def convert_to_azw3(epub_path: Path):
    ebook_convert = shutil.which('ebook-convert')
    if not ebook_convert:
        print("\nCalibre not found — cannot convert to AZW3 automatically.")
        print("  1. Install Calibre: https://calibre-ebook.com")
        print(f"  2. Or email the EPUB to your Kindle address (Amazon auto-converts)")
        print(f"  3. Or run manually: ebook-convert \"{epub_path.name}\" \"{epub_path.with_suffix('.azw3').name}\"")
        return

    azw3_path = epub_path.with_suffix('.azw3')
    print("Converting to AZW3 (Kindle KF8) via Calibre...")
    result = subprocess.run(
        [ebook_convert, str(epub_path), str(azw3_path),
         '--output-profile', 'kindle_pw3'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        size_mb = azw3_path.stat().st_size / 1024 / 1024
        print(f"Saved: {azw3_path} ({size_mb:.1f} MB)")
        print(f"  Transfer via USB to Kindle documents/ folder")
    else:
        log.error("ebook-convert failed:\n%s", result.stderr)
        print(f"AZW3 conversion failed — see manga_downloader.log")
        print(f"  {result.stderr.splitlines()[-1] if result.stderr else ''}")


# ── Entry point ─────────────────────────────────────────────────────────────

def pick_manga_folder() -> Path:
    manga_base = Path(__file__).parent / 'manga'
    folders = sorted([f for f in manga_base.iterdir() if f.is_dir()], key=lambda p: p.name)
    if not folders:
        print("No manga folders found in manga/")
        sys.exit(1)

    print("Available manga:")
    for i, folder in enumerate(folders, 1):
        pdfs = list(folder.glob('*.pdf'))
        print(f"  {i}. {folder.name.replace('_', ' ')} ({len(pdfs)} chapters)")

    while True:
        raw = input(f"\nSelect manga (1-{len(folders)}): ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(folders):
                return folders[idx]
            print(f"  Out of range — enter a number between 1 and {len(folders)}.")
        except ValueError:
            print(f"  Invalid input — enter a number.")


FORMAT_OPTIONS = [
    ("epub",      "EPUB only           — universal format, all readers"),
    ("azw3",      "AZW3 only           — Kindle USB transfer (recommended)"),
    ("epub+azw3", "EPUB + AZW3         — both files"),
]


def pick_format() -> str:
    """Interactive format selection. Returns 'epub', 'azw3' or 'epub+azw3'."""
    print("\nOutput format:")
    for i, (key, label) in enumerate(FORMAT_OPTIONS, 1):
        print(f"  {i}. {label}")
    while True:
        raw = input("Select format (1-3): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(FORMAT_OPTIONS):
            return FORMAT_OPTIONS[int(raw) - 1][0]
        print(f"  Enter a number between 1 and {len(FORMAT_OPTIONS)}.")


def pick_grayscale() -> bool:
    """Ask user whether to use grayscale mode. Returns True/False."""
    print("\nGrayscale mode?")
    print("  Reduces file size ~40%, ideal for B&W manga and Kindle.")
    raw = input("  Use grayscale? (Y/n) ").strip().lower()
    return raw != 'n'


DPI_PRESETS = [
    (150, "High    — best quality, ~15 MB/chapter"),
    (100, "Medium  — recommended for Kindle email"),
    (72,  "Low     — smallest file, ~4 MB/chapter"),
]


def pick_dpi(default: int = None) -> int:
    """Interactive DPI selection. Returns chosen DPI value."""
    print("\nImage quality (DPI):")
    for i, (dpi, label) in enumerate(DPI_PRESETS, 1):
        marker = " *" if dpi == default else ""
        print(f"  {i}. {label}  ({dpi} dpi){marker}")
    print(f"  Or enter a custom value (50-300)")

    while True:
        raw = input("Select quality: ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(DPI_PRESETS):
                return DPI_PRESETS[n - 1][0]
            if 50 <= n <= 300:
                return n
        print(f"  Enter 1-{len(DPI_PRESETS)} or a number between 50 and 300.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert manga PDFs to EPUB/AZW3')
    parser.add_argument('folder', nargs='?', help='Path to manga folder')
    parser.add_argument('--dpi', type=int, help='Skip DPI prompt and use this value (50-300)')
    args = parser.parse_args()

    manga_dir = Path(args.folder) if args.folder else pick_manga_folder()

    if not manga_dir.exists():
        print(f"Folder not found: {manga_dir}")
        sys.exit(1)

    dpi = args.dpi if args.dpi else pick_dpi(default=150)

    if not (50 <= dpi <= 300):
        print("  DPI must be between 50 and 300.")
        sys.exit(1)

    fmt = pick_format()
    gs  = pick_grayscale()

    epub_path = build_epub(manga_dir, dpi=dpi, grayscale=gs)

    if fmt in ('azw3', 'epub+azw3'):
        convert_to_azw3(epub_path)

    if fmt == 'azw3':
        epub_path.unlink(missing_ok=True)
        print("  EPUB removed (AZW3 only mode)")

    print("\nDone.")
