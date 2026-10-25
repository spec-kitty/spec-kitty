"""The four residue-aware successor migrations (#6669, WP03).

``0.9.0_frontmatter_only_lanes``, ``0.9.1_complete_migration``,
``2.0.6_consistency_sweep`` and ``3.1.1_normalize_status_json`` are shipped,
byte-frozen migrations that rewrite every ``kitty-specs/`` child, including a
residue folder that is not a Mission. Each is listed in
``SUPERSEDED_MIGRATIONS`` and replaced by a successor that repairs the same
Missions and leaves residue untouched.

Every case goes through the registry or the runner. A shipped class is built
directly only as a parity oracle on a twin fixture.

- the registry registers the predecessor as a no-op and the successor, also
  after ``clear()`` plus ``auto_discover_migrations()`` (the rediscovery trap)
- repair parity with the predecessor, in the scenarios its own tests cover
- residue stays byte-identical in main ``kitty-specs/`` and in
  ``.worktrees/*/kitty-specs/``, and is named once by project-relative path
- a tasks-only pre-identity Mission is still repaired where git does not know
  it (no git, an ignored ``kitty-specs/``, an untracked nested project)
- a settled predecessor makes the successor inert (live run and dry run), also
  on ledger adoption and in a worktree with its own ledger
- the order manifest puts each successor right after its predecessor
"""

from __future__ import annotations

import ast
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.context.mission_resolver import residue_notice_path
from specify_cli.status.transitions import CANONICAL_LANES
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations import m_0_9_0_frontmatter_only_lanes as shipped_090
from specify_cli.upgrade.migrations import m_0_9_1_complete_lane_migration as shipped_091
from specify_cli.upgrade.migrations import m_2_0_6_consistency_sweep as shipped_206
from specify_cli.upgrade.migrations import m_3_1_1_normalize_status_json as shipped_311
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult, SupersededMigration
from specify_cli.upgrade.registry import MigrationRegistry, settled_in_selection_view
from specify_cli.upgrade.runner import MigrationRunner
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS, superseded_note

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

PRED_090 = "0.9.0_frontmatter_only_lanes"
PRED_091 = "0.9.1_complete_migration"
PRED_206 = "2.0.6_consistency_sweep"
PRED_311 = "3.1.1_normalize_status_json"
NEW_090 = "0.9.0_residue_safe_frontmatter_only_lanes"
NEW_091 = "0.9.1_residue_safe_complete_migration"
NEW_206 = "2.0.6_residue_safe_consistency_sweep"
NEW_311 = "3.1.1_residue_safe_normalize_status_json"
PAIRS = [(PRED_090, NEW_090), (PRED_091, NEW_091), (PRED_206, NEW_206), (PRED_311, NEW_311)]
PAIR_IDS = [new for _old, new in PAIRS]

TARGET = "4.0.0rc8"
WALL_CLOCK_TS = "2026-04-07T09:56:25.543799+00:00"
RESIDUE_SLUGS = ("res-tasks", "res-events", "res-status", "res-doing", "res-decisions")
LEGACY_WP = '---\nwork_package_id: "WP01"\ntitle: "WP01 x"\nlane: "doing"\n---\n# WP01\n'


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


@pytest.fixture
def quiet_runtime_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    """The global runtime-asset step of the 2.0.6 successor is not what these cases are about."""
    monkeypatch.setattr(
        "specify_cli.upgrade.migrations.m_2_0_6_residue_safe_consistency_sweep._migrate_runtime_assets",
        lambda *_args, **_kwargs: ([], []),
    )


def _get(migration_id: str) -> BaseMigration:
    migration = MigrationRegistry.get_by_id(migration_id)
    assert migration is not None, migration_id
    return migration


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")


def _commit_all(root: Path, message: str = "commit") -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _snapshot(root: Path) -> dict[str, bytes]:
    """Every file under *root* (relative POSIX path -> bytes), skipping git and the upgrade bookkeeping."""
    skipped = {".git", ".kittify"}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not skipped & set(path.relative_to(root).parts)
    }


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _stale_status(mission: Path) -> None:
    """A ``status.json`` carrying a wall-clock ``materialized_at`` (what 3.1.1 normalises)."""
    _write(mission / "status.json", json.dumps({"event_count": 0, "materialized_at": WALL_CLOCK_TS, "work_packages": {}}, indent=2) + "\n")


def _dirty_mission(project: Path, slug: str = "001-legacy") -> Path:
    """A tasks-only, pre-identity Mission that every one of the four predecessors would repair."""
    mission = project / "kitty-specs" / slug
    _write(mission / "tasks" / "doing" / "WP01-x.md", LEGACY_WP)
    _stale_status(mission)
    return mission


def _plain_project(tmp_path: Path) -> Path:
    project = tmp_path / "plain"
    (project / ".kittify").mkdir(parents=True)
    return project


