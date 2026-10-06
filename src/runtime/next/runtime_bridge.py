"""Bridge between CLI ``decide_next()`` and the CLI-internal ``_internal_runtime`` engine.

The runtime is now internalized as part of mission
``shared-package-boundary-cutover-01KQ22DS``; production code no longer imports
the standalone ``spec-kitty-runtime`` PyPI package.

Maps the CLI's Decision dataclass to the runtime's NextDecision by:

1. Starting or loading a mission run (persisted under .kittify/runtime/)
2. Delegating step planning to the runtime DAG planner
3. Handling WP-level iteration within "implement" and "review" steps
4. Enforcing CLI-level guards (artifact checks, WP status)
5. Preserving the existing JSON output contract

Underscore-prefixed functions in the ``runtime_bridge_*`` seam modules that the
bridge calls are a package-internal seam API, not module-private.

Run state is stored locally under ``.kittify/runtime/runs/<run_id>/``.
A tracked-mission-to-run compatibility index currently lives at
``.kittify/runtime/feature-runs.json``.
"""

# ─────────────────────────────────────────────────────────────────────────────
# #2531 DECOMPOSITION IN PROGRESS (mission runtime-bridge-degod-01KX8M1C).
#
# This module is being progressively decomposed from a single ~3800-LOC /
# 62-symbol god module into cohesive, independently-tested seams under
# ``runtime/next/``. Extracted so far:
#
#   runtime_bridge_engine.py   sole home of ``_internal_runtime`` engine /
#                              planner private access (FR-013); also owns the
#                              ``advance_run_state_after_composition`` logic
#                              (former CC23 body, reduced to <=15); callers
#                              here and in the composition seam call it on the
#                              engine seam, and a test patches it there.
#
#   runtime_bridge_retrospective.py   sole home of the self-contained
#                              Confirm.ask-gated retrospective / learning-
#                              capture cluster (FR-006). The bridge calls the
#                              cluster on the seam (``_retrospective_seam.<name>``)
#                              and keeps no forwarder for it; a test patches a
#                              retrospective symbol on the seam.
#
#   runtime_bridge_io.py       sole home of the narrow I/O ports (IC-04):
#                              feature-runs.json index, template/pack
#                              discovery, run lifecycle, the OperationalContext
#                              builder, the FR-009 gather_artifact_presence
#                              fact-port, and the pure resolve_commit_target
#                              lifted out of _wrap_with_decision_git_log. The
#                              bridge calls them on the seam and keeps no
#                              forwarder; two names are re-exported here for
#                              callers outside the package (see below).
#
#   runtime_bridge_cores.py    sole home of the pure, zero-dependency leaves
#                              (FR-009): the tasks.md parse family and the
#                              guard inversion (`evaluate_guards(snapshot)`
#                              folding `_check_cli_guards` /
#                              `_check_composed_action_guard` /
#                              `_check_requirement_mapping_ready`'s decision
#                              tail over the WP05 `ArtifactPresenceSnapshot`
#                              fact-port). The bridge calls the parse family
#                              on the cores seam; `_parse_requirement_refs_
#                              from_tasks_md` takes the requirement grammar as
#                              a ``grammar=`` argument, which the bridge call
#                              site supplies.
#
#   runtime_bridge_cores.py    ALSO owns the Decision-builder (FR-011,
#                              WP07): ``DecisionEnvelope`` + ``step_or_
#                              blocked`` collapse the 29 open-coded
#                              ``Decision(...)`` constructions (+ the 4x
#                              ``_state_to_action -> _build_prompt_or_error
#                              -> step-or-blocked`` triad) that used to be
#                              scattered across this module's three public
#                              entries. This module keeps ``_materialize_
#                              decision`` (the thin residual wrapper
#                              supplying the production ``prompt_exists``
#                              port) plus ``_map_wp_step_decision`` /
#                              ``_map_non_wp_step_decision`` /
#                              ``_build_decision_required_prompt_file``, the
#                              extractions that keep ``_map_runtime_
#                              decision`` / ``query_current_state`` at or
#                              under the complexity ceiling.
#
#   runtime_bridge_composition.py   sole home of the composition-dispatch
#                              cluster (WP08): the dispatch entry
#                              (``_dispatch_via_composition``), the
#                              composed-action guard
#                              (``_check_composed_action_guard``), the
#                              composition-input resolution helpers, the
#                              research/documentation guard-fact readers, and
#                              — the FR-008 headline — the
#                              ``_should_dispatch_via_composition`` selection
#                              seam isolated as a clean, gates-#2535-free
#                              predicate for a future WP14 consumer to route
#                              through. The bridge calls it on the seam; it
#                              keeps no forwarder for any of its names.
#
#   runtime_bridge_identity.py   sole home of the hottest fracture line
#                              (WP10, LAST): coord-branch naming
#                              (``_resolve_coordination_branch``), mission-ULID
#                              resolution (``_resolve_mission_ulid``), and
#                              primary-feature-dir resolution
#                              (``_primary_runtime_feature_dir``) — the scars
#                              #2091/#1978/#1918/#1814/#2069 cluster. The
#                              bridge calls them on the identity seam, and the
#                              two callers of ``_primary_runtime_feature_dir``
#                              inside the seam call it directly, so a test
#                              patches it on ``runtime_bridge_identity``.
#                              ``_wrap_with_decision_git_log`` (the cluster's
#                              caller) and ``_mission_routes_through_
#                              coordination`` are KEEP-IN-PLACE here, unmoved.
#
# This is the FINAL extraction (WP10) — see
# ``kitty-specs/runtime-bridge-degod-01KX8M1C/``.
#
# RULES (do NOT regress):
#   * Never reach into ``_internal_runtime.engine`` / ``.planner`` directly
#     from this module — go through ``runtime_bridge_engine`` (arch-guarded,
#     see ``tests/runtime/test_bridge_engine.py``).
#   * ``__all__`` (below) covers the 8 public names only (governs
#     ``import *``). The bridge defines no forwarders for names a seam owns;
#     a test patches a seam-owned name on its owning seam.
#
# De-godding effort: https://github.com/Priivacy-ai/spec-kitty/issues/2531
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import dataclasses
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from kernel.clock import now_utc_iso

from runtime.next._internal_runtime import (
    MissionRunRef,
    NextDecision,
    next_step as runtime_next_step,
    provide_decision_answer as runtime_provide_decision_answer,
)
from runtime.next._internal_runtime.schema import ActorIdentity, MissionRuntimeError, load_mission_template_file
from runtime.next import runtime_bridge_composition as _composition
from runtime.next import runtime_bridge_cores as _cores
from runtime.next import runtime_bridge_decision_log as _decision_log
from runtime.next import runtime_bridge_decision_mapping as _mapping
from runtime.next import runtime_bridge_engine as _engine_adapter
from runtime.next import runtime_bridge_identity as _identity_seam
from runtime.next import runtime_bridge_io as _io_seam

# Public names kept for callers outside this package (CLI modules look them up
# here); they are the very same objects the owning seams define. Runtime-internal
# calls go through the owning seam (``_io_seam.get_or_start_run(...)``), so patch
# the seam to intercept the runtime's own calls; patching these names here only
# affects the CLI callers that import them from the bridge.
from runtime.next.runtime_bridge_decision_log import DecisionGitLogUnavailable
from runtime.next.runtime_bridge_io import build_operational_context_for_claim, get_or_start_run
from runtime.next import runtime_bridge_retrospective as _retrospective_seam

# The bridge keeps no forwarders or self-aliases for names the seams own: a
# parse-family, retrospective or composition-input helper is called on its
# owning seam (``_cores`` / ``_retrospective_seam`` / ``_composition``) at each
# call site below, and a test patches it there.

from specify_cli.core.constants import MISSION_TYPE_SOFTWARE_DEV
from specify_cli.mission import get_mission_type
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.status import CanonicalStatusNotFoundError
from specify_cli.status import Lane
from specify_cli.status import wp_state_for
from specify_cli.status_lanes import is_acceptable_ending
from runtime.next.decision import (
    Decision,
    DecisionKind,
    _build_prompt_or_error,
    _build_prompt_safe,
    _compute_wp_progress,
    _state_to_action,
)
from runtime.next._internal_runtime.events import RuntimeEventEmitter, runtime_emitter_for_mission, seed_runtime_emitter
from mission_runtime import ActionContextError, OwnedCheckout, OwnedRefusalCode

logger = logging.getLogger(__name__)

# MISSION_RUNTIME_YAML / MISSION_YAML moved to runtime_bridge_io.py (T017 —
# their only residual users, the discovery cluster, moved with them).


def _resolve_owned_coordination_workspace(
    workspace_type: Any,
    repo_root: Path,
    mission_slug: str,
    mid8: str,
) -> Path:
    """Materialize after transient shared git-worktree registry contention.

    Two distinct owned missions may reach ``git worktree add`` concurrently.
    Their filesystem destinations do not overlap, but git serializes updates to
    the shared worktree registry.  Retry only that subprocess failure; durable
    failures still surface unchanged after a short bounded window.  This avoids
    a second persistent lock file and therefore cannot leak ownership locks.
    """
    import subprocess
    import time

    attempts = 20
    for attempt in range(attempts):
        try:
            resolved: Path = workspace_type.resolve(repo_root, mission_slug, mid8)
            return resolved
        except subprocess.CalledProcessError as exc:
            if not _is_transient_git_worktree_contention(exc):
                raise
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
    raise AssertionError("unreachable coordination workspace retry tail")


def _is_transient_git_worktree_contention(
    exc: Any,
) -> bool:
    """Recognize only Git's shared lock-contention diagnostics."""
    if getattr(exc, "returncode", None) != 128:
        return False
    output = "\n".join(str(value) for value in (getattr(exc, "stderr", ""), getattr(exc, "stdout", "")) if value).casefold()
    lock_exists = "file exists" in output and ("config.lock" in output or ("unable to create" in output and ".lock" in output))
    return lock_exists or ("could not lock config file" in output and "file exists" in output) or ("another git process" in output and "lock" in output)


# FR-001 / C-IC02: the typed read-path codes whose fidelity MUST be preserved
# across the next-family catch-sites. These are *read-path topology* failures
# (the mission exists but its status read surface is broken / ambiguous), as
# opposed to a genuinely-missing mission (``FEATURE_CONTEXT_UNRESOLVED`` and the
# like), which legitimately stays ``MISSION_NOT_FOUND``. Collapsing a code in
# this set into ``MISSION_NOT_FOUND`` mis-routes the operator (the disease #15).
_READ_PATH_ERROR_CODES: frozenset[str] = frozenset(
    {
        "STATUS_READ_PATH_NOT_FOUND",
        "COORDINATION_BRANCH_DELETED",
        "MISSION_AMBIGUOUS_SELECTOR",
    }
)


def _is_read_path_error(exc: object) -> bool:
    """Return True when *exc* carries a typed read-path topology code (C-IC02)."""
    return getattr(exc, "code", None) in _READ_PATH_ERROR_CODES


class QueryModeValidationError(ValueError):
    """Raised when query mode cannot produce a truthful read-only preview."""


