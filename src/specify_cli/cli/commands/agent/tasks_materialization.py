"""Frontmatter/file persistence and markdown-row mutation helpers.

WP03 (#2058): cohesive seam extracted from the ``tasks`` god-module. These
helpers persist status to disk (review-cycle artifacts, ``tasks.md`` rows) and
mutate markdown rows in the three supported task-row formats (checkbox,
pipe-table, inline ``Subtasks:`` references).

Import direction is one-way: this module may import from ``tasks_outline``
(seam↔seam is allowed) but MUST NOT import from ``tasks`` (the god-module that
re-exports these names back for existing call sites).
"""

from __future__ import annotations

from kernel._safe_re import re
from kernel.clock import now_utc_stamp
from mission_runtime import MissionArtifactKind, placement_seam
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.status import EVENTS_FILENAME, SNAPSHOT_FILENAME

if TYPE_CHECKING:
    # Type-only: ``kernel._safe_re``'s ``re`` has no statically-typed
    # ``Pattern`` attribute mypy can resolve as an annotation target (only
    # plain stdlib ``re`` supports ``re.Pattern[str]``). RE2-compiled patterns
    # are structurally identical to stdlib ``Pattern`` objects for the methods
    # this module calls (``.fullmatch``), so annotating against the stdlib
    # type is accurate, not a fiction.
    import re as _typing_re

# WP02 (#2058): the shared result vocabulary and the pipe-table row parsers
# live in the ``tasks_outline`` seam. Imported here so
# the materialization helpers keep their exact prior behavior.
from specify_cli.cli.commands.agent.tasks_outline import (
    TASKS_MD_FILENAME,
    TaskIdResolutionFormat,
    TaskIdResolutionOutcome,
    TaskIdResult,
    _is_pipe_table_task_row,
    _parse_pipe_table_header,
)

# FR-004 (kernel-clock-single-door WP03): defined once on the door
# (kernel.clock.UTC_SECOND_TIMESTAMP_FORMAT), imported above; call sites here
# are untouched (package remediation is WP12's job).


def _persist_review_artifact_override(
    artifact_path: Path,
    *,
    repo_root: Path,
    wp_id: str,
    actor: str,
    reason: str,
) -> None:
    """Record durable evidence that a rejected latest review was superseded.

    FR-009 (WP09): event-sourced. Rather than stamping the four
    ``review_artifact_override_*`` scalars onto the artifact frontmatter — and
    mirroring the identical scalars into the coord worktree so the merge gate
    would see them (the former ``_persist_review_artifact_override_in_coord``
    duplication) — emit a single, topology-resolved ``InnerStateChanged``
    ``review`` delta carrying a :class:`ReviewOverride` ``{at, actor, wp_id,
    reason}``. The reduced ``review`` snapshot slot is the single authority both
    the primary and coord worktrees resolve, so the primary/coord frontmatter
    mirror collapses to this one emit. Only the *storage* changes; the approval
    handler still fires the override at exactly the same moment.
    """
    from specify_cli.status import emit_inner_state_changed
    from specify_cli.status import ReviewOverride, WPInnerStateDelta

    # WP01 (#2959) partition-correct override write: the override annotation MUST
    # land on the SAME partition the merge review-artifact gate READS, or a
    # coord-topology mission that took a review rejection can never be merged (the
    # override is written to a surface the gate never consults — the deadlock).
    # That gate resolves each WP's lane state from its COORD ``STATUS_STATE`` home
    # (``post_merge/review_artifact_consistency.py`` → ``resolve_artifact_surface``),
    # so resolve the emit target through the kind-aware placement seam
    # (``STATUS_STATE``) — the SAME authority the gate consumes — rather than
    # deriving it from the PRIMARY artifact path (``artifact_path.parents[2]``,
    # which is the primary tasks/ tree). Review artifacts live at
    # ``<feature_dir>/tasks/<wp-slug>/review-cycle-N.md`` so ``parents[2].name`` is
    # the (partition-invariant) mission slug; the seam then routes the write to
    # the coord husk for a materialised coord topology and to the primary dir for
    # every other topology. ``emit_inner_state_changed`` stays partition-agnostic
    # (other callers depend on it); the reroute is at THIS caller only, mirroring
    # the proven per-leg pattern in ``tasks_dependency_graph.py:120-135``.
    # ``placement_seam(...).read_dir`` is typed ``-> Path`` but mypy widens it to
    # ``Any`` through the ``follow_imports=skip`` boundary on ``specify_cli.*``;
    # bind explicitly so the declared ``Path`` narrows back.
    mission_slug = artifact_path.parents[2].name
    feature_dir: Path = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.STATUS_STATE
    )
    timestamp = now_utc_stamp()
    override = ReviewOverride(at=timestamp, actor=actor, wp_id=wp_id, reason=reason)
    emit_inner_state_changed(
        feature_dir,
        wp_id,
        WPInnerStateDelta(review=override),
        actor=actor,
        mission_slug=mission_slug,
        at=timestamp,
        repo_root=repo_root,
    )


