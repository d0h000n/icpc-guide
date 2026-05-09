"""Admin: tree-aware ProblemSet management + inline ProblemAppearances."""

from __future__ import annotations

from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Problem, ProblemAppearance, ProblemSet


class ProblemAppearanceInline(admin.TabularInline):
    model = ProblemAppearance
    extra = 0
    fields = ("order_index", "label", "problem")
    autocomplete_fields = ("problem",)
    ordering = ("order_index",)


class CategoryMembershipInline(admin.TabularInline):
    model = ProblemSet.categories.through
    extra = 0
    autocomplete_fields = ("category",)
    verbose_name = "category membership"
    verbose_name_plural = "categories"


@admin.register(ProblemSet)
class ProblemSetAdmin(TreeAdmin):
    form = movenodeform_factory(ProblemSet)
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
    list_display = ("problem_set", "order_index", "label", "problem")
    list_filter = ("problem_set__categories",)
    search_fields = ("problem__title", "label", "problem_set__title")
    autocomplete_fields = ("problem", "problem_set")
    ordering = ("problem_set", "order_index")
