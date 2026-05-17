"""Admin review queue for user-submitted proposals (spec §4.1.6, §4.2)."""

from __future__ import annotations

from django.contrib import admin, messages
from django.http import HttpRequest

from .models import CategoryProposal, ProblemSetProposal
from .services import ProposalError, approve_category_proposal, reject_proposal


class _BaseProposalAdmin(admin.ModelAdmin):
    list_filter = ("status",)
    readonly_fields = ("user", "created_at", "reviewed_at", "reviewed_by")
    ordering = ("-created_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Proposals are submitted by users; admins review, not create.
        return False


@admin.register(CategoryProposal)
class CategoryProposalAdmin(_BaseProposalAdmin):
    list_display = ("short_name", "name", "user", "status", "created_at")
    search_fields = ("short_name", "name", "user__nickname")
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="선택된 제안 승인 (Category 생성)")
    def approve_selected(self, request: HttpRequest, queryset) -> None:
        approved = 0
        for proposal in queryset:
            try:
                approve_category_proposal(proposal, request.user)
                approved += 1
            except ProposalError as exc:
                messages.error(request, f"#{proposal.pk}: {exc}")
        if approved:
            messages.success(request, f"{approved}건 승인 완료.")

    @admin.action(description="선택된 제안 반려")
    def reject_selected(self, request: HttpRequest, queryset) -> None:
        rejected = 0
        for proposal in queryset:
            try:
                reject_proposal(proposal, request.user)
                rejected += 1
            except ProposalError as exc:
                messages.error(request, f"#{proposal.pk}: {exc}")
        if rejected:
            messages.success(request, f"{rejected}건 반려 완료.")


@admin.register(ProblemSetProposal)
class ProblemSetProposalAdmin(_BaseProposalAdmin):
    list_display = ("payload_title", "user", "status", "created_at")
    search_fields = ("user__nickname",)
    actions = ("reject_selected",)

    @admin.display(description="title")
    def payload_title(self, obj: ProblemSetProposal) -> str:
        return obj.payload.get("title") or "(no title)"

    @admin.action(description="선택된 제안 반려")
    def reject_selected(self, request: HttpRequest, queryset) -> None:
        rejected = 0
        for proposal in queryset:
            try:
                reject_proposal(proposal, request.user)
                rejected += 1
            except ProposalError as exc:
                messages.error(request, f"#{proposal.pk}: {exc}")
        if rejected:
            messages.success(request, f"{rejected}건 반려 완료.")

    # NOTE on approval: ProblemSetProposal carries a free-form JSON payload;
    # rather than a one-click approve, admins copy/paste payload into the real
    # ProblemSet form (Categories→ProblemSet) and then mark this proposal
    # approved via the change form. Spec §4.1.6 leaves the exact workflow to
    # admin discretion. A scripted approve_problem_set_proposal() lives in
    # services.py once the payload schema is locked (step 7.2).

    def get_actions(self, request: HttpRequest):
        # Keep the bulk-reject action; approval is per-record via change form.
        return super().get_actions(request)
