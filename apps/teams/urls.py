from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    path("", views.team_list, name="list"),
    path("new/", views.team_create, name="create"),
    path("<slug:slug>/", views.team_detail, name="detail"),
    path("<slug:slug>/edit/", views.team_edit, name="edit"),
    path(
        "<slug:slug>/members/<int:member_id>/remove/",
        views.member_remove,
        name="member_remove",
    ),
    path(
        "<slug:slug>/transfer-ownership/",
        views.transfer_ownership,
        name="transfer_ownership",
    ),
    path("<slug:slug>/leave/", views.leave_team, name="leave"),
]
