"""#7692 FR-011 (WP04 rework): the two root-checkout hazards a retarget record check refuses up front.

* :func:`preflight_skip_worktree._index_bit`: a skip-worktree or assume-unchanged bit on the new target's
  ``meta.json`` (refused even with no edit; the bake's own precheck is unchanged);
* :func:`preflight_retarget._untracked_mission_copies_refusal`: untracked copies of the Mission directory
  in a root checkout on a new target that is not a holder.

The end-to-end arms are in ``tests/terminus/test_consolidate_retarget_refusals.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import preflight_skip_worktree
from specify_cli.consolidation import preflight_retarget

pytestmark = pytest.mark.fast

_REL_META = Path("kitty-specs/m/meta.json")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "develop")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-qm", "init")
    return root


def _track_meta(repo: Path) -> None:
    (repo / _REL_META).parent.mkdir(parents=True, exist_ok=True)
    (repo / _REL_META).write_text("{}\n", encoding="utf-8")
    _git(repo, "add", _REL_META.as_posix())
    _git(repo, "commit", "-qm", "meta")


def test_no_bit_reads_as_none(repo: Path) -> None:
    _track_meta(repo)
    assert preflight_skip_worktree._index_bit(repo, _REL_META) is None


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("--skip-worktree", ("skip-worktree", f"git update-index --no-skip-worktree {_REL_META.as_posix()}")),
        ("--assume-unchanged", ("assume-unchanged", f"git update-index --no-assume-unchanged {_REL_META.as_posix()}")),
    ],
)
def test_each_bit_is_named_with_the_command_that_clears_it(repo: Path, flag: str, expected: tuple[str, str]) -> None:
    _track_meta(repo)
    _git(repo, "update-index", flag, _REL_META.as_posix())
    assert preflight_skip_worktree._index_bit(repo, _REL_META) == expected


def test_an_untracked_path_reads_as_no_bit(repo: Path) -> None:
    assert preflight_skip_worktree._index_bit(repo, _REL_META) is None


def test_untracked_mission_copies_on_the_new_target_are_refused(repo: Path) -> None:
    (repo / _REL_META).parent.mkdir(parents=True)
    (repo / _REL_META).write_text("{}\n", encoding="utf-8")

    refusal = preflight_retarget._untracked_mission_copies_refusal(repo, _REL_META, recorded_target="main", effective_target="develop")

    assert refusal is not None and refusal.error_code == preflight_retarget.RETARGET_RECORD_UNWRITABLE
    assert "kitty-specs/m/meta.json" in refusal.message and "overwrite" in refusal.message
    assert "Remove the untracked copies under kitty-specs/m/" in refusal.next_step


def test_no_untracked_copies_admit(repo: Path) -> None:
    assert preflight_retarget._untracked_mission_copies_refusal(repo, _REL_META, recorded_target="main", effective_target="develop") is None


def test_a_root_checkout_on_another_branch_is_not_judged_here(repo: Path) -> None:
    (repo / _REL_META).parent.mkdir(parents=True)
    (repo / _REL_META).write_text("{}\n", encoding="utf-8")
    assert preflight_retarget._untracked_mission_copies_refusal(repo, _REL_META, recorded_target="main", effective_target="release") is None
