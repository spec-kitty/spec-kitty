"""#7569: an approval records one reviewer of record, never the git user, never a minted token.

Drives the real ``move-task`` entry point against a real git repository whose
``user.name`` is the distinctive ``Git User Fallback`` (the #4670 fixture in
``test_verdict_attribution_4670``). The review claim is seeded **unforced**, as
``agent action review --agent <identity>`` records it.

Every "absent" assertion searches the whole serialized event line, and each case
carries a positive control (the claimant identity IS present in the same line), so
an absence can never pass vacuously.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.tasks_move_task import ReviewerOfRecord, resolve_reviewer_of_record
from specify_cli.status import Lane, ReviewResult
from specify_cli.status.reducer import ReviewResultLookup
from specify_cli.status.models import StatusEvent, actor_full_identity
from tests._support.status_seed import seed_status_event
from tests.specify_cli.cli.commands.agent.test_verdict_attribution_4670 import (
    _MISSION_SLUG,
    _build_mission,
    _move,
    _seed_hops,
    _wp_slug_dir,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_GIT_USER = "Git User Fallback"
_CLAIMANT = "claude:sonnet:reviewer-renata"
_OPERATOR = "claude:sonnet:operator"
_MINTED_PREFIXES = ("auto-approval:", "approval:", "auto-forward:")
_DONE_OVERRIDE = ["--done-override-reason", "fixture lane is not merged"]


def _seed_review_ready(feature_dir: Path, mission_slug: str) -> None:
    """WP01 implemented by ``fixture`` and submitted for review."""
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


def _seed_claim(feature_dir: Path, mission_slug: str, actor: object) -> None:
    """The unforced ``for_review -> in_review`` review claim ``agent action review`` records."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="claim-2026-01-02",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at="2026-01-02T00:00:01+00:00",
            actor=actor,
            force=False,
            execution_mode="worktree",
        ),
    )


def _claimed_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str, claimant: object = _CLAIMANT) -> tuple[Path, Path, str]:
    mission_slug = f"{_MISSION_SLUG}-{suffix}"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)
    _seed_review_ready(feature_dir, mission_slug)
    _seed_claim(feature_dir, mission_slug, claimant)
    return repo, feature_dir, mission_slug


def _event_line(feature_dir: Path, to_lane: str) -> tuple[str, dict[str, Any]]:
    """The raw JSON line and parsed record of the newest event moving WP01 to ``to_lane``."""
    lines = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        record = json.loads(line)
        if record.get("wp_id") == "WP01" and record.get("to_lane") == to_lane:
            return line, record
    raise AssertionError(f"no WP01 event to {to_lane!r} in the log")


def _identity_fields(record: dict[str, Any]) -> dict[str, str | None]:
    """Every identity field an approval or done event records."""
    review_result = record.get("review_result") or {}
    evidence_review = (record.get("evidence") or {}).get("review") or {}
    policy = record.get("policy_metadata") or {}
    return {
        "actor": actor_full_identity(record.get("actor")),
        "review_result.reviewer": actor_full_identity(review_result.get("reviewer")),
        "evidence.review.reviewer": actor_full_identity(evidence_review.get("reviewer")),
        "policy_metadata.tool": actor_full_identity(policy.get("tool")),
    }


def _references(record: dict[str, Any]) -> list[str]:
    review_result = record.get("review_result") or {}
    evidence_review = (record.get("evidence") or {}).get("review") or {}
    return [ref for ref in (review_result.get("reference"), evidence_review.get("reference")) if ref is not None]


def _assert_no_fabrication(line: str) -> None:
    assert _GIT_USER not in line, f"the git user.name leaked into the event: {line}"
    for prefix in _MINTED_PREFIXES:
        assert f'"{prefix}' not in line, f"a minted {prefix!r} reference was recorded: {line}"


def _assert_pointer_to_existing_cycle(repo: Path, mission_slug: str, reference: str) -> None:
    assert reference.startswith("review-cycle://"), reference
    filename = reference.rsplit("/", 1)[-1]
    assert (repo / _wp_slug_dir(mission_slug) / filename).is_file(), f"{reference} points at no file"


