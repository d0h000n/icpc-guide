"""Dump ProblemSet trees + Problems back to YAML.

Round-trips with `import_problemsets` so you can edit existing data in YAML:

    uv run python manage.py export_problemsets > all.yml          # everything
    uv run python manage.py export_problemsets ICPC > icpc.yml    # one root by title
    uv run python manage.py export_problemsets --to data/icpc.yml ICPC

Output shape mirrors the importer's input (top-level dict with `categories:`
and `problem_sets:`). Re-importing the same file is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from django.core.management.base import BaseCommand, CommandError

from apps.categories.models import Category
from apps.problemsets.models import ProblemAppearance, ProblemSet


class Command(BaseCommand):
    help = "Export ProblemSet trees to YAML."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "roots",
            nargs="*",
            help="Root ProblemSet titles to export. If omitted, exports everything.",
        )
        parser.add_argument(
            "--to",
            type=Path,
            help="Write to file instead of stdout.",
        )

    def handle(self, *args, **options) -> None:
        root_titles: list[str] = options["roots"]
        out_path: Path | None = options["to"]

        if root_titles:
            roots = list(ProblemSet.objects.filter(depth=1, title__in=root_titles))
            missing = set(root_titles) - {r.title for r in roots}
            if missing:
                raise CommandError(f"No such root ProblemSet(s): {sorted(missing)}")
        else:
            roots = list(ProblemSet.objects.filter(depth=1).order_by("title"))

        # Limit categories to those actually used somewhere in the exported subtree.
        used_category_ids: set[int] = set()
        for root in roots:
            descendant_paths = ProblemSet.objects.filter(path__startswith=root.path).values_list(
                "id", flat=True
            )
            used_category_ids.update(
                Category.objects.filter(problem_sets__id__in=descendant_paths)
                .values_list("id", flat=True)
                .distinct()
            )

        payload: dict[str, Any] = {
            "categories": [
                {
                    "short_name": c.short_name,
                    "name": c.name,
                    **({"description": c.description} if c.description else {}),
                    **({"url": c.url} if c.url else {}),
                }
                for c in Category.objects.filter(id__in=used_category_ids).order_by("short_name")
            ],
            "problem_sets": [self._serialize_node(r) for r in roots],
        }
        if not payload["categories"]:
            payload.pop("categories")

        text = yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            indent=2,
        )

        if out_path:
            out_path.write_text(text, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {out_path}"))
        else:
            sys.stdout.write(text)

    def _serialize_node(self, node: ProblemSet) -> dict[str, Any]:
        out: dict[str, Any] = {"title": node.title}
        if node.year is not None:
            out["year"] = node.year
        if node.description:
            out["description"] = node.description
        if node.external_url:
            out["external_url"] = node.external_url

        cats = list(node.categories.values_list("short_name", flat=True).order_by("short_name"))
        if cats:
            out["categories"] = cats

        children = list(node.get_children().order_by("path"))
        if children:
            out["children"] = [self._serialize_node(c) for c in children]

        appearances = list(
            ProblemAppearance.objects.filter(problem_set=node)
            .select_related("problem")
            .order_by("order_index")
        )
        if appearances:
            out["problems"] = [self._serialize_appearance(a) for a in appearances]

        return out

    def _serialize_appearance(self, app: ProblemAppearance) -> dict[str, Any]:
        out: dict[str, Any] = {
            "label": app.label,
            "title": app.problem.title,
        }
        if app.problem.external_url:
            out["external_url"] = app.problem.external_url
        if app.problem.solved_ac_tier_manual is not None:
            out["tier"] = app.problem.solved_ac_tier_manual
        return out
