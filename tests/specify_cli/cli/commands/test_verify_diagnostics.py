"""``verify-setup --diagnostics`` report (``specify_cli.diagnostics.project``).

Ported from the deleted ``tests/test_dashboard/test_diagnostics.py`` when the
module moved out of the bundled dashboard (#5530), plus the paths the move
changed: no ``dashboard_health`` key, the Mission-named observation, a failing
feature-status probe, and a git branch that cannot be read.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from specify_cli.diagnostics import project as diagnostics

pytestmark = pytest.mark.unit

_SLUG = "004-modular-code-refactoring"


def _feature_status(worktree_path: Path, *, worktree_exists: bool = True) -> dict[str, object]:
    return {
        "state": "in_development",
        "branch_exists": True,
        "branch_merged": False,
        "worktree_exists": worktree_exists,
        "worktree_path": str(worktree_path),
        "artifacts_in_main": ["spec.md"],
        "artifacts_in_worktree": ["spec.md"],
    }


def _install_manifest_stubs(
    monkeypatch: pytest.MonkeyPatch,
    worktree_path: Path,
    *,
    worktree_exists: bool = True,
    status_error: Exception | None = None,
) -> None:
    """Swap ``specify_cli.manifest`` for lightweight manifest + worktree stubs."""

    class FakeManifest:
        def __init__(self, kittify_dir: Path, *, mission_type: str | None = None) -> None:
            self.kittify_dir = kittify_dir
            self.mission_type = mission_type

        def get_expected_files(self) -> dict[str, list[str]]:
            return {"commands": ["commands/tasks.md"], "templates": ["templates/base.md"]}

        def check_files(self) -> dict[str, Any]:
            return {
                "present": {"commands/tasks.md": "commands"},
                "missing": {"templates/base.md": "templates"},
                "modified": {},
                "extra": [],
            }

    class FakeWorktreeStatus:
        def __init__(self, repo_root: Path) -> None:
            self.repo_root = repo_root

        def get_worktree_summary(self) -> dict[str, int]:
            return {"total_features": 1, "active_worktrees": 1, "merged_features": 0, "in_development": 1, "not_started": 0}

        def get_all_features(self) -> list[str]:
            return [_SLUG]

        def get_feature_status(self, feature: str) -> dict[str, object]:
            del feature
            if status_error is not None:
                raise status_error
            return _feature_status(worktree_path, worktree_exists=worktree_exists)

    fake_module = types.ModuleType("specify_cli.manifest")
    fake_module.FileManifest = FakeManifest  # type: ignore[attr-defined]  # stub module built at runtime
    fake_module.WorktreeStatus = FakeWorktreeStatus  # type: ignore[attr-defined]  # stub module built at runtime
    monkeypatch.setitem(sys.modules, "specify_cli.manifest", fake_module)


def _fake_git(branch: str) -> Any:
    def fake_run(args: list[str], **kwargs: Any) -> types.SimpleNamespace:
        del kwargs
        assert args == ["git", "branch", "--show-current"]
        return types.SimpleNamespace(stdout=f"{branch}\n", returncode=0)

    return fake_run


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / ".worktrees").mkdir()
    monkeypatch.setattr("specify_cli.core.git_ops.resolve_primary_branch", lambda _: "main")
    return project


def test_reports_manifest_and_worktree_state(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_manifest_stubs(monkeypatch, project_dir / ".worktrees")
    monkeypatch.setattr(diagnostics.subprocess, "run", _fake_git("feature/testing"))

    result = diagnostics.run_diagnostics(project_dir, feature_dir=project_dir / "kitty-specs" / _SLUG)

    assert result["git_branch"] == "feature/testing"
    assert result["worktrees_exist"] is True
    assert result["file_integrity"]["total_expected"] == 2
    assert result["file_integrity"]["total_missing"] == 1
    assert result["file_integrity"]["missing_files"] == ["templates/base.md"]
    assert result["worktree_overview"]["active_worktrees"] == 1
    assert result["all_features"][0]["name"] == _SLUG
    assert result["current_feature"]["detected"] is True
    assert result["current_feature"]["name"] == _SLUG
    assert "Mission integrity: 1 expected files not found" in result["observations"]


def test_report_no_longer_carries_dashboard_health(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_manifest_stubs(monkeypatch, project_dir / ".worktrees")
    monkeypatch.setattr(diagnostics.subprocess, "run", _fake_git("main"))

    result = diagnostics.run_diagnostics(project_dir)

    assert "dashboard_health" not in result
    assert not any("dashboard" in issue.lower() for issue in result["issues"])


def test_without_feature_dir_shows_no_mission_context(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_manifest_stubs(monkeypatch, project_dir / ".worktrees")
    monkeypatch.setattr(diagnostics.subprocess, "run", _fake_git("main"))

    result = diagnostics.run_diagnostics(project_dir)

    assert result["active_mission"] == "no mission context"
    assert result["current_feature"] == {}


def test_feature_dir_meta_resolves_the_mission_type(project_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feature_dir = tmp_path / "feature-dir"
    feature_dir.mkdir()
    meta = {"mission_type": "research", "mission_slug": "099-test", "created_at": "2026-01-01"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _install_manifest_stubs(monkeypatch, project_dir / ".worktrees")
    monkeypatch.setattr(diagnostics.subprocess, "run", _fake_git("main"))

    result = diagnostics.run_diagnostics(project_dir, feature_dir=feature_dir)

    assert result["active_mission"] == "research"


def test_mission_without_its_worktree_is_observed(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_manifest_stubs(monkeypatch, project_dir / ".worktrees", worktree_exists=False)
    monkeypatch.setattr(diagnostics.subprocess, "run", _fake_git("main"))

    result = diagnostics.run_diagnostics(project_dir, feature_dir=project_dir / "kitty-specs" / _SLUG)

    assert f"Mission {_SLUG} has no worktree but has development artifacts" in result["observations"]


def test_failing_feature_status_probe_is_reported_not_raised(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_manifest_stubs(monkeypatch, project_dir / ".worktrees", status_error=RuntimeError("status unreadable"))
    worktree_status = sys.modules["specify_cli.manifest"].WorktreeStatus(project_dir)
    report: dict[str, Any] = {}

    diagnostics._collect_current_feature(project_dir / "kitty-specs" / _SLUG, worktree_status, report)

    assert report["current_feature"] == {"detected": False, "error": "status unreadable"}


def test_unreadable_git_branch_is_an_issue(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run(args: list[str], **kwargs: Any) -> None:
        del kwargs
        raise subprocess.CalledProcessError(128, args)

    monkeypatch.setattr(diagnostics.subprocess, "run", failing_run)
    report: dict[str, Any] = {"git_branch": None, "issues": []}

    diagnostics._detect_git_branch(project_dir, report)

    assert report["git_branch"] is None
    assert report["issues"] == ["Could not detect git branch"]
