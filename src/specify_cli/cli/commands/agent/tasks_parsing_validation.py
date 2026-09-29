"""Review-verdict and review-readiness validation, plus the issue-matrix re-export.

WP06 (#2058): cohesive seam extracted from the ``tasks`` god-module. These
helpers parse and validate review-side state: the latest review-cycle
verdict, the self-review fallback option guard, the stale/stalled review
status annotations, and the ``move-task → for_review/approved/done``
readiness validation.

The issue-matrix approval-blocker family (``_issue_matrix_approval_blocker``
and its helpers) moved to :mod:`specify_cli.tasks.issue_matrix_approval`
(#5222, F4) -- a domain home, since ``policy.merge_gates`` reuses the SAME
terminal-verdict rule and importing a private name from this CLI seam was a
policy -> CLI layer inversion. Re-exported here (self-import) so every
existing ``from ...tasks_parsing_validation import
_issue_matrix_approval_blocker`` call site (``tasks.py``,
``tasks_move_task.py``) is unaffected byte-for-byte.

Import direction is one-way (INV-2): this module may import from
``tasks_outline`` / ``tasks_materialization`` / ``tasks_dependency_graph``
(seam↔seam is allowed) but MUST
NOT import from ``tasks`` (the god-module re-exports these names back for
existing call sites).

Collaborators that live in ``tasks.py`` and that tests monkeypatch on the
``tasks`` namespace (``get_main_repo_root``, ``get_mission_type``,
``get_feature_target_branch``, ``resolve_workspace_for_wp``, and the
``tasks``-resident git helpers) are *injected* into
:func:`_validate_ready_for_review` by the thin ``tasks.py`` wrapper rather
than imported here. This keeps the existing patch contracts byte-for-byte
without re-importing the god-module.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from kernel.clock import UTC, datetime, now_utc, parse_iso
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from specify_cli.workspace.context import ResolvedWorkspace

from specify_cli.cli.commands._commit_recipes import safe_commit_recipe
from specify_cli.cli.commands.agent.tasks_dependency_graph import (
    _count_behind_commits_outside_planning_artifacts,
)
from specify_cli.core.constants import (
    KITTY_SPECS_DIR,
    MISSION_TYPE_RESEARCH,
    MISSION_TYPE_SOFTWARE_DEV,
)
from specify_cli.lanes._git import lane_has_commit_beyond_base
from specify_cli.status import (
    Lane,
    StatusEvent,
    event_sourced_review_result,
    is_changes_requested,
    to_artifact_verdict,
)
from specify_cli.status import is_dossier_snapshot as _is_dossier_snapshot

logger = logging.getLogger(__name__)

# Known verdict values from the review-cycle schema.
# Unknown values warn but do NOT block (backward compatibility).
_VALID_VERDICTS: frozenset[str] = frozenset({"approved", "approved_after_orchestrator_fix", "arbiter_override", "rejected"})

# ---------------------------------------------------------------------------
# Issue-matrix approval rule (#5222, F4): moved to a domain home under
# ``specify_cli.tasks`` so ``policy.merge_gates`` (which reuses this SAME
# terminal-verdict lever) imports a policy -> domain edge instead of reaching
# up into this CLI ``agent`` command tree for a private name. Re-exported
# here (self-import) so ``tasks.py`` / ``tasks_move_task.py`` -- and every
# other existing ``from ...tasks_parsing_validation import
# _issue_matrix_approval_blocker`` call site -- are unaffected byte-for-byte.
# See :mod:`specify_cli.tasks.issue_matrix_approval` for the implementation.
# ---------------------------------------------------------------------------
from specify_cli.tasks.issue_matrix_approval import (  # noqa: E402
    SPEC_MD_FILENAME as SPEC_MD_FILENAME,
    _issue_matrix_approval_blocker as _issue_matrix_approval_blocker,
    _issue_matrix_diagnostic_lines as _issue_matrix_diagnostic_lines,
    _issue_matrix_error_prefix as _issue_matrix_error_prefix,
    _issue_matrix_evaluation as _issue_matrix_evaluation,
    _issue_matrix_in_mission_rows as _issue_matrix_in_mission_rows,
    _issue_matrix_row_issues as _issue_matrix_row_issues,
)

# ---------------------------------------------------------------------------
# Self-review fallback option guard (verbatim move from tasks.py, WP06/T022)
# ---------------------------------------------------------------------------


def _self_review_fallback_option_error(
    *,
    enabled: bool,
    target_lane: str,
    force: bool,
    intended_reviewer: str | None,
    failure_reason: str | None,
) -> str | None:
    """Validate explicit self-review fallback metadata before approval."""
    from specify_cli.status import resolve_lane_alias

    if not enabled:
        if intended_reviewer or failure_reason:
            return "--intended-reviewer/--reviewer-failure-reason require --self-review-fallback."
        return None

    if resolve_lane_alias(target_lane) not in (Lane.APPROVED, Lane.DONE):
        return "--self-review-fallback is only valid when approving or marking done."
    if not force:
        return "--self-review-fallback requires --force so force_count records the independence override."
    if not (intended_reviewer or "").strip():
        return "--self-review-fallback requires --intended-reviewer <agent>."
    if not (failure_reason or "").strip():
        return "--self-review-fallback requires --reviewer-failure-reason <reason>."
    return None


# ---------------------------------------------------------------------------
# Review-cycle verdict + status-flag helpers (verbatim move, WP06/T022)
# ---------------------------------------------------------------------------
#
# WP05 (verdict-seam-write-unification-01KZ9Q35, FR-003) retired
# ``_get_latest_review_cycle_verdict`` (the frontmatter verdict reader) along
# with its two now-dead private helpers, ``_review_cycle_number`` (the
# review-cycle-filename sort key) and ``_review_artifact_dir_for_wp`` (the
# tasks_dir-anchored artifact-dir resolver) -- neither has any remaining
# caller anywhere in this repository once the verdict reader they existed to
# support is gone.


def _latest_status_event_time(events: list[StatusEvent], wp_id: str) -> datetime | None:
    """Return the latest parsed event time for a WP."""
    latest: datetime | None = None
    for event in events:
        if event.wp_id != wp_id or not event.at:
            continue
        try:
            parsed = parse_iso(event.at)
        except ValueError:
            continue
        parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _apply_wp_review_verdict_flag(
    wp: dict[str, object],
    *,
    wp_id: str,
    feature_dir: Path,
    stale_verdicts: list[dict[str, object]],
) -> None:
    """Annotate a single terminal-lane WP row with its event-sourced verdict
    (FR-004/T024 -- repointed off ``review-cycle-N.md`` frontmatter onto
    :func:`~specify_cli.status.event_sourced_review_result`, the WP05 collapse).

    T064/FR-012: a damaged event-log ``review_result`` slot is folded into the
    SAME ``stale_verdicts`` channel this module already returns (a
    ``"damaged": True`` entry), rather than a new return slot -- this keeps
    the 2-tuple return shape callers outside this WP's owned surface
    (``tasks_status_cmd.py``) already unpack unchanged. **Absent** (no slot at
    all -- an un-migrated mission, or a WP that never exited ``in_review``) is
    NOT damage and raises no warning at all (mirrors the retired reader's
    "no artifact yet" case).
    """
    lookup = event_sourced_review_result(feature_dir, wp_id)
    if not lookup.slot_present:
        return
    if lookup.result is None:
        # refuse (FR-012): the event log recorded a verdict transition for
        # this WP but the ``review_result`` slot itself is damaged/malformed
        # -- distinguishable from "no verdict at all" purely by
        # ``slot_present``.
        damaged_warning: dict[str, object] = {
            "wp_id": wp_id,
            "artifact": None,
            "verdict": None,
            "damaged": True,
        }
        stale_verdicts.append(damaged_warning)
        wp["_damaged_verdict"] = True
        wp["damaged_review_artifact"] = damaged_warning
        return
    if is_changes_requested(lookup.result.verdict):
        stale_warning: dict[str, object] = {
            "wp_id": wp_id,
            "artifact": lookup.result.reference,
            "verdict": to_artifact_verdict(lookup.result.verdict),
        }
        stale_verdicts.append(stale_warning)
        wp["_stale_verdict"] = True
        wp["stale_review_artifact"] = stale_warning


def _apply_review_status_flags(
    work_packages: list[dict[str, object]],
    *,
    feature_dir: Path,
    events: list[StatusEvent],
    stall_threshold_minutes: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Annotate status rows with stale verdict, damaged verdict, and
    stalled-review warnings.

    ``feature_dir`` is the STATUS_STATE-authoritative mission dir (the event
    log's home) -- WP05 (verdict-seam-write-unification-01KZ9Q35) repointed
    this off a ``tasks_dir``-anchored ``review-cycle-N.md`` frontmatter glob
    (:func:`_apply_wp_review_verdict_flag`).
    """
    stale_verdicts: list[dict[str, object]] = []
    stalled_wps: list[dict[str, object]] = []
    now = now_utc()

    for wp in work_packages:
        wp_id = wp.get("id")
        if not isinstance(wp_id, str) or not wp_id:
            continue

        lane = wp.get("lane")
        if lane in (Lane.APPROVED, Lane.DONE):
            _apply_wp_review_verdict_flag(wp, wp_id=wp_id, feature_dir=feature_dir, stale_verdicts=stale_verdicts)

        if lane == Lane.IN_REVIEW:
            last_event_time = _latest_status_event_time(events, wp_id)
            if last_event_time is None:
                continue
            age_minutes = int((now - last_event_time).total_seconds() / 60)
            if age_minutes > stall_threshold_minutes:
                stall_label = f"STALLED — no move-task in {age_minutes}m"
                stall_warning: dict[str, object] = {
                    "wp_id": wp_id,
                    "age_minutes": age_minutes,
                    "threshold_minutes": stall_threshold_minutes,
                }
                stalled_wps.append(stall_warning)
                wp["_stall_label"] = stall_label
                wp["review_stall"] = stall_warning

    return stale_verdicts, stalled_wps


