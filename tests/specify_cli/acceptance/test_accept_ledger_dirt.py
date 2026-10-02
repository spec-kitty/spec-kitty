"""Accept is a decision-ledger committer (FR-009b / operator decision G1).

The accept dirty gate must not block on the CURRENT mission's uncommitted PRIMARY
decision ledger (``decisions/index.json`` + ``DM-*.md``) -- the residual acceptance
commit lands it -- while every other dirty path still fails closed. These tests
drive ``_accept_dirty_gate`` itself (the gate the unit test of the residual commit
bypasses) and the residual scan that feeds the commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitPath, StatusEntry
from specify_cli.acceptance import _accept_dirty_gate
from specify_cli.acceptance.ledger_dirt import is_mission_decision_ledger_entry, mission_decision_ledger_files
from specify_cli.cli.commands.accept import _primary_dirty_paths

pytestmark = pytest.mark.fast

_FEATURE = "ledger-mission-01ABCDEF"
_KS = f"kitty-specs/{_FEATURE}"
_INDEX = f" M {_KS}/decisions/index.json"
_NEW_DM = f"?? {_KS}/decisions/DM-01NEWDECISION0000000000.md"


def _entry(line: str) -> StatusEntry:
    """Build the typed status entry for a porcelain-style ``XY path`` fixture line."""
    return StatusEntry(xy=line[:2], path=GitPath.parse(line[3:]), is_directory=line.endswith("/"))


def _gate(tmp_path: Path, lines: list[str]) -> list[str]:
    gated: list[str] = _accept_dirty_gate([_entry(line) for line in lines], repo_root=tmp_path, feature=_FEATURE)
    return gated


def test_uncommitted_ledger_does_not_block_the_gate(tmp_path: Path) -> None:
    assert _gate(tmp_path, [_INDEX, _NEW_DM]) == []


def test_collapsed_untracked_ledger_directory_does_not_block_the_gate(tmp_path: Path) -> None:
    decisions = tmp_path / _KS / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "index.json").write_text("{}\n", encoding="utf-8")
    (decisions / "DM-01A.md").write_text("x\n", encoding="utf-8")
    assert _gate(tmp_path, [f"?? {_KS}/decisions/"]) == []


@pytest.mark.parametrize(
    "dirty",
    [
        " M src/demo/a.py",
        f" M {_KS}/spec.md",
        " M kitty-specs/other-mission-01ZZZZZZ/decisions/index.json",
        "?? kitty-specs/other-mission-01ZZZZZZ/decisions/DM-01B.md",
        f" M {_KS}/plan.md",
    ],
)
def test_unrelated_dirt_still_blocks_alongside_the_ledger(tmp_path: Path, dirty: str) -> None:
    assert _gate(tmp_path, [_INDEX, _NEW_DM, dirty]) == [dirty]


def test_collapsed_directory_mixing_ledger_and_other_files_still_blocks(tmp_path: Path) -> None:
    (tmp_path / _KS / "decisions").mkdir(parents=True)
    (tmp_path / _KS / "decisions" / "index.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / _KS / "notes.md").write_text("x\n", encoding="utf-8")
    line = f"?? {_KS}/"
    assert _gate(tmp_path, [line]) == [line]


def test_empty_or_missing_directory_entry_is_not_a_ledger_line(tmp_path: Path) -> None:
    line = f"?? {_KS}/decisions/"
    assert is_mission_decision_ledger_entry(_entry(line), repo_root=tmp_path, mission_slug=_FEATURE) is False


def test_ledger_files_helper_lists_modified_and_untracked_ledger_only(tmp_path: Path) -> None:
    lines = [_INDEX, _NEW_DM, f" M {_KS}/spec.md", " M src/demo/a.py", _NEW_DM]
    assert mission_decision_ledger_files([_entry(line) for line in lines], repo_root=tmp_path, mission_slug=_FEATURE) == [
        f"{_KS}/decisions/index.json",
        f"{_KS}/decisions/DM-01NEWDECISION0000000000.md",
    ]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.mark.git_repo
def test_residual_scan_includes_the_untracked_new_dm_file(tmp_path: Path) -> None:
    """The residual commit feeds on ``_primary_dirty_paths``: the new ``DM-*.md`` must be in it."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    decisions = tmp_path / _KS / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "index.json").write_text('{"entries": []}\n', encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    (decisions / "index.json").write_text('{"entries": [1]}\n', encoding="utf-8")
    (decisions / "DM-01NEW.md").write_text("new\n", encoding="utf-8")
    (tmp_path / _KS / "stray.txt").write_text("unmanaged\n", encoding="utf-8")

    dirty = _primary_dirty_paths(tmp_path, _FEATURE)

    assert f"{_KS}/decisions/index.json" in dirty
    assert f"{_KS}/decisions/DM-01NEW.md" in dirty
    assert f"{_KS}/stray.txt" not in dirty  # unmanaged untracked files are never swept into the commit
