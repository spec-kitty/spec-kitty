"""#7540 item 2: the rollback authority resyncs a settled default Mission's own coordination residue.

A default Mission settled to ``lanes_with_coord`` keeps its ``meta.json`` only on its Mission
branch, which the coordination worktree holds; the repository root checkout has none. The
rollback's residue context read the stored topology from a raw ``<root>/kitty-specs/<slug>`` join,
so it found nothing, fell back to the strictest classifier, and a ``consolidate --abort`` after a
killed run left the run's own uncommitted status log and snapshot in the coordination checkout
"as found". Each test drives the real ``spec-kitty`` CLI: ``consolidate`` is SIGKILLed right before
the ``git commit`` of ``status transition WP02`` (the #5931 window) by a ``git`` wrapper first on
``PATH``, then ``consolidate --abort`` runs.

The coordination BRANCH may still be reported NOT restored after the kill; that is a separate
defect (#5931), so these tests judge only the coordination checkout.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import (
    Built,
    _quiet,
    build,
    cli,
    consolidate,
)
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_LEFT_AS_FOUND = "coordination checkout left as found"
_NOTES = "#7540 operator notes, not residue\n"

_GIT_WRAPPER = """#!/usr/bin/env bash
if [[ ! -e "__MARKER__" ]] && [[ "$*" =~ status\\ transition\\ WP02 ]] && [[ "$*" =~ commit ]]; then
    : > "__MARKER__"
    kill -9 $PPID
    exit 137
fi
exec "__REAL_GIT__" "$@"
"""


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)


def _install_kill_wrapper(tmp_path: Path) -> tuple[Path, Path]:
    """A ``git`` that SIGKILLs its caller once, at the ``status transition WP02`` commit."""
    real_git = shutil.which("git")
    assert real_git is not None
    bin_dir = tmp_path / "killbin"
    bin_dir.mkdir()
    marker = tmp_path / "killed.marker"
    wrapper = bin_dir / "git"
    wrapper.write_text(_GIT_WRAPPER.replace("__MARKER__", str(marker)).replace("__REAL_GIT__", real_git), encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir, marker


def _killed_consolidate(tmp_path: Path) -> Built:
    """Build the settled Mission and SIGKILL ``consolidate`` inside the per-WP done commits."""
    built = build(tmp_path)
    bin_dir, marker = _install_kill_wrapper(tmp_path)
    path = os.pathsep.join((str(bin_dir), os.environ.get("PATH", "")))
    proc = consolidate(built, hooks={"PATH": path})
    assert marker.exists(), f"the kill never fired (exit {proc.returncode})\nSTDOUT:\n{proc.stdout[-3000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
    assert proc.returncode != 0
    return built


def _abort(built: Built) -> subprocess.CompletedProcess[str]:
    return cli(built, "consolidate", "--mission", built.slug, "--abort")


@pytest.mark.p0_repro(issue=7544)
def test_abort_after_kill_resyncs_the_runs_own_coordination_residue(tmp_path: Path) -> None:
    built = _killed_consolidate(tmp_path)
    dirty_before = git(built.coord_worktree, "status", "--porcelain")
    assert "status.events.jsonl" in dirty_before or "status.json" in dirty_before, dirty_before

    proc = _abort(built)
    output = proc.stdout + proc.stderr

    assert _LEFT_AS_FOUND not in output, output[-4000:]
    assert git(built.coord_worktree, "status", "--porcelain") == ""


def test_abort_after_kill_keeps_a_foreign_edit_in_the_coordination_checkout(tmp_path: Path) -> None:
    built = _killed_consolidate(tmp_path)
    notes = built.coord_worktree / built.rel / "notes.md"
    notes.write_text(_NOTES, encoding="utf-8")

    proc = _abort(built)
    output = proc.stdout + proc.stderr

    assert _LEFT_AS_FOUND in output, output[-4000:]
    assert notes.read_text(encoding="utf-8") == _NOTES
