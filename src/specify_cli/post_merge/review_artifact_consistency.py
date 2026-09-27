"""Review artifact consistency gates for release signoff."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mission_runtime import MissionArtifactKind
from specify_cli.missions._read_path_resolver import resolve_partition_read_dir
from specify_cli.review.artifacts import TERMINAL_REVIEW_LANES
from specify_cli.status import materialize_snapshot
from specify_cli.status import ReviewOverride
from specify_cli.status import is_changes_requested, review_result_from_state

REJECTED_REVIEW_ARTIFACT_CONFLICT = "REJECTED_REVIEW_ARTIFACT_CONFLICT"
REJECTED_REVIEW_ARTIFACT_INVARIANT = (
    "terminal_wp_latest_review_artifact_must_not_be_rejected"
)
REJECTED_REVIEW_ARTIFACT_REMEDIATION = [
    "Run another review cycle that writes an approved review-cycle artifact.",
    "Or move the WP out of approved/done before merge.",
]


@dataclass(frozen=True)
class RejectedReviewArtifactFinding:
    """A terminal WP whose latest review artifact is still rejected."""

    wp_id: str
    lane: str
    artifact_path: Path | None
    cycle_number: int
    verdict: str


# The artifact-frontmatter *schema* leg (``ReviewArtifactSchemaFinding``) is
# retired per FR-013: this gate no longer parses review-cycle frontmatter, so it
# can never discover a malformed one. ``RejectedReviewArtifactFinding`` is now the
# sole finding kind; the alias is retained so downstream signatures stay stable.
ReviewArtifactFinding = RejectedReviewArtifactFinding


def _resolve_lane_state_read_dir(feature_dir: Path) -> Path:
    """Resolve the ``STATUS_STATE`` home (coord husk for a materialised coord mission).

    FR-006 / gate-execution-context C1 (#2885): a WP's lane state must be read
    from its own declared partition, never from whichever dir the caller handed
    in -- reading LANE STATE off a PRIMARY dir under a coord topology saw an
    empty log and passed a rejected review by default. Resolution, including
    the #154 phantom-partition degrade, is owned by the single handed-dir
    authority :func:`~specify_cli.missions._read_path_resolver.resolve_partition_read_dir`
    (#5180), which the render and verdict reads share.
    """
    return resolve_partition_read_dir(feature_dir, MissionArtifactKind.STATUS_STATE)


def _snapshot_review_override(state: Mapping[str, Any]) -> ReviewOverride | None:
    """Resolve the event-sourced ``review`` override from a reduced WP snapshot.

    FR-009 (WP09): the reduced ``review`` snapshot slot is the single authority
    for override recognition — this post-merge consistency check is the third leg
    of the both-halves pair (alongside the write emit and the merge-gate read), so
    it must resolve the override from the same slot rather than re-parsing artifact
    frontmatter. Returns ``None`` when the slot is absent or malformed; an
    incomplete override is carried through and rejected by ``ReviewOverride``'s
    ``complete`` predicate downstream.
    """
    review_raw = state.get("review")
    if not isinstance(review_raw, Mapping):
        return None
    try:
        return ReviewOverride.from_dict(review_raw)
    except (KeyError, TypeError, ValueError):
        return None


def _event_sourced_gate_verdict(state: Mapping[str, Any]) -> str | None:
    """FR-001 (WP07/T029): the event log's own opinion on this WP's verdict.

    Returns ``"approved"`` / ``"changes_requested"`` when the reduced snapshot's
    ``review_result`` slot carries a recorded verdict — the event log is
    authoritative for *which* verdict is current, so either value overrides
    whatever the frontmatter's latest review-cycle artifact says (T029's two
    disagreement tests: event-approved-over-frontmatter-rejected, and the
    reverse).

    Returns ``None`` when the event log has no opinion for gate-clearing
    purposes — this DELIBERATELY collapses two distinct
    :class:`~specify_cli.status.reducer.ReviewResultLookup` outcomes that stay
    distinguishable upstream:

    - the slot is entirely ABSENT (un-migrated mission / WP never exited
      ``in_review`` — T027's fallback case), and
    - the slot is present but ``None`` (a ``--force`` exit from ``in_review``
      that supplied no ``ReviewResult`` — T028's "no verdict was ever
      recorded" case).

    Both cases mean the same thing for THIS gate specifically:
    **post-WP05 (verdict-seam-write-unification-01KZ9Q35, FR-013 pure-event
    repoint)**, the event log having no opinion means this gate has NO
    signal at all for the WP — the former frontmatter-only fallback
    (``latest_review_artifact_verdict`` / the terminal-lane rejection check)
    is retired, not consulted. ``None`` here therefore means "not blocked",
    matching G2 (contracts/verdict-authority-read.md: absent/damaged is
    fail-open-safe for a rejection-detecting gate, never a fabricated
    block). This collapse is not a re-assertion that the two
    :class:`~specify_cli.status.reducer.ReviewResultLookup` cases are the
    same thing (they are not — see that class's own docstring).

    Delegates to :func:`~specify_cli.status.reducer.review_result_from_state`
    (re-exported on the ``specify_cli.status`` facade per WP01,
    verdict-seam-boundary-hardening-01KZG179) rather than re-inlining the
    ``ReviewResult.from_dict`` decode: the three-way
    :class:`~specify_cli.status.reducer.ReviewResultLookup` outcome collapses
    to this function's two-way contract by treating ``result is None`` (either
    ``slot_present=False`` or a present-but-unrecorded/malformed slot) as "no
    verdict".
    """
    lookup = review_result_from_state(state)
    return str(lookup.result.verdict) if lookup.result is not None else None


def _terminal_event_conflict(
    wp_id: str,
    lane: str,
    snapshot_override: ReviewOverride | None,
    event_verdict: str | None,
) -> RejectedReviewArtifactFinding | None:
    """FR-013/D-PLAN-8 (WP05, pure-event): a terminal WP whose event-sourced
    verdict is ``changes_requested`` blocks merge -- the ONLY signal this gate
    consults post-repoint. No on-disk review-cycle artifact is read or
    resolved here at all, so ``artifact_path`` is always ``None`` in the
    reported finding.

    Retired (not repointed, per FR-013's explicit scope): the former
    artifact-frontmatter leg (``_artifact_dirs_for_wp`` +
    ``latest_review_artifact_verdict`` + ``_resolve_terminal_verdict_conflict``)
    that additionally parsed ``review-cycle-N.md`` frontmatter and reconciled
    it against this same event-sourced verdict. FR-001's "the event wins on
    disagreement" precedence is now moot for THIS gate -- there is no second,
    frontmatter-sourced opinion left to disagree with. The malformed-artifact
    ``ReviewArtifactSchemaFinding`` leg is retired for the identical reason:
    this gate no longer parses artifact frontmatter, so it can no longer
    discover a malformed one.

    Order matters:

    1. A non-terminal lane is never blocked (unchanged).
    2. A complete arbiter override already clears the gate unconditionally
       (FR-010) — checked BEFORE ``event_verdict``.
    3. ``event_verdict == "changes_requested"``: blocked.
    4. Otherwise (``event_verdict`` is ``"approved"`` or ``None`` -- absent or
       damaged, per :func:`_event_sourced_gate_verdict`'s collapse): not
       blocked. G2 (contracts/verdict-authority-read.md): a safety-gate
       consumer treats absent/damaged as "no block", never a crash and never
       a fabricated rejection.
    """
    if lane not in TERMINAL_REVIEW_LANES:
        return None
    if snapshot_override is not None and snapshot_override.complete:
        return None
    if event_verdict is None or not is_changes_requested(event_verdict):
        return None
    return RejectedReviewArtifactFinding(
        wp_id=wp_id,
        lane=lane,
        artifact_path=None,
        cycle_number=0,
        verdict=event_verdict,
    )


def find_rejected_review_artifact_conflicts(
    feature_dir: Path,
    wp_ids: list[str] | None = None,
) -> list[ReviewArtifactFinding]:
    """Return review artifact findings that block merge readiness.

    **WP05 (verdict-seam-write-unification-01KZ9Q35, T025/FR-013/D-PLAN-8)
    pure-event repoint**: this gate now consults ONLY the reduced snapshot's
    event-sourced ``review_result``/``review`` slots (via
    :func:`_event_sourced_gate_verdict` / :func:`_snapshot_review_override`)
    -- it no longer resolves or parses any on-disk ``review-cycle-N.md``
    artifact at all. See :func:`_terminal_event_conflict` for what was
    retired and why.

    The lane snapshot resolves from its ``STATUS_STATE`` home (coord husk for
    a materialised coord-topology mission) — never trusted from the single
    ``feature_dir`` the caller happened to pass (that trust WAS #2885: the
    dry-run preview handed a PRIMARY dir, so the reduce read an empty status
    log and every WP looked stateless, passing a rejected review by default).

    Reduces via the read-only :func:`materialize_snapshot`, NOT :func:`materialize`
    (#2934): this is a merge-readiness *check*, so it must not mutate the working
    tree. ``materialize`` writes ``status.json`` as a side effect; on a mission
    whose event log is empty/absent that write orphans a derived ``status.json``
    with no backing ``status.events.jsonl`` (the invalid state ``validate`` flags),
    which the merge then commits alone. A gate reads; it does not persist.

    ``cli/commands/review/_lane_gate.py``'s ``check_wp_lanes`` (Gate 1) calls
    this same function, so it consults the event-sourced answer too, with no
    separate call needed there.
    """
    lane_state_dir = _resolve_lane_state_read_dir(feature_dir)
    snapshot = materialize_snapshot(lane_state_dir)
    selected_wp_ids = wp_ids or sorted(snapshot.work_packages)
    findings: list[ReviewArtifactFinding] = []

    for wp_id in selected_wp_ids:
        state = snapshot.work_packages.get(wp_id)
        if state is None:
            continue
        lane = str(state.get("lane", ""))
        snapshot_override = _snapshot_review_override(state)
        event_verdict = _event_sourced_gate_verdict(state)
        finding = _terminal_event_conflict(wp_id, lane, snapshot_override, event_verdict)
        if finding is not None:
            findings.append(finding)

    return findings


def format_review_artifact_conflict(
    finding: RejectedReviewArtifactFinding,
    *,
    repo_root: Path | None = None,
) -> str:
    """Render one finding with a stable path for operator diagnostics."""
    path = finding.artifact_path
    if path is None:
        return (
            f"{finding.wp_id} is lane '{finding.lane}', but the event-sourced "
            f"review verdict is '{finding.verdict}' and no on-disk review "
            "artifact exists."
        )
    if repo_root is not None:
        with suppress(ValueError):
            path = path.relative_to(repo_root)
    return (
        f"{finding.wp_id} is lane '{finding.lane}', but latest review artifact "
        f"{path} has verdict '{finding.verdict}' (cycle {finding.cycle_number})."
    )


def format_review_artifact_finding(
    finding: ReviewArtifactFinding,
    *,
    repo_root: Path | None = None,
) -> str:
    """Render one review artifact finding with stable path context."""
    return format_review_artifact_conflict(finding, repo_root=repo_root)


def review_artifact_conflict_diagnostic(
    finding: RejectedReviewArtifactFinding,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Return the stable diagnostic contract payload for one conflict."""
    path: Path | None = finding.artifact_path
    if path is not None and repo_root is not None:
        with suppress(ValueError):
            path = path.relative_to(repo_root)
    return {
        "diagnostic_code": REJECTED_REVIEW_ARTIFACT_CONFLICT,
        "branch_or_work_package": finding.wp_id,
        "violated_invariant": REJECTED_REVIEW_ARTIFACT_INVARIANT,
        "remediation": REJECTED_REVIEW_ARTIFACT_REMEDIATION,
        "lane": finding.lane,
        "latest_review_cycle_path": str(path) if path is not None else None,
        "latest_review_cycle_verdict": finding.verdict,
        "review_cycle_number": finding.cycle_number,
    }


def review_artifact_finding_diagnostic(
    finding: ReviewArtifactFinding,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Return the stable diagnostic payload for any review artifact finding."""
    return review_artifact_conflict_diagnostic(finding, repo_root=repo_root)


@dataclass(frozen=True)
class ReviewArtifactPreflightResult:
    """Structured result of the review-artifact consistency preflight.

    Shared by both the real-merge gate (raises on failure) and the
    ``merge --dry-run`` preview surface (renders diagnostics and exits non-zero).
    """

    findings: tuple[ReviewArtifactFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings

    def diagnostics(
        self,
        *,
        repo_root: Path | None = None,
    ) -> list[dict[str, object]]:
        """Return the stable diagnostic payloads, one per finding."""
        return [
            review_artifact_finding_diagnostic(finding, repo_root=repo_root)
            for finding in self.findings
        ]


def run_review_artifact_consistency_preflight(
    feature_dir: Path,
    *,
    wp_ids: list[str] | None = None,
) -> ReviewArtifactPreflightResult:
    """Run the review-artifact consistency gate and wrap the result.

    This is the single implementation path shared by ``merge`` and
    ``merge --dry-run`` so the two surfaces cannot drift. Callers that need
    rendering can call ``ReviewArtifactPreflightResult.diagnostics()``.
    """
    findings = find_rejected_review_artifact_conflicts(feature_dir, wp_ids)
    return ReviewArtifactPreflightResult(findings=tuple(findings))
