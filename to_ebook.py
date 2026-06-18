"""
Convert downloaded manga chapters (PDFs) to a single EPUB or MOBI ebook.

Usage:
    python to_ebook.py                               # interactive folder picker
    python to_ebook.py manga/Boruto_Two_Blue_Vortex  # direct path
    python to_ebook.py manga/Boruto --format mobi --dpi 150 --grayscale \\
        --fit-kindle --kindle-model 1 --margin 15 --split 0
"""

import argparse
import sys
from pathlib import Path

from epub_builder import build_epub, natural_sort_key
from ebook_convert import convert_to_mobi, merge_to_pdf
from ebook_options import EbookOptions, parse_kindle_size
from ebook_prompts import (
    pick_manga_folder, pick_format, pick_grayscale, pick_dpi,
    pick_kindle_settings, prompt_split_if_large,
    KINDLE_W, KINDLE_H, KINDLE_PRESETS, KINDLE_DEFAULT_MARGIN,
)


def build_ebooks(manga_dir: Path, opts: EbookOptions, metadata=None):
    """
    Build ebooks (split into volumes if requested). Handles epub/mobi/pdf.

    `opts` (EbookOptions) carries the resolved build options and `metadata`
    (a MangaMetadata or None) is supplied by the caller — this function does no
    prompting, so it can be driven equally by the CLI or a future GUI.
    """
    split = opts.split
    all_pdfs = sorted(manga_dir.glob('*.pdf'), key=lambda p: natural_sort_key(p.name))
    if not all_pdfs:
        print(f"No PDFs found in {manga_dir}")
        return

    chunks = (
        [all_pdfs[i:i + split] for i in range(0, len(all_pdfs), split)]
        if split else [all_pdfs]
    )
    if split:
        print(f"\n  Splitting into {len(chunks)} volumes of up to {split} chapters each.")

    for vol_idx, chunk in enumerate(chunks, 1):
        suffix = f"Vol{vol_idx:02d}" if split else ""
        if opts.fmt == 'pdf':
            merge_to_pdf(manga_dir, chunk, suffix)
        else:
            epub_path = build_epub(
                manga_dir, dpi=opts.dpi, grayscale=opts.grayscale,
                pdfs=chunk, title_suffix=suffix,
                fit_kindle=opts.fit_kindle, kindle_w=opts.kindle_w,
                kindle_h=opts.kindle_h, margin_pct=opts.margin_pct,
                metadata=metadata,
            )
            if opts.fmt in ('mobi', 'epub+mobi'):
                convert_to_mobi(epub_path, metadata=metadata)
            if opts.fmt == 'mobi':
                epub_path.unlink(missing_ok=True)

    if opts.fmt == 'mobi':
        print("  EPUB files removed (MOBI only mode)")


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_size_arg(s: str) -> tuple[int, int]:
    """Parse 'WxH' argparse type (reuses the shared validator)."""
    size = parse_kindle_size(s)
    if size:
        return size
    raise argparse.ArgumentTypeError(f"Invalid size '{s}' — use e.g. 1072x1448")


if __name__ == '__main__':
    _preset_help = '  '.join(
        f'{i}={name.split("(")[0].strip()}' for i, (name, _, _) in enumerate(KINDLE_PRESETS, 1)
    )
    parser = argparse.ArgumentParser(
        description='Convert manga PDFs to EPUB/MOBI/PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
examples:
  python to_ebook.py                                        # fully interactive
  python to_ebook.py manga/Boruto_Two_Blue_Vortex           # pick options interactively
  python to_ebook.py manga/Boruto --format mobi --grayscale --fit-kindle
  python to_ebook.py manga/Boruto --format mobi --dpi 150 --grayscale \\
      --fit-kindle --kindle-model 1 --margin 15 --split 0
""")
    parser.add_argument('folder', nargs='?', help='Path to manga folder')
    parser.add_argument('--format', dest='fmt',
                        choices=['epub', 'mobi', 'epub+mobi', 'pdf'],
                        help='Output format')
    parser.add_argument('--dpi', type=int, metavar='N',
                        help='Image quality in DPI (50-300)')
    parser.set_defaults(grayscale=None, fit_kindle=None)
    gs_grp = parser.add_mutually_exclusive_group()
    gs_grp.add_argument('--grayscale',    dest='grayscale', action='store_true',
                        help='Convert images to grayscale')
    gs_grp.add_argument('--no-grayscale', dest='grayscale', action='store_false')
    fk_grp = parser.add_mutually_exclusive_group()
    fk_grp.add_argument('--fit-kindle',    dest='fit_kindle', action='store_true',
                        help='Resize pages to fit Kindle screen')
    fk_grp.add_argument('--no-fit-kindle', dest='fit_kindle', action='store_false')
    parser.add_argument('--kindle-model', type=int, metavar='N',
                        choices=range(1, len(KINDLE_PRESETS) + 1),
                        help=f'Kindle preset ({_preset_help})')
    parser.add_argument('--kindle-size', type=_parse_size_arg, metavar='WxH',
                        help='Custom Kindle screen size (e.g. 1072x1448)')
    parser.add_argument('--margin', type=float, metavar='PCT',
                        help=f'Margin %% on each side (default {KINDLE_DEFAULT_MARGIN:.0f})')
    parser.add_argument('--split', type=int, metavar='N',
                        help='Chapters per volume (0 = no split)')
    args = parser.parse_args()

    manga_dir = Path(args.folder) if args.folder else pick_manga_folder()
    if not manga_dir.exists():
        print(f"Folder not found: {manga_dir}")
        sys.exit(1)

    fmt = args.fmt or pick_format()

    if fmt == 'pdf':
        dpi = args.dpi or 150
        gs = False
        fk, kw, kh, margin = False, KINDLE_W, KINDLE_H, 0.0
    else:
        dpi = args.dpi or pick_dpi(default=150)
        if not (50 <= dpi <= 300):
            print("  DPI must be between 50 and 300.")
            sys.exit(1)
        gs = args.grayscale if args.grayscale is not None else pick_grayscale()

        if args.fit_kindle is not None:
            fk = args.fit_kindle
            if fk:
                if args.kindle_size:
                    kw, kh = args.kindle_size
                elif args.kindle_model:
                    _, kw, kh = KINDLE_PRESETS[args.kindle_model - 1]
                else:
                    kw, kh = KINDLE_W, KINDLE_H
                margin = args.margin if args.margin is not None else KINDLE_DEFAULT_MARGIN
            else:
                kw, kh, margin = KINDLE_W, KINDLE_H, 0.0
        else:
            fk, kw, kh, margin = pick_kindle_settings()

    if args.split is not None:
        split = args.split if args.split > 0 else None
    else:
        split = prompt_split_if_large(len(list(manga_dir.glob('*.pdf'))))

    meta = None
    if fmt != 'pdf':
        from metadata_prompts import pick_metadata
        meta = pick_metadata(manga_dir.name.replace('_', ' '))

    opts = EbookOptions(fmt=fmt, dpi=dpi, grayscale=gs, split=split,
                        fit_kindle=fk, kindle_w=kw, kindle_h=kh, margin_pct=margin)
    build_ebooks(manga_dir, opts, metadata=meta)

    print("\nDone.")
