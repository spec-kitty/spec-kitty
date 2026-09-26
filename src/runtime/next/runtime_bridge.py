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
#                              (former CC23 ``_advance_run_state_after_composition``
#                              body, reduced to <=15) — this module keeps only
#                              a thin residual compat delegate under the same
#                              name so its 8x-patch/9x-attr monkeypatch surface
#                              still intercepts (contracts/compat-surface.md).
#
#   runtime_bridge_retrospective.py   sole home of the self-contained
#                              Confirm.ask-gated retrospective / learning-
#                              capture cluster (FR-006). This module keeps a
#                              native thin compat delegate under each of the 9
#                              symbols the WP02 compat guard binds (see the
#                              seam module's docstring for why a plain
#                              re-export is insufficient here — the guard's
#                              identity check hardcodes the cross-module
#                              baseline).
#
#   runtime_bridge_io.py       sole home of the narrow I/O ports (IC-04):
#                              feature-runs.json index, template/pack
#                              discovery, run lifecycle, the OperationalContext
#                              builder, the FR-009 gather_artifact_presence
#                              fact-port, and the pure resolve_commit_target
#                              lifted out of _wrap_with_decision_git_log. Same
#                              native-thin-delegate rule as the retrospective
#                              seam applies to every compat-tracked symbol
#                              moved there.
#
#   runtime_bridge_cores.py    sole home of the pure, zero-dependency leaves
#                              (FR-009): the tasks.md parse family and the
#                              guard inversion (`evaluate_guards(snapshot)`
#                              folding `_check_cli_guards` /
#                              `_check_composed_action_guard` /
#                              `_check_requirement_mapping_ready`'s decision
#                              tail over the WP05 `ArtifactPresenceSnapshot`
#                              fact-port). Same native-thin-delegate rule for
#                              every compat-tracked symbol moved there; two
#                              symbols (`_parse_wp_sections_from_tasks_md` /
#                              `_parse_requirement_refs_from_tasks_md`) use a
#                              same-module live-lookup between their two
#                              residual delegates rather than forwarding to
#                              the cores-internal call, closing the
#                              intra-seam false-green trap for their mutual
#                              call (see their docstrings below).
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
#                              through. Same native-thin-delegate rule for
#                              every compat-tracked symbol moved there.
#                              ``_advance_run_state_after_composition``
#                              (WP03) is unaffected — its logic already lives
#                              in the engine adapter and its thin residual
#                              delegate stays defined right here, unmoved.
#
#   runtime_bridge_identity.py   sole home of the hottest fracture line
#                              (WP10, LAST): coord-branch naming
#                              (``_resolve_coordination_branch``), mission-ULID
#                              resolution (``_resolve_mission_ulid``), and
#                              primary-feature-dir resolution
#                              (``_primary_runtime_feature_dir``) — the scars
#                              #2091/#1978/#1918/#1814/#2069 cluster. Same
#                              native-thin-delegate rule for every compat-
#                              tracked symbol moved there; both intra-seam
#                              callers of ``_primary_runtime_feature_dir``
#                              (patched 6x) route back through THIS module's
#                              own delegate via a live, deferred lookup rather
#                              than a bare intra-seam call (research.md
#                              §Compat's grounded false-green trap).
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
#     ``import *``); the ~50 private symbols tests patch stay preserved by the
#     explicit guarded compat re-export block, not by ``__all__`` (FR-012).
#
# De-godding effort: https://github.com/Priivacy-ai/spec-kitty/issues/2531
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import dataclasses
import logging
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kernel.clock import now_utc_iso

if TYPE_CHECKING:
    from charter.activation.invocation_context import OperationalContext as OperationalContextT

from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionRunRef,
    NextDecision,
    next_step as runtime_next_step,
    provide_decision_answer as runtime_provide_decision_answer,
)
from runtime.next._internal_runtime.schema import ActorIdentity, MissionRuntimeError, load_mission_template_file
from runtime.next import runtime_bridge_composition as _composition
from runtime.next import runtime_bridge_cores as _cores
from runtime.next import runtime_bridge_engine as _engine_adapter
from runtime.next import runtime_bridge_identity as _identity_seam
from runtime.next import runtime_bridge_io as _io_seam
from runtime.next import runtime_bridge_retrospective as _retrospective_seam

# WP18 (#2561) — the untracked self-alias re-exports that formerly lived here
# (the five ``runtime_bridge_cores`` parse-family helpers, plus
# ``_retrospective_blocks_completion`` / ``_composition_dispatch_inputs`` /
# ``_has_generated_docs``) were retired now that no consumer patches them via
# the ``runtime_bridge.<name>`` façade path. Their leaves are reached directly
# from the owning seam (``_cores`` / ``_retrospective_seam`` / ``_composition``)
# at each call site below; the seam ``_rb.<name>`` round-trips were repointed to
# the owning seam in the same change.

from specify_cli.core.constants import MISSION_TYPE_SOFTWARE_DEV
from specify_cli.mission import get_mission_type
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.status import CanonicalStatusNotFoundError
from specify_cli.status import Lane
from specify_cli.status import get_all_wp_snapshots
from specify_cli.status import wp_state_for
from specify_cli.status_lanes import has_operator_provenance, is_acceptable_ending
from runtime.next.decision import (
    Decision,
    DecisionKind,
    _build_prompt_or_error,
    _build_prompt_safe,
    _compute_wp_progress,
    _find_first_wp_by_lane,
    _state_to_action,
)
from runtime.next._internal_runtime.events import RuntimeEventEmitter, runtime_emitter_for_mission, seed_runtime_emitter
from mission_runtime import routes_through_coordination

logger = logging.getLogger(__name__)

KITTIFY_DIR = ".kittify"
# MISSION_RUNTIME_YAML / MISSION_YAML moved to runtime_bridge_io.py (T017 —
# their only residual users, the discovery cluster, moved with them).


class DecisionGitLogUnavailable(RuntimeError):
    """Decision audit logging cannot be made durable for a modern mission."""


def _primary_runtime_feature_dir(repo_root: Path, mission_slug: str) -> Path:
    """Thin compat delegate (native ``def``; FR-012 compat surface, #2531
    WP10) — forwards to :func:`runtime_bridge_identity._primary_runtime_feature_dir`.
    Patched 6x by ``tests/runtime/test_runtime_bridge_identity.py`` — kept as a
    native ``def`` (never a plain re-export) so this name's ``__module__``
    stays ``runtime_bridge``, and both intra-seam callers of the real
    implementation (:func:`runtime_bridge_identity._resolve_coordination_branch`
    / ``._resolve_mission_ulid``) route back through THIS delegate via a live,
    deferred lookup rather than a bare intra-seam call — see
    ``runtime_bridge_identity``'s module docstring for the false-green
    mechanism this closes."""
    return _identity_seam._primary_runtime_feature_dir(repo_root, mission_slug)


