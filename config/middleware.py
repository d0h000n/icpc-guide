"""Project-wide HTTP-response middleware."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponseBase


class NoStoreMiddleware:
    """Force `Cache-Control: no-store` on every dynamic response.

    Every page in this app shows nav state derived from the session cookie
    (logged-in nickname vs. login button, owner-only buttons on team pages,
    per-user solve toggles, etc.), so any caching by browsers, bfcache, or
    intermediate proxies risks displaying stale auth state across tabs and
    back/forward navigation.

    Static assets (served by WhiteNoise under ``STATIC_URL``) keep their own
    long-cache headers — we explicitly skip them.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self.get_response(request)
        static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
        if request.path.startswith(static_url):
            return response
        # Keep Vary: Cookie (added by SessionMiddleware when session is read)
        # for any well-behaved proxy that does honor it.
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response["Pragma"] = "no-cache"

        # Cross-tab auth-state marker (read by base.html JS).
        # Updates on every response. When a tab regains focus, its embedded
        # init marker is compared to the live cookie value — mismatch triggers
        # a reload so a tab opened before login/logout doesn't show stale UI.
        user = getattr(request, "user", None)
        marker = str(user.pk) if (user is not None and user.is_authenticated) else "0"
        if request.COOKIES.get("auth_marker") != marker:
            response.set_cookie(
                "auth_marker",
                marker,
                max_age=60 * 60 * 24 * 365,
                samesite="Lax",
                httponly=False,
            )
        return response
