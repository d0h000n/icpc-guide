"""S3 — user-facing proposal submission. Spec §4.1.6, §4.2."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from .forms import CategoryProposalForm, ProblemSetProposalCreateForm
from .models import CategoryProposal, ProblemSetProposal


@never_cache
@login_required
def propose_index(request: HttpRequest) -> HttpResponse:
    """Landing page — pick what to propose + show this user's prior submissions."""
    my_cat = CategoryProposal.objects.filter(user=request.user).order_by("-created_at")
    my_ps = ProblemSetProposal.objects.filter(user=request.user).order_by("-created_at")
    return render(
        request,
        "proposals/index.html",
        {"my_category_proposals": my_cat, "my_problemset_proposals": my_ps},
    )


@never_cache
@login_required
def propose_category(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = CategoryProposalForm(request.POST)
        if form.is_valid():
            proposal: CategoryProposal = form.save(commit=False)
            proposal.user = request.user
            proposal.save()
            messages.success(request, "카테고리 제안이 접수되었습니다. 검토 후 알려드릴게요.")
            return redirect(reverse("proposals:index"))
    else:
        form = CategoryProposalForm()
    return render(request, "proposals/category_form.html", {"form": form})


@never_cache
@login_required
def propose_problem_set(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProblemSetProposalCreateForm(request.POST)
        if form.is_valid():
            form.save(user=request.user)
            messages.success(request, "Problem Set 제안이 접수되었습니다. 검토 후 알려드릴게요.")
            return redirect(reverse("proposals:index"))
    else:
        form = ProblemSetProposalCreateForm()
    return render(request, "proposals/problem_set_form.html", {"form": form})
