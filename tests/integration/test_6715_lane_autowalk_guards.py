"""#6715: ``move-task`` and ``accept`` refuse a hollow or self-reviewed lanes/coord work package.

Background (#6715, P0). On a ``coord`` Mission a work package claimed by ``claude`` through
``agent action implement``, with nothing committed to its owned file and its subtask ticked,
auto-walked ``in_progress -> for_review -> in_review -> approved`` on an unforced
``move-task --to approved --agent claude --note lgtm`` at exit 0: the lanes readiness gate counts
commits and the coord lane carries tool bookkeeping commits (the planning-artifact merge, "chore:
Start WP02 implementation", merges of the Mission branch). ``accept --lenient`` then passed too.

The move now runs the topology-neutral evidence check (``consolidation/wp_evidence.py``, the
window and matcher consolidate uses) and, for an unforced approval, the #5939 independence
comparison (``tool:model:profile``); ``accept`` refuses before writing anything, whatever
``--lenient`` says, and records ``--attest-no-implementation`` first.

* :func:`test_hollow_self_approval_is_refused_at_the_move` -- the issue's exact flow, coord and
  lanes; under coord the lane provably carries bookkeeping commits that do not count.
* :func:`test_a_non_owned_lane_commit_does_not_count` -- a commit outside the owned files defeats
  the commit count but not the evidence check.
* :func:`test_self_approval_with_real_work_is_not_independent` -- a real owned commit approved by
  its own implementer refuses ``REVIEW_NOT_INDEPENDENT``; the same agent name with a different
  ``--profile`` is another identity and is allowed (coord, lanes and single_branch).
* :func:`test_forced_hollow_approval_is_refused_at_accept_until_attested` -- ``--force`` still
  bypasses the move (ruling 3), ``accept`` refuses ``IMPLEMENTATION_MISSING`` (JSON envelope,
  nothing ``done``), and ``accept --attest-no-implementation`` then ``consolidate`` land it.
* :func:`test_real_work_with_independent_review_moves_accepts_and_consolidates` -- the positive
  control with unforced moves end to end.

Drives the REAL CLI in an isolated HOME, reusing the WP01 fixture helpers.
"""

from __future__ import annotations

import json
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
    _workspace_for,
    drive,
    lanes_of,
    on_target,
    setup_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]

_RESEARCH = "research/notes.md"


def _out(proc: subprocess.CompletedProcess[str]) -> str:
    """The run's stdout and stderr with every whitespace run collapsed (the console wraps long lines)."""
    return " ".join((proc.stdout + proc.stderr).split())


