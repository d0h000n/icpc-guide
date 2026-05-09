from django.urls import path

from . import views

app_name = "problemsets"

urlpatterns = [
    path("", views.problem_set_list, name="list"),
    path("<int:pk>/", views.problem_set_detail, name="detail"),
]
