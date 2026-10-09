"""Backfill a profile-resolving ``mission_type`` into legacy ``meta.json`` (rc3 M0).

Legacy missions store their type in the deprecated ``mission`` field of
``meta.json``; newer missions use ``mission_type``. Upcoming missions **M3**
(per-type hard-fail on a profile-less ``mission_type``) and **M5** (drops the
legacy ``mission`` resolution fallback entirely) make an un-migrated
``mission``-only mission break on upgrade. This module mints a
**profile-resolving** ``mission_type`` for every eligible legacy mission so
that combined change is non-breaking (spec.md "Program gate for rc3").

Predicate = profile-resolution, NOT charter activation (M3 §B authority,
operator decision "B"). A candidate is written only when
``MissionTypeProfileRepository.for_project(repo_root).get(canonical_key)``
resolves a governance profile at *any* layer (built-in / org / project) —
this is **activation-independent**: a built-in type such as ``software-dev``
or ``research`` always resolves via its shipped profile, so an unprovisioned
legacy repo (no ``.kittify/`` at all) backfills cleanly. Keying the writer on
the audit's activation-based ``resolved`` split instead would refuse to
backfill exactly the population this migration targets (spec "Why the
tolerance predicate is profile-resolution, NOT charter activation").

Structured after the single-field sibling ``backfill_topology.py`` (NOT the
two-dimension ``backfill_identity.py``): one dataclass, one per-mission
decision function with a flat skip/skip/skip/needs-manual/write branch order,
one repo-walk. The coordination-branch git probe from ``backfill_topology.py``
is intentionally NOT copied here (irrelevant to ``mission_type``); there is
no dossier-rehash pass — the sync transport it would have driven is deleted
(issue #5), so a written ``mission_type`` is persisted to ``meta.json`` and
nothing else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from charter.activation.mission_type_key import canonical_mission_type_key
from charter.activation.mission_type_profile_repository import MissionTypeProfileRepository
from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
from specify_cli.mission_metadata import locked_update_meta
from specify_cli.mission import MissionNotFoundError

logger = logging.getLogger(__name__)

# Canonical meta.json keys (hoisted per Sonar S1192 — referenced >=3 sites
# across this module and its test suite).
MISSION_TYPE_KEY = "mission_type"
LEGACY_MISSION_KEY = "mission"

_REASON_META_NOT_FOUND = "meta.json not found"
_REASON_ALREADY_PRESENT = "mission_type already present"
_REASON_NO_LEGACY_VALUE = "no legacy mission value"

MissionTypeBackfillAction = Literal["wrote", "skip", "needs_manual_resolution", "error"]


@dataclass
class MissionTypeBackfillResult:
    """Per-mission result from :func:`backfill_mission_mission_type`.

    Attributes:
        feature_dir: Absolute path to the mission directory.
        slug: Directory name used as the mission slug.
        action: ``"wrote"`` — a profile-resolving ``mission_type`` was minted
            and persisted; ``"skip"`` — no meta.json, an existing
            ``mission_type`` key, or no candidate legacy value; ``"error"`` —
            unreadable / corrupt ``meta.json``.
        mission_type: The canonical key written, when *action* is
            ``"wrote"``.
        legacy_value: The raw legacy ``mission`` value seen, when reporting
            or on ``"needs_manual_resolution"``/``"wrote"``.
        reason: Human-readable explanation (populated on ``"skip"``,
            ``"needs_manual_resolution"``, and ``"error"``).
    """

    feature_dir: Path
    slug: str
    action: MissionTypeBackfillAction
    mission_type: str | None = None
    legacy_value: str | None = None
    reason: str | None = None


def _profile_resolves(repo: MissionTypeProfileRepository, key: str) -> bool:
    """The M3 §B tolerance authority — activation-independent, id-matched."""
    return repo.get(key) is not None


def _record_mission_type(meta: dict[str, Any], key: str) -> bool:
    """Set ``mission_type`` on a fresh *meta* unless the key is already present; report whether it changed."""
    if MISSION_TYPE_KEY in meta:
        return False
    meta[MISSION_TYPE_KEY] = key
    return True


def backfill_mission_mission_type(
    feature_dir: Path,
    *,
    repo: MissionTypeProfileRepository,
    dry_run: bool = False,
) -> MissionTypeBackfillResult:
    """Idempotently persist a profile-resolving ``mission_type`` into ``meta.json``.

    Never overwrites an existing ``mission_type`` key (AC-2a — key-presence
    skip, not value-validity: a present-but-blank ``mission_type`` is the
    deferred/out-of-scope ``typeless`` case and is deliberately left alone).
    A candidate whose legacy value canonicalizes but resolves no governance
    profile at any layer is reported ``needs_manual_resolution`` and never
    written (AC-4/R-4) — the backfill never manufactures an M3-breaker.

    Args:
        feature_dir: Absolute path to a single mission directory.
        repo: A :class:`MissionTypeProfileRepository` built once by the
            caller (never per-mission) via ``.for_project(repo_root)``.
        dry_run: When ``True``, report the would-write without touching disk.

    Returns:
        A :class:`MissionTypeBackfillResult` describing what happened.
    """
    slug = feature_dir.name
    meta_path = feature_dir / "meta.json"

    if not meta_path.exists():
        return MissionTypeBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="skip",
            reason=_REASON_META_NOT_FOUND,
        )

    try:
        meta_result = load_meta_fail_closed(feature_dir)
        meta: dict[str, Any] = meta_result or {}

        if MISSION_TYPE_KEY in meta:
            return MissionTypeBackfillResult(
                feature_dir=feature_dir,
                slug=slug,
                action="skip",
                reason=_REASON_ALREADY_PRESENT,
            )

        raw = meta.get(LEGACY_MISSION_KEY)
        key = canonical_mission_type_key(raw) if isinstance(raw, str) else None
        if key is None:
            # Non-string / blank legacy value: not a candidate. This mirrors
            # the audit's ``typeless`` classification (AC-6) — never crashes,
            # never becomes a candidate for the profile-resolution check.
            return MissionTypeBackfillResult(
                feature_dir=feature_dir,
                slug=slug,
                action="skip",
                reason=_REASON_NO_LEGACY_VALUE,
            )

        if not _profile_resolves(repo, key):
            return MissionTypeBackfillResult(
                feature_dir=feature_dir,
                slug=slug,
                action="needs_manual_resolution",
                legacy_value=raw,
                reason=f"no governance profile resolves for {key!r} at any layer",
            )

        if not dry_run:
            # Written on a fresh read under the Mission write lock; a key a concurrent writer
            # recorded meanwhile is never overwritten (AC-2a).
            locked_update_meta(feature_dir, lambda fresh: _record_mission_type(fresh, key), validate=False, fallback_to_dir_name=True)

        return MissionTypeBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="wrote",
            mission_type=key,
            legacy_value=raw,
        )
    except MissionMetaReadError as exc:
        return MissionTypeBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="error",
            reason=f"corrupt json: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 — FR-005: one bad mission never aborts the walk
        return MissionTypeBackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="error",
            reason=str(exc),
        )


def backfill_mission_type_repo(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> list[MissionTypeBackfillResult]:
    """Walk ``kitty-specs/`` and idempotently backfill every mission's ``mission_type``.

    The :class:`MissionTypeProfileRepository` is built **once** for the whole
    walk (never per-mission), mirroring the audit's resolve-once posture.

    Args:
        repo_root: Absolute path to the repository root.
        dry_run: When ``True``, compute results without writing any files.
        mission_slug: When provided, scope the walk to a single mission
            directory. A slug that does not exist under ``kitty-specs/``
            raises :class:`MissionNotFoundError` — never a silent
            ``wrote=0`` / empty-list false-green (AC-9).

    Returns:
        List of :class:`MissionTypeBackfillResult`, one per mission directory
        visited.

    Raises:
        MissionNotFoundError: ``mission_slug`` was given but no matching
            directory exists under ``kitty-specs/``.
    """
    kitty_specs = repo_root / "kitty-specs"

    if not kitty_specs.is_dir():
        if mission_slug is not None:
            raise MissionNotFoundError(
                f"No mission directory found for slug {mission_slug!r} under {kitty_specs}"
            )
        logger.warning("kitty-specs/ not found at %s", repo_root)
        return []

    # Filter by directory NAME (never join the untrusted ``--mission`` slug into a
    # filesystem path — mirrors the sibling backfills and keeps the slug out of the
    # path-construction FS-sink the untrusted-path containment audit tracks).
    all_dirs = sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir())
    if mission_slug is not None:
        candidates = [entry for entry in all_dirs if entry.name == mission_slug]
        if not candidates:
            raise MissionNotFoundError(
                f"No mission directory found for slug {mission_slug!r} under {kitty_specs}"
            )
    else:
        candidates = all_dirs

    repo = MissionTypeProfileRepository.for_project(repo_root)
    return [
        backfill_mission_mission_type(feature_dir, repo=repo, dry_run=dry_run)
        for feature_dir in candidates
    ]


# Only the repo-walk entry point is consumed by another ``src/`` module (the
# ``migrate backfill-mission-type`` command). The constants, the action alias,
# the result dataclass, and the per-mission helper are module-internal (used
# here and by tests via explicit import) — keeping them out of ``__all__``
# satisfies the symbol-level dead-code gate (C-007 / FR-303).
__all__ = ["backfill_mission_type_repo"]
