"""Classifier for status.json mission artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from ..detectors import detect_legacy_keys
from ..models import MissionFinding, Severity
from ..shape_registry import check_unknown_keys
from ._details import format_exception_detail


def classify_status_json(
    mission_dir: Path,
    *,
    skip_drift: bool = False,
) -> list[MissionFinding]:
    """Classify status.json for legacy keys, unknown keys, and snapshot drift.

    The drift check is read-only: it uses ``materialize_to_json`` (which
    produces a deterministic string without writing any file) rather than
    ``materialize`` (which writes status.json to disk).  When
    ``skip_drift=True`` the drift check is skipped entirely — the engine
    passes this flag when ``status.events.jsonl`` has corruption that would
    cause the reducer to raise.

    Args:
        mission_dir: Path to the mission directory.
        skip_drift: If True, skip the snapshot drift check.

    Returns:
        A list of :class:`~specify_cli.audit.models.MissionFinding` objects.
        Never raises — all exceptions become findings.
    """
    path = mission_dir / "status.json"
    if not path.exists():
        return []

    findings: list[MissionFinding] = []

    try:
        raw_text = path.read_text(encoding="utf-8")
        obj = json.loads(raw_text)
    except OSError as exc:
        return [
            MissionFinding(
                code="CORRUPT_JSON",
                severity=Severity.ERROR,
                artifact_path="status.json",
                detail=f"could not read file: {format_exception_detail(exc)}",
            )
        ]
    except json.JSONDecodeError as exc:
        return [
            MissionFinding(
                code="CORRUPT_JSON",
                severity=Severity.ERROR,
                artifact_path="status.json",
                detail=f"JSON decode error: {exc.msg}",
            )
        ]

    if not isinstance(obj, dict):
        return [
            MissionFinding(
                code="CORRUPT_JSON",
                severity=Severity.ERROR,
                artifact_path="status.json",
                detail="top-level JSON value must be an object",
            )
        ]

    # Legacy key detection
    findings.extend(detect_legacy_keys(obj, "status.json"))

    # Unknown key detection
    findings.extend(check_unknown_keys("status.json", obj, "status.json"))

    if skip_drift:
        return findings

    # Read-only drift check (C-001 compliance).
    # NEVER call reducer.materialize() — it writes status.json to disk.
    # materialize_snapshot() keeps parity with materialize() without writing.
    try:
        from specify_cli.status import materialize_snapshot, materialize_to_json

        snapshot = materialize_snapshot(mission_dir)
        computed_json = materialize_to_json(snapshot)
    except Exception as exc:
        findings.append(
            MissionFinding(
                code="SNAPSHOT_DRIFT",
                severity=Severity.ERROR,
                artifact_path="status.json",
                detail=(f"reducer raised during drift check: {format_exception_detail(exc)}"),
            )
        )
        return findings

    # Normalise both sides: parse + re-serialise with identical options
    try:
        persisted_normalised = (
            json.dumps(
                json.loads(raw_text),
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
    except Exception:
        # raw_text is already parsed above, so this branch is unreachable in practice
        persisted_normalised = raw_text

    if computed_json != persisted_normalised:
        if _is_provenance_only_drift(computed_json, persisted_normalised):
            findings.append(
                MissionFinding(
                    code="SNAPSHOT_DRIFT_PROVENANCE",
                    severity=Severity.WARNING,
                    artifact_path="status.json",
                    detail=(
                        "reducer output differs from persisted status.json only "
                        "in per-work-package provenance fields (actor, "
                        "last_event_id, last_transition_at); a reducer-version "
                        "change re-attributed provenance without altering "
                        "lane/outcome state, so this drift is not an actionable "
                        "TeamSpace-readiness problem — an active mission's "
                        "snapshot self-heals on the next materialize, and an "
                        "archived mission's is frozen by the archive gate"
                    ),
                )
            )
        elif _is_terminal_snapshot(computed_json):
            findings.append(
                MissionFinding(
                    code="SNAPSHOT_DRIFT_TERMINAL",
                    severity=Severity.WARNING,
                    artifact_path="status.json",
                    detail=(
                        "a completed mission's frozen status.json no longer matches "
                        "the current reducer output, but every work package is "
                        "'done' and the dossier is immutable (the archive gate "
                        "forbids editing it), so this drift is not an actionable "
                        "TeamSpace-readiness problem"
                    ),
                )
            )
        else:
            findings.append(
                MissionFinding(
                    code="SNAPSHOT_DRIFT",
                    severity=Severity.ERROR,
                    artifact_path="status.json",
                    detail="reducer output does not match persisted status.json",
                )
            )

    return findings


_PROVENANCE_ONLY_WP_FIELDS = frozenset({"actor", "last_event_id", "last_transition_at"})


def _is_provenance_only_drift(computed_json: str, persisted_json: str) -> bool:
    """Return True iff ``computed_json`` and ``persisted_json`` (both already
    normalised, deterministic JSON strings) differ *only* in the per-work-package
    provenance fields ``actor``, ``last_event_id``, and ``last_transition_at`` --
    the shape a reducer-version change produces when it re-attributes WHO/WHEN a
    transition happened without altering WHAT happened (lane, counts, summary,
    or any other field).

    Returns False (not provenance-only, so the caller must not tolerate the
    drift) when:
    - any top-level field other than ``work_packages`` differs,
    - the set of work-package IDs differs (an added/removed WP is a real
      membership change, not a provenance re-attribution),
    - any single work package differs in a field outside the provenance triple,
    - or there turns out to be no difference at all (defensive; the caller only
      invokes this after confirming ``computed_json != persisted_json``).
    """
    computed = json.loads(computed_json)
    persisted = json.loads(persisted_json)
    if not isinstance(computed, dict) or not isinstance(persisted, dict):
        return False

    computed_other = {k: v for k, v in computed.items() if k != "work_packages"}
    persisted_other = {k: v for k, v in persisted.items() if k != "work_packages"}
    if computed_other != persisted_other:
        return False

    computed_wps = computed.get("work_packages", {})
    persisted_wps = persisted.get("work_packages", {})
    if not isinstance(computed_wps, dict) or not isinstance(persisted_wps, dict):
        return False
    if set(computed_wps) != set(persisted_wps):
        return False

    saw_a_difference = False
    for wp_id, computed_wp in computed_wps.items():
        persisted_wp = persisted_wps[wp_id]
        if not isinstance(computed_wp, dict) or not isinstance(persisted_wp, dict):
            return False
        diff_keys = {key for key in set(computed_wp) | set(persisted_wp) if computed_wp.get(key) != persisted_wp.get(key)}
        if not diff_keys:
            continue
        if not diff_keys <= _PROVENANCE_ONLY_WP_FIELDS:
            return False
        saw_a_difference = True

    return saw_a_difference


def _is_terminal_snapshot(computed_json: str) -> bool:
    """Return True when every work package in the authoritative reducer
    output (``computed_json``, from ``materialize_to_json``) has reached the
    terminal ``done`` lane.

    A mission with no work packages at all is not considered terminal —
    an empty ``work_packages`` mapping usually means the reducer could not
    reconstruct any state (e.g. an empty or absent event log), which is an
    active/unfixable-by-regeneration case, not a completed one.
    """
    work_packages = json.loads(computed_json).get("work_packages", {})
    if not isinstance(work_packages, dict) or not work_packages:
        return False
    return all(isinstance(wp, dict) and wp.get("lane") == "done" for wp in work_packages.values())
