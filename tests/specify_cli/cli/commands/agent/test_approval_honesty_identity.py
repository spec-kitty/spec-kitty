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

import pytest

from specify_cli.status import Lane
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


def test_done_carries_the_approval_reviewer_and_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 3: ``approved -> done`` carries the recorded approval's reviewer and reference verbatim."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "done")
    approved = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed"])
    assert approved.exit_code == 0, approved.output
    _approval_line, approval = _event_line(feature_dir, "approved")

    done = _move(["WP01", "--to", "done", "--mission", mission_slug, *_DONE_OVERRIDE])
    assert done.exit_code == 0, done.output

    line, record = _event_line(feature_dir, "done")
    _assert_no_fabrication(line)
    assert "reviewer-renata" in line, "positive control: the carried reviewer must be in the very line searched"
    done_review = record["evidence"]["review"]
    assert done_review["reviewer"] == approval["review_result"]["reviewer"]
    assert done_review["reference"] == approval["review_result"]["reference"]
    assert actor_full_identity(record["policy_metadata"]["tool"]) == actor_full_identity(_CLAIMANT)


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
