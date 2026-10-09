"""Task metadata validation and repair for Spec Kitty.

Detects and fixes inconsistencies between work package file locations
and their frontmatter metadata.
"""

from __future__ import annotations

import re
from kernel.clock import now_utc_stamp
from pathlib import Path

import yaml

from specify_cli.status_lanes import CANONICAL_LANES
from specify_cli.template import parse_frontmatter
from specify_cli.task_utils import build_document

__all__ = [
    "TaskMetadataError",
    "detect_lane_mismatch",
    "repair_lane_mismatch",
    "validate_task_metadata",
    "scan_all_tasks_for_mismatches",
]


class TaskMetadataError(Exception):
    """Raised when task metadata is inconsistent."""

    pass


def detect_lane_mismatch(task_file: Path) -> tuple[bool, str | None, str | None]:
    """Detect if task file's lane metadata doesn't match its directory.

    Args:
        task_file: Path to the work package prompt file

    Returns:
        Tuple of (has_mismatch, expected_lane, actual_lane)
        - has_mismatch: True if lane doesn't match directory
        - expected_lane: Lane based on file location (e.g., "for_review")
        - actual_lane: Lane from frontmatter metadata

    Examples:
        >>> task_file = Path("tasks/for_review/WP01.md")
        >>> has_mismatch, expected, actual = detect_lane_mismatch(task_file)
        >>> if has_mismatch:
        ...     print(f"File in {expected} but metadata says {actual}")
    """
    if not task_file.exists():
        return False, None, None

    # Determine expected lane from file path
    expected_lane = None
    for lane in ["planned", "doing", "for_review", "done"]:
        if f"/tasks/{lane}/" in str(task_file) or f"\\tasks\\{lane}\\" in str(task_file):
            expected_lane = lane
            break

    if not expected_lane:
        # File not in a recognized lane directory
        return False, None, None

    # Read frontmatter
    try:
        content = task_file.read_text(encoding="utf-8-sig")
        frontmatter, _, _ = parse_frontmatter(content)
    except Exception:
        return False, expected_lane, None

    # MIGRATION-ONLY: raw dict access is intentional here — this function
    # reads-then-mutates-then-writes frontmatter for legacy repair and must
    # operate on the mutable dict from parse_frontmatter(), not WPMetadata.
    actual_lane = frontmatter.get("lane", "").strip()

    has_mismatch = actual_lane != expected_lane
    return has_mismatch, expected_lane, actual_lane


def repair_lane_mismatch(  # MIGRATION-ONLY
    task_file: Path,
    *,
    agent: str = "system",
    shell_pid: str = "",
    add_history: bool = True,
    dry_run: bool = False,
) -> tuple[bool, str | None]:
    """MIGRATION-ONLY: Repair lane field in legacy WP frontmatter.

    This function reads and writes frontmatter ``lane`` for legacy
    migration purposes only. It must NOT be called from active runtime
    commands. Active status authority is ``status.events.jsonl``.

    Args:
        task_file: Path to the work package prompt file
        agent: Agent name for activity log
        shell_pid: Shell PID for activity log
        add_history: If True, append activity log entry
        dry_run: If True, don't modify file

    Returns:
        Tuple of (was_repaired, error_message)
        - was_repaired: True if repair was needed and applied
        - error_message: None if successful, error description if failed

    Examples:
        >>> was_repaired, error = repair_lane_mismatch(
        ...     Path("tasks/for_review/WP01.md"),
        ...     agent="codex",
        ...     shell_pid="12345"
        ... )
        >>> if was_repaired:
        ...     print("Fixed lane metadata")
    """
    has_mismatch, expected_lane, actual_lane = detect_lane_mismatch(task_file)

    if not has_mismatch:
        return False, None  # No repair needed

    if expected_lane is None:
        return False, f"Could not determine expected lane for {task_file.name}"

    # The read, the repair and the write are one hold of the Mission write lock, so another writer's
    # change to this file between the read and the write is never overwritten (plan A10).
    from specify_cli.status import FeatureStatusLockTimeoutError, mission_write_lock

    try:
        with mission_write_lock(_mission_dir_of(task_file)):
            return _rewrite_lane_metadata(
                task_file,
                expected_lane,
                actual_lane,
                agent=agent,
                shell_pid=shell_pid,
                add_history=add_history,
                dry_run=dry_run,
            )
    except FeatureStatusLockTimeoutError as exc:
        return False, f"Failed to lock the mission for {task_file.name}: {exc}"


def _mission_dir_of(task_file: Path) -> Path:
    """The Mission directory that owns *task_file*: the parent of its ``tasks`` directory, else its own directory."""
    for parent in task_file.parents:
        if parent.name == "tasks":
            return parent.parent
    return task_file.parent


