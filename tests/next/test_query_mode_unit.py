"""Unit tests for spec-kitty next query mode (FR-012, FR-013)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli import app as cli_app

pytestmark = pytest.mark.fast
runner = CliRunner()


@pytest.fixture(autouse=True)
def _skip_root_project_schema_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep command-unit tests isolated from the checkout's project metadata."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.setattr("specify_cli.locate_project_root", lambda: None)
    # These unit tests do not stage a charter; patch the hook boundary so the
    # argument-validation / dispatch paths remain isolated.
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
        lambda *_args, **_kwargs: result,
    )


def _make_mock_decision(
    is_query: bool = False,
    mission_state: str = "specify",
    *,
    agent: str | None = "claude",
    preview_step: str | None = None,
    **overrides,
):
    from runtime.next.decision import Decision, DecisionKind

    return Decision(
        kind=DecisionKind.query if is_query else DecisionKind.step,
        agent=agent,
        mission_slug="069-test",
        mission="software-dev",
        mission_state=mission_state,
        timestamp="2026-04-07T00:00:00+00:00",
        is_query=is_query,
        mission_type="software-dev",
        preview_step=preview_step,
        **overrides,
    )


class TestQueryModeDoesNotAdvance:
    def test_bare_call_invokes_query_not_decide(self, tmp_path: Path) -> None:
        """When --result is omitted, query_current_state() is called, not decide_next()."""
        mock_decision = _make_mock_decision(is_query=True, mission_state="specify")

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision) as mock_query,
            patch("specify_cli.cli.commands.next_cmd.decide_next") as mock_decide,
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test", "--json"],
            )

        mock_query.assert_called_once()
        mock_decide.assert_not_called()

    def test_query_mode_allows_missing_agent(self, tmp_path: Path) -> None:
        mock_decision = _make_mock_decision(is_query=True, mission_state="not_started", preview_step="discovery", agent=None)

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision) as mock_query,
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--json"],
            )

        assert result.exit_code == 0
        mock_query.assert_called_once_with(None, "069-test", tmp_path)

    def test_result_success_still_requires_agent(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--result", "success", "--json"],
            )

        assert result.exit_code == 1
        assert "--agent is required when --result is provided" in result.output

    def test_result_json_preflight_failure_returns_error_document(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fail_preflight(*_args, **_kwargs):
            print("Error: charter_source missing; run `spec-kitty charter sync`", file=__import__("sys").stderr)
            raise typer.Exit(1)

        monkeypatch.setattr(
            "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
            fail_preflight,
        )
        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
        ):
            result = runner.invoke(
                cli_app,
                [
                    "next",
                    "--mission",
                    "069-test",
                    "--agent",
                    "codex",
                    "--result",
                    "success",
                    "--json",
                ],
            )

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["error_code"] == "CHARTER_PREFLIGHT_FAILED"
        assert "charter_source missing" in payload["blocked_reason"]

    def test_answer_requires_result_when_used_without_result(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--answer", "yes", "--json"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "--answer requires --result because query mode is read-only" in data["error"]

    def test_answer_without_result_does_not_invoke_query_or_answer_handling(self, tmp_path: Path) -> None:
        mock_decision = _make_mock_decision(is_query=True, mission_state="not_started", preview_step="discovery")

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("specify_cli.cli.commands.next_cmd._handle_answer", return_value="input:approval") as mock_answer,
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision) as mock_query,
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--agent", "claude", "--answer", "yes", "--json"],
            )

        assert result.exit_code == 1
        mock_answer.assert_not_called()
        mock_query.assert_not_called()
        data = json.loads(result.output)
        assert "--answer requires --result because query mode is read-only" in data["error"]

    def test_answer_without_result_human_output_is_error_not_query(self, tmp_path: Path) -> None:
        mock_decision = _make_mock_decision(is_query=True, mission_state="not_started", preview_step="discovery")

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("specify_cli.cli.commands.next_cmd._handle_answer", return_value="input:approval"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--agent", "claude", "--answer", "yes"],
            )

        assert result.exit_code == 1
        assert "--answer requires --result because query mode is read-only" in result.output


class TestQueryModeOutput:
    def test_human_output_begins_with_query_label(self, tmp_path: Path) -> None:
        """SC-003: first line of stdout is the verbatim query label."""
        mock_decision = _make_mock_decision(is_query=True, mission_state="specify")

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test"],
            )

        lines = result.output.strip().split("\n")
        assert lines[0] == "[QUERY \u2014 no result provided, state not advanced]"
        assert lines[1] == "  Mission: 069-test @ specify"
        assert lines[2] == "  Mission Type: software-dev"

    def test_hosted_readiness_does_not_prepend_query_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`next` query output remains a protocol response under hosted mode."""
        from specify_cli.readiness import AuthStatus

        monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
        monkeypatch.setattr(
            "specify_cli.readiness.auth.probe_auth_status",
            lambda **_kw: (AuthStatus.LOGGED_OUT_IN_TEAMSPACE, "spec-kitty/spec-kitty"),
        )
        mock_decision = _make_mock_decision(is_query=True, mission_state="specify")

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test"],
            )

        assert result.exit_code == 0
        assert "logged_out_on_connected_teamspace" not in result.output
        assert result.output.splitlines()[0] == "[QUERY \u2014 no result provided, state not advanced]"

    def test_json_output_includes_is_query_true(self, tmp_path: Path) -> None:
        """JSON output includes is_query: true."""
        mock_decision = _make_mock_decision(is_query=True)

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test", "--json"],
            )

        data = json.loads(result.output)
        assert data.get("is_query") is True

    def test_json_stdout_is_single_json_value_when_preflight_emits_human_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight advisory text belongs on stderr, never in ``next --json`` stdout."""
        from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

        mock_decision = _make_mock_decision(is_query=True)

        def noisy_preflight(*_args, **_kwargs):
            print("human charter advisory")
            return CharterPreflightResult(passed=True, checks=[], warnings=["structured advisory"])

        monkeypatch.setattr(
            "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
            noisy_preflight,
        )

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test", "--json"],
            )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload.get("is_query") is True
        assert result.stdout.strip().startswith("{")
        assert result.stdout.strip().endswith("}")
        assert "human charter advisory" not in result.stdout

    def test_human_output_shows_not_started_preview_step(self, tmp_path: Path) -> None:
        mock_decision = _make_mock_decision(is_query=True, mission_state="not_started", preview_step="discovery")

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test"],
            )

        assert "Mission: 069-test @ not_started" in result.output
        assert "Next step: discovery" in result.output

    def test_human_output_shows_pending_decision_details(self, tmp_path: Path) -> None:
        mock_decision = _make_mock_decision(
            is_query=True,
            mission_state="collect_input",
            question="Approve?",
            options=["yes", "no"],
            decision_id="input:approval",
        )

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test"],
            )

        assert "Question: Approve?" in result.output
        assert "Options: yes, no" in result.output
        assert "Decision ID: input:approval" in result.output

    def test_json_kind_is_query(self, tmp_path: Path) -> None:
        """JSON output kind field is 'query'."""
        mock_decision = _make_mock_decision(is_query=True)

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("runtime.next.runtime_bridge.query_current_state", return_value=mock_decision),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test", "--json"],
            )

        data = json.loads(result.output)
        assert data.get("kind") == "query"
        assert data.get("is_query") is True


class TestBuildPromptSafe:
    def test_build_prompt_safe_suppresses_stdout_noise(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from runtime.next.decision import _build_prompt_safe

        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("# prompt\n", encoding="utf-8")

        def noisy_build_prompt(**_kwargs):
            print("noisy stdout")
            return None, prompt_path

        with patch("runtime.next.prompt_builder.build_prompt", side_effect=noisy_build_prompt):
            result = _build_prompt_safe(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="069-test",
                wp_id="WP01",
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert result == str(prompt_path)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestQueryCurrentStateErrorPaths:
    """Cover the three error-handling branches in query_current_state() (runtime_bridge.py).

    These tests exercise lines 575, 591-592, and 610-611 which are otherwise
    unreachable via CLI-level tests.
    """

    def test_missing_feature_dir_raises_mission_not_found(self, tmp_path: Path) -> None:
        """Missing mission dirs fail closed instead of emitting synthetic unknown state."""
        from runtime.next.runtime_bridge import MissionNotFoundError, query_current_state

        # tmp_path / "kitty-specs" / "069-missing" does NOT exist
        with pytest.raises(MissionNotFoundError, match="069-missing"):
            query_current_state("claude", "069-missing", tmp_path)

    def test_resolved_missing_feature_dir_raises_mission_not_found(self, tmp_path: Path) -> None:
        """Resolved-but-absent paths also fail closed."""
        from mission_runtime import MissionArtifactKind, MissionContext, MissionTopology
        from mission_runtime.context import MissionArtifactContext
        from runtime.next.runtime_bridge import MissionNotFoundError, query_current_state

        missing = tmp_path / "kitty-specs" / "069-missing"

        with patch(
            "mission_runtime.mission_context_for",
            return_value=MissionContext(
                mission_slug="069-missing",
                mission_type="software-dev",
                topology=MissionTopology.SINGLE_BRANCH,
                artifacts=(
                    MissionArtifactContext(
                        kind=MissionArtifactKind.PRIMARY_METADATA,
                        read_dir=missing,
                        write_dir=missing,
                        commit_target=None,
                    ),
                    MissionArtifactContext(
                        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
                        read_dir=missing,
                        write_dir=missing,
                        commit_target=None,
                    ),
                    MissionArtifactContext(
                        kind=MissionArtifactKind.STATUS_STATE,
                        read_dir=missing,
                        write_dir=missing,
                        commit_target=None,
                    ),
                ),
            ),
        ):
            with pytest.raises(MissionNotFoundError, match="069-missing"):
                query_current_state("claude", "069-missing", tmp_path)

    def test_ephemeral_query_run_exception_raises_validation_error(self, tmp_path: Path) -> None:
        """Fresh-query bootstrap failures surface an actionable query error."""
        from runtime.next.runtime_bridge import QueryModeValidationError, query_current_state

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=None),
            patch("runtime.next.runtime_bridge_io._start_ephemeral_query_run", side_effect=RuntimeError("run init failed")),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
        ):
            with pytest.raises(QueryModeValidationError, match="Could not read query state"):
                query_current_state("claude", "069-test", tmp_path)

    def test_read_snapshot_exception_raises_validation_error(self, tmp_path: Path) -> None:
        """Corrupted runtime state should fail query mode loudly, not return unknown."""
        from runtime.next.runtime_bridge import QueryModeValidationError, query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        mock_run_ref = MagicMock()
        mock_run_ref.run_dir = str(tmp_path / "run")

        with (
            patch("runtime.next.runtime_bridge.get_or_start_run", return_value=mock_run_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", side_effect=Exception("snapshot read failed")),
        ):
            with pytest.raises(QueryModeValidationError, match="Could not read query state"):
                query_current_state("claude", "069-test", tmp_path)

    def test_invalid_first_step_raises_clear_validation_error(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import QueryModeValidationError, query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        mock_run_ref = MagicMock()
        mock_run_ref.run_dir = str(tmp_path / "run")
        mock_run_ref.run_id = "run-123"

        snapshot = MagicMock()
        snapshot.completed_steps = []
        snapshot.pending_decisions = {}
        snapshot.decisions = {}
        snapshot.issued_step_id = None
        snapshot.policy_snapshot = MagicMock()

        blocked = MagicMock()
        blocked.kind = "blocked"
        blocked.step_id = None

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=mock_run_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch("runtime.next._internal_runtime.planner.plan_next", return_value=blocked),
        ):
            with pytest.raises(QueryModeValidationError, match="has no issuable first step"):
                query_current_state("claude", "069-test", tmp_path)

    def test_pending_decision_metadata_is_preserved_in_query_mode(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        mock_run_ref = MagicMock()
        mock_run_ref.run_dir = str(tmp_path / "run")
        mock_run_ref.run_id = "run-123"

        snapshot = MagicMock()
        snapshot.completed_steps = ["discovery"]
        snapshot.pending_decisions = {"input:approval": {"status": "pending"}}
        snapshot.decisions = {"input:approval": {"status": "pending"}}
        snapshot.issued_step_id = "collect_input"
        snapshot.policy_snapshot = MagicMock()

        decision_required = MagicMock()
        decision_required.kind = "decision_required"
        decision_required.step_id = "collect_input"
        decision_required.decision_id = "input:approval"
        decision_required.input_key = "approval"
        decision_required.question = "Approve?"
        decision_required.options = ["yes", "no"]

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=mock_run_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch("runtime.next._internal_runtime.planner.plan_next", return_value=decision_required),
        ):
            decision = query_current_state("claude", "069-test", tmp_path)

        assert decision.mission_state == "collect_input"
        assert decision.step_id == "collect_input"
        assert decision.decision_id == "input:approval"
        assert decision.input_key == "approval"
        assert decision.question == "Approve?"
        assert decision.options == ["yes", "no"]

    def test_fresh_run_query_omits_ephemeral_run_id(self, tmp_path: Path) -> None:
        """Bootstrapping an ephemeral run for fresh-mode query must NOT leak
        the temp run_id into the response. The temp dir is torn down before
        the function returns, so a non-null ``run_id`` would mislead callers
        into thinking they can advance state against a run that no longer
        exists on disk."""
        from runtime.next.runtime_bridge import query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        ephemeral_ref = MagicMock()
        ephemeral_ref.run_dir = str(tmp_path / "ephemeral_run")
        ephemeral_ref.run_id = "ephemeral-123-DO-NOT-LEAK"

        snapshot = MagicMock()
        snapshot.completed_steps = []
        snapshot.pending_decisions = {}
        snapshot.decisions = {}
        snapshot.issued_step_id = None
        snapshot.template_path = str(tmp_path / "template.yaml")
        snapshot.policy_snapshot = MagicMock()

        first_step = MagicMock()
        first_step.kind = "step"
        first_step.step_id = "discovery"

        ephemeral_store = tmp_path / "ephemeral_store"
        ephemeral_store.mkdir()

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=None),
            patch(
                "runtime.next.runtime_bridge_io._start_ephemeral_query_run",
                return_value=(ephemeral_ref, ephemeral_store),
            ),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch("runtime.next._internal_runtime.planner.plan_next", return_value=first_step),
        ):
            decision = query_current_state(None, "069-test", tmp_path)

        assert decision.mission_state == "not_started"
        assert decision.preview_step == "discovery"
        # The crux: the ephemeral run_id must not be exposed.
        assert decision.run_id is None
        # And the temp store is cleaned up.
        assert not ephemeral_store.exists()

    def test_persisted_run_query_keeps_run_id(self, tmp_path: Path) -> None:
        """Counter-test for the omission above: when the run is real and
        persisted (not ephemeral), the run_id must still be emitted."""
        from runtime.next.runtime_bridge import query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        persisted_ref = MagicMock()
        persisted_ref.run_dir = str(tmp_path / "real_run")
        persisted_ref.run_id = "real-run-id-456"

        snapshot = MagicMock()
        snapshot.completed_steps = ["discovery"]
        snapshot.pending_decisions = {}
        snapshot.decisions = {}
        snapshot.template_path = str(tmp_path / "template.yaml")
        snapshot.issued_step_id = "plan"
        snapshot.policy_snapshot = MagicMock()

        next_step = MagicMock()
        next_step.kind = "step"
        next_step.step_id = "plan"

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=persisted_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch("runtime.next._internal_runtime.planner.plan_next", return_value=next_step),
        ):
            decision = query_current_state(None, "069-test", tmp_path)

        # Real persisted run → run_id is the real one (callers can advance against it).
        assert decision.run_id == "real-run-id-456"

    def test_inner_query_validation_error_propagates_unwrapped(self, tmp_path: Path) -> None:
        """A QueryModeValidationError raised inside the bootstrap should propagate
        as-is rather than being wrapped in a generic 'Could not read query state'
        error. This guards the explicit re-raise branch in query_current_state."""
        from runtime.next.runtime_bridge import QueryModeValidationError, query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        mock_run_ref = MagicMock()
        mock_run_ref.run_dir = str(tmp_path / "run")
        mock_run_ref.run_id = "run-inner"

        snapshot = MagicMock()
        snapshot.template_path = str(tmp_path / "template.yaml")
        snapshot.completed_steps = []
        snapshot.pending_decisions = {}
        snapshot.decisions = {}
        snapshot.policy_snapshot = MagicMock()

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=mock_run_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch(
                "runtime.next._internal_runtime.planner.plan_next",
                side_effect=QueryModeValidationError("planner contract violation"),
            ),
        ):
            with pytest.raises(QueryModeValidationError, match="planner contract violation"):
                query_current_state(None, "069-test", tmp_path)

    def test_terminal_runtime_decision_renders_done_mission_state(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        mock_run_ref = MagicMock()
        mock_run_ref.run_dir = str(tmp_path / "run")
        mock_run_ref.run_id = "run-terminal"

        snapshot = MagicMock()
        snapshot.completed_steps = ["discovery", "plan", "implement"]
        snapshot.pending_decisions = {}
        snapshot.decisions = {}
        snapshot.issued_step_id = None
        snapshot.policy_snapshot = MagicMock()

        terminal = MagicMock()
        terminal.kind = "terminal"
        terminal.step_id = None

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=mock_run_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch("runtime.next._internal_runtime.planner.plan_next", return_value=terminal),
        ):
            decision = query_current_state(None, "069-test", tmp_path)

        assert decision.mission_state == "done"
        assert decision.is_query is True

    def test_existing_run_ref_raises_when_state_json_missing(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _existing_run_ref
        from runtime.next.runtime_bridge_io import RunStateMissing

        index = {
            "069-test": {
                "run_id": "stale-run",
                "run_dir": str(tmp_path / "stale_run"),
                "mission_type": "software-dev",
            }
        }
        # The directory exists but state.json is missing. WP05 / FR-016: this is
        # a loud structured error -- returning None here used to let query mode
        # preview a phantom fresh ephemeral run over the orphaned history.
        (tmp_path / "stale_run").mkdir()

        with (
            patch("runtime.next.runtime_bridge_io.load_feature_runs", return_value=index),
            pytest.raises(RunStateMissing),
        ):
            _existing_run_ref("069-test", tmp_path, "software-dev")

    def test_start_ephemeral_query_run_cleans_up_on_bootstrap_failure(self, tmp_path: Path) -> None:
        """If start_mission_run raises, the freshly created temp dir is removed."""
        from runtime.next.runtime_bridge import _start_ephemeral_query_run

        created_dirs: list[Path] = []
        original_mkdtemp = __import__("tempfile").mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            created_dirs.append(Path(path))
            return path

        with (
            # #2531 decomposition: the real implementation (and its
            # ``tempfile``/``start_mission_run`` bindings) now lives in
            # ``runtime_bridge_io`` -- ``runtime_bridge._start_ephemeral_query_run``
            # is a thin compat delegate that forwards to it. ``_runtime_template_key``
            # / ``_build_discovery_context`` are still resolved via the io module's
            # ``_rb`` (``runtime_bridge``) back-reference, so those two patch targets
            # are unchanged.
            patch("runtime.next.runtime_bridge_io.tempfile.mkdtemp", side_effect=tracking_mkdtemp),
            patch("runtime.next.runtime_bridge_io._runtime_template_key", return_value="software-dev"),
            patch("runtime.next.runtime_bridge_io._build_discovery_context", return_value=None),
            patch("runtime.next.runtime_bridge_io.start_mission_run", side_effect=RuntimeError("template missing")),
            pytest.raises(RuntimeError, match="template missing"),
        ):
            _start_ephemeral_query_run("069-test", "software-dev", tmp_path)

        assert created_dirs, "Expected at least one mkdtemp call"
        # All tracked directories must be cleaned up.
        for path in created_dirs:
            assert not path.exists(), f"{path} should have been removed on failure"

    def test_blocked_query_keeps_step_id_and_reason_separate(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import query_current_state
        from unittest.mock import MagicMock

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        mock_run_ref = MagicMock()
        mock_run_ref.run_dir = str(tmp_path / "run")
        mock_run_ref.run_id = "run-123"

        snapshot = MagicMock()
        snapshot.completed_steps = ["discovery"]
        snapshot.pending_decisions = {}
        snapshot.decisions = {}
        snapshot.issued_step_id = "collect_input"
        snapshot.blocked_reason = "Waiting on external approval"
        snapshot.policy_snapshot = MagicMock()

        blocked = MagicMock()
        blocked.kind = "blocked"
        blocked.step_id = "collect_input"
        blocked.reason = "Waiting on external approval"

        with (
            patch("runtime.next.runtime_bridge_io._existing_run_ref", return_value=mock_run_ref),
            patch("runtime.next.runtime_bridge.get_mission_type", return_value="software-dev"),
            patch("runtime.next.runtime_bridge._compute_wp_progress", return_value=None),
            patch("runtime.next._internal_runtime.engine._read_snapshot", return_value=snapshot),
            patch("runtime.next.runtime_bridge.load_mission_template_file", return_value=MagicMock()),
            patch("runtime.next._internal_runtime.planner.plan_next", return_value=blocked),
        ):
            decision = query_current_state("claude", "069-test", tmp_path)

        assert decision.mission_state == "collect_input"
        assert decision.step_id == "collect_input"
        assert decision.reason == "Waiting on external approval"


class TestQueryModeErrorOutput:
    def test_json_query_validation_failure_returns_error_document(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import QueryModeValidationError

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch(
                "runtime.next.runtime_bridge.query_current_state",
                side_effect=QueryModeValidationError("Mission 'software-dev' has no issuable first step for run '069-test'"),
            ),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--json"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "has no issuable first step" in data["error"]

    def test_json_answer_failure_returns_single_error_document(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("specify_cli.cli.commands.next_cmd._handle_answer", side_effect=typer.Exit("No pending decisions to answer")),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-test", "--agent", "claude", "--answer", "yes", "--result", "success", "--json"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "No pending decisions to answer" in data["error"]


class TestResultSuccessStillAdvances:
    def test_result_success_calls_decide_not_query(self, tmp_path: Path) -> None:
        """C-005: --result success retains its advancing behavior."""
        from runtime.next.decision import Decision, DecisionKind

        # WP02 / #844: kind=step now requires a non-null, on-disk-resolvable
        # prompt_file at construction time (C1/C2). Materialize a real prompt
        # under tmp_path so the validator passes.
        prompt = tmp_path / "step.md"
        prompt.write_text("# step", encoding="utf-8")

        mock_decision = Decision(
            kind=DecisionKind.step,
            agent="claude",
            mission_slug="069-test",
            mission="069-test",
            mission_state="plan",
            timestamp="2026-04-07T00:00:00+00:00",
            prompt_file=str(prompt),
        )

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-test"),
            patch("specify_cli.cli.commands.next_cmd.decide_next", return_value=mock_decision) as mock_decide,
            patch("runtime.next.runtime_bridge.query_current_state") as mock_query,
            patch("specify_cli.mission_v1.events.emit_event"),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--agent", "claude", "--mission", "069-test", "--result", "success", "--json"],
            )

        mock_decide.assert_called_once()
        mock_query.assert_not_called()


class TestMissionNotFoundNextStep:
    """MissionNotFoundError carries + surfaces an actionable next_step (#1911)."""

    def test_error_populates_next_step(self) -> None:
        """The exception exposes a concrete operator remediation by default."""
        from runtime.next.runtime_bridge import MissionNotFoundError

        err = MissionNotFoundError("069-missing")

        # Affordance restored: actionable, mentions how to list missions and
        # echoes the bad handle so the operator can self-correct.
        assert err.next_step
        assert "mission list" in err.next_step
        assert "069-missing" in err.next_step
        # #1910 contract preserved exactly.
        assert err.handle == "069-missing"
        assert err.error_code == "MISSION_NOT_FOUND"

    def test_query_mode_json_payload_surfaces_next_step(self, tmp_path: Path) -> None:
        """The query-mode JSON envelope includes next_step beside error_code."""
        from runtime.next.runtime_bridge import MissionNotFoundError

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-missing"),
            patch(
                "runtime.next.runtime_bridge.query_current_state",
                side_effect=MissionNotFoundError("069-missing"),
            ),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-missing", "--json"],
            )

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["error_code"] == "MISSION_NOT_FOUND"
        assert payload["handle"] == "069-missing"
        assert "next_step" in payload
        assert "mission list" in payload["next_step"]

    def test_query_mode_human_prints_next_line(self, tmp_path: Path) -> None:
        """The human-readable query-mode path prints a 'Next:' remediation line."""
        from runtime.next.runtime_bridge import MissionNotFoundError

        with (
            patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.next_cmd._resolve_mission_slug", return_value="069-missing"),
            patch(
                "runtime.next.runtime_bridge.query_current_state",
                side_effect=MissionNotFoundError("069-missing"),
            ),
        ):
            result = runner.invoke(
                cli_app,
                ["next", "--mission", "069-missing"],
            )

        assert result.exit_code == 1
        assert "Next:" in result.output
        assert "mission list" in result.output
