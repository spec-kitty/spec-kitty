"""Research command implementation for Spec Kitty CLI."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

from specify_cli.asset_preservation import guard_destructive_overwrite
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


@dataclass(frozen=True)
class _AssetOutcome:
    """The result of one guarded research-asset write attempt.

    ``reason`` carries the underlying :class:`OverwriteVerdict.reason` code
    (#4926 reporting-honesty fix) so a caller can distinguish WHY a skip
    happened — "no template resolved for this asset" vs. "a template
    resolved but the destination already exists and wasn't authorized to be
    overwritten" — instead of collapsing every skip into one blanket
    "no template" claim.
    """

    relative_path: Path
    created: bool
    diagnostic: str
    reason: str


# `OverwriteVerdict.reason` codes (guard.py `_overwrite_existing`) that mean
# "a template resolved, but the destination already exists and wasn't proven
# package-owned / authorized to overwrite" — i.e. something WAS preserved,
# not "nothing to create here".
_PRESERVED_EXISTING_REASONS = frozenset({"unauthorized", "would-truncate-to-empty"})


def _has_preserved_existing(skipped: list[tuple[Path, str, str]]) -> bool:
    """True when at least one skip was a preserve-existing refusal rather
    than a genuine no-template-resolved case (#4926)."""
    return any(reason in _PRESERVED_EXISTING_REASONS for _, _, reason in skipped)


def _write_research_asset(
    *,
    dest_rel: Path,
    template_rel: Path,
    planning_dir: Path,
    project_root: Path,
    mission_type: str,
    force: bool,
) -> _AssetOutcome:
    """Decide-then-write ONE research asset through
    ``guard_destructive_overwrite`` (#4926/FR-002/T021): the skip decision is
    made BEFORE any filesystem mutation, so a refusal never unlinks the
    destination first and "fabricates" second. Shared by both the
    research.md/data-model.md copy path and the CSV stub loop
    (research/evidence-log.csv, research/source-register.csv) — all four
    assets shared the same destroyer, so they now share the same fix.
    """
    dest_path = planning_dir / dest_rel
    template_path = resolve_template_path(project_root, mission_type, template_rel)
    substantive = template_path is not None and template_path.is_file()
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    verdict = guard_destructive_overwrite(
        dest_path,
        project_root,
        replacement_substantive=substantive,
        authorized=force,
    )
    if not verdict.proceed:
        return _AssetOutcome(dest_rel, created=False, diagnostic=verdict.diagnostic, reason=verdict.reason)

    # The guard proceeds only when the replacement is substantive (an absent
    # or existing destination with a non-substantive replacement always
    # refuses, regardless of `authorized` — guard_destructive_overwrite's
    # truth table), so `template_path` is guaranteed to be a real file here.
    assert template_path is not None
    shutil.copy2(template_path, dest_path)
    return _AssetOutcome(dest_rel, created=True, diagnostic=verdict.diagnostic, reason=verdict.reason)


def _read_mission_dir_or_exit(repo_root: Path, mission_slug: str, kind: MissionArtifactKind) -> Path:
    """Resolve a mission artifact read dir, exiting cleanly on an unsafe or
    ambiguous slug.

    #2878: a traversal-shaped ``--mission`` value trips the safe-path-segment
    guard (``assert_safe_path_segment``) inside the placement seam and raises
    ``UnsafePathSegmentError`` that no caller in this command catches — the raw
    traceback the issue reports. Mirrors merge's ``_resolve_slug_or_exit``
    exemplar (cli/commands/merge.py): canonical diagnostic + ``exit 2``, never
    a traceback. The ``merge._constants`` import stays function-local so the
    happy path never pays the merge package's import graph.

    #4723: a bare human slug matching >1 composed ``<slug>-<mid8>`` primary
    dir raises ``MissionSelectorAmbiguous`` from the seam's bare-modern-slug
    fold — previously uncaught here, producing the same kind of raw traceback
    #2878 already fixed for ``UnsafePathSegmentError``. Rendered with the same
    structured ``MISSION_AMBIGUOUS_SELECTOR`` shape other read-path-resolver
    consumers (``verify.py``, ``materialize.py``, ``archive.py``) use.
    """
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    try:
        return placement_seam(repo_root, mission_slug).read_dir(kind)
    except UnsafePathSegmentError as exc:
        from specify_cli.merge._constants import _SAFE_PATH_SEGMENT_DIAGNOSTIC

        console.print(f"[red]Error:[/red] {_SAFE_PATH_SEGMENT_DIAGNOSTIC}: {exc}")
        raise typer.Exit(2) from exc
    except MissionSelectorAmbiguous as exc:
        console.print(f"[red]Error:[/red] {exc}")
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
        console.print("  1. Run [cyan]/spec-kitty.plan[/cyan] inside your coding agent (Claude Code, Codex, Cursor) to fill in the technical architecture")
        console.print("  2. Complete all [FEATURE], [DATE], and technical context placeholders")
        console.print("  3. Remove [REMOVE IF UNUSED] sections and choose your project structure")
        console.print("  4. Then run [cyan]/spec-kitty.research[/cyan] again in the agent")
        raise typer.Exit(1)

    created_paths: list[Path] = []
    skipped_assets: list[tuple[Path, str, str]] = []

    def _copy_asset(step_key: str, label: str, relative_path: Path, template_name: Path) -> None:
        tracker.start(step_key)
        try:
            outcome = _write_research_asset(
                dest_rel=relative_path,
                template_rel=template_name,
                planning_dir=planning_dir,
                project_root=project_root,
                mission_type=mission_type,
                force=force,
            )
        except Exception as exc:  # pragma: no cover - surfaces filesystem errors
            tracker.error(step_key, str(exc))
            console.print(tracker.render())
            raise typer.Exit(1)

        if outcome.created:
            created_paths.append(planning_dir / relative_path)
            tracker.complete(step_key, label)
        else:
            skipped_assets.append((relative_path, outcome.diagnostic, outcome.reason))
            tracker.skip(step_key, outcome.diagnostic)

    _copy_asset("research-md", "research.md ready", Path("research.md"), Path("research.md"))
    _copy_asset("data-model", "data-model.md ready", Path("data-model.md"), Path("data-model.md"))

    tracker.start("research-csv")
    csv_targets = [
        (Path("research") / "evidence-log.csv", Path("research") / "evidence-log.csv"),
        (Path("research") / "source-register.csv", Path("research") / "source-register.csv"),
    ]
    csv_errors: list[str] = []
    csv_skipped: list[tuple[Path, str, str]] = []
    csv_created = 0
    for dest_rel, template_rel in csv_targets:
        try:
            outcome = _write_research_asset(
                dest_rel=dest_rel,
                template_rel=template_rel,
                planning_dir=planning_dir,
                project_root=project_root,
                mission_type=mission_type,
                force=force,
            )
        except Exception as exc:  # pragma: no cover
            csv_errors.append(f"{dest_rel}: {exc}")
            continue

        if outcome.created:
            created_paths.append(planning_dir / dest_rel)
            csv_created += 1
        else:
            csv_skipped.append((dest_rel, outcome.diagnostic, outcome.reason))

    skipped_assets.extend(csv_skipped)

    if csv_errors:
        tracker.error("research-csv", "; ".join(csv_errors))
        console.print(tracker.render())
        raise typer.Exit(1)
    elif csv_created:
        tracker.complete("research-csv", f"{csv_created} CSV template(s) ready")
    elif _has_preserved_existing(csv_skipped):
        # #4926: a CSV template resolved but the destination(s) already exist
        # and weren't authorized to be overwritten — distinct from "no
        # template ships for this mission type".
        tracker.skip("research-csv", "Existing research CSV template(s) preserved; re-run with --force to overwrite")
    else:
        tracker.skip("research-csv", f"No research CSV template for mission type '{mission_display}'")

    tracker.start("summary")
    if created_paths:
        tracker.complete("summary", f"{len(created_paths)} artifact(s) ready")
    elif _has_preserved_existing(skipped_assets):
        # #4926: at least one skip was a preserve-existing refusal, not a
        # genuine "no template resolved anywhere" case — say so honestly.
        tracker.skip("summary", "Existing research artifact(s) preserved (not overwritten) — re-run with --force")
    else:
        tracker.skip("summary", f"No research template for mission type '{mission_display}' — nothing created")

    console.print(tracker.render())

    console.print()
    if created_paths:
        relative_paths = [str(path.relative_to(planning_dir)) if path.is_relative_to(planning_dir) else str(path) for path in created_paths]
        summary_lines = "\n".join(f"- [cyan]{rel}[/cyan]" for rel in sorted(set(relative_paths)))
        if skipped_assets:
            # #4926: a mix of created + skipped assets — report what was
            # skipped too, rather than silently omitting it from a headline
            # that only names what got created.
            skip_lines = "\n".join(f"- [yellow]{rel}[/yellow]: {diagnostic}" for rel, diagnostic, _reason in skipped_assets)
            summary_lines = f"{summary_lines}\n\n[yellow]Preserved / skipped:[/yellow]\n{skip_lines}"
        console.print(
            Panel(
                summary_lines,
                title="Research Artifacts",
                border_style="cyan",
                padding=(1, 2),
            )
        )
    else:
        # #4926 reporting-honesty fix: "nothing was created" has two distinct,
        # non-interchangeable causes — (a) a template genuinely resolved
        # nowhere for this mission type, or (b) a template DID resolve but
        # every destination already existed and wasn't authorized to be
        # overwritten. Collapsing both into "No research template for
        # mission type X" is provably false in case (b): the first run's own
        # output already proved a template exists. Derive the headline from
        # the actual per-asset skip reasons instead of the created_paths-only
        # signal (T022's original fix only handled the genuine-absence case).
        skipped_lines = "\n".join(f"- [yellow]{rel}[/yellow]: {diagnostic}" for rel, diagnostic, _reason in skipped_assets)
        if _has_preserved_existing(skipped_assets):
            headline = (
                "Existing research artifacts preserved; they are not proven package-owned and "
                "[cyan]--force[/cyan] was not given, so they were not overwritten. "
                "Re-run with [cyan]--force[/cyan] to overwrite them."
            )
        else:
            headline = f"No research template for mission type '{mission_display}'. Nothing was created; any existing files were preserved unchanged."
        console.print(
            Panel(
                headline + "\n\n" + (skipped_lines or "No assets processed."),
                title="Research Artifacts",
                border_style="yellow",
                padding=(1, 2),
            )
        )
    console.print()


__all__ = ["research"]
