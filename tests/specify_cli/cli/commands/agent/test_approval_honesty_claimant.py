"""#7573: an unforced verdict out of ``in_review`` must come from the review claimant.

Drives the real ``move-task`` entry point against the #4670 fixture (a real git
repository) with an **unforced** review claim, as ``agent action review --agent
<identity>`` records it. A non-claimant approval refuses with
``APPROVER_NOT_CLAIMANT`` and writes nothing (NFR-003); ``--force`` stays the
operator override and is recorded as a forced move, never a review.

The identities are compared segment for segment (tool, model, profile) through
``status.review_roles.same_review_identity``: a same-tool supervisor and a bare
tool against a profiled claimant are both other identities.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent, actor_full_identity
from tests._support.status_seed import seed_status_event
from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h
from tests.specify_cli.cli.commands.agent.test_verdict_attribution_4670 import (
    _MISSION_SLUG,
    _build_mission,
    _move,
    _seed_hops,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CODE = "APPROVER_NOT_CLAIMANT"
_CLAIMANT = "claude:sonnet:reviewer-renata"
_ORCHESTRATOR = "kitty-orchestrator"
_SUPERVISOR = "claude:sonnet:supervisor"
_DONE_OVERRIDE = ["--done-override-reason", "fixture lane is not merged"]


def _claimed_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str, claimant: str = _CLAIMANT) -> tuple[Path, Path, str]:
    """WP01 implemented by ``fixture``, submitted, then claimed for review (unforced) by ``claimant``."""
    mission_slug = f"{_MISSION_SLUG}-{suffix}"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)
    _seed_hops(
        feature_dir,
        mission_slug,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        ],
        at_day="2026-01-01",
    )
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="claim-2026-01-02",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at="2026-01-02T00:00:01+00:00",
            actor=claimant,
            force=False,
            execution_mode="worktree",
        ),
    )
    return repo, feature_dir, mission_slug


def _snapshot(repo: Path, feature_dir: Path) -> dict[str, Any]:
    """The bytes of the event log and every review cycle, plus ``git status --porcelain`` (NFR-003)."""
    files = [feature_dir / "status.events.jsonl", *sorted(feature_dir.rglob("review-cycle-*.md"))]
    porcelain = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, check=True, capture_output=True, text=True).stdout
    return {
        "files": {str(path.relative_to(repo)): path.read_bytes() for path in files},
        "porcelain": porcelain,
    }


def _json_payload(output: str) -> dict[str, Any]:
    """The ``--json`` error envelope printed on refusal."""
    start = output.index("{")
    payload: dict[str, Any] = json.loads(output[start:])
    return payload


# Each case: (suffix, argv after "--mission <slug>", the approver the refusal must name).
_REFUSED_CASES = [
    pytest.param("other-tool", ["--to", "approved", "--agent", _ORCHESTRATOR], _ORCHESTRATOR, id="case1-other-tool"),
    pytest.param("same-tool", ["--to", "approved", "--agent", _SUPERVISOR], _SUPERVISOR, id="case2-same-tool-other-profile"),
    pytest.param("reviewer-flag", ["--to", "approved", "--reviewer", _ORCHESTRATOR], _ORCHESTRATOR, id="case3-reviewer-flag-only"),
    pytest.param(
        "flags-disagree",
        ["--to", "approved", "--agent", _CLAIMANT, "--reviewer", "someone-else"],
        "someone-else",
        id="case4-agent-and-reviewer-disagree",
    ),
    pytest.param("straight-done", ["--to", "done", "--agent", _SUPERVISOR, *_DONE_OVERRIDE], _SUPERVISOR, id="case5-done-from-in-review"),
    # Review cycle 1, probe 1: ``--profile`` would rename the supervisor into the claimant's profile.
    pytest.param(
        "profile-renames-supervisor",
        ["--to", "approved", "--agent", _SUPERVISOR, "--profile", "reviewer-renata"],
        _SUPERVISOR,
        id="probe1-profile-cannot-rename-a-supervisor",
    ),
]


@pytest.mark.parametrize(("suffix", "argv", "approver"), _REFUSED_CASES)
def test_non_claimant_verdict_is_refused_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str, argv: list[str], approver: str) -> None:
    """Cases 1-5 and 8: refused with the code, both identities and the remedy; nothing written."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, suffix)
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--mission", mission_slug, "--note", "Review passed", *argv])

    assert result.exit_code == 1, result.output
    output = " ".join(result.output.split())
    assert _CODE in output
    assert _CLAIMANT in output, "the refusal must name the claimant"
    assert approver in output, "the refusal must name the other identity"
    assert f"--agent {_CLAIMANT}" in output, "remedy: the claimant records the verdict"
    assert "--force" in output and "forced move" in output, "remedy: the operator override"
    assert "action review" not in output, "decision claimant_remedy: no re-claim route exists"
    assert _snapshot(repo, feature_dir) == before


