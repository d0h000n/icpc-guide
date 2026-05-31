"""Tests for ProblemSetAdmin's bulk-paste helpers.

These exercise the admin helpers (`_apply_bulk_problems`, `_apply_bulk_children`)
directly with a stub form, so we get coverage without rebuilding the entire
movenodeform formset boilerplate in tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.problemsets.admin import ProblemSetAdmin
from apps.problemsets.bulk import parse_children_text, parse_problems_text
from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet

from .factories import ProblemSetRootFactory

pytestmark = pytest.mark.django_db


def _request():
    """Plain request with messages storage set up so admin helpers can call messages.*."""
    request = RequestFactory().post("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _form(instance: ProblemSet, *, problems: str = "", children: str = ""):
    return SimpleNamespace(
        instance=instance,
        cleaned_data={
            "bulk_problems": parse_problems_text(problems),
            "bulk_children": parse_children_text(children),
        },
    )


@pytest.fixture
def admin_obj() -> ProblemSetAdmin:
    return ProblemSetAdmin(ProblemSet, AdminSite())


def test_bulk_problems_creates_appearances_and_problems(admin_obj):
    pset = ProblemSetRootFactory(title="Yokohama 2022")
    raw = "A | Alpha | https://a.example | 12\nB | Beta | | 7"
    admin_obj._apply_bulk_problems(_request(), _form(pset, problems=raw))

    apps = list(pset.appearances.order_by("label"))
    assert [a.label for a in apps] == ["A", "B"]
    assert apps[0].problem.title == "Alpha"
    assert apps[0].problem.external_url == "https://a.example"
    assert apps[0].problem.solved_ac_tier_manual == 12
    assert apps[1].problem.solved_ac_tier_manual == 7


def test_bulk_problems_reuses_existing_problem_by_title(admin_obj):
    pset = ProblemSetRootFactory(title="Yokohama 2022")
    other = ProblemSetRootFactory(title="PTZ Day 1")
    existing = Problem.objects.create(
        title="Shared", external_url="https://orig", solved_ac_tier_manual=20
    )
    ProblemAppearance.objects.create(problem=existing, problem_set=other, label="X")

    admin_obj._apply_bulk_problems(_request(), _form(pset, problems="A | Shared | https://new | 5"))

    # Reused, not duplicated.
    assert Problem.objects.filter(title="Shared").count() == 1
    # And its original fields stay (get_or_create only sets defaults on create).
    existing.refresh_from_db()
    assert existing.external_url == "https://orig"
    assert existing.solved_ac_tier_manual == 20
    # New appearance landed on `pset`.
    assert pset.appearances.filter(label="A", problem=existing).exists()


def test_bulk_problems_label_clash_skipped(admin_obj):
    pset = ProblemSetRootFactory(title="Yokohama 2022")
    p_old = Problem.objects.create(title="OldTitle")
    ProblemAppearance.objects.create(problem=p_old, problem_set=pset, label="A")

    admin_obj._apply_bulk_problems(_request(), _form(pset, problems="A | NewTitle"))

    # Existing appearance untouched, no new Problem created.
    assert pset.appearances.get(label="A").problem == p_old
    assert not Problem.objects.filter(title="NewTitle").exists()


def test_bulk_problems_duplicate_label_within_input_skipped(admin_obj):
    pset = ProblemSetRootFactory(title="Yokohama 2022")
    admin_obj._apply_bulk_problems(_request(), _form(pset, problems="A | Alpha\nA | Different"))

    apps = list(pset.appearances.all())
    assert len(apps) == 1
    assert apps[0].problem.title == "Alpha"
    assert not Problem.objects.filter(title="Different").exists()


def test_bulk_problems_existing_same_problem_noop(admin_obj):
    """Re-adding the exact same (label, problem) noop's silently."""
    pset = ProblemSetRootFactory(title="Yokohama 2022")
    Problem.objects.create(title="Alpha")
    admin_obj._apply_bulk_problems(_request(), _form(pset, problems="A | Alpha"))
    admin_obj._apply_bulk_problems(_request(), _form(pset, problems="A | Alpha"))
    assert pset.appearances.count() == 1


def test_bulk_children_creates_under_parent(admin_obj):
    parent = ProblemSetRootFactory(title="Yokohama")
    raw = "Yokohama 2022 | 2022\nYokohama 2023 | 2023\nYokohama 2024"
    admin_obj._apply_bulk_children(_request(), _form(parent, children=raw))

    children = list(parent.get_children().order_by("path"))
    assert [c.title for c in children] == ["Yokohama 2022", "Yokohama 2023", "Yokohama 2024"]
    assert children[0].year == 2022
    assert children[2].year is None


def test_bulk_children_skips_existing_title(admin_obj):
    parent = ProblemSetRootFactory(title="Yokohama")
    parent.add_child(title="Yokohama 2022", year=2022)

    admin_obj._apply_bulk_children(
        _request(), _form(parent, children="Yokohama 2022 | 2022\nYokohama 2023 | 2023")
    )

    titles = [c.title for c in parent.get_children().order_by("path")]
    assert titles == ["Yokohama 2022", "Yokohama 2023"]


def test_bulk_problems_empty_no_op(admin_obj):
    pset = ProblemSetRootFactory(title="Y")
    admin_obj._apply_bulk_problems(_request(), _form(pset, problems=""))
    assert pset.appearances.count() == 0


def test_bulk_children_empty_no_op(admin_obj):
    parent = ProblemSetRootFactory(title="Y")
    admin_obj._apply_bulk_children(_request(), _form(parent, children=""))
    assert parent.get_children().count() == 0
