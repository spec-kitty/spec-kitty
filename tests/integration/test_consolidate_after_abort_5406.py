"""#5406 / #7540 item 3: the ``consolidate`` after ``consolidate --abort`` rematerializes the coordination worktree.

``consolidate --abort`` keeps its coordination teardown (operator ruling 2026-09-30): it removes
the coordination worktree. The next ``consolidate`` must rematerialize that worktree on demand,
from the local coordination branch, and land the Mission. Before the fix it refused with the
single_branch remedy ("lanes.json is not on the current checkout ... Run `git checkout <branch>`"),
which is wrong for a ``lanes_with_coord`` Mission whose branch is its coordination branch.

Drives the real ``spec-kitty`` CLI through the fixture of
``test_default_mission_consolidate_lands_primary`` (three code WPs settled ``lanes_with_coord``,
root checkout and target on the unprotected branch ``work``, every WP approved).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import (
    _TARGET,
    _ok,
    _quiet_status_fanout,  # noqa: F401 -- autouse fixture, imported so it applies here too
    build,
    consolidate,
)
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import THREE_LANES, git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_FAIL_AT_RECONCILE = {"WP20_FAIL_BEFORE": "_phase_reconcile_before_teardown", "WP20_FAIL_KIND": "exit"}


@pytest.mark.timeout(900)
def test_consolidate_after_abort_rematerializes_coordination_worktree(tmp_path: Path) -> None:
    built = build(tmp_path)

    failed = consolidate(built, hooks=_FAIL_AT_RECONCILE)
    assert failed.returncode != 0, failed.stdout[-3000:]

    aborted = _ok(consolidate(built, "--abort"))
    assert not built.coord_worktree.exists(), aborted.stdout[-3000:]

    proc = consolidate(built)
    assert "git checkout" not in proc.stdout + proc.stderr, proc.stdout[-3000:]
    _ok(proc)
    for owned in THREE_LANES:
        git(built.root, "cat-file", "-e", f"{_TARGET}:{owned}")
