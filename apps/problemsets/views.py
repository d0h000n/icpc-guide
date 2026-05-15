"""problemsets views — public browsing (Guest OK)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.categories.models import Category
from apps.ratings.models import Comment, Rating
from apps.ratings.services import aggregate_for as rating_aggregate_for
from apps.ratings.services import my_rating as my_rating_for
from apps.solving.models import SolveRecord
from apps.solving.services import completion_for, subtree_problem_count
from apps.teams.models import Team, TeamMember

from .models import CollapsedNode, ProblemSet


@never_cache
@require_safe
def problem_set_list(request: HttpRequest) -> HttpResponse:
    """Browse-all view: tree of every ProblemSet with category / year filters.

    Category filter semantics: pick all ProblemSets whose any ancestor (or self)
    is a direct member of the chosen category. Descendants inherit membership
    transitively per spec v0.4 §3.3 (Category constraint).
    """
    qs = ProblemSet.objects.prefetch_related("categories").order_by("path")

    selected_category = (request.GET.get("category") or request.GET.get("source") or "").strip()
    year_from = request.GET.get("year_from", "").strip()
    year_to = request.GET.get("year_to", "").strip()

    if selected_category:
        # Members directly tagged with this category.
        members = ProblemSet.objects.filter(categories__short_name=selected_category)
        path_q = Q()
        any_member = False
        for path in members.values_list("path", flat=True):
            path_q |= Q(path__startswith=path)
            any_member = True
        qs = qs.filter(path_q) if any_member else qs.none()
    if year_from.isdigit():
        qs = qs.filter(year__gte=int(year_from))
    if year_to.isdigit():
        qs = qs.filter(year__lte=int(year_to))

    categories = Category.objects.order_by("short_name")
    years = list(
        ProblemSet.objects.exclude(year__isnull=True)
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )

    problem_sets = list(qs)

    # Per-user tree collapse: hide a node if any of its ancestors is collapsed.
    collapsed_pks: set[int] = set()
    collapsed_paths: list[str] = []
    if request.user.is_authenticated:
        collapsed_qs = CollapsedNode.objects.filter(user=request.user).select_related("problem_set")
        collapsed_paths = [c.problem_set.path for c in collapsed_qs]
        collapsed_pks = {c.problem_set_id for c in collapsed_qs}

    def _is_hidden(ps: ProblemSet) -> bool:
        for cpath in collapsed_paths:
            # ps is hidden iff one of its ancestors (strict prefix) is collapsed.
            if ps.path != cpath and ps.path.startswith(cpath):
                return True
        return False

    rows = []
    for ps in problem_sets:
        if _is_hidden(ps):
            continue
        s, t = completion_for(ps, request.user)
        rows.append(
            {
                "node": ps,
                "solved": s,
                "total": t,
                "is_collapsed": ps.pk in collapsed_pks,
            }
        )

    return render(
        request,
        "problemsets/list.html",
        {
            "rows": rows,
            "categories": categories,
            "years": years,
            "selected_category": selected_category,
            "year_from": year_from,
            "year_to": year_to,
            "is_filtered": bool(selected_category or year_from or year_to),
        },
    )


@never_cache
@login_required
@require_POST
def toggle_collapse(request: HttpRequest, pk: int) -> HttpResponse:
    """Flip the current user's "this node is collapsed in tree view" state."""
    pset = get_object_or_404(ProblemSet, pk=pk)
    obj, created = CollapsedNode.objects.get_or_create(user=request.user, problem_set=pset)
    if not created:
        obj.delete()
    # Empty body + HX-Trigger so the tree wrapper refreshes itself with the
    # current GET filters preserved (see #set-tree's hx-get / hx-trigger).
    response = HttpResponse(status=204)
    response["HX-Trigger"] = "tree-changed"
    return response


