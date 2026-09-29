"""Store + backfill a mission's :class:`MissionTopology` in ``meta.json`` (#2069).

The topology of a mission (the orthogonal coordination × lanes grid cell) used to
be re-inferred from disk/git at every resolve. FR-002/FR-003 make it a **stored,
authoritative** value:

- :func:`read_topology` — the PURE reader (#1814): returns the stored ``topology``
  when present, otherwise derives the shape ONCE via WP01's
  :func:`classify_topology` (the single authority for the 2×2 grid) and returns it
  **without writing**. The read/validate/accept SEAM paths use this so a read never
  mutates ``meta.json``.
- :class:`TopologyBackfillResult` / :func:`backfill_mission_topology` /
  :func:`backfill_topology_repo` — mirror the ``backfill_identity`` precedent: an
  idempotent, canonical-JSON, never-overwrite-an-existing-value migration that the
  ``spec-kitty migrate backfill-topology`` command drives.

``flattened`` is a separate boolean provenance flag (history mark), NOT a topology
value: a mission that lost its ``coordination_branch`` is SINGLE_BRANCH/LANES *and*
``flattened: true``. ``"FLATTENED"`` is never stored as a ``topology``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mission_runtime import MissionTopology, classify_topology, routes_through_coordination, unstamped_runtime_topology

from specify_cli.lanes import CorruptLanesError, read_lanes_json
from specify_cli.lanes.compute import has_code_lanes

logger = logging.getLogger(__name__)

# Canonical meta.json keys (hoisted per Sonar S1192 — used in >=3 sites).
#
# ``TOPOLOGY_KEY`` / ``FLATTENED_KEY`` are PUBLIC (promoted from the former
# module-private ``_TOPOLOGY_KEY`` / ``_FLATTENED_KEY`` by
# verdict-seam-write-unification-01KZ9Q35 WP10 / D-PLAN-17): this module is
# their semantic owner, and ``mission_metadata.flatten_coordination_metadata``
# (#3219 / FR-015) imports them directly rather than re-spelling the string
# literals at the import site (squad #16). ``_COORDINATION_BRANCH_KEY`` stays
# private -- no other module needs to reference it by name.
TOPOLOGY_KEY = "topology"
FLATTENED_KEY = "flattened"
_COORDINATION_BRANCH_KEY = "coordination_branch"

# Valid stored topology string values (the enum's stable .value forms).
_VALID_TOPOLOGY_VALUES = frozenset(member.value for member in MissionTopology)


def _has_lanes(feature_dir: Path) -> bool:
    """Return whether the mission has a CODE lane (corrupt ⇒ treated absent).

    #5100 IC-02 / R-3: "has lanes" for topology-derivation purposes means "has
    a CODE lane", never merely "a lanes.json exists on disk" — delegates to
    :func:`specify_cli.lanes.compute.has_code_lanes` so the canonical
    ``lane-planning`` lane every mission carries (single_branch and lanes
    alike) does not, by itself, make a mission's topology ``LANES``. This is
    the single authority :func:`read_topology`, :func:`_derive_topology`, and
    the backfill walk all route through.
    """
    try:
        manifest = read_lanes_json(feature_dir)
    except CorruptLanesError:
        # A corrupt lanes.json is not a usable lanes signal; classify as no-lanes
        # rather than crashing the migration. The corruption surfaces elsewhere.
        logger.warning("Corrupt lanes.json in %s — treating as no lanes", feature_dir.name)
        return False
    if manifest is None:
        return False
    # Bind explicitly: mypy widens the late-bound ``specify_cli.lanes`` return to
    # ``Any`` (``follow_imports=skip``); the annotation narrows it back.
    has_code: bool = has_code_lanes(manifest)
    return has_code


def _derive_topology(meta: dict[str, Any], feature_dir: Path) -> MissionTopology:
    """Derive the topology from current signals via WP01's single authority."""
    coordination_branch = meta.get(_COORDINATION_BRANCH_KEY) or None
    return classify_topology(coordination_branch, _has_lanes(feature_dir))


