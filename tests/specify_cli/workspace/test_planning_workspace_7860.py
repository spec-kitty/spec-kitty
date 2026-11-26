"""#7860: a planning work package's workspace is the checkout holding the Mission branch.

Real git. Before a default Mission lands, its planning lane writes on its Mission branch,
which the coordination worktree holds once the topology is settled. ``resolve_workspace_for_wp``
resolves the planning work package there, under its own resolution kind, and names that branch
(FR-001). Explicit topologies, landed Missions, the ``single_branch`` repo-root lane and owned
checkouts keep today's result byte for byte (FR-006). A Mission branch no checkout holds refuses
with ``PLANNING_CHECKOUT_MISSING``; it never resolves to the repository root checkout (NFR-002).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from specify_cli.core.errors import StructuredError
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.workspace.context import (
    ResolvedWorkspace,
    clear_workspace_resolution_caches,
    resolve_workspace_for_wp,
)
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "pw-01M8BBBB"
_MISSION_ID = "01M8BBBBBBBBBBBBBBBBBBBBBB"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "main"
_PLANNING_WP = "WP01"
_PLANNING_LANE_CODE_WP = "WP02"
_CODE_WP = "WP03"
#: The distinct resolution kind of the Mission-branch checkout (``workspace.context.MISSION_BRANCH_CHECKOUT_KIND``).
MISSION_BRANCH_CHECKOUT_KIND = "mission_branch_checkout"


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _init(repo: Path) -> None:
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", _TARGET)
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-q", "-m", "init")


def _wp(wp_id: str, execution_mode: str) -> str:
    return (
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: []\n"
        f"execution_mode: {execution_mode}\nowned_files:\n- kitty-specs/{_SLUG}/notes-{wp_id}.md\n---\n\n# {wp_id}\n"
    )


def _manifest(*, single_branch: bool = False) -> LanesManifest:
    planning_wps = (_PLANNING_WP, _PLANNING_LANE_CODE_WP)
    lanes = [
        ExecutionLane(
            lane_id=PLANNING_LANE_ID,
            wp_ids=planning_wps,
            write_scope=(f"kitty-specs/{_SLUG}/**",),
            predicted_surfaces=("planning",),
            depends_on_lanes=(),
            parallel_group=0,
        )
    ]
    if not single_branch:
        lanes.append(
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(_CODE_WP,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        )
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=_MISSION_BRANCH,
        target_branch=_TARGET,
        lanes=lanes,
        computed_at="2026-11-25T00:00:00Z",
        computed_from="test",
    )


def _meta(**overrides: object) -> dict[str, object]:
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _SLUG,
        "mission_type": "software-dev",
        "friendly_name": _SLUG,
        "target_branch": _TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": _MISSION_BRANCH,
        "coordination_branch": _MISSION_BRANCH,
        "created_at": "2026-11-25T00:00:00+00:00",
    }
    meta.update(overrides)
    return {key: value for key, value in meta.items() if value is not None}


def _commit_mission(checkout: Path, meta: dict[str, object], *, single_branch: bool = False) -> None:
    mission = checkout / "kitty-specs" / _SLUG
    (mission / "tasks").mkdir(parents=True, exist_ok=True)
    (mission / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (mission / "tasks" / f"{_PLANNING_WP}-plan.md").write_text(_wp(_PLANNING_WP, "planning_artifact"), encoding="utf-8")
    (mission / "tasks" / f"{_PLANNING_LANE_CODE_WP}-code.md").write_text(_wp(_PLANNING_LANE_CODE_WP, "code_change"), encoding="utf-8")
    if not single_branch:
        (mission / "tasks" / f"{_CODE_WP}-code.md").write_text(_wp(_CODE_WP, "code_change"), encoding="utf-8")
    write_lanes_json(mission, _manifest(single_branch=single_branch))
    git_out(checkout, "add", "-A")
    git_out(checkout, "commit", "-q", "-m", "mission")


def _settled_default_mission(tmp_path: Path) -> tuple[Path, Path]:
    """Root checkout on the target, the Mission branch (with the Mission) in the coordination worktree."""
    repo = tmp_path / "repo"
    _init(repo)
    holder = repo / ".worktrees" / f"{_SLUG}-coord"
    git_out(repo, "worktree", "add", "-q", "-b", _MISSION_BRANCH, str(holder))
    _commit_mission(holder, _meta())
    return repo, holder


def _repo_root_workspace(repo: Path, wp_id: str, execution_mode: str, branch: str | None, lane_wp_ids: list[str]) -> ResolvedWorkspace:
    """Today's ``repo_root`` resolution of a ``lane-planning`` work package, field for field."""
    return ResolvedWorkspace(
        mission_slug=_SLUG,
        wp_id=wp_id,
        execution_mode=execution_mode,
        mode_source="frontmatter",
        resolution_kind="repo_root",
        workspace_name=f"{_SLUG}-{PLANNING_LANE_ID}",
        worktree_path=repo,
        branch_name=branch,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=lane_wp_ids,
        context=None,
    )