def _resolve_coordination_branch(mission_slug: str, repo_root: Path) -> str:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_identity._resolve_coordination_branch` (FR-012
    compat surface, #2531 WP10; see module-level comment above and
    ``runtime_bridge_identity``'s docstring)."""
    return _identity_seam._resolve_coordination_branch(mission_slug, repo_root)


def _resolve_mission_ulid(mission_slug: str, repo_root: Path) -> str | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_identity._resolve_mission_ulid` (FR-012 compat
    surface, #2531 WP10; see module-level comment above and
    ``runtime_bridge_identity``'s docstring)."""
    return _identity_seam._resolve_mission_ulid(mission_slug, repo_root)


def _mission_routes_through_coordination(
    mission_slug: str,
    repo_root: Path,
    *,
    effective_root: Path | None = None,
) -> bool:
    """Return True when the mission's STORED topology routes through coordination.

    Reads the WP02 stored :class:`MissionTopology` (FR-004) from ``meta.json`` via
    the **pure** :func:`read_topology` reader and disposes the coord-vs-flattened
    SHAPE from it — replacing the retired ``meta.coordination_branch is not None``
    derivation (the second #2069 inference, which keyed the decision on a value
    presence rather than the stored shape, SC-001). The read is PURE: an
    un-backfilled mission is classified once and NOT persisted, so this read path
    never writes ``meta.json`` (the read-only contract, #1814). The coord-routing
    membership is disposed by the ONE canonical predicate
    (:func:`routes_through_coordination`) over the ONE canonical set — no second
    ``{COORD, LANES_WITH_COORD}`` set is restated here (FR-005). A coord-routing
    topology (``COORD`` / ``LANES_WITH_COORD``) returns ``True``; the coord-less
    cells return ``False``. Missing/malformed meta degrades to non-coord (matching
    the historical "no declared coord topology" arm).
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.migration.backfill_topology import read_topology

    # Anchor the stored-topology read on the topology-BLIND primary dir (where
    # meta.json lives), mirroring ``resolution._resolve_coordination_branch``.
    # A KIND-BLIND resolver (``candidate_feature_dir_for_mission``) genuinely
    # CAN land on a materialized-but-empty coord worktree here — that was the
    # original hazard this anchoring guarded against. The kind-aware seam
    # cannot: for a PRIMARY-partition kind (``PRIMARY_METADATA``) the decision
    # layer short-circuits to the primary anchor for EVERY topology and coord
    # state, before any coord probe (read-side-seam-primary-primitive-closure-
    # 01KYKMMT WP07, T032 — FR-004/FR-015).
    if effective_root is None:
        feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    else:
        from mission_runtime import mission_context_for

        mission_context = mission_context_for(
            repo_root,
            mission_slug,
            effective_root=effective_root,
        )
        feature_dir = mission_context.artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
    try:
        topology = read_topology(feature_dir)
    except (FileNotFoundError, ValueError, OSError, MissionMetaReadError):
        return False
    return routes_through_coordination(topology)


def _wrap_with_decision_git_log(
    emitter: RuntimeEventEmitter,
    mission_slug: str,
    repo_root: Path,
    *,
    effective_root: Path | None = None,
) -> Any:
    """Wrap ``emitter`` with DecisionGitLog for durable decision recording.

    Returns the wrapped emitter.  If construction fails (e.g. import error),
    the original emitter is returned unchanged so mission execution is not
    blocked.
    """
    if effective_root is None:
        coord_routing_topology = _mission_routes_through_coordination(mission_slug, repo_root)
    else:
        coord_routing_topology = _mission_routes_through_coordination(
            mission_slug,
            repo_root,
            effective_root=effective_root,
        )
    try:
        from specify_cli.coordination.workspace import CoordinationWorkspace
        from specify_cli.events.decision_log import DecisionGitLog

        if effective_root is None:
            coordination_branch = _resolve_coordination_branch(mission_slug, repo_root)
            mission_id = _resolve_mission_ulid(mission_slug, repo_root)  # str | None
        else:
            from mission_runtime import MissionArtifactKind, mission_context_for
            from specify_cli.mission_metadata import resolve_mission_identity

            mission_context = mission_context_for(
                repo_root,
                mission_slug,
                effective_root=effective_root,
            )
            coordination_branch = mission_context.artifact(MissionArtifactKind.STATUS_STATE).commit_target.ref
            primary_metadata_dir = mission_context.artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
            mission_id = resolve_mission_identity(primary_metadata_dir).mission_id

        # T019 (#2531 WP05): mid8 derivation + the fail-closed mid8-required
        # validation + CommitTarget/worktree_root-candidate selection is the
        # ONE pure decision that used to live inline here — lifted into
        # runtime_bridge_io.resolve_commit_target (data-model.md §Ports). See
        # that function's docstring for why this call raises
        # DecisionGitLogUnavailable identically to the pre-extraction inline
        # code (still caught by the except below) and why the .exists()-gated
        # branch remains here as the one genuinely I/O-bearing decision.
        _mid8, worktree_root_candidate, decision_target = _io_seam.resolve_commit_target(
            coord_routing_topology=coord_routing_topology,
            mission_slug=mission_slug,
            mission_id=mission_id,
            coordination_branch=coordination_branch,
            repo_root=repo_root,
        )

        # The decision-target topology SHAPE is READ from the WP02 stored topology
        # (FR-004 / SC-001) — never from ``_coord_path.exists()`` (the retired
        # disk-``stat`` ladder, C-004). The on-disk worktree-materialization check
        # (``_coord_path.exists()``) survives ONLY to choose the worktree_root for a
        # coord-routing mission (C-006 transient discrimination: materialized →
        # use it; not-yet-materialized → compose via ``CoordinationWorkspace.resolve``)
        # — it is NOT the topology classifier.
        if coord_routing_topology:
            # C-011 risk site: the worktree_root selection is preserved EXACTLY —
            # keyed off the stored-topology coord-routing decision and the C-006
            # transient on-disk materialization check, never ``.kind``.
            if worktree_root_candidate.exists():
                worktree_root = worktree_root_candidate
            elif effective_root is None:
                worktree_root = CoordinationWorkspace.resolve(repo_root, mission_slug, _mid8)
            else:
                worktree_root = _resolve_owned_coordination_workspace(
                    CoordinationWorkspace,
                    repo_root,
                    mission_slug,
                    _mid8,
                )
        else:
            # Coord-less topology: decisions land on the primary checkout's
            # current branch (a lane/mission branch); landing == coordination ==
            # target. worktree_root is the repo_root (preserved exactly).
            worktree_root = worktree_root_candidate

        return DecisionGitLog(
            repo_root=repo_root,
            worktree_root=worktree_root,
            destination_ref=coordination_branch,
            mission_slug=mission_slug,
            inner=emitter,
            mission_id=mission_id,
            target=decision_target,
        )
    except Exception as exc:
        if coord_routing_topology:
            raise DecisionGitLogUnavailable(
                "DecisionGitLog construction failed for declared coordination "
                f"topology mission {mission_slug!r}; refusing to continue "
                "without durable decision evidence."
            ) from exc
        logger.warning(
            "DecisionGitLog construction failed for mission %s; falling back to plain emitter.",
            mission_slug,
            exc_info=True,
        )
        return emitter


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
# Feature → Run index — bodies moved to runtime_bridge_io.py (T017); see
# ``_load_feature_runs`` below for the residual thin compat delegate.
#
# tasks.md parse family — bodies moved to runtime_bridge_cores.py (#2531
# WP06, T021; verbatim, zero-dependency pure leaf). ``TASKS_GLOB`` stays
# here (still used by ``_should_advance_wp_step`` / ``_check_requirement_
# mapping_ready``, neither of which moved).
# ---------------------------------------------------------------------------

TASKS_GLOB = "WP*.md"


def _parse_wp_sections_from_tasks_md(tasks_content: str) -> dict[str, str]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_cores._parse_wp_sections_from_tasks_md`."""
    return _cores._parse_wp_sections_from_tasks_md(tasks_content)


def _parse_requirement_refs_from_tasks_md(tasks_content: str) -> dict[str, list[str]]:
    """Thin compat delegate — parse requirement references per WP.

    Composed via THIS module's own :func:`_parse_wp_sections_from_tasks_md`
    delegate (bare call, resolved against ``runtime_bridge``'s own globals)
    rather than forwarding to :func:`runtime_bridge_cores._parse_requirement_
    refs_from_tasks_md` (whose internal call to the cores-local
    ``_parse_wp_sections_from_tasks_md`` would resolve against
    ``runtime_bridge_cores``'s globals instead). Both symbols are WP02
    compat-tracked and patched independently
    (``tests/runtime/test_bridge_compat_surface.py``'s ``REACH`` map); a
    blind forward here would make ``monkeypatch.setattr(runtime_bridge,
    "_parse_wp_sections_from_tasks_md", ...)`` a no-op false-green for any
    scenario that reaches it only through this function (the exact
    intra-seam-call trap research.md §Compat documents for
    ``_primary_runtime_feature_dir``)."""
    return {
        wp_id: _cores._collect_requirement_refs_for_section(section_content) for wp_id, section_content in _parse_wp_sections_from_tasks_md(tasks_content).items()
    }


class _BufferingRuntimeEmitter(_retrospective_seam._BufferingRuntimeEmitter):
    """Thin compat delegate (native ``class`` statement; FR-012 compat
    surface, #2531 WP04). Real implementation lives in
    :class:`runtime_bridge_retrospective._BufferingRuntimeEmitter` — inherited
    unchanged (no override). Kept as a native subclass definition (not a
    plain re-export alias) so ``_BufferingRuntimeEmitter.__module__`` stays
    ``runtime_bridge`` — the WP02 compat guard's identity/relocated-symbol
    check only tolerates the pre-existing ``runtime.next.decision``-origin
    cross-module symbols; see the module-level #2531 comment block above and
    ``runtime_bridge_retrospective``'s docstring."""


def _rich_hic_prompt() -> tuple[bool, str | None]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._rich_hic_prompt` (FR-012 compat
    surface, #2531 WP04; see module-level comment above)."""
    return _retrospective_seam._rich_hic_prompt()


def _resolve_mission_id_for_terminus(feature_dir: Path) -> str:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._resolve_mission_id_for_terminus`."""
    return _retrospective_seam._resolve_mission_id_for_terminus(feature_dir)


def _build_retrospective_facilitator_callback(
    mission_slug: str,
    repo_root: Path,
    provenance_kind: str = "runtime_post_completion",
) -> Any:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._build_retrospective_facilitator_callback`."""
    return _retrospective_seam._build_retrospective_facilitator_callback(mission_slug, repo_root, provenance_kind)


def _resolve_retrospective_policy_for_runtime(
    repo_root: Path,
) -> tuple[Any, dict[str, str], Exception | None]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._resolve_retrospective_policy_for_runtime`."""
    return _retrospective_seam._resolve_retrospective_policy_for_runtime(repo_root)


def _run_retrospective_learning_capture(
    *,
    mission_id: str,
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    block_on_failure: bool,
) -> None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._run_retrospective_learning_capture`."""
    _retrospective_seam._run_retrospective_learning_capture(
        mission_id=mission_id,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        repo_root=repo_root,
        block_on_failure=block_on_failure,
    )


def _classify_exc(exc: Exception) -> str:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._classify_exc`."""
    return _retrospective_seam._classify_exc(exc)


def _remediation_hint(exc: Exception, source_map: dict[str, str]) -> str | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._remediation_hint`."""
    return _retrospective_seam._remediation_hint(exc, source_map)


def _classify_and_emit_failure(
    *,
    mission_id: str,
    mission_slug: str,
    repo_root: Path,
    exc: Exception,
    source_map: dict[str, str],
    provenance_kind: str,
    emit_capture_failed: Any,
) -> None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_retrospective._classify_and_emit_failure`."""
    _retrospective_seam._classify_and_emit_failure(
        mission_id=mission_id,
        mission_slug=mission_slug,
        repo_root=repo_root,
        exc=exc,
        source_map=source_map,
        provenance_kind=provenance_kind,
        emit_capture_failed=emit_capture_failed,
    )


def _load_feature_runs(repo_root: Path) -> dict[str, _io_seam._FeatureRunEntry]:
    """Thin compat delegate — forwards to :func:`runtime_bridge_io.load_feature_runs`
    (via the repo_root -> path resolver :func:`runtime_bridge_io._feature_runs_path`)."""
    return _io_seam.load_feature_runs(_io_seam._feature_runs_path(repo_root))


def _mission_key_for_run_ref(run_ref: MissionRunRef, default: str) -> str:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._mission_key_for_run_ref`."""
    return _io_seam._mission_key_for_run_ref(run_ref, default)


def _build_run_ref(*, run_id: str, run_dir: str, mission_type: str) -> MissionRunRef:
    """Thin compat delegate — forwards to :func:`runtime_bridge_io._build_run_ref`.

    Passes this module's own ``MissionRunRef`` binding through explicitly
    (rather than letting the io module close over its own import) so tests
    that monkeypatch ``runtime_bridge.MissionRunRef`` observe the substitution."""
    return _io_seam._build_run_ref(run_id=run_id, run_dir=run_dir, mission_type=mission_type, run_ref_cls=MissionRunRef)


# ---------------------------------------------------------------------------
# WP iteration helpers
# ---------------------------------------------------------------------------

_WP_ITERATION_STEPS = frozenset({"implement", "review"})


def _is_wp_iteration_step(step_id: str) -> bool:
    """Check if a step is a WP-iteration step (implement, review)."""
    return step_id in _WP_ITERATION_STEPS


def _finalized_task_board_override_step(
    feature_dir: Path,
    progress: dict[str, int | float] | None,
    *,
    status_dir: Path | None = None,
) -> str | None:
    """Return the next step implied by finalized WP state, if available.

    This is intentionally narrow: it only overrides stale early runtime phases
    after a mission already has tasks.md, finalized WP files, and canonical WP
    lane state. It does not reorder non-finalized mission DAG execution.
    A board whose WPs all reach acceptable endings reports ``accept``; ``done``
    remains reserved for a board whose reduced lanes are all done, so an
    operator-canceled WP is never reported as done.
    """
    if progress is None:
        return None
    total = int(progress.get("total_wps", 0) or 0)
    if total <= 0:
        return None
    if not (feature_dir / "tasks.md").is_file() or not (feature_dir / "tasks").is_dir():
        return None

    if _find_first_wp_by_lane(feature_dir, "planned", status_dir=status_dir) is not None:
        return "implement"
    if _find_first_wp_by_lane(feature_dir, "claimed", status_dir=status_dir) is not None:
        return "implement"
    if _find_first_wp_by_lane(feature_dir, "in_progress", status_dir=status_dir) is not None:
        return "implement"
    if _find_first_wp_by_lane(feature_dir, "for_review", status_dir=status_dir) is not None:
        return "review"
    if _find_first_wp_by_lane(feature_dir, "in_review", status_dir=status_dir) is not None:
        return "blocked:review_in_progress"

    done_endings, acceptable_endings = _count_wp_endings(
        feature_dir,
        status_dir=status_dir,
    )
    if acceptable_endings == total:
        return "done" if done_endings == total else "accept"
    return "blocked:no_actionable_wp"


def _reduced_wp_lane(wp_snapshot: Mapping[str, Any] | None) -> str:
    """Return the canonical lane slot from a reduced WP snapshot."""
    if wp_snapshot is None:
        return str(Lane.UNINITIALIZED)
    return str(wp_snapshot.get("lane", Lane.GENESIS))


def _count_wp_endings(
    feature_dir: Path,
    *,
    status_dir: Path | None = None,
) -> tuple[int, int]:
    """Count WP files whose reduced lanes are done and acceptable endings."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return 0, 0

    lane_read_dir = status_dir if status_dir is not None else feature_dir
    try:
        wp_snapshots = get_all_wp_snapshots(lane_read_dir)
    except CanonicalStatusNotFoundError:
        return 0, 0

    acceptable_endings = 0
    done_endings = 0
    for wp_file in sorted(tasks_dir.glob(TASKS_GLOB)):
        wp_match = re.match(r"(WP\d+)", wp_file.stem)
        wp_id = wp_match.group(1) if wp_match else wp_file.stem
        wp_snapshot = wp_snapshots.get(wp_id)
        lane = _reduced_wp_lane(wp_snapshot)
        if lane == str(Lane.DONE):
            done_endings += 1
        if is_acceptable_ending(
            lane,
            has_provenance=has_operator_provenance(wp_snapshot),
        ):
            acceptable_endings += 1
    return done_endings, acceptable_endings


def _should_advance_wp_step(
    step_id: str,
    feature_dir: Path,
    *,
    repo_root: Path | None = None,
    mission_slug: str | None = None,
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
        anchor_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)

    tasks_dir = anchor_dir / "tasks"
    if not tasks_dir.is_dir():
        return True  # no WPs to iterate over

    wp_files = sorted(tasks_dir.glob(TASKS_GLOB))
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
) -> list[str]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_cores.evaluate_guards` over a
    :func:`runtime_bridge_io.gather_artifact_presence` snapshot (#2531 WP06,
    T022). ``wp_advance_ready`` is threaded through separately (not gathered
    by the snapshot) for ``implement``/``review`` so the pre-existing,
    unmoved :func:`_should_advance_wp_step` I/O read — and its own WP02
    compat reach — stay exactly where they were.

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
    ``read_all_wp_requirement_refs``, and the ``tasks_md.read_text`` prose
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
            parse_requirement_ids_from_spec_md,
            read_all_wp_requirement_refs,
        )

        spec_content = spec_md.read_text(encoding="utf-8")
        spec_ids = parse_requirement_ids_from_spec_md(spec_content)
        all_spec_requirement_ids = set(spec_ids["all"])
        functional_requirement_ids = set(spec_ids["functional"])

        _log_requirement_extraction_warnings_safely(feature_dir, spec_content)

        wps_manifest, manifest_findings = _load_wps_manifest_findings(feature_dir)
        if manifest_findings is not None:
            return manifest_findings
        wp_requirement_refs = read_all_wp_requirement_refs(tasks_dir)

        if wps_manifest is None:
            tasks_md = feature_dir / TASKS_ARTIFACT
            if tasks_md.exists():
                tasks_md_refs = _parse_requirement_refs_from_tasks_md(tasks_md.read_text(encoding="utf-8"))
                for wp_id, refs in tasks_md_refs.items():
                    if refs and not wp_requirement_refs.get(wp_id):
                        wp_requirement_refs[wp_id] = refs
    except Exception as exc:
        return [f"Requirement mapping preflight failed: {exc}"]

    wp_ids = tuple(sorted(wp_file.stem.split("-", 1)[0] for wp_file in tasks_dir.glob(TASKS_GLOB)))
    facts = _cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset(all_spec_requirement_ids),
        functional_requirement_ids=frozenset(functional_requirement_ids),
        wp_ids=wp_ids,
        wp_requirement_refs={wp_id: tuple(refs) for wp_id, refs in wp_requirement_refs.items()},
        feature_dir_name=feature_dir.name,
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
# The cluster itself now lives in ``runtime_bridge_composition.py`` (#2531
# WP08) — see that module's docstring for the constraints (C-001/C-002/
# C-003/C-008) that still govern it. This residual keeps:
#
#   * a **native thin compat delegate** for every WP02-tracked symbol
#     (FR-012) below, so ``monkeypatch.setattr(runtime_bridge, "<name>", …)``
#     keeps intercepting exactly as before the move;
#   * a **plain re-export** for the two untracked helpers
#     (``_composition_dispatch_inputs``, ``_has_generated_docs``) that
#     ``decide_next_via_runtime`` / ``runtime_bridge_io`` still reach bare /
#     via live lookup, respectively.
#
# ``_resolve_step_binding`` and ``_LEGACY_TASKS_STEP_IDS`` have no caller left
# in this module and are not compat-tracked — they live ONLY in
# ``runtime_bridge_composition.py`` now, with no residual re-export.
# (``_composition_dispatch_inputs`` / ``_has_generated_docs`` plain
# re-exports live in the top-of-file import block above, alongside the
# other untracked-helper re-exports, to keep them module-level per E402.)


def _normalize_action_for_composition(step_id: str) -> str:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._normalize_action_for_composition`
    (FR-012 compat surface, #2531 WP08)."""
    return _composition._normalize_action_for_composition(step_id)


def _should_dispatch_via_composition(
    mission: str,
    step_id: str,
    *,
    run_dir: Path | None = None,
    repo_root: Path | None = None,
) -> bool:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._should_dispatch_via_composition`
    (FR-008 selection seam; FR-012 compat surface, #2531 WP08). See the seam
    module's docstring for the full order-critical charter-lookup /
    custom-widening contract."""
    return _composition._should_dispatch_via_composition(mission, step_id, run_dir=run_dir, repo_root=repo_root)


def _resolve_step_agent_profile(run_dir: Path, step_id: str) -> str | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._resolve_step_agent_profile`
    (FR-012 compat surface, #2531 WP08)."""
    return _composition._resolve_step_agent_profile(run_dir, step_id)


def _resolve_runtime_contract_for_step(
    *,
    repo_root: Path,
    run_dir: Path,
    mission: str,
    step_id: str,
) -> Any | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._resolve_runtime_contract_for_step`
    (identity-only compat surface — GUARD_B_ONLY_IMPORT_SURFACE in
    contracts/compat-surface.md; #2531 WP08)."""
    return _composition._resolve_runtime_contract_for_step(repo_root=repo_root, run_dir=run_dir, mission=mission, step_id=step_id)


def _count_source_documented_events(feature_dir: Path) -> int:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._count_source_documented_events`
    (FR-012 compat surface, #2531 WP08)."""
    return _composition._count_source_documented_events(feature_dir)


def _publication_approved(feature_dir: Path) -> bool:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._publication_approved`
    (FR-012 compat surface, #2531 WP08)."""
    return _composition._publication_approved(feature_dir)


def _check_composed_action_guard(
    action: str,
    feature_dir: Path,
    *,
    mission: str = "software-dev",
    legacy_step_id: str | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._check_composed_action_guard`
    (FR-012 compat surface, #2531 WP08). See the seam module's docstring for
    the full guard-branch-family / legacy-vs-composition-only contract.

    ``repo_root`` (#3704 WP03, FR-003) is forwarded unchanged; defaults to
    ``None`` (built-in tree only, matching every existing caller of this
    compat surface that does not yet pass a real ``repo_root``)."""
    return _composition._check_composed_action_guard(action, feature_dir, mission=mission, legacy_step_id=legacy_step_id, repo_root=repo_root)


def _dispatch_via_composition(
    *,
    repo_root: Path,
    mission: str,
    action: str,
    actor: str,
    profile_hint: str | None,
    request_text: str | None,
    mode_of_work: Any | None,
    feature_dir: Path,
    legacy_step_id: str | None = None,
    contract: Any | None = None,
) -> list[str] | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_composition._dispatch_via_composition`
    (FR-012 compat surface, #2531 WP08). See the seam module's docstring for
    the full ``StepContractExecutor`` handoff / structured-failure contract."""
    return _composition._dispatch_via_composition(
        repo_root=repo_root,
        mission=mission,
        action=action,
        actor=actor,
        profile_hint=profile_hint,
        request_text=request_text,
        mode_of_work=mode_of_work,
        feature_dir=feature_dir,
        legacy_step_id=legacy_step_id,
        contract=contract,
    )


# Single-dispatch invariant (FR-001 / phase6-composition-stabilization-01KQ2JAS):
# After a composition-backed software-dev action succeeds, run state must still
# advance through the next public step — but the legacy ``runtime_next_step``
# DAG dispatch handler MUST NOT be invoked for the same action attempt.
#
# THIN RESIDUAL COMPAT DELEGATE (#2531 WP03, FR-013): the logic that used to
# live here now lives at ``runtime_bridge_engine.advance_run_state_after_composition``
# (adapter-owned — it reuses the same engine primitives ``runtime_next_step``
# uses internally: ``_read_snapshot``, ``_append_event``, ``_load_frozen_template``,
# ``plan_next``, ``_write_snapshot``). This delegate exists ONLY so the heavy
# monkeypatch surface tests bind to (8x ``monkeypatch.setattr``/``mocker.patch``
# + 9x bare-attribute reads across the suite, per contracts/compat-surface.md)
# keeps resolving against ``runtime_bridge._advance_run_state_after_composition``
# unchanged. Do not add logic here — extend the adapter instead.
def _advance_run_state_after_composition(
    *,
    run_ref: MissionRunRef,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict[str, int | float] | None,
    origin: dict[str, Any],
    sync_emitter: RuntimeEventEmitter,
) -> Decision:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_engine.advance_run_state_after_composition`. See the
    module-level comment above for why this delegate must stay (FR-012 compat
    surface) even though the logic itself moved (FR-013)."""
    return _engine_adapter.advance_run_state_after_composition(
        run_ref=run_ref,
        agent=agent,
        mission_slug=mission_slug,
        mission_type=mission_type,
        repo_root=repo_root,
        feature_dir=feature_dir,
        timestamp=timestamp,
        progress=progress,
        origin=origin,
        sync_emitter=sync_emitter,
    )


# ---------------------------------------------------------------------------
# Run management
# ---------------------------------------------------------------------------


def _build_discovery_context(repo_root: Path) -> DiscoveryContext:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._build_discovery_context`. Flagged 🔴 high-risk in
    research.md §Compat (patched at ``test_query_mode_unit.py:751``, reached
    only via intra-seam movers in ``runtime_bridge_io.py``) — every one of
    those intra-seam callers routes back through this delegate via a live
    lookup rather than a bare intra-module call; see the seam module's
    docstring."""
    return _io_seam._build_discovery_context(repo_root)


def _resolve_runtime_template_in_root(root: Path, mission_type: str) -> Path | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._resolve_runtime_template_in_root`."""
    return _io_seam._resolve_runtime_template_in_root(root, mission_type)


def _runtime_template_key(mission_type: str, repo_root: Path) -> str:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._runtime_template_key`."""
    return _io_seam._runtime_template_key(mission_type, repo_root)


def _existing_run_ref(
    mission_slug: str,
    repo_root: Path,
    mission_type: str,
) -> MissionRunRef | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._existing_run_ref`."""
    return _io_seam._existing_run_ref(mission_slug, repo_root, mission_type)


def _start_ephemeral_query_run(
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
) -> tuple[MissionRunRef, Path]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._start_ephemeral_query_run`."""
    return _io_seam._start_ephemeral_query_run(mission_slug, mission_type, repo_root)


def get_or_start_run(
    mission_slug: str,
    repo_root: Path,
    mission_type: str,
    *,
    emitter: Any | None = None,
) -> MissionRunRef:
    """Thin compat delegate — forwards to :func:`runtime_bridge_io.get_or_start_run`.

    Run mapping stored in .kittify/runtime/feature-runs.json:
    { "042-test-feature": { "run_id": "abc", "run_dir": "..." } }
    """
    return _io_seam.get_or_start_run(mission_slug, repo_root, mission_type, emitter=emitter)


# ---------------------------------------------------------------------------
# OperationalContext wiring (FR-017, NFR-004) — bodies live in
# runtime_bridge_io.py (T017); these are native thin compat delegates.
# ---------------------------------------------------------------------------


def _resolve_run_dir_for_mission(repo_root: Path, mission_slug: str) -> Path | None:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._resolve_run_dir_for_mission`."""
    return _io_seam._resolve_run_dir_for_mission(repo_root, mission_slug)


def _resolve_tech_stack_for_profile(repo_root: Path, profile_id: str | None) -> frozenset[str]:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._resolve_tech_stack_for_profile`."""
    return _io_seam._resolve_tech_stack_for_profile(repo_root, profile_id)


def build_operational_context_for_claim(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    actor: str | None,
    active_model: str | None,
    active_role: str | None,
    current_activity: str = "implement",
    active_profile: str | None = None,
) -> OperationalContextT:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io.build_operational_context_for_claim`. See that
    function's docstring for the full OC-builder contract (shared by the two
    claim entry points, ``implement.py`` and ``agent/workflow.py``)."""
    return _io_seam.build_operational_context_for_claim(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        actor=actor,
        active_model=active_model,
        active_role=active_role,
        current_activity=current_activity,
        active_profile=active_profile,
    )


def _build_operational_context_for_decision(
    *,
    agent: str,
    run_ref: MissionRunRef,
    feature_dir: Path,
    repo_root: Path,
    step_id: str | None,
    mission_state: str | None = None,
) -> OperationalContextT:
    """Thin compat delegate — forwards to
    :func:`runtime_bridge_io._build_operational_context_for_decision`."""
    return _io_seam._build_operational_context_for_decision(
        agent=agent,
        run_ref=run_ref,
        feature_dir=feature_dir,
        repo_root=repo_root,
        step_id=step_id,
        mission_state=mission_state,
    )


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
# blocked`` over a ``runtime_bridge_cores.DecisionEnvelope``. This module
# supplies the one genuinely I/O-bearing dependency the pure core needs (the
# step branch's on-disk prompt-file check) and threads the caller-computed
# non-deterministic fields (timestamp/run_id/decision_id) — the core itself
# never stamps them (NFR-003).
# ---------------------------------------------------------------------------


def _prompt_exists(path: str) -> bool:
    """Production ``prompt_exists`` port for :func:`runtime_bridge_cores.step_or_blocked`.

    Mirrors ``Decision.__post_init__``'s own check (``decision.py:129``)
    exactly (``Path(prompt).is_file()``) — the injected predicate and the
    dataclass invariant agree on what "resolves on disk" means.
    """
    return Path(path).is_file()


def _materialize_decision(
    envelope: _cores.DecisionEnvelope,
    guard_failures: list[str] | None = None,
) -> Decision:
    """Thin residual wrapper around :func:`runtime_bridge_cores.step_or_blocked`
    supplying the production ``prompt_exists`` port (FR-011)."""
    return _cores.step_or_blocked(envelope, guard_failures, prompt_exists=_prompt_exists)


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


def _dn_bootstrap(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    effective_root: Path | None = None,
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
    if effective_root is None:
        feature_dir = _resolve_runtime_feature_dir(repo_root, mission_slug)
        primary_metadata_dir: Path | None = _primary_runtime_feature_dir(repo_root, mission_slug)
    else:
        from mission_runtime import MissionArtifactKind, mission_context_for

        mission_context = mission_context_for(
            repo_root,
            mission_slug,
            effective_root=effective_root,
        )
        status_dir = mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir
        primary_metadata_dir = mission_context.artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        feature_dir = status_dir if status_dir.is_dir() else primary_metadata_dir
    now = now_utc_iso()

    if not feature_dir.is_dir():
        return None, _materialize_decision(
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
        return None, _materialize_decision(
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
    # Wrap with DecisionGitLog so decision events are durably committed to
    # the coordination branch (spec-kitty #1546, FR-001–FR-005).
    if effective_root is None:
        emitter_for_engine: Any = _wrap_with_decision_git_log(sync_emitter, mission_slug, repo_root)
    else:
        emitter_for_engine = _wrap_with_decision_git_log(
            sync_emitter,
            mission_slug,
            repo_root,
            effective_root=effective_root,
        )

    # Resolve origin info
    origin: dict[str, Any] = {}
    try:
        from specify_cli.runtime.resolver import resolve_mission as resolve_mission_path

        mission_result = resolve_mission_path(mission_type, repo_root)
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
        run_ref = get_or_start_run(
            mission_slug,
            repo_root,
            mission_type,
            emitter=emitter_for_engine,
        )
    except Exception as exc:
        return None, _materialize_decision(
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
    operational_context = _build_operational_context_for_decision(
        agent=agent,
        run_ref=run_ref,
        feature_dir=feature_dir,
        repo_root=repo_root,
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
        ),
        None,
    )


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
    now = ctx.now
    progress = ctx.progress
    origin = ctx.origin
    run_ref = ctx.run_ref
    current_step_id = ctx.current_step_id

    # WP iteration check: if we're on a WP step and WPs remain, don't advance runtime
    if ctx.result == "success" and current_step_id and _is_wp_iteration_step(current_step_id):
        try:
            should_advance = _should_advance_wp_step(current_step_id, feature_dir, repo_root=repo_root, mission_slug=mission_slug)
        except CanonicalStatusNotFoundError as exc:
            return _materialize_decision(
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
            return _materialize_decision(
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
            return _build_wp_iteration_decision(
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
            )
        except _cores.UnregisteredMissionFamilyError:
            logger.warning(
                "Unregistered mission_family %r reached the CLI guard path; returning a neutral (empty) guard result.",
                mission_type,
            )
            guard_failures = []
        if guard_failures:
            return _build_wp_iteration_decision(
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
    if ctx.result == "success" and current_step_id and not _is_wp_iteration_step(current_step_id) and mission_type == MISSION_TYPE_SOFTWARE_DEV:
        guard_failures = _check_cli_guards(
            current_step_id,
            feature_dir,
            mission_family=mission_type,
            repo_root=repo_root,
        )
        if guard_failures:
            action, wp_id, workspace_path = _state_to_action(
                current_step_id,
                mission_slug,
                feature_dir,
                repo_root,
                mission_type,
            )
            prompt_file: str | None = None
            prompt_error: str | None = None
            if action:
                prompt_file, prompt_error = _build_prompt_or_error(
                    action,
                    feature_dir,
                    mission_slug,
                    wp_id,
                    agent,
                    repo_root,
                    mission_type,
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
            return _materialize_decision(
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
        )
        if action
        else None
    )
    return _materialize_decision(
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
    mission_slug = ctx.mission_slug
    mission_type = ctx.mission_type
    feature_dir = ctx.feature_dir
    repo_root = ctx.repo_root
    now = ctx.now
    progress = ctx.progress
    origin = ctx.origin
    run_ref = ctx.run_ref
    current_step_id = ctx.current_step_id

    if (
        ctx.result == "success"
        and current_step_id
        and _should_dispatch_via_composition(
            mission_type,
            current_step_id,
            run_dir=ctx.run_dir,
            repo_root=repo_root,
        )
    ):
        composed_action = _normalize_action_for_composition(current_step_id)
        # R-005: for custom missions, the active step's ``agent_profile`` is
        # the source of truth for ``profile_hint``. For built-in missions
        # (e.g., ``software-dev``), built-in templates do NOT set
        # ``agent_profile``, so this resolves to ``None`` and the executor's
        # ``_resolve_profile_hint`` falls back to ``_ACTION_PROFILE_DEFAULTS``
        # — preserving byte-identical built-in dispatch behavior (FR-010).
        resolved_profile, runtime_contract = _composition._composition_dispatch_inputs(
            repo_root=repo_root,
            run_dir=ctx.run_dir,
            mission=mission_type,
            step_id=current_step_id,
            action=composed_action,
        )
        composition_failures = _dispatch_via_composition(
            repo_root=repo_root,
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
        )
        if composition_failures:
            return _dn_composition_blocked_decision(ctx, current_step_id, composition_failures)
        # Composition succeeded; advance run state via the
        # composition-specific advancement helper and short-circuit the
        # legacy ``runtime_next_step`` fall-through (FR-001/FR-002). The
        # helper emits the same lane / state events the legacy path emits,
        # through the decision-log-wrapped engine emitter so a
        # ``DecisionInputRequested`` it raises is durably recorded
        # (ADR 2026-09-06-2 (c)); any error from it surfaces through the
        # existing ``Decision`` ``blocked`` shape (EDGE-003) — the legacy
        # DAG dispatch handler is **not** entered as a fallback.
        try:
            return _advance_run_state_after_composition(
                run_ref=run_ref,
                agent=agent,
                mission_slug=mission_slug,
                mission_type=mission_type,
                repo_root=repo_root,
                feature_dir=feature_dir,
                timestamp=now,
                progress=progress,
                origin=origin,
                sync_emitter=ctx.emitter_for_engine,
            )
        except Exception as exc:  # noqa: BLE001 — EDGE-003 contract: any
            # advancement-helper failure must surface as a structured
            # Decision, not as a Python traceback, and MUST NOT silently
            # fall through to the legacy DAG dispatch handler.
            logger.exception(
                "advancement helper failed after composition for %s/%s",
                mission_type,
                composed_action,
            )
            return _materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.blocked,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=(f"Run-state advancement after composition failed for {mission_type}/{composed_action}: {type(exc).__name__}: {exc}"),
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                )
            )

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
    buffer: _BufferingRuntimeEmitter | None,
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
    mission_id = _resolve_mission_id_for_terminus(ctx.feature_dir)
    try:
        if policy_error is not None:
            raise policy_error
        _run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=ctx.mission_slug,
            feature_dir=ctx.feature_dir,
            repo_root=ctx.repo_root,
            block_on_failure=True,
        )
    except Exception as exc:
        # Gate refused. Drop the buffered emit calls (so no
        # MissionRunCompleted ever reaches the real emitter) and
        # restore state.json + truncate run.events.jsonl to pre-call.
        if buffer is not None:
            buffer.discard()
        _dn_rollback_buffered_run_state(ctx.run_dir, pre_state_bytes, pre_events_size)
        return _materialize_decision(
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


def _dn_decision_materialize(ctx: DecideNextContext) -> Decision:
    """Phase 4/4 of ``decide_next_via_runtime`` (FR-010) — advance via the
    runtime planner and materialize the terminal/step/query ``Decision``
    through WP07's Decision-builder. Always returns a ``Decision`` (never
    ``None``): this is the chain's terminal phase.

    Strict retrospective policy remains a pre-completion gate. The default
    post-completion policy is best-effort and must not buffer or roll back
    MissionRunCompleted; it runs after terminal events have flushed.
    """
    policy, _source_map, policy_error = _resolve_retrospective_policy_for_runtime(ctx.repo_root)
    retrospective_enabled = bool(getattr(policy, "enabled", False))
    block_on_retrospective = _retrospective_seam._retrospective_blocks_completion(policy)

    pre_state_bytes: bytes | None = None
    pre_events_size: int | None = None
    # Use the DecisionGitLog-wrapped emitter as the engine's emitter so that
    # decision events are durably committed to the coordination branch.
    engine_emitter: Any = ctx.emitter_for_engine
    buffer: _BufferingRuntimeEmitter | None = None

    if block_on_retrospective:
        captured = _dn_capture_pre_speculative_state(ctx.run_dir)
        if captured is None:
            # If we cannot capture pre-state we cannot guarantee a clean
            # rollback. Surface this as a blocked Decision rather than
            # advancing into a state we cannot retract.
            return _materialize_decision(
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
        buffer = _BufferingRuntimeEmitter()
        engine_emitter = buffer

    # Advance via runtime
    try:
        runtime_decision = runtime_next_step(
            ctx.run_ref,
            agent_id=ctx.agent,
            result=ctx.result,
            emitter=engine_emitter,
        )
    except Exception as exc:
        # Engine raised: discard any buffered events; nothing left to flush.
        if buffer is not None:
            buffer.discard()
        return _materialize_decision(
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
        mission_id = _resolve_mission_id_for_terminus(ctx.feature_dir)
        _run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=ctx.mission_slug,
            feature_dir=ctx.feature_dir,
            repo_root=ctx.repo_root,
            block_on_failure=False,
        )

    return _map_runtime_decision(
        runtime_decision,
        ctx.agent,
        ctx.mission_slug,
        ctx.mission_type,
        ctx.repo_root,
        ctx.feature_dir,
        ctx.now,
        ctx.progress,
        ctx.origin,
    )


#: Reused across both #2947 short-circuit branches (S1192 — repeated literal).
_MERGED_MISSION_DONE_REASON = "All work packages are done"


def _merged_mission_short_circuit(
    *,
    repo_root: Path,
    mission_slug: str,
    agent: str | None,
    now: str,
    terminal_kind: str,
) -> Decision | None:
    """Committed-authority pre-check (#2947, D8/D9/D13/F5) shared by BOTH
    ``next`` entry points, called BEFORE either selects a workspace or starts
    a run.

    Consumes WP01's :func:`committed_authority.mission_terminal_verdict` —
    the PRIMARY-surface authority (never the coordination checkout) — so a
    merged mission is recognized from committed truth instead of a stale/
    artifact-missing coordination workspace fabricating an unstarted run
    (D9). ``mission_type`` is resolved off the same PRIMARY surface
    (:func:`_primary_runtime_feature_dir`) — never via workspace selection.

    ``terminal_kind`` lets the two callers diverge on the ONE dimension D13
    requires: :func:`decide_next_via_runtime` passes ``DecisionKind.terminal``
    (matching issue #2947's ``--result success`` repro, and creating NO run
    since this returns before workspace selection / ``get_or_start_run``);
    :func:`query_current_state` passes ``DecisionKind.query`` (query mode is
    structurally ``kind: query`` only — mirrors the finalized-override
    ``mission_state="done"`` precedent, :func:`_build_finalized_override_
    query_decision`). A ``blocked_conflict`` verdict honors the same mode
    split: advancing mode emits ``kind: blocked`` (an actionable blocked
    decision), while query mode emits ``kind: query`` with
    ``mission_state="blocked"`` — preserving the query-mode ``is_query`` /
    ``kind: query`` invariant and matching the finalized-override ``blocked:``
    precedent (never ``kind: blocked`` from a read-only query).

    F5 invariant: returns ``None`` for verdict ``"none"`` so the caller's
    existing behavior is BYTE-IDENTICAL to today (protects the many
    in-flight query/decide fixtures) — the only two verdicts this function
    ever materializes a ``Decision`` for are ``"terminal"`` and
    ``"blocked_conflict"``.

    #3829 item 1: the ``"none"`` fall-through also covers the
    handle-form errors ``mission_terminal_verdict`` declines on
    (traversal-unsafe / ambiguous handles) — the raw path-guard
    ``ValueError`` those handles used to raise FROM THIS SHORT-CIRCUIT
    pre-empted the caller's own typed classification
    (``resolve_handle_to_read_path`` → ``MissionNotFoundError`` /
    read-path code); declining restores the pre-#3825 error shapes
    byte-for-byte.
    """
    from runtime.next.committed_authority import mission_terminal_verdict

    verdict = mission_terminal_verdict(repo_root, mission_slug)
    if verdict == "none":
        return None

    mission_type = get_mission_type(_primary_runtime_feature_dir(repo_root, mission_slug))
    if verdict == "terminal":
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=terminal_kind,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="done",
                timestamp=now,
                reason=_MERGED_MISSION_DONE_REASON,
            )
        )
    # blocked_conflict — honor the mode: query mode keeps the structural
    # ``kind: query`` invariant (``mission_state="blocked"``, mirroring the
    # finalized-override ``blocked:`` precedent), advancing mode emits an
    # actionable ``kind: blocked``. Field set mirrors the inline blocked
    # emissions; no invented payload shape. The reason carries an operator
    # remediation affordance (#3829 item 2): the fail-closed block is
    # correct, but it previously named no recovery command — an operator
    # seeing ``kind: blocked`` indefinitely had no pointer to the board that
    # shows the straggling WP or to the move-task that resolves it.
    blocked_kind = DecisionKind.query if terminal_kind == DecisionKind.query else DecisionKind.blocked
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=blocked_kind,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state="blocked",
            timestamp=now,
            reason=(
                "Merged mission has committed work packages that are not an "
                "acceptable ending (conflict). Inspect the committed board with "
                f"'spec-kitty agent tasks status --mission {mission_slug}' and "
                "resolve the straggling work package(s) — e.g. "
                f"'spec-kitty agent tasks move-task <wp> --to approved --mission {mission_slug}'."
            ),
        )
    )


def decide_next_via_runtime(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    effective_root: Path | None = None,
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
    merged_short_circuit = _merged_mission_short_circuit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        agent=agent,
        now=now_utc_iso(),
        terminal_kind=DecisionKind.terminal,
    )
    if merged_short_circuit is not None:
        return merged_short_circuit

    if effective_root is None:
        ctx, early_decision = _dn_bootstrap(agent, mission_slug, result, repo_root)
    else:
        ctx, early_decision = _dn_bootstrap(
            agent,
            mission_slug,
            result,
            repo_root,
            effective_root=effective_root,
        )
    if early_decision is not None:
        return early_decision
    assert ctx is not None  # _dn_bootstrap always pairs a ctx with None (or vice versa)

    for phase in (_dn_dependency_gate, _dn_composition_dispatch, _dn_decision_materialize):
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
    effective_root: Path | None = None,
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
                effective_root=effective_root,
            )
            preview = preview_claimable_wp(
                mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK).read_dir,
                status_dir=mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir,
            )
            override_wp_id = preview.wp_id
            if preview.wp_id is None and preview.selection_reason is not None:
                reason = preview.selection_reason
    return _materialize_decision(
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
    return _materialize_decision(
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
    return _materialize_decision(
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
    return _materialize_decision(
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
    effective_root: Path | None = None,
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
    merged_short_circuit = _merged_mission_short_circuit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        agent=agent,
        now=now,
        terminal_kind=DecisionKind.query,
    )
    if merged_short_circuit is not None:
        return merged_short_circuit

    from mission_runtime import ActionContextError, MissionArtifactKind, mission_context_for

    try:
        mission_context = mission_context_for(
            repo_root,
            mission_slug,
            effective_root=effective_root,
        )
        mission_slug = mission_context.mission_slug
    except ActionContextError as exc:
        # FR-001 / C-IC02: pass a typed *read-path* error through VERBATIM. The
        # resolver already produced the precise code (e.g.
        # COORDINATION_BRANCH_DELETED / STATUS_READ_PATH_NOT_FOUND) plus the real
        # read-path remediation; collapsing it into a generic MISSION_NOT_FOUND
        # ("run mission list") points the operator the wrong way (the mission is
        # not missing — its read path is broken; the disease #15). The command
        # layer surfaces ``exc.code`` + checked paths from the typed error.
        # (Earlier this raised ``MissionNotFoundError`` for ALL ActionContextError
        # and mis-attributed the collapse to FR-004 / WP03; that attribution was
        # stale — the next-family collapse is owned by THIS WP.)
        if _is_read_path_error(exc):
            raise
        # A genuinely-missing mission (e.g. FEATURE_CONTEXT_UNRESOLVED — no mission
        # directory at all) is legitimately MISSION_NOT_FOUND (FR-004 / WP03).
        raise MissionNotFoundError(mission_slug) from exc

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
    progress = _compute_wp_progress(task_board.read_dir, status_dir=status_state.read_dir)

    run_ref = _existing_run_ref(mission_slug, repo_root, mission_type)
    ephemeral_run_store: Path | None = None

    # Read current step WITHOUT calling next_step(). When no step has been
    # issued yet, use the planner read-only to compute a truthful preview.
    # The try/finally below guarantees the ephemeral run store is cleaned up
    # on every return path (success, raise, or early exit).
    try:
        try:
            if run_ref is None:
                run_ref, ephemeral_run_store = _start_ephemeral_query_run(
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

        # Query mode never persists the ephemeral run it bootstraps for a
        # not-yet-started mission. Returning that run's id in the JSON would
        # mislead callers into thinking they can issue ``spec-kitty next
        # --mission <slug> --result …`` against it; in reality the run state
        # is wiped in the finally block before the function returns. Only
        # emit ``run_id`` when the run is a real, persisted one.
        emitted_run_id: str | None = None
        if ephemeral_run_store is None:
            emitted_run_id = getattr(run_ref, "run_id", None)

        finalized_override = _finalized_task_board_override_step(
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
                effective_root=effective_root,
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
    finally:
        if ephemeral_run_store is not None:
            shutil.rmtree(ephemeral_run_store, ignore_errors=True)


def answer_decision_via_runtime(
    mission_slug: str,
    decision_id: str,
    answer: str,
    agent: str,
    repo_root: Path,
    *,
    actor_type: str = "human",
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
    run_ref = get_or_start_run(mission_slug, repo_root, mission_type)
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
    answer_emitter: Any = _wrap_with_decision_git_log(sync_emitter, mission_slug, repo_root)
    actor = ActorIdentity(actor_id=agent, actor_type=actor_type)
    runtime_provide_decision_answer(
        run_ref,
        decision_id,
        answer,
        actor,
        emitter=answer_emitter,
    )


# ---------------------------------------------------------------------------
# Internal mapping helpers
# ---------------------------------------------------------------------------


# advancing-next-board-unification-01M3BGQ0 (#4980, #4975) — the single
# board-authority-backed WP-iteration action selector (NFR-002 / CT-7).
#
# Mirrors query mode's ``_build_finalized_override_query_decision`` exactly:
# the same coord-aware ``status_dir`` (resolved via ``mission_context_for``,
# never the bare ``feature_dir``), the same ``_finalized_task_board_
# override_step`` step derivation, and the same per-step WP resolution
# authority (``preview_claimable_wp`` for implement; the canonical
# ``_find_first_wp_by_lane`` for_review reader for review — C-003 forbids
# minting a fifth lane reader). ``_build_wp_iteration_decision`` and
# ``_map_wp_step_decision`` both route through this instead of the bare
# ``_state_to_action(step_id, feature_dir, ...)`` call that #4980/#4975 are
# two faces of (research.md's parallel-authority inventory items #1/#2).
@dataclasses.dataclass(frozen=True)
class _WpBoardAction:
    """Result of the single board-authority WP-iteration action selector.

    Exactly one of three shapes:

    * **dispatch** — ``action``/``wp_id``/``workspace_path`` set,
      ``blocked_reason`` ``None``.
    * **blocked floor** — ``blocked_reason`` set (a CT-4 runnable recovery
      command embedded in backticks), ``action``/``wp_id``/``workspace_path``
      ``None``.
    * **decline** — every field ``None``. The board authority has no
      finalized-board opinion yet (pre-finalize bootstrap, or the board says
      ``accept``/``done`` — that transition is owned by the leave-step
      boolean, not this selector). The caller falls back to
      :func:`_state_to_action` unchanged (FR-006).
    """

    board_step: str | None
    action: str | None
    wp_id: str | None
    workspace_path: str | None
    blocked_reason: str | None


_WP_BOARD_DECLINE = _WpBoardAction(board_step=None, action=None, wp_id=None, workspace_path=None, blocked_reason=None)

#: CT-4's runnable recovery command for the coord-read fail-closed floor
#: (CT-5) — materializing the coordination worktree, never flattening it.
_COORD_UNMATERIALIZED_RECOVERY = "spec-kitty doctor workspaces --fix"


def _inspect_board_recovery_command(mission_slug: str) -> str:
    """CT-4's runnable recovery command for the generic 'inspect the board'
    blocked arms (``no_actionable_wp`` / ``review_in_progress`` / a
    claimable-WP race)."""
    return f"spec-kitty agent tasks status --mission {mission_slug}"


def _wp_blocked_action(board_step: str | None, reason: str) -> _WpBoardAction:
    return _WpBoardAction(board_step=board_step, action=None, wp_id=None, workspace_path=None, blocked_reason=reason)


def _wp_dispatch_action(board_step: str, action: str, wp_id: str, workspace_path: str) -> _WpBoardAction:
    return _WpBoardAction(board_step=board_step, action=action, wp_id=wp_id, workspace_path=workspace_path, blocked_reason=None)


def _resolve_wp_board_implement_action(
    mission_slug: str,
    repo_root: Path,
    task_board_dir: Path,
    status_dir: Path,
) -> _WpBoardAction:
    """CT-3 / FR-003: implement-branch WP resolution, mirroring query mode's
    ``_build_finalized_override_query_decision`` exactly (the same
    ``preview_claimable_wp`` dependency-aware authority, the same coord-aware
    ``status_dir``). A ``None`` claimable WP (e.g. the only planned-lane WP
    is dependency-walled) is a genuine blocked floor here — FR-005 forbids a
    WP-less ``kind=step`` dispatch."""
    from runtime.next.discovery import preview_claimable_wp
    from specify_cli.workspace.context import resolve_workspace_for_wp

    preview = preview_claimable_wp(task_board_dir, status_dir=status_dir)
    if preview.wp_id is None:
        reason = preview.selection_reason or "no claimable work package"
        return _wp_blocked_action(
            "implement",
            f"{reason}. Inspect the board: `{_inspect_board_recovery_command(mission_slug)}`.",
        )
    workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, preview.wp_id).worktree_path)
    return _wp_dispatch_action("implement", "implement", preview.wp_id, workspace_path)


def _resolve_wp_board_review_action(
    mission_slug: str,
    repo_root: Path,
    task_board_dir: Path,
    status_dir: Path,
) -> _WpBoardAction:
    """CT-2 / FR-001: review-branch WP resolution via the canonical
    ``_find_first_wp_by_lane`` for_review reader (C-003 — no fifth lane
    reader is minted)."""
    from specify_cli.workspace.context import resolve_workspace_for_wp

    wp_id = _find_first_wp_by_lane(task_board_dir, "for_review", status_dir=status_dir)
    if wp_id is None:
        # A race between the board's own for_review probe and this re-read
        # — never a WP-less dispatch (FR-005); fall to the blocked floor.
        return _wp_blocked_action(
            "review",
            f"Board reported a reviewable work package but none was found on re-read. Inspect the board: `{_inspect_board_recovery_command(mission_slug)}`.",
        )
    workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, wp_id).worktree_path)
    return _wp_dispatch_action("review", "review", wp_id, workspace_path)


def _resolve_wp_board_action(*, mission_slug: str, repo_root: Path) -> _WpBoardAction:
    """The single board-authority-backed WP-iteration action selector
    (NFR-002 / CT-7) both ``_build_wp_iteration_decision`` and
    ``_map_wp_step_decision`` consult instead of the bare ``_state_to_action``
    WP-iteration branches.

    Resolves the coord-aware ``status_dir``/``task_board_dir`` via
    ``mission_context_for`` exactly as query mode does (never the bare
    ``feature_dir`` the two callers otherwise hold — that is the #4975
    mechanism) and computes its OWN ``progress`` from the resolved
    ``task_board_dir`` (never a caller-supplied, potentially coord-blind
    ``progress`` — the bootstrap-computed ``ctx.progress`` is ``None`` for a
    coord mission because it is read off the coord-aware ``feature_dir``,
    which carries no ``tasks/``).

    NFR-003 (CT-5): an unmaterialized/deleted coordination surface is caught
    here and turned into a *named* blocked reason — never allowed to
    collapse into the generic ``no_actionable_wp`` floor and never
    substituted with an empty-primary read. ``mission_context_for``'s own
    status-surface derivation silently composes a not-yet-materialized coord
    path rather than raising (a pre-existing, documented "sanctioned
    degrade" distinct from the newer fail-closed policy ADR 2026-09-24-2
    introduced for ``resolve_artifact_surface``/``placement_seam.read_dir``)
    — so this selector probes ``placement_seam.read_dir`` first, purely for
    its raise, before trusting ``mission_context_for``'s directories for the
    real board reads. Mirrors the existing ``placement_seam(repo_root,
    mission_slug).read_dir(...)`` pattern this module already uses for
    ``PRIMARY_METADATA`` (see ``_mission_routes_through_coordination``
    above) — no new resolution mechanism, the canonical fail-closed
    authority applied to one more kind.
    """
    from mission_runtime import ActionContextError, MissionArtifactKind, mission_context_for, placement_seam
    from specify_cli.coordination.surface_resolver import (
        CoordinationBranchDeleted,
        CoordinationWorktreeUnmaterialized,
    )

    try:
        placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
        mission_context = mission_context_for(repo_root, mission_slug)
    except (CoordinationWorktreeUnmaterialized, CoordinationBranchDeleted) as exc:
        return _wp_blocked_action(
            None,
            f"Coordination surface for mission {mission_slug!r} is not readable ({exc}). Materialize it: `{_COORD_UNMATERIALIZED_RECOVERY}`.",
        )
    except ActionContextError:
        # Mission context genuinely cannot be resolved -- decline and let the
        # caller's FR-006 fallback (_state_to_action) produce whatever it
        # would have produced pre-fix; bootstrap already succeeded, so this
        # is not expected on a live advancing call.
        return _WP_BOARD_DECLINE

    task_board_dir = mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK).read_dir
    status_dir = mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir
    progress = _compute_wp_progress(task_board_dir, status_dir=status_dir)
    board_step = _finalized_task_board_override_step(task_board_dir, progress, status_dir=status_dir)

    if board_step is None or board_step in ("accept", "done"):
        return _WP_BOARD_DECLINE
    if board_step.startswith("blocked:"):
        sentinel = board_step.split(":", 1)[1]
        return _wp_blocked_action(
            board_step,
            f"No actionable work package ({sentinel.replace('_', ' ')}). Inspect the board: `{_inspect_board_recovery_command(mission_slug)}`.",
        )
    if board_step == "implement":
        return _resolve_wp_board_implement_action(mission_slug, repo_root, task_board_dir, status_dir)
    if board_step == "review":
        return _resolve_wp_board_review_action(mission_slug, repo_root, task_board_dir, status_dir)
    return _WP_BOARD_DECLINE  # forward-compat: an unrecognized board step declines rather than guesses


def _wp_iteration_action_and_state(
    step_id: str,
    mission_slug: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
) -> tuple[str | None, str | None, str | None, str | None, str]:
    """Resolve ``(action, wp_id, workspace_path, blocked_reason,
    mission_state)`` for a WP-iteration step through the single board
    authority (NFR-002 / CT-7), falling back to :func:`_state_to_action`
    only when the board authority has no finalized-board opinion yet
    (FR-006 — bootstrap / pre-finalize behavior preserved byte-for-byte).

    ``blocked_reason`` non-``None`` means the caller MUST emit
    ``kind=blocked`` with this reason instead of a step dispatch (CT-4/CT-5)
    — a board ``blocked:*`` sentinel or a coord-read fail-closed error.

    When the board reports a step different from the stale issued
    ``step_id`` (e.g. board=``implement`` while issued=``review``, the
    #4980 re-dispatch), ``mission_state`` reflects the board's own step —
    matching query mode's ``_build_finalized_override_query_decision``
    (data-model.md's "post-fix required: mission_state = board step").
    """
    board = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo_root)
    if board.blocked_reason is not None:
        return None, None, None, board.blocked_reason, step_id
    if board.action is not None:
        return board.action, board.wp_id, board.workspace_path, None, board.board_step or step_id
    action, wp_id, workspace_path = _state_to_action(step_id, mission_slug, feature_dir, repo_root, mission_type)
    return action, wp_id, workspace_path, None, step_id


def _build_wp_iteration_decision(
    step_id: str,
    agent: str,
    mission_slug: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    timestamp: str,
    progress: dict | None,
    origin: dict,
    run_ref: MissionRunRef,
    guard_failures: list[str] | None = None,
) -> Decision:
    """Build a Decision for WP iteration within a step — routed through the
    single board-authority selector (NFR-002 / CT-7); see
    :func:`_wp_iteration_action_and_state`."""
    action, wp_id, workspace_path, blocked_reason, mission_state = _wp_iteration_action_and_state(
        step_id,
        mission_slug,
        mission_type,
        feature_dir,
        repo_root,
    )

    if blocked_reason is not None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=blocked_reason,
                progress=progress,
                origin=origin,
                run_id=run_ref.run_id,
                step_id=step_id,
            ),
            guard_failures or [],
        )

    if action is None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=f"No action mapped for step '{step_id}'",
                progress=progress,
                origin=origin,
                run_id=run_ref.run_id,
                step_id=step_id,
            ),
            guard_failures or [],
        )

    prompt_file, prompt_error = _build_prompt_or_error(
        action,
        feature_dir,
        mission_slug,
        wp_id,
        agent,
        repo_root,
        mission_type,
    )
    # WP06 (FR-006/FR-013) / WP07 (FR-011): step_or_blocked never issues
    # kind=step with an unresolvable prompt_file; see the analogous note in
    # decide_next_via_runtime for why the shared core's hard-coded
    # "prompt_file_not_resolvable" literal is safe for the
    # resolved-but-vanished-by-construction-time race.
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.step,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=timestamp,
            reason=prompt_error or "no_prompt_template",
            action=action,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=progress,
            origin=origin,
            run_id=run_ref.run_id,
            step_id=step_id,
        ),
        guard_failures or [],
    )


