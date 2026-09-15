"""Tests for ``spec-kitty agent decision widen`` internal subcommand (WP09 / T046-T049).

Coverage:
  T046: widen subcommand exists under decision_app with hidden=True
  T047: --dry-run prints expected JSON payload and exits 0
  T048: live path calls SaasClient.post_widen and prints success JSON
  T048: SaasClientError → error to stderr, exit 1
  T048: empty --invited list → exit 1
  T049: _render_widen_hint_if_present strips prefix and prints dim text
  T049: _render_widen_hint_if_present no-ops when no hint present
  T049: _render_widen_hint_if_present handles multiple lines
  T049: _render_widen_hint_if_present is exported from interview_helpers
  misc: widen not shown in ``decision --help`` (hidden=True)
  misc: widen --help is accessible when called directly
  misc: --invited user IDs with whitespace-only entries filtered correctly
  misc: missing --invited argument → exit non-zero
  misc: --mission-slug is optional (None is valid)
  misc: dry_run payload includes endpoint field
"""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.saas_client.errors import SaasClientError

from tests._support.ansi import strip_ansi

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: Corrected for `#3111`/FR-005. The previous literal ``01KWIDETEST00000000001``
#: was **22 characters and contained an `I`**, so it fails every one of the three
#: existing ULID regexes — including the one the CLI shape check now reuses.
#:
#: **The fixture was corrected; the check was NOT loosened.** Relaxing, widening
#: or bypassing the ULID check so the old literal passes — including "reuse a
#: fourth, looser regex here" — is a forbidden repair: Q7's whole point is that
#: the check reuses **one existing** regex, and a looser one at the CLI would be
#: this mission's own whack-a-field.
DECISION_ID = "01KZWDENTEST00000000000042"
MISSION_SLUG = "test-widen-mission"

runner = CliRunner()


