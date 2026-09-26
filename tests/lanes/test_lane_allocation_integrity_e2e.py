"""Cross-cutting e2e integration regression for #4889 + #4905 (WP03).

Proves BOTH defects are dead **together** on a realistic coord-topology
mission, driving the REAL entry points -- never the internal
``allocate_lane_worktree`` helper directly (unlike
``tests/lanes/test_issue_4889_destroyed_lane_guard.py``, which calls the
allocator in-process to pin the decision table) and never a single caller
only (unlike ``tests/specify_cli/cli/commands/agent/
test_issue_4905_coord_staging.py``, which drives ``agent action implement``
exclusively).

Entry points exercised here:

* ``spec-kitty implement`` -- the plain top-level CLI command
  (``cli/commands/implement.py::implement`` -> ``lanes/implement_support.py::
  create_lane_workspace`` -> ``allocate_lane_worktree``).
* ``spec-kitty agent action implement`` / ``agent action review`` /
  ``agent tasks move-task`` -- the coord lifecycle surface
  (``cli/commands/agent/workflow.py`` /
  ``workflow_executor.py::implement_claim_transition`` ->
  ``_commit_via_coordination_transaction``, the shared sink #4905 fixed).
* the orchestrator-api ``start-implementation`` command
  (``orchestrator_api/commands.py::_resolve_start_workspace`` ->
  ``allocate_lane_worktree``) -- the non-CLI caller FR-008 requires the
  #4889 guard to cover independently of the CLI.

RED/GREEN provenance (T023, ADR 2026-07-17-1)
-----------------------------------------------
This lane already carries both fixes (WP01's ``DestroyedLaneError`` guard in
``src/specify_cli/lanes/worktree_allocator.py`` and WP02's
``_partition_paths_by_primary_kind`` sink partition in
``src/specify_cli/cli/commands/agent/workflow.py``), so every test below is
GREEN as committed. Red-first intent (mutation-sense) is confirmed by
reasoning from the two WPs' diffs rather than by a live revert-and-restore
in this shared lane worktree:

* Reverting WP01's guard (dropping the ``_refuse_if_lane_destroyed`` call
  before ``allocate_lane_worktree``'s FRESH route) would make
  ``test_destroyed_lane_fail_closed_e2e`` fail: the CLI would print
  ``Lane worktree ready`` and exit 0 instead of refusing, and the
  orchestrator's ``start-implementation`` would return a fresh
  ``workspace_path`` instead of ``LANE_ALLOCATION_FAILED``.
* Reverting WP02's partition (routing PRIMARY-partition paths back onto the
  coordination worktree) would make ``test_coord_second_wp_starts_e2e``
  fail: ``_wp_task_blobs_on_coord`` would find ``tasks/WP01.md`` on the
  coordination branch tree, and WP02's claim would raise
  ``PlanningCommitMergeConflictError`` instead of exiting 0.

Demotion note: WP01's ``tests/lanes/test_issue_4889_destroyed_lane_guard.py``
already has a focused unit home for the allocator decision table (it calls
``allocate_lane_worktree`` directly), and WP02's
``tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py``
already has a focused unit home for the per-funnel-site partition. Neither
is redundant with this file today -- this module adds the CROSS-CUTTING /
caller-independence proof neither of those exercises (the orchestrator-api
caller for #4889; the combined #4889+#4905 interaction for #4905) -- so
nothing is marked for demotion here. Per red-first-tests-are-transitional,
if a future change gives the orchestrator-api caller and the interaction
proof their own focused unit coverage, this file's ``@pytest.mark.
regression`` marker becomes the demotion candidate instead.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner, Result

from specify_cli import app as root_app
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.analysis_report import write_analysis_report
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.orchestrator_api.commands import app as orchestrator_app
from specify_cli.workspace.context import WorkspaceContext, find_context_for_wp, get_context_path
from tests.lane_test_utils import derive_mission_id
from tests.specify_cli.charter_preflight._fixtures import (
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
    write_metadata,
)
from tests.utils import _seed_canonical_wp_state, write_wp

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

runner = CliRunner()

_ANALYSIS_REPORT_BODY = "# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n"
_TARGET_BRANCH = "mission-target"


# ---------------------------------------------------------------------------
# git / coord-tree helpers (mirrors test_issue_4905_coord_staging.py)
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _rev_parse(repo_root: Path, ref: str = "HEAD") -> str:
    return _git(repo_root, "rev-parse", ref).stdout.strip()


def _coord_tree_paths(repo_root: Path, coord_branch: str) -> list[str]:
    out = _git(repo_root, "ls-tree", "-r", "--name-only", coord_branch)
    return [line for line in out.stdout.splitlines() if line]


def _wp_task_blobs_on_coord(repo_root: Path, coord_branch: str, mission_dirname: str) -> list[str]:
    prefix = f"kitty-specs/{mission_dirname}/tasks/"
    return [p for p in _coord_tree_paths(repo_root, coord_branch) if p.startswith(prefix) and p.endswith(".md")]


def _write_acceptance_matrix_for(feature_dir: Path, mission_dirname: str) -> None:
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=mission_dirname,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-01",
                    description="#4889/#4905 e2e integration fixture is self-consistent",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Mission fixture (adapted from test_issue_4905_coord_staging.py's
# ``_build_two_lane_coord_mission`` -- a divergent-DAG coord mission whose
# coord branch NEVER carries a ``kitty-specs/tasks/*.md`` blob through shared
# ancestry, matching the real coord-mint-before-planning-finishes shape) so
# ``kitty-specs/<slug>/tasks/WP*.md`` is a genuine post-fix invariant, not an
# accident of construction.
# ---------------------------------------------------------------------------


def _build_coord_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mission_slug: str,
) -> tuple[Path, str, str]:
    """Build a 2-lane coord-topology mission (WP01 -> lane-a, WP02 -> lane-b).

    Returns ``(repo_root, mission_dirname, coord_branch)``. The repo is left
    checked out on the target/planning branch (mirrors a real
    ``spec-kitty implement`` invocation, always run from the primary
    checkout) and ``SPECIFY_REPO_ROOT``/cwd are pointed at it.
    """
    repo_root = tmp_path / mission_slug / "repo"
    repo_root.mkdir(parents=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "wp03-e2e@example.invalid")
    _git(repo_root, "config", "user.name", "WP03 Regression")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")

    charter_path, metadata_path = seed_charter(repo_root)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo_root)
    seed_charter_yaml(repo_root)
    seed_manifest(repo_root, built_in_only=False)
    seed_graph(repo_root)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "anchor")
    anchor_sha = _rev_parse(repo_root)

    mission_id = derive_mission_id(mission_slug)
    mid8 = mission_id[:8]
    mission_dirname = f"{mission_slug}-{mid8}"
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"

    # --- COORD branch: coord-owned (STATUS_STATE / ACCEPTANCE_MATRIX) content
    # only -- deliberately NEVER a kitty-specs/tasks/*.md blob. ---
    _git(repo_root, "checkout", "-q", "-b", coord_branch)
    coord_feature_dir = repo_root / "kitty-specs" / mission_dirname
    coord_feature_dir.mkdir(parents=True)
    for wp_id, ts_suffix in (("WP01", "01"), ("WP02", "02")):
        _seed_canonical_wp_state(
            repo_root,
            mission_dirname,
            wp_id,
            "planned",
            actor="system",
            assignee="Owner",
            shell_pid="1234",
            timestamp=f"2025-01-01T00:00:{ts_suffix}Z",
        )
    _write_acceptance_matrix_for(coord_feature_dir, mission_dirname)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "coord: bootstrap status + acceptance-matrix")

    # --- TARGET/planning branch: PRIMARY-partition content only. ---
    _git(repo_root, "checkout", "-q", anchor_sha)
    _git(repo_root, "checkout", "-q", "-b", _TARGET_BRANCH)
    for path_dir in ("src", "tests", "docs"):
        (repo_root / path_dir).mkdir(exist_ok=True)

    target_feature_dir = repo_root / "kitty-specs" / mission_dirname
    target_feature_dir.mkdir(parents=True)
    (target_feature_dir / "contracts").mkdir(exist_ok=True)
    (target_feature_dir / "spec.md").write_text("# Spec\n\nFR-001: Demo spec for #4889/#4905 e2e fixture.\n", encoding="utf-8")
    (target_feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (target_feature_dir / "tasks.md").write_text(
        "## WP01\n\n- [ ] T001 Placeholder task\n\n## WP02\n\n- [ ] T002 Placeholder task\n",
        encoding="utf-8",
    )
    (target_feature_dir / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (target_feature_dir / "data-model.md").write_text("# Data model\n", encoding="utf-8")
    (target_feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")

    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_slug": mission_slug,
        "slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "coordination_branch": coord_branch,
        "friendly_name": "WP03 #4889/#4905 e2e integration mission",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (target_feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_wp(repo_root, mission_dirname, "planned", "WP01", seed_canonical=False)
    write_wp(repo_root, mission_dirname, "planned", "WP02", seed_canonical=False)

    write_analysis_report(
        feature_dir=target_feature_dir,
        repo_root=repo_root,
        body=_ANALYSIS_REPORT_BODY,
        analyzer_agent="test",
    )

    lanes_manifest = LanesManifest(
        version=1,
        mission_slug=mission_dirname,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{mission_dirname}",
        target_branch=_TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=("test",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id="lane-b",
                wp_ids=("WP02",),
                write_scope=("src/**",),
                predicted_surfaces=("test",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-01-01T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(target_feature_dir, lanes_manifest)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record spec/plan/tasks + WP01/WP02")
    planning_commit_sha = _rev_parse(repo_root)

    lanes_manifest.planning_commit_sha = planning_commit_sha
    write_lanes_json(target_feature_dir, lanes_manifest)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record planning_commit_sha")

    CoordinationWorkspace.resolve(repo_root, mission_dirname, mid8)

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root, mission_dirname, coord_branch


# ---------------------------------------------------------------------------
# Real-entry-point invocation helpers
# ---------------------------------------------------------------------------


def _valid_policy_json() -> str:
    return json.dumps(
        {
            "orchestrator_id": "wp03-e2e",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )


def _run_cli_implement(mission_dirname: str, wp_id: str, *, actor: str = "test-actor") -> Result:
    """Drive the real top-level ``spec-kitty implement`` CLI command."""
    return runner.invoke(
        root_app,
        ["implement", wp_id, "--mission", mission_dirname, "--actor", actor],
    )


def _run_agent_action_implement(mission_dirname: str, wp_id: str, *, agent: str = "test-agent") -> Result:
    """Drive the real ``spec-kitty agent action implement`` CLI command."""
    return runner.invoke(
        root_app,
        [
            "agent",
            "action",
            "implement",
            wp_id,
            "--mission",
            mission_dirname,
            "--agent",
            agent,
            "--allow-sparse-checkout",
        ],
    )


def _run_agent_action_review(mission_dirname: str, wp_id: str, *, agent: str = "reviewer-renata") -> Result:
    return runner.invoke(
        root_app,
        ["agent", "action", "review", wp_id, "--mission", mission_dirname, "--agent", agent],
    )


def _run_move_task(mission_dirname: str, wp_id: str, to_lane: str) -> Result:
    return runner.invoke(
        root_app,
        ["agent", "tasks", "move-task", wp_id, "--to", to_lane, "--mission", mission_dirname],
    )


def _run_start_implementation(repo_root: Path, mission_dirname: str, wp_id: str) -> Result:
    """Drive the real orchestrator-api ``start-implementation`` command."""
    with patch(
        "specify_cli.orchestrator_api.commands._get_main_repo_root",
        return_value=repo_root,
    ):
        return runner.invoke(
            orchestrator_app,
            [
                "start-implementation",
                "--mission",
                mission_dirname,
                "--wp",
                wp_id,
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )


def _destroy_lane(repo_root: Path, worktree_path: Path, branch: str) -> None:
    """Delete a lane's worktree AND local branch (the #4889 defect trigger)."""
    _git(repo_root, "worktree", "remove", "--force", str(worktree_path))
    _git(repo_root, "branch", "-D", branch)


