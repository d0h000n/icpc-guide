"""User and profile-related models."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class ProfileVisibility(models.TextChoices):
    PRIVATE = "private", "Private"
    PUBLIC = "public", "Public"


class User(AbstractUser):
    """Custom user with nickname and external handles.

    Extending early so future migrations stay simple. Profile-visibility
    rules (spec §4.6.3) are enforced by views, not the model.
    """

    nickname = models.CharField(max_length=30, unique=True)
    profile_visibility = models.CharField(
        max_length=16,
        choices=ProfileVisibility.choices,
        default=ProfileVisibility.PRIVATE,
    )
    boj_handle = models.CharField(max_length=40, blank=True)
    codeforces_handle = models.CharField(max_length=40, blank=True)
    atcoder_handle = models.CharField(max_length=40, blank=True)

    # createsuperuser will prompt for these in addition to USERNAME_FIELD + password.
    REQUIRED_FIELDS = ["email", "nickname"]

    class Meta:
        ordering = ["nickname"]

    def __str__(self) -> str:
        return self.nickname or self.username
