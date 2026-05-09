"""Rating + Comment endpoints (HTMX-driven). Spec §4.5."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.problemsets.models import ProblemSet

from .models import Comment, Rating
from .services import aggregate_for, my_rating


def _render_widget(request: HttpRequest, pset: ProblemSet) -> HttpResponse:
    avg, count = aggregate_for(pset)
    return render(
        request,
        "ratings/_widget.html",
        {
            "problem_set": pset,
            "my_rating": my_rating(pset, request.user),
            "avg_stars": avg,
            "rating_count": count,
            "stars_range": range(1, 6),
        },
    )


@never_cache
@login_required
@require_POST
def rate(request: HttpRequest, problem_set_pk: int) -> HttpResponse:
    """UPSERT the current user's Rating on a ProblemSet (1–5)."""
    pset = get_object_or_404(ProblemSet, pk=problem_set_pk)
    raw = request.POST.get("stars", "").strip()
    if not raw.isdigit():
        return HttpResponseBadRequest("stars must be 1–5")
    stars = int(raw)
    if not 1 <= stars <= 5:
        return HttpResponseBadRequest("stars must be 1–5")
    Rating.objects.update_or_create(
        user=request.user,
        problem_set=pset,
        defaults={"stars": stars},
    )
    return _render_widget(request, pset)


@never_cache
@login_required
@require_POST
def unrate(request: HttpRequest, problem_set_pk: int) -> HttpResponse:
    """Remove the current user's Rating (and any attached Comment via cascade)."""
    pset = get_object_or_404(ProblemSet, pk=problem_set_pk)
    Rating.objects.filter(user=request.user, problem_set=pset).delete()
    return _render_widget(request, pset)


# --- Comments (spec §4.5.2) -------------------------------------------------


def _render_comments(request: HttpRequest, pset: ProblemSet) -> HttpResponse:
    comments = (
        Comment.objects.filter(rating__problem_set=pset)
        .select_related("rating__user")
        .order_by("-updated_at")
    )
    my_comment = None
    has_rating = False
    if request.user.is_authenticated:
        my_comment = comments.filter(rating__user=request.user).first()
        has_rating = Rating.objects.filter(user=request.user, problem_set=pset).exists()
    return render(
        request,
        "ratings/_comments_section.html",
        {
            "problem_set": pset,
            "comments": comments,
            "my_comment": my_comment,
            "has_rating": has_rating,
        },
    )


@never_cache
@login_required
@require_POST
def comment_upsert(request: HttpRequest, problem_set_pk: int) -> HttpResponse:
    """Create or update the current user's Comment on a ProblemSet.

    Spec §4.5: requires an existing Rating; body 1–300 chars.
    """
    pset = get_object_or_404(ProblemSet, pk=problem_set_pk)
    body = (request.POST.get("body") or "").strip()
    if not body:
        return HttpResponseBadRequest("body required")
    if len(body) > 300:
        return HttpResponseBadRequest("body too long (max 300)")

    rating = Rating.objects.filter(user=request.user, problem_set=pset).first()
    if rating is None:
        return HttpResponseBadRequest("rate the set before commenting")

    Comment.objects.update_or_create(rating=rating, defaults={"body": body})
    return _render_comments(request, pset)


@never_cache
@login_required
@require_POST
def comment_delete(request: HttpRequest, problem_set_pk: int) -> HttpResponse:
    pset = get_object_or_404(ProblemSet, pk=problem_set_pk)
    Comment.objects.filter(rating__user=request.user, rating__problem_set=pset).delete()
    return _render_comments(request, pset)


# --- Raters list (spec §4.5.1) ----------------------------------------------


@never_cache
@login_required
@require_safe
def raters_list(request: HttpRequest, problem_set_pk: int) -> HttpResponse:
    """Modal contents: who rated this set, and with how many stars.

    Login-only (Guest sees aggregate avg only). Returns an HTMX-loadable
    fragment that renders a DaisyUI-style modal.
    """
    pset = get_object_or_404(ProblemSet, pk=problem_set_pk)
    ratings = list(
        Rating.objects.filter(problem_set=pset)
        .select_related("user")
        .order_by("-stars", "user__nickname")
    )
    # Pre-compute the "filled / empty" star iterators per row so the template
    # can render bars without a custom filter.
    for r in ratings:
        r.stars_filled = range(r.stars)
        r.stars_empty = range(5 - r.stars)
    return render(
        request,
        "ratings/_raters_modal.html",
        {"problem_set": pset, "ratings": ratings},
    )
