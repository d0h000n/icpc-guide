"""Step 3.2 + 3.5: toggle view + detail-page integration tests (post-N—M)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import Problem, ProblemAppearance
from apps.solving.models import SolveRecord

from .factories import (
    ProblemFactory,
    ProblemSetRootFactory,
    SourceFactory,
    UserFactory,
)


def _toggle_url(problem_set, problem):
    return reverse(
        "solving:toggle",
        kwargs={"problem_set_pk": problem_set.pk, "problem_pk": problem.pk},
    )


@pytest.mark.django_db
def test_toggle_creates_record_when_unsolved(client) -> None:
    user = UserFactory()
    leaf = ProblemSetRootFactory()
    problem = ProblemFactory()
    ProblemAppearance.objects.create(problem=problem, problem_set=leaf, label="A")
    client.force_login(user)

    response = client.post(_toggle_url(leaf, problem))
    assert response.status_code == 200
    assert SolveRecord.objects.filter(user=user, problem=problem).exists()
    body = response.content.decode()
    assert "푼 문제" in body
    assert "btn-success" in body


@pytest.mark.django_db
def test_toggle_deletes_record_when_solved(client) -> None:
    user = UserFactory()
    leaf = ProblemSetRootFactory()
    problem = ProblemFactory()
    ProblemAppearance.objects.create(problem=problem, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=user, problem=problem)
    client.force_login(user)

    response = client.post(_toggle_url(leaf, problem))
    assert response.status_code == 200
    assert not SolveRecord.objects.filter(user=user, problem=problem).exists()
    body = response.content.decode()
    assert "체크" in body
    assert "btn-outline" in body


@pytest.mark.django_db
def test_toggle_requires_login(client) -> None:
    leaf = ProblemSetRootFactory()
    problem = ProblemFactory()
    response = client.post(_toggle_url(leaf, problem))
    assert response.status_code == 302
    assert "/accounts/login" in response.url
    assert SolveRecord.objects.count() == 0


@pytest.mark.django_db
def test_toggle_get_method_not_allowed(client) -> None:
    user = UserFactory()
    leaf = ProblemSetRootFactory()
    problem = ProblemFactory()
    client.force_login(user)
    response = client.get(_toggle_url(leaf, problem))
    assert response.status_code == 405


@pytest.mark.django_db
def test_toggle_only_affects_self(client) -> None:
    user_a = UserFactory()
    user_b = UserFactory()
    leaf = ProblemSetRootFactory()
    problem = ProblemFactory()
    ProblemAppearance.objects.create(problem=problem, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=user_b, problem=problem)

    client.force_login(user_a)
    client.post(_toggle_url(leaf, problem))

    assert SolveRecord.objects.filter(user=user_b, problem=problem).exists()
    assert SolveRecord.objects.filter(user=user_a, problem=problem).exists()


@pytest.mark.django_db
def test_toggle_response_includes_oob_completion_counter(client) -> None:
    user = UserFactory()
    src = SourceFactory()
    leaf = ProblemSetRootFactory(source=src)
    p1 = Problem.objects.create(title="X")
    p2 = Problem.objects.create(title="Y")
    ProblemAppearance.objects.create(problem=p1, problem_set=leaf, label="A")
    ProblemAppearance.objects.create(problem=p2, problem_set=leaf, label="B")
    client.force_login(user)

    response = client.post(_toggle_url(leaf, p1))
    body = response.content.decode()
    assert f'id="completion-{leaf.pk}"' in body
    assert 'hx-swap-oob="true"' in body
    assert "1 / 2" in body
    assert 'value="1"' in body
    assert 'max="2"' in body


@pytest.mark.django_db
def test_toggle_dedup_across_multiple_appearances(client) -> None:
    """v0.3 N—M: solving a Problem in one set marks it solved everywhere it appears."""
    user = UserFactory()
    src = SourceFactory()
    s1 = ProblemSetRootFactory(source=src)
    s2 = ProblemSetRootFactory(source=src)
    p_shared = Problem.objects.create(title="Yokohama A / PTZ B")
    ProblemAppearance.objects.create(problem=p_shared, problem_set=s1, label="A")
    ProblemAppearance.objects.create(problem=p_shared, problem_set=s2, label="B")
    client.force_login(user)

    # Toggle on s1 — record created.
    client.post(_toggle_url(s1, p_shared))
    assert SolveRecord.objects.filter(user=user, problem=p_shared).count() == 1

    # The same Problem on s2 should now show as solved on the s2 detail page.
    response = client.get(reverse("problemsets:detail", args=[s2.pk]))
    body = response.content.decode()
    # Solved-state button rendering on s2's detail page (the toggle URL points to s2).
    assert _toggle_url(s2, p_shared) in body
    assert "btn-success" in body
    # Counter on s2 is 1/1 (one Problem in subtree, solved).
    assert f'id="completion-{s2.pk}"' in body
    assert "1 / 1" in body


@pytest.mark.django_db
def test_detail_shows_toggle_buttons_for_authenticated(client) -> None:
    user = UserFactory()
    src = SourceFactory()
    leaf = ProblemSetRootFactory(source=src)
    p1 = Problem.objects.create(title="X")
    ProblemAppearance.objects.create(problem=p1, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=user, problem=p1)

    client.force_login(user)
    response = client.get(reverse("problemsets:detail", args=[leaf.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert _toggle_url(leaf, p1) in body
    assert "btn-success" in body
    assert f'id="completion-{leaf.pk}"' in body
    assert "1 / 1" in body


@pytest.mark.django_db
def test_detail_no_toggle_for_anonymous(client) -> None:
    src = SourceFactory()
    leaf = ProblemSetRootFactory(source=src)
    p = Problem.objects.create(title="X")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, label="A")

    response = client.get(reverse("problemsets:detail", args=[leaf.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert _toggle_url(leaf, p) not in body
    assert f'id="completion-{leaf.pk}"' not in body
    assert "로그인" in body
