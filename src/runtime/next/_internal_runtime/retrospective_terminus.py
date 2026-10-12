"""Retrospective lifecycle terminus hook for spec-kitty next.

This module drives the retrospective lifecycle at mission terminus, coordinating:
  - Mode detection (autonomous vs human_in_command).
  - Event emission (requested, started, completed, skipped, failed).
  - Facilitator invocation via an injectable callback (real agent wired later).
  - Record persistence via write_record.
  - Gate consultation via before_mark_done (raises MissionCompletionBlocked on refusal).

TODO: integrate into next runtime mission-completion path.  The runtime calls
run_terminus(...) immediately before marking the mission done.  A future patch
(or WP11 integration tests) wires it up.  This keeps WP06 self-contained.

Owned by: WP06
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from kernel.clock import now_utc_iso
from runtime.next._internal_runtime.retrospective_hook import (
    before_mark_done,
)
from specify_cli.lanes.branch_naming import resolve_mid8
from specify_cli.retrospective.events import (
    CompletedPayload,
    FailedPayload,
    RequestedPayload,
    SkippedPayload,
    StartedPayload,
    emit_retrospective_event,
)
from specify_cli.retrospective.mode import detect as detect_mode
from specify_cli.retrospective.schema import (
    ActorRef,
    RetrospectiveRecord,
)
from specify_cli.retrospective.writer import (
    canonical_record_path,
    repo_relative_record_path,
    write_record,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_RUNTIME_ACTOR = ActorRef(kind="runtime", id="next", profile_id=None)

# Placeholder facilitator identity used in StartedPayload when real wiring is absent.
_DEFERRED_FACILITATOR_ID = "deferred"
_DEFERRED_ACTION_ID = "action:retrospect"

_TERMINUS_STEP_ID = "terminus"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mission_slug_from_feature_dir(feature_dir: Path) -> str:
    """Derive a mission slug from the feature_dir name (best effort)."""
    return feature_dir.name


def _record_path_str(record: RetrospectiveRecord, repo_root: Path) -> str:
    """Return the repository-relative canonical record path for the event payload (#5868).

    FR-001/003 (#2119): the emitted payload path MUST equal the ACTUAL write home
    (``kitty-specs/<slug>/retrospective.yaml``), not the legacy gitignored
    ``.kittify/missions/<id>/`` string. Route through the SINGLE durable-home
    authority (:func:`resolve_retrospective_home`) so the payload re-homes in
    lock-step with the record — never re-splitting the brain. The handle is
    canonicalized inside the authority (FR-011 write leg) so a bare slug still
    reports the canonical durable home.
    """
    canonical = canonical_record_path(repo_root, record.mission.mission_slug)
    return repo_relative_record_path(canonical, repo_root)


def _findings_summary(record: RetrospectiveRecord) -> dict[str, int]:
    return {
        "helped": len(record.helped),
        "not_helpful": len(record.not_helpful),
        "gaps": len(record.gaps),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_terminus(
    *,
    mission_id: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    operator_actor: ActorRef,
    facilitator_callback: Callable[..., RetrospectiveRecord] | None = None,
    hic_prompt: Callable[[], tuple[bool, str | None]] | None = None,
) -> None:
    """Drive the retrospective lifecycle at mission terminus.

    facilitator_callback: invoked when the lifecycle decides to run the retrospective.
        Receives mission identity context and returns a RetrospectiveRecord.
    hic_prompt: in HiC mode, returns (run_now: bool, skip_reason: str | None).
        If None, defaults to a Rich prompt.

    Steps:
        1. Resolve mode (autonomous vs human_in_command).
        2. Emit retrospective.requested with the resolved mode.
        3. Autonomous:
           - Emit retrospective.started.
           - Invoke facilitator_callback(...).
           - On success: persist record + emit retrospective.completed.
           - On failure: emit retrospective.failed + call before_mark_done
             (gate will block, raising MissionCompletionBlocked).
        4. HiC:
           - Call hic_prompt() (or default Rich prompt).
           - If run: emit started → invoke → persist → emit completed.
           - If skip: persist skip record + emit retrospective.skipped.
        5. Call before_mark_done(mission_id, ...).
           Raises MissionCompletionBlocked if the gate refuses.

    Raises:
        MissionCompletionBlocked: if before_mark_done refuses completion.
        Any exception raised by facilitator_callback in autonomous mode will
        cause retrospective.failed to be emitted and before_mark_done to be
        called (which will then raise MissionCompletionBlocked).
    """
    mission_slug = _mission_slug_from_feature_dir(feature_dir)
    # Canonical mid8 resolver (FR-001): the terminus always holds a full ULID
    # ``mission_id``, so this is byte-identical to the deleted ``_mid8`` shadow.
    mid = resolve_mid8(mission_slug, mission_id=mission_id)

    # ------------------------------------------------------------------
    # 1. Resolve mode.
    # ------------------------------------------------------------------
    mode = detect_mode(repo_root=repo_root)

    logger.debug(
        "run_terminus: mission=%s mode=%s source=%s",
        mission_id,
        mode.value,
        mode.source_signal.kind,
    )

    # ------------------------------------------------------------------
    # 2. Emit retrospective.requested.
    #    Actor: runtime in autonomous; operator_actor in HiC.
    # ------------------------------------------------------------------
    requested_actor = _RUNTIME_ACTOR if mode.value == "autonomous" else operator_actor

    emit_retrospective_event(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid,
        actor=requested_actor,
        event_name="retrospective.requested",
        payload=RequestedPayload(
            mode=mode,
            terminus_step_id=_TERMINUS_STEP_ID,
            requested_by=requested_actor,
        ),
    )

    # ------------------------------------------------------------------
    # 3 / 4. Dispatch by mode.
    # ------------------------------------------------------------------
    if mode.value == "autonomous":
        _run_autonomous(
            mission_id=mission_id,
            feature_dir=feature_dir,
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid=mid,
            facilitator_callback=facilitator_callback,
        )
    else:
        _run_hic(
            mission_id=mission_id,
            mission_type=mission_type,
            feature_dir=feature_dir,
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid=mid,
            operator_actor=operator_actor,
            facilitator_callback=facilitator_callback,
            hic_prompt=hic_prompt,
        )

    # ------------------------------------------------------------------
    # 5. Gate consultation — always last.
    # ------------------------------------------------------------------
    before_mark_done(mission_id, feature_dir=feature_dir, repo_root=repo_root)


# ---------------------------------------------------------------------------
# Autonomous path
# ---------------------------------------------------------------------------


def _run_autonomous(
    *,
    mission_id: str,
    feature_dir: Path,
    repo_root: Path,
    mission_slug: str,
    mid: str,
    facilitator_callback: Callable[..., RetrospectiveRecord] | None,
) -> None:
    """Autonomous retrospective path: auto-invoke facilitator."""
    # Emit started.
    emit_retrospective_event(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid,
        actor=_RUNTIME_ACTOR,
        event_name="retrospective.started",
        payload=StartedPayload(
            facilitator_profile_id=_DEFERRED_FACILITATOR_ID,
            action_id=_DEFERRED_ACTION_ID,
        ),
    )

    # Invoke facilitator. When no callback is wired (deferred runtime
    # integration), emit ``retrospective.failed`` with a structured failure
    # code so the gate blocks completion and the operator sees a clear
    # diagnostic. Do not raise: the gate is the source of truth for
    # blocking, and emitting an event keeps the audit trail intact.
    if facilitator_callback is None:
        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.failed",
            payload=FailedPayload(
                failure_code="facilitator_not_configured",
                message=(
                    "Autonomous retrospective requested but no facilitator_callback "
                    "is wired into the runtime. Configure a facilitator or set "
                    "the charter clause permitting autonomous skip."
                ),
                record_path=None,
            ),
        )
        return

    try:
        record = facilitator_callback(
            mission_id=mission_id,
            feature_dir=feature_dir,
            repo_root=repo_root,
        )
    except Exception as exc:
        logger.exception("Facilitator raised in autonomous mode: %s", exc)
        # Emit failed — no record persisted.
        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.failed",
            payload=FailedPayload(
                failure_code="facilitator_error",
                message=str(exc),
                record_path=None,
            ),
        )
        # Gate will block — let it do so naturally via before_mark_done.
        return

    # Persist record.
    canonical_path = write_record(record, repo_root=repo_root)

    # Emit completed.
    emit_retrospective_event(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid,
        actor=_RUNTIME_ACTOR,
        event_name="retrospective.completed",
        payload=CompletedPayload(
            record_path=repo_relative_record_path(canonical_path, repo_root),
            record_hash="",  # hash deferred to real integration
            findings_summary=_findings_summary(record),
            proposals_count=len(record.proposals),
        ),
    )


# ---------------------------------------------------------------------------
# HiC path
# ---------------------------------------------------------------------------


def _run_hic(
    *,
    mission_id: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    mission_slug: str,
    mid: str,
    operator_actor: ActorRef,
    facilitator_callback: Callable[..., RetrospectiveRecord] | None,
    hic_prompt: Callable[[], tuple[bool, str | None]] | None,
) -> None:
    """Human-in-command retrospective path: prompt operator then act.

    When ``hic_prompt`` is None, no operator-side prompt is wired.  We emit
    ``retrospective.failed`` with code ``prompt_not_configured`` so the gate
    produces a structured blocked decision; the bridge supplies a real
    Rich-backed prompt on interactive paths.
    """
    if hic_prompt is None:
        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid,
            actor=operator_actor,
            event_name="retrospective.failed",
            payload=FailedPayload(
                failure_code="prompt_not_configured",
                message=(
                    "Human-in-command retrospective requires an interactive "
                    "prompt callback; none was supplied to run_terminus."
                ),
                record_path=None,
            ),
        )
        return

    run_now, skip_reason = hic_prompt()

    if run_now:
        # Run branch: emit started → invoke → persist → emit completed.
        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid,
            actor=operator_actor,
            event_name="retrospective.started",
            payload=StartedPayload(
                facilitator_profile_id=_DEFERRED_FACILITATOR_ID,
                action_id=_DEFERRED_ACTION_ID,
            ),
        )

        if facilitator_callback is None:
            # No facilitator wired — emit failed instead of raising so the
            # event log carries an honest record of the deferred wiring and
            # the gate produces a clear blocked decision.
            emit_retrospective_event(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                mission_id=mission_id,
                mid8=mid,
                actor=operator_actor,
                event_name="retrospective.failed",
                payload=FailedPayload(
                    failure_code="facilitator_not_configured",
                    message=(
                        "Operator chose to run the retrospective but no "
                        "facilitator_callback is wired into the runtime. "
                        "Skip the retrospective or configure a facilitator."
                    ),
                    record_path=None,
                ),
            )
            return

        try:
            record = facilitator_callback(
                mission_id=mission_id,
                feature_dir=feature_dir,
                repo_root=repo_root,
            )
        except Exception as exc:
            logger.exception("Facilitator raised in HiC run path: %s", exc)
            emit_retrospective_event(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                mission_id=mission_id,
                mid8=mid,
                actor=operator_actor,
                event_name="retrospective.failed",
                payload=FailedPayload(
                    failure_code="facilitator_error",
                    message=str(exc),
                    record_path=None,
                ),
            )
            return

        canonical_path = write_record(record, repo_root=repo_root)

        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid,
            actor=operator_actor,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path=repo_relative_record_path(canonical_path, repo_root),
                record_hash="",  # hash deferred to real integration
                findings_summary=_findings_summary(record),
                proposals_count=len(record.proposals),
            ),
        )

    else:
        # Skip branch: persist skip record + emit skipped.
        # skip_reason guaranteed non-empty by prompt contract.
        if not skip_reason:
            skip_reason = "(no reason provided)"  # defensive — should not happen

        # Build a minimal skipped record.  We import the full schema types here
        # to produce a valid persisted record that round-trips schema validation.
        from specify_cli.retrospective.schema import (  # noqa: PLC0415
            MissionIdentity,
            RecordProvenance,
        )

        now_ts = now_utc_iso()
        skip_record = RetrospectiveRecord(
            schema_version="1",
            mission=MissionIdentity(
                mission_id=mission_id,
                mid8=mid,
                mission_slug=mission_slug,
                mission_type=mission_type,
                mission_started_at=now_ts,
                mission_completed_at=None,
            ),
            mode=detect_mode(repo_root=repo_root),
            status="skipped",
            started_at=now_ts,
            completed_at=None,
            actor=operator_actor,
            provenance=RecordProvenance(
                authored_by=operator_actor,
                runtime_version="0.0.0-terminus",
                written_at=now_ts,
                schema_version="1",
            ),
            skip_reason=skip_reason,
        )

        canonical_path = write_record(skip_record, repo_root=repo_root)

        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid,
            actor=operator_actor,
            event_name="retrospective.skipped",
            payload=SkippedPayload(
                record_path=repo_relative_record_path(canonical_path, repo_root),
                skip_reason=skip_reason,
                skipped_by=operator_actor,
            ),
        )