def _invoke(args: list[str], cwd: Path | None = None) -> Result:
    """Invoke the agent_app with given args."""
    old_cwd = os.getcwd()
    try:
        if cwd is not None:
            os.chdir(cwd)
        return runner.invoke(agent_app, args, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def _arrange_owning_ledger(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make *root* genuinely own ``DECISION_ID``, and act from it.

    `#3111` gave ``cmd_widen`` an ownership check that runs **before**
    ``SaasClient.from_env``: the acting checkout must be able to show, from its
    own ``kitty-specs/*/decisions/index.json``, that it owns the decision being
    widened. The live-path tests below drive the command against a bare
    ``tmp_path`` that owns no ledger at all, so without this arrangement the
    command refuses before the mocks are ever reached.

    **This is an ARRANGEMENT, not a repair.** The admissible response to those
    reds is to make the acting root genuinely own the decision — not to make
    ownership permissive when the acting root has no ``kitty-specs/``. That
    "no ledger anywhere, so allow it" shortcut is the fall-through `#3111` exists
    to close, reached from a different direction; it would green all eight
    live-path tests in one line and reinstate the leak.

    ``SPECIFY_REPO_ROOT`` is set so ``locate_project_root`` resolves to *root*
    deterministically rather than depending on whatever lies above ``tmp_path``.
    """
    decisions = root / "kitty-specs" / MISSION_SLUG / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    mission_id = "01KZMISSION0000000000000ZA"
    payload = {
        "version": 1,
        "mission_id": mission_id,
        "entries": [
            {
                "decision_id": DECISION_ID,
                "origin_flow": "plan",
                "step_id": "step-1",
                "input_key": "key",
                "question": "q?",
                "status": "open",
                "created_at": "2026-01-01T00:00:00+00:00",
                "mission_id": mission_id,
                "mission_slug": MISSION_SLUG,
            }
        ],
    }
    (decisions / "index.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    return root


def _make_widen_response(
    decision_id: str = DECISION_ID,
    widened_at: str = "2026-04-23T12:00:00+00:00",
    slack_thread_url: str | None = "https://slack.example.com/thread/123",
    invited_count: int | None = 2,
) -> dict:  # type: ignore[type-arg]
    """Build a mock WidenResponse TypedDict."""
    return {
        "decision_id": decision_id,
        "widened_at": widened_at,
        "slack_thread_url": slack_thread_url,
        "invited_count": invited_count,
    }


# ---------------------------------------------------------------------------
# T047 — --dry-run mode
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_exits_zero(self, tmp_path: Path) -> None:
        """--dry-run exits 0."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101,102", "--dry-run"],
            cwd=tmp_path,
        )
        assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}\n{result.output}"

    def test_dry_run_prints_valid_json(self, tmp_path: Path) -> None:
        """--dry-run output is valid JSON."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101,102", "--dry-run"],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert payload["dry_run"] is True

    def test_dry_run_includes_decision_id(self, tmp_path: Path) -> None:
        """--dry-run output includes the decision_id."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101,102", "--dry-run"],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert payload["decision_id"] == DECISION_ID

    def test_dry_run_includes_invited_list(self, tmp_path: Path) -> None:
        """--dry-run output includes parsed invited list."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101, 102", "--dry-run"],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert payload["invited"] == [101, 102]

    def test_dry_run_includes_endpoint(self, tmp_path: Path) -> None:
        """--dry-run output includes the endpoint field."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101", "--dry-run"],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert "endpoint" in payload
        assert DECISION_ID in payload["endpoint"]

    def test_dry_run_includes_payload(self, tmp_path: Path) -> None:
        """--dry-run output includes the payload sub-object."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101,102", "--dry-run"],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert "payload" in payload
        assert payload["payload"]["invited_user_ids"] == [101, 102]

    def test_dry_run_includes_mission_slug_none(self, tmp_path: Path) -> None:
        """--dry-run includes mission_slug=None when not provided."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "101", "--dry-run"],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert payload["mission_slug"] is None

    def test_dry_run_includes_mission_slug_when_provided(self, tmp_path: Path) -> None:
        """--dry-run includes mission_slug when --mission-slug is passed."""
        result = _invoke(
            [
                "decision",
                "widen",
                DECISION_ID,
                "--invited",
                "101",
                "--mission-slug",
                MISSION_SLUG,
                "--dry-run",
            ],
            cwd=tmp_path,
        )
        payload = json.loads(result.output)
        assert payload["mission_slug"] == MISSION_SLUG

    def test_dry_run_no_http_call(self, tmp_path: Path) -> None:
        """--dry-run makes no HTTP calls (SaasClient is never constructed)."""
        with patch("specify_cli.saas_client.client.SaasClient.from_env") as mock_from_env:
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101", "--dry-run"],
                cwd=tmp_path,
            )
        mock_from_env.assert_not_called()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# T048 — live path (SaasClient.post_widen)
# ---------------------------------------------------------------------------


class TestLivePath:
    def test_live_success_exits_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful widen exits 0."""
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.return_value = _make_widen_response()
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101,102"],
                cwd=tmp_path,
            )
        assert result.exit_code == 0, f"exit {result.exit_code}\n{result.output}"

    def test_live_success_prints_success_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful widen prints JSON with success=True."""
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.return_value = _make_widen_response()
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101,102"],
                cwd=tmp_path,
            )
        payload = json.loads(result.output)
        assert payload["success"] is True

    def test_live_success_includes_decision_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful widen prints decision_id."""
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.return_value = _make_widen_response()
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101"],
                cwd=tmp_path,
            )
        payload = json.loads(result.output)
        assert payload["decision_id"] == DECISION_ID

    def test_live_success_calls_post_widen(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Live path calls post_widen with parsed invited list."""
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.return_value = _make_widen_response()
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101, 102"],
                cwd=tmp_path,
            )
        mock_client.post_widen.assert_called_once_with(
            decision_id=DECISION_ID, invited=[101, 102]
        )

    def test_live_saas_error_exits_one(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SaasClientError → exit 1, **and for that reason** (LOW-5).

        This was an exit-code-only assertion, and **an ownership refusal also exits
        1**. That is why it was a FALSE GREEN during WP04's implementation: it
        survived while the other seven live-path tests in this class went red, so
        it read as evidence that the live path still worked when in fact the
        command was refusing before ``post_widen`` was ever reached. An
        exit-code-only assertion on a code that two unrelated paths share cannot
        tell you which path you are on.

        Two assertions are folded in, and they are not redundant with each other:

        * the message, which is what its sibling
          ``test_live_saas_error_message_in_output`` checks; and
        * ``post_widen`` having actually been called, which is the sharper
          discriminator and the thing the sibling does **not** check. An ownership
          refusal returns before ``from_env``, so a reached ``post_widen`` is
          positive proof the exit 1 came from :class:`SaasClientError`.
        """
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.side_effect = SaasClientError("server error", status_code=500)
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101"],
                cwd=tmp_path,
            )
        assert result.exit_code == 1
        assert "server error" in result.output, (
            f"exit 1 without the SaasClientError message: an ownership refusal "
            f"exits 1 too, so this is the assertion that says WHICH path produced "
            f"it. Output was: {result.output!r}"
        )
        # The live path must have been REACHED, not merely have exited 1: an
        # ownership refusal returns before ``from_env``, so `post_widen` having
        # been called is what excludes it. `assert_called_once_with` raises on
        # failure, so no `assert` wrapper (and no trailing message tuple) here.
        mock_client.post_widen.assert_called_once_with(decision_id=DECISION_ID, invited=[101])

    def test_live_saas_error_message_in_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SaasClientError message appears in output and exit code is 1."""
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.side_effect = SaasClientError("server error", status_code=500)
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101"],
                cwd=tmp_path,
            )
        assert result.exit_code == 1
        assert "server error" in result.output

    def test_live_path_passes_repo_root_to_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """cmd_widen passes repo_root to SaasClient.from_env.

        D-5: file-auth path (.kittify/saas-auth.json) must be reachable from the
        widen command — requires from_env(repo_root=<path>), not from_env() (#2248).
        """
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.return_value = _make_widen_response()
        captured: list[object] = []

        def _capture_from_env(repo_root: object = None) -> object:
            captured.append(repo_root)
            return mock_client

        with patch("specify_cli.saas_client.client.SaasClient.from_env", side_effect=_capture_from_env):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", "101"],
                cwd=tmp_path,
            )
        assert result.exit_code == 0, f"exit {result.exit_code}\n{result.output}"
        assert len(captured) == 1
        assert captured[0] is not None, (
            "from_env must receive a repo_root so .kittify/saas-auth.json is reachable (D-5 / #2248)"
        )
        assert isinstance(captured[0], Path)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_empty_invited_list_exits_one(self, tmp_path: Path) -> None:
        """Empty --invited CSV → exit 1."""
        result = _invoke(
            ["decision", "widen", DECISION_ID, "--invited", "  ,  "],
            cwd=tmp_path,
        )
        assert result.exit_code == 1

    def test_whitespace_only_entries_filtered(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace-only entries in --invited are filtered; non-empty passes."""
        _arrange_owning_ledger(tmp_path, monkeypatch)
        mock_client = MagicMock()
        mock_client.post_widen.return_value = _make_widen_response()
        with patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=mock_client):
            result = _invoke(
                ["decision", "widen", DECISION_ID, "--invited", " 101 , , 102 "],
                cwd=tmp_path,
            )
        assert result.exit_code == 0
        mock_client.post_widen.assert_called_once_with(
            decision_id=DECISION_ID, invited=[101, 102]
        )

    def test_missing_invited_flag_exits_nonzero(self, tmp_path: Path) -> None:
        """Omitting --invited entirely → non-zero exit (required option)."""
        result = runner.invoke(
            agent_app,
            ["decision", "widen", DECISION_ID],
            catch_exceptions=False,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# T046 — hidden=True behaviour
# ---------------------------------------------------------------------------


class TestHiddenFlag:
    def test_widen_not_in_decision_help(self, tmp_path: Path) -> None:
        """``decision --help`` does NOT list 'widen'."""
        result = _invoke(["decision", "--help"], cwd=tmp_path)
        assert "widen" not in result.output

    def test_widen_help_accessible_directly(self, tmp_path: Path) -> None:
        """``decision widen --help`` is accessible."""
        result = _invoke(["decision", "widen", "--help"], cwd=tmp_path)
        assert result.exit_code == 0
        # Strip ANSI: under CI, Rich force-enables terminal styling so the
        # captured help carries colour codes that break a raw substring check.
        output = strip_ansi(result.output)
        assert "internal" in output.lower() or "--invited" in output


# ---------------------------------------------------------------------------
# T049 — _render_widen_hint_if_present
# ---------------------------------------------------------------------------


class TestRenderWidenHint:
    def _make_console(self) -> tuple[Console, StringIO]:
        """Return a Console that writes to a StringIO buffer."""
        buf = StringIO()
        console = Console(file=buf, highlight=False, markup=True)
        return console, buf

    def test_hint_is_rendered_as_dim(self) -> None:
        """A line starting with [WIDEN-HINT] is rendered."""
        from specify_cli.widen.interview_helpers import render_widen_hint_if_present

        console, buf = self._make_console()
        render_widen_hint_if_present("[WIDEN-HINT] Check with the team first.", console)
        output = buf.getvalue()
        assert "Check with the team first." in output

    def test_no_hint_no_output(self) -> None:
        """Context without [WIDEN-HINT] produces no output."""
        from specify_cli.widen.interview_helpers import render_widen_hint_if_present

        console, buf = self._make_console()
        render_widen_hint_if_present("Normal question context.", console)
        assert buf.getvalue().strip() == ""

    def test_multiple_hint_lines_all_rendered(self) -> None:
        """Multiple [WIDEN-HINT] lines are all rendered."""
        from specify_cli.widen.interview_helpers import render_widen_hint_if_present

        console, buf = self._make_console()
        context = "[WIDEN-HINT] Hint line 1.\n[WIDEN-HINT] Hint line 2."
        render_widen_hint_if_present(context, console)
        output = buf.getvalue()
        assert "Hint line 1." in output
        assert "Hint line 2." in output

    def test_mixed_lines_only_hints_rendered(self) -> None:
        """Only [WIDEN-HINT] lines are rendered; other lines are ignored."""
        from specify_cli.widen.interview_helpers import render_widen_hint_if_present

        console, buf = self._make_console()
        context = "Normal line.\n[WIDEN-HINT] This is the hint.\nAnother normal line."
        render_widen_hint_if_present(context, console)
        output = buf.getvalue()
        assert "This is the hint." in output
        assert "Normal line." not in output
        assert "Another normal line." not in output

    def test_exported_from_interview_helpers(self) -> None:
        """render_widen_hint_if_present is exported in __all__."""
        from specify_cli.widen import interview_helpers

        assert "render_widen_hint_if_present" in interview_helpers.__all__

    def test_prefix_stripped_from_hint_text(self) -> None:
        """The [WIDEN-HINT] prefix is NOT included in the rendered text."""
        from specify_cli.widen.interview_helpers import render_widen_hint_if_present

        console, buf = self._make_console()
        render_widen_hint_if_present("[WIDEN-HINT] Press w to widen.", console)
        output = buf.getvalue()
        assert "[WIDEN-HINT]" not in output
        assert "Press w to widen." in output

    def test_empty_context_no_output(self) -> None:
        """Empty question_context produces no output."""
        from specify_cli.widen.interview_helpers import render_widen_hint_if_present

        console, buf = self._make_console()
        render_widen_hint_if_present("", console)
        assert buf.getvalue().strip() == ""
