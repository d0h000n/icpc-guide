"""ProblemSet (treebeard MP tree) and Problem models. Spec §3.1."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from treebeard.mp_tree import MP_Node


class ProblemSet(MP_Node):
    """Hierarchical problem set node. Internal nodes group; leaves hold Problems.

    Tree mechanics provided by treebeard (Materialized Path) — `path`, `depth`,
    `numchild` columns are added automatically. See architecture §4.1.
    """

    title = models.CharField(max_length=200)
    categories = models.ManyToManyField(
        "sources.Category",
        through="CategoryMembership",
        related_name="problem_sets",
        blank=True,
    )
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    external_url = models.URLField(blank=True)
    # Auto-computed in P3 (스코어보드 기반). Nullable, hidden in V1.
    difficulty_score = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_problem_sets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Sibling order within the tree — title alphabetical by default.
    node_order_by = ["title"]

    class Meta:
        ordering = ["path"]
        indexes = [
            models.Index(fields=["year"]),
        ]

    def __str__(self) -> str:
        return self.title


class CategoryMembership(models.Model):
    """Through model for ProblemSet ↔ Category M2M (spec v0.4 §3.1)."""

    category = models.ForeignKey(
        "sources.Category",
        on_delete=models.CASCADE,
    )
    problem_set = models.ForeignKey(
        ProblemSet,
        on_delete=models.CASCADE,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "problem_set"],
                name="unique_category_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["problem_set"]),
        ]

    def __str__(self) -> str:
        return f"{self.category.short_name} ⊃ {self.problem_set.title}"

    def save(self, *args, **kwargs) -> None:
        # Run clean() so direct .objects.create() and admin form saves both
        # enforce the ancestor-descendant rule.
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Reject if any ancestor or descendant is already in the same category.

        Spec v0.4 §3.3: "Category가 어떤 두 조상-자손 관계에 있는 ProblemSet
        A, B를 sibling하게 직접 멤버로 가질 수 없다."
        """
        super().clean()
        if not self.problem_set_id or not self.category_id:
            return
        path = self.problem_set.path
        existing = (
            CategoryMembership.objects.filter(category_id=self.category_id)
            .exclude(pk=self.pk)
            .select_related("problem_set")
        )
        for other in existing:
            other_path = other.problem_set.path
            if path == other_path:
                continue
            if path.startswith(other_path) or other_path.startswith(path):
                raise ValidationError(
                    f"이 카테고리에 이미 트리상 조상 또는 자손인 "
                    f"'{other.problem_set.title}' 가 등록돼 있습니다."
                )


class CollapsedNode(models.Model):
    """A user's per-account "I've collapsed this node in the tree view" preference.

    Default behavior is everything-expanded; entries here mean the user clicked
    to collapse this ProblemSet, so its descendants should be hidden until they
    expand it again. Persists across sessions/devices (account-bound).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collapsed_nodes",
    )
    problem_set = models.ForeignKey(
        ProblemSet,
        on_delete=models.CASCADE,
        related_name="collapsed_by",
    )
    collapsed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "problem_set"],
                name="unique_user_collapsed_node",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} collapsed {self.problem_set}"


@receiver(m2m_changed, sender=ProblemSet.categories.through)
def _validate_category_membership_on_add(sender, instance, action, pk_set, **kwargs):
    """Apply CategoryMembership.clean() when callers use .categories.add()."""
    if action != "pre_add" or not pk_set:
        return
    if isinstance(instance, ProblemSet):
        for cat_pk in pk_set:
            sender(problem_set=instance, category_id=cat_pk).clean()
    else:
        # `instance` is the Category side (Category.problem_sets.add(...)).
        for ps_pk in pk_set:
            sender(category=instance, problem_set_id=ps_pk).clean()


class SolvedAcTier(models.IntegerChoices):
    """solved.ac tier numeric encoding (1=Bronze V ... 30=Master). Manual entry only."""

    BRONZE_V = 1, "Bronze V"
    BRONZE_IV = 2, "Bronze IV"
    BRONZE_III = 3, "Bronze III"
    BRONZE_II = 4, "Bronze II"
    BRONZE_I = 5, "Bronze I"
    SILVER_V = 6, "Silver V"
    SILVER_IV = 7, "Silver IV"
    SILVER_III = 8, "Silver III"
    SILVER_II = 9, "Silver II"
    SILVER_I = 10, "Silver I"
    GOLD_V = 11, "Gold V"
    GOLD_IV = 12, "Gold IV"
    GOLD_III = 13, "Gold III"
    GOLD_II = 14, "Gold II"
    GOLD_I = 15, "Gold I"
    PLATINUM_V = 16, "Platinum V"
    PLATINUM_IV = 17, "Platinum IV"
    PLATINUM_III = 18, "Platinum III"
    PLATINUM_II = 19, "Platinum II"
    PLATINUM_I = 20, "Platinum I"
    DIAMOND_V = 21, "Diamond V"
    DIAMOND_IV = 22, "Diamond IV"
    DIAMOND_III = 23, "Diamond III"
    DIAMOND_II = 24, "Diamond II"
    DIAMOND_I = 25, "Diamond I"
    RUBY_V = 26, "Ruby V"
    RUBY_IV = 27, "Ruby IV"
    RUBY_III = 28, "Ruby III"
    RUBY_II = 29, "Ruby II"
    RUBY_I = 30, "Ruby I"


class Problem(models.Model):
    """Canonical problem — same problem can appear in multiple ProblemSets.

    See spec v0.3 §3.1: per-set positioning (order_index, label) lives on
    `ProblemAppearance` so the same Problem can be linked into "ICPC Yokohama
    Regional" and "PTZ Camp" simultaneously without duplication.
    """

    title = models.CharField(max_length=200)
    external_url = models.URLField(blank=True)
    solved_ac_tier_manual = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=SolvedAcTier.choices,
    )

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class ProblemAppearance(models.Model):
    """One occurrence of a Problem inside a specific ProblemSet.

    A Problem may have multiple appearances (e.g. ICPC regional + a training
    camp). Position and label are per-appearance because labels differ across
    sets.
    """

    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="appearances",
    )
    problem_set = models.ForeignKey(
        ProblemSet,
        on_delete=models.CASCADE,
        related_name="appearances",
    )
    order_index = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=4)

    class Meta:
        ordering = ["problem_set_id", "order_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["problem_set", "order_index"],
                name="unique_appearance_order_within_set",
            ),
            models.UniqueConstraint(
                fields=["problem_set", "label"],
                name="unique_appearance_label_within_set",
            ),
            models.UniqueConstraint(
                fields=["problem", "problem_set"],
                name="unique_problem_per_set",
            ),
        ]
        indexes = [
            models.Index(fields=["problem_set", "order_index"]),
            models.Index(fields=["problem"]),
        ]

    def __str__(self) -> str:
        return f"{self.label}. {self.problem.title}"
