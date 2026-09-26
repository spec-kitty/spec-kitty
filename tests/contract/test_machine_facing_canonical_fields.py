"""Contract tests for canonical mission identity fields in machine-facing payloads."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from specify_cli.acceptance import AcceptanceSummary
from specify_cli.acceptance.matrix import AcceptanceMatrix, write_acceptance_matrix
from specify_cli.agent_utils.status import show_kanban_status
from specify_cli.core.worktree_topology import FeatureTopology, WPTopologyEntry, render_topology_json
from specify_cli.context.models import MissionContext
from runtime.next.decision import Decision, DecisionKind
from specify_cli.orchestrator_api.commands import app as orchestrator_app
from specify_cli.policy.config import MergeGateConfig
from specify_cli.policy.merge_gates import evaluate_merge_gates
from specify_cli.verify_enhanced import run_enhanced_verify
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.progress import generate_progress_json
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event
from specify_cli.status.views import write_derived_views


import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast]
runner = CliRunner()
_PROJECT_UUID = "8a4a7da6-a97c-4bb4-893a-b31664abfee4"


def _make_mission(
    tmp_path: Path,
    mission_slug: str = "064-complete-mission-identity-cutover",
) -> tuple[Path, Path]:
    """Create a minimal mission directory with meta.json and two task files."""
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}.md").write_text(
            (
                f"---\nwork_package_id: {wp_id}\n"
                f"title: Test {wp_id}\nlane: planned\ndependencies: []\n---\n\n# {wp_id}\n"
            ),
            encoding="utf-8",
        )

    meta = {
        "mission_number": mission_slug.split("-")[0],
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Canonical Mission Identity Cutover",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-08T00:00:00+00:00",
    }
    (mission_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return repo_root, mission_dir


def _append_lane_event(
    mission_dir: Path,
    *,
    wp_id: str = "WP01",
    to_lane: str = "done",
    event_id: str = "01TESTAAAAAAAAAAAAAAAAAAA1",
) -> None:
    mission_slug = mission_dir.name
    append_event(
        mission_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(to_lane),
            at="2026-04-08T12:00:00+00:00",
            actor="test-agent",
            force=False,
            execution_mode="worktree",
        ),
    )


def _valid_policy_json() -> str:
    return json.dumps(
        {
            "orchestrator_id": "test-orch",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )


def _invoke_orchestrator(args: list[str], repo_root: Path) -> dict[str, object]:
    with patch(
        "specify_cli.orchestrator_api.commands._get_main_repo_root",
        return_value=repo_root,
    ):
        result = runner.invoke(orchestrator_app, args, catch_exceptions=False)
    assert result.exit_code in (0, 1), result.output
    assert result.output.strip(), (
        f"orchestrator emitted no JSON: output={result.output!r}, "
        f"exception={result.exception!r}"
    )
    try:
        return json.loads(result.output)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"orchestrator emitted invalid JSON: output={result.output!r}, "
            f"exception={result.exception!r}"
        ) from exc


def test_status_snapshot_emits_canonical_mission_fields(tmp_path: Path) -> None:
    _repo_root, mission_dir = _make_mission(tmp_path)
    _append_lane_event(mission_dir)

    payload = materialize(mission_dir).to_dict()

    assert payload["mission_slug"] == mission_dir.name
    # Post-083: mission_number is display-only (FR-044). Pipelines that route
    # through resolve_mission_identity coerce the legacy string "064" to the
    # canonical int 64, which mission_identity_fields stringifies as "64"
    # (no leading zeros at the payload boundary). Canonical identity is
    # mission_id (ULID), not mission_number.
    assert payload["mission_number"] == "64"
    assert payload["mission_type"] == "software-dev"


def test_board_summary_emits_canonical_mission_fields(tmp_path: Path) -> None:
    _repo_root, mission_dir = _make_mission(tmp_path)
    _append_lane_event(mission_dir, to_lane="claimed")
    derived_dir = tmp_path / ".kittify" / "derived"

    write_derived_views(mission_dir, derived_dir)
    payload = json.loads((derived_dir / mission_dir.name / "board-summary.json").read_text(encoding="utf-8"))

    assert payload["mission_slug"] == mission_dir.name
    # board-summary.json serializes mission_number as an int after WP02:
    # resolve_mission_identity coerces legacy "064" to int 64.
    assert payload["mission_number"] == 64
    assert payload["mission_type"] == "software-dev"


def test_progress_json_emits_canonical_mission_fields(tmp_path: Path) -> None:
    _repo_root, mission_dir = _make_mission(tmp_path)
    _append_lane_event(mission_dir)
    derived_dir = tmp_path / ".kittify" / "derived"

    generate_progress_json(mission_dir, derived_dir)
    payload = json.loads((derived_dir / mission_dir.name / "progress.json").read_text(encoding="utf-8"))

    assert payload["mission_slug"] == mission_dir.name
    # Display string form (no leading zeros) — see status_snapshot test above.
    assert payload["mission_number"] == "64"
    assert payload["mission_type"] == "software-dev"


def test_context_payload_emits_canonical_mission_fields() -> None:
    payload = MissionContext(
        token="ctx-01TEST000000000000000000AA",
        project_uuid="8a4a7da6-a97c-4bb4-893a-b31664abfee4",
        mission_id="064-complete-mission-identity-cutover",
        work_package_id="WP01",
        wp_code="WP01",
        mission_slug="064-complete-mission-identity-cutover",
        mission_number="064",
        mission_type="software-dev",
        target_branch="main",
        authoritative_repo="/nonexistent/repo",
        authoritative_ref="kitty/mission-064-complete-mission-identity-cutover-lane-a",
        owned_files=("src/specify_cli/**",),
        execution_mode="code_change",
        dependency_mode="independent",
        created_at="2026-04-08T12:00:00+00:00",
        created_by="codex",
    ).to_dict()

    assert payload["mission_slug"] == "064-complete-mission-identity-cutover"
    assert payload["mission_number"] == "064"
    assert payload["mission_type"] == "software-dev"


def test_acceptance_matrix_emits_canonical_mission_fields(tmp_path: Path) -> None:
    _repo_root, mission_dir = _make_mission(tmp_path)
    matrix = AcceptanceMatrix(mission_slug=mission_dir.name)

    write_acceptance_matrix(mission_dir, matrix)
    payload = json.loads((mission_dir / "acceptance-matrix.json").read_text(encoding="utf-8"))

    assert payload["mission_slug"] == mission_dir.name
    # Display string form (no leading zeros).
    assert payload["mission_number"] == "64"
    assert payload["mission_type"] == "software-dev"


def test_merge_gate_evaluation_emits_canonical_mission_fields(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path)
    _append_lane_event(mission_dir, to_lane="approved")

    payload = evaluate_merge_gates(
        mission_dir,
        mission_dir.name,
        ["WP01"],
        MergeGateConfig(mode="warn"),
        repo_root,
    ).to_dict()

    assert payload["mission_slug"] == mission_dir.name
    # Display string form (no leading zeros).
    assert payload["mission_number"] == "64"
    assert payload["mission_type"] == "software-dev"


def test_next_decision_payload_emits_canonical_mission_fields() -> None:
    # NOTE: kind=DecisionKind.terminal (not step) — WP02's __post_init__ validator
    # rejects kind="step" without a non-empty, on-disk-resolvable prompt_file.
    # This test asserts mission-field rendering in to_dict(), which is independent
    # of the prompt-file contract, so a terminal kind exercises the same code path.
    payload = Decision(
        kind=DecisionKind.terminal,
        agent="codex",
        mission_slug="064-complete-mission-identity-cutover",
        mission="software-dev",
        mission_state="implement",
        timestamp="2026-04-08T12:00:00+00:00",
    ).to_dict()

    assert payload["mission_slug"] == "064-complete-mission-identity-cutover"
    # Decision builds mission_number from mission_number_from_slug (int) via
    # mission_identity_fields, so "064" prefix renders as "64" in the payload.
    assert payload["mission_number"] == "64"
    assert payload["mission_type"] == "software-dev"


def test_acceptance_summary_emits_canonical_mission_fields(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path)
    summary = AcceptanceSummary(
        feature=mission_dir.name,
        repo_root=repo_root,
        feature_dir=mission_dir,
        tasks_dir=mission_dir / "tasks",
        branch="main",
        worktree_root=repo_root / ".worktrees",
        primary_repo_root=repo_root,
        lanes={"done": ["WP01"]},
        work_packages=[],
        metadata_issues=[],
        activity_issues=[],
        unchecked_tasks=[],
        needs_clarification=[],
        missing_artifacts=[],
        optional_missing=[],
        git_dirty=[],
        path_violations=[],
        warnings=[],
    )

    payload = summary.to_dict()
    assert payload["mission_slug"] == mission_dir.name
    # AcceptanceSummary emits mission_number as int after WP02.
    assert payload["mission_number"] == 64
    assert payload["mission_type"] == "software-dev"


def test_worktree_topology_payload_emits_canonical_mission_fields() -> None:
    topology = FeatureTopology(
        mission_slug="064-complete-mission-identity-cutover",
        target_branch="main",
        mission_branch="kitty/mission-064-complete-mission-identity-cutover",
        mission_number="064",
        mission_type="software-dev",
        entries=[
            WPTopologyEntry(
                wp_id="WP01",
                lane_id="lane-a",
                lane_wp_ids=["WP01"],
                branch_name="kitty/mission-064-complete-mission-identity-cutover-lane-a",
                base_branch="kitty/mission-064-complete-mission-identity-cutover",
            )
        ],
    )

    payload = json.loads("\n".join(render_topology_json(topology, "WP01")[1:-1]))
    assert payload["mission_slug"] == "064-complete-mission-identity-cutover"
    assert payload["mission_number"] == "064"
    assert payload["mission_type"] == "software-dev"


def test_agent_status_payload_emits_canonical_mission_fields(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path)
    _append_lane_event(mission_dir, to_lane="claimed")

    with (
        patch("specify_cli.agent_utils.status.locate_project_root", return_value=repo_root),
        patch("specify_cli.agent_utils.status.get_main_repo_root", return_value=repo_root),
    ):
        payload = show_kanban_status(mission_dir.name)

    assert payload["mission_slug"] == mission_dir.name
    # show_kanban_status returns mission_number as int after WP02.
    assert payload["mission_number"] == 64
    assert payload["mission_type"] == "software-dev"


def test_verify_enhanced_feature_detection_emits_canonical_mission_fields(tmp_path: Path) -> None:
    from rich.console import Console

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".kittify").mkdir()
    mission_dir = project_root / "kitty-specs" / "064-complete-mission-identity-cutover"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_number": "064",
                "mission_slug": mission_dir.name,
                "slug": mission_dir.name,
                "mission_type": "software-dev",
                "target_branch": "main",
                "friendly_name": "Canonical Mission Identity Cutover",
                "created_at": "2026-04-08T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    console = Console(file=open(os.devnull, "w"))  # noqa: SIM115
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)
        payload = run_enhanced_verify(
            repo_root=project_root,
            project_root=project_root,
            cwd=project_root,
            feature=mission_dir.name,
            json_output=True,
            check_files=False,
            console=console,
            feature_dir=mission_dir,
        )

    detected = payload["feature_detection"]
    assert detected["mission_slug"] == mission_dir.name
    # run_enhanced_verify returns mission_number as int after WP02.
    assert detected["mission_number"] == 64
    assert detected["mission_type"] == "software-dev"


def test_orchestrator_query_payloads_emit_canonical_mission_fields(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path)
    _append_lane_event(mission_dir, to_lane="done")

    for args in (
        ["mission-state", "--mission", mission_dir.name],
        ["list-ready", "--mission", mission_dir.name],
    ):
        envelope = _invoke_orchestrator(args, repo_root)
        payload = envelope["data"]
        assert payload["mission_slug"] == mission_dir.name
        # orchestrator-api returns mission_number as int after WP02.
        assert payload["mission_number"] == 64
        assert payload["mission_type"] == "software-dev"


def test_orchestrator_transition_payloads_emit_canonical_mission_fields(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path)
    # Seed WP01 out of the non-display 'genesis' state into 'planned' (as
    # finalize-tasks does) so start-implementation's composite transition is
    # legal (planned -> claimed -> in_progress).
    append_event(
        mission_dir,
        StatusEvent(
            event_id="01TESTSEED0000000000000001",
            mission_slug=mission_dir.name,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-04-07T00:00:00+00:00",
            actor="seed",
            force=False,
            execution_mode="worktree",
        ),
    )

    envelope = _invoke_orchestrator(
        [
            "start-implementation",
            "--mission",
            mission_dir.name,
            "--wp",
            "WP01",
            "--actor",
            "claude",
            "--policy",
            _valid_policy_json(),
        ],
        repo_root,
    )
    payload = envelope["data"]
    assert payload["mission_slug"] == mission_dir.name
    # orchestrator-api transition payloads return mission_number as int.
    assert payload["mission_number"] == 64
    assert payload["mission_type"] == "software-dev"


def test_orchestrator_error_payloads_emit_canonical_mission_fields(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path)

    incomplete = _invoke_orchestrator(
        ["accept-mission", "--mission", mission_dir.name, "--actor", "claude"],
        repo_root,
    )
    incomplete_payload = incomplete["data"]
    assert incomplete["error_code"] == "MISSION_NOT_READY"
    assert incomplete_payload["mission_slug"] == mission_dir.name
    # orchestrator-api error payloads return mission_number as int.
    assert incomplete_payload["mission_number"] == 64
    assert incomplete_payload["mission_type"] == "software-dev"

    mock_preflight = MagicMock(target_branch="main", errors=["lanes.json is missing for this mission"])
    with patch(
        "specify_cli.orchestrator_api.commands._build_merge_preflight",
        return_value=mock_preflight,
    ):
        preflight = _invoke_orchestrator(
            ["merge-mission", "--mission", mission_dir.name, "--target", "main"],
            repo_root,
        )
    preflight_payload = preflight["data"]
    assert preflight["error_code"] == "PREFLIGHT_FAILED"
    assert preflight_payload["mission_slug"] == mission_dir.name
    # Preflight error payloads also return mission_number as int.
    assert preflight_payload["mission_number"] == 64
    assert preflight_payload["mission_type"] == "software-dev"


def test_no_mission_run_slug_in_first_party_payloads() -> None:
    """No first-party machine-facing payload may introduce mission_run_slug."""
    repo_root = Path(__file__).resolve().parents[2]
    offending = [
        str(path.relative_to(repo_root))
        for path in repo_root.glob("src/specify_cli/**/*.py")
        if "mission_run_slug" in path.read_text(encoding="utf-8")
    ]
    assert not offending, (
        "mission_run_slug introduced in: "
        f"{offending}. Forbidden by C-009/FR-019."
    )


def test_mission_created_and_closed_event_names_unchanged() -> None:
    """The canonical catalog event names must not be renamed."""
    repo_root = Path(__file__).resolve().parents[2]
    offending = [
        str(path.relative_to(repo_root))
        for path in repo_root.glob("src/specify_cli/**/*.py")
        if "MissionRunCreated" in path.read_text(encoding="utf-8")
        or "MissionRunClosed" in path.read_text(encoding="utf-8")
    ]
    assert not offending, (
        "MissionRun* catalog event rename detected in: "
        f"{offending}. Forbidden by FR-017/§3.3."
    )


def test_aggregate_type_mission_unchanged() -> None:
    """aggregate_type must remain 'Mission'; no rename to 'MissionRun'."""
    repo_root = Path(__file__).resolve().parents[2]
    offending = [
        str(path.relative_to(repo_root))
        for path in repo_root.glob("src/specify_cli/**/*.py")
        if 'aggregate_type="MissionRun"' in path.read_text(encoding="utf-8")
        or "aggregate_type='MissionRun'" in path.read_text(encoding="utf-8")
    ]
    assert not offending, (
        "aggregate_type renamed to MissionRun in: "
        f"{offending}. Forbidden by §3.3."
    )