def _plant_residue(specs: Path) -> list[Path]:
    """Five residue shapes: a tasks WP, an event log, a status.json, a ``tasks/doing`` WP and a decisions folder."""
    _write(specs / "res-tasks" / "tasks" / "WP01-x.md", LEGACY_WP)
    _write(specs / "res-events" / "status.events.jsonl", '{"not": "an event"}\n')
    _stale_status(specs / "res-status")
    _write(specs / "res-doing" / "tasks" / "doing" / "WP01-x.md", LEGACY_WP)
    _write(specs / "res-decisions" / "decisions" / "index.json", "{}\n")
    _write(specs / "res-decisions" / "decisions" / "index.json.lock", "")
    return [specs / slug for slug in RESIDUE_SLUGS]


def _tracked_project(tmp_path: Path, *, worktree: bool = False) -> Path:
    """A git project with one committed Mission (so git-aware mode applies), optionally with ``.worktrees/wt1``."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / ".kittify").mkdir()
    _write(root / "kitty-specs" / "real-mission" / "spec.md", "# real\n")
    _write(root / "kitty-specs" / "real-mission" / "meta.json", json.dumps({"mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "mission_slug": "real-mission"}))
    _commit_all(root, "init")
    if worktree:
        _git(root, "worktree", "add", "-q", "-b", "wt1-branch", str(root / ".worktrees" / "wt1"))
    return root


def _without_real_mission(snapshot: dict[str, bytes]) -> dict[str, bytes]:
    return {path: data for path, data in snapshot.items() if path.split("/")[0] != "real-mission"}


def _notice_paths(result: MigrationResult) -> list[str]:
    return sorted(path for path in (residue_notice_path(w) for w in result.warnings) if path)


def _expected_notices(prefix: str) -> list[str]:
    return sorted(f"{prefix}{slug}" for slug in RESIDUE_SLUGS)


# ---------------------------------------------------------------------------
# 1. Substitution and rediscovery
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_registry_registers_the_predecessor_as_a_no_op_and_the_successor(tmp_path: Path, old: str, new: str) -> None:
    project = _plain_project(tmp_path)
    _dirty_mission(project)

    predecessor = _get(old)
    successor = _get(new)

    assert isinstance(predecessor, SupersededMigration)
    assert predecessor.superseded_by == superseded_note(new)
    assert SUPERSEDED_MIGRATIONS[old] == new
    assert predecessor.detect(project) is False
    assert not isinstance(successor, SupersededMigration)
    assert successor.detect(project) is True, "the fixture must be one the successor repairs, or the cases below prove nothing"


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_successor_keeps_the_routing_attributes_of_its_predecessor(old: str, new: str) -> None:
    predecessor, successor = _get(old), _get(new)

    for attribute in ("target_version", "runs_on_worktrees", "requires_git_repository", "clone_local_effect", "runs_first"):
        assert getattr(successor, attribute) == getattr(predecessor, attribute), attribute
    assert successor.migration_id == new


def test_successors_are_rediscovered_after_clear() -> None:
    """A name import of a shipped class would hide a successor from ``auto_discover_migrations`` after ``clear()``."""
    MigrationRegistry.clear()
    assert all(MigrationRegistry.get_by_id(new) is None for _old, new in PAIRS)

    auto_discover_migrations()

    for old, new in PAIRS:
        assert MigrationRegistry.get_by_id(new) is not None, new
        assert isinstance(MigrationRegistry.get_by_id(old), SupersededMigration), old


def test_the_subclass_successors_derive_from_the_shipped_classes() -> None:
    assert isinstance(_get(NEW_090), shipped_090.FrontmatterOnlyLanesMigration)
    assert isinstance(_get(NEW_091), shipped_091.CompleteLaneMigration)
    assert not isinstance(_get(NEW_206), shipped_206.ConsistencySweepMigration)
    assert not isinstance(_get(NEW_311), shipped_311.NormalizeStatusJsonMigration)


# ---------------------------------------------------------------------------
# 2. Repair parity
# ---------------------------------------------------------------------------


def _lane_mission(project: Path, *, system_files: tuple[str, ...] = (), extra: bool = False) -> None:
    mission = project / "kitty-specs" / "001-test-feature"
    for lane, wp in (("planned", "WP01"), ("doing", "WP02"), ("for_review", "WP03"), ("done", "WP04")):
        _write(mission / "tasks" / lane / f"{wp}.md", f'---\nwork_package_id: "{wp}"\ntitle: "Test {wp}"\n---\n\n# {wp}\n')
        for name in system_files:
            _write(mission / "tasks" / lane / name, "x")
    if extra:
        _write(mission / "tasks" / "doing" / "notes.txt", "keep me")
        _write(mission / "tasks" / "done" / "phase-1.md", "---\nlane: 'done'\ntitle: p\n---\nbody\n")
        _write(mission / "spec.md", "# not a task file\n")


def _worktree_assets(project: Path) -> None:
    _write(project / ".worktrees" / "001-lane-a" / ".claude" / "commands" / "spec-kitty.tasks.md", "legacy")
    _write(project / ".worktrees" / "001-lane-a" / ".kittify" / "scripts" / "task.sh", "#!/bin/sh\n")
    _write(project / ".worktrees" / "001-lane-a" / "kitty-specs" / "002-wt-feature" / "tasks" / "doing" / "WP01-x.md", LEGACY_WP)


def _empty_lane_dirs(project: Path) -> None:
    for lane in ("planned", "doing", "for_review", "done"):
        (project / "kitty-specs" / "001-test-feature" / "tasks" / lane).mkdir(parents=True)


def _lane_mission_with_worktree_assets(project: Path) -> None:
    _lane_mission(project)
    _worktree_assets(project)


_LANE_SCENARIOS: dict[str, Callable[[Path], None]] = {
    "plain": lambda project: _lane_mission(project),
    "ds_store": lambda project: _lane_mission(project, system_files=(".DS_Store",)),
    "gitkeep": lambda project: _lane_mission(project, system_files=(".gitkeep",)),
    "extra_files": lambda project: _lane_mission(project, extra=True),
    "empty_lane_dirs": _empty_lane_dirs,
    "worktree_assets": _lane_mission_with_worktree_assets,
}


@pytest.mark.parametrize("scenario", list(_LANE_SCENARIOS))
@pytest.mark.parametrize(
    ("shipped_module", "shipped_name", "new", "dry_run"),
    [
        (shipped_090, "FrontmatterOnlyLanesMigration", NEW_090, False),
        (shipped_090, "FrontmatterOnlyLanesMigration", NEW_090, True),
        (shipped_091, "CompleteLaneMigration", NEW_091, False),
        (shipped_091, "CompleteLaneMigration", NEW_091, True),
    ],
    ids=["0.9.0", "0.9.0-dry", "0.9.1", "0.9.1-dry"],
)
def test_lane_successors_repair_exactly_what_the_shipped_class_repairs(
    tmp_path: Path, scenario: str, shipped_module: object, shipped_name: str, new: str, dry_run: bool
) -> None:
    """Parity oracle: the shipped class on a twin fixture (built directly, never via the registry)."""
    twin_a, twin_b = _plain_project(tmp_path / "a"), _plain_project(tmp_path / "b")
    _LANE_SCENARIOS[scenario](twin_a)
    _LANE_SCENARIOS[scenario](twin_b)
    shipped: BaseMigration = getattr(shipped_module, shipped_name)()
    successor = _get(new)

    assert successor.detect(twin_a) == shipped.detect(twin_b)
    oracle = shipped.apply(twin_b, dry_run=dry_run)
    result = successor.apply(twin_a, dry_run=dry_run)

    assert (result.success, result.changes_made, result.errors, result.warnings) == (oracle.success, oracle.changes_made, oracle.errors, oracle.warnings)
    assert _snapshot(twin_a) == _snapshot(twin_b)
    assert _tree_names(twin_a) == _tree_names(twin_b)


def _tree_names(root: Path) -> list[str]:
    """Directory names too (an empty lane folder is part of the shape)."""
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if ".kittify" not in path.relative_to(root).parts)


def test_091_normalises_frontmatter_through_the_registry(tmp_path: Path) -> None:
    project = _plain_project(tmp_path)
    wp = _write(project / "kitty-specs" / "001-test-feature" / "tasks" / "WP01.md", '---\nwork_package_id: "WP01"\nlane: "for_review"\ntitle: "T"\n---\n# body\n')
    successor = _get(NEW_091)

    dry = successor.apply(project, dry_run=True)
    assert any(change.startswith("Would normalize: ") for change in dry.changes_made)
    assert 'lane: "for_review"' in wp.read_text(encoding="utf-8")

    live = successor.apply(project, dry_run=False)
    assert live.success, live.errors
    assert any(change.startswith("Normalized: ") for change in live.changes_made)
    assert 'lane: "for_review"' not in wp.read_text(encoding="utf-8")


def test_the_lane_successors_override_every_method_of_the_shipped_class_that_walks_kitty_specs() -> None:
    """A walker that the successor neither overrides nor reaches through an overridden predicate would still rewrite residue."""
    for shipped_module, class_name, new in ((shipped_090, "FrontmatterOnlyLanesMigration", NEW_090), (shipped_091, "CompleteLaneMigration", NEW_091)):
        tree = ast.parse(Path(str(shipped_module.__file__)).read_text(encoding="utf-8"))
        shipped_class = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name)
        methods = {node.name: node for node in shipped_class.body if isinstance(node, ast.FunctionDef)}
        walkers = [name for name, node in methods.items() if _mentions_kitty_specs(node)]
        assert len(walkers) >= 2, f"{class_name}: the AST scan found no walker"
        overridden = {name for name in methods if name in vars(type(_get(new)))}
        for name in walkers:
            reached = {call.func.attr for call in ast.walk(methods[name]) if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)}
            assert name in overridden or reached & overridden, (
                f"{class_name}.{name} walks kitty-specs but is neither overridden nor reached through an overridden method"
            )


def _mentions_kitty_specs(node: ast.AST) -> bool:
    return any(isinstance(item, ast.Constant) and item.value == "kitty-specs" for item in ast.walk(node))


def _full_meta(slug: str) -> str:
    return (
        json.dumps(
            {
                "feature_number": "001",
                "slug": slug,
                "mission_slug": slug,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n"
    )


def test_206_flags_malformed_meta_as_repairable(tmp_path: Path) -> None:
    _write(tmp_path / "repo" / "kitty-specs" / "001-broken-meta" / "meta.json", "{not-json")
    assert _get(NEW_206).detect(tmp_path / "repo") is True


def test_206_flags_incomplete_meta_as_repairable(tmp_path: Path) -> None:
    _write(
        tmp_path / "repo" / "kitty-specs" / "001-incomplete-meta" / "meta.json",
        json.dumps({"feature_number": "001", "slug": "001-incomplete-meta", "target_branch": "main", "created_at": "2026-01-01T00:00:00+00:00"}) + "\n",
    )
    assert _get(NEW_206).detect(tmp_path / "repo") is True


def test_206_apply_repairs_feature_state_and_legacy_prompt_refs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet_runtime_assets: None) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "001-upgrade-sweep"
    wp = _write(feature_dir / "tasks" / "WP01-upgrade.md", LEGACY_WP)
    _write(feature_dir / "tasks.md", "# Tasks\n\n**Prompt**: `.claude/prompts/tasks/doing/WP01-upgrade.md`\n")
    _write(
        feature_dir / "status.json",
        json.dumps({"mission_slug": "", "event_count": 0, "work_packages": {}, "summary": dict.fromkeys(CANONICAL_LANES, 0)}, indent=2) + "\n",
    )
    monkeypatch.setattr("specify_cli.upgrade.feature_meta.resolve_primary_branch", lambda _repo_root: "2.x")

    result = _get(NEW_206).apply(repo_root, dry_run=False)

    assert result.success is True
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert (meta["target_branch"], meta["mission_type"]) == ("2.x", "software-dev")
    assert 'lane: "doing"' not in wp.read_text(encoding="utf-8")
    assert "lane: in_progress" in wp.read_text(encoding="utf-8")
    assert ".claude/prompts/tasks/WP01-upgrade.md" in (feature_dir / "tasks.md").read_text(encoding="utf-8")
    assert not (feature_dir / "status.events.jsonl").exists()
    assert len(sorted(feature_dir.glob("status.json.orphan.bak.*"))) == 1


def test_206_apply_quarantines_an_unreadable_event_log(tmp_path: Path, quiet_runtime_assets: None) -> None:
    feature_dir = tmp_path / "repo" / "kitty-specs" / "001-corrupt-events"
    _write(feature_dir / "tasks" / "WP01-upgrade.md", LEGACY_WP.replace('"doing"', '"planned"'))
    _write(feature_dir / "meta.json", _full_meta("001-corrupt-events"))
    _write(feature_dir / "status.events.jsonl", "{bad json\n")

    result = _get(NEW_206).apply(tmp_path / "repo", dry_run=False)

    assert result.success is True
    assert not (feature_dir / "status.events.jsonl").exists()
    assert len(list(feature_dir.glob("status.events.jsonl.unreadable.bak.*"))) == 1
    assert any("archived unreadable status.events.jsonl" in change for change in result.changes_made)
    status = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
    assert (status["work_packages"], status["event_count"]) == ({}, 0)


def test_206_apply_cleans_legacy_worktree_assets(tmp_path: Path, quiet_runtime_assets: None) -> None:
    repo_root = tmp_path / "repo"
    worktree = repo_root / ".worktrees" / "001-feature-lane-a"
    _write(worktree / ".claude" / "commands" / "spec-kitty.tasks.md", "legacy")
    _write(worktree / ".kittify" / "scripts" / "task.sh", "#!/bin/sh\n")

    result = _get(NEW_206).apply(repo_root, dry_run=False)

    assert result.success is True
    assert not (worktree / ".claude" / "commands").exists()
    assert not (worktree / ".kittify" / "scripts").exists()
    assert any("cleaned 1 worktree" in change for change in result.changes_made)


@pytest.mark.parametrize("twin", [True, False], ids=["conflict", "no-conflict"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_206_runtime_asset_conflicts_surface_as_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, twin: bool, dry_run: bool) -> None:
    """#5450: a legacy file that cannot move onto its override is a warning, not silence."""
    global_home = tmp_path / "global"
    (global_home / "missions").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))
    project = tmp_path / "project"
    _write(project / ".kittify" / "missions" / "erp" / "mission.yaml", "LEGACY v1")
    override = project / ".kittify" / "overrides" / "missions" / "erp" / "mission.yaml"
    if twin:
        _write(override, "OVERRIDE v2")

    result = _get(NEW_206).apply(project, dry_run=dry_run)

    if twin:
        assert len(result.warnings) == 1
        assert "1 customized legacy runtime asset(s) not moved" in result.warnings[0]
        assert "a non-folder blocks the overrides path" in result.warnings[0]
        assert "spec-kitty migrate --dry-run --verbose" in result.warnings[0]
        assert override.read_text(encoding="utf-8") == "OVERRIDE v2"
    else:
        assert result.warnings == []


