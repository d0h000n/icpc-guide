"""Step 6.8: Visibility audit for team-related surfaces (spec §4.6.3).

Cross-cuts steps 6.3 (team detail), 6.7 (team context), and 5.2 (profile).
Each rule is verified at the surface that enforces it.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import ProfileVisibility
from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet
from apps.solving.models import SolveRecord
from apps.teams.models import TeamVisibility

from .factories import TeamFactory, TeamMemberFactory, UserFactory

# ---------- public team + member listing visible to outsiders ----------


@pytest.mark.django_db
def test_public_team_lists_member_nicknames_to_outsider(client) -> None:
    """spec §4.6.3: 비멤버 → public 팀 = 팀명·설명·멤버 닉네임 목록 공개."""
    owner = UserFactory(nickname="alice")
    member = UserFactory(nickname="bob")
    team = TeamFactory(owner=owner, visibility=TeamVisibility.PUBLIC)
    TeamMemberFactory(team=team, user=member)

    outsider = UserFactory()
    client.force_login(outsider)
    body = client.get(reverse("teams:detail", args=[team.slug])).content.decode()
    assert "alice" in body
    assert "bob" in body


@pytest.mark.django_db
def test_public_team_member_with_private_profile_clicks_through_to_blocked_profile(
    client,
) -> None:
    """public 팀 + private 멤버: 외부인은 닉네임은 보지만 상세 풀이는 못 본다.

    팀 페이지에선 닉네임만 노출(통과), 프로필 페이지에선 visibility 룰이 차단.
    """
    private_member = UserFactory(
        nickname="hidden_one",
        profile_visibility=ProfileVisibility.PRIVATE,
        boj_handle="hidden_boj",
    )
    team = TeamFactory(visibility=TeamVisibility.PUBLIC)
    TeamMemberFactory(team=team, user=private_member)

    outsider = UserFactory()
    client.force_login(outsider)

    # 1) On team page: nickname appears, no detailed handles leak.
    team_body = client.get(reverse("teams:detail", args=[team.slug])).content.decode()
    assert "hidden_one" in team_body
    assert "hidden_boj" not in team_body  # team page doesn't surface handles

    # 2) Clicking through to the profile: profile view blocks details.
    profile_body = client.get(reverse("accounts:profile", args=["hidden_one"])).content.decode()
    assert "hidden_one" in profile_body
    assert "hidden_boj" not in profile_body
    assert "비공개입니다" in profile_body


# ---------- team context = always full visibility between members ----------


@pytest.mark.django_db
def test_team_context_reveals_private_members_solves_to_teammates(client) -> None:
    """spec §4.4.3 마지막 문단 + §4.6.3: 팀 컨텍스트에선 다른 멤버의 풀이 상태가
    팀 멤버에게 항상 보인다 (해당 멤버의 profile_visibility와 무관)."""
    me = UserFactory(nickname="me")
    private_teammate = UserFactory(
        nickname="ghost",
        profile_visibility=ProfileVisibility.PRIVATE,
    )
    team = TeamFactory(owner=me)
    TeamMemberFactory(team=team, user=private_teammate)

    leaf = ProblemSet.add_root(title="Day 1")
    p = Problem.objects.create(title="GhostlySolve")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, order_index=1, label="A")
    SolveRecord.objects.create(user=private_teammate, problem=p)

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[leaf.pk]) + f"?team={team.slug}"
    ).content.decode()
    # The private teammate is listed as a solver in the per-problem column.
    assert "ghost" in body
    # And their per-member subtree count reflects the solve (1/1).
    assert "1 / 1" in body


@pytest.mark.django_db
def test_non_member_cannot_force_team_context_via_url(client) -> None:
    """Spec §4.4.3 implies team context is only for members. Url-tampering
    by a non-member must not surface anyone's solve activity."""
    private_teammate = UserFactory(
        nickname="hidden_dancer",  # avoid substring-collision with daisyUI's btn-ghost
        profile_visibility=ProfileVisibility.PRIVATE,
    )
    team = TeamFactory(visibility=TeamVisibility.PUBLIC)
    TeamMemberFactory(team=team, user=private_teammate)

    leaf = ProblemSet.add_root(title="Day 1")
    p = Problem.objects.create(title="MysticProblem")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, order_index=1, label="A")
    SolveRecord.objects.create(user=private_teammate, problem=p)

    stranger = UserFactory()
    client.force_login(stranger)
    body = client.get(
        reverse("problemsets:detail", args=[leaf.pk]) + f"?team={team.slug}"
    ).content.decode()
    # No team panel and no per-problem solver column for the non-member.
    assert "팀 누적" not in body
    assert "팀원 해결" not in body
    # The private teammate's nickname is not promoted into this page either —
    # neither inline nor via a profile link.
    assert "hidden_dancer" not in body
    assert reverse("accounts:profile", args=["hidden_dancer"]) not in body


@pytest.mark.django_db
def test_private_team_404_for_anonymous_even_with_correct_slug(client) -> None:
    """spec §5.3: 비인가 접근은 403이 아니라 404 (존재 비노출). 이미 6.3에서
    커버됐지만 visibility 감사 차원에서 한 번 더 명시."""
    team = TeamFactory(visibility=TeamVisibility.PRIVATE)
    response = client.get(reverse("teams:detail", args=[team.slug]))
    assert response.status_code == 404
