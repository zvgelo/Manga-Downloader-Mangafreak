from models import Chapter, SearchResult


# ── SearchResult ──────────────────────────────────────────────────────────────

def test_search_result_defaults():
    r = SearchResult(title="Naruto", series_url="https://x/naruto")
    assert r.display_lines == []
    assert r.cover_url == ""


def test_menu_lines_uses_display_lines_when_present():
    r = SearchResult(title="Naruto", series_url="u",
                     display_lines=["Naruto", "Ongoing", "700 ch"])
    assert r.menu_lines == ["Naruto", "Ongoing", "700 ch"]


def test_menu_lines_falls_back_to_title():
    r = SearchResult(title="Naruto", series_url="u")
    assert r.menu_lines == ["Naruto"]


def test_search_results_independent_display_lines():
    # default_factory must not share one list across instances
    a = SearchResult(title="A", series_url="u")
    b = SearchResult(title="B", series_url="u")
    a.display_lines.append("x")
    assert b.display_lines == []


# ── Chapter ───────────────────────────────────────────────────────────────────

def test_chapter_fields():
    ch = Chapter(title="Chapter 5", url="https://x/5")
    assert ch.title == "Chapter 5"
    assert ch.url == "https://x/5"


def test_chapter_title_is_mutable():
    # enrich_chapter_titles updates title in-place
    ch = Chapter(title="Chapter 5", url="u")
    ch.title = "Chapter 5 - Blue Vortex"
    assert ch.title == "Chapter 5 - Blue Vortex"


def test_chapter_equality():
    assert Chapter("Chapter 1", "u") == Chapter("Chapter 1", "u")
    assert Chapter("Chapter 1", "u") != Chapter("Chapter 2", "u")
