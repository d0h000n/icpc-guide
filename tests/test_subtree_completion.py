"""Step 3.3 + 3.5: subtree completion helper + display on detail / list pages."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet
from apps.solving.models import SolveRecord
from apps.solving.services import (
    completion_for,
    subtree_problem_count,
    subtree_solved_count,
)

from .factories import UserFactory


def _link(problem, problem_set, label):
    return ProblemAppearance.objects.create(
        problem=problem,
        problem_set=problem_set,
        label=label,
    )


# ---------- Helper / service tests ----------


@pytest.mark.django_db
def test_subtree_count_includes_self_and_descendants() -> None:
    root = ProblemSet.add_root(title="Camp")
    child = root.add_child(title="2024 Summer")
    leaf = child.add_child(title="Day 1")

    p1 = Problem.objects.create(title="X")
    p2 = Problem.objects.create(title="Y")
    _link(p1, leaf, "A")
    _link(p2, leaf, "B")

    assert subtree_problem_count(root) == 2
    assert subtree_problem_count(child) == 2
    assert subtree_problem_count(leaf) == 2


@pytest.mark.django_db
def test_subtree_count_isolates_sibling_branches() -> None:
    a = ProblemSet.add_root(title="A")
    b = ProblemSet.add_root(title="B")

    a_leaf = a.add_child(title="A-leaf")
    b_leaf = b.add_child(title="B-leaf")
    _link(Problem.objects.create(title="X"), a_leaf, "A")
    _link(Problem.objects.create(title="Y"), b_leaf, "A")
    _link(Problem.objects.create(title="Z"), b_leaf, "B")

    assert subtree_problem_count(a) == 1
    assert subtree_problem_count(b) == 2


@pytest.mark.django_db
def test_subtree_count_dedups_problem_appearing_in_multiple_descendants() -> None:
    """v0.3: same Problem in 두 자식 leaf → distinct count = 1."""
    root = ProblemSet.add_root(title="Camp")
    leaf_a = root.add_child(title="A")
    leaf_b = root.add_child(title="B")

    shared = Problem.objects.create(title="Shared")
    _link(shared, leaf_a, "A")
    _link(shared, leaf_b, "A")

    # Two appearances, but only one distinct Problem.
    assert ProblemAppearance.objects.filter(problem=shared).count() == 2
    assert subtree_problem_count(root) == 1


@pytest.mark.django_db
def test_subtree_solved_count_anonymous_returns_zero() -> None:
    from django.contrib.auth.models import AnonymousUser

    leaf = ProblemSet.add_root(title="Day 1")
    _link(Problem.objects.create(title="X"), leaf, "A")

    assert subtree_solved_count(leaf, AnonymousUser()) == 0


@pytest.mark.django_db
def test_subtree_solved_count_per_user() -> None:
    root = ProblemSet.add_root(title="Camp")
    leaf = root.add_child(title="Day 1")
    p1 = Problem.objects.create(title="X")
    p2 = Problem.objects.create(title="Y")
    _link(p1, leaf, "A")
    _link(p2, leaf, "B")

    user = UserFactory()
    SolveRecord.objects.create(user=user, problem=p1)
    SolveRecord.objects.create(user=user, problem=p2)
    UserFactory()  # noise

    assert completion_for(root, user) == (2, 2)
    assert completion_for(leaf, user) == (2, 2)


@pytest.mark.django_db
def test_subtree_solved_count_dedups_shared_problem() -> None:
    """Solving once a Problem that appears in two siblings counts as 1, not 2."""
    root = ProblemSet.add_root(title="Camp")
    leaf_a = root.add_child(title="A")
    leaf_b = root.add_child(title="B")

    shared = Problem.objects.create(title="Shared")
    _link(shared, leaf_a, "A")
    _link(shared, leaf_b, "A")

    user = UserFactory()
    SolveRecord.objects.create(user=user, problem=shared)

    assert subtree_solved_count(root, user) == 1
    assert completion_for(root, user) == (1, 1)


# ---------- Detail page integration ----------


@pytest.mark.django_db
def test_internal_node_detail_shows_self_and_per_child_completion(client) -> None:
    user = UserFactory()
    root = ProblemSet.add_root(title="Camp")
    summer = root.add_child(title="2024 Summer", year=2024)
    winter = root.add_child(title="2024 Winter", year=2024)

    s_leaf = summer.add_child(title="Summer Day 1")
    w_leaf = winter.add_child(title="Winter Day 1")
    sp = Problem.objects.create(title="X")
    _link(sp, s_leaf, "A")
    _link(Problem.objects.create(title="Y"), w_leaf, "A")

    SolveRecord.objects.create(user=user, problem=sp)
    client.force_login(user)

    response = client.get(reverse("problemsets:detail", args=[root.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert f'id="completion-{root.pk}"' in body
    assert f'id="completion-{summer.pk}"' in body
    assert f'id="completion-{winter.pk}"' in body


@pytest.mark.django_db
def test_internal_node_detail_no_counter_for_anonymous(client) -> None:
    root = ProblemSet.add_root(title="Camp")
    root.add_child(title="Child")

    response = client.get(reverse("problemsets:detail", args=[root.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "completion-" not in body


# ---------- List page integration ----------


@pytest.mark.django_db
def test_list_shows_per_row_completion_for_authenticated(client) -> None:
    user = UserFactory()
    root = ProblemSet.add_root(title="Camp")
    leaf = root.add_child(title="Day 1")
    p1 = Problem.objects.create(title="X")
    p2 = Problem.objects.create(title="Y")
    _link(p1, leaf, "A")
    _link(p2, leaf, "B")
    SolveRecord.objects.create(user=user, problem=p1)

    client.force_login(user)
    response = client.get(reverse("problemsets:list"))
    body = response.content.decode()
    assert response.status_code == 200
    assert f'id="completion-{root.pk}"' in body
    assert f'id="completion-{leaf.pk}"' in body
    assert "1 / 2" in body


@pytest.mark.django_db
def test_list_no_completion_counter_for_anonymous(client) -> None:
    ProblemSet.add_root(title="Camp")

    response = client.get(reverse("problemsets:list"))
    body = response.content.decode()
    assert response.status_code == 200
    assert "completion-" not in body