def _rewrite_lane_metadata(
    task_file: Path,
    expected_lane: str,
    actual_lane: str | None,
    *,
    agent: str,
    shell_pid: str,
    add_history: bool,
    dry_run: bool,
) -> tuple[bool, str | None]:
    """Read *task_file*, set its ``lane`` (and the activity-log entry), and write it back; runs under the Mission lock."""
    try:
        content = task_file.read_text(encoding="utf-8-sig")
        frontmatter, body, _ = parse_frontmatter(content)
    except Exception as exc:
        return False, f"Failed to parse frontmatter: {exc}"

    # Update lane in frontmatter
    frontmatter["lane"] = expected_lane

    # Add activity log entry if requested
    if add_history:
        timestamp = now_utc_stamp()
        # WP04/T015 (NFR-003/SC-004): the runtime ``shell_pid`` slot is no longer
        # emitted as a parseable frontmatter field — no repair/template path may
        # re-introduce a runtime slot into ``tasks/WP##.md``. The claiming pid is
        # kept only as inert audit provenance inside the human-readable action
        # note (never parsed as a runtime field).
        repair_note = f"Auto-repaired lane metadata (was: {actual_lane}) [shell_pid {shell_pid}]"
        history_entry = (
            f'  - timestamp: "{timestamp}"\n'
            f'    lane: "{expected_lane}"\n'
            f'    agent: "{agent}"\n'
            f'    action: "{repair_note}"\n'
        )

        # Find activity_log in frontmatter
        if "activity_log" in frontmatter:
            # Append to existing activity log
            existing_log = frontmatter.get("activity_log", "")
            if isinstance(existing_log, list):
                # Already parsed as list - append dict
                frontmatter["activity_log"].append(
                    {
                        "timestamp": timestamp,
                        "lane": expected_lane,
                        "agent": agent,
                        "action": repair_note,
                    }
                )
            elif isinstance(existing_log, str):
                # Raw YAML string - append entry
                frontmatter["activity_log"] = existing_log.rstrip() + "\n" + history_entry
        else:
            # Create new activity log
            frontmatter["activity_log"] = history_entry

    if dry_run:
        return True, None  # Would repair but dry run

    # Rebuild file content
    try:
        # Convert frontmatter dict back to YAML string
        frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        new_content = build_document(frontmatter_yaml, body, "\n")
        task_file.write_text(new_content, encoding="utf-8-sig")
        return True, None
    except Exception as exc:
        return False, f"Failed to write file: {exc}"


def validate_task_metadata(task_file: Path) -> list[str]:  # MIGRATION-ONLY: raw dict access is intentional — diagnostic validator
    """Validate task metadata and return list of issues.

    Args:
        task_file: Path to the work package prompt file

    Returns:
        List of validation issues (empty if valid)

    Issues checked:
    - Lane mismatch between directory and frontmatter
    - Missing required frontmatter fields
    - Invalid lane values
    - Malformed activity log

    Examples:
        >>> issues = validate_task_metadata(Path("tasks/doing/WP01.md"))
        >>> if issues:
        ...     for issue in issues:
        ...         print(f"⚠️ {issue}")
    """
    issues = []

    if not task_file.exists():
        issues.append(f"File not found: {task_file}")
        return issues

    # Check lane mismatch
    has_mismatch, expected_lane, actual_lane = detect_lane_mismatch(task_file)
    if has_mismatch:
        issues.append(f"Lane mismatch: file in '{expected_lane}/' but metadata says '{actual_lane}'")

    # Parse frontmatter
    try:
        content = task_file.read_text(encoding="utf-8-sig")
        frontmatter, _, _ = parse_frontmatter(content)
    except Exception as exc:
        issues.append(f"Failed to parse frontmatter: {exc}")
        return issues

    # Check required fields
    required_fields = ["work_package_id", "lane"]
    for field in required_fields:
        if field not in frontmatter or not frontmatter[field]:
            issues.append(f"Missing required field: {field}")

    # Validate lane value against the 9 active/display lanes (CANONICAL_LANES).
    # "genesis" is intentionally excluded — it is a non-display/non-authorable
    # lane that no WP file should carry in its frontmatter.
    # "doing" is retained as a recognised alias for "in_progress" so that
    # legacy WP files written before the Lane enum migration don't report
    # false positives during the transition period.
    lane = frontmatter.get("lane", "")
    valid_lanes = frozenset(CANONICAL_LANES) | {"doing"}
    if lane and lane not in valid_lanes:
        issues.append(f"Invalid lane value: '{lane}' (must be one of {sorted(valid_lanes)})")

    # Check work_package_id format
    wp_id = frontmatter.get("work_package_id", "")
    if wp_id and not re.match(r"^WP\d+$", wp_id):
        issues.append(f"Invalid work_package_id format: '{wp_id}' (should be WP##)")

    return issues


def scan_all_tasks_for_mismatches(
    feature_dir: Path,
) -> dict[str, tuple[bool, str | None, str | None]]:
    """Scan all task files in a feature for lane mismatches.

    Args:
        feature_dir: Path to feature directory (e.g., kitty-specs/001-feature)

    Returns:
        Dictionary mapping file paths to (has_mismatch, expected_lane, actual_lane)
        Only includes files with mismatches.

    Examples:
        >>> feature_dir = Path("kitty-specs/001-my-feature")
        >>> mismatches = scan_all_tasks_for_mismatches(feature_dir)
        >>> for file_path, (_, expected, actual) in mismatches.items():
        ...     print(f"{file_path}: {actual} → {expected}")
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return {}

    mismatches: dict[str, tuple[bool, str | None, str | None]] = {}

    # Scan all lanes
    for lane in ["planned", "doing", "for_review", "done"]:
        lane_dir = tasks_dir / lane
        if not lane_dir.exists():
            continue

        for task_file in lane_dir.rglob("WP*.md"):
            has_mismatch, expected, actual = detect_lane_mismatch(task_file)
            if has_mismatch:
                # Store relative path for readability
                try:
                    rel_path = task_file.relative_to(feature_dir)
                except ValueError:
                    rel_path = task_file
                mismatches[str(rel_path)] = (has_mismatch, expected, actual)

    return mismatches