def _build_decision_required_prompt_file(
    decision: NextDecision,
    mission_slug: str,
    repo_root: Path,
    agent: str,
) -> str | None:
    """Best-effort ``decision_required`` prompt build (silently ``None`` on failure).

    Verbatim extraction of ``_map_runtime_decision``'s former inline
    try/except (#2531 WP07/T026 — CC reduction; no behavior change: a failed
    ``build_decision_prompt`` still yields ``prompt_file=None``, same as
    before)."""
    if not decision.question:
        return None
    from runtime.next.prompt_builder import build_decision_prompt

    try:
        _, prompt_path = build_decision_prompt(
            question=decision.question,
            options=decision.options,
            decision_id=decision.decision_id or "unknown",
            mission_slug=mission_slug,
            repo_root=repo_root,
            agent=agent,
        )
        return str(prompt_path)
    except Exception:
        return None


def _map_wp_step_decision(
    *,
    step_id: str,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict | None,
    origin: dict,
    run_id: str | None,
) -> Decision:
    """WP-iteration branch of the ``kind="step"`` mapping (#2531 WP07/T026),
    now routed through the single board-authority selector (NFR-002 / CT-7)
    — see :func:`_wp_iteration_action_and_state`. Reached from the
    DAG-advance path (``_map_runtime_decision`` / ``_dn_decision_
    materialize``) whenever the engine just issued a fresh WP-iteration
    step (#4975: the coord implement-dispatch face)."""
    action, wp_id, workspace_path, blocked_reason, mission_state = _wp_iteration_action_and_state(
        step_id,
        mission_slug,
        mission_type,
        feature_dir,
        repo_root,
    )
    if blocked_reason is not None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=blocked_reason,
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )
    if action is None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=f"No action mapped for WP step '{step_id}'",
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )
    prompt_file, prompt_error = _build_prompt_or_error(
        action,
        feature_dir,
        mission_slug,
        wp_id,
        agent,
        repo_root,
        mission_type,
    )
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.step,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=timestamp,
            reason=prompt_error or "prompt_file_not_resolvable",
            action=action,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=progress,
            origin=origin,
            run_id=run_id,
            step_id=step_id,
        )
    )


