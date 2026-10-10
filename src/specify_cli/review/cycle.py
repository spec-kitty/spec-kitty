"""Shared review-cycle invariant boundary.

This module owns only rejected review-cycle artifact invariants:
artifact creation, required frontmatter validation, canonical pointer
construction/resolution, legacy feedback pointer normalization, and rejected
ReviewResult derivation.
"""

from __future__ import annotations

from kernel.clock import UTC_SECOND_TIMESTAMP_FORMAT, now_utc
from kernel.git_topology import GitTopologyError
from mission_runtime import MissionArtifactKind, OwnedCheckout, WriteLocation, placement_seam
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CoordCommitRouter,
    MissionHandle,
)
from specify_cli.coordination.commit_outcome import SurfaceOutcome, commit_outcome_exit_code, render_commit_outcome
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
    git_operation_in_progress,
    mission_write_lock,
)
from specify_cli.missions._read_path_resolver import mission_write_lock_dir

logger = logging.getLogger(__name__)

# FR-004 (kernel-clock-single-door WP03): defined once on the door
# (kernel.clock.UTC_SECOND_TIMESTAMP_FORMAT), imported above; call sites here
# are untouched (package remediation is WP13c's job).
#: ``workflow-review-claim`` is the legacy spelling of ``action-review-claim``
#: still present in older event logs (#2267).
REVIEW_FEEDBACK_SENTINELS = frozenset({"force-override", "action-review-claim", "workflow-review-claim"})

#: #4327: synthetic approval/rejection tokens ``move-task`` mints when no real
#: pointer exists (``review:<WP>``, ``approval:<WP>``, ``auto-approval:<WP>:<date>``).
#: Like the exact-value sentinels above they are markers, not review-feedback
#: artifact pointers -- a reader must skip them instead of resolving them (and
#: then reporting a bogus "artifact is missing" against a WP that was approved,
#: never rejected). Prefix-matched because they embed the WP id.
#:
#: These three prefix constants are the SINGLE SOURCE OF TRUTH for the
#: synthetic ``review_ref`` grammar: ``SYNTHETIC_REVIEW_REF_PREFIXES`` (the
#: classifier's input) and the ``synthetic_*_ref`` mint formatters below are
#: both built from them, so a prefix rename here flows to mint and classify
#: together instead of drifting silently.
_REVIEW_PREFIX = "review:"
_APPROVAL_PREFIX = "approval:"
_AUTO_APPROVAL_PREFIX = "auto-approval:"

SYNTHETIC_REVIEW_REF_PREFIXES = (_REVIEW_PREFIX, _APPROVAL_PREFIX, _AUTO_APPROVAL_PREFIX)


def is_synthetic_review_ref(value: str) -> bool:
    """Whether *value* is a synthetic ``review_ref`` marker token (#4327).

    True only for a non-empty token carrying one of the synthetic prefixes --
    a bare prefix with nothing after it is not a token, and the real pointer
    families (``review-cycle://...``, ``feedback://...``) never match: they
    start with ``review-cycle:``/``feedback:``, not ``review:``/``approval:``.
    """
    stripped = value.strip()
    return any(stripped.startswith(prefix) and len(stripped) > len(prefix) for prefix in SYNTHETIC_REVIEW_REF_PREFIXES)


def synthetic_review_ref(wp_id: str) -> str:
    """Mint the synthetic rejection ``review_ref`` token for *wp_id* (#4327).

    Used when a rejection has no real review-feedback pointer to record.
    """
    return f"{_REVIEW_PREFIX}{wp_id}"


def synthetic_approval_ref(wp_id: str) -> str:
    """Mint the synthetic approval ``review_ref`` token for *wp_id* (#4327).

    Used when an approval has no ``--approval-ref`` and no real pointer.
    """
    return f"{_APPROVAL_PREFIX}{wp_id}"


def synthetic_auto_approval_ref(wp_id: str, date: str) -> str:
    """Mint the synthetic auto-approval ``review_ref`` token for *wp_id* on
    *date* (#4327). *date* is caller-formatted (``format_stamp(now_utc(), '%Y%m%d')``
    at the current call sites) -- this formatter does not touch the clock.
    """
    return f"{_AUTO_APPROVAL_PREFIX}{wp_id}:{date}"