def test_206_an_already_consistent_project_says_so(tmp_path: Path, quiet_runtime_assets: None) -> None:
    result = _get(NEW_206).apply(_plain_project(tmp_path), dry_run=False)

    assert result.success is True
    assert result.changes_made == ["Project already consistent for 2.0.6"]


def _status_json(mission: Path, materialized_at: str) -> Path:
    stale = materialized_at != ""
    payload = {
        "event_count": 0,
        "last_event_id": None,
        "materialized_at": materialized_at,
        "mission_number": mission.name.split("-", 1)[0],
        "mission_slug": "",
        "mission_type": "software-dev",
        "summary": dict.fromkeys(("approved", "blocked", "canceled", "claimed", "done", "for_review", "in_progress", "in_review", "planned"), 0),
        "work_packages": {},
    }
    path = _write(mission / "status.json", json.dumps(payload, sort_keys=True, indent=2) + "\n")
    assert stale or path.exists()
    return path


class TestNormalizeStatusJsonSuccessor:
    """Ported from ``tests/upgrade/migrations/test_normalize_status_json.py``, through the registry."""

    def test_detect_is_false_without_kitty_specs_or_status_json(self, tmp_path: Path) -> None:
        migration = _get(NEW_311)
        assert migration.detect(tmp_path) is False
        (tmp_path / "kitty-specs" / "001-feature").mkdir(parents=True)
        assert migration.detect(tmp_path) is False

    def test_detect_ignores_a_normalised_file_and_flags_a_stale_one(self, tmp_path: Path) -> None:
        migration = _get(NEW_311)
        specs = tmp_path / "kitty-specs"
        _status_json(specs / "001-feature", "")
        assert migration.detect(tmp_path) is False
        _status_json(specs / "002-feature", WALL_CLOCK_TS)
        _status_json(specs / "003-feature", "")
        assert migration.detect(tmp_path) is True

    def test_can_apply(self, tmp_path: Path) -> None:
        migration = _get(NEW_311)
        ok, reason = migration.can_apply(tmp_path)
        assert (ok, bool(reason)) == (False, True)
        (tmp_path / ".kittify").mkdir()
        assert migration.can_apply(tmp_path)[0] is True

    def test_apply_normalises_a_stale_file(self, tmp_path: Path) -> None:
        status = _status_json(tmp_path / "kitty-specs" / "001-feature", WALL_CLOCK_TS)

        result = _get(NEW_311).apply(tmp_path, dry_run=False)

        assert result.success is True
        assert len(result.changes_made) == 1
        assert "001-feature" in result.changes_made[0]
        assert json.loads(status.read_text(encoding="utf-8"))["materialized_at"] == ""

    def test_apply_writes_the_bytes_the_shipped_writer_writes(self, tmp_path: Path) -> None:
        """Parity oracle on a twin: same file bytes as the frozen 3.1.1 migration."""
        status_a = _status_json(tmp_path / "a" / "kitty-specs" / "001-feature", WALL_CLOCK_TS)
        status_b = _status_json(tmp_path / "b" / "kitty-specs" / "001-feature", WALL_CLOCK_TS)

        _get(NEW_311).apply(tmp_path / "a", dry_run=False)
        shipped_311.NormalizeStatusJsonMigration().apply(tmp_path / "b", dry_run=False)

        assert status_a.read_bytes() == status_b.read_bytes()

    def test_apply_skips_an_already_normalised_file_and_a_folder_without_status_json(self, tmp_path: Path) -> None:
        specs = tmp_path / "kitty-specs"
        _status_json(specs / "001-feature", "")
        (specs / "002-feature").mkdir()

        result = _get(NEW_311).apply(tmp_path, dry_run=False)

        assert (result.success, result.changes_made) == (True, [])

    def test_dry_run_reports_but_does_not_write(self, tmp_path: Path) -> None:
        status = _status_json(tmp_path / "kitty-specs" / "001-feature", WALL_CLOCK_TS)
        before = status.read_bytes()

        result = _get(NEW_311).apply(tmp_path, dry_run=True)

        assert result.success is True
        assert "001-feature" in result.changes_made[0]
        assert "would" in result.changes_made[0]
        assert status.read_bytes() == before

    def test_apply_is_idempotent(self, tmp_path: Path) -> None:
        _status_json(tmp_path / "kitty-specs" / "001-feature", WALL_CLOCK_TS)
        migration = _get(NEW_311)
        migration.apply(tmp_path, dry_run=False)

        again = migration.apply(tmp_path, dry_run=False)

        assert (again.success, again.changes_made) == (True, [])

    def test_apply_with_mixed_missions_names_only_the_stale_ones(self, tmp_path: Path) -> None:
        specs = tmp_path / "kitty-specs"
        _status_json(specs / "001-stale", WALL_CLOCK_TS)
        _status_json(specs / "002-clean", "")
        _status_json(specs / "003-stale", WALL_CLOCK_TS)

        result = _get(NEW_311).apply(tmp_path, dry_run=False)

        assert result.success is True
        names = " ".join(result.changes_made)
        assert len(result.changes_made) == 2
        assert "001-stale" in names and "003-stale" in names
        assert "002-clean" not in names

    def test_an_unreadable_status_json_is_a_reported_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _status_json(tmp_path / "kitty-specs" / "001-feature", WALL_CLOCK_TS)

        def boom(_mission_dir: Path) -> bool:
            raise ValueError("unreadable")

        monkeypatch.setattr("specify_cli.upgrade.migrations.m_3_1_1_residue_safe_normalize_status_json._needs_normalisation", boom)

        result = _get(NEW_311).apply(tmp_path, dry_run=False)

        assert result.success is False
        assert result.errors == ["001-feature: unreadable"]