def test_refusal_carries_the_code_in_the_json_diagnostic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 1 (``--json``): the diagnostic ``code`` is ``APPROVER_NOT_CLAIMANT`` and names both identities."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "json")
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--agent", _SUPERVISOR, "--json"])

    assert result.exit_code == 1, result.output
    payload = _json_payload(result.output)
    assert payload["code"] == _CODE, payload
    assert payload["review_claimant"] == _CLAIMANT
    assert payload["requesting_agent"] == _SUPERVISOR
    assert payload["error"].startswith(f"{_CODE}:"), payload
    assert _snapshot(repo, feature_dir) == before


def test_bare_tool_is_not_a_profiled_claimant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 10: claimant ``codex::reviewer-renata``, ``--agent codex``: refused (strict equality)."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "bare-tool", claimant="codex::reviewer-renata")
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--agent", "codex", "--note", "ok"])

    assert result.exit_code == 1, result.output
    output = " ".join(result.output.split())
    assert _CODE in output and "codex::reviewer-renata" in output
    assert _snapshot(repo, feature_dir) == before


@pytest.mark.parametrize(
    "identity_flags",
    [
        pytest.param([], id="no-agent"),
        pytest.param(["--agent", _CLAIMANT], id="agent-is-claimant"),
        pytest.param(["--reviewer", _CLAIMANT], id="reviewer-is-claimant"),
        pytest.param(["--agent", "claude:sonnet:reviewer-renata:reviewer"], id="agent-with-role-segment"),
    ],
)
def test_claimant_approval_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity_flags: list[str]) -> None:
    """Case 6 (positive control): the claimant records the verdict, with or without ``--agent``."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "claimant")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed", *identity_flags])

    assert result.exit_code == 0, result.output
    record = _latest(feature_dir, "approved")
    assert record["force"] is False
    assert actor_full_identity(record["actor"]) == actor_full_identity(_CLAIMANT)


def test_forced_approval_by_a_non_claimant_is_recorded_as_forced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 7: ``--force`` is the operator override: reviewer ``kitty-orchestrator``, reference ``force-override``."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "forced")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--force", "--agent", _ORCHESTRATOR, "--note", "operator override"])

    assert result.exit_code == 0, result.output
    record = _latest(feature_dir, "approved")
    assert record["force"] is True
    review = record["evidence"]["review"]
    assert actor_full_identity(review["reviewer"]) == actor_full_identity(_ORCHESTRATOR)
    assert review["reference"] == "force-override"
    assert actor_full_identity(record["actor"]) == actor_full_identity(_ORCHESTRATOR)


def _assert_one_reviewer_of_record(feature_dir: Path, expected: str) -> None:
    """FR-001: every identity field of the approval names *expected* (segment for segment)."""
    from specify_cli.status.review_roles import same_review_identity

    record = _latest(feature_dir, "approved")
    recorded = {
        "actor": actor_full_identity(record["actor"]),
        "evidence.review.reviewer": record["evidence"]["review"]["reviewer"],
        "review_result.reviewer": record["review_result"]["reviewer"],
        "policy_metadata.tool": record["policy_metadata"]["tool"],
        "review-cycle reviewer_agent": _latest_cycle_reviewer_agent(feature_dir),
    }
    wrong = {field: value for field, value in recorded.items() if not same_review_identity(value, expected)}
    assert wrong == {}, f"fields not naming {expected}: {wrong}"


def _latest_cycle_reviewer_agent(feature_dir: Path) -> str | None:
    cycles = sorted(feature_dir.rglob("review-cycle-*.md"), key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    assert cycles, "the approval wrote no review cycle"
    for line in cycles[-1].read_text(encoding="utf-8").splitlines():
        if line.startswith("reviewer_agent:"):
            return line.partition(":")[2].strip().strip("'\"")
    return None


@pytest.mark.parametrize(
    "identity_flags",
    [
        pytest.param(["--agent", "codex"], id="agent"),
        pytest.param(["--reviewer", "codex"], id="reviewer"),
    ],
)
def test_profile_flag_completes_an_asserted_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity_flags: list[str]) -> None:
    """Review cycle 1, probe 2: ``codex`` + ``--profile reviewer-renata`` records ``codex::reviewer-renata`` everywhere.

    The claim itself was recorded that way (``--agent codex --profile reviewer-renata``), so the same
    flags on the verdict name the same reviewer. The binding completes the asserted identity
    (``build_status_actor``: it fills a segment the flag leaves open), and the review fields record
    that completed identity, the one the guard compared, never the bare ``codex`` flag.
    """
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "binding", claimant="codex::reviewer-renata")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, *identity_flags, "--profile", "reviewer-renata", "--note", "ok"])

    assert result.exit_code == 0, result.output
    assert _latest(feature_dir, "approved")["force"] is False
    _assert_one_reviewer_of_record(feature_dir, "codex::reviewer-renata")


def test_claimant_approval_records_one_reviewer_of_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control of FR-001 without a binding: the claimant's own flag lands in every field."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "one-record")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--agent", _CLAIMANT, "--note", "ok"])

    assert result.exit_code == 0, result.output
    _assert_one_reviewer_of_record(feature_dir, _CLAIMANT)


def test_profile_flag_cannot_rename_a_different_profile_into_the_claimant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative control of the binding case: the claimant's tool with ``--profile python-pedro`` is another identity."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "binding-other", claimant="codex::reviewer-renata")
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--agent", "codex", "--profile", "python-pedro", "--note", "ok"])

    assert result.exit_code == 1, result.output
    output = " ".join(result.output.split())
    assert _CODE in output and "codex::reviewer-renata" in output and "codex::python-pedro" in output
    assert _snapshot(repo, feature_dir) == before


def _latest(feature_dir: Path, to_lane: str) -> dict[str, Any]:
    for line in reversed((feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()):
        record: dict[str, Any] = json.loads(line)
        if record.get("wp_id") == "WP01" and record.get("to_lane") == to_lane:
            return record
    raise AssertionError(f"no WP01 event to {to_lane!r}")


def test_skip_review_artifact_check_over_a_rejection_by_a_non_claimant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 9 (boundary): ``--skip-review-artifact-check`` over a rejected verdict, by a non-claimant.

    Pins today's ordering: the claimant guard sits in the guard prefix that
    ``override_persist_signal`` evaluates, so the refusal fires before the review-override
    persist and the event log gains nothing at all: no override record, no lane event.
    """
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_planned")
    h.drive_to_for_review(m)
    claim = h.move(m, h.WP, "in_review", h.REVIEWER)
    assert claim.exit_code == 0, claim.output
    before_log = (m.feature_dir / "status.events.jsonl").read_bytes()
    before_cycles = h.review_cycle_files(m)

    result = h.move(m, h.WP, "approved", "codex:gpt-5:supervisor", "--skip-review-artifact-check", "--note", "rejection superseded")

    assert result.exit_code == 1, result.output
    assert _CODE in " ".join(result.output.split())
    assert (m.feature_dir / "status.events.jsonl").read_bytes() == before_log
    assert h.review_cycle_files(m) == before_cycles


