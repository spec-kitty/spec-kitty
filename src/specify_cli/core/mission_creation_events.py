"""Creation lifecycle events and the coordination status-surface seed.

Moved from ``mission_creation.py`` (#5634); reshaped by the decision-core and seam
cleanups. ``mission_creation`` re-exports every name defined here. A call to a name
tests patch on ``mission_creation``, or to a function another ``mission_creation*``
module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    WriteLocation,
    placement_seam,
)
from specify_cli.core.mission_creation_decisions import (
    is_coordination_routed,
)
from specify_cli.core.owned_mission import OwnedCreateRoot
from specify_cli.core.mission_creation_errors import MissionCreationError
from specify_cli.core.mission_creation_identity import _Purpose
from specify_cli.core.mission_creation_meta import _META_KEY_CREATED_AT, _META_KEY_MISSION_TYPE, _MetaBuild
from specify_cli.core.mission_creation_rollback import CreateRollbackJournal, _CoordCreateRollbackContext

logger = logging.getLogger("specify_cli.core.mission_creation")


def _emit_create_events(
    *,
    feature_dir: Path,
    mission_slug_formatted: str,
    meta: dict[str, Any],
    planning_branch: str,
    resolved_root: Path,
    write_root: Path,
    purpose: _Purpose,
    normalized_friendly_name: str,
    spec_file: Path,
    lifecycle_root: Path | None = None,
    status_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Emit ``MissionCreated`` then ``SpecifyStarted`` to the local canonical log.

    ``lifecycle_root`` (WP13 item 6, out-of-map): the owned create root's
    ``repository_root`` when the create is owned, ``None`` otherwise. Passed as
    ``repo_root=`` to both emitters so the lifecycle log is written against the
    fact's repository root instead of re-deriving R from the owned checkout's
    path (``get_main_repo_root`` walk) after the claim was validated.

    ``status_dir`` (T031, coord-artifact-single-home-01M3V4BE): the directory
    ``status.events.jsonl`` is read from/written to. Defaults to
    ``feature_dir`` (every PRIMARY-partition caller: ``lanes`` /
    ``single_branch``, and ``spec.md``'s own relative-path computation below,
    which always uses ``write_root``/``spec_file`` -- never the status
    location). A coordination-routed create passes the coordination Mission
    dir here instead, so the creation events land on the coordination
    surface from birth (D6) while ``feature_dir`` keeps naming the PRIMARY
    scaffold directory for every other purpose.
    """
    from specify_cli.core import mission_creation as _mc

    status_dir = status_dir if status_dir is not None else feature_dir
    try:
        from specify_cli.identity.project import load_identity
        from specify_cli.status import (
            MISSION_CREATED,
            _resolve_local_actor,
            emit_mission_created_local,
            read_lifecycle_events,
        )

        _identity = load_identity(resolved_root / ".kittify" / "config.yaml")
        creation_actor = _resolve_local_actor()
        expected_created_payload = _mc.build_mission_created_payload(
            mission_slug=mission_slug_formatted,
            mission_id=meta.get("mission_id"),
            mission_number=None,
            mission_type=str(meta.get(_META_KEY_MISSION_TYPE) or "software-dev"),
            target_branch=planning_branch,
            wp_count=0,
            friendly_name=normalized_friendly_name,
            purpose_tldr=purpose.tldr,
            purpose_context=purpose.context,
            created_at=str(meta[_META_KEY_CREATED_AT]) if meta.get(_META_KEY_CREATED_AT) else None,
            actor=creation_actor,
        )
        created_event = emit_mission_created_local(
            status_dir,
            mission_slug=mission_slug_formatted,
            mission_id=meta.get("mission_id"),
            mission_number=None,
            mission_type=str(meta.get(_META_KEY_MISSION_TYPE) or "software-dev"),
            target_branch=planning_branch,
            wp_count=0,
            project_uuid=str(_identity.project_uuid) if _identity.project_uuid else None,
            project_slug=_identity.project_slug,
            friendly_name=normalized_friendly_name,
            purpose_tldr=purpose.tldr,
            purpose_context=purpose.context,
            created_at=str(meta[_META_KEY_CREATED_AT]) if meta.get(_META_KEY_CREATED_AT) else None,
            actor=creation_actor,
            fanout=False,
            repo_root=lifecycle_root,
        )
        created_events = [event for event in read_lifecycle_events(status_dir / "status.events.jsonl") if event.get("event_type") == MISSION_CREATED]
        if len(created_events) != 1:
            raise MissionCreationError(f"expected exactly one persisted MissionCreated event, found {len(created_events)}")
        persisted_created = created_events[0]
        if (
            persisted_created.get("aggregate_id") != meta.get("mission_id")
            or persisted_created.get("aggregate_type") != "Mission"
            or persisted_created.get("payload") != expected_created_payload
        ):
            raise MissionCreationError("persisted MissionCreated event does not match the canonical creation snapshot")
    except Exception as _local_evt_exc:  # noqa: BLE001
        raise MissionCreationError(
            "Local canonical MissionCreated persistence failed for "
            f"{mission_slug_formatted!r}: {_local_evt_exc}. The partial scaffold "
            "is retained for explicit resume-probe diagnosis; do not retry create "
            "until it is repaired or removed."
        ) from _local_evt_exc

    # Mission creation immediately scaffolds ``spec.md`` and opens the specify
    # phase. Record ``SpecifyStarted`` against the canonical local log so that
    # TeamSpace replay can show "currently specifying" before the agent
    # commits substantive spec content (which is where ``setup-plan`` later
    # emits ``SpecifyCompleted``). Without this event the canonical lifecycle
    # stream skips straight from ``MissionCreated`` to ``SpecifyCompleted``,
    # leaving the specify-phase entry point invisible to dashboards and
    # TeamSpace -- see issue #1067.
    phase_event: dict[str, Any] | None = None
    try:
        from specify_cli.status import (
            SPECIFY_STARTED,
            emit_artifact_phase_local,
        )

        phase_event = emit_artifact_phase_local(
            status_dir,
            event_type=SPECIFY_STARTED,
            mission_slug=mission_slug_formatted,
            actor="spec-kitty mission create",
            artifact_path=(str(spec_file.relative_to(write_root)) if spec_file.is_relative_to(write_root) else "spec.md"),
            repo_root=lifecycle_root,
        )
    except Exception as _phase_evt_exc:  # noqa: BLE001
        logger.debug(
            "Local SpecifyStarted persistence skipped for %s: %s",
            mission_slug_formatted,
            _phase_evt_exc,
        )

    return created_event, phase_event


