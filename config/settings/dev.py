"""Local development settings."""

import os

from .base import *  # noqa: F401, F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Email backend prints to console during dev.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Allow overriding via .env, but default to insecure dev key.
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")

INTERNAL_IPS = ["127.0.0.1"]

# --- Dev origins (VS Code port forwarding + GitHub Codespaces) ---
# Two ways to reach a dev server in Codespaces:
#   (a) VS Code forwards the port to the user's machine as localhost:<port>
#   (b) GitHub Codespaces public URL: https://<name>-<port>.app.github.dev
# Both must be trusted by Django's CSRF middleware on form POST.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "https://localhost:8000",
    "http://127.0.0.1:8000",
    "https://127.0.0.1:8000",
    "https://*.app.github.dev",
]

if os.environ.get("CODESPACES") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    _cs_name = os.environ.get("CODESPACE_NAME")
    _cs_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    if _cs_name:
        # Explicit origin in addition to the wildcard, in case wildcard matching
        # rejects something (Django evaluates exact entries first).
        CSRF_TRUSTED_ORIGINS.append(f"https://{_cs_name}-8000.{_cs_domain}")
