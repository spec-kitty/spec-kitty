"""The lane landing proof that sets aside only Mission bookkeeping the lane never authored (#7747).

A ``lanes_with_coord`` lane syncs with the coordination branch (``implement`` merges it in), so it
carries older copies of Mission files the tool rewrites later: the status log, ``status.json``,
``meta.json`` and each work package prompt's claim frontmatter. A squash landing collapses the
coordination history into one commit, so the plain absorption proof keeps every such lane.

``is_absorbed_but_for_mission_bookkeeping`` holds when every lane difference is accounted for:

* outside ``kitty-specs/``: merging the tip changes nothing on the landing ref;
* the lane's own Mission status log: every lane event line is on the landing ref;
* ``status.json``, ``meta.json`` and ``tasks/WP*.md`` of the lane's own Mission: both sides have the
  file and the lane never authored its copy (no commit the lane made itself changed it, except a
  merge that took it whole from the merged-in side), or the landing ref's history holds that copy;
* a ``kitty-specs/`` file whose lane copy is the merge base's copy, or that the lane does not have
  and did not delete: nothing to lose.

Everything else, and any git error, is "not landed". A merge or merge-driver result is never
evidence for a ``kitty-specs/`` path (operator rulings 2026-11-22 and 2026-11-23, Option A).

Real repositories; no CLI.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from kernel.git import GitCommandError
from specify_cli.lanes import lane_tip
from specify_cli.lanes.lane_tip import is_absorbed, is_absorbed_but_for_mission_bookkeeping

pytestmark = [pytest.mark.git_repo]

_SLUG = "demo-01ABCDEF"
_OTHER_SLUG = "other-01ABCDEF"
_MD = f"kitty-specs/{_SLUG}"
_COORD = f"kitty/mission-{_SLUG}"
_LANE = f"kitty/mission-{_SLUG}-lane-a"
_TARGET = "refs/heads/main"
_SPEC = f"{_MD}/spec.md"
_META = f"{_MD}/meta.json"
_SNAPSHOT = f"{_MD}/status.json"
_LOG = f"{_MD}/status.events.jsonl"
_WP01 = f"{_MD}/tasks/WP01-work.md"
_WP02 = f"{_MD}/tasks/WP02-work.md"
_RETRO = f"{_MD}/retrospective.yaml"
_PRODUCT = "src/lane.py"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _write(cwd: Path, files: dict[str, str | None]) -> None:
    for rel, text in files.items():
        path = cwd / rel
        if text is None:
            _git(cwd, "rm", "-q", rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        _git(cwd, "add", rel)


def _commit(cwd: Path, message: str, files: dict[str, str | None]) -> str:
    _write(cwd, files)
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


def _wp(wp: str, body: str, **front: str) -> str:
    fields = "".join(f"{key}: {value}\n" for key, value in front.items())
    return f"---\nwork_package_id: {wp}\n{fields}---\n# {wp}\n\n{body}\n"


def _log(*event_ids: str) -> str:
    return "".join(f'{{"event_id": "{event_id}"}}\n' for event_id in event_ids)


@dataclass(frozen=True)
class Landed:
    """A squash-landed ``lanes_with_coord`` Mission whose lane is still in place."""

    root: Path
    coord: Path
    lane: Path

    def tip(self) -> str:
        return _git(self.lane, "rev-parse", "HEAD")

    def proof(self, slug: str = _SLUG) -> bool:
        proven: bool = is_absorbed_but_for_mission_bookkeeping(self.root, self.tip(), _TARGET, slug)
        return proven


def _init(root: Path) -> None:
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "init", {".gitignore": ".worktrees/\n", "README.md": "base\n"})


def _land(root: Path, coord: Path, lane: Path) -> None:
    """The squash landing: coordination tip + lane product, then the post-landing bookkeeping."""
    _git(root, "checkout", "-q", _COORD, "--", "kitty-specs")
    _git(root, "checkout", "-q", _LANE, "--", _PRODUCT)
    _git(root, "commit", "-q", "-m", "squash merge of mission")
    _commit(
        root,
        "record done transitions",
        {
            _META: '{"v": 4, "merged_at": "now"}\n',
            _SNAPSHOT: '{"v": 4}\n',
            _LOG: _log("e1", "e2", "e3", "e4"),
            _RETRO: "retro: true\n",
        },
    )


@pytest.fixture
def landed(tmp_path: Path) -> Landed:
    """Coordination branch, a lane that synced with it once and committed its product, a squash landing."""
    root = tmp_path / "repo"
    _init(root)
    coord = root / ".worktrees" / "coord"
    _git(root, "worktree", "add", "-q", "-b", _COORD, str(coord))
    _commit(
        coord,
        "tasks",
        {
            _SPEC: "# spec\n",
            _META: '{"v": 1}\n',
            _SNAPSHOT: '{"v": 1}\n',
            _LOG: _log("e1"),
            _WP01: _wp("WP01", "Do the work."),
            _WP02: _wp("WP02", "Do the other work."),
        },
    )
    lane = root / ".worktrees" / "lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(lane), _COORD)
    _commit(
        coord,
        "WP01 claimed",
        {_META: '{"v": 2}\n', _SNAPSHOT: '{"v": 2}\n', _LOG: _log("e1", "e2"), _WP01: _wp("WP01", "Do the work.", agent="claude")},
    )
    _git(lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the implement sync
    _commit(lane, "feat(WP01)", {_PRODUCT: "x = 1\n"})
    _commit(
        coord,
        "WP02 claimed",
        {_META: '{"v": 3}\n', _SNAPSHOT: '{"v": 3}\n', _LOG: _log("e1", "e2", "e3"), _WP02: _wp("WP02", "Do the other work.", agent="claude")},
    )
    _land(root, coord, lane)
    return Landed(root=root, coord=coord, lane=lane)


# --- the #7747 shape ------------------------------------------------------------------------


def test_a_squash_landed_lane_is_landed_but_for_its_mission_bookkeeping(landed: Landed) -> None:
    assert not is_absorbed(landed.root, landed.tip(), _TARGET, base=None)  # the #7747 refusal
    assert landed.proof()
    assert _git(landed.lane, "ls-tree", "--name-only", "HEAD", _RETRO) == ""  # a file only the target has: nothing to lose


def test_a_lane_tip_on_the_landing_ref_is_landed(landed: Landed) -> None:
    _git(landed.root, "merge", "-q", "-s", "ours", "--no-edit", _LANE)  # the landing ref now reaches the tip
    assert landed.proof()


def test_another_missions_bookkeeping_is_not_set_aside(landed: Landed) -> None:
    assert not landed.proof(_OTHER_SLUG)


def test_an_unknown_tip_fails_closed(landed: Landed) -> None:
    assert not is_absorbed_but_for_mission_bookkeeping(landed.root, "0" * 40, _TARGET, _SLUG)


def test_an_unknown_landing_ref_fails_closed(landed: Landed) -> None:
    assert not is_absorbed_but_for_mission_bookkeeping(landed.root, landed.tip(), "refs/heads/nope", _SLUG)


# --- what the lane authored is never set aside ----------------------------------------------


def test_an_edit_of_its_own_work_package_body_keeps_the_lane(landed: Landed) -> None:
    _commit(landed.lane, "rewrite the prompt", {_WP01: _wp("WP01", "Do the work, differently.", agent="claude")})
    assert not landed.proof()


def test_product_code_not_on_the_target_keeps_the_lane(landed: Landed) -> None:
    _commit(landed.lane, "late work", {"src/late.py": "y = 2\n"})
    assert not landed.proof()


def test_an_event_only_the_lane_holds_keeps_the_lane(landed: Landed) -> None:
    _commit(landed.lane, "a lane-only event", {_LOG: _log("e1", "e2", "lane-only")})
    assert not landed.proof()


def test_a_bookkeeping_file_the_lane_deleted_keeps_the_lane(landed: Landed) -> None:
    _commit(landed.lane, "drop meta", {_META: None})
    assert not landed.proof()


def test_a_merge_that_resolved_a_mission_file_by_hand_keeps_the_lane(landed: Landed) -> None:
    """A sync merge whose result is neither side's version is the lane's own authoring."""
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-commit", _COORD)
    (landed.lane / _WP02).write_text(_wp("WP02", "Resolved by hand."), encoding="utf-8")
    _git(landed.lane, "add", _WP02)
    _git(landed.lane, "commit", "-q", "--no-edit")
    assert not landed.proof()


def test_a_merge_driver_result_is_never_evidence_for_a_mission_file(landed: Landed) -> None:
    """A driver that keeps the target's side hides a lane edit from merge-tree; the proof does not read it."""
    _commit(landed.root, "merge attributes", {".gitattributes": "kitty-specs/** merge=keeptarget\n"})
    _git(landed.root, "config", "merge.keeptarget.driver", "true")
    _commit(landed.lane, "the lane's own prompt edit", {_WP01: _wp("WP01", "Lane-only change.", agent="claude")})
    _commit(landed.root, "the target's prompt edit", {_WP01: _wp("WP01", "Target change.", agent="claude", lane="done")})
    assert is_absorbed(landed.root, landed.tip(), _TARGET, base=None)  # control: the driver makes it look landed
    assert not landed.proof()