_PLANNING_LANE_WPS = [_PLANNING_WP, _PLANNING_LANE_CODE_WP]


# --- case 1: default, not landed, settled lanes_with_coord ------------------------------------


@pytest.mark.parametrize(("wp_id", "execution_mode"), [(_PLANNING_WP, "planning_artifact"), (_PLANNING_LANE_CODE_WP, "code_change")])
def test_a_default_missions_planning_wp_resolves_to_the_mission_branch_checkout(tmp_path: Path, wp_id: str, execution_mode: str) -> None:
    repo, holder = _settled_default_mission(tmp_path)

    resolved = resolve_workspace_for_wp(repo, _SLUG, wp_id)

    from specify_cli.workspace import context

    assert resolved.resolution_kind == context.MISSION_BRANCH_CHECKOUT_KIND == MISSION_BRANCH_CHECKOUT_KIND
    assert resolved.worktree_path.resolve() == holder.resolve()
    assert resolved.branch_name == _MISSION_BRANCH
    assert resolved.lane_id == PLANNING_LANE_ID
    assert resolved.lane_wp_ids == _PLANNING_LANE_WPS
    assert resolved.execution_mode == execution_mode
    # A shared checkout, never a lane worktree: the claim is stamped ``direct_repo`` (decided).
    assert resolved.runs_in_checkout_root is True
    assert resolved.is_shared_checkout is True
    assert resolved.status_execution_mode == "direct_repo"
    assert resolved.exists is True
    assert resolved.is_husk is False


def test_a_default_missions_code_lane_wp_is_unchanged(tmp_path: Path) -> None:
    repo, _holder = _settled_default_mission(tmp_path)

    resolved = resolve_workspace_for_wp(repo, _SLUG, _CODE_WP)

    assert resolved.resolution_kind == "lane_workspace"
    assert resolved.lane_id == "lane-a"


