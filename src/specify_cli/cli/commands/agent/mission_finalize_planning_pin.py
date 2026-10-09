"""``finalize-tasks`` phase: the planning-commit pin.

Preserve-or-capture, ``--refresh-planning-commit`` and their reports.

Part of the ``mission_finalize`` decomposition (#5627); bodies moved verbatim.
``mission_finalize`` re-exports every name defined here, so historical
``mission_finalize.<name>`` imports and patch targets keep resolving. To keep
those patches *intercepting*, calls to a patched name or to a function owned by
another finalize module go through a lazy in-function
``from specify_cli.cli.commands.agent import mission_finalize as _mf`` import
(cycle-safe: never at module scope) -- the same seam-bridge idiom
``tasks_shared`` uses.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, NoReturn, cast

import typer


if TYPE_CHECKING:
    from specify_cli.coordination.commit_router import CommitRouterResult
from kernel.git import GitCommandError, StatusEntry, changed_paths
from mission_runtime import MissionArtifactKind
from specify_cli.core.constants import KITTY_SPECS_DIR
from mission_runtime import OwnedCheckout
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.planning_commit_classify import PinClass
from specify_cli.status import BootstrapResult, Lane

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.mission_finalize_bootstrap import _BootstrapState
    from specify_cli.cli.commands.agent.mission_finalize_validation import _DependencyResolution
from specify_cli.cli.commands.agent.mission_finalize_branch_contract import TargetBranchPersistOutcome
from specify_cli.cli.commands.agent.mission_finalize_commit import _CommitOutcome


def _resolve_status_read_dir(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> Path:
    """Resolve the coordination-aware status read dir for ``mission_slug``.

    The single recipe for "where does finalize read this mission's status
    from": the placement seam's ``STATUS_STATE`` read dir for an owned
    checkout, otherwise :func:`resolve_status_surface_with_anchor` (the same
    authority ``implement.py`` uses).

    It applies **no** failure policy: ``FileNotFoundError``, ``ValueError``,
    ``StatusReadPathNotFound`` and ``CoordinationBranchDeleted`` propagate
    unchanged. Callers own the policy -- :func:`_execution_has_begun` degrades
    to "not begun", a fail-closed caller refuses.
    """
    from specify_cli.coordination.surface_resolver import resolve_status_surface_with_anchor

    if owned is not None:
        from mission_runtime import placement_seam

        return placement_seam(
            owned.repository_root,
            mission_slug,
            owned=owned,
        ).read_dir(MissionArtifactKind.STATUS_STATE)
    read_dir: Path = resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir
    return read_dir


def _execution_has_begun(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> bool:
    """#3311 T014: read-only "has execution begun" signal for the finalize gate.

    MANDATORY reader recipe: resolve the coord-aware status read dir via
    :func:`resolve_status_surface_with_anchor` (the same authority
    ``implement.py`` uses, ``implement.py:1668-1680``), then read lanes
    read-only through :func:`get_all_wp_lanes`. **Never calls
    ``reducer.materialize()``** — that WRITES ``status.json`` to disk, which a
    "read" helper for a gate check must never do (C-005 / the
    read-does-not-write invariant this WP is guarded against).

    ``has_event_log`` gates first: an absent event log means the mission has
    never been finalized/bootstrapped, so execution categorically has not
    begun (a fresh mission, or the very first finalize run).

    Returns:
        ``True`` iff any WP's current lane is something other than
        ``planned`` (claimed, in_progress, for_review, ..., done, blocked,
        canceled). ``False`` when the event log is absent, empty, every
        seeded WP is still ``planned``, or the surface/event log cannot be
        read at all (degrades gracefully like this module's sibling
        ``capture_branch_tip`` — a signal-computation helper must
        never crash the whole ``finalize-tasks`` command over an unreadable
        read-only surface; a corrupted event log is a pre-existing store
        problem `status doctor` surfaces separately, not something this gate
        should newly turn into a hard finalize failure).
    """
    from specify_cli.coordination.surface_resolver import (
        CoordinationBranchDeleted,
        StatusReadPathNotFound,
    )
    from specify_cli.status import StoreError, get_all_wp_lanes, has_event_log

    try:
        read_dir = _resolve_status_read_dir(repo_root, mission_slug, owned=owned)
    except (FileNotFoundError, ValueError, StatusReadPathNotFound, CoordinationBranchDeleted):
        # Surface resolution failed closed (no meta.json / malformed meta / an
        # unresolvable coord surface). No event log can be read from an
        # unresolvable surface either, so this degrades to the same
        # "not begun" answer ``has_event_log``'s absence produces below.
        return False
    if not has_event_log(read_dir):
        return False
    try:
        lanes = get_all_wp_lanes(read_dir)
    except StoreError:
        # Corrupted/malformed event log content. Degrade to "not begun"
        # rather than raise — see the docstring's graceful-degradation note.
        return False
    return any(lane != Lane.PLANNED for lane in lanes.values())


@dataclass(frozen=True)
class PlanningCommitResolution:
    """#4141: the outcome of this run's ``planning_commit_sha`` decision.

    Carries the resolved SHA plus the provenance a refresh decision needs —
    the previously recorded SHA and the ``target_branch`` tip it was compared
    against — so ``_compute_and_write_lanes`` can report the decision on the
    console and ``_emit_success_report`` can carry it in the ``--json``
    payload without re-reading git or ``lanes.json`` a second time.

    ``action`` is one of:

    * ``"captured"`` — execution has not begun; the branch tip was captured
      (the historical pre-execution behavior, unchanged by #4141).
    * ``"preserved"`` — execution has begun and no ``--refresh-planning-commit``
      was supplied; the previously recorded SHA is preserved (#3311).
    * ``"refreshed"`` — the operator explicitly requested
      ``--refresh-planning-commit`` and the recorded pin is being re-pointed
      to the target-branch tip. Before execution begins, the old pin is kept
      as the compare-and-swap expectation; after execution begins, the tip is
      captured only after the advance-only ancestor check passes (orphaned
      pins require the separate ``--allow-orphaned`` path).
    * ``"repinned"`` — execution has begun and the operator supplied both
      ``--refresh-planning-commit --allow-orphaned``; the recorded SHA was a
      proven ORPHAN (present, not an ancestor — the mid-mission-rebase
      shape, #4827) and was re-pointed to the target-branch tip.
    """

    sha: str | None
    action: str
    previous_sha: str | None = None
    branch_tip: str | None = None
    #: WP15 cycle 2 (B7, contracts/commit-outcome.md): the
    #: ``planning_commit_classify.PinClass`` value (as its ``str`` form) the
    #: no-flag AUTOMATIC decision classified the recorded pin as, when that
    #: path ran. ``None`` for the pre-execution ``"captured"`` action (no
    #: pin was classified) and for the explicit ``--refresh-planning-commit``
    #: path (classified by a DIFFERENT decision function,
    #: ``_resolve_refresh_planning_commit_decision``, not surfaced here).
    pin_class: str | None = None
    #: A short, machine-readable reason code for why the AUTOMATIC decision
    #: landed on its action -- currently only populated for
    #: ``"kept_with_warning"`` (the pin class name, e.g. ``"foreign"``).
    refusal_reason: str | None = None


@dataclass(frozen=True)
class _PrimaryPinRefreshCommit:
    """Preflighted inputs for one primary-only planning-pin commit."""

    primary_root: Path
    worktree_root: Path
    owned: OwnedCheckout | None
    lanes_path: Path
    files: tuple[Path, ...]
    message: str
    new_sha: str
    expected_parent_sha: str


def _planning_pin_change(
    planning_dir: Path,
    planning_sha: PlanningCommitResolution | None,
) -> dict[str, object] | None:
    """Describe the lanes.json pin delta a refresh would write, if any."""
    if planning_sha is None:
        return None

    from specify_cli.lanes.persistence import read_lanes_json

    existing = read_lanes_json(planning_dir)
    previous = existing.planning_commit_sha if existing is not None else None
    if previous == planning_sha.sha:
        return None
    return {
        "artifact": "lanes.json",
        "changes": {"planning_commit_sha": {"from": previous, "to": planning_sha.sha}},
    }


_PLANNING_REFRESH_STATUS_BY_ACTION: Final[dict[str, str]] = {
    "preserved": "preserved",
    "refreshed": "refreshed",
    "kept_with_warning": "kept_with_warning",
}


def _planning_commit_refresh_payload(
    planning_sha: PlanningCommitResolution | None,
) -> dict[str, object] | None:
    """Build the additive ``planning_commit_refresh`` JSON field (FR-012, contracts/commit-outcome.md).

    Populated only for the three actions the AUTOMATIC (no-flag) decision
    path can resolve once execution has begun (preserved/refreshed/
    kept_with_warning) — ``None`` for a pre-execution ``"captured"`` run (no
    pin was yet recorded to refresh) and for the explicit
    ``--refresh-planning-commit``/``--allow-orphaned`` path (``"refreshed"``/
    ``"repinned"``), which keeps reporting through the pre-existing
    ``planning_commit`` field only (contract: "An explicit
    --refresh-planning-commit keeps its existing refusals"). An orphaned pin
    never reaches here — it fails closed before any write (#4827).

    WP15 cycle 2 (B7/C2-1, contracts/commit-outcome.md): the payload also
    carries ``pin_class`` (the recorded pin's ``PinClass``, as classified by
    the automatic decision) and ``reason`` (populated only for
    ``kept_with_warning``, where it names WHY the automatic refresh could not
    proceed). The contract's INDETERMINATE row (``kept_with_warning`` for an
    uncapturable tip) is implemented exactly as the contract states, per the
    orchestrator's C2-1 ruling: INDETERMINATE is reported as a VISIBLE
    ``kept_with_warning`` with ``reason="indeterminate_tip_uncapturable"``,
    never a silent ``preserved``.
    """
    if planning_sha is None:
        return None
    status = _PLANNING_REFRESH_STATUS_BY_ACTION.get(planning_sha.action)
    if status is None:
        return None
    return {
        "status": status,
        "recorded": planning_sha.previous_sha,
        "candidate": planning_sha.branch_tip,
        "pin_class": planning_sha.pin_class,
        "reason": planning_sha.refusal_reason,
    }


def _planning_commit_payload(
    planning_sha: PlanningCommitResolution | None,
    lanes_manifest: LanesManifest | None,
) -> dict[str, object]:
    """Build the one JSON representation of finalize's planning-pin decision."""
    resolved_sha = planning_sha.sha if planning_sha is not None else (lanes_manifest.planning_commit_sha if lanes_manifest is not None else None)
    return {
        "sha": resolved_sha,
        "action": planning_sha.action if planning_sha is not None else None,
        "previous_sha": planning_sha.previous_sha if planning_sha is not None else None,
        "branch_tip": planning_sha.branch_tip if planning_sha is not None else None,
    }


def _validate_only_planning_preview(
    planning_dir: Path,
    existing_changes: list[dict[str, object]],
    planning_sha: PlanningCommitResolution | None,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    """Combine bootstrap changes with the lanes pin delta for dry-run output."""
    pin_change = _planning_pin_change(planning_dir, planning_sha)
    would_modify = [*existing_changes]
    if pin_change is not None:
        would_modify.append(pin_change)
    return would_modify, pin_change


def _add_planning_commit_to_validation_report(
    report: dict[str, object],
    planning_sha: PlanningCommitResolution | None,
) -> None:
    """Add the canonical pin decision to validate-only JSON when requested."""
    if planning_sha is not None:
        report["planning_commit"] = _planning_commit_payload(planning_sha, None)


def _report_validate_only_pin_change(
    pin_change: dict[str, object] | None,
    planning_sha: PlanningCommitResolution | None,
) -> None:
    """Show the lanes pin delta in human-mode validate-only output."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if pin_change is None or planning_sha is None:
        return
    _mf.console.print(f"  Would refresh planning_commit_sha in lanes.json: {planning_sha.previous_sha or '<unset>'} -> {planning_sha.sha or '<unset>'}")


def _refuse_planning_sha_refresh(error_msg: str, *, json_output: bool) -> NoReturn:
    """#4141: emit a refresh refusal diagnostic and exit before any write.

    Raised from inside :func:`_preserve_or_capture_planning_commit_sha`
    BEFORE ``write_lanes_json`` runs, so a refused refresh leaves the on-disk
    ``lanes.json`` (and its recorded ``planning_commit_sha``) untouched.
    Never returns — always raises ``typer.Exit(1)``.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if json_output:
        _mf._emit_json({"error": error_msg})
    else:
        _mf.console.print(f"[red]Error:[/red] {error_msg}")
    raise typer.Exit(1)


def _resolve_refresh_planning_commit_decision(
    *,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    recorded: str | None,
    tip: str | None,
    allow_orphaned: bool,
    json_output: bool,
) -> PlanningCommitResolution:
    """#4141/#4827: resolve the ``--refresh-planning-commit`` branch.

    Advance-only by default (the #4141 contract, unchanged): an ADVANCED
    recorded SHA (an ancestor of the tip, or no recorded SHA at all to
    compare) refreshes unconditionally. ``--allow-orphaned`` additionally
    permits re-pointing a PROVEN ORPHANED pin (present in the object store,
    unreachable from the tip — the mid-mission-rebase shape, #4827); without
    it an orphan is refused with a message that still contains the substring
    "not an ancestor" (keeps the #4141
    ``test_refresh_refused_when_recorded_sha_not_ancestor`` fixture green — it
    exercises exactly this shape per research.md D3). A FOREIGN (absent)
    object is refused regardless of ``--allow-orphaned`` — there is nothing
    to re-point to; the operator must investigate how it was recorded.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if tip is None:
        _refuse_planning_sha_refresh(
            f"Cannot refresh planning_commit_sha for mission {mission_slug!r}: "
            f"the tip of target branch {target_branch!r} could not be captured. "
            "Refusing to refresh rather than silently preserve or guess.",
            json_output=json_output,
        )
    pin_class = _mf.classify_recorded_pin(repo_root, recorded, tip)
    if pin_class is PinClass.FOREIGN:
        _refuse_planning_sha_refresh(
            f"Cannot refresh planning_commit_sha for mission {mission_slug!r}: the recorded "
            f"SHA {recorded} is not present in this repository (object absent, not merely "
            "unreachable). Refusing to re-point to a SHA that cannot be inspected; investigate "
            "how it was recorded.",
            json_output=json_output,
        )
    if pin_class is PinClass.ORPHANED and not allow_orphaned:
        _refuse_planning_sha_refresh(
            f"Cannot refresh planning_commit_sha for mission {mission_slug!r}: the recorded "
            f"SHA {recorded} is not an ancestor of the {target_branch!r} tip {tip}. If this is a "
            "deliberate mid-mission rebase (the recorded commit is still present, just no longer "
            "reachable from the tip), re-run with --refresh-planning-commit --allow-orphaned to "
            "re-point to the live tip. Otherwise the planning history was rewritten/diverged "
            "rather than advanced by an amendment; resolve the divergence manually. Refusing to "
            "re-point.",
            json_output=json_output,
        )
    action = "repinned" if pin_class is PinClass.ORPHANED else "refreshed"
    return PlanningCommitResolution(sha=tip, action=action, previous_sha=recorded, branch_tip=tip)


def _refuse_planning_pin_refresh(reason: str, *, json_output: bool) -> NoReturn:
    """Fail closed before or during a primary-only pin refresh."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    message = f"Cannot refresh planning_commit_sha safely: {reason}"
    if json_output:
        _mf._emit_json({"error": message, "error_code": "PLANNING_REFRESH_FAIL_CLOSED"})
    else:
        _mf.console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _refresh_worktree_status_findings(
    primary_root: Path,
    primary_worktree: Path,
    mission_slug: str,
) -> list[str]:
    """Inspect both partitions without materializing a coordination worktree."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    findings: list[str] = []
    primary_status, status_error = _read_refresh_worktree_status(primary_worktree)
    if status_error is not None:
        findings.append(f"primary worktree status could not be inspected: {status_error}")
    elif primary_status:
        findings.append(f"primary worktree has pending changes: {_render_pending_entries(primary_status)}")

    from mission_runtime import placement_seam, routes_through_coordination, resolve_mid8, resolve_topology

    if not routes_through_coordination(resolve_topology(primary_root, mission_slug)):
        return findings

    meta_dir = placement_seam(primary_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    meta = _mf.load_meta_fail_closed(meta_dir) or {}
    raw_mission_id = meta.get("mission_id")
    if not isinstance(raw_mission_id, str):
        findings.append("coordination worktree status could not be inspected without writing mission metadata")
        return findings
    mid8 = resolve_mid8(mission_slug, mission_id=raw_mission_id)
    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_worktree = CoordinationWorkspace.worktree_path(primary_root, mission_slug, mid8)
    if not coord_worktree.exists():
        return findings
    coord_status, status_error = _read_refresh_worktree_status(coord_worktree)
    if status_error is not None:
        findings.append(f"coordination worktree status could not be inspected: {status_error}")
    elif coord_status:
        findings.append(f"coordination worktree has pending status/history changes: {_render_pending_entries(coord_status)}")
    return findings


def _refresh_worktree_status_error(
    primary_root: Path,
    primary_worktree: Path,
    mission_slug: str,
) -> str | None:
    """Return the first blocker from a read-only status inspection of both partitions."""
    findings = _refresh_worktree_status_findings(primary_root, primary_worktree, mission_slug)
    return findings[0] if findings else None


def _report_refresh_status_findings(
    findings: list[str] | None,
    planning_sha: PlanningCommitResolution | None,
) -> None:
    """Explain when pending partition status will block a mutating refresh."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if planning_sha is None:
        return
    if findings:
        _mf.console.print("[yellow]⚠[/yellow] Mutating refresh would refuse on status preflight findings:")
        for finding in findings:
            _mf.console.print(f"  - {finding}")
        return
    _mf.console.print("  Mutating refresh status preflight: no pending primary or coordination changes")


def _render_pending_entries(entries: tuple[StatusEntry, ...]) -> str:
    """One display line per pending entry (for a finding message; never parsed back)."""
    return "\n".join(entry.display() for entry in entries)


def _read_refresh_worktree_status(worktree: Path) -> tuple[tuple[StatusEntry, ...] | None, str | None]:
    """Return the pending status entries and any diagnostic from a read-only Git probe."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    try:
        # ``optional_locks=False``: a read-only probe must not refresh (write) the index.
        return _mf.status_entries(worktree, untracked="all", optional_locks=False), None
    except GitCommandError as exc:
        # Guard: a failed probe is reported as a blocking finding, never as "clean".
        detail = exc.stderr.strip()
        return None, f"refresh could not inspect worktree {worktree}: {detail or 'git status failed'}"


def _refresh_branch_contract_error(
    planning_dir: Path,
    target_branch: str,
    target_branch_override: str | None,
) -> str | None:
    """Refuse refresh when ordinary finalize would need a meta.json mutation."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    meta = _mf.load_meta_fail_closed(planning_dir) or {}
    existing_target = meta.get("target_branch")
    if target_branch_override and target_branch_override.strip() and existing_target != target_branch:
        return "a target-branch override would also change primary meta.json"
    if meta.get("pr_bound") and existing_target != target_branch:
        return "legacy PR-bound metadata needs a primary meta.json repair"
    return None


def _preflight_refresh_planning_commit(
    repo_root: Path,
    planning_dir: Path,
    mission_slug: str,
    target_branch: str,
    *,
    target_branch_override: str | None,
    owned: OwnedCheckout | None,
    json_output: bool,
) -> None:
    """Read-only guard run before finalize can write files or lifecycle events."""
    contract_error = _refresh_branch_contract_error(planning_dir, target_branch, target_branch_override)
    if contract_error is not None:
        _refuse_planning_pin_refresh(contract_error, json_output=json_output)
    primary_root = owned.repository_root if owned else repo_root
    primary_worktree = owned.owned_root if owned else repo_root
    surface_error = _refresh_worktree_status_error(primary_root, primary_worktree, mission_slug)
    if surface_error is not None:
        _refuse_planning_pin_refresh(surface_error, json_output=json_output)


def _prepare_primary_pin_refresh_commit(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    new_sha: str,
    *,
    json_output: bool,
    owned: OwnedCheckout | None,
) -> _PrimaryPinRefreshCommit:
    """Resolve, preflight, and tip-check the one primary candidate commit."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from mission_runtime import is_primary_artifact_kind, placement_seam
    from specify_cli.git.commit_helpers import preflight_commit

    primary_root = owned.repository_root if owned else repo_root
    worktree_root = owned.owned_root if owned else repo_root
    lanes_path = planning_dir / "lanes.json"
    destination = placement_seam(
        primary_root,
        mission_slug,
        owned=owned,
    ).write_target(MissionArtifactKind.LANE_STATE)
    if not is_primary_artifact_kind(MissionArtifactKind.LANE_STATE) or destination.ref != target_branch:
        _refuse_planning_pin_refresh("lanes.json does not resolve to the planning target branch", json_output=json_output)

    files = tuple(owned.files([lanes_path])) if owned else (lanes_path,)
    message = _finalize_bookkeeping_commit_message(mission_slug)
    surface_error = _refresh_worktree_status_error(primary_root, worktree_root, mission_slug)
    if surface_error is not None:
        _refuse_planning_pin_refresh(surface_error, json_output=json_output)
    try:
        preflight_commit(
            repo_root=primary_root,
            worktree_root=worktree_root,
            target=destination,
            message=message,
            paths=files,
            owned=owned,
        )
    except Exception as exc:  # noqa: BLE001 — fail before the lanes manifest write
        _refuse_planning_pin_refresh(f"primary lanes.json commit preflight failed: {exc}", json_output=json_output)

    expected_tip = planning_sha.branch_tip or planning_sha.sha
    if expected_tip is None:
        _refuse_planning_pin_refresh("the captured planning parent SHA is missing", json_output=json_output)
    current_tip = _mf.capture_branch_tip(primary_root, target_branch)
    if current_tip != expected_tip:
        _refuse_planning_pin_refresh(
            f"planning target {target_branch!r} moved after pin capture ({expected_tip} -> {current_tip}); retry against the new tip",
            json_output=json_output,
        )

    return _PrimaryPinRefreshCommit(
        primary_root=primary_root,
        worktree_root=worktree_root,
        owned=owned,
        lanes_path=lanes_path,
        files=files,
        message=message,
        new_sha=new_sha,
        expected_parent_sha=expected_tip,
    )


def _commit_planning_pin_refresh(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    *,
    tasks_md_stale: bool,
    json_output: bool,
    owned: OwnedCheckout | None,
) -> None:
    """Commit a clean refresh as a single primary lanes.json write."""
    if state.would_modify:
        _refuse_planning_pin_refresh("WP frontmatter also needs finalization", json_output=json_output)
    if tasks_md_stale:
        _refuse_planning_pin_refresh("tasks.md would need regeneration", json_output=json_output)
    if bootstrap_result.newly_seeded:
        _refuse_planning_pin_refresh("canonical coordination status would need bootstrap writes", json_output=json_output)

    from specify_cli.lanes.persistence import lanes_json_lock

    with lanes_json_lock(planning_dir):
        _commit_planning_pin_refresh_locked(
            planning_dir,
            repo_root,
            mission_slug,
            target_branch,
            planning_sha,
            state,
            dep_resolution,
            bootstrap_result,
            json_output=json_output,
            owned=owned,
        )


def _guard_lanes_bytes_unchanged_before_commit(lanes_path: Path, expected_bytes: bytes) -> None:
    """WP15/T004 campsite: the final compare-and-swap guard before the pin-refresh commit.

    Extracted verbatim from :func:`_commit_planning_pin_refresh_locked` (the
    tidy-first first commit) -- the LAST read of ``lanes_path`` before
    ``commit_for_mission`` runs, so a concurrent writer that landed between
    ``write_lanes_json`` and this exact instant is caught instead of silently
    overwritten. Preserves compare-and-swap semantics exactly: raises
    ``RuntimeError`` (never returns a status) so the caller's existing
    ``except Exception`` handler restores the original bytes and reports one
    real, single-ref outcome -- this helper has no restore/report
    responsibility of its own.
    """
    if lanes_path.read_bytes() != expected_bytes:
        raise RuntimeError("lanes.json changed before the conditional commit; concurrent content was left untouched")


def _finalize_pin_refresh_commit_outcome(
    result: CommitRouterResult,
    plan: _PrimaryPinRefreshCommit,
    *,
    old_lanes_bytes: bytes,
    candidate_lanes_bytes: bytes,
    json_output: bool,
) -> _CommitOutcome:
    """WP15/T082/T004 (cycle 2 B10 campsite): interpret ``commit_for_mission``'s
    result for the pin-only refresh commit -- extracted out of
    :func:`_commit_planning_pin_refresh_locked` to keep it under the C901
    ceiling. Renders the shared commit-outcome surfaces (contract rule 6) on
    EVERY outcome arm, success or refusal, and derives the refusal decision
    from :func:`~specify_cli.coordination.commit_outcome.commit_outcome_exit_code`
    (never the legacy ``result.status`` alone) -- except for the
    pin-refresh-SPECIFIC ``"unchanged"`` anomaly (see the inline note below),
    which is a LOCAL invariant this single-ref commit owns, not something the
    shared exit-code rule governs. Never returns on a refusal
    (:func:`_refuse_planning_pin_refresh` is ``NoReturn``).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.coordination.commit_outcome import commit_outcome_exit_code, commit_outcome_payload, render_commit_outcome

    commit_outcome = _CommitOutcome()
    commit_outcome.commit_surfaces = cast("list[dict[str, object]]", commit_outcome_payload(result)["surfaces"])
    commit_outcome.rendered_lines = render_commit_outcome(result)
    if not json_output:
        for line in commit_outcome.rendered_lines:
            _mf.console.print(line, markup=False)

    # This single-ref pin commit has exactly one PRIMARY surface, so
    # ``commit_outcome_exit_code`` (contract rule 5: nonzero iff any surface
    # is refused/error) is the correct outcome-consumer decision for a
    # genuine router refusal/error. ``"unchanged"`` is handled as its OWN,
    # LOCAL anomaly first: this call just wrote a NEW sha to lanes.json, so
    # the router reporting no diff means a concurrent writer raced us --
    # that is refused regardless of what the shared exit-code rule would say
    # about an "unchanged" status (which is a legitimate success elsewhere).
    if result.status == "unchanged":
        restore_error = _restore_planning_pin_candidate(plan.lanes_path, candidate_lanes_bytes, old_lanes_bytes)
        detail = "primary lanes.json changed but the commit seam reported unchanged"
        if restore_error is not None:
            detail = f"{detail}; {restore_error}"
        _refuse_planning_pin_refresh(detail, json_output=json_output)
    if commit_outcome_exit_code(result) != 0:
        restore_error = _restore_planning_pin_candidate(plan.lanes_path, candidate_lanes_bytes, old_lanes_bytes)
        detail = result.diagnostic or "primary lanes.json commit was refused"
        if restore_error is not None:
            detail = f"{detail}; {restore_error}"
        _refuse_planning_pin_refresh(detail, json_output=json_output)

    commit_outcome.commit_created = True
    commit_outcome.commit_hash = result.commit_hash
    commit_outcome.commit_hashes = [{"branch": ref, "hash": sha} for ref, sha in result.commit_hashes]
    commit_outcome.diagnostic = result.diagnostic
    committed_root = plan.worktree_root
    commit_outcome.files_committed = [str(path.relative_to(committed_root)) for path in plan.files]
    if result.diagnostic is not None and not json_output:
        _mf.console.print(f"[yellow]Warning:[/yellow] {result.diagnostic}")
    return commit_outcome


def _commit_planning_pin_refresh_locked(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    *,
    json_output: bool,
    owned: OwnedCheckout | None,
) -> None:
    """Validate byte identity and commit while holding the lanes writer lock."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy
    from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json

    lanes_path = planning_dir / "lanes.json"
    try:
        old_lanes_bytes = lanes_path.read_bytes()
    except OSError as exc:
        _refuse_planning_pin_refresh(f"lanes.json could not be read: {exc}", json_output=json_output)
    lanes_manifest = read_lanes_json(planning_dir)
    if lanes_manifest is None:
        _refuse_planning_pin_refresh("lanes.json is missing or unreadable", json_output=json_output)
    if lanes_path.read_bytes() != old_lanes_bytes:
        _refuse_planning_pin_refresh("lanes.json changed while its manifest was being read", json_output=json_output)
    if lanes_manifest.planning_commit_sha != planning_sha.previous_sha:
        _refuse_planning_pin_refresh("lanes.json changed after the planning pin was captured", json_output=json_output)
    if planning_sha.sha is None:
        _refuse_planning_pin_refresh("the target branch tip could not be captured", json_output=json_output)

    if lanes_manifest.planning_commit_sha == planning_sha.sha:
        _report_planning_pin_refresh_success(
            planning_dir,
            target_branch,
            planning_sha,
            state,
            dep_resolution,
            bootstrap_result,
            lanes_manifest,
            _CommitOutcome(),
            json_output=json_output,
            unchanged=True,
        )
        return

    plan = _mf._prepare_primary_pin_refresh_commit(
        planning_dir,
        repo_root,
        mission_slug,
        target_branch,
        planning_sha,
        planning_sha.sha,
        json_output=json_output,
        owned=owned,
    )

    if plan.lanes_path.read_bytes() != old_lanes_bytes:
        _refuse_planning_pin_refresh("lanes.json changed after refresh preparation; concurrent content was left untouched", json_output=json_output)
    lanes_manifest.planning_commit_sha = plan.new_sha
    write_lanes_json(planning_dir, lanes_manifest)
    candidate_lanes_bytes = plan.lanes_path.read_bytes()
    try:
        _guard_lanes_bytes_unchanged_before_commit(plan.lanes_path, candidate_lanes_bytes)
        result = commit_for_mission(
            repo_root=plan.primary_root,
            mission_slug=mission_slug,
            files=plan.files,
            message=plan.message,
            policy=ProtectionPolicy.resolve(plan.primary_root),
            kind=MissionArtifactKind.LANE_STATE,
            target_branch=target_branch,
            owned=plan.owned,
            expected_parent_sha=plan.expected_parent_sha,
            expected_path_bytes={plan.lanes_path: candidate_lanes_bytes},
        )
    except Exception as exc:  # noqa: BLE001 — report the real one-ref outcome
        restore_error = _restore_planning_pin_candidate(plan.lanes_path, candidate_lanes_bytes, old_lanes_bytes)
        detail = f"primary lanes.json commit failed: {exc}"
        if restore_error is not None:
            detail = f"{detail}; {restore_error}"
        _refuse_planning_pin_refresh(detail, json_output=json_output)

    commit_outcome = _finalize_pin_refresh_commit_outcome(
        result,
        plan,
        old_lanes_bytes=old_lanes_bytes,
        candidate_lanes_bytes=candidate_lanes_bytes,
        json_output=json_output,
    )

    _report_planning_pin_refresh_success(
        planning_dir,
        target_branch,
        planning_sha,
        state,
        dep_resolution,
        bootstrap_result,
        lanes_manifest,
        commit_outcome,
        json_output=json_output,
        unchanged=False,
    )


def _report_planning_pin_refresh_success(
    planning_dir: Path,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    lanes_manifest: LanesManifest,
    commit_outcome: _CommitOutcome,
    *,
    json_output: bool,
    unchanged: bool,
) -> None:
    """Report a pin refresh in the selected output mode.

    WP13-review binding correction (applied here too): when
    ``commit_outcome.commit_surfaces`` is populated, render it through the
    SAME shared trio the main commit pipeline uses.

    WP15 cycle 2 (B10): the text-mode, ``not unchanged`` (real commit
    attempt) surface lines are printed by the CALLER
    (:func:`_commit_planning_pin_refresh_locked`) BEFORE this function runs
    at all -- on EVERY outcome arm, success or refusal -- so they are never
    printed twice here.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if json_output:
        _mf._emit_success_report(
            planning_dir / "tasks",
            state,
            commit_outcome,
            dep_resolution,
            bootstrap_result,
            lanes_manifest,
            target_branch_persist=TargetBranchPersistOutcome(persisted=False),
            planning_sha=planning_sha,
        )
    elif unchanged:
        _mf.console.print(f"[green]✓[/green] planning_commit_sha already matches the {target_branch} tip ({planning_sha.sha}); no commit needed")
    else:
        _report_planning_sha_decision(target_branch, planning_sha, json_output=False)


def _restore_planning_pin_candidate(
    lanes_path: Path,
    candidate_bytes: bytes,
    original_bytes: bytes,
) -> str | None:
    """CAS-restore our lanes candidate without overwriting concurrent edits."""
    from specify_cli.lanes.persistence import lanes_json_lock, write_lanes_json_if_bytes_match

    with lanes_json_lock(lanes_path.parent):
        try:
            current_bytes = lanes_path.read_bytes()
        except OSError as exc:
            return f"could not inspect lanes.json for rollback: {exc}"
        if current_bytes != candidate_bytes:
            return "lanes.json changed during the failed commit and was left untouched"
        try:
            if not write_lanes_json_if_bytes_match(lanes_path.parent, candidate_bytes, original_bytes):
                return "lanes.json changed during rollback and was left untouched"
        except OSError as exc:
            return f"could not restore the original lanes.json: {exc}"
    return None


def _planning_changed_since_pin(
    repo_root: Path,
    mission_slug: str,
    recorded_sha: str | None,
    target_tip: str | None,
) -> bool:
    """FR-012 (T083): True iff a PRIMARY-partition planning file changed between ``recorded_sha`` and ``target_tip``.

    Scoped to this Mission's own directory (``kitty-specs/<mission_slug>``)
    and classified per changed path via the single file->kind authority
    (:func:`~mission_runtime.kind_for_mission_file`) so only genuine
    PRIMARY-partition planning content (spec/plan/tasks/WP files, …) counts —
    never a COORD-kind residual (status/matrices) that might incidentally
    live under the same directory tree. ``lanes.json`` is explicitly excluded
    even though it classifies PRIMARY: it is finalize's OWN pin-refresh
    output, so counting it would make the automatic refresh re-trigger itself
    on its own prior commit (research D16's self-trigger hazard).

    Returns ``False`` (nothing to compare) when either endpoint is missing or
    the two endpoints are identical — never raises on a git probe failure,
    degrading to "no change detected" (the safe default: callers only use
    this to decide whether to ATTEMPT a refresh, never to skip a safety
    check).
    """
    if recorded_sha is None or target_tip is None or recorded_sha == target_tip:
        return False
    from mission_runtime import is_primary_artifact_kind, kind_for_mission_file

    try:
        changed = changed_paths(repo_root, recorded_sha, target_tip, pathspecs=(f"{KITTY_SPECS_DIR}/{mission_slug}",))
    except GitCommandError:
        return False
    for git_path in changed:
        changed_path = str(git_path)
        if not changed_path or PurePosixPath(changed_path).name == "lanes.json":
            continue
        kind = kind_for_mission_file(changed_path, mission_slug=mission_slug)
        if kind is not None and is_primary_artifact_kind(kind):
            return True
    return False


def _resolve_preserve_planning_commit_decision(
    *,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    recorded: str | None,
    tip: str | None,
    json_output: bool,
) -> PlanningCommitResolution:
    """#3311/#4827/FR-012 (T083/T084): resolve the no-flag (preserve/auto-refresh) branch.

    Fails closed BEFORE any write only for a PROVEN ORPHAN against a
    capturable tip (D3/D4): the tool must not silently keep every
    subsequently allocated lane merging a dead base (#4827, unchanged by this
    WP — ``test_plain_finalize_fails_closed_on_orphaned_pin`` stays green).

    For every other pin class, FR-012's default automatic refresh applies:
    when a PRIMARY planning file changed since the recorded pin for a reason
    OTHER than finalize's own prior bookkeeping commits
    (:func:`_planning_changed_since_pin` AND NOT
    :func:`_drift_is_finalize_bookkeeping_only` — the SAME #4178/D7(b)
    distinction the preserve-path drift WARN already relies on, reused here
    rather than re-implemented: without it, finalize's OWN first
    ``tasks.md``/``meta.json``/WP-frontmatter bookkeeping commit — landed
    AFTER the tip was captured for ``"captured"`` — would look like a
    "planning change" on every subsequent re-finalize with zero operator
    amendment), an ADVANCED pin (a provable safe advance -- the recorded
    object IS present and diffable) is refreshed to the tip
    (``action="refreshed"``). A FOREIGN pin's recorded object is absent
    entirely, so no path-scoped diff can even run against it; the automatic
    refresh cannot prove anything about it, so ANY tip advance over a FOREIGN
    pin is reported with a WARNING rather than failing closed or silently
    refreshing (ruling Q6, ``action="kept_with_warning"`` — the warning
    itself is printed later by :func:`_report_planning_sha_decision`, AFTER
    the write, per the #4178 print-after-write convention). An INDETERMINATE
    pin (an uncapturable tip, e.g. a non-git workspace, or no recorded SHA at
    all) is ALSO reported as ``action="kept_with_warning"`` (WP15 cycle 2,
    C2-1, orchestrator ruling): the classifier's own docstring says callers
    "degrade to their own historical preserve behavior", but finalize
    specifically must not silently swallow an uncapturable tip — it gets a
    dedicated ``refusal_reason="indeterminate_tip_uncapturable"`` distinct
    from a classified FOREIGN refusal. No genuine planning change at all
    degrades to the historical #3311 preserve (``action="preserved"``).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    pin_class = _mf.classify_recorded_pin(repo_root, recorded, tip)
    if pin_class is PinClass.ORPHANED:
        error_msg = (
            f"Cannot re-finalize mission {mission_slug!r}: the recorded planning_commit_sha "
            f"{recorded} is orphaned — present in this repository but not an ancestor of the "
            f"{target_branch!r} tip {tip} (a mid-mission rebase). Lanes would keep merging a dead "
            "base. Re-run with --refresh-planning-commit --allow-orphaned to re-point the "
            "recorded SHA to the live tip, or investigate the divergence manually. Refusing to "
            "write lanes.json."
        )
        if json_output:
            _mf._emit_json({"error": error_msg})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    if pin_class is PinClass.ADVANCED:
        planning_changed = (
            recorded is not None
            and tip is not None
            and _planning_changed_since_pin(repo_root, mission_slug, recorded, tip)
            and not _drift_is_finalize_bookkeeping_only(repo_root, mission_slug, recorded, tip)
        )
        if planning_changed:
            return PlanningCommitResolution(sha=tip, action="refreshed", previous_sha=recorded, branch_tip=tip, pin_class=pin_class.value)
    elif pin_class is PinClass.FOREIGN and recorded != tip:
        return PlanningCommitResolution(
            sha=recorded,
            action="kept_with_warning",
            previous_sha=recorded,
            branch_tip=tip,
            pin_class=pin_class.value,
            refusal_reason=pin_class.value,
        )
    elif pin_class is PinClass.INDETERMINATE:
        # WP15 cycle 2 (C2-1, orchestrator ruling on contracts/commit-outcome.md):
        # the classifier's OWN docstring says callers may degrade silently
        # for INDETERMINATE ("nothing about it can be inspected at all"), but
        # the ruling overrides that for finalize specifically -- a silent
        # `preserved` here would mask a genuinely uncapturable target-branch
        # tip from the operator. Report it as a VISIBLE, non-fatal warning
        # (exit 0) instead, with a dedicated reason code distinct from the
        # bare pin_class value so a consumer can tell "could not classify at
        # all" apart from "classified as FOREIGN and refused".
        return PlanningCommitResolution(
            sha=recorded,
            action="kept_with_warning",
            previous_sha=recorded,
            branch_tip=tip,
            pin_class=pin_class.value,
            refusal_reason="indeterminate_tip_uncapturable",
        )
    return PlanningCommitResolution(sha=recorded, action="preserved", previous_sha=recorded, branch_tip=tip, pin_class=pin_class.value)


def _preserve_or_capture_planning_commit_sha(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    *,
    json_output: bool,
    owned: OwnedCheckout | None = None,
    refresh_planning_commit: bool = False,
    allow_orphaned: bool = False,
) -> PlanningCommitResolution:
    """#3311 T015 / #4141 / #4827: resolve this run's ``planning_commit_sha`` decision.

    ADR ``2026-07-29-1`` / FR-009 freezes the recorded planning-artifact SHA
    into the SAME write ``_compute_and_write_lanes`` performs — no second
    commit, no re-read at lane-allocation time. #3311: once execution has
    begun (:func:`_execution_has_begun` — any WP past ``planned``), a
    re-finalize triggered by an ownership-only amendment must PRESERVE that
    frozen SHA instead of silently re-capturing the CURRENT branch tip, which
    would clobber the established planning provenance a lane worktree may
    already carry a merge-base against. Before execution begins, the
    historical no-flag recompute + re-capture behavior is unchanged — every
    pre-execution re-finalize keeps regenerating freely (C-005). An explicit
    refresh instead retains the existing lanes pin as the compare-and-swap
    expectation and captures the current branch tip, allowing the clean
    primary-only refresh path to report and commit the old-to-new transition.

    Once execution has begun, the recorded SHA is classified against the
    target-branch tip with the shared WP01 authority
    (:func:`specify_cli.lanes.planning_commit_classify.classify_recorded_pin`
    — never a lane worktree HEAD, see that module's C-006 note) and the
    decision is delegated to
    :func:`_resolve_refresh_planning_commit_decision` (``--refresh-planning-
    commit`` supplied) or :func:`_resolve_preserve_planning_commit_decision`
    (the no-flag default). ``--allow-orphaned`` (#4827) is the explicit
    operator assertion required to re-pin a PROVEN ORPHAN (present, not
    reachable — a mid-mission rebase) to the live tip; without it the
    no-flag path fails closed before any write and bare
    ``--refresh-planning-commit`` refuses (advance-only, unchanged #4141
    contract).

    Refuse (raise ``typer.Exit(1)`` before writing any bytes) when the
    requested resolution cannot be done safely: execution has begun yet no
    on-disk ``lanes.json`` exists to read the recorded SHA from (an
    inconsistent state finalize should never reach, since bootstrapping the
    event log itself requires a prior successful finalize run that already
    wrote ``lanes.json``); a refresh was requested but the branch tip could
    not be captured; an execution-begun refresh was requested whose recorded
    SHA is orphaned or foreign; or the no-flag default hit a proven orphan.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    execution_has_begun = _mf._execution_has_begun(repo_root, mission_slug, owned=owned)
    if not execution_has_begun:
        previous_sha: str | None = None
        action = "captured"
        if refresh_planning_commit:
            from specify_cli.lanes.persistence import read_lanes_json

            refreshed_from = read_lanes_json(planning_dir)
            previous_sha = refreshed_from.planning_commit_sha if refreshed_from is not None else None
            action = "refreshed"
        tip = _mf.capture_branch_tip(repo_root, target_branch)
        return PlanningCommitResolution(
            sha=tip,
            action=action,
            previous_sha=previous_sha,
            branch_tip=tip if refresh_planning_commit else None,
        )

    from specify_cli.lanes.persistence import is_execution_wedged, read_lanes_json

    existing: LanesManifest | None = read_lanes_json(planning_dir)
    if is_execution_wedged(execution_has_begun=execution_has_begun, lanes_present=existing is not None):
        error_msg = (
            f"Cannot re-finalize mission {mission_slug!r}: execution has begun "
            "(a WP is past 'planned') but no lanes.json exists on disk to "
            "preserve planning provenance from. Refusing to write a new "
            "lanes.json rather than guess a planning_commit_sha. Run "
            "'spec-kitty doctor mission-state --fix --mission "
            f"{mission_slug}' to rebuild lanes.json from the event log."
        )
        if json_output:
            _mf._emit_json({"error": error_msg})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    # Narrowing note (not a suppression): ``is_execution_wedged`` is opaque to
    # mypy, so unlike the pre-WP01 inline ``if existing is None: raise`` it
    # narrows nothing on its own. We are past the raise above with
    # ``execution_has_begun`` True, so ``is_execution_wedged(...)`` being
    # False here can only mean ``lanes_present`` was True, i.e. ``existing``
    # is not None — assert makes that logical necessity visible to mypy.
    assert existing is not None
    # Type note (not a suppression): this module's [[tool.mypy.overrides]]
    # sets ``follow_imports = "skip"`` for all ``specify_cli.*`` modules (to
    # avoid walking the CLI bootstrap graph), so a single-file mypy invocation
    # loses ``LanesManifest``'s real field types across that import boundary
    # and sees ``existing.planning_commit_sha`` as ``Any`` — assigning ``Any``
    # to ``str | None`` is not an error, so no ignore is needed (the
    # pre-#4141 ``no-any-return`` ignore on the old ``return`` site became
    # unused when this became an assignment). ``planning_commit_sha`` is
    # genuinely ``str | None`` (specify_cli/lanes/models.py); `mypy
    # src/specify_cli/lanes/models.py src/specify_cli/lanes/persistence.py` in
    # isolation reports zero issues.
    recorded: str | None = existing.planning_commit_sha
    # #4827: captured once here (rather than separately inside each resolve_*
    # helper, the pre-#4827 shape) -- both the refresh and preserve branches
    # need the SAME tip snapshot to classify against (C-006).
    tip = _mf.capture_branch_tip(repo_root, target_branch)
    if refresh_planning_commit:
        return _resolve_refresh_planning_commit_decision(
            repo_root=repo_root,
            mission_slug=mission_slug,
            target_branch=target_branch,
            recorded=recorded,
            tip=tip,
            allow_orphaned=allow_orphaned,
            json_output=json_output,
        )
    return _resolve_preserve_planning_commit_decision(
        repo_root=repo_root,
        mission_slug=mission_slug,
        target_branch=target_branch,
        recorded=recorded,
        tip=tip,
        json_output=json_output,
    )


# FR-013 (mission-writer-followups / #5885): finalize's bookkeeping subject
# became "Add tasks for mission <slug>". The pre-change wording is kept here as
# a NAMED legacy constant so the drift check below still recognises a Mission
# finalized BEFORE the rename as finalize's own bookkeeping (no false drift).
# The ``LEGACY`` in the name is the structural exemption the operator-text scan
# (tests/specify_cli/test_no_for_feature_operator_text.py) keys on, so this is
# the single sanctioned "for feature" string that survives the rename.
_LEGACY_FINALIZE_BOOKKEEPING_SUBJECT = "Add tasks for feature {mission_slug}"


def _finalize_bookkeeping_commit_message(mission_slug: str) -> str:
    """Single source for finalize's own bookkeeping commit subject line.

    Used both as the ACTUAL commit message (:func:`_commit_finalize_
    artifacts`) and as the signature :func:`_drift_is_finalize_bookkeeping_
    only` checks for when distinguishing a real planning amendment from
    finalize's own prior re-run commits (#4178 / research.md D7(b)).
    """
    return f"Add tasks for mission {mission_slug}"


def _legacy_finalize_bookkeeping_commit_message(mission_slug: str) -> str:
    """The pre-rename finalize bookkeeping subject (FR-013 back-compat only)."""
    return _LEGACY_FINALIZE_BOOKKEEPING_SUBJECT.format(mission_slug=mission_slug)


def _drift_is_finalize_bookkeeping_only(
    repo_root: Path,
    mission_slug: str,
    recorded_sha: str,
    branch_tip: str,
) -> bool:
    """#4178 / D7(b): True iff every commit between ``recorded_sha`` and
    ``branch_tip`` is finalize's OWN bookkeeping commit for this mission.

    The preserve-path drift WARN exists to catch a genuine planning
    amendment landing mid-execution — not finalize's own prior bookkeeping
    commits advancing the tip on every re-run, which happens unconditionally
    once execution has begun (``planning_commit_sha`` stays frozen while the
    branch keeps moving under finalize's own ``"Add tasks for mission ..."``
    commits (and, for Missions finalized before the #5885 rename, the legacy
    ``"Add tasks for feature ..."`` subject — FR-013). Verified (research.md
    D7): ``_compute_and_write_lanes``
    resolves this run's decision before ``_commit_finalize_artifacts`` lands
    that commit, so a re-finalize with no operator amendment in between still
    sees ``branch_tip != sha`` purely from a PRIOR run's own bookkeeping
    commit — a false positive this check exists to suppress.

    Fails OPEN (returns ``False`` — "real drift, keep warning") on any git
    error or an empty range: this only gates a non-blocking console WARN, and
    hiding a genuine drift signal is worse than an occasional over-warn.
    """

    accepted = {
        _finalize_bookkeeping_commit_message(mission_slug),
        _legacy_finalize_bookkeeping_commit_message(mission_slug),
    }
    result = subprocess.run(
        ["git", "log", "--format=%s", f"{recorded_sha}..{branch_tip}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    subjects = [line for line in result.stdout.splitlines() if line]
    return bool(subjects) and all(subject in accepted for subject in subjects)


def _report_planning_sha_decision(
    target_branch: str,
    planning_sha: PlanningCommitResolution | None,
    *,
    json_output: bool,
    repo_root: Path | None = None,
    mission_slug: str | None = None,
) -> None:
    """#4141/#4827: surface the ``planning_commit_sha`` decision on the console.

    Human-mode only: the ``--json`` success report carries the same decision
    structurally (``planning_commit`` in the payload), and a console print
    would corrupt the machine-readable payload (the same reason the
    coord-staleness WARN is gated on ``not json_output``). ``None`` (the
    historical monkeypatched test seam) reports nothing.

    Always called AFTER ``write_lanes_json`` has already run (#4178
    print-before-write; the caller -- :func:`_compute_and_write_lanes` --
    only reaches this call once ``compute_and_write_lanes`` has returned).

    ``repo_root``/``mission_slug`` are optional (keyword-only, default
    ``None``): when supplied, the preserve-path drift WARN additionally
    suppresses itself when the ONLY commits between the recorded SHA and the
    branch tip are finalize's own bookkeeping commits (#4178 / D7(b), via
    :func:`_drift_is_finalize_bookkeeping_only`). Omitting them keeps the
    pre-#4827 "any drift" behavior for direct unit-level callers of this
    function.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if json_output or planning_sha is None:
        return
    if planning_sha.action == "repinned":
        _mf.console.print(
            f"[green]✓[/green] Re-pinned orphaned planning_commit_sha "
            f"{planning_sha.previous_sha or '(none)'} -> {planning_sha.sha} "
            f"(lanes merge the {target_branch} tip at their next allocation)"
        )
        return
    if planning_sha.action == "refreshed":
        _mf.console.print(
            f"[green]✓[/green] Refreshed planning_commit_sha "
            f"{planning_sha.previous_sha or '(none)'} -> {planning_sha.sha} "
            f"(lanes merge the {target_branch} tip at their next allocation)"
        )
        return
    if planning_sha.action == "kept_with_warning":
        # Ruling Q6 (FR-012/T084): the AUTOMATIC refresh could not prove a
        # safe advance for a non-orphan FOREIGN pin (the recorded object is
        # absent from the repository entirely) or classify an INDETERMINATE
        # one (WP15 cycle 2 C2-1 — an uncapturable tip or no recorded SHA at
        # all, also now reported here rather than degrading silently) — warn
        # and keep the old pin rather than fail closed. Printed here (after
        # ``write_lanes_json`` already ran with the OLD sha unchanged) per
        # the #4178 print-after-write convention this function's docstring
        # documents.
        if planning_sha.refusal_reason == "indeterminate_tip_uncapturable":
            # WP15 cycle 2 (C2-1): both pieces may be missing (that is
            # exactly what makes the pin INDETERMINATE), so the message
            # names whichever is actually absent instead of assuming either
            # is present.
            recorded_desc = planning_sha.previous_sha or "(no pin recorded yet)"
            tip_desc = planning_sha.branch_tip or "(uncapturable)"
            _mf.console.print(
                f"[yellow]⚠[/yellow] planning_commit_sha could not be classified against the "
                f"{target_branch!r} tip: recorded={recorded_desc}, tip={tip_desc} (the target "
                "branch tip could not be resolved -- e.g. a non-git workspace, or the branch "
                "does not exist yet -- or there is no recorded pin to classify); keeping the "
                "recorded pin unchanged. No action is needed unless the target branch is "
                "expected to exist."
            )
            return
        # WP15 cycle 2 (B8): the remedy named below must actually work. A
        # FOREIGN pin's object cannot be inspected at all, so
        # ``--refresh-planning-commit --allow-orphaned`` is REFUSED for it
        # too (``_resolve_refresh_planning_commit_decision`` refuses FOREIGN
        # unconditionally -- ``--allow-orphaned`` only lifts the refusal for
        # a proven ORPHAN, a different, inspectable shape). There is no
        # automated recovery for a genuinely absent object; the message says
        # so instead of pointing at a command that is guaranteed to fail.
        _mf.console.print(
            f"[yellow]⚠[/yellow] planning_commit_sha {planning_sha.previous_sha!r} could not be "
            f"safely auto-refreshed to the {target_branch} tip {planning_sha.branch_tip} "
            "(the recorded commit object is absent from this repository, so it cannot be "
            "verified at all); keeping the recorded pin. This object cannot be re-pointed "
            "automatically -- investigate how it was recorded (e.g. a stale clone or a "
            "pruned object), then correct lanes.json's planning_commit_sha manually once "
            "you have confirmed the right pin."
        )
        return
    if planning_sha.action == "preserved" and planning_sha.sha is not None and planning_sha.branch_tip is not None and planning_sha.branch_tip != planning_sha.sha:
        if (
            repo_root is not None
            and mission_slug is not None
            and _drift_is_finalize_bookkeeping_only(repo_root, mission_slug, planning_sha.sha, planning_sha.branch_tip)
        ):
            return
        _mf.console.print(
            f"[yellow]⚠[/yellow] Planning branch {target_branch} has advanced since "
            f"planning_commit_sha was recorded ({planning_sha.sha} -> tip {planning_sha.branch_tip}); "
            "lanes keep merging the recorded snapshot. If that advance is a legitimate "
            "planning amendment, re-run finalize-tasks with --refresh-planning-commit to re-point it."
        )
