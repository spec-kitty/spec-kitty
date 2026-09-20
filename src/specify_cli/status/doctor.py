"""Status doctor: health check framework for operational hygiene.

Detects stale claims, orphan workspaces, materialization drift,
and derived-view drift. Reports problems and recommends actions
but NEVER modifies files (read-only).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from kernel.clock import now_utc, parse_iso
from specify_cli.status_lanes import TERMINAL_LANES
from .models import Lane, WPInnerStateDelta
from .reducer import SNAPSHOT_FILENAME, reduce
from .store import read_events

logger = logging.getLogger(__name__)

#: The string-scalar runtime slots a ``WPInnerStateDelta`` can fold into a WP
#: snapshot. Derived from the single canonical field list (C-005: no second
#: copy) so a new scalar slot is covered automatically. An empty string in any
#: of these on a non-terminal WP is corrupt canonical state (#2960 / FR-014).
_BLANKABLE_RUNTIME_SLOTS: tuple[str, ...] = WPInnerStateDelta._SCALAR_FIELDS


class Severity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class Category(StrEnum):
    STALE_CLAIM = "stale_claim"
    ORPHAN_WORKSPACE = "orphan_workspace"
    MATERIALIZATION_DRIFT = "materialization_drift"
    DERIVED_VIEW_DRIFT = "derived_view_drift"
    REVIEW_INDEPENDENCE = "review_independence"
    ISSUE_MATRIX = "issue_matrix"
    SPARSE_CHECKOUT = "sparse_checkout"
    UNINITIALIZED_STATUS = "uninitialized_status"
    DUPLICATE_FRONTMATTER_KEY = "duplicate_frontmatter_key"
    BLANKED_RUNTIME_SLOT = "blanked_runtime_slot"


@dataclass
class Finding:
    """A single health check finding."""

    severity: Severity
    category: Category
    wp_id: str | None
    message: str
    recommended_action: str


@dataclass
class DoctorResult:
    """Aggregate result of all health checks."""

    mission_slug: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(f.severity == Severity.ERROR for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == Severity.WARNING for f in self.findings)

    @property
    def is_healthy(self) -> bool:
        return len(self.findings) == 0

    def findings_by_category(self, category: Category) -> list[Finding]:
        return [f for f in self.findings if f.category == category]


def _load_or_reduce_snapshot(
    feature_dir: Path,
    _mission_slug: str,
) -> dict[str, Any] | None:
    """Load snapshot from status.json or reduce from events.

    Returns the snapshot as a dict (work_packages keyed by WP ID),
    or None if neither source is available.
    """
    # Try status.json first
    status_path = feature_dir / SNAPSHOT_FILENAME
    if status_path.exists():
        try:
            data: dict[str, Any] = json.loads(status_path.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            logger.debug("Could not read status.json, trying event log")

    # Try reducing from event log
    try:
        events = read_events(feature_dir)
        if events:
            snapshot = reduce(events)
            snapshot_dict: dict[str, Any] = snapshot.to_dict()
            return snapshot_dict
    except Exception:
        logger.debug("Could not reduce from event log", exc_info=True)

    return None


def check_uninitialized_status(
    feature_dir: Path,
    snapshot: dict[str, Any] | None,
) -> list[Finding]:
    """Flag a mission that has WP definitions but no canonical status (#1589).

    When ``finalize-tasks`` never bootstrapped the event log (e.g. it aborted on
    a dependency cycle), the snapshot is empty/absent and every WP-level check is
    skipped — making the mission look "healthy" while its runtime is wedged. If
    WP files exist but no canonical status does, emit a WARNING naming the real
    cause (a dependency cycle, when present) so doctor does not green a broken
    mission.
    """
    if snapshot and snapshot.get("work_packages"):
        return []  # canonical status is initialized — nothing to flag here

    tasks_dir = feature_dir / "tasks"
    wp_files = sorted(tasks_dir.glob("WP*.md")) if tasks_dir.is_dir() else []
    if not wp_files:
        return []  # no WPs defined yet — legitimately nothing to initialize

    from .uninitialized_hint import cycle_root_cause

    root_cause = cycle_root_cause(feature_dir)
    if root_cause is not None:
        message = f"Mission has {len(wp_files)} work package(s) defined but canonical status is not initialized: {root_cause}"
        action = "Resolve the dependency cycle, then run `spec-kitty agent mission finalize-tasks`."
    else:
        message = f"Mission has {len(wp_files)} work package(s) defined but canonical status is not initialized (event log missing/empty)."
        action = "Run `spec-kitty agent mission finalize-tasks` to bootstrap the event log."
    return [
        Finding(
            severity=Severity.WARNING,
            category=Category.UNINITIALIZED_STATUS,
            wp_id=None,
            message=message,
            recommended_action=action,
        )
    ]


def check_stale_claims(
    _feature_dir: Path,
    snapshot: dict[str, Any],
    *,
    claimed_threshold_days: int = 7,
    in_progress_threshold_days: int = 14,
) -> list[Finding]:
    """Check for WPs stuck in claimed or in_progress."""
    findings: list[Finding] = []
    now = now_utc()

    work_packages = snapshot.get("work_packages", {})
    for wp_id, wp_state in work_packages.items():
        lane = wp_state.get("lane")
        last_transition_at = wp_state.get("last_transition_at")

        if not last_transition_at:
            continue

        try:
            transition_time = parse_iso(last_transition_at)
        except (ValueError, TypeError):
            continue

        age_days = (now - transition_time).days

        if lane == Lane.CLAIMED and age_days > claimed_threshold_days:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category=Category.STALE_CLAIM,
                    wp_id=wp_id,
                    message=(
                        f"{wp_id} has been in 'claimed' for {age_days} days (threshold: {claimed_threshold_days} days). Actor: {wp_state.get('actor', 'unknown')}"
                    ),
                    recommended_action=(f"Either begin work on {wp_id} (move to in_progress) or release the claim (move back to planned)."),
                )
            )

        if lane == Lane.IN_PROGRESS and age_days > in_progress_threshold_days:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category=Category.STALE_CLAIM,
                    wp_id=wp_id,
                    message=(
                        f"{wp_id} has been in 'in_progress' for {age_days} days "
                        f"(threshold: {in_progress_threshold_days} days). "
                        f"Actor: {wp_state.get('actor', 'unknown')}"
                    ),
                    recommended_action=(f"Check if {wp_id} is blocked (move to blocked with reason) or complete the work (move to for_review)."),
                )
            )

    return findings


def check_blanked_runtime_slots(snapshot: dict[str, Any]) -> list[Finding]:
    """Flag non-terminal WPs whose runtime attribution slots are blanked (#2960).

    An annotation carrying ``agent: ""`` (or any empty-string scalar runtime
    slot) that reached the snapshot means recorded attribution was clobbered
    with a blank — corrupt canonical state that must NOT read as Healthy
    (FR-014). The write-boundary normalization in ``WPInnerStateDelta`` and the
    reducer no-op guard prevent new blanks; this check is the read-side net that
    catches state already corrupt on disk (e.g. a legacy log).

    Terminal WPs (``done``/``canceled``) are skipped — a blank slot on finished
    work is not actionable.

    #4786 read-root narrowing: a blank ``agent`` slot explained by the
    reducer's ``implementer_of_record`` derived projection
    (``status.reducer._project_implementer_attribution``) is a
    legitimately-released, historically-owned WP (the live claim correctly
    handed off / released per #4673) — not corrupt canonical state — so it is
    no longer raised as a finding. Every other blank scalar (and an ``agent``
    blank with no recoverable claim history at all) is still genuine on-disk
    corruption and is flagged as before.
    """
    findings: list[Finding] = []
    work_packages = snapshot.get("work_packages", {})
    for wp_id, wp_state in work_packages.items():
        if wp_state.get("lane") in TERMINAL_LANES:
            continue
        for slot in _BLANKABLE_RUNTIME_SLOTS:
            value = wp_state.get(slot)
            if not (isinstance(value, str) and value == ""):
                continue
            if slot == "agent" and wp_state.get("implementer_of_record"):
                continue
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    category=Category.BLANKED_RUNTIME_SLOT,
                    wp_id=wp_id,
                    message=(f"{wp_id} runtime slot '{slot}' is an empty string — recorded attribution was blanked (corrupt canonical state, #2960)."),
                    recommended_action=(
                        f"Run `spec-kitty doctor mission-state --fix --mission <slug>` "
                        f"to repair {wp_id}'s '{slot}' slot, or drop the blanking "
                        f"annotation from the event log; the reducer treats '' as a "
                        f"no-op so a fresh non-empty annotation restores it."
                    ),
                )
            )
    return findings


def check_orphan_workspaces(
    repo_root: Path,
    mission_slug: str,
    snapshot: dict[str, Any],
) -> list[Finding]:
    """Detect orphan worktrees for completed/canceled features."""
    findings: list[Finding] = []

    # Check if all WPs are in terminal states
    work_packages = snapshot.get("work_packages", {})
    if not work_packages:
        return findings

    all_terminal = all(wp.get("lane") in TERMINAL_LANES for wp in work_packages.values())

    if not all_terminal:
        return findings  # Feature still has active WPs, worktrees are legitimate

    # Scan for worktrees matching this feature
    worktrees_dir = repo_root / ".worktrees"
    if not worktrees_dir.exists():
        return findings

    feature_pattern = f"{mission_slug}-lane-*"
    orphan_dirs = list(worktrees_dir.glob(feature_pattern))

    for orphan_dir in orphan_dirs:
        if orphan_dir.is_dir():
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category=Category.ORPHAN_WORKSPACE,
                    wp_id=None,
                    message=(
                        f"Worktree '{orphan_dir.name}' exists but all WPs in "
                        f"'{mission_slug}' are terminal "
                        f"({', '.join(sorted(TERMINAL_LANES))}). "
                        f"Path: {orphan_dir}"
                    ),
                    recommended_action=(f"Remove the orphan worktree: git worktree remove {orphan_dir.name}"),
                )
            )

    return findings


def check_drift(feature_dir: Path) -> list[Finding]:
    """Delegate to validation engine for drift detection.

    Uses try/except import to handle the case where WP11
    (validate) is not yet implemented.
    """
    findings: list[Finding] = []
    try:
        from specify_cli.status.validate import validate_materialization_drift
    except ImportError:
        # Validation engine not available yet (WP11 not merged)
        return findings

    # Materialization drift
    drift_findings = validate_materialization_drift(feature_dir)
    for msg in drift_findings:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                category=Category.MATERIALIZATION_DRIFT,
                wp_id=None,
                message=msg,
                recommended_action=("Run 'spec-kitty agent status materialize' to regenerate status.json from the canonical event log."),
            )
        )

    # NB: derived-view drift is no longer checked here. The event log is the sole
    # authority and validate_derived_views is a permanent no-op (frontmatter lane
    # drift was retired), so the former call-site only did discarded setup work
    # (#1775 Randy-Reducer FSM-3). validate_derived_views remains as a public
    # tombstone for any external caller.

    return findings


def check_reviewer_self_approval(feature_dir: Path) -> list[Finding]:
    """Flag explicit self-review fallback events as review-independence risk."""
    findings: list[Finding] = []
    try:
        from specify_cli.status.lifecycle_events import (
            REVIEWER_SELF_APPROVAL,
            mission_event_log_path,
            read_lifecycle_events,
        )
    except ImportError:
        return findings

    for event in read_lifecycle_events(mission_event_log_path(feature_dir)):
        if event.get("event_type") != REVIEWER_SELF_APPROVAL:
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        wp_id = str(payload.get("wp_id") or event.get("aggregate_id") or "")
        implementing_actor = str(payload.get("implementing_actor") or "unknown")
        intended_reviewer = str(payload.get("intended_reviewer") or "unknown")
        failure_reason = str(payload.get("failure_reason") or "reviewer_failed")
        findings.append(
            Finding(
                severity=Severity.WARNING,
                category=Category.REVIEW_INDEPENDENCE,
                wp_id=wp_id or None,
                message=(
                    f"{wp_id or 'A work package'} used self-review fallback: "
                    f"{implementing_actor} approved after intended reviewer "
                    f"{intended_reviewer} failed ({failure_reason})."
                ),
                recommended_action="Re-review with an independent reviewer before merge/release.",
            )
        )

    return findings


def check_issue_matrix(feature_dir: Path, *, issue_matrix_dir: Path | None = None) -> list[Finding]:
    """Flag missions with issue references whose issue-matrix verdicts are missing.

    ``issue_matrix_dir`` (coord-commit-integrity SURFACE A #1c): the COORD-partition
    read surface for the issue-matrix artifact — the coordination worktree under
    coord/lanes-with-coord topology, resolved by the caller through the shared
    placement seam (:func:`mission_runtime.coord_read_dir_for`). Defaults to
    ``feature_dir`` when ``None`` (coord-less missions and legacy callers).

    Discovery scans every mission artifact that can carry a load-bearing GH
    issue reference — ``spec.md``, ``plan.md``, ``research.md``,
    ``analysis-report.md``, ``tasks/*.md``, ``contracts/*.md`` — not
    ``spec.md`` alone (write-side-seam-matrix-tracer-01KYP3MH WP08 T029,
    FR-004). All of those are PRIMARY-partition kinds, so discovery ALWAYS
    reads ``feature_dir`` — never ``issue_matrix_dir``.
    """
    try:
        from specify_cli.tasks.issue_reference_discovery import discover_issue_references

        refs = discover_issue_references(feature_dir)
    except Exception as exc:
        logger.debug("Could not evaluate issue-matrix doctor check", exc_info=True)
        return [
            Finding(
                severity=Severity.WARNING,
                category=Category.ISSUE_MATRIX,
                wp_id=None,
                message=f"issue-matrix could not be evaluated: {exc}",
                recommended_action="Fix the issue-matrix check before approval/merge.",
            )
        ]

    if not refs:
        return []

    # T043 (C-008 / B-1 fix): presence is a dir-based check
    # (:func:`issue_matrix_artifact_present`), not a ``.md``-only
    # ``.exists()`` — the prior precheck made a JSON-only mission (B3) look
    # like the matrix was missing before ``validate_issue_matrix`` (which
    # already resolves JSON-first via WP05's canonical dir-based reader,
    # :func:`~specify_cli.tasks.issue_matrix_migration.load_issue_matrix`)
    # ever ran.
    from specify_cli.cli.commands.review._issue_matrix import validate_issue_matrix
    from specify_cli.tasks.issue_matrix import ISSUE_MATRIX_MD_FILENAME
    from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

    matrix_dir = issue_matrix_dir or feature_dir
    if not issue_matrix_artifact_present(matrix_dir):
        issue_list = ", ".join(f"#{ref.number}" for ref in refs)
        return [
            Finding(
                severity=Severity.WARNING,
                category=Category.ISSUE_MATRIX,
                wp_id=None,
                message=f"Mission references GitHub issues but the issue-matrix is missing: {issue_list}.",
                recommended_action="Create the issue-matrix and record final verdicts before approval/merge.",
            )
        ]

    result = validate_issue_matrix(matrix_dir / ISSUE_MATRIX_MD_FILENAME)
    findings: list[Finding] = []
    referenced_issues = {f"#{ref.number}" for ref in refs}
    matrix_issues = {row.issue for row in result.rows}
    for diagnostic in result.diagnostics:
        match = re.search(r"Row for issue '([^']+)'", diagnostic.get("message", ""))
        if match:
            matrix_issues.add(match.group(1))
    missing_issues = sorted(referenced_issues - matrix_issues)
    if missing_issues:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                category=Category.ISSUE_MATRIX,
                wp_id=None,
                message=(f"issue-matrix.md is missing rows for referenced issue(s): {', '.join(missing_issues)}."),
                recommended_action="Add one row per referenced issue before approval/merge.",
            )
        )
    for diagnostic in result.diagnostics:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                category=Category.ISSUE_MATRIX,
                wp_id=None,
                message=str(diagnostic.get("message", "issue-matrix.md contains an unresolved issue verdict.")),
                recommended_action=(
                    "Replace unknown/deferred issue verdicts with fixed, "
                    "verified-already-fixed, a documented follow-up, or "
                    "in-mission (until a later WP in this mission closes it)."
                ),
            )
        )

    return findings


def check_duplicate_frontmatter_keys(scan_dir: Path) -> list[Finding]:
    """Flag legacy dual-key artifacts (FR-008, #3372) — diagnostic only.

    Thin delegation to the raw-text detector in
    :mod:`specify_cli.status.dup_key_repair`. Detection CANNOT use the canonical
    frontmatter boundary: it fails closed on duplicate keys (ruamel
    ``DuplicateKeyError``), so loading a dual-key artifact raises rather than
    reporting it. This check NEVER mutates; repair is opt-in via
    ``spec-kitty doctor mission-state --fix`` (keep-last-non-empty, batch-atomic).
    """
    from specify_cli.status.dup_key_repair import detect_duplicate_key_artifacts

    findings: list[Finding] = []
    for finding in detect_duplicate_key_artifacts(scan_dir):
        line_list = ", ".join(str(number) for number in finding.line_numbers)
        findings.append(
            Finding(
                severity=Severity.WARNING,
                category=Category.DUPLICATE_FRONTMATTER_KEY,
                wp_id=None,
                message=(
                    f"{finding.path.name} has a duplicate frontmatter key "
                    f"'{finding.key}' (lines {line_list}) — invalid YAML that "
                    f"fails closed at the frontmatter boundary and will trip an upgrade."
                ),
                recommended_action=("Run 'spec-kitty doctor mission-state --fix' to repair duplicate-key artifacts (keep-last-non-empty, batch-atomic)."),
            )
        )
    return findings


def check_sparse_checkout(repo_root: Path) -> list[Finding]:
    """Repo-level check: legacy sparse-checkout state lingering from pre-3.x.

    Wraps WP02's pure detection primitive (``scan_repo``) and emits a single
    warning-level finding that lists every affected path (primary plus any
    lane worktrees whose config has ``core.sparseCheckout=true``). The
    finding's ``recommended_action`` points the operator at
    ``spec-kitty doctor sparse-checkout --fix`` (T017), which is the only
    CLI entry point that invokes WP03's ``remediate``.

    Emits no finding on a clean repo, so this is safe to invoke on every
    mission doctor run (FR-002). Detection failures are swallowed by
    design: a broken probe must not block other doctor checks.

    Context: Priivacy-ai/spec-kitty#588 — sparse-checkout was removed in
    v3.0.0 but no migration was shipped, so state lingers in user repos
    and causes silent data loss during mission merges.
    """
    findings: list[Finding] = []

    try:
        from specify_cli.git.sparse_checkout import scan_repo
    except ImportError:
        # WP02 detection primitive not available — fail quietly rather than
        # blocking the rest of the doctor run.
        return findings

    try:
        report = scan_repo(repo_root)
    except Exception:
        logger.debug("sparse-checkout scan failed", exc_info=True)
        return findings

    if not report.any_blocking:
        return findings

    affected_paths = [str(p) for p in report.affected_paths]

    # Compose a plain-language explanation that matches Quickstart Flow 1:
    # cite #588, list paths, point at the fix action.
    lines: list[str] = ["Legacy sparse-checkout state detected."]
    if report.primary.is_active:
        pattern_note = ""
        if report.primary.pattern_file_present:
            pattern_note = f" (pattern file: {report.primary.pattern_file_path}, {report.primary.pattern_line_count} lines)"
        lines.append(f"Primary: {report.primary.path}{pattern_note}")
    active_wts = [w for w in report.worktrees if w.is_blocking]
    if active_wts:
        lines.append(f"Lane worktrees affected: {len(active_wts)}")
        for wt in active_wts:
            lines.append(f"  {wt.path}")
    lines.append(
        "Why this matters: spec-kitty v3.0+ removed sparse-checkout "
        "support but did not ship a migration. This state can cause "
        "silent data loss during mission merge and broken lane worktrees "
        "on agent action implement. See spec-kitty/spec-kitty#588."
    )

    findings.append(
        Finding(
            severity=Severity.WARNING,
            category=Category.SPARSE_CHECKOUT,
            wp_id=None,
            message="\n".join(lines),
            recommended_action=(
                "Run 'spec-kitty doctor sparse-checkout --fix' to remove "
                "legacy sparse-checkout state from the primary repo and "
                f"any lane worktrees. Affected paths: "
                f"{', '.join(affected_paths)}"
            ),
        )
    )

    return findings


def run_doctor(
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path,
    *,
    stale_claimed_days: int = 7,
    stale_in_progress_days: int = 14,
) -> DoctorResult:
    """Run all health checks for a feature.

    This is the main entry point. It loads the snapshot (from status.json
    or by reducing the event log), then runs all checks.

    Args:
        feature_dir: Path to the feature's kitty-specs directory.
        mission_slug: Feature identifier (e.g., "034-feature-name").
        repo_root: Path to the repository root.
        stale_claimed_days: Days before a claimed WP is flagged as stale.
        stale_in_progress_days: Days before an in_progress WP is flagged.

    Returns:
        DoctorResult with all findings.

    Raises:
        FileNotFoundError: If feature_dir does not exist.
    """
    if not feature_dir.exists():
        raise FileNotFoundError(f"Feature directory does not exist: {feature_dir}")

    result = DoctorResult(mission_slug=mission_slug)

    # Load snapshot (from status.json or reduce from events)
    snapshot = _load_or_reduce_snapshot(feature_dir, mission_slug)

    # #1589: a mission with WP files but no canonical status must not read as
    # healthy. Checked before the snapshot-gated checks so it fires when the
    # snapshot is empty/absent.
    result.findings.extend(check_uninitialized_status(feature_dir, snapshot))

    if snapshot:
        result.findings.extend(
            check_stale_claims(
                feature_dir,
                snapshot,
                claimed_threshold_days=stale_claimed_days,
                in_progress_threshold_days=stale_in_progress_days,
            )
        )
        result.findings.extend(check_orphan_workspaces(repo_root, mission_slug, snapshot))
        result.findings.extend(check_drift(feature_dir))
        # FR-014 (#2960): a blanked runtime slot on an active WP is corrupt
        # canonical state — must not read as Healthy.
        result.findings.extend(check_blanked_runtime_slots(snapshot))

    result.findings.extend(check_reviewer_self_approval(feature_dir))
    # coord-commit-integrity SURFACE A #1c: route the COORD-partition issue-matrix
    # read through the shared placement seam (coord surface under
    # coord/lanes-with-coord; primary ``feature_dir`` fallback when coord-less or
    # the coord worktree is gone). ``spec.md`` stays on ``feature_dir`` (PRIMARY).
    from mission_runtime import MissionArtifactKind, coord_read_dir_for

    issue_matrix_dir = coord_read_dir_for(repo_root, mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    result.findings.extend(check_issue_matrix(feature_dir, issue_matrix_dir=issue_matrix_dir))

    # Repo-level sparse-checkout finding (FR-002). Appended last so existing
    # findings keep their position — scripts scraping doctor output rely on
    # the order of prior findings; new ones are safe to add at the tail.
    result.findings.extend(check_sparse_checkout(repo_root))

    # Legacy dual-key artifact finding (FR-008, #3372). Scoped to this mission's
    # own artifact tree; appended at the tail for the same order-stability reason.
    result.findings.extend(check_duplicate_frontmatter_keys(feature_dir))

    return result
