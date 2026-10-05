"""orchestrator-api acceptance and consolidation verbs (#5628).

``accept-mission`` and ``consolidate-mission`` plus the lane-consolidation
preflight, execution and cleanup helpers behind them. Registered on the
app by ``commands.py``.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from specify_cli.acceptance import AcceptanceSummary
    from specify_cli.core.paths import RetentionDecision
    from specify_cli.lanes.models import LanesManifest

import typer

from specify_cli.core.contract_gate import is_allowed_error_code, validate_outbound_payload
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.status import wp_state_for
from specify_cli.status import Lane

from .envelope import (
    make_envelope,
)


from . import _common
from ._common import (
    _HELP_ACTOR,
    _HELP_MISSION_SLUG,
    _emit,
    _fail,
    _planning_read_dir,
)


@dataclass
class _MergePreflightResult:
    target_branch: str
    errors: list[str]


#: Fallback code for a :class:`DestructiveOpRefused` whose real
#: ``error_code`` (``MERGE_UNSAFE_PRIMARY_OFF_TARGET`` /
#: ``MERGE_UNSAFE_PRIMARY_DIRTY`` / ``MERGE_UNSAFE_WORKTREE_DIRTY``) is not
#: (yet) registered in ``upstream_contract.json``'s ``allowed_error_codes`` --
#: that file is a derived artifact of the upstream ``spec-kitty-events`` /
#: ``spec-kitty-saas`` contract (client-repo inversion) and is not this
#: mission's to extend. Reuses the already-registered code this same command
#: emits for every OTHER merge preflight refusal, so the envelope shape stays
#: within contract while the real code survives as diagnostic ``data``
#: (mirrors ``_fail_from_decision_error``'s ``_DECISION_UNREGISTERED_CODE_FALLBACK``
#: pattern -- never a silently-dropped, never a leaked-unregistered code).
_DESTRUCTIVE_OP_REFUSED_FALLBACK = "PREFLIGHT_FAILED"


class MergeTeardownRefused(RuntimeError):
    """A merge that landed, whose post-landing cleanup refused with a stable code (#5613).

    A ``RuntimeError``, so ``consolidate_mission`` envelopes it exactly as before
    (``PREFLIGHT_FAILED``, the message in ``data["errors"]``). The code travels in
    ``data["teardown_error_code"]`` so callers key on it instead of the prose, the
    way :func:`_fail_from_destructive_op_refused` carries ``destructive_op_error_code``.
    """

    def __init__(self, message: str, *, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(message)


class ApprovedBoundRefused(RuntimeError):
    """A lane holds work review did not approve; refused before any lane was consolidated (#5668).

    A ``RuntimeError``, so ``consolidate_mission`` envelopes it as ``PREFLIGHT_FAILED``
    with the message in ``data["errors"]``. The refusal's own code (the leading
    ``CODE:`` of its text) travels in ``data["preflight_error_code"]`` so callers key
    on it instead of the prose; ``None`` for the one refusal that carries no code.
    """

    def __init__(self, message: str, *, error_code: str | None) -> None:
        self.error_code = error_code
        super().__init__(message)


def _fail_from_destructive_op_refused(cmd: str, mission_dir: Path, target_branch: str, exc: DestructiveOpRefused) -> NoReturn:
    """Envelope a :class:`DestructiveOpRefused` refusal instead of letting it
    escape as a raw traceback (#4753 finding B).

    ``merge_mission`` previously caught ONLY ``RuntimeError`` around
    ``_execute_lane_merge`` -- but the pre-mutation safety preflight
    (``guarded_worktree_remove`` / ``assert_worktree_clean``, reached through
    ``_apply_lane_merge_cleanup``) raises ``DestructiveOpRefused``, a plain
    ``Exception`` subclass (C-002: deliberately NOT a ``RuntimeError``, so it
    is never conflated with ``SafeCommitHeadMismatch``). That refusal is
    exactly the module's own destructive-op safety mechanism doing its job --
    it must reach the external orchestrator as a structured failure envelope,
    not a broken JSON-first contract.
    """
    real_code = exc.error_code
    envelope_code = real_code if is_allowed_error_code("orchestrator_api", real_code) else _DESTRUCTIVE_OP_REFUSED_FALLBACK
    data: dict[str, object] = {
        **_common._mission_identity_payload(mission_dir),
        "target_branch": target_branch,
        "errors": [str(exc)],
        "destructive_op_error_code": real_code,
        "remediation": exc.remediation,
    }
    if exc.worktree_path is not None:
        data["worktree_path"] = str(exc.worktree_path)
    if exc.dirty_entries:
        data["dirty_entries"] = list(exc.dirty_entries)
    _fail(cmd, envelope_code, "Merge refused: destructive operation safety check failed", data)


def _resolve_merge_target_branch(main_repo_root: Path, mission_slug: str, target: str | None) -> str:
    """Resolve the branch ``merge-mission`` integrates into.

    Order: explicit ``--target`` > meta ``merge_target_branch`` > meta
    ``target_branch`` > repo default.

    The mission target lives in the PRIMARY-checkout meta.json (like
    ``coordination_branch``), so it is read via ``primary_feature_dir_for_mission``
    — NOT the topology-aware candidate. Under coordination topology that candidate
    resolves to the coordination worktree, whose mission dir has no meta.json; the
    prior code read that surface, missed the mission's ``target_branch``, and
    silently fell back to the repo default (main) — merging into the wrong branch.
    """
    from specify_cli.core.paths import resolve_merge_target_branch

    return resolve_merge_target_branch(main_repo_root, mission_slug, target)[0]


def _build_merge_preflight(
    main_repo_root: Path,
    mission_slug: str,
    target: str | None,
) -> _MergePreflightResult:
    """Validate merge prerequisites and collect machine-readable errors."""
    from specify_cli.core.git_preflight import build_git_preflight_failure_payload, run_git_preflight
    from specify_cli.core.git_ops import run_command
    from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError, require_lanes_json

    resolved_target = _resolve_merge_target_branch(main_repo_root, mission_slug, target)
    errors: list[str] = []

    if (main_repo_root / ".git").exists():
        preflight = run_git_preflight(main_repo_root, check_worktree_list=True)
        if not preflight.passed:
            payload = build_git_preflight_failure_payload(preflight, command_name="orchestrator-api merge-mission")
            errors.append(payload["error"])
            errors.extend(payload.get("remediation", []))

        ret_local, _, _ = run_command(
            ["git", "rev-parse", "--verify", f"refs/heads/{resolved_target}"],
            capture=True,
            check_return=False,
            cwd=main_repo_root,
        )
        ret_remote, _, _ = run_command(
            ["git", "rev-parse", "--verify", f"refs/remotes/origin/{resolved_target}"],
            capture=True,
            check_return=False,
            cwd=main_repo_root,
        )
        if ret_local != 0 and ret_remote != 0:
            errors.append(f"Target branch '{resolved_target}' does not exist locally or on origin.")

    try:
        # lanes.json is a PRIMARY-partition artifact — read from the primary
        # surface, NOT the coord worktree mission_dir (#2118).
        require_lanes_json(_planning_read_dir(main_repo_root, mission_slug))
    except (MissingLanesError, CorruptLanesError) as exc:
        errors.append(str(exc))

    return _MergePreflightResult(target_branch=resolved_target, errors=errors)


def _execute_planning_only_merge(
    main_repo_root: Path,
    mission_slug: str,
    target_branch: str,
    *,
    strategy: object,
    push: bool,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> None:
    """Run the hardened CLI closeout path while preserving JSON-only stdout."""
    import typer

    from specify_cli.cli.commands import consolidate as merge_command

    try:
        with merge_command.console.capture():
            merge_command._run_lane_based_consolidation(
                repo_root=main_repo_root,
                mission_slug=mission_slug,
                push=push,
                delete_branch=delete_branch,
                remove_worktree=remove_worktree,
                target_override=target_branch,
                strategy=strategy,
                assume_yes=True,
            )
    except typer.Exit as exc:
        raise RuntimeError(f"Planning-artifact closeout failed with exit code {exc.exit_code}") from exc


def _resolve_lane_merge_retention(
    main_repo_root: Path,
    mission_slug: str,
    *,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> tuple[RetentionDecision, bool]:
    """Resolve the retention decision + mission-branch-deletable flag (C-007/T010).

    ``_execute_lane_merge`` is a genuine SECOND deletion implementation (not a
    passthrough to ``merge/executor.py``), so NFR-003 ("all cleanup paths")
    requires it to route through the same
    :func:`~specify_cli.core.paths.resolve_merge_retention` authority rather
    than deleting unconditionally. This mirrors the executor's topology-aware
    coupling **GATE** (#3131 T008 / INV-2): for a coord-topology mission (its
    primary meta.json carries a ``coordination_branch`` key) the
    mission/coordination branch is only deletable when BOTH ``delete_branch``
    and ``remove_worktree`` resolve True (``teardown_coordination``); for a
    non-coord mission it stays keyed to ``delete_branch`` alone. This guarantees
    a **retaining** coord mission's branch is never deleted here (NFR-003).

    Scope note: only the deletion GATE mirrors the executor. The orchestrator
    does NOT perform the executor's full coordination-triple teardown
    (``_teardown_coordination_triple``: coord-marker flatten + coord-worktree
    removal) — it only deletes the mission branch. A NON-retaining coord mission
    merged through orchestrator-api therefore leaves the ``coordination_branch``
    marker/worktree un-torn-down (a pre-existing orchestrator-api limitation,
    tracked separately, NOT introduced by #3131). Full coord teardown is the
    executor/CLI ``spec-kitty consolidate`` path's responsibility.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.core.paths import resolve_merge_retention
    from specify_cli.mission_metadata import load_meta_or_empty

    primary_meta_dir = placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    retention = resolve_merge_retention(
        primary_meta_dir,
        explicit_delete_branch=delete_branch,
        explicit_remove_worktree=remove_worktree,
    )
    is_coord = "coordination_branch" in load_meta_or_empty(primary_meta_dir)
    mission_branch_deletable = retention.teardown_coordination if is_coord else retention.delete_branch
    return retention, mission_branch_deletable


def _branch_tip_sha(main_repo_root: Path, branch: str) -> str | None:
    """The tip SHA of ``refs/heads/<branch>``, or ``None`` when the branch does not exist."""
    from specify_cli.core.git_ops import run_command

    ret, out, _err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture=True,
        check_return=False,
        cwd=main_repo_root,
    )
    return out.strip() if ret == 0 and out.strip() else None


def _delete_mission_branch_at(main_repo_root: Path, lanes_manifest: LanesManifest, approved_tip: str | None) -> None:
    """Delete the mission branch only while it still sits at *approved_tip* (#5570).

    Replaces an unconditional ``git branch -D`` (``check_return=False``) that made a commit
    landing after the merge unreachable and still reported success. A branch that moved keeps
    its commits and the merge reports a failure (:class:`MergeTeardownRefused`, a ``RuntimeError``
    that ``consolidate_mission`` envelopes) carrying the ``COORD_MOVED_AFTER_LANDING`` code, which
    its message also ends with (#5613); an already-absent branch has nothing to protect. A branch
    git refuses to drop for another reason (e.g. checked out in a coordination worktree this path does not
    remove, a pre-existing limitation) is left in place with a warning, as before.

    Raises:
        MergeTeardownRefused: the branch moved past *approved_tip*; it was NOT deleted.
    """
    import logging

    from specify_cli.consolidation._constants import COORD_MOVED_AFTER_LANDING, COORD_MOVED_AFTER_LANDING_SUFFIX
    from specify_cli.git.ref_advance import RefDeleteError, RefDeleteMismatchError, delete_branch_ref

    branch = lanes_manifest.mission_branch
    if approved_tip is None or branch == lanes_manifest.target_branch:
        return
    try:
        delete_branch_ref(main_repo_root, branch, approved_tip)
    except RefDeleteMismatchError as exc:
        if exc.actual_sha is None:
            return  # already gone: nothing was destroyed by us
        raise MergeTeardownRefused(
            f"Merge landed, but mission branch {branch!r} moved to {exc.actual_sha[:12]} during cleanup (it was at {approved_tip[:12]}); "
            f"it was NOT deleted. Review the commit(s) with `git log {lanes_manifest.target_branch}..{branch}`, "
            f"land any that belong on the target, then delete the branch yourself.{COORD_MOVED_AFTER_LANDING_SUFFIX}",
            error_code=COORD_MOVED_AFTER_LANDING,
        ) from exc
    except RefDeleteError as exc:
        logging.getLogger(__name__).warning("Mission branch %s was not deleted: %s", branch, exc)


def _apply_lane_merge_cleanup(
    main_repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    *,
    retention: RetentionDecision,
    mission_branch_deletable: bool,
) -> None:
    """Worktree removal + lane/mission branch deletion, gated on the RESOLVED
    retention decision (#3131 T010) — extracted from ``_execute_lane_merge``
    to stay under the complexity ceiling; not a passthrough (see there)."""
    import functools

    from specify_cli.coordination.coherence import is_toolchain_generated_churn
    from specify_cli.core.git_ops import run_command
    from specify_cli.git.destructive_guard import guarded_worktree_remove
    from specify_cli.lanes.branch_naming import code_lane_branch_name, worktree_path
    from specify_cli.lanes.compute import is_planning_lane

    # #5570: the mission branch is deleted as a compare-and-swap at the tip read
    # HERE, before the worktree/lane-branch legs below open a window for a commit
    # to land on it. No teardown gate runs on this path, so the cleanup's own start
    # is the earliest approval point.
    mission_branch_tip = _branch_tip_sha(main_repo_root, lanes_manifest.mission_branch) if mission_branch_deletable else None

    if retention.remove_worktree:
        for lane in lanes_manifest.lanes:
            # Lane naming is keyed on the creation input alone (WP07,
            # FR-002/PD-1); no Mission identity is passed here.
            wt_path = worktree_path(main_repo_root, mission_slug, lane_id=lane.lane_id)
            if wt_path.exists():
                # #4753 C-003: ``retention.remove_worktree`` is the upstream
                # decision of WHETHER to remove at all (already resolved
                # above, and already honors the operator's
                # --keep-worktree/retain_worktrees policy); the guard's own
                # ``retain`` is a DIFFERENT axis (dirty-worktree handling) and
                # always stays False here (review ADVISORY-3) so a dirty lane
                # worktree refuses instead of being force-removed.
                guarded_worktree_remove(
                    wt_path,
                    retain=False,
                    is_residue=functools.partial(
                        is_toolchain_generated_churn,
                        mission_slug=mission_slug,
                    ),
                )

    # LANE branches stay keyed to the plain resolved ``delete_branch`` (no
    # topology coupling — only the mission/coordination branch is coupled).
    if retention.delete_branch:
        for lane in lanes_manifest.lanes:
            if is_planning_lane(lane):
                continue
            run_command(
                [
                    "git",
                    "branch",
                    "-D",
                    code_lane_branch_name(mission_slug, lane.lane_id),
                ],
                cwd=main_repo_root,
                check_return=False,
            )

    # MISSION/coordination branch: the DELETION GATE is topology-aware (#3131
    # T008/T010 — see ``_resolve_lane_merge_retention``), so a retaining coord
    # mission's branch is never deleted here. NOTE: unlike the executor's
    # ``_teardown_coordination_triple``, this path does NOT flatten the
    # ``coordination_branch`` marker or remove the coord worktree — full coord
    # teardown is the executor/CLI path's job (pre-existing orchestrator-api
    # limitation, tracked separately).
    if mission_branch_deletable:
        _delete_mission_branch_at(main_repo_root, lanes_manifest, mission_branch_tip)


def _refuse_protected_status_target(main_repo_root: Path, mission_slug: str, lanes_manifest: LanesManifest) -> None:
    """#5385: refuse, before any branch moves, a consolidation whose ``done`` bookkeeping the policy refuses.

    The same up-front preflight the CLI consolidation runs
    (:func:`~specify_cli.consolidation.preflight.refuse_protected_status_target`),
    raised as the ``RuntimeError`` this path reports as a failure envelope. It
    covers both the code-lane path (which would otherwise squash onto the target
    and only then fail the ``done`` write) and the planning-artifact-only
    closeout (whose console is captured, so its own refusal line is not seen).
    """
    from specify_cli.consolidation.preflight import refuse_protected_status_target

    verdict = refuse_protected_status_target(main_repo_root, mission_slug, lanes_manifest)
    if verdict is not None:
        raise RuntimeError(f"{verdict.error_code}: {verdict.message} Next step: {verdict.next_step}")


def _bound_refusal_code(refusal: str) -> str | None:
    """The leading ``CODE:`` of a refusal text when it names a :class:`BoundRefusalCode`, else ``None``."""
    from specify_cli.consolidation.approved_bound import BoundRefusalCode

    head = refusal.partition(":")[0]
    try:
        return BoundRefusalCode(head).value
    except ValueError:
        return None


def _status_placement_tip(main_repo_root: Path, mission_slug: str) -> str | None:
    """The status placement's tip as a SHA, or ``None`` when it cannot be resolved for any reason.

    The executor's coordination checkpoint (``run_state._capture_coord_checkpoint``) answers
    ``None`` for any placement failure; so does this, whatever the failure is.
    """
    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.consolidation.git_probes import resolve_commit

    try:
        return resolve_commit(main_repo_root, resolve_placement_only(main_repo_root, mission_slug, kind=MissionArtifactKind.STATUS_STATE).ref)
    except Exception:  # noqa: BLE001 -- the executor's coordination checkpoint treats every placement or git failure as "no coordination tip"
        return None


def _approved_bound_claim_base(main_repo_root: Path, mission_slug: str, lanes_manifest: LanesManifest) -> str:
    """The commit the executor's fresh-run claim measures lanes from, resolved to a SHA.

    The status placement's tip (the coordination branch when the mission has one), else
    the mission branch, as ``phase_claim._capture_reconciliation_claim`` picks it for a
    run with no persisted record. ``approved_bound_refusal`` answers ``None`` for a base
    that does not resolve, which would read as "nothing to refuse", so a mission branch
    that does not resolve raises here instead (a ``GitProbeError``, a ``RuntimeError``
    the caller envelopes as ``PREFLIGHT_FAILED`` before any lane is merged).
    """
    from specify_cli.consolidation.git_probes import resolve_commit

    return _status_placement_tip(main_repo_root, mission_slug) or resolve_commit(main_repo_root, lanes_manifest.mission_branch)


def _refuse_post_approval_lane_content(main_repo_root: Path, mission_dir: Path, mission_slug: str, lanes_manifest: LanesManifest) -> None:
    """#5668: refuse, before the first lane is consolidated, a lane holding content committed after review approved it.

    This path merges lanes with no claim and no gate behind it (and no rollback), so
    the same lane check the ``consolidate`` claim runs
    (:func:`~specify_cli.consolidation.reconciliation.approved_bound_refusal`) must
    precede the first merge. The excluded work packages and the window base are the
    ones the executor resolves for a fresh run. Anything that stops the check from
    answering (an unreadable status log, an unresolvable base) refuses as well.
    """
    from specify_cli.consolidation.done_bookkeeping import acceptably_canceled_wp_ids
    from specify_cli.consolidation.git_probes import resolve_commit
    from specify_cli.consolidation.reconciliation import approved_bound_refusal
    from specify_cli.status import StoreError

    try:
        refusal = approved_bound_refusal(
            main_repo_root,
            mission_dir,
            lanes_manifest,
            coord_base_ref=_approved_bound_claim_base(main_repo_root, mission_slug, lanes_manifest),
            excluded_canceled_wp_ids=acceptably_canceled_wp_ids(main_repo_root, mission_slug),
            excluded_window_base=resolve_commit(main_repo_root, lanes_manifest.target_branch),
        )
    except (StoreError, OSError) as exc:
        raise RuntimeError(f"The approved lanes could not be checked against what review approved ({exc}); no lane was merged.") from exc
    if refusal is not None:
        raise ApprovedBoundRefused(refusal, error_code=_bound_refusal_code(refusal))


def _execute_lane_merge(
    main_repo_root: Path,
    mission_dir: Path,
    mission_slug: str,
    target_branch: str,
    *,
    strategy: str,
    push: bool,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> None:
    """Execute the lane-based merge flow without emitting console prose."""
    from specify_cli.cli.commands.consolidate import _mark_wp_merged_done
    from specify_cli.core.git_ops import has_remote, run_command
    from specify_cli.lanes.compute import is_planning_artifact_only
    from specify_cli.lanes.consolidation import consolidate_lane_into_mission, integrate_mission_into_target
    from specify_cli.lanes.persistence import require_lanes_json
    from specify_cli.consolidation.config import MergeStrategy
    from specify_cli.policy.config import load_policy_config
    from specify_cli.policy.merge_gates import evaluate_merge_gates

    # lanes.json is PRIMARY-partition — read from the primary surface, not the
    # coord worktree mission_dir (#2118).
    lanes_manifest = require_lanes_json(_planning_read_dir(main_repo_root, mission_slug))
    lanes_manifest.target_branch = target_branch
    merge_strategy = MergeStrategy(strategy)
    _refuse_protected_status_target(main_repo_root, mission_slug, lanes_manifest)

    if is_planning_artifact_only(lanes_manifest):
        _execute_planning_only_merge(
            main_repo_root,
            mission_slug,
            target_branch,
            strategy=merge_strategy,
            push=push,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
        )
        return

    # #3131 C-007/T010: resolve once, before any gate/merge work, so the
    # cleanup gates below never delete unconditionally.
    retention, mission_branch_deletable = _resolve_lane_merge_retention(
        main_repo_root,
        mission_slug,
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
    )

    policy = load_policy_config(main_repo_root)
    all_wp_ids = [wp for lane in lanes_manifest.lanes for wp in lane.wp_ids]
    gate_eval = evaluate_merge_gates(
        mission_dir,
        mission_slug,
        all_wp_ids,
        policy.merge_gates,
        main_repo_root,
    )
    if not gate_eval.overall_pass:
        blocking = [gate.details for gate in gate_eval.gates if gate.blocking]
        raise RuntimeError("; ".join(blocking) or "Merge gates failed.")

    _refuse_post_approval_lane_content(main_repo_root, mission_dir, mission_slug, lanes_manifest)

    for lane in lanes_manifest.lanes:
        lane_result = consolidate_lane_into_mission(main_repo_root, mission_slug, lane.lane_id, lanes_manifest)
        if not lane_result.success:
            raise RuntimeError("; ".join(lane_result.errors) or f"Lane {lane.lane_id} merge failed.")

    mission_result = integrate_mission_into_target(
        main_repo_root,
        mission_slug,
        lanes_manifest,
        strategy=merge_strategy,
    )
    if not mission_result.success:
        raise RuntimeError("; ".join(mission_result.errors) or "Mission merge failed.")

    for lane in lanes_manifest.lanes:
        for wp_id in lane.wp_ids:
            _mark_wp_merged_done(main_repo_root, mission_slug, wp_id, lanes_manifest.target_branch)

    if push and has_remote(main_repo_root):
        run_command(["git", "push", "origin", lanes_manifest.target_branch], cwd=main_repo_root)

    # #3131 T010: gated on the RESOLVED decision, not the raw (possibly unset)
    # caller args — a retaining mission's branches/worktree survive.
    _apply_lane_merge_cleanup(
        main_repo_root,
        mission_slug,
        lanes_manifest,
        retention=retention,
        mission_branch_deletable=mission_branch_deletable,
    )


# ── Command 8: accept-mission ──────────────────────────────────────────────


def _readiness_failure_payload(mission_dir: Path, summary: AcceptanceSummary) -> dict[str, object]:
    """FR-007/C-001 error-data shape for a failed host readiness verdict.

    ``summary.outstanding()`` already returns ``dict[str, list[str]]`` (JSON-safe
    as-is); ``skipped_checks``/``blocked_checks`` are lists of
    ``AcceptanceCheckDiagnostic`` and are serialised through its own
    ``to_dict()`` (``{check, detail}``) rather than a second, driftable
    ad-hoc shape.
    """
    return {
        **_common._mission_identity_payload(mission_dir),
        "outstanding": summary.outstanding(),
        "activity_issues": list(summary.activity_issues),
        "skipped_checks": [item.to_dict() for item in summary.skipped_checks],
        "blocked_checks": [item.to_dict() for item in summary.blocked_checks],
    }


def _stamp_mission_acceptance_or_fail(cmd: str, mission_dir: Path, summary: AcceptanceSummary, actor: str) -> str:
    """Record acceptance inside the WP01/WP02 locked pre-stamp verdict guard.

    Calls the SAME ``_stamp_acceptance_record`` seam the host ``accept`` CLI
    uses (never ``feature_status_lock``/``locked_acceptance_verdict_guard``
    directly here -- one lock-composition call site) -- it re-reads the
    acceptance matrix fresh under the per-mission status lock immediately
    before writing, and applies the identical planning-artifact-only bypass
    rule (any OTHER missing matrix dir fails closed). Both a guard refusal
    (a verdict committed after the readiness check above but before this
    stamp -- SC-005) and a lock-acquisition timeout surface as
    ``specify_cli.acceptance.AcceptanceError`` and map to ``MISSION_NOT_READY``
    here -- never a raw traceback.
    """
    from specify_cli.acceptance import AcceptanceError, _stamp_acceptance_record
    from specify_cli.mission_metadata import load_meta_strict

    from specify_cli.acceptance.matrix import AcceptanceMatrixParseError

    try:
        _stamp_acceptance_record(summary, actor, "orchestrator", None)
    except (AcceptanceError, AcceptanceMatrixParseError) as exc:
        # A matrix left malformed between the readiness check and the guard's
        # locked re-read refuses like any other not-ready verdict.
        _fail(cmd, "MISSION_NOT_READY", str(exc), _common._mission_identity_payload(mission_dir))
    # Read back from ``summary.feature_dir`` -- the PRIMARY anchor
    # ``_stamp_acceptance_record``/``record_acceptance`` actually wrote
    # ``meta.json`` into (``acceptance/__init__.py``'s
    # ``_primary_anchor_feature_dir``) -- never ``mission_dir``, which for a
    # coord-topology mission is the coordination worktree's STATUS dir and
    # carries no ``meta.json`` at all (review cycle 1, Issue 1): reading from
    # the wrong directory let the write succeed and then raised a raw
    # ``FileNotFoundError`` instead of returning the JSON envelope.
    meta = load_meta_strict(summary.feature_dir)
    return str(meta["accepted_at"])


def accept_mission(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
) -> None:
    """Accept a mission after all WPs are approved or done."""
    cmd = "accept-mission"

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.status import materialize
    from specify_cli.core.dependency_graph import build_dependency_graph

    # STATUS read off the coord-aware dir; dependency graph (WP frontmatter,
    # PRIMARY-partition) off the primary surface (#2118).
    snapshot = materialize(mission_dir)
    dep_graph = build_dependency_graph(_planning_read_dir(main_repo_root, mission))

    # Check all WPs (from dep_graph) are approved/done; WPs with no events are implicitly planned.
    all_wp_ids = set(dep_graph.keys()) | set(snapshot.work_packages.keys())
    incomplete = [
        wp_id
        for wp_id in sorted(all_wp_ids)
        if wp_state_for(snapshot.work_packages.get(wp_id, {}).get("lane", Lane.PLANNED)).lane not in {Lane.APPROVED, Lane.DONE}
    ]
    if incomplete:
        _fail(
            cmd,
            "MISSION_NOT_READY",
            f"Mission has {len(incomplete)} incomplete WP(s)",
            {
                **_common._mission_identity_payload(mission_dir),
                "incomplete_wps": sorted(incomplete),
            },
        )
        return

    from specify_cli.acceptance import ACCEPTANCE_CHECKS_FAILED_MESSAGE, AcceptanceError, collect_feature_summary
    from specify_cli.acceptance.matrix import AcceptanceMatrixParseError
    from specify_cli.config.path_conventions import PathConventionsConfigError
    from specify_cli.upgrade.pre30_guard import Pre30LayoutError

    try:
        # FR-007 / C-001: pin ``strict_metadata=True`` explicitly -- the same
        # single readiness authority the host ``accept`` CLI uses -- rather
        # than resting on the parameter's current default.
        summary = collect_feature_summary(main_repo_root, mission, strict_metadata=True)
    except Pre30LayoutError as exc:
        # #1057 / squad Blocker 1: pre-3.0 lane-directory missions hard-reject
        # rather than producing a vacuous all-done summary. A mission whose layout
        # the runtime no longer reads is not acceptable until migrated, so it maps
        # to MISSION_NOT_READY; the full `spec-kitty upgrade` instruction rides in
        # the message field (keeping the orchestrator JSON envelope contract).
        _fail(cmd, "MISSION_NOT_READY", str(exc), _common._mission_identity_payload(mission_dir))
        return
    except PathConventionsConfigError as exc:
        _fail(
            cmd,
            "MISSION_NOT_READY",
            str(exc),
            {
                "message": str(exc),
                **_common._mission_identity_payload(mission_dir),
            },
        )
        return
    except (AcceptanceError, AcceptanceMatrixParseError) as exc:
        # A malformed acceptance matrix or an undecodable artifact (the host
        # ``accept`` CLI reports both) refuses inside the JSON envelope rather
        # than escaping as a traceback.
        _fail(cmd, "MISSION_NOT_READY", str(exc), _common._mission_identity_payload(mission_dir))
        return

    if not summary.ok:
        # FR-007/FR-009/FR-010/C-001/C-002 (#4934): the host readiness verdict
        # (the SAME ``AcceptanceSummary.ok`` the CLI ``accept`` command gates
        # on) is now APPLIED here instead of being computed and discarded --
        # the pre-fix defect this WP closes. No second readiness computation
        # (C-001); the existing ``MISSION_NOT_READY`` error code is reused
        # (C-002) rather than minting a new one.
        _fail(cmd, "MISSION_NOT_READY", ACCEPTANCE_CHECKS_FAILED_MESSAGE, _readiness_failure_payload(mission_dir, summary))
        return

    accepted_at = _stamp_mission_acceptance_or_fail(cmd, mission_dir, summary, actor)
    approved_wps = list(summary.lanes.get("approved", []))
    done_wps = list(summary.lanes.get("done", []))

    data = {
        **_common._mission_identity_payload(mission_dir),
        "accepted": True,
        "mode": "auto",
        "accepted_at": accepted_at,
        "accepted_wps": [*approved_wps, *done_wps],
        "approved_wps": approved_wps,
        "done_wps": done_wps,
        "merge_pending_wps": approved_wps,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 9: consolidate-mission ──────────────────────────────────────────
# #3080 (post-plan A4): renamed from ``merge-mission`` for canonical-word
# consistency with the host CLI's ``spec-kitty consolidate``. The lane-
# consolidation semantics are unchanged; only the command/function names and
# the envelope's ``command`` field moved.


def consolidate_mission(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    target: str = typer.Option(None, "--target", help="Target branch to merge into (auto-detected from meta.json)"),
    strategy: str = typer.Option("merge", "--strategy", help="Merge strategy: merge, squash, or rebase"),
    push: bool = typer.Option(False, "--push", help="Push target branch after merge"),
) -> None:
    """Consolidate a lane-based mission into target."""
    cmd = "consolidate-mission"

    _SUPPORTED_STRATEGIES = frozenset(["merge", "squash", "rebase"])
    if strategy not in _SUPPORTED_STRATEGIES:
        _fail(
            cmd,
            "UNSUPPORTED_STRATEGY",
            f"Strategy '{strategy}' is not supported. Supported strategies: {sorted(_SUPPORTED_STRATEGIES)}",
            {"strategy": strategy, "supported": sorted(_SUPPORTED_STRATEGIES)},
        )
        return

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    preflight = _build_merge_preflight(main_repo_root, mission, target)
    if preflight.errors:
        _fail(
            cmd,
            "PREFLIGHT_FAILED",
            "Merge failed",
            {
                **_common._mission_identity_payload(mission_dir),
                "target_branch": preflight.target_branch,
                "errors": preflight.errors,
            },
        )
        return

    try:
        # #3131 C-007/T010: unset (None) so the mission's meta.json retention
        # policy governs — this CLI has no --delete-branch/--remove-worktree
        # flags of its own, so hardcoding True/True here silently bypassed a
        # retaining mission's policy every time (the exact NFR-003 gap).
        _execute_lane_merge(
            main_repo_root,
            mission_dir,
            mission,
            preflight.target_branch,
            strategy=strategy,
            push=push,
            delete_branch=None,
            remove_worktree=None,
        )
    except DestructiveOpRefused as exc:
        # #4753 finding B: DestructiveOpRefused is NOT a RuntimeError
        # (C-002) -- the except clause below never sees it, so this must be
        # caught first or it escapes as a raw traceback.
        _fail_from_destructive_op_refused(cmd, mission_dir, preflight.target_branch, exc)
    except RuntimeError as exc:
        failure: dict[str, object] = {
            **_common._mission_identity_payload(mission_dir),
            "target_branch": preflight.target_branch,
            "errors": [str(exc)],
        }
        if isinstance(exc, MergeTeardownRefused):
            # #5613: the stable code, beside the unchanged envelope code and message.
            failure["teardown_error_code"] = exc.error_code
        if isinstance(exc, ApprovedBoundRefused) and exc.error_code is not None:
            # #5668: the lane-check refusal's code, machine-readable and additive.
            failure["preflight_error_code"] = exc.error_code
        _fail(cmd, "PREFLIGHT_FAILED", "Merge failed", failure)
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "merged": True,
        "target_branch": preflight.target_branch,
        "strategy": strategy,
        "worktree_removed": False,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)
