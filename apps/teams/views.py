"""Team views — list / create / detail / member management. Spec §4.4, §4.6."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from .forms import TeamCreateForm
from .models import Team, TeamMember, TeamMemberRole, TeamVisibility


def _is_member(user, team: Team) -> bool:
    if not user.is_authenticated:
        return False
    return team.memberships.filter(user=user).exists()


def _is_owner(user, team: Team) -> bool:
    if not user.is_authenticated:
        return False
    return team.owner_id == user.pk


@never_cache
def team_list(request: HttpRequest) -> HttpResponse:
    """S5 — my teams (auth) + public teams browser (anyone)."""
    my_teams: list[Team] = []
    if request.user.is_authenticated:
        my_teams = list(
            Team.objects.filter(memberships__user=request.user).order_by("-updated_at").distinct()
        )
    public_teams = list(
        Team.objects.filter(visibility=TeamVisibility.PUBLIC)
        .order_by("-updated_at")
        .exclude(id__in=[t.id for t in my_teams])
    )
    return render(
        request,
        "teams/list.html",
        {"my_teams": my_teams, "public_teams": public_teams},
    )


@never_cache
@login_required
def team_create(request: HttpRequest) -> HttpResponse:
    """S5 — new team. Creator becomes owner + first member."""
    if request.method == "POST":
        form = TeamCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                team: Team = form.save(commit=False)
                team.owner = request.user
                team.save()
                TeamMember.objects.create(team=team, user=request.user, role=TeamMemberRole.OWNER)
            messages.success(request, "팀이 생성됐습니다.")
            return redirect(reverse("teams:detail", args=[team.slug]))
    else:
        form = TeamCreateForm()

    return render(request, "teams/create.html", {"form": form})


@never_cache
def team_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """S6 — team detail. Spec §4.6.2/3:
    - public: anyone may view.
    - private: members only; non-members get 404 (existence not leaked).
    """
    team = get_object_or_404(Team.objects.select_related("owner"), slug=slug)
    is_member = _is_member(request.user, team)
    is_owner = _is_owner(request.user, team)
    if team.visibility == TeamVisibility.PRIVATE and not is_member:
        raise Http404("Team not found")

    members = list(team.memberships.select_related("user").order_by("-role", "joined_at"))

    return render(
        request,
        "teams/detail.html",
        {
            "team": team,
            "members": members,
            "is_member": is_member,
            "is_owner": is_owner,
        },
    )
