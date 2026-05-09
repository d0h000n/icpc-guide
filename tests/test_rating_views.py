"""Step 4.2: rate/unrate endpoints + ProblemSet detail star widget."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.ratings.models import Rating

from .factories import (
    CommentFactory,
    ProblemSetRootFactory,
    RatingFactory,
    UserFactory,
)


def _rate_url(pset):
    return reverse("ratings:rate", args=[pset.pk])


def _unrate_url(pset):
    return reverse("ratings:unrate", args=[pset.pk])


# ---------- rate endpoint ----------


@pytest.mark.django_db
def test_rate_creates_when_unrated(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)

    response = client.post(_rate_url(pset), {"stars": "4"})
    assert response.status_code == 200
    rating = Rating.objects.get(user=user, problem_set=pset)
    assert rating.stars == 4
    assert b"\xed\x8f\x89\xea\xb7\xa0" in response.content  # "평균"


@pytest.mark.django_db
def test_rate_updates_existing_via_upsert(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=user, problem_set=pset, stars=2)
    client.force_login(user)

    response = client.post(_rate_url(pset), {"stars": "5"})
    assert response.status_code == 200
    assert Rating.objects.get(user=user, problem_set=pset).stars == 5
    assert Rating.objects.filter(user=user, problem_set=pset).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("bad", ["0", "6", "-1", "abc", ""])
def test_rate_rejects_out_of_range(client, bad) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)

    response = client.post(_rate_url(pset), {"stars": bad})
    assert response.status_code == 400
    assert not Rating.objects.filter(user=user, problem_set=pset).exists()


@pytest.mark.django_db
def test_rate_requires_login(client) -> None:
    pset = ProblemSetRootFactory()
    response = client.post(_rate_url(pset), {"stars": "3"})
    assert response.status_code == 302
    assert "/accounts/login" in response.url
    assert Rating.objects.count() == 0


@pytest.mark.django_db
def test_rate_get_method_not_allowed(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)
    response = client.get(_rate_url(pset))
    assert response.status_code == 405


# ---------- unrate endpoint ----------


@pytest.mark.django_db
def test_unrate_deletes_existing(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=user, problem_set=pset, stars=4)
    client.force_login(user)

    response = client.post(_unrate_url(pset))
    assert response.status_code == 200
    assert not Rating.objects.filter(user=user, problem_set=pset).exists()


@pytest.mark.django_db
def test_unrate_no_op_when_no_rating(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)
    response = client.post(_unrate_url(pset))
    assert response.status_code == 200


@pytest.mark.django_db
def test_unrate_cascades_comment(client) -> None:
    """Spec §4.5: deleting Rating also drops the attached Comment."""
    from apps.ratings.models import Comment

    user = UserFactory()
    pset = ProblemSetRootFactory()
    rating = RatingFactory(user=user, problem_set=pset)
    CommentFactory(rating=rating)
    assert Comment.objects.count() == 1

    client.force_login(user)
    client.post(_unrate_url(pset))

    assert not Rating.objects.filter(user=user, problem_set=pset).exists()
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_unrate_only_affects_self(client) -> None:
    other = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=other, problem_set=pset, stars=4)

    me = UserFactory()
    client.force_login(me)
    client.post(_unrate_url(pset))

    # Other user's rating untouched.
    assert Rating.objects.filter(user=other, problem_set=pset).exists()


# ---------- aggregate display ----------


@pytest.mark.django_db
def test_rate_response_shows_aggregate(client) -> None:
    user_a = UserFactory()
    user_b = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=user_b, problem_set=pset, stars=5)

    client.force_login(user_a)
    response = client.post(_rate_url(pset), {"stars": "3"})
    body = response.content.decode()
    assert "2명 평가" in body
    # Average is 4.0 — formatted with 1 decimal.
    assert "4.0" in body


# ---------- detail page integration ----------


@pytest.mark.django_db
def test_detail_renders_widget_for_authenticated(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=user, problem_set=pset, stars=4)

    client.force_login(user)
    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert f'id="rating-widget-{pset.pk}"' in body
    assert _rate_url(pset) in body
    assert "내 별점: 4점" in body


@pytest.mark.django_db
def test_detail_widget_for_anonymous_shows_average_only(client) -> None:
    pset = ProblemSetRootFactory()
    rater = UserFactory()
    Rating.objects.create(user=rater, problem_set=pset, stars=5)

    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    # Anonymous: widget rendered with stars but without rate buttons or unrate.
    assert f'id="rating-widget-{pset.pk}"' in body
    assert _rate_url(pset) not in body
    assert "1명 평가" in body
