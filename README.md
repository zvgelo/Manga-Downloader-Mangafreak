# Manga Downloader — MangaFreak

Downloads manga chapters from [ww2.mangafreak.me](https://ww2.mangafreak.me), saves them as PDFs and optionally exports to EPUB or MOBI (Kindle).

## Features

- Interactive terminal UI with clear-screen headers
- Flexible chapter selection: single, range, comma-separated picks or all at once
- Skips already downloaded chapters automatically
- Grayscale mode — reduces file size ~40%, ideal for B&W manga and Kindle
- Exports to **EPUB**, **MOBI** (Kindle USB transfer) or merged **PDF** with table of contents
- Kindle screen fit — resizes pages to prevent blank overflow pages, with configurable margin
- Supports multiple Kindle models (basic, Paperwhite, Scribe) and custom screen sizes
- Volume splitting — prompts to split large manga (>30 chapters) into volumes
- Adjustable image DPI for ebook export
- `to_ebook.py` fully scriptable via CLI flags — no interactive prompts needed
- Spread detection — splits landscape double-pages into portrait panels
- Retry with exponential backoff on network errors
- Error logging to `manga_downloader.log`

## Requirements

- Python 3.10+
- Google Chrome installed
- [Calibre](https://calibre-ebook.com) — required for MOBI export (`ebook-convert` must be on PATH)

## Installation

```bash
pip install -r requirements.txt
```

`chromedriver` is downloaded automatically by `webdriver-manager` to match your installed Chrome version — no manual setup needed.

## Usage

### Download manga

```bash
python main.py
```

The tool walks you through:

**1. Search**
```
Search manga: boruto two blue vortex
```

**2. Pick manga from results**
```
  1. Boruto Two Blue Vortex
     33 Chapters Published. (Ongoing)

Select manga (1-1): 1
```

**3. Select chapters**

| Input      | Result                      |
|------------|-----------------------------|
| `all`      | all chapters                |
| `5`        | chapter 5 only              |
| `1-3`      | chapters 1, 2, 3            |
| `1,3,7`    | chapters 1, 3 and 7         |
| `1-3,7,10` | chapters 1, 2, 3, 7 and 10 |

**4. Grayscale option**
```
Grayscale mode?
  Reduces file size ~40%, ideal for B&W manga and Kindle.
  Use grayscale? (Y/n):
```

**5. Ebook export (optional)**

After downloading, the tool asks if you want to create an ebook:

```
Create ebook from downloaded chapters? (y/N): y

Output format:
  1. EPUB only      — universal format, all readers
  2. MOBI only      — Kindle USB transfer
  3. EPUB + MOBI    — both files
  4. PDF only       — merged single file, no re-encoding

Grayscale mode? (Y/n): y

Fit to Kindle screen?
  Resizes pages to prevent blank overflow pages. Recommended for MOBI.
  Fit to Kindle? (Y/n): y

Kindle model:
  1. Kindle basic 11th gen 2022  (6")   (1072×1448)
  2. Kindle Paperwhite / Oasis   (6.8") (1264×1680)
  3. Kindle Scribe               (10.2") (1860×2480)
  4. Custom size
  Select model (1-4): 1

Margin (prevents blank continuation pages on Kindle):
  Default: 15%
  Margin % (Enter for 15%):

Split into volumes?
  33 chapters detected. Large ebooks can be slow on Kindle.
  Split into volumes? (y/N): y

  Chapters per volume:
    1. 10 chapters  (4 volumes)
    2. 20 chapters  (2 volumes)
    3. 30 chapters  (2 volumes)
    Or enter a custom number (5-33)
  Chapters per volume: 20
```

### Export existing downloads to ebook

#### Interactive

```bash
python to_ebook.py                               # folder picker
python to_ebook.py manga/Boruto_Two_Blue_Vortex  # direct path
```

#### Single command (no prompts)

```bash
python to_ebook.py manga/Boruto_Two_Blue_Vortex \
  --format mobi --dpi 150 --grayscale \
  --fit-kindle --kindle-model 1 --margin 15 --split 0
```

All flags:

| Flag | Values | Description |
|------|--------|-------------|
| `--format` | `epub` `mobi` `epub+mobi` `pdf` | Output format |
| `--dpi` | `50`–`300` | Image quality (default 150) |
| `--grayscale` / `--no-grayscale` | — | Grayscale mode |
| `--fit-kindle` / `--no-fit-kindle` | — | Resize pages for Kindle |
| `--kindle-model` | `1` `2` `3` | Kindle preset (1=basic, 2=Paperwhite, 3=Scribe) |
| `--kindle-size` | e.g. `1072x1448` | Custom Kindle screen size |
| `--margin` | `0`–`40` | Margin % per side (default 15) |
| `--split` | `N` or `0` | Chapters per volume (`0` = no split) |

**DPI guide:**

| DPI | Quality | ~Size per chapter |
|-----|---------|-------------------|
| 150 | High    | ~15 MB            |
| 100 | Medium  | ~10 MB (recommended for Kindle email) |
| 72  | Low     | ~4 MB             |

Transfer MOBI to Kindle via USB to the `documents/` folder.

## Output structure

```
manga/
└── Boruto_Two_Blue_Vortex/
    ├── Boruto_Two_Blue_Vortex_Chapter_1.pdf
    ├── Boruto_Two_Blue_Vortex_Chapter_2.pdf
    └── ...

# Single ebook
Boruto_Two_Blue_Vortex.epub
Boruto_Two_Blue_Vortex.mobi

# Split into volumes
Boruto_Two_Blue_Vortex_Vol01.mobi
Boruto_Two_Blue_Vortex_Vol02.mobi
```

## Project structure

```
main.py           — entry point, UI and download orchestration
browser.py        — Selenium / Chrome setup
scraper.py        — search, chapter listing, image URL extraction
downloader.py     — image downloading, spread detection and PDF generation
to_ebook.py       — orchestration (build_ebooks) and CLI entry point
epub_builder.py   — image extraction from PDFs and EPUB assembly
ebook_convert.py  — MOBI conversion via Calibre and PDF merging
ebook_prompts.py  — interactive prompts and Kindle / format constants
logger.py         — logging configuration
```

## Logging

Errors are logged to `manga_downloader.log` in the project root with timestamps and full tracebacks. The file is created on first run and is excluded from git.
