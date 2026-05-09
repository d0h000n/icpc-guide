"""Tests for `manage.py import_problemsets` (YAML bulk import)."""

from __future__ import annotations

import textwrap
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.categories.models import Category
from apps.problemsets.models import (
    Problem,
    ProblemAppearance,
    ProblemSet,
)


def _write(tmp_path, body: str):
    path = tmp_path / "data.yml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _run(*paths, dry_run: bool = False) -> str:
    out = StringIO()
    err = StringIO()
    args = ["import_problemsets", *[str(p) for p in paths]]
    if dry_run:
        args.append("--dry-run")
    call_command(*args, stdout=out, stderr=err)
    return out.getvalue() + err.getvalue()


# ---------- categories ----------


@pytest.mark.django_db
def test_top_level_categories_are_upserted(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        categories:
          - { short_name: japan, name: Japan }
          - { short_name: korea, name: Korea }
        problem_sets: []
        """,
    )
    _run(path)
    assert Category.objects.filter(short_name="japan").exists()
    assert Category.objects.filter(short_name="korea").exists()


@pytest.mark.django_db
def test_unknown_category_on_node_raises(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: ICPC
            categories: [japan]   # not declared, not pre-existing
        """,
    )
    with pytest.raises(CommandError, match="Unknown categories"):
        _run(path)


# ---------- ProblemSet tree ----------


@pytest.mark.django_db
def test_creates_root_then_descendants(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: ICPC
            children:
              - title: Asia-Pacific
                children:
                  - title: Yokohama 2023
                    year: 2023
        """,
    )
    _run(path)
    icpc = ProblemSet.objects.get(title="ICPC")
    assert icpc.depth == 1
    yk = ProblemSet.objects.get(title="Yokohama 2023")
    assert yk.year == 2023
    chain = [a.title for a in yk.get_ancestors()]
    assert chain == ["ICPC", "Asia-Pacific"]


@pytest.mark.django_db
def test_rerun_is_idempotent(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: ICPC
            children:
              - title: Yokohama 2023
                year: 2023
        """,
    )
    _run(path)
    _run(path)
    assert ProblemSet.objects.filter(title="ICPC").count() == 1
    assert ProblemSet.objects.filter(title="Yokohama 2023").count() == 1


@pytest.mark.django_db
def test_rerun_updates_changed_fields(tmp_path) -> None:
    p1 = _write(
        tmp_path,
        """
        problem_sets:
          - title: ICPC
            year: 2022
        """,
    )
    _run(p1)
    p1.write_text(
        textwrap.dedent(
            """
            problem_sets:
              - title: ICPC
                year: 2024
                description: 새 설명
            """
        )
    )
    _run(p1)
    icpc = ProblemSet.objects.get(title="ICPC")
    assert icpc.year == 2024
    assert icpc.description == "새 설명"


# ---------- Problems + Appearances ----------


@pytest.mark.django_db
def test_problems_become_appearances_on_leaf(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: Yokohama 2023
            year: 2023
            problems:
              - { label: A, title: "Hasty Santa Claus", external_url: "https://qoj.ac/p/8439", tier: 17 }
              - { label: B, title: "Interactive Number Guessing", tier: 14 }
        """,
    )
    _run(path)

    yk = ProblemSet.objects.get(title="Yokohama 2023")
    apps = list(yk.appearances.order_by("order_index"))
    assert [a.label for a in apps] == ["A", "B"]
    assert [a.problem.title for a in apps] == [
        "Hasty Santa Claus",
        "Interactive Number Guessing",
    ]
    assert apps[0].problem.solved_ac_tier_manual == 17
    assert apps[0].problem.external_url == "https://qoj.ac/p/8439"


@pytest.mark.django_db
def test_canonical_problem_shared_across_sets(tmp_path) -> None:
    """Same `title` in two different sets → ONE Problem, two ProblemAppearances."""
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: Yokohama 2023
            problems:
              - { label: A, title: "Shared Problem", tier: 17 }
          - title: PTZ Camp Day 5
            problems:
              - { label: C, title: "Shared Problem" }
        """,
    )
    _run(path)
    p = Problem.objects.get(title="Shared Problem")
    assert p.appearances.count() == 2


