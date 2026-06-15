"""
Tests for the pure MangaDex data layer (metadata.py) — no network.
A fake HTTP transport feeds canned JSON to MangaDexClient.
"""

from metadata import (MangaDexClient, MangaMetadata, _clean_description, _parse,
                      apply_chapter_titles, chapters_missing_titles)
from models import Chapter


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeHttp:
    """Records GET calls and replays a queue of canned responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return FakeResp(self._responses.pop(0))


def _manga(id_, title, author=None, artist=None, year=2023, status="ongoing"):
    rels = []
    if author:
        rels.append({"type": "author", "attributes": {"name": author}})
    if artist:
        rels.append({"type": "artist", "attributes": {"name": artist}})
    return {
        "id": id_,
        "attributes": {"title": {"en": title}, "year": year,
                       "status": status, "description": {"en": ""}},
        "relationships": rels,
    }


# ── _parse / _clean_description ───────────────────────────────────────────────

def test_parse_extracts_core_fields():
    meta = _parse(_manga("abc", "Naruto", author="Kishimoto", artist="Kishimoto"))
    assert meta == MangaMetadata(
        title="Naruto", author="Kishimoto", artist="Kishimoto",
        year=2023, description="", status="ongoing", manga_id="abc",
    )


def test_parse_falls_back_to_any_title_language():
    m = _manga("x", "ignored")
    m["attributes"]["title"] = {"ja": "ナルト"}
    assert _parse(m).title == "ナルト"


def test_clean_description_strips_markdown_and_trailing_links():
    raw = "A **bold** tale with a [link](http://x).\n\nLinks: http://y"
    assert _clean_description(raw) == "A bold tale with a link."


# ── MangaDexClient.search ─────────────────────────────────────────────────────

def test_search_returns_parsed_candidates():
    http = FakeHttp([{"data": [_manga("1", "Naruto", author="K"),
                               _manga("2", "Bleach", author="K2")]}])
    client = MangaDexClient(http=http)

    results = client.search("naruto", limit=6)

    assert [r.title for r in results] == ["Naruto", "Bleach"]
    assert results[0].manga_id == "1"
    # query params forwarded
    _, params = http.calls[0]
    assert params["title"] == "naruto" and params["limit"] == 6


def test_search_empty_data_returns_empty_list():
    client = MangaDexClient(http=FakeHttp([{"data": []}]))
    assert client.search("nothing") == []


# ── MangaDexClient.fetch_chapter_titles ───────────────────────────────────────

def _feed(*entries):
    return {"data": [{"attributes": {"chapter": c, "title": t,
                                     "translatedLanguage": lang}}
                     for c, t, lang in entries]}


def test_fetch_chapter_titles_prefers_english():
    http = FakeHttp([_feed(("1", "Polski", "pl"), ("1", "English", "en"))])
    titles = MangaDexClient(http=http).fetch_chapter_titles("id")
    assert titles == {"1": "English"}


def test_fetch_chapter_titles_falls_back_to_polish():
    http = FakeHttp([_feed(("2", "Tylko PL", "pl"))])
    assert MangaDexClient(http=http).fetch_chapter_titles("id") == {"2": "Tylko PL"}


def test_fetch_chapter_titles_paginates_until_short_page():
    # 500-entry page forces a second request; second page is short → stop
    page1 = {"data": [{"attributes": {"chapter": str(i), "title": f"T{i}",
                                      "translatedLanguage": "en"}}
                      for i in range(500)]}
    page2 = _feed(("500", "Last", "en"))
    http = FakeHttp([page1, page2])

    titles = MangaDexClient(http=http).fetch_chapter_titles("id")

    assert len(titles) == 501
    assert titles["500"] == "Last"
    assert len(http.calls) == 2
    assert http.calls[1][1]["offset"] == 500


def test_fetch_chapter_titles_stops_on_transport_error():
    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("network down")
    assert MangaDexClient(http=Boom()).fetch_chapter_titles("id") == {}


# ── pure enrichment helpers ───────────────────────────────────────────────────

def test_chapters_missing_titles_flags_only_bare_numbers():
    chapters = [Chapter("Chapter 1", "u1"),
                Chapter("Chapter 2 - Blue Vortex", "u2"),
                Chapter("Chapter 3", "u3")]
    assert chapters_missing_titles(chapters) == [0, 2]


def test_apply_chapter_titles_appends_in_place():
    chapters = [Chapter("Chapter 1", "u1"), Chapter("Chapter 3", "u3")]
    updated = apply_chapter_titles(chapters, [0, 1], {"1": "Beginnings"})
    assert updated == 1
    assert chapters[0].title == "Chapter 1 - Beginnings"
    assert chapters[1].title == "Chapter 3"  # no map entry → untouched
