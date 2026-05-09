"""Rating aggregation helpers (avg, count) used by views + templates."""

from __future__ import annotations

from django.db.models import Avg, Count

from apps.problemsets.models import ProblemSet

from .models import Rating


def aggregate_for(problem_set: ProblemSet) -> tuple[float, int]:
    """Return (avg_stars, rating_count) for one ProblemSet. avg=0 if no ratings."""
    agg = Rating.objects.filter(problem_set=problem_set).aggregate(
        avg=Avg("stars"),
        count=Count("id"),
    )
    return (agg["avg"] or 0.0, agg["count"] or 0)


def my_rating(problem_set: ProblemSet, user) -> Rating | None:
    """The current user's Rating on a ProblemSet, or None."""
    if not user.is_authenticated:
        return None
    return Rating.objects.filter(user=user, problem_set=problem_set).first()
