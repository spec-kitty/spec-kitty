"""``consolidate --abort`` restores the pre-mutation snapshot before it clears the record.

Contract (FR-005/FR-007/FR-011, SC-005/SC-006, ``contracts/rollback-authority.md``):
``--abort`` restores every snapshotted branch through the single CAS rollback
authority FIRST, and clears the record only after a full restore. Without that,
the NEXT fresh run would capture the ADVANCED base as its own "pre-run" state.

Trigger: the #5385 shape. A LANES mission whose target is the protected ``main``
raises ``BookkeepingPolicyRefused`` in ``_phase_record_done_and_project`` AFTER the
squash advanced the target and AFTER the post-mutation tips were recorded for the
``_phase_mission_to_target`` phase. Since #5385 the driver's rollback door restores
that crash in-process, so a real run only leaves crash residue (advanced ``main`` +
advanced mission branch + a resumable ``state.json``) when the process dies between
the failure and the in-process rollback. :func:`_run_hard_killed` models exactly that
hard kill: it runs the REAL CLI in a subprocess whose ``_report_rollback`` prints the
original traceback and calls ``os._exit(137)`` -- everything before it (git, the
policy refusal, the recorded tips) is real. The same wrapper disables the up-front
protected-target preflight (#5385 WP02), which would otherwise refuse this shape
before any branch moves.

Cases that a real CLI run cannot produce say so in their docstring:

* the pre-fix record deletes the new keys from a REAL ``state.json`` (models a record
  written by the previous release -- there is no other way to obtain one);
* the FR-011 verified landing reuses ``test_repro_5021``'s real mid-teardown fixture and
  adds the real pre-run tips as ``pre_mutation_refs`` (that fixture predates the snapshot).

Provenance: #5318 (abort), #5338 (abort after a deleted lane branch), #5385 (crash trigger).

One smoke per behaviour family (#5618 part 2): this file keeps the end-to-end proof
that ``--abort`` restores every snapshotted branch after a hard-killed run. The other
abort cases are pinned at the seam, each proven by a planted break that turns its guard
red: another actor's commit kept (CAS ``live != post``), a moved branch with no recorded
post tip, an operator's carrier-lane fix kept (``_restore_target``), a verified landing
kept, a pre-fix record's notice, a live foreign merge lock
(``test_abort_with_a_snapshot_refuses_while_a_live_foreign_merge_holds_the_lock``), the post-tip carry-forward
across a crashed resume, and a deleted lane branch. Guards:
``tests/consolidation/test_rollback_authority.py``,
``tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py``,
``tests/consolidation/test_executor_rollback_wiring.py``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from specify_cli.consolidation.state import (
    get_state_path,
)
from tests.terminus.conftest import (
    _SRC,
    CoordMission,
    blob_present_at,
    run_terminus,
)
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import (
    flat,
    ref_shas,
    restored_pairs,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def _abort(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])


def _state_path(mission: CoordMission) -> Path:
    return get_state_path(mission.repo, mission.mission_id)


# Replaces the in-process rollback with a hard kill: print the original failure (the
# traceback the operator would see), flush, and die before any ref is restored.
_HARD_KILL = """
import os, sys, traceback
import specify_cli
from specify_cli.consolidation import executor

def _killed_before_rollback(*_args, **_kwargs):
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(137)

executor._report_rollback = _killed_before_rollback
executor._refuse_protected_status_target_or_continue = lambda *_a, **_k: None  # WP02 (#5385): let the protected shape reach the post-squash crash
sys.argv = ["spec-kitty", *sys.argv[1:]]
specify_cli.main()
"""


def _run_hard_killed(mission: CoordMission, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the REAL CLI like :func:`run_terminus`, but kill the process at the rollback door (models a SIGKILL)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC)
    env["HOME"] = str(mission.home)
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run([sys.executable, "-c", _HARD_KILL, *args], cwd=str(mission.repo), env=env, capture_output=True, text=True, check=False)


def _crashed_lanes_run(tmp_path: Path, mid8: str) -> tuple[CoordMission, dict[str, str]]:
    """LANES mission on protected ``main``: a post-squash crash (#5385) hard-killed before the rollback, refs advanced."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8=mid8)
    before = ref_shas(mission)
    result = _run_hard_killed(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    assert result.returncode != 0, f"fixture precondition: the run must crash. output={output}"
    assert "PROTECTED_BRANCH_REFUSED" in output, f"fixture precondition: the crash must be the #5385 policy refusal. output={output}"
    after = ref_shas(mission)
    assert after["target"] != before["target"], "fixture precondition: the squash must have advanced the target before the crash"
    assert after["coord"] != before["coord"], "fixture precondition: the mission branch must have advanced (lane merges + bake)"
    assert _state_path(mission).exists(), "fixture precondition: a crashed run leaves a resumable record"
    return mission, before


def test_abort_restores_every_snapshotted_branch(tmp_path: Path) -> None:
    mission, before = _crashed_lanes_run(tmp_path, "01M5318A")

    result = _abort(mission)
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode == 0, f"a fully restored abort exits 0. output={output}"
    assert after["target"] == before["target"], f"--abort left the target advanced ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"--abort left the mission branch advanced. output={output}"
    assert {k: v for k, v in after.items() if k.startswith("lane:")} == {k: v for k, v in before.items() if k.startswith("lane:")}
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "the squashed content must be gone from the target"
    assert not _state_path(mission).exists(), "the record is cleared only after the restore"
    assert restored_pairs(output, mission.target_branch), f"the report must name the target restore. output={output}"
    assert restored_pairs(output, mission.coord_branch), f"the report must name the mission-branch restore. output={output}"
