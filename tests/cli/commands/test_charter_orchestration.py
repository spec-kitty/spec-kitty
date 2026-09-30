"""Bucket A (orchestration) coverage for ``specify_cli.cli.commands.charter``.

These tests exercise the CLI surface via ``typer.testing.CliRunner``.  They
assert on exit codes and stdout substrings.  Each test uses ``tmp_path`` to
build a minimal project tree so ``find_repo_root`` succeeds, and patches only
the heavy external collaborators (charter library internals, saas client)
that cannot run without live services.

Tactic: function-over-form-testing (src/charter/offering/tactics/built-in/testing/).
Structure: AAA (Arrange / Act / Assert).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared project-tree factory
# ---------------------------------------------------------------------------

_MINIMAL_CHARTER = """\
# Test Charter

> Created: 2026-01-01
> Version: 1.0.0

## Purpose

Charter for test project.
"""


def _make_project(tmp_path: Path, *, with_charter: bool = True, with_git: bool = True) -> Path:
    """Return a minimal project root that find_repo_root() accepts.

    Creates .kittify/ (required by locate_project_root) and optionally an
    initialized git repo so git-using code paths don't hard-fail.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)

    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)

    if with_charter:
        (charter_dir / "charter.md").write_text(_MINIMAL_CHARTER, encoding="utf-8")

    if with_git:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

    return tmp_path


# ---------------------------------------------------------------------------
# T023a — ``charter interview --defaults`` exits 0 and writes interview file
# ---------------------------------------------------------------------------


def test_interview_invalid_profile_exits_nonzero(tmp_path: Path) -> None:
    """Arrange: project; Act: invoke interview with invalid --profile;
    Assert: exit code != 0 and error message in output."""
    project = _make_project(tmp_path)

    fake_interview_data = MagicMock()
    fake_interview_data.answers = {}
    fake_interview_data.selected_paradigms = []
    fake_interview_data.selected_directives = []
    fake_interview_data.available_tools = []

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project),
        patch("specify_cli.cli.commands.charter.default_interview", return_value=fake_interview_data),
    ):
        result = runner.invoke(app, ["interview", "--defaults", "--profile", "bogus"])

    assert result.exit_code != 0
    assert "Error" in result.output or "profile" in result.output.lower()


# ---------------------------------------------------------------------------
# T023b — ``charter sync`` exits 0 when charter exists and is synced
# ---------------------------------------------------------------------------


def test_sync_exits_zero_when_charter_synced(tmp_path: Path) -> None:
    """Arrange: project with charter.md; Act: sync; Assert: exit 0."""
    project = _make_project(tmp_path)

    fake_result = MagicMock()
    fake_result.synced = True
    fake_result.stale_before = True
    fake_result.files_written = ["governance.yaml", "directives.yaml"]
    fake_result.extraction_mode = "llm"
    fake_result.error = None

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project),
        patch("charter.activation.sync.sync", return_value=fake_result),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0, result.output
    assert "synced" in result.output.lower() or "Charter" in result.output


def test_sync_exits_nonzero_when_charter_missing(tmp_path: Path) -> None:
    """Arrange: project without charter.md; Act: sync; Assert: exit != 0 with error."""
    project = _make_project(tmp_path, with_charter=False)

    with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code != 0
    assert "Error" in result.output or "not found" in result.output.lower()


def test_sync_noop_when_already_synced(tmp_path: Path) -> None:
    """Arrange: project with synced charter; Act: sync; Assert: exit 0, noop message."""
    project = _make_project(tmp_path)

    fake_result = MagicMock()
    fake_result.synced = False
    fake_result.stale_before = False
    fake_result.files_written = []
    fake_result.extraction_mode = "llm"
    fake_result.error = None

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project),
        patch("charter.activation.sync.sync", return_value=fake_result),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0, result.output
    assert "No-op:" in result.output


# ---------------------------------------------------------------------------
# T023c — ``charter status`` exits 0 and includes "Charter" in output
# ---------------------------------------------------------------------------


def test_status_json_output_contains_result_key(tmp_path: Path) -> None:
    """Arrange: project; Act: status --json; Assert: exit 0 and JSON with result key."""
    project = _make_project(tmp_path)

    fake_synthesis: dict[str, Any] = {
        "generation_state": "not_started",
        "generated_inputs": {"path": ".kittify/charter/generated", "exists": False, "counts": {"directive": 0, "tactic": 0, "styleguide": 0}, "total": 0},
        "manifest": {
            "state": "missing",
            "path": ".kittify/charter/synthesis-manifest.yaml",
            "exists": False,
            "artifact_count": 0,
            "live_artifact_count": 0,
            "live_provenance_count": 0,
            "run_id": None,
            "created_at": None,
            "adapter_id": None,
            "adapter_version": None,
            "missing_provenance_paths": [],
            "error": None,
        },
        "provenance": {
            "path": ".kittify/charter/provenance",
            "count": 0,
            "parsed_count": 0,
            "manifest_artifact_count": 0,
            "missing_for_manifest_count": 0,
            "missing_for_manifest": [],
            "corpus_snapshot_ids": [],
            "adapters": [],
            "warnings": [],
            "entries": [],
        },
        "evidence": {"warnings": [], "code": None, "configured_urls": [], "configured_url_count": 0, "corpus_snapshot_id": None, "corpus_entry_count": 0},
    }

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project),
        patch(
            "specify_cli.cli.commands.charter._collect_charter_sync_status",
            return_value={
                "available": True,
                "charter_path": ".kittify/charter/charter.md",
                "status": "synced",
                "current_hash": "abc123",
                "stored_hash": "abc123",
                "last_sync": None,
                "library_docs": 0,
                "files": [],
            },
        ),
        patch("specify_cli.cli.commands.charter._collect_synthesis_status", return_value=fake_synthesis),
    ):
        result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["result"] == "success"


# ---------------------------------------------------------------------------
# T023d — ``charter context`` exits 0 and emits action context text
# ---------------------------------------------------------------------------
