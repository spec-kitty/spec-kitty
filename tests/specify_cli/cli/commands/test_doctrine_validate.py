"""CLI tests for ``spec-kitty charter validate`` (FR-017, WP09 T049).

Covers the three operator paths:

1. validate a single artifact YAML file,
2. validate a directory tree (recurses into per-kind subdirectories),
3. exit non-zero with per-file diagnostics when any file fails.

Reuses the schema registry from ``pack_validator`` so a regression there
(e.g. dropping ``styleguides`` from the registry) breaks this test too.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_valid_styleguide(path: Path, sid: str = "ok-style") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""
            schema_version: "1.0"
            id: {sid}
            title: OK Style
            scope: code
            principles:
              - keep it simple
            applies_to_languages: []
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _write_invalid_styleguide(path: Path) -> None:
    """Missing required ``principles`` field — schema MUST reject."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            schema_version: "1.0"
            id: broken-style
            title: Broken
            scope: code
            principles: []
            """
        ).lstrip(),
        encoding="utf-8",
    )


def test_validate_single_file_passes(tmp_path: Path) -> None:
    target = tmp_path / "good.styleguide.yaml"
    _write_valid_styleguide(target)

    result = runner.invoke(charter_app, ["validate", str(target)], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    assert "OK" in result.stdout


def test_validate_single_file_reports_schema_failure(tmp_path: Path) -> None:
    target = tmp_path / "bad.styleguide.yaml"
    _write_invalid_styleguide(target)

    result = runner.invoke(charter_app, ["validate", str(target)], catch_exceptions=False)

    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "principles" in result.stdout  # surfaces the schema error


def test_validate_directory_walks_per_kind_subdirs(tmp_path: Path) -> None:
    """A doctrine tree with multiple per-kind directories validates as a unit."""
    _write_valid_styleguide(tmp_path / "styleguides" / "one.styleguide.yaml", "one")
    _write_valid_styleguide(tmp_path / "styleguides" / "two.styleguide.yaml", "two")

    result = runner.invoke(charter_app, ["validate", str(tmp_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    # Rich wraps long absolute paths across newlines, so we assert on the
    # summary line and the OK-marker count rather than the path text itself.
    flat = " ".join(result.stdout.split())
    assert "2 artifact(s) passed validation" in flat
    assert result.stdout.count("OK") >= 2


def test_validate_directory_returns_nonzero_on_any_failure(tmp_path: Path) -> None:
    """One bad file fails the whole tree validation."""
    _write_valid_styleguide(tmp_path / "styleguides" / "good.styleguide.yaml", "good")
    _write_invalid_styleguide(tmp_path / "styleguides" / "bad.styleguide.yaml")

    result = runner.invoke(charter_app, ["validate", str(tmp_path)], catch_exceptions=False)

    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "1 of 2 artifact(s) failed" in result.stdout


def test_validate_rejects_unknown_suffix(tmp_path: Path) -> None:
    """A YAML file that does not match a canonical kind suffix is rejected."""
    target = tmp_path / "random.yaml"
    target.write_text("hello: world\n", encoding="utf-8")

    result = runner.invoke(charter_app, ["validate", str(target)], catch_exceptions=False)

    assert result.exit_code == 1
    flat = " ".join(result.stdout.split())
    assert "unrecognised artifact filename suffix" in flat


def test_validate_missing_path_returns_2(tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist.yaml"

    result = runner.invoke(charter_app, ["validate", str(target)], catch_exceptions=False)

    assert result.exit_code == 2
    assert "Path not found" in result.stdout


def test_validate_empty_directory_exits_0_with_warning(tmp_path: Path) -> None:
    """A directory with no doctrine artifacts is benign — exit 0 with a note."""
    result = runner.invoke(charter_app, ["validate", str(tmp_path)], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    assert "No doctrine artifact files found" in result.stdout
