"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import healthz, home, whoami

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("whoami", whoami, name="whoami"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("sets/", include("apps.problemsets.urls")),
    path("categories/", include("apps.categories.urls")),
    path("solve/", include("apps.solving.urls")),
    path("ratings/", include("apps.ratings.urls")),
    path("teams/", include("apps.teams.urls")),
    path("propose/", include("apps.proposals.urls")),
    path("", home, name="home"),
    path("", include("apps.accounts.urls")),
]
