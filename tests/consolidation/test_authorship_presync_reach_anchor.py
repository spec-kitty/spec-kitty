"""The authorship walk keeps a lane-spine merge the pre-sync approval stamp reaches (#7802).

In an integrator clone the approval's ``lane_head`` is the reviewer's unpushed sync
merge, absent here. Before this fix ``_drop_unreviewed_merges`` only knew that stamp,
so every earlier merge on the lane spine (a lifecycle sync, a reviewed merge) was
dropped from the authored content although the pre-sync stamp, which the lane does
hold, reaches it. The pre-sync stamp is an ancestor of ``lane_head``, so adding it as
a reach anchor never keeps a merge ``lane_head`` would not keep.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.consolidation.reconciliation_authorship import (
    _approved_stamps,
    _drop_unreviewed_merges,
    _PresenceScope,
)

pytestmark = pytest.mark.fast

_ABSENT = "f" * 40  # the reviewer's sync merge: never fetched into this clone


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def lane_with_merge(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "switch", "-q", "-c", "coord")
    (repo / "plan.txt").write_text("plan\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "coord work")
    _git(repo, "switch", "-q", "main")
    _git(repo, "switch", "-q", "-c", "lane")
    (repo / "a.txt").write_text("lane\n")
    _git(repo, "commit", "-q", "-am", "lane work")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "coord")
    merge = _git(repo, "rev-parse", "HEAD")
    (repo / "b.txt").write_text("more\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "implementer tip X")
    tip = _git(repo, "rev-parse", "HEAD")
    return repo, merge, tip


def _presence(stamp: str | None, presync: str | None) -> _PresenceScope:
    return _PresenceScope(
        base="unused",
        carried=frozenset(),
        lane_bases={},
        canceled=frozenset(),
        approval_stamps={"WP01": stamp},
        approval_presync_stamps={"WP01": presync},
    )


def test_presync_stamp_keeps_an_earlier_lane_merge(lane_with_merge: tuple[Path, str, str]) -> None:
    repo, merge, tip = lane_with_merge
    spine = _git(repo, "rev-list", "--first-parent", "lane").splitlines()
    lane = SimpleNamespace(lane_id="lane-a", wp_ids=("WP01",))
    stamps = _approved_stamps(lane, {"WP01": {"lane": "approved"}}, _presence(_ABSENT, tip))

    kept = _drop_unreviewed_merges(repo, spine, stamps)

    assert merge in kept


def test_without_a_presync_stamp_the_absent_stamp_still_drops_the_merge(lane_with_merge: tuple[Path, str, str]) -> None:
    """Positive control on the same fixture: an absent ``lane_head`` alone reaches nothing."""
    repo, merge, _tip = lane_with_merge
    spine = _git(repo, "rev-list", "--first-parent", "lane").splitlines()
    lane = SimpleNamespace(lane_id="lane-a", wp_ids=("WP01",))
    stamps = _approved_stamps(lane, {"WP01": {"lane": "approved"}}, _presence(_ABSENT, None))

    assert merge not in _drop_unreviewed_merges(repo, spine, stamps)
