"""#7860 (WP03, FR-011): a default Mission's planning claim base and the ``for_review`` gate.

Real git. Before a default Mission lands, its planning work package is worked in the checkout
holding the Mission branch (the coordination worktree once settled, WP02). The claim base must be
that checkout's ``HEAD``, never the repository root checkout's: the root sits on the target, which
holds none of the Mission's history, so a root-recorded base makes the ``for_review`` gate diff the
whole Mission history (spec, plan, tasks) and pass a hollow work package (research R-03 #2).

* case 1: the claim base is the Mission-branch checkout's ``HEAD`` (the target moved on after the
  Mission was created, so the two ``HEAD``s differ);
* case 2: the gate refuses a hollow work package right after the claim, although the Mission branch
  holds spec and plan commits beyond the target, and the refusal names the checkout and its branch;
* case 3: the positive control, one owned commit in that checkout passes;
* case 4: an explicit topology keeps the repository root checkout's ``HEAD``;
* case 5: a sibling planning work package's commit after the claim passes the coarse gate (the
  documented residual); the evidence axis (WP04) is the real check, and WP05's acceptance suite
  asserts it refuses the hollow work package with ``IMPLEMENTATION_MISSING``;
* the CLI claim paths: ``agent action implement`` (driven end to end) and native ``implement``
  (``create_lane_workspace``) both record the base from the Mission-branch checkout;
* the #5296 code-lane waiver holds for the Mission-branch checkout whatever branch the repository
  root checkout is on: code lanes are never merged into the Mission branch; a stored
  ``single_branch`` Mission's waiver is unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.lanes.claim_base import read_claim_base
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.for_review_gate import evaluate_for_review_gate
from specify_cli.lanes.implement_support import check_claim_ancestry, guard_repo_root_claim
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.workspace.context import (
    MISSION_BRANCH_CHECKOUT_KIND,
    clear_workspace_resolution_caches,
    resolve_workspace_for_wp,
)
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SLUG = "pc-01M8CCCC"
MISSION_ID = "01M8CCCCCCCCCCCCCCCCCCCCCC"
MISSION_BRANCH = f"kitty/mission-{SLUG}"
TARGET = "main"
PLANNING_WP = "WP01"
SIBLING_WP = "WP02"
CODE_WP = "WP03"
CODE_LANE = "lane-a"


@dataclass(frozen=True)
class DefaultMission:
    """A settled default Mission: the root checkout on the target, the Mission branch in its own checkout."""

    repo: Path
    holder: Path

    @property
    def mission_dir(self) -> Path:
        return self.holder / "kitty-specs" / SLUG


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _init(repo: Path) -> None:
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", TARGET)
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-q", "-m", "init")


def owned_path(wp_id: str) -> str:
    """The one owned file of *wp_id* (author-written Mission content, never bookkeeping)."""
    return f"kitty-specs/{SLUG}/research/notes-{wp_id}.md"


def _wp(wp_id: str, execution_mode: str) -> str:
    frontmatter = f"work_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: []\nsubtasks: []\n"
    frontmatter += f"execution_mode: {execution_mode}\nowned_files:\n- {owned_path(wp_id)}\n"
    return f"---\n{frontmatter}---\n\n# {wp_id}\n"


def manifest(*, planning_depends_on_code: bool = False) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=SLUG,
        mission_id=MISSION_ID,
        mission_branch=MISSION_BRANCH,
        target_branch=TARGET,
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=(PLANNING_WP, SIBLING_WP),
                write_scope=(f"kitty-specs/{SLUG}/**",),
                predicted_surfaces=("planning",),
                depends_on_lanes=(CODE_LANE,) if planning_depends_on_code else (),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id=CODE_LANE,
                wp_ids=(CODE_WP,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-11-26T00:00:00Z",
        computed_from="test",
    )


def meta(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": SLUG,
        "mission_type": "software-dev",
        "friendly_name": SLUG,
        "target_branch": TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": MISSION_BRANCH,
        "coordination_branch": MISSION_BRANCH,
        "created_at": "2026-11-26T00:00:00+00:00",
    }
    values.update(overrides)
    return {key: value for key, value in values.items() if value is not None}


def commit_mission(checkout: Path, meta_values: dict[str, object], *, planning_depends_on_code: bool = False) -> None:
    """Commit the Mission the way planning does: spec, then plan, then the tasks and lanes."""
    mission = checkout / "kitty-specs" / SLUG
    mission.mkdir(parents=True, exist_ok=True)
    (mission / "spec.md").write_text("# Spec\n", encoding="utf-8")
    git_out(checkout, "add", "-A")
    git_out(checkout, "commit", "-q", "-m", "spec")
    (mission / "plan.md").write_text("# Plan\n", encoding="utf-8")
    git_out(checkout, "add", "-A")
    git_out(checkout, "commit", "-q", "-m", "plan")
    (mission / "tasks").mkdir()
    (mission / "meta.json").write_text(json.dumps(meta_values, indent=2), encoding="utf-8")
    (mission / "tasks" / f"{PLANNING_WP}-plan.md").write_text(_wp(PLANNING_WP, "planning_artifact"), encoding="utf-8")
    (mission / "tasks" / f"{SIBLING_WP}-plan.md").write_text(_wp(SIBLING_WP, "planning_artifact"), encoding="utf-8")
    (mission / "tasks" / f"{CODE_WP}-code.md").write_text(_wp(CODE_WP, "code_change"), encoding="utf-8")
    write_lanes_json(mission, manifest(planning_depends_on_code=planning_depends_on_code))
    git_out(checkout, "add", "-A")
    git_out(checkout, "commit", "-q", "-m", "tasks")


def commit_file(checkout: Path, relpath: str, message: str) -> str:
    path = checkout / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{message}\n", encoding="utf-8")
    git_out(checkout, "add", relpath)
    git_out(checkout, "commit", "-q", "-m", message)
    return git_out(checkout, "rev-parse", "HEAD")


def settled_default_mission(tmp_path: Path, *, planning_depends_on_code: bool = False) -> DefaultMission:
    """Root on the target, which moves on after the Mission is created; the Mission branch in the coordination worktree."""
    repo = tmp_path / "repo"
    _init(repo)
    holder = repo / ".worktrees" / f"{SLUG}-coord"
    git_out(repo, "worktree", "add", "-q", "-b", MISSION_BRANCH, str(holder))
    commit_mission(holder, meta(), planning_depends_on_code=planning_depends_on_code)
    commit_file(repo, "target-only.txt", "the target moves on after the Mission was created")
    return DefaultMission(repo=repo, holder=holder)


def claim(repo: Path, wp_id: str = PLANNING_WP) -> None:
    """The CLI claim seam both ``implement`` verbs share."""
    guard_repo_root_claim(repo, SLUG, wp_id, resolve_workspace_for_wp(repo, SLUG, wp_id))


# --- case 1: the claim base is the Mission-branch checkout's HEAD ------------------------------


def test_the_claim_base_is_the_mission_branch_checkouts_head(tmp_path: Path) -> None:
    mission = settled_default_mission(tmp_path)
    holder_head = git_out(mission.holder, "rev-parse", "HEAD")
    root_head = git_out(mission.repo, "rev-parse", "HEAD")
    assert holder_head != root_head

    claim(mission.repo)

    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) == holder_head


# --- case 2: hollow -> refused, naming the checkout and its branch -----------------------------


def test_the_gate_refuses_a_hollow_planning_wp_despite_mission_history_ahead_of_the_target(tmp_path: Path) -> None:
    mission = settled_default_mission(tmp_path)
    claim(mission.repo)

    decision = evaluate_for_review_gate(mission.repo, SLUG, PLANNING_WP)

    assert decision.passed is False
    assert decision.lane_branch == MISSION_BRANCH
    assert decision.base_ref == git_out(mission.holder, "rev-parse", "HEAD")
    assert f"in the Mission branch checkout {mission.holder} (branch {MISSION_BRANCH})" in decision.reason
    assert "repository root checkout" not in decision.reason


# --- case 3: positive control -------------------------------------------------------------------


def test_the_gate_passes_one_owned_commit_in_the_mission_branch_checkout(tmp_path: Path) -> None:
    mission = settled_default_mission(tmp_path)
    claim(mission.repo)
    commit_file(mission.holder, owned_path(PLANNING_WP), "WP01 research notes")

    decision = evaluate_for_review_gate(mission.repo, SLUG, PLANNING_WP)

    assert decision.passed is True
    assert decision.lane_branch == MISSION_BRANCH


# --- case 4: an explicit topology keeps the repository root checkout ----------------------------


def test_an_explicit_topology_records_the_repository_root_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    commit_mission(repo, meta(topology_source=None))
    assert resolve_workspace_for_wp(repo, SLUG, PLANNING_WP).resolution_kind == "repo_root"

    claim(repo)

    assert read_claim_base(repo, SLUG, PLANNING_WP) == git_out(repo, "rev-parse", "HEAD")
    decision = evaluate_for_review_gate(repo, SLUG, PLANNING_WP)
    assert decision.passed is False
    assert "in the repository root checkout beyond" in decision.reason
    assert decision.lane_branch == TARGET


# --- case 5: a sibling's commit (the documented residual) ---------------------------------------


def test_a_sibling_commit_passes_the_coarse_gate(tmp_path: Path) -> None:
    """Documented residual: the gate counts any non-status commit since the claim base in the shared checkout."""
    mission = settled_default_mission(tmp_path)
    claim(mission.repo)
    commit_file(mission.holder, owned_path(SIBLING_WP), "WP02 research notes")

    assert evaluate_for_review_gate(mission.repo, SLUG, PLANNING_WP).passed is True


# --- the #5296 code-lane waiver for the Mission-branch checkout ---------------------------------


def test_code_lanes_are_never_required_in_the_mission_branch_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The waiver no longer depends on the repository root checkout's branch for the Mission-branch checkout."""
    from specify_cli.lanes import implement_support
    from specify_cli.lanes.branch_naming import lane_branch_name

    mission = settled_default_mission(tmp_path, planning_depends_on_code=True)
    # An approved code lane whose tip is not an ancestor of the Mission branch.
    git_out(mission.repo, "branch", lane_branch_name(SLUG, CODE_LANE, target_branch=TARGET), TARGET)
    monkeypatch.setattr(implement_support, "_dependency_lane_status", lambda _dir: {CODE_WP: "approved"})
    # The root checkout is off the target: the pre-#7860 waiver (root on target) would not fire.
    git_out(mission.repo, "checkout", "-q", "-b", "scratch")
    workspace = resolve_workspace_for_wp(mission.repo, SLUG, PLANNING_WP)
    assert workspace.resolution_kind == MISSION_BRANCH_CHECKOUT_KIND

    result = check_claim_ancestry(mission.repo, SLUG, mission.mission_dir, PLANNING_WP, workspace.worktree_path)

    assert result.ok is True
    assert result.missing_refs == ()
    assert result.code_lanes_deferred_to == TARGET


