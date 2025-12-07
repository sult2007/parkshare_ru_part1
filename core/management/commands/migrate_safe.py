from __future__ import annotations

import contextlib

from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


class Command(BaseCommand):
    help = (
        "Runs migrations with a two-phase, production-safe workflow. "
        "Phase 1 prints a plan; Phase 2 applies migrations with --noinput."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to migrate (default: default).",
        )
        parser.add_argument(
            "--plan-only",
            action="store_true",
            help="Only show the migration plan without applying changes.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply migrations after showing the plan (non-interactive).",
        )

    def handle(self, *args, **options):
        database = options["database"]
        plan_only = options["plan_only"]
        apply = options["apply"]

        self.stdout.write(self.style.NOTICE(f"Checking database connection [{database}]..."))
        with contextlib.suppress(Exception):
            connections[database].ensure_connection()

        try:
            self.stdout.write(self.style.NOTICE("Phase 1: migration plan"))
            call_command("migrate", database=database, plan=True)
        except Exception as exc:
            raise CommandError(f"Failed to build migration plan: {exc}") from exc

        if plan_only and not apply:
            self.stdout.write(self.style.SUCCESS("Plan generated. Skipping apply (--plan-only)."))
            return

        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    "No --apply flag provided. Review plan above and rerun with --apply to execute."
                )
            )
            return

        self.stdout.write(self.style.NOTICE("Phase 2: applying migrations (non-interactive)..."))
        try:
            call_command("migrate", database=database, interactive=False)
        except Exception as exc:
            raise CommandError(f"Migration apply failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Migrations applied successfully."))
