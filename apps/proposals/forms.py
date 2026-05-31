"""Forms for user-submitted proposals (S3). Spec §4.1.4 + §4.1.6, §4.2."""

from __future__ import annotations

from django import forms

from apps.categories.models import Category
from apps.problemsets.bulk import BulkParseError, parse_problems_text
from apps.problemsets.models import ProblemSet

from .models import CategoryProposal, ProblemSetProposal

_INPUT_CLS = "input input-bordered w-full"
_TEXTAREA_CLS = "textarea textarea-bordered w-full"
_SELECT_CLS = "select select-bordered w-full"


class CategoryProposalForm(forms.ModelForm):
    """User-facing form for proposing a new Category (spec §4.2)."""

    class Meta:
        model = CategoryProposal
        fields = ("name", "short_name", "description", "url")
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT_CLS, "placeholder": "예: Japan"}),
            "short_name": forms.TextInput(
                attrs={"class": _INPUT_CLS, "placeholder": "예: japan"},
            ),
            "description": forms.Textarea(attrs={"class": _TEXTAREA_CLS, "rows": 3}),
            "url": forms.URLInput(attrs={"class": _INPUT_CLS}),
        }


class ProblemSetProposalForm(forms.Form):
    """User-facing form for proposing a new ProblemSet (spec §4.1.6).

    Mirrors §4.1.4 fields. We collect into a structured dict and stash it as
    ``ProblemSetProposal.payload`` for admin review (admin runs
    ``approve_problem_set_proposal`` from services.py to turn it into a real
    ProblemSet on approval).
    """

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": _INPUT_CLS, "placeholder": "예: ICPC Yokohama 2024"}
        ),
    )
    parent = forms.ModelChoiceField(
        queryset=ProblemSet.objects.order_by("path"),
        required=False,
        empty_label="(없음 - 최상위)",
        widget=forms.Select(attrs={"class": _SELECT_CLS}),
    )
    year = forms.IntegerField(
        required=False,
        min_value=1970,
        max_value=2100,
        widget=forms.NumberInput(attrs={"class": _INPUT_CLS, "placeholder": "예: 2024"}),
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.order_by("short_name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": _SELECT_CLS, "size": 6}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _TEXTAREA_CLS, "rows": 3}),
    )
    external_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": _INPUT_CLS}),
    )
    problems_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": _TEXTAREA_CLS,
                "rows": 6,
                "placeholder": (
                    "리프 set인 경우, 한 줄에 한 문제씩:\n"
                    "라벨 | 제목 | 외부 URL | (티어 1-30, 선택)\n"
                    "예: A | Apple Tree | https://example.com/a | 15"
                ),
            },
        ),
        help_text="내부 노드(자식 set으로 채워질 예정)이면 비워두세요.",
    )

    def clean_problems_text(self) -> list[dict]:
        try:
            return parse_problems_text(self.cleaned_data.get("problems_text") or "")
        except BulkParseError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def to_payload(self) -> dict:
        """Snapshot form data as a JSON-safe dict for ProblemSetProposal.payload."""
        cd = self.cleaned_data
        parent: ProblemSet | None = cd.get("parent")
        return {
            "title": cd["title"],
            "parent_id": parent.pk if parent else None,
            "year": cd.get("year"),
            "description": cd.get("description") or "",
            "external_url": cd.get("external_url") or "",
            "category_short_names": [c.short_name for c in cd.get("categories") or []],
            "problems": cd.get("problems_text") or [],
        }


class ProblemSetProposalCreateForm(ProblemSetProposalForm):
    """Wraps the field form so the view can save in one call."""

    def save(self, user) -> ProblemSetProposal:
        return ProblemSetProposal.objects.create(user=user, payload=self.to_payload())
