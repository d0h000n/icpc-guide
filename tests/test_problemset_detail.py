"""View tests for ProblemSet detail page (task 2.1, updated for v0.4 M2M)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet

from .factories import CategoryFactory


@pytest.mark.django_db
def test_detail_404_for_missing(client) -> None:
    response = client.get(reverse("problemsets:detail", args=[9999]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_anonymous_can_view_leaf(client) -> None:
    cat = CategoryFactory(short_name="ptz")
    leaf = ProblemSet.add_root(title="Day 1", year=2024)
    leaf.categories.add(cat)
    p1 = Problem.objects.create(title="Easy")
    p2 = Problem.objects.create(title="Hard")
    ProblemAppearance.objects.create(problem=p1, problem_set=leaf, order_index=1, label="A")
    ProblemAppearance.objects.create(problem=p2, problem_set=leaf, order_index=2, label="B")

    response = client.get(reverse("problemsets:detail", args=[leaf.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Day 1" in body
    assert "ptz" in body
    assert "Easy" in body
    assert "Hard" in body
    assert "문제 목록" in body
    assert "하위 set" not in body


@pytest.mark.django_db
def test_detail_anonymous_can_view_internal_node(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    child_a = root.add_child(title="2024 Summer", year=2024)
    root.add_child(title="2024 Winter", year=2024)

    response = client.get(reverse("problemsets:detail", args=[root.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Camp" in body
    assert "2024 Summer" in body
    assert "2024 Winter" in body
    assert "하위 set" in body
    assert "문제 목록" not in body
    assert reverse("problemsets:detail", args=[child_a.pk]) in body


@pytest.mark.django_db
def test_detail_breadcrumb_includes_ancestors(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    mid = root.add_child(title="2024 Summer", year=2024)
    leaf = mid.add_child(title="Day 1", year=2024)

    response = client.get(reverse("problemsets:detail", args=[leaf.pk]))
    body = response.content.decode()
    assert reverse("problemsets:detail", args=[root.pk]) in body
    assert reverse("problemsets:detail", args=[mid.pk]) in body
    assert "Camp" in body
    assert "2024 Summer" in body


@pytest.mark.django_db
def test_detail_inherits_categories_from_ancestors(client) -> None:
    """A descendant ProblemSet shows categories tagged on its ancestors."""
    cat = CategoryFactory(short_name="japan", name="Japan")
    root = ProblemSet.add_root(title="ICPC")
    root.categories.add(cat)
    leaf = root.add_child(title="Yokohama 2023", year=2023)

    response = client.get(reverse("problemsets:detail", args=[leaf.pk]))
    body = response.content.decode()
    assert "japan" in body  # inherited badge from root
