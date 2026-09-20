"""CLI tests for 'spec-kitty charter resynthesize' (T032).

Happy path:
  - Default generated adapter writes bounded change; output reports regenerated artifacts.
  - --list-topics shows the valid selector surface.
  - --json returns valid JSON with result="success" or "noop".

Error paths:
  - Unresolved selector renders rich panel + exits 2 + writes nothing.
  - Missing interview answers → exit 1.
  - No prior manifest → exit 1.
  - --help works.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_cwd_from_worktree_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4785 Finding 3 / WP04 reconciliation: ``resynthesize.py`` now fails
    closed via the WP02 write-root guard (``resolve_charter_write_root``),
    probed against the REAL process cwd -- deliberately NOT patchable
    through this suite's ``find_repo_root`` mocks, since the guard exists
    precisely to catch cwd/``find_repo_root`` divergence. Without isolating
    cwd here, every test below would spuriously trip the guard whenever the
    test process happens to run from inside a real linked git worktree
    (e.g. a spec-kitty lane worktree) -- unrelated to anything this suite
    exercises. ``tmp_path`` is a plain (non-git) directory, so chdir'ing
    into it makes the guard's kernel ``git_topology`` probe degrade safely
    (not-a-repo -> not-a-linked-worktree, no raise).
    """
    monkeypatch.chdir(tmp_path)


def _plain_output(output: str) -> str:
    """Remove ANSI styling so help assertions are stable across terminals."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_interview_answers(repo_root: Path) -> None:
    """Write minimal interview answers YAML for CLI testing."""
    answers_path = repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    answers_path.write_text(
        """\
schema_version: '1'
mission: software-dev
profile: minimal
answers:
  mission_type: software_dev
  testing_philosophy: test-driven
  neutrality_posture: balanced
  risk_appetite: moderate
  language_scope: python
selected_paradigms: []
selected_directives:
  - DIRECTIVE_003
available_tools: []
""",
        encoding="utf-8",
    )


def _make_mock_result(
    is_noop: bool = False,
    matched_form: str = "kind_slug",
    matched_value: str = "tactic:how-we-apply-directive-003",
) -> MagicMock:
    """Create a mock ResynthesisResult."""
    mock_target = MagicMock()
    mock_target.kind = "tactic"
    mock_target.slug = "how-we-apply-directive-003"

    mock_resolved = MagicMock()
    mock_resolved.targets = [mock_target] if not is_noop else []
    mock_resolved.matched_form = matched_form
    mock_resolved.matched_value = matched_value

    mock_manifest = MagicMock()
    mock_manifest.run_id = "01KPE222PERF000000000000001"
    mock_manifest.artifacts = []

    mock_result = MagicMock()
    mock_result.is_noop = is_noop
    mock_result.resolved_topic = mock_resolved
    mock_result.manifest = mock_manifest
    mock_result.diagnostic = "EC-4 zero-match diagnostic" if is_noop else ""

    return mock_result


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


class TestResynthesizeHelp:
    def test_resynthesize_help(self) -> None:
        """--help works and shows --topic option."""
        result = runner.invoke(app, ["resynthesize", "--help"], terminal_width=120, color=False)
        assert result.exit_code == 0
        plain = _plain_output(result.output)
        assert "--topic" in plain
        assert "--list-topics" in plain
        assert "--adapter" in plain

    def test_synthesize_help(self) -> None:
        """synthesize --help works."""
        result = runner.invoke(app, ["synthesize", "--help"], terminal_width=120, color=False)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Happy path: resolved selector
# ---------------------------------------------------------------------------


class TestResynthesizeHappyPath:
    def test_resolved_selector_exits_0(self, tmp_path: Path) -> None:
        """Resolved topic exits 0 and reports regenerated artifacts."""
        _write_interview_answers(tmp_path)
        mock_result = _make_mock_result()

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        assert "how-we-apply-directive-003" in result.output or "Resynthesis" in result.output

    def test_resolved_selector_json_output(self, tmp_path: Path) -> None:
        """--json returns valid JSON with result='success'."""
        _write_interview_answers(tmp_path)
        mock_result = _make_mock_result()

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                    "--json",
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        data = json.loads(result.output)
        assert data["result"] == "success"
        assert "topic" in data
        assert "matched_form" in data
        assert "regenerated" in data

    def test_noop_result_exits_0(self, tmp_path: Path) -> None:
        """EC-4 noop result exits 0 with no-op message."""
        _write_interview_answers(tmp_path)
        mock_result = _make_mock_result(is_noop=True, matched_form="drg_urn")

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "paradigm:evidence-first",
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        assert "noop" in result.output.lower() or "No-op" in result.output

    def test_noop_json_output(self, tmp_path: Path) -> None:
        """EC-4 noop + --json → result='noop'."""
        _write_interview_answers(tmp_path)
        mock_result = _make_mock_result(is_noop=True, matched_form="drg_urn")

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "paradigm:evidence-first",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["result"] == "noop"
        assert data["targets_count"] == 0

    def test_list_topics_json_output(self, tmp_path: Path) -> None:
        """--list-topics returns the available selector sets."""
        _write_interview_answers(tmp_path)

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.charter._list_resynthesis_topics",
                return_value={
                    "project_artifacts": ["directive:PROJECT_001"],
                    "drg_urns": ["directive:DIRECTIVE_003"],
                    "interview_sections": ["testing_philosophy"],
                    "interview_section_aliases": ["testing-philosophy"],
                },
            ),
        ):
            result = runner.invoke(app, ["resynthesize", "--list-topics", "--json"])

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        data = json.loads(result.output)
        assert data["result"] == "success"
        assert data["topics"]["project_artifacts"] == ["directive:PROJECT_001"]

    # ---------------------------------------------------------------------------
    # Error paths
    # ---------------------------------------------------------------------------

    def test_reference_warnings_surfaced_on_console(self, tmp_path: Path) -> None:
        """#4121 (MAJOR 2): unresolved-reference warnings from the overlay
        re-emission print on the CLI, not only into ``logging`` output."""
        _write_interview_answers(tmp_path)
        mock_result = _make_mock_result()
        mock_result.reference_warnings = ("agent_profile:ops-responder references unresolved procedure:gone",)

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        plain = _plain_output(result.output)
        assert "agent_profile:ops-responder references unresolved procedure:gone" in plain

    def test_reference_warnings_in_json_envelope(self, tmp_path: Path) -> None:
        """#4121 (MAJOR 2): the --json envelope carries them in ``warnings``."""
        _write_interview_answers(tmp_path)
        mock_result = _make_mock_result()
        mock_result.reference_warnings = ("agent_profile:ops-responder references unresolved procedure:gone",)

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["result"] == "success"
        assert "agent_profile:ops-responder references unresolved procedure:gone" in data["warnings"]