# ---------------------------------------------------------------------------
# _guard_review_claimant: the pure guard, table-driven
# ---------------------------------------------------------------------------

_IN_REVIEW_APPROVAL: dict[str, Any] = {"old_lane": "in_review", "target_lane": "approved", "review_claimant": _CLAIMANT}


@pytest.mark.parametrize(
    ("overrides", "refused"),
    [
        pytest.param({"asserted_agent": _SUPERVISOR}, True, id="same-tool-other-profile"),
        pytest.param({"asserted_agent": "claude"}, True, id="bare-tool-vs-profiled-claimant"),
        pytest.param({"asserted_reviewer": _ORCHESTRATOR}, True, id="reviewer-flag-only"),
        pytest.param({"asserted_agent": _CLAIMANT}, False, id="agent-is-claimant"),
        pytest.param({}, False, id="no-assertion-resolves-to-claimant"),
        pytest.param({"asserted_agent": _SUPERVISOR, "force": True}, False, id="forced"),
        pytest.param({"asserted_agent": _SUPERVISOR, "review_claimant": None}, False, id="no-claimant"),
        pytest.param({"asserted_agent": _SUPERVISOR, "target_lane": "planned"}, False, id="not-an-approval-lane"),
        pytest.param({"asserted_agent": _SUPERVISOR, "old_lane": "for_review"}, False, id="direct-approval-keeps-todays-rules"),
        pytest.param({"asserted_agent": "a", "asserted_reviewer": "b", "old_lane": "approved", "review_claimant": None}, True, id="flags-disagree-anywhere"),
        pytest.param({"asserted_agent": _CLAIMANT, "asserted_reviewer": _CLAIMANT + ":reviewer"}, False, id="flags-agree-role-ignored"),
        # The binding wins over the flag's own profile (``build_status_actor``); a move where it would
        # override one is refused, so the recorded identity is never one the flag contradicts.
        pytest.param({"agent": _SUPERVISOR, "asserted_agent": _CLAIMANT}, True, id="binding-overrides-agent-profile"),
        pytest.param({"reviewer_flag": _SUPERVISOR, "asserted_reviewer": _CLAIMANT}, True, id="binding-overrides-reviewer-profile"),
        pytest.param(
            {"agent": _SUPERVISOR, "asserted_agent": _CLAIMANT, "old_lane": "for_review", "review_claimant": None},
            True,
            id="binding-override-refused-on-a-direct-approval",
        ),
        pytest.param({"agent": "claude:sonnet", "asserted_agent": _CLAIMANT}, False, id="binding-completes-agent"),
        pytest.param({"reviewer_flag": "claude", "asserted_reviewer": _CLAIMANT}, False, id="binding-completes-reviewer"),
        pytest.param({"agent": _CLAIMANT + ":reviewer", "asserted_agent": _CLAIMANT}, False, id="role-segment-is-no-override"),
    ],
)
def test_guard_review_claimant_table(overrides: dict[str, Any], refused: bool) -> None:
    from specify_cli.cli.commands.agent.tasks_transition_core import APPROVER_NOT_CLAIMANT, _guard_review_claimant
    from tests._support.tasks_transition_request import base_request

    refusal = _guard_review_claimant(base_request(**{**_IN_REVIEW_APPROVAL, **overrides}))

    assert (refusal is not None) is refused
    if refusal is not None:
        assert refusal.diagnostic is not None and refusal.diagnostic["code"] == APPROVER_NOT_CLAIMANT
        assert refusal.error.startswith(f"{APPROVER_NOT_CLAIMANT}:")
        assert "--force" in refusal.error and "action review" not in refusal.error


