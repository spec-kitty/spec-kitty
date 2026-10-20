"""``upgrade --dry-run --verbose`` outside a git repository must not crash (#6539).

The verbose preview calls ``detect()`` / ``can_apply()`` directly. A migration that
resolves the canonical repo root raises ``NotInsideRepositoryError`` there, so the
preview reports a migration that declares ``requires_git_repository`` as not
applicable instead, without calling ``detect()``.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()


def _legacy_project(root: Path) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text("spec_kitty:\n  version: 3.1.0\n  schema_version: 3\n", encoding="utf-8")
    return root


def test_dry_run_verbose_outside_git_reports_repository_bound_migration_as_skipped(tmp_path: Path) -> None:
    project = _legacy_project(tmp_path)

    with contextlib.chdir(project):
        result = _runner.invoke(_test_app, ["--project", "--dry-run", "--verbose"], catch_exceptions=False)

    output = _ANSI_RE.sub("", result.output)
    assert result.exit_code == 0, output
    assert "3.2.0rc35_unified_bundle: skipped" in output
    assert "not inside a git repository" in output