def _commit_real_work(worktree_path: Path, *, filename: str = "feature.py", content: str = "value = 42\n") -> str:
    """Commit real (non-stub) work in a lane worktree; returns the new commit SHA."""
    (worktree_path / filename).write_text(content, encoding="utf-8")
    _git(worktree_path, "add", filename)
    _git(worktree_path, "commit", "-q", "-m", f"feat: real work in {filename}")
    return _rev_parse(worktree_path)


def _wp_context(repo_root: Path, mission_dirname: str, wp_id: str) -> WorkspaceContext:
    context = find_context_for_wp(repo_root, mission_dirname, wp_id)
    assert context is not None, f"expected a persisted WorkspaceContext for {wp_id} after claim"
    return context


# ---------------------------------------------------------------------------
# T020 -- #4889 e2e across routes + callers
# ---------------------------------------------------------------------------


def test_destroyed_lane_fail_closed_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive a coord mission to ``in_progress``, destroy the lane, and refuse
    via BOTH the real CLI (``spec-kitty implement``) and the real
    orchestrator-api (``start-implementation``) callers -- FR-008
    caller-independence, on the identical destroyed state so both refusals
    provably see the same fail-closed condition.
    """
    repo_root, mission_dirname, _coord_branch = _build_coord_mission(tmp_path, monkeypatch, mission_slug="wp03-4889-e2e")

    claim = _run_cli_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output

    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = repo_root / context.worktree_path
    branch_name = context.branch_name
    assert worktree_path.exists()
    assert branch_exists(repo_root, branch_name)

    work_sha = _commit_real_work(worktree_path)
    # The commit is real, git-object-backed work -- confirm it exists before
    # destruction (sanity, not the interesting assertion below).
    assert _git(repo_root, "cat-file", "-e", work_sha).returncode == 0

    context_path = get_context_path(repo_root, f"{mission_dirname}-{context.lane_id}")
    context_before = context_path.read_text(encoding="utf-8")

    _destroy_lane(repo_root, worktree_path, branch_name)
    assert not worktree_path.exists()
    assert not branch_exists(repo_root, branch_name)

    # The stranded commit is not gone -- only unreferenced -- so it must
    # still be a resolvable git object (recoverable via reflog/fsck, exactly
    # what the diagnostic below points at).
    strand_check = _git(repo_root, "cat-file", "-e", work_sha)
    assert strand_check.returncode == 0, "stranded commit must remain a resolvable git object after lane destruction"

    # --- Caller 1: the real CLI entry point. ---
    cli_refusal = _run_cli_implement(mission_dirname, "WP01")
    assert cli_refusal.exit_code != 0, cli_refusal.output
    assert branch_name in cli_refusal.output, cli_refusal.output
    assert "reflog" in cli_refusal.output or "fsck" in cli_refusal.output, cli_refusal.output
    assert "Lane worktree ready" not in cli_refusal.output, cli_refusal.output
    assert context_path.read_text(encoding="utf-8") == context_before, "CLI refusal must not touch the persisted workspace context"
    assert not worktree_path.exists()
    assert not branch_exists(repo_root, branch_name)

    # --- Caller 2: the real orchestrator-api entry point, same destroyed state. ---
    orch_refusal = _run_start_implementation(repo_root, mission_dirname, "WP01")
    assert orch_refusal.exit_code == 1, orch_refusal.output
    orch_payload = json.loads(orch_refusal.output)
    assert orch_payload["error_code"] == "LANE_ALLOCATION_FAILED", orch_payload
    assert branch_name in json.dumps(orch_payload.get("data", {})), orch_payload
    assert not worktree_path.exists()
    assert not branch_exists(repo_root, branch_name)
    assert context_path.read_text(encoding="utf-8") == context_before, "orchestrator refusal must not touch the persisted workspace context"


def test_destroyed_lane_control_arms_still_succeed_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001 zero false positives, driven through the real CLI: REUSE,
    CRASH_RECOVERY, and a genuinely-fresh claim must all still succeed.
    """
    # --- REUSE: intact worktree + branch -> second claim is a no-op resume. ---
    repo_root, mission_dirname, _coord = _build_coord_mission(tmp_path, monkeypatch, mission_slug="wp03-4889-ctrl-reuse")
    first = _run_cli_implement(mission_dirname, "WP01")
    assert first.exit_code == 0, first.output
    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = repo_root / context.worktree_path
    branch_name = context.branch_name

    second = _run_cli_implement(mission_dirname, "WP01")
    assert second.exit_code == 0, second.output
    assert worktree_path.exists()
    assert branch_exists(repo_root, branch_name)

    # --- CRASH_RECOVERY: branch intact, worktree gone -> re-attach, not refusal. ---
    repo_root, mission_dirname, _coord = _build_coord_mission(tmp_path, monkeypatch, mission_slug="wp03-4889-ctrl-crash")
    claim = _run_cli_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output
    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = repo_root / context.worktree_path
    branch_name = context.branch_name

    _git(repo_root, "worktree", "remove", "--force", str(worktree_path))
    assert branch_exists(repo_root, branch_name)

    recovered = _run_cli_implement(mission_dirname, "WP01")
    assert recovered.exit_code == 0, recovered.output
    assert "Lane worktree ready" in recovered.output or "✓" in recovered.output, recovered.output
    assert worktree_path.exists()

    # --- Genuinely fresh: WP02 has never been claimed -> ordinary fresh allocation. ---
    repo_root, mission_dirname, _coord = _build_coord_mission(tmp_path, monkeypatch, mission_slug="wp03-4889-ctrl-fresh")
    fresh = _run_cli_implement(mission_dirname, "WP02")
    assert fresh.exit_code == 0, fresh.output
    context = _wp_context(repo_root, mission_dirname, "WP02")
    assert (repo_root / context.worktree_path).exists()