def stored_topology(meta: Mapping[str, Any]) -> MissionTopology | None:
    """Return the EXPLICITLY stored ``topology`` value, or ``None`` (#5100 WP05 cycle 2, Issue 3).

    The SINGLE stored-only authority: a valid :class:`MissionTopology` string
    under ``TOPOLOGY_KEY``, with NO derive-from-signals fallback and no disk
    access beyond the already-in-hand ``meta`` mapping. :func:`topology_from_meta`
    layers the derive fallback on top of this (stored-or-derive); a caller that
    must never accept a DERIVED value -- because deriving would read a signal
    (e.g. ``lanes.json``) the caller's own in-flight operation has not written
    yet, and so would misclassify -- calls this directly instead of
    re-implementing the ``stored in _VALID_TOPOLOGY_VALUES`` check a second
    time. See :func:`~specify_cli.lanes.worktree_allocator._stored_topology_for_fail_closed_guard`,
    the first such caller.
    """
    stored = meta.get(TOPOLOGY_KEY)
    if isinstance(stored, str) and stored in _VALID_TOPOLOGY_VALUES:
        return MissionTopology(stored)
    return None


def topology_from_meta(meta: Mapping[str, Any], feature_dir: Path) -> MissionTopology:
    """Tolerant sibling of :func:`read_topology`: derives from an ALREADY-loaded meta dict.

    Review cycle-1 nit 3: a caller that already tolerantly loaded ``meta``
    (e.g. ``load_meta_or_empty`` -- missing/malformed degrades to ``{}``,
    never raises) must not then thread its topology through a SECOND,
    stricter read (:func:`read_topology` opens ``meta.json`` itself and
    raises ``FileNotFoundError``/``MissionMetaReadError``). This performs
    the identical stored-value-or-derive logic over the in-hand mapping --
    it never touches ``meta.json``, so it inherits the caller's own
    tolerance instead of adding a new raise on a path that had none.
    """
    stored = stored_topology(meta)
    if stored is not None:
        return stored
    # #5100 FR-013 / #2602 (squad N7): an UNSTAMPED mission never derives
    # ``single_branch`` at runtime -- only the explicit backfill writer
    # (:func:`backfill_mission_topology` via :func:`_derive_topology`) keeps
    # the classic 2x2 cell. See :func:`mission_runtime.unstamped_runtime_topology`.
    return unstamped_runtime_topology(_derive_topology(dict(meta), feature_dir))


def _write_meta_canonical(meta_path: Path, meta: dict[str, Any]) -> None:
    """Persist ``meta`` in the canonical sorted-key form (matches ``backfill_identity``)."""
    content = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    meta_path.write_text(content, encoding="utf-8")


def read_topology(feature_dir: Path) -> MissionTopology:
    """PURE read of a mission's :class:`MissionTopology` — never persists (#1814).

    The read-path counterpart of :func:`backfill_mission_topology`. Returns the
    stored ``topology`` when ``meta.json`` carries a valid value; otherwise derives
    the shape ONCE via WP01's :func:`classify_topology` (from ``coordination_branch``
    + lanes presence) and returns it **without writing**. A read/validate/accept
    path therefore never mutates ``meta.json`` — the read-only-contract that a
    persisting read would violate when wired into the SEAM read paths (the finalize
    ``--validate-only`` / accept-readiness / transactional-read regression, #1814).

    Persisting the back-filled value is the explicit job of
    :func:`backfill_mission_topology` and the ``spec-kitty migrate backfill-topology``
    command — NEVER an incidental side effect of a read.

    Args:
        feature_dir: Absolute path to a mission directory containing ``meta.json``.

    Returns:
        The :class:`MissionTopology` for the mission.

    Raises:
        FileNotFoundError: If ``meta.json`` does not exist.
        MissionMetaReadError: If ``meta.json`` is not a JSON object or is corrupt.
    """
    # FR-007: fail-closed reader routing. Malformed meta surfaces typed
    # MissionMetaReadError instead of raw ValueError. Missing files still raise
    # FileNotFoundError to preserve documented contract.
    from specify_cli.core.paths import load_meta_fail_closed

    meta_result = load_meta_fail_closed(feature_dir)
    if meta_result is None:
        raise FileNotFoundError(feature_dir / "meta.json")
    meta: dict[str, Any] = meta_result or {}

    # Single authority (#5100 WP04 folded nit, post-WP03-review): the
    # stored-value-or-derive check is :func:`topology_from_meta`'s own body —
    # delegate rather than re-run the identical ``stored in
    # _VALID_TOPOLOGY_VALUES`` check a second time here. Un-backfilled legacy
    # missions still derive the shape ONCE from current signals and return it
    # WITHOUT persisting (the read-only contract — #1814); the explicit
    # backfill command / mint path is the only writer.
    return topology_from_meta(meta, feature_dir)


