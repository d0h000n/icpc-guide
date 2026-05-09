from django.contrib import admin

from .models import Team, TeamInvite, TeamMember


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("joined_at",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "visibility", "member_count", "updated_at")
    list_filter = ("visibility",)
    search_fields = ("name", "slug", "owner__nickname")
    autocomplete_fields = ("owner",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [TeamMemberInline]

    @admin.display(description="members")
    def member_count(self, obj: Team) -> int:
        return obj.memberships.count()


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("team__name", "user__nickname")
    autocomplete_fields = ("team", "user")
    readonly_fields = ("joined_at",)


@admin.register(TeamInvite)
class TeamInviteAdmin(admin.ModelAdmin):
    list_display = ("team", "invited_by", "invitee_user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("team__name", "token")
    autocomplete_fields = ("team", "invited_by", "invitee_user")
    readonly_fields = ("token", "created_at", "accepted_at")
