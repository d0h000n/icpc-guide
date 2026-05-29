"""Proposal review services. Spec §4.1.6, §4.2.

Each `approve_*` runs inside a transaction so a half-approved proposal can never
leak (e.g. real Category created but proposal still PENDING).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.categories.models import Category
from apps.problemsets.models import Problem, ProblemAppearance, ProblemSet

from .models import CategoryProposal, ProblemSetProposal, ProposalStatus


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
def approve_problem_set_proposal(
    proposal: ProblemSetProposal,
    reviewer,
    *,
    admin_note: str = "",
) -> ProblemSet:
    """Promote a pending ProblemSetProposal into a real ProblemSet tree node.

    Payload schema (all optional except `title`):

        {
          "title": "ICPC Asia Yokohama Regional 2024",
          "parent_id": 42,                # pk of parent ProblemSet, omit for root
          "year": 2024,
          "description": "...",
          "external_url": "https://...",
          "category_short_names": ["japan", "icpc"],
          "problems": [
            {"label": "A", "title": "Apple Tree",
             "external_url": "https://...", "tier": 15}
          ]
        }

    Raises ProposalError on bad state, missing title, unknown parent/category,
    or duplicate label/order within the new set.
    """
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalError(f"proposal already {proposal.status}")

    payload = proposal.payload or {}
    title = (payload.get("title") or "").strip()
    if not title:
        raise ProposalError("payload.title is required")

    parent_id = payload.get("parent_id")
    parent: ProblemSet | None = None
    if parent_id is not None:
        try:
            parent = ProblemSet.objects.get(pk=parent_id)
        except ProblemSet.DoesNotExist as exc:
            raise ProposalError(f"parent ProblemSet #{parent_id} not found") from exc

    node_kwargs = dict(
        title=title,
        year=payload.get("year"),
        description=payload.get("description") or "",
        external_url=payload.get("external_url") or "",
        created_by=proposal.user,
    )
    if parent is None:
        new_set = ProblemSet.add_root(**node_kwargs)
    else:
        new_set = parent.add_child(**node_kwargs)

    short_names = payload.get("category_short_names") or []
    if short_names:
        cats = list(Category.objects.filter(short_name__in=short_names))
        missing = set(short_names) - {c.short_name for c in cats}
        if missing:
            raise ProposalError(f"unknown category short_names: {sorted(missing)}")
        for cat in cats:
            new_set.categories.add(cat)

    problems_payload = payload.get("problems") or []
    for idx, item in enumerate(problems_payload, start=1):
        p_title = (item.get("title") or "").strip()
        if not p_title:
            raise ProposalError(f"problems[{idx - 1}].title is required")
        problem = Problem.objects.create(
            title=p_title,
            external_url=item.get("external_url") or "",
            solved_ac_tier_manual=item.get("tier"),
        )
        ProblemAppearance.objects.create(
            problem=problem,
            problem_set=new_set,
            label=(item.get("label") or "")[:4] or chr(ord("A") + idx - 1),
        )

    proposal.status = ProposalStatus.APPROVED
    proposal.reviewed_at = timezone.now()
    proposal.reviewed_by = reviewer
    if admin_note:
        proposal.admin_note = admin_note
    proposal.save(update_fields=["status", "reviewed_at", "reviewed_by", "admin_note"])
    return new_set


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