class TestResynthesizeErrorPaths:
    def test_unresolved_selector_exits_2(self, tmp_path: Path) -> None:
        """Unresolved selector → exit code 2 (contracts/topic-selector.md §2.2)."""
        _write_interview_answers(tmp_path)

        from charter.activation.synthesizer.errors import TopicSelectorUnresolvedError

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                side_effect=TopicSelectorUnresolvedError(
                    raw="bogus:nonexistent",
                    candidates=("tactic:how-we-apply-directive-003 (distance=5)",),
                    attempted_forms=("kind_slug", "drg_urn"),
                ),
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "bogus:nonexistent",
                ],
            )

        # Exit code 2 is the contract (contracts/topic-selector.md §2.2)
        assert result.exit_code == 2, f"Expected exit 2 for unresolved topic, got {result.exit_code}: {result.output}"

    def test_unresolved_selector_renders_panel_title(self, tmp_path: Path) -> None:
        """Unresolved selector renders 'Cannot resolve --topic' panel."""
        _write_interview_answers(tmp_path)

        from charter.activation.synthesizer.errors import TopicSelectorUnresolvedError

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                side_effect=TopicSelectorUnresolvedError(
                    raw="bogus:nonexistent",
                    candidates=(),
                    attempted_forms=("kind_slug", "drg_urn"),
                ),
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "bogus:nonexistent",
                    "--adapter",
                    "fixture",
                ],
            )

        assert result.exit_code == 2
        # Panel title should contain the unresolved topic string
        combined = result.output
        assert "bogus:nonexistent" in combined

    def test_unresolved_selector_writes_nothing(self, tmp_path: Path) -> None:
        """Unresolved selector: no files written to .kittify/."""
        _write_interview_answers(tmp_path)

        from charter.activation.synthesizer.errors import TopicSelectorUnresolvedError

        doctrine_dir = tmp_path / ".kittify" / "doctrine"

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                side_effect=TopicSelectorUnresolvedError(
                    raw="bogus:nonexistent",
                    candidates=(),
                    attempted_forms=("kind_slug", "drg_urn"),
                ),
            ),
        ):
            runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "bogus:nonexistent",
                    "--adapter",
                    "fixture",
                ],
            )

        # doctrine dir should not have been created by the error path
        assert not doctrine_dir.exists(), "doctrine/ should not be created on unresolved selector"

    def test_missing_interview_answers_exits_1(self, tmp_path: Path) -> None:
        """No interview answers → exit 1."""
        with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                    "--adapter",
                    "fixture",
                ],
            )
        assert result.exit_code == 1, f"Expected exit 1: {result.output}"

    def test_no_prior_manifest_exits_1(self, tmp_path: Path) -> None:
        """No prior manifest → FileNotFoundError → exit 1."""
        _write_interview_answers(tmp_path)

        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "charter.activation.synthesizer.resynthesize_pipeline.run",
                side_effect=FileNotFoundError("No prior synthesis manifest"),
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                    "--adapter",
                    "fixture",
                ],
            )

        assert result.exit_code == 1, f"Expected exit 1: {result.output}"

    def test_unknown_adapter_exits_1(self, tmp_path: Path) -> None:
        """--adapter production (removed) → exit 1; spec-kitty never calls LLMs itself."""
        _write_interview_answers(tmp_path)

        with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path):
            result = runner.invoke(
                app,
                [
                    "resynthesize",
                    "--topic",
                    "tactic:how-we-apply-directive-003",
                    "--adapter",
                    "production",
                ],
            )

        assert result.exit_code == 1, f"Expected exit 1: {result.output}"
