"""CLI surface tests for ``spec-kitty migrate repin-hooks`` (#254).

Mirrors the ``patch(locate_project_root)`` pattern in
``tests/migration/test_backfill_identity_cli.py`` — ``repin-hooks`` has no
``--project-root`` option (it operates on the CURRENT repo like
``backfill-identity``/``backfill-topology``/``rebaseline-dossier-hashes``),
so the project root is substituted at the resolver, not via a CLI flag.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app

pytestmark = [pytest.mark.integration]


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    (repo / ".kittify").mkdir()
    return repo


def test_help_flag_registers_subcommand() -> None:
    result = CliRunner().invoke(migrate_app, ["repin-hooks", "--help"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "repin-hooks" in plain
    assert "--json" in plain


def test_json_output_reports_current_interpreter(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    with patch(
        "specify_cli.cli.commands.migrate_cmd.locate_project_root",
        return_value=repo,
    ):
        result = CliRunner().invoke(migrate_app, ["repin-hooks", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "repinned"
    assert payload["interpreter"] == os.path.abspath(sys.executable)

    hook_path = Path(payload["hook_path"])
    assert hook_path.is_file()
    assert os.path.abspath(sys.executable) in hook_path.read_text(encoding="utf-8")


def test_exits_1_when_project_root_not_found() -> None:
    with patch(
        "specify_cli.cli.commands.migrate_cmd.locate_project_root",
        return_value=None,
    ):
        result = CliRunner().invoke(migrate_app, ["repin-hooks"])

    assert result.exit_code == 1


@pytest.mark.parametrize("shape", ["main", "alias", "linked"])
def test_real_repository_discovery_installs_only_the_primary_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str) -> None:
    repo = _init_repo(tmp_path)
    cwd = repo
    if shape == "alias":
        cwd = tmp_path / "repository alias"
        cwd.symlink_to(repo, target_is_directory=True)
    elif shape == "linked":
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "seed"],
            cwd=repo,
            check=True,
        )
        cwd = tmp_path / "linked"
        subprocess.run(["git", "worktree", "add", "--detach", str(cwd)], cwd=repo, check=True, capture_output=True)
    child = cwd / "nested"
    child.mkdir()
    monkeypatch.chdir(child)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    result = CliRunner().invoke(migrate_app, ["repin-hooks", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert Path(payload["hook_path"]).resolve() == (repo / ".git/hooks/pre-commit").resolve()
    assert os.path.abspath(sys.executable) in (repo / ".git/hooks/pre-commit").read_text()
    assert not (child / ".git").exists()
    if shape == "linked":
        assert (cwd / ".git").is_file()


def test_global_only_kittify_ancestor_refuses_without_creating_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / ".kittify").mkdir(parents=True)
    marker = home / ".kittify/global-asset.yaml"
    marker.write_text("kind: global-runtime-assets\n")
    child = home / "workspace/nested"
    child.mkdir(parents=True)
    monkeypatch.chdir(child)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    before = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}
    result = CliRunner().invoke(migrate_app, ["repin-hooks", "--json"])
    assert result.exit_code == 1, result.output
    assert "git" in result.output.lower()
    assert not (home / ".git").exists()
    assert not (child / ".git").exists()
    assert {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("replacement", [False, True])
def test_formerly_real_deleted_repository_is_not_recreated_from_cached_topology(tmp_path: Path, replacement: bool) -> None:
    import shutil

    from kernel.git_topology import git_toplevel
    from specify_cli.cli.commands.migrate.repin_hooks import run_repin_hooks_migration

    repo = _init_repo(tmp_path)
    assert git_toplevel(repo) == repo.resolve()
    shutil.rmtree(repo / ".git")
    if replacement:
        (repo / ".git").mkdir()
    with pytest.raises(RuntimeError):
        run_repin_hooks_migration(repo)
    if replacement:
        assert list((repo / ".git").iterdir()) == []
    else:
        assert not (repo / ".git").exists()


def test_hook_install_refuses_git_deleted_after_the_authority_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    from specify_cli.cli.commands.migrate.repin_hooks import run_repin_hooks_migration
    from specify_cli.policy import hook_installer

    repo = _init_repo(tmp_path)
    original = hook_installer.install

    def remove_before_install(root: Path):
        shutil.rmtree(repo / ".git")
        return original(root)

    monkeypatch.setattr(hook_installer, "install", remove_before_install)
    with pytest.raises((RuntimeError, OSError)):
        run_repin_hooks_migration(repo)
    assert not (repo / ".git").exists()


def test_nested_nonroot_directory_cannot_gain_repository_metadata(tmp_path: Path) -> None:
    from specify_cli.cli.commands.migrate.repin_hooks import run_repin_hooks_migration

    repo = _init_repo(tmp_path)
    child = repo / "nested"
    child.mkdir()
    with pytest.raises(RuntimeError):
        run_repin_hooks_migration(child)
    assert not (child / ".git").exists()