class MissionNotFoundError(Exception):
    """Raised when a mission handle cannot be resolved to an existing mission.

    Carries the attempted handle so callers can include it in structured
    error output (FR-004 / WP03 — fail-closed next query mode), plus an
    actionable ``next_step`` remediation so operators are told concretely how
    to recover (list available missions / verify the handle). The ``next_step``
    affordance restores the operator guidance the superseded
    ``QueryModeValidationError`` used to carry (#1911).
    """

    error_code: str = "MISSION_NOT_FOUND"

    def __init__(self, handle: str, next_step: str | None = None) -> None:
        self.handle = handle
        # #4723: 'spec-kitty mission list' enumerates mission TYPES
        # (software-dev, research, …), never real mission handles — it cannot
        # reveal a colliding pair of missions, and following its own advice
        # would not surface anything actionable. 'spec-kitty doctor topology'
        # enumerates every mission's real handle from kitty-specs/.
        self.next_step = next_step or (f"Run 'spec-kitty doctor topology' to see available missions, then re-run with a valid handle (attempted: '{handle}').")
        super().__init__(f"Mission not found: '{handle}'")


# ---------------------------------------------------------------------------
# Feature → Run index — owned by runtime_bridge_io.py (T017).
#
# tasks.md parse family — bodies moved to runtime_bridge_cores.py (#2531
# WP06, T021; verbatim, zero-dependency pure leaf). ``TASKS_GLOB`` and the
# WP-iteration step set are owned by runtime_bridge_decision_mapping.py
# (#2560); the guards below read them there.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# WP advance guards
# ---------------------------------------------------------------------------


def _should_advance_wp_step(
    step_id: str,
    feature_dir: Path,
    *,
    repo_root: Path | None = None,
    mission_slug: str | None = None,
    owned: OwnedCheckout | None = None,
) -> bool:
    """Check if all WPs are done for this phase, meaning we should advance.

    For implement: all WPs must be handed off, accepted, done, or reach an
    acceptable ending (operator-canceled).
    For review: all WPs must be approved, done, or canceled-with-operator-
    provenance (#3780, D2/D6/D11).

    Routes through WP01's :func:`committed_authority.wp_ending` — a single
    status reduction per WP that yields lane AND operator-provenance in one
    read (C-004), fronted by the same explicit fail-loud event-log gate
    ``get_wp_lane`` used (C-003/D6): a genuinely-absent committed status log
    still raises ``CanonicalStatusNotFoundError`` here, never a silent
    ``False``.

    FR-009 (#3884): when the caller opts in by supplying ``repo_root`` (no
    separate flag, mirroring the #3704 precedent), the ``tasks/`` directory
    this function reads is anchored via ``mission_runtime.placement_seam``'s
    PRIMARY-partition resolution for ``MissionArtifactKind.WORK_PACKAGE_TASK``
    instead of the raw ``feature_dir`` -- a coord-topology mission's
    coordination-worktree ``feature_dir`` never receives ``tasks/WP*.md``
    (a PRIMARY-partition artifact), so the unanchored read hit this
    function's own no-``tasks/``-dir early return below and skipped the
    per-WP loop entirely, regardless of whether FR-004's disjunct exists. Any
    coord-less topology (``SINGLE_BRANCH``/``LANES``) -- where ``feature_dir``
    already IS the primary directory -- sees no behavior change: the anchor
    resolves to the same directory for both. May raise ``MissionSelectorAmbiguous`` for a genuinely
    ambiguous ``mission_slug`` handle -- caught at this function's one real
    call site (``_dn_dependency_gate``, FR-010).
    """
    anchor_dir = feature_dir
    if repo_root is not None:
        from mission_runtime import MissionArtifactKind, placement_seam

        # Fail closed on a missing handle rather than silently falling back to
        # ``feature_dir.name`` (#3981): at this call ``feature_dir`` is a
        # coord-worktree / status dir whose ``.name`` is NOT a kitty-specs
        # mission handle, so the old fallback would feed a wrong (and possibly
        # ambiguous) handle into ``placement_seam``. Matches this function's own
        # no-silent-fallback stance on ``MissionSelectorAmbiguous`` (C-009): a
        # caller that anchors (``repo_root=``) must name the mission explicitly.
        if mission_slug is None:
            raise ValueError("_should_advance_wp_step: mission_slug is required when repo_root is supplied (anchoring); feature_dir.name is not a mission handle.")
        anchor_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)

    tasks_dir = anchor_dir / "tasks"
    # A file-based WP count cannot distinguish an empty pre-finalize board
    # from finalized lane state whose canonical task file disappeared. Keep
    # the run in its WP step so the board selector can emit the canonical
    # task-read error instead of advancing through composition.
    if repo_root is not None and _mapping._wp_task_surface_error(anchor_dir, feature_dir, mission_slug) is not None:
        return False

    if not tasks_dir.is_dir():
        return True  # no WPs to iterate over

    wp_files = sorted(tasks_dir.glob(_mapping.TASKS_GLOB))
    if not wp_files:
        return True

    from runtime.next import committed_authority
    from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

    for wp_file in wp_files:
        wp_match = re.match(r"(WP\d+)", wp_file.stem)
        wp_id = wp_match.group(1) if wp_match else wp_file.stem
        ending = committed_authority.wp_ending(feature_dir, wp_id)
        try:
            state = wp_state_for(ending.lane)
        except ValueError:
            # A lane string outside _STATE_MAP (a genuinely-unknown / malformed
            # value -- note "uninitialized" and "genesis" ARE in _STATE_MAP and
            # are handled by _wp_blocks_step's disjunct, not here). Treat an
            # unknown lane as not-yet-handed-off, so this WP blocks advancement.
            return False
        has_provenance = ending.reason_source == OPERATOR_REASON_SOURCE
        if _wp_blocks_step(step_id, state, has_provenance=has_provenance):
            return False

    return True


def _wp_blocks_step(step_id: str, state: Any, has_provenance: bool = False) -> bool:
    """Return whether a WP state blocks advancement for ``step_id``.

    ``has_provenance`` (#3780, defaulted so the single caller above stays the
    only 3-arg call site) is folded through the shipped
    :func:`specify_cli.status_lanes.is_acceptable_ending` authority for the
    ``review`` branch (D2/C-001): approved/done are unconditionally
    acceptable; canceled is acceptable only with operator-authored
    provenance (synthetic cancellations stay fail-closed); every other lane
    still blocks. The ``implement`` branch is unchanged — a canceled WP is
    never run-affecting there regardless of provenance.
    """
    lane = state.lane
    if is_acceptable_ending(
        str(lane),
        has_provenance=has_provenance,
    ):
        return False
    if step_id == "implement":
        # Advance past implement only when the WP has been handed off
        # (for_review or approved) or reaches an acceptable ending.
        # is_run_affecting is True for all active lanes; we further restrict
        # to only allow advancement for the "handed off" active lanes.
        # FR-004 (#3884): the two NON_DISPLAY_LANES -- Lane.UNINITIALIZED and
        # Lane.GENESIS -- are neither is_blocked nor is_run_affecting (neither
        # ever entered an active lane), so both fell through the run-affecting
        # disjunct and silently did not block. A WP that was never claimed
        # (UNINITIALIZED) or never lifecycled past creation (GENESIS) must not
        # be conflated with a genuinely-exempt handed-off state -- either one
        # is pending work that has to block the implement -> review advance.
        return lane in (Lane.UNINITIALIZED, Lane.GENESIS) or state.is_blocked or (state.is_run_affecting and lane not in (Lane.FOR_REVIEW, Lane.APPROVED))
    if step_id == "review":
        return not is_acceptable_ending(str(lane), has_provenance=has_provenance)
    return False


# ---------------------------------------------------------------------------
# Guard evaluation (CLI-level, not runtime-level)
# ---------------------------------------------------------------------------


SPEC_ARTIFACT = "spec.md"
TASKS_ARTIFACT = "tasks.md"
STATE_FILE = "state.json"


def _check_cli_guards(
    step_id: str,
    feature_dir: Path,
    *,
    mission_family: str | None = None,
    repo_root: Path | None = None,
    owned: OwnedCheckout | None = None,
) -> list[str]:
    """Evaluate the CLI guards for ``step_id`` and return the failures.

    Gathers an :func:`runtime_bridge_io.gather_artifact_presence` snapshot and
    folds it through :func:`runtime_bridge_cores.evaluate_guards_strict`, which
    raises for an unregistered mission family. ``wp_advance_ready`` is not part
    of the gathered snapshot: for ``implement``/``review`` it is read here from
    the bridge-owned :func:`_should_advance_wp_step` and set on the snapshot.

    ``mission_family`` is supplied by runtime paths that already resolved the
    primary-anchored mission type. Direct callers may omit it to preserve the
    legacy feature-dir lookup behavior.

    ``repo_root`` (#3704 WP03, FR-003) is forwarded to
    :func:`runtime_bridge_io.gather_artifact_presence` for org-tier
    ``expected-artifacts.yaml`` resolution (#3704 WP02, FR-008); defaults to
    ``None`` (built-in tree only — today's exact behavior for every existing
    caller that does not yet pass a real ``repo_root``).

    Returns list of failure descriptions; empty list means all guards pass.
    """
    mission_family = mission_family if mission_family is not None else get_mission_type(feature_dir)
    snapshot = _io_seam.gather_artifact_presence(
        feature_dir,
        mission_family=mission_family,
        step_id=step_id,
        repo_root=repo_root,
        owned=owned,
    )
    if step_id in ("implement", "review"):
        # Intentionally NOT anchored (no repo_root=/mission_slug= forwarded), even
        # though repo_root is in scope above for gather_artifact_presence: this call
        # is reachable only from _dn_dependency_gate's WP-iteration branch (#3884
        # INT-001), and only AFTER that branch's own anchored _should_advance_wp_step
        # call (repo_root=repo_root, mission_slug=mission_slug) already returned
        # True for the identical (step_id, feature_dir) — see the "All WPs done for
        # this step" comment at its call site. Do not "fix" this by anchoring it; if
        # phase ordering ever changes so this can be reached with WPs still pending,
        # this needs a repo_root=/mission_slug= forward of its own, mirroring
        # _dn_dependency_gate's call, not a silent carry-forward assumption.
        snapshot = dataclasses.replace(snapshot, wp_advance_ready=_should_advance_wp_step(step_id, feature_dir))
    return _cores.evaluate_guards_strict(snapshot)


def _occurrence_gate_failures(feature_dir: Path) -> list[str]:
    """Bulk-edit occurrence-map gate errors (empty when not bulk_edit or map is valid).

    Reuses the existing ``ensure_occurrence_classification_ready`` enforcement
    (C-001: no new validation logic). Self-conditions on stored ``change_mode``
    (C-003), so it is safe to call unconditionally at the tasks_finalize
    boundary — non-bulk-edit missions and valid-admissible bulk-edit missions
    both return an empty list.
    """
    from specify_cli.bulk_edit.gate import ensure_occurrence_classification_ready

    return list(ensure_occurrence_classification_ready(feature_dir).errors)


def _log_requirement_extraction_warnings(feature_dir: Path, warnings: list[str]) -> None:
    """#3394 F1 advisory, folded into this path's diagnostics too.

    :func:`specify_cli.requirement_mapping.find_undeclared_requirement_citations`
    was originally wired into ``finalize-tasks``/``map-requirements`` only;
    this path (``spec-kitty next``'s requirement-mapping preflight) got
    nothing, so an operator whose spec.md cites requirement-shaped tokens in
    an undeclared shape had no "why" surfaced here. Logged (never appended to
    the returned failures list), so it stays purely advisory: a log line,
    never a guard failure.
    """
    for warning in warnings:
        logger.warning("[%s] %s", feature_dir.name, warning)


