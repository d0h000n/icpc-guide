"""Smoke tests for the home page — step 0 산출물 검증."""

from __future__ import annotations

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_anonymous_shows_login_cta(client) -> None:
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Problem Set Tracker" in response.content


@pytest.mark.django_db
def test_home_authenticated_shows_nickname(client, user) -> None:
    client.force_login(user)
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert user.nickname.encode() in response.content
    assert b"Hello" in response.content


@pytest.mark.django_db
def test_login_page_renders(client) -> None:
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
