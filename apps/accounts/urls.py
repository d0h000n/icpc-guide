from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("me/", views.me, name="me"),
    path("u/<str:nickname>/", views.profile, name="profile"),
]
