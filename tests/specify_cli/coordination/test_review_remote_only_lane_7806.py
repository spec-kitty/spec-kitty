"""Repro #7806 — review in a teammate's clone refuses a lane branch that exists only on the remote.

The author implements WP01, moves it to ``for_review`` and pushes every branch.
A teammate clones the repository: the lane branch then exists in the clone only
as ``refs/remotes/origin/<lane>``. ``agent action review WP01`` refused with
``LANE_AUTO_REBASE_FAILED ... is not a local branch``, because nothing created
the local lane head before the review claim synced the lane.

Built on PR #7804's two-clone fixture (``test_coord_clone_writer_5936``: real
``spec-kitty init``, ``agent mission create``, ``implement``, ``move-task``, a
bare origin and a real ``git clone``). The CLI runs from this checkout's
``src`` (``python -m specify_cli.__init__`` with ``PYTHONPATH`` set by the
fixture), never an installed ``spec-kitty``.

Arms:

* the review succeeds and the lane is a local head that tracks ``origin``;
* fail-closed: with no ref for the lane anywhere in the clone, review refuses
  and creates nothing;
* destroyed lane: a recorded lane work tip that the tracking ref does not
  contain refuses with ``DESTROYED_LANE`` and creates nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.specify_cli.coordination.test_coord_clone_writer_5936 import (
    _has_local_head,
    _must,
    _run,
    _sk,
    _Team,
    _teammate,
    team,
)

__all__ = ["team"]  # the module-scoped two-clone fixture, re-exported for pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression, pytest.mark.slow, pytest.mark.non_sandbox]


def _lane(team: _Team) -> str:
    return f"{team.coord_branch}-lane-a"


def _review(team: _Team, clone: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = _sk(env or team.env, clone, "agent", "action", "review", "WP01", "--agent", "teammate", "--mission", team.slug)
    return proc.returncode, proc.stdout + proc.stderr


def _assert_lane_remote_only(team: _Team, clone: Path) -> None:
    assert not _has_local_head(team.env, clone, _lane(team)), "fixture precondition: no local lane head"
    tracking = _run(team.env, clone, "git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{_lane(team)}")
    assert tracking.returncode == 0, "fixture precondition: the clone carries the lane's remote-tracking ref"


def test_review_creates_the_remote_only_lane_as_a_tracking_branch(team: _Team, tmp_path: Path) -> None:
    """Review in a fresh teammate clone creates the lane from origin's tracking ref, with ``--track``, and succeeds."""
    clone = _teammate(team, tmp_path)
    _assert_lane_remote_only(team, clone)

    code, output = _review(team, clone)

    assert code == 0, f"review refused in the teammate clone:\n{output[-3000:]}"
    assert "is not a local branch" not in output
    lane = _lane(team)
    assert _has_local_head(team.env, clone, lane)
    upstream = _run(team.env, clone, "git", "rev-parse", "--abbrev-ref", f"{lane}@{{upstream}}")
    assert upstream.stdout.strip() == f"origin/{lane}", upstream.stdout + upstream.stderr
    remote = _run(team.env, clone, "git", "rev-parse", f"refs/remotes/origin/{lane}").stdout.strip()
    local = _run(team.env, clone, "git", "rev-parse", f"refs/heads/{lane}").stdout.strip()
    # The review claim may add its own sync commit; the lane must descend from origin's tip, never fork from main.
    assert _run(team.env, clone, "git", "merge-base", "--is-ancestor", remote, local).returncode == 0


def test_review_refuses_when_the_clone_has_no_ref_for_the_lane(team: _Team, tmp_path: Path) -> None:
    """Fail-closed: no local head and no tracking ref (the origin check off, so nothing is fetched) refuses."""
    clone = _teammate(team, tmp_path)
    lane = _lane(team)
    _must(_run(team.env, clone, "git", "update-ref", "-d", f"refs/remotes/origin/{lane}"), "drop lane tracking ref")
    env = {**team.env, "SPEC_KITTY_ORIGIN_CHECK": "off"}

    code, output = _review(team, clone, env)

    assert code != 0, output[-3000:]
    assert not _has_local_head(team.env, clone, lane)


def test_review_refuses_a_destroyed_lane_whose_tip_origin_lacks(team: _Team, tmp_path: Path) -> None:
    """A recorded lane work tip ahead of the tracking ref is stranded work: review refuses ``DESTROYED_LANE``."""
    clone = _teammate(team, tmp_path)
    lane = _lane(team)
    _assert_lane_remote_only(team, clone)
    tree = _run(team.env, clone, "git", "rev-parse", f"refs/remotes/origin/{lane}^{{tree}}").stdout.strip()
    parent = _run(team.env, clone, "git", "rev-parse", f"refs/remotes/origin/{lane}").stdout.strip()
    stranded = _must(_run(team.env, clone, "git", "commit-tree", tree, "-p", parent, "-m", "stranded local work"), "commit-tree").stdout.strip()
    _must(_run(team.env, clone, "git", "update-ref", f"refs/spec-kitty/lane-tip/{lane}", stranded), "record lane tip")

    code, output = _review(team, clone)

    assert code != 0, output[-3000:]
    assert "DESTROYED_LANE" in output, output[-3000:]
    flat = " ".join(output.split())
    # The refusal names the review's own next step, not the implement command.
    assert "spec-kitty agent action review WP01" in flat, output[-3000:]
    assert "re-run the implement command" not in flat, output[-3000:]
    assert not _has_local_head(team.env, clone, lane)


def test_review_with_origin_check_off_creates_from_the_last_fetched_ref_and_warns(team: _Team, tmp_path: Path) -> None:
    """Origin check off: nothing is fetched, the lane is still created from the local tracking ref, with a warning."""
    clone = _teammate(team, tmp_path)
    _assert_lane_remote_only(team, clone)
    env = {**team.env, "SPEC_KITTY_ORIGIN_CHECK": "off"}

    code, output = _review(team, clone, env)

    assert code == 0, output[-3000:]
    assert "was not refreshed from the remote" in output, output[-3000:]
    assert _has_local_head(team.env, clone, _lane(team))
