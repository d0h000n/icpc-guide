"""User-submitted proposals (spec §3.1, §4.1.6, §4.2).

CategoryProposal & ProblemSetProposal land in an admin review queue. On
approval the admin turns them into real Category / ProblemSet rows.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ProposalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class _ProposalBase(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    status = models.CharField(
        max_length=16,
        choices=ProposalStatus.choices,
        default=ProposalStatus.PENDING,
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CategoryProposal(_ProposalBase):
    """Spec §4.2: a user requesting that a new Category be added."""

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)

    class Meta(_ProposalBase.Meta):
        verbose_name = "category proposal"
        verbose_name_plural = "category proposals"

    def __str__(self) -> str:
        return f"CategoryProposal({self.short_name}, {self.status})"


class ProblemSetProposal(_ProposalBase):
    """Spec §4.1.6: a user proposes a new ProblemSet.

    Payload is intentionally a free-form JSON dict so the proposal can carry
    nested set/problem structure without us locking the shape. Admin reviews
    and converts to actual tree on approval.
    """

    payload = models.JSONField(default=dict)

    class Meta(_ProposalBase.Meta):
        verbose_name = "problem set proposal"
        verbose_name_plural = "problem set proposals"

    def __str__(self) -> str:
        title = self.payload.get("title", "(no title)")
        return f"ProblemSetProposal({title}, {self.status})"
