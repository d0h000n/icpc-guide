"""Category — cross-cutting grouping of ProblemSets (e.g. "Japan", "Korea").

Spec v0.4 §3.1: replaces the v0.3 `Source` concept. A Category bundles several
ProblemSets together for browsing convenience, independent of the canonical
ProblemSet tree. Admin-managed by default; user-owned categories are a
backlog item (단계 6+).
"""

from __future__ import annotations

from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["short_name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.short_name
