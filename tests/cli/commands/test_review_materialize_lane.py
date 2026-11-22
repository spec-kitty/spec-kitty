"""``_materialize_review_lane`` in process (#7806): every arm on a real git repository.

The lane exists in the clone only as ``refs/remotes/origin/<lane>``, planted with
``update-ref`` (no network). The end-to-end two-clone repro lives in
``tests/specify_cli/coordination/test_review_remote_only_lane_7806.py``; these
arms cover the helper's own branches.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from specify_cli.cli.commands.agent import workflow
from specify_cli.lanes.lane_tip import tip_ref

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_LANE = "kitty/mission-demo-01ABCDEF-lane-a"
_TRACKING = f"refs/remotes/origin/{_LANE}"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n", encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A clone whose only ``origin`` holds the lane as a tracking ref and no local head."""
    root = tmp_path / "clone"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    _commit(root, "base.txt")
    _git(root, "remote", "add", "origin", str(tmp_path / "origin.git"))
    _git(root, "update-ref", _TRACKING, "HEAD")
    return root


def _workspace() -> Any:
    return SimpleNamespace(lane_id="lane-a")


def _local_head(repo: Path) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{_LANE}"], capture_output=True).returncode == 0


def test_creates_the_lane_as_a_tracking_branch(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workflow._materialize_review_lane(_workspace(), repo, "WP01", _LANE, refreshed=True)

    assert _git(repo, "rev-parse", f"refs/heads/{_LANE}") == _git(repo, "rev-parse", _TRACKING)
    assert _git(repo, "config", f"branch.{_LANE}.remote") == "origin"
    out = capsys.readouterr().out
    assert f"Created {_LANE} from origin/{_LANE} (tracking)." in out
    assert "was not refreshed" not in out


def test_an_unrefreshed_ref_warns_before_the_creation(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workflow._materialize_review_lane(_workspace(), repo, "WP01", _LANE, refreshed=False)

    out = capsys.readouterr().out
    assert f"Warning: origin/{_LANE} was not refreshed from the remote; creating {_LANE} from it as last fetched." in out
    assert _local_head(repo)


def test_an_existing_local_head_is_left_alone(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repo, "branch", _LANE, "main")
    own = _commit(repo, "other.txt")
    _git(repo, "branch", "-f", _LANE, own)

    workflow._materialize_review_lane(_workspace(), repo, "WP01", _LANE, refreshed=False)

    assert _git(repo, "rev-parse", f"refs/heads/{_LANE}") == own
    assert capsys.readouterr().out == ""


def test_no_tracking_ref_creates_nothing(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repo, "update-ref", "-d", _TRACKING)

    workflow._materialize_review_lane(_workspace(), repo, "WP01", _LANE, refreshed=True)

    assert not _local_head(repo)
    assert capsys.readouterr().out == ""


def test_a_tip_the_tracking_ref_contains_still_creates(repo: Path) -> None:
    _git(repo, "update-ref", tip_ref(_LANE), _TRACKING)

    workflow._materialize_review_lane(_workspace(), repo, "WP01", _LANE, refreshed=True)

    assert _local_head(repo)


def test_a_stranded_lane_tip_refuses_with_the_review_next_step(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repo, "checkout", "-q", "-b", "scratch")
    stranded = _commit(repo, "stranded.txt")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "update-ref", tip_ref(_LANE), stranded)

    with pytest.raises(typer.Exit) as raised:
        workflow._materialize_review_lane(_workspace(), repo, "WP01", _LANE, refreshed=True)

    assert raised.value.exit_code == 1
    out = " ".join(capsys.readouterr().out.split())
    assert "DESTROYED_LANE" in out
    assert "spec-kitty agent action review WP01" in out
    assert stranded[:7] in out
    assert not _local_head(repo), "a refusal creates nothing"


@pytest.mark.parametrize(
    ("kind", "exists", "expected_ref", "warns"),
    [
        pytest.param("create_from", False, _TRACKING, False, id="created-from-the-refreshed-ref"),
        pytest.param("keep", False, None, True, id="kept-ref-not-refreshed"),
        pytest.param("create_from", True, None, False, id="existing-worktree"),
    ],
)
def test_reconcile_materializes_the_lane_and_names_its_start_ref(
    kind: str, exists: bool, expected_ref: str | None, warns: bool, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The review prep creates a missing local lane head whatever its freshness plan, warning when the ref was not refreshed."""
    from specify_cli.git import origin_freshness

    action = SimpleNamespace(kind=origin_freshness.ReviewLaneKind(kind), remote_ref=_TRACKING, message=None)
    monkeypatch.setattr(origin_freshness, "resolve_origin_check_mode", lambda _value: SimpleNamespace(warning=None))
    monkeypatch.setattr(origin_freshness, "plan_review_lane", lambda *_args: action)
    workspace: Any = SimpleNamespace(lane_id="lane-a", branch_name=_LANE, runs_in_checkout_root=False, is_husk=False, exists=exists)

    assert workflow._reconcile_review_lane(workspace, repo, "WP01", None) == expected_ref
    assert _local_head(repo)
    assert ("was not refreshed" in capsys.readouterr().out) is warns