# ---------------------------------------------------------------------------
# Review-readiness validation (WP06/T023): the ~348-LOC god-function
# ``_validate_ready_for_review`` decomposed into named, behavior-preserving
# sub-validators, each maxCC <= 15. Validation order, every gate, every error
# string, and the (bool, list[str]) return shape are preserved exactly.
# ---------------------------------------------------------------------------


class _ConsoleLike(Protocol):
    # Positional ``print`` only — the validators render with
    # ``console.print(message)`` and never pass keyword options. A ``**kwargs``
    # protocol method is structurally UNsatisfiable by ``rich.console.Console``
    # (whose ``print`` exposes named keyword options, not ``**kwargs``), so the
    # narrow positional shape is what lets the real ``Console`` conform.
    def print(self, *values: object) -> None: ...


def _attribute_blocking_entry(paths: tuple[str, ...], wp_id: str, mission_slug: str, blocking_set: set[str]) -> str:
    """Return the honest attribution phrase for one blocking dirty entry.

    *paths* is a single-element tuple for an ordinary add/modify/delete
    porcelain line, or the ``(old, new)`` pair for a rename-form line
    (PR-FRESH-001) -- checked in that order so a rename into the moving WP's
    own directory is still reported as ``owned by {wp_id}`` even when the
    *old* side belongs to someone else, never hiding that the moving WP
    itself owns a side of the entry.

    *blocking_set* is the same blocking-path set ``classify_dirty_paths``
    already computed for this call (PR-FRESH2-001): ownership is derived
    ONLY from the side(s) that are themselves members of that set, never
    from a side ``_is_benign`` already exempted. Without this filter, a
    benign-exempted side (self-bookkeeping churn such as ``meta.json``, or
    any WP's flat ``tasks/WPxx-*.md`` task file) that merely happens to sit
    under the moving WP's own directory could resolve to ``wp_id`` via
    ``owning_wp_for_path`` alone and mislabel an entry that actually blocks
    for a wholly different (genuinely unattributable) reason — diverging
    from ``classify_dirty_paths``'s own blocking/benign partition, exactly
    what spec.md's Key Entities section forbids.

    FR-001/002/003 already route any path owned by a *different* WP into
    ``benign`` (see dirty_classifier.classify_dirty_paths), so a blocking
    entry's determined owner, for each blocking-side path, is always either
    the moving WP itself (its own residue) or "not attributable" — never a
    different, specific WP. See spec.md FR-005 / User Story 2.
    """
    from specify_cli.review.dirty_classifier import owning_wp_for_path

    for path in paths:
        if path not in blocking_set:
            continue
        if owning_wp_for_path(path, mission_slug) == wp_id:
            return f"owned by {wp_id}"
    return "not attributable to a specific work package"


