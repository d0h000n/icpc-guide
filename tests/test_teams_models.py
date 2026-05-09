"""Step 6.1: Team / TeamMember / TeamInvite model tests."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.teams.models import (
    TeamInvite,
    TeamInviteStatus,
    TeamMember,
    TeamMemberRole,
    TeamVisibility,
)

from .factories import (
    TeamFactory,
    TeamInviteFactory,
    TeamMemberFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_team_factory_creates_owner_membership() -> None:
    team = TeamFactory()
    assert team.memberships.count() == 1
    membership = team.memberships.get()
    assert membership.user == team.owner
    assert membership.role == TeamMemberRole.OWNER


@pytest.mark.django_db
def test_team_slug_is_unique() -> None:
    TeamFactory(slug="alpha")
    with pytest.raises(IntegrityError):
        TeamFactory(slug="alpha")


@pytest.mark.django_db
def test_team_visibility_default_is_private() -> None:
    team = TeamFactory()
    assert team.visibility == TeamVisibility.PRIVATE


@pytest.mark.django_db
def test_team_member_unique_per_team_user() -> None:
    team = TeamFactory()
    other = UserFactory()
    TeamMember.objects.create(team=team, user=other)
    with pytest.raises(IntegrityError):
        TeamMember.objects.create(team=team, user=other)


@pytest.mark.django_db
def test_team_member_one_user_many_teams() -> None:
    user = UserFactory()
    t1 = TeamFactory()
    t2 = TeamFactory()
    TeamMemberFactory(team=t1, user=user)
    TeamMemberFactory(team=t2, user=user)
    assert user.team_memberships.count() == 2


@pytest.mark.django_db
def test_team_member_cascades_when_team_deleted() -> None:
    team = TeamFactory()
    TeamMemberFactory(team=team)
    team.delete()
    assert TeamMember.objects.count() == 0


@pytest.mark.django_db
def test_team_member_cascades_when_user_deleted() -> None:
    team = TeamFactory()
    user = UserFactory()
    TeamMemberFactory(team=team, user=user)
    user.delete()
    assert not TeamMember.objects.filter(user_id=user.pk).exists()


@pytest.mark.django_db
def test_team_owner_protected_from_user_delete() -> None:
    """spec §2.4: owner-deletion needs auto-transfer logic; the FK uses PROTECT
    so naive `user.delete()` on an owner blocks until handled by step 6.6."""
    from django.db.models.deletion import ProtectedError

    team = TeamFactory()
    with pytest.raises(ProtectedError):
        team.owner.delete()


@pytest.mark.django_db
def test_team_invite_token_auto_generated_and_unique() -> None:
    inv1 = TeamInviteFactory()
    inv2 = TeamInviteFactory()
    assert inv1.token
    assert inv2.token
    assert inv1.token != inv2.token


@pytest.mark.django_db
def test_team_invite_default_status_pending() -> None:
    inv = TeamInviteFactory()
    assert inv.status == TeamInviteStatus.PENDING


@pytest.mark.django_db
def test_team_invite_cascades_when_team_deleted() -> None:
    team = TeamFactory()
    TeamInviteFactory(team=team)
    team.delete()
    assert TeamInvite.objects.count() == 0