def test_the_waiver_still_requires_code_lanes_for_an_explicit_planning_lane_off_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: an explicit topology with the root checkout off the target keeps today's requirement."""
    from specify_cli.lanes import implement_support
    from specify_cli.lanes.branch_naming import lane_branch_name

    repo = tmp_path / "repo"
    _init(repo)
    commit_mission(repo, meta(topology_source=None), planning_depends_on_code=True)
    lane_branch = lane_branch_name(SLUG, CODE_LANE, target_branch=TARGET)
    git_out(repo, "branch", lane_branch, TARGET)
    commit_file(repo, "lane-only.txt", "placeholder")
    git_out(repo, "branch", "-f", lane_branch, "HEAD")
    git_out(repo, "reset", "-q", "--hard", "HEAD~1")
    monkeypatch.setattr(implement_support, "_dependency_lane_status", lambda _dir: {CODE_WP: "approved"})
    git_out(repo, "checkout", "-q", "-b", "scratch")

    result = check_claim_ancestry(repo, SLUG, repo / "kitty-specs" / SLUG, PLANNING_WP, repo)

    assert result.ok is False
    assert result.code_lanes_deferred_to is None


def test_the_planning_self_heal_reconciles_the_checkout_the_ancestry_was_judged_in(tmp_path: Path) -> None:
    """The self-heal re-check reads the Mission-branch checkout for a default Mission, the root checkout otherwise."""
    from specify_cli.lanes.implement_support import _planning_self_heal_workspace

    (tmp_path / "default").mkdir()
    mission = settled_default_mission(tmp_path / "default")
    planning_lane = manifest().lanes[0]
    explicit = tmp_path / "explicit" / "repo"
    explicit.parent.mkdir()
    _init(explicit)
    commit_mission(explicit, meta(topology_source=None))

    assert _planning_self_heal_workspace(mission.repo, SLUG, PLANNING_WP, planning_lane, manifest()).resolve() == mission.holder.resolve()
    assert _planning_self_heal_workspace(explicit, SLUG, PLANNING_WP, planning_lane, manifest()) == explicit