def _collect_status_artifacts(feature_dir: Path) -> list[Path]:
    """Return paths to all deterministic status artifacts that exist on disk.

    These files are generated by the emit pipeline (events.jsonl, status.json)
    and by task management (tasks.md).  Including them in a single commit
    alongside the WP file ensures the working tree stays clean after every
    ``move_task`` or ``workflow review`` transition.

    Args:
        feature_dir: Absolute path to the kitty-specs mission directory.

    Returns:
        List of existing artifact paths (may be empty).
    """
    candidates = [
        feature_dir / EVENTS_FILENAME,
        feature_dir / SNAPSHOT_FILENAME,
        feature_dir / TASKS_MD_FILENAME,
    ]
    return [p for p in candidates if p.exists()]


class WpSlugAmbiguous(ValueError):
    """Raised when ``tasks/`` carries multiple files matching the same task id
    to DIFFERENT resolved slugs (T057/US3 AC3): e.g. both ``WP01-foo.md`` and
    ``WP01_bar.md`` present. Refuse rather than silently pick the first
    ``iterdir()`` result — the divergence FR-007 exists to close.
    """


#: T057 (US3 AC1): the accepted separator set between a task id and the rest
#: of a ``tasks/`` filename's stem — hyphen, underscore, dot, or no separator
#: at all (an exact-stem match). Anchored immediately after the task id so a
#: task id that is a PREFIX of another (``WP1`` vs ``WP10``) never matches the
#: longer one's file: the char right after the task id, if any, must itself
#: be one of these three.
_WP_SLUG_SEPARATOR_CHARS = "-_."


def _wp_slug_pattern(task_id: str) -> _typing_re.Pattern[str]:
    """Build the T057 separator-anchored matcher for one task id.

    A file stem matches when it equals *task_id* exactly, or starts with
    *task_id* followed immediately by one of ``-``/``_``/``.``. This is the
    SINGLE place the accepted-separator rule is expressed — every other
    resolver in this mission consumes an already-resolved ``wp_slug`` string
    rather than re-implementing this matching rule locally (T057 step 4).
    """
    escaped = re.escape(task_id)
    separators = re.escape(_WP_SLUG_SEPARATOR_CHARS)
    # ``re.compile(...)`` (the RE2-backed ``kernel._safe_re`` module) resolves
    # as ``Any`` to mypy (see the ``TYPE_CHECKING`` import above); bind
    # explicitly so the declared ``Pattern[str]`` return narrows back from
    # ``Any`` rather than mypy flagging an implicit ``Any`` return.
    compiled: _typing_re.Pattern[str] = re.compile(rf"{escaped}(?:[{separators}].*)?")
    return compiled


def _wp_slug_candidates(tasks_dir: Path, task_id: str) -> list[str]:
    """Return every DISTINCT ``tasks/`` file stem matching *task_id* (T057)."""
    pattern = _wp_slug_pattern(task_id)
    return sorted(
        {
            str(p.stem)
            for p in tasks_dir.iterdir()
            if pattern.fullmatch(str(p.stem))
        }
    )