def _log_requirement_extraction_warnings_safely(feature_dir: Path, spec_content: str) -> None:
    """Compute and log the #3394 F1 advisory without ever gating on it.

    #3394 focused-review F3 (severity 2): the advisory call used to sit
    directly inside ``_check_requirement_mapping_ready``'s broad
    ``except Exception``, which exists to fail-closed on genuine extraction
    crashes (``parse_requirement_ids_from_spec_md``, the WPs manifest load,
    the tasks.md ref parse). That means an exception raised by the advisory
    *computation* itself -- not its content, which is never appended to the
    returned failures -- would propagate to that handler and turn into a
    "Requirement mapping preflight failed" gate failure, contradicting the
    "advisory can never gate" property. ``find_undeclared_requirement_
    citations`` is pure regex/string-splitting with no I/O and currently has
    no failure mode, so this was near-zero practical risk -- but true by
    luck of the function, not by construction. This wrapper makes it true by
    construction: any exception here is swallowed and logged at DEBUG, never
    re-raised, so it cannot reach the enclosing fail-closed handler. Scoped
    to this one call; the surrounding broad ``except Exception`` is
    untouched and still fail-closed for the other three extraction calls.
    """
    try:
        from specify_cli.requirement_mapping import find_undeclared_requirement_citations

        _log_requirement_extraction_warnings(feature_dir, find_undeclared_requirement_citations(spec_content))
    except Exception:
        logger.debug(
            "[%s] Requirement-citation advisory computation failed; skipping (non-blocking)",
            feature_dir.name,
            exc_info=True,
        )


def _load_wps_manifest_findings(feature_dir: Path) -> tuple[object | None, list[str] | None]:
    """Load ``wps.yaml`` via :func:`load_wps_manifest`, translating a corrupt
    manifest into a findings-list entry instead of a raw traceback.

    Mission cli-error-surface-seam WP07/#4746 (T026): pre-fix, a corrupt
    ``wps.yaml`` (or any of the three OTHER operations sharing
    :func:`_check_requirement_mapping_ready`'s ``try`` block) collapsed into
    the SAME indistinguishable generic string via that function's broad
    ``except Exception``. Catching :class:`WpsManifestReadError` narrowly
    here — before it can reach that broad catch — gives the corrupt-manifest
    case its own typed, actionable message while leaving the broad catch's
    fail-closed behavior for the other three operations completely
    unchanged (see the companion assertion in
    ``tests/specify_cli/test_audit_tail_readers.py``).

    This is a gather-only internal preflight, not a CLI command boundary
    (see :func:`_check_requirement_mapping_ready`'s docstring) — so a
    corrupt manifest is reported as a finding string, never re-raised.

    Returns:
        ``(manifest, None)`` on success — ``manifest`` is ``None`` when
        ``wps.yaml`` is legitimately absent (D5, the legacy-mission case
        :func:`load_wps_manifest` itself resolves to ``None``). ``(None,
        [finding])`` when ``wps.yaml`` exists but is corrupt.
    """
    from specify_cli.core.wps_manifest import WpsManifestReadError, load_wps_manifest

    try:
        return load_wps_manifest(feature_dir), None
    except WpsManifestReadError as exc:
        return None, [f"Requirement mapping preflight failed: wps.yaml is corrupt: {exc}"]


def _check_requirement_mapping_ready(feature_dir: Path) -> list[str]:
    """Validate requirement coverage before issuing the finalize-tasks prompt.

    This intentionally mirrors ``agent mission finalize-tasks`` requirement
    source precedence: WP frontmatter is primary, and ``tasks.md`` is only a
    legacy fallback when no ``wps.yaml`` manifest is present.

    Gather-only shell (#2531 WP06, T023): reads spec.md/tasks.md/the WPs
    manifest and builds a :class:`runtime_bridge_cores.RequirementMappingFacts`
    bundle; the missing/unknown/unmapped decision itself (former CC~22 tail)
    now lives in the pure :func:`runtime_bridge_cores._evaluate_requirement_
    mapping` — the ``# noqa: C901`` this function used to carry is REMOVED,
    not relocated (FR-004/NFR-002).

    Also logs any :func:`specify_cli.requirement_mapping.
    find_undeclared_requirement_citations` advisory as a non-blocking
    diagnostic -- see :func:`_log_requirement_extraction_warnings_safely` for
    the full rationale, including why its computation is isolated from this
    function's own fail-closed ``except Exception`` below.

    WP07/#4746 (T026): the ``load_wps_manifest`` call below is routed
    through :func:`_load_wps_manifest_findings`, which catches the typed
    ``WpsManifestReadError`` (mission cli-error-surface-seam WP01/WP07)
    narrowly and returns its own findings entry -- so a corrupt manifest no
    longer masquerades behind the SAME generic
    "Requirement mapping preflight failed: {exc}" string this function's
    broad ``except Exception`` below still produces, unchanged, for the
    other three operations sharing this ``try`` block
    (``spec_md.read_text``, ``parse_requirement_ids_from_spec_md``,
    ``read_all_wp_raw_requirement_refs``, and the ``tasks_md.read_text`` prose
    fallback).
    """
    spec_md = feature_dir / SPEC_ARTIFACT
    if not spec_md.exists():
        return []

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return []

    try:
        from specify_cli.requirement_mapping import (
            grammar,
            parse_requirement_ids_from_spec_md,
            read_all_wp_raw_requirement_refs,
        )

        spec_content = spec_md.read_text(encoding="utf-8")
        spec_ids = parse_requirement_ids_from_spec_md(spec_content)
        all_spec_requirement_ids = set(spec_ids["all"])
        functional_requirement_ids = set(spec_ids["functional"])

        _log_requirement_extraction_warnings_safely(feature_dir, spec_content)

        wps_manifest, manifest_findings = _load_wps_manifest_findings(feature_dir)
        if manifest_findings is not None:
            return manifest_findings
        # WP04 (C-002): the WP01 unified RAW reader, not the normalising
        # one -- classification (FR-019) needs the raw authored tokens, the
        # same source ``mission_finalize.py``'s finalize classifies, so a
        # malformed or foreign-qualified ref does not silently vanish
        # before the injected grammar's verdict table ever sees it.
        wp_requirement_refs = read_all_wp_raw_requirement_refs(tasks_dir)

        if wps_manifest is None:
            tasks_md = feature_dir / TASKS_ARTIFACT
            if tasks_md.exists():
                tasks_md_refs = _cores._parse_requirement_refs_from_tasks_md(tasks_md.read_text(encoding="utf-8"), grammar=grammar)
                for wp_id, refs in tasks_md_refs.items():
                    if refs and not wp_requirement_refs.get(wp_id):
                        wp_requirement_refs[wp_id] = refs
    except Exception as exc:
        return [f"Requirement mapping preflight failed: {exc}"]

    wp_ids = tuple(sorted(wp_file.stem.split("-", 1)[0] for wp_file in tasks_dir.glob(_mapping.TASKS_GLOB)))
    facts = _cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset(all_spec_requirement_ids),
        functional_requirement_ids=frozenset(functional_requirement_ids),
        wp_ids=wp_ids,
        wp_requirement_refs={wp_id: tuple(refs) for wp_id, refs in wp_requirement_refs.items()},
        feature_dir_name=feature_dir.name,
        grammar=grammar,
    )
    return _cores._evaluate_requirement_mapping(facts)


def _check_bare_prose_requirements_ready(feature_dir: Path) -> list[str]:
    """WP05 (#3396) T023 — gather-only residual for the bare-prose
    requirement signal (fact-port/pure-core split, mirroring
    ``_check_requirement_mapping_ready``).

    Deliberately independent of ``tasks_dir``/WP-file state (FR-002): reads
    ONLY spec.md, so the signal is available and populated in
    ``status_facts`` regardless of whether any WP file exists yet -- the
    guards (``runtime_bridge_cores.py``) read it BEFORE their own
    ``tasks_dir`` readiness checks, closing the exact dead-path shape the
    reverted ``3823f2b00`` left open.

    Fail-loud, textually separate from the advisory (Story 5 / FR-007 /
    FR-008): this does NOT route through
    ``_log_requirement_extraction_warnings_safely`` -- that wrapper's "never
    crash into a gate" contract is the opposite of this detector's "never
    silently report clean" contract. Any exception here becomes an explicit,
    non-empty, blocking failure via ``BareProseRequirementFacts.
    classification_error`` (NFR-002: silent-success prohibition) --
    mirroring ``_check_requirement_mapping_ready``'s own
    ``except Exception as exc: return [...]`` shape one function up, never
    a bare traceback and never downgraded to a log line.
    """
    spec_md = feature_dir / SPEC_ARTIFACT
    if not spec_md.exists():
        return []

    try:
        from specify_cli.requirement_mapping import find_bare_prose_requirement_ids

        spec_content = spec_md.read_text(encoding="utf-8")
        candidates = find_bare_prose_requirement_ids(spec_content)
        facts = _cores.BareProseRequirementFacts(
            flagged={candidate.section_heading: tuple(candidate.ids) for candidate in candidates},
            classification_error=None,
        )
    except Exception as exc:
        facts = _cores.BareProseRequirementFacts(
            flagged={},
            classification_error=(
                f"Bare-prose requirement detection failed to classify {feature_dir.name}'s spec.md: "
                f"{exc!r} -- treating as blocking (never silently clean, NFR-002)."
            ),
        )
    return _cores._evaluate_bare_prose_requirements(facts)


def _has_raw_dependencies_field(wp_file: Path) -> bool:
    """Check if WP file has an explicit 'dependencies' field in raw frontmatter.

    Reads raw text to avoid auto-injection by read_frontmatter().
    """
    try:
        text = wp_file.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    end = text.find("---", 3)
    if end == -1:
        return False
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies:"):
            return True
    return False


# ---------------------------------------------------------------------------
# Composition dispatch (WP02 / mission software-dev-composition-rewrite-01KQ26CY)
# ---------------------------------------------------------------------------
#
# The cluster lives in ``runtime_bridge_composition.py`` (#2531 WP08) — see
# that module's docstring for the constraints (C-001/C-002/C-003/C-008) that
# govern it. The bridge reaches it as ``_composition.<name>``; it keeps no
# forwarder for any of the cluster's names (#2561).


# Single-dispatch invariant (FR-001 / phase6-composition-stabilization-01KQ2JAS):
# After a composition-backed software-dev action succeeds, run state must still
# advance through the next public step — but the legacy ``runtime_next_step``
# DAG dispatch handler MUST NOT be invoked for the same action attempt. The
# advancement itself is owned by
# ``runtime_bridge_engine.advance_run_state_after_composition``.
#
# ---------------------------------------------------------------------------
# Main bridge functions
# ---------------------------------------------------------------------------


