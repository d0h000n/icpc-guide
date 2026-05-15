"""Step 6.6: 50-member cap + auto owner transfer on user delete."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.teams.models import (
    Team,
    TeamInvite,
    TeamInviteStatus,
    TeamMember,
    TeamMemberRole,
)

from .factories import (
    TeamFactory,
    TeamInviteFactory,
    TeamMemberFactory,
    UserFactory,
)

# ---------- 50-member cap ----------


@pytest.mark.django_db
def test_membership_blocked_at_cap_via_clean() -> None:
    """The 51st member.save() should raise via clean()."""
    team = TeamFactory()  # owner = 1 member already
    # Fill to exactly MAX_MEMBERS
    for _ in range(Team.MAX_MEMBERS - 1):
        TeamMemberFactory(team=team)
    assert team.memberships.count() == Team.MAX_MEMBERS

    extra = UserFactory()
    with pytest.raises(ValidationError):
        TeamMember(team=team, user=extra).save()


@pytest.mark.django_db
def test_invite_accept_rejects_when_team_full(client) -> None:
    team = TeamFactory()
    # Fill to cap.
    for _ in range(Team.MAX_MEMBERS - 1):
        TeamMemberFactory(team=team)

    invite = TeamInviteFactory(team=team)
    joiner = UserFactory()
    client.force_login(joiner)
    response = client.post(reverse("teams:invite_accept", args=[invite.token]))
    # View renders the "team full" page; no membership created.
    assert response.status_code == 200
    assert not TeamMember.objects.filter(team=team, user=joiner).exists()
    invite.refresh_from_db()
    assert invite.status == TeamInviteStatus.PENDING  # still usable when seat opens


# ---------- owner auto-transfer on user delete ----------


@pytest.mark.django_db
def test_owner_delete_promotes_oldest_member() -> None:
    """Spec §2.4."""
    team = TeamFactory()
    second = TeamMemberFactory(team=team)
    third = TeamMemberFactory(team=team)

    team.owner.delete()

    team.refresh_from_db()
    assert team.owner == second.user
    assert team.memberships.get(user=second.user).role == TeamMemberRole.OWNER
    assert team.memberships.get(user=third.user).role == TeamMemberRole.MEMBER


@pytest.mark.django_db
def test_owner_delete_drops_empty_team() -> None:
    team = TeamFactory()
    pk = team.pk
    team.owner.delete()
    assert not Team.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_member_delete_just_removes_membership() -> None:
    """A non-owner user deleting themselves just leaves the team intact."""
    team = TeamFactory()
    member = TeamMemberFactory(team=team)
    member_user = member.user

    member_user.delete()

    team.refresh_from_db()
    assert team.owner.pk != member_user.pk  # owner unchanged
    assert not team.memberships.filter(user_id=member_user.pk).exists()


@pytest.mark.django_db
def test_owner_delete_handles_multiple_owned_teams() -> None:
    """One user owns several teams; each transfers independently."""
    owner = UserFactory()
    t1 = TeamFactory(owner=owner)
    t2 = TeamFactory(owner=owner)
    successor_a = TeamMemberFactory(team=t1)
    successor_b = TeamMemberFactory(team=t2)

    owner.delete()

    t1.refresh_from_db()
    t2.refresh_from_db()
    assert t1.owner == successor_a.user
    assert t2.owner == successor_b.user


@pytest.mark.django_db
def test_owner_delete_cascades_invites_through_team_only_when_team_dropped() -> None:
    """If the team survives (has other members) invites stick around; if the
    team is dropped (empty after owner gone), invites cascade with it."""
    surviving = TeamFactory()
    TeamMemberFactory(team=surviving)
    surviving_invite = TeamInviteFactory(team=surviving)

    dying = TeamFactory()
    dying_invite = TeamInviteFactory(team=dying)

    # Triggers owner transfer on `surviving` and team deletion on `dying`.
    surviving.owner.delete()
    dying.owner.delete()

    assert TeamInvite.objects.filter(pk=surviving_invite.pk).exists()
    assert not TeamInvite.objects.filter(pk=dying_invite.pk).exists()
