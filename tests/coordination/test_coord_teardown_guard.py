"""Regression: coordination worktree teardown must refuse to destroy dirt (#4753, WP02).

Pre-fix, ``CoordinationWorkspace.teardown`` ran an unconditional
``git worktree remove --force`` on an existing coordination worktree --
uncommitted operator work inside it was silently destroyed with no warning.

This test drives the REAL entry point (``CoordinationWorkspace.teardown``)
against a coordination worktree carrying a genuine tracked-file dirt (the
kind of change ``ref_advance._dirty_entries`` always flags, independent of
any obstruction/target-tree heuristic) and asserts that the shared guarded
seam (``specify_cli.git.destructive_guard.guarded_worktree_remove``) refuses
instead of force-removing it (FR-003 / NFR-001).

``teardown`` owns ONLY the worktree leg of the coordination triple by design
(it must never delete the branch -- that is ``spec-kitty merge``'s job). So a
refusal here, which raises before any destructive git command runs, leaves
the coordination branch untouched by construction -- there is no code path
between the raise and a branch delete for it to hold back (FR-004): the
triple survives because the worktree leg never got as far as mutating
anything.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import CoordinationWorkspace
from specify_cli.coordination.teardown import (
    COORD_TEARDOWN_KEPT_ONLY_COPY,
    COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE,
    CoordTeardownKeptOnlyCopy,
    teardown_coordination_topology,
)
from specify_cli.git.destructive_guard import DestructiveOpRefused

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

MISSION_ID = "01KXTM590000000000000000"
MID8 = MISSION_ID[:8]
SLUG = f"coord-guard-fixture-{MID8}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


@pytest.fixture
def coord_repo(tmp_path: Path) -> tuple[Path, str]:
    """A real repo with a materialised coordination worktree."""
    repo = _init_repo(tmp_path)
    branch = CoordinationWorkspace.branch_name(SLUG, MID8)
    _git(repo, "branch", branch)
    CoordinationWorkspace.resolve(repo, SLUG, MID8)
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)
    return repo, branch


def test_teardown_refuses_dirty_coord_worktree(coord_repo: tuple[Path, str]) -> None:
    """A tracked-file edit inside the coord worktree blocks force-removal."""
    repo, branch = coord_repo
    coord_path = CoordinationWorkspace.worktree_path(repo, SLUG, MID8)
    tracked_file = coord_path / "README.md"
    original = tracked_file.read_text(encoding="utf-8")
    tracked_file.write_text(original + "uncommitted operator work\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        CoordinationWorkspace.teardown(repo, SLUG, MID8)

    # NFR-001: the refusal is pre-mutation -- worktree, its dirty content, and
    # the coordination branch (a resource `teardown` never even attempts to
    # touch) all survive byte-identical.
    assert coord_path.exists(), "dirty coordination worktree must survive the refusal"
    assert tracked_file.read_text(encoding="utf-8") == original + "uncommitted operator work\n"
    branches = _git(repo, "branch", "--list", branch).stdout.strip()
    assert branches != "", "coordination branch must survive a worktree-teardown refusal"


def test_teardown_removes_clean_coord_worktree(coord_repo: tuple[Path, str]) -> None:
    """Unchanged behavior: a clean coordination worktree is still removed."""
    repo, branch = coord_repo
    coord_path = CoordinationWorkspace.worktree_path(repo, SLUG, MID8)
    assert coord_path.exists()

    CoordinationWorkspace.teardown(repo, SLUG, MID8)

    assert not coord_path.exists()
    # `teardown` never deletes the branch -- that stays `spec-kitty merge`'s job.
    branches = _git(repo, "branch", "--list", branch).stdout.strip()
    assert branches != ""


def test_teardown_is_idempotent_on_already_removed_worktree(
    coord_repo: tuple[Path, str],
) -> None:
    """Calling teardown twice on an already-torn-down worktree stays a no-op."""
    repo, _branch = coord_repo
    CoordinationWorkspace.teardown(repo, SLUG, MID8)
    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8)

    # Second call must not raise.
    CoordinationWorkspace.teardown(repo, SLUG, MID8)


# -- #5965: the coordination worktree is judged by its ROLE, with the Mission's stored topology ---------


def _write_mission_meta(repo: Path, topology: str = "coord") -> Path:
    mission_dir = repo / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mid8": MID8, "mission_slug": SLUG, "topology": topology, "coordination_branch": f"kitty/mission-{SLUG}"}),
        encoding="utf-8",
    )
    return mission_dir


def _coord_artifact(repo: Path, relative: str) -> Path:
    path = CoordinationWorkspace.worktree_path(repo, SLUG, MID8) / "kitty-specs" / SLUG / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("only copy\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("relative", ["tasks/WP02-work/review-cycle-1.md", "traces/notes.md", "issue-matrix.json"])
def test_teardown_keeps_coordination_kind_files_the_old_predicate_called_residue(coord_repo: tuple[Path, str], relative: str) -> None:
    """With the Mission's stored topology the coordination worktree holds the ONLY copy of these, so they refuse (#5965)."""
    repo, _branch = coord_repo
    _write_mission_meta(repo)
    kept = _coord_artifact(repo, relative)

    with pytest.raises(DestructiveOpRefused) as refused:
        CoordinationWorkspace.teardown(repo, SLUG, MID8)

    assert kept.name in str(refused.value)
    assert kept.read_text(encoding="utf-8") == "only copy\n"
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)


def test_teardown_with_meta_still_removes_a_clean_worktree(coord_repo: tuple[Path, str]) -> None:
    repo, _branch = coord_repo
    _write_mission_meta(repo)

    CoordinationWorkspace.teardown(repo, SLUG, MID8)

    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8)


def test_teardown_without_meta_treats_nothing_as_residue(coord_repo: tuple[Path, str]) -> None:
    """No stored topology to judge by: even a status file refuses (the strictest answer), a clean worktree goes."""
    repo, _branch = coord_repo
    status = CoordinationWorkspace.worktree_path(repo, SLUG, MID8) / "status.json"
    status.write_text("{}\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        CoordinationWorkspace.teardown(repo, SLUG, MID8)

    status.unlink()
    CoordinationWorkspace.teardown(repo, SLUG, MID8)
    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8)


def test_teardown_seam_turns_the_refusal_into_kept_only_copy_with_the_callers_follow_up(coord_repo: tuple[Path, str]) -> None:
    """``teardown_coordination_topology`` no longer swallows the guard: it reports the kept files and the follow-up command."""
    repo, branch = coord_repo
    _write_mission_meta(repo)
    kept = _coord_artifact(repo, "traces/notes.md")

    with pytest.raises(CoordTeardownKeptOnlyCopy) as excinfo:
        teardown_coordination_topology(repo, SLUG, MID8, persist=False, check_ledger=False, follow_up_command="spec-kitty consolidate --abort")

    error = excinfo.value
    assert error.error_code == COORD_TEARDOWN_KEPT_ONLY_COPY and error.exit_code == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE
    assert any("notes.md" in entry for entry in error.kept_files)
    assert "spec-kitty consolidate --abort" in str(error)
    assert kept.is_file() and _git(repo, "branch", "--list", branch).stdout.strip() != ""


def test_teardown_seam_still_swallows_other_failures(coord_repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _branch = coord_repo

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk on fire")

    monkeypatch.setattr(CoordinationWorkspace, "teardown", boom)

    assert teardown_coordination_topology(repo, SLUG, MID8, persist=False, check_ledger=False) is False