def _resolve_runtime_feature_dir(repo_root: Path, mission_slug: str) -> Path:
    """Resolve a mission dir for runtime reads without importing CLI context.

    Routes through the single guarded read-side seam
    (:func:`resolve_handle_to_read_path`, WP01/IC-01): it reads the PRIMARY
    ``meta.json``, runs the ONE sanctioned mid8 cascade (``resolve_declared_mid8``)
    and returns the existence-gated topology-aware dir — folding away the bespoke
    ``_resolve_mission_ulid`` → ``resolve_mid8`` cascade here (FR-002, C-007).

    Boundary-safe fold-in (C-007): ``runtime_bridge`` already imports
    ``specify_cli.missions._read_path_resolver`` (see
    ``_mission_routes_through_coordination`` above; ``_primary_runtime_
    feature_dir`` moved to ``runtime_bridge_identity`` at #2531 WP10 but keeps
    the same import), so consuming ``resolve_handle_to_read_path`` from the
    same module adds NO new package-boundary edge.

    Subsumption note (T013): the retired body derived ``mid8`` as
    ``resolve_mid8(slug, mission_id=<declared ULID or None>)`` — exactly tier 2 of
    the seam's ``resolve_declared_mid8``. The seam additionally honours an explicit
    declared ``meta.mid8`` (tier 1) before that and the ``mid8_from_slug`` heuristic
    (tier 3) after, so it resolves the SAME dir for any meta the old body handled
    while also covering the explicit-mid8 case the old body silently skipped.
    """
    from specify_cli.missions._read_path_resolver import (
        resolve_handle_to_read_path as _resolve_handle,
    )

    return _resolve_handle(repo_root, mission_slug)


# ---------------------------------------------------------------------------
# Decision-builder residual (#2531 WP07, FR-011) — every ``Decision(...)``
# construction below is routed through ``runtime_bridge_cores.step_or_
# blocked`` over a ``runtime_bridge_cores.DecisionEnvelope`` by
# ``runtime_bridge_decision_mapping._materialize_decision`` (#2560), which
# supplies the one genuinely I/O-bearing dependency the pure core needs (the
# step branch's on-disk prompt-file check). Callers thread the
# non-deterministic fields (timestamp/run_id/decision_id) — the core itself
# never stamps them (NFR-003).
# ---------------------------------------------------------------------------


