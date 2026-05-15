"""Team views — list / create / detail / member management. Spec §4.4, §4.6."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import TeamCreateForm, TeamEditForm
from .models import (
    Team,
    TeamInvite,
    TeamInviteStatus,
    TeamMember,
    TeamMemberRole,
    TeamVisibility,
)


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


def _require_owner(user, team: Team) -> None:
    if not _is_owner(user, team):
        raise PermissionDenied("Only the team owner can do this.")


@never_cache
@login_required
def team_edit(request: HttpRequest, slug: str) -> HttpResponse:
    """Owner-only metadata edit. Spec §4.4.1."""
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request.user, team)
    if request.method == "POST":
        form = TeamEditForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, "팀 정보가 저장됐습니다.")
            return redirect(reverse("teams:detail", args=[team.slug]))
    else:
        form = TeamEditForm(instance=team)
    return render(request, "teams/edit.html", {"team": team, "form": form})


@never_cache
@login_required
@require_POST
def member_remove(request: HttpRequest, slug: str, member_id: int) -> HttpResponse:
    """Owner removes a non-owner member. Spec §4.4.1."""
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request.user, team)
    member = get_object_or_404(TeamMember, team=team, pk=member_id)
    if member.user_id == team.owner_id:
        messages.error(request, "owner는 직접 제거할 수 없습니다. owner 양도 후 진행하세요.")
        return redirect(reverse("teams:detail", args=[team.slug]))
    member.delete()
    messages.success(request, f"{member.user.nickname} 멤버를 제거했습니다.")
    return redirect(reverse("teams:detail", args=[team.slug]))


@never_cache
@login_required
@require_POST
def transfer_ownership(request: HttpRequest, slug: str) -> HttpResponse:
    """Owner hands the team over to another existing member. Spec §4.4.1."""
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request.user, team)

    new_owner_member_id = request.POST.get("new_owner_member_id", "").strip()
    if not new_owner_member_id.isdigit():
        messages.error(request, "양도할 멤버를 선택하세요.")
        return redirect(reverse("teams:detail", args=[team.slug]))

    new_membership = get_object_or_404(TeamMember, team=team, pk=int(new_owner_member_id))
    if new_membership.user_id == team.owner_id:
        messages.error(request, "이미 owner인 멤버입니다.")
        return redirect(reverse("teams:detail", args=[team.slug]))

    with transaction.atomic():
        old_membership = TeamMember.objects.get(team=team, user=team.owner)
        old_membership.role = TeamMemberRole.MEMBER
        old_membership.save(update_fields=["role"])

        new_membership.role = TeamMemberRole.OWNER
        new_membership.save(update_fields=["role"])

        team.owner = new_membership.user
        team.save(update_fields=["owner", "updated_at"])

    messages.success(request, f"owner를 {new_membership.user.nickname}에게 양도했습니다.")
    return redirect(reverse("teams:detail", args=[team.slug]))


# --- Invites (spec §4.4.2) --------------------------------------------------


@never_cache
@login_required
@require_POST
def invite_create(request: HttpRequest, slug: str) -> HttpResponse:
    """Owner mints a new invite token (auto-generated, default no expiry).

    Spec §4.4.2: owner generates a link with token. Expiry is optional in V1
    — admin can revoke instead.
    """
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request.user, team)
    TeamInvite.objects.create(team=team, invited_by=request.user)
    return redirect(reverse("teams:detail", args=[team.slug]) + "#invites")


@never_cache
@login_required
@require_POST
def invite_revoke(request: HttpRequest, slug: str, invite_id: int) -> HttpResponse:
    team = get_object_or_404(Team, slug=slug)
    _require_owner(request.user, team)
    invite = get_object_or_404(TeamInvite, team=team, pk=invite_id)
    invite.status = TeamInviteStatus.REVOKED
    invite.save(update_fields=["status"])
    return redirect(reverse("teams:detail", args=[team.slug]) + "#invites")


@never_cache
@login_required
def invite_accept(request: HttpRequest, token: str) -> HttpResponse:
    """Anyone with a pending invite token can join. POST confirms.

    GET shows a one-page confirmation. Spec §4.4.2.
    """
    from django.utils import timezone

    invite = get_object_or_404(TeamInvite.objects.select_related("team"), token=token)
    expired = invite.expires_at is not None and invite.expires_at < timezone.now()

    if invite.status == TeamInviteStatus.ACCEPTED:
        # Already used → if they're a member, fine; otherwise show error.
        return render(
            request,
            "teams/invite_accept.html",
            {"invite": invite, "already_used": True},
        )
    if invite.status == TeamInviteStatus.REVOKED or expired:
        return render(
            request,
            "teams/invite_accept.html",
            {"invite": invite, "expired_or_revoked": True, "expired": expired},
        )

    if request.method == "POST":
        team = invite.team
        if team.memberships.filter(user=request.user).exists():
            return redirect(reverse("teams:detail", args=[team.slug]))
        if team.memberships.count() >= Team.MAX_MEMBERS:
            return render(
                request,
                "teams/invite_accept.html",
                {"invite": invite, "team_full": True},
            )
        with transaction.atomic():
            TeamMember.objects.create(team=team, user=request.user, role=TeamMemberRole.MEMBER)
            invite.status = TeamInviteStatus.ACCEPTED
            invite.invitee_user = request.user
            invite.accepted_at = timezone.now()
            invite.save(update_fields=["status", "invitee_user", "accepted_at"])
        messages.success(request, f"'{team.name}' 팀에 합류했습니다.")
        return redirect(reverse("teams:detail", args=[team.slug]))

    return render(request, "teams/invite_accept.html", {"invite": invite})


@never_cache
@login_required
@require_POST
def leave_team(request: HttpRequest, slug: str) -> HttpResponse:
    """Member voluntarily leaves the team. Owner must transfer first."""
    team = get_object_or_404(Team, slug=slug)
    if _is_owner(request.user, team):
        messages.error(request, "owner는 먼저 다른 멤버에게 양도한 뒤 탈퇴할 수 있습니다.")
        return redirect(reverse("teams:detail", args=[team.slug]))

    membership = TeamMember.objects.filter(team=team, user=request.user).first()
    if membership is None:
        raise Http404("not a member")
    membership.delete()
    messages.success(request, f"'{team.name}' 팀에서 탈퇴했습니다.")
    return redirect(reverse("teams:list"))
