"""Step 5: me page (edit + stats) + public profile + visibility rules."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import ProfileVisibility
from apps.problemsets.models import Problem, ProblemAppearance
from apps.ratings.models import Rating
from apps.solving.models import SolveRecord

from .factories import (
    CommentFactory,
    ProblemSetRootFactory,
    RatingFactory,
    UserFactory,
)

# ---------- /accounts/me/ — owner page ----------


@pytest.mark.django_db
def test_me_requires_login(client) -> None:
    response = client.get(reverse("accounts:me"))
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_me_renders_form_and_stats(client) -> None:
    user = UserFactory(nickname="alice", boj_handle="alice123")
    client.force_login(user)
    response = client.get(reverse("accounts:me"))
    assert response.status_code == 200
    body = response.content.decode()
    # Form pre-fills.
    assert "alice123" in body
    # Stats panel with zero counts initially.
    assert "푼 문제" in body
    assert "남긴 별점" in body


@pytest.mark.django_db
def test_me_post_updates_profile(client) -> None:
    user = UserFactory(nickname="alice")
    client.force_login(user)
    response = client.post(
        reverse("accounts:me"),
        {
            "nickname": "alice2",
            "profile_visibility": ProfileVisibility.PUBLIC,
            "boj_handle": "alice_boj",
            "codeforces_handle": "",
            "atcoder_handle": "",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.nickname == "alice2"
    assert user.profile_visibility == ProfileVisibility.PUBLIC
    assert user.boj_handle == "alice_boj"


@pytest.mark.django_db
def test_me_rejects_duplicate_nickname(client) -> None:
    UserFactory(nickname="taken")
    me = UserFactory(nickname="alice")
    client.force_login(me)
    response = client.post(
        reverse("accounts:me"),
        {
            "nickname": "taken",
            "profile_visibility": ProfileVisibility.PRIVATE,
            "boj_handle": "",
            "codeforces_handle": "",
            "atcoder_handle": "",
        },
    )
    assert response.status_code == 200  # form re-rendered with error
    me.refresh_from_db()
    assert me.nickname == "alice"


@pytest.mark.django_db
def test_me_stats_count_user_activity(client) -> None:
    user = UserFactory()
    leaf = ProblemSetRootFactory(title="Day 1")
    p = Problem.objects.create(title="P")
    ProblemAppearance.objects.create(problem=p, problem_set=leaf, label="A")
    SolveRecord.objects.create(user=user, problem=p)
    rating = RatingFactory(user=user, problem_set=leaf)
    CommentFactory(rating=rating)

    client.force_login(user)
    body = client.get(reverse("accounts:me")).content.decode()
    # Each stat appears with its monospace count.
    assert ">1<" in body  # one solve, one rating, one comment
    assert "Day 1" in body  # solved_set_titles list


# ---------- /u/<nickname>/ — public profile ----------


@pytest.mark.django_db
def test_profile_404_for_unknown_nickname(client) -> None:
    response = client.get(reverse("accounts:profile", args=["ghost"]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_profile_public_shows_full_info_to_anonymous(client) -> None:
    UserFactory(
        nickname="alice",
        profile_visibility=ProfileVisibility.PUBLIC,
        boj_handle="alice_boj",
    )
    response = client.get(reverse("accounts:profile", args=["alice"]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "alice" in body
    assert "alice_boj" in body
    assert "푼 문제" in body  # stats visible
    assert "비공개입니다" not in body


@pytest.mark.django_db
def test_profile_private_hides_details_from_others(client) -> None:
    UserFactory(
        nickname="bob",
        profile_visibility=ProfileVisibility.PRIVATE,
        boj_handle="bob_boj",
    )
    me = UserFactory()
    client.force_login(me)
    response = client.get(reverse("accounts:profile", args=["bob"]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "bob" in body  # nickname always visible
    assert "bob_boj" not in body  # external handles hidden
    assert "비공개입니다" in body
    assert "푼 문제" not in body


@pytest.mark.django_db
def test_profile_private_owner_sees_full_info(client) -> None:
    me = UserFactory(
        nickname="me",
        profile_visibility=ProfileVisibility.PRIVATE,
        boj_handle="me_boj",
    )
    client.force_login(me)
    response = client.get(reverse("accounts:profile", args=["me"]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "me_boj" in body  # owner sees own private info
    assert "비공개입니다" not in body
    # Owner sees an "edit" link back to /accounts/me/.
    assert reverse("accounts:me") in body


# ---------- nickname → profile linking integration ----------


@pytest.mark.django_db
def test_comment_author_links_to_profile(client) -> None:
    user = UserFactory(nickname="commenter")
    rating = RatingFactory(user=user)
    CommentFactory(rating=rating, body="hello")

    response = client.get(reverse("problemsets:detail", args=[rating.problem_set.pk]))
    body = response.content.decode()
    assert reverse("accounts:profile", args=["commenter"]) in body


@pytest.mark.django_db
def test_raters_modal_nicknames_link_to_profile(client) -> None:
    pset = ProblemSetRootFactory()
    rater = UserFactory(nickname="rater_x")
    Rating.objects.create(user=rater, problem_set=pset, stars=4)

    me = UserFactory()
    client.force_login(me)
    body = client.get(reverse("ratings:raters", args=[pset.pk])).content.decode()
    assert reverse("accounts:profile", args=["rater_x"]) in body


@pytest.mark.django_db
def test_nav_nickname_links_to_own_profile(client) -> None:
    user = UserFactory(nickname="alice")
    client.force_login(user)
    body = client.get(reverse("home")).content.decode()
    assert reverse("accounts:profile", args=["alice"]) in body