def _primary_mission_is_completed(primary_metadata_dir: Path) -> bool:
    """Return whether the PRIMARY checkout proves the mission is MERGED.

    Deliberately gated on the merge marker alone (squad pass 1 on PR #845):
    ``is_mission_completed`` is also True for an unmerged mission whose WPs are
    all terminal, and short-circuiting there skips the final advance that
    appends ``MissionRunCompleted`` and runs the retrospective completion gate.
    Fail-closed and non-raising: a corrupt primary ``meta.json``
    (``MissionMetaReadError``) reads as not-merged.
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.status import StoreError, is_mission_merged

    if not (primary_metadata_dir / "meta.json").is_file():
        return False
    try:
        return bool(is_mission_merged(primary_metadata_dir))
    except (StoreError, MissionMetaReadError):
        return False


@dataclasses.dataclass(frozen=True)
class DecideNextContext:
    """Frozen value carrier threading ``decide_next_via_runtime``'s shared
    locals through its four-phase early-return chain (FR-010,
    data-model.md §DecideNextContext): bootstrap -> dependency-gate ->
    composition-dispatch -> decision-materialize.

    Populated once by the bootstrap phase; carries no I/O of its own. This
    is an internal residual type — never re-exported, not a new public
    surface (NFR-004) — so the ``decision.py:428`` lazy edge to the
    orchestrator stays lazy (C-007).
    """

    agent: str
    mission_slug: str
    result: str
    repo_root: Path
    feature_dir: Path
    now: str
    mission_type: str
    sync_emitter: RuntimeEventEmitter
    emitter_for_engine: Any
    origin: dict[str, Any]
    progress: dict[str, int | float] | None
    run_ref: MissionRunRef
    run_dir: Path
    current_step_id: str | None
    # owned-checkout-lifecycle-authority WP11 (FR-009): the validated
    # ownership fact, when this call runs under an owned checkout. ``None``
    # for every non-owned mission — the historical, byte-identical path.
    owned: OwnedCheckout | None = None


def _owned_coordination_unavailable_decision(agent: str, mission_slug: str, mission_type: str, now: str, exc: BaseException) -> Decision:
    """The typed ``blocked`` Decision of an unavailable owned coordination workspace."""
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state="unknown",
            timestamp=now,
            reason=(
                f"Coordination worktree registry is unavailable for mission {mission_slug!r} ({exc}). "
                "Try 'git worktree prune' or 'spec-kitty doctor coordination --fix'."
            ),
            error_code=OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value,
        )
    )


def _dn_bootstrap(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[DecideNextContext | None, Decision | None]:
    """Phase 1/4 of ``decide_next_via_runtime`` (FR-010) — resolve
    feature/mission/run and build the shared :class:`DecideNextContext`.

    Unlike the other three phases this one cannot accept a
    ``DecideNextContext`` as input (there is nothing to thread yet), so its
    signature is the raw entry params in, ``(ctx, decision)`` out: exactly
    one of the pair is non-``None``. A non-``None`` ``Decision`` means
    bootstrap itself short-circuited (feature dir missing / run failed to
    start) and the caller must return it immediately without running the
    remaining phases.
    """
    is_owned_call = owned is not None

    if not is_owned_call:
        feature_dir = _resolve_runtime_feature_dir(repo_root, mission_slug)
        primary_metadata_dir: Path | None = _identity_seam._primary_runtime_feature_dir(repo_root, mission_slug)
    else:
        from mission_runtime import MissionArtifactKind, mission_context_for

        try:
            mission_context = mission_context_for(
                repo_root,
                mission_slug,
                owned=owned,
                tolerate_unmaterialized_coord=True,  # FR-022: a declared-but-not-yet-created coordination worktree is read/materialised, not refused
            )
        except ActionContextError as exc:
            if not _decision_log._is_owned_coordination_unavailable(exc):
                raise
            return None, _owned_coordination_unavailable_decision(agent, mission_slug, "unknown", now_utc_iso(), exc)
        status_dir = mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir
        primary_metadata_dir = mission_context.artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        feature_dir = status_dir if status_dir.is_dir() else primary_metadata_dir
    now = now_utc_iso()

    if not feature_dir.is_dir():
        return None, _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission="unknown",
                mission_state="unknown",
                timestamp=now,
                reason=f"Feature directory not found: {feature_dir}",
            )
        )

    # ``meta.json`` (the mission-type source) lives on the topology-BLIND PRIMARY
    # checkout; the coordination worktree's sparse policy excludes it. Reading the
    # type off the coord-aware ``feature_dir`` yields an empty meta -> the neutral
    # ``""`` from ``get_mission_type`` (post-#883 no software-dev default), which
    # then breaks runtime template resolution. Anchor the type read on the primary
    # dir, mirroring ``_mission_routes_through_coordination`` above (FR-001).
    from mission_runtime import MissionArtifactKind, placement_seam  # noqa: PLC0415

    mission_type = get_mission_type(
        placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA) if primary_metadata_dir is None else primary_metadata_dir
    )
    if primary_metadata_dir is not None and _primary_mission_is_completed(primary_metadata_dir):
        return None, _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.terminal,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="done",
                timestamp=now,
                reason="Mission is already completed",
            )
        )
    # E3 (#3929): register the runtime-moment producer at this entry, never while
    # ``specify_cli.status`` imports (that re-enters ``runtime.next`` mid-import).
    from specify_cli.status import ensure_runtime_moment_producer  # noqa: PLC0415

    ensure_runtime_moment_producer()
    sync_emitter = runtime_emitter_for_mission(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_type=mission_type,
    )
    # Root discipline (contracts/owned-checkout-carrier.md §7): callees that
    # are not yet owned-aware receive ``owned.owned_root`` in the root
    # argument they already have — the run store, the lifecycle store,
    # composition policy and git cwd all stay at P for an owned mission,
    # preserving today's owned behaviour.
    config_root = owned.owned_root if owned is not None else repo_root

    # Wrap with DecisionGitLog so decision events are durably committed to
    # the coordination branch (spec-kitty #1546, FR-001–FR-005).
    from specify_cli.coordination.workspace import CoordinationWorkspaceUnavailable

    try:
        if not is_owned_call:
            emitter_for_engine: Any = _decision_log._wrap_with_decision_git_log(sync_emitter, mission_slug, repo_root)
        else:
            emitter_for_engine = _decision_log._wrap_with_decision_git_log(
                sync_emitter,
                mission_slug,
                repo_root,
                owned=owned,
            )
    except (CoordinationWorkspaceUnavailable, ActionContextError) as exc:
        # #4867 / FR-012 / O8: an owned caller gets a typed ``blocked``
        # decision instead of an opaque ``fatal: ... commondir: Success``
        # escaping as a Python traceback. The transient-lock retry already
        # ran inside ``_resolve_owned_coordination_workspace`` — reaching
        # here means the failure is durable. WP04's
        # ``ActionContextError(OWNED_COORDINATION_WORKSPACE_UNAVAILABLE)`` (an
        # unmaterialized surface read) maps identically; any other
        # ``ActionContextError`` is not ours to translate.
        if not _decision_log._is_owned_coordination_unavailable(exc):
            raise
        return None, _owned_coordination_unavailable_decision(agent, mission_slug, mission_type, now, exc)

    # Resolve origin info
    origin: dict[str, Any] = {}
    try:
        from specify_cli.runtime.resolver import resolve_mission as resolve_mission_path

        mission_result = resolve_mission_path(mission_type, config_root)
        origin = {
            "mission_tier": getattr(mission_result.tier, "value", str(mission_result.tier)),
            "mission_path": str(mission_result.path.parent),
        }
    except FileNotFoundError:
        origin = {"mission_tier": "unknown", "mission_path": "unknown"}

    progress = _compute_wp_progress(feature_dir)

    # Get or start runtime run (before result handling so failed/blocked
    # decisions include canonical run_id, step_id, and mission_state)
    try:
        run_ref = _io_seam.get_or_start_run(mission_slug, config_root, mission_type, emitter=emitter_for_engine, owned=owned)
    except Exception as exc:
        return None, _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="unknown",
                timestamp=now,
                reason=f"Failed to start/load runtime run: {exc}",
                progress=progress,
                origin=origin,
            )
        )

    run_dir = Path(run_ref.run_dir)

    # Read current run state
    try:
        snapshot = _engine_adapter._read_snapshot(run_dir)
        current_step_id = snapshot.issued_step_id
    except Exception:
        current_step_id = None
    else:
        seed_runtime_emitter(sync_emitter, snapshot)

    # FR-017: populate the runtime OperationalContext at the `next` decision
    # boundary via the extracted helper (keeps the bootstrap phase flat). The
    # builder is read-only — it never allocates a worktree or emits a status
    # event (NFR-004).
    operational_context = _io_seam._build_operational_context_for_decision(
        agent=agent,
        run_ref=run_ref,
        feature_dir=feature_dir,
        repo_root=config_root,
        step_id=current_step_id,
        mission_state=current_step_id,
    )
    logger.debug(
        "decide_next operational context: model=%s profile=%s role=%s activity=%s",
        operational_context.active_model,
        operational_context.active_profile,
        operational_context.active_role,
        operational_context.current_activity,
    )

    return (
        DecideNextContext(
            agent=agent,
            mission_slug=mission_slug,
            result=result,
            repo_root=repo_root,
            feature_dir=feature_dir,
            now=now,
            mission_type=mission_type,
            sync_emitter=sync_emitter,
            emitter_for_engine=emitter_for_engine,
            origin=origin,
            progress=progress,
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id=current_step_id,
            owned=owned,
        ),
        None,
    )


def _run_is_untouched(run_dir: Path) -> bool:
    """True when the persisted run has never advanced: no completed step and no
    decision, pending or answered (query mode's initial-step predicate). An
    unreadable or malformed snapshot is NOT untouched, so the caller keeps its existing path."""
    try:
        snapshot = _engine_adapter._read_snapshot(run_dir)
        return not snapshot.completed_steps and not snapshot.pending_decisions and not snapshot.decisions
    except Exception:
        return False


def _dn_finalized_board_override(ctx: DecideNextContext) -> Decision | None:
    """Front phase of ``decide_next_via_runtime`` (#5310) — advance first-contact
    parity with query mode.

    Query mode applies the finalized-board override at the top of
    ``_query_dispatch_decision``; advance used to reach the board only once the
    persisted run already sat on a WP-iteration step, so a first-contact advance
    against a finalized board booted ``discovery`` and walked the DAG from its
    first step. This phase consults the SAME board authority
    (:func:`_resolve_wp_board_action`; never a re-derived claimability) before
    the DAG phases, for an advancing ``success`` result against an *untouched*
    run (nothing completed, no decisions: the same "never advanced" predicate
    query mode uses for its initial-step branch). A run that already walked the
    DAG owns its own progression (``_dn_dependency_gate`` /
    ``_dn_composition_dispatch``); pre-empting it would leave the run state
    behind the decision it issued.

    A board dispatch (``implement``/``review``) or a named ``blocked:*`` verdict
    is materialized the way the WP-iteration path does; every other board answer
    (decline for accept/done/no finalized board, coord/task-surface errors) falls
    through unchanged so pre-finalize and terminal behaviour stay byte-identical.
    """
    if ctx.result != "success" or not _run_is_untouched(ctx.run_dir):
        return None
    board = _mapping._resolve_wp_board_action(mission_slug=ctx.mission_slug, repo_root=ctx.repo_root, owned=ctx.owned)
    if board.action is not None and board.board_step is not None:
        return _mapping._build_wp_iteration_decision(
            board.board_step,
            ctx.agent,
            ctx.mission_slug,
            ctx.mission_type,
            ctx.feature_dir,
            ctx.repo_root,
            ctx.now,
            ctx.progress,
            ctx.origin,
            ctx.run_ref,
            owned=ctx.owned,
        )
    if board.blocked_reason is not None and board.board_step is not None and board.board_step.startswith("blocked:"):
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=ctx.agent,
                mission_slug=ctx.mission_slug,
                mission=ctx.mission_type,
                mission_state="blocked",
                timestamp=ctx.now,
                reason=board.blocked_reason,
                progress=ctx.progress,
                origin=ctx.origin,
                run_id=ctx.run_ref.run_id,
            )
        )
    return None


def _dn_dependency_gate(ctx: DecideNextContext) -> Decision | None:
    """Phase 2/4 of ``decide_next_via_runtime`` (FR-010) — the
    dependency/guard gate: the WP-iteration stay-in-step check (plus its
    on-advance guard check), and the non-WP-step guard check. Returns a
    blocked/step ``Decision`` when a guard holds the run in place, else
    ``None`` to fall through to composition-dispatch.
    """
    agent = ctx.agent
    mission_slug = ctx.mission_slug
    mission_type = ctx.mission_type
    feature_dir = ctx.feature_dir
    repo_root = ctx.repo_root
    owned = ctx.owned
    now = ctx.now
    progress = ctx.progress
    origin = ctx.origin
    run_ref = ctx.run_ref
    current_step_id = ctx.current_step_id

    # WP iteration check: if we're on a WP step and WPs remain, don't advance runtime
    if ctx.result == "success" and current_step_id and _mapping._is_wp_iteration_step(current_step_id):
        try:
            should_advance = _should_advance_wp_step(current_step_id, feature_dir, repo_root=repo_root, mission_slug=mission_slug, owned=owned)
        except CanonicalStatusNotFoundError as exc:
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.blocked,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=str(exc),
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                ),
                [str(exc)],
            )
        except MissionSelectorAmbiguous as exc:  # NEW — FR-010 (#3884)
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.blocked,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=str(exc),
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                ),
                [str(exc)],
            )
        if not should_advance:
            # Stay in current step, return WP-level action
            return _mapping._build_wp_iteration_decision(
                current_step_id,
                agent,
                mission_slug,
                mission_type,
                feature_dir,
                repo_root,
                now,
                progress,
                origin,
                run_ref,
                owned=owned,
            )
        # All WPs done for this step — check guards before advancing.
        #
        # Unlike the non-WP pre-check below (deliberately scoped to
        # ``software-dev`` only, #3407), this WP-iteration branch runs for
        # every mission family whose current step is ``implement``/``review``
        # (``_WP_ITERATION_STEPS``) — including ``software-dev`` and
        # ``plan``, both of which ARE registered in ``_GUARD_TABLES``, but
        # also any custom mission family that has no guard-table entry at
        # all (#3627). ``_check_cli_guards`` -> ``evaluate_guards_strict``
        # fails closed with ``UnregisteredMissionFamilyError`` for such a
        # family by design (see its own docstring); that is correct for the
        # scoped non-WP pre-check, but here it must degrade to "no guard
        # failures" instead of crashing the WP-iteration advance decision —
        # composition-dispatch's own tolerant ``evaluate_guards`` remains the
        # authority for those custom families, exactly as it already is for
        # every non-WP-iteration step of theirs.
        try:
            guard_failures = _check_cli_guards(
                current_step_id,
                feature_dir,
                mission_family=mission_type,
                repo_root=repo_root,
                owned=owned,
            )
        except _cores.UnregisteredMissionFamilyError:
            logger.warning(
                "Unregistered mission_family %r reached the CLI guard path; returning a neutral (empty) guard result.",
                mission_type,
            )
            guard_failures = []
        if guard_failures:
            return _mapping._build_wp_iteration_decision(
                current_step_id,
                agent,
                mission_slug,
                mission_type,
                feature_dir,
                repo_root,
                now,
                progress,
                origin,
                run_ref,
                guard_failures=guard_failures,
                owned=owned,
            )

    # Check guards for non-WP steps before advancing.
    #
    # This CLI-native pre-check (#3407 M3) is scoped to the ``software-dev``
    # mission family only. Its ``kind=step`` "re-issue the current step"
    # semantic belongs to software-dev's linear specify → plan → tasks CLI
    # vocabulary; it must NOT pre-empt composition dispatch for the other
    # families. For ``documentation`` / ``research`` / ``plan`` and every
    # custom mission type, the composed-action guard (Phase 3) is the
    # authority — it surfaces the same missing-artifact failure as a
    # ``kind=blocked`` decision (the fail-CLOSED contract, spec.md AC of the
    # documentation/research runtime walks) and, unlike ``_check_cli_guards``
    # here, degrades gracefully for guard-table-unregistered custom families
    # instead of raising ``UnregisteredMissionFamilyError``. Gating on the
    # family keeps software-dev byte-identical to its pre-#3407 behavior
    # (AC-14) while restoring the correct blocked decision for the composed
    # families (WP06 wrongly routed them through this ``kind=step`` path).
    if ctx.result == "success" and current_step_id and not _mapping._is_wp_iteration_step(current_step_id) and mission_type == MISSION_TYPE_SOFTWARE_DEV:
        guard_failures = _check_cli_guards(
            current_step_id,
            feature_dir,
            mission_family=mission_type,
            repo_root=repo_root,
            owned=owned,
        )
        if guard_failures:
            action, wp_id, workspace_path = _state_to_action(
                current_step_id,
                mission_slug,
                feature_dir,
                repo_root,
                mission_type,
                owned=owned,
            )
            prompt_file: str | None = None
            prompt_error: str | None = None
            prompt_error_code: str | None = None
            if action:
                prompt_file, prompt_error, prompt_error_code = _build_prompt_or_error(
                    action,
                    feature_dir,
                    mission_slug,
                    wp_id,
                    agent,
                    repo_root,
                    mission_type,
                    owned=owned,
                )
            else:
                prompt_error = f"no action mapped for step '{current_step_id}'; cannot resolve prompt"
            # WP06 (FR-006/FR-013) / WP07 (FR-011): step_or_blocked never
            # issues kind=step with an unresolvable prompt_file — it falls
            # back to kind=blocked using this pre-computed reason (matches
            # the original "prompt_file is None" branch's literal exactly;
            # the "resolved-but-vanished-by-construction-time" race uses the
            # core's own hard-coded literal — see DecisionEnvelope's
            # docstring for why that is safe to share across sites).
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.step,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=prompt_error or "prompt_file_not_resolvable",
                    action=action,
                    wp_id=wp_id,
                    workspace_path=workspace_path,
                    prompt_file=prompt_file,
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                    error_code=prompt_error_code,
                ),
                guard_failures,
            )

    return None


def _dn_composition_blocked_decision(
    ctx: DecideNextContext,
    current_step_id: str,
    composition_failures: list[str],
) -> Decision:
    """Build the blocked ``Decision`` for a composition-dispatch guard
    failure — the ``_state_to_action`` -> ``_build_prompt_safe`` prompt
    resolution the composition-dispatch phase needs when the executor
    reports guard failures instead of advancing (FR-008 composition
    guard-failure surface). Split out of ``_dn_composition_dispatch`` to
    keep that phase's own complexity down; it re-extracts nothing WP06-08
    already own — it is pure orchestration plumbing local to this phase.
    """
    action, wp_id, workspace_path = _state_to_action(
        current_step_id,
        ctx.mission_slug,
        ctx.feature_dir,
        ctx.repo_root,
        ctx.mission_type,
        owned=ctx.owned,
    )
    prompt_file = (
        _build_prompt_safe(
            action,
            ctx.feature_dir,
            ctx.mission_slug,
            wp_id,
            ctx.agent,
            ctx.repo_root,
            ctx.mission_type,
            owned=ctx.owned,
        )
        if action
        else None
    )
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=ctx.agent,
            mission_slug=ctx.mission_slug,
            mission=ctx.mission_type,
            mission_state=current_step_id,
            timestamp=ctx.now,
            reason=composition_failures[0],
            action=action,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=ctx.progress,
            origin=ctx.origin,
            run_id=ctx.run_ref.run_id,
            step_id=current_step_id,
        ),
        composition_failures,
    )


def _advance_failed_decision(ctx: DecideNextContext, composed_action: str, exc: Exception) -> Decision:
    """EDGE-003 contract: any advancement-helper failure must surface as a
    structured ``blocked`` Decision, not as a Python traceback, and MUST NOT
    silently fall through to the legacy DAG dispatch handler."""
    logger.exception(
        "advancement helper failed after composition for %s/%s",
        ctx.mission_type,
        composed_action,
    )
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=ctx.agent,
            mission_slug=ctx.mission_slug,
            mission=ctx.mission_type,
            mission_state=ctx.current_step_id,
            timestamp=ctx.now,
            reason=(f"Run-state advancement after composition failed for {ctx.mission_type}/{composed_action}: {type(exc).__name__}: {exc}"),
            progress=ctx.progress,
            origin=ctx.origin,
            run_id=ctx.run_ref.run_id,
            step_id=ctx.current_step_id,
        )
    )


def _dn_plan_composition_advance(ctx: DecideNextContext, composed_action: str) -> tuple[Any, _mapping._WpIterationResolution | None] | Decision:
    """Plan (pure) the run-state advance after a successful composed action and
    resolve a planned WP step's workspace BEFORE anything is persisted (FR-008).

    Returns ``(plan, wp_resolution)`` for :func:`_dn_composition_dispatch` to
    commit, or the EDGE-003 ``blocked`` Decision when the plan itself cannot be
    computed. The resolution runs OUTSIDE any ``except``: a typed failure
    propagates unwrapped, and because nothing has been written the run stays
    untouched."""
    try:
        plan = _engine_adapter.plan_composition_advance(ctx.run_ref, ctx.agent)
    except Exception as exc:  # noqa: BLE001 — EDGE-003: a planning failure is a structured blocked Decision
        return _advance_failed_decision(ctx, composed_action, exc)
    wp_resolution = _resolve_planned_wp_workspace(
        plan.decision,
        mission_slug=ctx.mission_slug,
        mission_type=ctx.mission_type,
        feature_dir=ctx.feature_dir,
        repo_root=ctx.repo_root,
        owned=ctx.owned,
    )
    return plan, wp_resolution


def _dn_composition_dispatch(ctx: DecideNextContext) -> Decision | None:
    """Phase 3/4 of ``decide_next_via_runtime`` (FR-010) — composition
    dispatch (mission `software-dev-composition-rewrite-01KQ26CY`).

    For the built-in `software-dev` mission's five public actions, route the
    just-completed step through `StepContractExecutor.execute` BEFORE we let
    the runtime planner advance run state. The composition produces the
    invocation_id chain (host harness interprets it); a structured guard
    failure surface (Decision.kind=blocked, guard_failures populated) is
    used in lieu of a Python traceback when the executor raises
    `StepContractExecutionError`. C-008 gates this on `action_sequence`
    membership for the resolved mission type -- any mission type, not just
    `software-dev`; a step outside its own sequence falls through (returns
    ``None``) to composition unchanged so decision-materialize runs the
    runtime planner next.
    """
    agent = ctx.agent
    mission_type = ctx.mission_type
    feature_dir = ctx.feature_dir
    current_step_id = ctx.current_step_id
    # Root discipline (FR-009): composition policy and task-board resolution
    # are P-local governance reads for an owned mission.
    config_root = ctx.owned.owned_root if ctx.owned is not None else ctx.repo_root

    if (
        ctx.result == "success"
        and current_step_id
        and _composition._should_dispatch_via_composition(
            mission_type,
            current_step_id,
            run_dir=ctx.run_dir,
            repo_root=config_root,
        )
    ):
        composed_action = _composition._normalize_action_for_composition(current_step_id)
        # R-005: for custom missions, the active step's ``agent_profile`` is
        # the source of truth for ``profile_hint``. For built-in missions
        # (e.g., ``software-dev``), built-in templates do NOT set
        # ``agent_profile``, so this resolves to ``None`` and the executor's
        # ``_resolve_profile_hint`` falls back to ``_ACTION_PROFILE_DEFAULTS``
        # — preserving byte-identical built-in dispatch behavior (FR-010).
        resolved_profile, runtime_contract = _composition._composition_dispatch_inputs(
            repo_root=config_root,
            run_dir=ctx.run_dir,
            mission=mission_type,
            step_id=current_step_id,
            action=composed_action,
        )
        composition_failures = _composition._dispatch_via_composition(
            repo_root=config_root,
            mission=mission_type,
            action=composed_action,
            actor=agent,
            profile_hint=resolved_profile,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir,
            # Thread the original step_id so the post-action guard can branch
            # on substep semantics for legacy tasks_outline/tasks_packages/
            # tasks_finalize. Without this, the collapsed guard demands the
            # terminal post-finalize state on every substep and blocks the
            # live tasks_outline → tasks_packages → tasks_finalize flow.
            legacy_step_id=current_step_id,
            contract=runtime_contract,
            owned=ctx.owned,
        )
        if composition_failures:
            return _dn_composition_blocked_decision(ctx, current_step_id, composition_failures)
        # Composition succeeded; advance run state via the
        # composition-specific advancement helper and short-circuit the
        # legacy ``runtime_next_step`` fall-through (FR-001/FR-002). Plan and
        # resolve first (FR-008), then commit. The helper emits the same
        # lane / state events the legacy path emits, through the
        # decision-log-wrapped engine emitter so a ``DecisionInputRequested``
        # it raises is durably recorded (ADR 2026-09-06-2 (c)); any error from
        # it surfaces through the existing ``Decision`` ``blocked`` shape
        # (EDGE-003) — the legacy DAG dispatch handler is **not** entered as a
        # fallback.
        planned = _dn_plan_composition_advance(ctx, composed_action)
        if isinstance(planned, Decision):
            return planned
        plan, wp_resolution = planned
        try:
            return _engine_adapter.advance_run_state_after_composition(
                run_ref=ctx.run_ref,
                agent=agent,
                mission_slug=ctx.mission_slug,
                mission_type=mission_type,
                repo_root=ctx.repo_root,
                feature_dir=feature_dir,
                timestamp=ctx.now,
                progress=ctx.progress,
                origin=ctx.origin,
                sync_emitter=ctx.emitter_for_engine,
                owned=ctx.owned,
                plan=plan,
                wp_resolution=wp_resolution,
            )
        except Exception as exc:  # noqa: BLE001 — EDGE-003: any advancement-helper failure surfaces as a blocked Decision
            return _advance_failed_decision(ctx, composed_action, exc)

    return None


def _dn_capture_pre_speculative_state(
    run_dir: Path,
) -> tuple[bytes | None, int | None] | None:
    """Capture ``(state.json bytes, run.events.jsonl size)`` before a
    speculative engine advance, so a later retrospective-gate refusal can
    roll back cleanly. Returns ``None`` on a disk-read failure — the caller
    must then surface a blocked ``Decision`` rather than advance into a
    state it cannot retract (mirrors the original inline try/except
    exactly)."""
    state_path = run_dir / STATE_FILE
    events_path = run_dir / "run.events.jsonl"
    try:
        pre_state_bytes = state_path.read_bytes() if state_path.exists() else None
        pre_events_size = events_path.stat().st_size if events_path.exists() else 0
    except OSError:
        return None
    return pre_state_bytes, pre_events_size


def _dn_rollback_buffered_run_state(
    run_dir: Path,
    pre_state_bytes: bytes | None,
    pre_events_size: int | None,
) -> None:
    """Restore state.json / truncate run.events.jsonl to their pre-speculative-
    advance values after the retrospective gate refuses completion. Mirrors
    the original inline rollback exactly, including its error-logging-only
    failure mode — a failed rollback is logged, not itself surfaced as a
    Decision (the caller has already committed to returning the gate-refused
    blocked Decision)."""
    if pre_state_bytes is not None:
        try:
            (run_dir / STATE_FILE).write_bytes(pre_state_bytes)
        except OSError as restore_exc:
            logger.error(
                "rollback of state.json failed after gate block: %s",
                restore_exc,
            )
    if pre_events_size is not None:
        events_path = run_dir / "run.events.jsonl"
        try:
            if events_path.exists():
                with open(events_path, "r+b") as handle:
                    handle.truncate(pre_events_size)
        except OSError as restore_exc:
            logger.error(
                "rollback of run.events.jsonl failed after gate block: %s",
                restore_exc,
            )


def _dn_terminal_retrospective_gate(
    ctx: DecideNextContext,
    policy_error: Exception | None,
    buffer: _retrospective_seam._BufferingRuntimeEmitter | None,
    pre_state_bytes: bytes | None,
    pre_events_size: int | None,
) -> Decision | None:
    """Run the strict (block-on) retrospective gate for a just-produced
    terminal ``Decision``. On refusal: drop the buffered emit calls (so no
    ``MissionRunCompleted`` ever reaches the real emitter), roll back
    state.json/run.events.jsonl, and return the blocked ``Decision``. On
    success (gate passes, or was never entered because ``policy_error`` is
    ``None`` and capture raises nothing) returns ``None`` so the caller
    proceeds to flush the buffer. Split out of ``_dn_decision_materialize``
    to keep that phase's own complexity down — pure orchestration plumbing
    local to this phase, not a re-extraction of WP04's retrospective seam.
    """
    mission_id = _retrospective_seam._resolve_mission_id_for_terminus(ctx.feature_dir)
    config_root = ctx.owned.owned_root if ctx.owned is not None else ctx.repo_root
    try:
        if policy_error is not None:
            raise policy_error
        _retrospective_seam._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=ctx.mission_slug,
            feature_dir=ctx.feature_dir,
            repo_root=config_root,
            block_on_failure=True,
        )
    except Exception as exc:
        # Gate refused. Drop the buffered emit calls (so no
        # MissionRunCompleted ever reaches the real emitter) and
        # restore state.json + truncate run.events.jsonl to pre-call.
        if buffer is not None:
            buffer.discard()
        _dn_rollback_buffered_run_state(ctx.run_dir, pre_state_bytes, pre_events_size)
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=ctx.agent,
                mission_slug=ctx.mission_slug,
                mission=ctx.mission_type,
                mission_state=ctx.current_step_id or "unknown",
                timestamp=ctx.now,
                reason=f"Retrospective gate refused completion: {exc}",
                progress=ctx.progress,
                origin=ctx.origin,
            )
        )
    return None


def _resolve_planned_wp_workspace(
    decision: NextDecision,
    *,
    mission_slug: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    owned: OwnedCheckout | None,
) -> _mapping._WpIterationResolution | None:
    """THE single place a planned WP-iteration step's board action + workspace
    is resolved BEFORE the advance is persisted (FR-008 / R-06), shared by the
    legacy ``runtime_next_step`` path (:func:`_dn_decision_materialize`) and
    the composition path (``advance_run_state_after_composition``).

    ``None`` unless ``decision`` is a WP-iteration step. A resolution failure
    PROPAGATES -- typed, carrying its ``error_code`` -- before anything is
    written, so the run stays at the issued step instead of being advanced
    into a step whose workspace cannot be resolved (the wedge). It is
    deliberately never wrapped into a ``blocked`` Decision (FR-008)."""
    if decision.kind != "step" or not decision.step_id or not _mapping._is_wp_iteration_step(decision.step_id):
        return None
    return _mapping._wp_iteration_action_and_state(
        decision.step_id,
        mission_slug,
        mission_type,
        feature_dir,
        repo_root,
        owned=owned,
    )


def _dn_preresolve_wp_workspace(ctx: DecideNextContext) -> tuple[Any, _mapping._WpIterationResolution | None]:
    """Plan the advance (the engine's own pure :func:`plan_advance`) and resolve
    the step it will issue BEFORE anything is persisted. Returns ``(plan,
    resolution)``; ``(None, None)`` when no plan can be previewed. The plan is
    then COMMITTED by :func:`_dn_advance_engine` -- the engine plans once."""
    try:
        plan = _engine_adapter.plan_advance(ctx.run_ref, ctx.agent, ctx.result)
    except _engine_adapter.PLAN_UNAVAILABLE_ERRORS:
        logger.debug("advance preview unavailable for %s; advancing without pre-resolution", ctx.mission_slug, exc_info=True)
        return None, None
    resolution = _resolve_planned_wp_workspace(
        plan.decision,
        mission_slug=ctx.mission_slug,
        mission_type=ctx.mission_type,
        feature_dir=ctx.feature_dir,
        repo_root=ctx.repo_root,
        owned=ctx.owned,
    )
    return plan, resolution


def _dn_advance_engine(ctx: DecideNextContext, plan: Any, engine_emitter: Any) -> NextDecision:
    """Persist the advance: commit the previewed ``plan`` when there is one
    (no second planning), else -- or when the run moved past the plan
    (:class:`StaleAdvancePlan`) -- the engine's own ``next_step``."""
    if plan is not None:
        try:
            return _engine_adapter.commit_advance(ctx.run_ref, plan, ctx.agent, engine_emitter)
        except _engine_adapter.StaleAdvancePlan:
            logger.debug("advance plan for %s is stale; re-planning through next_step", ctx.mission_slug, exc_info=True)
    return runtime_next_step(ctx.run_ref, agent_id=ctx.agent, result=ctx.result, emitter=engine_emitter)


def _dn_decision_materialize(ctx: DecideNextContext) -> Decision:
    """Phase 4/4 of ``decide_next_via_runtime`` (FR-010) — advance via the
    runtime planner and materialize the terminal/step/query ``Decision``
    through WP07's Decision-builder. Always returns a ``Decision`` (never
    ``None``): this is the chain's terminal phase.

    Strict retrospective policy remains a pre-completion gate. The default
    post-completion policy is best-effort and must not buffer or roll back
    MissionRunCompleted; it runs after terminal events have flushed.
    """
    # Root discipline (FR-009): retrospective policy is a P-local governance
    # read for an owned mission.
    config_root = ctx.owned.owned_root if ctx.owned is not None else ctx.repo_root
    policy, _source_map, policy_error = _retrospective_seam._resolve_retrospective_policy_for_runtime(config_root)
    retrospective_enabled = bool(getattr(policy, "enabled", False))
    block_on_retrospective = _retrospective_seam._retrospective_blocks_completion(policy)

    # T061 step 3: resolve a WP-iteration step's workspace BEFORE anything is
    # persisted; a failure propagates here with the run directory untouched.
    preview_plan, preresolved = _dn_preresolve_wp_workspace(ctx)
    preview_step_id = preview_plan.decision.step_id if preview_plan is not None else None

    pre_state_bytes: bytes | None = None
    pre_events_size: int | None = None
    # Use the DecisionGitLog-wrapped emitter as the engine's emitter so that
    # decision events are durably committed to the coordination branch.
    engine_emitter: Any = ctx.emitter_for_engine
    buffer: _retrospective_seam._BufferingRuntimeEmitter | None = None

    if block_on_retrospective:
        captured = _dn_capture_pre_speculative_state(ctx.run_dir)
        if captured is None:
            # If we cannot capture pre-state we cannot guarantee a clean
            # rollback. Surface this as a blocked Decision rather than
            # advancing into a state we cannot retract.
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.blocked,
                    agent=ctx.agent,
                    mission_slug=ctx.mission_slug,
                    mission=ctx.mission_type,
                    mission_state=ctx.current_step_id or "unknown",
                    timestamp=ctx.now,
                    reason=("Cannot read run state.json / run.events.jsonl before speculative engine advance; refusing to advance"),
                    progress=ctx.progress,
                    origin=ctx.origin,
                )
            )
        pre_state_bytes, pre_events_size = captured
        buffer = _retrospective_seam._BufferingRuntimeEmitter()
        engine_emitter = buffer

    # Advance via runtime
    try:
        runtime_decision = _dn_advance_engine(ctx, preview_plan, engine_emitter)
    except Exception as exc:
        # Engine raised: discard any buffered events; nothing left to flush.
        if buffer is not None:
            buffer.discard()
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=ctx.agent,
                mission_slug=ctx.mission_slug,
                mission=ctx.mission_type,
                mission_state=ctx.current_step_id or "unknown",
                timestamp=ctx.now,
                reason=f"Runtime engine error: {exc}",
                progress=ctx.progress,
                origin=ctx.origin,
            )
        )

    if block_on_retrospective and runtime_decision.kind == DecisionKind.terminal:
        gate_decision = _dn_terminal_retrospective_gate(ctx, policy_error, buffer, pre_state_bytes, pre_events_size)
        if gate_decision is not None:
            return gate_decision

    # Gate either passed (terminal allow) or never ran (non-terminal /
    # not opted in): flush any buffered emit calls into the decision-log-
    # wrapped engine emitter so decision events are durably recorded and
    # observers receive them in original order (ADR 2026-09-06-2 (c)).
    if buffer is not None:
        buffer.flush(ctx.emitter_for_engine)

    if retrospective_enabled and not block_on_retrospective and runtime_decision.kind == DecisionKind.terminal:
        mission_id = _retrospective_seam._resolve_mission_id_for_terminus(ctx.feature_dir)
        _retrospective_seam._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=ctx.mission_slug,
            feature_dir=ctx.feature_dir,
            repo_root=config_root,
            block_on_failure=False,
        )

    return _mapping._map_runtime_decision(
        runtime_decision,
        ctx.agent,
        ctx.mission_slug,
        ctx.mission_type,
        ctx.repo_root,
        ctx.feature_dir,
        ctx.now,
        ctx.progress,
        ctx.origin,
        owned=ctx.owned,
        # Reuse the pre-persist resolution only for the very step it was
        # computed for; any other outcome resolves normally in the mapper.
        wp_resolution=preresolved if runtime_decision.step_id == preview_step_id else None,
    )


