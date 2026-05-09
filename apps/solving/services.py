"""Aggregation helpers for SolveRecord-driven displays.

Implements the "내부 노드 완주율" rule from architecture.md §4.3:
   "자식 path prefix 쿼리 1회 + Python 측 합산"

For a ProblemSet, completion = (distinct Problems the user solved within the
subtree) / (distinct Problems appearing within the subtree).

distinct() handles the v0.3 N—M case (same Problem in multiple sets/appearances)
without double-counting.
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from apps.problemsets.models import Problem, ProblemSet

from .models import SolveRecord


def subtree_problem_count(pset: ProblemSet) -> int:
    """Distinct Problems appearing in `pset`'s subtree (itself + every descendant)."""
    return (
        Problem.objects.filter(
            appearances__problem_set__path__startswith=pset.path,
        )
        .distinct()
        .count()
    )


def subtree_solved_count(pset: ProblemSet, user) -> int:
    """Distinct Problems in `pset`'s subtree the user has solved."""
    if not user.is_authenticated or isinstance(user, AnonymousUser):
        return 0
    return (
        SolveRecord.objects.filter(
            user=user,
            problem__appearances__problem_set__path__startswith=pset.path,
        )
        .values("problem")
        .distinct()
        .count()
    )


def completion_for(pset: ProblemSet, user) -> tuple[int, int]:
    """(solved, total) for one ProblemSet's subtree."""
    return subtree_solved_count(pset, user), subtree_problem_count(pset)
