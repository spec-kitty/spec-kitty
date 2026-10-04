"""The destroyed-lane guard on LANES/flat (non-coord) missions, through the implement CLI.

Originally the #5115 (P0) red-first repro.

Today (before this WP), the guard's base-reachability check
(``_lane_base_reachable_from_target``) compares a lane's creation base
against its mission's target branch. On a COORD-topology mission that base is
the coordination branch -- genuinely unreachable from the target until
consolidation lands it, so the check does its job. On a LANES-topology
mission (no coordination branch at all) the base is the LEGACY
``mission_branch``, which is forked directly from -- and never diverges from
-- the target branch: it is ALWAYS an ancestor. The base-reachability check
therefore NEVER fires for this topology, and a destroyed lane holding real,
unmerged, committed work is silently re-cut empty by the FRESH route --
exactly the #5115 P0.

Trim note (#5618 part 2): one smoke per behaviour is kept here -- the refusal naming the
tip, a squash-merged lane re-opening, and the live-branch tip backfill (no seam guard turns
red when the REUSE-arm ``record_tip`` is removed, so it stays). The tip-equals-base,
inactive-recorder, ancestor-merged, deleted-context, unknown-tip and unevaluable-absorption
replays are pinned at the seam by ``test_destroyed_lane_guard_tip_rows.py``,
``test_issue_4889_destroyed_lane_guard.py`` and ``test_lane_tip.py``; each row was proven by a
planted break in ``worktree_allocator.py`` / ``lane_tip.py``.

This module's fixture (``_build_lanes_mission``) is the NO-COORD sibling of
``test_lane_allocation_integrity_e2e.py``'s ``_build_coord_mission``: same
anchor/charter/bundle scaffolding, but a single target branch carries
EVERYTHING (spec/plan/tasks, ``lanes.json``, AND the canonical status event
log) -- there is no coordination branch, and ``meta.json`` carries
``"topology": "lanes"`` with no ``coordination_branch`` field at all.

Status: the #5115 defect is FIXED; these tests are permanent guards against it recurring
(history: they began as red-first reproductions, with ``test_destroyed_lane_refuses_and_names_tip``
committed alone and failing at the ``exit_code != 0`` assertion).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import Result

from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
from specify_cli.analysis_report import write_analysis_report
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.lane_test_utils import derive_mission_id
from tests.lanes.test_issue_4889_destroyed_lane_guard import _ids
from tests.lanes.test_lane_allocation_integrity_e2e import (
    _commit_real_work,
    _destroy_lane,
    _rev_parse,
    _run_cli_implement,
    _wp_context,
)
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

_TARGET_BRANCH = "mission-target"
_ANALYSIS_REPORT_BODY = "# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


def _underlying_exception(result: Result) -> BaseException | None:
    """Unwrap the ORIGINAL exception ``implement``'s generic ``except Exception as
    exc: ... raise typer.Exit(1) from exc`` handler chained.

    ``CliRunner.invoke`` reports its top-level ``.exception`` as the
    ``SystemExit`` click's own runner raises when converting ``typer.Exit`` --
    a fresh exception with no ``__cause__`` of its own. The ORIGINAL
    exception survives one level down, as ``SystemExit.__context__`` (the
    ``typer.Exit`` click's handler raised, itself chained ``from exc``) ``.
    __cause__``. Verified empirically against this exact typer/click version
    (see the WP07 handoff report) rather than assumed from documentation.
    """
    exc = result.exception
    context = getattr(exc, "__context__", None)
    return getattr(context, "__cause__", None)


def _write_acceptance_matrix_for(feature_dir: Path, mission_dirname: str) -> None:
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=mission_dirname,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-01",
                    description="#5115 non-coord destroyed-lane fixture is self-consistent",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        ),
    )


def _build_lanes_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mission_slug: str,
) -> tuple[Path, str]:
    """Build a single-lane, NO-COORD ``lanes``-topology mission (WP01 -> lane-a).

    Clone of ``test_lane_allocation_integrity_e2e.py::_build_coord_mission``
    with the coordination branch removed entirely: everything (planning
    artifacts, ``lanes.json``, AND the canonical status event log) lives on
    the ONE target branch, and ``meta.json`` carries no
    ``coordination_branch`` field -- the exact non-coord shape #5115 targets.
    Returns ``(repo_root, mission_dirname)``.
    """
    repo_root = tmp_path / mission_slug / "repo"
    repo_root.mkdir(parents=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "wp07-5115@example.invalid")
    _git(repo_root, "config", "user.name", "WP07 Regression")
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

    mission_id = derive_mission_id(mission_slug)
    mid8 = mission_id[:8]
    mission_dirname = f"{mission_slug}-{mid8}"

    _git(repo_root, "checkout", "-q", "-b", _TARGET_BRANCH)
    for path_dir in ("src", "tests", "docs"):
        (repo_root / path_dir).mkdir(exist_ok=True)

    feature_dir = repo_root / "kitty-specs" / mission_dirname
    feature_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001: Demo spec for the #5115 non-coord fixture.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01\n\n- [ ] T001 Placeholder task\n", encoding="utf-8")
    (feature_dir / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (feature_dir / "data-model.md").write_text("# Data model\n", encoding="utf-8")
    (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")

    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_slug": mission_slug,
        "slug": mission_slug,
        "mission_type": "software-dev",
        "topology": "lanes",
        "target_branch": _TARGET_BRANCH,
        "friendly_name": "WP07 #5115 non-coord regression mission",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_wp(repo_root, mission_dirname, "planned", "WP01", seed_canonical=False)

    write_analysis_report(
        feature_dir=feature_dir,
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
        ],
        computed_at="2026-01-01T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(feature_dir, lanes_manifest)

    _write_acceptance_matrix_for(feature_dir, mission_dirname)

    # #5115: the canonical status event log lives on THIS SAME branch --
    # there is no coordination branch to redirect the STATUS_STATE read to.
    _seed_canonical_wp_state(
        repo_root,
        mission_dirname,
        "WP01",
        "planned",
        actor="system",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2025-01-01T00:00:01Z",
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record spec/plan/tasks + WP01 (no coord)")
    planning_commit_sha = _rev_parse(repo_root)

    lanes_manifest.planning_commit_sha = planning_commit_sha
    write_lanes_json(feature_dir, lanes_manifest)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "planning: record planning_commit_sha")

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root, mission_dirname


@pytest.fixture(autouse=True)
def _isolated_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ambient ``core.hooksPath`` (or any other global config) leaks in.

    Without this, a developer machine's global ``core.hooksPath`` could
    redirect every hook install this module exercises, making the tests
    depend on the running machine's config instead of the fixture's own
    repo. Every test in this module drives real git commits through the
    installed hook, so this MUST be set before any of them run.
    """
    empty_config = tmp_path / "empty.gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))


# ---------------------------------------------------------------------------
# T028.1 -- permanent guard (defect fixed): destroyed lane refuses and names the tip
# ---------------------------------------------------------------------------


def test_destroyed_lane_refuses_and_names_tip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    ids = _ids(request.node.name)
    repo_root, mission_dirname = _build_lanes_mission(tmp_path, monkeypatch, mission_slug=ids.mission_slug)

    claim = _run_cli_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output

    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = Path(repo_root) / context.worktree_path
    branch_name = context.branch_name

    # Plain `git commit` in the lane worktree -- the pre-commit ownership
    # guard the CLI's own `implement` install must pass this untouched.
    work_sha = _commit_real_work(worktree_path)

    _destroy_lane(repo_root, worktree_path, branch_name)
    assert not worktree_path.exists()
    assert not branch_exists(repo_root, branch_name)

    refusal = _run_cli_implement(mission_dirname, "WP01")

    assert refusal.exit_code != 0, refusal.output
    assert work_sha[:7] in refusal.output or work_sha in refusal.output
    assert "Lane worktree ready" not in refusal.output
    assert not worktree_path.exists()
    assert not branch_exists(repo_root, branch_name)

    from specify_cli.lanes.worktree_allocator import DestroyedLaneError

    exc = _underlying_exception(refusal)
    assert isinstance(exc, DestroyedLaneError)
    assert exc.error_code == "DESTROYED_LANE"
    assert exc.tip_sha == work_sha
    # NFR-004: the remedy names both the restore and the deliberate-abandon
    # commands against the recorded tip ref.
    assert f"refs/spec-kitty/lane-tip/{branch_name}" in exc.next_step
    assert "git branch" in exc.next_step
    assert "git update-ref -d" in exc.next_step

    recorded_tip = _git(repo_root, "rev-parse", f"refs/spec-kitty/lane-tip/{branch_name}").stdout.strip()
    assert recorded_tip == work_sha


# ---------------------------------------------------------------------------
# Control -- pins the ABSENCE of a false positive, not the fix itself
# ---------------------------------------------------------------------------


def test_squash_merged_lane_reopens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Control: a squash-merged (then destroyed) lane must still re-open."""
    ids = _ids(request.node.name)
    repo_root, mission_dirname = _build_lanes_mission(tmp_path, monkeypatch, mission_slug=ids.mission_slug)

    claim = _run_cli_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output
    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = Path(repo_root) / context.worktree_path
    branch_name = context.branch_name

    _commit_real_work(worktree_path)

    _git(repo_root, "checkout", "-q", _TARGET_BRANCH)
    _git(repo_root, "merge", "--squash", "-q", branch_name)
    _git(repo_root, "commit", "-q", "-m", "squash-merge lane-a into target")

    _destroy_lane(repo_root, worktree_path, branch_name)

    reopened = _run_cli_implement(mission_dirname, "WP01")

    assert reopened.exit_code == 0, reopened.output


# ---------------------------------------------------------------------------
# FR-021 -- live-branch tip backfill on touch
# ---------------------------------------------------------------------------


def test_live_branch_backfills_tip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """FR-021: a pre-existing lane with a live branch but no tip ref gets backfilled on touch."""
    ids = _ids(request.node.name)
    repo_root, mission_dirname = _build_lanes_mission(tmp_path, monkeypatch, mission_slug=ids.mission_slug)

    claim = _run_cli_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output
    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = Path(repo_root) / context.worktree_path
    branch_name = context.branch_name

    work_sha = _commit_real_work(worktree_path)

    # Simulate an upgraded clone: the tip was never recorded for this
    # pre-existing lane, but the branch and worktree are both still live.
    _git(repo_root, "update-ref", "-d", f"refs/spec-kitty/lane-tip/{branch_name}")
    # Nit (review cycle 1): assert on the git call's own result, not on a
    # bare rev-parse whose non-zero exit would otherwise surface as an
    # uncaught CalledProcessError rather than a clean assertion failure.
    from specify_cli.lanes.lane_tip import read_tip

    assert read_tip(repo_root, branch_name) is None

    touch = _run_cli_implement(mission_dirname, "WP01")
    assert touch.exit_code == 0, touch.output

    assert read_tip(repo_root, branch_name) == work_sha
