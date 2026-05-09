from django.apps import AppConfig


class CategoriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.categories"
    # Keep app label `sources` so existing migration history (sources_*) survives
    # the directory rename without a destructive table migration. Internal-only
    # detail; user-facing names everywhere are "Category".
    label = "sources"
    verbose_name = "Categories"