def test_a_default_single_branch_missions_waiver_is_unchanged(tmp_path: Path) -> None:
    """A stored ``single_branch`` Mission keeps the repository root checkout: nothing is deferred to the target."""
    repo = tmp_path / "repo"
    _init(repo)
    git_out(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    commit_mission(repo, meta(topology="single_branch", coordination_branch=None))
    workspace = resolve_workspace_for_wp(repo, SLUG, PLANNING_WP)
    assert workspace.resolution_kind == "repo_root"

    result = check_claim_ancestry(repo, SLUG, repo / "kitty-specs" / SLUG, PLANNING_WP, repo)

    assert result.code_lanes_deferred_to is None


def test_native_implement_records_the_mission_branch_checkouts_head(tmp_path: Path) -> None:
    """``spec-kitty implement`` reaches the claim seam through workspace creation."""
    from specify_cli.lanes.implement_support import create_lane_workspace

    mission = settled_default_mission(tmp_path)
    workspace = resolve_workspace_for_wp(mission.repo, SLUG, PLANNING_WP)
    wp_file = mission.mission_dir / "tasks" / f"{PLANNING_WP}-plan.md"

    result = create_lane_workspace(mission.repo, SLUG, PLANNING_WP, wp_file, workspace, manifest(), [], "git")

    assert result.workspace_path.resolve() == mission.holder.resolve()
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) == git_out(mission.holder, "rev-parse", "HEAD")


