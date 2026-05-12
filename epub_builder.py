import re
import sys
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image as PILImage

from logger import get_logger

log = get_logger(__name__)


def natural_sort_key(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text))]


@contextmanager
def _silence_mupdf():
    """Suppress MuPDF C-level output (ICC profile warnings etc.)."""
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
                           grayscale: bool = False, fit_kindle: bool = False,
                           kindle_w: int = 1072, kindle_h: int = 1448,
                           margin_pct: float = 0.0) -> list[str]:
    """Extract each PDF page as JPEG. Returns list of filenames."""
    with _silence_mupdf():
        doc = pymupdf.open(str(pdf_path))
    filenames = []
    for i, page in enumerate(doc):
        with _silence_mupdf():
            pix = page.get_pixmap(dpi=dpi)
        img = PILImage.open(BytesIO(pix.tobytes("jpeg")))

        if fit_kindle:
            factor = (100 - 2 * margin_pct) / 100
            target_w = kindle_w * factor
            target_h = kindle_h * factor
            scale = min(target_w / img.width, target_h / img.height)
            img = img.resize((int(img.width * scale), int(img.height * scale)),
                             PILImage.LANCZOS)

        if grayscale:
            img = img.convert('L')

        img_path = str(images_dir / f"{prefix}_{i + 1:03d}.jpg")
        img.save(img_path, 'JPEG', quality=95)
        filenames.append(f"{prefix}_{i + 1:03d}.jpg")
    doc.close()
    return filenames


# ── EPUB templates ───────────────────────────────────────────────────────────

