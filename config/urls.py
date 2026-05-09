"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import healthz, home

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("sets/", include("apps.problemsets.urls")),
    path("categories/", include("apps.categories.urls")),
    path("solve/", include("apps.solving.urls")),
    path("ratings/", include("apps.ratings.urls")),
    path("", home, name="home"),
    path("", include("apps.accounts.urls")),
]
