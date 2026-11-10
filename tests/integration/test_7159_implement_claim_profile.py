"""#7159: the implement claim records the dispatch-resolved identity, so a same-tool reviewer under another profile is independent.

Background (#7159, P1). ``agent action implement WP02 --agent claude --profile python-pedro`` on a
fresh code lane created the lane through the top-level ``implement`` command, which recorded the
claim (``planned -> claimed -> in_progress``) with the bare actor ``"claude"``. The structured claim
path then found the work package already ``in_progress`` and emitted nothing. The approval gate reads
the implementer of record from that claim, so ``move-task --to approved --agent claude --profile
reviewer-renata`` was refused ``REVIEW_NOT_INDEPENDENT`` (implementer ``claude::``).

* :func:`test_implement_profile_is_recorded_on_the_fresh_lane_claim` -- the claim events carry the
  structured implementer actor with the ``--profile``; another profile approves, the same profile is
  refused (coord and lanes).
* :func:`test_an_agentless_claim_keeps_the_generic_placeholder` -- without ``--agent`` the claim
  never records the planned frontmatter agent as the implementer (#6400).
* :func:`test_an_unprovable_binding_refuses_before_any_lane_or_claim` -- the dispatch binding is
  resolved before the lane is created, so ``--model`` refuses with nothing left behind.
* :func:`test_implementer_resubmission_refines_a_bare_claim` -- operator ruling on #7159's rc8
  comment: a ``for_review`` submission by the implementer refines the recorded claim identity
  (it fills segments the claim did not record and never contradicts one), so a bare claim followed by
  a full-identity submission no longer has to go back to ``planned``.

Drives the REAL CLI in an isolated HOME, reusing the #6715 fixture helpers.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_6715_consolidate_lane_evidence import _Mission, _commit_owned, _commit_specs, _sk, lanes_of, setup_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]


def _out(proc: subprocess.CompletedProcess[str]) -> str:
    return " ".join((proc.stdout + proc.stderr).split())


def _move(mission: _Mission, wp: str, to: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _sk(mission, "agent", "tasks", "move-task", wp, "--to", to, "--note", "lgtm", "--mission", mission.slug, *extra)


def _claim_events(mission: _Mission, wp: str) -> list[dict[str, object]]:
    # The status surface is the repository root checkout (lanes) or the coordination worktree
    # (coord); lane checkouts carry no status files.
    (log,) = (path for path in mission.repo.rglob(f"kitty-specs/{mission.slug}/status.events.jsonl") if path.is_file())
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [event for event in events if event.get("wp_id") == wp and event.get("to_lane") in {"claimed", "in_progress"} and "kind" not in event]


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_implement_profile_is_recorded_on_the_fresh_lane_claim(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    _sk(mission, "agent", "action", "implement", "WP02", "--agent", "claude", "--profile", "python-pedro", "--mission", mission.slug, check=True)
    _sk(mission, "agent", "tasks", "mark-status", "T2", "--status", "done", "--mission", mission.slug)
    _commit_owned(mission, "WP02", "tools/check.sh")
    _commit_specs(mission.repo)

    claims = _claim_events(mission, "WP02")
    assert claims, "the implement claim appended no claimed/in_progress event"
    for event in claims:
        actor = event["actor"]
        assert isinstance(actor, dict), f"the claim recorded a bare actor: {actor!r}"
        assert (actor.get("tool"), actor.get("profile"), actor.get("role")) == ("claude", "python-pedro", "implementer"), actor

    refused = _move(mission, "WP02", "approved", "--agent", "claude", "--profile", "python-pedro")

    assert refused.returncode != 0, f"the implementer's own profile must not approve. output:\n{_out(refused)[-2000:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP02 cannot be approved by its implementer" in _out(refused), _out(refused)[-2000:]
    assert lanes_of(mission).get("WP02") != "approved"

    allowed = _move(mission, "WP02", "approved", "--agent", "claude", "--profile", "reviewer-renata")

    assert allowed.returncode == 0, f"a same-tool reviewer under another profile is independent. output:\n{_out(allowed)[-2000:]}"
    assert lanes_of(mission).get("WP02") == "approved"


def test_implementer_resubmission_refines_a_bare_claim(tmp_path: Path) -> None:
    mission = setup_mission(tmp_path, "lanes")
    _sk(mission, "agent", "action", "implement", "WP02", "--agent", "claude", "--mission", mission.slug, check=True)
    _sk(mission, "agent", "tasks", "mark-status", "T2", "--status", "done", "--mission", mission.slug)
    _commit_owned(mission, "WP02", "tools/check.sh")
    _commit_specs(mission.repo)
    submitted = _move(mission, "WP02", "for_review", "--agent", "claude:claude-opus-5-5:implementer-ivan")
    assert submitted.returncode == 0, _out(submitted)[-2000:]

    refused = _move(mission, "WP02", "approved", "--agent", "claude:claude-opus-5-5:implementer-ivan")

    assert refused.returncode != 0, f"the submitter must not approve its own work. output:\n{_out(refused)[-2000:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP02 cannot be approved by its implementer" in _out(refused), _out(refused)[-2000:]

    allowed = _move(mission, "WP02", "approved", "--agent", "claude:claude-sonnet-5-5:reviewer-renata")

    assert allowed.returncode == 0, f"the submission refines the bare claim, so another profile is independent. output:\n{_out(allowed)[-2000:]}"
    assert lanes_of(mission).get("WP02") == "approved"


def test_an_agentless_claim_keeps_the_generic_placeholder(tmp_path: Path) -> None:
    mission = setup_mission(tmp_path, "lanes")
    # Without --agent the command still refuses ("--agent parameter required"), but only after the
    # fresh lane's claim was recorded; that claim must not name the planned frontmatter agent.
    _sk(mission, "agent", "action", "implement", "WP02", "--mission", mission.slug)

    claims = _claim_events(mission, "WP02")
    assert claims, "the implement claim appended no claimed/in_progress event"
    assert {json.dumps(event["actor"]) for event in claims} == {json.dumps("implement-command")}


def test_an_unprovable_binding_refuses_before_any_lane_or_claim(tmp_path: Path) -> None:
    mission = setup_mission(tmp_path, "lanes")
    worktrees_before = sorted(path.name for path in (mission.repo / ".worktrees").glob("*")) if (mission.repo / ".worktrees").exists() else []

    refused = _sk(mission, "agent", "action", "implement", "WP02", "--agent", "claude", "--model", "claude-opus-5-5", "--mission", mission.slug)

    assert refused.returncode != 0, _out(refused)[-2000:]
    assert "--model cannot be recorded" in _out(refused), _out(refused)[-2000:]
    worktrees_after = sorted(path.name for path in (mission.repo / ".worktrees").glob("*")) if (mission.repo / ".worktrees").exists() else []
    assert worktrees_after == worktrees_before, "the refusal must not leave a lane worktree behind"
    assert lanes_of(mission).get("WP02") == "planned"
    branches = subprocess.run(["git", "branch", "--list", "kitty/*lane*"], cwd=mission.repo, capture_output=True, text=True, check=True).stdout
    assert branches.strip() == "", f"the refusal must not leave a lane branch behind: {branches!r}"
    assert _claim_events(mission, "WP02") == [], "the refusal must not append a claim event"
