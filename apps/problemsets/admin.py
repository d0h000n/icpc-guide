"""Admin: tree-aware ProblemSet management + inline ProblemAppearances + bulk paste."""

from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .bulk import BulkParseError, parse_children_text, parse_problems_text
from .models import Problem, ProblemAppearance, ProblemSet

_BULK_PROBLEMS_PLACEHOLDER = (
    "한 줄에 한 문제. 라벨 | 제목 | 외부 URL | (티어 1-30, 선택)\n"
    "예:\nA | Hasty Santa Claus | https://qoj.ac/contest/1101/problem/5470 | 12\n"
    "B | Interactive Number Guessing | https://qoj.ac/contest/1101/problem/5471 | 13"
)
_BULK_CHILDREN_PLACEHOLDER = (
    "한 줄에 한 자식 set. 제목 | (연도, 선택)\n예:\nYokohama 2020 | 2020\n"
    "Yokohama 2021 | 2021\nYokohama 2022 | 2022"
)


def _make_problemset_form():
    """movenodeform 위에 bulk-paste 텍스트필드를 얹은 admin form."""
    base = movenodeform_factory(ProblemSet)

    class ProblemSetAdminForm(base):
        bulk_problems = forms.CharField(
            required=False,
            widget=forms.Textarea(
                attrs={
                    "rows": 8,
                    "style": "font-family: monospace;",
                    "placeholder": _BULK_PROBLEMS_PLACEHOLDER,
                },
            ),
            help_text=(
                "저장 시 위 형식의 문제들을 이 set에 추가합니다. 기존 문제는 그대로 두고 새 라벨만 "
                "추가하며, 라벨 충돌 시 그 줄은 건너뜁니다. 같은 제목의 Problem은 재사용됩니다."
            ),
            label="문제 한꺼번에 추가",
        )
        bulk_children = forms.CharField(
            required=False,
            widget=forms.Textarea(
                attrs={
                    "rows": 5,
                    "style": "font-family: monospace;",
                    "placeholder": _BULK_CHILDREN_PLACEHOLDER,
                },
            ),
            help_text=(
                "저장 시 위 형식의 자식 ProblemSet들을 이 set 아래에 추가합니다. 같은 제목의 자식이 "
                "이미 있으면 건너뜁니다."
            ),
            label="자식 set 한꺼번에 추가",
        )

        def clean_bulk_problems(self):
            try:
                return parse_problems_text(self.cleaned_data.get("bulk_problems") or "")
            except BulkParseError as exc:
                raise forms.ValidationError(str(exc)) from exc

        def clean_bulk_children(self):
            try:
                return parse_children_text(self.cleaned_data.get("bulk_children") or "")
            except BulkParseError as exc:
                raise forms.ValidationError(str(exc)) from exc

    return ProblemSetAdminForm


class ProblemAppearanceInline(admin.TabularInline):
    model = ProblemAppearance
    extra = 0
    fields = ("label", "problem")
    autocomplete_fields = ("problem",)
    ordering = ("label",)


class CategoryMembershipInline(admin.TabularInline):
    model = ProblemSet.categories.through
    extra = 0
    autocomplete_fields = ("category",)
    verbose_name = "category membership"
    verbose_name_plural = "categories"


@admin.register(ProblemSet)
class ProblemSetAdmin(TreeAdmin):
    form = _make_problemset_form()
    list_display = ("title", "year", "depth", "numchild", "category_list")
    list_filter = ("categories", "year")
    search_fields = ("title", "description")
    readonly_fields = ("created_at",)
    inlines = [CategoryMembershipInline, ProblemAppearanceInline]

    @admin.display(description="Categories")
    def category_list(self, obj: ProblemSet) -> str:
        return ", ".join(obj.categories.values_list("short_name", flat=True)) or "—"

    def save_model(self, request, obj, form, change) -> None:
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change) -> None:
        super().save_related(request, form, formsets, change)
        self._apply_bulk_problems(request, form)
        self._apply_bulk_children(request, form)

    def _apply_bulk_problems(self, request, form) -> None:
        entries = form.cleaned_data.get("bulk_problems") or []
        if not entries:
            return
        instance: ProblemSet = form.instance
        added, skipped, reasons = 0, 0, []
        seen_labels: set[str] = set()
        for entry in entries:
            label = entry["label"]
            if label in seen_labels:
                skipped += 1
                reasons.append(f"'{label}' 라벨이 입력란 안에서 중복 — 건너뜀")
                continue
            seen_labels.add(label)
            clash = ProblemAppearance.objects.filter(problem_set=instance, label=label).first()
            if clash and clash.problem.title != entry["title"]:
                skipped += 1
                reasons.append(f"'{label}' 라벨이 이미 '{clash.problem.title}'에 사용 중 — 건너뜀")
                continue
            problem, _ = Problem.objects.get_or_create(
                title=entry["title"],
                defaults={
                    "external_url": entry["external_url"] or "",
                    "solved_ac_tier_manual": entry["tier"],
                },
            )
            _, created = ProblemAppearance.objects.get_or_create(
                problem=problem,
                problem_set=instance,
                defaults={"label": label},
            )
            if created:
                added += 1
            else:
                skipped += 1
                reasons.append(f"'{entry['title']}'은 이미 이 set에 등록됨 — 건너뜀")
        if added:
            messages.success(request, f"문제 {added}개 추가됨.")
        for r in reasons:
            messages.warning(request, r)

    def _apply_bulk_children(self, request, form) -> None:
        entries = form.cleaned_data.get("bulk_children") or []
        if not entries:
            return
        instance: ProblemSet = form.instance
        added, skipped = 0, 0
        for entry in entries:
            if instance.get_children().filter(title=entry["title"]).exists():
                skipped += 1
                continue
            instance.add_child(title=entry["title"], year=entry["year"])
            added += 1
        if added:
            messages.success(request, f"자식 set {added}개 추가됨.")
        if skipped:
            messages.warning(request, f"동명 자식이 이미 있어 {skipped}개 건너뜀.")


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "solved_ac_tier_manual", "appearance_count")
    list_filter = ("solved_ac_tier_manual",)
    search_fields = ("title",)
    ordering = ("title",)

    @admin.display(description="등장 횟수", ordering="appearances__count")
    def appearance_count(self, obj: Problem) -> int:
        return obj.appearances.count()


@admin.register(ProblemAppearance)
class ProblemAppearanceAdmin(admin.ModelAdmin):
    list_display = ("problem_set", "label", "problem")
    list_filter = ("problem_set__categories",)
    search_fields = ("problem__title", "label", "problem_set__title")
    autocomplete_fields = ("problem", "problem_set")
    ordering = ("problem_set", "label")