def test_a_planning_file_the_lane_wrote_keeps_the_lane(landed: Landed) -> None:
    """Ruling B (2026-11-24) sets aside only what the lane never wrote: its own spec edit keeps it."""
    _commit(landed.lane, "the lane edits the spec", {_SPEC: "# spec, lane edit\n"})
    assert not landed.proof()


# --- operator ruling 2026-11-24 (B, C): the lane's own changes only -------------------------


def test_an_older_planning_file_the_lane_never_wrote_is_set_aside(landed: Landed) -> None:
    """B: a planning edit on the coordination branch after the lane's last sync does not keep the lane."""
    _commit(landed.root, "spec edited after the last sync", {_SPEC: "# spec, revised\n"})
    assert landed.proof()


def test_another_missions_planning_file_is_not_set_aside(landed: Landed) -> None:
    """B covers the lane's own Mission only: another Mission's file both sides moved keeps it."""
    other = f"kitty-specs/{_OTHER_SLUG}/spec.md"
    _commit(landed.coord, "another Mission's spec", {other: "# other\n"})
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)
    _commit(landed.root, "that Mission moves on", {other: "# other, revised\n"})
    assert not landed.proof()


def test_a_snapshot_a_merge_rematerialized_is_set_aside_when_its_log_landed(landed: Landed) -> None:
    """C: status.json is a projection of the log; a merge (or driver) result for it is not read."""
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-commit", _COORD)
    (landed.lane / _SNAPSHOT).write_text('{"v": "rematerialized"}\n', encoding="utf-8")
    _git(landed.lane, "add", _SNAPSHOT)
    _git(landed.lane, "commit", "-q", "--no-edit")
    assert landed.proof()


