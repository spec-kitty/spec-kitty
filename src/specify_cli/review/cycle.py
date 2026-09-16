"""Shared review-cycle invariant boundary.

This module owns only rejected review-cycle artifact invariants:
artifact creation, required frontmatter validation, canonical pointer
construction/resolution, legacy feedback pointer normalization, and rejected
ReviewResult derivation.
"""

from __future__ import annotations

from kernel.clock import UTC_SECOND_TIMESTAMP_FORMAT, now_utc
from kernel.git_topology import GitTopologyError
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CoordCommitRouter,
    MissionHandle,
)
from specify_cli.core.paths import assert_safe_path_segment
from specify_cli.git.protection_policy import ProtectionPolicy
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from specify_cli.review.artifacts import (
    AffectedFile,
    ReviewCycleArtifact,
)
from specify_cli.review.verdict_commit_queue import (
    DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS,
    verdict_save_queue_is_held,
)
from specify_cli.status import (
    ReviewResult,
    emission_event_verdict,
    feature_status_lock,
    git_operation_in_progress,
)

logger = logging.getLogger(__name__)

# FR-004 (kernel-clock-single-door WP03): defined once on the door
# (kernel.clock.UTC_SECOND_TIMESTAMP_FORMAT), imported above; call sites here
# are untouched (package remediation is WP13c's job).
REVIEW_FEEDBACK_SENTINELS = frozenset({"force-override", "action-review-claim"})

#: T042 (FR-002/mechanism shared with WP11): the commit call's own retry-on-
#: contention bound. Small and fixed -- a lock-contention window measured in
#: milliseconds, not a long-running outage -- per plan.md's Risks section
#: ("do not attempt exponential backoff at a multi-second scale here").
_COMMIT_CONTENTION_MAX_ATTEMPTS = 3
_COMMIT_CONTENTION_RETRY_SLEEP_SECONDS = 0.15

_REVIEW_CYCLE_FILE_RE = re.compile(r"^review-cycle-(?P<cycle>[1-9][0-9]*)\.md$")


def review_feedback_source_path(sub_artifact_dir: Path, cycle_number: int) -> Path:
    """Return the in-repo path a reviewer should write cycle *cycle_number*'s
    rejection feedback to.

    Deliberately NOT ``review-cycle-N.md``: inside *sub_artifact_dir* that
    filename is the TOOL-authored verdict artifact, which
    :func:`_guard_feedback_source_provenance` refuses as a ``feedback_source``.
    The review prompt used to advertise exactly that path, so the rejection
    command it printed could never be run as printed (#3430). Owning the name
    here, beside the guard, is what stops the advertised path and the accepted
    path drifting apart again.
    """
    return sub_artifact_dir / f"review-feedback-{cycle_number}.md"


def next_review_feedback_source_path(sub_artifact_dir: Path) -> Path:
    """Return the reviewer-facing feedback path for the NEXT review cycle.

    The cycle number is derived through :meth:`ReviewCycleArtifact.
    next_cycle_number` — the SAME ``max(parsed) + 1`` authority the rejection
    writer allocates the ``review-cycle-N.md`` artifact with — never a count
    of files present. #3243: the review prompt used to derive its advertised
    number as ``len(glob("review-cycle-*.md")) + 1``, which diverges from the
    writer's allocation whenever the count is not the max (a numbering gap
    from a deleted middle artifact advertises ``review-feedback-3.md`` while
    the rejection allocates ``review-cycle-4.md``; an unparseable sibling like
    ``review-cycle-final.md`` inflates the count AND makes the writer refuse
    outright, so the printed rejection command was not runnable — the exact
    #3430 failure shape one level up).

    Raises:
        ValueError: propagate :meth:`ReviewCycleArtifact.next_cycle_number`'s
            refusal (unparseable sibling filename, or a colliding next number)
            — a caller advertising a path the writer would refuse must fail
            closed with the same repair message, not print a command that
            cannot be run as printed.
    """
    return review_feedback_source_path(
        sub_artifact_dir,
        ReviewCycleArtifact.next_cycle_number(sub_artifact_dir),
    )