# ---------------------------------------------------------------------------
# 3. Residue stays untouched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_the_shipped_class_would_rewrite_residue_so_the_cases_below_have_teeth(tmp_path: Path, old: str, new: str) -> None:
    """Oracle: run the frozen class directly on a twin. If it left residue alone these cases would prove nothing."""
    repo = _tracked_project(tmp_path)
    residue = _plant_residue(repo / "kitty-specs")
    before = _snapshot(repo / "kitty-specs")
    shipped_class = {
        PRED_090: shipped_090.FrontmatterOnlyLanesMigration,
        PRED_091: shipped_091.CompleteLaneMigration,
        PRED_206: shipped_206.ConsistencySweepMigration,
        PRED_311: shipped_311.NormalizeStatusJsonMigration,
    }[old]
    assert residue

    shipped_class().apply(repo)

    assert _snapshot(repo / "kitty-specs") != before


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_residue_is_left_byte_identical_in_the_checkout_and_named_once(tmp_path: Path, quiet_runtime_assets: None, old: str, new: str) -> None:
    repo = _tracked_project(tmp_path, worktree=True)
    wt = repo / ".worktrees" / "wt1"
    _plant_residue(repo / "kitty-specs")
    _plant_residue(wt / "kitty-specs")
    main_before, wt_before = _snapshot(repo / "kitty-specs"), _snapshot(wt / "kitty-specs")

    result = _get(new).apply(repo)

    assert result.success, result.errors
    assert _snapshot(wt / "kitty-specs") == wt_before
    main_after = _snapshot(repo / "kitty-specs")
    assert {path: data for path, data in main_after.items() if path.split("/")[0] != "real-mission"} == {
        path: data for path, data in main_before.items() if path.split("/")[0] != "real-mission"
    }
    expected = _expected_notices("kitty-specs/")
    if new in (NEW_090, NEW_091):
        expected = sorted(expected + _expected_notices(".worktrees/wt1/kitty-specs/"))
    assert _notice_paths(result) == expected
    assert len(_notice_paths(result)) == len(set(_notice_paths(result))), "each residue folder is named once"


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_residue_is_left_byte_identical_when_the_successor_runs_inside_the_worktree(tmp_path: Path, quiet_runtime_assets: None, old: str, new: str) -> None:
    repo = _tracked_project(tmp_path, worktree=True)
    wt = repo / ".worktrees" / "wt1"
    _plant_residue(wt / "kitty-specs")
    before = _snapshot(wt / "kitty-specs")

    result = _get(new).apply(wt)

    assert result.success, result.errors
    assert _without_real_mission(_snapshot(wt / "kitty-specs")) == _without_real_mission(before)
    assert _notice_paths(result) == _expected_notices("kitty-specs/")


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_residue_alone_never_makes_detect_true(tmp_path: Path, old: str, new: str) -> None:
    repo = _tracked_project(tmp_path)
    migration = _get(new)
    without_residue = migration.detect(repo)
    _plant_residue(repo / "kitty-specs")

    assert migration.detect(repo) is without_residue


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_a_mission_beside_residue_is_still_repaired(tmp_path: Path, quiet_runtime_assets: None, old: str, new: str) -> None:
    repo = _tracked_project(tmp_path)
    mission = _dirty_mission(repo, "001-legacy")
    _write(mission / "meta.json", json.dumps({"mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAW", "mission_slug": "001-legacy"}))
    _plant_residue(repo / "kitty-specs")
    migration = _get(new)

    assert migration.detect(repo) is True
    result = migration.apply(repo)

    assert result.success, result.errors
    assert result.changes_made, "the Mission beside the residue is repaired"
    assert not any(slug in change for change in result.changes_made for slug in RESIDUE_SLUGS)


