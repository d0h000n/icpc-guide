"""Move existing ProblemSet.source FK values into CategoryMembership rows.

Per spec v0.4: a Category should not contain both an ancestor and a descendant
ProblemSet (the ancestor implicitly covers the subtree). Existing data has the
same source FK on every node in a tree, so we attach the membership only to
the **root** node of each tree (depth=1 in treebeard MP). Descendants inherit
membership transitively via the tree.
"""

from __future__ import annotations

from django.db import migrations


def populate_memberships(apps, schema_editor):
    ProblemSet = apps.get_model("problemsets", "ProblemSet")
    CategoryMembership = apps.get_model("problemsets", "CategoryMembership")

    to_create = []
    for ps in ProblemSet.objects.filter(depth=1, source__isnull=False):
        to_create.append(
            CategoryMembership(problem_set_id=ps.id, category_id=ps.source_id)
        )
    CategoryMembership.objects.bulk_create(to_create, ignore_conflicts=True)


def restore_source_fk(apps, schema_editor):
    """Reverse: copy each root's first membership back into source FK,
    propagate down the tree (best-effort recovery)."""
    ProblemSet = apps.get_model("problemsets", "ProblemSet")
    CategoryMembership = apps.get_model("problemsets", "CategoryMembership")

    for root in ProblemSet.objects.filter(depth=1):
        membership = CategoryMembership.objects.filter(problem_set=root).first()
        if membership is None:
            continue
        # Apply to root + all descendants (path-prefix).
        ProblemSet.objects.filter(path__startswith=root.path).update(
            source_id=membership.category_id
        )


class Migration(migrations.Migration):
    dependencies = [
        ("problemsets", "0006_add_category_m2m"),
    ]

    operations = [
        migrations.RunPython(populate_memberships, reverse_code=restore_source_fk),
    ]
