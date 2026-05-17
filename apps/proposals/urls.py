from django.urls import path

from . import views

app_name = "proposals"

urlpatterns = [
    path("", views.propose_index, name="index"),
    path("category/", views.propose_category, name="category"),
    path("problem-set/", views.propose_problem_set, name="problem_set"),
]
