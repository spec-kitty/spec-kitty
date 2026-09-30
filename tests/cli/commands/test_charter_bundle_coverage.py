"""Coverage tests for ``specify_cli.cli.commands.charter_bundle`` (A/B/C split).

Tactic: function-over-form-testing (src/charter/offering/tactics/built-in/testing/).
Structure: AAA (Arrange / Act / Assert).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter_bundle import (
    _classify_paths,
    _classify_gitignore,
    _enumerate_out_of_scope_files,
    _read_gitignore_lines,
    _render_human,
    app,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)


def _make_minimal_report() -> dict[str, Any]:
    return {
        "canonical_root": "/nonexistent/repo",
        "manifest_schema_version": "1.0.0",
        "bundle_compliant": True,
        "tracked_files": {"expected": [".kittify/charter/charter.md"], "present": [".kittify/charter/charter.md"], "missing": []},
        "derived_files": {"expected": [".kittify/charter/governance.yaml"], "present": [], "missing": []},
        "gitignore": {"expected_entries": [".kittify/charter/governance.yaml"], "present_entries": [".kittify/charter/governance.yaml"], "missing_entries": []},
        "out_of_scope_files": [],
        "warnings": [],
        "errors": [],
        "synthesis_state": {"present": False, "passed": True, "errors": [], "warnings": []},
        "passed": True,
        "result": "success",
    }


# ---------------------------------------------------------------------------
# Manifest v2 shape (WP01 / T002) — construct + validate guarantees M1/M2
# ---------------------------------------------------------------------------


class TestManifestV2Shape:
    def test_manifest_v2_constructs_and_validates(self) -> None:
        """Manifest v2 constructs without raising (the model_validator
        disjointness check passes for the canonical v2 shape)."""
        from charter.bundle import CANONICAL_MANIFEST

        assert CANONICAL_MANIFEST.schema_version == "2.0.0"

    def test_derived_files_is_empty(self) -> None:
        from charter.bundle import CANONICAL_MANIFEST

        assert CANONICAL_MANIFEST.derived_files == []

    def test_content_hash_files_is_charter_yaml(self) -> None:
        from charter.bundle import CANONICAL_MANIFEST, CHARTER_YAML

        assert CANONICAL_MANIFEST.content_hash_files == [CHARTER_YAML]


# ---------------------------------------------------------------------------
# Bucket B — Filesystem I/O helpers
# ---------------------------------------------------------------------------


class TestReadGitignoreLines:
    def test_returns_empty_list_when_gitignore_missing(self, tmp_path: Path) -> None:
        """Arrange: no .gitignore;
        Act: read;
        Assert: empty list returned."""
        result = _read_gitignore_lines(tmp_path)
        assert result == []

    def test_returns_lines_from_existing_gitignore(self, tmp_path: Path) -> None:
        """Arrange: .gitignore with content;
        Act: read;
        Assert: list of lines returned."""
        (tmp_path / ".gitignore").write_text("node_modules/\n*.pyc\n", encoding="utf-8")
        result = _read_gitignore_lines(tmp_path)
        assert "node_modules/" in result
        assert "*.pyc" in result

    def test_strips_trailing_newline_chars(self, tmp_path: Path) -> None:
        """Arrange: .gitignore with CRLF line endings;
        Act: read;
        Assert: no trailing carriage returns in results."""
        (tmp_path / ".gitignore").write_text("entry\r\n", encoding="utf-8")
        result = _read_gitignore_lines(tmp_path)
        for line in result:
            assert not line.endswith("\r")


class TestClassifyPaths:
    def test_present_when_file_exists_on_disk(self, tmp_path: Path) -> None:
        """Arrange: file exists; Act: classify; Assert: in present list."""
        (tmp_path / "charter.md").write_text("# Charter", encoding="utf-8")
        present, missing = _classify_paths(tmp_path, [Path("charter.md")])
        assert "charter.md" in present
        assert missing == []

    def test_missing_when_file_absent(self, tmp_path: Path) -> None:
        """Arrange: file does not exist; Act: classify; Assert: in missing list."""
        present, missing = _classify_paths(tmp_path, [Path("nonexistent.md")])
        assert present == []
        assert "nonexistent.md" in missing

    def test_require_tracked_false_accepts_untracked_files(self, tmp_path: Path) -> None:
        """Arrange: file exists but is untracked; Act: classify without require_tracked;
        Assert: file in present list."""
        (tmp_path / "file.md").write_text("content", encoding="utf-8")
        present, missing = _classify_paths(tmp_path, [Path("file.md")], require_tracked=False)
        assert "file.md" in present


class TestClassifyGitignore:
    def test_entries_present_when_in_gitignore(self, tmp_path: Path) -> None:
        """Arrange: .gitignore has required entry;
        Act: classify; Assert: in present list."""
        (tmp_path / ".gitignore").write_text(".kittify/charter/governance.yaml\n", encoding="utf-8")
        present, missing = _classify_gitignore(tmp_path, [".kittify/charter/governance.yaml"])
        assert ".kittify/charter/governance.yaml" in present
        assert missing == []

    def test_entries_missing_when_not_in_gitignore(self, tmp_path: Path) -> None:
        """Arrange: .gitignore lacks required entry;
        Act: classify; Assert: in missing list."""
        (tmp_path / ".gitignore").write_text("other_entry\n", encoding="utf-8")
        present, missing = _classify_gitignore(tmp_path, [".kittify/charter/governance.yaml"])
        assert present == []
        assert ".kittify/charter/governance.yaml" in missing


class TestEnumerateOutOfScopeFiles:
    def test_empty_when_no_charter_directory(self, tmp_path: Path) -> None:
        """Arrange: no charter dir; Act: enumerate; Assert: empty results."""
        mock_manifest = MagicMock()
        mock_manifest.tracked_files = []
        mock_manifest.derived_files = []
        out_of_scope, warnings = _enumerate_out_of_scope_files(tmp_path, mock_manifest)
        assert out_of_scope == []
        assert warnings == []

    def test_detects_undeclared_files_in_charter_dir(self, tmp_path: Path) -> None:
        """Arrange: charter dir with an unknown file;
        Act: enumerate; Assert: file appears in out_of_scope."""
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "unknown_extra.yaml").write_text("data: 1", encoding="utf-8")

        mock_manifest = MagicMock()
        mock_manifest.tracked_files = []
        mock_manifest.derived_files = []

        out_of_scope, warnings = _enumerate_out_of_scope_files(tmp_path, mock_manifest)
        assert any("unknown_extra.yaml" in s for s in out_of_scope)


# ---------------------------------------------------------------------------
# Bucket C — Rendering helpers
# ---------------------------------------------------------------------------


class TestRenderHuman:
    def test_renders_compliant_message_when_bundle_is_compliant(self, capsys) -> None:  # type: ignore[no-untyped-def]
        """Arrange: report with bundle_compliant=True;
        Act: render;
        Assert: 'compliant' in rendered output."""
        from rich.console import Console
        import io

        buf = io.StringIO()
        console = Console(file=buf, highlight=False)
        report = _make_minimal_report()
        report["bundle_compliant"] = True
        report["passed"] = True

        _render_human(report, console)
        output = buf.getvalue()
        assert "compliant" in output.lower() or "Compliant" in output

    def test_renders_not_compliant_when_bundle_fails(self, capsys) -> None:  # type: ignore[no-untyped-def]
        """Arrange: report with bundle_compliant=False;
        Act: render;
        Assert: 'NOT compliant' or similar in output."""
        from rich.console import Console
        import io

        buf = io.StringIO()
        console = Console(file=buf, highlight=False)
        report = _make_minimal_report()
        report["bundle_compliant"] = False
        report["tracked_files"]["missing"] = [".kittify/charter/charter.md"]
        report["passed"] = False
        report["result"] = "failure"

        _render_human(report, console)
        output = buf.getvalue()
        assert "NOT compliant" in output or "not compliant" in output.lower()


# ---------------------------------------------------------------------------
# Bucket A — CLI orchestration (via CliRunner)
# ---------------------------------------------------------------------------


class TestValidateCLI:
    def test_validate_exits_nonzero_when_resolver_raises_not_inside_repo(self, tmp_path: Path) -> None:
        """Arrange: cwd is not inside a git repo;
        Act: invoke bundle validate;
        Assert: exit code 2."""
        from charter.resolution import NotInsideRepositoryError

        with patch("specify_cli.cli.commands.charter_bundle.resolve_canonical_repo_root", side_effect=NotInsideRepositoryError("not a repo")):
            result = runner.invoke(app, ["validate"])

        assert result.exit_code == 2
