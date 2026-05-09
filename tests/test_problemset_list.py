"""View tests for ProblemSet list page (task 2.2, updated for v0.4 M2M)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import ProblemSet

from .factories import CategoryFactory


@pytest.mark.django_db
def test_list_anonymous_can_view(client) -> None:
    cat = CategoryFactory(short_name="ptz")
    root = ProblemSet.add_root(title="Camp")
    root.categories.add(cat)

    response = client.get(reverse("problemsets:list"))
    assert response.status_code == 200
    assert b"Camp" in response.content
    assert b"ptz" in response.content


@pytest.mark.django_db
def test_list_empty_renders_friendly_state(client) -> None:
    response = client.get(reverse("problemsets:list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "아직 등록된 set이 없습니다" in body


@pytest.mark.django_db
def test_list_shows_full_tree_unfiltered(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    summer = root.add_child(title="2024 Summer", year=2024)
    summer.add_child(title="Day 1", year=2024)

    response = client.get(reverse("problemsets:list"))
    body = response.content.decode()
    assert "Camp" in body
    assert "2024 Summer" in body
    assert "Day 1" in body


@pytest.mark.django_db
def test_list_filter_by_category_includes_descendants(client) -> None:
    """Filter by category attaches at the root; descendants appear via path-prefix."""
    ptz = CategoryFactory(short_name="ptz")
    cerc = CategoryFactory(short_name="cerc")
    ptz_root = ProblemSet.add_root(title="PTZ Camp")
    ptz_root.categories.add(ptz)
    ptz_root.add_child(title="PTZ Day 1")  # descendant — not directly in category

    cerc_root = ProblemSet.add_root(title="CERC Set")
    cerc_root.categories.add(cerc)

    response = client.get(reverse("problemsets:list"), {"category": "ptz"})
    body = response.content.decode()
    assert "PTZ Camp" in body
    assert "PTZ Day 1" in body  # descendant inherits via tree
    assert "CERC Set" not in body


@pytest.mark.django_db
def test_list_filter_legacy_source_param_still_works(client) -> None:
    """Back-compat: old `?source=` URLs (categories list page) still resolve."""
    ptz = CategoryFactory(short_name="ptz")
    root = ProblemSet.add_root(title="PTZ Camp")
    root.categories.add(ptz)

    response = client.get(reverse("problemsets:list"), {"source": "ptz"})
    assert response.status_code == 200
    assert b"PTZ Camp" in response.content


@pytest.mark.django_db
def test_list_filter_by_year_exact_via_range(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    root.add_child(title="2023 Summer", year=2023)
    root.add_child(title="2024 Summer", year=2024)

    response = client.get(
        reverse("problemsets:list"),
        {"year_from": "2024", "year_to": "2024"},
    )
    body = response.content.decode()
    assert "2024 Summer" in body
    assert "2023 Summer" not in body


@pytest.mark.django_db
def test_list_filter_by_year_range(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    root.add_child(title="A 2020", year=2020)
    root.add_child(title="A 2022", year=2022)
    root.add_child(title="A 2024", year=2024)

    response = client.get(
        reverse("problemsets:list"),
        {"year_from": "2021", "year_to": "2023"},
    )
    body = response.content.decode()
    assert "A 2022" in body
    assert "A 2020" not in body
    assert "A 2024" not in body


@pytest.mark.django_db
def test_list_filter_year_from_only(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    root.add_child(title="A 2020", year=2020)
    root.add_child(title="A 2024", year=2024)

    response = client.get(reverse("problemsets:list"), {"year_from": "2023"})
    body = response.content.decode()
    assert "A 2024" in body
    assert "A 2020" not in body


@pytest.mark.django_db
def test_list_filter_combined_category_and_year(client) -> None:
    ptz = CategoryFactory(short_name="ptz")
    cerc = CategoryFactory(short_name="cerc")
    root_ptz = ProblemSet.add_root(title="PTZ Camp")
    root_ptz.categories.add(ptz)
    root_ptz.add_child(title="PTZ 2024", year=2024)

    root_cerc = ProblemSet.add_root(title="CERC")
    root_cerc.categories.add(cerc)
    root_cerc.add_child(title="CERC 2024", year=2024)

    response = client.get(
        reverse("problemsets:list"),
        {"category": "ptz", "year_from": "2024", "year_to": "2024"},
    )
    body = response.content.decode()
    assert "PTZ 2024" in body
    assert "CERC 2024" not in body


@pytest.mark.django_db
def test_list_invalid_year_param_is_ignored(client) -> None:
    ProblemSet.add_root(title="Camp")
    response = client.get(reverse("problemsets:list"), {"year_from": "abc"})
    assert response.status_code == 200
    assert b"Camp" in response.content


@pytest.mark.django_db
def test_nav_links_to_list_from_home(client) -> None:
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert reverse("problemsets:list").encode() in response.content
