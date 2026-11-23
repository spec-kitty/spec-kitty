"""#7747: a clean squash landing of a ``lanes_with_coord`` Mission removes every lane.

Each lane synced with the coordination branch while it was implemented (``implement`` merges it in),
so it carries older copies of Mission files the tool rewrote after the sync: the status log and
snapshot, ``meta.json`` and the work package prompts' claim frontmatter. Before the fix, lane cleanup
kept every lane with ``NOT_LANDED_ON_NAMED_REMOTE``, although every product change was on the target.

Drives the real ``spec-kitty`` CLI (implement, review, approve, default squash ``consolidate``) on a
real repository, through the harness of ``test_default_mission_consolidate_lands_primary.py``: three
lanes, the smallest Mission finalize settles to ``lanes_with_coord``. Nightly-only directory
(``tests/integration``); the unit rules live in ``tests/lanes/test_lane_tip_mission_bookkeeping.py``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import (
    Built,
    _lane_worktree,
    _ok,
    _quiet,
    build,
    consolidate,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_LANES = ("lane-a", "lane-b", "lane-c")


@pytest.fixture(scope="module")
def landed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Built, subprocess.CompletedProcess[str]]]:
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        built = build(tmp_path_factory.mktemp("landing-proof-7747"))
        yield built, consolidate(built)


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)


def _cleanup_block(stdout: str) -> list[str]:
    lines = stdout.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == "Lane cleanup")
    block: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        block.append(line)
    return block


def test_every_lane_of_a_squash_landing_is_removed(landed: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = landed
    _ok(proc)
    block = _cleanup_block(proc.stdout)
    assert not [line for line in block if line.lstrip().startswith("Kept")], "\n".join(block)
    removed = {line.split()[1] for line in block if line.lstrip().startswith("Removed")}
    assert removed == set(_LANES), "\n".join(block)


def test_no_lane_worktree_or_branch_is_left(landed: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = landed
    _ok(proc)
    for index in (1, 2, 3):
        assert not _lane_worktree(built, index).exists()
    assert git(built.root, "branch", "--list", f"kitty/mission-{built.slug}-lane-*") == ""