CONTAINER_XML = """\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


CONTENT_CSS = """\
    html, body { margin: 0 !important; padding: 0 !important; background: #000; }
    div.p  { margin: 0 !important; padding: 0 !important;
             text-align: center; page-break-inside: avoid; }
    div.p + div.p { page-break-before: always; }
    img    { max-width: 100% !important; max-height: 100vh !important;
             width: auto !important; height: auto !important;
             display: block; margin: 0 auto !important; }\
"""


def build_content_xhtml(manga_title: str, chapters: list) -> str:
    divs = []
    for chapter_name, ch_id, img_filenames in chapters:
        for i, fn in enumerate(img_filenames):
            anchor = f' id="{ch_id}"' if i == 0 else ''
            divs.append(
                f'  <div class="p"{anchor}>'
                f'<img src="../images/{fn}" alt="{chapter_name}"/></div>'
            )
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8"/>
  <title>{manga_title}</title>
  <style>
{CONTENT_CSS}
  </style>
</head>
<body>
{chr(10).join(divs)}
</body>
</html>"""


def build_nav_xhtml(manga_title: str, toc_entries: list) -> str:
    items = "\n".join(
        f'      <li><a href="{href}">{name}</a></li>' for name, href in toc_entries
    )
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


def build_content_opf(manga_title: str, book_id: str,
                      manifest_items: list, spine_items: list,
                      metadata=None) -> str:
    import html as _html

    meta_lines = [
        f'    <dc:identifier id="uid">{book_id}</dc:identifier>',
        f'    <dc:title>{manga_title}</dc:title>',
        '    <dc:language>ja</dc:language>',
    ]
    if metadata:
        if getattr(metadata, 'author', ''):
            meta_lines.append(f'    <dc:creator>{_html.escape(metadata.author)}</dc:creator>')
        artist = getattr(metadata, 'artist', '')
        if artist and artist != metadata.author:
            meta_lines.append(f'    <dc:creator>{_html.escape(artist)}</dc:creator>')
        if getattr(metadata, 'year', None):
            meta_lines.append(f'    <dc:date>{metadata.year}-01-01</dc:date>')
        if getattr(metadata, 'description', ''):
            meta_lines.append(
                f'    <dc:description>{_html.escape(metadata.description)}</dc:description>'
            )
    manifest_lines = [
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
    ]
    for item_id, href, media_type in manifest_items:
        manifest_lines.append(
            f'    <item id="{item_id}" href="{href}" media-type="{media_type}"/>'
        )
    spine_lines = [f'    <itemref idref="{item}"/>' for item in spine_items]

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
{chr(10).join(meta_lines)}
  </metadata>
  <manifest>
{chr(10).join(manifest_lines)}
  </manifest>
  <spine toc="ncx" page-progression-direction="rtl">
{chr(10).join(spine_lines)}
  </spine>
</package>"""


def build_epub(manga_dir: Path, dpi: int = 150, grayscale: bool = False,
               pdfs: list = None, title_suffix: str = "",
               fit_kindle: bool = False, kindle_w: int = 1072,
               kindle_h: int = 1448, margin_pct: float = 0.0,
               metadata=None) -> Path:
    manga_title = manga_dir.name.replace('_', ' ')
    if title_suffix:
        manga_title = f"{manga_title} {title_suffix}"
    book_id = str(uuid.uuid4())
    slug = manga_dir.name + (f"_{title_suffix.replace(' ', '_')}" if title_suffix else "")
    output_path = manga_dir.parent / f"{slug}.epub"

    if pdfs is None:
        pdfs = sorted(manga_dir.glob('*.pdf'), key=lambda p: natural_sort_key(p.name))
    if not pdfs:
        print(f"No PDFs found in {manga_dir}")
        sys.exit(1)

    mode_label = "grayscale" if grayscale else "color"
    print(f"\nBuilding: {manga_title}")
    print(f"Chapters: {len(pdfs)}  |  DPI: {dpi}  |  Mode: {mode_label}\n")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        meta_inf   = tmp / 'META-INF'
        oebps      = tmp / 'OEBPS'
        images_dir = oebps / 'images'
        pages_dir  = oebps / 'pages'
        for d in (meta_inf, oebps, images_dir, pages_dir):
            d.mkdir()

        (meta_inf / 'container.xml').write_text(CONTAINER_XML, encoding='utf-8')

        manifest_items = []
        all_chapters   = []

        for ch_idx, chapter_pdf in enumerate(pdfs, 1):
            chapter_name = chapter_pdf.stem.replace('_', ' ')
            prefix = re.sub(r'[^\w]', '_', chapter_pdf.stem)
            print(f"  [{ch_idx}/{len(pdfs)}] Extracting {chapter_name}...")
            try:
                img_filenames = extract_chapter_images(
                    chapter_pdf, images_dir, prefix, dpi,
                    grayscale=grayscale, fit_kindle=fit_kindle,
                    kindle_w=kindle_w, kindle_h=kindle_h, margin_pct=margin_pct,
                )
            except Exception as e:
                log.exception("Failed to extract %s: %s", chapter_pdf, e)
                print(f"  Error extracting {chapter_name} — skipping (see log)")
                continue

            for fn in img_filenames:
                safe_id = fn.replace('.jpg', '').replace('-', '_')
                manifest_items.append((f"img_{safe_id}", f"images/{fn}", "image/jpeg"))
            all_chapters.append((chapter_name, prefix, img_filenames))

        content_file = "content.xhtml"
        (pages_dir / content_file).write_text(
            build_content_xhtml(manga_title, all_chapters), encoding='utf-8'
        )
        manifest_items.append(("content", f"pages/{content_file}", "application/xhtml+xml"))
        spine_items = ["content"]
        toc_entries = [
            (name, f"pages/{content_file}#{ch_id}") for name, ch_id, _ in all_chapters
        ]

        (oebps / 'nav.xhtml').write_text(
            build_nav_xhtml(manga_title, toc_entries), encoding='utf-8'
        )
        (oebps / 'toc.ncx').write_text(
            build_toc_ncx(manga_title, book_id, toc_entries), encoding='utf-8'
        )
        (oebps / 'content.opf').write_text(
            build_content_opf(manga_title, book_id, manifest_items, spine_items,
                              metadata=metadata),
            encoding='utf-8',
        )

        print(f"\nPacking EPUB...")
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', zipfile.ZIP_STORED)
            for file_path in sorted(tmp.rglob('*')):
                if file_path.is_file():
                    zf.write(str(file_path), str(file_path.relative_to(tmp)))

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Saved: {output_path} ({size_mb:.1f} MB)")
    return output_path
