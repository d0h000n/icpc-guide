from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "nickname",
                    "profile_visibility",
                    "boj_handle",
                    "codeforces_handle",
                    "atcoder_handle",
                )
            },
        ),
    )
    list_display = ("username", "nickname", "email", "is_staff", "profile_visibility")
    search_fields = ("username", "nickname", "email")
