"""Team, TeamMember, TeamInvite. Spec §3.1, §4.4."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
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
        # DO_NOTHING because the pre_delete signal in apps.TeamsConfig.ready()
        # transfers ownership before the user is removed. PROTECT would block
        # the delete before the signal could fire; SET_NULL would clobber the
        # signal's reassignment after-the-fact.
        on_delete=models.DO_NOTHING,
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

    def save(self, *args, **kwargs) -> None:
        # Only enforce the 50-member cap here — the unique-together constraint
        # is still surfaced at DB level (IntegrityError), matching the pattern
        # the other apps in this project use.
        if not self.pk:
            self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.team_id and not self.pk:
            # Only enforce on new memberships — existing ones are fine to edit.
            current = TeamMember.objects.filter(team_id=self.team_id).count()
            if current >= Team.MAX_MEMBERS:
                raise ValidationError(f"팀 인원이 {Team.MAX_MEMBERS}명에 도달했습니다 (spec §3.3).")


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


def transfer_owned_teams_on_user_delete(sender, instance, **kwargs):
    """Spec §2.4: when a team owner is deleted, hand ownership to the
    oldest-joined remaining member. Empty teams are deleted.

    Runs in pre_delete on the User model so Team.owner FK PROTECT doesn't fire.
    Connected in apps.TeamsConfig.ready().
    """
    for team in Team.objects.filter(owner=instance):
        successor = (
            TeamMember.objects.filter(team=team)
            .exclude(user=instance)
            .order_by("joined_at")
            .first()
        )
        if successor is None:
            team.delete()
            continue
        successor.role = TeamMemberRole.OWNER
        successor.save(update_fields=["role"])
        team.owner = successor.user
        team.save(update_fields=["owner", "updated_at"])
        TeamMember.objects.filter(team=team, user=instance).delete()
