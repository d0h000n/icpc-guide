"""Step 6.5: invite link issue + accept flow."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.teams.models import TeamInvite, TeamInviteStatus, TeamMember

from .factories import (
    TeamFactory,
    TeamInviteFactory,
    TeamMemberFactory,
    UserFactory,
)

# ---------- create / revoke ----------


@pytest.mark.django_db
def test_invite_create_owner_only(client) -> None:
    team = TeamFactory()
    intruder = UserFactory()
    TeamMemberFactory(team=team, user=intruder)
    client.force_login(intruder)
    response = client.post(reverse("teams:invite_create", args=[team.slug]))
    assert response.status_code == 403
    assert not TeamInvite.objects.filter(team=team).exists()


@pytest.mark.django_db
def test_invite_create_works_for_owner(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    client.force_login(me)
    response = client.post(reverse("teams:invite_create", args=[team.slug]))
    assert response.status_code == 302
    invite = TeamInvite.objects.get(team=team)
    assert invite.invited_by == me
    assert invite.status == TeamInviteStatus.PENDING
    assert len(invite.token) > 20


@pytest.mark.django_db
def test_invite_revoke_marks_status(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    invite = TeamInviteFactory(team=team)
    client.force_login(me)
    response = client.post(reverse("teams:invite_revoke", args=[team.slug, invite.pk]))
    assert response.status_code == 302
    invite.refresh_from_db()
    assert invite.status == TeamInviteStatus.REVOKED


# ---------- accept ----------


@pytest.mark.django_db
def test_accept_requires_login(client) -> None:
    invite = TeamInviteFactory()
    response = client.get(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_accept_get_shows_confirmation(client) -> None:
    invite = TeamInviteFactory()
    me = UserFactory()
    client.force_login(me)
    response = client.get(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 200
    assert b"\xed\x95\xa9\xeb\xa5\x98" in response.content  # "합류" button


@pytest.mark.django_db
def test_accept_post_adds_membership(client) -> None:
    team = TeamFactory()
    invite = TeamInviteFactory(team=team)
    joiner = UserFactory()
    client.force_login(joiner)
    response = client.post(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 302
    assert TeamMember.objects.filter(team=team, user=joiner).exists()
    invite.refresh_from_db()
    assert invite.status == TeamInviteStatus.ACCEPTED
    assert invite.invitee_user == joiner
    assert invite.accepted_at is not None


@pytest.mark.django_db
def test_accept_rejects_already_used_invite(client) -> None:
    team = TeamFactory()
    consumer = UserFactory()
    invite = TeamInviteFactory(
        team=team,
        status=TeamInviteStatus.ACCEPTED,
        invitee_user=consumer,
    )

    other = UserFactory()
    client.force_login(other)
    response = client.post(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 200
    assert not TeamMember.objects.filter(team=team, user=other).exists()


@pytest.mark.django_db
def test_accept_rejects_revoked_invite(client) -> None:
    invite = TeamInviteFactory(status=TeamInviteStatus.REVOKED)
    joiner = UserFactory()
    client.force_login(joiner)
    response = client.post(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 200
    assert not TeamMember.objects.filter(team=invite.team, user=joiner).exists()


@pytest.mark.django_db
def test_accept_rejects_expired_invite(client) -> None:
    past = timezone.now() - timedelta(days=1)
    invite = TeamInviteFactory(expires_at=past)
    joiner = UserFactory()
    client.force_login(joiner)
    response = client.post(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 200
    assert not TeamMember.objects.filter(team=invite.team, user=joiner).exists()


@pytest.mark.django_db
def test_accept_when_already_member_redirects_to_detail(client) -> None:
    team = TeamFactory()
    me = UserFactory()
    TeamMemberFactory(team=team, user=me)
    invite = TeamInviteFactory(team=team)
    client.force_login(me)
    response = client.post(reverse("teams:invite_accept", args=[invite.token]))
    assert response.status_code == 302
    assert response.url == reverse("teams:detail", args=[team.slug])


@pytest.mark.django_db
def test_accept_404_for_unknown_token(client) -> None:
    me = UserFactory()
    client.force_login(me)
    response = client.get(reverse("teams:invite_accept", args=["no-such-token-12345"]))
    assert response.status_code == 404


# ---------- detail page integration ----------


@pytest.mark.django_db
def test_detail_owner_sees_invite_section(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    TeamInviteFactory(team=team)
    client.force_login(me)
    body = client.get(reverse("teams:detail", args=[team.slug])).content.decode()
    assert reverse("teams:invite_create", args=[team.slug]) in body
    # Token appears as full URL in the rendered list.
    assert "/invites/" in body


@pytest.mark.django_db
def test_detail_non_owner_does_not_see_invite_section(client) -> None:
    team = TeamFactory(visibility="public")
    other = UserFactory()
    TeamMemberFactory(team=team, user=other)
    TeamInviteFactory(team=team)
    client.force_login(other)
    body = client.get(reverse("teams:detail", args=[team.slug])).content.decode()
    assert reverse("teams:invite_create", args=[team.slug]) not in body