def _review_cycle_wp_dir(
    repo_root: Path,
    mission_slug: str,
    wp_slug: str,
    *,
    kind: MissionArtifactKind = MissionArtifactKind.WORK_PACKAGE_TASK,
    effective_root: Path | None = None,
) -> Path:
    """Return the ``tasks/<wp>`` dir a review-cycle artifact reads/writes,
    on disk.

    **ADR 2026-08-03-1 designates ``review-cycle-N.md`` as
    ``MissionArtifactKind.REVIEW_CYCLE`` — COORD-partition per-work-package
    bookkeeping under a coordination topology, PRIMARY otherwise.** This is
    the ONE owner function every consumer in this mission's scope routes
    through — the READ seam (:func:`resolve_review_cycle_pointer`), the WRITE
    seam (:func:`create_rejected_review_cycle`), and the arbiter
    (:func:`specify_cli.review.arbiter.persist_arbiter_decision`) all resolve
    through this single call (FR-007), parametrized by ``kind`` so each
    consumer states which partition rule it wants rather than re-deriving the
    directory independently.

    **FR-011 correction (WP06): the merge-time gate does NOT opt into
    ``REVIEW_CYCLE`` here.** An earlier revision of this docstring claimed
    the merge-time gate (:mod:`specify_cli.post_merge.review_artifact_consistency`)
    was this function's one ``kind=REVIEW_CYCLE`` caller; verified against the
    live tree, that module never calls ``_review_cycle_wp_dir`` at all -- it
    resolves its own read directory through a separate helper
    (``_resolve_partition_read_dir``). No caller in this mission's scope
    currently passes ``kind=MissionArtifactKind.REVIEW_CYCLE`` to this
    function; every real call site (the READ seam, the WRITE seam, the
    arbiter, ``tasks_materialization.py::_persist_review_feedback``,
    ``workflow_executor.py``, ``workflow_cores.py``,
    ``tasks_verdict_persistence.py``) relies on the ``WORK_PACKAGE_TASK``
    default below and passes no ``kind`` argument.

    ``kind`` defaults to ``MissionArtifactKind.WORK_PACKAGE_TASK`` (PRIMARY,
    for every topology) — every real caller relies on this default and passes
    no ``kind`` argument. A caller MAY instead pass
    ``kind=MissionArtifactKind.REVIEW_CYCLE`` to resolve the ADR-designated
    COORD-under-coord-topology home (absorbing
    ``CoordinationBranchDeleted``/``StatusReadPathNotFound`` to the PRIMARY
    home for pre-ADR missions, per the ADR's "exception absorption" migration
    rule) — no production caller opts into this branch today (verified above);
    it remains a designed, reachable code path for a future consumer, not
    dead code (see ``kind is MissionArtifactKind.REVIEW_CYCLE`` below).

    **WP13 finding (disclosed, not silently worked around): the WRITE-side
    default cannot yet change to ``REVIEW_CYCLE``.** Trying
    ``kind=REVIEW_CYCLE`` as the DEFAULT (so a coord-topology mission's
    review-cycle WRITE physically lands in the already-materialised
    coordination worktree, not the primary checkout) reproducibly broke a
    currently-green, un-owned regression test:
    ``tests/coordination/test_analysis_report_rehome.py::
    test_review_cycle_authored_lands_on_coord_ref_and_is_absent_on_primary``
    (WP04's own re-pin for this ADR) asserts the artifact's REPO-ROOT-RELATIVE
    path is ``kitty-specs/<slug>/tasks/<wp>/review-cycle-1.md`` — i.e. the
    PHYSICAL write lands in the PRIMARY working tree even though
    ``commit_router.commit_artifact``'s path-based classification (WP04, T015)
    already stages that SAME content onto the COORD branch via git plumbing,
    independent of the physical write location. Defaulting to
    ``REVIEW_CYCLE`` would move the physical write into the separate
    coordination worktree directory instead, breaking that assertion.

    **Historical second hazard — CLOSED in this mission (WP05).** An earlier
    draft of this disclosure named a second, reader-side hazard:
    ``tasks_verdict_persistence.py::resolve_review_verdict_facts`` deriving the
    verdict-read directory via a bare PRIMARY-anchored ``wp_path`` join that
    ignored any kind-aware resolver, so flipping the WRITE default to COORD
    would have left that reader blind to a real, current rejection (a fail-open
    regression on a safety-critical guard). WP05 (FR-002) migrated that reader
    onto the coord-aware ``_resolve_verdict_read_feature_dir`` (STATUS_STATE
    placement), so it now co-resolves with every other verdict consumer and the
    hazard no longer exists — see
    ``tests/coordination/test_verdict_dir_co_resolution.py``.

    That leaves the ``test_analysis_report_rehome`` PHYSICAL-write assertion as
    the sole remaining reason this WP does not ship a WRITE-side default flip.
    Opting a single consumer such as the merge-time gate into
    ``kind=REVIEW_CYCLE`` would be independently safe (it never touches
    ``_review_cycle_wp_dir``'s write-side default) — but per FR-011's
    correction above, no consumer has actually done so yet. A follow-up WP that
    flips the write-side default must re-verify ``test_analysis_report_rehome.py``
    (plus recheck the three unrouted sites recorded by WP04:
    ``workflow.py::review``,
    ``workflow_cores.py::has_prior_rejection``,
    ``workflow_executor.py::implement_try_render_fix_mode_prompt``) in the SAME
    change before the WRITE-side default can safely flip. See this WP's final
    report for the full citations.

    **FR-007 wording reconciliation (WP06).** WP08's reviewed retirement set
    marks THIS function for retirement — a future WP is expected to retire
    ``_review_cycle_wp_dir`` itself once the write-side default safely flips
    (the hazards above are resolved) and every consumer routes through the
    canonical placement resolver directly. Until then, the COORD→PRIMARY
    exception-absorption fallback implemented in the ``kind is
    MissionArtifactKind.REVIEW_CYCLE`` branch below is **relocated** into
    that eventual canonical placement resolver, not "preserved verbatim" (an
    earlier spec revision's phrasing, corrected by research.md) — its
    rationale re-scopes to the surviving write/prose-locate seam once the
    retired verdict read-path (WP05's collapse) no longer exercises it.

    Historically retires the lenient kind-aware ``resolve_planning_read_dir``
    fold (and the kind-blind ``candidate_feature_dir_for_mission`` fold that
    resolved the coord worktree for a coord-topology mission —
    #2646/#2697/#2275). ``MissionSelectorAmbiguous`` propagates unchanged (no
    silent pick — C-009).
    """
    seam = placement_seam(repo_root, mission_slug, effective_root=effective_root)
    if kind is MissionArtifactKind.REVIEW_CYCLE:
        # Function-local import: avoids a module-load cycle between
        # review/cycle.py and the coordination/missions modules (the same
        # H2/I-6 precedent ``_review_cycle_reconcile_doctor.py`` documents for
        # its own identical absorption pattern).
        from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

        try:
            # ``placement_seam(...).read_dir`` is typed ``-> Path`` but mypy
            # widens it to ``Any`` through the ``follow_imports=skip``
            # boundary on ``specify_cli.*``; bind explicitly so the join's
            # return narrows back to ``Path``.
            mission_dir: Path = seam.read_dir(MissionArtifactKind.REVIEW_CYCLE)
        except StatusReadPathNotFound:
            # ``CoordinationBranchDeleted`` is a ``StatusReadPathNotFound``
            # subclass, so this single except also covers that specific case
            # (the ADR's "exception absorption" migration rule).
            mission_dir = seam.read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
        return mission_dir / "tasks" / wp_slug

    resolved_dir: Path = seam.read_dir(kind)
    return resolved_dir / "tasks" / wp_slug


class ReviewCycleError(ValueError):
    """Raised when a review-cycle invariant cannot be satisfied."""


DurabilityClassification: TypeAlias = Literal[
    "durable", "busy", "persistence_failed", "local_only"
]


@dataclass(frozen=True)
class VerdictPersistenceOutcome:
    """Evidence-persistence fact returned to verdict orchestration.

    This value deliberately contains no verdict.  Review-cycle Markdown is
    evidence; the event history remains the sole current-verdict authority.
    """

    classification: DurabilityClassification
    verdict_durably_persisted: bool
    evidence_ref: str | None
    destination_ref: str | None
    reason: str | None
    message: str

    def __post_init__(self) -> None:
        if self.classification == "durable":
            if not self.verdict_durably_persisted:
                raise ValueError("durable outcome requires a true durability flag")
            if not self.evidence_ref or not self.destination_ref:
                raise ValueError("durable outcome requires evidence and destination refs")
            if self.reason is not None:
                raise ValueError("durable outcome must not carry a failure reason")
        else:
            if self.verdict_durably_persisted:
                raise ValueError("only durable outcomes may set the durability flag")
            if not self.reason:
                raise ValueError("non-durable outcome requires a stable reason")


