"""Step 4.4: raters list modal (spec §4.5.1, login-only)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.ratings.models import Rating

from .factories import (
    ProblemSetRootFactory,
    UserFactory,
)


def _raters_url(pset):
    return reverse("ratings:raters", args=[pset.pk])


@pytest.mark.django_db
def test_raters_requires_login(client) -> None:
    pset = ProblemSetRootFactory()
    response = client.get(_raters_url(pset))
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_raters_post_method_not_allowed(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)
    response = client.post(_raters_url(pset))
    assert response.status_code == 405


@pytest.mark.django_db
def test_raters_lists_all_ratings_with_nicknames_and_stars(client) -> None:
    pset = ProblemSetRootFactory()
    alice = UserFactory(nickname="alice")
    bob = UserFactory(nickname="bob")
    Rating.objects.create(user=alice, problem_set=pset, stars=5)
    Rating.objects.create(user=bob, problem_set=pset, stars=3)

    me = UserFactory()
    client.force_login(me)
    response = client.get(_raters_url(pset))
    body = response.content.decode()
    assert response.status_code == 200
    assert "alice" in body
    assert "bob" in body
    assert "평가자 목록 (2)" in body
    assert pset.title in body


@pytest.mark.django_db
def test_raters_sorted_by_stars_desc_then_nickname(client) -> None:
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=UserFactory(nickname="alice"), problem_set=pset, stars=3)
    Rating.objects.create(user=UserFactory(nickname="bob"), problem_set=pset, stars=5)
    Rating.objects.create(user=UserFactory(nickname="carol"), problem_set=pset, stars=5)

    me = UserFactory()
    client.force_login(me)
    body = client.get(_raters_url(pset)).content.decode()
    bob_idx = body.find("bob")
    carol_idx = body.find("carol")
    alice_idx = body.find("alice")
    # bob (5) and carol (5) appear before alice (3); within same star count,
    # alphabetical → bob before carol.
    assert bob_idx < carol_idx < alice_idx


@pytest.mark.django_db
def test_raters_empty_state(client) -> None:
    pset = ProblemSetRootFactory()
    me = UserFactory()
    client.force_login(me)
    response = client.get(_raters_url(pset))
    body = response.content.decode()
    assert response.status_code == 200
    assert "아직 평가가 없습니다" in body


@pytest.mark.django_db
def test_raters_404_for_missing_set(client) -> None:
    me = UserFactory()
    client.force_login(me)
    response = client.get(reverse("ratings:raters", args=[9999]))
    assert response.status_code == 404


# ---------- detail page integration ----------


@pytest.mark.django_db
def test_detail_authenticated_with_ratings_shows_button(client) -> None:
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=UserFactory(), problem_set=pset, stars=4)

    me = UserFactory()
    client.force_login(me)
    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    assert _raters_url(pset) in body
    assert "평가자 보기" in body


@pytest.mark.django_db
def test_detail_anonymous_no_button(client) -> None:
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=UserFactory(), problem_set=pset, stars=4)

    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    # Anonymous users see the aggregate but not the raters button.
    assert _raters_url(pset) not in body
    assert "평가자 보기" not in body


@pytest.mark.django_db
def test_detail_no_ratings_no_button(client) -> None:
    pset = ProblemSetRootFactory()
    me = UserFactory()
    client.force_login(me)
    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    assert _raters_url(pset) not in body
