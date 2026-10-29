"""#6715 pre-merge adversarial-squad regressions, driven through the REAL CLI in an isolated HOME.

* Partial-identity self-approval (operator ruling R1, 2026-10-29): an implementer recorded as
  ``claude:claude-opus:implementer-ivan`` approving as bare ``claude`` (or the reverse, bare
  ``claude`` then ``claude:x``) is NOT an independent review, because a segment recorded on only
  one side never proves independence. ``move-task --to approved`` refuses it unforced, and a
  forced approval past the move refuses at ``accept`` and ``consolidate``
  (:func:`test_partial_identity_self_approval_is_refused_everywhere`).
* Same tool, different profile (a genuine review): implementer
  ``claude:claude-opus:implementer-ivan``, review claim ``claude:claude-opus:reviewer-renata``.
  The approval without ``--agent`` records the FULL review-claim identity, the printed approve
  command carries it, and the Mission accepts and consolidates
  (:func:`test_same_tool_different_profile_review_lands`).
* Tool-written Mission files are not evidence (ruling R2): a planning-artifact work package that
  owns its whole Mission directory and changed nothing an author writes refuses
  ``IMPLEMENTATION_MISSING``; a real research edit passes
  (:func:`test_planning_wp_owning_its_mission_dir_needs_author_content`).
* An attestation is validated against the evidence verdict before it is recorded: a work package
  whose verdict is ``IMPLEMENTATION_UNREADABLE`` (its lane branch was never created) refuses the
  request on ``accept`` and ``consolidate`` and nothing is recorded
  (:func:`test_attestation_refused_for_a_wp_whose_evidence_is_unreadable`).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_6715_consolidate_lane_evidence import (
    _BANNER,
    _Mission,
    _commit_owned,
    _commit_specs,
    _git,
    _sk,
    drive,
    lanes_of,
    on_target,
    setup_mission,
)
from tests.integration.test_6715_no_implementation_attestation import _attestation_mentions, _flat

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]

_OTHER_WPS = ("WP01", "WP02", "WP03", "WP04")
_IVAN = "claude:claude-opus:implementer-ivan"
_RENATA = "claude:claude-opus:reviewer-renata"


def _isolate(mission: _Mission, *keep: str) -> None:
    """Cancel every work package but *keep*, so the run judges only those."""
    for wp in _OTHER_WPS:
        if wp not in keep:
            _sk(mission, "agent", "tasks", "move-task", wp, "--to", "canceled", "--force", "--note", "isolate", "--mission", mission.slug, check=True)
    _commit_specs(mission.repo)


def _record_verdict(mission: _Mission) -> None:
    _sk(mission, "agent", "acceptance-verdict", "--mission", mission.slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_specs(mission.repo)


def _accept(mission: _Mission, *extra: str) -> subprocess.CompletedProcess[str]:
    proc = _sk(mission, "accept", "--mission", mission.slug, "--lenient", *extra)
    _commit_specs(mission.repo)
    return proc


def _approval_actors(mission: _Mission, wp: str) -> list[object]:
    """Every recorded actor of *wp*'s transitions into ``approved``, on any status log of the Mission."""
    relpath = f"kitty-specs/{mission.slug}/status.events.jsonl"
    actors: list[object] = []
    for log in [*mission.repo.glob(relpath), *mission.repo.glob(f".worktrees/*/{relpath}")]:
        for line in log.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("wp_id") == wp and event.get("to_lane") == "approved":
                actors.append(event.get("actor"))
    return actors


def _implement(mission: _Mission, implementer: str) -> None:
    _sk(mission, "agent", "action", "implement", "WP01", "--agent", implementer, "--mission", mission.slug, check=True)
    _commit_owned(mission, "WP01", "src/m1/a.py")
    _sk(mission, "agent", "tasks", "mark-status", "T1", "--status", "done", "--mission", mission.slug)


@pytest.mark.parametrize(
    ("topology", "implementer", "approver"),
    [
        pytest.param("coord", _IVAN, "claude", id="coord-approver-bare"),
        pytest.param("single_branch", "claude", "claude:x", id="single_branch-implementer-bare"),
    ],
)
def test_partial_identity_self_approval_is_refused_everywhere(tmp_path: Path, topology: str, implementer: str, approver: str) -> None:
    mission = setup_mission(tmp_path, topology)
    _implement(mission, implementer)

    moved = _sk(mission, "agent", "tasks", "move-task", "WP01", "--to", "approved", "--agent", approver, "--note", "lgtm", "--mission", mission.slug)
    assert moved.returncode != 0, f"an approval by the implementer's own tool with a one-sided segment must refuse at the move:\n{_flat(moved)[-1500:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP01" in _flat(moved), _flat(moved)[-1500:]
    assert lanes_of(mission).get("WP01") != "approved"

    # Forced past the move (the approval stamp is kept: a review claim precedes the approval).
    _sk(
        mission,
        "agent",
        "tasks",
        "move-task",
        "WP01",
        "--to",
        "for_review",
        "--agent",
        implementer,
        "--note",
        "done",
        "--force",
        "--mission",
        mission.slug,
        check=True,
    )
    _sk(mission, "agent", "action", "review", "WP01", "--agent", approver, "--mission", mission.slug, check=True)
    _sk(mission, "agent", "tasks", "move-task", "WP01", "--to", "approved", "--agent", approver, "--note", "lgtm", "--force", "--mission", mission.slug, check=True)
    _commit_specs(mission.repo)
    assert lanes_of(mission).get("WP01") == "approved"
    _isolate(mission, "WP01")
    _record_verdict(mission)

    accepted = _accept(mission)
    assert accepted.returncode != 0, f"accept must refuse the partial-identity self-approval:\n{_flat(accepted)[-2000:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP01" in _flat(accepted), _flat(accepted)[-2000:]

    main_before = _git(mission.repo, "rev-parse", "main")
    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)
    output = _flat(consolidated)
    assert consolidated.returncode != 0, f"consolidate must refuse the partial-identity self-approval:\n{output[-2000:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP01" in output, output[-2000:]
    assert _BANNER not in output
    assert lanes_of(mission).get("WP01") != "done"
    assert _git(mission.repo, "rev-parse", "main") == main_before