@dataclass(frozen=True)
class ReviewCyclePointerParts:
    """Validated canonical review-cycle pointer segments."""

    mission_slug: str
    wp_slug: str
    filename: str

    @property
    def cycle_number(self) -> int:
        match = _REVIEW_CYCLE_FILE_RE.match(self.filename)
        if match is None:  # pragma: no cover - impossible after validation
            raise ReviewCycleError(f"Invalid review-cycle filename: {self.filename}")
        return int(match.group("cycle"))


@dataclass(frozen=True)
class ResolvedReviewCyclePointer:
    """Resolution result for review feedback references."""

    reference: str
    path: Path | None
    kind: Literal["canonical", "legacy", "sentinel", "path"]
    warnings: tuple[str, ...] = ()

    @property
    def is_resolved(self) -> bool:
        return self.path is not None


@dataclass(frozen=True)
class CreatedRejectedReviewCycle:
    """Validated rejected review cycle ready for status mutation."""

    artifact_path: Path
    pointer: str
    artifact: ReviewCycleArtifact
    review_result: ReviewResult
    persistence: VerdictPersistenceOutcome
    warnings: tuple[str, ...] = ()


def _validate_segment(name: str, value: str) -> str:
    """Return a single safe path segment or raise ReviewCycleError.

    Delegates to the canonical ``assert_safe_path_segment`` (FR-001 / WP01) and
    re-raises any ``ValueError`` as ``ReviewCycleError`` to preserve the call-site
    contract (C-001: migrate, don't wrap — no parallel mechanism).
    """
    try:
        # ``assert_safe_path_segment`` is typed ``-> str`` but mypy widens it to
        # ``Any`` through the ``follow_imports=skip`` boundary on ``specify_cli.*``;
        # bind explicitly so the declared ``str`` return narrows back.
        safe_segment: str = assert_safe_path_segment(value)
        return safe_segment
    except ValueError as exc:
        raise ReviewCycleError(f"{name} is not a safe path segment: {exc}") from exc


