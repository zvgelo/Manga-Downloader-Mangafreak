# Manga Downloader — MangaFreak

Downloads manga chapters from [ww2.mangafreak.me](https://ww2.mangafreak.me) and saves them as PDF files.

## Features

- Interactive terminal UI with search, chapter listing and selection
- Flexible chapter selection: single, range, multiple picks or all at once
- Skips already downloaded chapters automatically
- Saves each chapter as a named PDF: `MangaTitle_Chapter_N.pdf`
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

```bash
python main.py
```

The tool walks you through three steps:

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

**3. Select chapters to download**

| Input     | Result                        |
|-----------|-------------------------------|
| `all`     | all chapters                  |
| `5`       | chapter 5 only                |
| `1-3`     | chapters 1, 2, 3              |
| `1,3,7`   | chapters 1, 3 and 7           |
| `1-3,7,10`| chapters 1, 2, 3, 7 and 10   |

## Output structure

```
manga/
└── Boruto_Two_Blue_Vortex/
    ├── Boruto_Two_Blue_Vortex_Chapter_1.pdf
    ├── Boruto_Two_Blue_Vortex_Chapter_2.pdf
    └── ...
```

## Project structure

```
main.py        — entry point, UI and flow orchestration
browser.py     — Selenium / Chrome setup
scraper.py     — search, chapter listing, image URL extraction
downloader.py  — image downloading and PDF generation
logger.py      — logging configuration
```

## Logging

Errors are logged to `manga_downloader.log` in the project root with timestamps and full tracebacks. The file is created on first run and is excluded from git.
