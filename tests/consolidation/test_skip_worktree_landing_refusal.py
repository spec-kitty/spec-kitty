"""``preflight.skip_worktree_landing_refusal``: which skip-worktree entries refuse a landing up front.

Only an entry the landing's checkout resync would have to rewrite refuses: the bit set by hand
(its file present; a sparse-checkout exclusion has none), on a path under the Mission directory or
one the Mission branch changes. End to end: ``tests/terminus/test_consolidate_skip_worktree_checkout.py``.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import preflight
from specify_cli.coordination.types import Refused
from specify_cli.lanes.models import LanesManifest

pytestmark = [pytest.mark.git_repo]

_SLUG = "m"
_META = f"kitty-specs/{_SLUG}/meta.json"
_MISSION_BRANCH = "kitty/mission-m"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    for rel in (_META, "src/b.py", "README.md"):
        _write(repo, rel, "base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", _MISSION_BRANCH)
    _write(repo, "src/b.py", "mission\n")
    _write(repo, _META, "mission\n")
    _git(repo, "commit", "-qam", "mission work")
    _git(repo, "checkout", "-q", "main")
    return repo


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[],
        computed_at="2026-11-17T00:00:00+00:00",
        computed_from="test",
    )


def _verdict(repo: Path) -> Refused | None:
    return preflight.skip_worktree_landing_refusal(repo, _SLUG, _manifest(), target_branch="main")


def test_no_bit_is_no_refusal(repo: Path) -> None:
    assert _verdict(repo) is None


@pytest.mark.parametrize("path", [_META, "src/b.py"], ids=["mission-dir", "landing-diff"])
def test_a_skip_worktree_entry_the_landing_writes_refuses(repo: Path, path: str) -> None:
    _git(repo, "update-index", "--skip-worktree", path)
    verdict = _verdict(repo)
    assert verdict is not None and verdict.error_code == preflight.CHECKOUT_SKIP_WORKTREE_ENTRIES
    assert path in verdict.message and "'main'" in verdict.message
    assert verdict.next_step.startswith(f"Clear the bit (`git update-index --no-skip-worktree {path}`), then re-run.")
    # #7692 landing fold: a sparse-checkout exclusion is named as a possible cause, with its own remedy.
    assert "git sparse-checkout list" in verdict.next_step and "git sparse-checkout add <dir>" in verdict.next_step


def test_a_skip_worktree_entry_the_landing_does_not_write_is_left_alone(repo: Path) -> None:
    _git(repo, "update-index", "--skip-worktree", "README.md")
    assert _verdict(repo) is None


def test_a_sparse_exclusion_with_no_file_is_left_alone(repo: Path) -> None:
    _git(repo, "update-index", "--skip-worktree", _META)
    (repo / _META).unlink()
    assert _verdict(repo) is None


def test_an_assume_unchanged_bit_is_left_alone(repo: Path) -> None:
    _git(repo, "update-index", "--assume-unchanged", _META)
    assert _verdict(repo) is None


def test_a_checkout_on_another_branch_is_not_judged(repo: Path) -> None:
    _git(repo, "update-index", "--skip-worktree", _META)
    assert preflight.skip_worktree_landing_refusal(repo, _SLUG, _manifest(), target_branch="develop") is None


def test_skip_worktree_with_assume_unchanged_too_refuses(repo: Path) -> None:
    """Review SW-2: ``ls-files -v`` tags an entry carrying both bits ``s``."""
    _git(repo, "update-index", "--skip-worktree", _META)
    _git(repo, "update-index", "--assume-unchanged", _META)
    assert _git(repo, "ls-files", "-v", _META).startswith("s ")
    verdict = _verdict(repo)
    assert verdict is not None and verdict.error_code == preflight.CHECKOUT_SKIP_WORKTREE_ENTRIES


def test_a_skip_worktree_dangling_symlink_refuses(repo: Path) -> None:
    """Review SW-3: a broken symlink is present in the working tree (``lexists``), so it refuses."""
    link = repo / "kitty-specs" / _SLUG / "link"
    link.symlink_to("nowhere")
    _git(repo, "add", str(link.relative_to(repo)))
    _git(repo, "commit", "-qm", "link")
    _git(repo, "update-index", "--skip-worktree", f"kitty-specs/{_SLUG}/link")
    verdict = _verdict(repo)
    assert verdict is not None and f"kitty-specs/{_SLUG}/link" in verdict.message


def test_a_checkout_of_the_mission_branch_is_scanned_too(repo: Path, tmp_path: Path) -> None:
    """Review SW-4: the Mission branch's checkout is resynced when lanes merge into it."""
    wt = tmp_path / "mission-wt"
    _git(repo, "worktree", "add", "-q", str(wt), _MISSION_BRANCH)
    _git(wt, "update-index", "--skip-worktree", _META)
    verdict = _verdict(repo)
    assert verdict is not None and verdict.error_code == preflight.CHECKOUT_SKIP_WORKTREE_ENTRIES
    assert f"git -C {wt}" in verdict.next_step and _MISSION_BRANCH in verdict.message


def test_an_edited_skip_worktree_code_file_the_landing_writes_refuses(repo: Path) -> None:
    """Review item 6: an edit under the bit is invisible to ``git status`` and the dirty gate; refused."""
    _git(repo, "update-index", "--skip-worktree", "src/b.py")
    (repo / "src" / "b.py").write_text("local edit\n", encoding="utf-8")
    assert _git(repo, "status", "--porcelain") == ""
    verdict = _verdict(repo)
    assert verdict is not None and "src/b.py" in verdict.message


@pytest.mark.parametrize(
    ("bits", "name"),
    [
        (("--skip-worktree",), "skip-worktree"),
        (("--assume-unchanged",), "assume-unchanged"),
        (("--skip-worktree", "--assume-unchanged"), "skip-worktree and assume-unchanged"),
    ],
)
def test_the_retarget_index_bit_names_every_bit_and_its_remedy_clears_them(repo: Path, bits: tuple[str, ...], name: str) -> None:
    """Re-review LOW-4: ``s`` (both bits) is named as both, and the printed remedy clears both in one step."""
    for bit in bits:
        _git(repo, "update-index", bit, _META)
    found = preflight._index_bit(repo, Path(_META))
    assert found is not None
    bit_name, remedy = found
    assert bit_name == name
    for command in remedy.split(" && "):  # the printed remedy, verbatim
        subprocess.run(shlex.split(command), cwd=repo, check=True)
    assert _git(repo, "ls-files", "-v", _META).startswith("H ")


def test_the_merge_record_key_rule_is_shared_by_the_executor_and_its_readers() -> None:
    """#7692 landing fold: one rule keys the merge record, so the stored and looked-up keys cannot drift."""
    import inspect

    from specify_cli.consolidation import executor, preflight

    assert preflight.record_key_for_identity("01M7M5JAXXXXXXXXXXXXXXXXXX", "slug") == "01M7M5JAXXXXXXXXXXXXXXXXXX"
    assert preflight.record_key_for_identity(None, "slug") == "slug"
    assert "record_key_for_identity(identity.mission_id, mission_slug)" in inspect.getsource(executor._run_lane_based_consolidation)
    assert "record_key_for_identity(" in inspect.getsource(preflight.merge_record_key)
