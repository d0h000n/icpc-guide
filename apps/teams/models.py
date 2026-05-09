"""Team, TeamMember, TeamInvite. Spec §3.1, §4.4."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models


def _make_token() -> str:
    return secrets.token_urlsafe(32)


class TeamVisibility(models.TextChoices):
    PRIVATE = "private", "Private"
    PUBLIC = "public", "Public"


class TeamMemberRole(models.TextChoices):
    OWNER = "owner", "Owner"
    MEMBER = "member", "Member"


class TeamInviteStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REVOKED = "revoked", "Revoked"


class Team(models.Model):
    """A group of users that can share a solve view (spec §4.4)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )
    visibility = models.CharField(
        max_length=16,
        choices=TeamVisibility.choices,
        default=TeamVisibility.PRIVATE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MAX_MEMBERS = 50  # spec §3.3

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name


class TeamMember(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=TeamMemberRole.choices,
        default=TeamMemberRole.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="unique_team_member",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["team"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.team} ({self.role})"


class TeamInvite(models.Model):
    """An invite link with token, optionally bound to a specific invitee."""

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_team_invites",
    )
    invitee_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_team_invites",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_make_token,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=TeamInviteStatus.choices,
        default=TeamInviteStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team"]),
        ]

    def __str__(self) -> str:
        return f"Invite to {self.team} ({self.status})"
