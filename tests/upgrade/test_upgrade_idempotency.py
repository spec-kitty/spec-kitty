"""NFR-001 idempotency for the normalized no-migrations branch (WP04, T023c).

Mission: upgrade-command-hardening-01M0N5N4.

Scope note (per the WP04 task spec): the REAL read-only-surface double-run
idempotency test (a project with pre-existing generated files, run through
the actual migration/writer seam twice) belongs to WP01's own fixture
(``tests/upgrade/test_generated_writer.py`` / the migration test suites) —
re-deriving that heavier fixture here would be redundant. This file's scope
is narrower and specific to WP04's own change: the CLI *entry* harness stubs
migrations out entirely on the no-migrations path (there is nothing for a
migration to "apply" a second time), so what WP04 owns proving is that the
normalized ``UpgradeOutcome`` tail (T017) is a clean, exit-0, no-op *repeat*
across two consecutive real invocations — not that migrations themselves are
idempotent (that would be a vacuous green here; see the module note above).
"""

from __future__ import annotations

import json
import contextlib
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)


def _init_project(root: Path, *, version: str = "1.0.0a1") -> None:
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _run_upgrade(args: list[str], cwd: Path):
    with contextlib.chdir(cwd):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _last_json_line(output: str) -> dict[str, object]:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_no_migrations_no_op_repeat_is_clean_exit_zero(tmp_path: Path) -> None:
    """NFR-001: running `upgrade` twice over an already-current, no-migrations
    project is a clean no-op both times — exit 0, zero migrations applied,
    zero errors, on both invocations."""
    project = tmp_path / "proj"
    _init_project(project)

    first = _run_upgrade(
        ["--target", "1.0.0a1", "--yes", "--no-worktrees", "--json"],
        cwd=project,
    )
    assert first.exit_code == 0, first.output
    first_payload = _last_json_line(first.output)
    assert first_payload["status"] == "up_to_date"
    assert first_payload["success"] is True

    second = _run_upgrade(
        ["--target", "1.0.0a1", "--yes", "--no-worktrees", "--json"],
        cwd=project,
    )
    assert second.exit_code == 0, second.output
    second_payload = _last_json_line(second.output)
    assert second_payload["status"] == "up_to_date"
    assert second_payload["success"] is True
    assert second_payload["errors"] == []


def test_no_migrations_no_op_repeat_produces_no_further_commit(tmp_path: Path) -> None:
    """The second no-op run has nothing new to commit: `auto_committed` must
    be False on the second invocation (the first run already settled the
    repository — the churn from run 1 is not re-committed on run 2)."""
    project = tmp_path / "proj"
    _init_project(project)

    first = _run_upgrade(
        ["--target", "1.0.0a1", "--yes", "--no-worktrees", "--json"],
        cwd=project,
    )
    assert first.exit_code == 0, first.output

    second = _run_upgrade(
        ["--target", "1.0.0a1", "--yes", "--no-worktrees", "--json"],
        cwd=project,
    )
    assert second.exit_code == 0, second.output
    second_payload = _last_json_line(second.output)
    assert second_payload["auto_committed"] is False
    assert second_payload["auto_commit_paths"] == []

    # The working tree is clean after both runs — no leftover churn.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == ""
