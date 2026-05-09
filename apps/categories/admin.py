from django.contrib import admin

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("short_name", "name", "url", "updated_at")
    search_fields = ("short_name", "name")
    ordering = ("short_name",)
    readonly_fields = ("created_at", "updated_at")
