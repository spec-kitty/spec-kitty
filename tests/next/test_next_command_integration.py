"""Integration tests for ``spec-kitty next`` CLI command.

This file imports runtime symbols only via ``runtime.next._internal_runtime``
following the WP02 cutover in mission ``shared-package-boundary-cutover-01KQ22DS``.
No quarantined ``spec_kitty_runtime`` references are needed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from specify_cli import app as cli_app
from runtime.next.decision import DecisionKind

import pytest

from tests._factories import provision_test_charter
from tests.lane_test_utils import write_single_lane_manifest
from tests.runtime._next_mission_scaffold import analysis_is_current

pytestmark = pytest.mark.git_repo

runner = CliRunner()

# Click >=8.2 removed ``mix_stderr`` and repointed ``Result.output`` at an
# always-mixed stdout+stderr stream (see click.testing.Result docstring:
# "Now has its own independent stream that is mixing <stdout> and <stderr>").
# Every assertion below that parses ``--json`` output as a single JSON
# document therefore reads ``result.stdout`` (pure stdout, matching what a
# real machine consumer piping this command's stdout would see), never
# ``result.output`` -- a stray stderr warning (e.g. from the sync emitter)
# would otherwise prepend non-JSON text and corrupt ``json.loads``.


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the charter preflight gate for these integration tests.

    The fixtures stage minimal mission state and do not run
    ``spec-kitty charter sync``, so the preflight gate would return
    ``Error: charter_source missing`` before reaching the dispatch /
    exit-code logic these tests exercise. The bypass contract is
    These tests do not exercise charter freshness, so patch the hook boundary
    directly instead of relying on production environment bypasses.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only",
        lambda *_args, **_kwargs: result,
    )

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Initialize a bare git repo at *path* so feature detection works."""
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    # Initial commit so branch exists
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_project(
    tmp_path: Path,
    mission_slug: str = "042-test-feature",
    mission_type: str = "software-dev",
) -> Path:
    """Scaffold a minimal spec-kitty project with a feature."""
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    # .kittify dir (minimal)
    kittify = repo_root / ".kittify"
    kittify.mkdir()
    # WP04 fail-closed: mission-type resolution requires a provisioned
    # charter (activated mission types). Seed the default activation set
    # via the production provisioner, same shared helper used across the
    # mission-creation test harness.
    provision_test_charter(repo_root)

    # Mint + persist a real project identity, exactly as ``spec-kitty init``
    # does. Post-#2263 the read/sync/status paths resolve identity WITHOUT
    # persisting, so a scaffold that omits the project UUID makes the sync
    # emitter warn "Event missing project_uuid; queued locally only" to stderr,
    # which CliRunner folds into ``result.output`` and corrupts ``--json``
    # parsing. A real project always carries a minted identity.
    from specify_cli.identity.project import ensure_identity

    ensure_identity(repo_root)

    # Feature directory
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": mission_type}),
        encoding="utf-8",
    )

    return repo_root


def _write_runtime_input_mission(repo_root: Path, mission_type: str) -> None:
    """Create a runtime-only mission that deterministically requests input."""
    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / mission_type
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        (
            "mission:\n"
            f"  key: {mission_type}\n"
            f"  name: {mission_type}\n"
            "  version: '1.0.0'\n"
            "steps:\n"
            "  - id: collect_input\n"
            "    title: Collect Input\n"
            "    description: Gather required answer\n"
            "    requires_inputs: [approval]\n"
            "  - id: execute\n"
            "    title: Execute\n"
            "    depends_on: [collect_input]\n"
            "    description: Proceed with mission\n"
        ),
        encoding="utf-8",
    )
    _write_command_templates(repo_root, ["collect_input", "execute"])


def _write_command_templates(repo_root: Path, action_names: list[str]) -> None:
    """Create minimal command templates for synthetic runtime steps.

    The next runtime now guarantees that emitted ``kind=step`` decisions carry
    a resolvable prompt file. Integration fixtures that expect runnable custom
    steps must therefore provide command templates in the resolver override tier.
    """
    template_dir = repo_root / ".kittify" / "overrides" / "command-templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    for action in action_names:
        (template_dir / f"{action}.md").write_text(
            f"# {action}\n\nRun the synthetic {action} step for this integration test.\n",
            encoding="utf-8",
        )


