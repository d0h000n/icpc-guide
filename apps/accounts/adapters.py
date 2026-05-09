"""allauth adapters — disable password signup, allow OAuth signup with nickname capture."""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """Disable email/password signup. The product is OAuth-only."""

    def is_open_for_signup(self, request) -> bool:
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Allow OAuth signup; nickname capture happens on the social signup form."""

    def is_open_for_signup(self, request, sociallogin) -> bool:
        return True
