"""Local-first canonical lifecycle event persistence.

This module is the durable, local-first writer for the canonical event
stream that records project initialization, mission creation,
spec/plan/tasks artifact lifecycle, and work-package creation. Lifecycle
events land on disk synchronously *before* any best-effort SaaS outbox
fan-out, so local dashboards and TeamSpace import always have a complete
history even when the scoped sync boundary is unavailable.

Two log targets exist:

* **Project-level log** (``<repo_root>/.kittify/canonical-events.jsonl``)
  carries project-wide events such as ``ProjectInitialized``.

* **Mission-level log** (``<feature_dir>/status.events.jsonl``) is
  shared with the existing ``WPStatusChanged`` reducer; lifecycle events
  carry a top-level ``event_type`` field and are intentionally skipped
  by :mod:`specify_cli.status.store`'s ``StatusEvent`` reader.

Idempotency
-----------

Each appender is keyed by ``(event_type, deduplication tuple)`` so
re-running the producer (e.g. ``finalize-tasks`` on an existing
mission) is a no-op for already-recorded events. This makes the
canonical stream a safe target for repair / replay tooling.

The schema mirrors the contracts defined in
``spec_kitty_events.project_lifecycle`` (sibling repo). The
``project_lifecycle`` module is referenced via string constants here
so that the CLI does not hard-fail when an older release of
``spec-kitty-events`` is installed; the payloads are forward-compatible
with the typed contracts.
"""

from __future__ import annotations

import json
import logging
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping

from kernel.clock import datetime, now_utc, now_utc_iso, parse_iso
from specify_cli.workspace.root_resolver import WorkspaceRootNotFound, resolve_canonical_root

from .locking import feature_status_lock, project_event_log_lock
from .models import Lane as _Lane
from .store import append_raw_rows_atomic

logger = logging.getLogger(__name__)


class MissionNotCompletedError(RuntimeError):
    """Raised when a post-mission lifecycle event is emitted before completion.

    Post-mission facts (``MissionReopened`` / ``FollowUpRecorded``) are only
    valid once a mission has reached completion (#1926). This is the producer
    side of the invariant the sibling events-package reducer enforces on the
    consumer side. The emit helpers raise this fail-closed *before* writing any
    event, so a rejected emit leaves the log untouched.
    """

    def __init__(self, action: str, mission_slug: str) -> None:
        self.action = action
        self.mission_slug = mission_slug
        super().__init__(f"cannot {action}: mission {mission_slug!r} has not completed/merged")


# ---------------------------------------------------------------------------
# Event type constants — kept in sync with spec_kitty_events.project_lifecycle
# ---------------------------------------------------------------------------

PROJECT_INITIALIZED = "ProjectInitialized"
MISSION_CREATED = "MissionCreated"
SPECIFY_STARTED = "SpecifyStarted"
SPECIFY_COMPLETED = "SpecifyCompleted"
PLAN_STARTED = "PlanStarted"
PLAN_COMPLETED = "PlanCompleted"
TASKS_STARTED = "TasksStarted"
TASKS_COMPLETED = "TasksCompleted"
WP_CREATED = "WPCreated"
REVIEWER_SELF_APPROVAL = "ReviewerSelfApproval"

# Post-mission lifecycle events (WP01 / FR-001). These record facts about a
# mission *after* it has merged/closed: a re-open returning it to an actionable
# state, and a follow-up commit/PR attributed to it. They are LOCAL-ONLY this
# mission — intentionally kept off the SaaS strict-validation path
# (``_validate_lifecycle_payload(strict=True)``): the external ``spec_kitty_events``
# package does not yet know these types, and propagating them to SaaS requires an
# external contract bump (follow-up, out of scope). The local event log remains
# authoritative. See research.md C-SAAS.
MISSION_REOPENED = "MissionReopened"
FOLLOW_UP_RECORDED = "FollowUpRecorded"

# The lifecycle event types that are LOCAL-ONLY: emitted after a mission's active
# lifecycle (reopen / follow-up) and deliberately kept OFF the SaaS strict-
# validation delivery path. The SINGLE public owner of this membership (#2884),
# consumed by the post-mission ordering in ``status/lifecycle.py`` and the import
# scan in ``sync/history_import/scan.py`` — replacing two hand-mirrored frozenset
# copies. NOTE: this is NOT the installed ``spec_kitty_events.LOCAL_ONLY_EVENT_TYPES``,
# which is empty in the package while both types ARE in its model map, so trusting
# it would let these reach strict validation and reject the whole batch.
LOCAL_ONLY_LIFECYCLE_EVENT_TYPES = frozenset({MISSION_REOPENED, FOLLOW_UP_RECORDED})

LIFECYCLE_EVENT_TYPES = frozenset(
    {
        PROJECT_INITIALIZED,
        MISSION_CREATED,
        SPECIFY_STARTED,
        SPECIFY_COMPLETED,
        PLAN_STARTED,
        PLAN_COMPLETED,
        TASKS_STARTED,
        TASKS_COMPLETED,
        WP_CREATED,
        REVIEWER_SELF_APPROVAL,
        MISSION_REOPENED,
        FOLLOW_UP_RECORDED,
    }
)

PROJECT_EVENTS_FILENAME = "canonical-events.jsonl"
MISSION_EVENTS_FILENAME = "status.events.jsonl"


# ---------------------------------------------------------------------------
# Authoritative non-lane event-type registry (#4897)
# ---------------------------------------------------------------------------

