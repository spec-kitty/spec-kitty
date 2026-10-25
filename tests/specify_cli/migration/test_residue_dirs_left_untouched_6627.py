"""#6627: the shared seams the upgrade migrations call leave residue ``kitty-specs/`` dirs alone.

A residue directory holds only untracked leftovers (here ``decisions/index.json``
and its ``.lock`` after a branch switch): no ``spec.md`` or ``meta.json`` on disk,
and :func:`is_mission_dir` rejects it (:func:`is_kitty_specs_residue`). The shipped
migrations ``2.0.6_consistency_sweep``, ``3.2.0a4_normalize_mission_lifecycle`` and
``runtime_state_backfill`` enumerate every directory, so the guard lives in the
shared helpers they call; their own module files stay byte-identical. A real
Mission that was never committed must still be repaired.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.cli.commands._cutover_doctor import collect_cutover_audit
from specify_cli.context.mission_resolver import is_kitty_specs_residue
from specify_cli.migration.backfill_identity import backfill_mission
from specify_cli.migration.normalize_mission_lifecycle import RESIDUE_SKIP_WARNING, normalize_repo
from specify_cli.migration.runtime_state_cutover import cutover_mission, cutover_repo
from specify_cli.upgrade.feature_meta import build_baseline_feature_meta, write_feature_meta
from specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep import ConsistencySweepMigration
from specify_cli.upgrade.migrations.m_zz_runtime_state_backfill import RuntimeStateBackfillMigration

pytestmark = [pytest.mark.git_repo]

_RESIDUE = "rrule-repeat-editor-ui-01M5JYRC"
_LEFTOVERS = ["decisions/index.json", "decisions/index.json.lock"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".kittify").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _residue(repo: Path) -> Path:
    decisions = repo / "kitty-specs" / _RESIDUE / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "index.json").write_text("{}\n", encoding="utf-8")
    (decisions / "index.json.lock").write_text("", encoding="utf-8")
    return decisions.parent


def _files(path: Path) -> list[str]:
    return sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file())


def _tracked_legacy_mission(repo: Path, slug: str = "042-legacy") -> Path:
    mission = repo / "kitty-specs" / slug
    mission.mkdir(parents=True)
    (mission / "spec.md").write_text("# Legacy\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "legacy mission")
    return mission


def _untracked_legacy_mission(repo: Path, slug: str = "043-uncommitted") -> Path:
    """A real Mission that was never committed (e.g. kitty-specs/ was gitignored before 0.12.1)."""
    mission = repo / "kitty-specs" / slug
    mission.mkdir(parents=True)
    (mission / "spec.md").write_text("# Uncommitted\n", encoding="utf-8")
    return mission


def test_residue_rule(repo: Path) -> None:
    residue = _residue(repo)
    outside = repo / "elsewhere" / _RESIDUE
    outside.mkdir(parents=True)
    meta_only = repo / "kitty-specs" / "045-meta-only"
    meta_only.mkdir(parents=True)
    (meta_only / "meta.json").write_text(json.dumps({"mission_slug": meta_only.name}), encoding="utf-8")

    assert is_kitty_specs_residue(residue)
    assert not is_kitty_specs_residue(outside), "only kitty-specs/ children can be residue"
    assert not is_kitty_specs_residue(_tracked_legacy_mission(repo))
    assert not is_kitty_specs_residue(_untracked_legacy_mission(repo)), "an uncommitted spec.md is a Mission"
    assert not is_kitty_specs_residue(meta_only), "an uncommitted identity-less meta.json may be a legacy Mission"


def test_residue_rule_keeps_a_pre_identity_mission_with_only_tasks(repo: Path) -> None:
    mission = repo / "kitty-specs" / "001-tasks-only"
    (mission / "tasks").mkdir(parents=True)
    (mission / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    assert not is_kitty_specs_residue(mission)


def test_residue_rule_keeps_a_mission_whose_tracked_spec_is_deleted_in_the_worktree(repo: Path) -> None:
    mission = _tracked_legacy_mission(repo)
    (mission / "spec.md").unlink()

    assert not is_kitty_specs_residue(mission)


def test_residue_rule_degrades_to_the_existence_rule_without_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "plain"
    residue = project / "kitty-specs" / _RESIDUE / "decisions"
    residue.mkdir(parents=True)
    mission = project / "kitty-specs" / "044-plain"
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-git-here"))

    assert is_kitty_specs_residue(residue.parent)
    assert not is_kitty_specs_residue(mission)
    assert cutover_mission(residue.parent).residue


def test_baseline_meta_is_none_for_residue(repo: Path) -> None:
    assert build_baseline_feature_meta(_residue(repo), repo) is None


@pytest.mark.parametrize("make_mission", [_tracked_legacy_mission, _untracked_legacy_mission])
def test_baseline_meta_still_built_for_a_legacy_mission(repo: Path, make_mission: Callable[[Path], Path]) -> None:
    mission = make_mission(repo)

    meta = build_baseline_feature_meta(mission, repo)

    assert meta is not None
    assert meta["mission_slug"] == mission.name


def test_write_feature_meta_none_writes_nothing(repo: Path) -> None:
    residue = _residue(repo)

    write_feature_meta(residue, None)

    assert _files(residue) == _LEFTOVERS


def test_consistency_sweep_writes_no_baseline_into_residue(repo: Path) -> None:
    residue = _residue(repo)
    tracked = _tracked_legacy_mission(repo)
    untracked = _untracked_legacy_mission(repo)

    result = ConsistencySweepMigration().apply(repo)

    assert result.success, result.errors
    assert _files(residue) == _LEFTOVERS
    assert not any(_RESIDUE in change for change in result.changes_made)
    assert (tracked / "meta.json").is_file(), "a committed legacy Mission still gets its baseline meta.json"
    assert (untracked / "meta.json").is_file(), "an uncommitted legacy Mission still gets its baseline meta.json"


def test_normalize_repo_reports_residue_and_writes_nothing(repo: Path) -> None:
    residue = _residue(repo)

    results = normalize_repo(repo)

    assert [(r.slug, r.status, r.warnings) for r in results] == [(_RESIDUE, "skipped", [RESIDUE_SKIP_WARNING])]
    assert _files(residue) == _LEFTOVERS


def test_normalize_repo_still_processes_an_untracked_legacy_mission(repo: Path) -> None:
    mission = _untracked_legacy_mission(repo)
    (mission / "meta.json").write_text(json.dumps({"mission_slug": mission.name}), encoding="utf-8")

    results = normalize_repo(repo, dry_run=True)

    assert [r.slug for r in results] == [mission.name]
    assert RESIDUE_SKIP_WARNING not in results[0].warnings


def test_upgrade_chain_mints_no_identity_into_residue_but_does_for_an_uncommitted_mission(repo: Path) -> None:
    residue = _residue(repo)
    mission = _untracked_legacy_mission(repo)

    assert ConsistencySweepMigration().apply(repo).success
    normalize_repo(repo)

    assert _files(residue) == _LEFTOVERS
    assert json.loads((mission / "meta.json").read_text(encoding="utf-8"))["mission_id"]
    assert backfill_mission(mission).action == "skip", "normalize_repo already minted the uncommitted Mission's identity"


def test_cutover_mission_skips_residue(repo: Path) -> None:
    residue = _residue(repo)

    result = cutover_mission(residue)

    assert (result.residue, result.flipped, result.error) == (True, False, None)
    assert _files(residue) == _LEFTOVERS


def test_cutover_repo_reports_residue_without_writing(repo: Path) -> None:
    residue = _residue(repo)

    results = cutover_repo(repo)

    assert [(r.slug, r.residue, r.flipped) for r in results] == [(_RESIDUE, True, False)]
    assert _files(residue) == _LEFTOVERS


def test_runtime_state_backfill_migration_leaves_residue_alone(repo: Path) -> None:
    residue = _residue(repo)

    result = RuntimeStateBackfillMigration().apply(repo)

    assert result.success, result.errors
    assert _files(residue) == _LEFTOVERS


def test_cutover_doctor_reports_residue_as_nothing_to_cut_over(repo: Path) -> None:
    _residue(repo)

    [entry] = collect_cutover_audit(repo)

    assert (entry.slug, entry.cut_over) == (_RESIDUE, True)
    assert "residue" in entry.reason


def test_residue_rule_propagates_a_git_timeout(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only an unrunnable git degrades to the existence rule; a timeout is a real failure."""
    from kernel.git import GitCommandError
    from specify_cli.context import mission_resolver

    def timed_out(cwd: Path, *args: str, **_: object) -> None:
        raise GitCommandError(argv=args, cwd=cwd, returncode=-1, stderr="timeout", timed_out=True)

    residue = _residue(repo)
    monkeypatch.setattr(mission_resolver, "run_git", timed_out)

    with pytest.raises(GitCommandError):
        is_kitty_specs_residue(residue)
