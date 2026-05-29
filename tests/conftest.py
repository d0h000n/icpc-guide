"""Project-wide pytest fixtures."""

from __future__ import annotations

import pytest

from apps.accounts.models import User


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    """Use non-manifest static storage in tests.

    Prod/dev use WhiteNoise's ManifestStaticFilesStorage, which requires a
    `collectstatic` manifest. Tests never run collectstatic, so any template
    rendering `{% static %}` (e.g. tier badges) would raise "Missing
    staticfiles manifest entry". Swap in the plain storage so `{% static %}`
    just builds `/static/...` URLs.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="x",
        nickname="alice",
    )