def test_the_planning_workspace_follows_the_one_planning_lane_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-005: the workspace reads ``planning_lane_target`` at call time, never a re-derived rule."""
    from specify_cli.coordination import planning_commit

    repo, _holder = _settled_default_mission(tmp_path)
    sentinel = planning_commit.PlanningLaneTarget(branch="sentinel-branch", checkout=tmp_path / "sentinel", on_mission_branch=True)
    monkeypatch.setattr(planning_commit, "planning_lane_target", lambda *_a, **_k: sentinel)

    resolved = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP)

    assert (resolved.resolution_kind, resolved.branch_name, resolved.worktree_path) == (MISSION_BRANCH_CHECKOUT_KIND, "sentinel-branch", tmp_path / "sentinel")


# --- case 2: explicit topology -> today's values, byte for byte -------------------------------


def test_an_explicit_topology_keeps_the_repository_root_result(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _commit_mission(repo, _meta(topology_source=None))

    planning = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP)
    planning_lane_code = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_LANE_CODE_WP)

    assert planning == _repo_root_workspace(repo, _PLANNING_WP, "planning_artifact", None, _PLANNING_LANE_WPS)
    assert planning_lane_code == _repo_root_workspace(repo, _PLANNING_LANE_CODE_WP, "code_change", _TARGET, _PLANNING_LANE_WPS)
    assert planning.is_shared_checkout is True


# --- case 3: default, landed -> the target --------------------------------------------------------


def test_a_landed_default_mission_keeps_the_repository_root_result(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _commit_mission(repo, _meta(merged_at="2026-11-25T01:00:00+00:00"))

    planning = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP)
    planning_lane_code = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_LANE_CODE_WP)

    assert planning == _repo_root_workspace(repo, _PLANNING_WP, "planning_artifact", None, _PLANNING_LANE_WPS)
    assert planning_lane_code == _repo_root_workspace(repo, _PLANNING_LANE_CODE_WP, "code_change", _TARGET, _PLANNING_LANE_WPS)


# --- case 4: default single_branch repo-root lane -> unchanged -------------------------------------


def test_a_default_single_branch_repo_root_lane_is_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    git_out(repo, "checkout", "-q", "-b", _MISSION_BRANCH)
    _commit_mission(repo, _meta(topology="single_branch", coordination_branch=None), single_branch=True)

    code_wp = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_LANE_CODE_WP)
    planning_wp = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP)

    # resolve_single_branch_write_ref: the stored single_branch Mission's minted Mission branch.
    assert code_wp == _repo_root_workspace(repo, _PLANNING_LANE_CODE_WP, "code_change", _MISSION_BRANCH, _PLANNING_LANE_WPS)
    assert planning_wp == _repo_root_workspace(repo, _PLANNING_WP, "planning_artifact", None, _PLANNING_LANE_WPS)


# --- case 5: the coordination worktree is gone -> named refusal, never the root ----------------


@pytest.mark.parametrize("wp_id", [_PLANNING_WP, _PLANNING_LANE_CODE_WP])
def test_a_removed_coordination_worktree_refuses_and_never_falls_back_to_the_root(tmp_path: Path, wp_id: str) -> None:
    repo, holder = _settled_default_mission(tmp_path)
    git_out(repo, "worktree", "remove", "--force", str(holder))

    with pytest.raises(StructuredError) as refused:
        resolve_workspace_for_wp(repo, _SLUG, wp_id)

    assert refused.value.error_code == "PLANNING_CHECKOUT_MISSING"
    message = str(refused.value)
    assert message.startswith("PLANNING_CHECKOUT_MISSING: ")
    assert _MISSION_BRANCH in message
    assert f"spec-kitty doctor coordination --mission {_SLUG} --fix" in message
    assert refused.value.to_dict()["mission_branch"] == _MISSION_BRANCH


def test_a_mission_branch_no_checkout_holds_refuses_from_the_planning_arm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The WP index is readable but no checkout holds the Mission branch: refuse, never the root."""
    import mission_runtime
    from specify_cli.coordination import planning_commit

    repo, _holder = _settled_default_mission(tmp_path)

    def _missing(*_a: object, **_k: object) -> object:
        raise mission_runtime.PlanningCheckoutMissing(_SLUG, _MISSION_BRANCH)

    monkeypatch.setattr(planning_commit, "planning_lane_target", _missing)

    with pytest.raises(StructuredError) as refused:
        resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP)

    assert refused.value.error_code == "PLANNING_CHECKOUT_MISSING"
    assert isinstance(refused.value.__cause__, mission_runtime.PlanningCheckoutMissing)


# --- case 6: an owned checkout -> the owned arm wins --------------------------------------------


def test_an_owned_coordination_checkout_keeps_the_owned_planning_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.coordination import planning_commit
    from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission

    repo = tmp_path / "R"
    _init(repo)
    owned_root = tmp_path / "P"
    git_out(repo, "worktree", "add", "-q", "-b", "codex/owned", str(owned_root))
    _commit_mission(owned_root, _meta(topology_source=None, target_branch="codex/owned"))
    fact = resolve_owned_mission(repo, owned_root, _SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)

    def _never(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned checkout never reads the planning lane target")

    monkeypatch.setattr(planning_commit, "planning_lane_target", _never)

    resolved = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP, owned=fact)

    assert resolved.resolution_kind == "repo_root"
    assert resolved.worktree_path == fact.owned_root


# --- case 7: resume of a WP claimed before this change -----------------------------------------


