"""Regression guard for GitHub issue #4905 (P1) -- coord-staging partition.

On ``coord`` / ``lanes_with_coord`` topologies the agent-verb lifecycle commit
(``_commit_via_coordination_transaction``, the shared sink every claim /
resume-refresh / review-claim staging site funnels through) used to stage the
PRIMARY-partition ``kitty-specs/<slug>/tasks/WP*.md`` file onto the
coordination branch alongside the STATUS_STATE bookkeeping (``status.
events.jsonl`` / ``status.json``). The next lane, cut from that polluted coord
tip, then FR-009-merges the recorded planning commit (which independently
"adds" the very same ``tasks/WP*.md`` path from unrelated history) and hits an
add/add conflict -- ``PlanningCommitMergeConflictError``, exit 1 -- so a
later WP's ``implement`` could never even start.

The fix partitions the sink's staged paths by artifact kind
(``mission_runtime.kind_for_mission_file`` / ``is_primary_artifact_kind``):
a PRIMARY-partition path routes to the mission's PRIMARY target branch via a
second, ``commit_to_primary_target=True`` transaction and NEVER reaches the
coordination worktree; only STATUS_STATE stays on ``coord_branch`` as before.

Fixture note (deliberate divergence from ``tests/characterization/
test_trio_json_envelope.py::_build_mission_repo``): that shared fixture mints
the coordination branch AT the fully-populated mission-scaffold commit, so
its coord branch ALREADY carries ``tasks/WP01.md`` through shared ancestry --
unsuitable for a "coord tree has zero WP*.md blobs" assertion (it would be
false from construction, not from the bug). This module instead builds a
DIVERGENT DAG matching the real coord-topology shape: an anchor commit forks
into a coord branch (bootstrap STATUS_STATE + ACCEPTANCE_MATRIX only, never
kitty-specs/tasks/*) and a SEPARATE planning/target branch (spec/plan/tasks +
both WP files), mirroring ``tests/specify_cli/cli/commands/agent/
test_lane_hygiene_content_diff.py::_build_coord_status_state_scenario``'s DAG
shape, extended with the charter/analysis-report/acceptance-matrix scaffolding
the real CLI gates require.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from specify_cli import app as root_app
from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
from specify_cli.analysis_report import write_analysis_report
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
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


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _rev_parse(repo_root: Path, ref: str = "HEAD") -> str:
    return _git(repo_root, "rev-parse", ref).stdout.strip()


def _coord_tree_paths(repo_root: Path, coord_branch: str) -> list[str]:
    """List every blob path committed on ``coord_branch``'s tree."""
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
                    description="#4905 coord-staging-partition fixture is self-consistent",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        ),
    )


