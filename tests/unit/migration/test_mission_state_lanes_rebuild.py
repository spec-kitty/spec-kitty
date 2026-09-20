"""#4758 canonical-state RECOVERY: lanes.json rebuild in ``doctor mission-state --fix``.

Mission ``canonical-state-recovery-01M2ZE3D`` / WP03.

The wedge (research.md, WP01/WP02): a mission whose canonical event log has
moved a WP past ``planned`` (execution has begun) while ``lanes.json`` is
absent from disk. ``lanes.json`` resolves worktrees for ``move-task`` and
friends, so a wedged mission can neither keep executing nor safely
re-finalize (WP01's ``_preserve_or_capture_planning_commit_sha`` refuses --
there is no recorded SHA to preserve). The one documented recovery action is
``spec-kitty doctor mission-state --fix --mission <slug>``
(``migration.mission_state.repair_repo``), which rebuilds ``lanes.json``
from the event log via WP01's pure
``specify_cli.lanes.compute_and_persist.compute_and_write_lanes`` core when
the shared wedge predicate
(``specify_cli.lanes.persistence.is_execution_wedged``) holds.

T011 is the pinned RED-first regression: before this WP's fix, ``repair_repo``
never rebuilds ``lanes.json`` at all -- a wedged mission stays wedged even
after ``--fix``. T012-T014 cover the fail-closed corrupt-log path, the #3311
never-rewrite guard, NFR-004 idempotence, the ownerless-mission edge case,
and an NFR-002 parity row for this specific condition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.migration.mission_state import (
    LANES_REBUILD_SKIPPED_NO_OWNED_FILES_ACTION,
    LANES_REBUILT_ACTION,
    repair_repo,
)
from specify_cli.status.bootstrap import bootstrap_canonical_state
from specify_cli.status.emit import emit_status_transition

pytestmark = [pytest.mark.regression, pytest.mark.unit]

_MISSION_SLUG = "070-wedge-mission"


def _write_meta(feature_dir: Path, mission_slug: str, *, mission_id: str = "01ARZ3NDEKTSV4RRFFQ69G5FAV") -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_type": "software-dev",
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )


def _write_owned_wp_files(repo_root: Path, tasks_dir: Path, wp_ids: tuple[str, ...]) -> None:
    """Write real code-change WP frontmatter files with disjoint owned_files.

    Also creates the files each WP's glob matches, so lane computation hits
    the happy path with zero glob-validation errors (mirrors
    ``tests/cli/test_tasks_finalize_lanes_minting.py``'s WP01 fixture).
    """
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for wp_id in wp_ids:
        (repo_root / "src" / wp_id.lower()).mkdir(parents=True, exist_ok=True)
        (repo_root / "src" / wp_id.lower() / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (tasks_dir / f"{wp_id}-test.md").write_text(
            "---\n"
            f"work_package_id: {wp_id}\n"
            f"title: Test {wp_id}\n"
            "execution_mode: code_change\n"
            f"owned_files:\n  - src/{wp_id.lower()}/**\n"
            f"authoritative_surface: src/{wp_id.lower()}/\n"
            "---\n\n"
            f"# {wp_id}\n\n## Activity Log\n",
            encoding="utf-8",
        )


def _write_ownerless_wp_files(tasks_dir: Path, wp_ids: tuple[str, ...]) -> None:
    """Write WP frontmatter files declaring no ownership at all (#4758 WP01 fold)."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for wp_id in wp_ids:
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n---\n\n# {wp_id}\n\n## Activity Log\n",
            encoding="utf-8",
        )


def _seed_wedged_events(feature_dir: Path, mission_slug: str, *, claim_wp: str = "WP01") -> None:
    """Bootstrap genesis->planned for every WP, then advance one WP forward.

    Reproduces the #4758 wedge directly at the canonical event-log layer
    (bypassing ``move-task``, which would itself refuse without
    ``lanes.json`` -- the wedge is, by definition, a state ``move-task``
    cannot have produced through its own guarded path; it models an earlier
    bug/interruption that left the event log ahead of ``lanes.json``).
    """
    bootstrap_canonical_state(feature_dir, mission_slug, repo_root=feature_dir.parent.parent)
    emit_status_transition(
        feature_dir,
        wp_id=claim_wp,
        to_lane="claimed",
        actor="test-wedge-seed",
        mission_slug=mission_slug,
        repo_root=feature_dir.parent.parent,
        ensure_sync_daemon=False,
        fan_out=False,
    )


def _build_wedged_mission(tmp_path: Path, mission_slug: str = _MISSION_SLUG, *, ownerless: bool = False) -> Path:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    _write_meta(feature_dir, mission_slug)
    if ownerless:
        _write_ownerless_wp_files(tasks_dir, ("WP01", "WP02"))
    else:
        _write_owned_wp_files(tmp_path, tasks_dir, ("WP01", "WP02"))
    _seed_wedged_events(feature_dir, mission_slug)
    assert read_lanes_json(feature_dir) is None, "fixture precondition: no lanes.json before repair"
    return feature_dir


# ---------------------------------------------------------------------------
# T011: RED-first regression (pinned #4758)
# ---------------------------------------------------------------------------


def test_repair_rebuilds_lanes_json_for_a_wedged_mission(tmp_path: Path) -> None:
    """#4758: ``doctor mission-state --fix`` un-wedges a mission.

    RED on the pre-WP03 tree: ``repair_repo`` canonicalized meta.json/
    status.events.jsonl/status.json but never touched ``lanes.json`` -- a
    wedged mission stayed wedged even after ``--fix``. GREEN post-fix:
    ``lanes.json`` is rebuilt from the event log, covers every owned WP, and
    the rebuild is recorded on the mission's ``meta_actions``.
    """
    feature_dir = _build_wedged_mission(tmp_path)

    report = repair_repo(tmp_path, mission=_MISSION_SLUG)

    result = next(m for m in report.missions if m.mission_slug == _MISSION_SLUG)
    assert result.status != "error", result.validation_errors
    assert LANES_REBUILT_ACTION in result.meta_actions

    lanes = read_lanes_json(feature_dir)
    assert lanes is not None, "#4758 regression: mission is still wedged after 'doctor mission-state --fix'."
    lanes_wp_ids = {wp_id for lane_entry in lanes.lanes for wp_id in lane_entry.wp_ids}
    assert lanes_wp_ids == {"WP01", "WP02"}
    # Honestly unrecoverable (the sole record of the SHA is lanes.json
    # itself -- exactly what was missing): never a fabricated/guessed value.
    assert lanes.planning_commit_sha is None


# ---------------------------------------------------------------------------
# T012: never rewrite existing lanes.json (#3311) + fail-closed corrupt log
# ---------------------------------------------------------------------------


def test_repair_never_rewrites_existing_lanes_json(tmp_path: Path) -> None:
    """#3311 guard preserved: a mission that already has lanes.json is untouched."""
    feature_dir = _build_wedged_mission(tmp_path)

    first = repair_repo(tmp_path, mission=_MISSION_SLUG)
    first_result = next(m for m in first.missions if m.mission_slug == _MISSION_SLUG)
    assert LANES_REBUILT_ACTION in first_result.meta_actions
    lanes_bytes_after_rebuild = (feature_dir / "lanes.json").read_bytes()

    second = repair_repo(tmp_path, mission=_MISSION_SLUG)
    second_result = next(m for m in second.missions if m.mission_slug == _MISSION_SLUG)
    assert LANES_REBUILT_ACTION not in second_result.meta_actions
    assert (feature_dir / "lanes.json").read_bytes() == lanes_bytes_after_rebuild


def test_repair_does_not_rebuild_lanes_when_execution_has_not_begun(tmp_path: Path) -> None:
    """A freshly-bootstrapped mission (every WP still 'planned') is not wedged.

    No ``lanes.json`` is written by this repair path -- that is
    ``finalize-tasks``'s job for a first-ever finalize (#4758 WP01), not
    doctor's recovery action, which exists only for the wedge.
    """
    mission_slug = "071-healthy-planned"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    _write_meta(feature_dir, mission_slug)
    _write_owned_wp_files(tmp_path, tasks_dir, ("WP01",))
    bootstrap_canonical_state(feature_dir, mission_slug, repo_root=tmp_path)

    report = repair_repo(tmp_path, mission=mission_slug)

    result = next(m for m in report.missions if m.mission_slug == mission_slug)
    assert LANES_REBUILT_ACTION not in result.meta_actions
    assert read_lanes_json(feature_dir) is None


def test_repair_fails_closed_on_corrupt_event_log_without_partial_lanes(tmp_path: Path) -> None:
    """A corrupt/truncated event log refuses -- never a partial lanes.json.

    Mirrors the existing ``_read_jsonl_rows``/row-canonicalization fail-closed
    behavior this repair already had before WP03; the assertion pins that the
    lanes-rebuild step specifically inherits it rather than running on an
    unreliable canonical state.
    """
    feature_dir = _build_wedged_mission(tmp_path)
    events_path = feature_dir / "status.events.jsonl"
    # Truncate mid-line: syntactically invalid JSON, simulating a crash
    # during an append.
    original = events_path.read_text(encoding="utf-8")
    events_path.write_text(original[: len(original) // 2], encoding="utf-8")

    report = repair_repo(tmp_path, mission=_MISSION_SLUG)

    result = next(m for m in report.missions if m.mission_slug == _MISSION_SLUG)
    assert result.status == "error"
    assert result.validation_errors, "expected a clear diagnostic for the corrupt event log"
    assert read_lanes_json(feature_dir) is None, "must never write a partial lanes.json on a fail-closed refusal"
    assert not (feature_dir / "lanes.json").exists()


# ---------------------------------------------------------------------------
# T013: green e2e, idempotence (NFR-004), ownerless mission
# ---------------------------------------------------------------------------


def test_repair_rebuild_is_idempotent_on_a_healthy_mission(tmp_path: Path) -> None:
    """NFR-004: re-running repair after the mission is un-wedged changes nothing."""
    feature_dir = _build_wedged_mission(tmp_path)

    repair_repo(tmp_path, mission=_MISSION_SLUG)
    lanes_bytes = (feature_dir / "lanes.json").read_bytes()

    second = repair_repo(tmp_path, mission=_MISSION_SLUG)
    result = next(m for m in second.missions if m.mission_slug == _MISSION_SLUG)

    assert result.status == "unchanged"
    assert result.file_changes == []
    assert (feature_dir / "lanes.json").read_bytes() == lanes_bytes


def test_repair_handles_ownerless_wedged_mission_coherently(tmp_path: Path) -> None:
    """An ownerless wedged mission (no WP declares owned_files) never crashes.

    WP01's review fold: legacy finalize is a silent no-op on lanes for
    ownerless WPs. Doctor's recovery mirrors that -- there is nothing
    meaningful to lane-compute -- but reports *why* explicitly rather than
    a bare "unchanged" that could be mistaken for "nothing was wrong".
    """
    feature_dir = _build_wedged_mission(tmp_path, mission_slug="072-ownerless-wedge", ownerless=True)

    report = repair_repo(tmp_path, mission="072-ownerless-wedge")

    result = next(m for m in report.missions if m.mission_slug == "072-ownerless-wedge")
    assert result.status != "error", result.validation_errors
    assert LANES_REBUILD_SKIPPED_NO_OWNED_FILES_ACTION in result.meta_actions
    assert read_lanes_json(feature_dir) is None


# ---------------------------------------------------------------------------
# NFR-002 parity: every canonical-state condition this repair DETECTS has a
# clearing CURE. WP03 contributes exactly one row -- the #4758 wedge -- to
# the larger detect/cure matrix WP01/WP02 established for the surrounding
# conditions; this table asserts that row has zero detect-without-cure gap.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("condition", "detect", "cure_clears_condition"),
    [
        (
            "execution_begun_no_lanes_json (#4758 wedge)",
            lambda feature_dir: read_lanes_json(feature_dir) is None,
            True,
        ),
    ],
)
def test_nfr002_detect_cure_parity_for_the_wedge_condition(
    tmp_path: Path,
    condition: str,
    detect: object,
    cure_clears_condition: bool,
) -> None:
    """Table-driven NFR-002 parity check: 0 detect-without-cure rows for this WP."""
    feature_dir = _build_wedged_mission(tmp_path)
    assert detect(feature_dir), f"{condition}: expected the condition to be present before repair"  # type: ignore[operator]

    repair_repo(tmp_path, mission=_MISSION_SLUG)

    condition_cleared = not detect(feature_dir)  # type: ignore[operator]
    assert condition_cleared == cure_clears_condition, f"{condition}: detect-without-cure gap"