@pytest.mark.parametrize(
    ("topology", "use_printed_command"),
    [
        pytest.param("coord", False, id="coord-no-agent"),
        pytest.param("single_branch", True, id="single_branch-printed-command"),
    ],
)
def test_same_tool_different_profile_review_lands(tmp_path: Path, topology: str, use_printed_command: bool) -> None:
    mission = setup_mission(tmp_path, topology)
    _implement(mission, _IVAN)
    _sk(mission, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", _IVAN, "--note", "done", "--mission", mission.slug, check=True)
    review = _sk(mission, "agent", "action", "review", "WP01", "--agent", _RENATA, "--mission", mission.slug, check=True)

    printed = re.search(r"move-task WP01 --to approved --mission \S+ --agent (\S+)", _flat(review))
    assert printed is not None, _flat(review)[-2000:]
    assert printed.group(1) == _RENATA, f"the printed approve command must carry the full review-claim identity, got {printed.group(1)!r}"

    approve = ["agent", "tasks", "move-task", "WP01", "--to", "approved", "--note", "Review passed", "--mission", mission.slug]
    if use_printed_command:
        approve += ["--agent", printed.group(1)]
    moved = _sk(mission, *approve)
    assert moved.returncode == 0, f"a same-tool, different-profile review is independent and must pass the move:\n{_flat(moved)[-2000:]}"
    _commit_specs(mission.repo)
    recorded = _approval_actors(mission, "WP01")
    assert recorded and isinstance(recorded[-1], dict), recorded
    assert (recorded[-1].get("tool"), recorded[-1].get("model"), recorded[-1].get("profile")) == ("claude", "claude-opus", "reviewer-renata"), recorded[-1]

    _isolate(mission, "WP01")
    _record_verdict(mission)
    accepted = _accept(mission)
    assert "REVIEW_NOT_INDEPENDENT" not in _flat(accepted), _flat(accepted)[-2000:]
    assert accepted.returncode == 0, f"accept must pass a genuine same-tool review:\n{_flat(accepted)[-2000:]}"

    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)
    output = _flat(consolidated)
    assert consolidated.returncode == 0, f"consolidate must land a genuine same-tool review:\n{output[-3000:]}"
    assert lanes_of(mission).get("WP01") == "done"
    assert on_target(mission, "src/m1/a.py")


@pytest.mark.parametrize("real_edit", [False, True], ids=["hollow", "research-edit"])
def test_planning_wp_owning_its_mission_dir_needs_author_content(tmp_path: Path, real_edit: bool) -> None:
    mission = setup_mission(tmp_path, "lanes", planning_glob="**")
    research = f"kitty-specs/{mission.slug}/research/notes.md"
    # WP01 lands real work, so the Mission branch exists and consolidate reaches the claim.
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=research if real_edit else None)
    _isolate(mission, "WP01", "WP04")
    _record_verdict(mission)
    _accept(mission)

    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)
    output = _flat(consolidated)
    if real_edit:
        assert consolidated.returncode == 0, f"a real research edit is author content and must land:\n{output[-3000:]}"
        assert on_target(mission, research)
        return
    assert consolidated.returncode != 0, f"tool-written Mission files are not evidence:\n{output[-3000:]}"
    assert "IMPLEMENTATION_MISSING: WP04" in output, output[-3000:]
    assert _BANNER not in output


@pytest.mark.parametrize("command", ["accept", "consolidate"])
def test_attestation_refused_for_a_wp_whose_evidence_is_unreadable(tmp_path: Path, command: str) -> None:
    mission = setup_mission(tmp_path, "lanes")
    # WP01 lands real work, so the Mission branch exists and consolidate reaches the claim.
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    # Approved without ever being implemented: its lane branch was never created.
    _sk(
        mission, "agent", "tasks", "move-task", "WP02", "--to", "approved", "--force", "--agent", "codex", "--note", "exists", "--mission", mission.slug, check=True
    )
    _isolate(mission, "WP01", "WP02")
    _record_verdict(mission)

    args = ["--attest-no-implementation", "WP02", "--attest-reason", "already exists"]
    proc = _accept(mission, *args) if command == "accept" else _sk(mission, "consolidate", "--mission", mission.slug, *args)
    output = _flat(proc)

    assert proc.returncode != 0, output[-2000:]
    assert "IMPLEMENTATION_UNREADABLE" in output, f"the refusal must say what blocks the attestation:\n{output[-2000:]}"
    assert "Nothing was recorded" in output, output[-2000:]
    assert _attestation_mentions(mission) == 0, "an attestation that cannot lift anything is never recorded"
