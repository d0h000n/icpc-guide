"""Team-related forms."""

from __future__ import annotations

from django import forms

from .models import Team


class TeamCreateForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ("name", "slug", "description", "visibility")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "slug": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
            "visibility": forms.Select(attrs={"class": "select select-bordered w-full"}),
        }


class TeamEditForm(TeamCreateForm):
    """Edit form — same fields. Slug uniqueness is enforced by the DB."""

    class Meta(TeamCreateForm.Meta):
        pass