def _commit_coord_create_events(
    resolved_root: Path,
    mission_slug_formatted: str,
    mission_id: str,
    status_dir: Path,
) -> None:
    """Commit the just-emitted creation events onto the coordination branch (T031/D6/D4).

    Runs UNCONDITIONALLY for every coordination-routed create, even when the
    target scaffold commit itself is a disclosed bootstrap skip (T032,
    FR-002a) -- the coordination surface must carry ``MissionCreated`` +
    ``SpecifyStarted`` from birth regardless of what happens to the target
    branch. Raises (never silently swallows) on anything but a genuine
    commit or a benign already-committed no-op, so the outer failure-atomic
    wrapper's rollback (:func:`_rollback_coordination_surface`) runs.

    Carries the ONE shared seed-marker trailer (``COORD_SEED_TRAILER``, D4):
    this is one of the two commit kinds research decision D4 names as
    trailer-bearing (the other is a pre-fix Mission's carry-over seed commit,
    owned by ``coord_seed.py``), so a coordination branch this create minted
    is post-fix from birth and is never later mistaken for one needing the
    pre-fix carry-over seed.
    """
    from specify_cli.coordination.commit_outcome import STATUS_COMMITTED, STATUS_UNCHANGED
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.coordination.coord_seed import COORD_SEED_TRAILER
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy.resolve_for_mission(resolved_root, mission_slug_formatted)
    message = f"chore({mission_slug_formatted}): record mission creation\n\n{COORD_SEED_TRAILER}: {mission_id}"
    result = commit_for_mission(
        resolved_root,
        mission_slug_formatted,
        files=(status_dir / "status.events.jsonl",),
        message=message,
        policy=policy,
        kind=MissionArtifactKind.STATUS_STATE,
    )
    if result.status not in (STATUS_COMMITTED, STATUS_UNCHANGED):
        raise MissionCreationError(
            f"Failed to commit mission-creation events onto the coordination branch "
            f"for {mission_slug_formatted!r}: status={result.status!r} diagnostic={result.diagnostic!r}"
        )


