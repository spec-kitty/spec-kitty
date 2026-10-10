"""Red-first reproduction of #5966: ``consolidate --abort`` of Mission A destroys Mission B's edits.

Two Missions share one repository. Mission A (``lanes`` topology, protected ``main``) is
hard-killed after its squash landed on the target, leaving a persisted pre-mutation snapshot
(the ``tests/terminus/test_abort_restores_snapshot.py`` crash shape, through the real CLI).
Mission B has uncommitted work in the repository root checkout: a reviewer's addition to a
tracked ``review-cycle-1.md`` and an operator's addition to a tracked ``traces/notes.md``.

``consolidate --abort`` restores ``main`` through ``rollback.py::_restore_one``, which passes the
bare ``is_toolchain_generated_churn`` (no Mission, no checkout role) as the residue predicate.
That treats Mission B's files as coordination residue, so the resync's dirty check lets
``git reset --hard`` run and the uncommitted edits are gone, with exit 0.

The edits are to TRACKED files because ``git reset --hard`` leaves untracked files alone; a
modified tracked file is what the reset destroys.

The fixed behaviour is a refusal that names the files and leaves the checkout untouched, so the
red test asserts survival first and then that refusal (non-zero exit naming both paths).
The red test is a ``p0_repro`` (ADR 2026-07-17-1) and runs only in the nightly ``p0-repro`` lane
(``SPEC_KITTY_RUN_P0_REPRO=1``); the fix PR removes the marker. The positive control is green
today and must stay green.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat
from tests.terminus.test_abort_restores_snapshot import _run_hard_killed

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_OTHER_MISSION = "kitty-specs/other-mission-01M5966B"
_REVIEW_CYCLE = f"{_OTHER_MISSION}/tasks/WP01-other/review-cycle-1.md"
_TRACE_NOTES = f"{_OTHER_MISSION}/traces/notes.md"
_REVIEW_COMMITTED = "# Review cycle 1\nverdict: rejected\n"
_REVIEW_EDITED = _REVIEW_COMMITTED + "feedback: the retry path swallows the timeout.\n"
_NOTES_COMMITTED = "# notes\n"
_NOTES_EDITED = _NOTES_COMMITTED + "hand-written operator trace, not yet committed.\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _abort(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])


def _crashed_mission_a_next_to_mission_b(tmp_path: Path) -> CoordMission:
    """Mission A hard-killed after its squash landed, with Mission B's files committed on ``main`` beforehand."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5966A")
    for relative, content in ((_REVIEW_CYCLE, _REVIEW_COMMITTED), (_TRACE_NOTES, _NOTES_COMMITTED)):
        path = mission.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(mission.repo, "add", "-A")
    _git(mission.repo, "commit", "-qm", "chore(fixture): Mission B review cycle and traces")

    crashed = _run_hard_killed(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert crashed.returncode != 0, f"fixture invalid: the run must crash after the squash. output={flat(crashed)}"
    assert (mission.repo / ".kittify" / "runtime" / "merge" / mission.mission_id / "state.json").is_file(), (
        "fixture invalid: a crashed run leaves a snapshot record"
    )
    return mission


@pytest.mark.p0_repro(issue=5966)
@pytest.mark.regression
def test_5966_abort_of_mission_a_keeps_mission_b_uncommitted_files(tmp_path: Path) -> None:
    mission = _crashed_mission_a_next_to_mission_b(tmp_path)
    review_cycle, notes = mission.repo / _REVIEW_CYCLE, mission.repo / _TRACE_NOTES
    review_cycle.write_text(_REVIEW_EDITED, encoding="utf-8")
    notes.write_text(_NOTES_EDITED, encoding="utf-8")

    result = _abort(mission)

    output = flat(result)
    assert review_cycle.read_text(encoding="utf-8") == _REVIEW_EDITED, (
        f"#5966: Mission B's uncommitted review-cycle edit was destroyed by Mission A's --abort. output={output}"
    )
    assert notes.read_text(encoding="utf-8") == _NOTES_EDITED, (
        f"#5966: Mission B's uncommitted traces/notes.md edit was destroyed by Mission A's --abort. output={output}"
    )
    assert result.returncode != 0, f"#5966: --abort must refuse (non-zero) rather than reset another Mission's work. output={output}"
    assert "review-cycle-1.md" in output and "notes.md" in output, f"the refusal must name Mission B's files. output={output}"


@pytest.mark.regression
def test_5966_control_mission_a_stale_status_copy_alone_is_cleaned_by_abort(tmp_path: Path) -> None:
    """The resync still cleans Mission A's own regenerated status copy, so the fix must not turn residue into a blocker."""
    mission = _crashed_mission_a_next_to_mission_b(tmp_path)
    events = mission.feature_dir / "status.events.jsonl"
    committed = events.read_text(encoding="utf-8")
    events.write_text(committed + "\n", encoding="utf-8")
    assert _git(mission.repo, "status", "--porcelain", "--", "kitty-specs").split() == ["M", str(events.relative_to(mission.repo))], (
        "fixture invalid: only Mission A's status log may be dirty"
    )

    result = _abort(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _git(mission.repo, "status", "--porcelain", "--", "kitty-specs") == "", f"the stale status copy must be cleaned. output={output}"
    assert events.read_text(encoding="utf-8") == committed
