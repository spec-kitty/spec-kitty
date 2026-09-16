"""Tests for the ``spec-kitty agent tests stale-check`` CLI subcommand.

Covers: FR-004 (CLI calls run_check, not subprocess), T007 (--json output).
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.cli.commands.agent.tests import app as tests_app
from specify_cli.post_merge.stale_assertions import (
    StaleAssertionFinding,
    StaleAssertionReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


def _setup_repo(tmp_path: Path) -> Path:
    _git(["init"], cwd=tmp_path)
    _git(["config", "user.email", "test@example.com"], cwd=tmp_path)
    _git(["config", "user.name", "Test User"], cwd=tmp_path)
    return tmp_path


def _commit(repo: Path, message: str = "commit") -> str:
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-m", message, "--allow-empty"], cwd=repo)
    return _git(["rev-parse", "HEAD"], cwd=repo)


def _make_dummy_report(repo_root: Path) -> StaleAssertionReport:
    return StaleAssertionReport(
        base_ref="base",
        head_ref="HEAD",
        repo_root=repo_root,
        findings=[
            StaleAssertionFinding(
                test_file=repo_root / "tests" / "test_foo.py",
                test_line=10,
                source_file=repo_root / "src" / "foo.py",
                source_line=5,
                changed_symbol="old_func",
                confidence="high",
                hint="Assertion references 'old_func' which was renamed in foo.py:5",
            )
        ],
        elapsed_seconds=0.5,
        files_scanned=3,
        findings_per_100_loc=2.5,
    )


runner = CliRunner()


# ---------------------------------------------------------------------------
# FR-004: CLI subcommand invokes run_check (not subprocess)
# ---------------------------------------------------------------------------

class TestCliSubcommandInvokesLibrary:
    """FR-004: the CLI must call run_check() directly, not spawn a subprocess."""

    def test_cli_subcommand_invokes_library(self, tmp_path: Path) -> None:
        """The stale-check command calls run_check and renders its output.

        Note: when invoking tests_app (a single-command Typer) directly via
        CliRunner, typer flattens the group so we invoke without the command
        name.  The full path ``agent tests stale-check`` is tested via
        agent_app in TestAgentRegistration.
        """
        dummy_report = _make_dummy_report(tmp_path)

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=dummy_report,
        ) as mock_run_check:
            result = runner.invoke(
                tests_app,
                ["--base", "HEAD~1", "--repo", str(tmp_path)],
            )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}:\n{result.output}"
        )
        mock_run_check.assert_called_once()
        call_kwargs = mock_run_check.call_args
        assert call_kwargs is not None

    def test_cli_does_not_use_subprocess_for_analysis(self, tmp_path: Path) -> None:
        """FR-004: the CLI must not spawn the CLI subcommand as a subprocess."""
        dummy_report = _make_dummy_report(tmp_path)

        # Track subprocess.run calls. We allow git subprocess calls,
        # but NOT calls that include "stale-check" in their args.
        subprocess_calls: list[list[str]] = []
        original_run = subprocess.run

        def spy_run(args, **kwargs):  # type: ignore[no-untyped-def]
            if isinstance(args, (list, tuple)):
                subprocess_calls.append(list(args))
            return original_run(args, **kwargs)

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=dummy_report,
        ):
            with mock.patch("subprocess.run", side_effect=spy_run):
                runner.invoke(
                    tests_app,
                    ["--base", "HEAD~1", "--repo", str(tmp_path)],
                )

        # Assert no call contained "stale-check" (that would be self-invocation).
        stale_check_calls = [
            c for c in subprocess_calls if "stale-check" in " ".join(c)
        ]
        assert stale_check_calls == [], (
            f"CLI must not invoke stale-check as a subprocess: {stale_check_calls}"
        )


# ---------------------------------------------------------------------------
# T007: --json output mode
# ---------------------------------------------------------------------------

class TestJsonOutputMode:
    """T007: --json flag causes JSON output that parses cleanly."""

    def test_json_output_is_valid_json(self, tmp_path: Path) -> None:
        dummy_report = _make_dummy_report(tmp_path)

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=dummy_report,
        ):
            result = runner.invoke(
                tests_app,
                ["--base", "HEAD~1", "--repo", str(tmp_path), "--json"],
            )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}:\n{result.output}"
        )

        # Output should parse as JSON.
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_json_output_has_required_fields(self, tmp_path: Path) -> None:
        dummy_report = _make_dummy_report(tmp_path)

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=dummy_report,
        ):
            result = runner.invoke(
                tests_app,
                ["--base", "HEAD~1", "--repo", str(tmp_path), "--json"],
            )

        parsed = json.loads(result.output)

        required_fields = {
            "base_ref", "head_ref", "repo_root", "findings",
            "elapsed_seconds", "files_scanned", "findings_per_100_loc",
        }
        for field_name in required_fields:
            assert field_name in parsed, (
                f"JSON output missing required field: {field_name}"
            )

    def test_json_output_findings_have_required_fields(self, tmp_path: Path) -> None:
        dummy_report = _make_dummy_report(tmp_path)

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=dummy_report,
        ):
            result = runner.invoke(
                tests_app,
                ["--base", "HEAD~1", "--repo", str(tmp_path), "--json"],
            )

        parsed = json.loads(result.output)
        assert len(parsed["findings"]) == 1

        finding = parsed["findings"][0]
        required_finding_fields = {
            "test_file", "test_line", "source_file", "source_line",
            "changed_symbol", "confidence", "hint",
        }
        for field_name in required_finding_fields:
            assert field_name in finding, (
                f"Finding JSON missing required field: {field_name}"
            )

    def test_json_output_round_trips(self, tmp_path: Path) -> None:
        """The JSON output must round-trip through json.loads."""
        dummy_report = _make_dummy_report(tmp_path)

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=dummy_report,
        ):
            result = runner.invoke(
                tests_app,
                ["--base", "HEAD~1", "--repo", str(tmp_path), "--json"],
            )

        # Should parse and not raise.
        parsed = json.loads(result.output)
        assert parsed["base_ref"] == "base"
        assert parsed["head_ref"] == "HEAD"
        assert parsed["files_scanned"] == 3
        assert parsed["elapsed_seconds"] == 0.5
        assert parsed["findings_per_100_loc"] == 2.5


# ---------------------------------------------------------------------------
# #3957: human output surfaces info-grade message-content findings
# ---------------------------------------------------------------------------

class TestInfoGradeHumanOutput:
    """#3957: info-grade (message-content) findings must not be dropped from
    the human-readable output — they are the assertions the analyzer
    deliberately skips, so they are surfaced under their own title."""

    def test_info_findings_rendered_in_human_output(self, tmp_path: Path) -> None:
        report = StaleAssertionReport(
            base_ref="base",
            head_ref="HEAD",
            repo_root=tmp_path,
            findings=[
                StaleAssertionFinding(
                    test_file=tmp_path / "tests" / "test_msg.py",
                    test_line=21,
                    source_file=tmp_path / "src" / "msg.py",
                    source_line=3,
                    changed_symbol="old error message",
                    confidence="info",
                    hint="message-content hint marker",
                    label="message-content-check",
                ),
            ],
            elapsed_seconds=0.5,
            files_scanned=3,
            findings_per_100_loc=2.5,
        )

        with mock.patch(
            "specify_cli.cli.commands.agent.tests.run_check",
            return_value=report,
        ):
            result = runner.invoke(
                tests_app,
                ["--base", "HEAD~1", "--repo", str(tmp_path)],
            )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}:\n{result.output}"
        )
        assert "INFO" in result.output, (
            "Expected an INFO block for info-grade findings in human output"
        )
        assert "review manually" in result.output
        assert "old error message" in result.output
        assert "test_msg.py" in result.output


# ---------------------------------------------------------------------------
# Registration: agent/__init__.py registers the tests subapp
# ---------------------------------------------------------------------------

class TestAgentRegistration:
    """Verify agent/__init__.py registers tests subapp correctly."""

    def test_agent_app_has_tests_subcommand(self) -> None:
        """The agent app must have a 'tests' subgroup."""
        # Check via CLI runner — stale-check --help should be reachable.
        result = runner.invoke(agent_app, ["tests", "--help"])
        assert result.exit_code == 0, (
            f"'agent tests --help' failed with exit code {result.exit_code}:\n"
            f"{result.output}"
        )
        assert "stale-check" in result.output, (
            "Expected 'stale-check' in agent tests help output"
        )

    def test_stale_check_help_reachable_from_agent(self) -> None:
        """spec-kitty agent tests stale-check --help must return help text."""
        import re
        result = runner.invoke(agent_app, ["tests", "stale-check", "--help"])
        assert result.exit_code == 0, (
            f"Exit code {result.exit_code}:\n{result.output}"
        )
        # Strip ANSI escape codes before checking option names — Rich may
        # wrap individual characters in colour codes on some terminals.
        plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "--base" in plain
        assert "--json" in plain
