"""Lifecycle gate: single source of truth for mission completion decisions.

AD-001 / Q1-C: the gate decides whether a mission is allowed to transition
to ``done``. Both ``runtime.next`` and any status-transition surface that
ever needs mission-level mode policy MUST consult this module.

Source-of-truth contracts:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/gate_api.md
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/data-model.md
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from charter.bundle import CHARTER_MD
from specify_cli.retrospective.events import RETROSPECTIVE_EVENT_NAMES
from specify_cli.retrospective.mode import detect as _detect_mode
from specify_cli.retrospective.schema import EventId, MissionId, Mode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typed error hierarchy (never silently converted to allow_completion=True)
# ---------------------------------------------------------------------------


class GateError(Exception):
    """Base class for lifecycle gate errors."""


class MissionIdentityMissing(GateError):
    """Raised when mission_id is empty or cannot be resolved."""


class EventLogUnreadable(GateError):
    """Raised when status.events.jsonl cannot be read or parsed."""


# ---------------------------------------------------------------------------
# GateReason / GateDecision — data model per data-model.md
# ---------------------------------------------------------------------------


class GateReason(BaseModel):
    """Reason for the gate's decision.

    ``code`` is one of the eight discriminants from the decision matrix.
    ``blocking_event_ids`` carries the ULID event_ids that drove a blocking
    decision (empty for allow decisions).
    ``charter_clause_ref`` is set when a charter clause is the authoritative
    source (either allowing or blocking).
    """

    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "completed_present",
        "skipped_permitted",
        "completed_present_hic",
        "missing_completion_autonomous",
        "silent_skip_attempted",
        "silent_auto_run_attempted",
        "charter_override_blocks",
        "facilitator_failure",
    ]
    detail: str
    blocking_event_ids: list[EventId] = Field(default_factory=list)
    charter_clause_ref: str | None = None


class GateDecision(BaseModel):
    """Return type of ``is_completion_allowed``.

    Deterministic: same event log + same mode signals → same GateDecision.
    (NFR-008)
    """

    model_config = ConfigDict(extra="forbid")

    allow_completion: bool
    mode: Mode
    reason: GateReason


# ---------------------------------------------------------------------------
# Charter autonomous-skip override (T022)
# ---------------------------------------------------------------------------

# Expected charter clause shape (for charter authors — also documented in WP12 ADR):
#
#   The charter markdown at ``.kittify/charter/charter.md`` may include the
#   frontmatter key ``autonomous_allow_skip`` to authorize operator-skip in
#   autonomous mode.  Example:
#
#     ---
#     mode: autonomous
#     autonomous_allow_skip: "mode-policy:autonomous-allow-skip"
#     ---
#
#   When this key is present and non-empty, its value is treated as the
#   clause id.  The gate returns ``allow=True`` with ``reason.code =
#   "skipped_permitted"`` and ``reason.charter_clause_ref`` set to that id.
#
#   Without this key, any ``retrospective.skipped`` event in autonomous mode
#   is treated as a silent skip and blocks completion (``silent_skip_attempted``).

# FR-005c note (``doctrine-charter-split-unification``): retrospective *policy*
# resolution flipped yaml-first (``charter.yaml`` ``governance.retrospective``,
# see ``policy.resolve_policy``).  ``autonomous_allow_skip`` is deliberately NOT
# part of that flip — like ``mode:`` it is a top-level frontmatter key with no
# counterpart in ``charter.activation.schemas.RetrospectiveGovernance`` (whose keys mirror
# ``policy._KNOWN_KEYS`` exactly), so giving it a ``governance`` home is a schema
# change (FR-005a scope), not a resolver change.  What WP06 T003 does collapse is
# the path constant: this module imports ``charter.bundle.CHARTER_MD`` directly
# (#3163) instead of redeclaring the literal or reaching into a sibling
# module's private alias.
_AUTONOMOUS_ALLOW_SKIP_KEY = "autonomous_allow_skip"


def _charter_authorizes_autonomous_skip(repo_root: Path) -> str | None:
    """Return the charter clause id authorizing autonomous-skip, or None.

    Reads ``.kittify/charter/charter.md`` and looks for the frontmatter key
    ``autonomous_allow_skip``.  If present and non-empty, its value is the
    clause id that permits operator-authorized skip in autonomous mode.

    Returns ``None`` if:
    - The charter file does not exist.
    - The charter has no YAML frontmatter block (no leading ``---``).
    - The frontmatter does not contain ``autonomous_allow_skip``.
    - Any error occurs reading or parsing the charter.

    Never raises; any error is logged at DEBUG level so the gate falls
    through to the default blocking behaviour.
    """
    charter_path = repo_root / CHARTER_MD
    if not charter_path.exists():
        return None

    try:
        raw = charter_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not read charter at %s: %s", charter_path, exc)
        return None

    if not raw.startswith("---"):
        return None

    lines = raw.splitlines()
    close_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break

    if close_idx is None:
        return None

    frontmatter_text = "\n".join(lines[1:close_idx])

    try:
        from ruamel.yaml import YAML as _YAML  # noqa: PLC0415

        yaml = _YAML(typ="safe")
        data = yaml.load(frontmatter_text)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not parse charter frontmatter: %s", exc)
        return None

    if not isinstance(data, dict):
        return None

    clause_value = data.get(_AUTONOMOUS_ALLOW_SKIP_KEY)
    if clause_value is None:
        return None

    clause_str = str(clause_value).strip()
    return clause_str if clause_str else None


# ---------------------------------------------------------------------------
# Event log reader
# ---------------------------------------------------------------------------


def _resolve_events_path(*, feature_dir: Path, repo_root: Path) -> Path:
    """Resolve the canonical ``status.events.jsonl`` path (FR-009 / #1735).

    Under coordination topology the authoritative event log lives in the
    coordination worktree, NOT in the primary checkout's feature dir — the
    passed ``feature_dir`` is identity-only. Reading events through it
    directly is exactly the #1735 split-brain bug class, so the gate routes
    the read through the single canonical surface resolver
    (:func:`specify_cli.coordination.surface_resolver.resolve_status_surface`,
    C-005). Falls back to the passed ``feature_dir`` only when the surface
    cannot be resolved (e.g. ``meta.json`` absent for a legacy/test mission).
    """
    # Imported lazily to keep the retrospective package importable without
    # dragging in the coordination package at module-import time (mirrors
    # the lazy-import convention used by status.aggregate for this resolver).
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415
        resolve_status_surface,
    )

    try:
        surface: Path = resolve_status_surface(repo_root, feature_dir.name)
    except (FileNotFoundError, ValueError):
        return feature_dir / "status.events.jsonl"
    return surface


def _read_retrospective_events(events_path: Path) -> list[dict[str, object]]:
    """Read status.events.jsonl and return only retrospective events.

    Args:
        events_path: Path to ``status.events.jsonl``.

    Returns:
        List of event envelope dicts whose ``event_name`` is in
        :data:`~specify_cli.retrospective.events.RETROSPECTIVE_EVENT_NAMES`.
        Returns an empty list if the file does not exist.

    Raises:
        EventLogUnreadable: if the file exists but cannot be read or a
            line cannot be parsed as JSON.
    """
    if not events_path.exists():
        return []

    try:
        raw_text = events_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EventLogUnreadable(
            f"Cannot read event log at {events_path}: {exc}"
        ) from exc

    retro_events: list[dict[str, object]] = []
    for lineno, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise EventLogUnreadable(
                f"Malformed JSON on line {lineno} of {events_path}: {exc}"
            ) from exc
        if not isinstance(obj, dict):
            continue
        event_name = obj.get("event_name", "")
        if event_name in RETROSPECTIVE_EVENT_NAMES:
            retro_events.append(obj)

    return retro_events


# ---------------------------------------------------------------------------
# Terminal event resolution
# ---------------------------------------------------------------------------

# Terminal retrospective events that drive the gate outcome.
_TERMINAL_RETRO_EVENTS: frozenset[str] = frozenset(
    {
        "retrospective.completed",
        "retrospective.skipped",
        "retrospective.failed",
    }
)


def _sort_key(event: dict[str, object]) -> tuple[str, str]:
    """Sort key for events: (at, event_id) — both ISO-8601/ULID sort correctly."""
    return (str(event.get("at", "")), str(event.get("event_id", "")))


def _latest_terminal_event(
    events: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the latest terminal retrospective event.

    Ordered by ``at`` timestamp (lexicographic ISO-8601 UTC), with ``event_id``
    ULID as a deterministic tiebreak.
    """
    terminal = [e for e in events if e.get("event_name") in _TERMINAL_RETRO_EVENTS]
    return max(terminal, key=_sort_key) if terminal else None


# ---------------------------------------------------------------------------
# Silent auto-run predicate (T023)
# ---------------------------------------------------------------------------


def _is_silent_auto_run(
    completed_event: dict[str, object],
    events: list[dict[str, object]],
) -> bool:
    """Return True if the completed event lacks a verifiable operator-driven request.

    A ``retrospective.completed`` event is "silent" in HiC mode unless the
    log carries a preceding ``retrospective.requested`` event whose top-level
    ``actor.kind`` is anything other than ``"runtime"`` (i.e., an operator).

    The gate finds the latest ``retrospective.requested`` event whose ``at``
    timestamp is at or before the completed event's ``at`` timestamp.

    Fail-closed semantics: when there is no preceding requested event — or
    when the requested event's actor is malformed or is ``"runtime"`` — the
    predicate returns ``True``. Missing provenance MUST NOT pass the gate;
    HiC completion requires positive evidence of operator initiation.
    """
    completed_at = str(completed_event.get("at", ""))

    preceding_requested = [
        e
        for e in events
        if e.get("event_name") == "retrospective.requested"
        and str(e.get("at", "")) <= completed_at
    ]

    if not preceding_requested:
        # No preceding requested event — fail closed.
        return True

    latest_req = max(preceding_requested, key=_sort_key)

    actor = latest_req.get("actor")
    if not isinstance(actor, dict):
        # Malformed actor — cannot verify operator-driven; fail closed.
        return True

    actor_kind = str(actor.get("kind", ""))
    # Only operator-kind actors satisfy the HiC operator-driven contract.
    return actor_kind == "runtime" or actor_kind == ""


# ---------------------------------------------------------------------------
# Internal decision-matrix helpers
# ---------------------------------------------------------------------------


def _decide_autonomous(
    *,
    mode: Mode,
    events: list[dict[str, object]],
    latest: dict[str, object] | None,
    repo_root: Path,
) -> GateDecision:
    """Apply the autonomous half of the decision matrix.

    Rows covered (gate_api.md):
    - none               → block, missing_completion_autonomous
    - completed          → allow, completed_present
    - skipped (default)  → block, silent_skip_attempted
    - skipped (charter)  → allow, skipped_permitted
    - failed             → block, facilitator_failure
    """
    if latest is None:
        return GateDecision(
            allow_completion=False,
            mode=mode,
            reason=GateReason(
                code="missing_completion_autonomous",
                detail=(
                    "No retrospective terminal event found. "
                    "Autonomous mode requires retrospective.completed "
                    "before the mission can be marked done."
                ),
            ),
        )

    event_name = str(latest.get("event_name", ""))
    event_id = str(latest.get("event_id", ""))

    if event_name == "retrospective.completed":
        return GateDecision(
            allow_completion=True,
            mode=mode,
            reason=GateReason(
                code="completed_present",
                detail=(
                    "retrospective.completed event is present; "
                    "autonomous completion is allowed."
                ),
            ),
        )

    if event_name == "retrospective.skipped":
        # T022: Charter override for autonomous-skip.
        clause_id = _charter_authorizes_autonomous_skip(repo_root)
        if clause_id is not None:
            return GateDecision(
                allow_completion=True,
                mode=mode,
                reason=GateReason(
                    code="skipped_permitted",
                    detail=(
                        f"Charter clause '{clause_id}' authorizes "
                        "operator-skip in autonomous mode."
                    ),
                    charter_clause_ref=clause_id,
                ),
            )
        return GateDecision(
            allow_completion=False,
            mode=mode,
            reason=GateReason(
                code="silent_skip_attempted",
                detail=(
                    "retrospective.skipped in autonomous mode is a silent skip. "
                    "Autonomous mode does not permit skip unless the charter "
                    "authorizes it via 'autonomous_allow_skip: "
                    "mode-policy:autonomous-allow-skip' in charter frontmatter."
                ),
                blocking_event_ids=[event_id],
            ),
        )

    if event_name == "retrospective.failed":
        return GateDecision(
            allow_completion=False,
            mode=mode,
            reason=GateReason(
                code="facilitator_failure",
                detail=(
                    "retrospective.failed event present; "
                    "facilitator reported a failure."
                ),
                blocking_event_ids=[event_id],
            ),
        )

    # Defensive: unexpected terminal event name.
    return GateDecision(
        allow_completion=False,
        mode=mode,
        reason=GateReason(
            code="missing_completion_autonomous",
            detail=(
                f"Unexpected terminal event {event_name!r} in autonomous mode; "
                "retrospective.completed is required."
            ),
            blocking_event_ids=[event_id],
        ),
    )


def _decide_hic(
    *,
    mode: Mode,
    events: list[dict[str, object]],
    latest: dict[str, object] | None,
) -> GateDecision:
    """Apply the human_in_command half of the decision matrix.

    Rows covered (gate_api.md):
    - none                           → block, silent_auto_run_attempted
    - completed (operator-driven)    → allow, completed_present_hic
    - completed (runtime-driven)     → block, silent_auto_run_attempted
    - skipped                        → allow, skipped_permitted
    - failed                         → block, facilitator_failure
    """
    if latest is None:
        return GateDecision(
            allow_completion=False,
            mode=mode,
            reason=GateReason(
                code="silent_auto_run_attempted",
                detail=(
                    "No retrospective terminal event found in human_in_command mode. "
                    "The runtime must offer the retrospective to the operator "
                    "before marking the mission done."
                ),
            ),
        )

    event_name = str(latest.get("event_name", ""))
    event_id = str(latest.get("event_id", ""))

    if event_name == "retrospective.completed":
        # T023: detect silent auto-run.
        if _is_silent_auto_run(completed_event=latest, events=events):
            return GateDecision(
                allow_completion=False,
                mode=mode,
                reason=GateReason(
                    code="silent_auto_run_attempted",
                    detail=(
                        "retrospective.completed present but the upstream "
                        "retrospective.requested was emitted by actor.kind='runtime', "
                        "not an operator. Silent auto-run is blocked in "
                        "human_in_command mode."
                    ),
                    blocking_event_ids=[event_id],
                ),
            )
        return GateDecision(
            allow_completion=True,
            mode=mode,
            reason=GateReason(
                code="completed_present_hic",
                detail=(
                    "retrospective.completed present and operator-driven; "
                    "human_in_command completion is allowed."
                ),
            ),
        )

    if event_name == "retrospective.skipped":
        return GateDecision(
            allow_completion=True,
            mode=mode,
            reason=GateReason(
                code="skipped_permitted",
                detail=(
                    "retrospective.skipped present; "
                    "human_in_command mode permits explicit skip."
                ),
            ),
        )

    if event_name == "retrospective.failed":
        return GateDecision(
            allow_completion=False,
            mode=mode,
            reason=GateReason(
                code="facilitator_failure",
                detail=(
                    "retrospective.failed event present; "
                    "facilitator reported a failure."
                ),
                blocking_event_ids=[event_id],
            ),
        )

    # Defensive: unexpected terminal event name.
    return GateDecision(
        allow_completion=False,
        mode=mode,
        reason=GateReason(
            code="silent_auto_run_attempted",
            detail=(
                f"Unexpected terminal event {event_name!r} in human_in_command mode."
            ),
            blocking_event_ids=[event_id],
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_completion_allowed(
    mission_id: MissionId,
    *,
    feature_dir: Path,
    repo_root: Path,
    mode_override: Mode | None = None,
) -> GateDecision:
    """Decide whether the mission is allowed to transition to done.

    This is the single source of truth for the retrospective gate (AD-001,
    Q1-C).  Both ``runtime.next`` and any status-transition surface that
    ever needs mission-level mode policy MUST call this function.

    Decision matrix (gate_api.md):

    +-----------+------------------------------+-------+----------------------------+
    | Mode      | Latest terminal retro event  | Allow | reason.code                |
    +-----------+------------------------------+-------+----------------------------+
    | auto      | none / only requested/started| No    | missing_completion_autono… |
    | auto      | retrospective.completed      | Yes   | completed_present          |
    | auto      | retrospective.skipped        | No    | silent_skip_attempted      |
    | auto      | skipped + charter clause     | Yes   | skipped_permitted          |
    | auto      | retrospective.failed         | No    | facilitator_failure        |
    | HiC       | none                         | No    | silent_auto_run_attempted  |
    | HiC       | completed (operator-driven)  | Yes   | completed_present_hic      |
    | HiC       | completed (runtime-driven)   | No    | silent_auto_run_attempted  |
    | HiC       | retrospective.skipped        | Yes   | skipped_permitted          |
    | HiC       | retrospective.failed         | No    | facilitator_failure        |
    +-----------+------------------------------+-------+----------------------------+

    Performance (NFR-007): when ``retrospective.completed`` is present the
    gate reads at most (1) the event log filtered to retro events and (2)
    the charter file for mode.  No filesystem walk; no network IO.

    Determinism (NFR-008): same (event log content, charter content, mode
    signals, ``mode_override``) → same ``GateDecision``.

    Args:
        mission_id: Canonical ULID mission identity.  Used for logging.
        feature_dir: Path to ``kitty-specs/<slug>/`` (identity anchor only).
            The event log is resolved through the canonical status surface
            (FR-009 / #1735) — under coordination topology it lives in the
            coordination worktree, not at ``feature_dir/status.events.jsonl``.
        repo_root: Used to resolve the charter for mode detection and the
            autonomous-skip authorization check.
        mode_override: Test-only injection.  Pass ``None`` in production so
            the gate resolves mode via ``mode.detect()``.

    Returns:
        :class:`GateDecision` with ``allow_completion`` set.

    Raises:
        MissionIdentityMissing: if ``mission_id`` is empty.
        EventLogUnreadable: if the event log exists but cannot be parsed.
        specify_cli.retrospective.mode.ModeResolutionError: if mode
            resolution fails (malformed charter).
    """
    if not mission_id:
        raise MissionIdentityMissing("mission_id must be a non-empty ULID string")

    # 1. Resolve mode.
    if mode_override is not None:
        mode = mode_override
    else:
        mode = _detect_mode(repo_root=repo_root)

    logger.debug(
        "gate.is_completion_allowed: mission=%s mode=%s", mission_id, mode.value
    )

    # 2. Read event log (filtered to retrospective events only) through the
    # canonical status surface (FR-009 / #1735): under coordination topology
    # the authoritative log lives in the coord worktree, not feature_dir.
    events_path = _resolve_events_path(feature_dir=feature_dir, repo_root=repo_root)
    events = _read_retrospective_events(events_path)

    # 3. Find the latest terminal event.
    latest = _latest_terminal_event(events)

    # 4. Dispatch by mode.
    if mode.value == "autonomous":
        decision = _decide_autonomous(
            mode=mode,
            events=events,
            latest=latest,
            repo_root=repo_root,
        )
    else:
        decision = _decide_hic(mode=mode, events=events, latest=latest)

    logger.debug(
        "gate decision: allow=%s code=%s",
        decision.allow_completion,
        decision.reason.code,
    )
    return decision
