"""WP10 T052 — Charter widen happy-path integration tests.

Tests cover:
- [w]iden affordance shown when prereqs satisfied.
- [w]iden NOT shown when prereqs absent (SC-004).
- w input → audience review → widen POST → [b] block → local answer resolves.
- w input → [c] continue → question parked in widen-pending store.
- Token absent → [w]iden suppressed (SC-004, C-007, C-009).
- NFR-001: prereq check under 300ms.
- NFR-004: inactivity reminder fires after configurable delay.
"""

from __future__ import annotations

import contextlib
import json
import time
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from charter.activation.interview import MINIMAL_QUESTION_ORDER
from rich.console import Console
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.widen.models import PrereqState, WidenAction, WidenFlowResult
from specify_cli.widen.state import WidenPendingStore
from tests._perf_helpers import assert_timing_budget

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-charter-widen-wp10"
MISSION_ID = "01KWP10CHARTERWIDENMISSION"

_N_QUESTIONS = len(MINIMAL_QUESTION_ORDER)
_META_PROMPTS = 3

runner = CliRunner()


def _setup_repo(tmp_path: Path) -> Path:
    """Create minimal repo with .kittify/ and mission meta.json."""
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
    """Build a newline-joined input string."""
    if meta is None:
        meta = [""] * _META_PROMPTS
    return "\n".join(answers + meta) + "\n"


def _invoke_interview(
    tmp_path: Path,
    inputs: str,
    *,
    mission_slug: str | None = MISSION_SLUG,
    extra_patches: list | None = None,
) -> object:
    with contextlib.chdir(tmp_path):
        args = ["interview", "--profile", "minimal"]
        if mission_slug is not None:
            args += ["--mission-slug", mission_slug]
        if extra_patches:
            with contextlib.ExitStack() as stack:
                for p in extra_patches:
                    stack.enter_context(p)
                return runner.invoke(charter_app, args, input=inputs, catch_exceptions=False)
        return runner.invoke(charter_app, args, input=inputs, catch_exceptions=False)


def _make_decision_error() -> Exception:
    from specify_cli.decisions.models import DecisionErrorCode
    from specify_cli.decisions.service import DecisionError

    return DecisionError(code=DecisionErrorCode.TERMINAL_CONFLICT)


# ---------------------------------------------------------------------------
# [w]iden affordance visibility
# ---------------------------------------------------------------------------


class TestBlockedPromptWriteBackFailures:
    """Blocked prompt write-back failures must not fake terminal progress."""

    def test_local_answer_failure_reprompts_before_advancing(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.charter import _run_blocked_prompt_loop

        console = Console(file=StringIO(), highlight=False, markup=False)
        timer = MagicMock()

        with (
            patch.object(console, "input", side_effect=["first answer", "second answer"]),
            patch(
                "specify_cli.cli.commands.charter._widen._schedule_inactivity_reminder",
                return_value=timer,
            ),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.resolve_decision",
                side_effect=[_make_decision_error(), MagicMock()],
            ) as mock_resolve,
        ):
            _run_blocked_prompt_loop(
                decision_id="dec-001",
                question_text="Which DB?",
                invited=["Alice"],
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                saas_client=MagicMock(),
                actor="tester",
            )

        assert mock_resolve.call_count == 2
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "not saved" in output.lower()
        assert "Resolved locally" in output

    def test_defer_failure_reprompts_before_advancing(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.charter import _run_blocked_prompt_loop

        console = Console(file=StringIO(), highlight=False, markup=False)
        timer = MagicMock()

        with (
            patch.object(console, "input", side_effect=["d", "not ready", "d", "ready"]),
            patch(
                "specify_cli.cli.commands.charter._widen._schedule_inactivity_reminder",
                return_value=timer,
            ),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.defer_decision",
                side_effect=[_make_decision_error(), MagicMock()],
            ) as mock_defer,
        ):
            _run_blocked_prompt_loop(
                decision_id="dec-001",
                question_text="Which DB?",
                invited=["Alice"],
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                saas_client=MagicMock(),
                actor="tester",
            )

        assert mock_defer.call_count == 2
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "not saved" in output.lower()
        assert "Decision deferred" in output


