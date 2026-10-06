"""Coordination-aware decision-log wrapper for the runtime bridge (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moved this cluster out of
``runtime_bridge.py`` verbatim:

* ``_wrap_with_decision_git_log`` wraps a runtime event emitter in a
  ``DecisionGitLog`` so decision events are committed to the mission's
  decision-log surface (the coordination worktree for a coordination-routed
  topology, the primary or owned checkout otherwise), or refuses with
  ``DecisionGitLogUnavailable`` when a coordination-routed mission cannot get
  durable decision evidence;
* ``_mission_routes_through_coordination`` reads the stored topology that
  decides that routing;
* ``_is_owned_coordination_unavailable`` recognises the typed owned refusal
  an owned caller maps to a ``blocked`` decision.

Callers: the bridge's advance path (``_dn_bootstrap``) and the answer path.
Each calls these names on this module, so a test that steers one patches it
here. ``DecisionGitLogUnavailable`` stays importable from
``runtime.next.runtime_bridge`` as the same class.

Import rule (pinned by ``tests/runtime/test_runtime_bridge_query_seam_layout.py``):
this module imports the identity and io seams, which sit below it, and never
the bridge, the query module, the decision-mapping module or the engine
adapter. ``runtime_bridge_io.resolve_commit_target`` raises
``DecisionGitLogUnavailable`` through a deferred import of this module (a
top-level one would be circular, since this module imports io).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mission_runtime import OwnedCheckout, OwnedRefusalCode, routes_through_coordination
from runtime.next import runtime_bridge_identity as _identity_seam
from runtime.next import runtime_bridge_io as _io_seam
from runtime.next._internal_runtime.events import RuntimeEventEmitter
from specify_cli.core.constants import KITTY_SPECS_DIR

logger = logging.getLogger(__name__)


class DecisionGitLogUnavailable(RuntimeError):
    """Decision audit logging cannot be made durable for a modern mission."""


def _mission_routes_through_coordination(
    mission_slug: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
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
    # Owned: the fact's own mission dir (PRIMARY dir only; no coordination surface consulted).
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA) if owned is None else owned.mission_dir
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
    owned: OwnedCheckout | None = None,
) -> Any:
    """Wrap ``emitter`` with DecisionGitLog for durable decision recording.

    Returns the wrapped emitter.  If construction fails (e.g. import error),
    the original emitter is returned unchanged so mission execution is not
    blocked.
    """
    is_owned_call = owned is not None
    if not is_owned_call:
        coord_routing_topology = _mission_routes_through_coordination(mission_slug, repo_root)
    else:
        coord_routing_topology = _mission_routes_through_coordination(
            mission_slug,
            repo_root,
            owned=owned,
        )
    # Root discipline (T060.4 / NFR-001): a coord-less owned mission's decision
    # events are appended and committed under the OWNED checkout P -- never the
    # repository root checkout R. A coord-routing owned mission keeps its
    # coordination worktree under R/.worktrees (correct by construction).
    anchor_root = owned.owned_root if owned is not None and not coord_routing_topology else repo_root
    try:
        from mission_runtime import MissionArtifactKind, TopologySurface, placement_seam
        from specify_cli.coordination.workspace import CoordinationWorkspaceUnavailable
        from specify_cli.events.decision_log import DecisionGitLog

        if not is_owned_call:
            coordination_branch = _identity_seam._resolve_coordination_branch(mission_slug, repo_root)
            mission_id = _identity_seam._resolve_mission_ulid(mission_slug, repo_root)  # str | None
        else:
            from mission_runtime import mission_context_for
            from specify_cli.mission_metadata import resolve_mission_identity

            mission_context = mission_context_for(
                repo_root,
                mission_slug,
                owned=owned,
                tolerate_unmaterialized_coord=True,  # FR-022: a declared-but-not-yet-created coordination worktree is read/materialised, not refused
            )
            status_target = mission_context.artifact(MissionArtifactKind.STATUS_STATE).commit_target
            if status_target is None:
                # Type-visible form of the former bare ``.commit_target.ref`` read
                # (#2560 move): the same AttributeError, handled by the except arms below.
                raise AttributeError("STATUS_STATE artifact has no commit target")
            coordination_branch = status_target.ref
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
            repo_root=anchor_root,
        )

        # The decision-target topology SHAPE is READ from the WP02 stored topology
        # (FR-004 / SC-001) — never from ``_coord_path.exists()`` (the retired
        # disk-``stat`` ladder, C-004).
        #
        # coord-artifact-single-home-01M3V4BE WP09 (T051, FR-003/FR-003a):
        # the NON-owned coord-routing arm's own materialization ladder
        # (on-disk ``.exists()`` check -> ``CoordinationWorkspace.resolve``)
        # is replaced by the ONE write-location accessor:
        # ``write_dir(DECISION_LOG)`` materializes, seeds, restores, or
        # refuses loudly as the coordination state requires -- the ladder it
        # replaces only materialized an UNMATERIALIZED worktree and was
        # blind to a pre-fix EMPTY surface (the #5519 fork this WP fixes).
        # ``worktree_root`` is taken from ``WriteLocation.surface_root``
        # (never ``.parent.parent`` or a naming-convention guess) and
        # ``mission_dir`` from ``.path``.
        #
        # The OWNED arm resolves through the SAME accessor (owned fact threaded
        # into the seam): ``write_dir`` reads the owned-aware ``meta.json``
        # (falling back to the repository-root declaration), derives and
        # verifies an undeclared coordination branch from the deterministic
        # naming grammar, and materializes through the bounded-retry
        # ``_resolve_owned_coordination_workspace`` helper -- an unavailable
        # registry surfaces as the typed ``ActionContextError``
        # (``OWNED_COORDINATION_WORKSPACE_UNAVAILABLE``) that the handler below
        # re-raises for ``_dn_bootstrap``. No arm composes the Mission dir
        # itself (FR-014: a COORD writer never re-derives a write location).
        if coord_routing_topology:
            location = placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.DECISION_LOG)
            if location.surface is not TopologySurface.COORD:
                # Defense in depth (review cycle 2, "same family" as B1-
                # residual): ``coord_routing_topology`` is True (the STORED
                # topology routes through coordination), so ``write_dir``
                # must never hand back a PRIMARY-surfaced location here --
                # that would silently land a coord-routed Mission's decision
                # log on the primary checkout (the exact #5519-class fork
                # this WP exists to close). A sanctioned write-side PRIMARY
                # answer for a coord-routing topology does not exist
                # (``write_dir`` materializes/seeds/restores or refuses --
                # see its own docstring); reaching this arm means SOME
                # upstream resolver (read_primary_meta's canonicalization,
                # the topology gate, or a future caller) disagreed with
                # ``_mission_routes_through_coordination``'s verdict. Refuse
                # loudly rather than wrap a ``DecisionGitLog`` on the wrong
                # surface.
                raise DecisionGitLogUnavailable(
                    f"write_dir(DECISION_LOG) resolved a PRIMARY surface for mission {mission_slug!r} "
                    "under a coordination-routed topology; refusing to wrap a DecisionGitLog on the "
                    "wrong surface."
                )
            worktree_root = location.surface_root
            mission_dir = location.path
        else:
            # Coord-less topology: decisions land on the primary checkout's
            # current branch (a lane/mission branch); landing == coordination ==
            # target. worktree_root is the repo_root (preserved exactly); the
            # Mission dir is composed the same way ``DecisionGitLog`` used to
            # compose it itself, using the OWNED root for an owned coord-less
            # Mission (C-008, ``anchor_root``).
            worktree_root = worktree_root_candidate
            mission_dir = anchor_root / KITTY_SPECS_DIR / mission_slug

        return DecisionGitLog(
            repo_root=anchor_root,
            worktree_root=worktree_root,
            destination_ref=coordination_branch,
            mission_slug=mission_slug,
            mission_dir=mission_dir,
            inner=emitter,
            mission_id=mission_id,
            target=decision_target,
        )
    except CoordinationWorkspaceUnavailable:
        # #4867 (T062): for an owned caller, let the typed refusal propagate
        # UNWRAPPED — never folded into ``DecisionGitLogUnavailable`` (which
        # carries no ``error_code`` an owned caller could route on).
        # ``_dn_bootstrap`` catches this and maps it to a ``blocked`` Decision
        # (``OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE``).
        if owned is not None:
            raise
        raise DecisionGitLogUnavailable(
            "DecisionGitLog construction failed for declared coordination "
            f"topology mission {mission_slug!r}; refusing to continue "
            "without durable decision evidence."
        ) from None
    except DecisionGitLogUnavailable:
        # Defense-in-depth surface check above already raises the precisely-
        # worded refusal; let it propagate UNWRAPPED rather than falling into
        # the generic ``except Exception`` below, which would re-wrap it in a
        # second, GENERIC ``DecisionGitLogUnavailable`` and discard the
        # specific "resolved a PRIMARY surface" diagnostic.
        raise
    except Exception as exc:
        if owned is not None and _is_owned_coordination_unavailable(exc):
            # WP04's typed ``ActionContextError(OWNED_COORDINATION_WORKSPACE_
            # UNAVAILABLE)`` (an unmaterialized surface read) propagates for
            # ``_dn_bootstrap`` to map to the same typed ``blocked`` Decision.
            raise
        if coord_routing_topology:
            # Review cycle 1 (N2, fold): a non-owned ``write_dir(DECISION_LOG)``
            # refusal such as ``CoordSeedForkRefused`` (``.code ==
            # "COORD_SEED_FORK_REFUSED"``) is intentionally folded into this
            # fail-closed ``DecisionGitLogUnavailable`` rather than propagated
            # (no owned-style typed-code routing exists on this arm) -- but
            # the typed code is still worth an operator's eyes, so it is
            # chained into the message when the cause carries one.
            typed_code = getattr(exc, "code", None) or getattr(exc, "error_code", None)
            code_suffix = f" ({typed_code})" if typed_code else ""
            raise DecisionGitLogUnavailable(
                "DecisionGitLog construction failed for declared coordination "
                f"topology mission {mission_slug!r}{code_suffix}; refusing to "
                "continue without durable decision evidence."
            ) from exc
        logger.warning(
            "DecisionGitLog construction failed for mission %s; falling back to plain emitter.",
            mission_slug,
            exc_info=True,
        )
        return emitter


def _is_owned_coordination_unavailable(exc: BaseException) -> bool:
    """True for the two typed FR-012 / O8 failures: the registry probe's
    :class:`CoordinationWorkspaceUnavailable` and WP04's
    ``ActionContextError`` carrying the same registry code."""
    code = getattr(exc, "error_code", None) or getattr(exc, "code", None)
    return code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value