# ---------------------------------------------------------------------------
# Backfill (mirrors backfill_identity.py)
# ---------------------------------------------------------------------------

TopologyBackfillAction = Literal["wrote", "skip", "error"]


@dataclass
class TopologyBackfillResult:
    """Per-mission result from :func:`backfill_mission_topology`.

    Attributes:
        feature_dir: Absolute path to the mission directory.
        slug: Directory name used as the mission slug.
        action: ``"wrote"`` — topology derived and persisted; ``"skip"`` — a valid
            ``topology`` was already present (or no ``meta.json``); ``"error"`` —
            unreadable / corrupt ``meta.json``.
        topology: The stored or newly-derived topology ``.value`` string, or
            ``None`` on error / missing meta.
        reason: Human-readable explanation (populated on ``"skip"``/``"error"``).
    """

    feature_dir: Path
    slug: str
    action: TopologyBackfillAction
    topology: str | None = None
    reason: str | None = None


def backfill_mission_topology(feature_dir: Path, *, dry_run: bool = False) -> TopologyBackfillResult:
    """Idempotently persist ``topology`` into ``<feature_dir>/meta.json``.

    A mission whose ``meta.json`` already carries a valid ``topology`` is a no-op
    (``action="skip"``); an existing value is **never** overwritten. A mission
    lacking the field has its topology derived once via WP01's
    :func:`classify_topology` and written in the canonical sorted-key form, with a
    default ``flattened: false`` provenance flag.

    Args:
        feature_dir: Absolute path to a single mission directory.
        dry_run: When ``True``, report the would-write without touching disk.

    Returns:
        A :class:`TopologyBackfillResult` describing what happened.
    """
    slug = feature_dir.name
    meta_path = feature_dir / "meta.json"

    if not meta_path.exists():
        return TopologyBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="skip",
            reason="meta.json not found",
        )

    from specify_cli.core.paths import load_meta_fail_closed, MissionMetaReadError

    try:
        meta_result = load_meta_fail_closed(feature_dir)
        meta: dict[str, Any] = meta_result or {}
    except MissionMetaReadError as exc:
        logger.warning("Corrupt meta.json in %s: %s", slug, exc)
        return TopologyBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="error",
            reason=f"corrupt json: {exc}",
        )

    stored = meta.get(TOPOLOGY_KEY)
    if isinstance(stored, str) and stored in _VALID_TOPOLOGY_VALUES:
        return TopologyBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="skip",
            topology=stored,
            reason="topology already present",
        )

    topology = _derive_topology(meta, feature_dir)

    # T007 (#2250 / FR-002): a declared ``coordination_branch`` that was never
    # created in git must NOT be backfilled as healthy coord. The probe lives at
    # the WRITE path ONLY — ``read_topology`` / ``_derive_topology`` /
    # ``classify_topology`` stay byte-for-byte pure (C-001: no I/O added there).
    # Reuse the canonical ``_coord_branch_exists`` seam (lazy import — avoids the
    # coordination ↔ migration layer cycle; same pattern as
    # ``_read_path_resolver.py:315``). The seam already fails closed: a non-git
    # directory or an unreadable git state returns ``True`` (branch treated as
    # present), so the normal write path is taken in tests without a git repo and
    # in degraded environments — no false-skip on git unavailability. #2219 cites
    # the analogous repo-global probe precedent.
    if routes_through_coordination(topology):
        coord_branch: str | None = meta.get(_COORDINATION_BRANCH_KEY) or None
        if coord_branch is not None:
            from specify_cli.coordination.surface_resolver import _coord_branch_exists

            _repo_root = feature_dir.parent.parent  # kitty-specs/<slug> → repo root
            if not _coord_branch_exists(_repo_root, coord_branch):
                logger.warning(
                    "Skipping topology backfill for %s: coordination_branch %r is "
                    "absent from git (never created or deleted). Flatten the mission "
                    "(remove coordination_branch from meta.json) or create the branch "
                    "before backfilling. #2250",
                    slug,
                    coord_branch,
                )
                return TopologyBackfillResult(
                    feature_dir=feature_dir,
                    slug=slug,
                    action="skip",
                    reason="coordination_branch absent from git",
                )

    if not dry_run:
        meta[TOPOLOGY_KEY] = topology.value
        meta.setdefault(FLATTENED_KEY, False)
        _write_meta_canonical(meta_path, meta)

    return TopologyBackfillResult(
        feature_dir=feature_dir,
        slug=slug,
        action="wrote",
        topology=topology.value,
    )


