import pytest
from main import parse_chapter_choice


# ── happy path ────────────────────────────────────────────────────────────────

def test_all_returns_every_index():
    assert parse_chapter_choice("all", 5) == [0, 1, 2, 3, 4]

def test_all_case_insensitive():
    assert parse_chapter_choice("ALL", 5) == [0, 1, 2, 3, 4]

def test_all_whitespace():
    assert parse_chapter_choice("  all  ", 5) == [0, 1, 2, 3, 4]

def test_single_chapter():
    assert parse_chapter_choice("3", 5) == [2]

def test_first_chapter():
    assert parse_chapter_choice("1", 10) == [0]

def test_last_chapter():
    assert parse_chapter_choice("5", 5) == [4]

def test_range():
    assert parse_chapter_choice("1-3", 5) == [0, 1, 2]

def test_range_full():
    assert parse_chapter_choice("1-5", 5) == [0, 1, 2, 3, 4]

def test_single_element_range():
    assert parse_chapter_choice("3-3", 5) == [2]

def test_comma_list():
    assert parse_chapter_choice("1,3,7", 10) == [0, 2, 6]

def test_mixed_range_and_single():
    assert parse_chapter_choice("1-3,7,10", 10) == [0, 1, 2, 6, 9]

def test_duplicates_are_deduplicated():
    assert parse_chapter_choice("1,1,2", 5) == [0, 1]

def test_overlapping_ranges_deduplicated():
    assert parse_chapter_choice("1-3,2-4", 5) == [0, 1, 2, 3]

def test_result_is_sorted():
    assert parse_chapter_choice("5,1,3", 10) == [0, 2, 4]

def test_spaces_around_parts():
    assert parse_chapter_choice(" 2 , 4 ", 5) == [1, 3]


# ── error cases ───────────────────────────────────────────────────────────────

def test_chapter_zero_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("0", 5)

def test_chapter_above_total_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("6", 5)

def test_range_start_above_total_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("4-6", 5)

def test_range_end_above_total_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("1-6", 5)

def test_reversed_range_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("3-1", 5)

def test_empty_string_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("", 5)

def test_trailing_comma_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("1,", 5)

def test_leading_comma_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice(",1", 5)

def test_text_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("abc", 5)

def test_float_raises():
    with pytest.raises(ValueError):
        parse_chapter_choice("1.5", 5)
