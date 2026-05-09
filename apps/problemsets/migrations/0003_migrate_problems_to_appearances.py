"""Copy each existing Problem's (problem_set, order_index, label) into a new
ProblemAppearance row. After this runs, every Problem has exactly one
Appearance — equivalent to the old 1:N model. Future Problems can grow
additional Appearances freely.
"""

from __future__ import annotations

from django.db import migrations


def copy_problem_to_appearance(apps, schema_editor):
    Problem = apps.get_model("problemsets", "Problem")
    ProblemAppearance = apps.get_model("problemsets", "ProblemAppearance")

    to_create = []
    for problem in Problem.objects.all():
        if problem.problem_set_id is None:
            # Defensive — the schema-migration step made the FK nullable, but
            # any pre-existing row has it set.
            continue
        to_create.append(
            ProblemAppearance(
                problem_id=problem.id,
                problem_set_id=problem.problem_set_id,
                order_index=problem.order_index or 0,
                label=problem.label or "",
            )
        )
    ProblemAppearance.objects.bulk_create(to_create)


def restore_problem_from_appearance(apps, schema_editor):
    """Reverse: copy first appearance back onto Problem.

    Lossy if a Problem has more than one appearance (the M2M case). The
    reverse path is intended only for rolling back a clean upgrade where each
    Problem still has exactly one appearance.
    """
    Problem = apps.get_model("problemsets", "Problem")
    ProblemAppearance = apps.get_model("problemsets", "ProblemAppearance")

    for problem in Problem.objects.all():
        appearance = (
            ProblemAppearance.objects.filter(problem=problem)
            .order_by("problem_set_id", "order_index")
            .first()
        )
        if appearance is None:
            continue
        problem.problem_set_id = appearance.problem_set_id
        problem.order_index = appearance.order_index
        problem.label = appearance.label
        problem.save(update_fields=["problem_set", "order_index", "label"])


class Migration(migrations.Migration):
    dependencies = [
        ("problemsets", "0002_add_problem_appearance"),
    ]

    operations = [
        migrations.RunPython(
            copy_problem_to_appearance,
            reverse_code=restore_problem_from_appearance,
        ),
    ]
