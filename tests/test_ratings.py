"""Step 4.1: Rating + Comment model tests."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.ratings.models import Comment, Rating

from .factories import (
    CommentFactory,
    ProblemSetRootFactory,
    RatingFactory,
    UserFactory,
)

# ---------- Rating ----------


@pytest.mark.django_db
def test_rating_basic_create() -> None:
    rating = RatingFactory(stars=4)
    assert rating.stars == 4
    assert rating.created_at is not None
    assert rating.updated_at is not None


@pytest.mark.django_db
def test_rating_unique_per_user_problem_set() -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    Rating.objects.create(user=user, problem_set=pset, stars=3)
    with pytest.raises(IntegrityError):
        Rating.objects.create(user=user, problem_set=pset, stars=5)


@pytest.mark.django_db
def test_rating_same_user_different_set_allowed() -> None:
    user = UserFactory()
    s1 = ProblemSetRootFactory()
    s2 = ProblemSetRootFactory()
    Rating.objects.create(user=user, problem_set=s1, stars=3)
    Rating.objects.create(user=user, problem_set=s2, stars=4)
    assert Rating.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_rating_stars_db_check_rejects_zero() -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    with pytest.raises(IntegrityError):
        Rating.objects.create(user=user, problem_set=pset, stars=0)


@pytest.mark.django_db
def test_rating_stars_db_check_rejects_six() -> None:
    user = UserFactory()
    pset = ProblemSetRootFactory()
    with pytest.raises(IntegrityError):
        Rating.objects.create(user=user, problem_set=pset, stars=6)


@pytest.mark.django_db
def test_rating_stars_form_validators_match_db() -> None:
    """full_clean() catches out-of-range before hitting DB (admin-form path)."""
    user = UserFactory()
    pset = ProblemSetRootFactory()
    rating = Rating(user=user, problem_set=pset, stars=7)
    with pytest.raises(ValidationError):
        rating.full_clean()


# ---------- Comment ----------


@pytest.mark.django_db
def test_comment_attaches_to_rating() -> None:
    rating = RatingFactory()
    comment = Comment.objects.create(rating=rating, body="좋은 set!")
    assert comment.rating == rating
    assert rating.comment == comment


@pytest.mark.django_db
def test_comment_one_to_one_with_rating() -> None:
    rating = RatingFactory()
    Comment.objects.create(rating=rating, body="first")
    with pytest.raises(IntegrityError):
        Comment.objects.create(rating=rating, body="second")


@pytest.mark.django_db
def test_comment_cascade_deletes_with_rating() -> None:
    rating = RatingFactory()
    CommentFactory(rating=rating)
    rating.delete()
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_comment_body_max_300_chars() -> None:
    rating = RatingFactory()
    c = Comment(rating=rating, body="x" * 301)
    with pytest.raises(ValidationError):
        c.full_clean()