def test_the_gate_fails_closed_when_the_mission_branch_checkout_has_no_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never report the target as the Mission branch."""
    from dataclasses import replace

    from specify_cli.workspace import context

    mission = settled_default_mission(tmp_path)
    claim(mission.repo)
    commit_file(mission.holder, owned_path(PLANNING_WP), "WP01 research notes")
    real = context.resolve_workspace_for_wp
    monkeypatch.setattr(context, "resolve_workspace_for_wp", lambda *a, **k: replace(real(*a, **k), branch_name=None))

    decision = evaluate_for_review_gate(mission.repo, SLUG, PLANNING_WP)

    assert decision.passed is False
    assert decision.lane_branch is None
    assert "resolved with no branch name" in decision.reason


# --- the agent claim path, end to end (review cycle 1, finding 1) --------------------------------


@pytest.mark.timeout(900)
def test_agent_action_implement_records_the_claim_base_and_the_gate_passes_owned_work(tmp_path: Path) -> None:
    """``agent action implement`` on a settled default Mission's planning WP records the base from the coordination worktree.

    Then an owned commit there passes the ``for_review`` claim-base gate on ``move-task``. The
    evidence axis is WP04's: until it is merged, its ``IMPLEMENTATION_MISSING`` refusal may still
    follow the gate, never the gate's own "no implementation commit since claim" refusal.
    """
    from tests.integration.test_7860_planning_evidence_window import (
        _claim_planning_wp,
        _commit_owned,
        _move_into_review,
        setup_default_mission,
    )

    mission = setup_default_mission(tmp_path)
    relpath = _claim_planning_wp(mission)

    base = read_claim_base(mission.repo, mission.slug, "WP02")
    assert base is not None, "agent action implement recorded no claim base"
    # Recorded from the coordination worktree before the claim's own status commits: on the
    # Mission branch, and never the target's tip (the repository root checkout).
    git_out(mission.repo, "merge-base", "--is-ancestor", base, mission.topic_branch)
    assert base != git_out(mission.repo, "rev-parse", "main")
    assert git_out(mission.repo, "merge-base", base, "main") != base

    hollow = evaluate_for_review_gate(mission.repo, mission.slug, "WP02")
    assert hollow.passed is False, hollow
    _commit_owned(mission.topic_checkout, relpath)
    gate = evaluate_for_review_gate(mission.repo, mission.slug, "WP02")
    assert gate.passed is True, gate
    assert gate.lane_branch == mission.topic_branch
    moved = _move_into_review(mission)
    output = moved.stdout + moved.stderr

    assert "no implementation commit since claim" not in output, output[-3000:]
    assert moved.returncode == 0 or "IMPLEMENTATION_MISSING" in output, output[-3000:]


def test_the_agent_claim_seam_records_only_for_a_shared_checkout_and_never_fails_the_claim(tmp_path: Path) -> None:
    """A lane worktree records nothing here; an unborn ``HEAD`` records nothing and does not raise."""
    from dataclasses import replace

    from specify_cli.cli.commands.agent.workflow_executor import _record_shared_checkout_claim_base

    (tmp_path / "m").mkdir()
    mission = settled_default_mission(tmp_path / "m")
    workspace = resolve_workspace_for_wp(mission.repo, SLUG, PLANNING_WP)
    _record_shared_checkout_claim_base(mission.repo, SLUG, PLANNING_WP, replace(workspace, resolution_kind="lane_workspace"))
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) is None

    unborn = tmp_path / "unborn"
    unborn.mkdir()
    git_out(unborn, "init", "-q", "-b", TARGET)
    _record_shared_checkout_claim_base(unborn, SLUG, PLANNING_WP, replace(workspace, worktree_path=unborn))
    assert read_claim_base(unborn, SLUG, PLANNING_WP) is None

    _record_shared_checkout_claim_base(mission.repo, SLUG, PLANNING_WP, workspace)
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) == git_out(mission.holder, "rev-parse", "HEAD")
