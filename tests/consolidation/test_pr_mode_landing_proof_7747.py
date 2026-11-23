"""``accept --mode pr`` lane cleanup judges a Mission lane with the shared landing proof (#7747, G1).

Operator ruling 2026-11-23 (3A): the pr-mode cleanup used to build its lane remover without the
Mission slug, so it kept the plain absorption proof. A ``lanes_with_coord`` lane that synced with the
coordination branch carries older copies of the Mission's bookkeeping. While the PR head carries the
coordination history the lane merged, the plain three-way proof already passes; when the pushed head
does not (it was squashed or rebased before it was pushed), the lane was kept with
``NOT_LANDED_ON_NAMED_REMOTE``.

In-matrix home: the ``consolidation`` module row's roots include ``src/specify_cli/acceptance/**``
(``tests/acceptance/`` is nightly-only). Real repositories; the process probe is injected.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from specify_cli.acceptance import pr_mode_lane_cleanup
from specify_cli.consolidation.lane_cleanup import LaneCleanupOutcome
from specify_cli.git.destructive_guard import NOT_LANDED_ON_NAMED_REMOTE
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import predict_lane_worktree
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.git_repo]

_SLUG = "demo-01ABCDEF"
_PR_HEAD = f"kitty/mission-{_SLUG}"
_COORD = f"kitty/coord-{_SLUG}"
_MD = f"kitty-specs/{_SLUG}"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, message: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
        (cwd / rel).write_text(text, encoding="utf-8")
        _git(cwd, "add", rel)
    _git(cwd, "commit", "-q", "-m", message)


def _idle(paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


def _manifest() -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_PR_HEAD,
        target_branch="main",
        lanes=[lane],
        computed_at="2026-11-23T00:00:00+00:00",
        computed_from="test",
    )


@pytest.fixture
def pushed(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """``(root, feature_dir, lane worktree, PR head worktree)``: the pushed head squashed the coordination tip and the lane's work."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "base", {".gitignore": ".worktrees/\n", "base.py": "x = 1\n"})
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "-u", "origin", "main")
    manifest = _manifest()
    feature_dir = root / _MD
    feature_dir.mkdir(parents=True)
    write_lanes_json(feature_dir, manifest)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "target_branch": "main"}), encoding="utf-8")

    coord = root.parent / "coord"
    _git(root, "worktree", "add", "-q", "-b", _COORD, str(coord))
    _commit(coord, "tasks", {f"{_MD}/status.json": '{"v": 1}\n', f"{_MD}/tasks/WP01-x.md": "---\nwork_package_id: WP01\n---\nwork\n"})
    lane = Path(predict_lane_worktree(root, _SLUG, "lane-a")[0])
    branch = lane_created_branch(manifest, "lane-a")
    _git(root, "worktree", "add", "-q", "-b", branch, str(lane), _COORD)
    _commit(coord, "WP01 claimed", {f"{_MD}/status.json": '{"v": 2}\n', f"{_MD}/tasks/WP01-x.md": "---\nwork_package_id: WP01\nagent: claude\n---\nwork\n"})
    _git(lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the implement sync
    _commit(lane, "feat(WP01)", {"src/lane.py": "y = 2\n"})
    _commit(coord, "WP01 approved", {f"{_MD}/status.json": '{"v": 3}\n'})
    head = root.parent / "pr-head"
    _git(root, "worktree", "add", "-q", "-b", _PR_HEAD, str(head), "main")
    _git(head, "checkout", "-q", _COORD, "--", "kitty-specs")
    _git(head, "checkout", "-q", branch, "--", "src/lane.py")
    _git(head, "commit", "-q", "-m", "the Mission, squashed before the push")
    _git(head, "push", "-q", "origin", _PR_HEAD)
    _git(root, "fetch", "-q", "origin")
    return root, feature_dir, lane, head


def test_a_lane_whose_head_carries_its_work_is_removed(pushed: tuple[Path, Path, Path, Path]) -> None:
    root, feature_dir, lane, _head = pushed
    report = pr_mode_lane_cleanup(root, feature_dir, _PR_HEAD, probe=_idle)
    assert report is not None
    [result] = report.results
    assert result.outcome is LaneCleanupOutcome.REMOVED, result
    assert not lane.exists()


def test_a_lane_with_work_the_head_lacks_is_kept(pushed: tuple[Path, Path, Path, Path]) -> None:
    root, feature_dir, lane, _head = pushed
    _commit(lane, "late work", {"src/late.py": "z = 3\n"})
    report = pr_mode_lane_cleanup(root, feature_dir, _PR_HEAD, probe=_idle)
    assert report is not None
    [result] = report.results
    assert result.outcome is LaneCleanupOutcome.KEPT, result
    assert result.code == NOT_LANDED_ON_NAMED_REMOTE
    assert lane.exists()
