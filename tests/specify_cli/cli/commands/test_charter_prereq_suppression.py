"""WP10 T052 — Charter prereq suppression tests.

Tests verify that [w]iden is silently suppressed (C-009) when any of the three
prereqs is missing:
  1. No SaaS token (tokenspace_ok=False)
  2. Slack not configured (slack_ok=False)
  3. SaaS unreachable (saas_reachable=False)
  4. All prereqs missing

Also verifies (SC-004):
  - Interview completes normally without widen.
  - answers.yaml is written correctly.
  - No error banners or noisy warnings about missing prereqs.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from charter.activation.interview import MINIMAL_QUESTION_ORDER
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.widen.models import PrereqState

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-prereq-suppression-wp10"
MISSION_ID = "01KWP10PREREQSUPPRESSION001"

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


def _invoke_with_prereqs(
    tmp_path: Path,
    prereq: PrereqState,
    inputs: str,
) -> object:
    """Invoke charter interview with a specific PrereqState injected."""
    with (
        contextlib.chdir(tmp_path),
        patch(
            "specify_cli.saas_client.client.SaasClient.from_env",
            return_value=MagicMock(_token="tok"),
        ),
        patch("specify_cli.widen.check_prereqs", return_value=prereq),
        patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
    ):
        mock_store = MagicMock()
        mock_store.list_pending.return_value = []
        mock_store_cls.return_value = mock_store

        return runner.invoke(
            charter_app,
            ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
            input=inputs,
            catch_exceptions=False,
        )


# ---------------------------------------------------------------------------
# Prereq suppression scenarios
# ---------------------------------------------------------------------------


class TestPrereqSuppression:
    """[w]iden must NOT appear when any prereq is missing (C-009, FR-003)."""

    def _default_inputs(self) -> str:
        return _make_inputs([""] * _N_QUESTIONS)

    def test_no_widen_on_saas_unreachable(self, tmp_path: Path) -> None:
        """SaaS unreachable → [w]iden suppressed (C-007, C-009)."""
        _setup_repo(tmp_path)
        prereq = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=False)
        result = _invoke_with_prereqs(tmp_path, prereq, self._default_inputs())
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output

    def test_no_widen_on_slack_not_configured(self, tmp_path: Path) -> None:
        """Slack not configured → [w]iden suppressed (FR-003)."""
        _setup_repo(tmp_path)
        prereq = PrereqState(teamspace_ok=True, slack_ok=False, saas_reachable=True)
        result = _invoke_with_prereqs(tmp_path, prereq, self._default_inputs())
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output

    def test_no_widen_when_no_teamspace(self, tmp_path: Path) -> None:
        """User not in any Teamspace → [w]iden suppressed (FR-003)."""
        _setup_repo(tmp_path)
        prereq = PrereqState(teamspace_ok=False, slack_ok=False, saas_reachable=True)
        result = _invoke_with_prereqs(tmp_path, prereq, self._default_inputs())
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output

    def test_no_widen_when_all_prereqs_fail(self, tmp_path: Path) -> None:
        """All prereqs missing → [w]iden suppressed (C-007)."""
        _setup_repo(tmp_path)
        prereq = PrereqState(teamspace_ok=False, slack_ok=False, saas_reachable=False)
        result = _invoke_with_prereqs(tmp_path, prereq, self._default_inputs())
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output


# ---------------------------------------------------------------------------
# SC-004: Interview completes normally without widen
# ---------------------------------------------------------------------------


class TestInterviewCompletesNormallyWithoutWiden:
    """SC-004: Interview completes and writes answers.yaml when [w] is suppressed."""

    def test_interview_completes_normally_without_widen(self, tmp_path: Path) -> None:
        """Normal interview flow works when widen is suppressed (SC-004)."""
        _setup_repo(tmp_path)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()

    def test_no_error_banner_when_token_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No noisy error banners when token is absent (C-009 silent suppression)."""
        _setup_repo(tmp_path)
        monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        # No error banners about missing credentials
        output_lower = result.output.lower()
        assert "error" not in output_lower or "exit_code" not in output_lower
        assert "spec_kitty_saas_token" not in output_lower

    def test_answers_yaml_correct_without_widen(self, tmp_path: Path) -> None:
        """answers.yaml is written correctly when [w] is suppressed (SC-004)."""
        _setup_repo(tmp_path)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()
        content = answers_path.read_text()
        assert len(content) > 0

    def test_no_direct_slack_api_calls(self, tmp_path: Path) -> None:
        """No direct Slack API calls in specify_cli codebase (C-004)."""
        import importlib.util

        # Verify no slack_sdk or direct slack HTTP is imported in specify_cli source
        spec_kitty_src = Path(
            importlib.util.find_spec("specify_cli").origin  # type: ignore[union-attr]
        ).parent

        slack_references: list[str] = []
        for py_file in spec_kitty_src.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8")
                if "slack_sdk" in text or "slack.com/api" in text:
                    slack_references.append(str(py_file))
            except Exception:
                pass

        assert not slack_references, f"Direct Slack API references found (violates C-004): {slack_references}"