def test_a_snapshot_the_lane_committed_is_set_aside_when_its_log_landed(landed: Landed) -> None:
    """C: authorship of status.json is never read."""
    _commit(landed.lane, "the lane writes the snapshot", {_SNAPSHOT: '{"v": "lane"}\n'})
    assert landed.proof()


def test_a_snapshot_whose_log_did_not_land_keeps_the_lane(landed: Landed) -> None:
    """C: the snapshot is judged by its log, so a lane-only event keeps it."""
    _commit(landed.lane, "a lane-only event and its snapshot", {_LOG: _log("e1", "e2", "lane-only"), _SNAPSHOT: '{"v": "lane"}\n'})
    assert not landed.proof()


# --- what holds -----------------------------------------------------------------------------


def test_a_lane_version_the_target_history_holds_is_set_aside(landed: Landed) -> None:
    """A lane-authored bookkeeping version the target recorded, then moved past, loses nothing."""
    _commit(landed.lane, "lane writes meta", {_META: '{"v": "lane"}\n'})
    _commit(landed.root, "target records it", {_META: '{"v": "lane"}\n'})
    _commit(landed.root, "target moves on", {_META: '{"v": 5}\n'})
    assert landed.proof()


def test_a_mission_file_only_the_target_moved_since_the_merge_base_is_nothing_to_lose(tmp_path: Path) -> None:
    """Another Mission's file the target changed after the lane forked: the lane's copy is the base's."""
    root = tmp_path / "repo"
    _init(root)
    other = f"kitty-specs/{_OTHER_SLUG}/spec.md"
    _commit(root, "another Mission's spec", {other: "# other\n"})
    lane = root / ".worktrees" / "lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(lane))
    _commit(lane, "feat(WP01)", {_PRODUCT: "x = 1\n"})
    _git(root, "checkout", "-q", _LANE, "--", _PRODUCT)
    _commit(root, "land the lane, then another Mission moves on", {other: "# other, revised\n", _META: '{"v": 1}\n'})
    tip = _git(lane, "rev-parse", "HEAD")
    assert is_absorbed_but_for_mission_bookkeeping(root, tip, _TARGET, _SLUG)
    _commit(lane, "the lane edits that file after all", {other: "# other, lane edit\n"})
    assert not is_absorbed_but_for_mission_bookkeeping(root, _git(lane, "rev-parse", "HEAD"), _TARGET, _SLUG)


# --- review folds (WP01 review, 2026-11-23): the clauses no other case reaches ----------------


def test_a_lane_that_deleted_its_own_status_log_is_landed(landed: Landed) -> None:
    """The stated exception to "a lane-made deletion keeps the lane" (#6736): the log is append-only and
    every event it held is on the target, so a lane without a copy has none to lose."""
    _commit(landed.lane, "drop the log copy", {_LOG: None})
    assert landed.proof()


def test_a_bookkeeping_file_the_lane_wrote_and_the_target_dropped_keeps_the_lane(landed: Landed) -> None:
    """A lane-written copy of a file the target no longer has is not set aside."""
    _commit(landed.lane, "lane writes meta", {_META: '{"v": "lane"}\n'})
    _commit(landed.root, "the target drops meta.json", {_META: None})
    assert not landed.proof()


