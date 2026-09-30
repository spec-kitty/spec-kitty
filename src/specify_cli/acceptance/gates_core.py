#!/usr/bin/env python3
"""Pure(ish) lane-gate checks for the acceptance package.

WP04 (coord-authority-trio-degod-01KX7094) / T022: extracted from
``acceptance/__init__.py`` to bring ``_check_lane_gates`` (CC19) under the
S3776 <=15 complexity gate without changing behaviour. This module owns the
deterministic lane/branch/matrix evaluation; the executor
(``acceptance.collect_feature_summary`` / ``perform_acceptance``) stays the
thin I/O-and-wiring layer.

Cross-module note: a couple of call sites here resolve
``specify_cli.acceptance._target_branch_for_feature`` and
``specify_cli.acceptance._read_text_strict`` via a **deferred** import inside
the function body rather than a top-level import. This is deliberate, not an
oversight: the WP01 characterization suite
(``tests/characterization/test_trio_pure_cores.py``) monkeypatches
``specify_cli.acceptance.read_target_branch_from_meta`` to isolate
``_check_lane_gates`` from real ``meta.json`` I/O. A Python function's free
variables resolve through the globals of the module it is *defined* in, so a
direct top-level ``from specify_cli.core.paths import read_target_branch_from_meta``
here would bind a private, unpatchable copy and silently ignore the test
double. Reading the collaborator off the live ``specify_cli.acceptance``
namespace at call time keeps the monkeypatch visible across the module
boundary. Do not "simplify" this into a top-level import.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mission_runtime import TopologySurface
from specify_cli.acceptance.execution_context import GateSurfaceRefMismatch
from specify_cli.core.subtask_rows import iter_unchecked_subtask_rows
from specify_cli.status_lanes import is_acceptable_ending

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout
    from specify_cli.acceptance.execution_context import (
        CannotEvaluate,
        GateExecutionContext,
    )

# WP02 (mission-completion-terminal-state): the former ``_ACCEPTED_READY_LANES``
# copy is retired onto the single acceptable-ending authority
# (``specify_cli.status_lanes.is_acceptable_ending``, FR-005 / directive 044).

# Mirrors ``specify_cli.acceptance.TASKS_FILE`` — a tiny, immutable,
# non-monkeypatched value-level constant kept local to avoid the deferred-lookup
# indirection the cross-module collaborators above require, for zero benefit.
_TASKS_FILE = "tasks.md"


@dataclass
class AcceptanceCheckDiagnostic:
    check: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"check": self.check, "detail": self.detail}


#: The reason `_check_lane_gates` skipped the acceptance-matrix gate entirely
#: (never evaluated it at all, as opposed to evaluating it and finding it
#: absent/failing). WP02 (accept-fails-closed / FR-010): a planning-artifact-only
#: mission never produces an ``acceptance-matrix.json`` (a `_evaluate_branch_gate`
#: no-op), and this is the ONLY skip reason the FR-010 pre-stamp guard in
#: ``_commit_acceptance_meta`` is allowed to bypass on. Any other
#: `acceptance_matrix_dir is None` on the stamping path fails closed.
PLANNING_ARTIFACT_ONLY_SKIP_REASON = "planning_artifact_only"


@dataclass(frozen=True)
class LaneGateOutcome:
    """What `_check_lane_gates` resolved, threaded up to `AcceptanceSummary`.

    ``matrix_dir`` is the surface the acceptance-matrix gate actually evaluated
    (WP02 / FR-010) -- ``None`` when the gate never ran at all (a blocked
    lanes-manifest/branch gate, a cannot-evaluate refusal, a missing matrix, or
    a lock timeout). ``skip_reason`` distinguishes the ONE legitimate "never
    ran" case (planning-artifact-only, see :data:`PLANNING_ARTIFACT_ONLY_SKIP_REASON`)
    from every other ``None`` case, which the FR-010 guard must fail closed on.
    """

    matrix_dir: Path | None = None
    skip_reason: str | None = None


def _all_work_packages_terminal(lanes: Mapping[str, list[str]]) -> bool:
    """True when every tracked WP is in a terminal-ready lane (approved/done).

    FR-009: WP terminal status is the authority for completion, so an
    orchestrated mission whose work landed through the lane lifecycle is
    complete even if the ``tasks.md`` checkboxes were never hand-ticked. Mirrors
    :attr:`AcceptanceSummary.all_done` but operates on the lane buckets directly
    so the ``unchecked_tasks`` derivation does not depend on summary
    construction order. Returns ``False`` when no WP is tracked at all (an empty
    mission has nothing terminal to vouch for completion).
    """
    tracked = any(wp_ids for wp_ids in lanes.values())
    if not tracked:
        return False
    # Routed through the single acceptable-ending authority at
    # ``has_provenance=False`` (this lane-only view carries no provenance):
    # behavior-identical to the retired ``_ACCEPTED_READY_LANES`` membership —
    # ``approved``/``done`` are terminal-ready, every other lane (``canceled``
    # included) is not. Provenance-aware terminality is decided by the caller
    # (``collect_feature_summary``) and threaded via
    # :func:`_normalized_unchecked_tasks`'s ``all_packages_acceptable`` override.
    return not any(wp_ids for lane, wp_ids in lanes.items() if not is_acceptable_ending(lane, has_provenance=False))


def _normalized_unchecked_tasks(
    unchecked_tasks: list[str],
    lanes: Mapping[str, list[str]],
    *,
    all_packages_acceptable: bool | None = None,
) -> list[str]:
    """Apply FR-009 + the ``tasks.md missing`` normalization to unchecked tasks.

    FR-009 (#2085a): unchecked-tasks completion derives from WP terminal status.
    When every tracked WP is at an acceptable ending, the work landed through the
    lane lifecycle, so the redundant ``tasks.md`` checkbox bookkeeping is not
    required — unticked checkboxes must not strand a finished mission. A mission
    with a non-terminal WP (e.g. ``in_review`` / ``for_review``) still reports
    its unchecked items. The ``[<tasks.md> missing]`` sentinel is also dropped
    (it is surfaced separately via the missing-artifacts gate).

    ``all_packages_acceptable`` (WP02) is the provenance-aware override: the
    lane-only :func:`_all_work_packages_terminal` cannot see whether a
    ``canceled`` WP carries operator provenance, so ``collect_feature_summary``
    — which holds the per-WP provenance — passes the authoritative decision here.
    When ``None`` (the two-arg call shape retained for the characterization
    suite), the lane-only fallback is used, preserving prior behavior exactly.
    A canceled-with-operator-provenance mission therefore no longer strands on
    unticked checkboxes (FR-001).

    The acceptance-MATRIX gate (C-010) is untouched: it remains the genuine
    verification surface — this normalization only governs the checkbox gate.
    """
    if unchecked_tasks == [f"{_TASKS_FILE} missing"]:
        return []
    terminal = all_packages_acceptable if all_packages_acceptable is not None else _all_work_packages_terminal(lanes)
    if terminal:
        return []
    return unchecked_tasks


def _find_unchecked_tasks(tasks_file: Path) -> list[str]:
    if not tasks_file.exists():
        return [f"{_TASKS_FILE} missing"]

    from specify_cli import acceptance as _acceptance_pkg

    return list(iter_unchecked_subtask_rows(_acceptance_pkg._read_text_strict(tasks_file)))


def _append_skipped_lane_checks(
    skipped_checks: list[AcceptanceCheckDiagnostic],
    *,
    reason: str,
    include_matrix_presence: bool = False,
) -> None:
    checks = [
        ("acceptance_matrix_presence", "Acceptance matrix presence check"),
        ("acceptance_matrix_evidence", "Acceptance matrix evidence validation"),
        ("negative_invariants", "Negative invariant execution"),
        ("acceptance_matrix_verdict", "Acceptance matrix verdict evaluation"),
    ]
    for check, label in checks[0 if include_matrix_presence else 1 :]:
        skipped_checks.append(
            AcceptanceCheckDiagnostic(
                check=check,
                detail=f"{label} skipped: {reason}",
            )
        )


def _record_lanes_manifest_stop(
    message: str,
    *,
    reason: str,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
) -> None:
    """Record the shared blocked/skipped/activity-issue shape for a
    ``lanes.json`` read that cannot proceed (corrupt or missing). Load-bearing:
    the ``activity_issues`` append is what flips ``AcceptanceSummary.ok`` —
    ``skipped_checks``/``blocked_checks`` alone are informational only.
    """
    activity_issues.append(message)
    blocked_checks.append(AcceptanceCheckDiagnostic(check="lanes_manifest", detail=message))
    _append_skipped_lane_checks(skipped_checks, reason=reason, include_matrix_presence=True)


def _resolve_lanes_manifest_or_stop(
    feature_dir: Path,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
) -> Any:
    """Read ``lanes.json``; return ``None`` when the caller should stop.

    Two distinct "stop" causes collapse to the same ``None`` sentinel because
    the caller's only remaining decision is whether to continue. Both
    corruption AND genuine absence are fail-closed (#4891): each records its
    own ``activity_issues`` / ``blocked_checks`` / ``skipped_checks``
    diagnostics here so the acceptance-matrix gate can never be silently
    bypassed by a missing manifest — there is no legitimate no-lanes shape on
    4.0 (every mission gets ``lanes.json`` via ``finalize-tasks``). Routed
    through :func:`~specify_cli.lanes.persistence.require_lanes_json` (rather
    than the bare ``read_lanes_json`` + ``None`` check the pre-#4891 version
    used) so the missing-manifest diagnostic is single-sourced from
    :class:`~specify_cli.lanes.persistence.MissingLanesError`'s remediation
    wording (``finalize-tasks`` / ``doctor mission-state --fix``) instead of a
    second, driftable copy of that guidance living here.
    """
    from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError, require_lanes_json

    try:
        return require_lanes_json(feature_dir)
    except CorruptLanesError as exc:
        _record_lanes_manifest_stop(
            str(exc),
            reason="lanes.json is corrupt or malformed",
            activity_issues=activity_issues,
            skipped_checks=skipped_checks,
            blocked_checks=blocked_checks,
        )
        return None
    except MissingLanesError as exc:
        _record_lanes_manifest_stop(
            str(exc),
            reason="lanes.json is missing",
            activity_issues=activity_issues,
            skipped_checks=skipped_checks,
            blocked_checks=blocked_checks,
        )
        return None


def _wp_kinds_for_manifest(repo_root: Path, mission_slug: str) -> Mapping[str, Any]:
    """Build the WP id -> :class:`WorkProductKind` index :func:`has_code_wps` needs.

    #5100 T020 / plan fold B3: the ONE place this module derives WP kinds,
    reusing the canonical normalized-WP index (:func:`build_normalized_wp_index`)
    rather than re-parsing frontmatter -- so this can never drift from what
    ``resolve_workspace_for_wp`` itself classifies a WP as.

    #5100 WP04 cycle-2 fix (review issue 2, mirrors
    ``consolidation/executor.py::_run_has_code_wps``'s identical fix): ONLY
    an EXPLICIT frontmatter ``execution_mode`` (``mode_source ==
    "frontmatter"``) is trusted as a "code" signal. A WP with no
    ``execution_mode`` normalizes via bare-default inference
    (``mode_source == "inferred_legacy"``, defaulting to ``code_change``
    when the body carries no signal at all) -- trusting that default here
    would flip a genuinely lane-planning-only legacy mission's branch gate
    into "has code" from a WP that never claimed to be one.
    """
    from specify_cli.ownership.models import WorkProductKind
    from specify_cli.workspace.context import build_normalized_wp_index

    index = build_normalized_wp_index(repo_root, mission_slug)
    return {wp_id: WorkProductKind(entry.metadata.execution_mode) for wp_id, entry in index.items() if entry.mode_source == "frontmatter"}


def _evaluate_branch_gate(
    repo_root: Path,
    lanes_manifest: Any,
    feature_dir: Path,
    branch: str | None,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
) -> bool:
    """Target-branch mismatch + allowed-branch + no-code gate.

    Returns ``True`` when the caller should continue on to the acceptance
    matrix evaluation, ``False`` when it should stop (blocked, or a mission
    with no code WPs -- which never carries a matrix).
    """
    from specify_cli.lanes.compute import mission_has_code as _mission_has_code_fn

    from specify_cli import acceptance as _acceptance_pkg

    meta_target_branch = _acceptance_pkg._target_branch_for_feature(feature_dir)
    if meta_target_branch and meta_target_branch != lanes_manifest.target_branch:
        message = f"Acceptance target branch mismatch: meta.json targets {meta_target_branch}, lanes.json targets {lanes_manifest.target_branch}"
        activity_issues.append(message)
        blocked_checks.append(AcceptanceCheckDiagnostic(check="mission_branch", detail=message))
        _append_skipped_lane_checks(
            skipped_checks,
            reason="meta.json target_branch does not match lanes.json target_branch",
            include_matrix_presence=True,
        )
        return False

    # #5100 T020 / plan fold B3: the "no code" claims below use the WP-kind
    # question (has_code_wps), never the lane-shape ``is_planning_artifact_only``
    # -- a single_branch repo-root lane can hold CODE WPs, which the lane-shape
    # predicate alone cannot see (it stays lane-based, unchanged, for its own
    # other callers).
    # #5100 WP04 cycle-3 fix (review issue 1): delegates to
    # ``lanes.compute.mission_has_code`` (has_code_lanes floor OR has_code_wps),
    # so a legacy lanes/coord mission's per-WP frontmatter ambiguity can never
    # flip this to "no code" the way the bare kind check alone did.
    mission_has_code = _mission_has_code_fn(lanes_manifest, _wp_kinds_for_manifest(repo_root, feature_dir.name))
    allowed_branches = {lanes_manifest.target_branch}
    if mission_has_code:
        allowed_branches.add(lanes_manifest.mission_branch)

    if branch is None or branch not in allowed_branches:
        allowed_label = ", ".join(sorted(branch_name for branch_name in allowed_branches if branch_name))
        current_label = branch or "detached HEAD"
        message = f"Acceptance must run on mission or target branch ({allowed_label}), not {current_label}"
        activity_issues.append(message)
        blocked_checks.append(AcceptanceCheckDiagnostic(check="mission_branch", detail=message))
        _append_skipped_lane_checks(
            skipped_checks,
            reason="current branch is neither mission branch nor target branch",
            include_matrix_presence=True,
        )
        return False

    if not mission_has_code:
        _append_skipped_lane_checks(
            skipped_checks,
            reason="planning_artifact-only missions do not produce acceptance-matrix.json",
            include_matrix_presence=True,
        )
        return False

    return True


def _acceptance_gate_context(
    repo_root: Path,
    feature_dir: Path,
    *,
    branch: str | None = None,
    owned: OwnedCheckout | None = None,
) -> GateExecutionContext:
    """Build the ACCEPT-phase :class:`GateExecutionContext` for the acceptance matrix.

    The ONE gate-context construction door for the acceptance-matrix gate (GEC-1 /
    T017): it resolves the surface through the WP02 total resolver
    (:func:`mission_runtime.resolve_artifact_surface`) so the four ``CoordState``
    answers are total by construction — ``DELETED`` raises ``CoordinationBranchDeleted``
    (C3 fail-loud), ``UNMATERIALIZED`` raises ``CoordinationWorktreeUnmaterialized``
    (#4959; :func:`_evaluate_acceptance_matrix` turns it into cannot-evaluate, #5399),
    ``EMPTY`` stamps ``PRIMARY`` (the create window), ``MATERIALIZED`` stamps ``COORD``. The gate is then handed the surface
    (never an ambient ``repo_root`` / cwd), and every verdict/refusal it emits names
    the returned ``surface_kind`` + ``ref`` (C6). ``ref`` prefers the caller-observed
    currently-checked-out ``branch`` (GEC-2 / C5's reference point — see
    :func:`_assert_ref_agreement`), falling back to the mission target branch, then
    the ``HEAD`` symbolic ref when neither is available.

    ``feature_dir.name`` (not the raw operator handle) keys the resolver: the caller
    threads the ``PRIMARY_METADATA`` read dir, whose ``.name`` is a materialized
    primary dir name the resolver canonicalizes — mirroring
    ``collect_feature_summary``'s own ``primary_slug = feature_dir.name`` (C-002).
    """
    from mission_runtime import MissionArtifactKind

    from specify_cli.acceptance.execution_context import (
        LifecyclePhase,
        build_gate_execution_context,
    )

    ref = _acceptance_gate_ref(feature_dir, branch)
    return build_gate_execution_context(
        repo_root,
        feature_dir.name,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        phase=LifecyclePhase.ACCEPT,
        ref=ref,
        owned=owned,
    )


def _acceptance_gate_ref(feature_dir: Path, branch: str | None) -> str:
    """The reference point the acceptance-matrix gate context is built against.

    The caller-observed ``branch`` first, then the mission target branch, then
    ``HEAD`` — shared by :func:`_acceptance_gate_context` and the #5399
    unmaterialized-coord refusal so both name the same ``ref`` (C6).
    ``_target_branch_for_feature`` is resolved off the live
    ``specify_cli.acceptance`` namespace at call time (not a top-level import) so
    the WP01 characterization monkeypatch of ``read_target_branch_from_meta``
    stays visible.
    """
    from specify_cli import acceptance as _acceptance_pkg

    return branch or _acceptance_pkg._target_branch_for_feature(feature_dir) or "HEAD"


def _unmaterialized_coord_cannot_evaluate(exc: Exception, ref: str) -> CannotEvaluate:
    """#5399: the cannot-evaluate outcome for an unmaterialized coordination worktree.

    #4959 made the placement seam raise ``CoordinationWorktreeUnmaterialized`` when
    the mission's coordination branch exists but its worktree was never checked
    out. The acceptance matrix is homed on that COORD surface, so the gate has no
    authoritative surface to judge: it refuses (fail closed, GEC-5 / C2) naming the
    unmaterialized COORD home and carrying the exception's remediation text, never
    a pass and never a raw traceback.
    """
    from specify_cli.acceptance.execution_context import (
        CannotEvaluate,
        CannotEvaluateReason,
    )

    return CannotEvaluate(
        reason=CannotEvaluateReason.SURFACE_CANNOT_HOLD_FACT,
        detail=f"coordination worktree is not materialized ({getattr(exc, 'error_code', type(exc).__name__)}): {exc}",
        surface_kind=TopologySurface.COORD,
        ref=ref,
    )


def _assert_ref_agreement(context: GateExecutionContext) -> GateSurfaceRefMismatch | None:
    """GEC-2 / C5: refuse rather than judge a surface that drifted from its ref.

    Ref-agreement is asserted only for a ``PRIMARY``-stamped surface. ``context.ref``
    names the branch this evaluation resolved as its reference point — the
    caller-observed currently-checked-out branch when available, else the mission's
    target branch (:func:`_acceptance_gate_context`) — and a ``PRIMARY`` surface
    lives in that SAME checkout, so the two must agree absent a race between when
    ``branch`` was read and when this gate runs (mirroring the ``safe_commit``
    HEAD-vs-destination assert this method is built on).

    A ``COORD``-stamped surface is a genuinely different worktree on its OWN
    coordination branch — ``ref`` was never meant to name that branch (C6 pins it to
    the mission's target/observed branch even for a coord-topology mission,
    ``test_c6_recorded_judgement_names_surface_and_ref``), so asserting branch
    identity there would be a category error: it would refuse every legitimate
    coordination-topology run, not merely a drifted one, which is precisely the
    topology-neutrality GEC-4/C7 forbids. That surface's structural validity is
    already guarded by GEC-3's total resolution (``CoordinationBranchDeleted``) and
    GEC-5's create-window check (:func:`_matrix_surface_cannot_hold`); this method
    does not duplicate those with an inapplicable branch comparison.

    Also a no-op when ``context.surface`` does not exist on disk: a surface with
    nothing checked out there has no branch to have drifted FROM (there is no git
    worktree to read), and the WP18 unit-level deferral tests
    (``tests/integration/test_deferral_enforcement_and_disclosure.py``, "no git
    shelling required" by design) drive this function against a synthetic,
    never-created ``tmp_path`` surface -- a distinct absence already reported
    honestly elsewhere (e.g. "acceptance-matrix.json ... not found"), not a
    ref-agreement refusal to invent here.
    """
    if context.surface_kind is not TopologySurface.PRIMARY:
        return None
    if not context.surface.exists():
        return None
    try:
        context.assert_at_ref()
    except GateSurfaceRefMismatch as exc:
        return exc
    return None


def _record_ref_mismatch_cannot_evaluate(
    exc: GateSurfaceRefMismatch,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
) -> None:
    """Record the C5 ref-mismatch refusal, naming the surface + expected/actual ref (C6).

    Mirrors :func:`_record_matrix_cannot_evaluate`'s shape: a blocking diagnostic and
    the matching skipped-checks fan-out, never a pass/fail verdict.
    """
    detail = (
        f"Acceptance matrix cannot be evaluated ({exc.error_code}): surface "
        f"(stamped {exc.surface_kind.value}) is at {exc.actual_ref!r} but the gate "
        f"expected it at {exc.expected_ref!r} [surface={exc.surface_kind.value} "
        f"ref={exc.expected_ref}]"
    )
    activity_issues.append(detail)
    blocked_checks.append(AcceptanceCheckDiagnostic(check="acceptance_matrix_cannot_evaluate", detail=detail))
    _append_skipped_lane_checks(skipped_checks, reason=exc.error_code)


def _acceptance_matrix_read_dir(repo_root: Path, feature_dir: Path) -> Path:
    """Resolve the dir the acceptance-matrix must be READ from for this mission.

    ``ACCEPTANCE_MATRIX`` is a *coordination*-partition kind
    (:data:`mission_runtime.artifacts._PLACEMENT_ARTIFACT_KINDS`): under coord
    topology ``write_acceptance_matrix`` lands it on the coordination
    worktree's ``feature_dir`` (T008), NOT the PRIMARY ``feature_dir`` threaded
    through the gate pipeline — that ``feature_dir`` is the ``PRIMARY_METADATA``
    read dir (``collect_feature_summary``), which resolves PRIMARY for every
    topology. Reading the matrix off the raw PRIMARY ``feature_dir`` therefore
    reports a false "acceptance-matrix.json not found" for a coord-topology
    mission whose matrix correctly lives on coord.

    Thin projection of the surface off :func:`_acceptance_gate_context` (the ONE
    gate-context door) — the ``.surface`` of the resolved
    :class:`GateExecutionContext`. The seam resolves the coord surface ONLY when the
    mission's stored topology routes through coordination AND that surface is
    materialised (``MATERIALIZED``); otherwise it resolves the primary mission dir
    AFFIRMATIVELY (AH-2) — so flat / ``SINGLE_BRANCH`` / ``LANES`` and the ``EMPTY``
    create window read exactly where they do today (regression-preserving); an
    ``UNMATERIALIZED`` coord worktree raises ``CoordinationWorktreeUnmaterialized``
    (#4959). A ``DELETED`` coordination branch raises
    :class:`CoordinationBranchDeleted` (C3 "fail loud"): a deleted coord branch
    carries unmerged acceptance state, so accept must refuse, not silently pass on a
    stale surface.
    """
    return _acceptance_gate_context(repo_root, feature_dir).surface


def _matrix_surface_cannot_hold(
    context: GateExecutionContext,
    repo_root: Path,
    feature_dir: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> CannotEvaluate | None:
    """GEC-5 / C2: refuse when the coord-homed matrix is judged on a PRIMARY stamp.

    A stamp is not permission: when the acceptance matrix's declared home is
    ``COORD`` (a coordination-routing mission) but the resolved surface came back
    stamped ``PRIMARY`` — the ``EMPTY`` create-window
    substitution — the coordination surface is not materialised, so the primary
    surface cannot hold the coord-homed matrix. Returns the distinguishable
    cannot-evaluate outcome (naming its surface + ref) rather than reading an empty
    primary and passing by default (#2885). Returns ``None`` for flat /
    ``SINGLE_BRANCH`` / ``LANES`` (declared home IS primary, AH-2) and for a
    materialised coord surface — both can legitimately hold the fact (C7 neutrality:
    the flat and coord-materialised cases behave identically).

    coord-write-placement-closure-01KYCF83 WP07 (T034 fold): ``declared_home_surface``
    now delegates to the shared ``mission_runtime.declared_read_surface`` predicate
    the new fail-loud read authority is built from — this call site is unchanged,
    but it now converges on the SAME partition+topology computation rather than a
    second independent one (no behavioral change; the guard still refuses here,
    it just shares its declared-home answer with the read authority).
    """
    from specify_cli.acceptance.execution_context import declared_home_surface

    from mission_runtime import MissionArtifactKind

    home = declared_home_surface(
        repo_root,
        feature_dir.name,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        owned=owned,
    )
    return context.surface_cannot_hold(home)


def _record_matrix_cannot_evaluate(
    cannot: CannotEvaluate,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
) -> None:
    """Record the cannot-evaluate outcome, naming the surface + ref it refused on (C6)."""
    detail = f"Acceptance matrix cannot be evaluated ({cannot.reason.value}): {cannot.detail} [surface={cannot.surface_kind.value} ref={cannot.ref}]"
    activity_issues.append(detail)
    blocked_checks.append(AcceptanceCheckDiagnostic(check="acceptance_matrix_cannot_evaluate", detail=detail))
    _append_skipped_lane_checks(skipped_checks, reason=cannot.reason.value)


def _judge_acceptance_matrix(
    acc_matrix: Any,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
) -> None:
    """FR-004: validate evidence and derive the verdict from ``acc_matrix``.

    Extracted so both the diagnose (``mutate_matrix=False``) leg and the
    post-seam leg (which judges the FRESH, re-read-and-spliced matrix, never
    accept's own pre-lock snapshot) share exactly one judgement path.
    """
    from specify_cli.acceptance.matrix import VERDICT_PASS_PENDING_CONSOLIDATION, validate_matrix_evidence

    for err in validate_matrix_evidence(acc_matrix):
        activity_issues.append(f"Evidence: {err}")

    verdict = acc_matrix.overall_verdict
    if verdict == "fail":
        activity_issues.append("Acceptance matrix verdict is 'fail' — negative invariants or criteria not satisfied")
    elif verdict == "pending":
        activity_issues.append("Acceptance matrix verdict is 'pending' — criteria or invariants have not been verified")
    elif verdict == VERDICT_PASS_PENDING_CONSOLIDATION:
        # NI-5 (C5): deferral does NOT block acceptance — this is deliberately a
        # skipped-check (informational), never an activity issue. NI-7: disclose to
        # the operator that the mission loop will not verify the deferral (it has a
        # single pre-consolidation reader) — the post-consolidation verification op
        # / PR CI is the enforcer, and the mission cannot reach ``done`` until then.
        skipped_checks.append(
            AcceptanceCheckDiagnostic(
                check="negative_invariants_deferred",
                detail=(
                    "One or more negative invariants are deferred to post-consolidation "
                    "verification; acceptance is not blocked, but this loop does not verify "
                    "them — the post-consolidation op (or PR CI) must, before the mission is done."
                ),
            )
        )


def _persist_matrix_under_lock(
    repo_root: Path,
    feature_dir: Path,
    matrix_dir: Path,
    snapshot: Any,
    judged: Any,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
) -> Any | None:
    """FR-003/FR-004/FR-005: splice accept's owned rows into the FRESH matrix
    through WP01's shared locked seam, instead of unconditionally overwriting
    the matrix with accept's own pre-lock snapshot (#4974's root defect).

    ``snapshot`` is accept's pre-lock read (taken BEFORE review-evidence
    population / negative-invariant enforcement mutated ``judged`` in place);
    ``judged`` is that same matrix AFTER those mutations. The seam re-reads the
    matrix fresh under the lock, splices in only the rows accept owns
    (:func:`~specify_cli.acceptance.matrix.splice_owned_rows`, FR-003), and
    writes the result -- so a verdict committed by a concurrent
    ``acceptance-verdict`` invocation while accept ran its (possibly slow)
    negative-invariant checks is never silently erased.

    ``commit=False``: mirrors the pre-existing ``--no-commit`` / diagnose
    contract (C-003) -- the accept-owned matrix may be MUTATED here but this
    call never commits; the real accept-commit path picks the resulting dirt
    up via ``cli/commands/accept.py``'s residual-artifact sweep, itself routed
    through the WP03 seam.

    Returns the FRESH matrix on success, or ``None`` on a
    :class:`~specify_cli.status.FeatureStatusLockTimeoutError` (FR-005: fails
    CLOSED -- no write happens, and the caller records a dedicated
    ``acceptance_matrix_lock`` blocked check so ``summary.ok`` is False).
    """
    from specify_cli.acceptance.matrix import locked_reread_splice_and_write, splice_owned_rows
    from specify_cli.status import FeatureStatusLockTimeoutError

    try:
        fresh_matrix, _write_result = locked_reread_splice_and_write(
            repo_root=repo_root,
            mission_slug=feature_dir.name,
            matrix_dir=matrix_dir,
            splice=lambda fresh: splice_owned_rows(fresh, snapshot, judged),
            commit=False,
        )
    except FeatureStatusLockTimeoutError as exc:
        message = f"Acceptance matrix lock timed out while recording accept's judgement: {exc}"
        activity_issues.append(message)
        blocked_checks.append(AcceptanceCheckDiagnostic(check="acceptance_matrix_lock", detail=message))
        _append_skipped_lane_checks(skipped_checks, reason="mission status lock timed out")
        return None
    return fresh_matrix


def _populate_and_enforce_matrix(
    repo_root: Path,
    matrix_dir: Path,
    acc_matrix: Any,
    context: GateExecutionContext,
) -> None:
    """NFR-001: review-evidence population + negative-invariant enforcement,
    run OUTSIDE the status lock, mutating ``acc_matrix`` IN PLACE.

    Called only on the ``mutate_matrix=True`` leg, against accept's pre-lock
    read -- never inside :func:`_persist_matrix_under_lock`'s locked span.
    """
    from specify_cli.acceptance.matrix import enforce_negative_invariants, populate_criteria_from_review_evidence

    if getattr(acc_matrix, "criteria", None) is not None:
        # FR-008 (IC-04, governance-at-the-gate WP04): auto-derive pending
        # ``code_review`` criterion rows from WP review evidence BEFORE the
        # verdict is read below -- closes the "criterion rows never
        # populated" gap (the matrix used to stay scaffolded ``pending``
        # forever unless an operator hand-invoked ``agent mission
        # acceptance-verdict``). Design + scope are documented on
        # :func:`~specify_cli.acceptance.matrix.populate_criteria_from_
        # review_evidence` itself. The ``getattr`` guard tolerates unit-test
        # doubles (bare ``SimpleNamespace`` fixtures elsewhere in this
        # module's test suite) that model only the fields their own test
        # cares about.
        acc_matrix.criteria = populate_criteria_from_review_evidence(matrix_dir, acc_matrix.criteria)

    if acc_matrix.negative_invariants:
        # WP04 T023: hand the gate context to the enforcer so a pending invariant
        # whose subject cannot exist on this surface defers (NI-3/C4) instead of
        # reporting a false still_present, and a freshly judged result is stamped
        # with the surface + ref it was established against (NI-1 provenance).
        acc_matrix.negative_invariants = enforce_negative_invariants(repo_root, acc_matrix.negative_invariants, context=context)


def _evaluate_acceptance_matrix(
    repo_root: Path,
    feature_dir: Path,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
    *,
    mutate_matrix: bool,
    branch: str | None = None,
    owned: OwnedCheckout | None = None,
) -> Path | None:
    """Read/enforce/validate the acceptance matrix once the branch gate passed.

    The matrix is judged strictly from the gate context's surface (C1) — the WP02
    total resolver picks coord vs primary; this gate never re-reads an ambient
    ``repo_root`` / cwd. GEC-2 (C5) refuses rather than judges when a ``PRIMARY``
    surface has drifted from the branch this evaluation resolved as its reference
    point (:func:`_assert_ref_agreement`). GEC-5 (C2) short-circuits to
    cannot-evaluate when the coord-homed matrix would be judged against a
    create-window PRIMARY substitution, rather than silently passing on an empty
    surface (#2885).

    NFR-001 / FR-003 / FR-004: review-evidence population and negative-invariant
    enforcement (both potentially slow) run OUTSIDE the status lock, against a
    ``snapshot`` deep-copied immediately after the pre-lock read. When
    ``mutate_matrix`` is True, the judged result is then spliced into the FRESH,
    re-read matrix under WP01's shared locked seam
    (:func:`_persist_matrix_under_lock`) rather than overwritten wholesale — a
    verdict a concurrent ``acceptance-verdict`` invocation committed in the
    meantime is judged, not erased (#4974). Evidence validation and the
    ``overall_verdict`` judgement always run against that FRESH matrix.

    Returns the resolved matrix directory when the matrix was found and judged
    (mutated or not) — threaded up to :attr:`AcceptanceSummary.
    acceptance_matrix_dir` (FR-010) — or ``None`` when the gate stopped before
    a matrix could be judged (ref-mismatch refusal, cannot-hold refusal, a
    missing matrix file, or a lock-acquisition timeout).
    """
    from specify_cli.acceptance.matrix import read_acceptance_matrix
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized

    try:
        context = _acceptance_gate_context(repo_root, feature_dir, branch=branch, owned=owned)
    except CoordinationWorktreeUnmaterialized as exc:
        # #5399: keep #4959's raise at the context build; the gate refuses cleanly.
        unmaterialized = _unmaterialized_coord_cannot_evaluate(exc, _acceptance_gate_ref(feature_dir, branch))
        _record_matrix_cannot_evaluate(unmaterialized, activity_issues, skipped_checks, blocked_checks)
        return None
    ref_mismatch = _assert_ref_agreement(context)
    if ref_mismatch is not None:
        _record_ref_mismatch_cannot_evaluate(ref_mismatch, activity_issues, skipped_checks, blocked_checks)
        return None

    cannot = _matrix_surface_cannot_hold(context, repo_root, feature_dir, owned=owned)
    if cannot is not None:
        _record_matrix_cannot_evaluate(cannot, activity_issues, skipped_checks, blocked_checks)
        return None

    matrix_dir: Path = context.surface
    acc_matrix = read_acceptance_matrix(matrix_dir)
    if acc_matrix is None:
        message = (
            "Acceptance matrix (acceptance-matrix.json) is required for lane-based "
            "features but was not found. This file is normally scaffolded "
            "automatically. If it is missing, regenerate it: "
            f"spec-kitty agent mission finalize-tasks --mission {feature_dir.name}"
        )
        activity_issues.append(message)
        blocked_checks.append(AcceptanceCheckDiagnostic(check="acceptance_matrix", detail=message))
        _append_skipped_lane_checks(
            skipped_checks,
            reason="acceptance-matrix.json is missing",
        )
        return None

    if not mutate_matrix:
        # Diagnose mode: read-only, no lock, no write (spec.md Edge Cases).
        if acc_matrix.negative_invariants:
            skipped_checks.append(
                AcceptanceCheckDiagnostic(
                    check="negative_invariants",
                    detail="Negative invariant execution skipped: diagnose mode is read-only",
                )
            )
        _judge_acceptance_matrix(acc_matrix, activity_issues, skipped_checks)
        return matrix_dir

    # C-004: ``matrix_dir`` is resolved ONCE above and reused unchanged as both
    # the re-read base and the write target -- never re-derived after this point.
    snapshot = deepcopy(acc_matrix)
    _populate_and_enforce_matrix(repo_root, matrix_dir, acc_matrix, context)

    fresh_matrix = _persist_matrix_under_lock(
        repo_root,
        feature_dir,
        matrix_dir,
        snapshot,
        acc_matrix,
        activity_issues,
        skipped_checks,
        blocked_checks,
    )
    if fresh_matrix is None:
        return None

    _judge_acceptance_matrix(fresh_matrix, activity_issues, skipped_checks)
    return matrix_dir


def _check_lane_gates(
    repo_root: Path,
    feature_dir: Path,
    branch: str | None,
    activity_issues: list[str],
    skipped_checks: list[AcceptanceCheckDiagnostic],
    blocked_checks: list[AcceptanceCheckDiagnostic],
    *,
    mutate_matrix: bool = True,
    owned: OwnedCheckout | None = None,
) -> LaneGateOutcome:
    """Enforce lane-based acceptance gates and acceptance matrix.

    Returns a :class:`LaneGateOutcome` naming the matrix surface the
    acceptance-matrix gate actually evaluated (WP02 / FR-010), or -- when the
    gate never ran -- the ONE legitimate skip reason
    (:data:`PLANNING_ARTIFACT_ONLY_SKIP_REASON`) a caller may use to bypass the
    FR-010 pre-stamp guard. Every other "never ran" case (a blocked
    lanes-manifest/branch gate, a cannot-evaluate refusal, a missing matrix, or
    a lock timeout) already leaves ``summary.ok`` False via ``activity_issues``
    / ``blocked_checks`` -- but the outcome still carries no skip reason, so
    the guard fails closed rather than trusting that invariant blindly.
    """
    lanes_manifest = _resolve_lanes_manifest_or_stop(feature_dir, activity_issues, skipped_checks, blocked_checks)
    if lanes_manifest is None:
        return LaneGateOutcome()

    blocked_before = len(blocked_checks)
    should_continue = _evaluate_branch_gate(repo_root, lanes_manifest, feature_dir, branch, activity_issues, skipped_checks, blocked_checks)
    if not should_continue:
        # The bypass is granted only when the branch gate stopped at its
        # no-code branch; a mission the branch gate BLOCKED for another
        # reason (target mismatch, wrong branch) gets no skip reason -- and
        # never needs the has_code_wps read at all (short-circuits before
        # it, so a blocked-before-lanes-resolved manifest never needs a
        # ``.lanes`` attribute).
        branch_gate_blocked = len(blocked_checks) > blocked_before
        if branch_gate_blocked:
            return LaneGateOutcome()

        from specify_cli.lanes.compute import mission_has_code as _mission_has_code_fn

        mission_has_code = _mission_has_code_fn(lanes_manifest, _wp_kinds_for_manifest(repo_root, feature_dir.name))
        if not mission_has_code:
            return LaneGateOutcome(skip_reason=PLANNING_ARTIFACT_ONLY_SKIP_REASON)
        return LaneGateOutcome()

    matrix_dir = _evaluate_acceptance_matrix(
        repo_root,
        feature_dir,
        activity_issues,
        skipped_checks,
        blocked_checks,
        mutate_matrix=mutate_matrix,
        branch=branch,
        owned=owned,
    )
    return LaneGateOutcome(matrix_dir=matrix_dir)


__all__: list[str] = []
