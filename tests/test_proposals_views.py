"""Tests for the user-facing proposal pages (S3, spec §4.1.6, §4.2)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.proposals.models import (
    CategoryProposal,
    ProblemSetProposal,
    ProposalStatus,
)

from .factories import CategoryFactory, ProblemSetRootFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_anonymous_redirected_to_login(client):
    for name in ("proposals:index", "proposals:category", "proposals:problem_set"):
        resp = client.get(reverse(name))
        assert resp.status_code == 302
        assert "login" in resp["Location"] or "accounts" in resp["Location"]


def test_index_lists_only_my_proposals(client):
    me = UserFactory()
    other = UserFactory()
    mine = CategoryProposal.objects.create(
        user=me, name="Japan", short_name="japan", description="", url=""
    )
    not_mine = CategoryProposal.objects.create(
        user=other, name="Korea", short_name="korea", description="", url=""
    )

    client.force_login(me)
    resp = client.get(reverse("proposals:index"))

    assert resp.status_code == 200
    items = list(resp.context["my_category_proposals"])
    assert mine in items
    assert not_mine not in items


def test_propose_category_post_creates_pending_proposal(client):
    me = UserFactory()
    client.force_login(me)

    resp = client.post(
        reverse("proposals:category"),
        data={
            "name": "Japan",
            "short_name": "japan",
            "description": "일본 권역",
            "url": "https://example.com/japan",
        },
    )
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("proposals:index"))

    proposal = CategoryProposal.objects.get(user=me, short_name="japan")
    assert proposal.status == ProposalStatus.PENDING
    assert proposal.name == "Japan"


def test_propose_category_invalid_short_name_keeps_form(client):
    me = UserFactory()
    client.force_login(me)

    # short_name is required (max_length=20, blank=False).
    resp = client.post(
        reverse("proposals:category"),
        data={"name": "Japan", "short_name": "", "description": "", "url": ""},
    )
    assert resp.status_code == 200
    assert not CategoryProposal.objects.exists()


def test_propose_problem_set_post_builds_payload(client):
    me = UserFactory()
    cat = CategoryFactory(short_name="japan")
    parent = ProblemSetRootFactory(title="ICPC")
    client.force_login(me)

    resp = client.post(
        reverse("proposals:problem_set"),
        data={
            "title": "ICPC Asia Yokohama 2024",
            "parent": str(parent.pk),
            "year": "2024",
            "categories": [str(cat.pk)],
            "description": "Regional",
            "external_url": "https://icpc.example/y2024",
            "problems_text": ("A | Apple | https://a.example | 12\nB | Banana |  | 7\nC | Cherry"),
        },
    )
    assert resp.status_code == 302

    proposal = ProblemSetProposal.objects.get(user=me)
    payload = proposal.payload
    assert payload["title"] == "ICPC Asia Yokohama 2024"
    assert payload["parent_id"] == parent.pk
    assert payload["year"] == 2024
    assert payload["category_short_names"] == ["japan"]
    assert payload["description"] == "Regional"
    assert payload["external_url"] == "https://icpc.example/y2024"
    assert payload["problems"] == [
        {"label": "A", "title": "Apple", "external_url": "https://a.example", "tier": 12},
        {"label": "B", "title": "Banana", "external_url": "", "tier": 7},
        {"label": "C", "title": "Cherry", "external_url": "", "tier": None},
    ]


def test_propose_problem_set_problems_text_validation(client):
    me = UserFactory()
    client.force_login(me)

    resp = client.post(
        reverse("proposals:problem_set"),
        data={
            "title": "ICPC",
            "parent": "",
            "year": "",
            "categories": [],
            "description": "",
            "external_url": "",
            "problems_text": "missing-pipe",
        },
    )
    assert resp.status_code == 200
    assert not ProblemSetProposal.objects.exists()


def test_propose_problem_set_internal_node_blank_problems(client):
    me = UserFactory()
    client.force_login(me)

    resp = client.post(
        reverse("proposals:problem_set"),
        data={
            "title": "ICPC",
            "parent": "",
            "year": "",
            "categories": [],
            "description": "internal node — children later",
            "external_url": "",
            "problems_text": "",
        },
    )
    assert resp.status_code == 302
    proposal = ProblemSetProposal.objects.get(user=me)
    assert proposal.payload["problems"] == []


def test_nav_link_shown_only_to_authenticated(client):
    # Guest: no nav link.
    resp = client.get("/")
    assert "/propose/" not in resp.content.decode()

    me = UserFactory()
    client.force_login(me)
    resp = client.get("/")
    assert "/propose/" in resp.content.decode()
