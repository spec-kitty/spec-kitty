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

import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import (
    Built,
    _lane_worktree,
    _ok,
    _commit_all,
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
    for index in (1, 2, 3):
        assert not _lane_worktree(built, index).exists()
    assert git(built.root, "branch", "--list", f"kitty/mission-{built.slug}-lane-*") == ""


# --- operator ruling 2026-11-24 (A, B, C): the shapes the first dogfood run kept ----------------------


def _lane_branch(built: Built, index: int) -> str:
    return f"kitty/mission-{built.slug}-lane-{'abc'[index - 1]}"


def _commit_blob(lane: Path, path: str, text: str, message: str) -> None:
    """Commit *path* in a lane checkout, which keeps status files out of its worktree (skip-worktree)."""
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=lane, input=text, capture_output=True, text=True, check=True).stdout.strip()
    git(lane, "update-index", "--cacheinfo", f"100644,{blob},{path}")
    git(lane, "update-index", "--skip-worktree", path)
    git(lane, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", message)


def _rework(built: Built, index: int) -> None:
    lane = _lane_worktree(built, index)
    if index == 2:
        # A: lane-b builds on lane-a and rewrites lane-a's line (a dependent lane's later rewrite).
        git(lane, "merge", "-q", "--no-ff", "--no-edit", _lane_branch(built, 1))
        (lane / "src" / "one.py").write_text("X = 10\n", encoding="utf-8")
        git(lane, "add", "src/one.py")
        git(lane, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", "feat(WP02): rewrite WP01's line")
    if index == 3:
        # C: lane-c's snapshot differs from the coordination branch's, so consolidate auto-rebases it.
        snapshot = f"{built.rel}/status.json"
        rematerialized = json.dumps(json.loads(git(lane, "show", f"HEAD:{snapshot}")), indent=4) + "\n"
        _commit_blob(lane, snapshot, rematerialized, "chore: rematerialized snapshot")


def _planning_edit(built: Built) -> None:
    """B: a planning edit on the coordination branch after every lane's last sync."""
    spec = built.coord_worktree / built.rel / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nEdited after the last sync.\n", encoding="utf-8")
    _commit_all(built.coord_worktree, "spec edit after the last sync")


@pytest.fixture(scope="module")
def reworked(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Built, subprocess.CompletedProcess[str]]]:
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        built = build(tmp_path_factory.mktemp("landing-proof-7747-reworked"), after_lane_commit=_rework, after_approvals=_planning_edit)
        yield built, consolidate(built)


def _lane_c_tip(block: list[str]) -> str:
    """The lane-c tip cleanup judged: its recreate hint when removed, its remedy's SHA when kept."""
    text = "\n".join(block)
    start = text.index("lane-c")
    match = re.search(r"\b[0-9a-f]{12,40}\b", text[start:])
    assert match, text
    return match.group(0)


def test_the_reworked_mission_reproduces_the_three_shapes(reworked: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    """Lane-b rewrote lane-a's line, the spec moved after the last sync, and consolidate auto-rebased lane-c."""
    built, proc = reworked
    _ok(proc)
    assert git(built.root, "show", "work:src/one.py") == "X = 10"
    assert "Edited after the last sync." in git(built.root, "show", f"work:{built.rel}/spec.md")
    tip = _lane_c_tip(_cleanup_block(proc.stdout))
    subject = git(built.root, "log", "-1", "--format=%s", tip)
    assert subject.startswith("auto-rebase(lane=lane-c)"), subject
    # C's dogfood signature: the merge driver's status.json is neither parent's version.
    snapshot = f"{built.rel}/status.json"
    merged = git(built.root, "rev-parse", f"{tip}:{snapshot}")
    parents = [git(built.root, "rev-parse", f"{tip}^{n}:{snapshot}") for n in (1, 2)]
    assert merged not in parents, (merged, parents)


def test_every_lane_of_the_reworked_mission_is_removed(reworked: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = reworked
    _ok(proc)
    block = _cleanup_block(proc.stdout)
    assert not [line for line in block if line.lstrip().startswith("Kept")], "\n".join(block)
    assert {line.split()[1] for line in block if line.lstrip().startswith("Removed")} == set(_LANES), "\n".join(block)
    assert git(built.root, "branch", "--list", f"kitty/mission-{built.slug}-lane-*") == ""
