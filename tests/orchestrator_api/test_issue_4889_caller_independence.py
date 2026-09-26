"""Issue #4889 (P0): the destroyed-lane guard fires for the orchestrator-api
caller too, not just the CLI.

The guard lives inside ``allocate_lane_worktree`` (the shared allocator),
never in a caller-specific wrapper, precisely so a second entry point cannot
bypass it. ``_resolve_start_workspace`` (reached by ``start-implementation``
and ``transition --to claimed``) is the caller this P0 most exists to
protect: an external orchestrator driving spec-kitty over the machine
contract has no CLI-side ``implement`` guard to fall back on.

This test drives ``_resolve_start_workspace`` directly against the exact
same destroyed-lane fixture shape as ``tests/lanes/test_issue_4889_destroyed_lane_guard.py``,
and asserts the failure surfaces as a structured ``LANE_ALLOCATION_FAILED``
JSON envelope (never a raw traceback) -- :class:`DestroyedLaneError`
subclasses ``StructuredError`` (-> ``RuntimeError``) specifically so the
existing ``except (..., RuntimeError)`` arm at
``orchestrator_api/commands.py::_resolve_start_workspace`` catches it with
ZERO edits to that file.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.missions._create import ensure_coordination_branch
from specify_cli.missions._read_path_resolver import coord_feature_dir
from specify_cli.orchestrator_api.commands import _resolve_start_workspace
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from specify_cli.workspace.context import WorkspaceContext, save_context

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

WP_ID = "WP01"
LANE_ID = "lane-a"
TARGET_BRANCH = "main"


@dataclass(frozen=True)
class MissionIds:
    mid8: str
    mission_id: str
    mission_slug: str


def _ids(tag: str) -> MissionIds:
    """Per-test mission identity -- see the sibling lanes-test module docstring
    for why a shared constant risks cross-test ``.kittify/workspaces``
    collisions on this harness.
    """
    digest = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:6].upper()
    mid8 = f"01{digest}"
    mission_id = mid8 + "0" * 18
    mission_slug = f"destroyed-lane-orch-{digest.lower()}"
    return MissionIds(mid8=mid8, mission_id=mission_id, mission_slug=mission_slug)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", TARGET_BRANCH)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, ids: MissionIds, *, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": ids.mission_id,
        "mission_slug": ids.mission_slug,
        "mid8": ids.mid8,
        "mission_type": "software-dev",
        "target_branch": TARGET_BRANCH,
        "created_at": "2026-09-25T00:00:00+00:00",
        "friendly_name": "Destroyed lane orchestrator fixture",
        "coordination_branch": coordination_branch,
    }
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_manifest(ids: MissionIds, coordination_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=ids.mission_slug,
        mission_id=ids.mission_id,
        mission_branch=coordination_branch,
        target_branch=TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-25T00:00:00Z",
        computed_from="test",
    )


_TRANSITION_CHAIN_IN_PROGRESS: list[tuple[str, str]] = [
    ("genesis", "planned"),
    ("planned", "claimed"),
    ("claimed", "in_progress"),
]


def _seed_status(coord_status_dir: Path, ids: MissionIds) -> None:
    coord_status_dir.mkdir(parents=True, exist_ok=True)
    for index, (from_lane, to_lane) in enumerate(_TRANSITION_CHAIN_IN_PROGRESS):
        event = StatusEvent(
            event_id=f"01AAAAAAAAAAAAAAAAAAAAAA{index}",
            mission_slug=ids.mission_slug,
            wp_id=WP_ID,
            from_lane=Lane(from_lane),
            to_lane=Lane(to_lane),
            at="2026-09-25T10:00:00+00:00",
            actor="test",
            force=False,
            execution_mode="worktree",
        )
        append_event(coord_status_dir, event)


def _build_destroyed_lane_fixture(tmp_path: Path, ids: MissionIds) -> tuple[Path, LanesManifest, Path, str]:
    """Same fixture shape as the lanes-layer test, plus a persisted
    ``lanes.json`` (``_resolve_start_workspace`` reads it from disk rather
    than accepting a manifest object directly).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    coord_result = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=ids.mission_slug,
        mission_id=ids.mission_id,
        target_branch=TARGET_BRANCH,
    )
    assert coord_result.created
    coord_branch = coord_result.branch_name

    feature_dir = repo / "kitty-specs" / ids.mission_slug
    _write_meta(feature_dir, ids, coordination_branch=coord_branch)
    manifest = _make_manifest(ids, coord_branch)
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: meta + lanes.json")

    coord_root = CoordinationWorkspace.resolve(repo, ids.mission_slug, ids.mid8)
    coord_status_dir = coord_feature_dir(repo, ids.mission_slug, ids.mid8)
    coord_status_dir.mkdir(parents=True, exist_ok=True)
    (coord_root / "coord-marker.txt").write_text("coord progress\n", encoding="utf-8")
    _git(coord_root, "add", "coord-marker.txt")
    _git(coord_root, "commit", "-q", "-m", "coord: progress")

    _seed_status(coord_status_dir, ids)

    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=ids.mission_slug,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    assert branch_exists(repo, branch)

    (worktree_path / "feature.py").write_text("value = 42\n", encoding="utf-8")
    _git(worktree_path, "add", "feature.py")
    _git(worktree_path, "commit", "-q", "-m", "feat: WP01 real work")

    base_commit = _git(repo, "rev-parse", coord_branch)
    context = WorkspaceContext(
        wp_id=WP_ID,
        mission_slug=ids.mission_slug,
        worktree_path=str(worktree_path.relative_to(repo)),
        branch_name=branch,
        base_branch=coord_branch,
        base_commit=base_commit,
        dependencies=[],
        created_at="2026-09-25T10:00:00+00:00",
        created_by="test",
        vcs_backend="git",
        lane_id=LANE_ID,
        lane_wp_ids=[WP_ID],
        current_wp=WP_ID,
    )
    save_context(repo, context)

    reach = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base_commit, TARGET_BRANCH],
        capture_output=True,
        text=True,
    )
    assert reach.returncode != 0, "fixture bug: base_commit must NOT be reachable from target"

    _git(repo, "worktree", "remove", "--force", str(worktree_path))
    _git(repo, "branch", "-D", branch)
    assert not worktree_path.exists()
    assert not branch_exists(repo, branch)

    return repo, manifest, worktree_path, branch


