"""Rating + Comment models. Spec §3.1, §4.5.

Comment is modeled as a 1-1 extension of Rating (FK on Comment, CASCADE).
This satisfies the spec rules in one shot:
  - "사용자×set 당 1개" via Rating's (user, problem_set) UNIQUE.
  - "Rating 없이 Comment 단독 존재 불가" via the required FK.
  - "Rating 삭제 시 Comment 함께 삭제" via on_delete=CASCADE.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models


class Rating(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    problem_set = models.ForeignKey(
        "problemsets.ProblemSet",
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    stars = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "problem_set"],
                name="unique_user_problemset_rating",
            ),
            models.CheckConstraint(
                condition=models.Q(stars__gte=1) & models.Q(stars__lte=5),
                name="rating_stars_range",
            ),
        ]
        indexes = [
            # Aggregate-by-set hot path (avg, count).
            models.Index(fields=["problem_set"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.problem_set}: {self.stars}★"


class Comment(models.Model):
    rating = models.OneToOneField(
        Rating,
        on_delete=models.CASCADE,
        related_name="comment",
    )
    body = models.TextField(max_length=300, validators=[MaxLengthValidator(300)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Comment by {self.rating.user} on {self.rating.problem_set}"
