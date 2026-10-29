"""``is_mission_dir``: the one is-a-Mission predicate (#5812)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands._mission_type_audit import audit_mission_types
from specify_cli.cli.commands.agent.mission_feature_resolution import _list_feature_spec_candidates
from specify_cli.context.mission_resolver import is_mission_dir, list_missions_for_selection, tracked_mission_paths
from specify_cli.status.identity_audit import audit_repo

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    return tmp_path


def _dir(repo: Path, name: str) -> Path:
    path = repo / "kitty-specs" / name
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize("marker", ["spec.md", "meta.json"])
@pytest.mark.parametrize("batch", [False, True])
def test_tracked_marker_is_a_mission(repo: Path, marker: str, batch: bool) -> None:
    path = _dir(repo, "m-01AAAAAA")
    (path / marker).write_text("{}" if marker == "meta.json" else "# s\n", encoding="utf-8")
    _git(repo, "add", "-A")
    tracked = tracked_mission_paths(repo) if batch else None
    assert is_mission_dir(path, repo_root=repo, tracked=tracked)


def test_untracked_meta_with_mission_id_is_a_mission(repo: Path) -> None:
    path = _dir(repo, "fresh-01BBBBBB")
    (path / "meta.json").write_text(json.dumps({"mission_id": "01HZZZZZZZZZZZZZZZZZZZZREA"}), encoding="utf-8")
    assert is_mission_dir(path, repo_root=repo, tracked=tracked_mission_paths(repo))


def test_gitignored_lock_only_is_residue(repo: Path) -> None:
    path = _dir(repo, "ghost-01CCCCCC")
    (path / "decisions").mkdir()
    (path / "decisions" / "index.json.lock").write_text("", encoding="utf-8")
    assert not is_mission_dir(path, repo_root=repo, tracked=tracked_mission_paths(repo))
    assert not is_mission_dir(path, repo_root=repo)


def test_untracked_meta_without_mission_id_is_residue(repo: Path) -> None:
    path = _dir(repo, "noid-01DDDDDD")
    (path / "meta.json").write_text(json.dumps({"mission_id": ""}), encoding="utf-8")
    assert not is_mission_dir(path, repo_root=repo, tracked=tracked_mission_paths(repo))


def test_non_git_root_falls_back_to_existence_rule(tmp_path: Path) -> None:
    has_spec = tmp_path / "kitty-specs" / "a"
    has_spec.mkdir(parents=True)
    (has_spec / "spec.md").write_text("# s\n", encoding="utf-8")
    empty = tmp_path / "kitty-specs" / "b"
    empty.mkdir()
    assert tracked_mission_paths(tmp_path) is None
    assert is_mission_dir(has_spec, repo_root=tmp_path)
    assert not is_mission_dir(empty, repo_root=tmp_path)


def test_nested_project_legacy_mission_is_a_mission(repo: Path) -> None:
    nested = repo / "mono" / "app"
    path = nested / "kitty-specs" / "legacy-01EEEEEE"
    path.mkdir(parents=True)
    (path / "spec.md").write_text("# s\n", encoding="utf-8")
    (path / "meta.json").write_text(json.dumps({"slug": "legacy"}), encoding="utf-8")
    _git(repo, "add", "-A")
    tracked = tracked_mission_paths(nested)
    assert tracked is not None and "kitty-specs/legacy-01EEEEEE/spec.md" in tracked
    assert is_mission_dir(path, repo_root=nested, tracked=tracked)
    assert is_mission_dir(path, repo_root=nested)


# ---------------------------------------------------------------------------
# FR-007 (#5875): every read-side Mission walker lists the same set.
# ---------------------------------------------------------------------------

_ID = "01HZZZZZZZZZZZZZZZZZZZZREA"


def _write(path: Path, name: str, text: str) -> None:
    (path / name).write_text(text, encoding="utf-8")


def _build_walker_corpus(root: Path, *, git: bool) -> None:
    """The FR-007 fixture: each kind of ``kitty-specs/`` child, committed first where it should be tracked."""
    committed = _dir(root, "committed-01AAAAAA")
    _write(committed, "meta.json", json.dumps({"mission_id": _ID, "mission_slug": "committed-01AAAAAA"}))
    _write(committed, "spec.md", "# s\n")
    legacy = _dir(root, "legacy-tracked")
    _write(legacy, "meta.json", json.dumps({"mission_number": 7}))
    tracked_spec = _dir(root, "spec-only-tracked")
    _write(tracked_spec, "spec.md", "# s\n")
    if git:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "fixture")
    fresh = _dir(root, "fresh-01BBBBBB")
    _write(fresh, "meta.json", json.dumps({"mission_id": "01HYYYYYYYYYYYYYYYYYYYYREA"}))
    noid = _dir(root, "noid-untracked")
    _write(noid, "meta.json", json.dumps({"mission_id": ""}))
    _write(_dir(root, "spec-only-untracked"), "spec.md", "# s\n")
    lock_only = _dir(root, "lock-only")
    (lock_only / "decisions").mkdir()
    _write(lock_only / "decisions", "index.json.lock", "")
    _write(root / "kitty-specs", "README.md", "not a Mission\n")


def _walker_slug_sets(root: Path) -> dict[str, set[str]]:
    return {
        "selection": {listing.mission_slug for listing in list_missions_for_selection(root)},
        "agent_candidates": {str(c["mission_slug"]) for c in _list_feature_spec_candidates(root)},
        "doctor_identity": {s.slug for s in audit_repo(root, residue_aware=True) if s.state != "residue"},
        "doctor_mission_type": {s.slug for s in audit_mission_types(root)},
    }


def test_walkers_agree_on_the_mission_set(repo: Path) -> None:
    """Selection, agent candidates, ``doctor identity`` and ``doctor mission-type`` list one set (FR-007)."""
    _build_walker_corpus(repo, git=True)

    sets = _walker_slug_sets(repo)

    expected = {"committed-01AAAAAA", "fresh-01BBBBBB", "legacy-tracked"}
    assert sets == dict.fromkeys(sets, expected)
    residue = {s.slug for s in audit_repo(repo, residue_aware=True) if s.state == "residue"}
    assert residue == {"noid-untracked", "spec-only-tracked", "spec-only-untracked", "lock-only"}


def test_walkers_agree_on_a_non_git_root(tmp_path: Path) -> None:
    """Outside git an id-less ``meta.json`` is a Mission by existence; a ``spec.md`` alone still is not."""
    _build_walker_corpus(tmp_path, git=False)

    sets = _walker_slug_sets(tmp_path)

    expected = {"committed-01AAAAAA", "fresh-01BBBBBB", "legacy-tracked", "noid-untracked"}
    assert sets == dict.fromkeys(sets, expected)