# ---------------------------------------------------------------------------
# 4. Fallback-mode repair (git does not know the Mission)
# ---------------------------------------------------------------------------


def _no_git(tmp_path: Path) -> Path:
    return _plain_project(tmp_path)


def _ignored_kitty_specs(tmp_path: Path) -> Path:
    project = tmp_path / "ignored"
    _init_repo(project)
    (project / ".kittify").mkdir()
    _write(project / ".gitignore", "kitty-specs/\n")
    _commit_all(project, "ignore kitty-specs")
    return project


def _nested_untracked(tmp_path: Path) -> Path:
    parent = tmp_path / "parent"
    _init_repo(parent)
    _write(parent / "kitty-specs" / "parent-mission" / "spec.md", "# parent\n")
    _commit_all(parent, "parent mission")
    project = parent / "sub" / "proj"
    (project / ".kittify").mkdir(parents=True)
    return project


_FALLBACK_PROJECTS = {"no-git": _no_git, "ignored-kitty-specs": _ignored_kitty_specs, "nested-untracked": _nested_untracked}


@pytest.mark.parametrize("make_project", list(_FALLBACK_PROJECTS.values()), ids=list(_FALLBACK_PROJECTS))
def test_206_repairs_a_tasks_only_pre_identity_mission(
    tmp_path: Path, make_project: Callable[[Path], Path], monkeypatch: pytest.MonkeyPatch, quiet_runtime_assets: None
) -> None:
    monkeypatch.setattr("specify_cli.upgrade.feature_meta.resolve_primary_branch", lambda _repo_root: "main")
    project = make_project(tmp_path)
    mission = project / "kitty-specs" / "001-legacy"
    wp = _write(mission / "tasks" / "WP01-x.md", LEGACY_WP)

    successor = _get(NEW_206)
    assert successor.detect(project) is True
    result = successor.apply(project)

    assert result.success, result.errors
    assert not any("is not a Mission" in warning for warning in result.warnings)
    assert (mission / "meta.json").is_file()
    assert "lane: in_progress" in wp.read_text(encoding="utf-8")


