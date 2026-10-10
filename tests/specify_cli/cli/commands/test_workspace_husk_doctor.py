"""Focused per-helper tests for ``_workspace_husk_doctor`` (WP09, #2059).

Cover the status-label classification, the fix-emission branches (registration
refusal / remaining husks / clean), the report-emission branches (clean / error /
husks-present), and the run_workspaces dispatch exit contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands import _workspace_husk_doctor as wh

pytestmark = [pytest.mark.fast]


# --- _workspace_husk_status_label --------------------------------------------


def test_status_label_unknown() -> None:
    assert "unknown registration" in wh._workspace_husk_status_label(None)


def test_status_label_registered() -> None:
    assert "registered (manual repair" in wh._workspace_husk_status_label(True)


def test_status_label_unregistered() -> None:
    assert "unregistered (safe" in wh._workspace_husk_status_label(False)


# --- report emission ---------------------------------------------------------


@dataclass
class _Husk:
    path: str = "/repo/.worktrees/husk-a"
    registered: bool | None = False


@dataclass
class _Report:
    healthy: bool = True
    husks: list[_Husk] = field(default_factory=list)
    registration_error: str | None = None
    worktrees_dir: str = "/repo/.worktrees"

    def to_dict(self) -> dict[str, Any]:
        return {"healthy": self.healthy, "husks": [h.path for h in self.husks]}


def test_report_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    monkeypatch.setattr(status_mod, "scan_workspace_husks", lambda _r: _Report(healthy=True))
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_report(tmp_path, json_output=False)
    assert exc.value.exit_code == 0


def test_report_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    monkeypatch.setattr(status_mod, "scan_workspace_husks", lambda _r: _Report(healthy=False))
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_report(tmp_path, json_output=True)
    assert exc.value.exit_code == 1


def test_report_error_no_husks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    report = _Report(healthy=False, husks=[], registration_error="git failed")
    monkeypatch.setattr(status_mod, "scan_workspace_husks", lambda _r: report)
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_report(tmp_path, json_output=False)
    assert exc.value.exit_code == 1


def test_report_husks_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    report = _Report(
        healthy=False, husks=[_Husk(registered=False), _Husk(registered=True)],
        registration_error="partial",
    )
    monkeypatch.setattr(status_mod, "scan_workspace_husks", lambda _r: report)
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_report(tmp_path, json_output=False)
    assert exc.value.exit_code == 1


# --- fix emission ------------------------------------------------------------


@dataclass
class _FixResult:
    removed: list[str] = field(default_factory=list)
    skipped_registered: list[str] = field(default_factory=list)
    skipped_appeared_valid: list[str] = field(default_factory=list)
    skipped_unsafe: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"removed": self.removed}


def test_fix_registration_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    def _boom(_r: Path) -> Any:
        raise status_mod.WorkspaceHuskRegistrationError("git down")

    monkeypatch.setattr(status_mod, "fix_workspace_husks", _boom)
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_fix(tmp_path, json_output=False)
    assert exc.value.exit_code == 1


def test_fix_registration_error_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    def _boom(_r: Path) -> Any:
        raise status_mod.WorkspaceHuskRegistrationError("git down")

    monkeypatch.setattr(status_mod, "fix_workspace_husks", _boom)
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_fix(tmp_path, json_output=True)
    assert exc.value.exit_code == 1


def test_fix_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    report = _Report(husks=[])
    monkeypatch.setattr(
        status_mod, "fix_workspace_husks", lambda _r: (report, _FixResult(removed=["a"]))
    )
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_fix(tmp_path, json_output=False)
    assert exc.value.exit_code == 0


def test_fix_remaining_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    report = _Report(husks=[_Husk()])
    fix_result = _FixResult(skipped_registered=["reg-a"], skipped_appeared_valid=["v-a"])
    monkeypatch.setattr(status_mod, "fix_workspace_husks", lambda _r: (report, fix_result))
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_fix(tmp_path, json_output=True)
    assert exc.value.exit_code == 1


def test_fix_human_with_skips(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.status as status_mod

    report = _Report(husks=[])
    fix_result = _FixResult(
        removed=["r"], skipped_registered=["reg"], skipped_appeared_valid=["v"], skipped_unsafe=["u"]
    )
    monkeypatch.setattr(status_mod, "fix_workspace_husks", lambda _r: (report, fix_result))
    with pytest.raises(typer.Exit) as exc:
        wh._emit_workspace_husk_fix(tmp_path, json_output=False)
    # Remaining (skipped) → exit 1.
    assert exc.value.exit_code == 1


# --- run_workspaces dispatch -------------------------------------------------


def test_run_workspaces_fix_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called: dict[str, Any] = {}
    monkeypatch.setattr(wh, "_emit_workspace_husk_fix", lambda r, j: called.setdefault("fix", (r, j)))
    wh.run_workspaces(tmp_path, fix=True, json_output=True)
    assert called["fix"] == (tmp_path, True)


def test_run_workspaces_report_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called: dict[str, Any] = {}
    monkeypatch.setattr(
        wh, "_emit_workspace_husk_report", lambda r, j: called.setdefault("report", (r, j))
    )
    wh.run_workspaces(tmp_path, fix=False, json_output=False)
    assert called["report"] == (tmp_path, False)


# --- _coord_worktree_needs_refresh (stale ancestor path) --------------------


def test_coord_worktree_needs_refresh_stale_ancestor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_coord_worktree_needs_refresh returns (True, branch) when HEAD is a strict
    ancestor of the branch tip.

    Covers lines 153-177: symbolic-ref OK, rev-parse HEAD returns SHA1, rev-parse
    branch tip returns SHA2 (SHA1 != SHA2), merge-base --is-ancestor exits 0 →
    (True, branch).  Subprocess calls are patched because the single-repo linked-
    worktree model makes HEAD and refs/heads/<branch> resolve identically in a real
    checkout (symbolic HEAD always tracks the current branch tip through the shared
    ref store).
    """
    import subprocess as real_subprocess
    from dataclasses import dataclass

    SHA1 = "aabbccddeeff001122334455667788990011aabb"
    SHA2 = "1122334455667788990011aabbccddeeff112233"
    BRANCH = "kitty/mission-test-0000000A"

    @dataclass
    class _FakeResult:
        returncode: int
        stdout: str = ""

    def _mock_run(args: list[str], **kwargs: object) -> _FakeResult:
        if "symbolic-ref" in args:
            return _FakeResult(returncode=0, stdout=BRANCH + "\n")
        if "rev-parse" in args and "HEAD" in args:
            return _FakeResult(returncode=0, stdout=SHA1 + "\n")
        if "rev-parse" in args and f"refs/heads/{BRANCH}" in args:
            return _FakeResult(returncode=0, stdout=SHA2 + "\n")
        if "merge-base" in args and "--is-ancestor" in args:
            # SHA1 is a strict ancestor of SHA2.
            return _FakeResult(returncode=0)
        return _FakeResult(returncode=1)  # unknown call → fail-safe

    monkeypatch.setattr(real_subprocess, "run", _mock_run)

    stale, branch = wh._coord_worktree_needs_refresh(tmp_path, tmp_path)
    assert stale is True
    assert branch == BRANCH