@pytest.mark.parametrize("extra", [[], ["--no-auto-commit"]], ids=["default", "no-auto-commit"])
def test_approval_records_the_claimant_never_the_git_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str]) -> None:
    """Cases 1, 2 and 6: an approval with no ``--agent`` records the review claimant in every field."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "approve")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed", *extra])
    assert result.exit_code == 0, result.output

    line, record = _event_line(feature_dir, "approved")
    _assert_no_fabrication(line)
    claimant = actor_full_identity(_CLAIMANT)
    assert "reviewer-renata" in line, "positive control: the claimant must be in the very line searched"
    assert _identity_fields(record) == dict.fromkeys(_identity_fields(record), claimant)
    references = _references(record)
    assert len(references) == 2 and references[0] == references[1], references
    _assert_pointer_to_existing_cycle(repo, mission_slug, references[0])


def _approved_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str) -> tuple[Path, str, dict[str, Any]]:
    """WP01 approved by the claimant; returns the feature dir, the slug and the approval record."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, suffix)
    approved = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed"])
    assert approved.exit_code == 0, approved.output
    _approval_line, approval = _event_line(feature_dir, "approved")
    return feature_dir, mission_slug, approval


def test_done_carries_the_approval_reviewer_and_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 3: ``approved -> done`` carries the approval's reviewer and reference into the review fields only.

    The done event's actor is the asserted mover (``--agent``), never the carried reviewer: the
    reviewer did not perform this move. ``policy_metadata.tool`` names the same performer, because
    it describes this hop's decision tool (its profile/model come from the mover's binding).
    """
    feature_dir, mission_slug, approval = _approved_mission(tmp_path, monkeypatch, "done")

    done = _move(["WP01", "--to", "done", "--mission", mission_slug, "--agent", _OPERATOR, *_DONE_OVERRIDE])
    assert done.exit_code == 0, done.output

    line, record = _event_line(feature_dir, "done")
    _assert_no_fabrication(line)
    assert "reviewer-renata" in line, "positive control: the carried reviewer must be in the very line searched"
    operator = actor_full_identity(_OPERATOR)
    assert actor_full_identity(record["actor"]) == operator
    assert record["force"] is False
    done_review = record["evidence"]["review"]
    assert done_review["reviewer"] == approval["review_result"]["reviewer"]
    assert done_review["reference"] == approval["review_result"]["reference"]
    assert actor_full_identity(done_review["reviewer"]) == actor_full_identity(_CLAIMANT)
    if record.get("review_result") is not None:
        assert record["review_result"]["reviewer"] == approval["review_result"]["reviewer"]
        assert record["review_result"]["reference"] == approval["review_result"]["reference"]
    assert actor_full_identity(record["policy_metadata"]["tool"]) == operator


def test_done_without_an_asserted_mover_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-007: ``approved -> done`` with neither ``--agent`` nor ``--reviewer`` keeps the base refusal.

    The carried approval names who reviewed, not who moves the work package to done; with no asserted
    mover the move would record the placeholder, so ``REVIEW_NOT_INDEPENDENT`` fires and nothing is written.
    """
    feature_dir, mission_slug, _approval = _approved_mission(tmp_path, monkeypatch, "done-unasserted")
    log = feature_dir / "status.events.jsonl"
    before = log.read_bytes()

    done = _move(["WP01", "--to", "done", "--mission", mission_slug, *_DONE_OVERRIDE])

    assert done.exit_code != 0, done.output
    assert "REVIEW_NOT_INDEPENDENT" in done.output
    assert log.read_bytes() == before


def test_done_with_reviewer_flag_records_it_as_the_mover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--reviewer`` alone is the asserted mover of a done move; the review fields stay the carried approval's."""
    feature_dir, mission_slug, approval = _approved_mission(tmp_path, monkeypatch, "done-reviewer")

    done = _move(["WP01", "--to", "done", "--mission", mission_slug, "--reviewer", _OPERATOR, *_DONE_OVERRIDE])
    assert done.exit_code == 0, done.output

    _line, record = _event_line(feature_dir, "done")
    assert actor_full_identity(record["actor"]) == actor_full_identity(_OPERATOR)
    assert record["evidence"]["review"]["reviewer"] == approval["review_result"]["reviewer"]
    assert record["evidence"]["review"]["reference"] == approval["review_result"]["reference"]