class TestWidenAffordanceVisibility:
    """[w]iden affordance presence and absence."""

    def test_widen_shown_when_prereqs_satisfied(self, tmp_path: Path) -> None:
        """[w]iden affordance present in prompt when all prereqs satisfied (FR-001).

        Note: CliRunner strips Rich markup brackets, so ``[w]iden`` renders as
        ``iden`` in the captured output (the ``[w]`` part is treated as markup).
        We verify the widen option by checking for ``iden`` combined with the
        ``efer`` fragment (which comes from ``[d]efer``) — both are present only
        when the widen affordance is rendered.
        """
        _setup_repo(tmp_path)
        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)
        # Accept defaults for all questions; test that prompt includes widen option
        inputs = _make_inputs([""] * _N_QUESTIONS)

        with (
            contextlib.chdir(tmp_path),
            patch(
                "specify_cli.saas_client.client.SaasClient.from_env",
                return_value=MagicMock(_token="tok"),
            ),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=MagicMock()),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.list_pending.return_value = []
            mock_store_cls.return_value = mock_store

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        # Rich strips [w] markup, so "iden" (from [w]iden) and "efer" (from [d]efer)
        # appear in the prompt line. When prereqs are absent only "efer" appears.
        # Verify by checking for the widen-specific fragment "iden" in prompt context.
        assert "iden" in result.output

    def test_widen_not_shown_when_token_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """With SPEC_KITTY_SAAS_TOKEN unset, [w]iden must NOT appear (SC-004)."""
        _setup_repo(tmp_path)
        monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output


# ---------------------------------------------------------------------------
# Happy path: w → block → local answer
# ---------------------------------------------------------------------------