def _resolve_wp_slug(main_repo_root: Path, mission_slug: str, task_id: str) -> str:
    """Resolve the WP slug (e.g. 'WP01-some-title') from a task ID.

    Looks for a ``tasks/`` file whose stem equals *task_id* or starts with
    *task_id* followed by one of the accepted separators -- ``-``, ``_``,
    ``.``, or no separator at all (spec.md US3 AC1). Falls back to the bare
    *task_id* when no ``tasks/`` file matches. Raises :class:`WpSlugAmbiguous`
    (US3 AC3) when more than one ``tasks/`` file matches *task_id* to
    DIFFERENT slugs -- refusing rather than silently picking an arbitrary
    ``iterdir()`` order, which is exactly the divergence FR-007 closes.

    Exact-stem and hyphen-prefix matching stay byte-for-byte unchanged from
    the pre-T057 behaviour: every existing caller that only ever wrote
    ``WP01-slug.md`` files sees identical output.
    """
    # WP04 / FR-006: ``tasks/WP*.md`` is a WORK_PACKAGE_TASK (primary-partition)
    # artifact — author+read on PRIMARY (INV-5). Route the read through the
    # kind-aware seam so a coord-topology mission's stale ``-coord`` husk cannot
    # shadow the real primary WP files (#2062 read-side close).
    # ``placement_seam(...).read_dir`` is typed ``-> Path`` but mypy widens it to
    # ``Any`` through the ``follow_imports=skip`` boundary on ``specify_cli.*``;
    # bind explicitly so the join's return narrows back to ``Path``.
    mission_dir: Path = placement_seam(main_repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    tasks_dir = mission_dir / "tasks"
    if not tasks_dir.exists():
        return task_id
    candidates = _wp_slug_candidates(tasks_dir, task_id)
    if len(candidates) > 1:
        raise WpSlugAmbiguous(
            f"task id {task_id!r} matches multiple tasks/ files resolving to "
            f"different slugs: {', '.join(candidates)}. Rename so exactly one "
            "file matches this task id before retrying."
        )
    return candidates[0] if candidates else task_id


def _persist_review_feedback(
    *,
    main_repo_root: Path,
    mission_slug: str,
    task_id: str,
    feedback_source: Path,
    reviewer_agent: str = "unknown",
    affected_files: list[dict[str, str]] | None = None,
) -> tuple[Path, str]:
    """Persist review feedback through the shared review-cycle boundary.

    Returns the created artifact path and canonical ``review-cycle://`` URI.
    """
    from specify_cli.review.cycle import create_rejected_review_cycle

    wp_slug = _resolve_wp_slug(main_repo_root, mission_slug, task_id)
    cycle = create_rejected_review_cycle(
        main_repo_root=main_repo_root,
        mission_slug=mission_slug,
        wp_id=task_id,
        wp_slug=wp_slug,
        feedback_source=feedback_source,
        reviewer_agent=reviewer_agent,
        affected_files=affected_files,
    )
    return cycle.artifact_path, cycle.pointer


def _update_pipe_table_status(line: str, status: str, header_map: dict[str, int]) -> str:
    """Update the status marker in a pipe-table row without corrupting other columns.

    Strategy (in priority order):
    1. If a "status" column exists in *header_map* -> update only that cell.
    2. If a "parallel" column exists -> do NOT touch it; append a new status cell.
    3. If the last cell already looks like a status marker ([P]/[D]/[ ]/[x]) ->
       replace it in place.
    4. Otherwise -> append a new status cell.
    """
    # Split on '|'; cells[0] and cells[-1] are empty strings outside the row.
    cells = line.split("|")
    inner_cells = cells[1:-1]

    done_marker = " [D] "
    pending_marker = " [ ] "
    new_marker = done_marker if status == "done" else pending_marker

    status_col = header_map.get("status")
    parallel_col = header_map.get("parallel")

    if status_col is not None and status_col < len(inner_cells):
        # Update the designated status column only
        inner_cells[status_col] = new_marker
    elif parallel_col is not None:
        # Parallel column exists — do NOT corrupt it; append status instead
        inner_cells.append(new_marker)
    else:
        # No header guidance — check if the last cell looks like a status marker
        if inner_cells and re.match(r"\s*\[\s*[PDx ]\s*\]\s*$", inner_cells[-1]):
            inner_cells[-1] = new_marker
        else:
            inner_cells.append(new_marker)

    return "|" + "|".join(inner_cells) + "|"


def _resolve_checkbox(
    task_id: str,
    lines: list[str],
    status: str,
) -> TaskIdResult | None:
    """Resolve and mutate checkbox rows for *task_id*."""
    new_checkbox = "[x]" if status == "done" else "[ ]"
    found = False
    for i, line in enumerate(lines):
        if re.search(rf"-\s*\[[ x]\]\s*{re.escape(task_id)}\b", line, re.IGNORECASE):
            lines[i] = re.sub(r"-\s*\[[ x]\]", f"- {new_checkbox}", line)
            found = True
    if not found:
        return None
    return TaskIdResult(
        id=task_id,
        outcome=TaskIdResolutionOutcome.UPDATED,
        format=TaskIdResolutionFormat.CHECKBOX,
        message=f"Marked {task_id} as {status} (checkbox row updated).",
    )


def _resolve_pipe_table(
    task_id: str,
    lines: list[str],
    status: str,
) -> TaskIdResult | None:
    """Resolve and mutate pipe-table rows for *task_id*."""
    found = False
    for i, line in enumerate(lines):
        if _is_pipe_table_task_row(line, task_id):
            header_map = _parse_pipe_table_header(lines, i)
            lines[i] = _update_pipe_table_status(line, status, header_map)
            found = True
    if not found:
        return None
    return TaskIdResult(
        id=task_id,
        outcome=TaskIdResolutionOutcome.UPDATED,
        format=TaskIdResolutionFormat.PIPE_TABLE,
        message=f"Marked {task_id} as {status} (pipe-table row updated).",
    )