def test_forced_approval_records_the_forcing_actor_and_force_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 4: a forced approval over a claim is recorded as the forcing actor with ``force-override``."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "forced")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--force", "--agent", _OPERATOR, "--note", "operator override"])
    assert result.exit_code == 0, result.output

    line, record = _event_line(feature_dir, "approved")
    _assert_no_fabrication(line)
    assert "operator" in line, "positive control: the forcing actor must be in the very line searched"
    operator = actor_full_identity(_OPERATOR)
    fields = _identity_fields(record)
    assert fields["review_result.reviewer"] == operator
    assert fields["evidence.review.reviewer"] == operator
    assert fields["policy_metadata.tool"] == operator
    assert _references(record) == ["force-override", "force-override"]


def test_reviewer_flag_alone_sets_the_approving_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 5: ``--reviewer`` is an identity assertion; without ``--agent`` it is the event actor."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "reviewer-flag", claimant="user")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--reviewer", _CLAIMANT, "--note", "Review passed"])
    assert result.exit_code == 0, result.output

    line, record = _event_line(feature_dir, "approved")
    _assert_no_fabrication(line)
    assert "reviewer-renata" in line, "positive control"
    assert _identity_fields(record)["actor"] == actor_full_identity(_CLAIMANT)


# ---------------------------------------------------------------------------
# Damaged review slot (operator ruling ``damaged_slot``, 2026-11-12)
# ---------------------------------------------------------------------------

_DAMAGED = ReviewResultLookup(slot_present=True, result=None)
_MOVE_TASK = "specify_cli.cli.commands.agent.tasks_move_task"
_VERDICT_SEAM = "specify_cli.cli.commands.agent.tasks_verdict_persistence"


def _damaged_slot_patches(*, guard_sees_damage: bool) -> list[Any]:
    """Inject a damaged event-log review slot (the real store refuses to append one).

    ``guard_sees_damage=False`` keeps the decision guard's own read clean, so only the approval
    writer's read (the cycle writer skips with "the recorded review verdict could not be read") and
    the reviewer-of-record read see the damage: the two reads disagree.
    """
    patches = [
        patch("specify_cli.status.event_sourced_review_result", return_value=_DAMAGED),
        patch(f"{_VERDICT_SEAM}.event_sourced_review_result", return_value=_DAMAGED),
    ]
    if not guard_sees_damage:
        patches.append(patch(f"{_MOVE_TASK}.resolve_review_verdict_facts", return_value=(None, None, None)))
    return patches


def _move_with(patches: list[Any], args: list[str]) -> Any:
    for active in patches:
        active.start()
    try:
        return _move(args)
    finally:
        for active in reversed(patches):
            active.stop()


def test_damaged_slot_refuses_every_approval_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A damaged review slot the decision guard reads refuses the approval; the log is byte-identical."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "damaged")
    log = feature_dir / "status.events.jsonl"
    before = log.read_bytes()

    result = _move_with(_damaged_slot_patches(guard_sees_damage=True), ["WP01", "--to", "approved", "--mission", mission_slug, "--note", "ok"])

    assert result.exit_code == 1, result.output
    assert "no parseable review verdict" in result.output
    assert log.read_bytes() == before


def test_unforced_approval_on_damaged_writer_slot_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling ``damaged_slot``: an unforced approval the cycle writer cannot record is refused, never ``force-override``."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "damaged-writer")
    log = feature_dir / "status.events.jsonl"
    before = log.read_bytes()

    result = _move_with(_damaged_slot_patches(guard_sees_damage=False), ["WP01", "--to", "approved", "--mission", mission_slug, "--note", "ok"])

    assert result.exit_code == 1, result.output
    assert "REVIEW_SLOT_DAMAGED" in result.output
    assert "status.events.jsonl" in result.output
    assert "--approval-ref" in result.output and "--force" in result.output
    assert log.read_bytes() == before


def test_unforced_approval_on_damaged_writer_slot_takes_the_approval_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: with ``--approval-ref`` the approval proceeds and records that reference, unforced."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "damaged-ref")

    result = _move_with(
        _damaged_slot_patches(guard_sees_damage=False),
        ["WP01", "--to", "approved", "--mission", mission_slug, "--note", "ok", "--approval-ref", "pr-1234"],
    )

    assert result.exit_code == 0, result.output
    line, record = _event_line(feature_dir, "approved")
    assert record["force"] is False
    assert "force-override" not in line
    assert _references(record) == ["pr-1234", "pr-1234"]


