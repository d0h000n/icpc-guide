"""Tests for the user-proposal review queue (spec §4.1.6, §4.2)."""

from __future__ import annotations

import pytest

from apps.categories.models import Category
from apps.proposals.models import CategoryProposal, ProposalStatus
from apps.proposals.services import (
    ProposalError,
    approve_category_proposal,
    reject_proposal,
)

from .factories import CategoryFactory, UserFactory

pytestmark = pytest.mark.django_db


def _new_category_proposal(**overrides) -> CategoryProposal:
    defaults = dict(
        user=UserFactory(),
        name="Japan",
        short_name="japan",
        description="ICPC Asia Yokohama 등 일본 권역 대회",
        url="https://example.com/japan",
    )
    defaults.update(overrides)
    return CategoryProposal.objects.create(**defaults)


def test_approve_category_proposal_creates_real_category():
    reviewer = UserFactory()
    proposal = _new_category_proposal()

    category = approve_category_proposal(proposal, reviewer)

    proposal.refresh_from_db()
    assert proposal.status == ProposalStatus.APPROVED
    assert proposal.reviewed_by == reviewer
    assert proposal.reviewed_at is not None

    assert isinstance(category, Category)
    assert category.short_name == "japan"
    assert category.name == "Japan"
    assert category.description.startswith("ICPC")
    assert category.url == "https://example.com/japan"


def test_approve_rejects_duplicate_short_name():
    CategoryFactory(short_name="japan")
    proposal = _new_category_proposal(short_name="japan")

    with pytest.raises(ProposalError, match="이미 사용 중"):
        approve_category_proposal(proposal, UserFactory())

    proposal.refresh_from_db()
    assert proposal.status == ProposalStatus.PENDING
    # No leftover Category from a half-applied transaction.
    assert Category.objects.filter(short_name="japan").count() == 1


def test_approve_twice_rejected():
    proposal = _new_category_proposal()
    approve_category_proposal(proposal, UserFactory())

    with pytest.raises(ProposalError, match="already"):
        approve_category_proposal(proposal, UserFactory())


def test_reject_marks_proposal_rejected_with_note():
    reviewer = UserFactory()
    proposal = _new_category_proposal()

    reject_proposal(proposal, reviewer, admin_note="중복")

    proposal.refresh_from_db()
    assert proposal.status == ProposalStatus.REJECTED
    assert proposal.admin_note == "중복"
    assert proposal.reviewed_by == reviewer
    # And no Category was created.
    assert not Category.objects.filter(short_name=proposal.short_name).exists()


def test_reject_after_approve_is_an_error():
    proposal = _new_category_proposal()
    approve_category_proposal(proposal, UserFactory())

    with pytest.raises(ProposalError):
        reject_proposal(proposal, UserFactory())


def test_admin_action_approve_creates_categories(client):
    admin = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(admin)

    p1 = _new_category_proposal(short_name="korea", name="Korea")
    p2 = _new_category_proposal(short_name="japan", name="Japan")

    url = "/admin/proposals/categoryproposal/"
    resp = client.post(
        url,
        data={
            "action": "approve_selected",
            "_selected_action": [str(p1.pk), str(p2.pk)],
            "index": "0",
        },
    )
    # Admin redirects back to the changelist on action success.
    assert resp.status_code == 302

    p1.refresh_from_db()
    p2.refresh_from_db()
    assert p1.status == ProposalStatus.APPROVED
    assert p2.status == ProposalStatus.APPROVED
    assert Category.objects.filter(short_name="korea").exists()
    assert Category.objects.filter(short_name="japan").exists()


def test_admin_action_reject_marks_pending_rejected(client):
    admin = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(admin)

    proposal = _new_category_proposal()

    url = "/admin/proposals/categoryproposal/"
    resp = client.post(
        url,
        data={
            "action": "reject_selected",
            "_selected_action": [str(proposal.pk)],
            "index": "0",
        },
    )
    assert resp.status_code == 302

    proposal.refresh_from_db()
    assert proposal.status == ProposalStatus.REJECTED
    assert not Category.objects.filter(short_name=proposal.short_name).exists()


def test_admin_change_list_loads(client, settings):
    # The admin templates use {% static %} which goes through
    # whitenoise's manifest storage in dev/prod; tests don't collectstatic.
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    admin = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(admin)
    _new_category_proposal()

    resp = client.get("/admin/proposals/categoryproposal/")
    assert resp.status_code == 200

    resp2 = client.get("/admin/proposals/problemsetproposal/")
    assert resp2.status_code == 200