def _write_invalid_runtime_mission(repo_root: Path, mission_type: str) -> None:
    """Create a mission whose first step is unschedulable on a fresh run."""
    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / mission_type
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        (
            "mission:\n"
            f"  key: {mission_type}\n"
            f"  name: {mission_type}\n"
            "  version: '1.0.0'\n"
            "steps:\n"
            "  - id: impossible\n"
            "    title: Impossible\n"
            "    description: Never issuable first step\n"
            "    depends_on: [missing-prereq]\n"
        ),
        encoding="utf-8",
    )


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a WP into a specific lane in the event log."""
    from specify_cli.status.store import append_event
    from specify_cli.status.models import StatusEvent, Lane

    # Map legacy aliases to canonical lane names
    _lane_alias = {"doing": "in_progress"}
    canonical_lane = _lane_alias.get(lane, lane)

    event = StatusEvent(
        event_id=f"test-{wp_id}-{canonical_lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(canonical_lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _add_wp_files(feature_dir: Path, wps: dict[str, str]) -> None:
    """Create WP task files.  wps maps WP ID to lane."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    for wp_id, lane in wps.items():
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\n"
            f"work_package_id: {wp_id}\n"
            f"lane: {lane}\n"
            f"title: {wp_id} task\n"
            f"execution_mode: code_change\n"
            f"owned_files:\n  - src/{wp_id.lower()}/**\n"
            f"authoritative_surface: src/{wp_id.lower()}/\n"
            f"---\n"
            f"# {wp_id}\n"
            f"Do something in src/{wp_id.lower()}/module.py.\n",
            encoding="utf-8",
        )
        # Seed the canonical event log for EVERY WP, planned included: an unseeded
        # WP is genesis (not claimable) under the FSM, so a planned WP must be
        # explicitly seeded or it would be invisible to claim selection (#1775).
        _seed_wp_lane(feature_dir, wp_id, lane)
    write_single_lane_manifest(feature_dir, wp_ids=tuple(wps.keys()))


def _advance_runtime_to_step(
    repo_root: Path,
    mission_slug: str,
    target_step_id: str,
    agent: str = "test-agent",
) -> None:
    """Advance the runtime run past steps until target_step_id is issued."""
    from runtime.next.runtime_bridge import get_or_start_run
    from specify_cli.mission import get_mission_type
    from runtime.next._internal_runtime import next_step as runtime_next_step, NullEmitter
    from runtime.next._internal_runtime.engine import _read_snapshot

    feature_dir = repo_root / "kitty-specs" / mission_slug
    mission_type = get_mission_type(feature_dir)
    run_ref = get_or_start_run(mission_slug, repo_root, mission_type)

    step_order = [
        "discovery",
        "specify",
        "plan",
        "tasks",
        "analyze",
        "implement",
        "review",
        "accept",
    ]
    target_idx = step_order.index(target_step_id) if target_step_id in step_order else -1

    for _ in range(target_idx + 2):
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step_id:
            return
        runtime_next_step(run_ref, agent_id=agent, result="success", emitter=NullEmitter())
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step_id:
            return


