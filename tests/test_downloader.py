import os
import pytest
from PIL import Image
from downloader import chapter_number, chapter_title, pdf_path, split_spread


# ── chapter_number ────────────────────────────────────────────────────────────

def test_chapter_number_integer():
    assert chapter_number("Chapter 5") == "5"

def test_chapter_number_with_title():
    assert chapter_number("Chapter 5 - Blue Vortex") == "5"

def test_chapter_number_decimal():
    assert chapter_number("Chapter 5.5 - Extra") == "5.5"

def test_chapter_number_case_insensitive():
    assert chapter_number("chapter 10") == "10"

def test_chapter_number_large():
    assert chapter_number("Chapter 123") == "123"

def test_chapter_number_fallback_slug():
    result = chapter_number("One-Shot")
    assert isinstance(result, str)
    assert len(result) > 0
    assert " " not in result

def test_chapter_number_fallback_no_leading_underscore():
    result = chapter_number("One-Shot")
    assert not result.startswith("_")
    assert not result.endswith("_")


# ── chapter_title ─────────────────────────────────────────────────────────────

def test_chapter_title_basic():
    assert chapter_title("Chapter 5 - Blue Vortex") == "Blue_Vortex"

def test_chapter_title_em_dash():
    assert chapter_title("Chapter 5 – Blue Vortex") == "Blue_Vortex"

def test_chapter_title_no_title_part():
    assert chapter_title("Chapter 5") == ""

def test_chapter_title_special_chars_replaced():
    assert chapter_title("Chapter 1 - Hello! World") == "Hello_World"

def test_chapter_title_multiple_spaces_normalized():
    assert chapter_title("Chapter 3 - Two  Words") == "Two_Words"

def test_chapter_title_no_chapter_word():
    assert chapter_title("Volume 1") == ""

def test_chapter_title_no_leading_or_trailing_underscore():
    result = chapter_title("Chapter 7 - !Start!")
    assert not result.startswith("_")
    assert not result.endswith("_")

def test_chapter_title_decimal_chapter():
    assert chapter_title("Chapter 5.5 - Bonus") == "Bonus"


# ── pdf_path ──────────────────────────────────────────────────────────────────

def test_pdf_path_no_title():
    path, ch_num = pdf_path("/manga", "Boruto", "Chapter 5")
    assert path == os.path.join("/manga", "Boruto_Chapter_5.pdf")
    assert ch_num == "5"

def test_pdf_path_with_title():
    path, ch_num = pdf_path("/manga", "Boruto", "Chapter 5 - Blue Vortex")
    assert path == os.path.join("/manga", "Boruto_Chapter_5_-_Blue_Vortex.pdf")
    assert ch_num == "5"

def test_pdf_path_decimal_chapter():
    path, ch_num = pdf_path("/manga", "Naruto", "Chapter 5.5 - Extra")
    assert path == os.path.join("/manga", "Naruto_Chapter_5.5_-_Extra.pdf")
    assert ch_num == "5.5"

def test_pdf_path_respects_manga_dir():
    path, _ = pdf_path("/some/deep/dir", "MyManga", "Chapter 1")
    assert path.startswith("/some/deep/dir")

def test_pdf_path_returns_pdf_extension():
    path, _ = pdf_path("/manga", "X", "Chapter 1")
    assert path.endswith(".pdf")


# ── split_spread ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_img(tmp_path):
    """Returns a helper that creates a temp JPEG and returns its path."""
    def _make(width, height, color="white", bottom_black_rows=0):
        img = Image.new("RGB", (width, height), color)
        if bottom_black_rows:
            black = Image.new("RGB", (width, bottom_black_rows), "black")
            img.paste(black, (0, height - bottom_black_rows))
        p = str(tmp_path / f"{width}x{height}.jpg")
        img.save(p, "JPEG")
        return p
    return _make


def test_portrait_returns_original(tmp_img):
    path = tmp_img(100, 200)
    result = split_spread(path, grayscale=False)
    assert result == [path]


def test_landscape_splits_into_columns(tmp_img):
    # 140x100 → ratio=1.4 > 1.2 → n=round(1.4/0.7)=2 columns
    path = tmp_img(140, 100)
    result = split_spread(path, grayscale=False)
    assert len(result) == 2
    assert all(os.path.exists(p) for p in result)


def test_landscape_slice_files_are_cleaned_up_by_caller(tmp_img):
    path = tmp_img(140, 100)
    slices = split_spread(path, grayscale=False)
    # split_spread only creates the slices; it's the caller's responsibility to clean up
    assert all(p != path for p in slices)


def test_landscape_grayscale_produces_l_mode_slices(tmp_img):
    path = tmp_img(140, 100)
    slices = split_spread(path, grayscale=True)
    for p in slices:
        with Image.open(p) as img:
            assert img.mode == "L"


def test_portrait_near_threshold_not_split(tmp_img):
    # ratio=1.19 < 1.2 → should not split
    path = tmp_img(119, 100)
    result = split_spread(path, grayscale=False)
    assert result == [path]


def test_portrait_with_large_black_padding_splits(tmp_img):
    # 300x400, bottom 200 rows black → content_h≈200
    # (400-200)/400=0.5 > 0.25 and 300/200=1.5 > 1.2 → splits into 2 columns
    path = tmp_img(300, 400, color="white", bottom_black_rows=200)
    result = split_spread(path, grayscale=False)
    assert len(result) >= 2


def test_portrait_small_padding_not_split(tmp_img):
    # bottom 10% black → (400-360)/400=0.1 < 0.25 → should not split
    path = tmp_img(300, 400, color="white", bottom_black_rows=40)
    result = split_spread(path, grayscale=False)
    assert result == [path]