def decide_next_via_runtime(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> Decision:
    """Main entry point replacing old decide_next().

    A linear four-phase early-return chain over :class:`DecideNextContext`
    (FR-010): bootstrap builds the context (and may itself short-circuit —
    feature dir missing / run failed to start); dependency-gate,
    composition-dispatch, and decision-materialize each take ``ctx`` and
    return ``Decision | None``, the first non-``None`` short-circuiting.
    decision-materialize is the terminal phase and always resolves.

    Flow:
    0. Committed-authority pre-check (#2947, D13) — a merged mission
       (``mission_terminal_verdict`` is ``terminal``/``blocked_conflict``)
       short-circuits BEFORE workspace selection / run start, returning
       ``kind: terminal`` (no run created) or ``kind: blocked``. A ``"none"``
       verdict falls through unchanged (F5).
    1. Resolve mission_type from meta.json
    2. get_or_start_run() to obtain MissionRunRef
    3. Check if current step is a WP-iteration step
       a. If yes and WPs remain: skip runtime advance, build WP prompt, return step
       b. If yes and all WPs done: call next_step(result="success") to advance
    4. For non-WP steps: call next_step(run_ref, agent, result) directly
    5. Map NextDecision -> Decision (preserving JSON contract)
    """
    merged_short_circuit = _mapping._merged_mission_short_circuit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        agent=agent,
        now=now_utc_iso(),
        terminal_kind=DecisionKind.terminal,
        owned=owned,
    )
    if merged_short_circuit is not None:
        return merged_short_circuit

    ctx, early_decision = _dn_bootstrap(
        agent,
        mission_slug,
        result,
        repo_root,
        owned=owned,
    )
    if early_decision is not None:
        return early_decision
    assert ctx is not None  # _dn_bootstrap always pairs a ctx with None (or vice versa)

    for phase in (_dn_finalized_board_override, _dn_dependency_gate, _dn_composition_dispatch, _dn_decision_materialize):
        decision = phase(ctx)
        if decision is not None:
            return decision

    raise AssertionError(  # pragma: no cover — decision-materialize always resolves
        "decide_next_via_runtime: no phase produced a Decision"
    )


