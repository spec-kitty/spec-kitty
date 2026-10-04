"""Permanent guard for GitHub issue #4905 (P1, fixed) -- coord-staging partition.

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
import re
import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
from specify_cli.analysis_report import check_analysis_report_current, write_analysis_report
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

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

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


def _seed_split_mission_event_logs(
    repo_root: Path,
    mission_dirname: str,
) -> tuple[Path, Path, bytes, bytes, Path]:
    """Seed retained, untracked mission-event logs on the primary and coord surfaces."""
    primary_feature_dir = repo_root / "kitty-specs" / mission_dirname
    metadata = json.loads((primary_feature_dir / "meta.json").read_text(encoding="utf-8"))
    coord_worktree = CoordinationWorkspace.worktree_path(
        repo_root,
        mission_dirname,
        str(metadata["mid8"]),
    )
    coord_feature_dir = coord_worktree / "kitty-specs" / mission_dirname
    primary_log = primary_feature_dir / "mission-events.jsonl"
    coord_log = coord_feature_dir / "mission-events.jsonl"

    primary_bytes = "".join(
        json.dumps(
            {
                "mission": mission_dirname,
                "payload": {"action": "discovery", "record": f"primary-{index}"},
                "timestamp": f"2026-09-28T00:00:0{index}+00:00",
                "type": "MissionNextInvoked",
            },
            sort_keys=True,
        )
        + "\n"
        for index in range(1, 5)
    ).encode("utf-8")
    coord_bytes = (
        json.dumps(
            {
                "mission": mission_dirname,
                "payload": {"action": "discovery", "record": "coord-later"},
                "timestamp": "2026-09-28T00:00:10+00:00",
                "type": "MissionNextInvoked",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    assert not primary_log.exists()
    assert not coord_log.exists()
    primary_log.write_bytes(primary_bytes)
    coord_log.write_bytes(coord_bytes)
    return primary_log, coord_log, primary_bytes, coord_bytes, coord_worktree


def _commit_primary_mission_event_log(repo_root: Path, mission_dirname: str) -> tuple[Path, bytes]:
    primary_log = repo_root / "kitty-specs" / mission_dirname / "mission-events.jsonl"
    primary_bytes = (
        json.dumps(
            {
                "mission": mission_dirname,
                "payload": {"action": "discovery", "record": "primary-committed"},
                "timestamp": "2026-09-28T00:00:01+00:00",
                "type": "MissionNextInvoked",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    primary_log.write_bytes(primary_bytes)
    event_log_rel = f"kitty-specs/{mission_dirname}/mission-events.jsonl"
    _git(repo_root, "add", event_log_rel)
    _git(repo_root, "commit", "-q", "-m", "planning: retain primary mission event log")
    return primary_log, primary_bytes


def _disable_auto_commit(repo_root: Path) -> None:
    (repo_root / ".kittify" / "config.yaml").write_text("auto_commit: false\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Claim-time guards: split mission event logs and dirty-planning gates
# ---------------------------------------------------------------------------


def test_claim_preserves_split_mission_event_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coord claim ignores the retained primary event log without merging either stream."""
    repo_root, mission_dirname, coord_branch = _build_two_lane_coord_mission(
        tmp_path,
        monkeypatch,
        mission_slug="coord-staging-4905-legacy-events",
    )
    primary_log, coord_log, primary_bytes, coord_bytes, coord_worktree = _seed_split_mission_event_logs(
        repo_root,
        mission_dirname,
    )
    event_log_rel = f"kitty-specs/{mission_dirname}/mission-events.jsonl"
    _disable_auto_commit(repo_root)

    assert _git(repo_root, "status", "--porcelain", "--untracked-files=all", "--", event_log_rel).stdout == f"?? {event_log_rel}\n"
    assert _git(coord_worktree, "status", "--porcelain", "--untracked-files=all", "--", event_log_rel).stdout == f"?? {event_log_rel}\n"
    assert event_log_rel not in _git(repo_root, "ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()
    assert event_log_rel not in _git(repo_root, "ls-tree", "-r", "--name-only", coord_branch).stdout.splitlines()

    result = _run_implement(mission_dirname, "WP01")

    assert result.exit_code == 0, result.output
    assert primary_log.read_bytes() == primary_bytes
    assert coord_log.read_bytes() == coord_bytes
    assert _git(repo_root, "status", "--porcelain", "--untracked-files=all", "--", event_log_rel).stdout == f"?? {event_log_rel}\n"
    assert _git(coord_worktree, "status", "--porcelain", "--untracked-files=all", "--", event_log_rel).stdout == f"?? {event_log_rel}\n"

    primary_tree_paths = _git(repo_root, "ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()
    coord_tree_paths = _git(repo_root, "ls-tree", "-r", "--name-only", coord_branch).stdout.splitlines()
    assert event_log_rel not in primary_tree_paths
    assert event_log_rel not in coord_tree_paths

    status_path = coord_worktree / "kitty-specs" / mission_dirname / "status.events.jsonl"
    status_events = [json.loads(line) for line in status_path.read_text(encoding="utf-8").splitlines()]
    assert any(event.get("wp_id") == "WP01" and event.get("to_lane") == "claimed" for event in status_events)


@pytest.mark.parametrize(
    ("stage_edit", "status_prefix"),
    [(False, " M "), (True, "M  ")],
    ids=["unstaged", "staged"],
)
def test_tracked_primary_mission_event_log_edit_still_blocks_coord_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage_edit: bool,
    status_prefix: str,
) -> None:
    repo_root, mission_dirname, coord_branch = _build_two_lane_coord_mission(
        tmp_path,
        monkeypatch,
        mission_slug="coord-staging-4905-tracked-events",
    )
    _disable_auto_commit(repo_root)
    primary_log, primary_bytes = _commit_primary_mission_event_log(repo_root, mission_dirname)
    primary_log.write_bytes(primary_bytes + b'{"payload":{"record":"edited"},"type":"MissionNextInvoked"}\n')
    event_log_rel = f"kitty-specs/{mission_dirname}/mission-events.jsonl"
    if stage_edit:
        _git(repo_root, "add", event_log_rel)

    assert _git(repo_root, "status", "--porcelain", "--untracked-files=all", "--", event_log_rel).stdout == (f"{status_prefix}{event_log_rel}\n")
    assert event_log_rel in _git(repo_root, "ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()
    assert event_log_rel not in _git(repo_root, "ls-tree", "-r", "--name-only", coord_branch).stdout.splitlines()
    assert check_analysis_report_current(primary_log.parent, repo_root).ok

    result = _run_implement(mission_dirname, "WP01")

    assert result.exit_code != 0
    assert "Planning artifacts not committed" in result.output
    assert event_log_rel in result.output


def test_dirty_primary_spec_still_blocks_coord_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_dirname, _ = _build_two_lane_coord_mission(
        tmp_path,
        monkeypatch,
        mission_slug="coord-staging-4905-dirty-spec",
    )
    _disable_auto_commit(repo_root)
    spec_path = repo_root / "kitty-specs" / mission_dirname / "spec.md"
    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nUncommitted change.\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=spec_path.parent,
        repo_root=repo_root,
        body=_ANALYSIS_REPORT_BODY,
        analyzer_agent="test",
    )

    result = _run_implement(mission_dirname, "WP01")

    assert result.exit_code != 0
    assert "Planning artifacts not committed" in result.output
    assert f"kitty-specs/{mission_dirname}/spec.md" in result.output


def test_flat_mission_event_log_remains_dirty_planning_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_dirname = _build_flat_two_lane_mission(
        tmp_path,
        monkeypatch,
        mission_slug="lanes-only-4905-legacy-events",
    )
    _disable_auto_commit(repo_root)
    event_log_rel = f"kitty-specs/{mission_dirname}/mission-events.jsonl"
    event_log_path = repo_root / event_log_rel
    event_log_path.write_text(
        '{"mission":"flat-control","payload":{"action":"discovery"},"timestamp":"2026-09-28T00:00:01+00:00","type":"MissionNextInvoked"}\n',
        encoding="utf-8",
    )

    result = _run_implement(mission_dirname, "WP01")

    assert result.exit_code != 0
    assert "Planning artifacts not committed" in result.output
    assert event_log_rel in result.output


def test_nested_and_backup_mission_event_lookalikes_remain_dirty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_dirname, _ = _build_two_lane_coord_mission(
        tmp_path,
        monkeypatch,
        mission_slug="coord-staging-4905-event-lookalikes",
    )
    _disable_auto_commit(repo_root)
    feature_dir = repo_root / "kitty-specs" / mission_dirname
    nested_event_log = feature_dir / "traces" / "mission-events.jsonl"
    backup_event_log = feature_dir / "mission-events.jsonl.backup"
    nested_event_log.parent.mkdir(parents=True)
    nested_event_log.write_text("nested\n", encoding="utf-8")
    backup_event_log.write_text("backup\n", encoding="utf-8")

    result = _run_implement(mission_dirname, "WP01")

    assert result.exit_code != 0
    assert "Planning artifacts not committed" in result.output
    assert f"kitty-specs/{mission_dirname}/traces/mission-events.jsonl" in result.output
    assert f"kitty-specs/{mission_dirname}/mission-events.jsonl.backup" in result.output


def test_deleting_primary_mission_event_log_keeps_structural_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_dirname, _ = _build_two_lane_coord_mission(
        tmp_path,
        monkeypatch,
        mission_slug="coord-staging-4905-event-delete",
    )
    _disable_auto_commit(repo_root)
    event_log_rel = f"kitty-specs/{mission_dirname}/mission-events.jsonl"
    event_log_path = repo_root / event_log_rel
    event_log_path.write_text("tracked history\n", encoding="utf-8")
    _git(repo_root, "add", event_log_rel)
    _git(repo_root, "commit", "-q", "-m", "planning: retain legacy event log")
    event_log_path.unlink()

    result = _run_implement(mission_dirname, "WP01")

    assert result.exit_code != 0
    assert "Uncommitted structural planning-artifact changes" in result.output
    assert event_log_rel in result.output


# ---------------------------------------------------------------------------
# T011 -- end-to-end guard (WP02 planning-merge conflict; subsumes the WP01 claim)
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
# T015 -- review-claim funnel site, review-cycle numbering, lanes control
# ---------------------------------------------------------------------------


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


def test_second_review_claim_advertises_cycle_two_with_no_primary_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP08 review cycle 2, B4 (MU7): ``workflow.py::review``'s advertised
    feedback path must come from the SAME write-side resolver
    (``_review_cycle_write_location`` / ``_review_cycle_write_dir``) the real
    rejection writer uses, never the hand-joined ``WORK_PACKAGE_TASK`` read
    dir -- reverting that one call survives 145/145 of the WP08 test set per
    review-WP08.md's mutation table (MU7), because nothing else asserts the
    SECOND claim's advertised cycle number or the PRIMARY-checkout absence.

    Drives a full real cycle: claim -> for_review -> review (claims cycle 1,
    advertises ``review-feedback-1.md`` on the coordination worktree) ->
    reject (writes ``review-cycle-1.md`` there) -> re-claim -> for_review ->
    review again. The second claim must advertise ``review-feedback-2.md``
    (the stale hand-joined dir would instead see an EMPTY PRIMARY
    ``tasks/WP01/`` and restart numbering at 1), and the PRIMARY repository
    root checkout must gain no ``tasks/WP01/`` directory at all.
    """
    repo_root, mission_dirname, _coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="mu7-review-cycle")

    claim = _run_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output

    to_for_review = runner.invoke(root_app, ["agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", mission_dirname])
    assert to_for_review.exit_code == 0, to_for_review.output

    review1 = runner.invoke(root_app, ["agent", "action", "review", "WP01", "--mission", mission_dirname, "--agent", "reviewer-renata"])
    assert review1.exit_code == 0, review1.output
    match1 = re.search(r"--review-feedback-file (\S+)", review1.output)
    assert match1 is not None, f"no --review-feedback-file hint in: {review1.output!r}"
    feedback_path_1 = Path(match1.group(1))
    assert feedback_path_1.name == "review-feedback-1.md", f"first claim must advertise cycle 1, got {feedback_path_1.name!r}"
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_dirname, mission_dirname.rsplit("-", 1)[-1])
    assert coord_worktree in feedback_path_1.parents, (
        f"the advertised feedback path must live under the coordination worktree {coord_worktree}, got {feedback_path_1}"
    )

    feedback_path_1.write_text("**Issue**: MU7 first pass.\n", encoding="utf-8")
    reject1 = runner.invoke(
        root_app,
        [
            "agent",
            "tasks",
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(feedback_path_1),
            "--mission",
            mission_dirname,
            "--agent",
            "reviewer-renata",
        ],
    )
    assert reject1.exit_code == 0, reject1.output

    reclaim = _run_implement(mission_dirname, "WP01")
    assert reclaim.exit_code == 0, reclaim.output

    to_for_review_2 = runner.invoke(root_app, ["agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", mission_dirname])
    assert to_for_review_2.exit_code == 0, to_for_review_2.output

    review2 = runner.invoke(root_app, ["agent", "action", "review", "WP01", "--mission", mission_dirname, "--agent", "reviewer-renata"])
    assert review2.exit_code == 0, review2.output
    match2 = re.search(r"--review-feedback-file (\S+)", review2.output)
    assert match2 is not None, f"no --review-feedback-file hint in: {review2.output!r}"
    feedback_path_2 = Path(match2.group(1))
    assert feedback_path_2.name == "review-feedback-2.md", (
        f"second claim must continue numbering from the existing coordination-surface "
        f"cycle (cycle 2), not restart at 1 from an empty PRIMARY dir: got {feedback_path_2.name!r}"
    )
    assert coord_worktree in feedback_path_2.parents

    primary_wp_dir = repo_root / "kitty-specs" / mission_dirname / "tasks" / "WP01"
    assert not primary_wp_dir.exists(), (
        f"the review claim must never create a tasks/WP01/ directory in the PRIMARY "
        f"repository-root checkout: {primary_wp_dir} exists with {sorted(p.name for p in primary_wp_dir.glob('*')) if primary_wp_dir.exists() else []}"
    )


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
