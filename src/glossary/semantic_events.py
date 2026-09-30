"""Helpers for reading glossary semantic-check events from JSONL logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "SemanticConflictRecord",
    "iter_semantic_conflicts",
    # Event-type string constants — import from here, never compare inline literals.
    "EVT_SEMANTIC_CHECK_EVALUATED",
    # EVT_SEMANTIC_CHECK_EVALUATED_LEGACY is intentionally NOT exported: it is an
    # internal compatibility constant used only within this module to handle the
    # older snake_case event shape in historical logs.
    "EVT_GLOSSARY_SENSE_UPDATED",
    "EVT_GLOSSARY_CLARIFICATION_REQUESTED",
    "EVT_GLOSSARY_CLARIFICATION_RESOLVED",
]

# ---------------------------------------------------------------------------
# Glossary event-type constants
# ---------------------------------------------------------------------------
# Canonical CamelCase form emitted by current producers and the CLI resolver.
EVT_SEMANTIC_CHECK_EVALUATED = "SemanticCheckEvaluated"
# Legacy snake_case form emitted by older test fixtures; handled in parallel with
# the canonical form during replay so historical event logs remain readable.
EVT_SEMANTIC_CHECK_EVALUATED_LEGACY = "semantic_check_evaluated"
EVT_GLOSSARY_SENSE_UPDATED = "GlossarySenseUpdated"
EVT_GLOSSARY_CLARIFICATION_REQUESTED = "GlossaryClarificationRequested"
EVT_GLOSSARY_CLARIFICATION_RESOLVED = "GlossaryClarificationResolved"

_EVENTS_DIR = Path(".kittify") / "events" / "glossary"


@dataclass(frozen=True)
class SemanticConflictRecord:
    """Normalized semantic-check conflict extracted from a glossary event log."""

    term: str
    term_id: str
    severity: str
    conflict_type: str
    conflicting_senses: list[str]
    timestamp: str | None
    resolution: str | None = None


def _event_files(repo_root: Path) -> list[Path]:
    events_dir = repo_root / _EVENTS_DIR
    if not events_dir.is_dir():
        return []
    return sorted(events_dir.glob("*.events.jsonl"))


def _matches_filter(event: dict[str, Any], invocation_id: str | None) -> bool:
    if invocation_id is None:
        return True
    candidates = {
        str(value)
        for value in (
            event.get("invocation_id"),
            event.get("step_id"),
            event.get("run_id"),
        )
        if value
    }
    return invocation_id in candidates


def _extract_term_surface(term_data: Any) -> str:
    if isinstance(term_data, dict):
        value = term_data.get("surface_text") or term_data.get("surface")
        return str(value or "").strip()
    return str(term_data or "").strip()


def _extract_term_id(term: str, finding: dict[str, Any], event: dict[str, Any]) -> str:
    for candidate in (
        finding.get("term_id"),
        event.get("term_id"),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    if term.startswith("glossary:"):
        return term
    if term:
        return f"glossary:{term}"
    return ""


def _extract_candidate_definitions(finding: dict[str, Any]) -> list[str]:
    legacy_values = finding.get("conflicting_senses")
    if isinstance(legacy_values, list):
        normalized = [str(value).strip() for value in legacy_values if str(value).strip()]
        if normalized:
            return normalized

    result: list[str] = []
    for candidate in finding.get("candidate_senses", []):
        if not isinstance(candidate, dict):
            continue
        definition = str(candidate.get("definition") or "").strip()
        surface = str(candidate.get("surface") or "").strip()
        scope = str(candidate.get("scope") or "").strip()
        if definition:
            result.append(definition)
        elif surface and scope:
            result.append(f"{surface} [{scope}]")
        elif surface:
            result.append(surface)
    return result


def _normalize_legacy_event(event: dict[str, Any]) -> list[SemanticConflictRecord]:
    term = str(event.get("term") or "").strip()
    term_id = _extract_term_id(term, event, event)
    if not term or not term_id:
        return []
    return [
        SemanticConflictRecord(
            term=term,
            term_id=term_id,
            severity=str(event.get("severity") or "").lower(),
            conflict_type=str(event.get("conflict_type") or ""),
            conflicting_senses=_extract_candidate_definitions(event),
            timestamp=str(event.get("checked_at") or event.get("timestamp") or "") or None,
            resolution=str(event.get("resolution") or "") or None,
        )
    ]


def _normalize_semantic_check_event(event: dict[str, Any]) -> list[SemanticConflictRecord]:
    records: list[SemanticConflictRecord] = []
    timestamp = str(event.get("timestamp") or event.get("checked_at") or "") or None
    for finding in event.get("findings", []):
        if not isinstance(finding, dict):
            continue
        term = _extract_term_surface(finding.get("term"))
        term_id = _extract_term_id(term, finding, event)
        if not term or not term_id:
            continue
        severity = str(
            finding.get("severity")
            or event.get("severity")
            or event.get("overall_severity")
            or ""
        ).lower()
        records.append(
            SemanticConflictRecord(
                term=term,
                term_id=term_id,
                severity=severity,
                conflict_type=str(finding.get("conflict_type") or ""),
                conflicting_senses=_extract_candidate_definitions(finding),
                timestamp=timestamp,
                resolution=str(finding.get("resolution") or "") or None,
            )
        )
    return records


def iter_semantic_conflicts(
    repo_root: Path,
    *,
    invocation_id: str | None = None,
) -> list[SemanticConflictRecord]:
    """Return normalized semantic conflicts from glossary event logs.

    Supports both the canonical ``SemanticCheckEvaluated`` schema and the
    earlier flat ``semantic_check_evaluated`` test fixture shape.
    """
    records: list[SemanticConflictRecord] = []
    for log_file in _event_files(repo_root):
        try:
            for line in log_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or not _matches_filter(event, invocation_id):
                    continue

                event_type = str(event.get("event_type") or "")
                if event_type == EVT_SEMANTIC_CHECK_EVALUATED:
                    records.extend(_normalize_semantic_check_event(event))
                elif event_type == EVT_SEMANTIC_CHECK_EVALUATED_LEGACY:
                    records.extend(_normalize_legacy_event(event))
        except OSError:
            continue
    return records