def _map_non_wp_step_decision(
    *,
    step_id: str | None,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict | None,
    origin: dict,
    run_id: str | None,
) -> Decision:
    """Non-WP branch of the ``kind="step"`` mapping (#2531 WP07/T026).

    Extracted verbatim from ``_map_runtime_decision``'s former non-WP
    triad — template-resolution via ``_state_to_action`` +
    ``_build_prompt_or_error``, collapsed via ``step_or_blocked``."""
    action, wp_id, workspace_path = _state_to_action(
        step_id or "unknown",
        mission_slug,
        feature_dir,
        repo_root,
        mission_type,
    )
    prompt_file: str | None = None
    prompt_error: str | None = None
    if action or step_id:
        prompt_file, prompt_error = _build_prompt_or_error(
            action or step_id or "unknown",
            feature_dir,
            mission_slug,
            wp_id,
            agent,
            repo_root,
            mission_type,
        )
    else:
        prompt_error = "no action and no step_id; cannot resolve prompt"
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.step,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=step_id or "unknown",
            timestamp=timestamp,
            reason=prompt_error or "no_prompt_template",
            action=action or step_id,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=progress,
            origin=origin,
            run_id=run_id,
            step_id=step_id,
        )
    )


def _map_runtime_decision(
    decision: NextDecision,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict | None,
    origin: dict,
) -> Decision:
    """Convert runtime NextDecision to CLI Decision dataclass.

    Exit-code contract (FR-008):
    - ``kind="terminal"`` → ``DecisionKind.terminal`` → ``next_cmd`` exits 0
    - ``kind="blocked"``  → ``DecisionKind.blocked``  → ``next_cmd`` exits 1
    - ``kind="step"``     → ``DecisionKind.step``     → ``next_cmd`` exits 0

    ``next_cmd.py`` maps the kind to exit code; this function must not change
    the kind semantics. Verified by:
    - ``tests/next/test_next_command_integration.py::TestNextCommandCLI::test_terminal_state_exit_code_zero``
    - ``tests/next/test_next_command_integration.py::TestNextCommandCLI::test_blocked_result_exit_code``

    #2531 WP07/T026: every branch now builds a
    :class:`runtime_bridge_cores.DecisionEnvelope` and materializes it via
    :func:`runtime_bridge_cores.step_or_blocked` (FR-011); the WP-step and
    non-WP-step branches (the former CC-heaviest part of this function) are
    extracted to :func:`_map_wp_step_decision` / :func:`_map_non_wp_step_
    decision` so this dispatcher stays a flat kind-lookup.
    """
    step_id = decision.step_id
    run_id = decision.run_id

    if decision.kind == DecisionKind.terminal:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.terminal,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="done",
                timestamp=timestamp,
                reason=decision.reason or "Mission complete",
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )

    if decision.kind == DecisionKind.blocked:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=step_id or "unknown",
                timestamp=timestamp,
                reason=decision.reason,
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )

    if decision.kind == DecisionKind.decision_required:
        prompt_file = _build_decision_required_prompt_file(decision, mission_slug, repo_root, agent)
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.decision_required,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=step_id or "unknown",
                timestamp=timestamp,
                reason=decision.reason or "Decision required",
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
                decision_id=decision.decision_id,
                input_key=decision.input_key,
                question=decision.question,
                options=decision.options,
                prompt_file=prompt_file,
            )
        )

    # kind == "step"
    if step_id and _is_wp_iteration_step(step_id):
        return _map_wp_step_decision(
            step_id=step_id,
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            repo_root=repo_root,
            feature_dir=feature_dir,
            timestamp=timestamp,
            progress=progress,
            origin=origin,
            run_id=run_id,
        )

    return _map_non_wp_step_decision(
        step_id=step_id,
        agent=agent,
        mission_slug=mission_slug,
        mission_type=mission_type,
        repo_root=repo_root,
        feature_dir=feature_dir,
        timestamp=timestamp,
        progress=progress,
        origin=origin,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Public surface (FR-007 / #2531 WP03). Governs ``from runtime_bridge import *``
# ONLY — it does NOT preserve the ~50 private symbols tests patch (those live
# in the explicit guarded compat re-export block introduced as later WPs
# relocate them; see contracts/compat-surface.md §``__all__``).
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
