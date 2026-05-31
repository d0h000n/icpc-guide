"""Parsers for bulk-paste textareas (admin + proposal form).

Format: one entry per line, fields separated by `|`. Trailing fields are
optional. Used by the ProblemSet admin's bulk-add controls (problems and
children) and the user proposal form.
"""

from __future__ import annotations

from typing import TypedDict


class ProblemEntry(TypedDict):
    label: str
    title: str
    external_url: str
    tier: int | None


class ChildSetEntry(TypedDict):
    title: str
    year: int | None


class BulkParseError(ValueError):
    """Caller-visible: a textarea line was malformed."""


def parse_problems_text(raw: str) -> list[ProblemEntry]:
    """Parse `라벨 | 제목 | URL | 티어` lines into Problem entries.

    URL and 티어 are optional. 티어 must be an int 1-30 (solved.ac scale).
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    parsed: list[ProblemEntry] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            raise BulkParseError(f"{lineno}번째 줄: '라벨 | 제목' 형식이 필요합니다.")
        label, title = parts[0], parts[1]
        if not label or not title:
            raise BulkParseError(f"{lineno}번째 줄: 라벨과 제목은 필수입니다.")
        url = parts[2] if len(parts) > 2 else ""
        tier_raw = parts[3] if len(parts) > 3 else ""
        tier: int | None = None
        if tier_raw:
            try:
                tier = int(tier_raw)
            except ValueError as exc:
                raise BulkParseError(f"{lineno}번째 줄: 티어는 1-30 사이 정수여야 합니다.") from exc
            if not 1 <= tier <= 30:
                raise BulkParseError(f"{lineno}번째 줄: 티어는 1-30 사이여야 합니다.")
        parsed.append({"label": label, "title": title, "external_url": url, "tier": tier})
    return parsed


def parse_children_text(raw: str) -> list[ChildSetEntry]:
    """Parse `제목 | 연도` lines into child ProblemSet entries.

    Year is optional. When provided it must be an integer.
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    parsed: list[ChildSetEntry] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        title = parts[0]
        if not title:
            raise BulkParseError(f"{lineno}번째 줄: 제목이 필요합니다.")
        year_raw = parts[1] if len(parts) > 1 else ""
        year: int | None = None
        if year_raw:
            try:
                year = int(year_raw)
            except ValueError as exc:
                raise BulkParseError(f"{lineno}번째 줄: 연도는 정수여야 합니다.") from exc
        parsed.append({"title": title, "year": year})
    return parsed
