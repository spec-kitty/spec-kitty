"""The remaining ``meta.json`` writers take the Mission write lock (mission-writer-followups WP03, FR-020).

Three families, each proven part by part (C-006):

* documentation state (``doc_analysis/doc_state.py``),
* consolidation (``phase_teardown``, ``baseline``, ``mission_number/bake``),
* migrations and upgrades (``migration/*``, ``upgrade/*``).

Every case runs two ways. The overlap test pauses writer A just before its ``meta.json`` write and runs a locked
writer B on another thread (see ``tests/_meta_overlap.py``: A is released only once B finished, or once B is observed
waiting for the lock). Without the lock A's stale copy overwrites B's field; with it B queues behind A and both
survive. The acquisition test checks the writer takes the Mission lock at all.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from typing import Any

import pytest

from specify_cli.mission_metadata import locked_update_meta
from specify_cli.status.mission_write import mission_lock_key
from tests._meta_overlap import run_overlap

pytestmark = [pytest.mark.unit]

mission_write = importlib.import_module("specify_cli.status.mission_write")

SLUG = "060-test"
MISSION_ID = "01TESTMISSION00000000000000"
B_MARKER = "writer_b_marker"
B_VALUE = "kept"

DOC_FAMILY = "documentation_state"
CONSOLIDATION_FAMILY = "consolidation"
MIGRATION_FAMILY = "migrations"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@dataclass(frozen=True)
class Case:
    """One writer under test: the meta it starts from, how to call it, and what it leaves behind."""

    family: str
    name: str
    call: Callable[[Path, Path], object]  # (repo, feature_dir) -> anything
    check: Callable[[dict[str, Any]], bool]  # is the writer's own result in the final meta?
    seed: dict[str, Any] = field(default_factory=dict)


class _Repo:
    """A profile repository stub that resolves every key."""

    def get(self, key: str) -> object:
        return object()


def _doc_state_full() -> dict[str, Any]:
    return {
        "iteration_mode": "initial",
        "divio_types_selected": ["tutorial"],
        "generators_configured": [],
        "target_audience": "developers",
        "last_audit_date": None,
        "coverage_percentage": 0.25,
    }


def _run(**attrs: Any) -> SimpleNamespace:
    return SimpleNamespace(lanes_manifest=SimpleNamespace(target_branch="main"), mission_slug=SLUG, **attrs)


def _doc(fn_name: str, *args: Any) -> Callable[[Path, Path], object]:
    def call(repo: Path, feature_dir: Path) -> object:
        import specify_cli.doc_analysis.doc_state as doc_state

        return getattr(doc_state, fn_name)(feature_dir / "meta.json", *args)

    return call


def _teardown(fn_name: str) -> Callable[[Path, Path], object]:
    def call(repo: Path, feature_dir: Path) -> object:
        import specify_cli.consolidation.phase_teardown as phase_teardown
        import specify_cli.lanes.single_branch_landing as landing

        run = _run(main_repo=repo, target_feature_dir=feature_dir)
        with (
            patch.object(landing, "lands_mission_branch", return_value=True),
            patch.object(phase_teardown, "commit_merge_bookkeeping"),
            patch.object(phase_teardown, "_paths_have_status_changes", return_value=False),
        ):
            return getattr(phase_teardown, fn_name)(run)

    return call


def _baseline(fn_name: str, *args: Any, **kwargs: Any) -> Callable[[Path, Path], object]:
    def call(repo: Path, feature_dir: Path) -> object:
        import specify_cli.consolidation.baseline as baseline

        return getattr(baseline, fn_name)(feature_dir, *args, **kwargs)

    return call


def _bake(fn_name: str, *args: Any, with_repo: bool = False, with_slug: bool = False) -> Callable[[Path, Path], object]:
    def call(repo: Path, feature_dir: Path) -> object:
        import specify_cli.consolidation.mission_number.bake as bake

        lead: list[Any] = [repo] if with_repo else []
        if with_slug:
            lead.append(SLUG)
        target = [feature_dir] if not with_slug else []
        return getattr(bake, fn_name)(*lead, *target, *args)

    return call


def _migration(module: str, fn_name: str, *args: Any, **kwargs: Any) -> Callable[[Path, Path], object]:
    def call(repo: Path, feature_dir: Path) -> object:
        import importlib

        return getattr(importlib.import_module(module), fn_name)(feature_dir, *args, **kwargs)

    return call


def _apply_target_branch_migration(repo: Path, feature_dir: Path) -> object:
    from specify_cli.upgrade.migrations.m_0_13_8_target_branch import TargetBranchMigration

    return TargetBranchMigration().apply(repo)


def _write_feature_meta(repo: Path, feature_dir: Path) -> object:
    from specify_cli.upgrade.feature_meta import load_feature_meta, write_feature_meta

    loaded = load_feature_meta(feature_dir) or {}
    write_feature_meta(feature_dir, {**loaded, "baseline_marker": "written"})
    return None


def _restamp_single_branch(repo: Path, feature_dir: Path) -> object:
    from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

    return restamp_single_branch_with_code_lanes(repo)


def _repair_meta_phase(repo: Path, feature_dir: Path) -> object:
    from specify_cli.migration.mission_state import _RepairState, _repair_meta_phase

    state = _RepairState(mission_slug=SLUG)
    return _repair_meta_phase(repo, feature_dir, [], state, generated_ids=None)


def _doc_update_state(repo: Path, feature_dir: Path) -> object:
    from specify_cli.doc_analysis.doc_state import update_documentation_state

    return update_documentation_state(feature_dir / "meta.json", coverage_percentage=0.75)


def _assign_planning_only(repo: Path, feature_dir: Path) -> object:
    from specify_cli.consolidation.mission_number.bake import _assign_planning_only_mission_number_if_needed

    return _assign_planning_only_mission_number_if_needed(repo, feature_dir)


def _backfill_mission_ids(repo: Path, feature_dir: Path) -> object:
    from specify_cli.migration.backfill_identity import backfill_mission_ids

    return backfill_mission_ids(repo)


CASES: list[Case] = [
    Case(DOC_FAMILY, "set_audit_metadata", _doc("set_audit_metadata", None, 0.5), lambda m: m["documentation_state"]["coverage_percentage"] == 0.5),
    Case(
        DOC_FAMILY,
        "set_generators_configured",
        _doc("set_generators_configured", [{"name": "sphinx", "language": "python", "config_path": "docs/conf.py"}]),
        lambda m: m["documentation_state"]["generators_configured"][0]["name"] == "sphinx",
    ),
    Case(DOC_FAMILY, "set_iteration_mode", _doc("set_iteration_mode", "gap_filling"), lambda m: m["documentation_state"]["iteration_mode"] == "gap_filling"),
    Case(
        DOC_FAMILY,
        "set_divio_types_selected",
        _doc("set_divio_types_selected", ["how-to"]),
        lambda m: m["documentation_state"]["divio_types_selected"] == ["how-to"],
    ),
    Case(
        DOC_FAMILY,
        "write_documentation_state",
        _doc("write_documentation_state", _doc_state_full()),
        lambda m: m["documentation_state"]["coverage_percentage"] == 0.25,
    ),
    Case(
        DOC_FAMILY,
        "ensure_documentation_state",
        _doc("ensure_documentation_state"),
        lambda m: m["documentation_state"]["iteration_mode"] == "initial",
        seed={"mission_type": "documentation"},
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "record_baseline_merge_commit",
        _baseline("record_baseline_merge_commit", "abc123", mission_id=MISSION_ID, merged_commit="def456"),
        lambda m: m["baseline_merge_commit"] == "abc123",
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "_stamp_pr_merge_provenance",
        _baseline("_stamp_pr_merge_provenance", "fedcba", "attested"),
        lambda m: m["pr_merge_commit"] == "fedcba",
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "bake_onto_target_tree",
        _bake("_bake_mission_number_onto_target_tree", 7),
        lambda m: m["mission_number"] == 7,
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "bake_primary_tree",
        _bake("_bake_mission_number_on_primary_tree", "kitty/mission-x", 7, with_repo=True, with_slug=True),
        lambda m: m["mission_number"] == 7,
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "clear_landed_mission_branch",
        _teardown("_clear_landed_single_branch_mission_branch"),
        lambda m: "mission_branch" not in m,
        seed={"mission_branch": "kitty/mission-x"},
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "flatten_after_branch_delete",
        _teardown("_flatten_coordination_metadata_after_branch_delete"),
        lambda m: m.get("flattened") is True,
        seed={"coordination_branch": "kitty/mission-060-test-01COORD0", "mid8": "01COORD0", "mission_id": "01COORD0XXXXXXXXXXXXXXXXXX", "topology": "coord"},
    ),
    Case(
        MIGRATION_FAMILY,
        "backfill_mission",
        _migration("specify_cli.migration.backfill_identity", "backfill_mission"),
        lambda m: bool(m.get("mission_id")),
        seed={"drop_identity": True},
    ),
    Case(
        MIGRATION_FAMILY,
        "backfill_mission_mission_type",
        _migration("specify_cli.migration.backfill_mission_type", "backfill_mission_mission_type", repo=_Repo()),
        lambda m: m.get("mission_type") == "software-dev",
        seed={"mission": "software-dev"},
    ),
    Case(
        MIGRATION_FAMILY,
        "backfill_mission_topology",
        _migration("specify_cli.migration.backfill_topology", "backfill_mission_topology"),
        lambda m: "topology" in m,
    ),
    Case(
        MIGRATION_FAMILY,
        "restamp_single_branch",
        _restamp_single_branch,
        lambda m: m.get("topology") == "lanes",
        seed={"topology": "single_branch"},
    ),
    Case(MIGRATION_FAMILY, "flip_phase", _migration("specify_cli.migration.runtime_state_cutover", "_flip_phase"), lambda m: int(str(m.get("status_phase"))) >= 1),
    Case(MIGRATION_FAMILY, "write_feature_meta", _write_feature_meta, lambda m: m.get("baseline_marker") == "written"),
    Case(MIGRATION_FAMILY, "target_branch_migration", _apply_target_branch_migration, lambda m: "target_branch" in m, seed={"drop_target_branch": True}),
    Case(MIGRATION_FAMILY, "repair_meta_phase", _repair_meta_phase, lambda m: bool(m.get("mission_id")), seed={"drop_identity": True}),
    Case(
        DOC_FAMILY,
        "update_documentation_state",
        _doc_update_state,
        lambda m: m["documentation_state"]["coverage_percentage"] == 0.75,
        seed={"mission_type": "documentation", "documentation_state": _doc_state_full()},
    ),
    Case(
        CONSOLIDATION_FAMILY,
        "assign_planning_only_number",
        _assign_planning_only,
        lambda m: isinstance(m.get("mission_number"), int),
    ),
    Case(
        MIGRATION_FAMILY,
        "backfill_mission_ids",
        _backfill_mission_ids,
        lambda m: bool(m.get("mission_id")),
        seed={"drop_identity": True},
    ),
]


def _case_id(case: Case) -> str:
    return f"{case.family}-{case.name}"


def _families(family: str) -> list[Any]:
    return [pytest.param(case, id=_case_id(case)) for case in CASES if case.family == family]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    return root


def _seed_mission(repo: Path, case: Case) -> Path:
    feature_dir = repo / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)
    meta: dict[str, Any] = {
        "slug": SLUG,
        "mission_slug": SLUG,
        "friendly_name": "Test",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-13T00:00:00+00:00",
        "mission_id": MISSION_ID,
        "mission_number": None,
    }
    seed = dict(case.seed)
    if seed.pop("drop_target_branch", False):
        meta.pop("target_branch")
    if seed.pop("drop_identity", False):
        meta.pop("mission_id")
        meta.pop("slug")
    if "mission" in seed:
        meta.pop("mission_type")
    meta.update(seed)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if case.name == "restamp_single_branch":
        _write_code_lane_manifest(feature_dir)
    return feature_dir


def _write_code_lane_manifest(feature_dir: Path) -> None:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    manifest = LanesManifest(
        version=1,
        mission_slug=SLUG,
        mission_id=MISSION_ID,
        mission_branch="kitty/mission-x",
        target_branch="main",
        lanes=[ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=("src/**",), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        computed_at="2026-04-13T00:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)


def _read(feature_dir: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


def _assert_overlap_keeps_both(monkeypatch: pytest.MonkeyPatch, repo: Path, case: Case) -> None:
    feature_dir = _seed_mission(repo, case)

    def writer_b() -> None:
        locked_update_meta(feature_dir, lambda meta: meta.update({B_MARKER: B_VALUE}), repo_root=repo, validate=False)

    errors = run_overlap(monkeypatch, lambda: case.call(repo, feature_dir), writer_b)

    assert errors == []
    final = _read(feature_dir)
    assert final.get(B_MARKER) == B_VALUE, f"{case.name}: the locked writer's field was lost"
    assert case.check(final), f"{case.name}: the writer's own result is missing from {final}"


@pytest.mark.parametrize("case", _families(DOC_FAMILY))
def test_documentation_state_writer_overlap_keeps_both_writes(monkeypatch: pytest.MonkeyPatch, repo: Path, case: Case) -> None:
    _assert_overlap_keeps_both(monkeypatch, repo, case)


@pytest.mark.parametrize("case", _families(CONSOLIDATION_FAMILY))
def test_consolidation_writer_overlap_keeps_both_writes(monkeypatch: pytest.MonkeyPatch, repo: Path, case: Case) -> None:
    _assert_overlap_keeps_both(monkeypatch, repo, case)


@pytest.mark.parametrize("case", _families(MIGRATION_FAMILY))
def test_migration_writer_overlap_keeps_both_writes(monkeypatch: pytest.MonkeyPatch, repo: Path, case: Case) -> None:
    _assert_overlap_keeps_both(monkeypatch, repo, case)


@pytest.mark.parametrize("case", [pytest.param(case, id=_case_id(case)) for case in CASES])
def test_every_writer_takes_the_mission_lock(monkeypatch: pytest.MonkeyPatch, repo: Path, case: Case) -> None:
    feature_dir = _seed_mission(repo, case)
    expected_key = mission_lock_key(feature_dir)
    acquired: list[str] = []
    real_lock = mission_write.feature_status_lock

    def recording(root: Path, key: str, *, timeout: float) -> Any:
        acquired.append(key)
        return real_lock(root, key, timeout=timeout)

    monkeypatch.setattr(mission_write, "feature_status_lock", recording)

    case.call(repo, feature_dir)

    assert case.check(_read(feature_dir)), f"{case.name}: writer did not leave its result"
    assert expected_key in acquired, f"{case.name}: wrote meta.json without taking the Mission lock ({acquired})"


def _seed_legacy_coordination_mission(repo: Path) -> Path:
    """A coordination-routed Mission that records no mid8 and no mission_id (what ``backfill-identity`` heals)."""
    feature_dir = repo / "kitty-specs" / "legacy-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"slug": "legacy-mission", "coordination_branch": "kitty/x"}), encoding="utf-8")
    return feature_dir


def test_unresolvable_coordination_key_fails_closed_for_ordinary_writers(repo: Path) -> None:
    from specify_cli.lanes.branch_naming import MissionLockKeyUnresolved

    feature_dir = _seed_legacy_coordination_mission(repo)

    with pytest.raises(MissionLockKeyUnresolved):
        locked_update_meta(feature_dir, lambda meta: meta.update(probe=1))
    assert "probe" not in _read(feature_dir)


def test_migrations_heal_a_mission_whose_coordination_key_is_unresolvable(repo: Path) -> None:
    from specify_cli.migration.backfill_identity import backfill_mission

    feature_dir = _seed_legacy_coordination_mission(repo)

    result = backfill_mission(feature_dir)

    assert result.action == "wrote"
    assert _read(feature_dir)["mission_id"] == result.mission_id


def test_scratch_checkout_bake_locks_the_primary_key_and_releases_it_before_git(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """The scratch-checkout write takes the Mission's primary key, and no lock is held while git add/commit run."""
    from contextlib import contextmanager

    from specify_cli.consolidation.mission_number.bake import _write_mission_number_to_branch

    feature_dir = repo / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"slug": SLUG, "mission_slug": SLUG, "mission_number": None}), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    branch = "kitty/mission-x"
    _git(repo, "branch", branch)

    keys: list[str] = []
    depth = {"held": 0}
    held_during_git: list[list[str]] = []
    real_lock = mission_write.feature_status_lock
    real_run = subprocess.run

    @contextmanager
    def recording_lock(root: Path, key: str, *, timeout: float) -> Any:
        keys.append(key)
        with real_lock(root, key, timeout=timeout) as held:
            depth["held"] += 1
            try:
                yield held
            finally:
                depth["held"] -= 1

    def recording_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        if list(command[:2]) == ["git", "add"] or "commit" in list(command[:4]):
            held_during_git.append(list(command))
            assert depth["held"] == 0, f"Mission lock held while running {command}"
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(mission_write, "feature_status_lock", recording_lock)
    monkeypatch.setattr(subprocess, "run", recording_run)

    assert _write_mission_number_to_branch(repo, branch, SLUG, 7) is True

    assert keys == [SLUG]  # the Mission's primary key, once
    assert len(held_during_git) == 2  # git add and git commit both ran, outside the lock
