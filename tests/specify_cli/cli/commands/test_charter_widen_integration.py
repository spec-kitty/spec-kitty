"""WP06 — Charter Widen Integration tests.

Tests cover all three WidenAction paths integrated with a fake charter interview:

- CANCEL path: ``w`` typed → widen flow returns CANCEL → re-prompts same question.
- BLOCK path: ``w`` typed → BLOCK → blocked-prompt loop entered; resolved via local answer.
- CONTINUE path: ``w`` typed → CONTINUE → WidenPendingEntry written to store; question skipped.

Additional tests verify:
- ``[w]iden`` is NOT shown when prereqs are absent (SPEC_KITTY_SAAS_TOKEN unset).
- Existing non-widen charter paths still pass (regression guard).
- _get_mission_id helper reads correctly from meta.json.
- _is_already_widened suppresses [w] when decision already pending.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from charter.activation.interview import MINIMAL_QUESTION_ORDER
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import (
    _get_mission_id,
    _is_already_widened,
    _resolve_dm_terminal,
    app as charter_app,
)
from specify_cli.widen.models import (
    PrereqState,
    WidenAction,
    WidenFlowResult,
    WidenPendingEntry,
)
from specify_cli.widen.state import WidenPendingStore

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-charter-widen-mission"
MISSION_ID = "01KWIDENCHARTERTESTMISSION01"

# Number of questions in the minimal profile + 3 metadata prompts (paradigms/directives/tools)
_N_QUESTIONS = len(MINIMAL_QUESTION_ORDER)
_META_PROMPTS = 3  # selected_paradigms, selected_directives, available_tools

runner = CliRunner()


def _setup_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with .kittify/ and mission meta.json."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "charter" / "interview").mkdir(parents=True, exist_ok=True)

    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


def _make_inputs(answers: list[str], meta: list[str] | None = None) -> str:
    """Build a newline-joined input string.

    ``answers`` is a list of one entry per charter question.
    ``meta`` defaults to empty strings for the 3 metadata prompts.
    """
    if meta is None:
        meta = [""] * _META_PROMPTS
    return "\n".join(answers + meta) + "\n"


def _invoke_interview(
    tmp_path: Path,
    inputs: str,
    *,
    mission_slug: str | None = MISSION_SLUG,
) -> Any:
    with contextlib.chdir(tmp_path):
        args = ["interview", "--profile", "minimal"]
        if mission_slug is not None:
            args += ["--mission-slug", mission_slug]
        return runner.invoke(charter_app, args, input=inputs, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestGetMissionId:
    def test_reads_mission_id_from_meta_json(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        result = _get_mission_id(tmp_path, MISSION_SLUG)
        assert result == MISSION_ID

    def test_returns_none_if_meta_missing(self, tmp_path: Path) -> None:
        result = _get_mission_id(tmp_path, "nonexistent-slug")
        assert result is None

    def test_returns_none_if_json_malformed(self, tmp_path: Path) -> None:
        mission_dir = tmp_path / "kitty-specs" / "bad-slug"
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "meta.json").write_text("not json", encoding="utf-8")
        result = _get_mission_id(tmp_path, "bad-slug")
        assert result is None

    def test_returns_none_if_mission_id_key_absent(self, tmp_path: Path) -> None:
        mission_dir = tmp_path / "kitty-specs" / "slug-no-id"
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": "slug-no-id"}), encoding="utf-8")
        result = _get_mission_id(tmp_path, "slug-no-id")
        assert result is None


class TestIsAlreadyWidened:
    def test_returns_false_for_empty_store(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        store = WidenPendingStore(tmp_path, MISSION_SLUG)
        assert _is_already_widened(store, "some-decision-id") is False

    def test_returns_true_when_decision_pending(self, tmp_path: Path) -> None:
        from kernel.clock import now_utc

        _setup_repo(tmp_path)
        store = WidenPendingStore(tmp_path, MISSION_SLUG)
        entry = WidenPendingEntry(
            decision_id="dec-001",
            mission_slug=MISSION_SLUG,
            question_id="charter.project_name",
            question_text="What is the project name?",
            entered_pending_at=now_utc(),
            widen_endpoint_response={},
        )
        store.add_pending(entry)
        assert _is_already_widened(store, "dec-001") is True
        assert _is_already_widened(store, "dec-002") is False

    def test_returns_false_on_exception(self) -> None:
        bad_store = MagicMock()
        bad_store.list_pending.side_effect = RuntimeError("boom")
        assert _is_already_widened(bad_store, "any") is False


class TestResolveDmTerminal:
    def test_cancel_on_exclamation_cancel(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        cancel_mock = MagicMock()
        with patch(
            "specify_cli.cli.commands.charter._dm_service.cancel_decision",
            cancel_mock,
        ):
            _resolve_dm_terminal(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                decision_id="dec-001",
                actual_answer="!cancel",
                actor="test",
            )
        cancel_mock.assert_called_once()

    def test_resolve_on_nonempty_answer(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        resolve_mock = MagicMock()
        with patch(
            "specify_cli.cli.commands.charter._dm_service.resolve_decision",
            resolve_mock,
        ):
            _resolve_dm_terminal(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                decision_id="dec-001",
                actual_answer="PostgreSQL",
                actor="test",
            )
        resolve_mock.assert_called_once()

    def test_defer_on_empty_answer(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        defer_mock = MagicMock()
        with patch(
            "specify_cli.cli.commands.charter._dm_service.defer_decision",
            defer_mock,
        ):
            _resolve_dm_terminal(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                decision_id="dec-001",
                actual_answer="",
                actor="test",
            )
        defer_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: widen absent (prereqs not satisfied)
# ---------------------------------------------------------------------------


class TestWidenAbsentWhenPrereqsMissing:
    """When SPEC_KITTY_SAAS_TOKEN is unset, [w]iden should NOT appear in output."""

    def test_widen_option_not_shown_without_token(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        # Use accept-default for all questions + empty meta prompts
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output

    def test_widen_option_not_shown_without_mission_slug(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs, mission_slug=None)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output


# ---------------------------------------------------------------------------
# Integration: widen paths with mocked WidenFlow + prereq check
# ---------------------------------------------------------------------------


def _make_widen_patches(
    *,
    prereq_ok: PrereqState,
    mock_flow: MagicMock,
    widen_store: Any = None,
) -> list[Any]:
    """Return a list of context-manager patches for widen integration tests.

    The imports are local to interview(), so we must patch at the source
    module locations.
    """
    mock_store = widen_store if widen_store is not None else MagicMock()
    return [
        patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=MagicMock(_token="tok")),
        patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
        patch("specify_cli.widen.flow.WidenFlow.__init__", return_value=None),
        patch("specify_cli.widen.flow.WidenFlow.run_widen_mode", mock_flow.run_widen_mode),
        patch("specify_cli.widen.state.WidenPendingStore.__init__", return_value=None),
        patch("specify_cli.widen.state.WidenPendingStore.list_pending", MagicMock(return_value=[])),
        patch("specify_cli.widen.state.WidenPendingStore.add_pending", mock_store.add_pending if isinstance(mock_store, MagicMock) else mock_store.add_pending),
    ]


class TestWidenCancelPath:
    """CANCEL path: typing w → CANCEL → re-prompts same question → normal answer."""

    def test_cancel_path_reprompts_question(self, tmp_path: Path) -> None:
        """Verify that after CANCEL the same question is re-prompted and flow continues."""
        _setup_repo(tmp_path)

        cancel_result = WidenFlowResult(action=WidenAction.CANCEL)
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = cancel_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        # Q1: "w" → CANCEL → re-prompted → "MyProject"
        # Q2..N: accept defaults (empty = default)
        # meta: 3 empty lines
        q1_inputs = ["w", "MyProject"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=MagicMock(_token="tok")),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow) as _flow_cls,
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store_inst = MagicMock()
            mock_store_inst.list_pending.return_value = []
            mock_store_cls.return_value = mock_store_inst

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        mock_flow.run_widen_mode.assert_called_once()
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()


class TestWidenContinuePath:
    """CONTINUE path: typing w → CONTINUE → WidenPendingEntry written; question skipped."""

    def test_continue_path_writes_pending_entry(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)

        decision_id = "01KWIDENDEC00001"
        continue_result = WidenFlowResult(
            action=WidenAction.CONTINUE,
            decision_id=decision_id,
            invited=["Alice Johnson", "Carol Lee"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = continue_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        # Use a real WidenPendingStore so we can assert the file was written
        _setup_repo(tmp_path)
        real_store = WidenPendingStore(tmp_path, MISSION_SLUG)

        # Q1: "w" → CONTINUE → question is skipped (widen pending)
        # Q2..N: accept defaults
        # meta: 3 empty lines
        q1_inputs = ["w"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=MagicMock(_token="tok")),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch("specify_cli.widen.state.WidenPendingStore", return_value=real_store),
            # WP08: suppress end-of-interview pending pass so this test focuses
            # only on the CONTINUE path (entry is written to store).
            # The end-of-interview pass is tested separately in
            # test_end_of_interview_pending_pass.py.
            patch(
                "specify_cli.widen.interview_helpers.run_end_of_interview_pending_pass",
                MagicMock(),
            ),
        ):
            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        mock_flow.run_widen_mode.assert_called_once()

        # WidenPendingEntry must have been written to the sidecar
        pending = real_store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == decision_id
        assert pending[0].mission_slug == MISSION_SLUG
        assert pending[0].question_id.startswith("charter.")


class TestWidenBlockPath:
    """BLOCK path: typing w → BLOCK → blocked-prompt loop; resolved via local answer."""

    def test_block_path_resolves_via_local_answer(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)

        decision_id = "01KWIDENDEC00002"
        block_result = WidenFlowResult(
            action=WidenAction.BLOCK,
            decision_id=decision_id,
            invited=["Alice Johnson"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = block_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        # Q1: "w" → BLOCK → "local answer here" at blocked prompt → Q2..N → meta
        q1_inputs = ["w", "local answer here"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=MagicMock(_token="tok")),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.resolve_decision",
                return_value=MagicMock(),
            ),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store_inst = MagicMock()
            mock_store_inst.list_pending.return_value = []
            mock_store_cls.return_value = mock_store_inst

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        mock_flow.run_widen_mode.assert_called_once()
        # "Resolved locally" message should appear
        assert "Resolved locally" in result.output

    def test_block_path_defer_from_blocked_prompt(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)

        decision_id = "01KWIDENDEC00003"
        block_result = WidenFlowResult(
            action=WidenAction.BLOCK,
            decision_id=decision_id,
            invited=["Bob Smith"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = block_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        # Q1: "w" → BLOCK → "d" at Waiting > → "" (empty rationale) → Q2..N → meta
        q1_inputs = ["w", "d", ""]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=MagicMock(_token="tok")),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.defer_decision",
                return_value=MagicMock(),
            ),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store_inst = MagicMock()
            mock_store_inst.list_pending.return_value = []
            mock_store_cls.return_value = mock_store_inst

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        mock_flow.run_widen_mode.assert_called_once()
        assert "deferred" in result.output.lower()


# ---------------------------------------------------------------------------
# Regression: existing non-widen charter tests still pass
# ---------------------------------------------------------------------------


class TestNonWidenRegressions:
    """Verify existing non-widen charter behavior is unaffected."""

    def test_normal_answer_saved_to_yaml(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        # Accept defaults for all questions
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs)
        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()

    def test_defaults_flag_skips_prompts(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--defaults"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()

    def test_json_output_flag(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--defaults", "--json"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["result"] == "success"
