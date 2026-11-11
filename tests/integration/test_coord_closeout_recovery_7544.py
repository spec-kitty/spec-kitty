"""#7544 Done-when: a 6-lane ``lanes_with_coord`` closeout recovers from its own commits, with no hand-run git.

A Mission created without ``--topology`` and settled to ``lanes_with_coord`` by its first
``finalize-tasks`` (six code WPs, six lanes) goes through the whole closeout on the real CLI:

* ``accept`` commits its record on the Mission (coordination) branch (#7550);
* ``consolidate`` fails late (injected before the reconciliation gate), and the one rollback
  authority restores every branch and leaves the coordination checkout clean (#7540 item 2);
* ``consolidate --abort`` tears the coordination worktree down (operator ruling on #5406), and
* the next ``consolidate`` rematerializes it and lands every lane (#5406).

A second scenario kills ``consolidate`` while it records the work packages done (#5931): ``--abort``
restores the run's own coordination commits and the next ``consolidate`` lands every lane.

The fixture is the one ``test_default_mission_consolidate_lands_primary`` uses (root checkout and
target on the unprotected branch ``work``), widened to six lanes. After the fixture build no git
command is run by hand; the only in-process interventions are the injected failure (the shared
shim's ``WP20_FAIL_BEFORE`` hook) and the kill (a ``git`` wrapper first on ``PATH``).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from tests.integration.test_consolidate_kill_done_commit_5931 import _install_kill_wrapper
from tests.integration.test_default_mission_consolidate_lands_primary import (
    _ANALYSIS,
    _SHIM,
    Built,
    _commit_all,
    _ok,
    cli,
    consolidate,
)
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import git, make_default_mission, run_finalize

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_TARGET = "work"
_SIX_LANES = tuple(f"src/mod{index}.py" for index in range(1, 7))
_LANE_IDS = "abcdef"
_LATE_FAILURE = {"WP20_FAIL_BEFORE": "_phase_reconcile_before_teardown", "WP20_FAIL_KIND": "exit"}


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


def _build(tmp_path: Path, owned: Sequence[str] = _SIX_LANES) -> Built:
    """A default Mission with one code WP per *owned* file, settled, implemented and approved."""
    mission = make_default_mission(tmp_path, owned, standing_on=_TARGET)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload.get("topology_decision")
    assert isinstance(decision, dict) and decision.get("settled_topology") == "lanes_with_coord", payload
    shim = tmp_path / "wp20_shim.py"
    shim.write_text(_SHIM, encoding="utf-8")
    built = Built(mission, shim)
    (built.coord_worktree / built.rel / "plan.md").write_text("# Plan\n", encoding="utf-8")
    _commit_all(built.coord_worktree, "plan")
    analysis = tmp_path / "analysis.md"
    analysis.write_text(_ANALYSIS, encoding="utf-8")
    _ok(cli(built, "agent", "mission", "record-analysis", "--mission", built.slug, "--input-file", str(analysis)))
    for index, path in enumerate(owned, start=1):
        wp = f"WP{index:02d}"
        _ok(cli(built, "agent", "action", "implement", wp, "--agent", "impl", "--mission", built.slug))
        lane = built.root / ".worktrees" / f"{built.slug}-lane-{_LANE_IDS[index - 1]}"
        (lane / path).parent.mkdir(parents=True, exist_ok=True)
        (lane / path).write_text(f"X = {index}\n", encoding="utf-8")
        git(lane, "add", path)
        git(lane, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", f"feat({wp})")
        for to, agent, force in (("for_review", "impl", ()), ("in_review", "rev", ()), ("approved", "rev", ("--force",))):
            _ok(cli(built, "agent", "tasks", "move-task", wp, "--to", to, "--mission", built.slug, "--agent", agent, *force, "--note", agent))
    _commit_all(built.coord_worktree, "status")
    _commit_all(built.root, "status")
    return built


def _record_matrix_verdicts(built: Built) -> None:
    matrix = json.loads((built.mission.coord_mission_dir / "acceptance-matrix.json").read_text(encoding="utf-8"))
    for criterion in matrix["criteria"]:
        _ok(
            cli(
                built,
                *("agent", "mission", "acceptance-verdict", "--mission", built.slug, "--criterion", criterion["criterion_id"]),
                *("--result", "pass", "--actor", "qa", "--evidence", "tests/", "--verification-method", "automated_test"),
            )
        )


def _assert_every_lane_landed(built: Built) -> None:
    tree = set(git(built.root, "ls-tree", "-r", "--name-only", _TARGET).splitlines())
    missing = [path for path in _SIX_LANES if path not in tree]
    assert not missing, f"lanes missing on {_TARGET}: {missing}"


def _output(proc: object) -> str:
    return f"{getattr(proc, 'stdout', '')}{getattr(proc, 'stderr', '')}"


@pytest.mark.timeout(1800)
def test_closeout_accept_late_failure_abort_rerun(tmp_path: Path) -> None:
    built = _build(tmp_path)
    _record_matrix_verdicts(built)

    # (1) accept commits its record on the Mission branch (#7550).
    accepted = cli(built, "accept", "--mission", built.slug, "--mode", "local", "--actor", "qa", "--lenient")
    _ok(accepted)
    assert "Traceback" not in _output(accepted)
    assert git(built.coord_worktree, "status", "--porcelain") == ""

    # (2) a late-phase failure: the one rollback authority restores every branch.
    target_before = git(built.root, "rev-parse", _TARGET)
    topic_before = git(built.root, "rev-parse", built.mission.topic)
    failed = consolidate(built, hooks=_LATE_FAILURE)
    out = _output(failed)
    assert failed.returncode != 0, out
    assert "NOT restored" not in out and "left as found" not in out, out
    assert git(built.root, "rev-parse", _TARGET) == target_before, out
    assert git(built.root, "rev-parse", built.mission.topic) == topic_before, out
    assert git(built.coord_worktree, "status", "--porcelain") == "", out

    # (3) --abort (tears the coordination worktree down, by ruling).
    aborted = cli(built, "consolidate", "--mission", built.slug, "--abort")
    assert aborted.returncode == 0, _output(aborted)

    # (4) the next consolidate rematerializes the coordination worktree and lands every lane (#5406).
    rerun = consolidate(built)
    _ok(rerun)
    assert "git checkout" not in _output(rerun)
    _assert_every_lane_landed(built)


@pytest.mark.timeout(1800)
def test_closeout_after_kill_in_done_commits(tmp_path: Path) -> None:
    built = _build(tmp_path)
    topic_before = git(built.root, "rev-parse", built.mission.topic)
    env, marker = _install_kill_wrapper(tmp_path)

    killed = consolidate(built, hooks=env)
    assert marker.exists() and killed.returncode != 0, _output(killed)

    # (1) --abort explains the run's own done commits (#5931) and resyncs the coordination checkout (#7540 item 2).
    aborted = cli(built, "consolidate", "--mission", built.slug, "--abort")
    out = _output(aborted)
    assert aborted.returncode == 0, out
    assert "moved by another actor" not in out and "left as found" not in out, out
    assert git(built.root, "rev-parse", built.mission.topic) == topic_before, out

    # (2) the next consolidate lands every lane.
    _ok(consolidate(built))
    _assert_every_lane_landed(built)