def _build_finalized_override_query_decision(
    *,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict | None,
    emitted_run_id: str | None,
    repo_root: Path,
    finalized_override: str,
    owned: OwnedCheckout | None = None,
) -> Decision:
    override_wp_id: str | None = None
    if finalized_override == "done":
        mission_state = "done"
        preview_step = None
        reason = "All work packages are done"
    elif finalized_override.startswith("blocked:"):
        mission_state = "blocked"
        preview_step = None
        reason = finalized_override.split(":", 1)[1].replace("_", " ")
    else:
        mission_state = finalized_override
        preview_step = finalized_override
        reason = None
        if finalized_override == "implement":
            from mission_runtime import MissionArtifactKind, mission_context_for
            from runtime.next.discovery import preview_claimable_wp

            mission_context = mission_context_for(
                repo_root,
                mission_slug,
                owned=owned,
                tolerate_unmaterialized_coord=True,  # FR-022: a declared-but-not-yet-created coordination worktree is read/materialised, not refused
            )
            preview = preview_claimable_wp(
                mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK).read_dir,
                status_dir=mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir,
            )
            override_wp_id = preview.wp_id
            if preview.wp_id is None and preview.selection_reason is not None:
                reason = preview.selection_reason
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=now,
            reason=reason,
            progress=progress,
            run_id=emitted_run_id,
            preview_step=preview_step,
            wp_id=override_wp_id,
        )
    )


def _build_initial_query_decision(
    *,
    runtime_decision: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict | None,
    emitted_run_id: str | None,
) -> Decision:
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state="not_started",
            timestamp=now,
            reason=None,
            progress=progress,
            run_id=emitted_run_id,
            preview_step=runtime_decision.step_id,
        )
    )


def _build_decision_required_query(
    *,
    runtime_decision: Any,
    snapshot: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict | None,
    emitted_run_id: str | None,
) -> Decision:
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=snapshot.issued_step_id or runtime_decision.step_id or "unknown",
            timestamp=now,
            reason=None,
            progress=progress,
            run_id=emitted_run_id,
            step_id=snapshot.issued_step_id or runtime_decision.step_id,
            decision_id=runtime_decision.decision_id,
            input_key=runtime_decision.input_key,
            question=runtime_decision.question,
            options=runtime_decision.options,
        )
    )


def _build_runtime_query_decision(
    *,
    runtime_decision: Any,
    snapshot: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict | None,
    emitted_run_id: str | None,
) -> Decision:
    mission_state = runtime_decision.step_id or "unknown"
    blocked_reason: str | None = None
    if runtime_decision.kind == DecisionKind.terminal:
        mission_state = "done"
    elif runtime_decision.kind == DecisionKind.blocked:
        mission_state = snapshot.issued_step_id or runtime_decision.step_id or "blocked"
        blocked_reason = snapshot.blocked_reason or getattr(runtime_decision, "reason", None)
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=now,
            reason=blocked_reason,
            progress=progress,
            run_id=emitted_run_id,
            step_id=snapshot.issued_step_id or runtime_decision.step_id,
        )
    )


