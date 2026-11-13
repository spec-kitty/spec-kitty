"""One review, one cycle; cited cycles exist (#7571 #3451 #7570 #6709).

Drives the real ``move-task`` entry point. A review claimed unforced by ``agent action review``
produces exactly one ``review-cycle-N.md``: when the claimant already wrote it, the approval adopts
it and writes nothing (FR-008); otherwise the approval writes it as before. A cycle answered by an
earlier verdict is never adopted (FR-009). A ``cycle N`` citation must name a current, valid cycle
(FR-010, ``REVIEW_CYCLE_CITATION_MISSING``), and a post-claim cycle the approval cannot adopt is
refused (FR-014, ``REVIEW_CYCLE_NOT_ADOPTABLE``). A forced move is not a review and writes none
(FR-006). #6709's edge semantics are pinned (FR-012). Refusals write nothing (NFR-003).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.review.artifacts import ReviewCycleArtifact
from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h
from tests.specify_cli.cli.commands.agent.test_approval_honesty_claimant import (
    _CLAIMANT,
    _claimed_mission,
    _json_payload,
    _latest,
    _snapshot,
)
from tests.specify_cli.cli.commands.agent.test_verdict_attribution_4670 import _move

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CITATION_MISSING = "REVIEW_CYCLE_CITATION_MISSING"
_NOT_ADOPTABLE = "REVIEW_CYCLE_NOT_ADOPTABLE"
_WP_SLUG = "WP01-core"


def _wp_dir(feature_dir: Path) -> Path:
    return feature_dir / "tasks" / _WP_SLUG


def _cycles(feature_dir: Path) -> list[str]:
    return sorted(path.name for path in _wp_dir(feature_dir).glob("review-cycle-*.md"))


def _pointer(mission_slug: str, n: int) -> str:
    return f"review-cycle://{mission_slug}/{_WP_SLUG}/review-cycle-{n}.md"


def _write_reviewer_cycle(feature_dir: Path, mission_slug: str, n: int, *, reviewer: str = _CLAIMANT) -> Path:
    """The claimant's own review, written as ``review-cycle-N.md`` after the claim (#7571)."""
    path = _wp_dir(feature_dir) / f"review-cycle-{n}.md"
    ReviewCycleArtifact(
        cycle_number=n,
        wp_id="WP01",
        mission_slug=mission_slug,
        reviewer_agent=reviewer,
        reviewed_at="2026-01-02T00:00:02Z",
        body="APPROVE: every acceptance criterion holds; the reviewer's own words.\n",
    ).write(path)
    return path


def _commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True, capture_output=True)


def _references(record: dict[str, Any]) -> set[str]:
    return {
        value
        for value in (
            record.get("review_ref"),
            (record.get("review_result") or {}).get("reference"),
            ((record.get("evidence") or {}).get("review") or {}).get("reference"),
        )
        if value
    }


def _output(result: Any) -> str:
    return " ".join(result.output.split())


# ---------------------------------------------------------------------------
# FR-008: adopt the reviewer's own cycle
# ---------------------------------------------------------------------------


def test_reviewer_written_cycle_is_adopted_not_doubled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 1 (#7571/#3451): one review, one cycle. Red on the base: it wrote review-cycle-2.md too."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "adopt")
    written = _write_reviewer_cycle(feature_dir, mission_slug, 1)
    reviewer_bytes = written.read_bytes()

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed"])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md"]
    assert written.read_bytes() == reviewer_bytes, "adoption writes nothing, not even to the adopted file"
    assert _references(_latest(feature_dir, "approved")) == {_pointer(mission_slug, 1)}


def test_adopted_cycle_reports_its_pointer_in_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSON envelope and the event name the same adopted cycle; an uncommitted file is local-only."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "adopt-json")
    _write_reviewer_cycle(feature_dir, mission_slug, 1)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert payload["review_feedback"] == _pointer(mission_slug, 1)
    assert payload["verdict_durably_persisted"] is False
    assert _references(_latest(feature_dir, "approved")) == {_pointer(mission_slug, 1)}


