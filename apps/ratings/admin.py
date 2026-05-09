from django.contrib import admin

from .models import Comment, Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "problem_set", "stars", "updated_at")
    list_filter = ("stars",)
    search_fields = ("user__nickname", "user__email", "problem_set__title")
    autocomplete_fields = ("user", "problem_set")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("rating_user", "rating_problem_set", "short_body", "updated_at")
    search_fields = (
        "rating__user__nickname",
        "rating__problem_set__title",
        "body",
    )
    autocomplete_fields = ("rating",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)

    @admin.display(description="user")
    def rating_user(self, obj: Comment):
        return obj.rating.user

    @admin.display(description="problem_set")
    def rating_problem_set(self, obj: Comment):
        return obj.rating.problem_set

    @admin.display(description="body")
    def short_body(self, obj: Comment) -> str:
        return obj.body[:60] + ("…" if len(obj.body) > 60 else "")