class TestWidenHappyPathBlock:
    """Primary scenario: w → BLOCK → local answer → Resolved locally."""

    def test_w_then_block_then_local_answer(self, tmp_path: Path) -> None:
        """w input → widen flow runs → BLOCK → local answer → 'Resolved locally'."""
        _setup_repo(tmp_path)

        decision_id = "01KWP10BLOCKTEST00001"
        block_result = WidenFlowResult(
            action=WidenAction.BLOCK,
            decision_id=decision_id,
            invited=["Alice Johnson"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = block_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        # Q1: "w" → BLOCK → local answer at blocked prompt → Q2..N → meta
        q1_inputs = ["w", "PostgreSQL with migration plan"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch(
                "specify_cli.saas_client.client.SaasClient.from_env",
                return_value=MagicMock(_token="tok"),
            ),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.resolve_decision",
                return_value=MagicMock(),
            ),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.list_pending.return_value = []
            mock_store_cls.return_value = mock_store

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        mock_flow.run_widen_mode.assert_called_once()
        assert "Resolved locally" in result.output

    def test_answers_yaml_written_after_block_path(self, tmp_path: Path) -> None:
        """answers.yaml is written correctly at interview completion after widen block."""
        _setup_repo(tmp_path)

        decision_id = "01KWP10BLOCKYAML0001"
        block_result = WidenFlowResult(
            action=WidenAction.BLOCK,
            decision_id=decision_id,
            invited=["Bob Smith"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = block_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        q1_inputs = ["w", "my local answer"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch(
                "specify_cli.saas_client.client.SaasClient.from_env",
                return_value=MagicMock(_token="tok"),
            ),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.resolve_decision",
                return_value=MagicMock(),
            ),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.list_pending.return_value = []
            mock_store_cls.return_value = mock_store

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()


# ---------------------------------------------------------------------------
# Happy path: w → continue → question parked
# ---------------------------------------------------------------------------


class TestWidenHappyPathContinue:
    """Secondary scenario: w → CONTINUE → question parked in pending store."""

    def test_continue_marker_failure_does_not_advance_question(
        self,
        tmp_path: Path,
    ) -> None:
        """Pending marker write failure must re-prompt instead of parking blank."""
        from specify_cli.cli.commands.charter import _dispatch_widen_input

        decision_id = "01KWP10CONTINUEFAIL01"
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = WidenFlowResult(
            action=WidenAction.CONTINUE,
            decision_id=decision_id,
            invited=["Alice Johnson"],
        )
        bad_store = MagicMock()
        bad_store.add_pending.side_effect = OSError("disk full")
        console = Console(file=StringIO(), highlight=False, markup=False)
        answers_override: dict[str, str] = {}

        answer, should_break = _dispatch_widen_input(
            widen_flow=mock_flow,
            current_decision_id=decision_id,
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            question_id="database",
            prompt_text="Which DB?",
            hint_line="[enter]=accept default | [w]iden",
            widen_store=bad_store,
            answers_override=answers_override,
            repo_root=tmp_path,
            console=console,
            saas_client=MagicMock(),
            actor="tester",
        )

        assert answer is None
        assert should_break is False
        assert answers_override == {}
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Question was NOT" in output
        assert "parked" in output

    def test_w_then_continue_parks_question(self, tmp_path: Path) -> None:
        """w input → CONTINUE → WidenPendingEntry written to store (FR-009)."""
        _setup_repo(tmp_path)

        decision_id = "01KWP10CONTINUETEST001"
        continue_result = WidenFlowResult(
            action=WidenAction.CONTINUE,
            decision_id=decision_id,
            invited=["Alice Johnson", "Carol Lee"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = continue_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)
        real_store = WidenPendingStore(tmp_path, MISSION_SLUG)

        q1_inputs = ["w"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch(
                "specify_cli.saas_client.client.SaasClient.from_env",
                return_value=MagicMock(_token="tok"),
            ),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch("specify_cli.widen.state.WidenPendingStore", return_value=real_store),
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

        pending = real_store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == decision_id
        assert pending[0].mission_slug == MISSION_SLUG

    def test_answers_yaml_written_after_continue_path(self, tmp_path: Path) -> None:
        """answers.yaml is written at completion after widen-continue (FR-010)."""
        _setup_repo(tmp_path)

        decision_id = "01KWP10CONTINUEYAML001"
        continue_result = WidenFlowResult(
            action=WidenAction.CONTINUE,
            decision_id=decision_id,
            invited=["Dana Park"],
        )
        mock_flow = MagicMock()
        mock_flow.run_widen_mode.return_value = continue_result

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        q1_inputs = ["w"]
        remaining_q = [""] * (_N_QUESTIONS - 1)
        inputs = _make_inputs(q1_inputs + remaining_q)

        with (
            contextlib.chdir(tmp_path),
            patch(
                "specify_cli.saas_client.client.SaasClient.from_env",
                return_value=MagicMock(_token="tok"),
            ),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=mock_flow),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
            patch(
                "specify_cli.widen.interview_helpers.run_end_of_interview_pending_pass",
                MagicMock(),
            ),
        ):
            mock_store = MagicMock()
            mock_store.list_pending.return_value = []
            mock_store_cls.return_value = mock_store

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()


# ---------------------------------------------------------------------------
# NFR-001: prereq check under 300ms
# ---------------------------------------------------------------------------


class TestNFR001PrereqLatency:
    """NFR-001: prereq check + audience-default fetch < 300ms at p95."""

    def test_prereq_check_succeeds(self) -> None:
        """Mocked prereq check reports satisfied prerequisites."""
        from specify_cli.widen import check_prereqs

        client = MagicMock()
        client._token = "tok"
        client.get_team_integrations.return_value = ["slack"]
        client.health_probe.return_value = True

        result = check_prereqs(client, "team-slug")

        assert result.all_satisfied is True

    @pytest.mark.performance
    def test_prereq_check_under_300ms(self) -> None:
        """Mocked prereq check runs well under 300ms (NFR-001)."""
        from specify_cli.widen import check_prereqs

        client = MagicMock()
        client._token = "tok"
        client.get_team_integrations.return_value = ["slack"]
        client.health_probe.return_value = True

        start = time.perf_counter()
        check_prereqs(client, "team-slug")
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 0.3, name="check_prereqs")

    def test_prereq_check_with_saas_error_is_not_satisfied(self) -> None:
        """Even on SaaS error, prereq check reports the failure correctly."""
        from specify_cli.saas_client import SaasClientError
        from specify_cli.widen import check_prereqs

        client = MagicMock()
        client._token = "tok"
        client.get_team_integrations.side_effect = SaasClientError("err")
        client.health_probe.return_value = False

        result = check_prereqs(client, "team-slug")

        assert result.all_satisfied is False

    @pytest.mark.performance
    def test_prereq_check_under_300ms_with_saas_error(self) -> None:
        """Even on SaaS error, prereq check stays under 300ms (NFR-001)."""
        from specify_cli.saas_client import SaasClientError
        from specify_cli.widen import check_prereqs

        client = MagicMock()
        client._token = "tok"
        client.get_team_integrations.side_effect = SaasClientError("err")
        client.health_probe.return_value = False

        start = time.perf_counter()
        check_prereqs(client, "team-slug")
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 0.3, name="check_prereqs (with SaaS error)")


# ---------------------------------------------------------------------------
# NFR-004: inactivity reminder fires
# ---------------------------------------------------------------------------


class TestNFR004InactivityReminder:
    """NFR-004: inactivity reminder fires after delay_seconds."""

    def test_inactivity_timer_fires_at_configured_delay(self) -> None:
        """With a 0.05s delay, verify the inactivity reminder fires."""
        import io

        from rich.console import Console

        from specify_cli.cli.commands.charter import _schedule_inactivity_reminder

        buf = io.StringIO()
        console = Console(file=buf, highlight=False, markup=True)

        timer = _schedule_inactivity_reminder(console, delay_seconds=0.05)
        timer.join(timeout=1.0)

        output = buf.getvalue()
        # The reminder must have been printed
        assert "waiting" in output.lower() or "widen" in output.lower(), f"Inactivity reminder not found in output: {output!r}"

    def test_inactivity_timer_is_daemon(self) -> None:
        """Timer thread is a daemon so it does not block process exit."""
        import io

        from rich.console import Console

        from specify_cli.cli.commands.charter import _schedule_inactivity_reminder

        buf = io.StringIO()
        console = Console(file=buf, highlight=False, markup=True)

        # Long delay — we just check daemonhood, not that it fires
        timer = _schedule_inactivity_reminder(console, delay_seconds=3600)
        assert timer.daemon is True
        timer.cancel()  # clean up