@pytest.mark.parametrize("new", [NEW_090, NEW_091], ids=["0.9.0", "0.9.1"])
@pytest.mark.parametrize("make_project", list(_FALLBACK_PROJECTS.values()), ids=list(_FALLBACK_PROJECTS))
def test_lane_successors_repair_a_tasks_only_pre_identity_mission(tmp_path: Path, make_project: Callable[[Path], Path], new: str) -> None:
    project = make_project(tmp_path)
    tasks = project / "kitty-specs" / "001-legacy" / "tasks"
    _write(tasks / "doing" / "WP01-x.md", LEGACY_WP)

    successor = _get(new)
    assert successor.detect(project) is True
    result = successor.apply(project)

    assert result.success, result.errors
    assert (tasks / "WP01-x.md").is_file()
    assert not (tasks / "doing").exists()
    assert _notice_paths(result) == []


@pytest.mark.parametrize("make_project", list(_FALLBACK_PROJECTS.values()), ids=list(_FALLBACK_PROJECTS))
def test_311_normalises_a_status_only_mission_in_every_fallback_project(tmp_path: Path, make_project: Callable[[Path], Path]) -> None:
    project = make_project(tmp_path)
    status = _status_json(project / "kitty-specs" / "001-legacy", WALL_CLOCK_TS)

    result = _get(NEW_311).apply(project)

    assert result.success, result.errors
    assert json.loads(status.read_text(encoding="utf-8"))["materialized_at"] == ""


