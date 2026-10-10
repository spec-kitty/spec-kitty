"""Legacy migration: reads and writes frontmatter ``lane`` field.

This migration predates the canonical event-log status model (3.0).
Frontmatter lane is no longer authoritative for active features.

Original purpose: repair feature metadata/state drift and legacy
worktree assets.
"""

from __future__ import annotations

import io
import json
import re
from kernel.clock import now_utc_compact_stamp
from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree
from pathlib import Path
from typing import Any

from specify_cli.agent_utils.directories import AGENT_DIRS
from specify_cli.frontmatter import FrontmatterError, FrontmatterManager
from specify_cli.runtime.doctor import check_stale_legacy_assets
from specify_cli.status import SNAPSHOT_FILENAME, materialize
from specify_cli.status import EVENTS_FILENAME, StoreError, read_events
from specify_cli.status import CANONICAL_LANES, resolve_lane_alias
from specify_cli.status import validate_materialization_drift
from specify_cli.status import mission_write_lock
from specify_cli.upgrade.feature_meta import (
    build_baseline_feature_meta,
    load_feature_meta,
    write_feature_meta,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

_PROMPT_LINE_RE = re.compile(r"^(\*\*Prompt\*\*:\s*`?)([^`\n]+)(`?)$", re.MULTILINE)


@MigrationRegistry.register
class ConsistencySweepMigration(BaseMigration):
    """Repair version-stamped projects that still have structural drift."""

    migration_id = "2.0.6_consistency_sweep"
    description = "Repair feature metadata/state drift and clean legacy worktree assets"
    target_version = "2.0.6"

    def detect(self, project_path: Path) -> bool:
        """Return True when project state still needs 2.0.6 consistency repair."""
        if check_stale_legacy_assets(project_path).passed is False:
            return True
        if _has_legacy_worktree_assets(project_path):
            return True

        return any(_feature_requires_repair(feature_dir, project_path) for feature_dir in _iter_feature_dirs(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Consistency repair only needs a spec project root."""
        if (project_path / ".kittify").exists() or (project_path / "kitty-specs").exists():
            return True, ""
        return False, "No .kittify/ or kitty-specs/ directory found"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Run the 2.0.6 consistency sweep."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        runtime_changes, runtime_warnings = _migrate_runtime_assets(project_path, dry_run)
        changes.extend(runtime_changes)
        warnings.extend(runtime_warnings)

        worktree_changes, worktree_errors = _cleanup_legacy_worktree_assets(project_path, dry_run)
        changes.extend(worktree_changes)
        errors.extend(worktree_errors)

        for feature_dir in _iter_feature_dirs(project_path):
            feature_changes, feature_warnings = _repair_feature(feature_dir, project_path, dry_run)
            changes.extend(feature_changes)
            warnings.extend(feature_warnings)

        if not changes and not warnings and not errors:
            changes.append("Project already consistent for 2.0.6")

        return MigrationResult(
            success=not errors,
            changes_made=changes,
            warnings=warnings,
            errors=errors,
        )


def _iter_feature_dirs(project_path: Path) -> list[Path]:
    kitty_specs = project_path / "kitty-specs"
    if not kitty_specs.exists():
        return []
    return [path for path in sorted(kitty_specs.iterdir()) if path.is_dir()]


def _feature_requires_repair(feature_dir: Path, repo_root: Path) -> bool:
    try:
        meta = load_feature_meta(feature_dir)
    except json.JSONDecodeError:
        return True
    if meta is None:
        return True
    desired_meta = build_baseline_feature_meta(
        feature_dir,
        repo_root,
        existing_meta=meta,
    )
    if meta != desired_meta:
        return True
    if _tasks_md_has_legacy_prompt_refs(feature_dir):
        return True
    if _has_orphan_status_snapshot(feature_dir):
        return True
    if _wp_frontmatter_needs_normalization(feature_dir):
        return True
    return bool(_feature_has_status_drift(feature_dir))


def _repair_feature(
    feature_dir: Path,
    repo_root: Path,
    dry_run: bool,
) -> tuple[list[str], list[str]]:
    changes: list[str] = []
    warnings: list[str] = []

    meta_changes, meta_warnings = _repair_feature_meta(feature_dir, repo_root, dry_run)
    changes.extend(meta_changes)
    warnings.extend(meta_warnings)

    normalized_count, normalize_warnings = _normalize_wp_frontmatter(feature_dir, dry_run)
    warnings.extend(f"{feature_dir.name}: {warning}" for warning in normalize_warnings)
    if normalized_count:
        verb = "Would normalize" if dry_run else "Normalized"
        changes.append(f"{feature_dir.name}: {verb.lower()} {normalized_count} work package files")

    orphan_change, orphan_warning = _cleanup_orphan_status_snapshot(feature_dir, dry_run)
    if orphan_change:
        changes.append(f"{feature_dir.name}: {orphan_change}")
    if orphan_warning:
        warnings.append(f"{feature_dir.name}: {orphan_warning}")

    unreadable_change, unreadable_warning = _cleanup_unreadable_events_log(feature_dir, dry_run)
    if unreadable_change:
        changes.append(f"{feature_dir.name}: {unreadable_change}")
    if unreadable_warning:
        warnings.append(f"{feature_dir.name}: {unreadable_warning}")

    has_event_log = _feature_has_event_log(feature_dir)
    if has_event_log or unreadable_change:
        if dry_run:
            if unreadable_change or _feature_has_status_drift(feature_dir):
                changes.append(f"{feature_dir.name}: would regenerate status.json")
        else:
            materialize(feature_dir)
            if unreadable_change or _feature_has_status_drift(feature_dir):
                changes.append(f"{feature_dir.name}: regenerated status.json")

    prompt_rewrites = _rewrite_tasks_prompt_refs(feature_dir, dry_run)
    if prompt_rewrites:
        verb = "Would rewrite" if dry_run else "Rewrote"
        changes.append(f"{feature_dir.name}: {verb.lower()} {prompt_rewrites} legacy prompt reference(s)")

    return changes, warnings


def _repair_feature_meta(feature_dir: Path, repo_root: Path, dry_run: bool) -> tuple[list[str], list[str]]:
    """Read, rebuild and (unless *dry_run*) write the baseline ``meta.json`` in ONE hold of the Mission write lock.

    The read that decides what to write happens inside the hold, so a field another writer sets between
    the read and the write is never overwritten by a stale baseline. The lock falls back to the directory
    name for a Mission whose own ``meta.json`` is what this repairs.
    """
    changes: list[str] = []
    warnings: list[str] = []
    with mission_write_lock(feature_dir, repo_root=repo_root, fallback_to_dir_name=True):
        meta = None
        try:
            meta = load_feature_meta(feature_dir)
        except json.JSONDecodeError as exc:
            warnings.append(f"{feature_dir.name}: invalid meta.json ({exc})")

        desired_meta = build_baseline_feature_meta(
            feature_dir,
            repo_root,
            existing_meta=meta,
        )
        if meta != desired_meta:
            action = "Would write" if dry_run else "Wrote"
            changes.append(f"{feature_dir.name}: {action.lower()} baseline meta.json")
            if not dry_run:
                write_feature_meta(feature_dir, desired_meta)
    return changes, warnings


def _normalize_wp_frontmatter(feature_dir: Path, dry_run: bool) -> tuple[int, list[str]]:
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return 0, []

    manager = FrontmatterManager()
    normalized = 0
    warnings: list[str] = []

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        with mission_write_lock(feature_dir, fallback_to_dir_name=True):
            changed, warning = _normalize_one_wp_frontmatter(manager, wp_file, dry_run)
        if warning is not None:
            warnings.append(warning)
        if changed:
            normalized += 1

    return normalized, warnings


def _normalize_one_wp_frontmatter(manager: FrontmatterManager, wp_file: Path, dry_run: bool) -> tuple[bool, str | None]:
    """Normalize one work package's frontmatter (runs under the Mission write lock); say whether it changed, or why it was skipped."""
    try:
        original = wp_file.read_text(encoding="utf-8-sig")
        frontmatter, body = manager.read(wp_file)
    except FrontmatterError as exc:
        return False, f"{wp_file.name}: {exc}"

    raw_lane = frontmatter.get("lane") or "planned"  # MIGRATION-ONLY: raw dict read-mutate-write
    canonical_lane = resolve_lane_alias(str(raw_lane))
    if canonical_lane in CANONICAL_LANES:
        frontmatter["lane"] = canonical_lane

    rendered = _render_frontmatter(manager, frontmatter, body)
    if original == rendered:
        return False, None
    if not dry_run:
        wp_file.write_text(rendered, encoding="utf-8")
    return True, None


def _render_frontmatter(manager: FrontmatterManager, frontmatter: dict[str, Any], body: str) -> str:
    buffer = io.StringIO()
    buffer.write("---\n")
    manager.yaml.dump(manager._normalize_frontmatter(frontmatter), buffer)
    buffer.write("---\n")
    buffer.write(body)
    return buffer.getvalue()


def _rewrite_tasks_prompt_refs(feature_dir: Path, dry_run: bool) -> int:
    """Rewrite legacy prompt references in ``tasks.md``; the read and the write are one hold of the Mission write lock."""
    with mission_write_lock(feature_dir, fallback_to_dir_name=True):
        return _rewrite_tasks_prompt_refs_locked(feature_dir, dry_run)


def _rewrite_tasks_prompt_refs_locked(feature_dir: Path, dry_run: bool) -> int:
    tasks_md = feature_dir / "tasks.md"
    tasks_dir = feature_dir / "tasks"
    if not tasks_md.exists() or not tasks_dir.exists():
        return 0

    content = tasks_md.read_text(encoding="utf-8")
    rewrites = 0

    def replacer(match: re.Match[str]) -> str:
        nonlocal rewrites
        prefix, prompt_path, suffix = match.groups()
        if "tasks/" not in prompt_path:
            return match.group(0)

        wp_match = re.search(r"(WP\d{2})", prompt_path)
        if wp_match is None:
            return match.group(0)

        candidates = sorted(tasks_dir.glob(f"{wp_match.group(1)}*.md"))
        if not candidates:
            return match.group(0)

        tasks_index = prompt_path.find("tasks/")
        if tasks_index == -1:
            return match.group(0)

        new_path = prompt_path[:tasks_index] + "tasks/" + candidates[0].name
        if new_path == prompt_path:
            return match.group(0)

        rewrites += 1
        return f"{prefix}{new_path}{suffix}"

    updated = _PROMPT_LINE_RE.sub(replacer, content)
    if rewrites and not dry_run:
        tasks_md.write_text(updated, encoding="utf-8")
    return rewrites


def _feature_has_event_log(feature_dir: Path) -> bool:
    events_path = feature_dir / EVENTS_FILENAME
    return events_path.exists() and bool(events_path.read_text(encoding="utf-8").strip())


def _feature_has_status_drift(feature_dir: Path) -> bool:
    """Check if the status.json snapshot is out of date with the event log."""
    if not _feature_has_event_log(feature_dir):
        return False

    return bool(validate_materialization_drift(feature_dir))


def _tasks_md_has_legacy_prompt_refs(feature_dir: Path) -> bool:
    tasks_md = feature_dir / "tasks.md"
    if not tasks_md.exists():
        return False
    for line in tasks_md.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("**Prompt**:"):
            continue
        if any(segment in line for segment in ("tasks/planned/", "tasks/doing/", "tasks/for_review/", "tasks/done/")):
            return True
    return False


def _wp_frontmatter_needs_normalization(feature_dir: Path) -> bool:
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return False
    manager = FrontmatterManager()
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        content = wp_file.read_text(encoding="utf-8-sig", errors="ignore")
        if re.search(r'^lane:\s*["\']', content, re.MULTILINE):
            return True
        if re.search(r"^lane:\s*doing\s*$", content, re.MULTILINE):
            return True
        try:
            frontmatter, _body = manager.read(wp_file)
        except FrontmatterError:
            return True
        raw_lane = frontmatter.get("lane")  # MIGRATION-ONLY: raw dict read-mutate-write
        if raw_lane is None or not str(raw_lane).strip():
            return True
    return False


def _has_orphan_status_snapshot(feature_dir: Path) -> bool:
    status_path = feature_dir / SNAPSHOT_FILENAME
    events_path = feature_dir / EVENTS_FILENAME
    if not status_path.exists() or events_path.exists():
        return False
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        data.get("event_count") == 0
        and data.get("work_packages") == {}
        and data.get("summary") == dict.fromkeys(CANONICAL_LANES, 0)
        and data.get("feature_slug", "") in {"", feature_dir.name}
    )


def _cleanup_orphan_status_snapshot(feature_dir: Path, dry_run: bool) -> tuple[str | None, str | None]:
    status_path = feature_dir / SNAPSHOT_FILENAME
    if not _has_orphan_status_snapshot(feature_dir):
        if status_path.exists() and not (feature_dir / EVENTS_FILENAME).exists() and not (feature_dir / "tasks").exists():
            return None, "status.json has no matching event log and could not be auto-repaired"
        return None, None

    timestamp = now_utc_compact_stamp()
    backup_name = f"{SNAPSHOT_FILENAME}.orphan.bak.{timestamp}"
    if not dry_run:
        status_path.rename(feature_dir / backup_name)
    return f"archived orphan {SNAPSHOT_FILENAME} to {backup_name}", None


def _cleanup_unreadable_events_log(feature_dir: Path, dry_run: bool) -> tuple[str | None, str | None]:
    events_path = feature_dir / EVENTS_FILENAME
    if not events_path.exists():
        return None, None

    content = events_path.read_text(encoding="utf-8").strip()
    if not content:
        return None, None

    try:
        read_events(feature_dir)
        return None, None
    except StoreError as exc:
        timestamp = now_utc_compact_stamp()
        backup_name = f"{EVENTS_FILENAME}.unreadable.bak.{timestamp}"
        if not dry_run:
            events_path.rename(feature_dir / backup_name)
        return (
            f"archived unreadable {EVENTS_FILENAME} to {backup_name}",
            f"status.events.jsonl was unreadable and has been quarantined ({exc})",
        )


def _migrate_runtime_assets(project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
    kittify_dir = project_path / ".kittify"
    if not kittify_dir.exists():
        return [], []

    try:
        from specify_cli.runtime.migrate import execute_migration

        report = execute_migration(project_path, dry_run=dry_run)
    except Exception as exc:  # pragma: no cover - defensive guard
        return [], [f"runtime asset cleanup skipped: {exc}"]

    changes: list[str] = []
    moved = len(report.moved)
    removed = len(report.removed)
    if moved or removed:
        verb = "Would migrate" if dry_run else "Migrated"
        changes.append(f"{verb.lower()} {removed} identical and {moved} customized legacy runtime asset(s)")
    return changes, []


def _has_legacy_worktree_assets(project_path: Path) -> bool:
    return any(_iter_worktree_cleanup_roots(project_path))


def _iter_worktree_cleanup_roots(project_path: Path) -> list[Path]:
    if ".worktrees" in project_path.parts:
        return [project_path]

    worktrees_dir = project_path / ".worktrees"
    if not worktrees_dir.exists():
        return []
    return [path for path in sorted(worktrees_dir.iterdir()) if path.is_dir()]


def _cleanup_legacy_worktree_assets(project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
    changes: list[str] = []
    errors: list[str] = []
    cleaned = 0

    for root in _iter_worktree_cleanup_roots(project_path):
        root_cleaned = False
        for agent_dir, subdir in AGENT_DIRS:
            commands_dir = root / agent_dir / subdir
            if commands_dir.is_symlink() or commands_dir.exists():
                root_cleaned = True
                if dry_run:
                    changes.append(f"[{root.name}] would remove {agent_dir}/{subdir}/")
                else:
                    try:
                        if commands_dir.is_symlink():
                            commands_dir.unlink()
                        else:
                            remove_tool_owned_tree(commands_dir, owned_root=commands_dir, reason="worktree agent commands dir")
                        parent = commands_dir.parent
                        if parent.exists() and not any(parent.iterdir()):
                            parent.rmdir()
                    except (OSError, ToolOwnedPathUnproven) as exc:
                        errors.append(f"[{root.name}] failed to remove {agent_dir}/{subdir}/: {exc}")

        scripts_dir = root / ".kittify" / "scripts"
        if scripts_dir.is_symlink() or scripts_dir.exists():
            root_cleaned = True
            if dry_run:
                changes.append(f"[{root.name}] would remove .kittify/scripts/")
            else:
                try:
                    if scripts_dir.is_symlink():
                        scripts_dir.unlink()
                    else:
                        remove_tool_owned_tree(scripts_dir, owned_root=scripts_dir, reason="worktree .kittify/scripts")
                except (OSError, ToolOwnedPathUnproven) as exc:
                    errors.append(f"[{root.name}] failed to remove .kittify/scripts/: {exc}")

        if root_cleaned:
            cleaned += 1

    if cleaned:
        verb = "Would clean" if dry_run else "Cleaned"
        changes.append(f"{verb.lower()} {cleaned} worktree(s) with legacy command/script assets")
    return changes, errors