def _complete_all_steps(
    repo_root: Path,
    mission_slug: str,
    agent: str = "test-agent",
) -> None:
    """Complete all runtime steps to reach terminal state."""
    from runtime.next.runtime_bridge import get_or_start_run
    from specify_cli.mission import get_mission_type
    from runtime.next._internal_runtime import next_step as runtime_next_step, NullEmitter

    feature_dir = repo_root / "kitty-specs" / mission_slug
    mission_type = get_mission_type(feature_dir)
    run_ref = get_or_start_run(mission_slug, repo_root, mission_type)

    for _ in range(20):
        decision = runtime_next_step(run_ref, agent_id=agent, result="success", emitter=NullEmitter())
        if decision.kind == "terminal":
            return


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNextCommandJSON:
    """Test JSON output mode of the ``next`` command."""

    def test_discovery_state_returns_step(self, tmp_path: Path) -> None:
        """Fresh feature with no events should be in discovery/initial state."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        d = decision.to_dict()
        assert d["agent"] == "test-agent"
        assert d["mission_slug"] == "042-test-feature"
        assert d["mission"] == "software-dev"
        assert "kind" in d

    def test_terminal_state_returns_terminal(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        # Complete all steps via runtime to reach terminal
        _complete_all_steps(repo_root, "042-test-feature")

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert decision.kind == DecisionKind.terminal

    def test_failed_result_flows_through_runtime_as_blocked(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        # Issue first step so runtime has an issued step to complete as failed.
        first = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert first.step_id is not None

        decision = decide_next("test-agent", "042-test-feature", "failed", repo_root)
        assert decision.kind == DecisionKind.blocked
        assert "failed" in (decision.reason or "").lower()
        assert decision.run_id is not None

    def test_blocked_result_returns_blocked(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        first = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert first.step_id is not None

        decision = decide_next("test-agent", "042-test-feature", "blocked", repo_root)
        assert decision.kind == DecisionKind.blocked

    def test_nonexistent_feature_returns_blocked(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "999-nonexistent", "success", repo_root)
        assert decision.kind == DecisionKind.blocked
        assert "not found" in decision.reason


class TestNextCommandImplementState:
    """Test implement state behavior with WP files."""

    def test_implement_state_picks_planned_wp(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(
            feature_dir,
            {
                "WP01": "done",
                "WP02": "planned",
                "WP03": "planned",
            },
        )
        # Advance runtime to implement step
        _advance_runtime_to_step(repo_root, "042-test-feature", "implement")

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert decision.kind == DecisionKind.step
        assert decision.action == "implement"
        assert decision.wp_id == "WP02"
        assert decision.workspace_path is not None

    def test_implement_state_no_planned_checks_for_review(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(
            feature_dir,
            {
                "WP01": "done",
                "WP02": "for_review",
            },
        )
        # Advance runtime to implement step
        _advance_runtime_to_step(repo_root, "042-test-feature", "implement")

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert decision.kind == DecisionKind.step
        assert decision.action == "review"
        assert decision.wp_id == "WP02"

    def test_all_wps_done_advances_to_review(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(
            feature_dir,
            {
                "WP01": "done",
                "WP02": "done",
            },
        )
        # Advance runtime to implement step
        _advance_runtime_to_step(repo_root, "042-test-feature", "implement")

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        # All WPs done => should advance past implement
        assert decision.kind in (DecisionKind.step, DecisionKind.blocked)


class TestNextCommandProgress:
    """Test that progress information is included."""

    def test_progress_in_decision(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(
            feature_dir,
            {
                "WP01": "done",
                "WP02": "doing",
                "WP03": "planned",
            },
        )

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert decision.progress is not None
        assert decision.progress["total_wps"] == 3
        assert decision.progress["done_wps"] == 1
        assert decision.progress["in_progress_wps"] == 1
        assert decision.progress["planned_wps"] == 1


class TestNextCommandOrigin:
    """Test that origin metadata is included."""

    def test_origin_in_decision(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        if decision.origin:
            assert "mission_path" in decision.origin


class TestNextCommandRuntimeFields:
    """Test that runtime fields are included in decisions."""

    def test_run_id_in_decision(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert decision.run_id is not None
        assert len(decision.run_id) > 0

    def test_step_id_in_decision(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        assert decision.step_id is not None

    def test_json_output_has_runtime_fields(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        d = decision.to_dict()
        assert "run_id" in d
        assert "step_id" in d
        assert "decision_id" in d
        assert "input_key" in d


class TestNextCommandKnownBlockedMissions:
    """Regression checks for formerly blocked mission mappings."""

    def test_plan_mission_should_return_runnable_step_when_mapped(self, tmp_path: Path) -> None:
        # WP04/T024 (FR-021): the plan mission's `mission-runtime.yaml`
        # now validates against the runtime schema, so this test
        # transitions from strict-xfail to a hard regression check.
        #
        # WP02 / #844 (C1/C2/C-005): when prompt resolution fails because
        # the scaffold lacks command templates, the runtime now returns
        # ``kind=blocked`` rather than emitting ``kind=step`` with a null
        # prompt_file. Either kind is valid here as long as the action is
        # mapped — what we are guarding against is silent step-with-null.
        repo_root = _scaffold_project(
            tmp_path,
            mission_slug="043-plan-feature",
            mission_type="plan",
        )
        _write_command_templates(repo_root, ["specify"])

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "043-plan-feature", "success", repo_root)
        assert decision.kind in (DecisionKind.step, DecisionKind.blocked)
        if decision.kind == DecisionKind.step:
            assert decision.prompt_file, (
                "kind='step' must carry a real prompt_file (C1)"
            )
        assert decision.action is not None

    def test_documentation_mission_should_return_runnable_step_when_mapped(self, tmp_path: Path) -> None:
        # WP02 / #844: see plan-mission test above. Same C1/C2 contract.
        repo_root = _scaffold_project(
            tmp_path,
            mission_slug="044-docs-feature",
            mission_type="documentation",
        )
        _write_command_templates(repo_root, ["discover"])

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "044-docs-feature", "success", repo_root)
        assert decision.kind in (DecisionKind.step, DecisionKind.blocked)
        if decision.kind == DecisionKind.step:
            assert decision.prompt_file, (
                "kind='step' must carry a real prompt_file (C1)"
            )
        assert decision.action is not None

    def test_missing_canonical_status_during_wp_iteration_returns_structured_decision(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import decide_next_via_runtime
        from specify_cli.status.lane_reader import CanonicalStatusNotFoundError

        class RunRef:
            run_id = "run-123"
            run_dir = str(tmp_path / "run")

        class Snapshot:
            issued_step_id = "implement"

        with (
            patch("runtime.next.runtime_bridge_io.get_or_start_run", return_value=RunRef()) as get_run,
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=Snapshot()),
            patch(
                "runtime.next.runtime_bridge_guards._should_advance_wp_step",
                side_effect=CanonicalStatusNotFoundError(
                    "Canonical status not found for mission '042-test-feature'. "
                    "Run 'spec-kitty agent mission finalize-tasks --mission "
                    "042-test-feature' to bootstrap the event log."
                ),
            ),
        ):
            decision = decide_next_via_runtime("test-agent", "042-test-feature", "success", repo_root)

        # decide_next_via_runtime looks the run up on the io seam: prove the fake was that binding.
        get_run.assert_called_once()
        assert decision.kind == DecisionKind.blocked
        assert any("finalize-tasks" in failure for failure in decision.guard_failures)


# ---------------------------------------------------------------------------
# CLI CliRunner tests — test actual Typer command routing
# ---------------------------------------------------------------------------


class TestNextCommandCLI:
    """Test the ``next`` command via CliRunner (real CLI routing)."""

    def test_json_output_valid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--json flag produces valid JSON with required fields."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature", "--json"],
        )
        assert result.exit_code == 0, f"stderr: {result.output}"
        data = json.loads(result.stdout)
        assert data["agent"] is None
        assert data["mission_slug"] == "042-test-feature"
        assert data["mission"] == "software-dev"
        assert "kind" in data
        assert "mission_state" in data
        assert "timestamp" in data
        assert "guard_failures" in data
        assert data["mission_state"] == "not_started"
        assert data["preview_step"] is not None
        assert "run_id" in data
        assert data["step_id"] is None

    def test_json_output_suppresses_runtime_notice(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Machine JSON output is never prefixed by the stale-runtime notice."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        def _emit_notice() -> bool:
            print("stale runtime notice", file=sys.stderr)
            return True

        with patch("specify_cli.cli.commands.next_cmd.maybe_emit_runtime_pkg_notice", side_effect=_emit_notice):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "042-test-feature", "--json"],
            )

        assert result.exit_code == 0, result.output
        assert "stale runtime notice" not in result.output
        data = json.loads(result.stdout)
        assert data["mission_slug"] == "042-test-feature"

    def test_next_honours_an_edited_pack_runtime_template(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FR-018: ``spec-kitty next`` plans from the pack runtime template.

        A copied pack root (``SPEC_KITTY_PACKS_ROOT``) whose software-dev runtime
        template gains a new first step is honoured by the CLI entry; the old
        built-in tier read ``specify_cli/missions`` and ignored it.
        """
        import shutil

        import yaml

        pack_copy = tmp_path / "packs-copy"
        shutil.copytree(Path(__file__).resolve().parents[2] / "packs", pack_copy)
        template_path = pack_copy / "built-in" / "missions" / "software-dev" / "mission-runtime.yaml"
        raw = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        marker_step = {"id": "zz_pack_marker", "title": "Marker", "description": "Edited in the pack copy"}
        raw["steps"][0]["depends_on"] = ["zz_pack_marker"]
        raw["steps"].insert(0, marker_step)
        template_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(pack_copy))

        repo_root = _scaffold_project(tmp_path)
        _write_command_templates(repo_root, ["zz_pack_marker"])
        monkeypatch.chdir(repo_root)

        result = runner.invoke(cli_app, ["next", "--mission", "042-test-feature", "--json"])

        assert result.exit_code == 0, result.output
        preview = json.loads(result.stdout)["preview_step"]
        assert "zz_pack_marker" in json.dumps(preview)

    def test_invalid_result_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid --result value causes exit code 1."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "bogus"],
        )
        assert result.exit_code == 1

    def test_blocked_result_exit_code(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--result blocked produces exit code 1."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        # First issue a step so runtime can complete it as blocked.
        first = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "success", "--json"],
        )
        assert first.exit_code == 0

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "blocked", "--json"],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["kind"] == "blocked"

    def test_terminal_state_exit_code_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Terminal state returns exit code 0."""
        repo_root = _scaffold_project(tmp_path)
        # Complete all steps via runtime
        _complete_all_steps(repo_root, "042-test-feature")
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "success", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["kind"] == "terminal"

    def test_human_output_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without --json, outputs human-readable text."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature"],
        )
        assert result.exit_code == 0
        assert "042-test-feature @ not_started" in result.output
        assert "Mission Type: software-dev" in result.output
        assert "Next step:" in result.output

    def test_blocked_human_output_renders_guard_failure_looked_for_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#4395: the #3883 blocked-decision 'looked for' render had no test —
        reverting the render hunk in ``_print_standard_human`` left the whole
        suite green. Pin it through the real CLI human-output path: a
        populated ``guard_failure_paths`` map prints an indented
        ``- <name>: looked for <path>`` line under ``Guards pending:`` for
        each failing guard."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        from runtime.next.decision import Decision

        blocked = Decision(
            kind="blocked",
            agent="test-agent",
            mission_slug="042-test-feature",
            mission="software-dev",
            mission_state="review",
            timestamp="2026-09-16T00:00:00Z",
            guard_failures=["spec.md", "tasks.md"],
            guard_failure_paths={
                "spec.md": "kitty-specs/042-test-feature/spec.md",
                "tasks.md": "kitty-specs/042-test-feature/tasks.md",
            },
        )

        with patch("specify_cli.cli.commands.next_cmd.decide_next", return_value=blocked):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "test-agent", "--mission", "042-test-feature", "--result", "blocked"],
            )

        assert result.exit_code == 1, result.output
        assert "Guards pending: spec.md, tasks.md" in result.output
        assert "    - spec.md: looked for kitty-specs/042-test-feature/spec.md" in result.output
        assert "    - tasks.md: looked for kitty-specs/042-test-feature/tasks.md" in result.output

    def test_blocked_human_output_omits_looked_for_lines_when_paths_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The mirror direction of the above (#4395): when ``guard_failure_paths``
        is empty, ``Guards pending:`` still lists the failing guards but no
        ``looked for`` line is printed for any of them."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        from runtime.next.decision import Decision

        blocked = Decision(
            kind="blocked",
            agent="test-agent",
            mission_slug="042-test-feature",
            mission="software-dev",
            mission_state="review",
            timestamp="2026-09-16T00:00:00Z",
            guard_failures=["spec.md", "tasks.md"],
            guard_failure_paths={},
        )

        with patch("specify_cli.cli.commands.next_cmd.decide_next", return_value=blocked):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "test-agent", "--mission", "042-test-feature", "--result", "blocked"],
            )

        assert result.exit_code == 1, result.output
        assert "Guards pending: spec.md, tasks.md" in result.output
        assert "looked for" not in result.output

    def test_real_guard_block_shows_real_path_for_missing_artifact_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#4390: a REAL software-dev mission's guard failures are human-
        readable MESSAGES, not filenames — the pre-fix render treated every
        one of them as a literal artifact tag, fabricating a
        ``looked for kitty-specs/<slug>/Not all work packages are approved
        or done`` line: a path never checked, worse than no path at all.

        This drives the genuine ``decide_next`` -> ``evaluate_guards_strict``
        -> presence path (no hand-fed ``guard_failure_paths``, no patched
        resolver) to a real composed-``tasks`` guard failure that combines
        BOTH failure shapes in one decision: ``tasks.md`` is genuinely
        missing (an artifact-presence failure) and WP01 genuinely has no
        ``dependencies`` field (a free-form, non-artifact failure). Only the
        first may grow a ``looked for`` line, and it must name the real
        ``tasks.md`` path the presence check actually reads — never a path
        built from the WP-dependency message text.
        """
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        # No frontmatter `dependencies:` field on WP01 -- a genuine, real
        # non-artifact guard failure (`_first_missing_dependency_failure`).
        _add_wp_files(feature_dir, {"WP01": "planned"})
        # Advance the real runtime to the composed "tasks" step without ever
        # writing tasks.md at the feature root, so its own presence check
        # genuinely fails too.
        _advance_runtime_to_step(repo_root, "042-test-feature", "tasks")
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test-agent", "--mission", "042-test-feature", "--result", "success"],
        )

        assert "Required artifact missing: tasks.md" in result.output
        assert "missing 'dependencies' in frontmatter" in result.output
        # (a) the genuinely missing artifact shows the real, repo-relative
        # path the presence check actually reads.
        assert "- tasks.md: looked for kitty-specs/042-test-feature/tasks.md" in result.output
        # (b) the non-artifact WP-dependency failure shows no "looked for"
        # line at all -- in particular never one built from its own message
        # text (the pre-fix fabrication this pins against).
        looked_for_lines = [line for line in result.output.splitlines() if "looked for" in line]
        assert len(looked_for_lines) == 1, looked_for_lines
        assert "dependencies" not in looked_for_lines[0]

    def test_nonexistent_feature_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-existent feature returns blocked with exit code 1."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "999-nonexistent", "--result", "success", "--json"],
        )
        # Feature detection may fail before decide_next, or decide_next returns blocked
        assert result.exit_code != 0 or "blocked" in result.output or "not found" in result.output.lower()

    def test_query_mode_does_not_advance_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bare query calls are read-only and keep the run snapshot unchanged."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        from specify_cli.mission import get_mission_type
        from runtime.next.runtime_bridge import get_or_start_run
        from runtime.next._internal_runtime.engine import _read_snapshot

        mission_type = get_mission_type(repo_root / "kitty-specs" / "042-test-feature")
        run_ref = get_or_start_run("042-test-feature", repo_root, mission_type)
        before = _read_snapshot(Path(run_ref.run_dir))

        r1 = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature", "--json"],
        )
        assert r1.exit_code == 0
        d1 = json.loads(r1.stdout)

        r2 = runner.invoke(
            cli_app,
            ["next", "--agent", "compat-agent", "--mission", "042-test-feature", "--json"],
        )
        assert r2.exit_code == 0
        d2 = json.loads(r2.stdout)

        after = _read_snapshot(Path(run_ref.run_dir))

        assert d1["mission_state"] == "not_started"
        assert d1["preview_step"] == d2["preview_step"]
        assert d2["agent"] == "compat-agent"
        assert before.model_dump(mode="json") == after.model_dump(mode="json")

    def test_query_mode_does_not_create_runtime_index_on_first_use(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        runtime_index = repo_root / ".kittify" / "runtime" / "feature-runs.json"
        assert not runtime_index.exists()

        result = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature", "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["mission_state"] == "not_started"
        assert data["preview_step"] is not None
        assert not runtime_index.exists()

    def test_json_output_includes_runtime_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """JSON output includes new runtime fields.

        For a fresh-run query, the run is bootstrapped in an ephemeral temp
        store and torn down before the function returns. ``run_id`` is
        therefore intentionally ``null`` so machine consumers don't try to
        advance state against a run that no longer exists on disk. The field
        is still present in the JSON shape — only its value is null.
        """
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "run_id" in data
        assert data["run_id"] is None  # ephemeral query run, not persisted
        assert "step_id" in data
        assert "preview_step" in data

    def test_query_mode_invalid_first_step_fails_clearly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path, mission_type="invalid-query-mission")
        _write_invalid_runtime_mission(repo_root, mission_type="invalid-query-mission")
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature", "--json"],
        )

        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "has no issuable first step" in data["error"]

    def test_advancing_mode_still_requires_agent_and_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--mission", "042-test-feature", "--result", "success", "--json"],
        )

        assert result.exit_code == 1
        assert "--agent is required when --result is provided" in result.output

    def test_advancing_mode_with_result_still_advances_normally(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "success", "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["step_id"] is not None
        assert data["preview_step"] is None


# ---------------------------------------------------------------------------
# --answer --json single-document output tests
# ---------------------------------------------------------------------------


class TestNextCommandAnswerJSON:
    def test_answer_json_single_document(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful answer flow emits one JSON document with merged answer fields."""
        repo_root = _scaffold_project(tmp_path, mission_type="input-mission")
        _write_runtime_input_mission(repo_root, mission_type="input-mission")
        monkeypatch.chdir(repo_root)

        # First call creates a real pending decision.
        first = runner.invoke(
            cli_app,
            ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "success", "--json"],
        )
        assert first.exit_code == 0, first.output
        first_data = json.loads(first.stdout)
        assert first_data["kind"] == "decision_required"
        assert first_data["decision_id"] == "input:approval"

        # Answer without --decision-id: command must auto-resolve the single pending decision.
        r = runner.invoke(
            cli_app,
            [
                "next",
                "--agent",
                "test",
                "--mission",
                "042-test-feature",
                "--result",
                "success",
                "--answer",
                "yes",
                "--json",
            ],
        )
        # WP02 / #844: with this scaffold the post-answer step has no
        # command template, so the runtime now correctly emits ``kind=blocked``
        # (rather than ``kind=step`` with a null prompt_file). The CLI exits
        # non-zero on ``blocked`` decisions; that is the legacy contract for
        # the ``next`` shim and is independent of #844. Either zero or one is
        # acceptable here — the regression we are guarding is the JSON shape
        # and the answer fields, not the exit code or kind.
        assert r.exit_code in (0, 1), r.output
        data = json.loads(r.stdout.strip())
        assert isinstance(data, dict)
        assert data["answered"] == "input:approval"
        assert data["answer"] == "yes"
        assert data["kind"] in {"step", "terminal", "blocked", "decision_required"}
        if data["kind"] == "step":
            assert data.get("prompt_file"), (
                "kind='step' must carry a real prompt_file (C1)"
            )

    def test_answer_json_never_emits_two_objects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: stdout must be exactly one JSON document, no trailing object."""
        repo_root = _scaffold_project(tmp_path, mission_type="input-mission")
        _write_runtime_input_mission(repo_root, mission_type="input-mission")
        monkeypatch.chdir(repo_root)

        # First, advance once so a pending decision exists to answer.
        first = runner.invoke(
            cli_app,
            [
                "next",
                "--agent",
                "test",
                "--mission",
                "042-test-feature",
                "--result",
                "success",
                "--json",
            ],
        )
        assert first.exit_code == 0, first.output

        r = runner.invoke(
            cli_app,
            [
                "next",
                "--agent",
                "test",
                "--mission",
                "042-test-feature",
                "--result",
                "success",
                "--answer",
                "yes",
                "--json",
            ],
        )
        # WP02 / #844: see test_answer_json_single_document above. The
        # post-answer step has no command template so the runtime now emits
        # ``kind=blocked`` (exit 1) rather than ``kind=step`` with a null
        # prompt. Either is acceptable here — what we are guarding is the
        # single-JSON-document invariant on stdout.
        assert r.exit_code in (0, 1), r.output

        # Ensure a single top-level JSON value with no trailing payload.
        decoder = json.JSONDecoder()
        text = r.stdout.strip()
        obj, idx = decoder.raw_decode(text)
        assert isinstance(obj, dict)
        assert text[idx:].strip() == "", f"Unexpected trailing output: {text[idx:]!r}"


# ---------------------------------------------------------------------------
# Decision-required metadata tests
# ---------------------------------------------------------------------------


class TestNextCommandDecisionRequired:
    def test_decision_required_has_question_field_in_json(self, tmp_path: Path) -> None:
        """JSON output includes question/options for real runtime decision_required."""
        repo_root = _scaffold_project(tmp_path, mission_type="input-mission")
        _write_runtime_input_mission(repo_root, mission_type="input-mission")

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        d = decision.to_dict()
        assert d["kind"] == "decision_required"
        assert "question" in d
        assert "options" in d
        assert d["question"] is not None

    def test_decision_required_has_decision_id_field(self, tmp_path: Path) -> None:
        """Decision-required responses include canonical decision_id/input_key fields."""
        repo_root = _scaffold_project(tmp_path, mission_type="input-mission")
        _write_runtime_input_mission(repo_root, mission_type="input-mission")

        from runtime.next.decision import decide_next

        decision = decide_next("test-agent", "042-test-feature", "success", repo_root)
        d = decision.to_dict()
        assert d["decision_id"] == "input:approval"
        assert d["input_key"] == "approval"


# ---------------------------------------------------------------------------
# Atomic task transition tests
# ---------------------------------------------------------------------------


class TestAtomicTaskTransitions:
    def test_plan_to_single_composed_tasks_step(self, tmp_path: Path) -> None:
        """Advance through the single public tasks step."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"

        # Create artifacts for earlier steps
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

        # Create WP files with dependencies for tasks_finalize guard
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\nlane: done\ndependencies: []\n"
            "requirement_refs: [FR-001]\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )
        # Seed event log so runtime bridge reads WP01 as done
        _seed_wp_lane(feature_dir, "WP01", "done")

        from runtime.next.decision import decide_next

        seen_steps = []
        for _i in range(40):
            decision = decide_next("test-agent", "042-test-feature", "success", repo_root, analysis_currency=analysis_is_current)
            if decision.kind == "terminal":
                break
            if decision.step_id and decision.step_id not in seen_steps:
                seen_steps.append(decision.step_id)

        assert "tasks" in seen_steps, f"tasks not visited; saw: {seen_steps}"
        assert "tasks_outline" not in seen_steps, f"legacy tasks_outline should not be issued; saw: {seen_steps}"
        assert "tasks_packages" not in seen_steps, f"legacy tasks_packages should not be issued; saw: {seen_steps}"
        assert "tasks_finalize" not in seen_steps, f"legacy tasks_finalize should not be issued; saw: {seen_steps}"

        plan_idx = seen_steps.index("plan")
        tasks_idx = seen_steps.index("tasks")
        analyze_idx = seen_steps.index("analyze")
        implement_idx = seen_steps.index("implement")
        assert plan_idx < tasks_idx < analyze_idx < implement_idx, f"Steps out of order: {seen_steps}"
