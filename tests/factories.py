"""factory_boy factories for test data."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.categories.models import Category
from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet
from apps.ratings.models import Comment, Rating
from apps.solving.models import SolveRecord


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    nickname = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda u: f"{u.username}@example.com")


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    short_name = factory.Sequence(lambda n: f"cat{n}")


# Backwards-compat alias for tests written before the v0.4 rename. New tests
# should use CategoryFactory directly.
SourceFactory = CategoryFactory


class ProblemFactory(DjangoModelFactory):
    """Builds a canonical Problem (no per-set fields).

    Use ``ProblemAppearanceFactory`` to attach it to a ProblemSet.
    """

    class Meta:
        model = Problem

    title = factory.Sequence(lambda n: f"Problem {n}")


class ProblemSetRootFactory(DjangoModelFactory):
    """Creates a ProblemSet at the tree root via treebeard's add_root.

    Accepts an optional `source=` (or `category=`) kwarg as a back-compat alias
    for "create then add this Category as a membership". Older tests still
    pass `source=...` from when ProblemSet had a Source FK; we redirect that
    into the v0.4 M2M without rewriting the call sites.
    """

    class Meta:
        model = ProblemSet

    title = factory.Sequence(lambda n: f"Set {n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        category = kwargs.pop("source", None) or kwargs.pop("category", None)
        instance = model_class.add_root(**kwargs)
        if category is not None:
            instance.categories.add(category)
        return instance


class ProblemAppearanceFactory(DjangoModelFactory):
    class Meta:
        model = ProblemAppearance

    problem = factory.SubFactory(ProblemFactory)
    problem_set = factory.SubFactory(ProblemSetRootFactory)
    order_index = factory.Sequence(lambda n: (n % 200) + 1)
    label = factory.Sequence(lambda n: chr(ord("A") + (n % 26)))


class SolveRecordFactory(DjangoModelFactory):
    class Meta:
        model = SolveRecord

    user = factory.SubFactory(UserFactory)
    problem = factory.SubFactory(ProblemFactory)
    note = ""


class RatingFactory(DjangoModelFactory):
    class Meta:
        model = Rating

    user = factory.SubFactory(UserFactory)
    problem_set = factory.SubFactory(ProblemSetRootFactory)
    stars = 5


class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment

    rating = factory.SubFactory(RatingFactory)
    body = factory.Sequence(lambda n: f"Comment body {n}")
