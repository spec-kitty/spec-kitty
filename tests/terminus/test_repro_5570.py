"""Repro #5570 — teardown must not delete a coordination branch that moved after the gate.

The teardown gate (``_enforce_projection_teardown_gate``) compare-and-swaps the coordination
tip once, then the retrospective is persisted, the coordination worktree is destroyed, and
only then ``_delete_mission_branch`` ran an unconditional ``git branch -D``. A status commit
landing in that window (a concurrent ``agent status emit``) was never projected onto the target
and became unreachable: the branch was deleted over it and the command exited 0.

Expected behaviour: the branch delete is a compare-and-swap at the gated tip. A moved tip
keeps the branch (with the late commit), keeps the coordination marker, and ``consolidate``
exits non-zero naming the branch and the moved SHA.

Driven through the REAL ``spec-kitty consolidate`` CLI in a subprocess. The only seam is a
concurrency injection: a driver wraps ``coordination.teardown._destroy_coordination_worktree``
so that a real commit is made on the coordination branch (from inside its worktree, exactly
where a concurrent status emit would land) immediately before the REAL destroy runs. No other
product code is replaced.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus
from tests.terminus.conftest import _cli_env as cli_env
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LATE_SHA_FILE = "late-commit-sha.txt"

# Runs the real CLI after wrapping up to two seams, each calling the REAL function:
# * the destroy leg first lands a real commit on the coordination branch (inside its worktree);
# * with FOREIGN_ON_RETRO set, the retrospective bookkeeping commit is followed by a FOREIGN
#   commit on the target (a concurrent operator commit between our commit and the anchor carry).
_INJECTION_DRIVER = """
import os
import subprocess
import sys
from pathlib import Path

import specify_cli.coordination.teardown as teardown

real_destroy = teardown._destroy_coordination_worktree


def destroy_after_late_commit(repo_root, mission_slug, mid8):
    worktree = Path(os.environ["COORD_WORKTREE"])
    note = worktree / "kitty-specs" / mission_slug / os.environ.get("LATE_NOTE_NAME", "late-status-emit.md")
    note.write_text("late status emit\\n", encoding="utf-8")
    late_event = os.environ.get("LATE_EVENT_JSON")
    if late_event:
        events = worktree / "kitty-specs" / mission_slug / "status.events.jsonl"
        with events.open("a", encoding="utf-8") as handle:
            handle.write(late_event + "\\n")
    def git(*args):
        return subprocess.run(["git", "-C", str(worktree), *args], check=True, capture_output=True, text=True)
    git("add", "-A")
    git("-c", "user.name=Late Emit", "-c", "user.email=late@example.com", "commit", "-q", "-m", "late status emit")
    Path(os.environ["LATE_SHA_FILE"]).write_text(git("rev-parse", "HEAD").stdout.strip(), encoding="utf-8")
    return real_destroy(repo_root, mission_slug, mid8)


teardown._destroy_coordination_worktree = destroy_after_late_commit

if os.environ.get("FOREIGN_ON_RETRO"):
    import specify_cli.git.bookkeeping_commit as bookkeeping

    real_commit = bookkeeping.commit_merge_bookkeeping

    def commit_then_foreign(**kwargs):
        result = real_commit(**kwargs)
        if "capture mission retrospective" in kwargs.get("message", ""):
            repo = str(kwargs["repo_root"])
            (Path(repo) / "foreign.txt").write_text("foreign\\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "foreign.txt"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", repo, "-c", "user.name=Foreign", "-c", "user.email=foreign@example.com", "commit", "-q", "-m", "foreign target commit"],
                check=True,
                capture_output=True,
            )
        return result

    bookkeeping.commit_merge_bookkeeping = commit_then_foreign

from specify_cli import main

argv = ["spec-kitty", "consolidate"]
if os.environ.get("RESUME"):
    argv.append("--resume")
sys.argv = [*argv, "--mission", os.environ["MISSION_SLUG"], "--yes"]
main()
"""


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with Rich's terminal line wrapping collapsed to single spaces."""
    return " ".join((result.stdout + result.stderr).split())


def _branch_exists(mission: CoordMission, branch: str) -> bool:
    ref = f"refs/heads/{branch}"
    return subprocess.run(["git", "-C", str(mission.repo), "rev-parse", "--verify", ref], capture_output=True, check=False).returncode == 0


