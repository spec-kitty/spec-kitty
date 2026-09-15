"""Integration tests for the stale-lane auto-rebase orchestrator.

Covers WP08 / T044 (happy path — two-lane additive merge) and T045 (negative
path — semantic conflict).

The orchestrator operates inside a git worktree and shells out to ``git``;
these tests construct a minimal real git repository in ``tmp_path``.
"""

from __future__ import annotations

from collections.abc import Callable

import json
import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from specify_cli.lanes import auto_rebase
from specify_cli.lanes.auto_rebase import AutoRebaseReport, attempt_auto_rebase
from specify_cli.lanes.models import ExecutionLane

pytestmark = pytest.mark.git_repo
REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=check
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with main + mission branches and one shared file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@spec-kitty"], repo)
    _run(["git", "config", "user.name", "test"], repo)
    # Seed with a pyproject.toml.
    seed = (
        "[project]\n"
        'name = "demo"\n'
        "dependencies = [\n"
        '  "alpha",\n'
        '  "bravo",\n'
        "]\n"
    )
    (repo / "pyproject.toml").write_text(seed)
    _run(["git", "add", "pyproject.toml"], repo)
    _run(["git", "commit", "-m", "seed"], repo)
    return repo


def _make_lane() -> ExecutionLane:
    return ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("pyproject.toml",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _make_lane_worktree(repo: Path, mission_slug: str, lane_id: str, branch: str) -> Path:
    """Create a lane worktree following the spec-kitty path convention."""
    worktree = repo / ".worktrees" / f"{mission_slug}-{lane_id}"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "worktree", "add", "-b", branch, str(worktree), "main"], repo)
    return worktree


def _write_pyproject(path: Path, deps: list[str]) -> None:
    body = "[project]\nname = \"demo\"\ndependencies = [\n"
    for d in deps:
        body += f'  "{d}",\n'
    body += "]\n"
    path.write_text(body)