def query_current_state(
    agent: str | None,
    mission_slug: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> Decision:
    """Return current mission state without advancing the DAG.

    Reads the run snapshot idempotently. Does NOT call next_step().
    Returns a Decision with kind=DecisionKind.query and is_query=True.

    Committed-authority pre-check (#2947, D13): before any workspace
    selection (``mission_context_for`` below), a merged mission
    (``mission_terminal_verdict`` is ``terminal``) short-circuits to
    ``kind: query`` / ``mission_state: "done"`` — query mode's structural
    ``kind: query`` contract (never ``kind: terminal`` here); a
    ``blocked_conflict`` verdict short-circuits to ``kind: blocked``. A
    ``"none"`` verdict falls through unchanged (F5), so
    ``_finalized_task_board_override_step`` (D9) never runs for a merged
    mission.

    Args:
        agent: Agent name (for Decision construction only).
        mission_slug: Mission slug (e.g. '069-planning-pipeline-integrity').
        repo_root: Repository root path.
    """
    now = now_utc_iso()
    merged_short_circuit = _mapping._merged_mission_short_circuit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        agent=agent,
        now=now,
        terminal_kind=DecisionKind.query,
        owned=owned,
    )
    if merged_short_circuit is not None:
        return merged_short_circuit

    mission_context = _query_resolve_mission_context(repo_root, mission_slug, owned=owned)
    mission_slug = mission_context.mission_slug

    from mission_runtime import MissionArtifactKind

    task_board = mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK)
    status_state = mission_context.artifact(MissionArtifactKind.STATUS_STATE)

    if not task_board.read_dir.is_dir():
        # Conscious decision (C-IC02): reaching here means the resolver RESOLVED
        # a directory and verified it ``exists()`` (see resolution.py), yet it is
        # not a directory on disk — i.e. the canonical mission dir name resolved
        # to a regular file. That is a genuinely malformed / missing mission, not
        # a read-path topology miss, so ``MISSION_NOT_FOUND`` is the correct,
        # deliberately-kept classification here (NOT a read-path collapse).
        raise MissionNotFoundError(mission_slug)

    mission_type = mission_context.mission_type
    task_error = _mapping._wp_task_surface_error(task_board.read_dir, status_state.read_dir, mission_slug)
    if task_error is not None:
        # Query remains a read-only query decision, but an inconsistent task
        # surface cannot produce truthful file-derived progress. Match the
        # advancing board's fail-closed recovery without emitting partial totals.
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.query,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="blocked",
                timestamp=now,
                reason=task_error,
            )
        )

    progress = _compute_wp_progress(task_board.read_dir, status_dir=status_state.read_dir)

    # Root discipline: the run store (and the template/policy reads that start
    # an ephemeral preview run) live at P for an owned mission.
    config_root = owned.owned_root if owned is not None else repo_root
    run_ref = _io_seam._existing_run_ref(mission_slug, config_root, mission_type, owned=owned)
    ephemeral_run_store: Path | None = None

    # Read current step WITHOUT calling next_step(). When no step has been
    # issued yet, use the planner read-only to compute a truthful preview.
    # The try/finally below guarantees the ephemeral run store is cleaned up
    # on every return path (success, raise, or early exit).
    try:
        run_ref, ephemeral_run_store, snapshot, runtime_decision = _query_read_runtime_plan(
            run_ref,
            mission_slug,
            mission_type,
            config_root,
        )

        # Query mode never persists the ephemeral run it bootstraps for a
        # not-yet-started mission. Returning that run's id in the JSON would
        # mislead callers into thinking they can issue ``spec-kitty next
        # --mission <slug> --result …`` against it; in reality the run state
        # is wiped in the finally block before the function returns. Only
        # emit ``run_id`` when the run is a real, persisted one.
        emitted_run_id: str | None = None
        if ephemeral_run_store is None:
            emitted_run_id = getattr(run_ref, "run_id", None)

        return _query_dispatch_decision(
            task_board=task_board,
            status_state=status_state,
            progress=progress,
            snapshot=snapshot,
            runtime_decision=runtime_decision,
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            now=now,
            repo_root=repo_root,
            owned=owned,
            emitted_run_id=emitted_run_id,
        )
    finally:
        if ephemeral_run_store is not None:
            shutil.rmtree(ephemeral_run_store, ignore_errors=True)


def _query_resolve_mission_context(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> Any:
    """Campsite extraction (T058) of ``query_current_state``'s mission-context
    resolution: the try/except ``ActionContextError`` -> read-path
    pass-through / ``MissionNotFoundError`` mapping. Behaviour-preserving —
    no change to the exception shapes this raises."""
    from mission_runtime import ActionContextError, mission_context_for

    try:
        return mission_context_for(
            repo_root,
            mission_slug,
            owned=owned,
            tolerate_unmaterialized_coord=True,  # FR-022: a fresh coordination mission is queryable before its worktree exists
        )
    except ActionContextError as exc:
        # FR-001 / C-IC02: pass a typed *read-path* error through VERBATIM. The
        # resolver already produced the precise code (e.g.
        # COORDINATION_BRANCH_DELETED / STATUS_READ_PATH_NOT_FOUND) plus the real
        # read-path remediation; collapsing it into a generic MISSION_NOT_FOUND
        # ("run mission list") points the operator the wrong way (the mission is
        # not missing — its read path is broken; the disease #15). The command
        # layer surfaces ``exc.code`` + checked paths from the typed error.
        if _is_read_path_error(exc):
            raise
        # A genuinely-missing mission (e.g. FEATURE_CONTEXT_UNRESOLVED — no mission
        # directory at all) is legitimately MISSION_NOT_FOUND (FR-004 / WP03).
        raise MissionNotFoundError(mission_slug) from exc


def _query_read_runtime_plan(
    run_ref: Any,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
) -> tuple[Any, Path | None, Any, Any]:
    """Campsite extraction (T058) of ``query_current_state``'s nested
    ephemeral-run-and-planner try/except. Returns
    ``(run_ref, ephemeral_run_store, snapshot, runtime_decision)``.
    Behaviour-preserving."""
    ephemeral_run_store: Path | None = None
    try:
        if run_ref is None:
            run_ref, ephemeral_run_store = _io_seam._start_ephemeral_query_run(
                mission_slug,
                mission_type,
                repo_root,
            )
            snapshot = _engine_adapter._read_snapshot(Path(run_ref.run_dir))
            template_path = Path(run_ref.run_dir) / "mission_template_frozen.yaml"
            template = load_mission_template_file(template_path)
        else:
            snapshot = _engine_adapter._read_snapshot(Path(run_ref.run_dir))
            template_path = Path(snapshot.template_path)
            template = load_mission_template_file(template_path)
        runtime_decision = _engine_adapter.plan_next(
            snapshot,
            template,
            snapshot.policy_snapshot,
            live_template_path=template_path,
        )
    except QueryModeValidationError:
        raise
    except Exception as exc:
        raise QueryModeValidationError(f"Could not read query state for mission '{mission_slug}': {exc}") from exc
    return run_ref, ephemeral_run_store, snapshot, runtime_decision


def _query_dispatch_decision(
    *,
    task_board: Any,
    status_state: Any,
    progress: dict | None,
    snapshot: Any,
    runtime_decision: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    repo_root: Path,
    owned: OwnedCheckout | None,
    emitted_run_id: str | None,
) -> Decision:
    """Campsite extraction (T058) of ``query_current_state``'s
    finalized-override / initial / decision-required / runtime branch
    ladder. Behaviour-preserving."""
    finalized_override = _mapping._finalized_task_board_override_step(
        task_board.read_dir,
        progress,
        status_dir=status_state.read_dir,
    )
    if finalized_override is not None:
        return _build_finalized_override_query_decision(
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            now=now,
            progress=progress,
            emitted_run_id=emitted_run_id,
            repo_root=repo_root,
            finalized_override=finalized_override,
            owned=owned,
        )

    if not snapshot.completed_steps and not snapshot.pending_decisions and not snapshot.decisions:
        if runtime_decision.kind in {DecisionKind.step, DecisionKind.decision_required} and runtime_decision.step_id:
            return _build_initial_query_decision(
                runtime_decision=runtime_decision,
                agent=agent,
                mission_slug=mission_slug,
                mission_type=mission_type,
                now=now,
                progress=progress,
                emitted_run_id=emitted_run_id,
            )
        raise QueryModeValidationError(f"Mission '{mission_type}' has no issuable first step for run '{mission_slug}'")

    if runtime_decision.kind == DecisionKind.decision_required:
        return _build_decision_required_query(
            runtime_decision=runtime_decision,
            snapshot=snapshot,
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            now=now,
            progress=progress,
            emitted_run_id=emitted_run_id,
        )

    return _build_runtime_query_decision(
        runtime_decision=runtime_decision,
        snapshot=snapshot,
        agent=agent,
        mission_slug=mission_slug,
        mission_type=mission_type,
        now=now,
        progress=progress,
        emitted_run_id=emitted_run_id,
    )


def answer_decision_via_runtime(
    mission_slug: str,
    decision_id: str,
    answer: str,
    agent: str,
    repo_root: Path,
    *,
    actor_type: str = "human",
    owned: OwnedCheckout | None = None,
) -> None:
    """Answer a pending decision.

    CLI answers are human-authored by default even though the command still
    carries an ``--agent`` identity for the surrounding mission loop.
    """
    import logging

    logger = logging.getLogger(__name__)

    from mission_runtime import ActionContextError, resolve_action_context

    try:
        _ctx = resolve_action_context(
            repo_root,
            action="tasks",
            feature=mission_slug,
            owned=owned,
        )
        feature_dir = Path(_ctx.feature_dir)
    except ActionContextError as exc:
        # FR-001 / C-IC02: preserve the typed read-path error IDENTICALLY on the
        # decision-answer path (the same fidelity obligation as the query path).
        # Collapsing it into a generic "not found" MissionRuntimeError would drop
        # ``exc.code`` (e.g. COORDINATION_BRANCH_DELETED) and the read-path
        # remediation, mis-routing the operator. Log the context, then re-raise
        # the typed ActionContextError so the command layer surfaces its code.
        logger.warning(
            "answer_decision_via_runtime: read-path error (%s) for mission %r in repo %s — cannot answer decision %r",
            exc.code,
            mission_slug,
            repo_root,
            decision_id,
        )
        raise
    if not feature_dir.is_dir():
        logger.warning(
            "answer_decision_via_runtime: mission %r resolved to missing dir %s — cannot answer decision %r",
            mission_slug,
            feature_dir,
            decision_id,
        )
        raise MissionRuntimeError(f"Mission {mission_slug!r} not found; cannot answer decision {decision_id!r}")
    mission_type = get_mission_type(feature_dir)
    config_root = owned.owned_root if owned is not None else repo_root
    run_ref = _io_seam.get_or_start_run(mission_slug, config_root, mission_type, owned=owned)
    # E3 (#3929): same bridge-entry registration as the decide path.
    from specify_cli.status import ensure_runtime_moment_producer  # noqa: PLC0415

    ensure_runtime_moment_producer()
    sync_emitter = runtime_emitter_for_mission(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_type=mission_type,
    )
    try:
        snapshot = _engine_adapter._read_snapshot(Path(run_ref.run_dir))
    except Exception as exc:
        logger.warning(
            "answer_decision_via_runtime: failed to seed emitter from snapshot for run %r: %s",
            run_ref.run_dir,
            exc,
        )
    else:
        seed_runtime_emitter(sync_emitter, snapshot)
    # Wrap with DecisionGitLog so the answered decision is committed to the
    # coordination branch (spec-kitty #1546, FR-001–FR-005).
    answer_emitter: Any = _decision_log._wrap_with_decision_git_log(sync_emitter, mission_slug, repo_root, owned=owned)
    actor = ActorIdentity(actor_id=agent, actor_type=actor_type)
    runtime_provide_decision_answer(
        run_ref,
        decision_id,
        answer,
        actor,
        emitter=answer_emitter,
    )


# ---------------------------------------------------------------------------
# Public surface (FR-007 / #2531 WP03). Governs ``from runtime_bridge import *``
# ONLY. It lists the 8 public names; seam-owned private names are not
# re-exported here.
# ---------------------------------------------------------------------------
__all__ = [
    "DecisionGitLogUnavailable",
    "MissionNotFoundError",
    "QueryModeValidationError",
    "answer_decision_via_runtime",
    "build_operational_context_for_claim",
    "decide_next_via_runtime",
    "get_or_start_run",
    "query_current_state",
]
