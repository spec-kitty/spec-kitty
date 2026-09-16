"""Lane workspace-context refresh on reuse (#3946 / F-78).

A shared lane worktree outlives its WPs: claiming a later WP into the lane
must advance the lane's persisted workspace context (``current_wp``) to that
WP, or every later lane commit warns ``ACTIVE_WP_CONTEXT_STALE`` and scopes
against the prior WP's ownership. Covers the shared
:func:`~specify_cli.lanes.implement_support.refresh_reused_lane_context`
helper directly, and pins the native ``implement`` reuse path
(:func:`~specify_cli.lanes.implement_support.create_lane_workspace`) that
routes through it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.workspace.context import WorkspaceContext

pytestmark = [pytest.mark.unit]

MISSION_SLUG = "010-lane-context-refresh"
MISSION_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LANE_ID = "lane-a"
CONTEXT_NAME = f"{MISSION_SLUG}-{LANE_ID}"


def _context(*, current_wp: str = "WP01") -> WorkspaceContext:
    return WorkspaceContext(
        wp_id=current_wp,
        mission_slug=MISSION_SLUG,
        worktree_path=f".worktrees/{CONTEXT_NAME}",
        branch_name=f"{MISSION_BRANCH}-{LANE_ID}",
        base_branch=MISSION_BRANCH,
        base_commit=None,
        dependencies=[],
        created_at="2026-09-06T00:00:00+00:00",
        created_by="implement-command-lane",
        vcs_backend="git",
        lane_id=LANE_ID,
        lane_wp_ids=["WP01", "WP02"],
        current_wp=current_wp,
        lane_test_env={},
    )


def test_refresh_updates_existing_context(tmp_path: Path) -> None:
    """A reused lane's context follows the newly active WP."""
    from specify_cli.lanes.implement_support import refresh_reused_lane_context
    from specify_cli.workspace.context import load_context, save_context

    save_context(tmp_path, _context(current_wp="WP01"))

    refreshed = refresh_reused_lane_context(tmp_path, MISSION_SLUG, LANE_ID, "WP02", ["WP01"])

    assert refreshed is True
    ctx = load_context(tmp_path, CONTEXT_NAME)
    assert ctx is not None
    assert ctx.current_wp == "WP02"
    assert ctx.wp_id == "WP02"
    assert ctx.dependencies == ["WP01"]


def test_refresh_is_a_noop_without_a_persisted_context(tmp_path: Path) -> None:
    """No context on disk (an orchestrator-driven lane that never had one)
    stays context-free — the helper never creates one."""
    from specify_cli.lanes.implement_support import refresh_reused_lane_context
    from specify_cli.workspace.context import get_context_path

    refreshed = refresh_reused_lane_context(tmp_path, MISSION_SLUG, LANE_ID, "WP02", [])

    assert refreshed is False
    assert not get_context_path(tmp_path, CONTEXT_NAME).exists()


def test_refresh_is_a_noop_without_a_lane(tmp_path: Path) -> None:
    """``lane_id=None`` (a repository-root planning workspace) is a no-op."""
    from specify_cli.lanes.implement_support import refresh_reused_lane_context
    from specify_cli.workspace.context import get_context_path

    refreshed = refresh_reused_lane_context(tmp_path, MISSION_SLUG, None, "WP02", [])

    assert refreshed is False
    assert not get_context_path(tmp_path, CONTEXT_NAME).exists()


# ---------------------------------------------------------------------------
# Native implement reuse path (create_lane_workspace) — git-backed pin
# ---------------------------------------------------------------------------

_GIT_REPO_MARK = pytest.mark.git_repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@_GIT_REPO_MARK
def test_create_lane_workspace_reuse_advances_current_wp(tmp_path: Path) -> None:
    """The SECOND WP claimed into a lane advances the persisted context's
    ``current_wp`` — the exact F-78 defect, pinned on the native flow."""
    from specify_cli.lanes.implement_support import create_lane_workspace
    from specify_cli.workspace.context import ResolvedWorkspace, load_context

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01LANECTX0000000000000000",
                "mission_slug": MISSION_SLUG,
                "target_branch": "main",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        (feature_dir / "tasks" / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ndependencies: []\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=MISSION_SLUG,
            mission_id="01LANECTX0000000000000000",
            mission_branch=MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id=LANE_ID,
                    wp_ids=("WP01", "WP02"),
                    write_scope=(),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-09-06T00:00:00+00:00",
            computed_from="test",
        ),
    )
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", MISSION_BRANCH)

    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(feature_dir)

    def _start(wp_id: str):
        resolved = ResolvedWorkspace(
            mission_slug=MISSION_SLUG,
            wp_id=wp_id,
            execution_mode="code_change",
            mode_source="frontmatter",
            resolution_kind="lane_workspace",
            workspace_name=CONTEXT_NAME,
            worktree_path=repo / ".worktrees" / CONTEXT_NAME,
            branch_name=None,
            lane_id=LANE_ID,
            lane_wp_ids=["WP01", "WP02"],
        )
        return create_lane_workspace(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=wp_id,
            wp_file=feature_dir / "tasks" / f"{wp_id}.md",
            resolved_workspace=resolved,
            lanes_manifest=manifest,
            declared_deps=[],
            vcs_backend_value="git",
        )

    first = _start("WP01")
    assert first.is_reuse is False
    ctx = load_context(repo, CONTEXT_NAME)
    assert ctx is not None
    assert ctx.current_wp == "WP01"

    # The prior WP is approved; the lane hosts both WPs (lanes.json), so the
    # second claim reuses the lane worktree — the normal sequential-WP outcome.
    second = _start("WP02")
    assert second.is_reuse is True
    ctx = load_context(repo, CONTEXT_NAME)
    assert ctx is not None
    assert ctx.current_wp == "WP02"
    assert ctx.wp_id == "WP02"