# ---------------------------------------------------------------------------
# T021 -- #4905 e2e WP01 -> WP02, plus multi-site coverage (claim + review-claim)
# ---------------------------------------------------------------------------


def test_coord_second_wp_starts_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A coord mission's WP01 claim, review-claim, and WP02's claim must all
    leave the coordination branch tree with zero ``tasks/WP*.md`` blobs, and
    WP02 must start without ``PlanningCommitMergeConflictError``.
    """
    repo_root, mission_dirname, coord_branch = _build_coord_mission(tmp_path, monkeypatch, mission_slug="wp03-4905-e2e")

    claim_wp01 = _run_agent_action_implement(mission_dirname, "WP01")
    assert claim_wp01.exit_code == 0, claim_wp01.output
    assert _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname) == []

    move = _run_move_task(mission_dirname, "WP01", "for_review")
    assert move.exit_code == 0, move.output

    review = _run_agent_action_review(mission_dirname, "WP01")
    assert review.exit_code == 0, review.output
    assert _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname) == [], "coord tree must stay clean after a review-claim too"

    claim_wp02 = _run_agent_action_implement(mission_dirname, "WP02")
    assert claim_wp02.exit_code == 0, claim_wp02.output
    assert "PlanningCommitMergeConflictError" not in claim_wp02.output, claim_wp02.output
    assert "PLANNING_COMMIT_MERGE_CONFLICT" not in claim_wp02.output, claim_wp02.output
    assert _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname) == []


# ---------------------------------------------------------------------------
# T022 -- interaction proof: the two fixes do not re-open each other
# ---------------------------------------------------------------------------


def test_fixes_are_independent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither fix perturbs the other's invariant:

    * a legitimate first claim (genuinely fresh, no prior context) never
      trips the #4889 guard, with the #4905 partition active;
    * a genuinely fresh SECOND lane (WP02) still allocates normally even
      while a DIFFERENT WP's (WP01's) lane is in the exact destroyed state
      #4889 must refuse, and the coord tree stays clean for it too;
    * the guard still correctly refuses WP01's own destroyed lane
      afterwards -- it is scoped to the destroyed WP, not a global freeze.
    """
    repo_root, mission_dirname, coord_branch = _build_coord_mission(tmp_path, monkeypatch, mission_slug="wp03-interaction")

    # Legitimate first claim: partition active, guard must not false-trip.
    claim_wp01 = _run_agent_action_implement(mission_dirname, "WP01")
    assert claim_wp01.exit_code == 0, claim_wp01.output
    assert _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname) == []

    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = repo_root / context.worktree_path
    branch_name = context.branch_name
    _commit_real_work(worktree_path)
    _destroy_lane(repo_root, worktree_path, branch_name)

    # A DIFFERENT, genuinely fresh lane (WP02) must still allocate normally --
    # the #4889 guard is scoped to WP01, and the #4905 partition must still
    # hold for WP02's claim even while WP01's destroyed-lane record exists.
    claim_wp02 = _run_agent_action_implement(mission_dirname, "WP02")
    assert claim_wp02.exit_code == 0, claim_wp02.output
    wp02_context = _wp_context(repo_root, mission_dirname, "WP02")
    assert (repo_root / wp02_context.worktree_path).exists()
    assert _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname) == [], (
        "the #4905 sink partition must not be suppressed by a concurrent #4889 destroyed-lane state"
    )

    # WP01's own destroyed lane must still refuse -- the guard is unaffected
    # by WP02's successful concurrent allocation.
    refusal = _run_agent_action_implement(mission_dirname, "WP01")
    assert refusal.exit_code != 0, refusal.output
    assert branch_name in refusal.output, refusal.output
