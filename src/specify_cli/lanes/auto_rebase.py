"""Stale-lane auto-rebase orchestrator.

Drives the auto-rebase pipeline described in
``docs/adr/3.x/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md``:

1. Attempt ``git merge <mission-branch>`` inside the lane worktree.
2. If the merge succeeds cleanly, return :class:`AutoRebaseReport` with
   ``succeeded=True``.
3. If conflicts surface, classify each conflicted region via
   :mod:`specify_cli.merge.conflict_classifier`. Any ``Manual`` classification
   aborts the merge and returns ``succeeded=False``.
4. For ``Auto`` classifications, splice the merged text back into the file
   and stage it. Run post-merge validation (TOML parse / AST parse).
5. If ``uv.lock`` was conflicted, regenerate it under the cross-process
   :class:`specify_cli.core.file_lock.MachineFileLock` to serialize across
   lanes. Stage the regenerated file.
6. If any ``__init__.py`` was modified, run ``ruff --fix --select I001 <file>``.
   Non-zero exit ⇒ revert to ``Manual``.
7. Create the merge commit with message
   ``"auto-rebase(lane=<id>): <N> conflicts resolved by classifier rules
   [<rule_ids>]"`` per ADR §Operator-visible-behavior.

This module performs all subprocess and filesystem I/O. The classifier in
:mod:`specify_cli.merge.conflict_classifier` is pure.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.file_lock import MachineFileLock
from specify_cli.lanes.merge import (
    _ensure_merge_driver_git_config,
    _make_merge_env,
)
from specify_cli.lanes.models import ExecutionLane
from specify_cli.merge.conflict_classifier import (
    RULE_ID_INIT_IMPORTS,
    RULE_ID_UVLOCK,
    Auto,
    ConflictClassification,
    Manual,
    classify,
    validate_resolution,
)
from specify_cli.status import EventLogMergeError, materialize, merge_event_log_texts
from specify_cli.coordination.coherence import is_coord_residue_churn
from mission_runtime import (
    MissionArtifactKind,
    kind_for_mission_file,
)

__all__ = [
    "AutoRebaseReport",
    "attempt_auto_rebase",
]

_UV_LOCK_FILENAME = "uv.lock"
_STATUS_JSON_FILENAME = "status.json"
RULE_ID_STATUS_EVENTS = "R-STATUS-EVENTS-JSONL-UNION"
RULE_ID_STATUS_JSON = "R-STATUS-JSON-REMATERIALIZE"
RULE_ID_COORDINATION_ARTIFACT = "R-COORDINATION-ARTIFACT-THEIRS"

# Auto-rebase manages a SUPERSET of the surface-residue set, because two
# DISTINCT concerns were conflated by the #2070 delegation:
#
#   1. *Surface residue* — "is a stale PRIMARY-checkout copy of this file mere
#      residue of a coordination-owned artifact?" Answered by the single authority
#      ``specify_cli.coordination.coherence.is_coord_residue_churn`` (imported
#      above so this consumer still draws residue recognition from that authority
#      — WP12 retired the former ``mission_runtime`` predicate onto this owner
#      leg; FR-012). Post write-surface-coherence (#2090) the COORD-partition members
#      (``issue-matrix.md`` / ``analysis-report.md`` / ``acceptance-matrix.json``)
#      are residue, while ``plan.md`` / ``tasks.md`` / ``lanes.json`` /
#      ``tasks/WP*.md`` moved to the PRIMARY partition and are NO LONGER residue
#      (a stale primary copy is REAL dirt — the dirty-tree gates depend on this and
#      it MUST NOT be reverted, #2128).
#
#   2. *Auto-rebase managed-artifact reconciliation* — "when a stale lane worktree
#      copy of a mission-owned PLANNING-LAYOUT artifact CONFLICTS with the mission
#      branch during auto-rebase, take the mission branch's copy deterministically."
#      The finalize-tasks layout (``lanes.json`` → ``LANE_STATE``, ``tasks/WP*.md``
#      → ``WORK_PACKAGE_TASK``) is owned by the mission branch; a lane's drifted
#      copy is discarded in favour of theirs. These are PRIMARY-partition (hence NOT
#      surface residue) yet still managed by auto-rebase — the two concerns are
#      orthogonal.
#
#      ``analysis-report.md`` (``ANALYSIS_REPORT``) joined this arm when
#      coord-commit-integrity (FR-003) re-homed it COORD→PRIMARY: it left the
#      surface-residue set (Arm 1) but stays a MACHINE-GENERATED, deterministically
#      reconcilable artifact (unlike the author-owned narrative docs below), so it
#      must remain take-theirs. Dropping it from BOTH arms would reintroduce the
#      #2070 auto-rebase-halt regression on an ``analysis-report.md`` conflict.
#
# NOT included here (these stay Manual halts so the operator reconciles real
# authored drift): ``plan.md`` (``FINALIZED_EXECUTION_PLAN``) and ``tasks.md``
# (``TASKS_INDEX``) — narrative planning docs whose conflicts are author-owned —
# and the planning SOURCE docs (``spec.md`` / ``data-model.md`` / ``research.md`` /
# ``checklists/``). Status artifacts have their own union / rematerialize rules.
_AUTO_REBASE_MANAGED_LAYOUT_KINDS: frozenset[MissionArtifactKind] = frozenset(
    {
        MissionArtifactKind.LANE_STATE,
        MissionArtifactKind.WORK_PACKAGE_TASK,
        MissionArtifactKind.ANALYSIS_REPORT,
    }
)


@dataclass(frozen=True)
class AutoRebaseReport:
    """Outcome of an auto-rebase attempt for a single lane.

    Mirrors the dataclass in ``data-model.md`` §3. The dataclass is
    ``frozen=True`` so callers cannot mutate the audit-log record.
    """

    lane_id: str
    attempted: bool
    succeeded: bool
    classifications: tuple[ConflictClassification, ...] = field(default_factory=tuple)
    halt_reason: str | None = None

    def __post_init__(self) -> None:
        # Invariant: halt_reason is set iff succeeded is False.
        if self.succeeded and self.halt_reason is not None:
            raise ValueError(
                "AutoRebaseReport: halt_reason must be None when succeeded=True"
            )
        if not self.succeeded and self.halt_reason is None and self.attempted:
            raise ValueError(
                "AutoRebaseReport: halt_reason must be set when succeeded=False "
                "and attempted=True"
            )


# Conflict-marker regex used to split a conflicted file into clean text,
# conflict regions, and the trailing clean tail.
_RE_CONFLICT_REGION = re.compile(
    r"<{7}[^\n]*\n.*?>{7}[^\n]*\n",
    re.DOTALL,
)


def _run(
    cmd: list[str], cwd: Path, *, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command capturing stdout/stderr as text."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
        env=_make_merge_env(),
    )


def _list_conflicted_files(worktree: Path) -> list[Path]:
    """Return absolute paths to files currently in conflict in ``worktree``."""
    result = _run(["git", "diff", "--name-only", "--diff-filter=U"], worktree)
    if result.returncode != 0:
        return []
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name:
            continue
        paths.append(worktree / name)
    return paths


def _relative_path(file_path: Path, worktree: Path) -> str:
    return file_path.relative_to(worktree).as_posix()


def _path_parts(rel_path: str) -> tuple[str, ...]:
    return tuple(Path(rel_path).parts)


def _is_status_events_path(rel_path: str) -> bool:
    parts = _path_parts(rel_path)
    return (
        len(parts) >= 3
        and parts[0] == KITTY_SPECS_DIR
        and parts[-1] == "status.events.jsonl"
    )


def _is_status_json_path(rel_path: str) -> bool:
    parts = _path_parts(rel_path)
    return (
        len(parts) >= 3
        and parts[0] == KITTY_SPECS_DIR
        and parts[-1] == _STATUS_JSON_FILENAME
    )


def _is_coordination_owned_artifact(rel_path: str) -> bool:
    """True for an artifact the auto-rebase "take theirs" arm deterministically
    resolves in favour of the mission branch's copy.

    Two arms — the auto-rebase managed set is a SUPERSET of surface residue (see
    :data:`_AUTO_REBASE_MANAGED_LAYOUT_KINDS` for the full rationale):

    1. *Surface residue* — drawn from the single authority
       :func:`specify_cli.coordination.coherence.is_coord_residue_churn`
       (``issue-matrix.md`` / ``acceptance-matrix.json``).
    2. *Mission-owned planning LAYOUT* — ``lanes.json`` (``LANE_STATE``),
       ``tasks/WP*.md`` (``WORK_PACKAGE_TASK``), and ``analysis-report.md``
       (``ANALYSIS_REPORT``, re-homed COORD→PRIMARY by coord-commit-integrity
       FR-003). These live on the PRIMARY partition so they are NO LONGER surface
       residue, yet auto-rebase still resolves a stale lane copy take-theirs
       against the finalize-tasks / generated layout. The #2070 delegation to the
       residue predicate alone dropped them and broke deterministic reconciliation
       (this regression's root cause).

    ``plan.md`` / ``tasks.md`` and the planning SOURCE docs are intentionally in
    NEITHER arm — their conflicts surface as Manual halts.
    """
    if is_coord_residue_churn(rel_path):
        return True
    kind = kind_for_mission_file(rel_path)
    return kind is not None and kind in _AUTO_REBASE_MANAGED_LAYOUT_KINDS


def _git_show_stage(worktree: Path, rel_path: str, stage: int) -> str | None:
    result = _run(["git", "show", f":{stage}:{rel_path}"], worktree)
    if result.returncode != 0:
        return None
    return result.stdout


def _result_output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip()


def _rejected_sparse_flag(result: subprocess.CompletedProcess[str]) -> bool:
    """True when git failed specifically because it does not know ``--sparse``.

    Git older than 2.35 answers ``git add --sparse`` / ``git rm --sparse``
    with ``error: unknown option 'sparse'``; any other failure is a real
    staging/removal error the caller must surface.
    """
    combined = f"{result.stderr}\n{result.stdout}"
    return "unknown option" in combined and "sparse" in combined


def _stage_sparse(worktree: Path, rel_path: str) -> tuple[bool, str | None]:
    """Stage ``rel_path`` for the managed-artifact resolution arms.

    ``--sparse`` exists so a sparse-checkout worktree can stage a path outside
    its checkout patterns (Git >= 2.35 only). It was previously passed
    unconditionally, which aborted every lane auto-rebase conflict resolution
    on Git < 2.35 with ``error: unknown option 'sparse'`` even for plain,
    non-sparse worktrees (#4202). It is now used only when the worktree
    actually has ``core.sparseCheckout`` enabled, with a plain-``git``-command
    fallback when the flag itself is what git rejected.
    """
    if _sparse_checkout_enabled(worktree):
        result = _run(["git", "add", "--sparse", rel_path], worktree)
        if result.returncode == 0:
            return True, None
        if not _rejected_sparse_flag(result):
            return False, _result_output(result)
    result = _run(["git", "add", rel_path], worktree)
    if result.returncode != 0:
        return False, _result_output(result)
    return True, None


def _sparse_checkout_enabled(worktree: Path) -> bool:
    result = _run(["git", "config", "--bool", "core.sparseCheckout"], worktree)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _reapply_sparse_checkout(worktree: Path) -> str | None:
    if not _sparse_checkout_enabled(worktree):
        return None
    result = _run(["git", "sparse-checkout", "reapply"], worktree)
    if result.returncode != 0:
        return result.stderr.strip() or result.stdout.strip()
    return None


def _remove_sparse(worktree: Path, rel_path: str) -> tuple[bool, str | None]:
    """Remove ``rel_path`` from the worktree and the index (take-theirs arm).

    ``--sparse`` gating mirrors :func:`_stage_sparse`: only genuine
    sparse-checkout worktrees get the flag, and a git that rejects the flag
    outright (Git < 2.35) degrades to the plain ``git rm`` command (#4202).
    """
    target = worktree / rel_path
    if target.exists():
        try:
            target.unlink()
        except OSError as exc:
            return False, f"could not remove {rel_path}: {exc!r}"
    if _sparse_checkout_enabled(worktree):
        result = _run(
            ["git", "rm", "-f", "--ignore-unmatch", "--sparse", rel_path], worktree
        )
        if result.returncode == 0:
            return True, None
        if not _rejected_sparse_flag(result):
            return False, _result_output(result)
    result = _run(["git", "rm", "-f", "--ignore-unmatch", rel_path], worktree)
    if result.returncode != 0:
        return False, _result_output(result)
    return True, None


def _managed_classification(file_path: Path, rule_id: str) -> ConflictClassification:
    return ConflictClassification(
        file_path=file_path,
        hunk_text="",
        resolution=Auto(merged_text="", rule_id=rule_id),
    )


def _resolve_status_events(
    file_path: Path,
    worktree: Path,
) -> tuple[ConflictClassification | None, str | None]:
    rel_path = _relative_path(file_path, worktree)
    stage_text_by_number = {
        stage: text
        for stage in (1, 2, 3)
        if (text := _git_show_stage(worktree, rel_path, stage)) is not None
    }
    if 2 not in stage_text_by_number or 3 not in stage_text_by_number:
        return None, (
            f"{RULE_ID_STATUS_EVENTS}: refusing status.events.jsonl deletion "
            f"conflict for {rel_path}"
        )

    stage_texts = list(stage_text_by_number.values())
    if not stage_texts:
        return None, f"{RULE_ID_STATUS_EVENTS}: no index stages found for {rel_path}"

    try:
        merged_text = merge_event_log_texts(*stage_texts)
    except EventLogMergeError as exc:
        return None, f"{RULE_ID_STATUS_EVENTS}: {exc}"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        file_path.write_text(merged_text, encoding="utf-8")
    except OSError as exc:
        return None, f"{RULE_ID_STATUS_EVENTS}: could not write {rel_path}: {exc!r}"

    ok, message = _stage_sparse(worktree, rel_path)
    if not ok:
        return None, f"{RULE_ID_STATUS_EVENTS}: git add {rel_path} failed: {message}"
    return _managed_classification(file_path, RULE_ID_STATUS_EVENTS), None


def _resolve_take_theirs(
    file_path: Path,
    worktree: Path,
) -> tuple[ConflictClassification | None, str | None]:
    rel_path = _relative_path(file_path, worktree)
    theirs = _git_show_stage(worktree, rel_path, 3)
    if theirs is None:
        ok, message = _remove_sparse(worktree, rel_path)
        if not ok:
            return None, (
                f"{RULE_ID_COORDINATION_ARTIFACT}: git rm {rel_path} "
                f"failed: {message}"
            )
        return _managed_classification(file_path, RULE_ID_COORDINATION_ARTIFACT), None

    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        file_path.write_text(theirs, encoding="utf-8")
    except OSError as exc:
        return None, (
            f"{RULE_ID_COORDINATION_ARTIFACT}: could not write {rel_path}: {exc!r}"
        )

    ok, message = _stage_sparse(worktree, rel_path)
    if not ok:
        return None, (
            f"{RULE_ID_COORDINATION_ARTIFACT}: git add {rel_path} "
            f"failed: {message}"
        )
    return _managed_classification(file_path, RULE_ID_COORDINATION_ARTIFACT), None


def _resolve_status_json(
    file_path: Path,
    worktree: Path,
) -> tuple[ConflictClassification | None, str | None]:
    rel_path = _relative_path(file_path, worktree)
    event_log_error = _hydrate_status_events_from_index(file_path.parent, worktree)
    if event_log_error is not None:
        return None, event_log_error

    try:
        materialize(file_path.parent)
    except Exception as exc:  # noqa: BLE001 - surface reducer/store failures to operator
        return None, f"{RULE_ID_STATUS_JSON}: could not materialize {rel_path}: {exc!r}"

    ok, message = _stage_sparse(worktree, rel_path)
    if not ok:
        return None, f"{RULE_ID_STATUS_JSON}: git add {rel_path} failed: {message}"
    return _managed_classification(file_path, RULE_ID_STATUS_JSON), None


def _hydrate_status_events_from_index(feature_dir: Path, worktree: Path) -> str | None:
    """Ensure materialize() can read event rows hidden by sparse checkout."""
    events_path = feature_dir / "status.events.jsonl"
    if events_path.exists():
        return None

    rel_path = _relative_path(events_path, worktree)
    index_text = _git_show_stage(worktree, rel_path, 0)
    if index_text is None:
        return f"{RULE_ID_STATUS_JSON}: missing authoritative {rel_path}"

    events_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        events_path.write_text(index_text, encoding="utf-8")
    except OSError as exc:
        return f"{RULE_ID_STATUS_JSON}: could not hydrate {rel_path}: {exc!r}"

    ok, message = _stage_sparse(worktree, rel_path)
    if not ok:
        return f"{RULE_ID_STATUS_JSON}: git add {rel_path} failed: {message}"
    return None


def _resolve_managed_artifact_conflicts(
    conflicted: list[Path],
    worktree: Path,
    classifications: list[ConflictClassification],
) -> tuple[list[Path], str | None]:
    """Resolve Spec Kitty-owned planning artifacts before generic text rules."""
    remaining: list[Path] = []
    status_json_paths_by_dir: dict[Path, Path] = {}
    status_refresh_dirs: set[Path] = set()

    for file_path in conflicted:
        rel_path = _relative_path(file_path, worktree)
        if _is_status_events_path(rel_path):
            classification, halt_reason = _resolve_status_events(file_path, worktree)
            status_refresh_dirs.add(file_path.parent)
        elif _is_status_json_path(rel_path):
            status_json_paths_by_dir[file_path.parent] = file_path
            status_refresh_dirs.add(file_path.parent)
            continue
        elif _is_coordination_owned_artifact(rel_path):
            classification, halt_reason = _resolve_take_theirs(file_path, worktree)
        else:
            remaining.append(file_path)
            continue

        if halt_reason is not None:
            return remaining, halt_reason
        assert classification is not None
        classifications.append(classification)

    for feature_dir in sorted(status_refresh_dirs, key=lambda path: path.as_posix()):
        file_path = status_json_paths_by_dir.get(feature_dir, feature_dir / _STATUS_JSON_FILENAME)
        classification, halt_reason = _resolve_status_json(file_path, worktree)
        if halt_reason is not None:
            return remaining, halt_reason
        assert classification is not None
        classifications.append(classification)

    return remaining, None


def _merge_head_exists(worktree: Path) -> bool:
    result = _run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], worktree)
    return result.returncode == 0


def _git_ref_has_path(worktree: Path, ref: str, rel_path: str) -> bool:
    result = _run(["git", "cat-file", "-e", f"{ref}:{rel_path}"], worktree)
    return result.returncode == 0


def _status_artifact_paths_from_ref(
    worktree: Path,
    ref: str,
) -> tuple[set[str], str | None]:
    result = _run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", KITTY_SPECS_DIR],
        worktree,
    )
    if result.returncode != 0:
        return set(), result.stderr.strip() or result.stdout.strip()
    return {
        rel_path
        for rel_path in result.stdout.splitlines()
        if _is_status_events_path(rel_path) or _is_status_json_path(rel_path)
    }, None


def _refuse_preexisting_lane_status_deletions(
    worktree: Path,
    mission_branch: str,
) -> str | None:
    """Refuse a lane-side pre-existing deletion of a coordination-owned status file.

    FR-009 reconciliation (ADR ``2026-07-29-1``, T004, #1684): this function's
    ``git merge-base HEAD <mission_branch>`` reasoning is UNCHANGED by the WP01
    lane-base fix. That fix merges the recorded finalize-tasks planning commit
    INTO a lane on top of its existing ``coordination_branch`` /
    ``mission_branch`` parentage — it never replaces that parentage — so the
    lane still descends directly from whatever branch ``mission_branch`` names
    here (either ``coordination_branch`` verbatim, via
    ``lifecycle_sync.py``'s call, or ``lanes_manifest.mission_branch``, via
    ``lanes/merge.py``'s ``consolidate_lane_into_mission`` — the SAME branch
    for coordination-topology missions, since both are composed by the
    identical ``branch_naming.mission_branch_name`` grammar). The merge-base
    computed here is therefore exactly what it was before WP01: the lane's own
    fork point off ``mission_branch``, unaffected by the additional
    planning-commit ancestor now present elsewhere in the lane's history.

    Note (not fixed here, out of WP01 scope): a SEPARATE lane-hygiene guard
    (#2274) compares ``kitty-specs/`` by commit-history rather than content and
    can false-positive immediately after this fix ships, because the extra
    planning-commit merge changes a lane's commit history under
    ``kitty-specs/<slug>/`` without changing its content relative to the
    planning branch. See ADR ``2026-07-29-1`` "More Information" for the
    coordinating issues (#2273/#2626/#2570).
    """
    merge_base = _run(["git", "merge-base", "HEAD", mission_branch], worktree)
    if merge_base.returncode != 0:
        return (
            f"{RULE_ID_STATUS_EVENTS}: could not find merge base with "
            f"{mission_branch}: {(merge_base.stderr or merge_base.stdout).strip()}"
        )
    base_ref = merge_base.stdout.strip()

    base_paths, error = _status_artifact_paths_from_ref(worktree, base_ref)
    if error is not None:
        return f"{RULE_ID_STATUS_EVENTS}: could not inspect base status artifacts: {error}"
    mission_paths, error = _status_artifact_paths_from_ref(worktree, mission_branch)
    if error is not None:
        return (
            f"{RULE_ID_STATUS_EVENTS}: could not inspect coordination status "
            f"artifacts: {error}"
        )

    for rel_path in sorted(base_paths & mission_paths):
        if not _git_ref_has_path(worktree, "HEAD", rel_path):
            return (
                f"{RULE_ID_STATUS_EVENTS}: refusing pre-existing lane-side "
                f"deletion of coordination-owned status artifact {rel_path}"
            )
    return None


def _staged_status_artifact_dirs(worktree: Path) -> tuple[set[Path], str | None]:
    result = _run(["git", "diff", "--name-status", "--cached"], worktree)
    if result.returncode != 0:
        return set(), result.stderr.strip() or result.stdout.strip()

    feature_dirs: set[Path] = set()
    for raw in result.stdout.splitlines():
        fields = raw.strip().split("\t")
        if not fields:
            continue
        status = fields[0]
        rel_paths = fields[1:] or [status]
        for rel_path in rel_paths:
            if _is_status_events_path(rel_path):
                if status.startswith(("D", "R")):
                    return set(), (
                        f"{RULE_ID_STATUS_EVENTS}: refusing staged deletion "
                        f"of {rel_path}"
                    )
                feature_dirs.add((worktree / rel_path).parent)
            elif _is_status_json_path(rel_path):
                feature_dirs.add((worktree / rel_path).parent)
    return feature_dirs, None


def _status_json_already_classified(
    file_path: Path,
    classifications: list[ConflictClassification],
) -> bool:
    return any(
        classification.file_path == file_path
        and isinstance(classification.resolution, Auto)
        and classification.resolution.rule_id == RULE_ID_STATUS_JSON
        for classification in classifications
    )


def _refresh_status_json_for_staged_artifacts(
    worktree: Path,
    classifications: list[ConflictClassification],
) -> str | None:
    feature_dirs, error = _staged_status_artifact_dirs(worktree)
    if error is not None:
        if error.startswith(f"{RULE_ID_STATUS_EVENTS}:"):
            return error
        return f"{RULE_ID_STATUS_JSON}: could not inspect staged paths: {error}"

    for feature_dir in sorted(feature_dirs, key=lambda path: path.as_posix()):
        file_path = feature_dir / _STATUS_JSON_FILENAME
        if _status_json_already_classified(file_path, classifications):
            continue
        classification, halt_reason = _resolve_status_json(file_path, worktree)
        if halt_reason is not None:
            return halt_reason
        assert classification is not None
        classifications.append(classification)
    return None


def _split_into_regions(
    text: str,
) -> tuple[list[tuple[bool, str]], int]:
    """Return ``(segments, conflict_count)`` where each segment is
    ``(is_conflict, text)``. Order is preserved so a faithful reassembly is
    a simple concatenation.
    """
    segments: list[tuple[bool, str]] = []
    last_end = 0
    count = 0
    for m in _RE_CONFLICT_REGION.finditer(text):
        if m.start() > last_end:
            segments.append((False, text[last_end : m.start()]))
        segments.append((True, m.group(0)))
        count += 1
        last_end = m.end()
    if last_end < len(text):
        segments.append((False, text[last_end:]))
    return segments, count


def _git_user_env_ready(worktree: Path) -> None:
    """Best-effort: ensure git user.name/user.email exist so ``git commit``
    does not fail under unconfigured environments (e.g. test sandboxes)."""
    for key, default in (("user.email", "auto-rebase@spec-kitty"), ("user.name", "spec-kitty auto-rebase")):
        existing = _run(["git", "config", "--get", key], worktree)
        if existing.returncode != 0 or not existing.stdout.strip():
            _run(["git", "config", key, default], worktree)


def _regenerate_uv_lock(repo_root: Path, worktree: Path) -> tuple[bool, str]:
    """Regenerate ``uv.lock`` under :class:`MachineFileLock`.

    Returns ``(success, message)``. ``message`` is the stderr/stdout summary
    on failure; empty string on success.
    """
    lock_path = repo_root / ".kittify" / "auto-rebase-uv-lock.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    async def _run_locked() -> tuple[bool, str]:
        async with MachineFileLock(lock_path):
            # Async subprocess so the event loop is not blocked while uv lock
            # runs (S7487). The cross-process MachineFileLock above still
            # serializes lock regeneration across parallel lane workers.
            proc = await asyncio.create_subprocess_exec(
                "uv",
                "lock",
                "--no-upgrade",
                cwd=str(worktree),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            if proc.returncode != 0:
                summary = (
                    stderr_bytes.decode("utf-8", errors="replace")
                    or stdout_bytes.decode("utf-8", errors="replace")
                ).strip()
                return False, summary
            return True, ""

    try:
        return asyncio.run(_run_locked())
    except FileNotFoundError:
        # uv not installed in this environment — fall back to checkout-theirs
        # to avoid blocking the orchestrator entirely. The operator can
        # regenerate later. We treat this as a soft success only when the
        # caller has explicitly accepted the policy; otherwise it is a hard
        # failure. Be conservative: hard failure.
        return False, "uv binary not found on PATH"
    except Exception as exc:  # noqa: BLE001 — surface to operator
        return False, f"uv lock raised: {exc!r}"


def _attempt_resolve_uv_lock(worktree: Path, repo_root: Path) -> tuple[bool, str]:
    """Discard both sides of the ``uv.lock`` conflict and stage the regenerated file."""
    # Remove the conflicted state by checking out --theirs then deleting the
    # file; uv lock will write a fresh one.
    lockfile = worktree / _UV_LOCK_FILENAME
    if lockfile.exists():
        try:
            lockfile.unlink()
        except OSError as exc:
            return False, f"could not remove conflicted uv.lock: {exc!r}"
    ok, message = _regenerate_uv_lock(repo_root, worktree)
    if not ok:
        return False, message
    add_result = _run(["git", "add", _UV_LOCK_FILENAME], worktree)
    if add_result.returncode != 0:
        return False, f"git add uv.lock failed: {add_result.stderr.strip()}"
    return True, ""


def _run_ruff_imports_fix(worktree: Path, file_path: Path) -> tuple[bool, str]:
    """Run ``ruff --fix --select I001`` on a single file. Returns ``(ok, message)``."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--fix", "--select", "I001", str(file_path)],
            cwd=str(worktree),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # ruff not installed — keep the merged content as-is (it is already
        # a deterministic union; the lint pass is purely cosmetic).
        return True, ""
    if result.returncode not in (0, 1):
        # 0 = no issues, 1 = fixed issues. Anything else is a hard failure.
        return False, (result.stderr or result.stdout).strip()
    return True, ""


def _abort_with_failure(
    worktree_path: Path,
    lane_id: str,
    classifications: list[ConflictClassification],
    halt_reason: str,
) -> AutoRebaseReport:
    """Run ``git merge --abort`` and return a failure ``AutoRebaseReport``."""
    _run(["git", "merge", "--abort"], worktree_path)
    sparse_error = _reapply_sparse_checkout(worktree_path)
    if sparse_error is not None:
        halt_reason = f"{halt_reason}; sparse checkout cleanup failed: {sparse_error}"
    return AutoRebaseReport(
        lane_id=lane_id,
        attempted=True,
        succeeded=False,
        classifications=tuple(classifications),
        halt_reason=halt_reason,
    )


def _classify_file_regions(
    file_path: Path,
    segments: list[tuple[bool, str]],
) -> tuple[list[ConflictClassification], ConflictClassification | None]:
    """Classify each conflict region in a file's segments.

    Returns ``(classifications, manual_hit)``. When ``manual_hit`` is not None,
    classification was aborted at the first ``Manual`` result.
    """
    file_classifications: list[ConflictClassification] = []
    for is_conflict, segment in segments:
        if not is_conflict:
            continue
        cls = classify(file_path, segment)
        file_classifications.append(cls)
        if isinstance(cls.resolution, Manual):
            return file_classifications, cls
    return file_classifications, None


def _splice_resolutions(
    segments: list[tuple[bool, str]],
    file_classifications: list[ConflictClassification],
) -> str:
    """Concatenate clean segments with the merged_text of Auto resolutions."""
    rebuilt_parts: list[str] = []
    idx = 0
    for is_conflict, segment in segments:
        if is_conflict:
            resolution = file_classifications[idx].resolution
            idx += 1
            assert isinstance(resolution, Auto)
            rebuilt_parts.append(resolution.merged_text)
        else:
            rebuilt_parts.append(segment)
    return "".join(rebuilt_parts)


def _validate_file_classifications(
    file_classifications: list[ConflictClassification],
    rebuilt: str,
) -> tuple[list[ConflictClassification], ConflictClassification | None]:
    """Validate Auto resolutions against the rebuilt file body."""
    validated: list[ConflictClassification] = []
    for cls in file_classifications:
        v = validate_resolution(cls, rebuilt)
        validated.append(v)
        if isinstance(v.resolution, Manual):
            return validated, v
    return validated, None


def _process_conflicted_file(
    file_path: Path,
    worktree_path: Path,
) -> tuple[list[ConflictClassification], bool, str | None]:
    """Classify, splice, validate, write, and stage one conflicted file.

    Returns ``(classifications, is_init_py, halt_reason)``. When
    ``halt_reason`` is not None, the caller should abort. ``classifications``
    is always the partial list to surface for audit.
    """
    try:
        body = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], False, f"could not read conflicted file {file_path}: {exc!r}"

    segments, conflict_count = _split_into_regions(body)
    if conflict_count == 0:
        return [], False, (
            f"file {file_path} marked conflicted but contains no conflict markers"
        )

    file_classifications, manual_hit = _classify_file_regions(file_path, segments)
    if manual_hit is not None:
        assert isinstance(manual_hit.resolution, Manual)
        return file_classifications, False, manual_hit.resolution.reason

    rebuilt = _splice_resolutions(segments, file_classifications)

    validated, validation_failed = _validate_file_classifications(
        file_classifications, rebuilt
    )
    if validation_failed is not None:
        assert isinstance(validation_failed.resolution, Manual)
        return validated, False, validation_failed.resolution.reason

    try:
        file_path.write_text(rebuilt, encoding="utf-8")
    except OSError as exc:
        return validated, False, f"could not write merged file {file_path}: {exc!r}"

    add_result = _run(
        ["git", "add", str(file_path.relative_to(worktree_path))],
        worktree_path,
    )
    if add_result.returncode != 0:
        return validated, False, (
            f"git add {file_path} failed: {add_result.stderr.strip()}"
        )

    return validated, file_path.name == "__init__.py", None


def _finalize_auto_rebase(
    lane_id: str,
    worktree_path: Path,
    repo_root: Path,
    classifications: list[ConflictClassification],
    init_py_touched: list[Path],
    uvlock_seen: bool,
) -> AutoRebaseReport:
    """Run post-resolution steps: uv.lock regen, ruff fix, commit."""
    if uvlock_seen:
        ok, message = _attempt_resolve_uv_lock(worktree_path, repo_root)
        if not ok:
            return _abort_with_failure(
                worktree_path, lane_id, classifications,
                f"{RULE_ID_UVLOCK}: {message}",
            )

    for init_path in init_py_touched:
        ok, message = _run_ruff_imports_fix(worktree_path, init_path)
        if not ok:
            return _abort_with_failure(
                worktree_path, lane_id, classifications,
                f"{RULE_ID_INIT_IMPORTS}: ruff failed: {message}",
            )
        _run(
            ["git", "add", str(init_path.relative_to(worktree_path))],
            worktree_path,
        )

    halt_reason = _refresh_status_json_for_staged_artifacts(worktree_path, classifications)
    if halt_reason is not None:
        return _abort_with_failure(
            worktree_path, lane_id, classifications, halt_reason,
        )

    sparse_error = _reapply_sparse_checkout(worktree_path)
    if sparse_error is not None:
        return _abort_with_failure(
            worktree_path, lane_id, classifications,
            f"sparse checkout cleanup failed: {sparse_error}",
        )

    rule_ids_used = sorted(
        {
            c.resolution.rule_id
            for c in classifications
            if isinstance(c.resolution, Auto)
        }
    )
    message = (
        f"auto-rebase(lane={lane_id}): {len(classifications)} conflicts "
        f"resolved by classifier rules [{', '.join(rule_ids_used)}]"
    )
    commit_result = _run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", message],
        worktree_path,
    )
    if commit_result.returncode != 0:
        return _abort_with_failure(
            worktree_path, lane_id, classifications,
            f"merge commit failed: "
            f"{(commit_result.stderr or commit_result.stdout).strip()}",
        )

    return AutoRebaseReport(
        lane_id=lane_id,
        attempted=True,
        succeeded=True,
        classifications=tuple(classifications),
    )


def attempt_auto_rebase(
    lane: ExecutionLane,
    branch: str,
    mission_branch: str,
    repo_root: Path,
    worktree_path: Path,
) -> AutoRebaseReport:
    """Attempt a stale-lane auto-rebase.

    The caller has already determined the lane is stale. This function:

    1. Runs ``git merge --no-commit <mission_branch>`` inside ``worktree_path``.
    2. If clean, refreshes any staged status snapshots and commits the merge.
    3. Classifies each conflict region. Any ``Manual`` aborts the merge and
       returns ``succeeded=False``.
    4. Applies ``Auto`` resolutions, regenerates ``uv.lock`` if needed, runs
       ``ruff --fix --select I001`` on touched ``__init__.py`` files, and
       commits with the audit message.
    """
    _git_user_env_ready(worktree_path)

    halt_reason = _refuse_preexisting_lane_status_deletions(
        worktree_path,
        mission_branch,
    )
    if halt_reason is not None:
        return AutoRebaseReport(
            lane_id=lane.lane_id,
            attempted=True,
            succeeded=False,
            classifications=(),
            halt_reason=halt_reason,
        )

    # Define the custom merge drivers (self-heal for freshly-init'd repos) but do
    # NOT seed ``.git/info/attributes``: auto-rebase must keep its own in-process
    # event-log union classifier (R-STATUS-EVENTS-JSONL-UNION) as the fallback for
    # repos without a committed ``.gitattributes`` mapping. Pre-activating the git
    # driver here would pre-empt that classifier (#2709/#2711 regression).
    _ensure_merge_driver_git_config(repo_root)

    merge_result = _run(
        ["git", "merge", "--no-edit", "--no-ff", "--no-commit", mission_branch],
        worktree_path,
    )
    if merge_result.returncode == 0:
        clean_classifications: list[ConflictClassification] = []
        halt_reason = _refresh_status_json_for_staged_artifacts(
            worktree_path, clean_classifications
        )
        if halt_reason is not None:
            return _abort_with_failure(
                worktree_path, lane.lane_id, clean_classifications, halt_reason,
            )

        sparse_error = _reapply_sparse_checkout(worktree_path)
        if sparse_error is not None:
            return _abort_with_failure(
                worktree_path, lane.lane_id, clean_classifications,
                f"sparse checkout cleanup failed: {sparse_error}",
            )

        if _merge_head_exists(worktree_path):
            commit_result = _run(
                ["git", "-c", "commit.gpgsign=false", "commit", "--no-edit"],
                worktree_path,
            )
            if commit_result.returncode != 0:
                return _abort_with_failure(
                    worktree_path, lane.lane_id, clean_classifications,
                    f"merge commit failed: "
                    f"{(commit_result.stderr or commit_result.stdout).strip()}",
                )

        return AutoRebaseReport(
            lane_id=lane.lane_id,
            attempted=True,
            succeeded=True,
            classifications=tuple(clean_classifications),
        )

    conflicted = _list_conflicted_files(worktree_path)
    if not conflicted:
        return _abort_with_failure(
            worktree_path, lane.lane_id, [],
            f"git merge failed without conflicts on {branch}: "
            f"{(merge_result.stderr or merge_result.stdout).strip()}",
        )

    classifications: list[ConflictClassification] = []
    init_py_touched: list[Path] = []
    uvlock_seen = False
    conflicted, halt_reason = _resolve_managed_artifact_conflicts(
        conflicted, worktree_path, classifications
    )
    if halt_reason is not None:
        return _abort_with_failure(
            worktree_path, lane.lane_id, classifications, halt_reason,
        )

    for file_path in conflicted:
        if file_path.name == _UV_LOCK_FILENAME:
            classifications.append(ConflictClassification(
                file_path=file_path,
                hunk_text="",
                resolution=Auto(merged_text="", rule_id=RULE_ID_UVLOCK),
            ))
            uvlock_seen = True
            continue

        file_classifications, is_init, halt_reason = _process_conflicted_file(
            file_path, worktree_path,
        )
        classifications.extend(file_classifications)
        if halt_reason is not None:
            return _abort_with_failure(
                worktree_path, lane.lane_id, classifications, halt_reason,
            )
        if is_init:
            init_py_touched.append(file_path)

    return _finalize_auto_rebase(
        lane.lane_id, worktree_path, repo_root,
        classifications, init_py_touched, uvlock_seen,
    )
