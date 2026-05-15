"""Step 6.4: team edit, remove member, transfer ownership, leave."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.teams.models import Team, TeamMember, TeamMemberRole

from .factories import TeamFactory, TeamMemberFactory, UserFactory

# ---------- edit ----------


@pytest.mark.django_db
def test_edit_requires_login(client) -> None:
    team = TeamFactory()
    response = client.get(reverse("teams:edit", args=[team.slug]))
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_edit_owner_only(client) -> None:
    team = TeamFactory()
    other = UserFactory()
    TeamMemberFactory(team=team, user=other)
    client.force_login(other)
    response = client.get(reverse("teams:edit", args=[team.slug]))
    assert response.status_code == 403


@pytest.mark.django_db
def test_edit_owner_updates_fields(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me, name="old", description="")
    client.force_login(me)
    response = client.post(
        reverse("teams:edit", args=[team.slug]),
        {
            "name": "new",
            "slug": team.slug,
            "description": "fresh",
            "visibility": "public",
        },
    )
    assert response.status_code == 302
    team.refresh_from_db()
    assert team.name == "new"
    assert team.description == "fresh"
    assert team.visibility == "public"


# ---------- member remove ----------


@pytest.mark.django_db
def test_member_remove_owner_only(client) -> None:
    team = TeamFactory()
    other = UserFactory()
    membership = TeamMemberFactory(team=team, user=other)

    intruder = UserFactory()
    TeamMemberFactory(team=team, user=intruder)
    client.force_login(intruder)
    response = client.post(reverse("teams:member_remove", args=[team.slug, membership.pk]))
    assert response.status_code == 403
    assert TeamMember.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_remove_works_for_owner(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    other = UserFactory()
    membership = TeamMemberFactory(team=team, user=other)

    client.force_login(me)
    response = client.post(reverse("teams:member_remove", args=[team.slug, membership.pk]))
    assert response.status_code == 302
    assert not TeamMember.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_remove_blocks_removing_owner(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    owner_membership = team.memberships.get(user=me)
    client.force_login(me)
    response = client.post(reverse("teams:member_remove", args=[team.slug, owner_membership.pk]))
    assert response.status_code == 302  # redirect with error message
    assert TeamMember.objects.filter(pk=owner_membership.pk).exists()


# ---------- transfer ownership ----------


@pytest.mark.django_db
def test_transfer_ownership_owner_only(client) -> None:
    team = TeamFactory()
    other = UserFactory()
    new_membership = TeamMemberFactory(team=team, user=other)

    intruder = UserFactory()
    TeamMemberFactory(team=team, user=intruder)
    client.force_login(intruder)
    response = client.post(
        reverse("teams:transfer_ownership", args=[team.slug]),
        {"new_owner_member_id": new_membership.pk},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_transfer_ownership_swaps_roles_and_owner_fk(client) -> None:
    me = UserFactory()
    successor = UserFactory()
    team = TeamFactory(owner=me)
    new_membership = TeamMemberFactory(team=team, user=successor)

    client.force_login(me)
    response = client.post(
        reverse("teams:transfer_ownership", args=[team.slug]),
        {"new_owner_member_id": new_membership.pk},
    )
    assert response.status_code == 302

    team.refresh_from_db()
    assert team.owner == successor
    assert team.memberships.get(user=successor).role == TeamMemberRole.OWNER
    assert team.memberships.get(user=me).role == TeamMemberRole.MEMBER


@pytest.mark.django_db
def test_transfer_ownership_to_same_user_rejected(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    owner_membership = team.memberships.get(user=me)
    client.force_login(me)
    response = client.post(
        reverse("teams:transfer_ownership", args=[team.slug]),
        {"new_owner_member_id": owner_membership.pk},
    )
    assert response.status_code == 302
    team.refresh_from_db()
    assert team.owner == me  # unchanged


# ---------- leave ----------


@pytest.mark.django_db
def test_leave_team_removes_membership(client) -> None:
    team = TeamFactory()
    me = UserFactory()
    TeamMemberFactory(team=team, user=me)
    client.force_login(me)
    response = client.post(reverse("teams:leave", args=[team.slug]))
    assert response.status_code == 302
    assert not TeamMember.objects.filter(team=team, user=me).exists()


@pytest.mark.django_db
def test_leave_team_owner_blocked(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    client.force_login(me)
    response = client.post(reverse("teams:leave", args=[team.slug]))
    assert response.status_code == 302
    # Still owner, still a member.
    assert Team.objects.filter(pk=team.pk).exists()
    assert TeamMember.objects.filter(team=team, user=me).exists()


@pytest.mark.django_db
def test_leave_team_non_member_404(client) -> None:
    team = TeamFactory()
    stranger = UserFactory()
    client.force_login(stranger)
    response = client.post(reverse("teams:leave", args=[team.slug]))
    assert response.status_code == 404


# ---------- detail page controls visibility ----------


@pytest.mark.django_db
def test_owner_sees_controls_on_detail(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    successor = UserFactory()
    TeamMemberFactory(team=team, user=successor)

    client.force_login(me)
    body = client.get(reverse("teams:detail", args=[team.slug])).content.decode()
    assert reverse("teams:edit", args=[team.slug]) in body
    assert reverse("teams:transfer_ownership", args=[team.slug]) in body
    # Successor's remove form present (owner can't remove themselves).
    successor_membership = team.memberships.get(user=successor)
    assert reverse("teams:member_remove", args=[team.slug, successor_membership.pk]) in body


@pytest.mark.django_db
def test_non_owner_does_not_see_owner_controls(client) -> None:
    team = TeamFactory(visibility="public")
    other = UserFactory()
    TeamMemberFactory(team=team, user=other)
    client.force_login(other)
    body = client.get(reverse("teams:detail", args=[team.slug])).content.decode()
    assert reverse("teams:edit", args=[team.slug]) not in body
    assert reverse("teams:transfer_ownership", args=[team.slug]) not in body
    # But a Leave button is present for the member.
    assert reverse("teams:leave", args=[team.slug]) in body
