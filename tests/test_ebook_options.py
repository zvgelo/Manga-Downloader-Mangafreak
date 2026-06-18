"""Tests for the pure ebook-option rules shared by CLI, argparse and any GUI."""

import pytest

from ebook_options import (EbookOptions, clamp_margin, parse_kindle_size,
                           valid_custom_split, valid_dpi)


@pytest.mark.parametrize("n,ok", [(49, False), (50, True), (150, True),
                                  (300, True), (301, False)])
def test_valid_dpi_bounds(n, ok):
    assert valid_dpi(n) is ok


@pytest.mark.parametrize("value,expected", [
    (-5, 0.0), (0, 0.0), (15, 15.0), (40, 40.0), (99, 40.0),
])
def test_clamp_margin(value, expected):
    assert clamp_margin(value) == expected


@pytest.mark.parametrize("n,total,ok", [
    (4, 30, False),   # below custom minimum
    (5, 30, True),
    (30, 30, True),
    (31, 30, False),  # above total
])
def test_valid_custom_split(n, total, ok):
    assert valid_custom_split(n, total) is ok


@pytest.mark.parametrize("raw,expected", [
    ("1072x1448", (1072, 1448)),
    ("1072X1448", (1072, 1448)),
    ("1264×1680", (1264, 1680)),
    ("800,600", (800, 600)),
    ("800 600", (800, 600)),
    ("  1072x1448  ", (1072, 1448)),
])
def test_parse_kindle_size_accepts_separators(raw, expected):
    assert parse_kindle_size(raw) == expected


@pytest.mark.parametrize("raw", [
    "abc", "1072", "100x100",       # 100 below KINDLE_SIZE_MIN
    "6000x600", "1072xfoo", "",
])
def test_parse_kindle_size_rejects_invalid(raw):
    assert parse_kindle_size(raw) is None


def test_ebook_options_defaults():
    o = EbookOptions(fmt="epub")
    assert o.dpi == 150 and o.grayscale is False
    assert o.split is None and o.fit_kindle is False
    assert o.margin_pct == 0.0
