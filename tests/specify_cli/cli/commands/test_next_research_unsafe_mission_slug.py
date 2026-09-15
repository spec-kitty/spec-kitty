"""#2878: traversal-shaped ``--mission`` slugs exit cleanly on next/research.

``assert_safe_path_segment`` (core/paths.py) raises ``UnsafePathSegmentError`` for
traversal-shaped slugs (``../x``, ``a/b``, leading-dot, …). ``merge`` already
converts that into its canonical typed-error surface (``_resolve_slug_or_exit``
exemplar: diagnostic line + exit 2); ``next`` and ``research`` had no handler,
so the raw traceback the issue reports escaped to the operator.

These tests lock the fixed behaviour on both commands: non-zero exit, the
canonical "single safe path segment" diagnostic, no traceback — plus the
structured JSON envelope for ``next --json`` (a machine contract must never
receive a Python stack trace). Counterexamples prove unrelated ``ValueError``
instances are not mislabeled as unsafe slugs.
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _invoke_next(tmp_path: pathlib.Path, args: list[str]):
    """Invoke ``next`` with project-root + charter-preflight patched out.

    The mission-resolution seam under test (``_resolve_mission_slug`` →
    placement seam) raises before any mission state is read, so a bare
    directory fixture is enough; the two patched boundaries are the only
    earlier gates that would otherwise exit first outside a provisioned repo.
    """
    from specify_cli.cli.commands import next_cmd

    app = typer.Typer()
    app.command()(next_cmd.next_step)
    with (
        patch.object(next_cmd, "locate_project_root", return_value=tmp_path),
        patch.object(next_cmd, "_run_charter_preflight_for_next", lambda *a, **k: None),
    ):
        return runner.invoke(app, args)


def _invoke_research(tmp_path: pathlib.Path, mission: str):
    """Invoke ``research`` with repo/project-root resolution patched out."""
    from specify_cli.cli.commands.research import research

    app = typer.Typer()
    app.command()(research)
    with (
        patch("specify_cli.cli.commands.research.find_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.research.get_project_root_or_exit",
            return_value=tmp_path,
        ),
    ):
        return runner.invoke(app, ["--mission", mission])


def test_next_does_not_relabel_unrelated_value_error(tmp_path: pathlib.Path) -> None:
    from specify_cli.cli.commands import next_cmd

    with patch.object(
        next_cmd,
        "_resolve_mission_slug",
        side_effect=ValueError("No resolved location for surface 'spec'"),
    ):
        result = _invoke_next(tmp_path, ["--agent", "claude", "--mission", "valid-slug"])

    assert result.exit_code == 2
    assert "No resolved location for surface 'spec'" in result.output
    assert "single safe path segment" not in result.output
    assert "Traceback" not in result.output


def test_next_json_preserves_unrelated_resolution_error_contract(tmp_path: pathlib.Path) -> None:
    from specify_cli.cli.commands import next_cmd

    message = "No resolved location for surface 'spec'"
    with patch.object(next_cmd, "_resolve_mission_slug", side_effect=ValueError(message)):
        result = _invoke_next(
            tmp_path,
            ["--agent", "claude", "--mission", "valid-slug", "--json"],
        )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "error"
    assert payload["error_code"] == "INTERNAL_RESOLUTION_ERROR"
    assert payload["error"] == message
    assert "Traceback" not in result.stdout


def test_merge_does_not_relabel_unrelated_value_error(tmp_path: pathlib.Path) -> None:
    from specify_cli.cli.commands import merge

    message = "No resolved location for surface 'spec'"
    with (
        patch.object(merge, "_resolve_mission_slug", side_effect=ValueError(message)),
        pytest.raises(ValueError, match="No resolved location"),
    ):
        merge._resolve_slug_or_exit(tmp_path, "valid-slug")


def test_research_does_not_relabel_unrelated_value_error(tmp_path: pathlib.Path) -> None:
    from specify_cli.cli.commands import research as research_module

    seam = patch.object(research_module, "placement_seam")
    with seam as mock_placement_seam:
        mock_placement_seam.return_value.read_dir.side_effect = ValueError("No resolved location for surface 'research'")
        result = _invoke_research(tmp_path, "valid-slug")

    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)
    assert "No resolved location for surface 'research'" in str(result.exception)
    assert "single safe path segment" not in result.output


class TestNextUnsafeMissionSlug:
    def test_traversal_slug_exits_2_with_clean_diagnostic(self, tmp_path: pathlib.Path) -> None:
        result = _invoke_next(tmp_path, ["--agent", "claude", "--mission", "../traversal"])
        assert result.exit_code == 2, f"Expected exit 2 for traversal slug, got {result.exit_code}\nOutput:\n{result.output}"
        assert "single safe path segment" in result.output, f"Expected canonical diagnostic in output, got:\n{result.output}"
        assert "Traceback" not in result.output, f"Raw traceback escaped for traversal slug:\n{result.output}"
        assert not isinstance(result.exception, ValueError)

    def test_separator_slug_exits_2_with_clean_diagnostic(self, tmp_path: pathlib.Path) -> None:
        result = _invoke_next(tmp_path, ["--agent", "claude", "--mission", "a/b"])
        assert result.exit_code == 2, result.output
        assert "single safe path segment" in result.output
        assert "Traceback" not in result.output

    def test_json_mode_emits_structured_error_envelope(self, tmp_path: pathlib.Path) -> None:
        result = _invoke_next(tmp_path, ["--agent", "claude", "--mission", "../traversal", "--json"])
        assert result.exit_code == 2, result.output
        payload = json.loads(result.stdout)
        assert payload["result"] == "error"
        assert payload["error_code"] == "UNSAFE_MISSION_SLUG"
        assert "single safe path segment" in payload["error"]
        assert "Traceback" not in result.stdout


class TestResearchUnsafeMissionSlug:
    def test_traversal_slug_exits_2_with_clean_diagnostic(self, tmp_path: pathlib.Path) -> None:
        result = _invoke_research(tmp_path, "../traversal")
        assert result.exit_code == 2, f"Expected exit 2 for traversal slug, got {result.exit_code}\nOutput:\n{result.output}"
        assert "single safe path segment" in result.output, f"Expected canonical diagnostic in output, got:\n{result.output}"
        assert "Traceback" not in result.output, f"Raw traceback escaped for traversal slug:\n{result.output}"
        assert not isinstance(result.exception, ValueError)

    def test_separator_slug_exits_2_with_clean_diagnostic(self, tmp_path: pathlib.Path) -> None:
        result = _invoke_research(tmp_path, "a/b")
        assert result.exit_code == 2, result.output
        assert "single safe path segment" in result.output
        assert "Traceback" not in result.output