def _consolidate_with_late_commit(
    mission: CoordMission,
    *,
    late_event: str | None = None,
    resume: bool = False,
    note_name: str = "late-status-emit.md",
    sha_file: str = _LATE_SHA_FILE,
    foreign_on_retro: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = cli_env(mission.home)
    if late_event is not None:
        env["LATE_EVENT_JSON"] = late_event
    if resume:
        env["RESUME"] = "1"
    if foreign_on_retro:
        env["FOREIGN_ON_RETRO"] = "1"
    env["LATE_NOTE_NAME"] = note_name
    # Deterministic path: after a refusal the worktree is gone until the resume rematerializes it.
    env["COORD_WORKTREE"] = str(mission.repo / ".worktrees" / f"{mission.slug}-coord")
    env["LATE_SHA_FILE"] = str(mission.repo / sha_file)
    env["MISSION_SLUG"] = mission.slug
    return subprocess.run(
        [sys.executable, "-c", _INJECTION_DRIVER],
        cwd=str(mission.repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def test_5570_commit_landing_after_the_gate_survives_and_consolidate_fails_loud(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570A")

    result = _consolidate_with_late_commit(mission)

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    late_sha_file = mission.repo / _LATE_SHA_FILE
    assert late_sha_file.exists(), f"fixture invalid: the injection seam never ran\n{output}"
    late_sha = late_sha_file.read_text(encoding="utf-8").strip()
    assert result.returncode != 0, f"#5570: consolidate exited 0 after deleting a coordination branch that moved past the gate\n{output}"
    assert _branch_exists(mission, mission.coord_branch), f"#5570: the coordination branch was deleted over the late commit\n{output}"
    assert mission.rev(mission.coord_branch) == late_sha, "the late commit must still be the coordination tip"
    combined = _flat(result)
    assert mission.coord_branch in combined, f"the refusal must name the branch\n{output}"
    assert late_sha[:12] in combined, f"the refusal must name the moved tip\n{output}"


_RESUME_ADVICE = "spec-kitty consolidate --resume"


def _advised_commands(combined: str) -> list[str]:
    """The ``spec-kitty ...`` commands the refusal prints, exactly as an operator would copy them."""
    return re.findall(r"`(spec-kitty [^`]+)`", combined)


def _target_status_events(mission: CoordMission) -> str:
    return git_out(mission.repo, "show", f"{mission.target_branch}:kitty-specs/{mission.slug}/status.events.jsonl")


_LATE_EVENT_ID = "01HXYZ55700000000000000099"
_LATE_EVENT = json.dumps(
    {
        "actor": "late-emitter",
        "at": "2026-10-03T18:30:00+00:00",
        "event_id": _LATE_EVENT_ID,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": "terminus-01M5570C",
        "force": True,
        "from_lane": "done",
        "reason": "late status emit",
        "review_ref": None,
        "to_lane": "in_progress",
        "wp_id": "WP01",
    },
    sort_keys=True,
)


def test_5570_printed_recovery_advice_reaches_an_honest_end_state(tmp_path: Path) -> None:
    """Follow the refusal's advice verbatim: it must work, or the refusal must say what does.

    The refusal tells the operator how to finish. By then the retrospective has been persisted and
    the coordination worktree destroyed, so the advice is only honest if running it really ends with
    the late commit projected onto the target (its file AND its status event) and the coordination
    branch deleted only after that, with the paired marker and the consolidation record cleaned up.
    """
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570C")
    refused = _consolidate_with_late_commit(mission, late_event=_LATE_EVENT)
    assert refused.returncode != 0, "fixture invalid: the first consolidate must refuse"
    assert _branch_exists(mission, mission.coord_branch)
    late_sha = (mission.repo / _LATE_SHA_FILE).read_text(encoding="utf-8").strip()

    advice = _flat(refused)
    commands = [c for c in _advised_commands(advice) if "consolidate" in c]
    assert commands, f"the refusal must print a concrete consolidate command\n{advice}"
    assert _RESUME_ADVICE in commands[-1], f"the refusal must advise {_RESUME_ADVICE!r}\n{advice}"

    resumed = run_terminus(mission, [*commands[-1].split()[1:], "--mission", mission.slug, "--yes"])
    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"

    assert resumed.returncode == 0, f"#5570: the advised resume must finish teardown\n{output}"
    assert "late-status-emit.md" in git_out(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch), (
        f"#5570: the late coordination commit was not projected onto the target\n{output}"
    )
    assert _LATE_EVENT_ID in _target_status_events(mission), f"#5570: the late status event never reached the target's event log\n{output}"
    assert not _branch_exists(mission, mission.coord_branch), f"the coordination branch must be deleted once the late commit is on the target\n{output}"
    assert late_sha, "fixture invalid: no late commit recorded"
    meta = json.loads(git_out(mission.repo, "show", f"{mission.target_branch}:kitty-specs/{mission.slug}/meta.json"))
    assert "coordination_branch" not in meta, "the coordination marker must be flattened once the branch is gone"
    assert git_out(mission.repo, "status", "--porcelain", "--", "kitty-specs").strip() == "", "the resume must leave the mission dir clean"
    assert not list((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json")), "a finished teardown must clear the consolidation record"


def _persisted_anchor(mission: CoordMission) -> str | None:
    state = json.loads((mission.repo / ".kittify" / "runtime" / "merge" / mission.mission_id / "state.json").read_text(encoding="utf-8"))
    anchor = state.get("reconciliation_passed_target_sha")
    return anchor if isinstance(anchor, str) else None


def test_5570_a_foreign_target_commit_is_never_stamped_verified(tmp_path: Path) -> None:
    """The PASS anchor follows only the commit THIS run made, never whatever the target tip is by then.

    A foreign commit lands on the target right after our retrospective bookkeeping commit. The
    anchor must stay at the verified tip, so the advised ``--resume`` runs the full claim again
    (refusing, fail-closed) instead of skipping reconciliation over the unverified foreign commit.
    """
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570D")
    refused = _consolidate_with_late_commit(mission, foreign_on_retro=True)
    assert refused.returncode != 0, "fixture invalid: the first consolidate must refuse"
    foreign_sha = mission.rev(mission.target_branch)
    assert git_out(mission.repo, "log", "-1", "--format=%s", foreign_sha).strip() == "foreign target commit", (
        "fixture invalid: the foreign commit must be the target tip"
    )
    verified_tip = git_out(mission.repo, "rev-parse", f"{foreign_sha}~2").strip()
    assert _persisted_anchor(mission) == verified_tip, "the anchor must not follow a foreign target commit"

    resumed = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])
    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"

    assert resumed.returncode != 0, f"#5570: resume skipped full reconciliation over a foreign target commit\n{output}"
    assert "Reconciliation refused" in _flat(resumed), output
    assert mission.rev(mission.target_branch) == foreign_sha, "the foreign commit must stay on the target"
    assert _branch_exists(mission, mission.coord_branch), "the coordination branch must be kept while the claim cannot be verified"


def test_5570_coordination_branch_moving_again_after_the_late_projection_refuses_again(tmp_path: Path) -> None:
    """A commit landing after the resume's own projection hits the compare-and-swap delete: kept, non-zero, then recoverable."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570E")
    first = _consolidate_with_late_commit(mission)
    assert first.returncode != 0, "fixture invalid: the first consolidate must refuse"

    second = _consolidate_with_late_commit(mission, resume=True, note_name="late-again.md", sha_file="late-again-sha.txt")
    output = f"stdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    again_file = mission.repo / "late-again-sha.txt"
    assert again_file.exists(), f"fixture invalid: the resume never reached the teardown seam\n{output}"
    again_sha = again_file.read_text(encoding="utf-8").strip()

    assert second.returncode != 0, f"#5570: the resume deleted a branch that moved after its projection\n{output}"
    assert _branch_exists(mission, mission.coord_branch), f"the branch must be kept\n{output}"
    assert mission.rev(mission.coord_branch) == again_sha, "the second late commit must still be the branch tip"
    assert again_sha[:12] in _flat(second), f"the refusal must name the moved tip\n{output}"
    assert "late-status-emit.md" in git_out(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch), "the first late commit was projected"
    assert "late-again.md" not in git_out(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch)

    third = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])
    output = f"stdout:\n{third.stdout}\nstderr:\n{third.stderr}"
    assert third.returncode == 0, f"the next resume must finish\n{output}"
    target_files = git_out(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch)
    assert "late-again.md" in target_files and "late-status-emit.md" in target_files, output
    assert not _branch_exists(mission, mission.coord_branch)


def test_5570_unmoved_coordination_branch_is_still_deleted(tmp_path: Path) -> None:
    """Positive control: with no commit in the window the real consolidate still tears down."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570B")

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, f"a clean consolidate must succeed\n{output}"
    assert not _branch_exists(mission, mission.coord_branch), f"an unmoved coordination branch must still be deleted\n{output}"
