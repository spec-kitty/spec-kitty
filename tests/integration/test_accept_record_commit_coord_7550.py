"""#7550: ``spec-kitty accept`` commits its record on the Mission branch of a settled default Mission.

A Mission created without ``--topology`` and settled to ``lanes_with_coord`` keeps its PRIMARY
partition (``meta.json`` included) on its topic branch, held by the coordination worktree, until
``consolidate`` lands it. The repository root checkout stands on the Mission's unprotected target
branch. ``accept`` writes its acceptance record into that ``meta.json`` (the placement seam's
``feature_dir``), so the record must be committed there too, and ``accepted_from_commit`` must name
the tip of the branch the record describes (the Mission branch), not the root checkout's target.

The test drives the real CLI (the shared fixture of ``test_default_mission_consolidate_lands_primary``:
three code WPs, every one approved, target ``work`` unprotected).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import Built, _ok, build, cli
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


def _record_matrix_verdicts(built: Built) -> None:
    """Record a passing verdict for every acceptance-matrix criterion (what an operator does before accept)."""
    matrix = json.loads((built.mission.coord_mission_dir / "acceptance-matrix.json").read_text(encoding="utf-8"))
    for criterion in matrix["criteria"]:
        _ok(
            cli(
                built,
                *("agent", "mission", "acceptance-verdict", "--mission", built.slug, "--criterion", criterion["criterion_id"]),
                *("--result", "pass", "--actor", "qa", "--evidence", "tests/", "--verification-method", "automated_test"),
            )
        )


@pytest.mark.p0_repro(issue=7544)
@pytest.mark.timeout(900)
def test_accept_commits_record_on_mission_branch_of_settled_default_mission(tmp_path: Path) -> None:
    built = build(tmp_path)
    _record_matrix_verdicts(built)
    coord = built.coord_worktree
    topic = built.mission.topic
    root_head_before = git(built.root, "rev-parse", "HEAD")
    mission_tip_before = git(built.root, "rev-parse", topic)

    # --lenient: the fixture repository has no tests/, docs/ or contracts/ directory; the path
    # conventions are not what this test is about.
    proc = cli(built, "accept", "--mission", built.slug, "--mode", "local", "--actor", "qa", "--lenient")

    _ok(proc)
    assert "Traceback" not in proc.stdout + proc.stderr
    touched = git(built.root, "log", "--format=", "--name-only", f"{mission_tip_before}..{topic}").splitlines()
    assert f"{built.rel}/meta.json" in touched, "accept did not commit its record on the Mission branch"
    assert git(coord, "status", "--porcelain") == "", "accept left the coordination worktree dirty"
    assert git(built.root, "status", "--porcelain") == "", "accept left the repository root checkout dirty"
    assert git(built.root, "rev-parse", "HEAD") == root_head_before, "accept moved the repository root checkout"
    meta = json.loads(git(built.root, "show", f"{topic}:{built.rel}/meta.json"))
    assert meta["accepted_from_commit"] == mission_tip_before, "accepted_from_commit does not name the Mission branch tip"
