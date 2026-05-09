"""Step 3.1: SolveRecord model tests."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.problemsets.models import Problem
from apps.solving.models import SolveRecord

from .factories import (
    ProblemFactory,
    SolveRecordFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_solve_record_records_solved_at_automatically() -> None:
    record = SolveRecordFactory()
    assert record.solved_at is not None


@pytest.mark.django_db
def test_solve_record_unique_per_user_problem() -> None:
    user = UserFactory()
    problem = ProblemFactory()
    SolveRecord.objects.create(user=user, problem=problem)
    with pytest.raises(IntegrityError):
        SolveRecord.objects.create(user=user, problem=problem)


@pytest.mark.django_db
def test_solve_record_same_problem_different_users_allowed() -> None:
    problem = ProblemFactory()
    u1, u2 = UserFactory(), UserFactory()
    SolveRecord.objects.create(user=u1, problem=problem)
    SolveRecord.objects.create(user=u2, problem=problem)
    assert SolveRecord.objects.count() == 2


@pytest.mark.django_db
def test_solve_record_one_user_many_problems_allowed() -> None:
    user = UserFactory()
    p1 = Problem.objects.create(title="X")
    p2 = Problem.objects.create(title="Y")
    SolveRecord.objects.create(user=user, problem=p1)
    SolveRecord.objects.create(user=user, problem=p2)
    assert user.solve_records.count() == 2


@pytest.mark.django_db
def test_solve_record_cascades_when_user_deleted() -> None:
    user = UserFactory()
    SolveRecordFactory(user=user)
    SolveRecordFactory(user=user)
    user.delete()
    assert SolveRecord.objects.count() == 0


@pytest.mark.django_db
def test_solve_record_cascades_when_problem_deleted() -> None:
    problem = ProblemFactory()
    SolveRecordFactory(problem=problem)
    SolveRecordFactory(problem=problem)
    problem.delete()
    assert SolveRecord.objects.count() == 0


@pytest.mark.django_db
def test_solve_record_note_optional_and_bounded() -> None:
    rec = SolveRecordFactory(note="짧은 메모")
    rec.refresh_from_db()
    assert rec.note == "짧은 메모"

    # Spec §3.1: note ≤ 200 chars. Field config enforces it at form/admin layer.
    field = SolveRecord._meta.get_field("note")
    assert field.max_length == 200
    assert field.blank is True