# The Decision Moment Protocol's own ``event_type`` vocabulary
# (``decisions/emit.py``, ``widen/flow.py``). ``status.events.jsonl`` is
# these events' CANONICAL store, NOT a prunable mirror:
# ``decisions/index_fold.py`` rebuilds ``decisions/index.json`` FROM this
# log. Before this registry existed, ``migration/mission_state.py``'s
# ``_is_preserved_non_lane_row`` believed the opposite -- that
# ``decisions/index.json`` was canonical and this copy disposable -- and
# quarantined these rows out of a healthy mission on every
# ``doctor mission-state --fix`` (#4897).
_DECISION_POINT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "DecisionPointOpened",
        "DecisionPointResolved",
        "DecisionPointDeferred",
        "DecisionPointCanceled",
        "DecisionPointWidened",
    }
)

#: SINGLE authority (#4897) for "this ``event_type`` row is an authoritative
#: non-lane record that shares ``status.events.jsonl`` and MUST survive
#: every repair/prune pass over that file". Consulted by BOTH the durable
#: reader (:func:`specify_cli.status.store.is_non_lane_event`) and the
#: mission-state repair
#: (:func:`specify_cli.migration.mission_state._is_preserved_non_lane_row`).
#: Before this registry existed the two consulted divergent hand-maintained
#: sets -- the reader treated ANY ``event_type`` as non-lane while the
#: repair preserved only :data:`LIFECYCLE_EVENT_TYPES` -- which silently
#: quarantined ``DecisionPoint*`` rows out from under a healthy mission
#: (#4897), continuing a recurring whack-a-field class (#2376 retrospective,
#: #3066 ``WPStatusChanged``, #3541 ``review_result``). A future event type
#: that both the reader and the repair must agree is non-lane-and-preserved
#: belongs in this union, not in a new parallel list in either consumer.
AUTHORITATIVE_NON_LANE_EVENT_TYPES: frozenset[str] = LIFECYCLE_EVENT_TYPES | _DECISION_POINT_EVENT_TYPES


def is_authoritative_non_lane_event_type(event_type: object) -> bool:
    """Return True when *event_type* is a known authoritative non-lane type.

    Typed ``object`` (not ``str``) because every call site passes
    ``row.get("event_type")`` directly, which may be any JSON value -- or
    absent, i.e. ``None`` -- for a malformed row.
    """
    return isinstance(event_type, str) and event_type in AUTHORITATIVE_NON_LANE_EVENT_TYPES


# ---------------------------------------------------------------------------
# Path resolvers
# ---------------------------------------------------------------------------


def project_event_log_path(repo_root: Path) -> Path:
    """Return the canonical project-level event log path for *repo_root*."""
    return repo_root / ".kittify" / PROJECT_EVENTS_FILENAME


def mission_event_log_path(feature_dir: Path) -> Path:
    """Return the canonical mission-level event log path for *feature_dir*."""
    return feature_dir / MISSION_EVENTS_FILENAME


# ---------------------------------------------------------------------------
# Reading & writing
# ---------------------------------------------------------------------------


def _iso_str_to_datetime(iso: str | None) -> datetime | None:
    """Parse an ISO-8601 string to a timezone-aware datetime, or return None.

    Used at payload-construction boundaries where callers pass ``str | None``
    but the ``spec_kitty_events`` 6.0.0 Pydantic models expect ``datetime | None``.
    ``datetime.fromisoformat`` handles the full RFC 3339 / ISO 8601 subset that
    Python's own ``datetime.isoformat()`` produces, so round-trips are lossless.
    """
    if iso is None:
        return None
    return parse_iso(iso)


def _generate_event_id() -> str:
    try:
        from ulid import ULID

        return str(ULID())
    except Exception:  # pragma: no cover — fallback for stripped envs
        import uuid

        return uuid.uuid4().hex


def _read_lifecycle_lines(path: Path) -> list[dict[str, Any]]:
    """Best-effort read of lifecycle event dicts from a JSONL file.

    Tolerates missing files, blank lines, and corrupted lines (the
    bad lines are skipped with a debug log). Only entries that carry
    a top-level ``event_type`` are returned: any sibling format (e.g.
    ``WPStatusChanged`` payloads written by the status reducer) is
    filtered out so callers can scan lifecycle history in isolation.
    """
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not read lifecycle log %s: %s", path, exc)
        return []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping non-JSON lifecycle line in %s", path)
            continue
        if isinstance(obj, dict) and isinstance(obj.get("event_type"), str):
            out.append(obj)
    return out


def _atomic_append(path: Path, line: str) -> None:
    """Append a single serialized JSON line to *path*, crash-safely.

    F2-T1 (F2.md section 2.2/3.3): this used to be a plain ``O_APPEND``
    write with no locking and no temp-file+rename, structurally different
    from -- and racing against -- ``status/store.py``'s crash-safe primitive
    that also writes this same file. It now delegates to the shared
    write-ahead-then-atomic-rename primitive
    (:func:`specify_cli.status.store.append_raw_rows_atomic`) instead, so
    both writers of ``status.events.jsonl`` / ``.kittify/canonical-events.jsonl``
    use the identical durability mechanism. Locking is the caller's
    responsibility (:func:`append_lifecycle_event` acquires the lock that
    owns *path* before calling this). Kept as a named, single-line-oriented
    seam (rather than inlining) so existing write-failure tests can keep
    monkeypatching this exact name (compatibility, F2.md section 3.4).

    Behavior change, explicitly named (F2.md section 3.4 review follow-up):
    because this now delegates to ``append_raw_rows_atomic``, every lifecycle
    row is run through ``store.sanitize_event_for_log`` before it hits disk,
    same as ``StatusEvent`` rows. Previously lifecycle rows were never
    sanitized. No lifecycle payload field currently collides with the PII
    field set that helper strips (``machine_name``, ``hostname``,
    ``workspace_path``, ``developer_name``, ``developer_email``) or its
    ``session_started_at``/``session_ended_at`` rewrite, so there is no
    observed behavior change today -- but a future lifecycle payload field
    that happens to share one of those names will now be silently stripped,
    and that is intentional, not an oversight.
    """
    append_raw_rows_atomic(path, [json.loads(line)])


