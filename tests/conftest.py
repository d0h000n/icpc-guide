"""Project-wide pytest fixtures."""

from __future__ import annotations

import pytest

from apps.accounts.models import User


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="x",
        nickname="alice",
    )