def _validate_research_artifacts(
    *,
    main_repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    mission_type: str,
    target_lane: str,
    console: _ConsoleLike,
) -> list[str] | None:
    """Check 1: uncommitted planning artifacts in the planning repo (all missions).

    Returns ``None`` when this gate passes (no blocking dirty files), otherwise
    a populated ``guidance`` list that the caller returns as the failure result.
    Mutates nothing outside its local ``guidance`` accumulator.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", str(feature_dir)], cwd=main_repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    uncommitted_in_main = result.stdout.rstrip()
    if not uncommitted_in_main:
        return None

    # Use the dirty classifier to partition paths into blocking vs. benign.
    # Benign paths (status artifacts, other WPs' task files, metadata) are
    # expected during concurrent multi-agent work and must NOT block handoff.
    from specify_cli.review.dirty_classifier import classify_dirty_paths

    # Each entry pairs one raw porcelain line with the path(s) it names.
    # A rename entry (PR-FRESH-001) reports as ONE composite line,
    # "old -> new" -- git's own convention for a staged/detected rename --
    # and must be judged on BOTH paths: it blocks if EITHER side would
    # block for the moving WP, and is benign only when BOTH sides are.
    # Splitting here, before either path string ever reaches the
    # classifier, keeps a rename from ever presenting a composite string to
    # a single-path classifier/regex.
    entries: list[tuple[str, tuple[str, ...]]] = []
    for line in uncommitted_in_main.split("\n"):
        if not line.strip():
            continue
        # git status --porcelain format: "XY path" (first 3 chars are status)
        file_part = line[3:] if len(line) > 3 else line.strip()
        # EXCLUDE policy (C-006): dossier snapshot writes are derived,
        # ephemeral, and recomputable; they must never self-block a
        # transition. Drop them before classification so they cannot
        # leak into the blocking bucket via a path that bypasses
        # ``.gitignore``.
        if _is_dossier_snapshot(file_part):
            continue
        if " -> " in file_part:
            old_path, new_path = file_part.split(" -> ", 1)
            paths: tuple[str, ...] = (old_path, new_path)
        else:
            paths = (file_part,)
        entries.append((line, paths))

    flat_paths = [path for _line, paths in entries for path in paths]
    blocking, _benign = classify_dirty_paths(
        dirty_paths=flat_paths,
        wp_id=wp_id,
        mission_slug=mission_slug,
    )
    blocking_set = set(blocking)
    blocking_entries = [(line, paths) for line, paths in entries if blocking_set & set(paths)]

    if len(entries) > len(blocking_entries):
        # Log info only — benign dirty files/entries do not block review handoff
        benign_entry_count = len(entries) - len(blocking_entries)
        console.print(f"[dim]Note: {benign_entry_count} unrelated dirty file(s) ignored (not owned by {wp_id})[/dim]")

    if not blocking_entries:
        return None

    guidance: list[str] = []
    guidance.append(f"Blocking: {len(blocking_entries)} uncommitted file(s):")
    guidance.append("")
    guidance.append("Modified files in kitty-specs/:")
    for line, paths in blocking_entries[:5]:
        attribution = _attribute_blocking_entry(paths, wp_id, mission_slug, blocking_set)
        guidance.append(f"  {line} ({attribution})")
    if len(blocking_entries) > 5:
        guidance.append(f"  ... and {len(blocking_entries) - 5} more")
    guidance.append("")
    guidance.append(f"Commit these files before moving to {target_lane}.")
    guidance.append(f"  cd {main_repo_root}")
    _research_message = f"research({wp_id}): <describe your research outputs>"
    _docs_message = f"docs({wp_id}): <describe your changes>"
    _commit_message = _research_message if mission_type == MISSION_TYPE_RESEARCH else _docs_message
    # FR-018 (WP03 review cycle 1, #1): name --to-branch, resolved from
    # main_repo_root's own checked-out branch (the planning-artifact
    # destination) -- one extra git call on this error-guidance path is
    # acceptable.
    from specify_cli.core.git_ops import get_current_branch as _get_branch_for_research

    _research_branch = _get_branch_for_research(main_repo_root)
    guidance.append(f"  {safe_commit_recipe([f'kitty-specs/{mission_slug}/'], _commit_message, _research_branch)}")
    guidance.append("")
    guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
    return guidance


def _resolve_worktree_path(
    *,
    main_repo_root: Path,
    mission_slug: str,
    workspace: ResolvedWorkspace | None,
) -> Path:
    """Return the lane worktree path, reproducing the legacy lane-a fallback."""
    if workspace is None:
        from specify_cli.lanes.branch_naming import worktree_path as _seam_worktree_path

        # Lane naming is keyed on the creation input alone (WP07, FR-002/PD-1);
        # ``Path(...)`` is a narrow coercion: the cross-module ``specify_cli.*``
        # imports are ``follow_imports = skip`` under mypy --strict, so the
        # seam's already-``Path`` return is otherwise inferred as ``Any``.
        return Path(_seam_worktree_path(main_repo_root, mission_slug, lane_id="lane-a"))
    return Path(workspace.worktree_path)


def _check_worktree_health(worktree_path: Path, wp_id: str, target_lane: str) -> list[str] | None:
    """Husk / toplevel / detached-HEAD / in-progress-operation guards.

    Returns ``None`` when the worktree is healthy, otherwise a populated
    ``guidance`` list. Order is load-bearing (#1833): the ``.git``-marker check
    runs BEFORE any git invocation so a husk directory never causes git to walk
    up into the primary repo.
    """
    from specify_cli.workspace.context import husk_resolution_error, verify_workspace_toplevel

    guidance: list[str] = []
    if not (worktree_path / ".git").exists():
        guidance.append(str(husk_resolution_error(worktree_path)))
        return guidance

    # Last-line defense (R4): the resolved path must be the toplevel
    # of its own working tree before any other git call runs there.
    toplevel_error = verify_workspace_toplevel(worktree_path)
    if toplevel_error is not None:
        guidance.append(str(toplevel_error))
        return guidance

    # Check for detached HEAD before other git status checks
    from specify_cli.core.git_ops import get_current_branch as _get_branch

    wt_branch = _get_branch(worktree_path)
    if wt_branch is None:
        guidance.append("Detached HEAD detected in worktree!")
        guidance.append("")
        guidance.append("Please reattach to a branch before review:")
        guidance.append(f"  cd {worktree_path}")
        guidance.append("  git checkout <your-branch>")
        guidance.append("")
        guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
        return guidance

    # Check for in-progress git operations (merge/rebase/cherry-pick)
    in_progress = []
    state_checks = {
        "MERGE_HEAD": "merge",
        "REBASE_HEAD": "rebase",
        "CHERRY_PICK_HEAD": "cherry-pick",
    }
    for ref, label in state_checks.items():
        state_result = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", ref], cwd=worktree_path, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        if state_result.returncode == 0:
            in_progress.append(label)

    if in_progress:
        guidance.append("In-progress git operation detected in worktree!")
        guidance.append("")
        guidance.append(f"Active operation(s): {', '.join(in_progress)}")
        guidance.append("")
        guidance.append("Resolve or abort before review:")
        guidance.append(f"  cd {worktree_path}")
        guidance.append("  git status")
        guidance.append("  git merge --abort   # if merge")
        guidance.append("  git rebase --abort  # if rebase")
        guidance.append("  git cherry-pick --abort  # if cherry-pick")
        guidance.append("")
        guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
        return guidance

    return None


def _check_branch_currency(
    *,
    worktree_path: Path,
    check_branch: str,
    mission_slug: str,
    wp_id: str,
    target_lane: str,
    behind_commits_touch_only_planning_artifacts: Callable[[Path, str, str], bool],
) -> list[str] | None:
    """Block when the lane worktree is behind its base by non-planning commits."""
    result = subprocess.run(
        ["git", "rev-list", "--count", f"HEAD..{check_branch}"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    behind_count = 0
    if result.returncode == 0 and result.stdout.strip():
        try:
            behind_count = int(result.stdout.strip())
        except ValueError:
            behind_count = 0

    # Allow status/planning-only commits to avoid repeated rebase friction.
    if behind_count > 0 and not behind_commits_touch_only_planning_artifacts(
        worktree_path,
        check_branch,
        mission_slug,
    ):
        # #3940: report source divergence, not the raw commit count — the
        # behind set on a missions-family branch is dominated by orchestrator
        # ledger commits (kitty-specs/ + .kittify/) that are not divergence.
        non_ledger_count = _count_behind_commits_outside_planning_artifacts(
            worktree_path,
            check_branch,
            behind_count,
        )
        guidance: list[str] = []
        guidance.append(f"{check_branch} branch has new commits not in this worktree!")
        guidance.append("")
        guidance.append(
            f"Your branch is behind {check_branch} by {behind_count} commit(s) "
            f"({non_ledger_count} non-ledger commit(s) touching files outside "
            "kitty-specs/ and .kittify/)."
        )
        guidance.append("Rebase before review:")
        guidance.append(f"  cd {worktree_path}")
        guidance.append(f"  git rebase {check_branch}")
        guidance.append("")
        guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
        return guidance
    return None


def _check_uncommitted_worktree_changes(
    *,
    worktree_path: Path,
    wp_id: str,
    target_lane: str,
    filter_runtime_state_paths: Callable[[str], str],
) -> list[str] | None:
    """Block when the worktree has genuine uncommitted implementation work."""
    result = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    # FR-015 / C-003: strip spec-kitty's own runtime-state files (e.g.
    # .spec-kitty/review-lock.json written by the review tooling, or
    # .kittify/ merge metadata) before deciding whether the worktree
    # has genuine uncommitted implementation work. The deny-list is a
    # fixed, named tuple (no patterns) so paths outside it still reach
    # the blocking branch and surface as "Uncommitted implementation
    # changes in worktree!" (C-004).
    uncommitted_in_worktree = filter_runtime_state_paths(result.stdout.strip())
    if not uncommitted_in_worktree:
        return None

    staged_lines = []
    unstaged_lines = []
    for line in uncommitted_in_worktree.split("\n"):
        if not line.strip():
            continue
        if line.startswith("??"):
            unstaged_lines.append(line)
            continue
        status = line[:2]
        if status[0] != " ":
            staged_lines.append(line)
        if status[1] != " ":
            unstaged_lines.append(line)

    guidance: list[str] = []
    if staged_lines and not unstaged_lines:
        guidance.append("Staged but uncommitted changes in worktree!")
    elif staged_lines and unstaged_lines:
        guidance.append("Staged and unstaged changes in worktree!")
    else:
        guidance.append("Uncommitted implementation changes in worktree!")
    guidance.append("")
    guidance.append("Modified files:")
    for line in uncommitted_in_worktree.split("\n")[:5]:
        guidance.append(f"  {line}")
    guidance.append("")
    guidance.append("Commit your work first:")
    guidance.append(f"  cd {worktree_path}")
    # FR-018 (WP03 review cycle 1, #1): name --to-branch, resolved from
    # worktree_path's own checked-out branch.
    from specify_cli.core.git_ops import get_current_branch as _get_branch_for_deliverable

    _deliverable_branch = _get_branch_for_deliverable(worktree_path)
    _deliverable_recipe = safe_commit_recipe(
        ["<deliverable-path-1>", "<deliverable-path-2>", "..."], f"feat({wp_id}): <describe implementation>", _deliverable_branch
    )
    guidance.append(f"  {_deliverable_recipe}")
    guidance.append("")
    guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
    return guidance


def _check_implementation_commit_present(
    *,
    worktree_path: Path,
    check_branch: str,
    wp_id: str,
    target_lane: str,
) -> list[str] | None:
    """Block when the lane branch has no commit beyond its base."""
    # Check if branch has commits beyond base (use actual base, not target).
    # Shared with the orchestrator-api for_review gate so both enforce the
    # same "an implementation commit exists" rule.
    if lane_has_commit_beyond_base(worktree_path, check_branch):
        return None

    guidance: list[str] = []
    guidance.append("No implementation commits on lane branch!")
    guidance.append("")
    guidance.append(f"The worktree exists but has no commits beyond {check_branch}.")
    guidance.append("Either:")
    guidance.append("  1. Commit your implementation work to the worktree")
    guidance.append("  2. Or verify work is complete (use --force if nothing to commit)")
    guidance.append("")
    guidance.append(f"  cd {worktree_path}")
    # FR-018 (WP03 review cycle 1, #1): name --to-branch, resolved from
    # worktree_path's own checked-out branch.
    from specify_cli.core.git_ops import get_current_branch as _get_branch_for_commit_present

    _no_commit_branch = _get_branch_for_commit_present(worktree_path)
    _deliverable_recipe = safe_commit_recipe(
        ["<deliverable-path-1>", "<deliverable-path-2>", "..."], f"feat({wp_id}): <describe implementation>", _no_commit_branch
    )
    guidance.append(f"  {_deliverable_recipe}")
    guidance.append("")
    guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
    return guidance


def _resolve_planning_branch_for_lane_guard(feature_dir: Path) -> str | None:
    """Resolve the planning branch the lane kitty-specs guard measures against.

    FR-009 / FR-010: reads the planning branch from meta.json — ``planning_base_
    branch`` with precedence, else the meta ``target_branch`` (routed through the
    single ``read_target_branch_from_meta`` authority per FR-008 / #2139). Returns
    ``None`` for legacy missions without meta.json so callers fall back to the
    lane base ref.

    #3271: this ref is now the guard's DELTA base, not just the error-message
    hint. In coord topology a lane legitimately inherits prior missions' committed
    ``kitty-specs/**`` from the base and — via the recorded planning-commit merge
    (ADR 2026-07-29-1 / #2993) — this mission's own planning artifacts. Both are
    ancestors of the planning branch, so diffing the lane against it yields an
    empty delta for that inherited content while still flagging genuine lane-
    authored ``kitty-specs`` edits. The lane's coordination/mission base ref
    (``check_branch``), by contrast, predates the inherited content and produced a
    false positive on every transition.
    """
    try:
        # FR-007 route: this site was INVISIBLE to the WP07 census, whose raw
        # ``grep "load_meta("`` cannot see an aliased import. Routed onto the
        # one fail-closed reader like every other divergent wrapper. The broad
        # catch below is retained deliberately: it guards the two imports and
        # BOTH readers (pre-existing best-effort contract -- the lane guard must
        # still report contamination when the optional planning-branch metadata
        # is unavailable).
        from specify_cli.core.paths import load_meta_fail_closed as _load_meta_lggrd
        from specify_cli.core.paths import read_target_branch_from_meta as _read_target_branch_lggrd

        _meta = _load_meta_lggrd(feature_dir)
        if _meta:
            _planning = _meta.get("planning_base_branch")
            if isinstance(_planning, str) and _planning:
                return _planning
            _target: str | None = _read_target_branch_lggrd(feature_dir)
            return _target
    except Exception as _lane_meta_exc:  # noqa: BLE001 - lane guard still reports contamination without optional metadata
        logger.debug("Could not resolve planning_base_branch for lane guard: %s", _lane_meta_exc)
    return None


def _check_kitty_specs_contamination(
    *,
    worktree_path: Path,
    check_branch: str,
    feature_dir: Path,
    wp_id: str,
    target_lane: str,
    list_wp_branch_specs_changes_for_guard: Callable[..., list[str]],
) -> list[str] | None:
    """Block when kitty-specs/ files were committed on the lane branch."""
    # #3271: measure the lane-hygiene delta against the PLANNING branch, not the
    # lane's coordination/mission base ref (``check_branch``). See
    # ``_resolve_planning_branch_for_lane_guard`` for why — inherited base content
    # and the #2993-merged planning artifacts are ancestors of the planning
    # branch, so they no longer false-positive. Legacy missions without meta.json
    # fall back to ``check_branch`` (unchanged behaviour for the flat/legacy case).
    _planning_branch = _resolve_planning_branch_for_lane_guard(feature_dir)
    _guard_base = _planning_branch or check_branch
    contamination_files = list_wp_branch_specs_changes_for_guard(
        worktree_path=worktree_path,
        base_branch=_guard_base,
    )
    if not contamination_files:
        return None

    guidance: list[str] = []
    guidance.append("Committed kitty-specs files on this lane branch:")
    for path in contamination_files[:5]:
        guidance.append(f"  {path}")
    if len(contamination_files) > 5:
        guidance.append(f"  ... and {len(contamination_files) - 5} more")
    guidance.append("")
    if _planning_branch:
        _first_planning_path = contamination_files[0] if contamination_files else f"{KITTY_SPECS_DIR}/<path-to-file>"
        guidance.append(
            f"{KITTY_SPECS_DIR}/ changes are not allowed on lane branches.\n"
            f"Planning artifacts must live on: {_planning_branch}\n\n"
            f"To verify a file exists on the planning branch:\n"
            f"  git show {_planning_branch}:{_first_planning_path}"
        )
    else:
        guidance.append(f"{KITTY_SPECS_DIR}/ changes are not allowed on lane branches (planning branch unknown — check {KITTY_SPECS_DIR}/ on the base branch).")
    guidance.append("")
    guidance.append(f"Clean the branch before moving to {target_lane}:")
    guidance.append(f"  cd {worktree_path}")
    guidance.append(f"  git restore --source {_guard_base} --staged --worktree -- {KITTY_SPECS_DIR}/")
    # FR-018 (WP03 review cycle 1, #1): --to-branch must name worktree_path's
    # OWN checked-out branch, resolved here with one extra git call -- never
    # check_branch/_guard_base, which is the comparison BASE this lane
    # diverges from, not the destination the commit must land on. Naming
    # check_branch would print a recipe safe-commit's own HEAD-match guard
    # then refuses to run.
    from specify_cli.core.git_ops import get_current_branch as _get_branch_for_cleanup

    _cleanup_branch = _get_branch_for_cleanup(worktree_path)
    _cleanup_recipe = safe_commit_recipe([f"{KITTY_SPECS_DIR}/"], "chore: remove planning artifacts from lane branch", _cleanup_branch)
    guidance.append(f"  {_cleanup_recipe}")
    guidance.append("")
    guidance.append(f"Then retry: spec-kitty agent tasks move-task {wp_id} --to {target_lane}")
    return guidance


def _validate_repo_root_workspace(
    *,
    workspace: ResolvedWorkspace,
    workspace_override: ResolvedWorkspace | None,
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
    target_lane: str,
) -> tuple[bool, list[str]]:
    """Readiness verdict for a WP that runs in the repository-root checkout.

    A branchless planning_artifact WP (and an owned checkout, which has its own
    implementation guard) keeps the historic short-circuit. A repo-root WP that
    owns a real branch (single_branch code WP) has no worktree to inspect, so
    the shared claim-base ``for_review`` gate (:mod:`specify_cli.lanes.for_review_gate`,
    the same one ``agent status emit`` and the orchestrator use) decides.
    """
    if workspace_override is not None or str(getattr(target_lane, "value", target_lane)) != "for_review" or getattr(workspace, "branch_name", None) is None:
        return True, []

    from specify_cli.lanes.for_review_gate import evaluate_for_review_gate

    decision = evaluate_for_review_gate(main_repo_root, mission_slug, wp_id)
    if decision.passed:
        return True, []
    return False, [decision.reason]


def _validate_worktree_state(
    *,
    repo_root: Path,
    main_repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    target_lane: str,
    resolve_workspace_for_wp: Callable[[Path, str, str], ResolvedWorkspace],
    get_feature_target_branch: Callable[[Path, str], str],
    review_currency_check_branch: Callable[..., str],
    behind_commits_touch_only_planning_artifacts: Callable[[Path, str, str], bool],
    filter_runtime_state_paths: Callable[[str], str],
    list_wp_branch_specs_changes_for_guard: Callable[..., list[str]],
    workspace_override: ResolvedWorkspace | None = None,
    review_base_ref: str | None = None,
    check_kitty_specs: bool = True,
) -> tuple[bool, list[str]] | None:
    """Check 2 (software-dev): worktree currency + commit gates.

    Returns ``None`` to signal "fall through to the final success result"
    (e.g. planning-artifact repo_root WP, or the worktree does not exist).
    Returns ``(True, [])`` for the early repo_root short-circuit, and
    ``(False, guidance)`` for any blocking gate.
    """
    # Planning-artifact WPs run in the repo root and have no separate worktree
    # to validate. We only short-circuit on planning-artifact mode when the
    # canonical resolver succeeds; if the WP has no on-disk markdown file (e.g.
    # in tests that mock surrounding state), fall through to the legacy
    # worktree-existence checks below rather than hard-failing.
    workspace: ResolvedWorkspace | None
    if workspace_override is not None:
        workspace = workspace_override
    else:
        try:
            workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id)
        except (ValueError, FileNotFoundError):
            workspace = None

    if workspace is not None and workspace.resolution_kind == "repo_root":
        return _validate_repo_root_workspace(
            workspace=workspace,
            workspace_override=workspace_override,
            main_repo_root=main_repo_root,
            mission_slug=mission_slug,
            wp_id=wp_id,
            target_lane=target_lane,
        )

    worktree_path = _resolve_worktree_path(
        main_repo_root=main_repo_root,
        mission_slug=mission_slug,
        workspace=workspace,
    )

    if not worktree_path.exists():
        return None

    health = _check_worktree_health(worktree_path, wp_id, target_lane)
    if health is not None:
        return False, health

    # Check if the lane worktree is behind the branch it is expected to
    # track. In the lane-only model this is usually the mission branch.
    target_branch = get_feature_target_branch(repo_root, mission_slug)

    check_branch = review_base_ref or review_currency_check_branch(
        main_repo_root=main_repo_root,
        mission_slug=mission_slug,
        target_branch=target_branch,
        workspace=workspace,
    )

    currency = _check_branch_currency(
        worktree_path=worktree_path,
        check_branch=check_branch,
        mission_slug=mission_slug,
        wp_id=wp_id,
        target_lane=target_lane,
        behind_commits_touch_only_planning_artifacts=behind_commits_touch_only_planning_artifacts,
    )
    if currency is not None:
        return False, currency

    uncommitted = _check_uncommitted_worktree_changes(
        worktree_path=worktree_path,
        wp_id=wp_id,
        target_lane=target_lane,
        filter_runtime_state_paths=filter_runtime_state_paths,
    )
    if uncommitted is not None:
        return False, uncommitted

    no_commit = _check_implementation_commit_present(
        worktree_path=worktree_path,
        check_branch=check_branch,
        wp_id=wp_id,
        target_lane=target_lane,
    )
    if no_commit is not None:
        return False, no_commit

    if check_kitty_specs:
        contamination = _check_kitty_specs_contamination(
            worktree_path=worktree_path,
            check_branch=check_branch,
            feature_dir=feature_dir,
            wp_id=wp_id,
            target_lane=target_lane,
            list_wp_branch_specs_changes_for_guard=list_wp_branch_specs_changes_for_guard,
        )
        if contamination is not None:
            return False, contamination

    return None


def _validate_ready_for_review(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    force: bool,
    target_lane: str = "for_review",
    *,
    effective_root: Path | None = None,
    workspace_override: ResolvedWorkspace | None = None,
    review_base_ref: str | None = None,
    check_kitty_specs: bool = True,
    get_main_repo_root: Callable[[Path], Path],
    get_mission_type: Callable[[Path], str],
    get_feature_target_branch: Callable[[Path, str], str],
    resolve_workspace_for_wp: Callable[[Path, str, str], ResolvedWorkspace],
    review_currency_check_branch: Callable[..., str],
    behind_commits_touch_only_planning_artifacts: Callable[[Path, str, str], bool],
    filter_runtime_state_paths: Callable[[str], str],
    list_wp_branch_specs_changes_for_guard: Callable[..., list[str]],
    console: _ConsoleLike,
) -> tuple[bool, list[str]]:
    """Validate that WP is ready for review by checking for uncommitted changes.

    For research missions: Checks for uncommitted research artifacts in planning repo.
    For software-dev missions: Checks for uncommitted changes in worktree AND
    verifies at least one implementation commit exists.

    The ``tasks``-resident collaborators are injected so that the existing
    monkeypatch contracts on the ``tasks`` namespace continue to apply; the
    thin ``tasks.py`` wrapper binds them to its live (patchable) globals.

    Args:
        repo_root: Repository root path (could be main or worktree)
        mission_slug: Feature slug (e.g., "010-lane-only-runtime")
        wp_id: Work package ID (e.g., "WP01")
        force: If True, skip validation (return success)
        target_lane: Lane the caller is transitioning to. Used to parameterize
            the retry hints emitted in guidance messages (FR-015) so reviewers
            transitioning to ``approved``/``planned`` see the correct retry
            command instead of a hard-coded ``for_review`` string.

    Returns:
        Tuple of (is_valid, guidance_messages)
        - is_valid: True if ready for review, False if blocked
        - guidance_messages: List of actionable instructions if blocked
    """
    if force:
        return True, []

    # Write path: keep main-repo-root resolution so canonical serialization
    # pins to the primary checkout regardless of where the operator stands.
    main_repo_root = get_main_repo_root(repo_root)
    # WP06 / FR-006 / T027: route research-artifact read to PRIMARY-partition seam.
    # research.md / meta.json / spec.md all live on PRIMARY (not the coord husk).
    # resolve_feature_dir_for_mission (coord-aware) would return the STATUS-only
    # coord husk for coord-topology missions, where these planning artifacts are absent.
    from mission_runtime import (  # late import — keeps cold-start cost low
        MissionArtifactKind,
        placement_seam,
    )

    feature_dir = placement_seam(main_repo_root, mission_slug, effective_root=effective_root).read_dir(MissionArtifactKind.RESEARCH)

    # Detect mission type from feature's meta.json
    mission_type = get_mission_type(feature_dir)

    # Check 1: Uncommitted research artifacts in planning repo (applies to ALL missions)
    # Research artifacts live in kitty-specs/ which is in the planning repo, not worktrees
    research_guidance = _validate_research_artifacts(
        main_repo_root=effective_root or main_repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        mission_type=mission_type,
        target_lane=target_lane,
        console=console,
    )
    if research_guidance is not None:
        return False, research_guidance

    # Check 2: For software-dev missions, check worktree for implementation commits
    if mission_type == MISSION_TYPE_SOFTWARE_DEV:
        worktree_result = _validate_worktree_state(
            repo_root=repo_root,
            main_repo_root=main_repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            target_lane=target_lane,
            resolve_workspace_for_wp=resolve_workspace_for_wp,
            get_feature_target_branch=get_feature_target_branch,
            review_currency_check_branch=review_currency_check_branch,
            behind_commits_touch_only_planning_artifacts=behind_commits_touch_only_planning_artifacts,
            filter_runtime_state_paths=filter_runtime_state_paths,
            list_wp_branch_specs_changes_for_guard=list_wp_branch_specs_changes_for_guard,
            workspace_override=workspace_override,
            review_base_ref=review_base_ref,
            check_kitty_specs=check_kitty_specs,
        )
        if worktree_result is not None:
            return worktree_result

    return True, []


__all__ = [
    "_apply_review_status_flags",
    # _check_branch_currency, _check_implementation_commit_present,
    # _check_kitty_specs_contamination, _check_uncommitted_worktree_changes,
    # _check_worktree_health, _issue_matrix_diagnostic_lines,
    # _issue_matrix_evaluation, _issue_matrix_in_mission_rows,
    # _issue_matrix_row_issues, _latest_status_event_time:
    # demoted — no cross-module src/ callers (WP01 harden-dead-symbol-gate).
    # (_primary_issue_matrix_satisfies was DELETED — coord-commit-integrity
    # SURFACE A #1c: a PRIMARY fallback for the COORD-partition issue-matrix was
    # the split-brain anti-pattern.)
    # (_review_artifact_dir_for_wp, _review_cycle_number,
    # _get_latest_review_cycle_verdict were DELETED — WP05
    # verdict-seam-write-unification-01KZ9Q35/FR-003: the frontmatter verdict
    # reader and its two support helpers, retired in favour of
    # ``event_sourced_review_result``.)
    # _validate_research_artifacts, _validate_worktree_state:
    # demoted — no cross-module src/ callers (WP01 harden-dead-symbol-gate).
    "_issue_matrix_approval_blocker",
    "_self_review_fallback_option_error",
    "_validate_ready_for_review",
]