def test_flag_conflict_without_claimant_asks_for_one_identity() -> None:
    from specify_cli.cli.commands.agent.tasks_transition_core import _guard_review_claimant
    from tests._support.tasks_transition_request import base_request

    refusal = _guard_review_claimant(
        base_request(old_lane="approved", target_lane="done", asserted_agent="claude:sonnet:mover", asserted_reviewer="codex", review_claimant=None)
    )

    assert refusal is not None
    assert "--agent claude:sonnet:mover and --reviewer codex name different identities" in refusal.error
    assert "Pass one identity" in refusal.error


def test_binding_override_names_the_flag_and_the_recorded_identity() -> None:
    from specify_cli.cli.commands.agent.tasks_transition_core import _guard_review_claimant
    from tests._support.tasks_transition_request import base_request

    refusal = _guard_review_claimant(base_request(**{**_IN_REVIEW_APPROVAL, "agent": _SUPERVISOR, "asserted_agent": _CLAIMANT}))

    assert refusal is not None
    assert f"--agent {_SUPERVISOR}" in refusal.error and f"records {_CLAIMANT}" in refusal.error
    assert f"--agent {_CLAIMANT}" in refusal.error and "--force" in refusal.error
    assert refusal.diagnostic is not None and refusal.diagnostic["requesting_agent"] == _SUPERVISOR


def test_asserted_review_identity_is_the_recorded_compact_form() -> None:
    from specify_cli.cli.commands.agent.tasks_transition_core import asserted_review_identity

    assert asserted_review_identity(None, None) is None
    assert asserted_review_identity("  ", None) is None
    assert asserted_review_identity("claude:sonnet:reviewer-renata:reviewer", None) == _CLAIMANT
    assert asserted_review_identity("codex", None) == "codex"
    assert asserted_review_identity(":bad", None) == ":bad"
