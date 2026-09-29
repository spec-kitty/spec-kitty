"""Forward migration tests for the single_branch code-lane re-stamp (#5100 IC-02).

Mission ``single-branch-topology-honesty-01M3M22V`` / WP03, T010.

Invariant T-1 (``data-model.md``): ``topology == single_branch`` implies
``lanes.json`` has no code lane. Before the mission's fail-closed writer
guard existed, a ``single_branch`` mission's lane computation was not yet
topology-aware, so 64 in-repo missions accumulated a stale
``topology: single_branch`` stamp alongside a ``lanes.json`` that already
had ordinary code lanes. This forward migration re-stamps every such
mission to ``topology: lanes`` and touches nothing else.

T010 test 1 uses a **registry lookup**, never an import of the migration
module by name -- an ``ImportError`` is not a valid red for "is this
migration registered" (mirrors
``tests/specify_cli/upgrade/migrations/test_heal_template_set_provenance.py``'s
``test_forward_migration_is_registered_at_current_release_version``, but via
``auto_discover_migrations()`` + ``MigrationRegistry.get_by_id`` instead of a
direct symbol import, so the RED before this WP's module exists is a bare
``assert ... is not None`` failure, not a collection-time ImportError).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit]

_MIGRATION_ID = "4_0_0rc5_single_branch_code_lanes_restamp"
_TARGET_VERSION = "4.0.0rc5"


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta_path


def _write_lanes(feature_dir: Path, lanes: list[dict[str, object]]) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "mission_slug": feature_dir.name,
        "mission_branch": f"kitty/mission-{feature_dir.name}",
        "target_branch": "main",
        "lanes": lanes,
        "computed_at": "2026-09-28T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
    }
    lanes_path = feature_dir / "lanes.json"
    lanes_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return lanes_path


def _single_branch_meta(mission_slug: str) -> dict[str, object]:
    return {
        "mission_type": "software-dev",
        "mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "mission_slug": mission_slug,
        "target_branch": "main",
        "topology": "single_branch",
    }


# ---------------------------------------------------------------------------
# T010 test 1: registered (RED-FIRST — commit this test alone)
# ---------------------------------------------------------------------------


def test_migration_registered() -> None:
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    auto_discover_migrations()
    migration = MigrationRegistry.get_by_id(_MIGRATION_ID)

    assert migration is not None
    assert migration.target_version == _TARGET_VERSION
    assert migration.runs_on_worktrees is False


# ---------------------------------------------------------------------------
# T010 test 2: selection + idempotency, over three mission shapes
# ---------------------------------------------------------------------------


def test_restamps_only_code_lane_missions_idempotent(tmp_path: Path) -> None:
    """(a) single_branch + code lane -> re-stamped; (b)/(c) unchanged, byte-identical."""
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    kitty_specs = tmp_path / "kitty-specs"

    # (a) single_branch with a code lane -> re-stamped to lanes.
    slug_a = "mission-a-code-lane"
    dir_a = kitty_specs / slug_a
    meta_a_path = _write_meta(dir_a, _single_branch_meta(slug_a))
    _write_lanes(dir_a, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    # (b) single_branch with only lane-planning -> unchanged.
    slug_b = "mission-b-planning-only"
    dir_b = kitty_specs / slug_b
    meta_b_path = _write_meta(dir_b, _single_branch_meta(slug_b))
    _write_lanes(dir_b, [{"lane_id": "lane-planning", "wp_ids": ["WP01", "WP02"]}])
    meta_b_before = meta_b_path.read_bytes()

    # (c) single_branch with no lanes.json -> unchanged.
    slug_c = "mission-c-no-lanes"
    dir_c = kitty_specs / slug_c
    meta_c_path = _write_meta(dir_c, _single_branch_meta(slug_c))
    meta_c_before = meta_c_path.read_bytes()

    auto_discover_migrations()
    migration = MigrationRegistry.get_by_id(_MIGRATION_ID)
    assert migration is not None

    result = migration.apply(tmp_path)

    assert result.success is True
    assert len(result.changes_made) == 1
    assert slug_a in result.changes_made[0]

    meta_a_after = json.loads(meta_a_path.read_text(encoding="utf-8"))
    assert meta_a_after["topology"] == "lanes"
    # Every OTHER meta key is byte-identical (canonical sorted-key write is
    # deterministic across the same content, so comparing the non-topology
    # keys is the honest "no other field changed" assertion).
    meta_a_before = _single_branch_meta(slug_a)
    for key, value in meta_a_before.items():
        if key == "topology":
            continue
        assert meta_a_after[key] == value

    assert meta_b_path.read_bytes() == meta_b_before, "planning-only mission must be untouched"
    assert meta_c_path.read_bytes() == meta_c_before, "lane-less mission must be untouched"

    # Idempotent (NFR-003): run again, byte-identical result.
    meta_a_after_first_run = meta_a_path.read_bytes()
    second_result = migration.apply(tmp_path)
    assert second_result.changes_made == []
    assert meta_a_path.read_bytes() == meta_a_after_first_run
    assert meta_b_path.read_bytes() == meta_b_before
    assert meta_c_path.read_bytes() == meta_c_before


def test_migration_never_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration writes meta.json but never shells out to git (no commit)."""
    import subprocess

    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    kitty_specs = tmp_path / "kitty-specs"
    slug = "mission-no-commit"
    dir_ = kitty_specs / slug
    _write_meta(dir_, _single_branch_meta(slug))
    _write_lanes(dir_, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    calls: list[list[str]] = []
    real_run = subprocess.run

    def _spy_run(cmd: list[str], *args: object, **kwargs: object) -> object:
        calls.append(list(cmd))
        return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subprocess, "run", _spy_run)

    auto_discover_migrations()
    migration = MigrationRegistry.get_by_id(_MIGRATION_ID)
    assert migration is not None
    migration.apply(tmp_path)

    assert not any("commit" in part for call in calls for part in call), f"migration must never commit: {calls}"


