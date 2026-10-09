"""Shape registry: known top-level keys per artifact type.

Defines ``KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT`` — a mapping from artifact type
name to the set of top-level keys that are expected in that artifact type.

``check_unknown_keys()`` uses this registry to emit ``UNKNOWN_SHAPE`` findings
for any top-level key that is not in the known set, not a legacy key, and not
a forbidden key (those have dedicated finding codes).

Also exposes row-family classifiers for mixed ``status.events.jsonl`` rows.
The audit engine uses these predicates to scope status-transition-only
``FORBIDDEN_KEYS`` checks away from legitimate lifecycle and DecisionPoint
event envelopes while still flagging malformed transition rows.

Reference: ``kitty-specs/unblock-sync-identity-boundary-canary-01KRZJ07/
contracts/audit-row-family.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from specify_cli.mission_metadata import MissionMetaOptional, MissionMetaRequired
from specify_cli.meta_keys import COORDINATION_KEYS, IDENTITY_KEYS

from .detectors import FORBIDDEN_KEYS, LEGACY_KEYS
from .models import MissionFinding, Severity

# ---------------------------------------------------------------------------
# meta.json known-key set — DERIVED from the canonical writer schema (C-005 /
# FR-011), never a hand-maintained second copy. A hand-rolled frozenset drifted
# from the writer and reported canonical coordination keys
# (``coordination_branch`` / ``topology`` / ``flattened`` / ``pr_bound``) as
# ``UNKNOWN_SHAPE`` false positives (#2696). Three canonical sources compose it:
#
#   1. The mission-metadata writer TypedDicts (``MissionMetaRequired`` +
#      ``MissionMetaOptional`` in ``specify_cli.mission_metadata``) — the single
#      source of truth for the field set ``write_meta`` persists.
#   2. The coordination write-path keys from ``specify_cli.meta_keys``, shared
#      by create, migration and flatten writers.
#   3. The identity keys from that same module, shared by create and backfill.
#
# ``tests/audit/test_shape_registry_writer_parity.py`` asserts the writer keys
# stay a subset of this set, so the two can never re-drift (NFR-004).
# ---------------------------------------------------------------------------

#: Coordination write-path keys — persisted to ``meta.json`` by the coordination
#: topology/flatten primitives and the branch-strategy ``pr_bound`` write-back.
META_COORDINATION_KEYS: frozenset[str] = COORDINATION_KEYS

#: Canonical identity keys (identity model 083+), minted at mission create and
#: not part of the ``MissionMeta*`` writer TypedDicts.
_META_IDENTITY_KEYS: frozenset[str] = IDENTITY_KEYS

#: Every field the canonical mission-metadata writer persists.
_META_WRITER_KEYS: frozenset[str] = frozenset(
    MissionMetaRequired.__annotations__
) | frozenset(MissionMetaOptional.__annotations__)

_META_KNOWN_KEYS: frozenset[str] = (
    _META_WRITER_KEYS | META_COORDINATION_KEYS | _META_IDENTITY_KEYS
)

# ---------------------------------------------------------------------------
# Known key sets per artifact type
# ---------------------------------------------------------------------------

KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT: dict[str, frozenset[str]] = {
    "meta.json": _META_KNOWN_KEYS,
    "status.json": frozenset(
        {
            "mission_slug",
            "feature_slug",  # back-compat alias
            "mission_number",
            "mission_type",
            "materialized_at",
            "event_count",
            "last_event_id",
            "work_packages",
            "summary",
            "retrospective",
        }
    ),
    "status_event_row": frozenset(
        {
            "actor",
            "at",
            "event_id",
            "evidence",
            "execution_mode",
            "feature_slug",
            "force",
            "from_lane",
            "reason",
            "review_ref",
            # Structured review verdict (FR-014): the reducer projects
            # ``StatusEvent.review_result`` (status/models.py) and the writer
            # serializes it onto the row, so a persisted status_event_row
            # legitimately carries this key. Optional/nullable — matching the
            # reducer's override-or-carry-forward semantics — so its absence on
            # a non-review transition is not a violation.
            "review_result",
            "to_lane",
            "wp_id",
            "mission_id",
            "mission_slug",
            "policy_metadata",
            # skip rows (legacy discriminator keys — present in some old rows):
            "event_type",
            "event_name",
        }
    ),
    "mission_lifecycle_row": frozenset(
        {
            "aggregate_id",
            "aggregate_type",
            "event_id",
            "event_type",
            "payload",
            "project_slug",
            "project_uuid",
            "schema_version",
            "timestamp",
        }
    ),
    "wp_frontmatter": frozenset(
        {
            "work_package_id",
            "title",
            "dependencies",
            "subtasks",
            "execution_mode",
            "owned_files",
            "authoritative_surface",
            "planning_base_branch",
            "merge_target_branch",
            "branch_strategy",
            "agent_profile",
            "role",
            "agent",
            "model",
            "history",
            "requirement_refs",
            "tracker_refs",
            # older shapes:
            "id",
            "status",
            "lane",
            "actor",
            "evidence",
            "review_ref",
            "reason",
            "force",
            "depends_on",
            # newer fields (083+):
            "tags",
        }
    ),
    # mission-events.jsonl rows (MissionNextInvoked and similar mission-level events)
    "mission_event_row": frozenset(
        {
            "mission",
            "payload",
            "timestamp",
            "type",
            # event_type-based rows (alternate schema)
            "event_type",
            "at",
            "event_id",
        }
    ),
    # decisions/events.jsonl rows (DecisionPoint* events)
    "decision_event_row": frozenset(
        {
            "at",
            "event_id",
            "event_type",
            "payload",
            "timestamp",
            "type",
        }
    ),
    # handoff/events.jsonl rows (handoff lane-transition-style events)
    "handoff_event_row": frozenset(
        {
            "actor",
            "at",
            "event_id",
            "evidence",
            "execution_mode",
            "feature_slug",
            "force",
            "from_lane",
            "mission_id",
            "mission_slug",
            "policy_metadata",
            "reason",
            "review_ref",
            "to_lane",
            "wp_id",
        }
    ),
}


# ---------------------------------------------------------------------------
# Row-family classifiers
# ---------------------------------------------------------------------------

# Aggregate types that legitimately carry the ``event_type`` discriminator.
# Issue #1142: the original predicate accepted only ``"Mission"``, which
# mis-classified ``Project``, ``WorkPackage``, and ``MissionDossier``
# lifecycle rows emitted by the events package as malformed
# status-transition rows. The audit engine then raised ``FORBIDDEN_KEY``
# findings against legitimate lifecycle keys (``event_type``,
# ``aggregate_type``), blocking canary scenarios 1 + 2 with
# ``TeamSpace migration required. Finding codes: FORBIDDEN_KEY``.
LIFECYCLE_AGGREGATE_TYPES: frozenset[str] = frozenset(
    {"Mission", "Project", "WorkPackage", "MissionDossier"}
)
STATUS_TRANSITION_DISCRIMINATORS: frozenset[str] = frozenset({"from_lane", "to_lane"})
DECISIONPOINT_STATUS_EVENT_KEYS: frozenset[str] = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT[
    "decision_event_row"
]


def is_mission_lifecycle_row(row: Mapping[str, Any]) -> bool:
    """Return ``True`` iff *row* matches the lifecycle event-row family.

    Lifecycle rows are written by ``status/lifecycle_events.py`` (and its
    peers) into ``status.events.jsonl``. They carry the lifecycle
    discriminator ``event_type`` (e.g. ``"MissionCreated"``,
    ``"SpecifyStarted"``, ``"WPStatusChanged"``) and identify the aggregate
    via ``aggregate_type`` set to one of
    ``{"Mission", "Project", "WorkPackage", "MissionDossier"}``. It must
    also avoid status-transition discriminators (``from_lane`` / ``to_lane``).
    These predicates keep the ``FORBIDDEN_KEYS`` audit rule effective against
    malformed status-transition rows that carry lifecycle-looking keys.

    Issue #1142 broadened the accepted ``aggregate_type`` set beyond the
    original ``"Mission"``-only check. The events package legitimately
    emits ``Project``/``WorkPackage``/``MissionDossier`` lifecycle rows
    and the audit must not flag those as forbidden-key violations.

    Args:
        row: A parsed JSONL row (typically from ``status.events.jsonl``).

    Returns:
        ``True`` when *row* is a lifecycle row; ``False`` otherwise
        (including for non-mapping inputs, which are conservatively
        rejected, for rows whose ``aggregate_type`` is absent, empty, or outside
        the known lifecycle set, and for hybrid rows that also carry transition
        discriminators).

    Reference:
        ``kitty-specs/unblock-sync-identity-boundary-canary-01KRZJ07/
        contracts/audit-row-family.md``.
    """
    if not isinstance(row, Mapping):
        return False
    if STATUS_TRANSITION_DISCRIMINATORS.intersection(row):
        return False
    aggregate_type = row.get("aggregate_type")
    if aggregate_type not in LIFECYCLE_AGGREGATE_TYPES:
        return False
    event_type = row.get("event_type")
    return isinstance(event_type, str) and bool(event_type)


def is_decisionpoint_status_event_row(row: Mapping[str, Any]) -> bool:
    """Return ``True`` iff *row* matches a DecisionPoint event envelope.

    Decision Moment producers append DecisionPoint events to
    ``status.events.jsonl`` with ``{event_id, at, event_type, payload}``.
    These rows are mission-level events, not lane-transition rows, and match
    the same skip boundary used by ``status.store.read_events()``.
    """
    if not isinstance(row, Mapping):
        return False
    if not set(row).issubset(DECISIONPOINT_STATUS_EVENT_KEYS):
        return False
    event_type = row.get("event_type")
    if not (isinstance(event_type, str) and event_type.startswith("DecisionPoint")):
        return False
    return isinstance(row.get("payload"), Mapping)


def status_event_row_artifact_type(row: Mapping[str, Any]) -> str:
    """Return the shape registry artifact type for a ``status.events.jsonl`` row."""
    if is_mission_lifecycle_row(row):
        return "mission_lifecycle_row"
    if is_decisionpoint_status_event_row(row):
        return "decision_event_row"
    return "status_event_row"


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


def check_unknown_keys(
    artifact_type: str,
    obj: dict[str, object],
    artifact_path: str,
) -> list[MissionFinding]:
    """Return ``UNKNOWN_SHAPE`` findings for unrecognised top-level keys.

    A key is considered *unknown* when it is:
    - not in ``KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT[artifact_type]``, AND
    - not in ``LEGACY_KEYS`` (those emit ``LEGACY_KEY`` findings), AND
    - not in ``FORBIDDEN_KEYS`` (those emit ``FORBIDDEN_KEY`` findings).

    If *artifact_type* is not in ``KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT``, the
    function returns an empty list — an unregistered artifact type is not
    itself an error.

    Args:
        artifact_type: One of the keys in ``KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT``
            (e.g. ``"meta.json"``, ``"status_event_row"``).
        obj: Parsed artifact dict whose top-level keys are inspected.
        artifact_path: Relative path to the artifact for finding records.

    Returns:
        A list of :class:`~specify_cli.audit.models.MissionFinding` objects
        with code ``"UNKNOWN_SHAPE"`` and severity ``INFO``.
    """
    known = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT.get(artifact_type)
    if known is None:
        return []

    findings: list[MissionFinding] = []
    for key in obj:
        if key not in known and key not in LEGACY_KEYS and key not in FORBIDDEN_KEYS:
            findings.append(
                MissionFinding(
                    code="UNKNOWN_SHAPE",
                    severity=Severity.INFO,
                    artifact_path=artifact_path,
                    detail=f"unknown key: {key!r} (artifact_type={artifact_type!r})",
                )
            )
    return findings
