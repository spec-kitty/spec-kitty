"""Fast status-slice coverage for workspace husk doctor helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import specify_cli.status.doctor_husks as doctor_husks

pytestmark = pytest.mark.fast


def _worktrees(repo: Path) -> Path:
    path = repo / ".worktrees"
    path.mkdir()
    return path


def test_scan_is_healthy_without_worktrees_dir(tmp_path: Path) -> None:
    report = doctor_husks.scan_workspace_husks(tmp_path)

    assert report.healthy is True
    assert report.to_dict() == {
        "worktrees_dir": str(tmp_path / ".worktrees"),
        "healthy": True,
        "registration_error": None,
        "husks": [],
    }


def test_scan_reports_registered_unregistered_and_ignores_valid_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktrees = _worktrees(tmp_path)
    unregistered = worktrees / "unregistered"
    registered = worktrees / "registered"
    valid = worktrees / "valid"
    unregistered.mkdir()
    registered.mkdir()
    valid.mkdir()
    (valid / ".git").write_text("gitdir: ../real\n", encoding="utf-8")
    (worktrees / "not-a-dir").write_text("ignore me\n", encoding="utf-8")

    def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> SimpleNamespace:
        assert cmd == ["git", "worktree", "list", "--porcelain"]
        return SimpleNamespace(
            returncode=0,
            stdout=f"worktree {registered}\nbranch refs/heads/test\n",
            stderr="",
        )

    monkeypatch.setattr(doctor_husks.subprocess, "run", fake_run)

    report = doctor_husks.scan_workspace_husks(tmp_path)

    assert report.healthy is False
    assert report.registration_error is None
    assert {entry.path: entry.registered for entry in report.husks} == {
        ".worktrees/registered": True,
        ".worktrees/unregistered": False,
    }
    assert report.to_dict()["husks"] == [
        {"path": ".worktrees/registered", "registered": True},
        {"path": ".worktrees/unregistered", "registered": False},
    ]


def test_scan_marks_registration_unknown_when_git_inventory_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktrees = _worktrees(tmp_path)
    (worktrees / "husk").mkdir()

    def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> SimpleNamespace:
        assert cmd == ["git", "worktree", "list", "--porcelain"]
        return SimpleNamespace(
            returncode=128,
            stdout="",
            stderr="fatal: broken worktree metadata\n",
        )

    monkeypatch.setattr(doctor_husks.subprocess, "run", fake_run)

    report = doctor_husks.scan_workspace_husks(tmp_path)

    assert report.healthy is False
    assert report.registration_error == (
        "git worktree list --porcelain failed: fatal: broken worktree metadata"
    )
    assert {entry.path: entry.registered for entry in report.husks} == {
        ".worktrees/husk": None,
    }

    with pytest.raises(doctor_husks.WorkspaceHuskRegistrationError):
        doctor_husks.fix_workspace_husks(tmp_path)


def test_fix_removes_only_unregistered_husks_and_rechecks_git_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    worktrees = _worktrees(tmp_path)
    removable = worktrees / "removable"
    registered = worktrees / "registered"
    appeared_valid = worktrees / "appeared-valid"
    removable.mkdir()
    registered.mkdir()
    appeared_valid.mkdir()
    (appeared_valid / ".git").write_text("gitdir: ../now-valid\n", encoding="utf-8")

    report = doctor_husks.HuskReport(
        worktrees_dir=str(worktrees),
        husks=[
            doctor_husks.HuskEntry(".worktrees/removable", False),
            doctor_husks.HuskEntry(".worktrees/registered", True),
            doctor_husks.HuskEntry(".worktrees/appeared-valid", False),
        ],
    )
    monkeypatch.setattr(doctor_husks, "scan_workspace_husks", lambda _root: report)

    returned_report, result = doctor_husks.fix_workspace_husks(tmp_path)

    assert returned_report is report
    assert result.removed == [".worktrees/removable"]
    assert result.skipped_registered == [".worktrees/registered"]
    assert result.skipped_appeared_valid == [".worktrees/appeared-valid"]
    assert result.to_dict() == {
        "removed": [".worktrees/removable"],
        "skipped_registered": [".worktrees/registered"],
        "skipped_appeared_valid": [".worktrees/appeared-valid"],
        "skipped_unsafe": [],
    }
    assert not removable.exists()
    assert registered.exists()
    assert appeared_valid.exists()
