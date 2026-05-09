"""View tests for Category list page (task 2.3, renamed in 3.6.4)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import ProblemSet

from .factories import CategoryFactory


@pytest.mark.django_db
def test_category_list_anonymous_can_view(client) -> None:
    CategoryFactory(short_name="PTZ", name="PTZ Camp")
    CategoryFactory(short_name="CERC", name="CERC")

    response = client.get(reverse("categories:list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "PTZ" in body
    assert "CERC" in body


@pytest.mark.django_db
def test_category_list_empty_state(client) -> None:
    response = client.get(reverse("categories:list"))
    assert response.status_code == 200
    assert "아직 등록된 카테고리가 없습니다" in response.content.decode()


@pytest.mark.django_db
def test_category_list_shows_problem_set_count(client) -> None:
    cat = CategoryFactory(short_name="PTZ")
    p1 = ProblemSet.add_root(title="Camp 1")
    p2 = ProblemSet.add_root(title="Camp 2")
    p1.categories.add(cat)
    p2.categories.add(cat)

    response = client.get(reverse("categories:list"))
    body = response.content.decode()
    assert "ProblemSet 2개" in body


@pytest.mark.django_db
def test_category_list_links_to_filtered_problem_sets(client) -> None:
    CategoryFactory(short_name="PTZ")
    response = client.get(reverse("categories:list"))
    body = response.content.decode()
    expected_link = f"{reverse('problemsets:list')}?category=PTZ"
    assert expected_link in body


@pytest.mark.django_db
def test_nav_links_to_categories(client) -> None:
    response = client.get(reverse("home"))
    assert reverse("categories:list").encode() in response.content