class TestOrchestratorApiCallerIndependence:
    """T002: ``_resolve_start_workspace`` refuses identically to the CLI."""

    def test_destroyed_lane_refuses_via_orchestrator(self, tmp_path: Path, request: pytest.FixtureRequest, capsys: pytest.CaptureFixture[str]) -> None:
        ids = _ids(request.node.name)
        repo, _manifest, worktree_path, branch = _build_destroyed_lane_fixture(tmp_path, ids)
        mission_dir = repo / "kitty-specs" / ids.mission_slug

        with pytest.raises(typer.Exit) as exc_info:
            _resolve_start_workspace(
                "start-implementation",
                repo,
                ids.mission_slug,
                mission_dir,
                WP_ID,
            )

        # NFR-004: non-zero exit, never an unhandled traceback.
        assert exc_info.value.exit_code != 0

        captured = capsys.readouterr()
        envelope = json.loads(captured.out.strip().splitlines()[-1])
        assert envelope["success"] is False
        assert envelope["error_code"] == "LANE_ALLOCATION_FAILED"
        assert envelope["data"]["wp_id"] == WP_ID
        assert branch in envelope["data"]["reason"]
        assert "reflog" in envelope["data"]["reason"] or "fsck" in envelope["data"]["reason"]

        # #4889 landing: DestroyedLaneError's structured to_dict() payload reaches
        # the orchestrator boundary (not only str(exc)), so an automated caller can
        # branch on the nested error_code and act on the structured fields rather
        # than substring-matching the message.
        assert envelope["data"]["error_code"] == "DESTROYED_LANE"
        assert envelope["data"]["branch_name"] == branch
        assert envelope["data"]["wp_id"] == WP_ID
        assert "next_step" in envelope["data"]

        # No side effects: no new lane worktree/branch materialized.
        assert not worktree_path.exists()
        assert not branch_exists(repo, branch)

    def test_destroyed_lane_refuses_no_raw_traceback(self, tmp_path: Path, request: pytest.FixtureRequest, capsys: pytest.CaptureFixture[str]) -> None:
        """NFR-004: the orchestrator never sees a bare Python traceback -- only
        the structured envelope reaches stdout (a bare-``Exception``
        ``DestroyedLaneError`` would have escaped the caller's ``except``
        tuple entirely and propagated as an unhandled traceback instead).
        """
        ids = _ids(request.node.name)
        repo, _manifest, _worktree_path, _branch = _build_destroyed_lane_fixture(tmp_path, ids)
        mission_dir = repo / "kitty-specs" / ids.mission_slug

        with pytest.raises(typer.Exit):
            _resolve_start_workspace(
                "start-implementation",
                repo,
                ids.mission_slug,
                mission_dir,
                WP_ID,
            )

        captured = capsys.readouterr()
        assert "Traceback (most recent call last)" not in captured.out
        assert "Traceback (most recent call last)" not in captured.err
