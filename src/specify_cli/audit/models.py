"""Data models for the read-only mission-state audit engine.

This module defines the core types used throughout the audit package:
- Severity: ordered StrEnum (error < warning < info)
- MissionFinding: immutable finding record
- MissionAuditResult: per-mission audit outcome
- RepoAuditReport: full repository audit report
- AuditOptions: engine configuration
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


TEAMSPACE_BLOCKER_CODES: frozenset[str] = frozenset(
    {
        "CORRUPT_JSON",
        "CORRUPT_JSONL",
        "DUPLICATE_MISSION_ID",
        "FORBIDDEN_KEY",
        "IDENTITY_INVALID",
        "IDENTITY_MISSING",
        "LEGACY_KEY",
        "SNAPSHOT_DRIFT",
    }
)

#: A ``kitty-specs/`` child holding only untracked or gitignored residue (#5812).
#: Reported at INFO and deliberately absent from ``TEAMSPACE_BLOCKER_CODES``.
RESIDUE_DIRECTORY = "RESIDUE_DIRECTORY"

_MISSION_ROOT_DIRNAME = KITTY_SPECS_DIR


def _stable_mission_dir_for_json(mission_dir: Path, mission_slug: str) -> str:
    """Return a deterministic, installation-independent mission path."""
    if not mission_dir.is_absolute():
        return mission_dir.as_posix()

    if mission_dir.parent.name == _MISSION_ROOT_DIRNAME:
        return Path(_MISSION_ROOT_DIRNAME, mission_dir.name).as_posix()

    return mission_slug or mission_dir.name


class Severity(StrEnum):
    """Audit finding severity level.

    Ordering: error < warning < info (lower index = higher severity).
    Use ``__le__`` / ``__lt__`` for threshold comparisons, e.g.::

        if any(f.severity <= fail_on_threshold for f in findings):
            sys.exit(1)
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __le__(self, other: Severity) -> bool:  # type: ignore[override]
        _order = {"error": 0, "warning": 1, "info": 2}
        return _order[self.value] <= _order[other.value]

    def __lt__(self, other: Severity) -> bool:  # type: ignore[override]
        _order = {"error": 0, "warning": 1, "info": 2}
        return _order[self.value] < _order[other.value]


@dataclass(frozen=True)
class MissionFinding:
    """A single audit finding for a mission artifact.

    Invariants (enforced by callers, not runtime-checked here):
    - ``artifact_path`` must use forward slashes, not OS-native separators.
    - ``artifact_path`` must be relative to the mission directory, never absolute.
    - ``detail`` must not contain any run-varying values (timestamps, PIDs,
      memory addresses) so that deterministic serialization is possible.

    Canonical finding codes are defined in ``detectors.py`` and
    ``identity_adapter.py``; see the WP01 spec for the full table.
    """

    code: str
    severity: Severity
    artifact_path: str
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dict with severity as its string value."""
        return {
            "artifact_path": self.artifact_path,
            "code": self.code,
            "detail": self.detail,
            "severity": self.severity.value,
        }


def is_teamspace_blocker(finding: MissionFinding) -> bool:
    """Return True when a finding should block TeamSpace import/sync readiness."""
    return finding.severity == Severity.ERROR or finding.code in TEAMSPACE_BLOCKER_CODES


@dataclass
class MissionAuditResult:
    """Audit outcome for a single mission directory.

    The engine is responsible for sorting ``findings`` by ``(artifact_path, code)``
    before constructing this object to guarantee deterministic serialization.
    """

    mission_slug: str
    mission_dir: Path
    findings: list[MissionFinding]

    @property
    def has_errors(self) -> bool:
        """True if any finding has ERROR severity."""
        return any(f.severity == Severity.ERROR for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        """True if any finding has WARNING severity."""
        return any(f.severity == Severity.WARNING for f in self.findings)

    @property
    def has_teamspace_blockers(self) -> bool:
        """True if any finding blocks TeamSpace import/sync readiness."""
        return any(is_teamspace_blocker(f) for f in self.findings)

    @property
    def finding_codes(self) -> set[str]:
        """Set of all finding codes present in this result."""
        return {f.code for f in self.findings}

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dict.

        ``mission_dir`` is serialized as a stable, non-absolute string because
        absolute ``Path`` values are install-location dependent.
        """
        return {
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "has_errors": self.has_errors,
            "has_teamspace_blockers": self.has_teamspace_blockers,
            "mission_dir": _stable_mission_dir_for_json(
                self.mission_dir, self.mission_slug
            ),
            "mission_slug": self.mission_slug,
        }


@dataclass
class RepoAuditReport:
    """Full audit report for a repository's ``kitty-specs/`` tree.

    ``missions`` must be sorted lexicographically by ``mission_slug`` by the
    engine before construction to satisfy NFR-001 (deterministic output).

    ``shape_counters`` maps finding code to total count across all missions.
    ``to_dict()`` sorts this dict by key for determinism.

    ``repo_summary`` shape (produced by the engine)::

        {
            "findings_by_severity": {"error": 5, "info": 3, "warning": 10},
            "missions_with_errors": 3,
            "missions_with_teamspace_blockers": 4,
            "missions_with_warnings": 7,
            "teamspace_blockers": 8,
            "total_findings": 18,
            "total_missions": 42,
        }
    """

    missions: list[MissionAuditResult]
    shape_counters: dict[str, int]
    repo_summary: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dict with shape_counters sorted by key."""
        return {
            "missions": [m.to_dict() for m in self.missions],
            "repo_summary": self.repo_summary,
            "shape_counters": dict(sorted(self.shape_counters.items())),
        }


@dataclass
class AuditOptions:
    """Engine configuration passed to ``run_audit()``.

    ``scan_root`` defaults to ``repo_root / KITTY_SPECS_DIR`` when ``None``
    (never hardcoded here — the engine resolves the default at call time).
    ``fail_on`` is ``None`` for "always exit 0"; set to ``Severity.ERROR``
    to fail on errors only, ``Severity.WARNING`` for errors+warnings, etc.
    ``invoking_cwd``, when set to the real OS invocation directory, is
    compared against ``repo_root`` (the caller's re-anchored primary
    checkout) for invoking-checkout-vs-primary disagreement — the
    ``--audit`` counterpart of ``enforce_primary_write_ownership``'s
    ``--fix`` refusal. From a foreign lane worktree this catches mission
    state that would otherwise read as a false green because ``repo_root``
    is read at both ends. ``None`` (the default) skips the check entirely,
    so existing callers/tests are unaffected.
    """

    repo_root: Path
    scan_root: Path | None = None
    mission_filter: str | None = None
    invoking_cwd: Path | None = None
    fail_on: Severity | None = None
