"""#5931 / SC-002: a kill inside ``consolidate``'s done-recording phase is undone by ``--abort``.

``consolidate`` records each approved work package ``done`` with one coordination commit
(``status transition WPnn``) inside the rollback span. Before the fix those commits moved the
coordination branch through ``safe_commit``'s plain ``git commit``, so the run persisted no advance
intent for them. A SIGKILL after ``WP01``'s done commit landed and before ``WP02``'s landed left a
tip the record could not explain: ``--abort`` printed ``NOT restored ... moved by another actor``
and kept the coordination branch on the run's own commit.

The kill comes from a ``git`` wrapper first on ``PATH``. It fires once, on the first git call that
would land ``WP02``'s done commit: a porcelain ``commit`` carrying the message (pre-fix) or the
compare-and-swap ``update-ref`` carrying it (the expected-parent path). Either way ``WP01``'s
commit has landed and ``WP02``'s has not.

Only the branch restore is asserted here. Until the rollback classifies the killed write's own
status files as residue, the first abort refuses to move the branch under them and prints a
``stash`` remedy; the test follows it and aborts again. Whether the coordination checkout is clean
after the abort, and a full re-run, are covered elsewhere (the residue classifier and the closeout
test).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import Built, build, cli, consolidate
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_KILL_MESSAGE = "status transition WP02"
_SIGKILL_EXIT = -9

#: Bash ``git`` that SIGKILLs its caller (the CLI) once, before WP02's done commit lands.
_WRAPPER = """#!/usr/bin/env bash
marker='__MARKER__'
if [ ! -e "$marker" ]; then
  lands=0
  names_wp=0
  for arg in "$@"; do
    case "$arg" in
      commit|update-ref) lands=1 ;;
    esac
    case "$arg" in
      *'__MESSAGE__'*) names_wp=1 ;;
    esac
  done
  if [ "$lands" = 1 ] && [ "$names_wp" = 1 ]; then
    : > "$marker"
    kill -9 "$PPID"
    exit 137
  fi
fi
exec '__REAL_GIT__' "$@"
"""


def _install_kill_wrapper(tmp_path: Path) -> tuple[dict[str, str], Path]:
    real_git = shutil.which("git")
    assert real_git is not None
    bin_dir = tmp_path / "kill-bin"
    bin_dir.mkdir()
    marker = tmp_path / "kill-fired"
    wrapper = bin_dir / "git"
    wrapper.write_text(
        _WRAPPER.replace("__MARKER__", str(marker)).replace("__MESSAGE__", _KILL_MESSAGE).replace("__REAL_GIT__", real_git),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return {"PATH": os.pathsep.join((str(bin_dir), os.environ.get("PATH", "")))}, marker


def _abort(built: Built) -> str:
    aborted = cli(built, "consolidate", "--mission", built.slug, "--abort")
    return aborted.stdout + aborted.stderr


def _coordination_tip(built: Built) -> str:
    return git(built.root, "rev-parse", f"refs/heads/{built.mission.topic}")


def test_abort_restores_coordination_branch_after_kill_between_done_commits(tmp_path: Path) -> None:
    built = build(tmp_path)
    tip_before = _coordination_tip(built)
    hooks, marker = _install_kill_wrapper(tmp_path)

    killed = consolidate(built, hooks=hooks)

    assert marker.exists(), f"the kill point was never reached\nSTDOUT:\n{killed.stdout[-3000:]}\nSTDERR:\n{killed.stderr[-2000:]}"
    assert killed.returncode == _SIGKILL_EXIT, killed.stdout[-2000:]
    log = git(built.root, "log", "--format=%s", f"{tip_before}..refs/heads/{built.mission.topic}")
    assert "status transition WP01" in log, log
    assert _KILL_MESSAGE not in log, log

    output = _abort(built)
    assert "moved by another actor" not in output, output[-4000:]

    if _coordination_tip(built) != tip_before:
        # The killed write left its own status files modified in the coordination checkout.
        # Until the rollback classifies them as residue it refuses to move a branch checked
        # out over them and prints this remedy; follow it, then abort again. The record
        # must still explain the run's own commit on the second abort.
        assert "git -C <coordination worktree> stash" in " ".join(output.split()), output[-4000:]
        git(built.coord_worktree, "stash")
        output = _abort(built)
        assert "moved by another actor" not in output, output[-4000:]

    assert _coordination_tip(built) == tip_before, output[-4000:]
