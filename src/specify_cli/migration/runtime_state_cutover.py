"""Cutover orchestration: seed runtime state, fail-closed verify, atomic flip.

The **single** invocable spine step (research D-01): one shared
:func:`cutover_mission` helper implements ``backfill -> fail-closed verify ->
atomic per-mission ``status_phase`` flip`` so the load-bearing atomicity lives in
exactly one place. Both the operator CLI (``spec-kitty migrate
backfill-runtime-state``) and — in a later WP — the upgrade migration reuse this
helper; neither re-implements verify-then-flip.

Fail-closed contract (FR-003 / NFR-001 / INV-1):

* :func:`cutover_mission` is the **sole production writer** of ``meta.json``
  ``status_phase``.
* It flips to the snapshot-authority value **only** after an ``ok`` verify. The
  flip phase (:func:`_flip_phase`) is structurally unreachable on a non-``ok``
  verify, a :class:`MigrationOrderingError`, or a per-mission backfill error — so
  a divergent-state mission is *never* flipped (zero silent data loss).
* The write target resolves via :func:`canonicalize_feature_dir` — never
  ``Path.cwd()`` and never a raw worktree/root alias — so no ``status_phase`` (or
  event) write ever lands at the repo root (INV-5 / C-003 / #2815). This helper
  adds **no** event-write path of its own: all seed events go through the backfill
  library, which already canonicalizes.
* (placement-port-residuals-closure-01KYDEF0 FR-001) That target is additionally
  ENFORCED against the placement port's own answer
  (:func:`~mission_runtime.resolve_artifact_surface`): a resolved PRIMARY home
  that disagrees with the write target fails closed
  (:class:`PlacementMismatchError`, writes nothing); a resolver *failure* (no
  enclosing git repo, an ambiguous handle, a deleted coordination branch, or an
  unresolvable action context) on a well-formed legacy mission degrades to the
  caller-supplied target instead of aborting the cutover (NFR-002).
  :func:`cutover_mission` itself still RAISES :class:`PlacementMismatchError`
  (per-mission fail-close, C-WRITER-1) — the corpus walkers
  (:func:`cutover_repo` and the upgrade migration's ``_cutover_corpus``) catch
  it PER MISSION so one mis-routed mission never strands the missions sorted
  after it (landing-fold finding 1).

Idempotency (NFR-002 / INV-4): the backfill mints byte-identical deterministic
seed ids (a re-run seeds nothing) and :func:`_flip_phase` short-circuits when the
phase is already snapshot-authority, so a second run seeds nothing and re-flips
nothing (byte-stable).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

from specify_cli.core.checkout_identity import Intent
from specify_cli.core.paths import assert_safe_path_segment
from specify_cli.core.utils import ensure_within_any
from specify_cli.mission_metadata import load_meta, write_meta
from specify_cli.workspace import canonicalize_feature_dir


from .backfill_runtime_state import (
    BackfillResult,
    MigrationOrderingError,
    VerifyResult,
    _runtime_feature_dir,
    backfill_runtime_state,
    verify_backfill,
)

logger = logging.getLogger(__name__)

#: The ``meta.json`` key this helper is the sole production writer of.
_STATUS_PHASE_KEY = "status_phase"

#: The snapshot-authority ``status_phase`` value written by the flip (contract
#: step 5). Stored as a string; ``status.emit._read_status_phase`` parses it via
#: ``int("1")`` unchanged. Any parsed phase ``>= 1`` counts as already-flipped.
_SNAPSHOT_AUTHORITY_PHASE = "1"


@dataclass
class CutoverResult:
    """Per-mission outcome of :func:`cutover_mission`.

    Attributes:
        slug: The mission slug (directory name).
        flipped: True iff this run reached the flip phase with an ``ok`` verify —
            the mission holds snapshot authority after the run. NOT "a write
            occurred": on a mission already at snapshot authority the flip
            short-circuits having written zero bytes and ``flipped`` stays True
            by contract (pinned in ``tests/migration/test_birth_cutover.py``);
            ``already_migrated`` is the field that distinguishes that case.
        already_migrated: True iff the mission's ``meta.json`` already declared
            a snapshot-authority ``status_phase`` when this run reached its
            flip decision — the flip's no-write short-circuit case (#3212).
            This is the one bit ``flipped``/``seeded_count`` cannot express:
            seeding and flipping are independent, so a mission with no legacy
            frontmatter state to seed still flips (``flipped=True,
            already_migrated=False``, zero seeds), while a re-run over a
            migrated mission writes nothing (``flipped=True,
            already_migrated=True``).
        would_flip: Dry-run signal — True iff verify passed against the
            current (already-seeded) state, with nothing written. A mission
            that still needs seeding fails verify first (a dry-run writes no
            seeds), so ``would_flip`` never fires for it; the dry-run signal
            for that case is the operator-facing ``would_seed`` (derived from
            ``seeded_count > 0`` in the CLI layer). Like ``flipped`` this is
            NOT "a live run would write": it stays True for a mission already
            at snapshot authority (the ``doctor cutover`` verdict rides that,
            FR-007) — combine with ``already_migrated`` for that question.
        seeded_count: NEW seed events appended this run (0 on an idempotent
            re-run or a dry-run over an already-seeded corpus).
        verify: The fail-closed :class:`VerifyResult`, or ``None`` when the run
            aborted before verify (ordering error / backfill error).
        error: Human-readable abort reason (ordering error / backfill error), or
            ``None`` on a clean run.
    """

    slug: str
    flipped: bool
    would_flip: bool = False
    already_migrated: bool = False
    seeded_count: int = 0
    verify: VerifyResult | None = None
    error: str | None = None


def _seed_phase(
    feature_dir: Path,
    *,
    read_dir: Path | None = None,
    dry_run: bool,
    owned: OwnedCheckout | None = None,
) -> BackfillResult:
    """Phase 1 — idempotently seed the mission's legacy runtime state as events.

    Thin wrapper over :func:`backfill_runtime_state`; extracted so the seed step
    is independently unit-testable and :func:`cutover_mission` stays trivial.
    *read_dir* is the FR-002 read/write-leg split (defaults to *feature_dir* —
    see :func:`backfill_runtime_state`'s docstring).
    """
    return backfill_runtime_state(
        feature_dir,
        read_dir=read_dir,
        dry_run=dry_run,
        owned=owned,
    )


def _verify_phase(
    feature_dir: Path,
    *,
    read_dir: Path | None = None,
    intent: Intent = Intent.WRITE,
    owned: OwnedCheckout | None = None,
) -> VerifyResult:
    """Phase 2 — fail-closed count+value parity of the snapshot vs the OLD reader.

    Thin wrapper over :func:`verify_backfill`; a non-``ok`` result makes the flip
    phase unreachable in :func:`cutover_mission`. *read_dir* is the FR-002
    read/write-leg split (defaults to *feature_dir* — see
    :func:`verify_backfill`'s docstring).

    *intent* is :attr:`~specify_cli.core.checkout_identity.Intent.WRITE` here
    (WP05 / #3049): this verify guards the seed+flip WRITE, so a foreign lane
    invocation that reads the redirected primary/coord path is refused
    fail-closed rather than reporting a false pass. The deliberate C-003 write
    target is unchanged — only the guard becomes invoking-checkout-aware.
    """
    return verify_backfill(
        feature_dir,
        read_dir=read_dir,
        intent=intent,
        owned=owned,
    )


class PlacementMismatchError(RuntimeError):
    """Fail-closed marker (FR-001): the port's resolved PRIMARY home disagrees.

    Raised by :func:`_flip_phase` ONLY when the placement port
    (:func:`~mission_runtime.resolve_artifact_surface`) resolves a genuine
    PRIMARY home for the mission and that home does not match the write
    target. A resolver *failure* (ambiguous handle, deleted coordination
    branch, no enclosing git repo) is a distinct, non-fatal signal that
    degrades instead of raising this — see
    :func:`_resolve_primary_home_or_degrade`. Conflating the two would let a
    resolver crash masquerade as this contract's fail-close (anti-scaffold;
    see WP01 T001).

    Carries ``seeded_count`` (FR-015, #3390): the flip is reached only AFTER
    the seed phase has already run for real on a live invocation, so a mismatch
    here can abort with genuine on-disk residue (an already-appended
    ``status.events.jsonl``) that the raising site itself has no
    :class:`CutoverResult` to report. :func:`cutover_mission` stamps the real
    seeded count onto this exception before it escapes, so any caller that
    catches it (:func:`cutover_repo`, the upgrade migration's corpus walker)
    can build an honest, non-under-reporting result instead of silently
    defaulting back to zero.
    """

    def __init__(self, message: str, *, seeded_count: int = 0) -> None:
        super().__init__(message)
        self.seeded_count = seeded_count


def _resolve_primary_home_or_degrade(feature_dir: Path, *, owned: OwnedCheckout | None = None) -> Path | None:
    """Resolve the placement port's PRIMARY home for *feature_dir*, or ``None``.

    ``None`` is the DEGRADE signal: a resolver raise on an otherwise
    well-formed legacy corpus mission — no enclosing git repo
    (:class:`~specify_cli.core.paths.WorkspaceRootNotFound`), an ambiguous
    handle (:class:`~specify_cli.missions._read_path_resolver.MissionSelectorAmbiguous`),
    a deleted coordination branch
    (:class:`~specify_cli.missions._read_path_resolver.StatusReadPathNotFound`),
    or an unresolvable action context
    (:class:`~mission_runtime.ActionContextError`) — must NOT abort the
    cutover (NFR-002); :func:`_flip_phase` falls back to its own
    ``canonicalize_feature_dir`` target in that case. This mirrors the
    structurally equivalent projection over the same resolver,
    :func:`~mission_runtime.coord_read_dir_for`, which degrades on the same
    three exception classes for the same reason (a resolver *failure*, not a
    genuine port answer). A genuine port ANSWER (this function's non-``None``
    return) is compared for equality by the caller — that comparison, not
    this function, decides the fail-close.
    """
    from mission_runtime import ActionContextError, MissionArtifactKind, resolve_artifact_surface
    from specify_cli.core.paths import WorkspaceRootNotFound, resolve_canonical_root
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
    )

    if owned is not None:
        _runtime_feature_dir(feature_dir, owned)
        return resolve_artifact_surface(
            owned.repository_root,
            owned.mission_slug,
            MissionArtifactKind.PRIMARY_METADATA,
            owned=owned,
        ).path

    try:
        repo_root = resolve_canonical_root(feature_dir)
        return resolve_artifact_surface(repo_root, feature_dir.name, MissionArtifactKind.PRIMARY_METADATA).path
    except (
        WorkspaceRootNotFound,
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        ActionContextError,
    ) as exc:
        logger.debug(
            "Placement-port resolution degraded for %s (%s); falling back to the canonicalized write target.",
            feature_dir,
            exc,
        )
        return None


def _flip_target(feature_dir: Path, *, owned: OwnedCheckout | None = None) -> Path:
    """Resolve the ONE ``status_phase`` write target (INV-5 / C-003).

    Never ``Path.cwd()`` and never a raw worktree/root alias: the unowned leg
    canonicalizes (so a worktree-rooted mission dir rewrites to the canonical
    repo's copy) and the owned leg takes the ``OwnedCheckout`` fact's
    mission directory. Shared by :func:`_flip_phase` (the write) and
    :func:`_already_at_snapshot_authority` (the read-only probe) so the two
    can never drift to different targets.
    """
    if owned is None:
        canonical: Path = canonicalize_feature_dir(feature_dir)
        return canonical
    resolved: Path = _runtime_feature_dir(feature_dir, owned)
    return resolved


def _already_at_snapshot_authority(feature_dir: Path, *, owned: OwnedCheckout | None = None) -> bool:
    """Read-only probe: is the flip target's ``meta.json`` already authoritative?

    Answers, BEFORE any write, exactly the question :func:`_flip_phase`'s own
    short-circuit answers after resolving its target — same target
    (via :func:`_flip_target`), same :func:`_is_snapshot_authority` predicate.
    Read-tolerant by design (``on_malformed="none"``): this probe must never
    turn a verdict-bearing read path (the dry-run branch of
    :func:`cutover_mission`, the ``doctor cutover`` audit behind it) into a
    crash on a corpus a live run would classify through its own fail-closed
    seams. ``False`` on a missing/malformed meta is "not yet migrated", which
    is the truthful pre-write answer.
    """
    meta = load_meta(_flip_target(feature_dir, owned=owned), allow_missing=True, on_malformed="none")
    return _is_snapshot_authority(meta or {})


def _flip_phase(feature_dir: Path, *, owned: OwnedCheckout | None = None) -> None:
    """Phase 3 — the SOLE ``status_phase`` writer; only reached on an ``ok`` verify.

    Resolves the write target via :func:`canonicalize_feature_dir` (never
    ``Path.cwd()`` / a raw alias — INV-5 / C-003), then ENFORCES that target
    against the placement port's own answer (FR-001, PR #2920 review F2
    follow-up): a resolved PRIMARY home that disagrees with the target fails
    closed (:class:`PlacementMismatchError`, writes nothing) instead of
    coinciding with the port's answer only by caller discipline. A resolver
    *failure* on a well-formed legacy mission degrades to the caller-supplied
    target instead of aborting (see :func:`_resolve_primary_home_or_degrade`),
    so a corpus-wide run stays green (NFR-002). Writes a tolerant
    ``validate=False`` write: this mutates exactly one key on a possibly-legacy
    ``meta.json`` that may lack unrelated required identity fields, so it must
    not fail the whole flip on an unrelated schema gap (the documented
    ``doc_state`` tolerant-write precedent).

    Idempotent: short-circuits when the phase is already snapshot-authority, so a
    re-run writes zero bytes (INV-4).

    Raises:
        PlacementMismatchError: the port resolved a genuine PRIMARY home that
            disagrees with the write target (fail-closed, FR-001).
    """
    target = _flip_target(feature_dir, owned=owned)
    resolved_home = _resolve_primary_home_or_degrade(feature_dir, owned=owned)
    if resolved_home is not None and resolved_home != target:
        raise PlacementMismatchError(
            f"_flip_phase refuses to write status_phase for {feature_dir.name!r}: "
            f"the placement port resolved its PRIMARY home to {resolved_home}, "
            f"which does not match the write target {target} (fail-closed, FR-001)."
        )
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(target) or {}
    if _is_snapshot_authority(meta):
        return
    meta[_STATUS_PHASE_KEY] = _SNAPSHOT_AUTHORITY_PHASE
    write_meta(target, meta, validate=False)
    logger.info("Flipped status_phase -> %s for %s", _SNAPSHOT_AUTHORITY_PHASE, target.name)


def _is_snapshot_authority(meta: dict[str, object]) -> bool:
    """Return True iff *meta* already declares a snapshot-authority phase (>= 1)."""
    try:
        return int(str(meta.get(_STATUS_PHASE_KEY)).strip()) >= 1
    except (TypeError, ValueError):
        return False


def cutover_mission(
    feature_dir: Path,
    *,
    status_feature_dir: Path | None = None,
    dry_run: bool = False,
    owned: OwnedCheckout | None = None,
) -> CutoverResult:
    """Seed -> fail-closed verify -> atomic ``status_phase`` flip for one mission.

    Orchestrates the three phases per the IC-01 contract, **branching on
    ``verify.ok`` without raising** so every path returns a :class:`CutoverResult`:

    1. seed (:func:`_seed_phase`); a :class:`MigrationOrderingError` (strip ran
       before verify) or a per-mission backfill error aborts with ``flipped=False``
       and ``error`` set — never a partial flip;
    2. verify (:func:`_verify_phase`); ``not verify.ok`` returns ``flipped=False``
       (the flip is unreachable — NFR-001 / INV-1);
    3. ``dry_run`` returns ``would_flip=verify.ok`` writing nothing;
    4. otherwise flip (:func:`_flip_phase`) and return ``flipped=True``.

    Steps 3–4 additionally record ``already_migrated`` — a read-only probe of
    whether the mission was already at snapshot authority BEFORE the flip
    decision (#3212) — so a caller can tell "flipped this run" apart from "the
    flip's no-write short-circuit" without keying on ``seeded_count``.

    Two-target spine (coord-write-placement-closure-01KYCF83 WP09 / IC-08 / T044):
    *feature_dir* is the PRIMARY-partition leg — the legacy frontmatter/``tasks/``
    read anchor AND the sole ``status_phase`` write target (:func:`_flip_phase`
    always resolves against *feature_dir*; FR-002/IC-03's port already routes
    ``PRIMARY_METADATA`` here for every topology, so this extends the existing
    spine rather than forking a second writer — C-004).  *status_feature_dir* is
    the COORD-partition leg the seed **events** are appended against (the
    ``STATUS_STATE`` port target — where ``status.events.jsonl`` canonically
    lives under coordination topology).  It defaults to *feature_dir* when
    omitted, collapsing both legs to the single directory the pre-WP09
    single-target behavior always used — the flat/single-branch degenerate case
    (T047).

    Read/write partition decoupling (placement-port-residuals-closure-01KYDEF0
    FR-002 / IC-02, closing the C-001 residual above): ``tasks/`` legacy
    frontmatter is a PRIMARY-partition artifact, so :func:`_seed_phase` /
    :func:`_verify_phase` now read it from *feature_dir* (the PRIMARY leg,
    passed as their ``read_dir``) while the seed-event write and verify anchor
    stay on *status_dir* (the COORD leg — I-02, unchanged). This is NOT a leg
    swap: the event log still lands on COORD; only the frontmatter read moved.
    The split lives inside :func:`~specify_cli.migration.backfill_runtime_state.backfill_runtime_state`
    / :func:`~specify_cli.migration.backfill_runtime_state.verify_backfill` (a
    ``read_dir`` keyword that defaults to their own *feature_dir* argument, so
    every single-leg caller — the corpus walk, the CLI backfill command — is
    byte-unchanged); :func:`cutover_mission`'s own signature stays stable.

    Args:
        feature_dir: kitty-specs mission directory (canonicalized downstream);
            the PRIMARY leg.
        status_feature_dir: kitty-specs mission directory for the COORD leg
            (seed events). Defaults to *feature_dir*.
        dry_run: When True, seed nothing / flip nothing; report would-seed counts.
        owned: Explicit single-branch context. Validate both anchors before seed
            and retain ownership through verification and the metadata write.

    Returns:
        A :class:`CutoverResult` describing the outcome.
    """
    status_dir = status_feature_dir if status_feature_dir is not None else feature_dir
    if owned is not None:
        # Validate both legs before seed can perform its first write.
        feature_dir = _runtime_feature_dir(feature_dir, owned)
        status_dir = _runtime_feature_dir(status_dir, owned)
    slug = feature_dir.name
    try:
        seed = _seed_phase(status_dir, read_dir=feature_dir, dry_run=dry_run, owned=owned)
    except MigrationOrderingError as exc:
        return CutoverResult(slug=slug, flipped=False, error=str(exc))
    slug = seed.slug
    if seed.action == "error":
        return CutoverResult(slug=slug, flipped=False, seeded_count=seed.seeded_count, error=seed.reason)

    try:
        verify = _verify_phase(status_dir, read_dir=feature_dir, owned=owned)
    except MigrationOrderingError as exc:
        return CutoverResult(slug=slug, flipped=False, seeded_count=seed.seeded_count, error=str(exc))

    if not verify.ok:
        return CutoverResult(slug=slug, flipped=False, seeded_count=seed.seeded_count, verify=verify)

    # #3212: the one bit `flipped`/`seeded_count` cannot express — whether the
    # mission was ALREADY at snapshot authority when this run reached its flip
    # decision. Probed once, read-only and write-free, on the shared
    # dry-run/live path: the CLI's Flipped / Skipped (already migrated)
    # counters key on it, never on `seeded_count` (seeding and flipping are
    # independent — a mission with no legacy frontmatter state to seed still
    # flips).
    already_migrated = _already_at_snapshot_authority(feature_dir, owned=owned)

    if dry_run:
        return CutoverResult(
            slug=slug,
            flipped=False,
            would_flip=True,
            already_migrated=already_migrated,
            seeded_count=seed.seeded_count,
            verify=verify,
        )

    try:
        _flip_phase(feature_dir, owned=owned)
    except PlacementMismatchError as exc:
        # FR-015 (#3390): the seed phase above already wrote real events to
        # disk (a live run) before the flip aborted. Stamp the true count onto
        # the exception so a caller that catches this (cutover_repo, the
        # upgrade migration's corpus walker) does not silently under-report
        # that on-disk residue by defaulting a fresh CutoverResult back to
        # seeded_count=0.
        exc.seeded_count = seed.seeded_count
        raise
    return CutoverResult(
        slug=slug,
        flipped=True,
        already_migrated=already_migrated,
        seeded_count=seed.seeded_count,
        verify=verify,
    )


class MissingMissionIdError(RuntimeError):
    """Fail-closed marker (NFR-003/R6): ``mission_id`` absent from ``meta.json``.

    Raised by :func:`stamp_accept_cutover` BEFORE :func:`cutover_mission` runs
    when the target mission's ``meta.json`` carries no ``mission_id`` —
    refusing to stamp rather than seeding under a slug-namespaced identity.
    :func:`~specify_cli.migration.backfill_runtime_state._mission_id`
    internally degrades a missing ``mission_id`` to the directory slug (a
    tolerant fallback appropriate for a one-off corpus migration), but the
    terminal accept seam is deliberately stricter: a ``mission_id`` minted
    *later* would change the deterministic-seed namespace
    (``sha256(mission_id | wp_id | field)``), orphaning or duplicating the
    seed rows this stamp already committed (data-model.md's seed-determinism
    section; contract ``MUST`` R6).
    """


def stamp_accept_cutover(
    feature_dir: Path,
    *,
    status_feature_dir: Path | None = None,
    owned: OwnedCheckout | None = None,
) -> CutoverResult:
    """Terminal-lifecycle accept-time stamp (IC-01 / contracts/stamp-seam.md).

    A thin, fail-closed wrapper over :func:`cutover_mission` — the SAME single
    authority :func:`~specify_cli.consolidation.executor._run_birth_cutover` calls at
    the merge seam (FR-005: no forked writer; this function adds no seeding or
    flip logic of its own). The only behavior layered on top is the
    NFR-003/R6 fail-closed assertion below, so the ``accept`` CLI seam and the
    ``merge`` seam are guaranteed to produce byte-identical seed payloads for
    the same mission (NFR-004).

    Args:
        feature_dir: The PRIMARY-partition mission directory — the legacy
            ``tasks/`` read anchor and the sole ``status_phase`` write target.
        status_feature_dir: The COORD-partition mission directory — the seed
            event write/verify anchor. Defaults to *feature_dir* (the
            flat/single-branch degenerate case, T047).
        owned: Explicit single-branch context, revalidated before any write.

    Returns:
        The :class:`CutoverResult` from :func:`cutover_mission`.

    Raises:
        MissingMissionIdError: *feature_dir*'s ``meta.json`` carries no
            ``mission_id`` — no seed is written (fail-closed, R6).
    """
    if owned is not None:
        feature_dir = _runtime_feature_dir(feature_dir, owned)
    meta = load_meta(feature_dir, allow_missing=True, on_malformed="none") or {}
    mission_id = meta.get("mission_id")
    if not mission_id:
        raise MissingMissionIdError(
            f"Refusing to stamp birth-cutover for {feature_dir.name!r}: "
            "meta.json carries no mission_id (fail-closed, NFR-003/R6 — no "
            "slug-namespaced seed fallback)."
        )
    return cutover_mission(
        feature_dir,
        status_feature_dir=status_feature_dir,
        dry_run=False,
        owned=owned,
    )


def cutover_repo(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> list[CutoverResult]:
    """Walk ``kitty-specs/`` (or a single ``--mission`` dir) and cutover each mission.

    Mirrors :func:`~specify_cli.migration.backfill_runtime_state.backfill_runtime_state_repo`:
    the write target is always resolved from each mission directory (never
    ``Path.cwd()`` — C-003), and each mission is processed independently
    (per-mission best-effort — research D-03). Keeping the walk here (not in the
    CLI body) keeps the command thin and the walk unit-testable.

    A :class:`PlacementMismatchError` out of :func:`cutover_mission` (FR-001's
    fail-close) is caught PER MISSION and folded into that mission's
    :class:`CutoverResult` (``flipped=False``, ``error`` set) — it must not
    abort the whole corpus walk, or one mis-routed mission would silently
    strand every mission sorted after it unvisited (placement-port-residuals-
    closure-01KYDEF0 finding 1).

    Args:
        repo_root: Absolute path to the repository root.
        dry_run: When True, seed/flip nothing; report would-seed counts.
        mission_slug: When provided, scope the walk to a single mission directory.

    Returns:
        One :class:`CutoverResult` per mission directory visited (empty when there
        is no ``kitty-specs/`` or the named mission does not exist).
    """
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        logger.warning("kitty-specs/ not found at %s", repo_root)
        return []

    if mission_slug is not None:
        assert_safe_path_segment(mission_slug)
        candidate = kitty_specs / mission_slug
        if not candidate.is_dir():
            logger.warning("No mission directory found for slug %r", mission_slug)
            return []
        try:
            candidates = [ensure_within_any(candidate, roots=[kitty_specs])]
        except ValueError as exc:
            raise ValueError(f"Mission directory resolves outside kitty-specs: {candidate}") from exc
    else:
        candidates = []
        for entry in sorted(kitty_specs.iterdir()):
            if not entry.is_dir():
                continue
            try:
                candidates.append(ensure_within_any(entry, roots=[kitty_specs]))
            except ValueError:
                logger.warning(
                    "Skipping mission directory that resolves outside kitty-specs: %s",
                    entry,
                )

    results: list[CutoverResult] = []
    for feature_dir in candidates:
        try:
            results.append(cutover_mission(feature_dir, dry_run=dry_run))
        except PlacementMismatchError as exc:
            results.append(
                CutoverResult(
                    slug=feature_dir.name,
                    flipped=False,
                    error=str(exc),
                    # FR-015 (#3390): preserve the real on-disk seed count the
                    # exception carries rather than defaulting to 0 (under-report).
                    seeded_count=exc.seeded_count,
                )
            )
    return results


__all__ = [
    "CutoverResult",
    "MissingMissionIdError",
    "cutover_mission",
    "cutover_repo",
    "stamp_accept_cutover",
]
