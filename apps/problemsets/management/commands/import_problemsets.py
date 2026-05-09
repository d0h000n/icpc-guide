"""Bulk-import ProblemSet trees + Problems from YAML.

YAML shape (top-level either a list of root nodes, or a dict with optional
`categories` declaration plus `problem_sets`):

    categories:
      - { short_name: icpc, name: "ICPC" }
      - { short_name: japan, name: "Japan" }

    problem_sets:
      - title: ICPC
        categories: [icpc]
        children:
          - title: Asia-Pacific Regionals
            children:
              - title: Yokohama Regional 2023
                year: 2023
                external_url: https://...
                problems:
                  - { label: A, title: "Hasty Santa Claus", external_url: "https://qoj.ac/problem/8439", tier: 17 }
                  - { label: B, title: "Interactive Number Guessing", tier: 14 }

Idempotency:
- ProblemSet matched by (parent, title). Found → field update; not found → create.
- Problem matched by canonical `title` — same title across files = same Problem
  (intentional — solving once counts everywhere; spec v0.3 N—M).
- ProblemAppearance: the per-set `problems:` list is treated as authoritative
  for that set; appearances of Problems not in the YAML for this set are dropped.
- Categories: if `categories:` is provided on a node, the M2M is set to
  exactly that list (not additive). Omit the key to leave existing alone.

Run:
    uv run python manage.py import_problemsets path/to/file.yml [more.yml ...]
    uv run python manage.py import_problemsets path/to/dir/
    uv run python manage.py import_problemsets --dry-run path/to/file.yml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.categories.models import Category
from apps.problemsets.models import (
    Problem,
    ProblemAppearance,
    ProblemSet,
    SolvedAcTier,
)


class Command(BaseCommand):
    help = "Import ProblemSet trees + Problems from YAML files."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "paths",
            nargs="+",
            type=Path,
            help="YAML file(s) or directory(ies) to import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run inside a rolled-back transaction; print what would change.",
        )

    def handle(self, *args, **options) -> None:
        files = self._collect_files(options["paths"])
        dry_run = options["dry_run"]

        # Reset counters at the start so they're consistent across the run.
        self._counts = {
            "categories_created": 0,
            "sets_created": 0,
            "sets_updated": 0,
            "problems_created": 0,
            "problems_updated": 0,
            "appearances_created": 0,
            "appearances_updated": 0,
            "appearances_deleted": 0,
        }

        try:
            with transaction.atomic():
                for f in files:
                    self.stdout.write(self.style.NOTICE(f"→ {f}"))
                    self._import_file(f)

                if dry_run:
                    transaction.set_rollback(True)
        except Exception as exc:  # noqa: BLE001 — re-raise as CommandError below
            raise CommandError(str(exc)) from exc

        verb = "Would change" if dry_run else "Changed"
        for k, v in self._counts.items():
            if v:
                self.stdout.write(f"  {verb} — {k}: {v}")
        if dry_run:
            self.stdout.write(self.style.WARNING("(dry-run) all changes rolled back."))
        else:
            self.stdout.write(self.style.SUCCESS("Import complete."))

    # ------------------------------------------------------------------ helpers

    def _collect_files(self, paths: list[Path]) -> list[Path]:
        out: list[Path] = []
        for p in paths:
            if not p.exists():
                raise CommandError(f"Path not found: {p}")
            if p.is_dir():
                out.extend(sorted(p.rglob("*.yml")) + sorted(p.rglob("*.yaml")))
            else:
                out.append(p)
        if not out:
            raise CommandError("No YAML files found.")
        return out

    def _import_file(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data is None:
            return

        if isinstance(data, dict):
            for cat_data in data.get("categories", []) or []:
                self._upsert_category(cat_data)
            roots = data.get("problem_sets", []) or []
        else:
            roots = data

        if not isinstance(roots, list):
            raise CommandError(
                f"{path}: top-level must be a list of root nodes, or a dict with 'problem_sets:'"
            )

        for entry in roots:
            self._upsert_node(entry, parent=None)

    def _upsert_category(self, data: dict[str, Any]) -> Category:
        short_name = data["short_name"]
        defaults = {
            "name": data.get("name") or short_name,
            "description": data.get("description", ""),
            "url": data.get("url", ""),
        }
        cat, created = Category.objects.update_or_create(
            short_name=short_name,
            defaults=defaults,
        )
        if created:
            self._counts["categories_created"] += 1
        return cat

    def _upsert_node(self, data: dict[str, Any], parent: ProblemSet | None) -> ProblemSet:
        title = data["title"]
        year = data.get("year")
        description = data.get("description", "")
        external_url = data.get("external_url", "")

        if parent is None:
            ps = ProblemSet.objects.filter(depth=1, title=title).first()
        else:
            ps = parent.get_children().filter(title=title).first()

        if ps is None:
            if parent is None:
                ps = ProblemSet.add_root(
                    title=title,
                    year=year,
                    description=description,
                    external_url=external_url,
                )
            else:
                ps = parent.add_child(
                    title=title,
                    year=year,
                    description=description,
                    external_url=external_url,
                )
            self._counts["sets_created"] += 1
        else:
            if ps.year != year or ps.description != description or ps.external_url != external_url:
                ps.year = year
                ps.description = description
                ps.external_url = external_url
                ps.save(update_fields=["year", "description", "external_url"])
                self._counts["sets_updated"] += 1

        # Categories M2M — replace if `categories:` key is provided
        if "categories" in data:
            self._sync_categories(ps, data["categories"] or [])

        # Children recursion
        for child_data in data.get("children", []) or []:
            self._upsert_node(child_data, parent=ps)

        # Problems on this leaf — replace if key provided
        if "problems" in data:
            self._sync_appearances(ps, data["problems"] or [])

        return ps

    def _sync_categories(self, ps: ProblemSet, short_names: list[str]) -> None:
        if not short_names:
            ps.categories.clear()
            return
        cats = list(Category.objects.filter(short_name__in=short_names))
        missing = set(short_names) - {c.short_name for c in cats}
        if missing:
            raise CommandError(
                f"Unknown categories on '{ps.title}': {sorted(missing)}. "
                f"Declare them in a top-level `categories:` block first."
            )
        # Idempotent set: clear what's not listed, then add (validators on M2M
        # signal still fire to enforce ancestor-descendant rule).
        current = set(ps.categories.values_list("id", flat=True))
        target = {c.id for c in cats}
        for cat_id in current - target:
            ps.categories.remove(cat_id)
        for cat in cats:
            if cat.id not in current:
                ps.categories.add(cat)

    def _sync_appearances(self, ps: ProblemSet, items: list[dict[str, Any]]) -> None:
        if not items:
            deleted, _ = ProblemAppearance.objects.filter(problem_set=ps).delete()
            self._counts["appearances_deleted"] += deleted
            return

        seen_problem_ids: list[int] = []
        for i, p_data in enumerate(items, start=1):
            label = p_data["label"]
            order_index = p_data.get("order_index", i)
            problem = self._upsert_problem(p_data)
            seen_problem_ids.append(problem.pk)

            # Delete any colliding appearance on this set with same order/label
            # but different Problem (so the unique constraints don't fire).
            ProblemAppearance.objects.filter(problem_set=ps).filter(
                models_q_or(order_index=order_index, label=label)
            ).exclude(problem=problem).delete()

            _, created = ProblemAppearance.objects.update_or_create(
                problem=problem,
                problem_set=ps,
                defaults={"label": label, "order_index": order_index},
            )
            if created:
                self._counts["appearances_created"] += 1
            else:
                self._counts["appearances_updated"] += 1

        deleted, _ = (
            ProblemAppearance.objects.filter(problem_set=ps)
            .exclude(problem_id__in=seen_problem_ids)
            .delete()
        )
        self._counts["appearances_deleted"] += deleted

    def _upsert_problem(self, data: dict[str, Any]) -> Problem:
        title = data["title"]
        external_url = data.get("external_url", "")
        tier = data.get("tier")
        if tier is not None:
            valid_tiers = {choice for choice, _ in SolvedAcTier.choices}
            if tier not in valid_tiers:
                raise CommandError(
                    f"Invalid solved.ac tier {tier} for problem '{title}' (must be 1–30)."
                )

        problem, created = Problem.objects.get_or_create(
            title=title,
            defaults={
                "external_url": external_url,
                "solved_ac_tier_manual": tier,
            },
        )
        if created:
            self._counts["problems_created"] += 1
            return problem

        # Update fields where the YAML provides a value and it differs.
        changed: list[str] = []
        if external_url and problem.external_url != external_url:
            problem.external_url = external_url
            changed.append("external_url")
        if tier is not None and problem.solved_ac_tier_manual != tier:
            problem.solved_ac_tier_manual = tier
            changed.append("solved_ac_tier_manual")
        if changed:
            problem.save(update_fields=changed)
            self._counts["problems_updated"] += 1
        return problem


def models_q_or(**filters):
    """Tiny helper so the call site reads naturally — Q(a=1) | Q(b=2)."""
    from django.db.models import Q

    q = Q()
    for k, v in filters.items():
        q |= Q(**{k: v})
    return q