# ---------------------------------------------------------------------------
# 5-9. Settled gate, dry-run parity, worktree ledger, superseded record, C-006
# ---------------------------------------------------------------------------


_PRE_LEDGER_METADATA = """spec_kitty:
  version: {version}
  initialized_at: '2026-01-01T00:00:00+00:00'
  last_upgraded_at: null
environment:
  python_version: ''
  platform: ''
  platform_version: ''
migrations:
  applied:
{applied}"""


def _pre_ledger(project: Path, version: str, applied: dict[str, str]) -> None:
    rows = "".join(f"  - id: {mid}\n    applied_at: '2026-01-01T00:00:00+00:00'\n    result: {result}\n" for mid, result in applied.items())
    _write(
        project / ".kittify" / "metadata.yaml",
        _PRE_LEDGER_METADATA.format(version=version, applied=rows or "  []\n").replace("  applied:\n  []\n", "  applied: []\n"),
    )


def _ledger_era(project: Path, *, unrecorded: set[str], skipped: frozenset[str] = frozenset()) -> None:
    """Stamp *project* at TARGET and record every registered migration as settled except *unrecorded*."""
    ProjectMetadata(version=TARGET, initialized_at=now_utc()).save(project / ".kittify")
    ledger = MigrationLedger(project)
    for migration in MigrationRegistry.get_all():
        if migration.migration_id in unrecorded:
            continue
        ledger.append(build_record(migration, "skipped" if migration.migration_id in skipped else "success"))


def _record(project: Path, migration_id: str, result: str) -> None:
    MigrationLedger(project).append(build_record(_get(migration_id), result))


