"""Step 4.3: comment upsert / delete endpoints + detail page integration."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.ratings.models import Comment, Rating

from .factories import (
    CommentFactory,
    ProblemSetRootFactory,
    RatingFactory,
    UserFactory,
)


def _comment_url(pset):
    return reverse("ratings:comment_upsert", args=[pset.pk])


def _comment_delete_url(pset):
    return reverse("ratings:comment_delete", args=[pset.pk])


# ---------- create / update ----------


@pytest.mark.django_db
def test_comment_create_requires_existing_rating(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)

    response = client.post(_comment_url(pset), {"body": "별점도 안 줬는데?"})
    assert response.status_code == 400
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_comment_create_after_rating(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=user, problem_set=pset, stars=4)
    client.force_login(user)

    response = client.post(_comment_url(pset), {"body": "좋은 set."})
    assert response.status_code == 200
    c = Comment.objects.get(rating__user=user, rating__problem_set=pset)
    assert c.body == "좋은 set."
    assert b"\xec\xa2\x8b\xec\x9d\x80 set." in response.content  # body echoed back


@pytest.mark.django_db
def test_comment_update_replaces_existing(client) -> None:
    user = UserFactory()
    rating = RatingFactory(user=user)
    CommentFactory(rating=rating, body="처음 코멘트")
    client.force_login(user)

    client.post(_comment_url(rating.problem_set), {"body": "수정된 코멘트"})
    c = Comment.objects.get(rating=rating)
    assert c.body == "수정된 코멘트"
    assert Comment.objects.count() == 1


@pytest.mark.django_db
def test_comment_empty_body_rejected(client) -> None:
    user = UserFactory()
    rating = RatingFactory(user=user)
    client.force_login(user)

    response = client.post(_comment_url(rating.problem_set), {"body": "   "})
    assert response.status_code == 400
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_comment_too_long_rejected(client) -> None:
    user = UserFactory()
    rating = RatingFactory(user=user)
    client.force_login(user)

    response = client.post(_comment_url(rating.problem_set), {"body": "x" * 301})
    assert response.status_code == 400
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_comment_requires_login(client) -> None:
    pset = ProblemSetRootFactory()
    response = client.post(_comment_url(pset), {"body": "hi"})
    assert response.status_code == 302
    assert "/accounts/login" in response.url
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_comment_get_method_not_allowed(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)
    response = client.get(_comment_url(pset))
    assert response.status_code == 405


# ---------- delete ----------


@pytest.mark.django_db
def test_comment_delete_removes_own(client) -> None:
    user = UserFactory()
    rating = RatingFactory(user=user)
    CommentFactory(rating=rating)
    client.force_login(user)

    response = client.post(_comment_delete_url(rating.problem_set))
    assert response.status_code == 200
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_comment_delete_only_affects_self(client) -> None:
    other = UserFactory()
    pset = ProblemSetRootFactory()
    other_rating = RatingFactory(user=other, problem_set=pset)
    CommentFactory(rating=other_rating, body="남의 코멘트")

    me = UserFactory()
    client.force_login(me)
    client.post(_comment_delete_url(pset))

    assert Comment.objects.filter(rating=other_rating).exists()


# ---------- detail page integration ----------


@pytest.mark.django_db
def test_detail_renders_comments_for_anonymous(client) -> None:
    pset = ProblemSetRootFactory()
    rater = UserFactory(nickname="alice")
    rating = RatingFactory(user=rater, problem_set=pset)
    CommentFactory(rating=rating, body="익명도 보임")

    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert f'id="comments-section-{pset.pk}"' in body
    assert "alice" in body
    assert "익명도 보임" in body
    # Anonymous: form not rendered, login link shown.
    assert _comment_url(pset) not in body
    assert "로그인" in body


@pytest.mark.django_db
def test_detail_authenticated_no_rating_shows_blocking_msg(client) -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    client.force_login(user)

    response = client.get(reverse("problemsets:detail", args=[pset.pk]))
    body = response.content.decode()
    assert "별점을 먼저 남겨야" in body
    # Form still hidden because no rating yet.
    assert _comment_url(pset) not in body


@pytest.mark.django_db
def test_detail_authenticated_with_rating_shows_form(client) -> None:
    user = UserFactory()
    rating = RatingFactory(user=user)
    client.force_login(user)

    response = client.get(reverse("problemsets:detail", args=[rating.problem_set.pk]))
    body = response.content.decode()
    assert _comment_url(rating.problem_set) in body
    assert "등록" in body  # button label when no comment yet


@pytest.mark.django_db
def test_detail_existing_comment_prefills_form_with_update_button(client) -> None:
    user = UserFactory()
    rating = RatingFactory(user=user)
    CommentFactory(rating=rating, body="기존 코멘트 본문")
    client.force_login(user)

    response = client.get(reverse("problemsets:detail", args=[rating.problem_set.pk]))
    body = response.content.decode()
    assert "기존 코멘트 본문" in body
    assert "수정" in body
    assert "삭제" in body
