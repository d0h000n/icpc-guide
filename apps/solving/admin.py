from django.contrib import admin

from .models import SolveRecord


@admin.register(SolveRecord)
class SolveRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "problem", "solved_at")
    list_filter = ("problem__appearances__problem_set__categories",)
    search_fields = (
        "user__nickname",
        "user__email",
        "problem__title",
        "problem__appearances__problem_set__title",
    )
    autocomplete_fields = ("user", "problem")
    readonly_fields = ("solved_at",)
    ordering = ("-solved_at",)
