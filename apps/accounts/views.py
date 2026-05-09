"""accounts views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from .forms import ProfileEditForm
from .models import ProfileVisibility, User
from .services import stats_for


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
    """Owner's own profile page (마이페이지) — edit form + stats. Spec §4.6.1."""
    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "프로필이 저장됐습니다.")
            return redirect(reverse("accounts:me"))
    else:
        form = ProfileEditForm(instance=request.user)

    return render(
        request,
        "accounts/me.html",
        {
            "form": form,
            "stats": stats_for(request.user),
        },
    )


@never_cache
def profile(request: HttpRequest, nickname: str) -> HttpResponse:
    """Public profile page at /u/<nickname>/. Spec §4.6.

    - Owner: full info + edit link.
    - Other → public profile: full info (read-only).
    - Other → private profile: nickname only + 비공개 안내.
    """
    target = get_object_or_404(User, nickname=nickname)
    is_owner = request.user.is_authenticated and request.user.pk == target.pk
    is_public = target.profile_visibility == ProfileVisibility.PUBLIC

    show_full = is_owner or is_public
    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": target,
            "is_owner": is_owner,
            "is_public": is_public,
            "show_full": show_full,
            "stats": stats_for(target) if show_full else None,
        },
    )