def test_a_resumed_claim_resolves_to_and_prints_the_mission_branch_checkout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A claim made before #7860 recorded its claim base at the repository root and no workspace record.

    A re-invoked ``implement`` resolves the Mission-branch checkout all the same, and prints it.
    """
    from specify_cli.cli.commands.agent import workflow_executor
    from specify_cli.lanes.claim_base import read_claim_base, record_claim_base

    repo, holder = _settled_default_mission(tmp_path)
    record_claim_base(repo, repo, _SLUG, _PLANNING_WP)
    assert read_claim_base(repo, _SLUG, _PLANNING_WP) is not None
    assert not (repo / ".kittify" / "workspaces").exists() or not list((repo / ".kittify" / "workspaces").iterdir())

    resolved = resolve_workspace_for_wp(repo, _SLUG, _PLANNING_WP)

    assert resolved.resolution_kind == MISSION_BRANCH_CHECKOUT_KIND
    assert resolved.worktree_path.resolve() == holder.resolve()

    workflow_executor.implement_finalize_and_print(
        prompt_lines=["prompt"],
        mission_slug=_SLUG,
        normalized_wp_id=_PLANNING_WP,
        repo_root=repo,
        workspace=resolved,
        workspace_path=resolved.worktree_path,
        has_feedback=False,
        review_feedback_ref=None,
        mission_type="software-dev",
        deliverables_path=None,
        subtask_cmd="T001",
    )
    printed = capsys.readouterr().out
    assert f"📍 Workspace: cd {resolved.worktree_path}" in printed
    assert f"the Mission branch {_MISSION_BRANCH} (the coordination branch)" in printed


# --- T007/T008: the readers of the new kind ---------------------------------------------------


def _mission_branch_workspace(path: Path, wp_id: str = _PLANNING_WP) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=_SLUG,
        wp_id=wp_id,
        execution_mode="planning_artifact",
        mode_source="frontmatter",
        resolution_kind=MISSION_BRANCH_CHECKOUT_KIND,
        workspace_name=f"{_SLUG}-{PLANNING_LANE_ID}",
        worktree_path=path,
        branch_name=_MISSION_BRANCH,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=_PLANNING_LANE_WPS,
    )


def test_the_shared_checkout_predicate_classifies_every_kind() -> None:
    from specify_cli.workspace.context import is_shared_checkout_kind

    assert is_shared_checkout_kind("repo_root") is True
    assert is_shared_checkout_kind(MISSION_BRANCH_CHECKOUT_KIND) is True
    assert is_shared_checkout_kind("owned_checkout") is False
    assert is_shared_checkout_kind("lane_workspace") is False
    assert is_shared_checkout_kind(None) is False


def test_stale_detection_never_reports_a_mission_branch_checkout_as_a_lane_worktree() -> None:
    from specify_cli.core.stale_detection import StaleCheckResult, StaleState

    result = StaleCheckResult(wp_id=_PLANNING_WP, stale=StaleState(status="not_applicable"), workspace_exists=True, workspace_kind=MISSION_BRANCH_CHECKOUT_KIND)
    lane = StaleCheckResult(wp_id=_CODE_WP, stale=StaleState(status="fresh"), workspace_exists=True, workspace_kind="lane_workspace")

    assert result.worktree_exists is False
    assert lane.worktree_exists is True


def test_the_status_view_fallback_treats_the_mission_branch_checkout_as_shared() -> None:
    from specify_cli.cli.commands.agent.tasks_status_view import build_stale_fallback_results
    from specify_cli.core.stale_detection import PLANNING_ARTIFACT_REPO_ROOT_REASON

    results = build_stale_fallback_results(
        [{"id": _PLANNING_WP, "workspace_kind": MISSION_BRANCH_CHECKOUT_KIND}, {"id": _CODE_WP, "workspace_kind": "lane_workspace"}],
        RuntimeError("boom"),
    )

    assert results[_PLANNING_WP].stale.reason == PLANNING_ARTIFACT_REPO_ROOT_REASON
    assert results[_CODE_WP].stale.reason == "stale_detection_unavailable"


def test_the_dependency_alert_names_the_mission_branch_checkout_and_no_rebase(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.tasks_dependency_graph import _dependent_rebase_line

    line = _dependent_rebase_line(_PLANNING_WP, _mission_branch_workspace(tmp_path), _mission_branch_workspace(tmp_path, _CODE_WP))

    assert f"the Mission branch {_MISSION_BRANCH} (the coordination branch)" in line
    assert str(tmp_path) in line
    assert "git rebase" not in line


def test_the_dependency_alert_keeps_todays_lines_for_other_shapes(tmp_path: Path) -> None:
    from dataclasses import replace

    from specify_cli.cli.commands.agent.tasks_dependency_graph import _dependent_rebase_line

    planning = replace(_mission_branch_workspace(tmp_path), resolution_kind="repo_root", branch_name=None)
    lane = replace(_mission_branch_workspace(tmp_path / "lane", _CODE_WP), resolution_kind="lane_workspace", branch_name="kitty/lane-a")
    current = replace(lane, wp_id="WP09")

    planning_line = _dependent_rebase_line(_PLANNING_WP, planning, current)
    assert "planning-lane workspace (repository root checkout)" in planning_line
    assert "ensure the target branch is up to date" in planning_line
    assert "main" not in planning_line
    assert "same lane" in _dependent_rebase_line(_CODE_WP, lane, current)
    assert _dependent_rebase_line(_CODE_WP, lane, replace(current, branch_name="kitty/lane-b")).endswith("git rebase kitty/lane-b")


def test_the_topology_names_the_mission_branch_for_the_planning_entry(tmp_path: Path) -> None:
    from specify_cli.core.worktree_topology import FeatureTopology, WPTopologyEntry, _entry_branch_name, _topology_note, render_topology_json

    workspace = _mission_branch_workspace(tmp_path)
    lane = next(iter(_manifest().lanes))
    assert _entry_branch_name(workspace, lane, _SLUG, _TARGET) == _MISSION_BRANCH

    entry = WPTopologyEntry(
        wp_id=_PLANNING_WP,
        resolution_kind=MISSION_BRANCH_CHECKOUT_KIND,
        lane_id=PLANNING_LANE_ID,
        branch_name=_MISSION_BRANCH,
        base_branch="abc123",
        review_paths=["kitty-specs/x.md"],
    )
    topology = FeatureTopology(mission_slug=_SLUG, target_branch=_TARGET, mission_branch=_MISSION_BRANCH, entries=[entry])

    assert topology.get_actual_base_for_wp(_PLANNING_WP) == "abc123"
    assert (
        _topology_note(entry, _PLANNING_WP) == f"{_PLANNING_WP} runs in the planning workspace on the Mission branch {_MISSION_BRANCH} (the coordination branch)."
    )
    payload = json.loads(render_topology_json(topology, _PLANNING_WP)[1])
    assert payload["diff_command"] == "git diff abc123..HEAD -- kitty-specs/x.md"


def test_the_topology_note_keeps_todays_text_for_other_shapes() -> None:
    from specify_cli.core.worktree_topology import WPTopologyEntry, _topology_note

    assert _topology_note(None, "WP09") == "WP09 is not in the computed topology."
    assert _topology_note(WPTopologyEntry(wp_id="WP01", resolution_kind="repo_root"), "WP01") == "WP01 runs in the repository root planning workspace."
    shared = WPTopologyEntry(wp_id="WP03", lane_id="lane-a", lane_wp_ids=["WP03", "WP04"])
    assert _topology_note(shared, "WP03") == "WP03 shares lane lane-a with WP03, WP04. Sequential WPs in the same lane reuse one worktree."
    assert _topology_note(WPTopologyEntry(wp_id="WP05", lane_id="lane-b", lane_wp_ids=["WP05"]), "WP05") == "WP05 owns lane lane-b alone."


def test_the_next_prompt_names_the_mission_branch_and_asks_for_the_commit(tmp_path: Path) -> None:
    from runtime.next.prompt_builder import _self_commit_branch, _workspace_header_lines

    workspace = _mission_branch_workspace(tmp_path)

    header = "\n".join(_workspace_header_lines("implement", _PLANNING_WP, "claude", _SLUG, "software-dev", workspace, None))
    assert f"Workspace: {tmp_path}" in header
    assert f"Workspace branch: the Mission branch {_MISSION_BRANCH} (the coordination branch)" in header
    assert _self_commit_branch(workspace, None) == _MISSION_BRANCH


def test_the_implement_banner_names_the_mission_branch_checkout(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands import implement as implement_module
    from specify_cli.cli.console import console

    result = SimpleNamespace(resolution_kind=MISSION_BRANCH_CHECKOUT_KIND, branch_name=_MISSION_BRANCH, lane_id=PLANNING_LANE_ID, lane_test_env={})
    with console.capture() as captured:
        implement_module._print_workspace_ready_banner(result, tmp_path, None)
    printed = captured.get()

    assert f"committed on the Mission branch {_MISSION_BRANCH} (the coordination branch)" in printed
    assert f"cd {tmp_path}" in printed
    assert "spec-kitty consolidate" in printed
    assert "repository root" not in printed


def test_the_translated_refusal_carries_the_mission_branch_fields() -> None:
    import mission_runtime
    from specify_cli.workspace.context import PlanningWorkspaceMissing

    source = mission_runtime.PlanningCheckoutMissing(_SLUG, _MISSION_BRANCH, remote="origin", coordinated=True)
    refusal = PlanningWorkspaceMissing(source)

    assert str(refusal) == str(source)
    assert refusal.to_dict() == {
        "error_code": "PLANNING_CHECKOUT_MISSING",
        "message": str(source),
        "mission_slug": _SLUG,
        "mission_branch": _MISSION_BRANCH,
        "remote": "origin",
        "coordinated": True,
    }


# --- review cycle 1 ------------------------------------------------------------------------------


def test_a_corrupt_meta_and_an_unknown_wp_keep_the_original_not_found_error(tmp_path: Path) -> None:
    """Finding 1: the missing-checkout probe never replaces the caller's own ``ValueError``."""
    repo = tmp_path / "repo"
    _init(repo)
    _commit_mission(repo, _meta(topology_source=None))
    (repo / "kitty-specs" / _SLUG / "meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Work package WP99 was not found"):
        resolve_workspace_for_wp(repo, _SLUG, "WP99")


