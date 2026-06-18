# TODO

Stan: kroki 1–6 GUI-readiness ukończone + runda hardeningu (cleanup, scraper,
browser, warstwy ebooka). 126 testów zielonych.

## ✅ Zrobione
- Rozdzielenie core ↔ frontend dla ścieżki pobierania (`models`, `settings`,
  `events`, `DownloadService`); core bez `input()` / `print()` / `rich`.
- Krok 6: `metadata.py` to czysta warstwa danych (`MangaDexClient` +
  `chapters_missing_titles` / `apply_chapter_titles`); interaktywne pickery w
  `metadata_prompts.py`.
- `ebook_options.py`: model `EbookOptions` + wspólne reguły walidacji
  (DPI, margines, rozmiar Kindle, split) reużywane przez CLI i argparse.
- `build_ebooks()` bezprompttowe — bierze `EbookOptions` i `metadata` jako
  argumenty (sterowalne z GUI).
- Naprawiony cleanup `chapter_dir` przy błędzie pobierania obrazów
  (`downloader.download_chapter`).
- `scraper.get_chapter_images`: jawny wait zamiast `time.sleep`, zapytanie
  scopowane selektorem CSS zamiast skanowania wszystkich `img`.
- `browser.py`: cache ścieżki chromedrivera (jeden `install()` na proces).
- `epub_builder.build_epub`: `ValueError` zamiast `sys.exit()`.
- README opisuje architekturę, trzy szwy i czystą warstwę danych ebooka.

## 🟠 P2 — jakość / drobne
- [ ] **DeprecationWarning Pillow** (`downloader.py:_row_brightness`) —
  `getdata()` znika w Pillow 14 (2027). Podmienić na `get_flattened_data()`
  z fallbackiem dla starszych wersji.
- [ ] `ebook_convert.py` / `epub_builder.py` nadal wypisują postęp przez
  `print()`. Dla GUI docelowo warto zdarzeniowy progress (jak `DownloadObserver`),
  ale to większa zmiana — świadomie odłożone.

## 🟡 P3 — luki w testach
Dodano: `test_scraper.py`, `test_metadata.py`, `test_ebook_options.py` oraz
regresję cleanupu w `test_download_chapter.py`. Wciąż bez pokrycia:
- [ ] `epub_builder.py` (składanie EPUB / OPF / nav) — testy na małym PDF-ie.
- [ ] `ebook_convert.merge_to_pdf` (TOC, scalanie) — test na fixturach PDF.
- [ ] `ui.py` (`RichDownloadObserver`) — smoke render bez realnego terminala.

## 🟢 P4 — przyszłość
- [ ] Frontend GUI jako druga implementacja `DownloadObserver` + użycie
  `DownloadService`, `MangaDexClient`, `EbookOptions`, `build_ebooks`.
- [ ] (opcjonalnie) Zdarzeniowy progress dla flow ebooka.
- [ ] (opcjonalnie) Profile w `Settings` per model Kindle / typ mangi.
