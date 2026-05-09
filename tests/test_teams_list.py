"""Step 6.2: team list / create page (S5)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.teams.models import (
    Team,
    TeamMemberRole,
    TeamVisibility,
)

from .factories import TeamFactory, TeamMemberFactory, UserFactory

# ---------- list ----------


@pytest.mark.django_db
def test_list_anonymous_sees_only_public_teams(client) -> None:
    TeamFactory(name="public-team", visibility=TeamVisibility.PUBLIC)
    TeamFactory(name="private-team", visibility=TeamVisibility.PRIVATE)

    body = client.get(reverse("teams:list")).content.decode()
    assert "public-team" in body
    assert "private-team" not in body


@pytest.mark.django_db
def test_list_authenticated_sees_my_teams_and_public(client) -> None:
    me = UserFactory()
    my_team = TeamFactory(name="my-team", visibility=TeamVisibility.PRIVATE)
    TeamMemberFactory(team=my_team, user=me)
    TeamFactory(name="other-public", visibility=TeamVisibility.PUBLIC)
    TeamFactory(name="other-private", visibility=TeamVisibility.PRIVATE)

    client.force_login(me)
    body = client.get(reverse("teams:list")).content.decode()
    assert "my-team" in body
    assert "other-public" in body
    # Other-private (not mine) must not leak.
    assert "other-private" not in body


@pytest.mark.django_db
def test_list_dedups_my_team_from_public_section(client) -> None:
    """A public team I'm in shows only in 'my teams', not also in 'public'."""
    me = UserFactory()
    TeamFactory(name="dual", visibility=TeamVisibility.PUBLIC, owner=me)
    # Owner is auto-added as TeamMember by factory's post_generation hook.

    client.force_login(me)
    body = client.get(reverse("teams:list")).content.decode()
    assert body.count("dual") == 1


@pytest.mark.django_db
def test_list_create_button_for_authenticated(client) -> None:
    me = UserFactory()
    client.force_login(me)
    body = client.get(reverse("teams:list")).content.decode()
    assert reverse("teams:create") in body


@pytest.mark.django_db
def test_list_no_create_button_for_anonymous(client) -> None:
    body = client.get(reverse("teams:list")).content.decode()
    assert reverse("teams:create") not in body


# ---------- create ----------


@pytest.mark.django_db
def test_create_requires_login(client) -> None:
    response = client.get(reverse("teams:create"))
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_create_post_creates_team_and_owner_membership(client) -> None:
    me = UserFactory()
    client.force_login(me)

    response = client.post(
        reverse("teams:create"),
        {
            "name": "Team Cosmos",
            "slug": "cosmos",
            "description": "we like stars",
            "visibility": TeamVisibility.PRIVATE,
        },
    )
    assert response.status_code == 302
    team = Team.objects.get(slug="cosmos")
    assert team.owner == me
    assert team.memberships.filter(user=me, role=TeamMemberRole.OWNER).exists()


@pytest.mark.django_db
def test_create_rejects_duplicate_slug(client) -> None:
    TeamFactory(slug="taken")
    me = UserFactory()
    client.force_login(me)
    response = client.post(
        reverse("teams:create"),
        {
            "name": "Another",
            "slug": "taken",
            "description": "",
            "visibility": TeamVisibility.PRIVATE,
        },
    )
    assert response.status_code == 200  # form re-rendered with error
    assert Team.objects.filter(slug="taken").count() == 1


# ---------- nav link ----------


@pytest.mark.django_db
def test_nav_links_to_teams(client) -> None:
    body = client.get(reverse("home")).content.decode()
    assert reverse("teams:list").encode().decode() in body
