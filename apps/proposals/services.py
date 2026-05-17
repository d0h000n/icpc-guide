"""Proposal review services. Spec §4.1.6, §4.2.

Each `approve_*` runs inside a transaction so a half-approved proposal can never
leak (e.g. real Category created but proposal still PENDING).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.categories.models import Category

from .models import CategoryProposal, ProposalStatus


class ProposalError(Exception):
    """Caller-visible failure: bad state or invalid payload."""


@transaction.atomic
def approve_category_proposal(
    proposal: CategoryProposal,
    reviewer,
    *,
    admin_note: str = "",
) -> Category:
    """Promote a pending CategoryProposal to a real Category.

    Raises ProposalError if the proposal isn't pending or if the resulting
    short_name collides with an existing Category.
    """
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalError(f"proposal already {proposal.status}")

    if Category.objects.filter(short_name=proposal.short_name).exists():
        raise ProposalError(f"카테고리 short_name '{proposal.short_name}' 가 이미 사용 중입니다.")

    category = Category.objects.create(
        name=proposal.name,
        short_name=proposal.short_name,
        description=proposal.description,
        url=proposal.url,
    )

    proposal.status = ProposalStatus.APPROVED
    proposal.reviewed_at = timezone.now()
    proposal.reviewed_by = reviewer
    if admin_note:
        proposal.admin_note = admin_note
    proposal.save(update_fields=["status", "reviewed_at", "reviewed_by", "admin_note"])
    return category


@transaction.atomic
def reject_proposal(proposal, reviewer, *, admin_note: str = "") -> None:
    """Mark a pending proposal (Category or ProblemSet) as rejected."""
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalError(f"proposal already {proposal.status}")
    proposal.status = ProposalStatus.REJECTED
    proposal.reviewed_at = timezone.now()
    proposal.reviewed_by = reviewer
    if admin_note:
        proposal.admin_note = admin_note
    proposal.save(update_fields=["status", "reviewed_at", "reviewed_by", "admin_note"])
