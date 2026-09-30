"""Tests for the ReviewCycleArtifact model (WP01).

Coverage target: 90%+ for src/specify_cli/review/artifacts.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.post_merge.review_artifact_consistency import (
    RejectedReviewArtifactFinding,
    find_rejected_review_artifact_conflicts,
)
from specify_cli.review.artifacts import (
    AffectedFile,
    ReviewCycleArtifact,
)
from specify_cli.review.cycle import create_rejected_review_cycle
from specify_cli.status import (
    ReviewOverride,
    ReviewResult,
    StatusEvent,
    emit_inner_state_changed,
)
from specify_cli.status._unsafe import append_event
from specify_cli.status.models import Lane, WPInnerStateDelta

pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_artifact(**kwargs: object) -> ReviewCycleArtifact:
    defaults: dict[str, Any] = {
        "cycle_number": 1,
        "wp_id": "WP01",
        "mission_slug": "066-review-loop-stabilization",
        "reviewer_agent": "claude",
        "reviewed_at": "2026-04-06T12:00:00Z",
        "affected_files": [
            AffectedFile(
                path="src/specify_cli/cli/commands/agent/tasks.py",
                line_range="245-265",
            )
        ],
        "reproduction_command": "pytest tests/review/ -x",
        "body": "## Feedback\n\nPlease fix the issues.",
    }
    defaults.update(kwargs)
    return ReviewCycleArtifact(**defaults)


# ---------------------------------------------------------------------------
# T1: to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

def test_review_cycle_artifact_to_dict_round_trip() -> None:
    original = _sample_artifact()
    d = original.to_dict()
    assert "verdict" not in d  # FR-003/SC-007 (WP06): structurally no verdict field
    restored = ReviewCycleArtifact.from_dict(d, body=original.body)

    assert restored.cycle_number == original.cycle_number
    assert restored.wp_id == original.wp_id
    assert restored.mission_slug == original.mission_slug
    assert restored.reviewer_agent == original.reviewer_agent
    assert restored.reviewed_at == original.reviewed_at
    assert restored.reproduction_command == original.reproduction_command
    assert restored.body == original.body
    assert restored.affected_files == [
        AffectedFile(path="src/specify_cli/cli/commands/agent/tasks.py", line_range="245-265")
    ]


# ---------------------------------------------------------------------------
# T2: write() / from_file() round-trip
# ---------------------------------------------------------------------------

def test_write_and_from_file_round_trip(tmp_path: Path) -> None:
    artifact = _sample_artifact()
    dest = tmp_path / "review-cycle-1.md"
    artifact.write(dest)

    assert dest.exists()
    restored = ReviewCycleArtifact.from_file(dest)

    assert restored.cycle_number == artifact.cycle_number
    assert restored.wp_id == artifact.wp_id
    assert restored.mission_slug == artifact.mission_slug
    assert restored.reviewer_agent == artifact.reviewer_agent
    assert restored.reviewed_at == artifact.reviewed_at
    assert restored.reproduction_command == artifact.reproduction_command
    assert restored.body.strip() == artifact.body.strip()
    assert restored.affected_files == artifact.affected_files


def test_write_and_from_file_preserves_complete_override(tmp_path: Path) -> None:
    """A write()→from_file() cycle must not drop the approval override (#1924).

    The override block is what the approval gate stamps onto a rejected latest
    so the terminal-lane consistency gate honors it; if to_dict() dropped it, a
    round-trip would silently reintroduce #1924-style merge gating.
    """
    artifact = _sample_artifact(
        override_actor="operator",
        override_reason="Arbiter approved despite the rejected latest cycle.",
    )
    dest = tmp_path / "review-cycle-1.md"
    artifact.write(dest)
    restored = ReviewCycleArtifact.from_file(dest)

    assert restored.override_actor == artifact.override_actor
    assert restored.override_reason == artifact.override_reason


def test_to_dict_omits_override_keys_when_absent() -> None:
    """Artifacts with no override emit no override keys (byte-identical output)."""
    d = _sample_artifact().to_dict()
    assert "review_artifact_override_actor" not in d
    assert "review_artifact_override_reason" not in d


# ---------------------------------------------------------------------------
# T3: next_cycle_number() on empty dir → 1
# ---------------------------------------------------------------------------

def test_next_cycle_number_empty_dir(tmp_path: Path) -> None:
    assert ReviewCycleArtifact.next_cycle_number(tmp_path) == 1


# ---------------------------------------------------------------------------
# T4: next_cycle_number() with 3 existing files → 4
# ---------------------------------------------------------------------------

def test_next_cycle_number_with_existing(tmp_path: Path) -> None:
    for i in range(1, 4):
        (tmp_path / f"review-cycle-{i}.md").write_text("---\n---\n", encoding="utf-8")
    assert ReviewCycleArtifact.next_cycle_number(tmp_path) == 4


# ---------------------------------------------------------------------------
# T5: latest() on empty dir → None
# ---------------------------------------------------------------------------

def test_latest_empty_dir(tmp_path: Path) -> None:
    assert ReviewCycleArtifact.latest(tmp_path) is None


# ---------------------------------------------------------------------------
# T6: latest() with multiple files → highest cycle number
# ---------------------------------------------------------------------------

def test_latest_with_multiple(tmp_path: Path) -> None:
    for cycle_n in (1, 3, 2):
        artifact = _sample_artifact(cycle_number=cycle_n, body=f"cycle {cycle_n}")
        artifact.write(tmp_path / f"review-cycle-{cycle_n}.md")

    latest = ReviewCycleArtifact.latest(tmp_path)
    assert latest is not None
    assert latest.cycle_number == 3


# ---------------------------------------------------------------------------
# T7: AffectedFile with optional line_range = None
# ---------------------------------------------------------------------------

def test_affected_file_optional_line_range() -> None:
    af = AffectedFile(path="src/foo.py")
    assert af.line_range is None
    d = af.to_dict()
    assert "line_range" not in d
    restored = AffectedFile.from_dict(d)
    assert restored.line_range is None


# ---------------------------------------------------------------------------
# T8: frontmatter field completeness
# ---------------------------------------------------------------------------

def test_frontmatter_field_completeness(tmp_path: Path) -> None:
    artifact = _sample_artifact()
    dest = tmp_path / "review-cycle-1.md"
    artifact.write(dest)

    text = dest.read_text(encoding="utf-8")
    for field_name in (
        "cycle_number",
        "wp_id",
        "mission_slug",
        "reviewer_agent",
        "reviewed_at",
        "affected_files",
        "reproduction_command",
    ):
        assert field_name in text, f"Missing field '{field_name}' in written artifact"
    # FR-003/SC-007 (WP06): the artifact structurally carries no verdict field
    # -- a dedicated, non-vacuous serialized assertion lives in
    # tests/review/test_artifacts_no_verdict_field.py; this is a light
    # corroborating check at this test's own existing completeness site.
    assert "verdict" not in text


# ---------------------------------------------------------------------------
# T9: legacy feedback:// pointer resolution
# ---------------------------------------------------------------------------

def test_legacy_feedback_pointer_resolution(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow_cores import resolve_review_feedback_pointer as _resolve_review_feedback_pointer

    # Create a fake git common-dir structure
    feedback_dir = tmp_path / ".git" / "spec-kitty" / "feedback" / "066-test" / "WP01"
    feedback_dir.mkdir(parents=True)
    feedback_file = feedback_dir / "20260406T120000Z-abcd1234.md"
    feedback_file.write_text("feedback content", encoding="utf-8")

    pointer = "feedback://066-test/WP01/20260406T120000Z-abcd1234.md"

    with patch(
        "specify_cli.review.cycle._resolve_git_common_dir",
        return_value=tmp_path / ".git",
    ):
        result = _resolve_review_feedback_pointer(tmp_path, pointer)

    assert result is not None
    assert result == feedback_file.resolve()


# ---------------------------------------------------------------------------
# T10: new review-cycle:// pointer resolution
# ---------------------------------------------------------------------------

def test_new_review_cycle_pointer_resolution(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow_cores import resolve_review_feedback_pointer as _resolve_review_feedback_pointer

    # Create a fake review artifact
    artifact_dir = (
        tmp_path
        / "kitty-specs"
        / "066-review-loop-stabilization"
        / "tasks"
        / "WP01-persisted-review-artifact-model"
    )
    artifact_dir.mkdir(parents=True)
    artifact_file = artifact_dir / "review-cycle-1.md"
    _sample_artifact(
        mission_slug="066-review-loop-stabilization",
        wp_id="WP01",
        cycle_number=1,
        body="## Feedback\n\nCanonical content.",
    ).write(artifact_file)

    pointer = "review-cycle://066-review-loop-stabilization/WP01-persisted-review-artifact-model/review-cycle-1.md"
    result = _resolve_review_feedback_pointer(tmp_path, pointer)

    assert result is not None
    assert result == artifact_file.resolve()


# ---------------------------------------------------------------------------
# T11: "force-override" sentinel returns None
# ---------------------------------------------------------------------------

def test_force_override_pointer_returns_none(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow_cores import resolve_review_feedback_pointer as _resolve_review_feedback_pointer

    result = _resolve_review_feedback_pointer(tmp_path, "force-override")
    assert result is None


# ---------------------------------------------------------------------------
# T12: _persist_review_feedback() creates artifact file
# ---------------------------------------------------------------------------

def test_persist_review_feedback_creates_artifact(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.tasks import _persist_review_feedback

    # Build kitty-specs task directory so _resolve_wp_slug finds the slug
    task_dir = (
        tmp_path
        / "kitty-specs"
        / "066-test-mission"
        / "tasks"
        / "WP01-some-title"
    )
    task_dir.mkdir(parents=True)
    # Create a stub WP file so the directory scanner finds it
    (task_dir.parent / "WP01-some-title.md").write_text("---\n---\n", encoding="utf-8")

    # Create a feedback source file
    feedback_file = tmp_path / "feedback.md"
    feedback_file.write_text("## Issues\n\nPlease fix.", encoding="utf-8")

    persisted_path, pointer = _persist_review_feedback(
        main_repo_root=tmp_path,
        mission_slug="066-test-mission",
        task_id="WP01",
        feedback_source=feedback_file,
        reviewer_agent="claude",
    )

    assert persisted_path.exists(), f"Expected artifact at {persisted_path}"
    assert pointer.startswith("review-cycle://"), f"Expected review-cycle:// pointer, got: {pointer}"
    assert "066-test-mission" in pointer
    assert "review-cycle-1.md" in pointer

    # Verify the artifact is parseable
    artifact = ReviewCycleArtifact.from_file(persisted_path)
    assert artifact.cycle_number == 1
    assert artifact.wp_id == "WP01"
    assert artifact.mission_slug == "066-test-mission"
    assert artifact.reviewer_agent == "claude"
    assert "Please fix." in artifact.body


# ---------------------------------------------------------------------------
# WP05 (verdict-seam-write-unification-01KZ9Q35, FR-003) retired
# ``latest_review_artifact_verdict`` and ``rejected_review_artifact_for_
# terminal_lane`` (review/artifacts.py's two genuine verdict-parser
# functions) along with their frontmatter-override-recognition logic -- every
# consumer now resolves the event authority
# (``status.event_sourced_review_result`` / the reduced ``review`` snapshot
# slot) instead. The five tests below are REPOINTED, not deleted (a prior
# mission's NFR-001 node-id floor, ``tests/architectural/
# mission_exit_baseline.txt``, pins their names): each now exercises the
# EVENT-SOURCED successor of what it originally asserted about the retired
# frontmatter functions, using the surviving merge gate
# (``find_rejected_review_artifact_conflicts``) and the KEPT content loader
# (``ReviewCycleArtifact.latest``) instead.
# ---------------------------------------------------------------------------

_TEST_ARTIFACTS_MISSION_SLUG = "066-artifacts-collapse-demo"


def _artifacts_feature_dir(tmp_path: Path) -> Path:
    """A real, git-initialized ``<repo_root>/kitty-specs/<slug>`` fixture.

    A bare non-git ``feature_dir`` (no real ``.git`` ancestor) makes
    ``feature_status_lock``'s git-common-dir probe fail and fall back to
    creating its OWN ``.git/spec-kitty-locks`` directly inside ``feature_dir``
    -- which then makes ``resolve_canonical_root(feature_dir)`` treat
    ``feature_dir`` itself as a (fake) repo root, so a LATER
    ``resolve_artifact_surface``-based path reconstruction
    (``missions/_read_path_resolver.py::resolve_partition_read_dir``)
    doubles the ``kitty-specs/<slug>`` suffix. A real ``git init`` avoids the
    ambiguity entirely -- matching this module's own ``pytest.mark.git_repo``
    marker intent.
    """
    import subprocess

    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    feature_dir = tmp_path / "kitty-specs" / _TEST_ARTIFACTS_MISSION_SLUG
    feature_dir.mkdir(parents=True)
    return feature_dir


def _artifacts_append_terminal_event(
    feature_dir: Path,
    *,
    verdict: str,
    to_lane: Lane,
    event_id: str,
) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=to_lane,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(reviewer="reviewer-renata", verdict=verdict, reference="x"),
        ),
    )


def test_latest_review_artifact_verdict_reads_highest_cycle(tmp_path: Path) -> None:
    """WP05 repoint: the KEPT content loader (``ReviewCycleArtifact.latest``,
    squad #1 -- not a verdict-authority reader) still answers "what does the
    highest-numbered artifact say", the same question this test originally
    asked of the now-retired ``latest_review_artifact_verdict``. WP06 (FR-003/
    SC-007): the artifact carries no ``verdict`` field anymore, so the
    "what does it say" content this test checks is the prose ``body`` --
    still the highest-cycle-wins guarantee, just via a field that survives."""
    _sample_artifact(cycle_number=1, body="cycle 1 body").write(tmp_path / "review-cycle-1.md")
    _sample_artifact(cycle_number=2, body="cycle 2 body").write(tmp_path / "review-cycle-2.md")

    latest = ReviewCycleArtifact.latest(tmp_path)

    assert latest is not None
    assert latest.cycle_number == 2
    assert latest.body.strip() == "cycle 2 body"


def test_terminal_lane_rejected_artifact_helper_flags_approved_or_done(tmp_path: Path) -> None:
    """WP05 repoint: the event-sourced merge gate
    (``find_rejected_review_artifact_conflicts``) flags a terminal WP whose
    CURRENT event-sourced verdict is ``changes_requested``, for both
    ``approved`` and ``done`` -- the event-authority successor of the retired
    ``rejected_review_artifact_for_terminal_lane`` helper."""
    for lane, event_id in ((Lane.APPROVED, "01ARTREJ0000000000000001"), (Lane.DONE, "01ARTREJ0000000000000002")):
        sub_tmp_path = tmp_path / str(lane)
        sub_tmp_path.mkdir(parents=True)
        feature_dir = _artifacts_feature_dir(sub_tmp_path)
        _artifacts_append_terminal_event(
            feature_dir, verdict="changes_requested", to_lane=lane, event_id=event_id
        )

        findings = find_rejected_review_artifact_conflicts(feature_dir)

        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, RejectedReviewArtifactFinding)
        assert finding.verdict == "changes_requested"


def test_terminal_lane_rejected_artifact_helper_ignores_non_rejected_latest(tmp_path: Path) -> None:
    """WP05 repoint: an event-sourced ``approved`` verdict is not flagged by
    the merge gate -- the event-authority successor of the retired helper's
    "ignores non-rejected latest" guarantee."""
    feature_dir = _artifacts_feature_dir(tmp_path)
    _artifacts_append_terminal_event(
        feature_dir, verdict="approved", to_lane=Lane.APPROVED, event_id="01ARTAPP0000000000000001"
    )

    assert find_rejected_review_artifact_conflicts(feature_dir) == []


def test_complete_override_is_honored_for_terminal_lane(tmp_path: Path) -> None:
    """#1924, WP05 repoint: a complete event-sourced :class:`ReviewOverride`
    clears the merge gate over a ``changes_requested`` verdict -- the
    event-authority successor of the retired frontmatter-override
    recognition this test originally asserted."""
    feature_dir = _artifacts_feature_dir(tmp_path)
    _artifacts_append_terminal_event(
        feature_dir, verdict="changes_requested", to_lane=Lane.APPROVED, event_id="01ARTOVR0000000000000001"
    )
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(
            review=ReviewOverride(
                at="2026-01-02T00:00:00+00:00",
                actor="operator",
                wp_id="WP01",
                reason="cycle1 verified: blocker resolved, all gates green",
            )
        ),
        actor="operator",
        mission_slug=feature_dir.name,
    )

    assert find_rejected_review_artifact_conflicts(feature_dir) == []


def test_incomplete_override_still_flags_rejected_terminal_lane(tmp_path: Path) -> None:
    """WP05 repoint: an override missing the reason is incomplete
    (:class:`ReviewOverride`'s own ``complete`` predicate) and must NOT
    suppress the merge-gate flag -- the event-authority successor of the
    retired helper's "incomplete override still flags" guarantee."""
    feature_dir = _artifacts_feature_dir(tmp_path)
    _artifacts_append_terminal_event(
        feature_dir, verdict="changes_requested", to_lane=Lane.APPROVED, event_id="01ARTINC0000000000000001"
    )
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(
            review=ReviewOverride(at="2026-01-02T00:00:00+00:00", actor="operator", wp_id="WP01", reason="")
        ),
        actor="operator",
        mission_slug=feature_dir.name,
    )

    findings = find_rejected_review_artifact_conflicts(feature_dir)

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, RejectedReviewArtifactFinding)
    assert finding.verdict == "changes_requested"


# ---------------------------------------------------------------------------
# WP09 (FR-006 / I-2): next_cycle_number must derive from the numbers actually
# on disk (max(parsed) + 1), never a count of files present. A numbering gap
# (e.g. cycles 1 and 3 present, 2 missing) must not produce a colliding
# number, and an unparseable sibling must be a hard refusal, not a silent
# skip that falls back to max() over only the parseable candidates.
# ---------------------------------------------------------------------------

def test_next_cycle_number_survives_a_numbering_gap(tmp_path: Path) -> None:
    """FR-006 reproduction: cycles 1 and 3 present must derive next = 4.

    ``len(candidates) + 1`` (the pre-fix behavior) returns 3 here, colliding
    with the live ``review-cycle-3.md``. This test was run against the
    unmodified ``next_cycle_number`` and observed failing with 3 before
    T032/T033 landed (see WP09's Activity Log for the verbatim output).
    """
    (tmp_path / "review-cycle-1.md").write_text("---\n---\n", encoding="utf-8")
    (tmp_path / "review-cycle-3.md").write_text("---\n---\n", encoding="utf-8")

    assert ReviewCycleArtifact.next_cycle_number(tmp_path) == 4


def test_next_cycle_number_refuses_on_unparseable_sibling(tmp_path: Path) -> None:
    """A sibling matching the glob but not the strict numbering regex must
    refuse, naming the offending filename — not be silently excluded from
    max(), which would reproduce the identical defect one level down.
    """
    (tmp_path / "review-cycle-1.md").write_text("---\n---\n", encoding="utf-8")
    (tmp_path / "review-cycle-garbage.md").write_text("---\n---\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"review-cycle-garbage\.md"):
        ReviewCycleArtifact.next_cycle_number(tmp_path)


def test_next_cycle_number_refuses_when_derived_number_already_exists(
    tmp_path: Path,
) -> None:
    """Defensive collision guard: even if the parse step reports only cycle 1
    (e.g. a concurrent writer added review-cycle-2.md between the parse and
    the existence check), a derived number that already exists on disk must
    still refuse rather than silently colliding with the live file.
    """
    (tmp_path / "review-cycle-1.md").write_text("---\n---\n", encoding="utf-8")
    (tmp_path / "review-cycle-2.md").write_text("---\n---\n", encoding="utf-8")

    with (
        patch(
            "specify_cli.review.artifacts._parse_review_cycle_candidates",
            return_value=([1], []),
        ),
        pytest.raises(ValueError, match=r"review-cycle-2\.md"),
    ):
        ReviewCycleArtifact.next_cycle_number(tmp_path)


def test_create_rejected_review_cycle_survives_a_numbering_gap(tmp_path: Path) -> None:
    """Integration (FR-006 / SC-002): with cycles 1 and 3 present, recording a
    new verdict lands at review-cycle-4.md and does not touch cycle 3 — its
    bytes are read before and after the operation and compared byte-for-byte.
    """
    repo = tmp_path / "repo"
    artifact_dir = repo / "kitty-specs" / "001-mission" / "tasks" / "WP01-core"
    artifact_dir.mkdir(parents=True)
    _sample_artifact(cycle_number=1, body="cycle 1 verdict content").write(
        artifact_dir / "review-cycle-1.md"
    )
    _sample_artifact(cycle_number=3, body="cycle 3 verdict content").write(
        artifact_dir / "review-cycle-3.md"
    )
    cycle_3_path = artifact_dir / "review-cycle-3.md"
    cycle_3_bytes_before = cycle_3_path.read_bytes()

    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: still broken after cycle 3.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="codex",
    )

    assert created.artifact_path == artifact_dir / "review-cycle-4.md"
    assert created.artifact_path.exists()
    cycle_3_bytes_after = cycle_3_path.read_bytes()
    assert cycle_3_bytes_after == cycle_3_bytes_before


def test_gate_reads_handed_mission_dir_when_anchor_is_a_foreign_repo(
    tmp_path: Path,
) -> None:
    """#154 regression: partition resolution must not read a phantom log.

    When the canonical-root walk finds a repository that is not the mission's
    own (an ambient ancestor checkout above an ad-hoc mission dir — the shape
    every bare ``<tmp>/repo`` fixture builds), recomposing the STATUS_STATE
    partition against that foreign anchor yields a path under it that does not
    exist. Reducing that phantom reads an empty snapshot — every WP stateless,
    gate passes by default, the silent-wrong-answer shape #2885 closed. The
    handed directory is then its own sole partition."""
    import subprocess

    ambient = tmp_path / "ambient-checkout"
    ambient.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(ambient)], check=True)
    mission_dir = ambient / "repo" / "kitty-specs" / _TEST_ARTIFACTS_MISSION_SLUG
    mission_dir.mkdir(parents=True)

    _artifacts_append_terminal_event(
        mission_dir,
        verdict="changes_requested",
        to_lane=Lane.APPROVED,
        event_id="01ARTFRGN0000000000000001",
    )

    findings = find_rejected_review_artifact_conflicts(mission_dir)

    assert len(findings) == 1
    assert findings[0].wp_id == "WP01"