# ---------------------------------------------------------------------------
# Review cycle-1 blocker: a legacy feature_slug-keyed lanes.json (e.g.
# 064-complete-mission-identity-cutover) must be reported honestly, never
# folded into "no code lanes" -- that would be a false negative that lets a
# genuine Invariant T-1 violation slip through un-selected and un-flagged.
# ---------------------------------------------------------------------------


def _write_legacy_feature_slug_lanes(feature_dir: Path) -> Path:
    """A legacy manifest keyed ``feature_slug`` (no ``mission_slug``), one code lane.

    Mirrors ``064-complete-mission-identity-cutover``'s real on-disk shape:
    the canonical ``read_lanes_json`` raises ``CorruptLanesError`` on it
    (``KeyError: 'mission_slug'`` during ``LanesManifest.from_dict``) even
    though the manifest objectively has a code lane.
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "feature_slug": feature_dir.name,
        "mission_id": feature_dir.name,
        "mission_branch": f"kitty/mission-{feature_dir.name}",
        "target_branch": "main",
        "lanes": [{"lane_id": "lane-a", "wp_ids": [f"WP{n:02d}" for n in range(1, 10)]}],
        "computed_at": "2026-04-06T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
    }
    lanes_path = feature_dir / "lanes.json"
    lanes_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return lanes_path


def test_restamp_reports_unreadable_lanes_honestly_not_as_no_code_lanes(tmp_path: Path) -> None:
    """The blocker's exact repro: a feature_slug-keyed lanes.json is not "clean"."""
    from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

    kitty_specs = tmp_path / "kitty-specs"
    slug = "064-complete-mission-identity-cutover"
    dir_ = kitty_specs / slug
    _write_meta(dir_, _single_branch_meta(slug))
    _write_legacy_feature_slug_lanes(dir_)

    results = restamp_single_branch_with_code_lanes(tmp_path, dry_run=True)

    assert len(results) == 1
    result = results[0]
    assert result.slug == slug
    # Never silently "clean" (action stays skip -- this migration cannot
    # itself repair the manifest -- but the reason must be honest, distinct
    # from, and never confusable with, "no code lanes").
    assert result.action == "skip"
    assert result.reason is not None
    assert "no code lanes" not in result.reason
    assert "unreadable" in result.reason
    assert "mission_slug" in result.reason  # the reader's real KeyError text


def test_restamp_unreadable_lanes_never_writes_meta(tmp_path: Path) -> None:
    """A skip (of any reason) must never touch meta.json -- live or dry-run."""
    kitty_specs = tmp_path / "kitty-specs"
    slug = "064-complete-mission-identity-cutover"
    dir_ = kitty_specs / slug
    meta_path = _write_meta(dir_, _single_branch_meta(slug))
    _write_legacy_feature_slug_lanes(dir_)
    meta_before = meta_path.read_bytes()

    from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

    restamp_single_branch_with_code_lanes(tmp_path, dry_run=False)

    assert meta_path.read_bytes() == meta_before


# ---------------------------------------------------------------------------
# Operator decision (PR #5398 handoff addendum): the re-stamp migration skips
# TERMINAL (archived) missions. A completed mission is never run again, so its
# stale ``single_branch`` stamp never reaches the fail-closed writer guard --
# re-stamping it would only churn a frozen ``kitty-specs/`` dossier. The skip
# keys on the canonical completion predicate
# :func:`specify_cli.status.lifecycle.is_mission_completed` (a ``merged_at``
# marker OR every WP terminal), the single authority for "this mission reached
# completion". A LIVE mission still re-stamps -- the guard still applies to it.
# ---------------------------------------------------------------------------


