"""#7120: a work package implemented on the target branch reaches a refusal it can act on.

The recorded shape: a `lanes` Mission whose single agent implemented on the target/topic branch, so
no lane worktree and no lane branch was ever created. `move-task --to for_review` refused
`IMPLEMENTATION_UNREADABLE` with "Make the lane branch and the recorded planning commit readable,
then retry." — an instruction that cannot be carried out, because there is no lane branch; creating
one would fabricate the evidence the gate exists to check. An agent loops, and the Mission record
stays `in_progress` after the code shipped.

This case drives the REAL CLI end to end in an isolated HOME and pins what the refusal must now say
(option 1 of the issue: name the shape, name a next step that exists) and what it must still do: refuse,
leave the work package where it was, and fabricate nothing. Widening the evidence window for this
shape (option 2) is a policy decision that remains open on #7120 and is deliberately not exercised
here.
"""

from __future__ import annotations

import pytest

from tests.integration.test_6715_consolidate_lane_evidence import _commit_specs, _git, _sk, lanes_of, setup_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(600)]


def test_a_lane_mission_implemented_on_the_target_branch_names_the_shape(tmp_path) -> None:
    mission = setup_mission(tmp_path, "lanes")

    # The implementation lands on the target branch, exactly as a single agent working in the repo
    # root does; `agent action implement` is never run, so no lane worktree or lane branch exists.
    target = mission.repo / "tools" / "check.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# WP02\n", encoding="utf-8")
    _git(mission.repo, "add", "--", "tools/check.sh")
    _git(mission.repo, "commit", "-qm", "feat(WP02): implement on the target branch")
    _sk(mission, "agent", "tasks", "move-task", "WP02", "--to", "in_progress", "--agent", "alice", "--note", "claimed", "--mission", mission.slug, check=True)
    _sk(mission, "agent", "tasks", "mark-status", "T2", "--status", "done", "--mission", mission.slug, check=True)
    _commit_specs(mission.repo)
    assert not [line for line in _git(mission.repo, "branch", "--list", "kitty/*").splitlines() if "lane" in line], "fixture: no lane branch may exist"

    moved = _sk(mission, "agent", "tasks", "move-task", "WP02", "--to", "for_review", "--agent", "alice", "--note", "done", "--mission", mission.slug)
    raw = moved.stdout + moved.stderr
    # The CLI wraps its output to the terminal width, so a phrase can straddle a line break;
    # compare on normalized whitespace or an assertion about a sentence is vacuous.
    output = " ".join(raw.split())

    assert moved.returncode != 0, f"the gate must still refuse a window it cannot read:\n{raw[-2500:]}"
    assert "IMPLEMENTATION_UNREADABLE" in output, raw[-2500:]
    assert "no lane of this Mission has a branch here" in output, "the local fact is stated as such:\n" + raw[-2500:]
    assert "without ever creating a lane branch" in output, "the target-branch shape is named:\n" + raw[-2500:]
    assert "no supported recovery" in output and "stop retrying" in output, "the refusal says there is nothing to retry:\n" + raw[-2500:]
    assert "issues/7120" in output, "the escalation is tracked:\n" + raw[-2500:]
    assert "fabricates the evidence it checks" in output, "manufacturing a lane window is named as fabrication:\n" + raw[-2500:]
    assert "Make the lane branch and the recorded planning commit readable, then retry." not in output, (
        "the unsatisfiable instruction is gone from this shape:\n" + raw[-2500:]
    )

    assert lanes_of(mission)["WP02"] == "in_progress", "nothing moved: a diagnosable refusal is still a refusal"
    assert not [line for line in _git(mission.repo, "branch", "--list", "kitty/*").splitlines() if "lane" in line], "nothing was fabricated"
