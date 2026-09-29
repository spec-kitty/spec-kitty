"""Done/approved bookkeeping for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-08 / WP08.

Done/approved transition emission, the canonical / target-branch done asserts,
the resume reconcile, and the per-WP recording loop moved out of the command
shim. ``_mark_wp_merged_done`` (CC22) and ``_assert_merged_wps_done_on_target``
(CC16) were decomposed into focused helpers (each <= 15 CC, FR-005) preserving
the PLANNED-fallback / force-done / dedup branching exactly. ``_mark_wp_merged_done``
is consumed by ``orchestrator_api/commands.py`` and is re-exported from the shim
(FR-006). One-way import: this module never imports the command shim.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from specify_cli.cli.console import console
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import run_command
from specify_cli.consolidation._constants import _STATUS_EVENTS_FILENAME, logger
from specify_cli.consolidation.git_probes import path_is_under_worktrees
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.status_lanes import has_operator_provenance, is_acceptable_ending
from mission_runtime import MissionArtifactKind, placement_seam, resolve_placement_only

if TYPE_CHECKING:
    from specify_cli.status import DoneEvidence, EventStream, Lane

# Lanes treated as "pre-approved" for the approved-replay emission.
_PRE_APPROVED_LANE_VALUES = frozenset({"planned", "claimed", "in_progress", "for_review"})

_CANCELED_LANE_VALUE = "canceled"


def acceptably_canceled_wp_ids(repo_root: Path, mission_slug: str) -> set[str]:
    """WP IDs at an acceptable *canceled* ending on the COORD status surface.

    The single merge-side authority (FR-004 / FR-009) for excluding canceled WPs
    from BOTH per-WP done/review derivations — ``executor.py``'s ``all_wp_ids``
    (feeding the review-artifact consistency gate, the evidence gate, the
    canonical-history guard, and ``wp_order``) and the independent per-lane loop
    in :func:`_record_merged_wps_done_for_merge`.

    Reduces the coordination status surface once and returns the WP IDs whose
    canonical lane is ``canceled`` with operator-authored provenance — an
    acceptable mission ending per
    :func:`~specify_cli.status_lanes.is_acceptable_ending` that carries no review
    artifact and is never ``done``, so it must NOT be driven through the invalid
    ``canceled -> done`` bookkeeping. A canceled WP WITHOUT operator provenance is
    deliberately NOT returned: it is not an acceptable ending and must still fail
    the merge loudly (directive 044 — the predicate is the sole authority; this
    reader never redefines acceptability). Returns an empty set when the coord
    event log is absent or unreadable — there is then no canceled WP to exclude,
    and the downstream done-state assertions stay authoritative.
    """
    from specify_cli.status import read_events, reduce
    from specify_cli.status import StoreError

    try:
        surface_path = resolve_status_surface(repo_root, mission_slug)
        snapshot = reduce(read_events(surface_path.parent))
    except (FileNotFoundError, StoreError):
        # Fail-open: an unresolvable/absent/corrupt coord surface yields no
        # canceled WP to exclude. The downstream ``_assert_merged_wps_reached_done``
        # (and the review-artifact/evidence gates) remain the authoritative
        # check and will surface a genuinely-missing surface loudly there.
        return set()

    excluded: set[str] = set()
    for wp_id, wp_snapshot in snapshot.work_packages.items():
        lane = str(wp_snapshot.get("lane", "")) if isinstance(wp_snapshot, dict) else ""
        if lane != _CANCELED_LANE_VALUE:
            continue
        provenance = has_operator_provenance(
            wp_snapshot if isinstance(wp_snapshot, dict) else None
        )
        if is_acceptable_ending(lane, has_provenance=provenance):
            excluded.add(wp_id)
    return excluded


def _resolve_merge_actor(repo_root: Path) -> str:
    """Resolve the actor identity for merge-time audit records.

    Priority: SPEC_KITTY_AGENT env var -> git config user.name ->
    GIT_AUTHOR_NAME -> USER/USERNAME. Falls back to ``<unknown>`` only if
    every source is empty, which should not happen in a properly
    configured environment. This mirrors the resolver pattern used by
    _merge_actor in scripts/tasks/tasks_cli.py so override audit records
    carry a real identity instead of <unknown>.
    """
    agent_env = os.environ.get("SPEC_KITTY_AGENT")
    if agent_env and agent_env.strip():
        return agent_env.strip()
    try:
        ret, out, _err = run_command(["git", "config", "user.name"], capture=True, cwd=repo_root)
        if ret == 0 and out and out.strip():
            return str(out).strip()
    except Exception:  # noqa: BLE001, S110 — actor resolution must never break merge
        pass
    # Final-tier fallback: environment username. Comment preserved deliberately
    # because reviewers ask why this exists — see Fix 2 / FR-008 post-merge follow-up.
    return (
        os.environ.get("GIT_AUTHOR_NAME")
        or os.environ.get("USER")
        or os.environ.get("USERNAME")
        or "<unknown>"
    )


def _has_transition_to(
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    to_lane: str,
    repo_root: Path,
) -> bool:
    """Check whether the event log already contains a transition for *wp_id* to *to_lane*.

    This dedup guard prevents duplicate events when ``_mark_wp_merged_done`` is
    called again on retry/resume.
    """
    from specify_cli.coordination.status_transition import has_transition_to_transactional

    return bool(
        has_transition_to_transactional(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane=to_lane,
            repo_root=repo_root,
        )
    )


def _resolve_snapshot_done_evidence(
    event_stream: EventStream,
    wp_id: str,
) -> DoneEvidence | None:
    """Build DoneEvidence from the reduced-snapshot ``review`` slot, else None.

    IC-04 / FR-006 / D-05: the event-sourced replacement for the deleted
    frontmatter done-evidence synthesis. The reviewer identity comes from the
    reduced snapshot's ``review.actor`` (the backfill seeds the historical
    approval there) — never the frontmatter reviewer field. Consumes the shared
    review-slot reader (``status.resolve_snapshot_review``) so the merge gate and
    the CLI interpret the slot identically (D-14). A WP with no ``review`` slot —
    or a slot carrying an empty ``actor`` — yields ``None`` (treated as absent),
    so the caller falls through to the lane-approved evidence.
    """
    from specify_cli.status import (
        APPROVED,
        DoneEvidence,
        ReviewApproval,
        resolve_event_stream_review,
    )

    override = resolve_event_stream_review(event_stream, wp_id)
    if override is None:
        return None
    reviewer = override.actor.strip()
    if not reviewer:
        return None
    return DoneEvidence(
        review=ReviewApproval(
            reviewer=reviewer,
            verdict=APPROVED,
            reference=f"snapshot-review:{wp_id}",
        )
    )


def _resolve_wp_path(primary_feature_dir: Path, wp_id: str) -> Path | None:
    """Return the first ``tasks/<wp_id>*.md`` path, or None when absent."""
    for candidate in sorted((primary_feature_dir / "tasks").glob(f"{wp_id}*.md")):
        if candidate.exists():
            return candidate
    return None


def _resolve_lane_with_planned_fallback(
    *,
    coord_lane: Lane,
    primary_feature_dir: Path,
    wp_id: str,
) -> tuple[Lane, bool]:
    """Resolve the effective lane, falling back to the primary checkout on PLANNED.

    When the coordination branch has no events for this WP (returns PLANNED),
    read the primary checkout's event log. WP lifecycle events written to the
    lane worktree and squash-merged into main without passing through the
    coordination branch surface as PLANNED on the coord side. Returns
    ``(lane, force_done)`` where ``force_done`` is True when the fallback found
    a usable primary lane (so the state machine accepts the done jump).
    """
    from specify_cli.status import Lane as _Lane

    if coord_lane != _Lane.PLANNED:
        return coord_lane, False

    from specify_cli.status import CanonicalStatusNotFoundError
    from specify_cli.status import get_wp_lane as _get_wp_lane
    from specify_cli.status import resolve_lane_alias as _resolve_lane_alias

    try:
        primary_raw = _get_wp_lane(primary_feature_dir, wp_id)
    except CanonicalStatusNotFoundError:
        primary_raw = _Lane.UNINITIALIZED

    # #2675/WP05: ``get_wp_lane`` always returns a real ``Lane`` member (never a
    # bare, unparseable string) — the absent-log fallback above now assigns
    # ``Lane.UNINITIALIZED`` instead of the pre-WP05 raw ``"uninitialized"``
    # string. ``Lane(resolve_lane_alias(...))`` therefore can no longer raise
    # ``ValueError`` for this input; the pre-WP05 ``except ValueError`` fallback
    # is expressed explicitly below instead of relying on a now-dead branch.
    lane = _Lane(_resolve_lane_alias(str(primary_raw)))
    if lane == _Lane.UNINITIALIZED:
        # The primary surface has no usable lifecycle state for this WP either
        # (unseeded sentinel) — preserve the exact pre-WP05 contract: do NOT
        # force the done jump.
        return coord_lane, False

    # The coord has no events for this WP; force the done transition so
    # the state machine doesn't reject it as an invalid jump from PLANNED.
    return lane, True


def _emit_approved_replay_if_needed(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    target_branch: str,
    repo_root: Path,
    lane: Lane,
    coord_lane: Lane,
    force_done: bool,
    evidence: DoneEvidence,
) -> tuple[Lane, bool] | None:
    """Emit the intermediate ``approved`` transition for pre-approved lanes.

    Returns the updated ``(lane, force_done)`` when a replay applied, the same
    tuple when dedup skipped the emit, or ``None`` when the emit failed (caller
    must abort the done emission). Preserves the original branching exactly.
    """
    from specify_cli.status import Lane as _Lane
    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status import TransitionError, TransitionRequest

    needs_approved_replay = (
        coord_lane == _Lane.PLANNED and lane == _Lane.APPROVED and force_done
    )
    in_pre_approved = lane.value in _PRE_APPROVED_LANE_VALUES
    if not ((in_pre_approved or needs_approved_replay) and evidence is not None):
        return lane, force_done

    if _has_transition_to(feature_dir, mission_slug, wp_id, "approved", repo_root):
        logger.debug("Dedup: %s already has 'approved' transition, skipping emit", wp_id)
    else:
        try:
            emit_status_transition_transactional(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    to_lane="approved",
                    actor="merge",
                    reason=f"Recorded prior review approval for merged {wp_id}",
                    evidence=evidence.to_dict(),
                    workspace_context=f"merge:{repo_root}",
                    repo_root=repo_root,
                    policy_metadata={
                        "merge_phase": "lane_integrated",
                        "target_branch": target_branch,
                    },
                ),
                ensure_sync_daemon=False,
            )
        except TransitionError as exc:
            console.print(f"[yellow]Warning:[/yellow] Failed to mark {wp_id} approved before done: {exc}")
            return None
    return _Lane.APPROVED, False


def _mark_wp_merged_done(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    target_branch: str,
) -> None:
    """Record merge-complete state for a merged WP using canonical status events.

    Includes event-log dedup: if the target transition already exists in the log
    the emission is skipped so that retries are idempotent.
    """
    from specify_cli.status import Lane as _Lane

    # FR-003 (#2185): the WP markdown lives under ``tasks/`` (WORK_PACKAGE_TASK,
    # PRIMARY-partition) on the PRIMARY checkout post-#2106. Route by kind so the WP
    # file lookup resolves the durable PRIMARY home regardless of topology — the
    # kind-aware seam folds PRIMARY-partition reads onto the topology-blind primary
    # dir, so it does NOT route to the STATUS-only ``-coord`` husk (which carries
    # status files but no task markdown). This is the canonical seam the rest of the
    # planning reads use; the historical "do not use the read-path resolver" comment
    # predated the kind-aware split and was self-contradicting. The status-transactional
    # legs below keep this same meta-bearing PRIMARY dir (they resolve/commit to the
    # coordination branch internally — they must NOT be handed the coord worktree dir).
    primary_feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    wp_path = _resolve_wp_path(primary_feature_dir, wp_id)
    if wp_path is None:
        console.print(f"[yellow]Warning:[/yellow] Could not locate WP file for {wp_id}; skipping merge-complete status update.")
        return

    # Transactional status helpers receive the primary meta-bearing feature
    # dir so they can resolve/commit to the coordination branch. Passing the
    # coord worktree dir loses meta in status-only coord worktrees and degrades
    # writes into local, non-durable file edits. The annotation-aware
    # transactional read below performs the authoritative status validation
    # without requiring a coordination worktree to be materialized.
    feature_dir = primary_feature_dir
    from specify_cli.coordination.status_transition import (
        emit_status_transition_transactional,
        read_event_stream_transactional,
        read_current_wp_state_transactional,
    )
    from specify_cli.status import (
        APPROVED,
        DoneEvidence,
        ReviewApproval,
        TransitionError,
        TransitionRequest,
        reduce,
    )

    event_stream = read_event_stream_transactional(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        repo_root=repo_root,
    )
    wp_snapshot = reduce(
        event_stream.transitions,
        event_stream.annotations,
    ).work_packages.get(wp_id, {})

    lane = read_current_wp_state_transactional(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        repo_root=repo_root,
    ).lane
    coord_lane = lane
    # Dedup guard (retry idempotence): the WP's CURRENT lane is already ``done``.
    # Deliberately not "a ``done`` exists anywhere in its history" (#5046 landing,
    # FR-011 recovery; Refs #4967 (partial)): a WP recorded ``done`` by a
    # consolidation whose gate then FAILed, and afterwards reopened for governed
    # rework, must be recorded ``done`` again once its rework is re-merged.
    if lane == _Lane.DONE:
        return

    lane, _force_done = _resolve_lane_with_planned_fallback(
        coord_lane=coord_lane,
        primary_feature_dir=primary_feature_dir,
        wp_id=wp_id,
    )

    # IC-04 / FR-006 / C-001 / D-05: the snapshot ``review`` slot is the
    # event-sourced done-evidence source (the frontmatter synthesis is deleted).
    # A WP with no review slot falls through to the lane-derived fallback below —
    # which also uses the resolved event-stream agent, never frontmatter.
    evidence = _resolve_snapshot_done_evidence(event_stream, wp_id)
    if evidence is None:
        if lane == _Lane.APPROVED:
            runtime_agent = wp_snapshot.get("agent")
            reviewer = runtime_agent.strip() if isinstance(runtime_agent, str) else "unknown"
            evidence = DoneEvidence(
                review=ReviewApproval(
                    reviewer=reviewer or "unknown",
                    verdict=APPROVED,
                    reference=f"lane-approved:{wp_id}",
                )
            )
        else:
            console.print(f"[yellow]Warning:[/yellow] {wp_id} has no recorded approval metadata; skipping automatic move to done after merge.")
            return

    replay_result = _emit_approved_replay_if_needed(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        target_branch=target_branch,
        repo_root=repo_root,
        lane=lane,
        coord_lane=coord_lane,
        force_done=_force_done,
        evidence=evidence,
    )
    if replay_result is None:
        return
    lane, _force_done = replay_result

    if lane != _Lane.APPROVED:
        console.print(f"[yellow]Warning:[/yellow] {wp_id} is in lane '{lane.value}', not approved; skipping automatic move to done after merge.")
        return

    try:
        # WP07 / FR-008: tag the done transition with merge_phase=lane_integrated
        # so consumers can audit which WPs were integrated via the two-stage
        # merge pipeline (lane -> coordination branch -> target branch) and
        # which target branch they landed on. The transition is emitted once
        # per WP after Stage 1 (lane->coord) completes and before Stage 2
        # (coord->target) runs the post-merge bookkeeping.
        emit_status_transition_transactional(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                to_lane="done",
                actor="merge",
                reason=f"Merged {wp_id} into {target_branch}",
                evidence=evidence.to_dict(),
                workspace_context=f"merge:{repo_root}",
                repo_root=repo_root,
                force=_force_done,
                policy_metadata={
                    "merge_phase": "lane_integrated",
                    "target_branch": target_branch,
                },
            ),
            ensure_sync_daemon=False,
        )
    except TransitionError as exc:
        console.print(f"[yellow]Warning:[/yellow] Failed to mark {wp_id} done after merge: {exc}")


def _assert_merged_wps_reached_done(
    repo_root: Path,
    mission_slug: str,
    wp_ids: list[str],
) -> None:
    """Fail the merge if merged WPs did not reach ``done`` in the event log."""
    from specify_cli.status import (
        CanonicalStatusNotFoundError,
        Lane,
        StoreError,
        get_wp_lane,
        resolve_lane_alias,
    )

    # Resolve the canonical status surface so reads are on the same side as
    # the writes in _mark_wp_merged_done (fixes coordination-branch divergence).
    surface_path = resolve_status_surface(repo_root, mission_slug)
    feature_dir = surface_path.parent

    try:
        incomplete: list[str] = []
        for wp_id in wp_ids:
            raw = get_wp_lane(feature_dir, wp_id)
            # #2675/WP05: ``get_wp_lane`` always returns a real ``Lane`` member,
            # so ``Lane(resolve_lane_alias(raw))`` can no longer raise
            # ``ValueError`` here (the pre-WP05 unrecognized-sentinel fallback
            # is now genuinely unreachable and has been removed rather than
            # left as a dead handler). ``Lane.UNINITIALIZED`` (unseeded
            # sentinel) still compares unequal to ``Lane.DONE`` below, so the
            # not-done treatment is preserved via the explicit equality check.
            lane = Lane(resolve_lane_alias(raw))
            if lane != Lane.DONE:
                incomplete.append(f"{wp_id}={lane.value}")
    except CanonicalStatusNotFoundError as exc:
        # The canonical event log is absent (e.g. a legacy mission that never ran
        # finalize-tasks, or a surface that diverged from the mark-done writes).
        # Code integration already succeeded; surface this as a deliberate,
        # actionable validation failure rather than an uncaught crash.
        console.print(
            "[red]Error:[/red] Post-merge status validation could not run: "
            f"no canonical event log at {surface_path}. Code was integrated, but "
            "WP done-state cannot be confirmed. Run "
            f"'spec-kitty agent mission finalize-tasks --mission {mission_slug}' "
            "to bootstrap the event log, then re-run the merge."
        )
        raise typer.Exit(1) from exc
    except StoreError as exc:
        console.print(
            "[red]Error:[/red] Post-merge status validation failed: "
            f"could not read {surface_path} ({exc})"
        )
        raise typer.Exit(1) from exc

    if incomplete:
        console.print(
            "[red]Error:[/red] Post-merge status validation failed: "
            "merged WPs did not reach done in the canonical event log."
        )
        console.print(f"  Offending WPs: {', '.join(incomplete)}")
        raise typer.Exit(1)


def _resolve_in_branch_status_events_path(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
) -> Path:
    """Return the IN-BRANCH tracked ``status.events.jsonl`` relative path.

    FR-038 (#1772 Bug 4): post-merge target validation reads ``git show
    <branch>:<rel>``, which only resolves TRACKED paths. A coord-aware
    ``feature_dir`` under ``.worktrees/<m>-coord/…`` is never tracked, so always
    resolve the canonical ``kitty-specs/<m>/status.events.jsonl`` path.
    """
    rel_events_path: Path
    try:
        rel_events_path = feature_dir.relative_to(repo_root) / _STATUS_EVENTS_FILENAME
    except ValueError:
        rel_events_path = Path(KITTY_SPECS_DIR) / mission_slug / _STATUS_EVENTS_FILENAME
    if path_is_under_worktrees(rel_events_path):
        rel_events_path = Path(KITTY_SPECS_DIR) / mission_slug / _STATUS_EVENTS_FILENAME
    return rel_events_path


def _parse_target_lanes_by_wp(events_text: str) -> dict[str, str]:
    """Reduce a target-branch event log to the latest ``to_lane`` per WP."""
    lanes_by_wp: dict[str, str] = {}
    for line in events_text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        wp_id = event.get("wp_id")
        to_lane = event.get("to_lane")
        if isinstance(wp_id, str) and isinstance(to_lane, str):
            lanes_by_wp[wp_id] = to_lane
    return lanes_by_wp


def _assert_merged_wps_done_on_target(
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    wp_ids: list[str],
    *,
    feature_dir: Path,
    mission_id: str | None,
) -> None:
    """Fail when modern merged WP done events are absent from target history."""
    if mission_id is None:
        return

    rel_events_path = _resolve_in_branch_status_events_path(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
    )

    ret_show, out_show, err_show = run_command(
        ["git", "show", f"{target_branch}:{rel_events_path.as_posix()}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_show != 0:
        console.print(
            "[red]Error:[/red] Post-merge target validation failed: "
            f"could not read {target_branch}:{rel_events_path.as_posix()} "
            f"({(err_show or out_show or '').strip()})"
        )
        raise typer.Exit(1)

    lanes_by_wp = _parse_target_lanes_by_wp(out_show or "")

    incomplete = [
        f"{wp_id}={lanes_by_wp.get(wp_id, 'missing')}"
        for wp_id in wp_ids
        if lanes_by_wp.get(wp_id) != "done"
    ]
    if incomplete:
        console.print(
            "[red]Error:[/red] Post-merge target validation failed: "
            "merged WPs did not reach done in target branch history."
        )
        console.print(f"  Offending WPs: {', '.join(incomplete)}")
        raise typer.Exit(1)


def _durable_coordination_lanes(
    *,
    repo_root: Path,
    mission_slug: str,
    candidate_wps: list[str],
) -> dict[str, str] | None:
    """Current lane per WP among *candidate_wps* on the COMMITTED coord ref.

    Returns ``None`` when the coordination ref cannot be resolved or carries no
    committed events (a non-coord topology or a legacy mission) — the caller then
    falls back to the transactional on-disk check. A WP with no committed event
    maps to ``""``. Shared by :func:`_durable_done_wps_on_coordination_ref` and
    :func:`_reconcile_completed_wps_for_resume` so both read ONE durable authority.
    """
    from specify_cli.coordination.status_service import (
        EventLogReadContract,
        read_event_log,
        wp_lane_actor_from_events,
    )

    try:
        coord_ref = resolve_placement_only(
            repo_root, mission_slug, kind=MissionArtifactKind.STATUS_STATE
        ).ref
    except Exception:  # noqa: BLE001 — unresolvable placement: fall back to on-disk check
        return None

    # The committed events live at ``kitty-specs/<slug>/status.events.jsonl`` on
    # the coordination ref; the primary feature dir (name == slug, meta-bearing)
    # is the correct ref-path anchor AND legacy-parse dir. Route through the
    # canonical PRIMARY-partition resolver (FR-004): a WORK_PACKAGE_TASK read folds
    # onto the topology-blind ``primary_feature_dir_for_mission`` (name == slug),
    # so no raw ``KITTY_SPECS_DIR/<slug>`` bypass — and a stale ``-coord`` husk can
    # never shadow the anchor.
    read_feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    events = read_event_log(
        EventLogReadContract.coordination_branch_ref(
            repo_root=repo_root,
            destination_ref=coord_ref,
            feature_dir=read_feature_dir,
            parser_feature_dir=read_feature_dir,
        )
    )
    if not events:
        return None
    return {wp_id: str(wp_lane_actor_from_events(events, wp_id).lane or "") for wp_id in candidate_wps}


def _durable_done_wps_on_coordination_ref(
    *,
    repo_root: Path,
    mission_slug: str,
    candidate_wps: list[str],
) -> set[str]:
    """WPs among *candidate_wps* reduced to ``done`` on the COMMITTED coord ref.

    FR-007: resume progress is derived from the durable event log — the
    committed coordination-branch ref — never the roll-backable worktree bytes.
    Consumes ``read_event_log(EventLogReadContract.coordination_branch_ref(...))``
    + ``wp_lane_actor_from_events`` (no new reducer). Returns an empty set (the
    caller re-derives via the transactional on-disk check) when the coordination
    ref cannot be resolved — a non-coord topology or a legacy mission.
    """
    from specify_cli.status import Lane

    lanes = _durable_coordination_lanes(repo_root=repo_root, mission_slug=mission_slug, candidate_wps=candidate_wps)
    if lanes is None:
        return set()
    return {wp_id for wp_id, lane in lanes.items() if lane == Lane.DONE}


def _reconcile_completed_wps_for_resume(
    *,
    feature_dir: Path,
    mission_slug: str,
    merge_state: ConsolidationState,
    repo_root: Path,
) -> set[str]:
    """Return completed WPs that still carry durable ``done`` evidence.

    FR-007: ``ConsolidationState.completed_wps`` is an advisory hint only. The authority
    for resume progress is the durable event log — the committed coordination
    ref (:func:`_durable_coordination_lanes`), with the transactional
    on-disk check as the topology-blind fallback ONLY when that ref cannot be
    read. A retry can happen after the target ref advanced but before the final
    status-event housekeeping commit; if the operator repairs the checkout back to
    HEAD, state.json may still list a WP as completed even though its ``done``
    evidence is gone. Drop those stale completions so the retry re-emits done
    evidence instead of skipping the WP and failing validation.

    The durable check reads the WP's CURRENT lane, never "a ``done`` event exists
    somewhere in its history" (#5046 landing, FR-011 recovery): a WP recorded
    ``done`` by a consolidation whose gate then FAILed, and afterwards reopened
    for governed rework (``done -> in_progress -> ... -> approved``), is no
    longer done — skipping it would fail post-merge validation forever, so the
    documented FAIL recovery ("revert through a surviving WP, re-run") could
    never succeed.
    """
    if not merge_state.completed_wps:
        return set()

    from specify_cli.status import Lane

    durable_lanes = _durable_coordination_lanes(
        repo_root=repo_root,
        mission_slug=mission_slug,
        candidate_wps=merge_state.completed_wps,
    )
    if durable_lanes is not None:
        confirmed = [wp_id for wp_id in merge_state.completed_wps if durable_lanes.get(wp_id) == Lane.DONE]
    else:
        confirmed = [
            wp_id
            for wp_id in merge_state.completed_wps
            if _has_transition_to(feature_dir, mission_slug, wp_id, "done", repo_root)
        ]
    if len(confirmed) != len(merge_state.completed_wps):
        dropped = sorted(set(merge_state.completed_wps) - set(confirmed))
        logger.info(
            "Re-emitting done events for WPs whose resume state outlived on-disk evidence: %s",
            ", ".join(dropped),
        )
        merge_state.completed_wps = confirmed
        save_state(merge_state, repo_root)
    return set(confirmed)


def _record_merged_wps_done_for_merge(
    *,
    main_repo: Path,
    feature_dir: Path,
    mission_slug: str,
    lanes_manifest: object,
    target_branch: str,
    merge_state: ConsolidationState,
    all_wp_ids: list[str],
) -> None:
    """Record done transitions for merged WPs and validate the canonical surface."""
    console.print("  [dim]Recording merged work packages as done...[/dim]")
    completed_set = _reconcile_completed_wps_for_resume(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        merge_state=merge_state,
        repo_root=main_repo,
    )
    # FR-004 / FR-009: a canceled WP with operator provenance is an acceptable
    # mission ending that carries no review artifact and never reaches ``done`` —
    # it must NOT be driven through the invalid ``canceled -> done`` transition
    # here (which would corrupt the honest-ending record this bookkeeping
    # protects). This is the SECOND independent per-WP derivation the exclusion
    # must reach (the first is ``executor.py``'s ``all_wp_ids``). The cancellation
    # audit record is untouched — the WP is simply skipped, not re-transitioned.
    excluded_canceled = acceptably_canceled_wp_ids(main_repo, mission_slug)
    for lane in lanes_manifest.lanes:  # type: ignore[attr-defined]
        for wp_id in lane.wp_ids:
            if wp_id in excluded_canceled:
                console.print(
                    f"  [dim]Skipping {wp_id} (canceled with provenance — "
                    "acceptable ending, excluded from done)[/dim]"
                )
                continue
            if wp_id in completed_set:
                console.print(f"  [dim]Skipping {wp_id} (already recorded as done)[/dim]")
                continue

            merge_state.set_current_wp(wp_id)
            save_state(merge_state, main_repo)

            _mark_wp_merged_done(main_repo, mission_slug, wp_id, target_branch)

            merge_state.mark_wp_complete(wp_id)
            save_state(merge_state, main_repo)
            completed_set.add(wp_id)

    _assert_merged_wps_reached_done(main_repo, mission_slug, all_wp_ids)


__all__ = [
    "acceptably_canceled_wp_ids",
    "_resolve_merge_actor",
    "_has_transition_to",
    "_mark_wp_merged_done",
    "_assert_merged_wps_reached_done",
    "_assert_merged_wps_done_on_target",
    "_reconcile_completed_wps_for_resume",
    "_record_merged_wps_done_for_merge",
]