def _build_two_lane_coord_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mission_slug: str,
) -> tuple[Path, str, str]:
    """Build a 2-lane coord-topology mission (WP01 -> lane-a, WP02 -> lane-b).

    Returns ``(repo_root, mission_dirname, coord_branch)``. ``mission_dirname``
    doubles as the ``--mission`` CLI handle (the materialized-coord contract;
    see ``_build_mission_repo``'s own docstring for why the on-disk dirname
    must carry the ``-<mid8>`` suffix once a coord worktree is materialized).

    The repo is left checked out on the target/planning branch (mirrors a
    real ``spec-kitty implement`` invocation, always run from the primary
    checkout) and ``SPECIFY_REPO_ROOT``/cwd are pointed at it.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "issue-4905@example.invalid")
    _git(repo_root, "config", "user.name", "Issue-4905 Regression")
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
    target_branch = "mission-target"
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"

    # --- COORD branch: coord-owned (STATUS_STATE / ACCEPTANCE_MATRIX) content
    # only -- deliberately NEVER a kitty-specs/tasks/*.md blob, matching the
    # real coord-mint-before-planning-finishes shape. ---
    _git(repo_root, "checkout", "-q", "-b", coord_branch)
    coord_feature_dir = repo_root / "kitty-specs" / mission_dirname
    coord_feature_dir.mkdir(parents=True)
    _seed_canonical_wp_state(
        repo_root,
        mission_dirname,
        "WP01",
        "planned",
        actor="system",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2025-01-01T00:00:00Z",
    )
    _seed_canonical_wp_state(
        repo_root,
        mission_dirname,
        "WP02",
        "planned",
        actor="system",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2025-01-01T00:00:01Z",
    )
    _write_acceptance_matrix_for(coord_feature_dir, mission_dirname)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "coord: bootstrap status + acceptance-matrix")

    # --- TARGET/planning branch: PRIMARY-partition content only. ---
    _git(repo_root, "checkout", "-q", anchor_sha)
    _git(repo_root, "checkout", "-q", "-b", target_branch)
    for path_dir in ("src", "tests", "docs"):
        (repo_root / path_dir).mkdir(exist_ok=True)

    target_feature_dir = repo_root / "kitty-specs" / mission_dirname
    target_feature_dir.mkdir(parents=True)
    (target_feature_dir / "contracts").mkdir(exist_ok=True)
    (target_feature_dir / "spec.md").write_text("# Spec\n\nFR-001: Demo spec for #4905 coord-staging fixture.\n", encoding="utf-8")
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
        "target_branch": target_branch,
        "coordination_branch": coord_branch,
        "friendly_name": "Issue #4905 coord-staging-partition mission",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (target_feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # WP files land on PRIMARY only -- seed_canonical=False so no *primary*
    # status.events.jsonl copy is written (canonical status lives on coord
    # exclusively, matching the real coord-topology contract; a stray primary
    # copy would be harmless but is not representative).
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
        target_branch=target_branch,
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

    # Second commit: now that the planning commit SHA is known, record it on
    # the manifest (FR-009 / ADR 2026-07-29-1) so lane allocation merges it.
    lanes_manifest.planning_commit_sha = planning_commit_sha
    write_lanes_json(target_feature_dir, lanes_manifest)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record planning_commit_sha")

    CoordinationWorkspace.resolve(repo_root, mission_dirname, mid8)

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root, mission_dirname, coord_branch


def _build_flat_two_lane_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mission_slug: str,
) -> tuple[Path, str]:
    """Build a ``lanes``-topology (no coordination_branch) control mission.

    Everything -- planning artifacts, WP files, and status -- lives on the
    single target/primary branch; there is no coordination branch to pollute.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "issue-4905@example.invalid")
    _git(repo_root, "config", "user.name", "Issue-4905 Regression")
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
    _git(repo_root, "commit", "-q", "-m", "seed")

    target_branch = "mission-target"
    _git(repo_root, "checkout", "-q", "-b", target_branch)
    for path_dir in ("src", "tests", "docs"):
        (repo_root / path_dir).mkdir(exist_ok=True)

    mission_id = derive_mission_id(mission_slug)
    mid8 = mission_id[:8]
    mission_dirname = mission_slug

    feature_dir = repo_root / "kitty-specs" / mission_dirname
    feature_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001: Demo.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "## WP01\n\n- [ ] T001 Placeholder task\n\n## WP02\n\n- [ ] T002 Placeholder task\n",
        encoding="utf-8",
    )
    (feature_dir / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (feature_dir / "data-model.md").write_text("# Data model\n", encoding="utf-8")
    (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")

    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_slug": mission_slug,
        "slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "friendly_name": "Issue #4905 lanes-topology control mission",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_wp(repo_root, mission_dirname, "planned", "WP01")
    write_wp(repo_root, mission_dirname, "planned", "WP02")

    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body=_ANALYSIS_REPORT_BODY,
        analyzer_agent="test",
    )
    _write_acceptance_matrix_for(feature_dir, mission_dirname)

    lanes_manifest = LanesManifest(
        version=1,
        mission_slug=mission_dirname,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{mission_dirname}",
        target_branch=target_branch,
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
    write_lanes_json(feature_dir, lanes_manifest)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record spec/plan/tasks + WP01/WP02")
    planning_commit_sha = _rev_parse(repo_root)
    lanes_manifest.planning_commit_sha = planning_commit_sha
    write_lanes_json(feature_dir, lanes_manifest)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record planning_commit_sha")

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root, mission_dirname


def _run_implement(mission_dirname: str, wp_id: str) -> Result:
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
            "test-agent",
            "--allow-sparse-checkout",
        ],
    )


# ---------------------------------------------------------------------------
# T010 -- red-first repro (coord pollution on claim)
# ---------------------------------------------------------------------------