def test_a_probe_that_cannot_decide_keeps_the_original_not_found_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 1: any probe failure other than ``PlanningCheckoutMissing`` leaves the original error standing."""
    from specify_cli.coordination import planning_commit

    repo, _holder = _settled_default_mission(tmp_path)

    def _broken(*_a: object, **_k: object) -> object:
        raise RuntimeError("git is unusable")

    monkeypatch.setattr(planning_commit, "planning_lane_target", _broken)

    with pytest.raises(ValueError, match="Work package WP99 was not found"):
        resolve_workspace_for_wp(repo, _SLUG, "WP99")


def test_move_task_pre_review_workspace_fails_closed_when_the_coordination_worktree_is_gone(tmp_path: Path) -> None:
    """Finding 2: the move-task pre-review resolution does not degrade a missing Mission-branch checkout.

    ``_mt_resolve_pre_review_workspace`` degrades to ``None`` (no evidence) on a missing lanes manifest
    or an unknown WP; a Mission branch checked out nowhere is not that case: it refuses (NFR-002).
    """
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent.tasks_move_task_gates import _mt_resolve_pre_review_workspace

    repo, holder = _settled_default_mission(tmp_path)
    git_out(repo, "worktree", "remove", "--force", str(holder))
    st = SimpleNamespace(owned=None, main_repo_root=repo, mission_slug=_SLUG, task_id=_PLANNING_WP)

    with pytest.raises(StructuredError) as refused:
        _mt_resolve_pre_review_workspace(cast(Any, st))

    assert refused.value.error_code == "PLANNING_CHECKOUT_MISSING"


def test_move_task_refuses_by_name_when_the_coordination_worktree_is_gone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 2, end to end: ``agent tasks move-task`` refuses by name and never prints a traceback.

    With the Mission's only checkout gone, the handle resolution refuses first
    (``MISSION_NOT_FOUND``), before any workspace resolution; the move never degrades to the root.
    """
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.tasks import app

    repo, holder = _settled_default_mission(tmp_path)
    git_out(repo, "worktree", "remove", "--force", str(holder))
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["move-task", _PLANNING_WP, "--to", "for_review", "--mission", _SLUG, "--agent", "claude", "--json"])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["success"] is False
    assert payload["error_code"] in {"MISSION_NOT_FOUND", "PLANNING_CHECKOUT_MISSING"}