def _move(mission: _Mission, wp: str, to: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _sk(mission, "agent", "tasks", "move-task", wp, "--to", to, "--note", "lgtm", "--mission", mission.slug, *extra)


def _claim(mission: _Mission, wp: str, subtask: str, agent: str, *, topology: str) -> None:
    if topology == "single_branch":
        _sk(mission, "agent", "tasks", "move-task", wp, "--to", "in_progress", "--agent", agent, "--note", "claim", "--mission", mission.slug, check=True)
    else:
        _sk(mission, "agent", "action", "implement", wp, "--agent", agent, "--mission", mission.slug, check=True)
    _sk(mission, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", mission.slug)


def _planning_commit(mission: _Mission) -> str:
    return str(json.loads((mission.feature_dir / "lanes.json").read_text(encoding="utf-8"))["planning_commit_sha"])


def _accept(mission: _Mission, *extra: str) -> subprocess.CompletedProcess[str]:
    _sk(mission, "agent", "acceptance-verdict", "--mission", mission.slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_specs(mission.repo)
    proc = _sk(mission, "accept", "--mission", mission.slug, "--json", "--lenient", *extra)
    _commit_specs(mission.repo)
    return proc


def _json_payload(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """The JSON object accept printed on stdout (a refusal is one line, a report is indented)."""
    try:
        payload: dict[str, object] = json.loads(proc.stdout)
    except ValueError:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return payload


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_hollow_self_approval_is_refused_at_the_move(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    _claim(mission, "WP02", "T2", "claude", topology=topology)
    lane_commits = int(_git(_workspace_for(mission, "WP02"), "rev-list", "--count", f"{_planning_commit(mission)}..HEAD"))

    moved = _move(mission, "WP02", "approved", "--agent", "claude")

    assert moved.returncode != 0, f"a hollow self-approval must be refused at the move. output:\n{_out(moved)[-2000:]}"
    assert "implementation" in _out(moved).lower(), _out(moved)[-2000:]
    assert "IMPLEMENTATION_MISSING: WP02" in _out(moved), _out(moved)[-2000:]
    if topology == "coord":
        # The commit count the lanes readiness gate reads is non-zero here (tool bookkeeping), so
        # only the owned-file evidence check can have refused the move.
        assert lane_commits > 0, "fixture: the coord lane carries bookkeeping commits"
    assert lanes_of(mission).get("WP02") != "approved"


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_a_non_owned_lane_commit_does_not_count(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    _claim(mission, "WP02", "T2", "claude", topology=topology)
    _commit_owned(mission, "WP02", "src/unrelated.py")

    moved = _move(mission, "WP02", "approved", "--agent", "claude")

    assert moved.returncode != 0, _out(moved)[-2000:]
    assert "IMPLEMENTATION_MISSING: WP02" in _out(moved), _out(moved)[-2000:]
    assert lanes_of(mission).get("WP02") != "approved"


@pytest.mark.parametrize("topology", ["coord", "lanes", "single_branch"])
def test_self_approval_with_real_work_is_not_independent(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    _claim(mission, "WP02", "T2", "claude", topology=topology)
    _commit_owned(mission, "WP02", "tools/check.sh")
    _commit_specs(mission.repo)

    refused = _move(mission, "WP02", "approved", "--agent", "claude")

    code = "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT" if topology == "single_branch" else "REVIEW_NOT_INDEPENDENT"
    assert refused.returncode != 0, f"an unforced self-approval must be refused. output:\n{_out(refused)[-2000:]}"
    assert f"{code}: WP02 cannot be approved by its implementer" in _out(refused), _out(refused)[-2000:]
    assert "IMPLEMENTATION_MISSING" not in _out(refused), "the owned commit is evidence"
    assert lanes_of(mission).get("WP02") != "approved"

    allowed = _move(mission, "WP02", "approved", "--agent", "claude", "--profile", "reviewer-renata")

    assert allowed.returncode == 0, f"the same agent name with another profile is another identity. output:\n{_out(allowed)[-2000:]}"
    assert lanes_of(mission).get("WP02") == "approved"


def test_forced_hollow_approval_is_refused_at_accept_until_attested(tmp_path: Path) -> None:
    mission = setup_mission(tmp_path, "coord")
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP03", "T3", implementer="claude", reviewer="bob", owned_path="src/m3/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=f"kitty-specs/{mission.slug}/{_RESEARCH}")
    # ``drive`` forces every move after the claim (ruling 3: --force bypasses the move gates).
    drive(mission, "WP02", "T2", implementer="claude", reviewer="bob", owned_path=None)
    assert lanes_of(mission).get("WP02") == "approved", "fixture: a forced move bypasses the evidence check"

    refused = _accept(mission)
    payload = _json_payload(refused)

    assert refused.returncode == 1, f"accept must refuse a hollow approval whatever --lenient says. output:\n{_out(refused)[-2000:]}"
    assert payload.get("error_code") == "IMPLEMENTATION_MISSING", payload
    assert payload.get("error_codes") == ["IMPLEMENTATION_MISSING"], payload
    assert "IMPLEMENTATION_MISSING: WP02" in str(payload.get("error")), payload
    assert not any(lane == "done" for lane in lanes_of(mission).values())

    accepted = _accept(mission, "--attest-no-implementation", "WP02", "--attest-reason", "docs-only")
    assert accepted.returncode == 0, f"the attested WP no longer blocks accept. output:\n{_out(accepted)[-3000:]}"

    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)
    output = _out(consolidated)
    assert consolidated.returncode == 0, output[-3000:]
    assert "WP02: IMPLEMENTATION_MISSING lifted by operator attestation (docs-only)" in output, output[-3000:]
    assert _BANNER in output
    assert all(lane == "done" for lane in lanes_of(mission).values()), lanes_of(mission)
    assert not on_target(mission, "tools/check.sh")


def _implement_and_review(mission: _Mission, wp: str, subtask: str, owned_path: str, *, bare_approval: bool = False) -> None:
    """Unforced: ``alice`` implements and commits, ``bob`` claims the review and approves.

    With *bare_approval* the approval out of ``in_review`` passes no ``--agent``: the executor
    records the review claimer (``bob``), a real reviewer.
    """
    slug = mission.slug
    _claim(mission, wp, subtask, "alice", topology="coord")
    _commit_owned(mission, wp, owned_path)
    _commit_specs(mission.repo)
    _sk(mission, "agent", "tasks", "move-task", wp, "--to", "for_review", "--agent", "alice", "--note", "done", "--mission", slug, check=True)
    _sk(mission, "agent", "action", "review", wp, "--agent", "bob", "--mission", slug, check=True)
    approver = () if bare_approval else ("--agent", "bob")
    _sk(mission, "agent", "tasks", "move-task", wp, "--to", "approved", *approver, "--note", "lgtm", "--mission", slug, check=True)
    _commit_specs(mission.repo)


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_real_work_with_independent_review_moves_accepts_and_consolidates(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    _implement_and_review(mission, "WP01", "T1", "src/m1/real.py")
    _implement_and_review(mission, "WP02", "T2", "tools/check.sh")
    _implement_and_review(mission, "WP03", "T3", "src/m3/real.py")
    _implement_and_review(mission, "WP04", "T4", f"kitty-specs/{mission.slug}/{_RESEARCH}")

    accepted = _accept(mission)
    assert accepted.returncode == 0, _out(accepted)[-3000:]
    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)

    assert consolidated.returncode == 0, _out(consolidated)[-3000:]
    assert all(lane == "done" for lane in lanes_of(mission).values()), lanes_of(mission)
    assert on_target(mission, "tools/check.sh")


# ---------------------------------------------------------------- placeholder approver (review cycle 1)


def _implement_wp02(mission: _Mission, topology: str) -> None:
    _claim(mission, "WP02", "T2", "claude", topology=topology)
    _commit_owned(mission, "WP02", "tools/check.sh")
    _commit_specs(mission.repo)


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_self_approval_without_agent_is_refused_at_the_move(tmp_path: Path, topology: str) -> None:
    """The implementer approves its own real work by leaving out ``--agent``: the approval would be recorded as ``user``."""
    mission = setup_mission(tmp_path, topology)
    _implement_wp02(mission, topology)

    moved = _move(mission, "WP02", "approved")

    assert moved.returncode != 0, f"an approval with no reviewer identity must be refused. output:\n{_out(moved)[-2000:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP02 cannot be approved without a reviewer identity" in _out(moved), _out(moved)[-2000:]
    assert "--agent <your identity>" in _out(moved)
    assert lanes_of(mission).get("WP02") != "approved"


def test_a_placeholder_approval_is_refused_at_accept_and_consolidate(tmp_path: Path) -> None:
    """Forced past the move (ruling 3), an approval recorded as ``user`` is never an independent review."""
    mission = setup_mission(tmp_path, "coord")
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP03", "T3", implementer="alice", reviewer="bob", owned_path="src/m3/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=f"kitty-specs/{mission.slug}/{_RESEARCH}")
    _implement_wp02(mission, "coord")
    slug = mission.slug
    _sk(mission, "agent", "tasks", "move-task", "WP02", "--to", "for_review", "--agent", "claude", "--note", "done", "--mission", slug, check=True)
    # A review claim and an approval with no reviewer identity: both are recorded as ``user``.
    _sk(mission, "agent", "tasks", "move-task", "WP02", "--to", "in_review", "--note", "review", "--mission", slug, check=True)
    _sk(mission, "agent", "tasks", "move-task", "WP02", "--to", "approved", "--note", "lgtm", "--force", "--mission", slug, check=True)
    _commit_specs(mission.repo)
    assert lanes_of(mission).get("WP02") == "approved", "fixture: --force bypasses the move gates"

    accepted = _accept(mission)
    payload = _json_payload(accepted)
    assert accepted.returncode == 1, _out(accepted)[-2000:]
    assert "REVIEW_NOT_INDEPENDENT" in (payload.get("error_codes") or []), payload
    assert "REVIEW_NOT_INDEPENDENT: WP02" in str(payload.get("error")), payload

    consolidated = _sk(mission, "consolidate", "--mission", slug)
    assert consolidated.returncode != 0, _out(consolidated)[-3000:]
    assert "REVIEW_NOT_INDEPENDENT: WP02" in _out(consolidated), _out(consolidated)[-3000:]
    assert _BANNER not in _out(consolidated)
    assert not any(lane == "done" for lane in lanes_of(mission).values()), lanes_of(mission)


def test_a_bare_approval_after_a_real_review_claim_moves_accepts_and_consolidates(tmp_path: Path) -> None:
    """``agent action review --agent bob`` then a bare approval: the approval is recorded as ``bob``."""
    mission = setup_mission(tmp_path, "coord")
    _implement_and_review(mission, "WP01", "T1", "src/m1/real.py")
    _implement_and_review(mission, "WP02", "T2", "tools/check.sh", bare_approval=True)
    _implement_and_review(mission, "WP03", "T3", "src/m3/real.py")
    _implement_and_review(mission, "WP04", "T4", f"kitty-specs/{mission.slug}/{_RESEARCH}")

    accepted = _accept(mission)
    assert accepted.returncode == 0, _out(accepted)[-3000:]
    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)

    assert consolidated.returncode == 0, _out(consolidated)[-3000:]
    assert all(lane == "done" for lane in lanes_of(mission).values()), lanes_of(mission)