def test_archived_single_branch_code_lane_mission_is_not_restamped(tmp_path: Path) -> None:
    """A completed (merged) single_branch + code-lane mission is skipped, meta untouched."""
    from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

    kitty_specs = tmp_path / "kitty-specs"
    slug = "archived-single-branch-code-lane"
    dir_ = kitty_specs / slug
    meta = _single_branch_meta(slug)
    meta["merged_at"] = "2026-09-25T14:19:52.098680+00:00"
    meta_path = _write_meta(dir_, meta)
    _write_lanes(dir_, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])
    meta_before = meta_path.read_bytes()

    results = restamp_single_branch_with_code_lanes(tmp_path, dry_run=False)

    assert len(results) == 1
    result = results[0]
    assert result.slug == slug
    assert result.action == "skip"
    assert result.reason is not None
    assert "archived" in result.reason
    assert "terminal" in result.reason
    # A skip never touches meta.json -- the frozen dossier stays byte-identical.
    assert meta_path.read_bytes() == meta_before


def test_live_single_branch_code_lane_mission_still_restamped(tmp_path: Path) -> None:
    """Twin control: a LIVE (un-merged, non-terminal) mission is still re-stamped."""
    from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

    kitty_specs = tmp_path / "kitty-specs"
    slug = "live-single-branch-code-lane"
    dir_ = kitty_specs / slug
    meta_path = _write_meta(dir_, _single_branch_meta(slug))  # no merged_at, no event log
    _write_lanes(dir_, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    results = restamp_single_branch_with_code_lanes(tmp_path, dry_run=False)

    assert len(results) == 1
    assert results[0].action == "restamped"
    assert json.loads(meta_path.read_text(encoding="utf-8"))["topology"] == "lanes"


# ---------------------------------------------------------------------------
# T010 test 3 (moved to WP05 T022 — post-tasks fold B-2): the fail-closed
# writer call sites land together with the single_branch compute_lanes arm.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T010 test 4: control — a planning-only, un-stamped mission derives
# SINGLE_BRANCH (the R-3 has_code_lanes fix in action) and the restamp
# migration never selects it
# ---------------------------------------------------------------------------


def test_planning_only_unstamped_mission_derives_lanes_and_is_never_restamped(tmp_path: Path) -> None:
    """A meta without ``topology`` + a planning-only manifest derives LANES at
    runtime (both before and after the restamp migration runs) and is never selected.

    #5100 FR-013 / #2602 (squad N7): a DERIVED ``single_branch`` never reaches a
    runtime reader -- only a STORED one is honoured -- so ``read_topology``
    returns LANES here (origin/main's runtime answer for this shape too). The
    history below describes the intermediate R-3 state.

    Review cycle-1 nit 2: this test was previously named/documented as
    "classification unchanged", which was misleading -- at the RED commit it
    fails with ``LANES is not SINGLE_BRANCH``, proving the ``has_code_lanes``
    fix DOES reclassify an unstamped planning-only mission (from the old,
    wrong LANES derivation to the correct SINGLE_BRANCH, R-3's intended
    semantics). What is actually invariant, and what this test really pins,
    is: (a) the DERIVED value is SINGLE_BRANCH, stably, both before and
    after the restamp migration runs over the whole repo, and (b) the
    restamp migration never selects this mission (its meta.json stays
    byte-identical) because a planning-only manifest never has a code lane.
    """
    from mission_runtime import MissionTopology

    from specify_cli.migration.backfill_topology import read_topology
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    kitty_specs = tmp_path / "kitty-specs"
    slug = "mission-planning-only-unstamped"
    dir_ = kitty_specs / slug
    meta_path = _write_meta(
        dir_,
        {
            "mission_type": "software-dev",
            "mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "mission_slug": slug,
            "target_branch": "main",
            # no "topology" key — un-backfilled legacy mission.
        },
    )
    _write_lanes(dir_, [{"lane_id": "lane-planning", "wp_ids": ["WP01"]}])
    meta_before = meta_path.read_bytes()

    before = read_topology(dir_)
    assert before is MissionTopology.LANES

    auto_discover_migrations()
    migration = MigrationRegistry.get_by_id(_MIGRATION_ID)
    assert migration is not None
    result = migration.apply(tmp_path)

    assert not any(slug in change for change in result.changes_made), "planning-only mission must never be selected"
    assert meta_path.read_bytes() == meta_before, "meta.json must be untouched by the restamp migration"

    after = read_topology(dir_)
    assert after is MissionTopology.LANES
    assert after is before
