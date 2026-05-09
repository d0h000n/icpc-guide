"""accounts views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


@never_cache
def home(request: HttpRequest) -> HttpResponse:
    """Landing page. Shows a greeting when the user is signed in."""
    return render(request, "accounts/home.html")


def healthz(request: HttpRequest) -> HttpResponse:
    """Liveness check for Fly. Intentionally does not touch the DB."""
    return HttpResponse("ok", content_type="text/plain")


@never_cache
@login_required
def me(request: HttpRequest) -> HttpResponse:
    """Minimal profile placeholder for step 0."""
    return render(request, "accounts/me.html")