def _resolve_git_common_dir(repo_root: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    raw_value = result.stdout.strip()
    if not raw_value:
        return None
    common_dir = Path(raw_value)
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    return common_dir


def build_review_cycle_pointer(mission_slug: str, wp_slug: str, filename: str) -> str:
    """Return a canonical ``review-cycle://`` pointer after validation."""
    parts = ReviewCyclePointerParts(
        mission_slug=_validate_segment("mission_slug", mission_slug),
        wp_slug=_validate_segment("wp_slug", wp_slug),
        filename=_validate_review_cycle_filename(filename),
    )
    return f"review-cycle://{parts.mission_slug}/{parts.wp_slug}/{parts.filename}"


def _validate_review_cycle_filename(filename: str) -> str:
    candidate = _validate_segment("filename", filename)
    if _REVIEW_CYCLE_FILE_RE.fullmatch(candidate) is None:
        raise ReviewCycleError("filename must match review-cycle-N.md")
    return candidate


def validate_review_cycle_pointer(pointer: str) -> ReviewCyclePointerParts:
    """Parse and validate a canonical review-cycle pointer."""
    value = pointer.strip()
    if not value.startswith("review-cycle://"):
        raise ReviewCycleError("review-cycle pointer must start with review-cycle://")

    relative = value[len("review-cycle://") :]
    raw_parts = relative.split("/")
    if len(raw_parts) != 3:
        raise ReviewCycleError("review-cycle pointer must have mission/wp/file segments")

    return ReviewCyclePointerParts(
        mission_slug=_validate_segment("mission_slug", raw_parts[0]),
        wp_slug=_validate_segment("wp_slug", raw_parts[1]),
        filename=_validate_review_cycle_filename(raw_parts[2]),
    )


def validate_review_artifact(artifact: ReviewCycleArtifact) -> None:
    """Validate required review artifact fields.

    FR-003/SC-007 (WP06): this no longer validates a ``verdict`` field --
    ``ReviewCycleArtifact`` carries no such field (WP05 retired every reader
    that treated the artifact's frontmatter as verdict authority; the event
    log, via ``status.event_sourced_review_result``, is now the sole
    authority). Validating a field the schema no longer has would be dead
    code, not a defensive check.
    """
    if artifact.cycle_number < 1:
        raise ReviewCycleError("review artifact cycle_number must be positive")
    _validate_segment("wp_id", artifact.wp_id)
    _validate_segment("mission_slug", artifact.mission_slug)
    if not str(artifact.reviewer_agent).strip():
        raise ReviewCycleError("review artifact reviewer_agent is required")
    if not str(artifact.reviewed_at).strip():
        raise ReviewCycleError("review artifact reviewed_at is required")
    if not str(artifact.body).strip():
        raise ReviewCycleError("review artifact body is required")


def validate_review_artifact_file(path: Path) -> ReviewCycleArtifact:
    """Load and validate a persisted review-cycle artifact."""
    artifact = ReviewCycleArtifact.from_file(path)
    validate_review_artifact(artifact)
    return artifact


def resolve_review_cycle_pointer(repo_root: Path, pointer: str) -> ResolvedReviewCyclePointer:
    """Resolve canonical and legacy review feedback references.

    Sentinels return a structured no-artifact result. Canonical pointers are
    validated and must point at a readable, valid review-cycle artifact. Legacy
    ``feedback://`` references resolve through the git common-dir with a warning.
    """
    value = pointer.strip()
    if not value:
        return ResolvedReviewCyclePointer(reference=pointer, path=None, kind="path")
    if value in REVIEW_FEEDBACK_SENTINELS:
        return ResolvedReviewCyclePointer(reference=value, path=None, kind="sentinel")

    if value.startswith("review-cycle://"):
        parts = validate_review_cycle_pointer(value)
        # #2136/#2164 + FR-001/FR-007 (WP13): resolve the mission dir through the
        # SAME shared owner function the WRITE seam uses (``create_rejected_
        # review_cycle`` -> ``_review_cycle_wp_dir``) rather than a raw
        # ``kitty-specs/<mission_slug>`` join. ADR 2026-08-03-1 designates
        # ``review-cycle-N.md`` as a REVIEW_CYCLE artifact (COORD-partition
        # under a coordination topology, PRIMARY otherwise); ``_review_cycle_
        # wp_dir`` deliberately still resolves the PRIMARY WORK_PACKAGE_TASK
        # home only (see that function's own docstring for the disclosed
        # safety finding blocking the full flip), so for every handle form
        # this and the write seam converge on the SAME home (a bare ``mid8``
        # / human slug names the on-disk ``<slug>-<mid8>`` dir only after
        # canonicalization, so a raw join would compose a DIVERGENT path).
        # ``MissionSelectorAmbiguous`` propagates (no silent pick — C-009).
        candidate = (
            _review_cycle_wp_dir(repo_root, parts.mission_slug, parts.wp_slug)
            / parts.filename
        ).resolve()
        if not candidate.exists() or not candidate.is_file():
            return ResolvedReviewCyclePointer(reference=value, path=None, kind="canonical")
        try:
            validate_review_artifact_file(candidate)
        except ValueError:
            return ResolvedReviewCyclePointer(reference=value, path=None, kind="canonical")
        return ResolvedReviewCyclePointer(reference=value, path=candidate, kind="canonical")

    if value.startswith("feedback://"):
        relative = value[len("feedback://") :]
        raw_parts = relative.split("/")
        if len(raw_parts) != 3:
            return ResolvedReviewCyclePointer(
                reference=value,
                path=None,
                kind="legacy",
                warnings=("Legacy feedback pointer is malformed.",),
            )
        try:
            mission_slug = _validate_segment("mission_slug", raw_parts[0])
            wp_slug = _validate_segment("wp_slug", raw_parts[1])
            filename = _validate_segment("filename", raw_parts[2])
        except ReviewCycleError as exc:
            return ResolvedReviewCyclePointer(
                reference=value,
                path=None,
                kind="legacy",
                warnings=(f"Legacy feedback pointer is invalid: {exc}",),
            )
        common_dir = _resolve_git_common_dir(repo_root)
        warning = "Legacy feedback:// pointer is deprecated; use review-cycle:// artifacts."
        if common_dir is None:
            return ResolvedReviewCyclePointer(reference=value, path=None, kind="legacy", warnings=(warning,))
        candidate = (common_dir / "spec-kitty" / "feedback" / mission_slug / wp_slug / filename).resolve()
        return ResolvedReviewCyclePointer(
            reference=value,
            path=candidate if candidate.exists() and candidate.is_file() else None,
            kind="legacy",
            warnings=(warning,),
        )

    legacy = Path(value).expanduser()
    candidate = legacy if legacy.is_absolute() else repo_root / legacy
    candidate = candidate.resolve()
    return ResolvedReviewCyclePointer(
        reference=value,
        path=candidate if candidate.exists() and candidate.is_file() else None,
        kind="path",
    )


def _guard_feedback_source_provenance(
    *, feedback_source: Path, sub_artifact_dir: Path
) -> None:
    """Refuse a *feedback_source* that IS a prior review-cycle artifact.

    Closes #2996(b) (fabricated duplicate) and #990 (content-wrapping) as the
    identical mechanism: a ``feedback_source`` that resolves — by path OR by
    content — to one of this WP's own ``review-cycle-N.md`` files must never
    be read as "new" reviewer feedback (research.md R2).

    Path-identity and content-identity are checked independently (neither
    short-circuits the other's necessity): a feedback file living at a
    ``review-cycle-N.md``-shaped path inside *sub_artifact_dir* is refused
    even if its content has been hand-edited to no longer match any existing
    cycle's body — only a genuine path check catches that case.

    T045 (FR-004/SC-001 narrowing, operator-sanctioned): the content leg used
    to be a body-EQUALITY comparison against every prior cycle's stored body
    (both sides run through frontmatter-stripping + whitespace normalization —
    fold ``ca53e0bbd``, M4 of the adversarial squad on PR #3156). That
    mechanism refused ANY exact-content match, including a genuinely DISTINCT
    reviewer's honest re-report of the same defect in the same words — which
    FR-004/SC-001 require to be admissible ("a reviewer can re-report a
    recurring defect using byte-identical feedback"). The content leg is
    narrowed to a SELF-CONTAINED question that does not need the old
    equality comparison at all: does *feedback_source* itself PARSE as a
    ``ReviewCycleArtifact`` (valid frontmatter + required fields)? A byte-copy
    of a stored verdict record parses successfully (it IS a verdict record,
    regardless of which prior cycle it copies or whether that cycle is even
    readable) and stays refused — preserving C-002's guarantee that a verdict
    record re-submitted as feedback is refused, by path AND content. Plain
    reviewer prose — even prose that is byte-identical to a prior cycle's
    stored body — does not parse (no YAML frontmatter mapping) and is now
    admitted, closing FR-004's gap. This mechanism change retires
    ``_content_identity``/``_strip_frontmatter``/``_normalize_whitespace``
    (no longer called): the GUARANTEE those helpers protected (#990/#2996(b))
    is preserved by the parse-check below, per C-002's "mechanism may change,
    guarantee may not weaken."

    Residual, consciously accepted (do not treat as a gap to close later): a
    byte-copy of an artifact whose frontmatter has been manually stripped
    parses AS PROSE, not as an artifact, so it is now admitted too — at that
    point the input is textually indistinguishable from a reviewer re-typing
    the same prose verbatim, which FR-004 explicitly licenses. No rule can
    separate "a human re-typed this" from "a machine stripped the
    frontmatter off a copy" once the frontmatter is gone; this is the
    necessary, honest cost of closing FR-004's gap, not an oversight.
    """
    resolved_feedback = feedback_source.resolve()
    resolved_dir = sub_artifact_dir.resolve()
    if (
        resolved_feedback.parent == resolved_dir
        and _REVIEW_CYCLE_FILE_RE.fullmatch(resolved_feedback.name) is not None
    ):
        raise ReviewCycleError(
            "feedback_source is this WP's own review-cycle artifact "
            f"({resolved_feedback.name}); pass the underlying reviewer "
            "feedback instead of a prior review-cycle artifact."
        )

    try:
        ReviewCycleArtifact.from_file(feedback_source)
    except (ValueError, OSError):
        return
    raise ReviewCycleError(
        "feedback_source content parses as a review-cycle artifact "
        f"({feedback_source.name}); pass distinct reviewer feedback instead "
        "of a prior review-cycle artifact's content."
    )


def _commit_failure_message(
    *,
    wp_id: str,
    mission_slug: str,
    cycle_number: int,
    artifact_path: Path,
    result: CommitArtifactResult,
    exhausted_contention_retries: bool,
) -> str:
    """Build the hard-failure message for a non-``"committed"`` commit result.

    T042: distinguishes "exhausted contention retries" (the probe kept firing
    across every retry) from a plain, non-transient commit failure, so an
    operator/log-reader can tell the two apart rather than seeing an
    identical message for both.
    """
    prefix = (
        f"Exhausted contention retries committing review-cycle-{cycle_number} "
        "artifact"
        if exhausted_contention_retries
        else f"Failed to commit review-cycle-{cycle_number} artifact"
    )
    return (
        f"{prefix} for {wp_id} on {mission_slug} (status={result.status!r}): "
        f"{result.diagnostic or 'no diagnostic provided'}. The artifact "
        f"was written to {artifact_path} but is NOT committed."
    )


def _commit_review_cycle_artifact(
    commit_router: CoordCommitRouter,
    *,
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
    artifact_path: Path,
    cycle_number: int,
    verdict: str,
    effective_root: Path | None = None,
) -> VerdictPersistenceOutcome:
    """Persist evidence through the existing router and verify its Git ref.

    No router status alone is durable proof.  A ``committed`` result becomes
    durable only when ``git show <placement-ref>:<evidence-ref>`` returns the
    exact local bytes.  Other result statuses become typed failures while the
    complete artifact remains available for an identical retry.  The legacy
    short retry on a corroborated Git-operation marker is preserved, entirely
    outside ``feature_status_lock``; checkout-wide queue ownership belongs to
    WP04 and is intentionally absent from this function.
    """
    message = (
        f"chore: Record review-cycle-{cycle_number} ({verdict}) for {wp_id} on "
        f"{mission_slug}"
    )
    mission = MissionHandle(
        repo_root=main_repo_root,
        mission_slug=mission_slug,
        effective_root=effective_root,
    )
    policy = ProtectionPolicy.resolve(main_repo_root)
    operation_root = effective_root or main_repo_root

    attempt = 1
    while True:
        result = commit_router.commit_artifact(
            mission,
            (artifact_path,),
            message,
            kind=MissionArtifactKind.REVIEW_CYCLE,
            policy=policy,
        )
        evidence_ref = _evidence_ref(operation_root, artifact_path)
        destination_ref = result.placement_ref or placement_seam(
            main_repo_root, mission_slug, effective_root=effective_root
        ).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
        if result.status == "committed":
            destination_bytes = _read_artifact_at_ref(
                operation_root, destination_ref, evidence_ref
            )
            local_bytes = artifact_path.read_bytes()
            if destination_bytes == local_bytes:
                return VerdictPersistenceOutcome(
                    classification="durable",
                    verdict_durably_persisted=True,
                    evidence_ref=evidence_ref,
                    destination_ref=destination_ref,
                    reason=None,
                    message=(
                        "Review-cycle evidence is committed and verified at "
                        f"{destination_ref}."
                    ),
                )
            reason = (
                "destination_readback_missing"
                if destination_bytes is None
                else "destination_readback_mismatch"
            )
            return VerdictPersistenceOutcome(
                classification="persistence_failed",
                verdict_durably_persisted=False,
                evidence_ref=evidence_ref,
                destination_ref=destination_ref,
                reason=reason,
                message=(
                    "Commit router reported committed, but exact evidence bytes "
                    f"were not verified at {destination_ref}."
                ),
            )

        contending = result.status == "error" and git_operation_in_progress(main_repo_root)
        if not contending or attempt >= _COMMIT_CONTENTION_MAX_ATTEMPTS:
            logger.warning(
                "%s",
                _commit_failure_message(
                    wp_id=wp_id,
                    mission_slug=mission_slug,
                    cycle_number=cycle_number,
                    artifact_path=artifact_path,
                    result=result,
                    exhausted_contention_retries=contending,
                ),
            )
            reason = {
                "unchanged": "unchanged_unverified",
                "no_op_wrong_surface": "wrong_surface",
                "error": "commit_error",
            }.get(result.status, "commit_failed")
            return VerdictPersistenceOutcome(
                classification="persistence_failed",
                verdict_durably_persisted=False,
                evidence_ref=evidence_ref,
                destination_ref=destination_ref,
                reason=reason,
                message=_commit_failure_message(
                    wp_id=wp_id,
                    mission_slug=mission_slug,
                    cycle_number=cycle_number,
                    artifact_path=artifact_path,
                    result=result,
                    exhausted_contention_retries=contending,
                ),
            )
        time.sleep(_COMMIT_CONTENTION_RETRY_SLEEP_SECONDS)
        attempt += 1


def _evidence_ref(main_repo_root: Path, artifact_path: Path) -> str:
    """Return the stable repository-relative evidence path."""
    try:
        return artifact_path.resolve().relative_to(main_repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise ReviewCycleError(
            f"Review-cycle artifact is outside the repository: {artifact_path}"
        ) from exc


def _read_artifact_at_ref(
    main_repo_root: Path, destination_ref: str, evidence_ref: str
) -> bytes | None:
    """Read exact evidence bytes from the governed Git ref, if present."""
    completed = subprocess.run(
        ["git", "show", f"{destination_ref}:{evidence_ref}"],
        cwd=main_repo_root,
        capture_output=True,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def _canonical_affected_files(
    affected_files: list[AffectedFile],
) -> tuple[tuple[str, str | None], ...]:
    return tuple(sorted((item.path, item.line_range) for item in affected_files))


@dataclass(frozen=True)
class _RetainedReviewCycleCandidate:
    artifact: ReviewCycleArtifact
    path: Path
    local_bytes: bytes


def _local_matching_retained_review_cycles(
    *,
    mission_slug: str,
    wp_id: str,
    sub_artifact_dir: Path,
    reviewer_agent: str,
    affected_files: list[AffectedFile],
    body: str,
) -> tuple[_RetainedReviewCycleCandidate, ...]:
    """Enumerate matching local evidence while the caller holds the short lock.

    This helper is filesystem-only by contract. Placement resolution and Git
    reachability checks happen after the caller releases ``feature_status_lock``.
    """
    wanted_affected = _canonical_affected_files(affected_files)
    matches: list[_RetainedReviewCycleCandidate] = []
    for candidate_path in sorted(sub_artifact_dir.glob("review-cycle-*.md")):
        try:
            candidate = validate_review_artifact_file(candidate_path)
        except ValueError:
            continue
        if (
            candidate.mission_slug != mission_slug
            or candidate.wp_id != wp_id
            or candidate.reviewer_agent != (reviewer_agent or "unknown")
            or candidate.body != body
            or _canonical_affected_files(candidate.affected_files) != wanted_affected
        ):
            continue
        matches.append(
            _RetainedReviewCycleCandidate(
                artifact=candidate,
                path=candidate_path,
                local_bytes=candidate_path.read_bytes(),
            )
        )
    return tuple(matches)


def _allocate_and_write_review_cycle_while_locked(
    *,
    mission_slug: str,
    wp_id: str,
    sub_artifact_dir: Path,
    reviewer_agent: str,
    affected_files: list[AffectedFile],
    body: str,
    reproduction_command: str | None = None,
) -> tuple[ReviewCycleArtifact, Path, str]:
    """Allocate, write, and validate with an already-held status lock."""
    cycle_n = ReviewCycleArtifact.next_cycle_number(sub_artifact_dir)
    filename = _validate_review_cycle_filename(f"review-cycle-{cycle_n}.md")
    artifact = ReviewCycleArtifact(
        cycle_number=cycle_n,
        wp_id=wp_id,
        mission_slug=mission_slug,
        reviewer_agent=reviewer_agent or "unknown",
        reviewed_at=now_utc().strftime(UTC_SECOND_TIMESTAMP_FORMAT),
        affected_files=affected_files,
        reproduction_command=reproduction_command,
        body=body,
    )
    validate_review_artifact(artifact)

    artifact_path = sub_artifact_dir / filename
    try:
        artifact.write(artifact_path)
        validate_review_artifact_file(artifact_path)
    except ReviewCycleError:
        artifact_path.unlink(missing_ok=True)
        raise
    return artifact, artifact_path, filename


def _in_queue_status_lock_timeout(main_repo_root: Path) -> float:
    """Bound the status-lock wait only when the verdict-save queue is held.

    The unbounded-hang hazard the bound closes (#3773 item 1) exists solely on
    the queue-held path: while a caller owns the checkout-wide verdict queue, an
    indefinitely-blocked ``feature_status_lock`` acquisition would wedge every
    other verdict save in the checkout. There, a ``FeatureStatusLockTimeoutError``
    is caught and translated into the truthful ``verdict_durably_persisted: false``
    busy envelope by ``_persist_review_cycle_with_queue``.

    Off the queue (the ``--no-auto-commit`` and ``local_only`` feedback paths)
    that translation does not apply, so bounding there would only turn a rare
    contention into an envelope-less error; those paths keep the historical
    unbounded (``-1``) wait instead.

    A ``main_repo_root`` that does not resolve to a Git checkout (the local-only
    feedback path can run outside one) cannot own the checkout-wide queue at all
    -- ``verdict_save_queue_is_held`` raises ``GitTopologyError`` there rather
    than returning ``False`` -- so it is treated identically to "not held": the
    historical unbounded wait, never a crash inside the allocator.
    """
    try:
        queue_held = verdict_save_queue_is_held(main_repo_root)
    except GitTopologyError:
        return -1.0
    return DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS if queue_held else -1.0


def _allocate_and_write_review_cycle_locked(
    *,
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
    sub_artifact_dir: Path,
    reviewer_agent: str,
    affected_files: list[AffectedFile],
    body: str,
    reproduction_command: str | None = None,
) -> tuple[ReviewCycleArtifact, Path, str]:
    """Allocate the next cycle number, build, write, and validate the artifact.

    T041/FR-005 scope: this function's ``with feature_status_lock(...)`` body
    is the ENTIRE critical section this WP serializes — cycle-number
    allocation through the write and its post-write validation, and NOTHING
    past it. The commit call (:func:`_commit_review_cycle_artifact`) is a git
    subprocess invocation and stays OUTSIDE this lock (NFR-006 forbids
    holding an inter-process lock across a ``git`` subprocess).

    FR-003/SC-007 (WP06): no longer takes a ``verdict`` parameter --
    ``ReviewCycleArtifact`` carries no such field. The caller
    (:func:`create_rejected_review_cycle`) still threads its own ``verdict``
    parameter into the event-side :class:`~specify_cli.status.ReviewResult`
    and the best-effort commit message; neither of those is this function's
    concern.

    This is a DIFFERENT, disjoint critical section from ``_mt_execute``'s own
    ``feature_status_lock`` acquisition over the status-event emit
    (``tasks_move_task.py`` calls ``_mt_finalize_plan`` — which reaches this
    writer — BEFORE ``_mt_execute`` acquires its own lock instance). The two
    do not serialize against each other: this WP's FR-005 scope is
    deliberately narrowed to (cycle-number-allocation + artifact-write) only,
    not the wider (artifact, status-event) pair, which would require
    restructuring the caller's control flow and is out of this WP's reach.
    Callers must not wrap this helper in another status-lock scope: resolving
    the lock path itself consults Git before acquisition. Code that already
    owns the lock uses :func:`_allocate_and_write_review_cycle_while_locked`
    so no nested setup subprocess can run inside the critical section.

    T043: a write or post-write-validation failure unlinks the just-written
    file WHILE STILL HOLDING the lock (the ``try/except`` is nested inside
    the ``with`` block, not after it), so a racing second writer can never
    observe the orphan mid-cleanup and mistake it for a legitimate prior
    cycle.
    """
    with feature_status_lock(
        main_repo_root,
        mission_slug,
        timeout=_in_queue_status_lock_timeout(main_repo_root),
    ):
        return _allocate_and_write_review_cycle_while_locked(
            mission_slug=mission_slug,
            wp_id=wp_id,
            sub_artifact_dir=sub_artifact_dir,
            reviewer_agent=reviewer_agent or "unknown",
            affected_files=affected_files,
            body=body,
            reproduction_command=reproduction_command,
        )


def _adopt_or_allocate_review_cycle_locked(
    *,
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
    sub_artifact_dir: Path,
    reviewer_agent: str,
    affected_files: list[AffectedFile],
    body: str,
    reproduction_command: str | None = None,
    effective_root: Path | None = None,
) -> tuple[ReviewCycleArtifact, Path, str, bool]:
    """Adopt identical retained evidence or allocate a new record.

    Local enumeration/allocation and final candidate revalidation use the
    short mission status lock. Placement and ``git show`` execute between
    those critical sections, never inside either one. WP04 owns the one
    checkout-wide verdict queue lease around this non-acquiring operation.
    """
    operation_root = effective_root or main_repo_root
    destination_ref = placement_seam(
        main_repo_root, mission_slug, effective_root=effective_root
    ).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    with feature_status_lock(
        main_repo_root,
        mission_slug,
        timeout=_in_queue_status_lock_timeout(main_repo_root),
    ):
        candidates = _local_matching_retained_review_cycles(
            mission_slug=mission_slug,
            wp_id=wp_id,
            sub_artifact_dir=sub_artifact_dir,
            reviewer_agent=reviewer_agent,
            affected_files=affected_files,
            body=body,
        )
        if not candidates:
            artifact, artifact_path, filename = (
                _allocate_and_write_review_cycle_while_locked(
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    sub_artifact_dir=sub_artifact_dir,
                    reviewer_agent=reviewer_agent,
                    affected_files=affected_files,
                    body=body,
                    reproduction_command=reproduction_command,
                )
            )
            return artifact, artifact_path, filename, False

    pending: list[_RetainedReviewCycleCandidate] = []
    committed: list[_RetainedReviewCycleCandidate] = []
    for candidate in candidates:
        evidence_ref = _evidence_ref(operation_root, candidate.path)
        destination_bytes = _read_artifact_at_ref(
            operation_root, destination_ref, evidence_ref
        )
        if destination_bytes is None:
            pending.append(candidate)
        elif destination_bytes == candidate.local_bytes:
            committed.append(candidate)

    if len(pending) > 1:
        names = ", ".join(candidate.path.name for candidate in pending)
        raise ReviewCycleError(
            "Multiple identical pending review-cycle records are ambiguous: " + names
        )
    selected = (
        pending[0]
        if pending
        else max(committed, key=lambda candidate: candidate.artifact.cycle_number)
        if committed
        else None
    )

    with feature_status_lock(
        main_repo_root,
        mission_slug,
        timeout=_in_queue_status_lock_timeout(main_repo_root),
    ):
        refreshed = _local_matching_retained_review_cycles(
            mission_slug=mission_slug,
            wp_id=wp_id,
            sub_artifact_dir=sub_artifact_dir,
            reviewer_agent=reviewer_agent,
            affected_files=affected_files,
            body=body,
        )
        original_snapshot = {
            candidate.path: candidate.local_bytes for candidate in candidates
        }
        refreshed_snapshot = {
            candidate.path: candidate.local_bytes for candidate in refreshed
        }
        if refreshed_snapshot != original_snapshot:
            raise ReviewCycleError(
                "Retained review-cycle candidates changed during adoption; retry "
                "the verdict save instead of guessing."
            )
        if selected is None:
            artifact, artifact_path, filename = (
                _allocate_and_write_review_cycle_while_locked(
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    sub_artifact_dir=sub_artifact_dir,
                    reviewer_agent=reviewer_agent,
                    affected_files=affected_files,
                    body=body,
                    reproduction_command=reproduction_command,
                )
            )
            return artifact, artifact_path, filename, False

    return (
        selected.artifact,
        selected.path,
        selected.path.name,
        selected in committed,
    )


def create_rejected_review_cycle(
    *,
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
    wp_slug: str,
    feedback_source: Path | None = None,
    body: str | None = None,
    reviewer_agent: str = "unknown",
    affected_files: list[dict[str, str]] | None = None,
    verdict: Literal["approved", "rejected"] = "rejected",
    commit_router: CoordCommitRouter | None = None,
    reproduction_command: str | None = None,
    effective_root: Path | None = None,
) -> CreatedRejectedReviewCycle:
    """Create or adopt evidence and return a typed persistence outcome.

    ``verdict`` defaults to ``"rejected"`` so every pre-existing caller keeps
    behaving unchanged (C-002 / backward compatibility). ``commit_router`` is
    optional for the same reason: callers that do not thread a commit
    capability receive an explicit ``local_only`` outcome. Automatic callers
    adopt identical retained evidence before allocating a new cycle. This
    function never acquires the checkout-wide verdict queue; WP04 invokes it
    while holding the sole lease.

    ``reproduction_command`` (governance-at-the-gate WP04 / FR-007, additive):
    optional evidence-capture field threaded straight onto the written
    :class:`~specify_cli.review.artifacts.ReviewCycleArtifact`. ``None`` by
    default so every pre-existing caller stays byte-identical; the
    first-pass-approval writer (``tasks_verdict_persistence._persist_approved_
    review_cycle``) is the first caller to populate it, with the exact
    ``move-task`` command that reproduces the decision.

    Exactly one of ``feedback_source`` / ``body`` must be supplied:

    * ``feedback_source`` — a real, caller-supplied reviewer-feedback file.
      Routes through :func:`_guard_feedback_source_provenance` (path- AND
      content-identity checks) because this is the shape #990/#2996(b) guard
      against: a reviewer accidentally or maliciously re-submitting a prior
      cycle's own artifact as "new" feedback.
    * ``body`` — a body the CALLER ITSELF generated (e.g. the machine's
      synthesized ``"Approved by {reviewer}: {reference}"`` approval note).
      Bypasses the provenance guard entirely: a self-generated body is
      categorically not the attack the guard exists to refuse, and routing
      it through the content-identity arm produces a false collision when
      the same deterministic inputs (reviewer, ``--note``) repeat across
      cycles (M1 — adversarial squad finding on PR #3156). There is no
      on-disk file to path-check either, so the path-identity arm is moot
      for this leg.
    """
    if (feedback_source is None) == (body is None):
        raise ReviewCycleError(
            "create_rejected_review_cycle requires exactly one of "
            "feedback_source or body"
        )

    safe_mission_slug = _validate_segment("mission_slug", mission_slug)
    safe_wp_slug = _validate_segment("wp_slug", wp_slug)
    safe_wp_id = _validate_segment("wp_id", wp_id)
    # FR-001/FR-007 write-in-home: land the review-cycle artifact in its
    # ``tasks/<wp>/`` home via the shared owner function (``_review_cycle_
    # wp_dir`` -- deliberately still PRIMARY/WORK_PACKAGE_TASK-anchored; see
    # that function's own docstring for the disclosed reason ADR 2026-08-03-1's
    # full COORD-under-coord-topology flip is not yet shipped) — not a
    # caller-derived, kind-blind join. This fixes both this direct
    # site AND the move-task ``--review-feedback-file`` caller (which passes
    # no pre-resolved dir), from this one edit.
    operation_root = effective_root or main_repo_root
    sub_artifact_dir = _review_cycle_wp_dir(
        main_repo_root,
        safe_mission_slug,
        safe_wp_slug,
        effective_root=effective_root,
    )

    if feedback_source is not None:
        if not feedback_source.exists():
            raise ReviewCycleError(f"Review feedback file not found: {feedback_source}")
        if not feedback_source.is_file():
            raise ReviewCycleError(
                f"Review feedback path is not a file: {feedback_source}"
            )
        resolved_body = feedback_source.read_text(encoding="utf-8")
        if not resolved_body.strip():
            raise ReviewCycleError(f"Review feedback file is empty: {feedback_source}")
        _guard_feedback_source_provenance(
            feedback_source=feedback_source,
            sub_artifact_dir=sub_artifact_dir,
        )
    else:
        assert body is not None
        if not body.strip():
            raise ReviewCycleError("Review feedback body is empty")
        resolved_body = body

    parsed_affected: list[AffectedFile] = [
        AffectedFile(path=affected["path"], line_range=affected.get("line_range"))
        for affected in affected_files or []
    ]

    # T040/T041 (FR-005/NFR-006): allocation, artifact construction, the
    # write, and post-write validation are ONE critical section serialized
    # under ``feature_status_lock`` — see
    # ``_allocate_and_write_review_cycle_locked``'s docstring for the exact
    # scope and why the commit call below must stay outside it.
    if commit_router is None:
        artifact, artifact_path, filename = _allocate_and_write_review_cycle_locked(
            main_repo_root=main_repo_root,
            mission_slug=safe_mission_slug,
            wp_id=safe_wp_id,
            sub_artifact_dir=sub_artifact_dir,
            reviewer_agent=reviewer_agent,
            affected_files=parsed_affected,
            body=resolved_body,
            reproduction_command=reproduction_command,
        )
        already_committed = False
    else:
        artifact, artifact_path, filename, already_committed = (
            _adopt_or_allocate_review_cycle_locked(
                main_repo_root=main_repo_root,
                mission_slug=safe_mission_slug,
                wp_id=safe_wp_id,
                sub_artifact_dir=sub_artifact_dir,
                reviewer_agent=reviewer_agent,
                affected_files=parsed_affected,
                body=resolved_body,
                reproduction_command=reproduction_command,
                effective_root=effective_root,
            )
        )
    pointer = build_review_cycle_pointer(safe_mission_slug, safe_wp_slug, filename)

    evidence_ref = _evidence_ref(operation_root, artifact_path)
    governed_destination_ref = placement_seam(
        main_repo_root, safe_mission_slug, effective_root=effective_root
    ).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    if commit_router is None:
        persistence = VerdictPersistenceOutcome(
            classification="local_only",
            verdict_durably_persisted=False,
            evidence_ref=evidence_ref,
            destination_ref=None,
            reason="no_auto_commit",
            message="Review-cycle evidence was written locally without auto-commit.",
        )
    elif already_committed:
        persistence = VerdictPersistenceOutcome(
            classification="durable",
            verdict_durably_persisted=True,
            evidence_ref=evidence_ref,
            destination_ref=governed_destination_ref,
            reason=None,
            message=(
                "Identical review-cycle evidence was already committed and verified at "
                f"{governed_destination_ref}."
            ),
        )
    else:
        try:
            persistence = _commit_review_cycle_artifact(
                commit_router,
                main_repo_root=main_repo_root,
                mission_slug=safe_mission_slug,
                wp_id=safe_wp_id,
                artifact_path=artifact_path,
                cycle_number=artifact.cycle_number,
                verdict=verdict,
                effective_root=effective_root,
            )
        except Exception as exc:
            destination_bytes = _read_artifact_at_ref(
                operation_root, governed_destination_ref, evidence_ref
            )
            if destination_bytes == artifact_path.read_bytes():
                persistence = VerdictPersistenceOutcome(
                    classification="durable",
                    verdict_durably_persisted=True,
                    evidence_ref=evidence_ref,
                    destination_ref=governed_destination_ref,
                    reason=None,
                    message=(
                        "Commit raised after persistence, but exact evidence was "
                        f"verified at {governed_destination_ref}."
                    ),
                )
            else:
                reason = "commit_timeout" if isinstance(exc, TimeoutError) else "commit_exception"
                persistence = VerdictPersistenceOutcome(
                    classification="persistence_failed",
                    verdict_durably_persisted=False,
                    evidence_ref=evidence_ref,
                    destination_ref=governed_destination_ref,
                    reason=reason,
                    message=(
                        f"Review-cycle commit raised {type(exc).__name__}: {exc}. "
                        f"Evidence is retained at {evidence_ref}."
                    ),
                )

    review_result = ReviewResult(
        reviewer=artifact.reviewer_agent,
        # WP05 (verdict-seam-write-unification-01KZ9Q35, T025): routed through
        # the canonical artifact<->event verdict bridge (FR-005) instead of
        # re-inlining the ``rejected``/``changes_requested`` equivalence here
        # -- ``verdict`` is this function's own ``Literal["approved",
        # "rejected"]`` parameter, i.e. exactly
        # :data:`~specify_cli.status.verdict_vocab.EmissionArtifactVerdict`,
        # so :func:`~specify_cli.status.verdict_vocab.emission_event_verdict`
        # (the emission-scoped bridge -- this constructs an EMITTED
        # ``review_result``) is the correct conversion, not the general
        # four-value :func:`~specify_cli.status.verdict_vocab.to_event_verdict`.
        verdict=emission_event_verdict(verdict),
        reference=pointer,
        feedback_path=str(artifact_path),
    )
    return CreatedRejectedReviewCycle(
        artifact_path=artifact_path,
        pointer=pointer,
        artifact=artifact,
        review_result=review_result,
        persistence=persistence,
    )
