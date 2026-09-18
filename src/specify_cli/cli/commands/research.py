"""Research command implementation for Spec Kitty CLI."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

from specify_cli.cli import StepTracker
from specify_cli.cli.console import console
from specify_cli.cli.helpers import get_project_root_or_exit, show_banner
from specify_cli.context.mission_resolver import mission_not_found_message
from specify_cli.core import MISSION_CHOICES
from specify_cli.core.paths import UnsafePathSegmentError
from specify_cli.core.project_resolver import resolve_template_path
from specify_cli.mission import get_mission_type
from specify_cli.plan_validation import PlanValidationError, validate_plan_filled
from specify_cli.task_utils import TaskCliError, find_repo_root
from mission_runtime import MissionArtifactKind, placement_seam


def _read_mission_dir_or_exit(repo_root: Path, mission_slug: str, kind: MissionArtifactKind) -> Path:
    """Resolve a mission artifact read dir, exiting cleanly on an unsafe slug.

    #2878: a traversal-shaped ``--mission`` value trips the safe-path-segment
    guard (``assert_safe_path_segment``) inside the placement seam and raises
    ``UnsafePathSegmentError`` that no caller in this command catches — the raw
    traceback the issue reports. Mirrors merge's ``_resolve_slug_or_exit``
    exemplar (cli/commands/merge.py): canonical diagnostic + ``exit 2``, never
    a traceback. The ``merge._constants`` import stays function-local so the
    happy path never pays the merge package's import graph.
    """
    try:
        return placement_seam(repo_root, mission_slug).read_dir(kind)
    except UnsafePathSegmentError as exc:
        from specify_cli.merge._constants import _SAFE_PATH_SEGMENT_DIAGNOSTIC

        console.print(f"[red]Error:[/red] {_SAFE_PATH_SEGMENT_DIAGNOSTIC}: {exc}")
        raise typer.Exit(2) from exc


def research(
    mission: str | None = typer.Option(
        None,
        "--mission",
        help="Mission slug to target",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing research artifacts"),
) -> None:
    """Execute Phase 0 research workflow to scaffold artifacts."""

    show_banner()

    try:
        repo_root = find_repo_root()
    except TaskCliError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    project_root = get_project_root_or_exit(repo_root)

    tracker = StepTracker("Research Phase Setup")
    tracker.add("project", "Locate project root")
    tracker.add("feature", "Resolve mission directory")
    tracker.add("research-md", "Ensure research.md")
    tracker.add("data-model", "Ensure data-model.md")
    tracker.add("research-csv", "Ensure research CSV stubs")
    tracker.add("summary", "Summarize outputs")
    console.print()

    tracker.start("project")
    tracker.complete("project", str(project_root))

    tracker.start("feature")
    mission_norm = mission.strip() if isinstance(mission, str) else None
    if not mission_norm:
        raise typer.BadParameter("--mission <slug> is required")
    mission_slug = mission_norm

    # WP09/FR-001 (kind-correct): route the kind-blind slug resolver onto the
    # seam. The comment below already documents ``feature_dir`` as "its
    # current STATUS-namespace surface" — the dossier sync consumer needs the
    # coord-aware STATUS home, which ``STATUS_STATE`` preserves (NFR-001).
    feature_dir = _read_mission_dir_or_exit(repo_root, mission_slug, MissionArtifactKind.STATUS_STATE)
    # FR-001: refuse a nonexistent mission BEFORE any mkdir/scaffold. The
    # resolver above is path-safety-only (it composes ``kitty-specs/<raw>`` for
    # an unresolvable handle), so without this gate ``planning_dir.mkdir`` below
    # scaffolded a phantom ``kitty-specs/<handle>/`` and exited 0 (contract C1).
    # Mirrors the ``materialize.py`` exemplar: existence check, canonical
    # ``Mission not found: <handle>`` (WP01 constant), non-zero exit — with the
    # filesystem left byte-for-byte unchanged (NFR-001). The path-safety refusal
    # for ``../x`` stays a distinct error (raised inside the resolver, C2).
    if not feature_dir.exists():
        console.print(f"[red]Error:[/red] {mission_not_found_message(mission_slug)}")
        raise typer.Exit(1)
    # F-001: re-key to the canonical directory name. `--mission` accepts
    # handles (bare mid8, numeric prefix); the resolver canonicalizes the
    # DIRECTORY only, while `trigger_feature_dossier_sync_if_enabled` keys the
    # SaaS namespace (NamespaceRef.from_context + OfflineBodyUploadQueue) by
    # this slug — a raw handle splits the namespace vs the full-slug
    # invocation. Unresolvable slugs compose `kitty-specs/<raw>` so the
    # re-key is an identity re-read for the scaffold-new-mission path.
    mission_slug = feature_dir.name

    # gate-read-surface-completion closeout (#2107 residual / FR-004 / FR-009):
    # `resolve_feature_dir_for_slug` is the COORD-aware resolver — under
    # coordination topology it returns the materialized `-coord` husk. The
    # planning artifacts this command READS (plan.md) and WRITES (research.md,
    # data-model.md, the research CSV stubs) are all PRIMARY-partition kinds
    # (`MissionArtifactKind.{FINALIZED_EXECUTION_PLAN,RESEARCH,DATA_MODEL}`) that
    # live with their mission on the primary `target_branch` for EVERY topology
    # since #2106. Resolving them off the coord husk made `research` validate the
    # ABSENT `coord/plan.md` and block (the #2107 driver shape), and scaffold the
    # research artifacts onto coord (re-introducing the split #2106 eliminated).
    # Route both the read and the scaffold WRITE through the kind-aware seam so
    # they converge on the primary surface. For a flattened/single-branch mission
    # the seam returns the same `target_branch` dir (NFR-001 — behavior-neutral).
    # The dossier sync below keeps `feature_dir` (its current STATUS-namespace
    # surface) untouched.
    planning_dir = _read_mission_dir_or_exit(repo_root, mission_slug, MissionArtifactKind.RESEARCH)
    planning_dir.mkdir(parents=True, exist_ok=True)

    # Get mission from feature's meta.json (not project-level default).
    # meta.json is a PRIMARY-partition kind, so it co-locates on `planning_dir`.
    mission_type = get_mission_type(planning_dir)
    mission_display = MISSION_CHOICES.get(mission_type, mission_type)
    tracker.complete("feature", f"{planning_dir} ({mission_display})")

    # Validate that plan.md has been filled out before proceeding. plan.md is a
    # PRIMARY-partition kind (FINALIZED_EXECUTION_PLAN) — read it via the seam so
    # a coord-topology mission validates the authored primary plan, not an absent
    # `coord/plan.md`.
    plan_read_dir = _read_mission_dir_or_exit(repo_root, mission_slug, MissionArtifactKind.FINALIZED_EXECUTION_PLAN)
    plan_path = plan_read_dir / "plan.md"
    try:
        validate_plan_filled(plan_path, mission_slug=mission_slug, strict=True)
    except PlanValidationError as exc:
        console.print(tracker.render())
        console.print()
        console.print(f"[red]Error:[/red] {exc}")
        console.print()
        console.print("[yellow]Next steps:[/yellow]")
        console.print("  1. Run [cyan]/spec-kitty.plan[/cyan] to fill in the technical architecture")
        console.print("  2. Complete all [FEATURE], [DATE], and technical context placeholders")
        console.print("  3. Remove [REMOVE IF UNUSED] sections and choose your project structure")
        console.print("  4. Then run [cyan]/spec-kitty.research[/cyan] again")
        raise typer.Exit(1)

    created_paths: list[Path] = []

    def _copy_asset(step_key: str, label: str, relative_path: Path, template_name: Path) -> None:
        tracker.start(step_key)
        dest_path = planning_dir / relative_path
        template_path = resolve_template_path(project_root, mission_type, template_name)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dest_path.exists() and not force:
                created_paths.append(dest_path)
                return
            if template_path and template_path.is_file():
                shutil.copy2(template_path, dest_path)
            else:
                if dest_path.exists():
                    dest_path.unlink()
                dest_path.touch()
            created_paths.append(dest_path)
            tracker.complete(step_key, label)
        except Exception as exc:  # pragma: no cover - surfaces filesystem errors
            tracker.error(step_key, str(exc))
            console.print(tracker.render())
            raise typer.Exit(1)

    _copy_asset("research-md", "research.md ready", Path("research.md"), Path("research.md"))
    _copy_asset("data-model", "data-model.md ready", Path("data-model.md"), Path("data-model.md"))

    tracker.start("research-csv")
    csv_targets = [
        (Path("research") / "evidence-log.csv", Path("research") / "evidence-log.csv"),
        (Path("research") / "source-register.csv", Path("research") / "source-register.csv"),
    ]
    csv_errors: list[str] = []
    for dest_rel, template_rel in csv_targets:
        dest_path = planning_dir / dest_rel
        template_path = resolve_template_path(project_root, mission_type, template_rel)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dest_path.exists() and not force:
                created_paths.append(dest_path)
                continue
            if template_path and template_path.is_file():
                shutil.copy2(template_path, dest_path)
            else:
                if dest_path.exists():
                    dest_path.unlink()
                dest_path.touch()
            created_paths.append(dest_path)
        except Exception as exc:  # pragma: no cover
            csv_errors.append(f"{dest_rel}: {exc}")

    if csv_errors:
        tracker.error("research-csv", "; ".join(csv_errors))
        console.print(tracker.render())
        raise typer.Exit(1)
    else:
        tracker.complete("research-csv", "CSV templates ready")

    tracker.start("summary")
    tracker.complete("summary", f"{len(created_paths)} artifacts ready")

    console.print(tracker.render())

    relative_paths = [str(path.relative_to(planning_dir)) if path.is_relative_to(planning_dir) else str(path) for path in created_paths]
    summary_lines = "\n".join(f"- [cyan]{rel}[/cyan]" for rel in sorted(set(relative_paths)))
    console.print()
    console.print(
        Panel(
            summary_lines or "No artifacts were created (existing files kept).",
            title="Research Artifacts",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


__all__ = ["research"]
