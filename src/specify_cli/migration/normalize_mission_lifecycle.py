"""Normalize legacy ``kitty-specs`` missions for the MVP lifecycle model.

The goal is not to rewrite historical repositories into a perfect new layout.
It is to make old missions coherent enough that lifecycle derivation and
Teamspace-facing projections can reason about them consistently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.context.mission_resolver import is_kitty_specs_residue, probe_tracked_mission_paths, residue_notice
from specify_cli.migration.backfill_identity import (
    backfill_mission,
    backfill_wp_ids,
)
from specify_cli.status import derive_mission_lifecycle, generate_lifecycle_json
from specify_cli.status import generate_progress_json
from specify_cli.status import write_derived_views




@dataclass
class NormalizeMissionLifecycleResult:
    slug: str
    status: str
    lifecycle_state: str | None = None
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def _discover_candidates(repo_root: Path, mission_slug: str | None = None) -> list[Path]:
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        return []
    candidates = [entry for entry in sorted(kitty_specs.iterdir()) if entry.is_dir()]
    if mission_slug is not None:
        candidates = [entry for entry in candidates if entry.name == mission_slug]
    return candidates


def _needs_event_log(feature_dir: Path) -> bool:
    events_path = feature_dir / "status.events.jsonl"
    if events_path.exists():
        return False
    return (feature_dir / "status.json").exists() or (feature_dir / "tasks").is_dir()


def _needs_derived_refresh(feature_dir: Path, derived_dir: Path) -> bool:
    feature_derived = derived_dir / feature_dir.name
    status_path = feature_derived / "status.json"
    progress_path = feature_derived / "progress.json"
    lifecycle_path = feature_derived / "lifecycle.json"
    if not status_path.exists() or not progress_path.exists() or not lifecycle_path.exists():
        return True

    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return False

    events_mtime = events_path.stat().st_mtime
    return any(
        events_mtime > path.stat().st_mtime
        for path in (status_path, progress_path, lifecycle_path)
    )


def _missing_meta_notice(feature_dir: Path, repo_root: Path) -> str | None:
    """The operator notice for a Mission whose ``meta.json`` is absent on disk, or ``None`` (#6673).

    Only a Mission git knows something about gets the actionable text; a folder git holds
    nothing for keeps the short "skipped" line (it is a pre-identity folder, not a repair
    this step can do).
    """
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    classified = classify_missing_tracked_meta(feature_dir, repo_root)
    return None if classified is None else classified.notice


def _load_meta_for_normalization(
    feature_dir: Path,
    result: NormalizeMissionLifecycleResult,
    repo_root: Path,
) -> dict[str, Any] | None:
    from specify_cli.core.paths import load_meta_fail_closed, MissionMetaReadError
    try:
        meta = load_meta_fail_closed(feature_dir)
    except (OSError, MissionMetaReadError) as exc:
        result.status = "error"
        result.error = f"Could not read meta.json: {exc}"
        return None
    if meta is None:
        # A tracked meta.json that is missing from the working tree is #6673: report the
        # restore command and never derive an identity for the folder.
        notice = _missing_meta_notice(feature_dir, repo_root)
        result.warnings.append(notice or "meta.json missing; mission skipped")
        return None
    return meta


def _apply_identity_normalization(
    feature_dir: Path,
    meta: dict[str, Any],
    result: NormalizeMissionLifecycleResult,
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], bool] | None:
    refresh_derived = False
    try:
        backfill = backfill_mission(feature_dir, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001 - mission_number sentinel and similar legacy breakage
        result.status = "error"
        result.error = f"Identity backfill failed: {exc}"
        return None

    if backfill.action == "wrote":
        result.actions.append("Backfilled mission identity metadata")
        refresh_derived = True
    if backfill.number_coerced:
        result.actions.append("Normalized legacy mission_number type")
        refresh_derived = True

    if not dry_run and (backfill.action == "wrote" or backfill.number_coerced):
        from specify_cli.core.paths import load_meta_fail_closed
        meta = load_meta_fail_closed(feature_dir) or meta

    return meta, refresh_derived


def _normalize_event_log(
    feature_dir: Path,
    meta: dict[str, Any],
    result: NormalizeMissionLifecycleResult,
    *,
    dry_run: bool,
) -> bool | None:
    if not _needs_event_log(feature_dir):
        return False

    mission_id = meta.get("mission_id")
    if mission_id and (feature_dir / "tasks").is_dir():
        if dry_run:
            result.actions.append(
                "Would backfill missing WP identity fields before rebuilding the event log"
            )
        else:
            backfill_wp_ids(feature_dir, str(mission_id))
            result.actions.append("Backfilled missing WP identity fields")

    if dry_run:
        result.actions.append("Would rebuild status.events.jsonl from legacy mission state")
        return True

    # Route through the single canonical per-mission event-rebuild entry
    # (WP13, #1754). Imported at point of use to keep unrelated importers of
    # this module off the rebuild dependency chain.
    from specify_cli.migration.mission_state import rebuild_mission_event_log

    rebuild = rebuild_mission_event_log(feature_dir, result.slug, wp_id_map={})
    if rebuild.errors:
        result.status = "error"
        result.error = "; ".join(rebuild.errors)
        result.warnings.extend(rebuild.warnings)
        return None

    result.actions.append(
        "Rebuilt status.events.jsonl "
        f"({rebuild.events_generated} synthetic events, {rebuild.events_corrected} corrected)"
    )
    result.warnings.extend(rebuild.warnings)
    return True


def _finalize_lifecycle_projection(
    feature_dir: Path,
    derived_dir: Path,
    result: NormalizeMissionLifecycleResult,
    *,
    dry_run: bool,
    refresh_derived: bool,
) -> None:
    if dry_run and refresh_derived:
        result.actions.append("Would regenerate canonical status/progress/lifecycle views")
        try:
            result.lifecycle_state = derive_mission_lifecycle(feature_dir).state
        except Exception as exc:  # noqa: BLE001 - preview should stay resilient
            result.warnings.append(f"Lifecycle preview unavailable: {exc}")
    elif not dry_run and refresh_derived:
        try:
            write_derived_views(feature_dir, derived_dir)
            generate_progress_json(feature_dir, derived_dir)
            generate_lifecycle_json(feature_dir, derived_dir)
            result.lifecycle_state = derive_mission_lifecycle(feature_dir).state
        except Exception as exc:  # noqa: BLE001 - collect per-mission failure
            result.status = "error"
            result.error = f"Lifecycle materialization failed: {exc}"
            return
        result.actions.append("Regenerated canonical status/progress/lifecycle views")
    else:
        try:
            result.lifecycle_state = derive_mission_lifecycle(feature_dir).state
        except Exception as exc:  # noqa: BLE001 - report but do not fail a read-only no-op
            result.warnings.append(f"Lifecycle preview unavailable: {exc}")


def _repo_relative(path: Path, repo_root: Path) -> str:
    """POSIX path of *path* relative to *repo_root* (the notice must be unambiguous across worktrees)."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_repo(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> list[NormalizeMissionLifecycleResult]:
    """Normalize lifecycle-relevant mission state for one repo."""
    results: list[NormalizeMissionLifecycleResult] = []
    candidates = _discover_candidates(repo_root, mission_slug=mission_slug)
    if not candidates:
        return results

    derived_dir = repo_root / ".kittify" / "derived"
    tracked = probe_tracked_mission_paths(repo_root)

    for feature_dir in candidates:
        slug = feature_dir.name
        result = NormalizeMissionLifecycleResult(slug=slug, status="skipped")
        if is_kitty_specs_residue(feature_dir, repo_root=repo_root, tracked=tracked):
            # #6627: residue (e.g. an untracked decisions/ leftover) is reported, never given an identity.
            result.warnings.append(residue_notice(_repo_relative(feature_dir, repo_root)))
            results.append(result)
            continue
        meta = _load_meta_for_normalization(feature_dir, result, repo_root)
        if meta is None:
            results.append(result)
            continue

        identity_result = _apply_identity_normalization(
            feature_dir,
            meta,
            result,
            dry_run=dry_run,
        )
        if identity_result is None:
            results.append(result)
            continue
        meta, refresh_derived = identity_result

        event_refresh = _normalize_event_log(
            feature_dir,
            meta,
            result,
            dry_run=dry_run,
        )
        if event_refresh is None:
            results.append(result)
            continue

        refresh_derived = (
            refresh_derived
            or event_refresh
            or _needs_derived_refresh(feature_dir, derived_dir)
        )
        _finalize_lifecycle_projection(
            feature_dir,
            derived_dir,
            result,
            dry_run=dry_run,
            refresh_derived=refresh_derived,
        )
        if result.status == "error":
            results.append(result)
            continue

        if result.actions:
            result.status = "normalized"
        results.append(result)

    return results
