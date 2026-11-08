"""Backfill the ``merged_at`` landing marker for Missions that landed before #4090 (#7433).

The one "has this Mission landed" signal (:func:`mission_runtime.mission_has_landed`, ADR
``2026-11-06-2``) reads the reopen-aware ``merged_at`` marker in the PRIMARY ``meta.json``.
Consolidation stamps it since #4090; a Mission that landed before that has none, so the status
read door treats it as not landed, and a coordination-topology one, whose coordination branch
consolidation tore down, refuses with ``COORDINATION_BRANCH_DELETED`` (#7335, #7431).

This backfill stamps the marker once, from the committed status log only (operator ruling
2026-11-08; the rule lives in :mod:`specify_cli.status.landing_evidence`):

* **Selected:** ``meta.json`` has no ``merged_at``.
* **Stamped** only when the Mission's status log, read through the status read door, shows every
  work package ``done`` or ``canceled`` with at least one ``done``, and records no
  ``MissionReopened`` event. ``mission_number`` is not evidence: ``doctor mission-state --fix``
  assigns it to Missions that never landed (#5471).
* **Date:** the ``at`` of the latest transition to ``done`` in that log, as aware-UTC ISO-8601.
  No git history is read.
* **Skipped and reported** otherwise, with the reason (unfinished work packages, all canceled,
  reopened, no log, unreadable log).
* **Write:** ``merged_at`` only, through the canonical meta writer
  :func:`~specify_cli.mission_metadata.locked_update_meta`. Nothing is committed here; the
  upgrade auto-commit or the operator owns that.

Idempotent: a stamped Mission has ``merged_at`` and is no longer selected, so a second run
writes nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from specify_cli.status import LandingVerdict, read_landing_evidence

__all__ = [
    "MergedAtBackfillAction",
    "MergedAtBackfillResult",
    "backfill_merged_at",
    "has_merged_at_to_backfill",
]

MergedAtBackfillAction = Literal["stamped", "skipped", "error"]

_META_JSON = "meta.json"
_MERGED_AT = "merged_at"


@dataclass(frozen=True)
class MergedAtBackfillResult:
    """The outcome for one Mission without ``merged_at``.

    ``verdict`` is the landing-evidence verdict (``None`` when ``meta.json`` itself is
    unreadable); ``reason`` says why a Mission was not stamped, and ``detail`` what was seen
    (the unfinished work packages, or the read error).
    """

    slug: str
    action: MergedAtBackfillAction
    verdict: LandingVerdict | None = None
    merged_at: str | None = None
    reason: str = ""
    detail: str = ""


def _mission_dirs(repo_root: Path) -> list[Path]:
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        return []
    return sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir() and (entry / _META_JSON).is_file())


def _needs_marker(meta: dict[str, Any]) -> bool:
    return not str(meta.get(_MERGED_AT) or "").strip()


def _stamp(feature_dir: Path, repo_root: Path, merged_at: str) -> bool:
    """Write ``merged_at`` under the Mission write lock unless a writer got there first."""
    from specify_cli.mission_metadata import locked_update_meta

    wrote = False

    def mutate(fresh: dict[str, Any]) -> bool:
        nonlocal wrote
        if not _needs_marker(fresh):
            return False
        fresh[_MERGED_AT] = merged_at
        wrote = True
        return True

    locked_update_meta(feature_dir, mutate, validate=False, repo_root=repo_root, fallback_to_dir_name=True)
    return wrote


def _backfill_one(repo_root: Path, feature_dir: Path, *, dry_run: bool) -> MergedAtBackfillResult | None:
    """The result for one Mission dir, or ``None`` when it already carries ``merged_at``."""
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    slug = feature_dir.name
    try:
        meta = load_meta_fail_closed(feature_dir) or {}
    except MissionMetaReadError as exc:
        return MergedAtBackfillResult(slug, "error", reason="meta.json is unreadable", detail=str(exc))
    if not _needs_marker(meta):
        return None
    evidence = read_landing_evidence(repo_root, slug)
    if not evidence.holds or evidence.merged_at is None:
        action: MergedAtBackfillAction = "error" if evidence.verdict is LandingVerdict.UNREADABLE else "skipped"
        return MergedAtBackfillResult(slug, action, verdict=evidence.verdict, reason=evidence.summary, detail=evidence.detail)
    if not dry_run and not _stamp(feature_dir, repo_root, evidence.merged_at):
        return None
    return MergedAtBackfillResult(slug, "stamped", verdict=evidence.verdict, merged_at=evidence.merged_at)


def _iter_results(repo_root: Path, *, dry_run: bool) -> Iterator[MergedAtBackfillResult]:
    for feature_dir in _mission_dirs(repo_root):
        result = _backfill_one(repo_root, feature_dir, dry_run=dry_run)
        if result is not None:
            yield result


def has_merged_at_to_backfill(repo_root: Path) -> bool:
    """True when at least one Mission would be stamped (stops at the first; writes nothing)."""
    return any(result.action == "stamped" for result in _iter_results(repo_root, dry_run=True))


def backfill_merged_at(repo_root: Path, *, dry_run: bool = False) -> list[MergedAtBackfillResult]:
    """Stamp ``merged_at`` on every Mission under ``kitty-specs/`` whose status log shows a landing.

    Returns one result per Mission without ``merged_at`` (stamped, skipped with its reason, or an
    error for an unreadable ``meta.json`` or status log); Missions that already carry
    ``merged_at`` are not listed. With *dry_run* nothing is written and ``stamped`` means
    "would be".
    """
    return list(_iter_results(repo_root, dry_run=dry_run))