@dataclass(frozen=True, slots=True)
class _CoordCreateSeed:
    """Where T031's create-time coordination seed landed, or that it did not run."""

    status_dir: Path | None
    rollback_ctx: _CoordCreateRollbackContext | None


def _seed_coord_surface_for_create(
    *,
    resolved_root: Path,
    mission_slug_formatted: str,
    mid8: str,
    topology: MissionTopology,
    meta_build: _MetaBuild,
    owned: OwnedCreateRoot | None,
    rollback_journal: CreateRollbackJournal | None,
) -> _CoordCreateSeed:
    """T031 (D6): materialize + seed the coordination surface for a coordination-routed create.

    Runs ONLY for ``COORD`` / ``LANES_WITH_COORD`` -- ``lanes`` /
    ``single_branch`` return ``_CoordCreateSeed(None, None)`` unchanged
    (C-008). Two further guards keep this a no-op without crashing:

    * ``coordination_branch_skipped_reason`` is set -- ``ensure_coordination_branch``
      declined to mint a real branch (the target does not resolve to a ref;
      synthetic/test contexts). There is no coordination branch to seed.
    * ``owned`` is not ``None`` -- an owned create's ``OwnedCreateMission`` is
      not the ``mission_runtime.OwnedCheckout`` :func:`placement_seam` / the
      coordination write-location accessor require, so an owned
      coordination-routed create (a SUPPORTED path, FR-022's
      ``TestFr022CoordinationTwin`` ratchet -- review cycle 2, B5' ruling
      reversed) never seeds the coordination surface. Its ``MissionCreated``
      / ``SpecifyStarted`` events land on ``feature_dir`` in the owned
      checkout instead (``_emit_create_events``'s own ``status_dir``
      default), and ``_scaffold_mission_dir`` / ``_build_create_result``
      both ALSO gate their own coordination-routed branches on ``owned is
      None`` so that log is scaffolded AND committed in the owned checkout
      exactly as at base (``e7b085d26c``). This is a named residual
      (INV-COORD-HOME): an owned coordination create's status log lives in
      its own PRIMARY dir, never the coordination surface itself --
      follow-up tracked separately, not fixed here.

    ``rollback_journal`` (review cycle 2 B2, HIGH): the context is
    recorded in this journal IMMEDIATELY after it is built, BEFORE
    :meth:`~mission_runtime.PlacementSeam.write_dir` is called below.
    ``write_dir`` can itself raise AFTER it has already materialized the
    coordination worktree and/or run the pre-fix seed (a seed failure,
    ``STATUS_LOCK_HELD``, a git-probe failure) -- appending only once this
    function RETURNS successfully would lose the rollback context for
    exactly the half-built-coordination-surface failure T032/US1.5 exists to
    prevent (the minted branch is then left orphaned: the generic rollback's
    ``git branch -D`` fails because the branch is still checked out in the
    worktree).
    """
    from specify_cli.missions._create import topology_mints_coordination_branch

    if not topology_mints_coordination_branch(topology):
        return _CoordCreateSeed(status_dir=None, rollback_ctx=None)
    coordination_branch = meta_build.meta.get("coordination_branch")
    if not isinstance(coordination_branch, str) or meta_build.coordination_branch_skipped_reason is not None:
        return _CoordCreateSeed(status_dir=None, rollback_ctx=None)
    rollback_ctx = _CoordCreateRollbackContext(
        repo_root=resolved_root,
        mission_slug_formatted=mission_slug_formatted,
        mid8=mid8,
        coordination_branch=coordination_branch,
        coordination_branch_created=meta_build.coordination_branch_created,
        pre_seed_coord_tip=meta_build.coordination_branch_pre_seed_tip,
    )
    if rollback_journal is not None:
        rollback_journal.record_coord(rollback_ctx)
    if not is_coordination_routed(mints_coordination=topology_mints_coordination_branch(topology), owned=owned is not None):
        return _CoordCreateSeed(status_dir=None, rollback_ctx=rollback_ctx)
    location: WriteLocation = placement_seam(resolved_root, mission_slug_formatted, owned=None).write_dir(MissionArtifactKind.STATUS_STATE)
    return _CoordCreateSeed(status_dir=location.path, rollback_ctx=rollback_ctx)
