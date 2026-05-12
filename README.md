# Manga Downloader — MangaFreak

Downloads manga chapters from [ww2.mangafreak.me](https://ww2.mangafreak.me), saves them as PDFs and optionally exports to EPUB or AZW3 (Kindle).

## Features

- Interactive terminal UI with clear-screen headers
- Flexible chapter selection: single, range, comma-separated picks or all at once
- Skips already downloaded chapters automatically
- Grayscale mode — reduces file size ~40%, ideal for B&W manga and Kindle
- Exports to **EPUB** or **AZW3** (Kindle KF8) with chapter table of contents
- Adjustable image DPI for ebook export
- Retry with exponential backoff on network errors
- Error logging to `manga_downloader.log`

## Requirements

- Python 3.9+
- Google Chrome installed

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

The tool walks you through the following steps:

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
Create ebook from downloaded chapters? (y/N)
```

If yes, you choose output format, DPI and grayscale mode interactively.

### Export existing downloads to ebook

```bash
python to_ebook.py                               # interactive folder picker
python to_ebook.py manga/Boruto_Two_Blue_Vortex  # direct path
python to_ebook.py manga/Boruto_Two_Blue_Vortex --dpi 100
```

**Format options:**

| Option       | Description                              |
|--------------|------------------------------------------|
| EPUB only    | Universal format, all readers            |
| AZW3 only    | Kindle USB transfer (recommended)        |
| EPUB + AZW3  | Both files                               |

**DPI guide:**

| DPI | Quality       | ~Size per chapter |
|-----|---------------|-------------------|
| 150 | High          | ~15 MB            |
| 100 | Medium        | ~10 MB (recommended for Kindle email) |
| 72  | Low           | ~4 MB             |

Transfer AZW3 to Kindle via USB to the `documents/` folder.

## Output structure

```
manga/
└── Boruto_Two_Blue_Vortex/
    ├── Boruto_Two_Blue_Vortex_Chapter_1.pdf
    ├── Boruto_Two_Blue_Vortex_Chapter_2.pdf
    └── ...
Boruto_Two_Blue_Vortex.epub
Boruto_Two_Blue_Vortex.azw3
```

## Project structure

```
main.py        — entry point, UI and download orchestration
browser.py     — Selenium / Chrome setup
scraper.py     — search, chapter listing, image URL extraction
downloader.py  — image downloading and PDF generation
to_ebook.py    — PDF to EPUB / AZW3 conversion
logger.py      — logging configuration
```

## Logging

Errors are logged to `manga_downloader.log` in the project root with timestamps and full tracebacks. The file is created on first run and is excluded from git.