def _lifecycle_write_lock(repo_root: Path | None, mission_slug: str | None) -> AbstractContextManager[Path | None]:
    """Return the lock context that guards a lifecycle log writer.

    Mission-scoped writes (``mission_slug`` provided, i.e. every appender
    except ``ProjectInitialized``) use the SAME mission-keyed
    :func:`feature_status_lock` that ``status/emit.py``'s
    ``emit_status_transition`` uses for ``status.events.jsonl`` -- this is
    what closes the F2-T1 lost-write race, since both writers now serialize
    on one lock file. Project-scoped writes (``ProjectInitialized``) use the
    sibling :func:`project_event_log_lock`. When *repo_root* cannot be
    resolved (the log path is not inside any git repo -- an edge case for
    ad-hoc/non-repo callers) locking is skipped, matching this module's
    pre-existing best-effort, never-raise contract; the write itself still
    goes through the crash-safe primitive either way.
    """
    if repo_root is None:
        return nullcontext()
    if mission_slug is not None:
        return feature_status_lock(repo_root, mission_slug)
    return project_event_log_lock(repo_root)


# canonical-producer-exempt: #1198 -- local lifecycle JSONL envelope.
def _build_envelope(
    event_type: str,
    payload: Mapping[str, Any],
    *,
    aggregate_id: str,
    aggregate_type: str,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    schema_version: str = "5.0.0",
) -> dict[str, Any]:
    return {  # canonical-producer-exempt: #1198 — see function-level comment above
        "event_id": _generate_event_id(),
        "event_type": event_type,
        "aggregate_id": aggregate_id,
        "aggregate_type": aggregate_type,
        "schema_version": schema_version,
        "timestamp": now_utc_iso(),
        "payload": dict(payload),
        "project_uuid": project_uuid,
        "project_slug": project_slug,
    }


def _repo_root_for_lifecycle_log(log_path: Path | None) -> Path | None:
    """Resolve the canonical repo root for *log_path* via ``resolve_canonical_root``.

    Routes to the existing public pure resolver (D-12 / FR-001) — CWD-invariant
    across primary checkout, coord worktree, and submodule topologies.  Returns
    ``None`` when the log path is absent or not inside any git repo.
    """
    if log_path is None:
        return None
    try:
        return Path(resolve_canonical_root(log_path.parent))
    except WorkspaceRootNotFound:
        return None


def _validate_lifecycle_payload(event_type: str, payload: Mapping[str, Any]) -> None:
    """Validate lifecycle payloads against the canonical events contract.

    Delegates to ``spec_kitty_events.conformance.validate_event`` so every
    event type the events package recognises (lifecycle, status, dossier,
    build, …) is checked under the same canonical rules.

    Phase-2 widening (issues Priivacy-ai/spec-kitty#1198 / #1200): we now
    pass ``strict=True`` and raise on both ``model_violations`` and
    ``schema_violations`` for known event types. The previous behavior
    raised only on model violations, which let JSON-schema-level drift
    (missing required fields, additionalProperties=false breaches) reach
    the SaaS boundary as a runtime canary failure instead of a producer
    emit-time error.

    Local-only event types (``spec_kitty_events.LOCAL_ONLY_EVENT_TYPES``)
    skip strict validation by design — the set is currently empty but
    reserved for future internal-only event types. The local
    :data:`LOCAL_ONLY_LIFECYCLE_EVENT_TYPES` SSOT is also consulted here
    (#2884): it is the actual enforcement point for the "kept OFF the SaaS
    strict-validation path" invariant its own docstring claims, since the
    external set does not yet cover ``MissionReopened`` / ``FollowUpRecorded``
    even though both are present in ``_EVENT_TYPE_TO_MODEL``.

    Unknown event types (event_type not in ``_EVENT_TYPE_TO_MODEL``) pass
    through quietly so unrecognised types don't become sudden hard
    failures. The producer lint catches the corresponding hand-rolled
    dict at static analysis time.
    """
    from spec_kitty_events import LOCAL_ONLY_EVENT_TYPES
    from spec_kitty_events.conformance import validate_event
    from spec_kitty_events.conformance.validators import _EVENT_TYPE_TO_MODEL

    if event_type in LOCAL_ONLY_EVENT_TYPES or event_type in LOCAL_ONLY_LIFECYCLE_EVENT_TYPES:
        return

    if event_type not in _EVENT_TYPE_TO_MODEL:
        return

    result = validate_event(dict(payload), event_type, strict=True)
    if result.model_violations or result.schema_violations:
        model_details = [f"{v.field}: {v.message}" for v in result.model_violations]
        schema_details = [f"{v.json_path}: {v.message}" for v in result.schema_violations]
        details = "; ".join((*model_details, *schema_details))
        raise ValueError(f"Lifecycle payload for {event_type!r} fails canonical contract: {details}")


