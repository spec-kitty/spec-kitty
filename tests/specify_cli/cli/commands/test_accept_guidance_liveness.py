"""#2745 (facet 2, FR-014) — ``accept`` guidance-liveness regression.

Mission ``terminus-safety-invariant-01M2XFT7`` / WP07, T020. #2745 reported
that ``spec-kitty accept`` on a mission with no lane branch refused with
impossible "materialize-then-retry" guidance instead of naming a real,
followable escape hatch. Prior investigation (research.md facet-2) found the
old pre-flight hard reject (``assert_not_protected_branch`` /
``ProtectedBranchCommitError`` — "Run status commit operations from the
mission lane branch/worktree", commit ``a79789055d``'s predecessor) was
already removed at ``accept.py:1005-1012`` ("the protected-primary guard is
no longer a hard reject here"). This module is that liveness confirmation.

**Outcome: VERIFIED-ALREADY-FIXED.** This probe is GREEN on current main /
this branch with no product change to ``accept.py`` needed. The scenario it
reproduces (a mission with no lane/mission branch checked out — HEAD still on
the mission's own protected ``target_branch`` — running ``accept`` to
completion) now routes the acceptance-meta commit through
``commit_for_mission`` (``acceptance/__init__.py::_commit_acceptance_meta_via_router``
→ ``coordination/commit_router.py::_commit_partition_group``), which derives
its refusal from the single ``resolve_surface_authority`` authority
(``coordination/surface_authority.py`` rule 3) instead of the old hardcoded
``assert_not_protected_branch`` deadlock. Its remedy names a concrete,
followable command:

    Check out or create a non-protected feature branch, then persist it onto
    this mission with: 'spec-kitty agent mission finalize-tasks --mission
    <slug> --target-branch <feature-branch>'. ... To commit on the current
    protected branch anyway, set SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1.

— genuinely followable (a real subcommand + flags, or a real env var), unlike
the retired "Run status commit operations from the mission lane branch/
worktree" instruction, which was impossible to satisfy for a mission that has
no lane branch/worktree to run from.

This probe is an ENDURING regression guard (not a throwaway): it pins that
``accept``'s protected-primary-no-lane-branch guidance stays substantively
followable and never regresses back to the impossible instruction.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from kernel.clock import now_utc_iso

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event

# Marked for mutmut sandbox skip — subprocess/git-backed fixture, mirroring
# the sibling accept CLI regression suites (test_accept_clean_tree.py etc.).
pytestmark = [pytest.mark.regression, pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "2745-accept-guidance-liveness"
_MISSION_ID = "01K5ACCEPTGUIDANCELIVENESS0"

#: The impossible, historically-emitted instruction (retired
#: ``assert_not_protected_branch`` / ``ProtectedBranchCommitError`` wording).
#: A mission with no lane branch/worktree cannot "run from" one — this is the
#: defect #2745 (facet 2) reported. Must NEVER reappear in accept's output.
_IMPOSSIBLE_INSTRUCTION_FRAGMENT = "mission lane branch/worktree"

#: The genuinely followable escape hatch the current code names (a real
#: subcommand + flags an operator can copy-paste and run).
_FOLLOWABLE_COMMAND_FRAGMENT = "spec-kitty agent mission finalize-tasks --mission"
_FOLLOWABLE_FLAG_FRAGMENT = "--target-branch <feature-branch>"
#: The alternative followable escape hatch: a real, documented env var.
_FOLLOWABLE_ENV_HATCH_FRAGMENT = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _build_accept_ready_mission_with_no_lane_branch(repo_root: Path) -> Path:
    """Build an accept-ready mission whose HEAD never leaves the mission's
    OWN protected ``target_branch`` — i.e. no lane/mission branch was ever
    checked out (the #2745 facet-2 scenario). Mirrors
    ``test_accept_clean_tree.py::_create_lane_feature`` except it
    deliberately OMITS that fixture's final ``git checkout -b
    <mission-branch>`` step, so ``accept`` runs with HEAD still on the
    protected primary.
    """
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "2745",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "Accept Guidance Liveness",
        "mission_type": "software-dev",
        # target_branch == "main": the mission's OWN branch IS the protected
        # primary — there is no separate lane/mission branch to check out.
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "subtasks: []\n"
        "---\n"
        "# WP01\nDone.\n"
    )

    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTGUIDANCELIVE000",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="test-agent",
            force=False,
            execution_mode="direct_repo",
            policy_metadata=build_claim_policy_metadata(
                shell_pid=12345,
                shell_pid_created_at="2026-01-01T00:00:00+00:00",
                agent="test-agent",
            ),
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTGUIDANCELIVE001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )
    materialize(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=f"kitty/mission-{_SLUG}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="mission behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[],
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    # Deliberately NO ``git checkout -b <mission-branch>`` — HEAD stays on the
    # protected "main", reproducing the #2745 "no lane branch" scenario.
    return feature_dir


def test_accept_on_protected_primary_with_no_lane_branch_names_followable_escape_hatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#2745 facet 2 / FR-014 / C-ACCEPT-GUIDANCE liveness probe.

    A mission whose HEAD never leaves its own protected ``target_branch``
    (no lane/mission branch ever checked out) runs ``accept`` to completion.
    The acceptance-meta commit is refused (protected primary, no coordination
    route) -- a genuine refusal (exit 1), not a silent no-op -- but the
    refusal SUBSTANTIVELY NAMES a real, followable escape hatch (a concrete
    ``finalize-tasks --target-branch <feature-branch>`` command, or the
    ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`` env hatch), and never
    emits the retired impossible "run from the mission lane branch/worktree"
    instruction. Not a tautological exit-code check: the assertions below
    inspect the ACTUAL error text.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _build_accept_ready_mission_with_no_lane_branch(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="auto",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
        )

    # It genuinely refuses (exit 1) -- this is not a silent no-op.
    assert exc_info.value.exit_code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    message = payload["error"]

    # SUBSTANTIVE positive assertion: the real, followable escape hatch is
    # named -- either a concrete CLI command an operator can copy-paste...
    names_finalize_tasks_command = _FOLLOWABLE_COMMAND_FRAGMENT in message and _FOLLOWABLE_FLAG_FRAGMENT in message
    # ...or the documented env-var hatch.
    names_env_hatch = _FOLLOWABLE_ENV_HATCH_FRAGMENT in message
    assert names_finalize_tasks_command or names_env_hatch, (
        f"accept's protected-primary refusal must name a followable escape hatch (finalize-tasks --target-branch or the env hatch); got: {message!r}"
    )

    # SUBSTANTIVE negative assertion: the retired impossible instruction
    # (#2745) never appears.
    assert _IMPOSSIBLE_INSTRUCTION_FRAGMENT not in message, f"accept regressed to the impossible #2745 'materialize-then-retry' style instruction; got: {message!r}"
    assert "materialize" not in message.lower() or "retry" not in message.lower(), (
        f"accept's guidance reads like the retired materialize-then-retry instruction; got: {message!r}"
    )
