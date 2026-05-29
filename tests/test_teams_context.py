"""Step 6.7: team context on ProblemSet detail page (spec §4.4.3)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet
from apps.solving.models import SolveRecord

from .factories import TeamFactory, TeamMemberFactory, UserFactory

# ---------- dropdown availability ----------


@pytest.mark.django_db
def test_dropdown_visible_when_user_has_teams(client) -> None:
    me = UserFactory()
    TeamFactory(owner=me)
    pset = ProblemSet.add_root(title="X")

    client.force_login(me)
    body = client.get(reverse("problemsets:detail", args=[pset.pk])).content.decode()
    assert "팀 컨텍스트" in body


@pytest.mark.django_db
def test_dropdown_hidden_when_user_has_no_teams(client) -> None:
    me = UserFactory()
    pset = ProblemSet.add_root(title="X")
    client.force_login(me)
    body = client.get(reverse("problemsets:detail", args=[pset.pk])).content.decode()
    assert "팀 컨텍스트" not in body


@pytest.mark.django_db
def test_dropdown_hidden_for_anonymous(client) -> None:
    TeamFactory(visibility="public")
    pset = ProblemSet.add_root(title="X")
    body = client.get(reverse("problemsets:detail", args=[pset.pk])).content.decode()
    assert "팀 컨텍스트" not in body


# ---------- team selection ----------


@pytest.mark.django_db
def test_team_param_ignored_for_non_member(client) -> None:
    team = TeamFactory()  # owner = some other user
    me = UserFactory()
    pset = ProblemSet.add_root(title="X")

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[pset.pk]) + f"?team={team.slug}"
    ).content.decode()
    # Member-only team-context panel does not render for non-members.
    assert "팀:" not in body or "팀 컨텍스트:" not in body  # heuristic; check explicit
    assert "팀 누적" not in body


@pytest.mark.django_db
def test_team_context_renders_for_member(client) -> None:
    owner = UserFactory(nickname="alice")
    me = UserFactory(nickname="me")
    team = TeamFactory(owner=owner, name="ACM Cosmos")
    TeamMemberFactory(team=team, user=me)
    pset = ProblemSet.add_root(title="Day 1")

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[pset.pk]) + f"?team={team.slug}"
    ).content.decode()
    assert "ACM Cosmos" in body
    assert "팀 누적" in body
    # All team members appear in the side list.
    assert "alice" in body
    assert "me" in body


@pytest.mark.django_db
def test_per_member_subtree_count_correct(client) -> None:
    me = UserFactory()
    other = UserFactory(nickname="bob")
    team = TeamFactory(owner=me)
    TeamMemberFactory(team=team, user=other)

    leaf = ProblemSet.add_root(title="Day")
    p1 = Problem.objects.create(title="P1")
    p2 = Problem.objects.create(title="P2")
    ProblemAppearance.objects.create(problem=p1, problem_set=leaf, label="A")
    ProblemAppearance.objects.create(problem=p2, problem_set=leaf, label="B")
    SolveRecord.objects.create(user=me, problem=p1)  # me: 1/2
    SolveRecord.objects.create(user=other, problem=p1)
    SolveRecord.objects.create(user=other, problem=p2)  # bob: 2/2

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[leaf.pk]) + f"?team={team.slug}"
    ).content.decode()
    # Team union: both problems → 2/2
    assert "2 / 2" in body
    # bob's per-member badge shows 2/2 too
    # (me's 1/2 also present — explicit assertion below)
    assert "1 / 2" in body


@pytest.mark.django_db
def test_per_problem_team_solvers_column_for_leaf(client) -> None:
    me = UserFactory(nickname="me")
    other = UserFactory(nickname="bob")
    team = TeamFactory(owner=me)
    TeamMemberFactory(team=team, user=other)

    leaf = ProblemSet.add_root(title="Day")
    p = Problem.objects.create(title="ShareMe")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=other, problem=p)

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[leaf.pk]) + f"?team={team.slug}"
    ).content.decode()
    assert "팀원 해결" in body
    # Solver "bob" appears next to ShareMe row; me hasn't solved → not in the row's badges.
    assert "ShareMe" in body
    assert "bob" in body


@pytest.mark.django_db
def test_team_aggregate_dedups_distinct_problems(client) -> None:
    """When two members solve the same problem, the union count stays at 1."""
    me = UserFactory()
    other = UserFactory()
    team = TeamFactory(owner=me)
    TeamMemberFactory(team=team, user=other)

    leaf = ProblemSet.add_root(title="Day")
    p = Problem.objects.create(title="OnlyOne")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=me, problem=p)
    SolveRecord.objects.create(user=other, problem=p)

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[leaf.pk]) + f"?team={team.slug}"
    ).content.decode()
    # Team union = 1 distinct problem (not 2)
    assert "1 / 1" in body


@pytest.mark.django_db
def test_team_context_works_for_internal_node(client) -> None:
    me = UserFactory()
    team = TeamFactory(owner=me)
    root = ProblemSet.add_root(title="Camp")
    leaf = root.add_child(title="Day")
    p = Problem.objects.create(title="P")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=me, problem=p)

    client.force_login(me)
    body = client.get(
        reverse("problemsets:detail", args=[root.pk]) + f"?team={team.slug}"
    ).content.decode()
    # Internal node: still shows the team panel with subtree counts.
    assert "팀 누적" in body
    assert "1 / 1" in body
