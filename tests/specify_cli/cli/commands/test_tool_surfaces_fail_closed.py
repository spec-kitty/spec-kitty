"""``doctor tool-surfaces --fix`` fail-closed from a foreign checkout (WP03).

Mission ``worktree-root-resolution-01M0B59R`` WP03 (FR-003, #2613 — the cleanest
confirmed defect). Tool surfaces are **per-checkout tracked** agent files
(``.claude/commands/*`` etc.), NOT status; there is no deliberate-centralization
defense for this command. ``doctor tool-surfaces --fix`` invoked from a linked
lane worktree re-anchors to the primary (``_resolve_tool_surfaces_project`` calls
``locate_project_root`` with no start-arg) and then passes that primary
``project_path`` into ``run_tool_surfaces(..., fix=True)`` — silently repairing
the PRIMARY's manifest.

Red-first (T010): on base, invoking ``--fix`` from the lane repairs the primary's
manifest while the lane's surface stays broken. The green-after conditions can
ONLY be satisfied by a fail-closed refusal (WP01 seam), never by the forbidden
redirect (C-003/#3128): (a) a ``FailClosedRefusal`` is raised; (b) its message
names the primary checkout verbatim; (c) the primary's manifest is unchanged;
AND (d) the lane's surface is not repaired either.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
import typer

from specify_cli.cli.commands import _command_surface_doctor as surface_doctor
from specify_cli.cli.commands._command_surface_doctor import (
    ToolSurfaceFixRefused,
    run_tool_surfaces_audit,
)
from specify_cli.core.checkout_identity import FailClosedRefusal
from specify_cli.tool_surface.service import ToolSurfaceOutcome
from specify_cli.tool_surface.status import SurfaceReport, SurfaceSummary

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

_REPAIR_MARKER = ".claude/commands/REPAIRED_BY_FIX.marker"


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def _make_primary(tmp_path: Path) -> Path:
    """Create a real git repo that is a spec-kitty project with a claude surface."""
    primary = tmp_path / "primary"
    (primary / ".kittify").mkdir(parents=True)
    commands = primary / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / "specify.md").write_text("# specify surface\n", encoding="utf-8")
    _run_git(["init"], cwd=primary)
    _run_git(["config", "user.email", "test@example.com"], cwd=primary)
    _run_git(["config", "user.name", "Test User"], cwd=primary)
    _run_git(["add", "-A"], cwd=primary)
    _run_git(["commit", "-m", "init"], cwd=primary)
    _run_git(["branch", "-M", "main"], cwd=primary)
    return primary


def _add_lane(primary: Path, tmp_path: Path) -> Path:
    """Add a real linked worktree (lane) of ``primary``."""
    lane = tmp_path / "lane-c"
    _run_git(["worktree", "add", "-b", "lane-c", str(lane)], cwd=primary)
    return lane


class _FakeRunToolSurfaces:
    """Records ``run_tool_surfaces`` calls and simulates a manifest repair.

    A ``fix=True`` call writes a marker into ``<project_root>/.claude/commands`` —
    the observable stand-in for the per-checkout manifest mutation. This lets the
    test assert *which* checkout would be mutated (primary vs lane) purely from
    the filesystem, closing the redirect fake: a fix routed into the lane would
    drop the marker there, and the guard must instead leave BOTH untouched.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Path, bool]] = []

    def __call__(
        self,
        project_root: Path,
        configured_tools: Sequence[str],
        *,
        tool_filter: str | None = None,
        kinds: object | None = None,
        fix: bool = False,
    ) -> ToolSurfaceOutcome:
        self.calls.append((project_root, fix))
        if fix:
            marker = project_root / _REPAIR_MARKER
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("repaired\n", encoding="utf-8")
        report = SurfaceReport(
            ok=True,
            project_root=str(project_root),
            configured_tools=("claude",),
            summary=SurfaceSummary(0, 0, 0, 0, 0, 0),
            surfaces=(),
            findings=(),
        )
        return ToolSurfaceOutcome(report=report)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, _FakeRunToolSurfaces]:
    """Real primary + linked lane worktree, with the repair engine stubbed."""
    primary = _make_primary(tmp_path)
    lane = _add_lane(primary, tmp_path)
    fake = _FakeRunToolSurfaces()
    # Stub the config read (avoids depending on config.yaml shape) and the repair
    # engine (we assert on the checkout it targets, not on real provider I/O).
    monkeypatch.setattr(
        surface_doctor,
        "_tool_config_or_exit",
        lambda _project, _json_output: SimpleNamespace(available=["claude"], explicit_agent_list=True),
    )
    monkeypatch.setattr("specify_cli.tool_surface.service.run_tool_surfaces", fake)
    return primary, lane, fake


def _marker(root: Path) -> Path:
    return root / _REPAIR_MARKER


def test_fix_from_lane_fails_closed_naming_primary(
    project: tuple[Path, Path, _FakeRunToolSurfaces],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--fix`` from a lane refuses (WP01 seam) and mutates no checkout.

    RED on base: the lane invocation re-anchors to the primary and the fake
    repair drops the marker into the PRIMARY's ``.claude/commands`` while the
    lane stays broken — no refusal is raised, so ``pytest.raises`` fails.
    """
    primary, lane, fake = project
    monkeypatch.chdir(lane)

    with pytest.raises(ToolSurfaceFixRefused) as exc_info:
        run_tool_surfaces_audit(kind=None, tool=None, fix=True, json_output=False)

    # (a) a FailClosedRefusal is raised (carried by the single-channel exception).
    refusal = exc_info.value.refusal
    assert isinstance(refusal, FailClosedRefusal)
    # (b) the message names the primary checkout verbatim.
    assert str(primary.resolve()) in refusal.message()
    # (c) the primary's manifest is unchanged.
    assert not _marker(primary).exists()
    # (d) the lane's surface was not repaired either (refused, not redirected).
    assert not _marker(lane).exists()
    # No repair call ever fired — the guard refuses before mutation.
    assert all(not called_fix for _root, called_fix in fake.calls)


def test_fix_from_owner_primary_repairs_its_own(
    project: tuple[Path, Path, _FakeRunToolSurfaces],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner-checkout ``--fix`` proceeds and repairs its own manifest."""
    primary, _lane, fake = project
    monkeypatch.chdir(primary)

    with pytest.raises(typer.Exit) as exc_info:
        # run_tool_surfaces_audit always exits (0 ok / 1 issues); the owner path
        # is NOT a fail-closed refusal.
        run_tool_surfaces_audit(kind=None, tool=None, fix=True, json_output=False)

    # Owner path exits cleanly — never a fail-closed refusal.
    assert not isinstance(exc_info.value, ToolSurfaceFixRefused)
    assert (primary.resolve(), True) in [(root.resolve(), called_fix) for root, called_fix in fake.calls]
    assert _marker(primary).exists()


def test_audit_from_lane_still_reads(
    project: tuple[Path, Path, _FakeRunToolSurfaces],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read-only ``--audit`` (fix=False) from a lane is never gated (FR-003 risk)."""
    _primary, lane, fake = project
    monkeypatch.chdir(lane)

    with pytest.raises(typer.Exit) as exc_info:
        run_tool_surfaces_audit(kind=None, tool=None, fix=False, json_output=False)

    # Not a ToolSurfaceFixRefused — the audit read proceeds and exits 0.
    assert not isinstance(exc_info.value, ToolSurfaceFixRefused)
    assert fake.calls, "audit must still invoke run_tool_surfaces"
    assert all(not called_fix for _root, called_fix in fake.calls)
