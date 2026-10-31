"""Global runtime storage is not inferred project-wide write authority."""

from pathlib import Path
import json
import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app

pytestmark = pytest.mark.integration


def _case(tmp_path: Path) -> tuple[Path, Path, Path]:
    from tests.dossier.test_rebaseline import _record_old_form_snapshot, _write_source_mission

    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    cwd = root / "workspace/nested"
    cwd.mkdir(parents=True)
    mission = root / "unrelated-project/kitty-specs/dossier-fixture"
    _write_source_mission(mission)
    snapshot = _record_old_form_snapshot(mission, "dossier-fixture")
    return root, cwd, snapshot


def _files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _global_storage(root: Path, monkeypatch: pytest.MonkeyPatch, *, alias: bool = False) -> None:
    storage = root / ".kittify"
    if alias:
        link = root.parent / "global runtime alias"
        link.symlink_to(storage, target_is_directory=True)
        storage = link
    monkeypatch.setenv("SPEC_KITTY_HOME", str(storage))
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("alias", [False, True])
def test_inferred_global_storage_refuses_before_glob_and_preserves_nested_dossier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dry_run: bool, alias: bool
) -> None:
    from specify_cli.dossier.rebaseline import iter_recorded_snapshot_files

    root, cwd, snapshot = _case(tmp_path)
    _global_storage(root, monkeypatch, alias=alias)
    monkeypatch.chdir(cwd)
    before = _files(root)
    args = ["rebaseline-dossier-hashes", "--json"] + (["--dry-run"] if dry_run else [])
    with patch("specify_cli.dossier.rebaseline.iter_recorded_snapshot_files", wraps=iter_recorded_snapshot_files) as traversal:
        result = CliRunner().invoke(migrate_app, args)
    assert _files(root) == before
    assert traversal.call_count == 0
    assert result.exit_code == 1, result.output
    assert "git" in result.output.lower()
    assert not (root / ".git").exists()
    assert not json.loads(snapshot.read_text())["parity_hash_sha256"].startswith("sha256:")


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_explicit_override_falls_through_to_global_root_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    root, cwd, snapshot = _case(tmp_path)
    _global_storage(root, monkeypatch)
    override = tmp_path / "invalid-override"
    if kind == "file":
        override.write_text("not a directory")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(override))
    monkeypatch.chdir(cwd)
    before = _files(root)
    result = CliRunner().invoke(migrate_app, ["rebaseline-dossier-hashes", "--json"])
    assert result.exit_code == 1, result.output
    assert _files(root) == before
    assert not json.loads(snapshot.read_text())["parity_hash_sha256"].startswith("sha256:")


@pytest.mark.parametrize("kind", ["real-repo", "non-global-non-git", "explicit-global-alias", "explicit-linked"])
def test_supported_project_admission_rebaselines_the_intended_dossier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    root, cwd, snapshot = _case(tmp_path)
    _global_storage(root, monkeypatch)
    if kind in {"real-repo", "explicit-linked"}:
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)
        if kind == "explicit-linked":
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "seed"],
                cwd=root,
                check=True,
            )
            linked = tmp_path / "linked"
            subprocess.run(["git", "worktree", "add", "--detach", str(linked)], cwd=root, check=True, capture_output=True)
            monkeypatch.setenv("SPECIFY_REPO_ROOT", str(linked))
            cwd = tmp_path / "unrelated-cwd"
            cwd.mkdir()
    elif kind == "non-global-non-git":
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "separate-global-runtime"))
    else:
        alias = tmp_path / "explicit project alias"
        alias.symlink_to(root, target_is_directory=True)
        monkeypatch.setenv("SPECIFY_REPO_ROOT", str(alias))
    monkeypatch.chdir(cwd)
    source = snapshot.parents[3] / "spec.md"
    original_source = source.read_bytes()
    result = CliRunner().invoke(migrate_app, ["rebaseline-dossier-hashes", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(snapshot.read_text())["parity_hash_sha256"].startswith("sha256:")
    assert source.read_bytes() == original_source
    if kind not in {"real-repo", "explicit-linked"}:
        assert not (root / ".git").exists()


def test_explicit_corpus_override_precedes_an_inferred_global_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inferred, cwd, untouched_snapshot = _case(tmp_path / "inferred")
    explicit, _, intended_snapshot = _case(tmp_path / "explicit")
    _global_storage(inferred, monkeypatch)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(explicit))
    monkeypatch.chdir(cwd)
    before = _files(inferred)
    result = CliRunner().invoke(migrate_app, ["rebaseline-dossier-hashes", "--json"])
    assert result.exit_code == 0, result.output
    assert _files(inferred) == before
    assert not json.loads(untouched_snapshot.read_text())["parity_hash_sha256"].startswith("sha256:")
    assert json.loads(intended_snapshot.read_text())["parity_hash_sha256"].startswith("sha256:")
    assert not (explicit / ".git").exists()
