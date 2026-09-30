"""``resolve_workspace_for_wp`` against a hand-written single_branch repo-root
lane manifest (#5100 WP04 T017).

The manifest shape this WP tests is only PRODUCED by ``compute_lanes`` in
WP05 (IC-03 activation); until then these tests hand-write the manifest the
contract (``contracts/single-branch-execution.md``, "Resolve") describes, so
the resolver arm is proven correct ahead of its real writer landing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.workspace.context import (
    WorkspaceContext,
    clear_workspace_resolution_caches,
    resolve_workspace_for_wp,
    save_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "single-branch-resolve-01KZZTEST"
_MISSION_ID = "01KZZRESOLVESINGLEBRANCHXX"


@pytest.fixture(autouse=True)
def reset_workspace_caches() -> None:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _seed_mission(repo_root: Path, *, topology: str) -> Path:
    (repo_root / ".kittify" / "workspaces").mkdir(parents=True, exist_ok=True)
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "topology": topology,
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": _MISSION_SLUG,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return feature_dir


def _write_code_wp(feature_dir: Path, wp_id: str, *, owned_files: list[str]) -> None:
    lines = [
        "---",
        f"work_package_id: {wp_id}",
        "title: Code change",
        "dependencies: []",
        "execution_mode: code_change",
        "owned_files:",
        *[f"- {f}" for f in owned_files],
        "---",
        "",
        "Body.",
        "",
    ]
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text("\n".join(lines), encoding="utf-8")


def _repo_root_manifest(*, mission_branch: str = "") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _lanes_code_manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def test_repo_root_lane_without_owned_fact_resolves_to_repository_root(tmp_path: Path) -> None:
    feature_dir = _seed_mission(tmp_path, topology="single_branch")
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    write_lanes_json(feature_dir, _repo_root_manifest())

    resolved = resolve_workspace_for_wp(tmp_path, _MISSION_SLUG, "WP01")

    assert resolved.resolution_kind == "repo_root"
    assert resolved.worktree_path == tmp_path
    assert resolved.branch_name == "main"
    assert resolved.lane_id == PLANNING_LANE_ID
    assert resolved.status_execution_mode == "direct_repo"


def _set_meta_mission_branch(feature_dir: Path, mission_branch: str | None) -> None:
    """Record (or clear) ``meta.mission_branch`` -- the write-branch authority."""
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if mission_branch is None:
        meta.pop("mission_branch", None)
    else:
        meta["mission_branch"] = mission_branch
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def test_repo_root_lane_branch_name_prefers_mission_branch_when_set(tmp_path: Path) -> None:
    feature_dir = _seed_mission(tmp_path, topology="single_branch")
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    _set_meta_mission_branch(feature_dir, "kitty/mission-single-branch-resolve-01kzz")
    write_lanes_json(feature_dir, _repo_root_manifest(mission_branch="kitty/mission-single-branch-resolve-01kzz"))

    resolved = resolve_workspace_for_wp(tmp_path, _MISSION_SLUG, "WP01")

    assert resolved.branch_name == "kitty/mission-single-branch-resolve-01kzz"


def test_repo_root_lane_branch_ignores_stale_lanes_json_mission_branch_after_landing(tmp_path: Path) -> None:
    """After a protected landing clears ``meta.mission_branch`` the stale
    ``lanes.json`` still names the (deleted) mission branch; the write branch
    -- the WRONG_BRANCH refusal's expectation -- must follow meta.json (the
    authority commit placement reads), i.e. the target branch."""
    feature_dir = _seed_mission(tmp_path, topology="single_branch")
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    _set_meta_mission_branch(feature_dir, None)
    write_lanes_json(feature_dir, _repo_root_manifest(mission_branch="kitty/mission-single-branch-resolve-01kzz"))

    resolved = resolve_workspace_for_wp(tmp_path, _MISSION_SLUG, "WP01")

    assert resolved.branch_name == "main"


def test_lanes_topology_code_wp_in_planning_lane_keeps_target_branch(tmp_path: Path) -> None:
    """The mission-branch rule is gated on STORED single_branch: a code WP that
    sits in ``lane-planning`` of a LANES mission resolves to the target branch
    (as on main), never to ``lanes.json.mission_branch`` (the integration branch)."""
    feature_dir = _seed_mission(tmp_path, topology="lanes")
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    write_lanes_json(feature_dir, _repo_root_manifest(mission_branch=f"kitty/mission-{_MISSION_SLUG}"))

    resolved = resolve_workspace_for_wp(tmp_path, _MISSION_SLUG, "WP01")

    assert resolved.branch_name == "main"


def test_repo_root_lane_with_owned_fact_resolves_to_the_owned_checkout(tmp_path: Path) -> None:
    """#5100's alternate write checkout, expressed as the validated fact.

    The retired bare ``effective_root=`` keyword is the owned-checkout fact now
    (owned-checkout-lifecycle-authority): an owned single_branch mission
    resolves to the owned checkout itself, a checkout-root kind whose status
    stamp is ``direct_repo`` (R-10) and whose branch is the fact's write branch.
    """
    from mission_runtime import MissionTopology, OwnedCheckout

    repository_root = tmp_path / "repo"
    owned_root = tmp_path / "owned-checkout"
    feature_dir = _seed_mission(owned_root, topology="single_branch")
    repository_root.mkdir()
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    write_lanes_json(feature_dir, _repo_root_manifest())
    fact = OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=feature_dir,
        mission_slug=_MISSION_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="main",
    )

    resolved = resolve_workspace_for_wp(repository_root, _MISSION_SLUG, "WP01", owned=fact)

    assert resolved.runs_in_checkout_root
    assert resolved.worktree_path == owned_root
    assert resolved.branch_name == "main"
    assert resolved.status_execution_mode == "direct_repo"


def test_stale_workspace_context_does_not_shadow_repo_root_lane(tmp_path: Path) -> None:
    """M8: the repo-root-lane arm is checked BEFORE the persisted
    WorkspaceContext lookup, so a stale context left over from before the
    mission adopted single_branch never routes the WP to a worktree."""
    feature_dir = _seed_mission(tmp_path, topology="single_branch")
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    write_lanes_json(feature_dir, _repo_root_manifest())
    save_context(
        tmp_path,
        WorkspaceContext(
            wp_id="WP01",
            mission_slug=_MISSION_SLUG,
            worktree_path=f".worktrees/{_MISSION_SLUG}-lane-a",
            branch_name=f"kitty/mission-{_MISSION_SLUG}-lane-a",
            base_branch=f"kitty/mission-{_MISSION_SLUG}",
            base_commit="deadbeef",
            dependencies=[],
            created_at="2026-01-01T00:00:00Z",
            created_by="implement-command-lane",
            vcs_backend="git",
            lane_id="lane-a",
            lane_wp_ids=["WP01"],
            current_wp="WP01",
        ),
    )

    resolved = resolve_workspace_for_wp(tmp_path, _MISSION_SLUG, "WP01")

    assert resolved.resolution_kind == "repo_root"
    assert resolved.worktree_path == tmp_path
    assert resolved.status_execution_mode == "direct_repo"


# ``test_effective_root_raises_for_non_single_branch_mission`` retired with the
# bare ``effective_root=`` keyword: an owned root for a mission outside the
# caller's allowed topologies is now refused once, at the minter
# (``owned_mission._require_allowed_topology`` -> OWNED_TOPOLOGY_UNSUPPORTED,
# pinned by ``tests/core/test_owned_mission_minter.py``), so no unvalidated
# root ever reaches ``resolve_workspace_for_wp``.


def test_lanes_topology_code_lane_still_resolves_to_worktrees(tmp_path: Path) -> None:
    """Control: an ordinary code lane (non-repo-root) is unaffected by the
    new arm and still resolves under ``.worktrees/``."""
    feature_dir = _seed_mission(tmp_path, topology="lanes")
    _write_code_wp(feature_dir, "WP01", owned_files=["src/a.py"])
    write_lanes_json(feature_dir, _lanes_code_manifest())

    resolved = resolve_workspace_for_wp(tmp_path, _MISSION_SLUG, "WP01")

    assert resolved.resolution_kind == "lane_workspace"
    assert resolved.worktree_path == tmp_path / ".worktrees" / f"{_MISSION_SLUG}-lane-a"
    assert resolved.status_execution_mode == "worktree"
