from django.urls import path

from . import views

app_name = "solving"

urlpatterns = [
    path(
        "toggle/<int:problem_set_pk>/<int:problem_pk>/",
        views.toggle_solve,
        name="toggle",
    ),
]