def _status_event(
    event_id: str,
    *,
    at: str,
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
) -> dict[str, object]:
    return {
        "actor": "tester",
        "at": at,
        "event_id": event_id,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": from_lane,
        "mission_slug": mission_slug,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _write_status_events(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def _write_event_log_driver_script(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r})",
                "from specify_cli.status.event_log_merge import merge_event_log_files",
                "merge_event_log_files(",
                "    base_path=Path(sys.argv[1]),",
                "    ours_path=Path(sys.argv[2]),",
                "    theirs_path=Path(sys.argv[3]),",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _configure_event_log_merge_driver(repo: Path, script_path: Path) -> None:
    _run(
        [
            "git",
            "config",
            "--local",
            "merge.spec-kitty-event-log.name",
            "Spec Kitty event log union merge",
        ],
        repo,
    )
    _run(
        [
            "git",
            "config",
            "--local",
            "merge.spec-kitty-event-log.driver",
            f"{shlex.quote(sys.executable)} {shlex.quote(str(script_path))} %O %A %B",
        ],
        repo,
    )


def _configure_production_event_log_merge_driver(repo: Path) -> None:
    _run(
        [
            "git",
            "config",
            "--local",
            "merge.spec-kitty-event-log.name",
            "Spec Kitty event log union merge",
        ],
        repo,
    )
    _run(
        [
            "git",
            "config",
            "--local",
            "merge.spec-kitty-event-log.driver",
            "spec-kitty merge-driver-event-log %O %A %B",
        ],
        repo,
    )


class TestAutoRebaseAdditive:
    """T044 — Happy path: two lanes add distinct deps; auto-resolve."""

    def test_two_lane_additive_pyproject_merge(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "008-demo"
        mission_branch = f"kitty/mission-{mission_slug}"

        # Create the mission branch at main's tip.
        _run(["git", "branch", mission_branch, "main"], repo)

        # Lane A's branch — simulated past-merge state via the mission branch:
        # we directly add a dep on the mission branch.
        _run(["git", "checkout", mission_branch], repo)
        _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo", "charlie"])
        _run(["git", "add", "pyproject.toml"], repo)
        _run(["git", "commit", "-m", "mission: add charlie"], repo)
        _run(["git", "checkout", "main"], repo)

        # Lane B's branch with a different additive change.
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _write_pyproject(
            worktree_b / "pyproject.toml", ["alpha", "bravo", "delta"]
        )
        _run(["git", "add", "pyproject.toml"], worktree_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _run(["git", "commit", "-m", "lane: add delta"], worktree_b)

        # Now Lane B is stale — its pyproject.toml conflicts with mission's.
        lane = _make_lane()
        report = attempt_auto_rebase(
            lane=lane,
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert isinstance(report, AutoRebaseReport)
        assert report.attempted is True
        assert report.succeeded is True, f"halt_reason={report.halt_reason}"
        assert report.halt_reason is None

        # Verify both deps survived.
        merged = (worktree_b / "pyproject.toml").read_text()
        data = tomllib.loads(merged)
        deps = data["project"]["dependencies"]
        # All four deps (alpha, bravo, charlie, delta) should be present.
        names = [d.split(">=")[0].split("==")[0].strip() for d in deps]
        for expected in ("alpha", "bravo", "charlie", "delta"):
            assert expected in names, f"expected {expected} in {names}"

        # Verify a merge commit landed with the expected message format.
        log = _run(
            ["git", "log", "-1", "--pretty=%s"], worktree_b, check=False
        )
        assert log.returncode == 0
        assert "auto-rebase(lane=lane-a)" in log.stdout
        assert "R-PYPROJECT-DEPS-UNION" in log.stdout

    def test_managed_planning_artifacts_are_resolved_deterministically(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-managed-artifacts"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        task_rel = mission_dir / "tasks" / "WP08-renderer-unit-tests.md"
        lanes_rel = mission_dir / "lanes.json"

        mission_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP08",
            from_lane="planned",
            to_lane="in_progress",
        )

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [mission_event])
        (repo / status_json_rel).write_text('{"stale": "mission"}\n', encoding="utf-8")
        (repo / task_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / task_rel).write_text("# WP08\ncoordination copy\n", encoding="utf-8")
        (repo / lanes_rel).write_text('{"coordination": true}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "mission: managed artifacts"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _write_status_events(worktree_b / status_events_rel, [lane_event])
        (worktree_b / status_json_rel).write_text('{"stale": "lane"}\n', encoding="utf-8")
        (worktree_b / task_rel).parent.mkdir(parents=True, exist_ok=True)
        (worktree_b / task_rel).write_text("# WP08\nlane copy\n", encoding="utf-8")
        (worktree_b / lanes_rel).write_text('{"coordination": false}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], worktree_b)
        _run(["git", "commit", "-m", "lane: managed artifacts"], worktree_b)

        lane = _make_lane()
        report = attempt_auto_rebase(
            lane=lane,
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        events = [
            json.loads(line)
            for line in (worktree_b / status_events_rel).read_text(encoding="utf-8").splitlines()
        ]
        assert [event["event_id"] for event in events] == [
            "01AAA000000000000000000001",
            "01BBB000000000000000000002",
        ]
        status = json.loads((worktree_b / status_json_rel).read_text(encoding="utf-8"))
        assert status["event_count"] == 2
        assert status["work_packages"]["WP08"]["lane"] == "in_progress"
        assert (worktree_b / task_rel).read_text(encoding="utf-8") == "# WP08\ncoordination copy\n"
        assert json.loads((worktree_b / lanes_rel).read_text(encoding="utf-8")) == {
            "coordination": True
        }

        rule_ids = {
            classification.resolution.rule_id
            for classification in report.classifications
            if hasattr(classification.resolution, "rule_id")
        }
        assert "R-STATUS-EVENTS-JSONL-UNION" in rule_ids
        assert "R-STATUS-JSON-REMATERIALIZE" in rule_ids
        assert "R-COORDINATION-ARTIFACT-THEIRS" in rule_ids

    def test_status_events_lane_delete_conflict_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-modify-delete"
        mission_branch = f"kitty/mission-{mission_slug}"
        status_events_rel = (
            Path("kitty-specs") / mission_slug / "status.events.jsonl"
        )
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "seed status events"], repo)
        _run(["git", "branch", mission_branch, "main"], repo)

        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: append status event"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        (worktree_b / status_events_rel).unlink()
        _run(["git", "add", str(status_events_rel)], worktree_b)
        _run(["git", "commit", "-m", "lane: delete status events"], worktree_b)
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "pre-existing lane-side deletion" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        assert not (worktree_b / status_events_rel).exists()
        assert "status.events.jsonl" not in _run(
            ["git", "status", "--porcelain"],
            worktree_b,
        ).stdout

    def test_status_events_coordination_delete_conflict_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-coordination-delete"
        mission_branch = f"kitty/mission-{mission_slug}"
        status_events_rel = (
            Path("kitty-specs") / mission_slug / "status.events.jsonl"
        )
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "seed status events"], repo)
        _run(["git", "branch", mission_branch, "main"], repo)

        _run(["git", "checkout", mission_branch], repo)
        (repo / status_events_rel).unlink()
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: delete status events"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _write_status_events(worktree_b / status_events_rel, [base_event, lane_event])
        _run(["git", "add", str(status_events_rel)], worktree_b)
        _run(["git", "commit", "-m", "lane: append status event"], worktree_b)
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "refusing status.events.jsonl deletion conflict" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        events = [
            json.loads(line)
            for line in (worktree_b / status_events_rel).read_text(encoding="utf-8").splitlines()
        ]
        assert [event["event_id"] for event in events] == [
            "01AAA000000000000000000001",
            "01CCC000000000000000000003",
        ]
        assert "status.events.jsonl" not in _run(
            ["git", "status", "--porcelain"],
            worktree_b,
        ).stdout

    def test_sparse_status_events_delete_conflict_reapplies_sparse_checkout(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-sparse-delete-conflict"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed sparse deletion status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: append status event"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        (repo / status_events_rel).unlink()
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "lane: delete status events"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _run(["git", "sparse-checkout", "init", "--no-cone"], worktree_b)
        _run(
            [
                "git",
                "sparse-checkout",
                "set",
                "--no-cone",
                "/*",
                f"!{status_events_rel.as_posix()}",
                f"!{status_json_rel.as_posix()}",
            ],
            worktree_b,
        )
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "pre-existing lane-side deletion" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()
        assert "status.events.jsonl" not in _run(
            ["git", "status", "--porcelain"],
            worktree_b,
        ).stdout

    def test_sparse_status_json_uses_index_status_events_when_hidden(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-sparse-status"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        (repo / ".gitattributes").write_text(
            "kitty-specs/**/status.events.jsonl merge=union\n",
            encoding="utf-8",
        )
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", ".gitattributes", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed sparse status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        (repo / status_json_rel).write_text('{"event_count": 2, "side": "mission"}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "mission: status artifacts"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        _write_status_events(repo / status_events_rel, [base_event, lane_event])
        (repo / status_json_rel).write_text('{"event_count": 2, "side": "lane"}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "lane: status artifacts"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _run(["git", "sparse-checkout", "init", "--no-cone"], worktree_b)
        _run(
            [
                "git",
                "sparse-checkout",
                "set",
                "--no-cone",
                "/*",
                f"!{status_events_rel.as_posix()}",
                f"!{status_json_rel.as_posix()}",
            ],
            worktree_b,
        )
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        committed_status = json.loads(
            _run(["git", "show", f"HEAD:{status_json_rel.as_posix()}"], worktree_b).stdout
        )
        committed_events = [
            json.loads(line)
            for line in _run(
                ["git", "show", f"HEAD:{status_events_rel.as_posix()}"],
                worktree_b,
            ).stdout.splitlines()
        ]
        assert {event["event_id"] for event in committed_events} == {
            "01AAA000000000000000000001",
            "01BBB000000000000000000002",
            "01CCC000000000000000000003",
        }
        assert committed_status["event_count"] == 3
        assert sorted(committed_status["work_packages"]) == ["WP01", "WP02", "WP03"]
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

    def test_status_events_conflict_rematerializes_unconflicted_status_json(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-event-only"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: append event"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        _write_status_events(repo / status_events_rel, [base_event, lane_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "lane: append event"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _run(["git", "sparse-checkout", "init", "--no-cone"], worktree_b)
        _run(
            [
                "git",
                "sparse-checkout",
                "set",
                "--no-cone",
                "/*",
                f"!{status_events_rel.as_posix()}",
                f"!{status_json_rel.as_posix()}",
            ],
            worktree_b,
        )
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        rule_ids = [
            getattr(classification.resolution, "rule_id", None)
            for classification in report.classifications
        ]
        assert rule_ids == [
            "R-STATUS-EVENTS-JSONL-UNION",
            "R-STATUS-JSON-REMATERIALIZE",
        ]
        subject = _run(["git", "log", "-1", "--pretty=%s"], worktree_b).stdout.strip()
        assert subject.startswith("auto-rebase(lane=lane-a): 2 conflicts resolved")
        committed_status = json.loads(
            _run(["git", "show", f"HEAD:{status_json_rel.as_posix()}"], worktree_b).stdout
        )
        assert committed_status["event_count"] == 3
        assert sorted(committed_status["work_packages"]) == ["WP01", "WP02", "WP03"]
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

    def test_failed_sparse_status_resolution_reapplies_sparse_checkout(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-sparse-failure"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )

        (repo / ".gitattributes").write_text(
            "kitty-specs/**/status.events.jsonl merge=union\n",
            encoding="utf-8",
        )
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", ".gitattributes", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed failure status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / status_events_rel).write_text(
            json.dumps({"event_id": "01BBB000000000000000000002"}) + "\n",
            encoding="utf-8",
        )
        (repo / status_json_rel).write_text('{"event_count": 2, "side": "mission"}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "mission: invalid status event"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).write_text('{"event_count": 2, "side": "lane"}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "lane: status json drift"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _run(["git", "sparse-checkout", "init", "--no-cone"], worktree_b)
        _run(
            [
                "git",
                "sparse-checkout",
                "set",
                "--no-cone",
                "/*",
                f"!{status_events_rel.as_posix()}",
                f"!{status_json_rel.as_posix()}",
            ],
            worktree_b,
        )
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "Invalid event structure" in report.halt_reason
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

    def test_clean_event_log_merge_driver_refreshes_status_json(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        driver_script = tmp_path / "event_log_driver.py"
        _write_event_log_driver_script(driver_script)
        _configure_event_log_merge_driver(repo, driver_script)
        mission_slug = "1968-clean-driver"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        (repo / ".gitattributes").write_text(
            "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log\n",
            encoding="utf-8",
        )
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", ".gitattributes", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed production driver status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        (repo / status_json_rel).write_text('{"event_count": 2, "side": "mission"}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "mission: event log and stale snapshot"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        _write_status_events(repo / status_events_rel, [base_event, lane_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "lane: event log only"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        committed_status = json.loads((worktree_b / status_json_rel).read_text(encoding="utf-8"))
        committed_events = [
            json.loads(line)
            for line in (worktree_b / status_events_rel).read_text(encoding="utf-8").splitlines()
        ]
        assert [event["event_id"] for event in committed_events] == [
            "01AAA000000000000000000001",
            "01BBB000000000000000000002",
            "01CCC000000000000000000003",
        ]
        assert committed_status["event_count"] == 3
        assert sorted(committed_status["work_packages"]) == ["WP01", "WP02", "WP03"]

    def test_mixed_conflict_clean_status_events_deletion_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-mixed-delete"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed mixed deletion status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / status_events_rel).unlink()
        _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo", "charlie"])
        _run(["git", "add", str(status_events_rel), "pyproject.toml"], repo)
        _run(["git", "commit", "-m", "mission: delete status events and add charlie"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _write_pyproject(worktree_b / "pyproject.toml", ["alpha", "bravo", "delta"])
        _run(["git", "add", "pyproject.toml"], worktree_b)
        _run(["git", "commit", "-m", "lane: add delta"], worktree_b)
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "refusing staged deletion" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        assert (worktree_b / status_events_rel).exists()
        assert (worktree_b / status_json_rel).exists()
        assert _run(["git", "status", "--porcelain"], worktree_b).stdout == ""

    def test_mixed_conflict_clean_event_log_driver_refreshes_status_json(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        driver_script = tmp_path / "event_log_driver.py"
        _write_event_log_driver_script(driver_script)
        _configure_event_log_merge_driver(repo, driver_script)
        mission_slug = "1968-mixed-driver"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        (repo / ".gitattributes").write_text(
            "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log\n",
            encoding="utf-8",
        )
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", ".gitattributes", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed mixed driver status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo", "charlie"])
        _run(["git", "add", str(status_events_rel), "pyproject.toml"], repo)
        _run(["git", "commit", "-m", "mission: events and charlie"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _write_status_events(worktree_b / status_events_rel, [base_event, lane_event])
        _write_pyproject(worktree_b / "pyproject.toml", ["alpha", "bravo", "delta"])
        _run(["git", "add", str(status_events_rel), "pyproject.toml"], worktree_b)
        _run(["git", "commit", "-m", "lane: events and delta"], worktree_b)

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        committed_status = json.loads((worktree_b / status_json_rel).read_text(encoding="utf-8"))
        committed_events = [
            json.loads(line)
            for line in (worktree_b / status_events_rel).read_text(encoding="utf-8").splitlines()
        ]
        assert [event["event_id"] for event in committed_events] == [
            "01AAA000000000000000000001",
            "01BBB000000000000000000002",
            "01CCC000000000000000000003",
        ]
        assert committed_status["event_count"] == 3
        assert sorted(committed_status["work_packages"]) == ["WP01", "WP02", "WP03"]
        assert _run(["git", "status", "--porcelain"], worktree_b).stdout == ""

    def test_production_event_log_driver_uses_current_venv_before_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        fake_spec_kitty = fake_bin / (
            "spec-kitty.cmd" if sys.platform == "win32" else "spec-kitty"
        )
        if sys.platform == "win32":
            fake_spec_kitty.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
        else:
            fake_spec_kitty.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_spec_kitty.chmod(0o755)
        monkeypatch.setenv(
            "PATH",
            str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
        )

        _configure_production_event_log_merge_driver(repo)
        mission_slug = "1968-production-driver-path"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        (repo / ".gitattributes").write_text(
            "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log\n",
            encoding="utf-8",
        )
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", ".gitattributes", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed production driver path artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: append event"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _write_status_events(worktree_b / status_events_rel, [base_event, lane_event])
        _run(["git", "add", str(status_events_rel)], worktree_b)
        _run(["git", "commit", "-m", "lane: append event"], worktree_b)

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        committed_events = [
            json.loads(line)
            for line in (worktree_b / status_events_rel).read_text(encoding="utf-8").splitlines()
        ]
        assert [event["event_id"] for event in committed_events] == [
            "01AAA000000000000000000001",
            "01BBB000000000000000000002",
            "01CCC000000000000000000003",
        ]
        committed_status = json.loads((worktree_b / status_json_rel).read_text(encoding="utf-8"))
        assert committed_status["event_count"] == 3

    def test_sparse_mixed_conflict_clean_event_log_driver_refreshes_status_json(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        driver_script = tmp_path / "event_log_driver.py"
        _write_event_log_driver_script(driver_script)
        _configure_event_log_merge_driver(repo, driver_script)
        mission_slug = "1968-sparse-mixed-driver"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        (repo / ".gitattributes").write_text(
            "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log\n",
            encoding="utf-8",
        )
        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", ".gitattributes", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed sparse mixed driver status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo", "charlie"])
        _run(["git", "add", str(status_events_rel), "pyproject.toml"], repo)
        _run(["git", "commit", "-m", "mission: sparse events and charlie"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        _write_status_events(repo / status_events_rel, [base_event, lane_event])
        _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo", "delta"])
        _run(["git", "add", str(status_events_rel), "pyproject.toml"], repo)
        _run(["git", "commit", "-m", "lane: sparse events and delta"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        _run(["git", "sparse-checkout", "init", "--no-cone"], worktree_b)
        _run(
            [
                "git",
                "sparse-checkout",
                "set",
                "--no-cone",
                "/*",
                f"!{status_events_rel.as_posix()}",
                f"!{status_json_rel.as_posix()}",
            ],
            worktree_b,
        )
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        committed_status = json.loads(
            _run(["git", "show", f"HEAD:{status_json_rel.as_posix()}"], worktree_b).stdout
        )
        committed_events = [
            json.loads(line)
            for line in _run(
                ["git", "show", f"HEAD:{status_events_rel.as_posix()}"],
                worktree_b,
            ).stdout.splitlines()
        ]
        assert [event["event_id"] for event in committed_events] == [
            "01AAA000000000000000000001",
            "01BBB000000000000000000002",
            "01CCC000000000000000000003",
        ]
        assert committed_status["event_count"] == 3
        assert sorted(committed_status["work_packages"]) == ["WP01", "WP02", "WP03"]
        assert not (worktree_b / status_events_rel).exists()
        assert not (worktree_b / status_json_rel).exists()
        assert _run(["git", "status", "--porcelain"], worktree_b).stdout == ""

    def test_clean_status_json_only_change_is_rematerialized(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-clean-status-json-only"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed status snapshot artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / status_json_rel).write_text("not-json\n", encoding="utf-8")
        _run(["git", "add", str(status_json_rel)], repo)
        _run(["git", "commit", "-m", "mission: corrupt derived status snapshot"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        (worktree_b / "src").mkdir(exist_ok=True)
        (worktree_b / "src" / "lane-only.txt").write_text("lane\n", encoding="utf-8")
        _run(["git", "add", "src/lane-only.txt"], worktree_b)
        _run(["git", "commit", "-m", "lane: unrelated work"], worktree_b)

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        committed_status = json.loads((worktree_b / status_json_rel).read_text(encoding="utf-8"))
        assert committed_status["event_count"] == 1
        assert sorted(committed_status["work_packages"]) == ["WP01"]
        assert _run(["git", "status", "--porcelain"], worktree_b).stdout == ""

    def test_clean_status_json_only_change_without_event_log_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-status-json-no-events"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_json_rel = mission_dir / "status.json"

        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(status_json_rel)], repo)
        _run(["git", "commit", "-m", "seed status snapshot without events"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / status_json_rel).write_text("not-json\n", encoding="utf-8")
        _run(["git", "add", str(status_json_rel)], repo)
        _run(["git", "commit", "-m", "mission: corrupt orphaned status snapshot"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        (worktree_b / "src").mkdir(exist_ok=True)
        (worktree_b / "src" / "lane-only.txt").write_text("lane\n", encoding="utf-8")
        _run(["git", "add", "src/lane-only.txt"], worktree_b)
        _run(["git", "commit", "-m", "lane: unrelated work"], worktree_b)
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "missing authoritative" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        assert _run(["git", "status", "--porcelain"], worktree_b).stdout == ""

    def test_preexisting_lane_status_events_deletion_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-preexisting-delete"
        mission_branch = f"kitty/mission-{mission_slug}"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / "README.md").write_text("mission\n", encoding="utf-8")
        _run(["git", "add", "README.md"], repo)
        _run(["git", "commit", "-m", "mission: unrelated work"], repo)
        _run(["git", "checkout", "main"], repo)

        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        (worktree_b / status_events_rel).unlink()
        _run(["git", "add", str(status_events_rel)], worktree_b)
        _run(["git", "commit", "-m", "lane: delete status events"], worktree_b)
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "pre-existing lane-side deletion" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        assert not (worktree_b / status_events_rel).exists()
        assert _run(["git", "status", "--porcelain"], worktree_b).stdout == ""

    def test_clean_status_events_deletion_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "1968-delete-clean"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed deletion status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / status_events_rel).unlink()
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: delete status events"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "lane-only.txt").write_text("lane\n", encoding="utf-8")
        _run(["git", "add", "src/lane-only.txt"], repo)
        _run(["git", "commit", "-m", "lane: unrelated work"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip()

        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is False
        assert report.halt_reason is not None
        assert "refusing staged deletion" in report.halt_reason
        assert _run(["git", "rev-parse", "HEAD"], worktree_b).stdout.strip() == pre_sync_head
        assert (worktree_b / status_events_rel).exists()
        assert (worktree_b / status_json_rel).exists()
        assert "status.events.jsonl" not in _run(
            ["git", "status", "--porcelain"],
            worktree_b,
        ).stdout


class TestAutoRebaseSemanticConflict:
    """T045 — Negative: a semantic conflict falls through to Manual."""

    def test_semantic_conflict_halts_and_cleans_up(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        mission_slug = "009-demo"
        mission_branch = f"kitty/mission-{mission_slug}"

        # Add a code file that both sides will modify in incompatible ways.
        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        (repo / "src").mkdir(parents=True, exist_ok=True)
        (repo / "src" / "flags.py").write_text(
            "def enabled():\n    return False\n"
        )
        _run(["git", "add", "src/flags.py"], repo)
        _run(["git", "commit", "-m", "mission: add flags"], repo)

        # Modify on mission branch.
        (repo / "src" / "flags.py").write_text(
            "def enabled():\n    # Mission's preferred body\n    return False\n"
        )
        _run(["git", "add", "src/flags.py"], repo)
        _run(["git", "commit", "-m", "mission: modify flags"], repo)
        _run(["git", "checkout", "main"], repo)

        # Lane branch makes a conflicting modification.
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        worktree_b = _make_lane_worktree(repo, mission_slug, "lane-a", branch_b)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)
        (worktree_b / "src").mkdir(parents=True, exist_ok=True)
        (worktree_b / "src" / "flags.py").write_text(
            "def enabled():\n    # Lane's preferred body\n    return True\n"
        )
        _run(["git", "add", "src/flags.py"], worktree_b)
        _run(["git", "commit", "-m", "lane: modify flags"], worktree_b)

        lane = _make_lane()
        report = attempt_auto_rebase(
            lane=lane,
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.attempted is True
        assert report.succeeded is False
        assert report.halt_reason is not None
        # The default rule's reason mentions the unmatched path.
        assert (
            "no classifier rule matched" in report.halt_reason
            or "src/flags.py" in report.halt_reason
        )

        # Lane B worktree must be clean (merge --abort ran).
        status = _run(["git", "status", "--porcelain"], worktree_b)
        # No conflicted files; the merge was aborted.
        assert "UU " not in status.stdout
        # The lane branch tip must still be the pre-merge commit (no merge
        # commit landed).
        rev = _run(["git", "rev-parse", "HEAD"], worktree_b)
        assert rev.returncode == 0


def _patch_auto_rebase_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reject_sparse: bool,
) -> list[list[str]]:
    """Wrap ``auto_rebase._run`` to record commands and simulate Git < 2.35.

    With ``reject_sparse=True`` every command carrying ``--sparse`` fails the
    way a pre-2.35 git answers it (``error: unknown option 'sparse'``); all
    other commands delegate to the real runner. Returns the recorded command
    list (mutated live, so assertions can read it after the call).
    """
    calls: list[list[str]] = []
    real_run: Callable[..., subprocess.CompletedProcess[str]] = auto_rebase._run

    def recording_run(cmd: list[str], cwd: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        if reject_sparse and "--sparse" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error: unknown option `sparse'")
        return real_run(cmd, cwd, check=check)

    monkeypatch.setattr(auto_rebase, "_run", recording_run)
    return calls


class TestSparseFlagGating4202:
    """#4202 — ``--sparse`` staging flags belong to sparse checkouts only.

    ``git add --sparse`` / ``git rm --sparse`` require Git >= 2.35 and only
    make sense inside a sparse-checkout worktree. Passing them unconditionally
    aborted every lane auto-rebase status-artifact resolution
    (``LANE_AUTO_REBASE_FAILED: R-STATUS-JSON-REMATERIALIZE``) on older Git,
    even for plain non-sparse worktrees.
    """

    def test_stage_non_sparse_worktree_uses_plain_git_add(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
        calls = _patch_auto_rebase_run(monkeypatch, reject_sparse=True)

        ok, message = auto_rebase._stage_sparse(repo, "notes.txt")

        assert (ok, message) == (True, None)
        add_calls = [cmd for cmd in calls if cmd[:2] == ["git", "add"]]
        assert add_calls == [["git", "add", "notes.txt"]]
        assert not any("--sparse" in cmd for cmd in calls)

    def test_stage_sparse_worktree_keeps_sparse_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        _run(["git", "sparse-checkout", "init", "--no-cone"], repo)
        _run(["git", "sparse-checkout", "set", "--no-cone", "/*"], repo)
        (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
        calls = _patch_auto_rebase_run(monkeypatch, reject_sparse=False)

        ok, message = auto_rebase._stage_sparse(repo, "notes.txt")

        assert (ok, message) == (True, None)
        add_calls = [cmd for cmd in calls if cmd[:2] == ["git", "add"]]
        assert add_calls == [["git", "add", "--sparse", "notes.txt"]]

    def test_stage_sparse_worktree_falls_back_when_git_rejects_sparse_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        _run(["git", "sparse-checkout", "init", "--no-cone"], repo)
        _run(["git", "sparse-checkout", "set", "--no-cone", "/*"], repo)
        (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
        calls = _patch_auto_rebase_run(monkeypatch, reject_sparse=True)

        ok, message = auto_rebase._stage_sparse(repo, "notes.txt")

        assert (ok, message) == (True, None)
        add_calls = [cmd for cmd in calls if cmd[:2] == ["git", "add"]]
        assert add_calls == [
            ["git", "add", "--sparse", "notes.txt"],
            ["git", "add", "notes.txt"],
        ]

    def test_remove_non_sparse_worktree_uses_plain_git_rm(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
        _run(["git", "add", "notes.txt"], repo)
        _run(["git", "commit", "-m", "seed notes"], repo)
        calls = _patch_auto_rebase_run(monkeypatch, reject_sparse=True)

        ok, message = auto_rebase._remove_sparse(repo, "notes.txt")

        assert (ok, message) == (True, None)
        rm_calls = [cmd for cmd in calls if cmd[:2] == ["git", "rm"]]
        assert rm_calls == [["git", "rm", "-f", "--ignore-unmatch", "notes.txt"]]
        assert not (repo / "notes.txt").exists()
        assert not any("--sparse" in cmd for cmd in calls)

    def test_remove_sparse_worktree_falls_back_when_git_rejects_sparse_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        _run(["git", "sparse-checkout", "init", "--no-cone"], repo)
        _run(["git", "sparse-checkout", "set", "--no-cone", "/*"], repo)
        (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
        _run(["git", "add", "notes.txt"], repo)
        _run(["git", "commit", "-m", "seed notes"], repo)
        calls = _patch_auto_rebase_run(monkeypatch, reject_sparse=True)

        ok, message = auto_rebase._remove_sparse(repo, "notes.txt")

        assert (ok, message) == (True, None)
        rm_calls = [cmd for cmd in calls if cmd[:2] == ["git", "rm"]]
        assert rm_calls == [
            ["git", "rm", "-f", "--ignore-unmatch", "--sparse", "notes.txt"],
            ["git", "rm", "-f", "--ignore-unmatch", "notes.txt"],
        ]

    def test_stage_failure_is_surfaced_not_retried(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = _init_repo(tmp_path)
        (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
        calls: list[list[str]] = []
        real_run: Callable[..., subprocess.CompletedProcess[str]] = auto_rebase._run

        def failing_run(cmd: list[str], cwd: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(list(cmd))
            if cmd[:2] == ["git", "add"]:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="fatal: unable to stage")
            return real_run(cmd, cwd, check=check)

        monkeypatch.setattr(auto_rebase, "_run", failing_run)

        ok, message = auto_rebase._stage_sparse(repo, "notes.txt")

        assert ok is False
        assert message is not None
        assert "fatal: unable to stage" in message
        add_calls = [cmd for cmd in calls if cmd[:2] == ["git", "add"]]
        assert add_calls == [["git", "add", "notes.txt"]]

    def test_non_sparse_status_conflict_resolves_on_git_without_sparse_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Field-report repro (#4202): a NON-sparse lane worktree whose git
        rejects ``--sparse`` must still resolve status conflicts — the
        R-STATUS-JSON-REMATERIALIZE path that aborted with
        ``LANE_AUTO_REBASE_FAILED`` before the gating fix."""
        repo = _init_repo(tmp_path)
        mission_slug = "4202-plain-worktree"
        mission_branch = f"kitty/mission-{mission_slug}"
        branch_b = f"kitty/mission-{mission_slug}-lane-a"
        mission_dir = Path("kitty-specs") / mission_slug
        status_events_rel = mission_dir / "status.events.jsonl"
        status_json_rel = mission_dir / "status.json"
        base_event = _status_event(
            "01AAA000000000000000000001",
            at="2026-06-15T04:00:00Z",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane="genesis",
            to_lane="planned",
        )
        mission_event = _status_event(
            "01BBB000000000000000000002",
            at="2026-06-15T04:01:00Z",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane="genesis",
            to_lane="planned",
        )
        lane_event = _status_event(
            "01CCC000000000000000000003",
            at="2026-06-15T04:02:00Z",
            mission_slug=mission_slug,
            wp_id="WP03",
            from_lane="genesis",
            to_lane="planned",
        )

        _write_status_events(repo / status_events_rel, [base_event])
        (repo / status_json_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / status_json_rel).write_text('{"event_count": 1}\n', encoding="utf-8")
        _run(["git", "add", str(mission_dir)], repo)
        _run(["git", "commit", "-m", "seed status artifacts"], repo)

        _run(["git", "branch", mission_branch, "main"], repo)
        _run(["git", "checkout", mission_branch], repo)
        _write_status_events(repo / status_events_rel, [base_event, mission_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "mission: append event"], repo)

        _run(["git", "checkout", "-b", branch_b, "main"], repo)
        _write_status_events(repo / status_events_rel, [base_event, lane_event])
        _run(["git", "add", str(status_events_rel)], repo)
        _run(["git", "commit", "-m", "lane: append event"], repo)
        _run(["git", "checkout", "main"], repo)

        worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
        worktree_b.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "worktree", "add", str(worktree_b), branch_b], repo)
        _run(["git", "config", "user.email", "test@spec-kitty"], worktree_b)
        _run(["git", "config", "user.name", "test"], worktree_b)

        calls = _patch_auto_rebase_run(monkeypatch, reject_sparse=True)
        report = attempt_auto_rebase(
            lane=_make_lane(),
            branch=branch_b,
            mission_branch=mission_branch,
            repo_root=repo,
            worktree_path=worktree_b,
        )

        assert report.succeeded is True, report.halt_reason
        assert not any("--sparse" in cmd for cmd in calls)
        rule_ids = [getattr(classification.resolution, "rule_id", None) for classification in report.classifications]
        assert rule_ids == [
            "R-STATUS-EVENTS-JSONL-UNION",
            "R-STATUS-JSON-REMATERIALIZE",
        ]
        committed_status = json.loads(_run(["git", "show", f"HEAD:{status_json_rel.as_posix()}"], worktree_b).stdout)
        assert committed_status["event_count"] == 3
        assert sorted(committed_status["work_packages"]) == ["WP01", "WP02", "WP03"]
