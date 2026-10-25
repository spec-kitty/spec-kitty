"""WP04 (FR-008, #6669): a residue folder is named at most once per upgrade run.

Collapse happens at the runner's warning-collection points
(``_append_warnings`` for the main checkout and the worktree loop, sharing one
seen-set); there is no rendering-side filter, so ``--json`` shows the same list.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any, ClassVar

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.context.mission_resolver import residue_notice
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner, _append_warnings

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FROM_VERSION = "3.2.0"
_TARGET_VERSION = "3.2.1"
_WT_BRANCH_PREFIX = "wip/"  # a non-integrating worktree: upgrade still writes it (#5457)

_cli_app = typer.Typer(add_completion=False)
_cli_app.command()(upgrade)

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)


# --------------------------------------------------------------------------
# Pure helper
# --------------------------------------------------------------------------


def test_identical_residue_notices_collapse_to_one(tmp_path: Path) -> None:
    notice = residue_notice("kitty-specs/x")
    target: list[str] = []
    _append_warnings(target, [notice, f"slug: {notice}", notice], checkout_root=tmp_path, seen=set())
    assert target == [notice]


def test_different_folders_keep_one_line_each(tmp_path: Path) -> None:
    first, second = residue_notice("kitty-specs/x"), residue_notice("kitty-specs/y")
    target: list[str] = []
    _append_warnings(target, [first, second, first], checkout_root=tmp_path, seen=set())
    assert target == [first, second]


def test_non_residue_warnings_pass_through_unchanged_and_in_order(tmp_path: Path) -> None:
    notice = residue_notice("kitty-specs/x")
    lines = ["plain", notice, "plain", "other", notice, "plain"]
    target: list[str] = ["existing"]
    _append_warnings(target, lines, checkout_root=tmp_path, seen=set())
    assert target == ["existing", "plain", notice, "plain", "other", "plain"]


def test_first_line_seen_for_a_folder_is_kept(tmp_path: Path) -> None:
    notice = residue_notice("kitty-specs/x")
    target: list[str] = []
    _append_warnings(target, [f"x: {notice}", notice], checkout_root=tmp_path, seen=set())
    assert target == [f"x: {notice}"]


def test_same_relative_path_in_two_checkouts_is_two_folders(tmp_path: Path) -> None:
    notice = residue_notice("kitty-specs/x")
    seen: set[Path] = set()
    target: list[str] = []
    _append_warnings(target, [notice], checkout_root=tmp_path / "a", seen=seen)
    _append_warnings(target, [notice], checkout_root=tmp_path / "b", seen=seen)
    assert target == [notice, notice]


def test_nested_path_in_main_equals_relative_path_in_worktree(tmp_path: Path) -> None:
    seen: set[Path] = set()
    target: list[str] = []
    _append_warnings(target, [residue_notice(".worktrees/wt1/kitty-specs/x")], checkout_root=tmp_path, seen=seen)
    _append_warnings(target, [f"Worktree wt1: {residue_notice('kitty-specs/x')}"], checkout_root=tmp_path / ".worktrees" / "wt1", seen=seen)
    assert target == [residue_notice(".worktrees/wt1/kitty-specs/x")]


# --------------------------------------------------------------------------
# Runner level, with stub migrations
# --------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _init_repo(root: Path, worktree: str = "wt1") -> Path:
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "metadata.yaml").write_text(_METADATA_YAML.format(version=_FROM_VERSION), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    wt = root / ".worktrees" / worktree
    _git(root, "worktree", "add", "-q", "-b", f"{_WT_BRANCH_PREFIX}{worktree}", str(wt))
    return wt


def _register_stubs(*, main_paths: list[str], worktree_paths: list[str], count: int = 2) -> None:
    """Register *count* stub migrations that each emit residue notices.

    Each stub emits ``main_paths`` when run on the main checkout and
    ``worktree_paths`` when run in a worktree (told apart by ``.worktrees`` in
    the project path); the main one also prefixes its slug like the frozen
    3.2.0a4 migration does.
    """
    MigrationRegistry.clear()
    for index in range(count):

        class _Stub(BaseMigration):
            description = "WP04 residue notice stub"
            target_version = _TARGET_VERSION
            runs_on_worktrees = True
            _main: ClassVar[list[str]] = main_paths
            _wt: ClassVar[list[str]] = worktree_paths

            def detect(self, project_path: Path) -> bool:  # noqa: ARG002
                return True

            def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
                return True, ""

            def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
                in_worktree = ".worktrees" in project_path.parts
                paths = self._wt if in_worktree else self._main
                prefix = "" if in_worktree else "slug-x: "
                return MigrationResult(
                    success=True,
                    changes_made=["stub"],
                    warnings=[prefix + residue_notice(p) for p in paths] + ["unrelated warning"],
                )

        _Stub.migration_id = f"test_wp04_residue_stub_{index}"
        MigrationRegistry.register(_Stub)


def _residue_lines(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "residue directory" in w]


def test_runner_names_a_folder_once_across_steps(tmp_path: Path) -> None:
    _init_repo(tmp_path / "repo")
    try:
        _register_stubs(main_paths=["kitty-specs/x"], worktree_paths=[], count=3)
        result = MigrationRunner(tmp_path / "repo").upgrade(_TARGET_VERSION, include_worktrees=False)
        assert len(_residue_lines(result.warnings)) == 1, result.warnings
        # Non-residue warnings keep today's behaviour: one per step.
        assert result.warnings.count("unrelated warning") == 3
    finally:
        MigrationRegistry.clear()


def test_runner_collapses_main_walk_of_worktree_with_worktree_own_run(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    try:
        _register_stubs(main_paths=[".worktrees/wt1/kitty-specs/x"], worktree_paths=["kitty-specs/x"])
        result = MigrationRunner(root).upgrade(_TARGET_VERSION, include_worktrees=True)
        residue = _residue_lines(result.warnings)
        assert len(residue) == 1, result.warnings
        assert ".worktrees/wt1/kitty-specs/x" in residue[0]
        # The worktree's own non-residue warning still carries its prefix.
        assert any(w.startswith("Worktree wt1: unrelated warning") for w in result.warnings)
    finally:
        MigrationRegistry.clear()


def test_runner_keeps_same_slug_in_two_checkouts_as_two_lines(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    try:
        _register_stubs(main_paths=["kitty-specs/x"], worktree_paths=["kitty-specs/x"])
        result = MigrationRunner(root).upgrade(_TARGET_VERSION, include_worktrees=True)
        residue = _residue_lines(result.warnings)
        assert len(residue) == 2, result.warnings
        assert sum(1 for w in residue if w.startswith("Worktree wt1: ")) == 1
    finally:
        MigrationRegistry.clear()


def test_a_second_run_starts_with_a_fresh_seen_set(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    try:
        _register_stubs(main_paths=["kitty-specs/x"], worktree_paths=[], count=1)
        runner = MigrationRunner(root)
        runner.upgrade(_TARGET_VERSION, dry_run=True, include_worktrees=False)
        second = runner.upgrade(_TARGET_VERSION, dry_run=True, include_worktrees=False)
        assert len(_residue_lines(second.warnings)) == 1
    finally:
        MigrationRegistry.clear()


def test_json_payload_shows_the_collapsed_list(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    try:
        _register_stubs(main_paths=[".worktrees/wt1/kitty-specs/x"], worktree_paths=["kitty-specs/x"])
        with contextlib.chdir(root):
            result = CliRunner().invoke(_cli_app, ["--target", _TARGET_VERSION, "--yes", "--json"], catch_exceptions=False)
        lines = [line for line in result.output.strip().splitlines() if line.strip()]
        payload: dict[str, Any] = json.loads(lines[-1])
        assert len(_residue_lines(payload["warnings"])) == 1, payload["warnings"]
    finally:
        MigrationRegistry.clear()
