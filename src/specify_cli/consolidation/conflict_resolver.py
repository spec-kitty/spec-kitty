"""Auto-resolution of merge conflicts for spec-kitty-owned files.

Implements T040: classifies conflicted files and resolves owned ones.

Rules:
- ``*.events.jsonl``: append-merge (concatenate both sides, dedup by event_id,
  sort by timestamp). This is the canonical event log; its integrity is critical.
- WP frontmatter / metadata files: take-theirs (latest version wins).
- Human-authored files: do NOT auto-resolve — mark as unresolved.
- Derived / runtime files (under .kittify/derived/ or .kittify/runtime/):
  SHOULD be gitignored and must NEVER appear as merge conflicts. If one does,
  flag it as UNEXPECTED_DERIVED (error, not silent auto-resolve).
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import json
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from kernel.paths import to_posix

__all__ = [
    "ConflictType",
    "ResolutionResult",
    "classify_conflict",
    "resolve_owned_conflicts",
]


class ConflictType(Enum):
    """Classification of a conflicted file."""

    OWNED_EVENT_LOG = "owned_event_log"
    """Canonical JSONL event log — append-merge (dedup by event_id, sort by ts)."""

    OWNED_METADATA = "owned_metadata"
    """Spec-kitty-owned metadata (frontmatter, meta.json) — take-theirs."""

    HUMAN_AUTHORED = "human_authored"
    """Human-authored file — must be resolved manually."""

    UNEXPECTED_DERIVED = "unexpected_derived"
    """Derived / runtime file that should be gitignored — flag as error."""


@dataclass
class ResolutionResult:
    """Outcome of attempting auto-resolution for a set of conflicted files."""

    resolved: list[str] = field(default_factory=list)
    """Files that were successfully auto-resolved."""

    unresolved: list[str] = field(default_factory=list)
    """Files that require manual resolution (human-authored)."""

    errors: list[str] = field(default_factory=list)
    """Errors encountered (unexpected derived files, I/O failures, etc.)."""

    @property
    def has_unresolved(self) -> bool:
        return bool(self.unresolved)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def classify_conflict(file_path: str) -> ConflictType:
    """Classify a conflicted file to determine resolution strategy.

    Args:
        file_path: Relative path to the conflicted file (as reported by git).

    Returns:
        ConflictType indicating how to handle this conflict.
    """
    # Derived / runtime files should be gitignored — flag as error if seen
    normalized = to_posix(file_path)
    if (
        normalized.startswith(".kittify/derived/")
        or normalized.startswith(".kittify/runtime/")
    ):
        return ConflictType.UNEXPECTED_DERIVED

    # Canonical event log — append-merge
    if normalized.endswith(".events.jsonl"):
        return ConflictType.OWNED_EVENT_LOG

    # Spec-kitty metadata files — take-theirs
    if (
        normalized.endswith("/meta.json")
        or normalized == "meta.json"
        or normalized.endswith("/status.json")
        or normalized == "status.json"
        or (
            normalized.startswith(".kittify/")
            and normalized.endswith(".json")
        )
    ):
        return ConflictType.OWNED_METADATA

    # WP prompt files (frontmatter markdown under kitty-specs/*/tasks/)
    if (
        f"{KITTY_SPECS_DIR}/" in normalized
        and "/tasks/" in normalized
        and normalized.endswith(".md")
    ):
        return ConflictType.OWNED_METADATA

    # Everything else requires manual resolution
    return ConflictType.HUMAN_AUTHORED


def _read_conflict_sides(workspace_path: Path, file_path: str) -> tuple[str, str]:
    """Extract ours and theirs from a conflicted file using git show.

    Returns (ours_content, theirs_content) as raw strings.
    The workspace must be the git worktree where the conflict occurred.
    """
    # Use git show :2:<path> for ours, :3:<path> for theirs
    ours_result = subprocess.run(
        ["git", "show", f":2:{file_path}"],
        cwd=str(workspace_path),
        capture_output=True,
        check=False,
    )
    theirs_result = subprocess.run(
        ["git", "show", f":3:{file_path}"],
        cwd=str(workspace_path),
        capture_output=True,
        check=False,
    )

    ours = ours_result.stdout.decode("utf-8", errors="replace") if ours_result.returncode == 0 else ""
    theirs = theirs_result.stdout.decode("utf-8", errors="replace") if theirs_result.returncode == 0 else ""
    return ours, theirs


def _merge_event_logs(ours: str, theirs: str) -> str:
    """Append-merge two JSONL event logs.

    Algorithm:
    1. Parse all lines from both sides as JSON objects.
    2. Deduplicate by event_id (keep first seen).
    3. Sort by the 'at' (timestamp) field.
    4. Emit as newline-delimited JSON, one event per line.

    Malformed lines are silently skipped to keep the log usable.
    """
    seen_ids: set[str] = set()
    events: list[dict[str, object]] = []

    for content in (ours, theirs):
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_id = event.get("event_id", "")
            if event_id and event_id in seen_ids:
                continue
            if event_id:
                seen_ids.add(event_id)
            events.append(event)

    # Sort by timestamp ascending; fall back to stable insertion order for equal ts
    events.sort(key=lambda e: str(e.get("at", "")))

    lines = [json.dumps(e, sort_keys=True) for e in events]
    result = "\n".join(lines)
    if result and not result.endswith("\n"):
        result += "\n"
    return result


def _stage_resolved_file(workspace_path: Path, file_path: str, content: str) -> None:
    """Write resolved content and stage the file with git add."""
    abs_path = workspace_path / file_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "add", file_path],
        cwd=str(workspace_path),
        check=True,
    )


def resolve_owned_conflicts(
    workspace_path: Path,
    conflicted_files: list[str],
) -> ResolutionResult:
    """Auto-resolve conflicts for spec-kitty-owned files.

    For each conflicted file:
    - Event logs (.events.jsonl): append-merge (dedup by event_id, sort by ts).
    - Metadata (frontmatter, meta.json): take-theirs.
    - Human-authored files: leave unresolved.
    - Unexpected derived files (.kittify/derived/, .kittify/runtime/):
      flag as error (they must be gitignored).

    After resolving a file, it is staged with ``git add``.

    Args:
        workspace_path: Path to the git worktree where the conflict occurred.
        conflicted_files: List of relative file paths with merge conflicts.

    Returns:
        ResolutionResult with resolved, unresolved, and error lists.
    """
    result = ResolutionResult()

    for file_path in conflicted_files:
        conflict_type = classify_conflict(file_path)

        if conflict_type == ConflictType.UNEXPECTED_DERIVED:
            result.errors.append(
                f"UNEXPECTED_DERIVED: {file_path!r} appeared as a merge conflict "
                "but should be gitignored. Check .gitignore configuration."
            )
            continue

        if conflict_type == ConflictType.HUMAN_AUTHORED:
            result.unresolved.append(file_path)
            continue

        # Attempt auto-resolution
        try:
            ours, theirs = _read_conflict_sides(workspace_path, file_path)

            if conflict_type == ConflictType.OWNED_EVENT_LOG:
                resolved_content = _merge_event_logs(ours, theirs)
            else:
                # OWNED_METADATA: take-theirs
                resolved_content = theirs if theirs else ours

            _stage_resolved_file(workspace_path, file_path, resolved_content)
            result.resolved.append(file_path)

        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            result.errors.append(
                f"Failed to auto-resolve {file_path!r}: {exc}"
            )

    return result
