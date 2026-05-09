"""solving views — toggle solved state for a Problem (HTMX-driven)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.problemsets.models import Problem, ProblemSet

from .models import SolveRecord
from .services import subtree_problem_count, subtree_solved_count


@login_required
@require_POST
def toggle_solve(
    request: HttpRequest,
    problem_set_pk: int,
    problem_pk: int,
) -> HttpResponse:
    """Flip the current user's solved state for one Problem.

    Spec v0.3 §4.3.1 — "토글로 체크/해제". `problem_set_pk` identifies which
    page-side completion counter to refresh via OOB swap; the SolveRecord
    itself is keyed only by (user, problem), so a toggle is global to that
    Problem regardless of which set was clicked from.
    """
    problem = get_object_or_404(Problem, pk=problem_pk)
    pset = get_object_or_404(ProblemSet, pk=problem_set_pk)

    existing = SolveRecord.objects.filter(user=request.user, problem=problem).first()
    if existing is None:
        SolveRecord.objects.create(user=request.user, problem=problem)
        is_solved = True
    else:
        existing.delete()
        is_solved = False

    solved = subtree_solved_count(pset, request.user)
    total = subtree_problem_count(pset)

    return render(
        request,
        "solving/_toggle_response.html",
        {
            "problem": problem,
            "problem_set": pset,
            "is_solved": is_solved,
            "solved_count": solved,
            "total_count": total,
        },
    )
