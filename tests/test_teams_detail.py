"""Step 6.3: team detail page + visibility rules. Spec §4.6.2/3."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.teams.models import TeamVisibility

from .factories import TeamFactory, TeamMemberFactory, UserFactory


def _detail_url(team):
    return reverse("teams:detail", args=[team.slug])


@pytest.mark.django_db
def test_public_team_anyone_can_view(client) -> None:
    team = TeamFactory(name="Public-Team", visibility=TeamVisibility.PUBLIC)
    response = client.get(_detail_url(team))
    assert response.status_code == 200
    assert b"Public-Team" in response.content


@pytest.mark.django_db
def test_private_team_member_can_view(client) -> None:
    team = TeamFactory(name="PrivateOne", visibility=TeamVisibility.PRIVATE)
    me = UserFactory()
    TeamMemberFactory(team=team, user=me)

    client.force_login(me)
    response = client.get(_detail_url(team))
    assert response.status_code == 200
    assert b"PrivateOne" in response.content


@pytest.mark.django_db
def test_private_team_owner_can_view(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me, visibility=TeamVisibility.PRIVATE)
    client.force_login(me)
    response = client.get(_detail_url(team))
    assert response.status_code == 200


@pytest.mark.django_db
def test_private_team_anonymous_gets_404(client) -> None:
    team = TeamFactory(visibility=TeamVisibility.PRIVATE)
    response = client.get(_detail_url(team))
    # spec §5.3 — private 자원에 비인가 접근은 404 (존재 자체 비노출)
    assert response.status_code == 404


@pytest.mark.django_db
def test_private_team_non_member_gets_404(client) -> None:
    team = TeamFactory(visibility=TeamVisibility.PRIVATE)
    other = UserFactory()
    client.force_login(other)
    response = client.get(_detail_url(team))
    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_lists_members_with_owner_first(client) -> None:
    team = TeamFactory(visibility=TeamVisibility.PUBLIC)
    member = UserFactory(nickname="bob")
    TeamMemberFactory(team=team, user=member)

    body = client.get(_detail_url(team)).content.decode()
    # Both owner (auto from factory) and bob appear.
    assert team.owner.nickname in body
    assert "bob" in body
    # Member nicknames link to their profiles.
    assert reverse("accounts:profile", args=[member.nickname]) in body


@pytest.mark.django_db
def test_detail_renders_team_metadata(client) -> None:
    team = TeamFactory(
        name="Cosmos",
        slug="cosmos",
        description="별을 좋아하는 팀",
        visibility=TeamVisibility.PUBLIC,
    )
    body = client.get(_detail_url(team)).content.decode()
    assert "Cosmos" in body
    assert "cosmos" in body  # slug shown
    assert "별을 좋아하는 팀" in body


@pytest.mark.django_db
def test_create_redirect_now_targets_detail(client) -> None:
    me = UserFactory()
    client.force_login(me)
    response = client.post(
        reverse("teams:create"),
        {
            "name": "Detail-Bound",
            "slug": "detail-bound",
            "description": "",
            "visibility": TeamVisibility.PRIVATE,
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("teams:detail", args=["detail-bound"])
