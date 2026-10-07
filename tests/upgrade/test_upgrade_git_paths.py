"""Real-git coverage: upgrade and migration sites read git paths losslessly.

Mission git-paths-are-data (#5392/#5400). Every test builds a temporary
repository and never mocks git. A space or a non-ASCII name is what ``git``
prints quoted in its display formats.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from specify_cli.migration.mission_state import MissionStateRepairError, _assert_git_safe
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.migrations.m_3_2_0rc35_sync_state_gitignore import _is_tracked
from specify_cli.upgrade.migrations.m_3_2_5_agents_skills_gitignore_backfill import _untrack_tracked_paths
from specify_cli.upgrade.migrations.m_4_0_0rc5_heal_template_set_provenance import (
    _checkout_tracks_mission,
    _source_path_snapshot,
)

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8")
    return done.stdout


def _init(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _write(repo: Path, rel: str, text: str = "x\n") -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _commit(repo: Path, message: str = "c") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


# ---------------------------------------------------------------------------
# upgrade/autocommit.git_status_paths
# ---------------------------------------------------------------------------


def test_git_status_paths_reads_non_ascii_and_spaced_names_exactly(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "README.md")
    _commit(repo)
    _write(repo, "docs/café notes.md")
    _write(repo, "ünï/ file.txt")

    paths = autocommit.git_status_paths(repo)

    assert paths == {"docs/café notes.md", "ünï/ file.txt"}


def test_git_status_paths_keeps_rename_destination_and_origin(tmp_path: Path) -> None:
    """CHANGELOG #2491/#2492: the set holds the destination; the origin rides alongside."""
    repo = _init(tmp_path / "repo")
    _write(repo, "old é.py", "print('hi')\n" * 10)
    _commit(repo)
    _git(repo, "mv", "old é.py", "new é.py")
    _write(repo, "other file.md")

    paths = autocommit.git_status_paths(repo)

    assert paths == {"new é.py", "other file.md"}
    assert isinstance(paths, autocommit._GitStatusPaths)
    assert paths.origins == {"new é.py": ("old é.py", True)}


