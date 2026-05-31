"""Unit tests for the shared bulk-paste parsers."""

from __future__ import annotations

import pytest

from apps.problemsets.bulk import (
    BulkParseError,
    parse_children_text,
    parse_problems_text,
)


# ----- parse_problems_text ----------------------------------------------


def test_problems_empty_returns_empty():
    assert parse_problems_text("") == []
    assert parse_problems_text("   \n\n  ") == []


def test_problems_basic_two_lines():
    raw = "A | Alpha | https://a.example | 12\nB | Beta"
    out = parse_problems_text(raw)
    assert out == [
        {"label": "A", "title": "Alpha", "external_url": "https://a.example", "tier": 12},
        {"label": "B", "title": "Beta", "external_url": "", "tier": None},
    ]


def test_problems_whitespace_around_pipes_tolerated():
    raw = "  A   |   Hasty Santa Claus   |   https://x   |   17  "
    out = parse_problems_text(raw)
    assert out[0]["label"] == "A"
    assert out[0]["title"] == "Hasty Santa Claus"
    assert out[0]["external_url"] == "https://x"
    assert out[0]["tier"] == 17


def test_problems_blank_lines_skipped():
    raw = "A | x\n\n  \nB | y"
    assert len(parse_problems_text(raw)) == 2


def test_problems_missing_pipe_errors():
    with pytest.raises(BulkParseError, match="형식이 필요"):
        parse_problems_text("just-a-title")


def test_problems_empty_label_or_title_errors():
    with pytest.raises(BulkParseError, match="필수"):
        parse_problems_text(" | Some Title")
    with pytest.raises(BulkParseError, match="필수"):
        parse_problems_text("A | ")


def test_problems_bad_tier_errors():
    with pytest.raises(BulkParseError, match="정수"):
        parse_problems_text("A | x | | thirteen")


def test_problems_tier_out_of_range_errors():
    with pytest.raises(BulkParseError, match="1-30"):
        parse_problems_text("A | x | | 99")
    with pytest.raises(BulkParseError, match="1-30"):
        parse_problems_text("A | x | | 0")


# ----- parse_children_text ----------------------------------------------


def test_children_empty_returns_empty():
    assert parse_children_text("") == []


def test_children_basic_title_and_year():
    raw = "Yokohama 2022 | 2022\nYokohama 2023 | 2023\nMystery (no year)"
    out = parse_children_text(raw)
    assert out == [
        {"title": "Yokohama 2022", "year": 2022},
        {"title": "Yokohama 2023", "year": 2023},
        {"title": "Mystery (no year)", "year": None},
    ]


def test_children_missing_title_errors():
    with pytest.raises(BulkParseError, match="제목"):
        parse_children_text(" | 2022")


def test_children_bad_year_errors():
    with pytest.raises(BulkParseError, match="정수"):
        parse_children_text("Yokohama 2022 | last-year")
