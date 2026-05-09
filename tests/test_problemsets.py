"""Step 1 model tests: Source, ProblemSet (tree), Problem, ProblemAppearance."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet

from .factories import ProblemSetRootFactory, SourceFactory


@pytest.mark.django_db
def test_source_short_name_must_be_unique() -> None:
    SourceFactory(short_name="PTZ")
    with pytest.raises(IntegrityError):
        SourceFactory(short_name="PTZ")


@pytest.mark.django_db
def test_problemset_tree_basic_hierarchy() -> None:
    root = ProblemSet.add_root(title="PTZ Camp")
    summer = root.add_child(title="PTZ 2024 Summer", year=2024)
    day1 = summer.add_child(title="Day 1", year=2024)

    assert root.depth == 1
    assert summer.depth == 2
    assert day1.depth == 3

    descendants = list(root.get_descendants().values_list("title", flat=True))
    assert "PTZ 2024 Summer" in descendants
    assert "Day 1" in descendants

    parent_chain = [a.title for a in day1.get_ancestors()]
    assert parent_chain == ["PTZ Camp", "PTZ 2024 Summer"]


@pytest.mark.django_db
def test_problemset_move_updates_paths() -> None:
    """Moving a node updates its path AND all descendants' paths (treebeard MP)."""
    a = ProblemSet.add_root(title="A")
    b = ProblemSet.add_root(title="B")
    a_child = a.add_child(title="A-child")
    a_grandchild = a_child.add_child(title="A-grandchild")

    a_child.move(b, pos="sorted-child")

    a_child.refresh_from_db()
    a_grandchild.refresh_from_db()
    assert a_child.get_parent() == b
    assert a_grandchild.get_parent() == a_child
    assert a_grandchild.path.startswith(b.path)


@pytest.mark.django_db
def test_appearance_order_unique_within_set() -> None:
    leaf = ProblemSetRootFactory()
    p = Problem.objects.create(title="P1")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, order_index=1, label="A")
    p2 = Problem.objects.create(title="P2")
    with pytest.raises(IntegrityError):
        ProblemAppearance.objects.create(problem=p2, problem_set=leaf, order_index=1, label="B")


@pytest.mark.django_db
def test_appearance_label_unique_within_set() -> None:
    leaf = ProblemSetRootFactory()
    p = Problem.objects.create(title="P1")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, order_index=1, label="A")
    p2 = Problem.objects.create(title="P2")
    with pytest.raises(IntegrityError):
        ProblemAppearance.objects.create(problem=p2, problem_set=leaf, order_index=2, label="A")


@pytest.mark.django_db
def test_appearance_same_label_allowed_across_different_sets() -> None:
    s1 = ProblemSetRootFactory()
    s2 = ProblemSetRootFactory()
    p1 = Problem.objects.create(title="X")
    p2 = Problem.objects.create(title="Y")
    ProblemAppearance.objects.create(problem=p1, problem_set=s1, order_index=1, label="A")
    ProblemAppearance.objects.create(problem=p2, problem_set=s2, order_index=1, label="A")
    assert ProblemAppearance.objects.count() == 2


@pytest.mark.django_db
def test_problem_can_appear_in_multiple_sets() -> None:
    """v0.3 N—M: one Problem can sit inside several ProblemSets."""
    s1 = ProblemSetRootFactory()
    s2 = ProblemSetRootFactory()
    p = Problem.objects.create(title="Shared problem (e.g. ICPC + PTZ)")

    ProblemAppearance.objects.create(problem=p, problem_set=s1, order_index=1, label="A")
    ProblemAppearance.objects.create(problem=p, problem_set=s2, order_index=3, label="C")

    assert p.appearances.count() == 2
    assert {a.problem_set_id for a in p.appearances.all()} == {s1.pk, s2.pk}


@pytest.mark.django_db
def test_appearance_unique_problem_per_set() -> None:
    """Same problem can't appear twice within the same set."""
    s = ProblemSetRootFactory()
    p = Problem.objects.create(title="Dup")
    ProblemAppearance.objects.create(problem=p, problem_set=s, order_index=1, label="A")
    with pytest.raises(IntegrityError):
        ProblemAppearance.objects.create(problem=p, problem_set=s, order_index=2, label="B")


@pytest.mark.django_db
def test_category_cannot_contain_ancestor_descendant_pair() -> None:
    """v0.4 §3.3: category may not list both an ancestor and a descendant."""
    from django.core.exceptions import ValidationError

    from apps.problemsets.models import CategoryMembership

    cat = SourceFactory(short_name="japan-rule")
    root = ProblemSet.add_root(title="ICPC")
    leaf = root.add_child(title="Yokohama 2023")

    # First: attach the ancestor — OK.
    root.categories.add(cat)
    # Second: attempt to attach the descendant via direct membership create.
    with pytest.raises(ValidationError):
        CategoryMembership.objects.create(category=cat, problem_set=leaf)
    # And via the M2M signal path on the Category side.
    with pytest.raises(ValidationError):
        leaf.categories.add(cat)


@pytest.mark.django_db
def test_category_can_contain_unrelated_problem_sets() -> None:
    """Sibling-or-distant ProblemSets may share a category without issue."""
    cat = SourceFactory(short_name="japan-ok")
    a = ProblemSet.add_root(title="AtCoder")
    b = ProblemSet.add_root(title="JOI")

    a.categories.add(cat)
    b.categories.add(cat)
    assert cat.problem_sets.count() == 2


@pytest.mark.django_db
def test_category_membership_cascades_when_category_deleted() -> None:
    """v0.4: Category ↔ ProblemSet is M2M with through CASCADE on category.

    Deleting a Category drops all CategoryMembership rows but keeps ProblemSets.
    """
    from apps.problemsets.models import CategoryMembership

    cat = SourceFactory(short_name="japan-test")
    root = ProblemSet.add_root(title="Yokohama")
    root.categories.add(cat)
    assert CategoryMembership.objects.filter(category=cat).count() == 1

    cat.delete()

    assert CategoryMembership.objects.filter(category_id=cat.pk).count() == 0
    # ProblemSet itself survives — only its membership in the deleted category disappears.
    assert ProblemSet.objects.filter(pk=root.pk).exists()
