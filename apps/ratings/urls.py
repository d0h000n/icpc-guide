from django.urls import path

from . import views

app_name = "ratings"

urlpatterns = [
    path("rate/<int:problem_set_pk>/", views.rate, name="rate"),
    path("unrate/<int:problem_set_pk>/", views.unrate, name="unrate"),
    path("comment/<int:problem_set_pk>/", views.comment_upsert, name="comment_upsert"),
    path(
        "comment/<int:problem_set_pk>/delete/",
        views.comment_delete,
        name="comment_delete",
    ),
    path("raters/<int:problem_set_pk>/", views.raters_list, name="raters"),
]