def _canonical_lifecycle_payload_for_saas(
    event_type: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a local lifecycle payload to the strict SaaS wire shape.

    Local Started events keep ``artifact_path`` so local replay and dashboards
    can identify the artifact opened by the phase transition. The canonical
    ``spec-kitty-events`` Started payloads intentionally do not expose that
    field, so the SaaS fan-out strips it before strict validation and queueing.
    """
    projected = dict(payload)
    if event_type.endswith("Started"):
        projected.pop("artifact_path", None)
    return projected


def repo_root_for_lifecycle_log(log_path: Path | None) -> Path | None:
    """Public alias for :func:`_repo_root_for_lifecycle_log`.

    Exposed on the ``status`` facade so the sync fan-out handler can resolve the
    repo root for a lifecycle log without reaching into a ``status`` submodule
    (repo-wide import-boundary contract). Pure helper, no side effects.
    """
    return _repo_root_for_lifecycle_log(log_path)


def build_saas_lifecycle_queue_event(
    envelope: Mapping[str, Any],
    *,
    build_id: str,
    project_uuid: str,
    project_slug: str | None,
    node_id: str,
    lamport_clock: int,
) -> dict[str, Any] | None:
    """Project a local lifecycle ``envelope`` to the strict SaaS queue event.

    Encapsulates the lifecycle-specific shaping (canonical payload projection,
    strict contract validation, and canonical-envelope assembly) so the sync
    fan-out handler can build a queueable event without importing ``status``
    internals directly (repo-wide import-boundary contract). Identity- and
    clock-derived primitives are passed in by the caller, keeping this module
    free of sync/identity/queue dependencies.

    Returns ``None`` when the envelope is not a queueable lifecycle event
    (missing/invalid ``event_type``, ``payload``, or ``aggregate_type``).
    """
    event_type = envelope.get("event_type")
    payload = envelope.get("payload")
    if not isinstance(event_type, str) or not isinstance(payload, Mapping):
        return None

    aggregate_type = envelope.get("aggregate_type")
    if not isinstance(aggregate_type, str):
        return None

    saas_payload = _canonical_lifecycle_payload_for_saas(event_type, payload)
    _validate_lifecycle_payload(event_type, saas_payload)

    event_id = _generate_event_id()
    aggregate_id = envelope.get("aggregate_id") or payload.get("mission_slug") or event_id
    # canonical-producer-exempt: #1198 -- lifecycle-to-SaaS wire envelope.
    return {
        "event_id": event_id,
        "event_type": event_type,
        "aggregate_id": str(aggregate_id),
        "aggregate_type": aggregate_type,
        "schema_version": "3.0.0",
        "build_id": build_id,
        "payload": saas_payload,
        "node_id": node_id,
        "lamport_clock": lamport_clock,
        "causation_id": None,
        "correlation_id": event_id,
        "timestamp": envelope.get("timestamp") or now_utc_iso(),
        "project_uuid": project_uuid,
        "project_slug": project_slug or envelope.get("project_slug"),
    }


def fanout_lifecycle_event_hosted(
    envelope: Mapping[str, Any],
    *,
    log_path: Path | None,
) -> None:
    """Offer a persisted lifecycle *envelope* to registered hosted adapters.

    This is the explicit hosted-effect half of lifecycle emission. It never
    writes the local JSONL log; callers that need the traditional composed
    behavior should continue to use :func:`append_lifecycle_event`.
    """
    from specify_cli.status.adapters import fire_lifecycle_saas_fanout

    fire_lifecycle_saas_fanout(envelope=envelope, log_path=log_path)


def _match_lifecycle_event(
    candidate: Mapping[str, Any],
    *,
    event_type: str,
    dedup_keys: Mapping[str, Any],
) -> bool:
    if candidate.get("event_type") != event_type:
        return False
    payload = candidate.get("payload") or {}
    if not isinstance(payload, Mapping):
        return False
    return all(_dedup_value_matches(key, payload.get(key), expected) for key, expected in dedup_keys.items())


def _dedup_value_matches(key: str, actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    if key == "artifact_path" and isinstance(actual, str) and isinstance(expected, str):
        return Path(actual).name == Path(expected).name
    return False


def has_lifecycle_event(
    log_path: Path,
    *,
    event_type: str,
    dedup_keys: Mapping[str, Any],
) -> bool:
    """Return True if the log already contains a matching lifecycle event."""
    return any(_match_lifecycle_event(entry, event_type=event_type, dedup_keys=dedup_keys) for entry in _read_lifecycle_lines(log_path))


def persist_lifecycle_event_local(
    log_path: Path,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    aggregate_id: str,
    aggregate_type: str,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    dedup_keys: Mapping[str, Any] | None = None,
    mission_slug: str | None = None,
) -> dict[str, Any] | None:
    """Persist a lifecycle event locally without invoking hosted adapters.

    Returns the persisted event envelope, or ``None`` when the append was
    skipped because an event with the same ``(event_type, dedup_keys)``
    tuple is already on disk. Failures fall back to a debug log; the
    function never raises so callers can chain it safely behind a
    fire-and-forget ``contextlib.suppress`` if they choose.

    ``mission_slug`` (F2-T1, F2.md section 3.3): pass the mission's slug for
    every mission-scoped appender (all of them except
    :func:`emit_project_initialized`) so the write is serialized under the
    SAME lock ``status/emit.py``'s ``emit_status_transition`` uses for that
    mission's ``status.events.jsonl`` -- closing the lost-write race between
    the two writers of that file. Leave it ``None`` for project-scoped
    writes (``.kittify/canonical-events.jsonl``), which lock on the sibling
    :func:`specify_cli.status.locking.project_event_log_lock` instead. The
    external return-value/never-raises contract is unchanged either way.
    """
    if event_type not in LIFECYCLE_EVENT_TYPES:
        logger.debug("Refusing to append unknown lifecycle event type %r", event_type)
        return None

    if dedup_keys and has_lifecycle_event(log_path, event_type=event_type, dedup_keys=dedup_keys):
        logger.debug(
            "Lifecycle event %s already present in %s; skipping append",
            event_type,
            log_path,
        )
        return None

    envelope = _build_envelope(
        event_type,
        payload,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        project_uuid=project_uuid,
        project_slug=project_slug,
    )
    repo_root = _repo_root_for_lifecycle_log(log_path)
    try:
        with _lifecycle_write_lock(repo_root, log_path.parent.name if mission_slug is not None else None):
            _atomic_append(log_path, json.dumps(envelope, sort_keys=True))
    except OSError as exc:
        logger.warning("Could not persist %s event to %s: %s", event_type, log_path, exc)
        return None
    return envelope


def append_lifecycle_event(
    log_path: Path,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    aggregate_id: str,
    aggregate_type: str,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    dedup_keys: Mapping[str, Any] | None = None,
    mission_slug: str | None = None,
) -> dict[str, Any] | None:
    """Persist locally, then offer the same envelope to hosted fan-out.

    This preserves the historical composed behavior for existing callers.
    Local persistence remains authoritative: a skipped or failed local write
    returns ``None`` and does not invoke a hosted adapter.
    """
    envelope = persist_lifecycle_event_local(
        log_path,
        event_type,
        payload,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys=dedup_keys,
        mission_slug=mission_slug,
    )
    if envelope is not None:
        fanout_lifecycle_event_hosted(envelope, log_path=log_path)
    return envelope


# ---------------------------------------------------------------------------
# Convenience helpers (per event type)
# ---------------------------------------------------------------------------


def emit_project_initialized(
    repo_root: Path,
    *,
    project_uuid: str,
    project_slug: str | None,
    actor: str = "cli",
    runtime_version: str | None = None,
    initialized_at: str | None = None,
) -> dict[str, Any] | None:
    """Record a local ``ProjectInitialized`` event for *repo_root*.

    Idempotent on ``project_uuid``: re-running ``spec-kitty init`` (or any
    bootstrap flow) on an already-initialized project is a no-op.

    The payload is constructed via the canonical
    :class:`spec_kitty_events.project_lifecycle.ProjectInitializedPayload`
    so producer-time validation rejects any field that drifts from the
    contract (issues Priivacy-ai/spec-kitty#1198 / #1200).
    """
    from spec_kitty_events.project_lifecycle import ProjectInitializedPayload

    log_path = project_event_log_path(repo_root)
    payload = ProjectInitializedPayload(
        project_uuid=project_uuid,
        project_slug=project_slug,
        actor=actor,
        runtime_version=runtime_version,
        initialized_at=_iso_str_to_datetime(initialized_at) or now_utc(),
    ).model_dump(mode="json", exclude_none=False)
    return append_lifecycle_event(
        log_path,
        PROJECT_INITIALIZED,
        payload,
        aggregate_id=project_uuid,
        aggregate_type="Project",
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys={"project_uuid": project_uuid},
    )


def _resolve_local_actor() -> str:
    """Resolve the opaque actor identifier for locally emitted mission moments.

    Same convention as the interview/charter ``_resolve_actor`` helpers and the
    sync emitter's ``_resolve_runtime_actor`` (git ``user.email``, else
    ``"cli"``): an identifier, never free text. The zeitgeist attrs codec
    projects it verbatim as the moment's ``actor`` key, so this — not the relay
    credential — is the WHO a mission-level moment renders with once set.
    Never raises: an unresolvable identity degrades to ``"cli"``, matching the
    emit path's never-raises contract.

    A resolved email that would not fit the codec's per-value byte bound
    (:data:`spec_kitty_events.zeitgeist_attrs.ZEITGEIST_ATTRS_MAX_BYTES`) also
    degrades to ``"cli"``: ``MissionCreatedPayload.actor`` has no
    ``max_length``, so an oversized value would otherwise pass producer-time
    validation and only fail downstream at broadcast, silently dropping the
    whole moment instead of just its WHO (#74).
    """
    import subprocess

    from spec_kitty_events.zeitgeist_attrs import ZEITGEIST_ATTRS_MAX_BYTES

    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        email = result.stdout.strip()
        if email and len(email.encode("utf-8")) <= ZEITGEIST_ATTRS_MAX_BYTES:
            return email
    except Exception:  # noqa: BLE001 — git may be absent or misconfigured; fall back to "cli" identity
        pass
    return "cli"


def emit_mission_created_local(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str | None,
    mission_number: int | None,
    mission_type: str,
    target_branch: str,
    wp_count: int = 0,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    friendly_name: str | None = None,
    purpose_tldr: str | None = None,
    purpose_context: str | None = None,
    created_at: str | None = None,
    actor: str | None = None,
    fanout: bool = True,
) -> dict[str, Any] | None:
    """Record a local ``MissionCreated`` event for *feature_dir*.

    Idempotent on ``mission_slug``. The mission's
    ``status.events.jsonl`` is created on first call. Set ``fanout=False``
    when a transaction must finish before the returned event can be published.

    ``mission_type`` and ``wp_count`` are required by the canonical
    ``mission_created_payload`` schema (events 5.1.0). The payload schema also
    declares an optional opaque ``actor`` (events 8.0.0): when *actor* is left
    ``None`` it is resolved at emit time (git ``user.email``, else ``"cli"``,
    via :func:`_resolve_local_actor`), so mission-level moments carry WHO from
    the only emit path that remains after the sync transport was deleted
    (issue #5). Pass an explicit *actor* to pin the identity instead.
    See Priivacy-ai/spec-kitty#1199 for the full required-field surface.

    The payload is constructed via the canonical
    :func:`specify_cli.core.mission_payload.build_mission_created_payload`
    (#2270), shared with the wire emitter so the local + wire paths cannot
    drift. Producer-time validation still rejects extras / missing required
    fields (issues Priivacy-ai/spec-kitty#1198 / #1200).
    """
    from specify_cli.core.mission_payload import build_mission_created_payload

    log_path = mission_event_log_path(feature_dir)

    payload = build_mission_created_payload(
        mission_slug=mission_slug,
        target_branch=target_branch,
        mission_type=mission_type,
        wp_count=wp_count,
        mission_id=mission_id,
        mission_number=mission_number,
        friendly_name=friendly_name,
        purpose_tldr=purpose_tldr,
        purpose_context=purpose_context,
        created_at=created_at,
        actor=actor if actor else _resolve_local_actor(),
    )

    persist = append_lifecycle_event if fanout else persist_lifecycle_event_local
    return persist(
        log_path,
        MISSION_CREATED,
        payload,
        aggregate_id=mission_id or mission_slug,
        aggregate_type="Mission",
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys={"mission_slug": mission_slug},
        mission_slug=mission_slug,
    )


def emit_artifact_phase_local(
    feature_dir: Path,
    *,
    event_type: str,
    mission_slug: str,
    mission_number: int | None = None,
    actor: str = "cli",
    artifact_path: str | None = None,
    summary: str | None = None,
    wp_count: int | None = None,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    at: str | None = None,
) -> dict[str, Any] | None:
    """Persist a Specify/Plan/Tasks phase locally without hosted fan-out.

    Started and completed events dedupe on
    ``(event_type, mission_slug, artifact_path)`` when an artifact path is
    known, falling back to ``(event_type, mission_slug)`` for legacy callers.
    The local log keeps ``artifact_path`` on Started events so dashboards and
    mission-creation replay know which artifact was opened.

    Started/Completed split (issues Priivacy-ai/spec-kitty#1198 / #1203
    "dormant mask"): the canonical pydantic payload models in
    ``spec_kitty_events.project_lifecycle`` declare ``extra="forbid"``,
    so ``summary`` / ``wp_count`` remain Completed-only. ``artifact_path`` is
    local lifecycle metadata for Started events; the SaaS fan-out path strips
    it before strict canonical validation.
    """
    from spec_kitty_events.project_lifecycle import (
        PlanCompletedPayload,
        PlanStartedPayload,
        SpecifyCompletedPayload,
        SpecifyStartedPayload,
        TasksCompletedPayload,
        TasksStartedPayload,
    )

    _PAYLOAD_MODEL_FOR_EVENT_TYPE: dict[str, type] = {
        SPECIFY_STARTED: SpecifyStartedPayload,
        SPECIFY_COMPLETED: SpecifyCompletedPayload,
        PLAN_STARTED: PlanStartedPayload,
        PLAN_COMPLETED: PlanCompletedPayload,
        TASKS_STARTED: TasksStartedPayload,
        TASKS_COMPLETED: TasksCompletedPayload,
    }

    payload_model_cls = _PAYLOAD_MODEL_FOR_EVENT_TYPE.get(event_type)
    if payload_model_cls is None:
        raise ValueError(f"Unsupported artifact phase event_type: {event_type!r}")

    # Common fields all six payloads share.
    fields: dict[str, Any] = {
        "mission_slug": mission_slug,
        "mission_number": mission_number,
        "actor": actor,
        "at": at or now_utc_iso(),
    }
    # Completed-only fields. Passing these on Started variants is
    # rejected by ``extra="forbid"`` on the typed model — the dormant
    # mask is now closed.
    if event_type.endswith("Completed"):
        if artifact_path is not None:
            fields["artifact_path"] = artifact_path
        if summary is not None:
            fields["summary"] = summary
        if event_type == TASKS_COMPLETED and wp_count is not None:
            fields["wp_count"] = wp_count

    payload: dict[str, Any] = payload_model_cls(**fields).model_dump(mode="json", exclude_none=False)
    if event_type.endswith("Started") and artifact_path is not None:
        payload["artifact_path"] = artifact_path

    dedup: dict[str, Any] = {"mission_slug": mission_slug}
    if artifact_path is not None:
        dedup["artifact_path"] = artifact_path

    log_path = mission_event_log_path(feature_dir)
    return persist_lifecycle_event_local(
        log_path,
        event_type,
        payload,
        aggregate_id=mission_slug,
        aggregate_type="Mission",
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys=dedup,
        mission_slug=mission_slug,
    )


def emit_artifact_phase(
    feature_dir: Path,
    *,
    event_type: str,
    mission_slug: str,
    mission_number: int | None = None,
    actor: str = "cli",
    artifact_path: str | None = None,
    summary: str | None = None,
    wp_count: int | None = None,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    at: str | None = None,
) -> dict[str, Any] | None:
    """Persist and fan out a Specify/Plan/Tasks lifecycle event.

    Existing callers retain their composed local-write-plus-hosted-fan-out
    behavior. Callers with their own hosted authority decision should use
    :func:`emit_artifact_phase_local` and later submit the returned envelope
    to :func:`fanout_lifecycle_event_hosted` with the mission log path.
    """
    envelope = emit_artifact_phase_local(
        feature_dir,
        event_type=event_type,
        mission_slug=mission_slug,
        mission_number=mission_number,
        actor=actor,
        artifact_path=artifact_path,
        summary=summary,
        wp_count=wp_count,
        project_uuid=project_uuid,
        project_slug=project_slug,
        at=at,
    )
    if envelope is not None:
        fanout_lifecycle_event_hosted(
            envelope,
            log_path=mission_event_log_path(feature_dir),
        )
    return envelope


def emit_wp_created_local(
    feature_dir: Path,
    *,
    mission_slug: str,
    wp_id: str,
    wp_title: str,
    wp_path: str | None = None,
    depends_on: Iterable[str] | None = None,
    actor: str = "cli",
    mission_number: int | None = None,
    created_at: str | None = None,
    project_uuid: str | None = None,
    project_slug: str | None = None,
) -> dict[str, Any] | None:
    """Record a local ``WPCreated`` event keyed by ``(mission_slug, wp_id)``.

    Payload is constructed via the canonical
    :class:`spec_kitty_events.project_lifecycle.WPCreatedPayload` so
    schema drift is rejected at the producer boundary
    (issues Priivacy-ai/spec-kitty#1198 / #1200).
    """
    from spec_kitty_events.project_lifecycle import WPCreatedPayload

    payload_model = WPCreatedPayload(
        mission_slug=mission_slug,
        mission_number=mission_number,
        wp_id=wp_id,
        wp_title=wp_title,
        wp_path=wp_path,
        depends_on=list(depends_on or []),
        actor=actor,
        created_at=_iso_str_to_datetime(created_at) or now_utc(),
    )
    payload: dict[str, Any] = payload_model.model_dump(mode="json", exclude_none=False)

    log_path = mission_event_log_path(feature_dir)
    return append_lifecycle_event(
        log_path,
        WP_CREATED,
        payload,
        aggregate_id=wp_id,
        aggregate_type="WorkPackage",
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys={"mission_slug": mission_slug, "wp_id": wp_id},
        mission_slug=mission_slug,
    )


def emit_reviewer_self_approval(
    feature_dir: Path,
    *,
    mission_slug: str,
    wp_id: str,
    implementing_actor: str,
    intended_reviewer: str,
    failure_reason: str,
    fallback_approved: bool = True,
    project_uuid: str | None = None,
    project_slug: str | None = None,
    at: str | None = None,
) -> dict[str, Any] | None:
    """Record that a WP was approved by its implementing actor after reviewer failure."""
    payload = {
        "mission_slug": mission_slug,
        "wp_id": wp_id,
        "implementing_actor": implementing_actor,
        "intended_reviewer": intended_reviewer,
        "failure_reason": failure_reason,
        "fallback_approved": fallback_approved,
        "timestamp": at or now_utc_iso(),
    }
    log_path = mission_event_log_path(feature_dir)
    return append_lifecycle_event(
        log_path,
        REVIEWER_SELF_APPROVAL,
        payload,
        aggregate_id=wp_id,
        aggregate_type="WorkPackage",
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys={
            "mission_slug": mission_slug,
            "wp_id": wp_id,
            "implementing_actor": implementing_actor,
            "intended_reviewer": intended_reviewer,
            "failure_reason": failure_reason,
        },
        mission_slug=mission_slug,
    )


def _require_mission_completed(feature_dir: Path, *, action: str, mission_slug: str) -> None:
    """Fail-closed guard: raise unless the mission has reached completion (#1926).

    Lazy-imports :func:`is_mission_completed` to avoid a circular import
    (``lifecycle`` imports event-type constants from this module).
    """
    from specify_cli.status.lifecycle import is_mission_completed  # noqa: PLC0415

    if not is_mission_completed(feature_dir):
        raise MissionNotCompletedError(action, mission_slug)


def emit_mission_reopened(
    feature_dir: Path,
    *,
    mission_id: str,
    mission_slug: str,
    reason: str,
    reopened_by: str,
    cleared_merge: Mapping[str, Any] | None = None,
    reopened_at: str | None = None,
    project_uuid: str | None = None,
    project_slug: str | None = None,
) -> dict[str, Any] | None:
    """Record that a merged/closed mission was returned to an actionable state.

    Appended *each* time (every re-open is a distinct fact — NOT deduped, per
    research.md R-A2). ``derive_mission_lifecycle`` treats a ``MissionReopened``
    that postdates the last merge/completion marker as the authority that makes
    the mission actionable again (FR-002). Attribution is via ``mission_id``
    (ULID, NFR-004) — never a slug-derived guess.

    ``cleared_merge`` is an optional snapshot of the ``merged_*`` fields selected
    for removal from ``meta.json`` by the IC-02 re-open command, retained for
    audit / reversibility. The command persists this replacement audit fact
    before clearing those fields, so marker-only completion remains provable
    while this canonical producer enforces its completion guard (#4870). This
    function does not itself perform or guarantee the trailing clear: if that
    later step fails, the command surfaces a structured, retryable error
    rather than this event's ``cleared_merge`` payload being an unconditional
    record of what is now on disk.

    This is a LOCAL-ONLY event (see ``MISSION_REOPENED`` registration note): it
    is intentionally kept off the SaaS strict-validation model map.

    Fail-closed (#1926): a mission can only be re-opened once it has *reached
    completion* (merged, or all WPs terminal). Re-opening a mission that never
    completed is rejected with :class:`MissionNotCompletedError` before any
    metadata or event is written. The completion check happens here — the
    canonical producer — so no emit path can bypass it.
    """
    _require_mission_completed(feature_dir, action="re-open", mission_slug=mission_slug)
    payload: dict[str, Any] = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "reason": reason,
        "reopened_by": reopened_by,
        "reopened_at": reopened_at or now_utc_iso(),
        "cleared_merge": dict(cleared_merge) if cleared_merge is not None else None,
    }
    log_path = mission_event_log_path(feature_dir)
    return append_lifecycle_event(
        log_path,
        MISSION_REOPENED,
        payload,
        aggregate_id=mission_id,
        aggregate_type="Mission",
        project_uuid=project_uuid,
        project_slug=project_slug,
        # No dedup_keys: append-each.
        mission_slug=mission_slug,
    )


def emit_follow_up_recorded(
    feature_dir: Path,
    *,
    mission_id: str,
    mission_slug: str,
    follow_up_type: str,
    commit_sha: str | None = None,
    pr_number: int | None = None,
    recorded_by: str,
    recorded_at: str | None = None,
    project_uuid: str | None = None,
    project_slug: str | None = None,
) -> dict[str, Any] | None:
    """Record a follow-up commit or PR against an already-completed mission.

    Fail-closed (#1926): a follow-up is a *post-mission* fact and is only valid
    once the mission has reached completion (merged, or all WPs terminal).
    Recording a follow-up against a mission that never completed is rejected with
    :class:`MissionNotCompletedError` before any event is written. The check
    lives here — the canonical producer — so no emit path can bypass it.

    **Idempotent** on its dedup key ``(mission_id, commit_sha | pr_number)`` —
    re-recording the identical ``--commit``/``--pr`` reference is a no-op,
    consistent with the existing ``has_lifecycle_event()`` dedup pattern. A
    commit and the PR that contains it are recorded as distinct facts (no
    resolved-commit-of-PR lookup — research.md / data-model.md).

    ``follow_up_type`` is ``"commit"`` (requires ``commit_sha``) or ``"pr"``
    (requires ``pr_number``). Attribution is via ``mission_id`` (NFR-004).

    This is a LOCAL-ONLY event (see ``FOLLOW_UP_RECORDED`` registration note).
    """
    if follow_up_type == "commit":
        if not commit_sha:
            raise ValueError("commit_sha is required when follow_up_type == 'commit'")
        dedup_keys: dict[str, Any] = {"mission_id": mission_id, "commit_sha": commit_sha}
    elif follow_up_type == "pr":
        if pr_number is None:
            raise ValueError("pr_number is required when follow_up_type == 'pr'")
        dedup_keys = {"mission_id": mission_id, "pr_number": pr_number}
    else:
        raise ValueError(f"follow_up_type must be 'commit' or 'pr', got {follow_up_type!r}")

    _require_mission_completed(feature_dir, action="record follow-up", mission_slug=mission_slug)

    payload: dict[str, Any] = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "follow_up_type": follow_up_type,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
        "recorded_by": recorded_by,
        "recorded_at": recorded_at or now_utc_iso(),
    }
    log_path = mission_event_log_path(feature_dir)
    return append_lifecycle_event(
        log_path,
        FOLLOW_UP_RECORDED,
        payload,
        aggregate_id=mission_id,
        aggregate_type="Mission",
        project_uuid=project_uuid,
        project_slug=project_slug,
        dedup_keys=dedup_keys,
        mission_slug=mission_slug,
    )


# ---------------------------------------------------------------------------
# Diagnostics / merge guard helpers
# ---------------------------------------------------------------------------


def read_lifecycle_events(log_path: Path) -> list[dict[str, Any]]:
    """Public read-only accessor for the lifecycle log (skips malformed lines)."""
    return _read_lifecycle_lines(log_path)


def _iter_status_event_objects(text: str) -> Iterable[dict[str, Any]]:
    """Yield reducer-style status events from raw mission log text."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "event_type" not in obj:
            yield obj


def _is_bootstrap_status_event(obj: Mapping[str, Any]) -> bool:
    """Return True when the reducer event is a canonical bootstrap seed.

    Post-FSM (#1775 review M6) the canonical seed is ``genesis -> planned`` with
    ``force=False`` (``genesis -> planned`` is a real allowed edge, so finalize no
    longer forces it). The legacy forced ``planned -> planned`` seed is still
    recognised so historical event logs keep classifying correctly.
    """
    to_lane = obj.get("to_lane")
    if to_lane != "planned":
        return False
    from_lane = obj.get("from_lane")
    if from_lane == _Lane.GENESIS:
        return True
    # Legacy forced bootstrap seed (pre-FSM): planned -> planned with force=True.
    return bool(obj.get("force")) and from_lane in (None, "planned")


def has_non_bootstrap_status_history(feature_dir: Path) -> bool:
    """Return True when the mission status log contains a non-bootstrap event.

    Bootstrap-only history is the pathological state described in
    issue #1069: the canonical event log contains only forced
    ``planned -> planned`` events emitted by ``finalize-tasks`` even
    though work packages have advanced past planned on the local
    filesystem. This helper reads ``status.events.jsonl`` directly
    (without invoking the status reducer) so it can be used as a
    cheap pre-merge guard.
    """
    log_path = mission_event_log_path(feature_dir)
    if not log_path.exists():
        return False
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for obj in _iter_status_event_objects(text):
        to_lane = obj.get("to_lane")
        if to_lane != "planned":
            return True
        if _is_bootstrap_status_event(obj):
            # Bootstrap planned event — skip.
            continue
        # Non-bootstrap planned event (e.g. legitimate planned -> planned
        # repair with a non-None from_lane mismatch is unreachable but
        # treat any other planned event defensively as real history).
        return True
    return False


__all__ = [
    "PROJECT_INITIALIZED",
    "MISSION_CREATED",
    "SPECIFY_STARTED",
    "SPECIFY_COMPLETED",
    "PLAN_STARTED",
    "PLAN_COMPLETED",
    "TASKS_STARTED",
    "TASKS_COMPLETED",
    "WP_CREATED",
    "REVIEWER_SELF_APPROVAL",
    "MISSION_REOPENED",
    "FOLLOW_UP_RECORDED",
    "LIFECYCLE_EVENT_TYPES",
    "AUTHORITATIVE_NON_LANE_EVENT_TYPES",
    "is_authoritative_non_lane_event_type",
    "PROJECT_EVENTS_FILENAME",
    "MISSION_EVENTS_FILENAME",
    "project_event_log_path",
    "mission_event_log_path",
    "fanout_lifecycle_event_hosted",
    "append_lifecycle_event",
    "has_lifecycle_event",
    "emit_project_initialized",
    "emit_mission_created_local",
    "emit_artifact_phase_local",
    "emit_artifact_phase",
    "emit_wp_created_local",
    "emit_reviewer_self_approval",
    "emit_mission_reopened",
    "emit_follow_up_recorded",
    "read_lifecycle_events",
    "has_non_bootstrap_status_history",
    "repo_root_for_lifecycle_log",
    "build_saas_lifecycle_queue_event",
]