def test_a_synced_bookkeeping_file_the_target_dropped_is_set_aside(landed: Landed) -> None:
    """Ruling B (2026-11-24): a copy the lane only synced is not the lane's change, whatever the target did."""
    _commit(landed.root, "the target drops meta.json", {_META: None})
    assert landed.proof()


def test_another_missions_snapshot_is_not_set_aside(landed: Landed) -> None:
    """status.json and meta.json are set aside only for the lane's own Mission."""
    other_snapshot = f"kitty-specs/{_OTHER_SLUG}/status.json"
    _commit(landed.coord, "another Mission's snapshot", {other_snapshot: '{"v": 1}\n'})
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)
    _commit(landed.root, "that Mission moves on", {other_snapshot: '{"v": 2}\n'})
    assert not landed.proof()


@pytest.mark.parametrize(
    "failure",
    [GitCommandError(argv=("merge-tree",), cwd=Path("."), returncode=128, stderr="boom"), OSError("git did not start")],
    ids=["git-error", "os-error"],
)
def test_a_git_failure_fails_closed(landed: Landed, monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    def broken(*_args: object, **_kwargs: object) -> object:
        raise failure

    monkeypatch.setattr(lane_tip, "merge_tree", broken)
    assert not landed.proof()


def test_a_mission_file_the_lane_lost_through_a_sync_merge_is_nothing_to_lose(tmp_path: Path) -> None:
    """The coordination branch deleted a file; the lane took that deletion whole from its sync merge."""
    root = tmp_path / "repo"
    _init(root)
    legacy = f"{_MD}/legacy.md"
    _commit(root, "a legacy Mission file", {legacy: "old\n"})
    coord = root / ".worktrees" / "coord"
    _git(root, "worktree", "add", "-q", "-b", _COORD, str(coord))
    _commit(coord, "the coordination branch drops it", {legacy: None})
    lane = root / ".worktrees" / "lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(lane), "main")
    _git(lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the implement sync
    _commit(lane, "feat(WP01)", {_PRODUCT: "x = 1\n"})
    _git(root, "checkout", "-q", _LANE, "--", _PRODUCT)
    _git(root, "commit", "-q", "-m", "land the lane's product")
    assert is_absorbed_but_for_mission_bookkeeping(root, _git(lane, "rev-parse", "HEAD"), _TARGET, _SLUG)


def test_is_ancestor_is_true_only_when_git_confirms_it(tmp_path: Path) -> None:
    """The ancestry check shared with ``doctor workspaces``: an unknown revision is no proof."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "T")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "one")
    first = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "two")
    assert lane_tip.is_ancestor(tmp_path, first, "refs/heads/main")
    assert not lane_tip.is_ancestor(tmp_path, _git(tmp_path, "rev-parse", "HEAD"), first)
    assert not lane_tip.is_ancestor(tmp_path, "0" * 40, "refs/heads/main")


# --- R24 adversarial squad folds (2026-11-24) -----------------------------------------------------


def test_a_non_ascii_mission_file_the_lane_wrote_keeps_the_lane(landed: Landed) -> None:
    """A path git quotes (core.quotePath) is still the lane's authoring: authorship reads NUL-separated names."""
    _commit(landed.lane, "lane notes", {f"{_MD}/notes-\u00e9.md": "lane notes\n"})
    assert not landed.proof()


def test_a_mission_sharing_the_slug_prefix_is_another_mission(landed: Landed) -> None:
    """``demo-01ABCDEF-2`` is not under ``demo-01ABCDEF/``: its files keep the other-Mission rule."""
    sibling = f"kitty-specs/{_SLUG}-2/spec.md"
    _commit(landed.coord, "a sibling Mission's spec", {sibling: "# sibling\n"})
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)
    _commit(landed.root, "the sibling Mission moves on", {sibling: "# sibling, revised\n"})
    assert not landed.proof()


def test_a_lane_commit_the_coordination_branch_merged_back_is_still_the_lanes(landed: Landed) -> None:
    """The lane's own commit stays authored after the coordination branch merged it and the lane resynced."""
    research = f"{_MD}/research.md"
    _commit(landed.root, "research baseline", {research: "r0\n"})
    _commit(landed.coord, "research baseline", {research: "r0\n"})
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)
    _commit(landed.lane, "lane research", {research: "LANE NOTES\n"})
    _git(landed.coord, "merge", "-q", "--no-ff", "--no-edit", _LANE)
    _git(landed.lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the resync; the landing keeps "r0"
    assert not landed.proof()


def test_a_status_log_the_lane_only_synced_is_set_aside_when_the_landing_rewrote_it(landed: Landed) -> None:
    """B for the log: a copy the lane never wrote holds no lane event, even when the landing's log no longer has its lines."""
    _commit(landed.root, "the landing's log is rewritten", {_LOG: _log("x1"), _SNAPSHOT: '{"v": "x"}\n'})
    assert landed.proof()