# ---------------------------------------------------------------------------
# resolve_reviewer_of_record: the pure combiner, table-driven (T003)
# ---------------------------------------------------------------------------

_RECORDED = ReviewResult(reviewer="claude:sonnet:reviewer-renata", verdict="approved", reference="review-cycle://m/WP01-core/review-cycle-1.md")
_NO_FACTS: dict[str, Any] = {
    "agent": None,
    "reviewer": None,
    "claimant": None,
    "forced": False,
    "carrying": False,
    "recorded_approval": None,
    "arbiter_ref": None,
    "approval_ref": None,
}


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        # carried (approved -> done)
        pytest.param(
            {"carrying": True, "recorded_approval": _RECORDED, "agent": "codex"},
            ReviewerOfRecord(_RECORDED.reviewer, _RECORDED.reference, "carried"),
            id="carried-verbatim",
        ),
        pytest.param({"carrying": True, "agent": "codex"}, ReviewerOfRecord("codex", "force-override", "carried"), id="carried-no-approval-agent"),
        pytest.param(
            {"carrying": True, "reviewer": " claude:opus "}, ReviewerOfRecord("claude:opus", "force-override", "carried"), id="carried-no-approval-reviewer"
        ),
        pytest.param({"carrying": True}, None, id="carried-no-identity"),
        pytest.param({"carrying": True, "agent": "  ", "reviewer": "", "claimant": "codex"}, None, id="carried-blank-identity-ignores-claimant"),
        # forced
        pytest.param(
            {"forced": True, "agent": "operator", "arbiter_ref": "arbiter://WP01/1"},
            ReviewerOfRecord("operator", "arbiter://WP01/1", "forced"),
            id="forced-arbiter-ref",
        ),
        pytest.param(
            {"forced": True, "agent": "operator", "arbiter_ref": "  "}, ReviewerOfRecord("operator", "force-override", "forced"), id="forced-blank-arbiter-ref"
        ),
        pytest.param({"forced": True, "claimant": "codex"}, ReviewerOfRecord("codex", "force-override", "forced"), id="forced-claimant"),
        pytest.param({"forced": True}, ReviewerOfRecord("user", "force-override", "forced"), id="forced-no-identity"),
        pytest.param({"forced": True, "agent": " ", "reviewer": "\t"}, ReviewerOfRecord("user", "force-override", "forced"), id="forced-whitespace-identity"),
        pytest.param(
            {"forced": True, "carrying": True, "recorded_approval": _RECORDED, "agent": "operator"},
            ReviewerOfRecord("operator", "force-override", "forced"),
            id="forced-wins-over-carried",
        ),
        # review (precedence --agent > --reviewer > claimant; --approval-ref kept)
        pytest.param({"agent": "a", "reviewer": "r", "claimant": "c"}, ReviewerOfRecord("a", None, "review"), id="review-agent-first"),
        pytest.param({"reviewer": "r", "claimant": "c"}, ReviewerOfRecord("r", None, "review"), id="review-reviewer-second"),
        pytest.param({"claimant": "c"}, ReviewerOfRecord("c", None, "review"), id="review-claimant-third"),
        pytest.param({"agent": "  ", "reviewer": " ", "claimant": " c "}, ReviewerOfRecord("c", None, "review"), id="review-blank-flags-skipped"),
        pytest.param({"claimant": "c", "approval_ref": " pr-12 "}, ReviewerOfRecord("c", "pr-12", "review"), id="review-keeps-approval-ref"),
        pytest.param({"claimant": "c", "approval_ref": "   "}, ReviewerOfRecord("c", None, "review"), id="review-blank-approval-ref"),
        pytest.param({"recorded_approval": _RECORDED}, None, id="review-ignores-recorded-approval"),
        pytest.param({}, None, id="review-no-identity"),
    ],
)
def test_resolve_reviewer_of_record(facts: dict[str, Any], expected: ReviewerOfRecord | None) -> None:
    """Each rule of the combiner (forced -> carried -> review), and the ``carrying`` flag that selects the carried rule."""
    assert resolve_reviewer_of_record(**{**_NO_FACTS, **facts}) == expected