def _kitty_specs_mission_dirs(repo_root: Path, *, mission_slug: str | None = None) -> list[Path]:
    """Return the mission directories a repo-wide topology walk should visit.

    Single shared home for the ``kitty-specs/`` walk (S1192): both
    :func:`backfill_topology_repo` and :func:`restamp_single_branch_with_code_lanes`
    route through this instead of restating the same ``iterdir`` + sort.
    """
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        logger.warning("kitty-specs/ not found at %s", repo_root)
        return []

    if mission_slug is not None:
        candidates = [entry for entry in kitty_specs.iterdir() if entry.is_dir() and entry.name == mission_slug]
        if not candidates:
            logger.warning("No mission directory found for slug %r", mission_slug)
        return candidates

    return sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir())


def backfill_topology_repo(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> list[TopologyBackfillResult]:
    """Walk ``kitty-specs/`` and idempotently backfill every mission's topology.

    Args:
        repo_root: Absolute path to the repository root.
        dry_run: When ``True``, compute results without writing any files.
        mission_slug: When provided, scope the walk to a single mission directory.

    Returns:
        List of :class:`TopologyBackfillResult`, one per mission directory visited.
    """
    candidates = _kitty_specs_mission_dirs(repo_root, mission_slug=mission_slug)
    return [backfill_mission_topology(feature_dir, dry_run=dry_run) for feature_dir in candidates]


# ---------------------------------------------------------------------------
# Re-stamp: single_branch missions whose lanes.json has code lanes (#5100)
# ---------------------------------------------------------------------------

RestampAction = Literal["restamped", "skip", "error"]


@dataclass
class RestampResult:
    """Per-mission result from :func:`restamp_single_branch_with_code_lanes`.

    Mirrors :class:`TopologyBackfillResult`'s shape (the established sibling
    contract for a whole-repo ``kitty-specs/`` walk).

    Attributes:
        feature_dir: Absolute path to the mission directory.
        slug: Directory name used as the mission slug.
        action: ``"restamped"`` — the mission's stored ``topology`` was (or,
            under ``dry_run``, would be) rewritten ``single_branch`` ->
            ``lanes``; ``"skip"`` — the mission does not violate Invariant
            T-1 (see ``data-model.md``) and needs no change; ``"error"`` —
            unreadable / corrupt ``meta.json``.
        reason: Human-readable explanation (populated on ``"skip"``/``"error"``).
    """

    feature_dir: Path
    slug: str
    action: RestampAction
    reason: str | None = None


def restamp_single_branch_with_code_lanes(repo_root: Path, *, dry_run: bool = False, mission_slug: str | None = None) -> list[RestampResult]:
    """Re-stamp every un-migrated ``single_branch`` + code-lane mission to ``lanes``.

    Contract: ``docs``-adjacent ``contracts/topology-restamp.md`` (mission
    single-branch-topology-honesty-01M3M22V). A mission is selected when its
    **stored** ``topology`` reads ``single_branch`` (:func:`read_topology`)
    AND its ``lanes.json`` has a code lane (:func:`has_code_lanes`) — the
    Invariant T-1 violation this migration repairs. Selected missions have
    ``topology`` rewritten to ``lanes`` through the canonical meta writer;
    **no other field is touched**, and this never commits (the upgrade
    auto-commit / operator commit owns that). Idempotent (NFR-003): a second
    run selects nothing, because the first run's write already satisfies the
    invariant.

    Args:
        repo_root: Absolute path to the repository root.
        dry_run: When ``True``, report what would be re-stamped without
            writing any files.
        mission_slug: When provided, scope the walk to a single mission
            directory (review cycle-1 nit 4: honours ``--mission`` instead
            of silently ignoring it -- mirrors :func:`backfill_topology_repo`'s
            existing scoping contract).

    Returns:
        List of :class:`RestampResult`, one per mission directory visited.
    """
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    results: list[RestampResult] = []
    for feature_dir in _kitty_specs_mission_dirs(repo_root, mission_slug=mission_slug):
        slug = feature_dir.name
        try:
            topology = read_topology(feature_dir)
        except FileNotFoundError:
            results.append(RestampResult(feature_dir, slug, "skip", reason="no meta.json"))
            continue
        except MissionMetaReadError as exc:
            results.append(RestampResult(feature_dir, slug, "error", reason=f"corrupt meta.json: {exc}"))
            continue

        if topology is not MissionTopology.SINGLE_BRANCH:
            results.append(RestampResult(feature_dir, slug, "skip", reason="topology is not single_branch"))
            continue

        try:
            manifest = read_lanes_json(feature_dir)
        except CorruptLanesError as exc:
            # Review cycle-1 blocker: an unreadable lanes.json (e.g. a
            # legacy feature_slug-keyed manifest the canonical reader
            # rejects) is NOT "no code lanes" -- that would be a false
            # negative that lets a genuine Invariant T-1 violation slip
            # through un-selected. Report it honestly with its own reason
            # (never folded into "no code lanes") so the doctor's separate
            # LANES_MANIFEST_UNREADABLE finding (see _identity_audit.py)
            # and this reason never silently disagree. Stays a "skip" (not
            # "error"): this migration cannot repair the manifest itself
            # (C-003 forbids teaching read_lanes_json a feature_slug
            # fallback), and one unreadable legacy mission must not fail
            # `spec-kitty upgrade` for every consumer repo.
            results.append(RestampResult(feature_dir, slug, "skip", reason=f"lanes.json unreadable: {exc}"))
            continue

        if manifest is None or not has_code_lanes(manifest):
            results.append(RestampResult(feature_dir, slug, "skip", reason="no code lanes"))
            continue

        # Operator decision (PR #5398 handoff addendum): skip TERMINAL (archived)
        # missions. A completed mission is never run again, so its stale
        # single_branch stamp never reaches the fail-closed writer guard --
        # re-stamping it would only churn a frozen kitty-specs/ dossier (the
        # always-on archive-freeze gate forbids rewriting archived dossiers).
        # Keyed on the canonical completion predicate is_mission_completed (the
        # single authority: a merged_at marker OR every WP terminal), so this
        # selection and the doctor's SINGLE_BRANCH_CODE_LANES_UNMIGRATED finding
        # stay in lockstep. Checked last -- only for a mission that would
        # otherwise be re-stamped -- so the event-log read it may perform is
        # never paid for the whole kitty-specs/ walk.
        from specify_cli.status import is_mission_completed

        if is_mission_completed(feature_dir):
            results.append(RestampResult(feature_dir, slug, "skip", reason="terminal (archived) mission — nothing runs it"))
            continue

        if not dry_run:
            meta = load_meta_fail_closed(feature_dir) or {}
            meta[TOPOLOGY_KEY] = MissionTopology.LANES.value
            _write_meta_canonical(feature_dir / "meta.json", meta)
        results.append(RestampResult(feature_dir, slug, "restamped"))

    return results


__all__ = [
    "FLATTENED_KEY",
    "TOPOLOGY_KEY",
    "backfill_topology_repo",
    "read_topology",
    "restamp_single_branch_with_code_lanes",
    "stored_topology",
    "topology_from_meta",
]