@never_cache
@require_safe
def problem_set_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Detail page for a ProblemSet. Guest accessible.

    Leaf nodes show the Problem list; internal nodes show child sets.
    Rating and completion-rate sections are placeholders until steps 3–4.
    """
    pset = get_object_or_404(
        ProblemSet.objects.select_related("created_by").prefetch_related("categories"),
        pk=pk,
    )

    is_leaf = pset.is_leaf()
    children = (
        list(pset.get_children().prefetch_related("categories").order_by("path"))
        if not is_leaf
        else []
    )

    solved_count, total_count = completion_for(pset, request.user)

    children_with_completion = []
    for child in children:
        c_solved, c_total = completion_for(child, request.user)
        children_with_completion.append({"node": child, "solved": c_solved, "total": c_total})

    appearances: list = []
    if is_leaf:
        appearances_qs = pset.appearances.select_related("problem").order_by("order_index")
        if request.user.is_authenticated:
            appearances_qs = appearances_qs.annotate(
                is_solved_by_me=Exists(
                    SolveRecord.objects.filter(
                        user=request.user,
                        problem=OuterRef("problem_id"),
                    )
                )
            )
        appearances = list(appearances_qs)
        if not request.user.is_authenticated:
            for a in appearances:
                a.is_solved_by_me = False

    ancestors = list(pset.get_ancestors())

    # Inherited categories: this set's own categories + every ancestor's.
    inherited_category_ids = set(pset.categories.values_list("id", flat=True))
    for anc in ancestors:
        inherited_category_ids.update(anc.categories.values_list("id", flat=True))
    inherited_categories = Category.objects.filter(id__in=inherited_category_ids).order_by(
        "short_name"
    )

    avg_stars, rating_count = rating_aggregate_for(pset)
    my_r = my_rating_for(pset, request.user)

    # --- Team context (spec §4.4.3) -----------------------------------
    my_teams: list[Team] = []
    selected_team: Team | None = None
    team_members: list[TeamMember] = []
    # {problem_id: set of user_ids that solved it} — used in leaf table
    team_member_solves_by_problem: dict[int, set[int]] = {}
    # {user_id: solved_count} for the current set's subtree
    per_member_subtree_solved: dict[int, int] = {}
    team_subtree_solved = 0  # union: any-member-solved distinct count

    if request.user.is_authenticated:
        my_teams = list(
            Team.objects.filter(memberships__user=request.user).order_by("name").distinct()
        )

    team_slug = (request.GET.get("team") or "").strip()
    if team_slug and request.user.is_authenticated:
        # Only honor if the requester is a member — spec §4.4.3.
        selected_team = (
            Team.objects.filter(slug=team_slug, memberships__user=request.user).distinct().first()
        )

    if selected_team is not None:
        team_members = list(
            selected_team.memberships.select_related("user").order_by("-role", "joined_at")
        )
        user_ids = [m.user_id for m in team_members]

        if is_leaf and appearances:
            problem_ids = [a.problem_id for a in appearances]
            solve_rows = SolveRecord.objects.filter(
                user_id__in=user_ids,
                problem_id__in=problem_ids,
            ).values_list("problem_id", "user_id")
            from collections import defaultdict

            mapping: defaultdict[int, set[int]] = defaultdict(set)
            for pid, uid in solve_rows:
                mapping[pid].add(uid)
            team_member_solves_by_problem = dict(mapping)

        # Subtree-wide stats: per-member counts + union count.
        subtree_solves = SolveRecord.objects.filter(
            user_id__in=user_ids,
            problem__appearances__problem_set__path__startswith=pset.path,
        ).values_list("problem_id", "user_id")
        per_member_problem_ids: dict[int, set[int]] = {uid: set() for uid in user_ids}
        all_problem_ids: set[int] = set()
        for pid, uid in subtree_solves:
            per_member_problem_ids[uid].add(pid)
            all_problem_ids.add(pid)
        per_member_subtree_solved = {uid: len(pids) for uid, pids in per_member_problem_ids.items()}
        team_subtree_solved = len(all_problem_ids)
        # Attach per-member counts to the TeamMember rows so the template can
        # render them without a dict-lookup template tag.
        for m in team_members:
            m.solved_in_subtree = per_member_subtree_solved.get(m.user_id, 0)

    team_subtree_total = subtree_problem_count(pset) if selected_team else 0

    comments = (
        Comment.objects.filter(rating__problem_set=pset)
        .select_related("rating__user")
        .order_by("-updated_at")
    )
    my_comment = None
    has_rating = False
    if request.user.is_authenticated:
        my_comment = comments.filter(rating__user=request.user).first()
        has_rating = Rating.objects.filter(user=request.user, problem_set=pset).exists()

    # Per-appearance: list of (member, solved) tuples for the team-context row.
    if selected_team is not None and is_leaf:
        for app in appearances:
            app.team_solvers = [
                m
                for m in team_members
                if m.user_id in team_member_solves_by_problem.get(app.problem_id, set())
            ]

    return render(
        request,
        "problemsets/detail.html",
        {
            "problem_set": pset,
            "ancestors": ancestors,
            "is_leaf": is_leaf,
            "children": children_with_completion,
            "appearances": appearances,
            "solved_count": solved_count,
            "total_count": total_count,
            "inherited_categories": inherited_categories,
            "my_rating": my_r,
            "avg_stars": avg_stars,
            "rating_count": rating_count,
            "stars_range": range(1, 6),
            "comments": comments,
            "my_comment": my_comment,
            "has_rating": has_rating,
            # Team context
            "my_teams": my_teams,
            "selected_team": selected_team,
            "team_members": team_members,
            "per_member_subtree_solved": per_member_subtree_solved,
            "team_subtree_solved": team_subtree_solved,
            "team_subtree_total": team_subtree_total,
        },
    )
