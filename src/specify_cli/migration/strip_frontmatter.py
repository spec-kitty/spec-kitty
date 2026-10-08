"""Remove mutable status fields from all WP frontmatter.

Mutable fields (``lane``, ``review_status``, ``reviewed_by``,
``review_feedback``, ``progress``, ``shell_pid``, ``assignee``, ``agent``)
are runtime state that must not live in the immutable WP definition once the
canonical status event-log takes over.

IMPORTANT: This step records ``lane`` values *before* stripping them.  The
caller (or the orchestrating migration runner) must persist these lane records
for use by the state-rebuild step (WP13 / T065) **before** this function is
called — or use the ``lane_records`` returned in :class:`StripResult`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Fields that carry runtime mutable state and must be removed.
#
# WP03/FR-010 extension — the runtime-state eviction adds the remaining
# frontmatter-carried runtime fields to this set so a corpus strip removes them
# once the canonical event log is authoritative:
#   - ``shell_pid_created_at``: the PID-reuse baseline co-written with
#     ``shell_pid`` at claim time (now folded into the reduced-snapshot slot).
#   - the ``review_artifact_override_*`` quartet
#     (``review_artifact_override_{at,actor,wp_id,reason}``): the exact
#     frontmatter keys the write half in
#     ``cli.commands.agent.tasks_materialization._persist_review_artifact_override``
#     emits — enumerated concretely, never glob-guessed.
#   - ``reviewer_shell_pid``: the reviewer-side claim PID.
#   - ``history``: **moved out of STATIC_FIELDS and into here** (mirroring
#     ``progress``) so the stripper actually removes it. ``STATIC_FIELDS`` is a
#     documentation/allowlist only; the stripper is driven purely by
#     ``MUTABLE_FIELDS``, so a field left solely in ``STATIC_FIELDS`` is never
#     removed. Per FR-010 ``history[]`` is dead+mis-filed — this WP only
#     *reclassifies + strips* it; the outright deletion of the field and its
#     writer ``add_history_entry`` is WP07/T028 territory.
#
# ``progress`` (already a member below) is **retired** here per FR-010: it is
# kept in ``MUTABLE_FIELDS`` deliberately so the strip removes it — this is an
# explicit retirement, NOT a silent drop. See ``RETIRED_FIELDS`` below.
MUTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "lane",
        "review_status",
        "reviewed_by",
        "review_feedback",
        "progress",
        "shell_pid",
        "assignee",
        "agent",
        # WP03/FR-010 additions
        "shell_pid_created_at",
        "review_artifact_override_at",
        "review_artifact_override_actor",
        "review_artifact_override_wp_id",
        "review_artifact_override_reason",
        "reviewer_shell_pid",
        "history",
    }
)

#: Fields deliberately retired (not silently dropped) by the runtime-state
#: eviction. They remain in :data:`MUTABLE_FIELDS` so the corpus strip removes
#: them; this marker records that the removal is intentional and gives a reader
#: a single place to see *why* a once-live field is gone. ``history`` and
#: ``progress`` are the two dead fields (FR-010) — both proven zero-reader
#: before deletion (see ``backfill_runtime_state.assert_zero_readers``).
RETIRED_FIELDS: frozenset[str] = frozenset(
    {
        "progress",
        "history",
    }
)

# Fields that are part of the immutable WP definition and must be preserved.
# NOTE: ``history`` was removed from this set in WP03/FR-010 and moved into
# ``MUTABLE_FIELDS`` (the two moves are a pair) so the stripper removes it.
STATIC_FIELDS: frozenset[str] = frozenset(
    {
        "work_package_id",
        "wp_code",
        "mission_id",
        "title",
        "dependencies",
        "requirement_refs",
        "execution_mode",
        "owned_files",
        "authoritative_surface",
        "subtasks",
        "phase",
        "planning_base_branch",
        "merge_target_branch",
        "branch_strategy",
        "base_branch",
        "base_commit",
        "created_at",
    }
)


@dataclass
class StripResult:
    """Summary of a :func:`strip_mutable_fields` run.

    Attributes:
        wps_processed: Number of WP files processed.
        fields_stripped: Total number of field instances removed across all WPs.
        lane_records: Mapping of ``wp_code → lane`` recorded *before* stripping,
            so the lane values are available for state reconstruction in WP13.
        warnings: List of non-fatal warning messages.
    """

    wps_processed: int = 0
    fields_stripped: int = 0
    lane_records: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def strip_mutable_fields(feature_dir: Path) -> StripResult:
    """Remove mutable fields from all WP frontmatter in *feature_dir*.

    For each ``tasks/WP*.md`` file:

    1. Reads the current frontmatter.
    2. Records the ``lane`` value (if present) in :attr:`StripResult.lane_records`.
    3. Removes all keys listed in :data:`MUTABLE_FIELDS`.
    4. Writes back using :class:`~specify_cli.frontmatter.FrontmatterManager`
       (ruamel.yaml round-trip, body content preserved byte-for-byte).

    Also inspects the top-level ``tasks.md`` if it exists and strips any
    status-like blocks from its frontmatter.

    Args:
        feature_dir: Path to the feature directory (e.g. ``kitty-specs/057-…``).

    Returns:
        :class:`StripResult` with counts and the pre-strip lane records.
    """
    result = StripResult()
    tasks_dir = feature_dir / "tasks"

    if not tasks_dir.is_dir():
        logger.debug("No tasks/ directory in %s — skipping frontmatter strip", feature_dir.name)
        return result

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        # Derive wp_code for the lane_records key
        import re

        m = re.match(r"^(WP\d+)", wp_file.stem)
        wp_code = m.group(1) if m else wp_file.stem

        try:
            stripped_count = _strip_one_file(wp_file, feature_dir, lane_records=result.lane_records, lane_key=wp_code)
        except Exception as exc:
            msg = f"Cannot read {wp_file.name}: {exc} — skipping"
            logger.warning(msg)
            result.warnings.append(msg)
            continue

        if stripped_count > 0:
            logger.info(
                "Stripped %d mutable field(s) from %s",
                stripped_count,
                wp_file.name,
            )

        result.wps_processed += 1
        result.fields_stripped += stripped_count

    # Also strip frontmatter from tasks.md if it has status-like blocks
    tasks_md = feature_dir / "tasks.md"
    if tasks_md.exists():
        try:
            stripped_count = _strip_one_file(tasks_md, feature_dir)
            if stripped_count > 0:
                logger.info(
                    "Stripped %d mutable field(s) from tasks.md in %s",
                    stripped_count,
                    feature_dir.name,
                )
                result.fields_stripped += stripped_count
        except Exception as exc:
            # tasks.md may not have frontmatter at all — that's fine
            logger.debug("tasks.md in %s has no frontmatter or could not be read: %s", feature_dir.name, exc)

    return result


def _remove_mutable_fields(frontmatter: dict[str, Any]) -> int:
    """Delete every :data:`MUTABLE_FIELDS` key from *frontmatter* in place; return how many were removed."""
    present = [name for name in MUTABLE_FIELDS if name in frontmatter]
    for name in present:
        del frontmatter[name]
    return len(present)


def _strip_one_file(path: Path, feature_dir: Path, *, lane_records: dict[str, str] | None = None, lane_key: str = "") -> int:
    """Strip the mutable fields from *path* under the Mission write lock; return how many were removed.

    The frontmatter is read inside the lock, so a field another writer landed meanwhile is neither lost
    nor missed; the ``lane`` value is recorded from that same read, BEFORE the strip. Nothing is
    written when no mutable field is present.
    """
    from specify_cli.frontmatter import locked_update_frontmatter

    stripped = 0

    def _strip(frontmatter: dict[str, Any]) -> bool:
        nonlocal stripped
        if lane_records is not None and "lane" in frontmatter:
            lane_records[lane_key] = str(frontmatter["lane"])
        stripped = _remove_mutable_fields(frontmatter)
        return stripped > 0

    locked_update_frontmatter(path, _strip, feature_dir=feature_dir)
    return stripped