def test_committed_adopted_cycle_is_durable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "adopt-durable")
    _write_reviewer_cycle(feature_dir, mission_slug, 1)
    _commit_all(repo, "reviewer writes cycle 1")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert payload["verdict_durably_persisted"] is True
    assert _cycles(feature_dir) == ["review-cycle-1.md"]


def test_adopted_cycle_survives_a_failed_emit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Risk: the revert compensator must never delete or revert the reviewer's adopted file."""
    from specify_cli.cli.commands.agent import tasks_move_task as _tmt

    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "adopt-revert")
    written = _write_reviewer_cycle(feature_dir, mission_slug, 1)
    _commit_all(repo, "reviewer writes cycle 1")
    reviewer_bytes = written.read_bytes()
    head_before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout

    def _failing_execute(_st: object, _ports: object) -> None:
        raise RuntimeError("simulated transition-emit failure after adoption")

    monkeypatch.setattr(_tmt, "_mt_execute", _failing_execute)
    result = _move(["WP01", "--to", "approved", "--mission", mission_slug])

    assert result.exit_code != 0, result.output
    assert written.read_bytes() == reviewer_bytes
    head_after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout
    assert head_after == head_before, "no revert commit touched the adopted cycle"


def test_claimant_without_a_cycle_gets_exactly_one_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 2: no reviewer cycle: the approval writes one (today's behaviour, kept)."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "write-one")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed"])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md"]
    assert _references(_latest(feature_dir, "approved")) == {_pointer(mission_slug, 1)}


def test_stale_cycle_is_not_adopted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 3 (FR-009): approval cycle 1, rejection cycle 2, rework, claim, approval: cycle 3 is written."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0
    first = h.move(m, h.WP, "approved", h.REVIEWER, "--note", "first approval")
    assert first.exit_code == 0, first.output
    feedback = m.repo / "review-feedback-2.md"
    feedback.write_text("## Issues\n\nA late finding.\n", encoding="utf-8")
    reopened = h.move(m, h.WP, "planned", h.REVIEWER, "--review-feedback-file", str(feedback))
    assert reopened.exit_code == 0, reopened.output
    assert h.review_cycle_files(m) == ["review-cycle-1.md", "review-cycle-2.md"]
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0

    result = h.move(m, h.WP, "approved", h.REVIEWER, "--note", "second approval")

    assert result.exit_code == 0, result.output
    assert h.review_cycle_files(m) == ["review-cycle-1.md", "review-cycle-2.md", "review-cycle-3.md"]
    approvals = [e for e in h.events(m) if e.get("to_lane") == "approved"]
    assert _references(approvals[-1]) == {f"review-cycle://{m.mission_slug}/{_WP_SLUG}/review-cycle-3.md"}


# ---------------------------------------------------------------------------
# FR-010: cited cycles exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "citation",
    [
        pytest.param(["--note", "cycle 4 APPROVE"], id="note"),
        pytest.param(["--approval-ref", "POINTER"], id="pointer"),
    ],
)
def test_citation_of_a_missing_cycle_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, citation: list[str]) -> None:
    """Case 4 (#7570): only cycle 1 exists; "cycle 4" refuses, names the path, writes nothing."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, f"cite-missing-{citation[0][2:]}")
    _write_reviewer_cycle(feature_dir, mission_slug, 1)
    argv = [_pointer(mission_slug, 4) if arg == "POINTER" else arg for arg in citation]
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, *argv])

    assert result.exit_code == 1, result.output
    output = _output(result)
    assert _CITATION_MISSING in output
    assert "review-cycle-4.md" in output
    assert _snapshot(repo, feature_dir) == before


def test_citation_refusal_carries_the_code_in_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "cite-json")
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "cycle 4 APPROVE", "--json"])

    assert result.exit_code == 1, result.output
    assert _json_payload(result.output)["code"] == _CITATION_MISSING
    assert _snapshot(repo, feature_dir) == before


def test_citation_of_a_rejections_cycle_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 5: cycle 1 is the recorded rejection's cycle."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "in_review_to_planned")
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0
    before_log = (m.feature_dir / "status.events.jsonl").read_bytes()

    result = h.move(m, h.WP, "approved", h.REVIEWER, "--note", "cycle 1 APPROVE")

    assert result.exit_code == 1, result.output
    assert _CITATION_MISSING in _output(result) and "review-cycle-1.md" in _output(result)
    assert (m.feature_dir / "status.events.jsonl").read_bytes() == before_log
    assert h.review_cycle_files(m) == ["review-cycle-1.md"]


def test_citation_of_a_cycle_from_before_the_latest_claim_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 6 (R7): cycle 1 answered an earlier approval; a later claim makes it stale."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0
    assert h.move(m, h.WP, "approved", h.REVIEWER, "--note", "first approval").exit_code == 0
    feedback = m.repo / "review-feedback-2.md"
    feedback.write_text("## Issues\n\nA late finding.\n", encoding="utf-8")
    assert h.move(m, h.WP, "planned", h.REVIEWER, "--review-feedback-file", str(feedback)).exit_code == 0
    h.drive_to_for_review(m)
    assert h.move(m, h.WP, "in_review", h.REVIEWER).exit_code == 0
    before_log = (m.feature_dir / "status.events.jsonl").read_bytes()

    result = h.move(m, h.WP, "approved", h.REVIEWER, "--note", "cycle 1 still APPROVE")

    assert result.exit_code == 1, result.output
    assert _CITATION_MISSING in _output(result) and "review-cycle-1.md" in _output(result)
    assert (m.feature_dir / "status.events.jsonl").read_bytes() == before_log


def test_valid_citation_adopts_the_cited_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 7: the claimant wrote cycle 1 after the claim and cites it: accepted, adopted, no cycle 2."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "cite-valid")
    _write_reviewer_cycle(feature_dir, mission_slug, 1)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "cycle 1 APPROVE"])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md"]
    assert _references(_latest(feature_dir, "approved")) == {_pointer(mission_slug, 1)}


def test_cycle_pointer_approval_ref_adopts_and_is_the_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "cite-pointer")
    _write_reviewer_cycle(feature_dir, mission_slug, 1)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--approval-ref", _pointer(mission_slug, 1)])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md"]
    assert _references(_latest(feature_dir, "approved")) == {_pointer(mission_slug, 1)}


# ---------------------------------------------------------------------------
# FR-014: a post-claim cycle the approval cannot adopt
# ---------------------------------------------------------------------------


def test_cycle_without_frontmatter_is_not_adoptable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 8a: a hand-written ``review-cycle-1.md`` with no frontmatter refuses; nothing written."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "not-adoptable-raw")
    path = _wp_dir(feature_dir) / "review-cycle-1.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("APPROVE, looks good\n", encoding="utf-8")
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed"])

    assert result.exit_code == 1, result.output
    output = _output(result)
    assert _NOT_ADOPTABLE in output and "review-cycle-1.md" in output
    assert "review-feedback-1.md" in output and "--review-feedback-file" in output
    assert _snapshot(repo, feature_dir) == before


def test_cycle_of_another_identity_is_not_adoptable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 8b: a post-claim cycle attributed to another reviewer refuses; nothing written."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "not-adoptable-other")
    _write_reviewer_cycle(feature_dir, mission_slug, 1, reviewer="codex:gpt-5:reviewer-renata")
    before = _snapshot(repo, feature_dir)

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--json"])

    assert result.exit_code == 1, result.output
    payload = _json_payload(result.output)
    assert payload["code"] == _NOT_ADOPTABLE
    assert "codex:gpt-5:reviewer-renata" in payload["error"]
    assert _snapshot(repo, feature_dir) == before


def test_forced_approval_is_not_judged_by_the_cycle_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refusals are unforced only: ``--force`` over a non-adoptable cycle is the operator override."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "not-adoptable-forced")
    _write_reviewer_cycle(feature_dir, mission_slug, 1, reviewer="codex:gpt-5:reviewer-renata")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--force", "--agent", "kitty-orchestrator"])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md"]
    assert _latest(feature_dir, "approved")["evidence"]["review"]["reference"] == "force-override"


# ---------------------------------------------------------------------------
# #6652 feedback-file leg, FR-006 forced moves, FR-012 pins, honest body
# ---------------------------------------------------------------------------


def test_feedback_file_on_approval_writes_one_cycle_with_the_feedback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 9: ``--review-feedback-file`` keeps today's guarded write (#6652)."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "feedback")
    feedback = repo / "review-feedback-1.md"
    feedback.write_text("APPROVE with a note on naming.\n", encoding="utf-8")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--review-feedback-file", str(feedback)])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md"]
    assert "APPROVE with a note on naming." in (_wp_dir(feature_dir) / "review-cycle-1.md").read_text(encoding="utf-8")


def test_feedback_file_beside_a_post_claim_cycle_skips_adoption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 9, documented outcome: with a feedback file, no adoption: today's write allocates cycle 2."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "feedback-and-cycle")
    _write_reviewer_cycle(feature_dir, mission_slug, 1)
    feedback = repo / "review-feedback-2.md"
    feedback.write_text("APPROVE, feedback-file route.\n", encoding="utf-8")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--review-feedback-file", str(feedback)])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == ["review-cycle-1.md", "review-cycle-2.md"]
    assert _references(_latest(feature_dir, "approved")) == {_pointer(mission_slug, 2)}


def test_forced_approval_writes_no_review_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 10 (FR-006): a forced approval is not a review: no cycle, reference ``force-override``."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "forced")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--force", "--agent", "kitty-orchestrator", "--json"])

    assert result.exit_code == 0, result.output
    assert _cycles(feature_dir) == []
    payload = json.loads(result.output[result.output.index("{") :])
    assert "review_feedback" not in payload
    assert _references(_latest(feature_dir, "approved")) == {"force-override"}


def test_done_after_approval_with_a_feedback_file_warns_and_writes_no_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 11a (FR-012 pin): ``approved -> done`` with a feedback file warns and writes nothing."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "done-feedback")
    assert _move(["WP01", "--to", "approved", "--mission", mission_slug]).exit_code == 0
    cycles_after_approval = _cycles(feature_dir)
    feedback = repo / "review-feedback-9.md"
    feedback.write_text("late note\n", encoding="utf-8")

    result = _move(
        [
            "WP01",
            "--to",
            "done",
            "--mission",
            mission_slug,
            "--agent",
            _CLAIMANT,
            "--review-feedback-file",
            str(feedback),
            "--done-override-reason",
            "fixture lane is not merged",
        ]
    )

    assert result.exit_code == 0, result.output
    assert "was not recorded" in _output(result)
    assert _cycles(feature_dir) == cycles_after_approval


def test_empty_feedback_file_on_approval_warns_and_writes_the_synthesized_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 11b (FR-012 pin): an empty feedback file warns; the synthesized cycle is written."""
    repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "empty-feedback")
    feedback = repo / "review-feedback-1.md"
    feedback.write_text("   \n", encoding="utf-8")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--review-feedback-file", str(feedback)])

    assert result.exit_code == 0, result.output
    assert "the file is empty" in _output(result)
    assert _cycles(feature_dir) == ["review-cycle-1.md"]


def test_written_cycle_names_the_reviewer_of_record_honestly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 12: body and reproduction command name the reviewer of record; no ``approval:<WP>`` token."""
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "honest-body")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--note", "Review passed"])

    assert result.exit_code == 0, result.output
    text = (_wp_dir(feature_dir) / "review-cycle-1.md").read_text(encoding="utf-8")
    assert f"Approved by {_CLAIMANT}." in text
    assert f"--agent {_CLAIMANT}" in text
    assert "approval:WP01" not in text
    assert "Reference:" not in text


def test_written_cycle_keeps_a_caller_approval_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo, feature_dir, mission_slug = _claimed_mission(tmp_path, monkeypatch, "honest-ref")

    result = _move(["WP01", "--to", "approved", "--mission", mission_slug, "--approval-ref", "PR-42 review thread"])

    assert result.exit_code == 0, result.output
    text = (_wp_dir(feature_dir) / "review-cycle-1.md").read_text(encoding="utf-8")
    assert f"Approved by {_CLAIMANT}.\nReference: PR-42 review thread" in text
