"""categories views — public category catalog (Guest OK)."""

from __future__ import annotations

from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Category


@never_cache
@require_safe
def category_list(request: HttpRequest) -> HttpResponse:
    """List of all Categories with attached ProblemSet counts. Guest accessible."""
    categories = Category.objects.annotate(
        problem_set_count=Count("problem_sets"),
    ).order_by("short_name")

    return render(
        request,
        "categories/list.html",
        {"categories": categories},
    )