def is_non_resolvable_review_ref(value: str) -> bool:
    """Whether *value* is a ``review_ref`` a reader must skip rather than
    resolve to a review-feedback artifact (#4327).

    Folds both non-artifact-pointer families a review-feedback reader needs
    to skip: the exact-value operational sentinels (``REVIEW_FEEDBACK_SENTINELS``,
    e.g. ``action-review-claim``) and the synthetic approval/rejection marker
    tokens (:func:`is_synthetic_review_ref`). Kept alongside both source sets
    so a reader has one predicate instead of re-deriving the two-rule check
    at each call site.
    """
    return value in REVIEW_FEEDBACK_SENTINELS or is_synthetic_review_ref(value)


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


def next_review_feedback_source_path(sub_artifact_dir: Path, sibling_dirs: tuple[Path, ...] = ()) -> Path:
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

    *sibling_dirs* (#5194) are the other surfaces readers consult, from
    :func:`_review_cycle_read_candidate_dirs`; the number is taken over the
    union, exactly as the allocator does, so the advertised path matches the
    cycle that will be written.

    Raises:
        ValueError: propagate :meth:`ReviewCycleArtifact.next_cycle_number`'s
            refusal (unparseable sibling filename, or a colliding next number)
            — a caller advertising a path the writer would refuse must fail
            closed with the same repair message, not print a command that
            cannot be run as printed.
    """
    return review_feedback_source_path(
        sub_artifact_dir,
        ReviewCycleArtifact.next_cycle_number(sub_artifact_dir, sibling_dirs),
    )


def _review_cycle_wp_dir(
    repo_root: Path,
    mission_slug: str,
    wp_slug: str,
    *,
    kind: MissionArtifactKind = MissionArtifactKind.REVIEW_CYCLE,
    owned: OwnedCheckout | None = None,
) -> Path:
    """Return the ``tasks/<wp>`` dir a review-cycle artifact is READ from.

    **ADR 2026-08-03-1 designates ``review-cycle-N.md`` as
    ``MissionArtifactKind.REVIEW_CYCLE`` — COORD-partition per-work-package
    bookkeeping under a coordination topology, PRIMARY otherwise.** This is
    the shared owner function every READER in this mission's scope routes
    through — the pointer resolver (:func:`resolve_review_cycle_pointer`),
    the arbiter (:func:`specify_cli.review.arbiter.persist_arbiter_decision`),
    the safety verdict reader (``tasks_verdict_persistence.py::
    _resolve_verdict_wp_dir``), and the fix-mode / prior-rejection probes
    (``workflow_cores.py::has_prior_rejection``,
    ``workflow_executor.py::implement_try_render_fix_mode_prompt``) — all
    resolve through this single call, every one at its default ``kind`` (no
    caller passes ``kind=`` — the AST guard in
    ``tests/coordination/test_verdict_dir_co_resolution.py`` enforces exactly
    that shape).

    **WP08 (coord-artifact-single-home-01M3V4BE): the default flipped to
    ``REVIEW_CYCLE``.** Every reader above now resolves the coordination
    worktree directory under a coordination-routed, materialized Mission
    (never the PRIMARY repository-root checkout) — closing the fail-open
    hazard a prior revision of this docstring disclosed: moving only the
    WRITE seam would have left every reader above still looking at PRIMARY,
    blind to a rejection that now lives solely on the coordination surface.
    Flipping this shared default moves every one of them in lockstep.

    **This is a READ-mode resolver (:meth:`~mission_runtime.resolution.
    PlacementSeam.read_dir`), not the write location.** The WRITE seam
    (:func:`create_rejected_review_cycle`) resolves its directory through
    :func:`_review_cycle_write_dir` instead, which uses :meth:`~mission_runtime.
    resolution.PlacementSeam.write_dir` — materializing/seeding an EMPTY
    coordination surface rather than silently falling back to PRIMARY
    (FR-014: a read resolver is never a write location). The two converge on
    the SAME directory once the coordination surface is MATERIALIZED (the
    steady state every reader above observes), which is exactly what lets
    them share this one function at its default ``kind``.

    A caller MAY still pass ``kind=MissionArtifactKind.WORK_PACKAGE_TASK`` (or
    any other kind) to resolve a different partition explicitly — no real
    caller does, so the AST guard treats any non-default, non-``REVIEW_CYCLE``
    ``kind=`` keyword as a poison arm.

    **Decision `plan.design.review-cycle-read-fallback` (WP08 cycle 2, C-002
    read-only fallback).** A rejection recorded BEFORE this Mission's
    single-home write flip (a ``local_only`` outcome -- ``--no-auto-commit``
    or ``commit_router=None``) physically lives ONLY in the PRIMARY
    repository-root checkout; it was never staged onto the coordination
    surface. Resolving unconditionally to the coordination directory would
    make that old-but-real rejection invisible to every reader (fail-open --
    ``has_prior_rejection`` and the fix-mode render would both silently miss
    it). So when the coordination directory exists but carries NO
    ``review-cycle-*.md`` files for this WP, this function falls back to the
    PRIMARY directory IF IT has them -- read-only, never the reverse: a
    coordination copy, once present, always wins (the steady state every
    other reader-co-resolution test pins), and nothing here ever writes to
    PRIMARY (:func:`create_rejected_review_cycle` resolves its own directory
    through the separate write-side seam, :func:`_review_cycle_write_dir`,
    which never falls back).

    Historically retired the lenient kind-aware ``resolve_planning_read_dir``
    fold (and the kind-blind ``candidate_feature_dir_for_mission`` fold that
    resolved the coord worktree for a coord-topology mission —
    #2646/#2697/#2275). ``MissionSelectorAmbiguous`` propagates unchanged (no
    silent pick — C-009).

    ``owned`` is the validated owned checkout, when the command runs against
    one: the directory is then resolved from the fact and never from the
    repository root checkout.
    """
    seam = placement_seam(repo_root, mission_slug, owned=owned)
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

        coord_wp_dir = mission_dir / "tasks" / wp_slug
        if _has_review_cycle_files(coord_wp_dir):
            return coord_wp_dir
        # Decision plan.design.review-cycle-read-fallback (see docstring):
        # the coordination surface is live but carries nothing for this WP --
        # look for an old, pre-single-home local-only rejection on PRIMARY
        # before declaring the (empty) coordination dir the answer.
        primary_dir: Path = seam.read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
        primary_wp_dir = primary_dir / "tasks" / wp_slug
        if _has_review_cycle_files(primary_wp_dir):
            return primary_wp_dir
        return coord_wp_dir

    resolved_dir: Path = seam.read_dir(kind)
    return resolved_dir / "tasks" / wp_slug


def _review_cycle_read_candidate_dirs(
    repo_root: Path,
    mission_slug: str,
    wp_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[Path, ...]:
    """Every ``tasks/<wp>`` dir a reader may find ``review-cycle-N.md`` in (#5194).

    Mirrors the candidates :func:`_review_cycle_wp_dir` consults: the REVIEW_CYCLE
    surface (COORD under a coordination topology) and the PRIMARY
    WORK_PACKAGE_TASK surface it falls back to. The allocator numbers a new
    cycle from the union, so a cycle recorded on one surface is never numbered
    again by a write to the other. Read-only: nothing here resolves a write
    location.
    """
    seam = placement_seam(repo_root, mission_slug, owned=owned)
    candidates = [_review_cycle_wp_dir(repo_root, mission_slug, wp_slug, owned=owned)]
    candidates.append(seam.read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks" / wp_slug)
    return tuple(dict.fromkeys(candidates))


def _has_review_cycle_files(wp_dir: Path) -> bool:
    """True iff *wp_dir* exists and carries at least one ``review-cycle-*.md``."""
    return wp_dir.is_dir() and any(wp_dir.glob("review-cycle-*.md"))


def _review_cycle_write_location(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> WriteLocation:
    """Return the :class:`~mission_runtime.write_location.WriteLocation`
    a NEW review-cycle artifact for this Mission must be written to.

    The ONE write-side counterpart to :func:`_review_cycle_wp_dir` (a
    READ-mode resolver). Routes through :meth:`~mission_runtime.resolution.
    PlacementSeam.write_dir` (contracts/write-location-accessor.md) instead of
    ``read_dir``, so an EMPTY coordination surface is materialized/seeded
    (or an UNMATERIALIZED local head is checked out) rather than silently
    substituting the PRIMARY checkout for a real coordination write (FR-014).
    Called exactly ONCE per :func:`create_rejected_review_cycle` invocation —
    ``write_dir`` may have side effects (seeding/materializing), so its
    result (including ``.surface_root``, the basis every evidence-path
    computation in this module now uses) is threaded through rather than
    re-derived.

    WP20's census scans this module for the write-side directory resolver by
    this qualname (``_review_cycle_write_dir`` was the alternative the WP08
    prompt offered; this is the ``WriteLocation``-returning shape it chose,
    since the caller also needs ``.surface_root`` for evidence-path
    relativization — see :func:`_evidence_ref`).
    """
    return placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.REVIEW_CYCLE)


def _review_cycle_write_dir(location: WriteLocation, wp_slug: str) -> Path:
    """Compose the per-WP sub-artifact directory from a resolved *location*."""
    return location.path / "tasks" / wp_slug


class ReviewCycleError(ValueError):
    """Raised when a review-cycle invariant cannot be satisfied."""


DurabilityClassification: TypeAlias = Literal["durable", "busy", "persistence_failed", "local_only"]


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
        candidate = (_review_cycle_wp_dir(repo_root, parts.mission_slug, parts.wp_slug) / parts.filename).resolve()
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


def _guard_feedback_source_provenance(*, feedback_source: Path, sub_artifact_dir: Path) -> None:
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
    if resolved_feedback.parent == resolved_dir and _REVIEW_CYCLE_FILE_RE.fullmatch(resolved_feedback.name) is not None:
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


def _with_surface_detail(message: str, result: CommitArtifactResult) -> str:
    """Append the shared ``render_commit_outcome`` lines to *message* (T046
    step 1 / contract rule 6, review cycle 2 B3).

    EVERY ``VerdictPersistenceOutcome.message`` this module builds carries
    this -- the durable arm, the readback-mismatch arm, the masked-refusal
    arm, and every non-committed arm (``unchanged`` / ``no_op_wrong_surface``
    / ``error`` / exhausted-retry) alike -- so an actionable surface fact
    (for example a ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip on the coordination
    group) is never visible on only ONE arm while every other arm falls back
    to the legacy top-level ``status``/``diagnostic`` alone. ``[]`` (the
    empty-surfaces legacy case) leaves *message* untouched.
    """
    lines = render_commit_outcome(result)
    if not lines:
        return message
    return f"{message} Surfaces: {'; '.join(lines)}"


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
        f"Exhausted contention retries committing review-cycle-{cycle_number} artifact"
        if exhausted_contention_retries
        else f"Failed to commit review-cycle-{cycle_number} artifact"
    )
    return _with_surface_detail(
        f"{prefix} for {wp_id} on {mission_slug} (status={result.status!r}): "
        f"{result.diagnostic or 'no diagnostic provided'}. The artifact "
        f"was written to {artifact_path} but is NOT committed.",
        result,
    )


def _first_refused_surface_reason(surfaces: tuple[SurfaceOutcome, ...]) -> str | None:
    """Return the reason of the first refused/error surface's first named path.

    Falls back to the surface's own ``diagnostic`` (a bare refusal with no
    named path), then ``None`` when nothing actionable is present.
    """
    for outcome in surfaces:
        if outcome.status not in ("refused", "error"):
            continue
        if outcome.refused:
            # ``SurfaceOutcome``/``PathFate`` are typed ``str`` fields, but
            # mypy widens them to ``Any`` through the ``follow_imports=skip``
            # boundary on ``specify_cli.*``; bind explicitly so the return
            # narrows back to ``str``.
            refused_reason: str = outcome.refused[0].reason
            return refused_reason
        if outcome.diagnostic:
            diagnostic: str = outcome.diagnostic
            return diagnostic
    return None


def _masked_surface_outcome(
    *,
    wp_id: str,
    mission_slug: str,
    cycle_number: int,
    result: CommitArtifactResult,
    evidence_ref: str,
    destination_ref: str,
) -> VerdictPersistenceOutcome:
    """Build the ``persistence_failed`` outcome for a masked refusal (FR-007).

    The router's legacy top-level ``status`` reported ``"committed"`` (the
    caller-surface projection, contract rule 4), but ``commit_outcome_exit_code``
    says a surface was refused/errored -- the OWNING copy can never be masked
    as a success. Renders through the shared ``render_commit_outcome`` trio
    (contract rule 6): no hand-formatted surface summary.
    """
    message = _with_surface_detail(
        f"Review-cycle-{cycle_number} commit for {wp_id} on {mission_slug} reported committed, but a surface was refused.",
        result,
    )
    logger.warning("%s", message)
    return VerdictPersistenceOutcome(
        classification="persistence_failed",
        verdict_durably_persisted=False,
        evidence_ref=evidence_ref,
        destination_ref=destination_ref,
        reason=_first_refused_surface_reason(result.surfaces) or "surface_refused",
        message=message,
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
    owned: OwnedCheckout | None = None,
    surface_root: Path | None = None,
) -> VerdictPersistenceOutcome:
    """Persist evidence through the existing router and verify its Git ref.

    No router status alone is durable proof.  A ``committed`` result becomes
    durable only when ``git show <placement-ref>:<evidence-ref>`` returns the
    exact local bytes AND no surface the contract (``commit_outcome_exit_code``)
    classifies as refused/errored -- the legacy top-level ``status`` alone
    (contract rule 4's caller-surface projection) is never trusted for success
    (FR-007 masking).  Other result statuses become typed failures while the
    complete artifact remains available for an identical retry.  The legacy
    short retry on a corroborated Git-operation marker is preserved, entirely
    outside ``feature_status_lock``; checkout-wide queue ownership belongs to
    WP04 and is intentionally absent from this function.

    ``owned`` (the validated owned checkout, when present) supplies the
    mission handle and the operation root the evidence path is relative to.
    ``surface_root`` (WP08, P-M3) is the basis the evidence path is relative
    to -- the coordination worktree root for a coordination-routed write, or
    the repository-root checkout otherwise (:attr:`~mission_runtime.
    write_location.WriteLocation.surface_root`). It defaults to the operation
    root (pre-WP08 behaviour) when the caller does not supply one.
    """
    message = f"chore: Record review-cycle-{cycle_number} ({verdict}) for {wp_id} on {mission_slug}"
    mission = MissionHandle(
        repo_root=main_repo_root,
        mission_slug=mission_slug,
        owned=owned,
    )
    # #5947 owned-correctness: when a validated owned checkout is in hand, the
    # protection decision must consume that fact (owned.repository_root + the
    # owned checkout's own config, scoped to this mission's write) rather than an
    # R-only, mission-unscoped policy built from main_repo_root. Non-owned
    # callers keep the repository-root resolve unchanged.
    policy = ProtectionPolicy.resolve_for_owned(owned, mission_slug) if owned is not None else ProtectionPolicy.resolve(main_repo_root)
    operation_root = _operation_root(main_repo_root, owned)
    evidence_root = surface_root if surface_root is not None else operation_root

    attempt = 1
    while True:
        result = commit_router.commit_artifact(
            mission,
            (artifact_path,),
            message,
            kind=MissionArtifactKind.REVIEW_CYCLE,
            policy=policy,
        )
        evidence_ref = _evidence_ref(evidence_root, artifact_path)
        destination_ref = result.placement_ref or placement_seam(main_repo_root, mission_slug, owned=owned).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
        if result.status == "committed":
            if commit_outcome_exit_code(result) != 0:
                return _masked_surface_outcome(
                    wp_id=wp_id,
                    mission_slug=mission_slug,
                    cycle_number=cycle_number,
                    result=result,
                    evidence_ref=evidence_ref,
                    destination_ref=destination_ref,
                )
            destination_bytes = _read_artifact_at_ref(operation_root, destination_ref, evidence_ref)
            local_bytes = artifact_path.read_bytes()
            if destination_bytes == local_bytes:
                return VerdictPersistenceOutcome(
                    classification="durable",
                    verdict_durably_persisted=True,
                    evidence_ref=evidence_ref,
                    destination_ref=destination_ref,
                    reason=None,
                    message=_with_surface_detail(
                        f"Review-cycle evidence is committed and verified at {destination_ref}.",
                        result,
                    ),
                )
            reason = "destination_readback_missing" if destination_bytes is None else "destination_readback_mismatch"
            return VerdictPersistenceOutcome(
                classification="persistence_failed",
                verdict_durably_persisted=False,
                evidence_ref=evidence_ref,
                destination_ref=destination_ref,
                reason=reason,
                message=_with_surface_detail(
                    f"Commit router reported committed, but exact evidence bytes were not verified at {destination_ref}.",
                    result,
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


def _operation_root(main_repo_root: Path, owned: OwnedCheckout | None) -> Path:
    """Return the checkout root a review-cycle operation reads and commits in.

    The one place the "owned checkout, else the caller's root" choice is made;
    evidence paths and ``git show`` read-backs are relative to it.
    """
    return owned.owned_root if owned is not None else main_repo_root


def _evidence_ref(surface_root: Path, artifact_path: Path) -> str:
    """Return *artifact_path* relative to the checkout that CONTAINS it.

    WP08 (P-M3): *surface_root* must be the root of the checkout the
    artifact physically lives under -- the coordination worktree root for a
    coordination-routed write (:attr:`~mission_runtime.write_location.
    WriteLocation.surface_root`), or the repository-root checkout otherwise.
    Relativizing against the WRONG checkout (e.g. always the repository-root
    checkout, even when the artifact lives in the nested coordination
    worktree under it) yields a path the ``git show <ref>:<path>`` read-back
    cannot find (``destination_readback_missing``) even though the commit
    genuinely landed.
    """
    try:
        return artifact_path.resolve().relative_to(surface_root.resolve()).as_posix()
    except ValueError as exc:
        raise ReviewCycleError(f"Review-cycle artifact is outside the repository: {artifact_path}") from exc


def _read_artifact_at_ref(main_repo_root: Path, destination_ref: str, evidence_ref: str) -> bytes | None:
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
    sibling_dirs: tuple[Path, ...] = (),
) -> tuple[ReviewCycleArtifact, Path, str]:
    """Allocate, write, and validate with an already-held status lock."""
    cycle_n = ReviewCycleArtifact.next_cycle_number(sub_artifact_dir, sibling_dirs)
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


def _review_cycle_lock_target(main_repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> tuple[Path, Path]:
    """``(Mission directory, lock root)`` for the review-cycle write lock.

    An owned checkout locks on the fact's own Mission directory and repository root: both are known, so
    the Mission directory is never resolved from the repository root through the read-path resolver.
    """
    if owned is not None:
        return owned.mission_dir, owned.repository_root
    return mission_write_lock_dir(main_repo_root, mission_slug), main_repo_root


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
    sibling_dirs: tuple[Path, ...] = (),
    owned: OwnedCheckout | None = None,
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
    (``tasks_move_task_executor`` calls ``_mt_finalize_plan`` — which reaches this
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
    lock_dir, lock_root = _review_cycle_lock_target(main_repo_root, mission_slug, owned)
    with mission_write_lock(
        lock_dir,
        repo_root=lock_root,
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
            sibling_dirs=sibling_dirs,
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
    sibling_dirs: tuple[Path, ...] = (),
    owned: OwnedCheckout | None = None,
    surface_root: Path | None = None,
) -> tuple[ReviewCycleArtifact, Path, str, bool]:
    """Adopt identical retained evidence or allocate a new record.

    Local enumeration/allocation and final candidate revalidation use the
    short mission status lock. Placement and ``git show`` execute between
    those critical sections, never inside either one. WP04 owns the one
    checkout-wide verdict queue lease around this non-acquiring operation.
    ``owned`` (the validated owned checkout, when present) supplies the
    placement seam and the operation root. ``surface_root`` (WP08, P-M3) is
    the basis retained-candidate evidence paths are relativized against;
    defaults to the operation root when the caller does not supply one.
    """
    operation_root = _operation_root(main_repo_root, owned)
    evidence_root = surface_root if surface_root is not None else operation_root
    destination_ref = placement_seam(main_repo_root, mission_slug, owned=owned).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    lock_dir, lock_root = _review_cycle_lock_target(main_repo_root, mission_slug, owned)
    with mission_write_lock(
        lock_dir,
        repo_root=lock_root,
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
            artifact, artifact_path, filename = _allocate_and_write_review_cycle_while_locked(
                mission_slug=mission_slug,
                wp_id=wp_id,
                sub_artifact_dir=sub_artifact_dir,
                reviewer_agent=reviewer_agent,
                affected_files=affected_files,
                body=body,
                reproduction_command=reproduction_command,
                sibling_dirs=sibling_dirs,
            )
            return artifact, artifact_path, filename, False

    pending: list[_RetainedReviewCycleCandidate] = []
    committed: list[_RetainedReviewCycleCandidate] = []
    for candidate in candidates:
        evidence_ref = _evidence_ref(evidence_root, candidate.path)
        destination_bytes = _read_artifact_at_ref(operation_root, destination_ref, evidence_ref)
        if destination_bytes is None:
            pending.append(candidate)
        elif destination_bytes == candidate.local_bytes:
            committed.append(candidate)

    if len(pending) > 1:
        names = ", ".join(candidate.path.name for candidate in pending)
        raise ReviewCycleError("Multiple identical pending review-cycle records are ambiguous: " + names)
    selected = pending[0] if pending else max(committed, key=lambda candidate: candidate.artifact.cycle_number) if committed else None

    with mission_write_lock(
        lock_dir,
        repo_root=lock_root,
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
        original_snapshot = {candidate.path: candidate.local_bytes for candidate in candidates}
        refreshed_snapshot = {candidate.path: candidate.local_bytes for candidate in refreshed}
        if refreshed_snapshot != original_snapshot:
            raise ReviewCycleError("Retained review-cycle candidates changed during adoption; retry the verdict save instead of guessing.")
        if selected is None:
            artifact, artifact_path, filename = _allocate_and_write_review_cycle_while_locked(
                mission_slug=mission_slug,
                wp_id=wp_id,
                sub_artifact_dir=sub_artifact_dir,
                reviewer_agent=reviewer_agent,
                affected_files=affected_files,
                body=body,
                reproduction_command=reproduction_command,
                sibling_dirs=sibling_dirs,
            )
            return artifact, artifact_path, filename, False

    return (
        selected.artifact,
        selected.path,
        selected.path.name,
        selected in committed,
    )


def _resolve_review_body(
    *,
    feedback_source: Path | None,
    body: str | None,
    sub_artifact_dir: Path,
) -> str:
    """Return the review-cycle body from exactly one of ``feedback_source`` / ``body``.

    A ``feedback_source`` file is validated (exists, is a file, non-empty) and
    then routed through :func:`_guard_feedback_source_provenance`; a
    caller-generated ``body`` bypasses that guard (see
    :func:`create_rejected_review_cycle`).
    """
    if feedback_source is None:
        assert body is not None
        if not body.strip():
            raise ReviewCycleError("Review feedback body is empty")
        return body
    if not feedback_source.exists():
        raise ReviewCycleError(f"Review feedback file not found: {feedback_source}")
    if not feedback_source.is_file():
        raise ReviewCycleError(f"Review feedback path is not a file: {feedback_source}")
    resolved_body = feedback_source.read_text(encoding="utf-8")
    if not resolved_body.strip():
        raise ReviewCycleError(f"Review feedback file is empty: {feedback_source}")
    _guard_feedback_source_provenance(
        feedback_source=feedback_source,
        sub_artifact_dir=sub_artifact_dir,
    )
    return resolved_body


def _persistence_after_commit_exception(
    exc: Exception,
    *,
    operation_root: Path,
    artifact_path: Path,
    evidence_ref: str,
    destination_ref: str,
) -> VerdictPersistenceOutcome:
    """Classify a commit that raised: durable when the exact bytes are already at the destination.

    A commit can raise after the router already persisted the artifact; the
    read-back at ``destination_ref`` is the only proof, so the outcome is
    ``durable`` when the bytes match and ``persistence_failed`` otherwise.
    """
    destination_bytes = _read_artifact_at_ref(operation_root, destination_ref, evidence_ref)
    if destination_bytes == artifact_path.read_bytes():
        return VerdictPersistenceOutcome(
            classification="durable",
            verdict_durably_persisted=True,
            evidence_ref=evidence_ref,
            destination_ref=destination_ref,
            reason=None,
            message=(f"Commit raised after persistence, but exact evidence was verified at {destination_ref}."),
        )
    reason = "commit_timeout" if isinstance(exc, TimeoutError) else "commit_exception"
    return VerdictPersistenceOutcome(
        classification="persistence_failed",
        verdict_durably_persisted=False,
        evidence_ref=evidence_ref,
        destination_ref=destination_ref,
        reason=reason,
        message=(f"Review-cycle commit raised {type(exc).__name__}: {exc}. Evidence is retained at {evidence_ref}."),
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
    owned: OwnedCheckout | None = None,
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

    ``owned`` is the validated owned checkout, when the command runs against
    one. Every directory, placement ref and evidence path is then derived from
    the fact (``owned.owned_root``), never from ``main_repo_root``.
    """
    if (feedback_source is None) == (body is None):
        raise ReviewCycleError("create_rejected_review_cycle requires exactly one of feedback_source or body")

    safe_mission_slug = _validate_segment("mission_slug", mission_slug)
    safe_wp_slug = _validate_segment("wp_slug", wp_slug)
    safe_wp_id = _validate_segment("wp_id", wp_id)
    # FR-001/FR-003/FR-007 single-home write (WP08): land the review-cycle
    # artifact in its ``tasks/<wp>/`` home via the WRITE-side resolver
    # (:func:`_review_cycle_write_location`), never the READ-mode
    # ``_review_cycle_wp_dir`` -- a coordination-routed, EMPTY Mission is
    # materialized/seeded by ``write_dir`` here, rather than silently
    # substituting the PRIMARY repository-root checkout (FR-014). Called
    # exactly ONCE: ``write_dir`` may seed/materialize, and every downstream
    # evidence-path computation reuses THIS SAME ``.surface_root`` (P-M3) —
    # never a second, independent derivation. This fixes both this direct
    # site AND the move-task ``--review-feedback-file`` caller (which passes
    # no pre-resolved dir), from this one edit.
    write_location = _review_cycle_write_location(main_repo_root, safe_mission_slug, owned=owned)
    surface_root = write_location.surface_root
    sub_artifact_dir = _review_cycle_write_dir(write_location, safe_wp_slug)
    sibling_dirs = _review_cycle_read_candidate_dirs(main_repo_root, safe_mission_slug, safe_wp_slug, owned=owned)

    resolved_body = _resolve_review_body(
        feedback_source=feedback_source,
        body=body,
        sub_artifact_dir=sub_artifact_dir,
    )

    parsed_affected: list[AffectedFile] = [AffectedFile(path=affected["path"], line_range=affected.get("line_range")) for affected in affected_files or []]

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
            sibling_dirs=sibling_dirs,
            owned=owned,
        )
        already_committed = False
    else:
        artifact, artifact_path, filename, already_committed = _adopt_or_allocate_review_cycle_locked(
            main_repo_root=main_repo_root,
            mission_slug=safe_mission_slug,
            wp_id=safe_wp_id,
            sub_artifact_dir=sub_artifact_dir,
            reviewer_agent=reviewer_agent,
            affected_files=parsed_affected,
            body=resolved_body,
            reproduction_command=reproduction_command,
            owned=owned,
            surface_root=surface_root,
            sibling_dirs=sibling_dirs,
        )
    pointer = build_review_cycle_pointer(safe_mission_slug, safe_wp_slug, filename)

    evidence_ref = _evidence_ref(surface_root, artifact_path)
    governed_destination_ref = placement_seam(main_repo_root, safe_mission_slug, owned=owned).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
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
            message=(f"Identical review-cycle evidence was already committed and verified at {governed_destination_ref}."),
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
                owned=owned,
                surface_root=surface_root,
            )
        except Exception as exc:
            persistence = _persistence_after_commit_exception(
                exc,
                operation_root=surface_root,
                artifact_path=artifact_path,
                evidence_ref=evidence_ref,
                destination_ref=governed_destination_ref,
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
