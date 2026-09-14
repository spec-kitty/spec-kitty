"""The labeled repository-watcher fallback — sampled, honest, bounded.

The rule under test, verbatim from the issue: "A repository watcher is a
labeled fallback for changed-file observation only; it cannot attribute
edits to a particular agent or claim file reads. Unknown actors/bindings
remain visible as unknown."
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.live_work.kinds import WorkEmissionKind
from specify_cli.live_work.models import FileDetail, FileOperation, UnknownActor
from specify_cli.live_work.watcher import MAX_WATCHED_PATHS, watch_changed_files

pytestmark = pytest.mark.fast


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "remote", "add", "origin", "https://github.com/acme/repo.git")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    for name in ("src/a.py", "src/b.py"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")
    return root


def test_clean_tree_produces_nothing(repo: Path) -> None:
    assert watch_changed_files(repo) == []


def test_edit_delete_and_untracked_create_are_observed_sampled(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("original\nchanged\n", encoding="utf-8")
    (repo / "src" / "b.py").unlink()
    (repo / "src" / "new.py").write_text("fresh\n", encoding="utf-8")
    observations = watch_changed_files(repo)
    by_path = {}
    for observation in observations:
        detail = observation.action
        assert isinstance(detail, FileDetail)
        by_path[detail.path] = detail
    assert by_path["src/a.py"].operation == FileOperation.EDIT
    assert by_path["src/b.py"].operation == FileOperation.DELETE
    assert by_path["src/new.py"].operation == FileOperation.CREATE


def test_rename_is_observed_with_destination(repo: Path) -> None:
    _git(repo, "mv", "src/a.py", "src/renamed.py")
    observations = watch_changed_files(repo)
    renames = [obs.action for obs in observations if isinstance(obs.action, FileDetail) and obs.action.operation == FileOperation.RENAME]
    assert renames
    rename = renames[0]
    assert rename.destination_path is not None
    assert rename.destination_path.endswith("src/renamed.py")


def test_every_observation_is_labeled_sampled_and_unknown(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n", encoding="utf-8")
    observations = watch_changed_files(repo)
    assert observations
    for observation in observations:
        detail = observation.action
        assert isinstance(detail, FileDetail)
        assert detail.attribution == "sampled"
        assert isinstance(observation.actor, UnknownActor)
        assert observation.provenance.limitation is not None
        assert "cannot attribute" in observation.provenance.limitation
        assert "file reads" in observation.provenance.limitation
        assert observation.provenance.capability == "live-work.watcher.fallback"


def test_secret_files_are_never_observed(repo: Path) -> None:
    (repo / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    (repo / "keys.pem").write_text("keymaterial\n", encoding="utf-8")
    (repo / "src" / "a.py").write_text("changed\n", encoding="utf-8")
    observations = watch_changed_files(repo)
    paths = [obs.action.path for obs in observations if isinstance(obs.action, FileDetail)]
    assert ".env" not in paths
    assert "keys.pem" not in paths
    assert "src/a.py" in paths


def test_watcher_is_bounded_per_invocation(repo: Path) -> None:
    for i in range(MAX_WATCHED_PATHS + 10):
        (repo / f"src/file{i:03d}.py").write_text("x\n", encoding="utf-8")
    observations = watch_changed_files(repo)
    assert len(observations) <= MAX_WATCHED_PATHS


def test_non_repository_is_honest_nothing(tmp_path: Path) -> None:
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    assert watch_changed_files(empty) == []


def test_all_kinds_are_file_observations_only(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("changed\n", encoding="utf-8")
    for observation in watch_changed_files(repo):
        assert observation.kind == WorkEmissionKind.FILE_EDITED
        # The watcher never claims a read.
        detail = observation.action
        assert isinstance(detail, FileDetail)
        assert detail.operation != FileOperation.READ