def test_claim_does_not_stage_wp_file_on_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED on pre-fix code: WP01's claim stages tasks/WP01.md onto coord.

    Asserts the DESIRED post-fix state directly (ADR 2026-07-17-1): after a
    real ``agent action implement WP01`` claim on a coord mission, the
    coordination branch tree has ZERO ``tasks/WP*.md`` blobs.
    """
    repo_root, mission_dirname, coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="coord-staging-4905")

    result = _run_implement(mission_dirname, "WP01")
    assert result.exit_code == 0, result.output

    flagged = _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname)
    assert flagged == [], f"#4905 regression: WP01's claim staged a WP file onto the coordination branch: {flagged!r}"


# ---------------------------------------------------------------------------
# T011 -- red-first repro (WP02 planning-merge conflict)
# ---------------------------------------------------------------------------


def test_wp02_starts_without_planning_merge_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED on pre-fix code: WP02's lane allocation hits PlanningCommitMergeConflictError.

    WP01's claim (lane-a) runs first; pre-fix it pollutes the coordination
    branch with ``tasks/WP01.md``. WP02's FIRST ``implement`` call then cuts a
    fresh lane-b worktree from that (polluted) coord tip and FR-009-merges the
    recorded planning commit -- which independently "adds" the same
    ``tasks/WP01.md`` path from unrelated history -- producing an add/add
    conflict pre-fix. Post-fix, coord never carries the WP file, so the merge
    is a clean add-only and WP02 starts (exit 0).
    """
    repo_root, mission_dirname, coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="coord-staging-4905-wp02")

    claim_wp01 = _run_implement(mission_dirname, "WP01")
    assert claim_wp01.exit_code == 0, claim_wp01.output

    claim_wp02 = _run_implement(mission_dirname, "WP02")
    assert claim_wp02.exit_code == 0, claim_wp02.output
    assert "PlanningCommitMergeConflictError" not in claim_wp02.output, claim_wp02.output
    assert "PLANNING_COMMIT_MERGE_CONFLICT" not in claim_wp02.output, claim_wp02.output

    flagged = _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname)
    assert flagged == [], f"#4905 regression: coord carries WP file(s) after WP02 started: {flagged!r}"


# ---------------------------------------------------------------------------
# T015 -- multi-site coverage: resume-refresh + review-claim, lanes control
# ---------------------------------------------------------------------------


def test_resume_refresh_does_not_stage_wp_file_on_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED on pre-fix code: the resume-refresh funnel site also pollutes coord.

    A second ``implement WP01`` call while WP01 is already ``in_progress``
    takes the resume-refresh path (``workflow_executor.py:1066``, distinct
    from the claim site) rather than re-claiming. Covers SC-003's "one
    assertion per funnel site" requirement.
    """
    repo_root, mission_dirname, coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="coord-staging-4905-resume")

    first = _run_implement(mission_dirname, "WP01")
    assert first.exit_code == 0, first.output

    second = _run_implement(mission_dirname, "WP01")
    assert second.exit_code == 0, second.output

    flagged = _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname)
    assert flagged == [], f"#4905 regression: resume-refresh staged a WP file onto the coordination branch: {flagged!r}"


def test_review_claim_does_not_stage_wp_file_on_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED on pre-fix code: the review-claim funnel site also pollutes coord.

    Drives WP01 from ``planned`` through a real claim to ``for_review`` (via
    ``move-task``), then a real ``agent action review WP01`` claim -- the
    ``for_review -> in_review`` funnel site (``workflow_executor.py:1741``).
    """
    repo_root, mission_dirname, coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="coord-staging-4905-review")

    claim = _run_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output

    move = runner.invoke(
        root_app,
        ["agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", mission_dirname],
    )
    assert move.exit_code == 0, move.output

    review = runner.invoke(
        root_app,
        ["agent", "action", "review", "WP01", "--mission", mission_dirname, "--agent", "reviewer-renata"],
    )
    assert review.exit_code == 0, review.output

    flagged = _wp_task_blobs_on_coord(repo_root, coord_branch, mission_dirname)
    assert flagged == [], f"#4905 regression: the review-claim funnel staged a WP file onto the coordination branch: {flagged!r}"


def test_lanes_topology_control_unaffected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: a ``lanes``-topology (no coordination_branch) mission is unaffected.

    There is no coord branch to pollute; both WP claims must simply succeed,
    exactly as before this fix.
    """
    repo_root, mission_dirname = _build_flat_two_lane_mission(tmp_path, monkeypatch, mission_slug="lanes-only-4905")

    claim_wp01 = _run_implement(mission_dirname, "WP01")
    assert claim_wp01.exit_code == 0, claim_wp01.output

    claim_wp02 = _run_implement(mission_dirname, "WP02")
    assert claim_wp02.exit_code == 0, claim_wp02.output
    assert "PlanningCommitMergeConflictError" not in claim_wp02.output, claim_wp02.output
