"""Per-account tree expand/collapse on /sets/."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.problemsets.models import CollapsedNode, ProblemSet

from .factories import UserFactory


def _toggle_url(pset):
    return reverse("problemsets:toggle_collapse", args=[pset.pk])


# ---------- toggle endpoint ----------


@pytest.mark.django_db
def test_toggle_creates_record_when_expanded(client) -> None:
    user = UserFactory()
    pset = ProblemSet.add_root(title="ICPC")
    client.force_login(user)

    response = client.post(_toggle_url(pset))
    assert response.status_code == 204
    assert response.headers.get("HX-Trigger") == "tree-changed"
    assert CollapsedNode.objects.filter(user=user, problem_set=pset).exists()


@pytest.mark.django_db
def test_toggle_deletes_record_when_collapsed(client) -> None:
    user = UserFactory()
    pset = ProblemSet.add_root(title="ICPC")
    CollapsedNode.objects.create(user=user, problem_set=pset)
    client.force_login(user)

    response = client.post(_toggle_url(pset))
    assert response.status_code == 204
    assert not CollapsedNode.objects.filter(user=user, problem_set=pset).exists()


@pytest.mark.django_db
def test_toggle_requires_login(client) -> None:
    pset = ProblemSet.add_root(title="ICPC")
    response = client.post(_toggle_url(pset))
    assert response.status_code == 302
    assert "/accounts/login" in response.url
    assert CollapsedNode.objects.count() == 0


@pytest.mark.django_db
def test_toggle_get_method_not_allowed(client) -> None:
    user = UserFactory()
    pset = ProblemSet.add_root(title="ICPC")
    client.force_login(user)
    response = client.get(_toggle_url(pset))
    assert response.status_code == 405


@pytest.mark.django_db
def test_toggle_404_for_missing_set(client) -> None:
    user = UserFactory()
    client.force_login(user)
    response = client.post(reverse("problemsets:toggle_collapse", args=[9999]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_toggle_only_affects_self(client) -> None:
    other = UserFactory()
    pset = ProblemSet.add_root(title="ICPC")
    CollapsedNode.objects.create(user=other, problem_set=pset)

    me = UserFactory()
    client.force_login(me)
    client.post(_toggle_url(pset))

    # Other user's record untouched.
    assert CollapsedNode.objects.filter(user=other, problem_set=pset).exists()
    # Mine is now created.
    assert CollapsedNode.objects.filter(user=me, problem_set=pset).exists()


# ---------- list view filtering ----------


@pytest.mark.django_db
def test_list_default_shows_full_tree_for_authenticated(client) -> None:
    user = UserFactory()
    root = ProblemSet.add_root(title="ICPC")
    child = root.add_child(title="Asia")
    child.add_child(title="Yokohama")

    client.force_login(user)
    body = client.get(reverse("problemsets:list")).content.decode()
    assert "ICPC" in body
    assert "Asia" in body
    assert "Yokohama" in body


@pytest.mark.django_db
def test_list_hides_descendants_of_collapsed_node(client) -> None:
    user = UserFactory()
    root = ProblemSet.add_root(title="ICPC")
    child = root.add_child(title="Asia")
    grandchild = child.add_child(title="Yokohama")
    CollapsedNode.objects.create(user=user, problem_set=child)

    client.force_login(user)
    body = client.get(reverse("problemsets:list")).content.decode()
    assert "ICPC" in body
    assert "Asia" in body  # the collapsed node itself is still visible
    assert "Yokohama" not in body  # but its descendants are hidden
    # Sanity: the underlying nodes still exist.
    assert ProblemSet.objects.filter(pk=grandchild.pk).exists()


@pytest.mark.django_db
def test_list_collapsed_button_indicator_for_non_leaf(client) -> None:
    user = UserFactory()
    root = ProblemSet.add_root(title="ICPC")
    root.add_child(title="Asia")  # makes ICPC non-leaf

    client.force_login(user)

    body = client.get(reverse("problemsets:list")).content.decode()
    # Default (not collapsed) → ▼
    assert "▼" in body
    assert _toggle_url(root) in body

    CollapsedNode.objects.create(user=user, problem_set=root)
    body = client.get(reverse("problemsets:list")).content.decode()
    # Collapsed → ▶
    assert "▶" in body


@pytest.mark.django_db
def test_list_anonymous_renders_client_side_toggle_button(client) -> None:
    """Guests get a client-side (localStorage) toggle on non-leaf rows; the
    server hx-post URL is intentionally absent (auth-only endpoint)."""
    root = ProblemSet.add_root(title="ICPC")
    root.add_child(title="Asia")

    body = client.get(reverse("problemsets:list")).content.decode()
    # No server toggle URL (login_required endpoint).
    assert _toggle_url(root) not in body
    # But the non-leaf row still gets a client-side toggle button.
    assert "data-collapse-btn" in body
    assert "__psTrackerToggleGuestCollapse" in body


@pytest.mark.django_db
def test_list_no_toggle_button_for_leaf_node(client) -> None:
    user = UserFactory()
    leaf = ProblemSet.add_root(title="LeafOnly")
    client.force_login(user)
    body = client.get(reverse("problemsets:list")).content.decode()
    # Leaf rows have no toggle button (no children to collapse).
    assert _toggle_url(leaf) not in body


@pytest.mark.django_db
def test_collapse_state_isolated_between_users(client) -> None:
    """User A's collapse must not affect what User B sees."""
    a = UserFactory()
    b = UserFactory()
    root = ProblemSet.add_root(title="ICPC")
    root.add_child(title="Asia")
    CollapsedNode.objects.create(user=a, problem_set=root)

    client.force_login(b)
    body = client.get(reverse("problemsets:list")).content.decode()
    assert "Asia" in body  # B has no collapse, sees everything
