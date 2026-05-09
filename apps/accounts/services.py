"""Helpers for profile pages — user-level aggregations.

Pulled out of views so the same shape can be rendered for either the owner's
me-page or a public profile (§5.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count

from apps.problemsets.models import ProblemSet
from apps.ratings.models import Comment, Rating
from apps.solving.models import SolveRecord


@dataclass(frozen=True)
class ProfileStats:
    solved_count: int
    rating_count: int
    comment_count: int
    solved_set_titles: list[str]


def stats_for(user) -> ProfileStats:
    """Public-facing aggregate counts for a user's profile.

    `solved_set_titles` is the list of leaf ProblemSet titles where the user
    has at least one SolveRecord on a Problem appearing in that set.
    """
    solved_count = SolveRecord.objects.filter(user=user).count()
    rating_count = Rating.objects.filter(user=user).count()
    comment_count = Comment.objects.filter(rating__user=user).count()
    set_titles = list(
        ProblemSet.objects.filter(
            appearances__problem__solve_records__user=user,
        )
        .annotate(_n=Count("id"))
        .order_by("title")
        .values_list("title", flat=True)
        .distinct()
    )
    return ProfileStats(
        solved_count=solved_count,
        rating_count=rating_count,
        comment_count=comment_count,
        solved_set_titles=set_titles,
    )
