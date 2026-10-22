"""US6 / SC-008 — mission archiving is a governed, first-class lifecycle operation.

Covers the four US6 acceptance scenarios plus the AM-4 (never-automatic) and
AM-5 (cancellation clears deferrals) invariants for
``specify_cli.missions._archive``:

1. a non-terminal mission is refused (AM-1)
2. a terminal mission carrying a ``still_present`` invariant is refused (AM-2)
3. a clean terminal mission is archived, stays enumerable, and is excluded from
   live validation (AM-3)
4. the FR-014 migration (and no lifecycle step) can auto-archive (AM-4)

plus AM-5: cancelling a mission with a dangling ``deferred_to_consolidation``
invariant is archivable and the deferral resolves to a ``canceled`` disposition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.acceptance.matrix import (
    AcceptanceMatrix,
    NegativeInvariant,
    write_acceptance_matrix,
)
from specify_cli.missions._archive import (
    MissionArchiveRefused,
    archive_mission,
    evaluate_archive_eligibility,
    is_mission_archived,
    list_archived_missions,
    resolve_deferrals_for_cancellation,
    resolve_terminal_state,
)
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "archive-demo-01KY7ARCHV"
_MISSION_ID = "01KY7ARCHV0000000000000000"

# The lane chain a completed WP walks, and the abandonment chain. Each is a
# monotonic (from_lane, to_lane) sequence the reducer folds to the final lane.
_DONE_CHAIN: list[tuple[Lane, Lane]] = [
    (Lane.PLANNED, Lane.CLAIMED),
    (Lane.CLAIMED, Lane.IN_PROGRESS),
    (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
    (Lane.FOR_REVIEW, Lane.IN_REVIEW),
    (Lane.IN_REVIEW, Lane.APPROVED),
    (Lane.APPROVED, Lane.DONE),
]
_CANCELED_CHAIN: list[tuple[Lane, Lane]] = [
    (Lane.PLANNED, Lane.CLAIMED),
    (Lane.CLAIMED, Lane.CANCELED),
]
_IN_PROGRESS_CHAIN: list[tuple[Lane, Lane]] = [
    (Lane.PLANNED, Lane.CLAIMED),
    (Lane.CLAIMED, Lane.IN_PROGRESS),
]


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _MISSION_SLUG,
                "slug": _MISSION_SLUG,
                "mission_id": _MISSION_ID,
                "mission_number": None,
                "mission_type": "software-dev",
                "friendly_name": "Archive Demo",
            }
        ),
        encoding="utf-8",
    )


def _drive_wp(feature_dir: Path, wp_id: str, chain: list[tuple[Lane, Lane]]) -> None:
    """Append a realistic transition chain for one WP to status.events.jsonl."""
    for idx, (from_lane, to_lane) in enumerate(chain):
        # 26-char ULID-shaped id, unique per (wp, step).
        suffix = f"{wp_id}{idx:02d}"
        event_id = ("01HXYZ" + "0" * (26 - 6 - len(suffix)) + suffix).upper()
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=event_id[:26],
                mission_slug=_MISSION_SLUG,
                mission_id=_MISSION_ID,
                wp_id=wp_id,
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-07-23T12:{idx:02d}:00+00:00",
                actor="operator",
                force=False,
                execution_mode="worktree",
            ),
        )


def _write_matrix(feature_dir: Path, invariants: list[NegativeInvariant]) -> None:
    matrix = AcceptanceMatrix(mission_slug=_MISSION_SLUG, negative_invariants=invariants)
    write_acceptance_matrix(feature_dir, matrix)


def _seed_mission(
    tmp_path: Path,
    *,
    wp_chains: dict[str, list[tuple[Lane, Lane]]],
    invariants: list[NegativeInvariant] | None = None,
) -> tuple[Path, Path]:
    """Seed a mission on disk. Returns ``(project_root, feature_dir)``."""
    project_root = tmp_path
    feature_dir = project_root / "kitty-specs" / _MISSION_SLUG
    _write_meta(feature_dir)
    for wp_id, chain in wp_chains.items():
        _drive_wp(feature_dir, wp_id, chain)
    _write_matrix(feature_dir, invariants or [])
    return project_root, feature_dir


def _invariant(inv_id: str, result: str) -> NegativeInvariant:
    return NegativeInvariant(
        invariant_id=inv_id,
        description=f"{inv_id} must not exist",
        verification_method="grep_absence",
        result=result,
    )


# ---------------------------------------------------------------------------
# US6 scenario 1 — non-terminal mission refused (AM-1)
# ---------------------------------------------------------------------------


def test_non_terminal_mission_is_refused(tmp_path: Path) -> None:
    project_root, feature_dir = _seed_mission(
        tmp_path, wp_chains={"WP01": _IN_PROGRESS_CHAIN}
    )
    # Real resolver confirms the mission is NOT terminal.
    assert resolve_terminal_state(feature_dir) is None

    with pytest.raises(MissionArchiveRefused) as excinfo:
        archive_mission(
            project_root=project_root,
            feature_dir=feature_dir,
            archived_by="operator",
            reason="tidying old missions",
        )
    assert excinfo.value.code == "AM-1"
    assert "terminal" in excinfo.value.reason
    # Refused archives leave no record.
    assert list_archived_missions(project_root) == []


# ---------------------------------------------------------------------------
# US6 scenario 2 — still_present invariant refused (AM-2)
# ---------------------------------------------------------------------------


def test_terminal_mission_with_still_present_is_refused(tmp_path: Path) -> None:
    project_root, feature_dir = _seed_mission(
        tmp_path,
        wp_chains={"WP01": _DONE_CHAIN},
        invariants=[_invariant("NI-1", "still_present")],
    )
    assert resolve_terminal_state(feature_dir) == "merged"

    with pytest.raises(MissionArchiveRefused) as excinfo:
        archive_mission(
            project_root=project_root,
            feature_dir=feature_dir,
            archived_by="operator",
            reason="wants to forget this violation",
        )
    assert excinfo.value.code == "AM-2"
    assert "still_present" in excinfo.value.reason
    assert not is_mission_archived(project_root, _MISSION_ID)


# ---------------------------------------------------------------------------
# US6 scenario 3 — clean terminal archived + enumerable + excluded (AM-3)
# ---------------------------------------------------------------------------


def test_clean_terminal_mission_is_archived_enumerable_and_excluded(
    tmp_path: Path,
) -> None:
    project_root, feature_dir = _seed_mission(
        tmp_path,
        wp_chains={"WP01": _DONE_CHAIN},
        invariants=[_invariant("NI-1", "confirmed_absent")],
    )
    assert resolve_terminal_state(feature_dir) == "merged"
    assert not is_mission_archived(project_root, _MISSION_ID)

    outcome = archive_mission(
        project_root=project_root,
        feature_dir=feature_dir,
        archived_by="stijn",
        reason="completed and released; retiring the dossier",
    )

    record = outcome.record
    assert record.mission_id == _MISSION_ID
    assert record.archived_by == "stijn"
    assert record.reason == "completed and released; retiring the dossier"
    assert record.terminal_state_at_archive == "merged"
    assert record.archived_at  # timestamp is stamped

    # AM-3: excluded from live validation (predicate flips) …
    assert is_mission_archived(project_root, _MISSION_ID)
    # … but remains enumerable.
    listed = list_archived_missions(project_root)
    assert [r.mission_id for r in listed] == [_MISSION_ID]
    assert listed[0].reason == record.reason


# ---------------------------------------------------------------------------
# US6 scenario 4 — the migration never auto-archives (AM-4)
# ---------------------------------------------------------------------------


def test_no_migration_or_lifecycle_module_imports_archive() -> None:
    """AM-4: archiving is unreachable from any migration / lifecycle step.

    Closed by construction (directive 043): no module under the migration
    surfaces references the archive module, so the FR-014 backfill migration —
    or any of its failure paths — can never call it.
    """
    src_root = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
    migration_dirs = [
        src_root / "cli" / "commands" / "migrate",
        src_root / "upgrade" / "migrations",
    ]
    migration_files = [
        src_root / "status" / "migrate.py",
    ]
    scanned = list(migration_files)
    for directory in migration_dirs:
        if directory.exists():
            scanned.extend(directory.rglob("*.py"))

    offenders: list[str] = []
    for path in scanned:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "missions._archive" in text or "archive_mission" in text:
            offenders.append(str(path.relative_to(src_root)))

    assert offenders == [], (
        "AM-4 violated — a migration/lifecycle module references the archive "
        f"surface: {offenders}"
    )


def test_archive_requires_operator_identity(tmp_path: Path) -> None:
    """AM-4 backstop: an anonymous (empty) operator identity is refused."""
    project_root, feature_dir = _seed_mission(
        tmp_path, wp_chains={"WP01": _DONE_CHAIN}
    )
    with pytest.raises(MissionArchiveRefused) as excinfo:
        archive_mission(
            project_root=project_root,
            feature_dir=feature_dir,
            archived_by="   ",
            reason="no operator named",
        )
    assert excinfo.value.code == "AM-4"


# ---------------------------------------------------------------------------
# AM-5 — cancellation clears deferrals; abandonment is not a deadlock
# ---------------------------------------------------------------------------


def test_canceled_mission_with_dangling_deferral_is_archivable(tmp_path: Path) -> None:
    project_root, feature_dir = _seed_mission(
        tmp_path,
        wp_chains={"WP01": _CANCELED_CHAIN},
        invariants=[_invariant("NI-1", "deferred_to_consolidation")],
    )
    assert resolve_terminal_state(feature_dir) == "canceled"

    outcome = archive_mission(
        project_root=project_root,
        feature_dir=feature_dir,
        archived_by="operator",
        reason="abandoned; consolidation never happened",
    )

    assert outcome.record.terminal_state_at_archive == "canceled"
    # The dangling deferral resolves to a ``canceled`` disposition (not a deadlock).
    assert [d.invariant_id for d in outcome.cleared_deferrals] == ["NI-1"]
    assert outcome.cleared_deferrals[0].disposition == "canceled"
    assert is_mission_archived(project_root, _MISSION_ID)


def test_merged_mission_does_not_clear_deferrals() -> None:
    """Only cancellation clears deferrals — a merged mission leaves them alone."""
    dispositions = resolve_deferrals_for_cancellation(
        [("NI-1", "deferred_to_consolidation")], terminal_state="merged"
    )
    assert dispositions == []


# ---------------------------------------------------------------------------
# Pure guard unit coverage (no filesystem)
# ---------------------------------------------------------------------------


def test_eligibility_requires_stated_reason() -> None:
    verdict = evaluate_archive_eligibility(
        terminal_state="merged", invariant_results=[], reason="   "
    )
    assert not verdict.eligible
    assert verdict.refusal_code == "AM-1"


def test_eligibility_clean_terminal_passes() -> None:
    verdict = evaluate_archive_eligibility(
        terminal_state="canceled",
        invariant_results=["confirmed_absent", "deferred_to_consolidation"],
        reason="abandoned",
    )
    assert verdict.eligible
    assert verdict.refusal_code is None
