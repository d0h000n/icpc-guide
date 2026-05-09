"""SolveRecord — one row per (user, problem) where the user has marked the problem solved.

Spec §3.1: "id, user_id, problem_id, solved_at, note (≤ 200자, 선택). record 존재 = solved."
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class SolveRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solve_records",
    )
    problem = models.ForeignKey(
        "problemsets.Problem",
        on_delete=models.CASCADE,
        related_name="solve_records",
    )
    solved_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-solved_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "problem"],
                name="unique_user_problem_solve",
            ),
        ]
        indexes = [
            # Lookups by problem alone — used in team context (§4.4) to find
            # "which members solved this problem".
            models.Index(fields=["problem"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} solved {self.problem}"