def test_git_status_paths_is_none_outside_a_repository(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert autocommit.git_status_paths(plain) is None


def test_prepare_upgrade_commit_files_names_quoted_paths(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "README.md")
    _commit(repo)
    baseline = autocommit.capture_upgrade_baseline(repo)
    assert baseline is not None
    _write(repo, ".kittify/café state.json")

    assert autocommit.prepare_upgrade_commit_files(repo, baseline) == [Path(".kittify/café state.json")]


# ---------------------------------------------------------------------------
# migrations: tracked probes
# ---------------------------------------------------------------------------


def test_rc35_is_tracked_with_spaced_and_non_ascii_path(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "kitty-ops/café ops.jsonl")
    _commit(repo)
    _write(repo, "kitty-ops/untracked one.jsonl")

    assert _is_tracked(repo, "kitty-ops/café ops.jsonl") is True
    assert _is_tracked(repo, "kitty-ops/untracked one.jsonl") is False
    assert _is_tracked(tmp_path / "not-a-repo", "kitty-ops/café ops.jsonl") is False


def test_agents_skills_backfill_untracks_quoted_tracked_paths(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, ".agents/skills/café skill/SKILL.md")
    _write(repo, ".kittify/skills-manifest.json", "{}\n")
    _write(repo, "src/keep.py")
    _commit(repo)

    untracked = _untrack_tracked_paths(repo, [".agents/skills/", ".kittify/skills-manifest.json"])

    assert untracked == [".agents/skills/café skill/SKILL.md", ".kittify/skills-manifest.json"]
    assert _git(repo, "ls-files", "-z").split("\0")[:-1] == ["src/keep.py"]
    assert (repo / ".agents/skills/café skill/SKILL.md").exists()


def test_agents_skills_backfill_untracks_when_project_is_a_repo_subdirectory(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    project = repo / "proj"
    _write(repo, "proj/.agents/skills/s/SKILL.md")
    _write(repo, "proj/src/keep.py")
    _commit(repo)

    untracked = _untrack_tracked_paths(project, [".agents/skills/"])

    assert untracked == [".agents/skills/s/SKILL.md"]
    assert _git(repo, "ls-files").split() == ["proj/src/keep.py"]
    assert (project / ".agents/skills/s/SKILL.md").exists()


def test_agents_skills_backfill_with_nothing_to_untrack_touches_nothing(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "src/keep.py")
    _commit(repo)

    assert _untrack_tracked_paths(repo, []) == []
    assert _untrack_tracked_paths(repo, [".agents/skills/"]) == []
    assert _git(repo, "ls-files").split() == ["src/keep.py"]


def _checkout_with_mission_source(root: Path, relative: PurePosixPath) -> tuple[Path, PurePosixPath]:
    repo = _init(root / "checkout")
    _write(repo, "pyproject.toml", '[project]\nname = "spec-kitty-cli"\n\n[project.urls]\nRepository = "https://github.com/spec-kitty/spec-kitty"\n')
    _write(repo, str(relative), "mission: x\n")
    _git(repo, "remote", "add", "origin", "https://github.com/spec-kitty/spec-kitty.git")
    return repo.resolve(), relative


def test_heal_template_set_provenance_recognises_a_tracked_spaced_source(tmp_path: Path) -> None:
    relative = PurePosixPath("packs/built-in/missions/my mission/mission.yaml")
    repo, relative = _checkout_with_mission_source(tmp_path, relative)
    _commit(repo)
    snapshot = _source_path_snapshot(repo, relative)
    assert snapshot is not None

    assert _checkout_tracks_mission(repo, relative, snapshot) is True


def test_heal_template_set_provenance_rejects_an_untracked_source(tmp_path: Path) -> None:
    relative = PurePosixPath("packs/built-in/missions/my mission/mission.yaml")
    repo, relative = _checkout_with_mission_source(tmp_path, relative)
    snapshot = _source_path_snapshot(repo, relative)
    assert snapshot is not None

    assert _checkout_tracks_mission(repo, relative, snapshot) is False


# ---------------------------------------------------------------------------
# migration/mission_state._assert_git_safe: a guard
# ---------------------------------------------------------------------------


def test_assert_git_safe_refuses_a_dirty_quoted_relevant_path(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "kitty-specs/café mission/meta.json", "{}\n")
    _commit(repo)
    (repo / "kitty-specs/café mission/meta.json").write_text("{ }\n", encoding="utf-8")

    with pytest.raises(MissionStateRepairError, match="café mission/meta.json"):
        _assert_git_safe(repo, ["kitty-specs/café mission"], allow_dirty=False)
    _assert_git_safe(repo, ["kitty-specs/café mission"], allow_dirty=True)


def test_assert_git_safe_passes_when_relevant_paths_are_clean(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "kitty-specs/café mission/meta.json", "{}\n")
    _commit(repo)
    _write(repo, "unrelated/dirty file.txt")

    _assert_git_safe(repo, ["kitty-specs/café mission"], allow_dirty=False)


def test_assert_git_safe_fails_closed_when_git_cannot_answer(tmp_path: Path) -> None:
    """FR-013: an unreadable index refuses (MissionStateRepairError), never reads "clean"."""
    repo = _init(tmp_path / "repo")
    _write(repo, "kitty-specs/m/meta.json", "{}\n")
    _commit(repo)
    (repo / ".git" / "index").write_bytes(b"not an index")

    with pytest.raises(MissionStateRepairError, match="could not read git status"):
        _assert_git_safe(repo, ["kitty-specs/m"], allow_dirty=False)


def test_assert_git_safe_skips_a_stale_worktree_registration(tmp_path: Path) -> None:
    """A registered worktree whose directory was deleted (not pruned) has nothing to be dirty."""
    repo = _init(tmp_path / "repo")
    _write(repo, "kitty-specs/m/meta.json", "{}\n")
    _commit(repo)
    stale = tmp_path / "stale-wt"
    _git(repo, "worktree", "add", "-q", "-b", "stale", str(stale))
    shutil.rmtree(stale)

    _assert_git_safe(repo, ["kitty-specs/m"], allow_dirty=False)