@pytest.mark.django_db
def test_problems_replaced_on_rerun_when_listed(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: Day 1
            problems:
              - { label: A, title: P1 }
              - { label: B, title: P2 }
        """,
    )
    _run(path)
    path.write_text(
        textwrap.dedent(
            """
            problem_sets:
              - title: Day 1
                problems:
                  - { label: A, title: P1 }
                  - { label: B, title: P3 }   # P2 replaced by P3
            """
        )
    )
    _run(path)
    day1 = ProblemSet.objects.get(title="Day 1")
    titles = sorted(a.problem.title for a in day1.appearances.all())
    assert titles == ["P1", "P3"]
    # The orphaned Problem itself stays canonical (SolveRecords would survive).
    assert Problem.objects.filter(title="P2").exists()


@pytest.mark.django_db
def test_relabel_within_set_is_safe(tmp_path) -> None:
    """Swapping labels (A↔B) on the same set must not violate UNIQUE."""
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: Day 1
            problems:
              - { label: A, title: P1 }
              - { label: B, title: P2 }
        """,
    )
    _run(path)
    path.write_text(
        textwrap.dedent(
            """
            problem_sets:
              - title: Day 1
                problems:
                  - { label: B, title: P1 }
                  - { label: A, title: P2 }
            """
        )
    )
    _run(path)
    day1 = ProblemSet.objects.get(title="Day 1")
    by_title = {a.problem.title: a.label for a in day1.appearances.all()}
    assert by_title == {"P1": "B", "P2": "A"}


@pytest.mark.django_db
def test_invalid_tier_raises(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: Day 1
            problems:
              - { label: A, title: P1, tier: 99 }
        """,
    )
    with pytest.raises(CommandError, match="Invalid solved.ac tier"):
        _run(path)


# ---------- Categories M2M sync ----------


@pytest.mark.django_db
def test_categories_set_replaces_existing(tmp_path) -> None:
    Category.objects.create(short_name="japan", name="Japan")
    Category.objects.create(short_name="icpc", name="ICPC")

    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: Yokohama 2023
            categories: [japan, icpc]
        """,
    )
    _run(path)
    yk = ProblemSet.objects.get(title="Yokohama 2023")
    assert set(yk.categories.values_list("short_name", flat=True)) == {"japan", "icpc"}

    path.write_text(
        textwrap.dedent(
            """
            problem_sets:
              - title: Yokohama 2023
                categories: [icpc]
            """
        )
    )
    _run(path)
    yk.refresh_from_db()
    assert set(yk.categories.values_list("short_name", flat=True)) == {"icpc"}


# ---------- dry-run ----------


@pytest.mark.django_db
def test_dry_run_rolls_back(tmp_path) -> None:
    path = _write(
        tmp_path,
        """
        problem_sets:
          - title: NEVER COMMITTED
        """,
    )
    _run(path, dry_run=True)
    assert not ProblemSet.objects.filter(title="NEVER COMMITTED").exists()


# ---------- export round-trip ----------


@pytest.mark.django_db
def test_export_then_reimport_is_noop(tmp_path) -> None:
    """Round-trip: export current DB to YAML, reimport, no record changes."""
    path_in = _write(
        tmp_path,
        """
        categories:
          - { short_name: japan, name: Japan }
        problem_sets:
          - title: ICPC
            categories: [japan]
            children:
              - title: Yokohama 2023
                year: 2023
                problems:
                  - { label: A, title: P1, tier: 17 }
                  - { label: B, title: P2 }
        """,
    )
    _run(path_in)

    before = {
        "ps": list(ProblemSet.objects.values_list("title", "year").order_by("path")),
        "p": sorted(Problem.objects.values_list("title", "solved_ac_tier_manual")),
        "app": sorted(
            ProblemAppearance.objects.values_list("problem__title", "problem_set__title", "label")
        ),
    }

    out_path = tmp_path / "exported.yml"
    out = StringIO()
    err = StringIO()
    call_command("export_problemsets", "--to", str(out_path), stdout=out, stderr=err)

    _run(out_path)

    after = {
        "ps": list(ProblemSet.objects.values_list("title", "year").order_by("path")),
        "p": sorted(Problem.objects.values_list("title", "solved_ac_tier_manual")),
        "app": sorted(
            ProblemAppearance.objects.values_list("problem__title", "problem_set__title", "label")
        ),
    }
    assert before == after