def _selected(project: Path, from_version: str = "0.0.0", to_version: str = "99.0.0") -> set[str]:
    return {m.migration_id for m in MigrationRegistry.get_applicable(from_version, to_version, project_path=project)}


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_a_settled_predecessor_makes_the_successor_inert(tmp_path: Path, old: str, new: str) -> None:
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    successor = _get(new)
    assert successor.detect(project) is True

    _record(project, old, "success")

    assert settled_in_selection_view(project, old) is True
    assert successor.detect(project) is False


@pytest.mark.parametrize("dry_run", [False, True], ids=["live", "dry-run"])
@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_the_runner_does_nothing_for_a_successor_whose_predecessor_is_settled(
    tmp_path: Path, quiet_runtime_assets: None, old: str, new: str, dry_run: bool
) -> None:
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _ledger_era(project, unrecorded={new})
    before = _snapshot(project / "kitty-specs")

    result = MigrationRunner(project).upgrade(TARGET, dry_run=dry_run, include_worktrees=False)

    assert result.success, result.errors
    assert new in result.migrations_skipped
    assert new not in result.migrations_applied
    assert result.migration_results[new].changes_made == []
    assert _snapshot(project / "kitty-specs") == before


@pytest.mark.parametrize("dry_run", [False, True], ids=["live", "dry-run"])
@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_adoption_settles_the_predecessor_and_the_successor_stays_inert_in_dry_run_and_live(
    tmp_path: Path, quiet_runtime_assets: None, old: str, new: str, dry_run: bool
) -> None:
    """A pre-ledger project stamped at exactly the predecessor's version, with the predecessor in ``applied``.

    The version is the predecessor's own, so adoption does not settle the successor
    itself (that needs a version above it): the successor is selected, and its
    ``detect()`` must read the predecessor as settled in both runs.
    """
    version = _get(new).target_version
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _pre_ledger(project, version, {old: "success"})

    assert new in _selected(project, version, version)
    assert settled_in_selection_view(project, old) is True
    assert _get(new).detect(project) is False

    before = _snapshot(project / "kitty-specs")
    result = MigrationRunner(project).upgrade(version, dry_run=dry_run, include_worktrees=False)

    assert result.success, result.errors
    assert new not in result.migrations_applied
    assert result.migration_results[new].changes_made == []
    assert _snapshot(project / "kitty-specs") == before


def test_a_worktree_with_its_own_ledger_that_records_the_predecessor_is_left_alone(tmp_path: Path) -> None:
    """The main checkout's own pass also walks ``.worktrees/*``; the worktree pass reads the worktree's ledger."""
    repo = _tracked_project(tmp_path, worktree=True)
    wt = repo / ".worktrees" / "wt1"
    (wt / ".kittify").mkdir(exist_ok=True)
    _dirty_mission(wt, "001-legacy")
    _write(wt / "kitty-specs" / "001-legacy" / "meta.json", json.dumps({"mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAX", "mission_slug": "001-legacy"}))
    successor = _get(NEW_090)
    assert successor.detect(wt) is True
    ProjectMetadata(version=TARGET, initialized_at=now_utc()).save(wt / ".kittify")
    _record(wt, PRED_090, "success")
    before = _snapshot(wt / "kitty-specs")

    result = MigrationRunner(repo)._upgrade_worktrees(TARGET, [successor], False)  # the worktree pass of `upgrade`

    assert result["errors"] == []
    assert _snapshot(wt / "kitty-specs") == before


def test_when_the_successor_applies_the_runner_records_the_predecessor_as_skipped(tmp_path: Path, quiet_runtime_assets: None) -> None:
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _ledger_era(project, unrecorded={PRED_090, NEW_090})

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)

    assert result.success, result.errors
    assert NEW_090 in result.migrations_applied
    assert PRED_090 in result.migrations_skipped
    records = {record.id: record.result for record in MigrationLedger(project).applicable_records_for(_get(PRED_090))}
    assert records[PRED_090] == "skipped"
    predecessor = _get(PRED_090)
    assert isinstance(predecessor, SupersededMigration)
    assert predecessor.superseded_by == superseded_note(NEW_090)
    assert {record.id: record.result for record in MigrationLedger(project).applicable_records_for(_get(NEW_090))}[NEW_090] == "success"


def test_c006_a_failed_predecessor_at_a_higher_version_is_settled_by_adoption(tmp_path: Path) -> None:
    """C-006, an accepted residual: ledger adoption settles every migration below the recorded version.

    A pre-ledger project stamped above 2.0.6 whose metadata records the predecessor as ``failed`` has
    its successor settled by adoption, so the repair the predecessor never finished is not retried by
    the successor. Pinned as the current behaviour, not as a goal.
    """
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _pre_ledger(project, "3.0.0", {PRED_206: "failed"})

    assert NEW_206 not in _selected(project, "3.0.0", "3.0.0")
    assert settled_in_selection_view(project, NEW_206) is True


# ---------------------------------------------------------------------------
# 10. Order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_each_successor_sits_right_after_its_predecessor_in_the_order_manifest(old: str, new: str) -> None:
    manifest = load_order_manifest()

    assert manifest.index(new) == manifest.index(old) + 1
    assert new not in SUPERSEDED_MIGRATIONS
