"""WP07/T026-T029a — claim writers ride ``policy_metadata``, not frontmatter.

Covers the FR-004/FR-005/FR-008/FR-014 cutover for the implementation- and
review-claim writers in ``cli.commands.agent.workflow_executor``:

- **T026/T027**: the ``(shell_pid, shell_pid_created_at, agent)`` triple rides
  the ``planned -> claimed`` (and ``for_review -> in_review``) transition's
  ``policy_metadata`` sidecar (:func:`~specify_cli.status.emit.build_claim_policy_metadata`),
  using the EXACT key names WP01's reducer fold
  (``reducer._wp_state_from_event``) extracts into the reduced snapshot.
- **FR-005/C-001 dual-write bridge**: until an operator flips a mission's
  ``meta.json`` ``status_phase`` to ``"1"`` (post WP03 backfill+verify / WP05
  reader cutover), the claim frontmatter mirror (``shell_pid``/``agent``)
  stays MANDATORY (default ON) so a fresh claim is never invisible to a still
  frontmatter-reading liveness check. Once flipped, WP07's own dual-write is
  torn down: the claim becomes a byte-identical no-op on the WP file
  (SC-001/SC-005 content-hash stability).
- **T029a**: resume/re-claim of an already ``in_progress`` WP refreshes
  ``shell_pid``/``shell_pid_created_at`` via an off-axis ``InnerStateChanged``
  annotation (never ``policy_metadata`` -- resume is not a lane transition),
  and never touches the WP file.

Fixture pattern mirrors ``test_workflow_canonical_cleanup.py`` (WP04): a
non-git ``tmp_path`` repo root with ``safe_commit``/branch-checkout
monkeypatched away so the CLAIM SIDE (status event emission + reduction) runs
for real while the git-commit side is stubbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

from specify_cli.cli.commands.agent import workflow
from specify_cli.analysis_report import write_analysis_report
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status import Lane, StatusEvent, StatusSnapshot, read_events, reduce
from specify_cli.status.store import append_event, read_event_stream

pytestmark = pytest.mark.fast

_MISSION_SLUG = "wp07-claim-policy-metadata-demo"


# ---------------------------------------------------------------------------
# Shared fixture helpers (adapted from test_workflow_canonical_cleanup.py --
# a NEW, WP07-owned test module per create_intent, not an extension of that
# file, which is not in this WP's owned_files).
# ---------------------------------------------------------------------------


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str, *, actor: str = "test") -> None:
    """Seed a WP into a specific lane in the event log (genesis -> lane)."""
    event = StatusEvent(
        event_id=f"test-{wp_id}-{lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(lane),
        at="2026-01-01T00:00:00+00:00",
        actor=actor,
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _write_wp_file(path: Path, wp_id: str, lane: str) -> None:
    # NOTE: no authored ``lane:`` field -- lane is event-log-only (this
    # mission's own doctrine; ``FrontmatterManager.WP_FIELD_ORDER`` never
    # carried it). Authoring one would activate the UNRELATED, pre-existing
    # ``_mirror_phase1_frontmatter_lane`` compatibility bridge once
    # ``status_phase`` is flipped to ``"1"`` for the cutover tests below,
    # which would spuriously mutate the WP file for a reason that has
    # nothing to do with this WP's shell_pid concern.
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": ["T001"],
        "title": f"{wp_id} Test",
        "phase": "Phase 0",
        "execution_mode": "code_change",
        "owned_files": [f"src/{wp_id.lower()}/**"],
        "authoritative_surface": f"src/{wp_id.lower()}/",
        "assignee": "",
        "agent": "",
        "shell_pid": "",
        "review_status": "",
        "reviewed_by": "",
        "dependencies": [],
    }
    body = f"# {wp_id} Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z - system - Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _write_current_analysis_report(feature_dir: Path, repo_root: Path) -> None:
    """Write a current analysis report for implement success-path fixtures."""
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    if not (feature_dir / "tasks.md").exists():
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )


def _mint_fake_worktree(repo_root: Path, workspace: Path) -> None:
    """Mark a fixture workspace as a git worktree (#1833 husk guard)."""
    workspace.mkdir(parents=True, exist_ok=True)
    gitdir = repo_root / ".git" / "worktrees" / workspace.name
    gitdir.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")


def _set_status_phase(feature_dir: Path, phase: str) -> None:
    """Flip a mission's ``status_phase`` (the FR-005 dual-write bridge flag)."""
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = phase
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture()
def workflow_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo_root = tmp_path
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text(
        "vcs:\n  type: git\nproject:\n  uuid: test-project-uuid\n  slug: test-project\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out",
        lambda repo_root, mission_slug: (repo_root, "main"),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow.safe_commit",
        lambda **kwargs: True,
    )
    return repo_root


def _seed_mission(workflow_repo: Path, *, lane: str = "planned") -> tuple[Path, Path]:
    """Seed a single-WP mission ready for an implementation claim.

    Returns ``(feature_dir, wp_path)``.
    """
    feature_dir = workflow_repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane=lane)
    _seed_wp_lane(feature_dir, "WP01", lane)
    _write_current_analysis_report(feature_dir, workflow_repo)
    _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, _MISSION_SLUG))
    return feature_dir, wp_path


def _claimed_transition(feature_dir: Path) -> StatusEvent:
    events = read_events(feature_dir)
    matches = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
    assert matches, f"expected a planned -> claimed transition for WP01, got events: {events}"
    return matches[-1]


def _reduce_full(feature_dir: Path) -> StatusSnapshot:
    """Reduce BOTH transitions and off-axis annotations (``reduce(read_events(...))``
    alone drops annotations -- ``read_events`` is deliberately a
    transitions-only view; the reducer's annotation-aware fold needs
    :func:`read_event_stream`)."""
    stream = read_event_stream(feature_dir)
    return reduce(stream.transitions, stream.annotations)


# ---------------------------------------------------------------------------
# T026 — implementation-claim: policy_metadata carries the triple.
# ---------------------------------------------------------------------------


class TestImplementClaimPolicyMetadata:
    def test_claim_transition_carries_shell_pid_and_agent_in_policy_metadata(self, workflow_repo: Path) -> None:
        feature_dir, _wp_path = _seed_mission(workflow_repo)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-agent"],
        )
        assert result.exit_code == 0, result.stdout

        claimed_event = _claimed_transition(feature_dir)
        assert claimed_event.policy_metadata is not None
        assert claimed_event.policy_metadata["agent"] == "test-agent"
        assert isinstance(claimed_event.policy_metadata["shell_pid"], int)
        # Best-effort baseline: present on this (real, live) test process.
        assert "shell_pid_created_at" in claimed_event.policy_metadata

    def test_claim_reduces_shell_pid_into_snapshot_slot(self, workflow_repo: Path) -> None:
        feature_dir, _wp_path = _seed_mission(workflow_repo)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-agent"],
        )
        assert result.exit_code == 0, result.stdout

        snapshot = _reduce_full(feature_dir)
        wp_state = snapshot.work_packages["WP01"]
        assert wp_state.get("agent") == "test-agent"
        assert isinstance(wp_state.get("shell_pid"), int)

    def test_claim_leaves_wp_file_byte_stable(self, workflow_repo: Path) -> None:
        """SC-001/SC-005 (post-cutover, UNCONDITIONAL): the runtime-state
        dual-write is torn down (WP04, FR-006/FR-007), so a claim writes NO
        shell_pid into frontmatter and the WP file's bytes are unchanged across
        the claim — regardless of ``status_phase`` (the reader is unconditional;
        the flag-OFF frontmatter mirror was deleted, not gated)."""
        feature_dir, wp_path = _seed_mission(workflow_repo)
        # No status_phase set (today's default): byte-stability holds anyway —
        # the dual-write is gone unconditionally, not merely flag-gated.
        assert not (feature_dir / "meta.json").read_text(encoding="utf-8").count('"status_phase"')
        before = wp_path.read_bytes()

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-agent"],
        )
        assert result.exit_code == 0, result.stdout

        after = wp_path.read_bytes()
        assert after == before, "WP file must be byte-identical across the claim once the dual-write is torn down"

        # The claim triple still reaches the transition + snapshot even
        # though the frontmatter mirror is gone.
        claimed_event = _claimed_transition(feature_dir)
        assert claimed_event.policy_metadata is not None
        assert claimed_event.policy_metadata["agent"] == "test-agent"
        snapshot = _reduce_full(feature_dir)
        assert isinstance(snapshot.work_packages["WP01"].get("shell_pid"), int)


# ---------------------------------------------------------------------------
# T027 — review-claim: policy_metadata + InnerStateChanged annotation.
# ---------------------------------------------------------------------------


class TestReviewClaimPolicyMetadata:
    def test_review_claim_carries_policy_metadata_and_reduces_shell_pid(self, workflow_repo: Path) -> None:
        feature_dir, _wp_path = _seed_mission(workflow_repo, lane="for_review")

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-reviewer"],
        )
        assert result.exit_code == 0, result.stdout

        events = read_events(feature_dir)
        review_events = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "in_review"]
        assert review_events, f"expected a for_review -> in_review transition, got: {events}"
        assert review_events[-1].policy_metadata is not None
        assert review_events[-1].policy_metadata["agent"] == "test-reviewer"

        stream = read_event_stream(feature_dir)
        claim_annotations = [
            event
            for event in stream.annotations
            if event.wp_id == "WP01" and event.delta.agent == "test-reviewer"
        ]
        assert len(claim_annotations) == 1

        # The reducer's transition fold only special-cases planned->claimed
        # (WP01), so the review-claim's shell_pid reaches the snapshot via
        # the InnerStateChanged annotation WP07/T027 emits alongside it.
        snapshot = _reduce_full(feature_dir)
        wp_state = snapshot.work_packages["WP01"]
        assert isinstance(wp_state.get("shell_pid"), int)

    def test_review_claim_cutover_flag_on_leaves_wp_file_byte_stable(self, workflow_repo: Path) -> None:
        feature_dir, wp_path = _seed_mission(workflow_repo, lane="for_review")
        _set_status_phase(feature_dir, "1")
        before = wp_path.read_bytes()

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-reviewer"],
        )
        assert result.exit_code == 0, result.stdout

        assert wp_path.read_bytes() == before, "WP file must stay byte-identical once the dual-write is torn down"

    def test_review_reclaim_annotation_failure_is_terminal(
        self,
        workflow_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _feature_dir, _wp_path = _seed_mission(workflow_repo, lane="for_review")
        first = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-reviewer"],
        )
        assert first.exit_code == 0, first.stdout

        def _fail_reclaim(*args: object, **kwargs: object) -> None:
            raise OSError("simulated durable append failure")

        monkeypatch.setattr("specify_cli.status.emit_inner_state_changed", _fail_reclaim)
        second = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-reviewer"],
        )

        assert second.exit_code != 0


# ---------------------------------------------------------------------------
# T029a — resume/re-claim of an already in_progress WP refreshes shell_pid
# via an InnerStateChanged annotation, never touching the WP file.
# ---------------------------------------------------------------------------


class TestResumeShellPidRefresh:
    def test_resume_emits_innerstatechanged_refresh_without_touching_wp_file(
        self,
        workflow_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        feature_dir, wp_path = _seed_mission(workflow_repo)

        first = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-agent"],
        )
        assert first.exit_code == 0, first.stdout

        annotations_after_claim = read_event_stream(feature_dir).annotations
        wp_bytes_after_claim = wp_path.read_bytes()
        commit_calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            workflow,
            "_commit_workflow_change",
            lambda **kwargs: commit_calls.append(kwargs),
        )

        # Bare resume: re-invoke implement on the now in_progress WP WITHOUT
        # --agent (agent assignment already resolved from the first claim,
        # so the ``--agent required`` guard does not fire). This is the
        # true no-op branch -- historically a complete no-op that never
        # touched the WP file; T029a adds the off-axis refresh here. (A
        # resume that re-passes --agent instead re-enters the T026 dual-write
        # bridge -- a DIFFERENT, pre-existing code path this test does not
        # target.)
        second = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG],
        )
        assert second.exit_code == 0, second.stdout

        stream_after_resume = read_event_stream(feature_dir)
        assert len(stream_after_resume.annotations) > len(annotations_after_claim), (
            "expected the resume to persist a NEW InnerStateChanged annotation"
        )
        assert len(commit_calls) == 1, (
            "resume refresh must enter the status-artifact commit/rollback boundary"
        )
        assert "Refresh WP01 implementation liveness" in str(
            commit_calls[0]["message"]
        )

        # No fresh planned -> claimed transition was driven by the resume.
        claimed_transitions = [e for e in stream_after_resume.transitions if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
        assert len(claimed_transitions) == 1, "resume must not re-drive the planned -> claimed transition"

        # The WP file is never touched by the resume refresh (no frontmatter
        # write at all for this path, regardless of the FR-005 flag).
        assert wp_path.read_bytes() == wp_bytes_after_claim

        # The reduced snapshot's shell_pid slot reflects the refresh (still
        # an int; this test process's own pid both times).
        snapshot = reduce(stream_after_resume.transitions, stream_after_resume.annotations)
        assert isinstance(snapshot.work_packages["WP01"].get("shell_pid"), int)

    def test_resume_refresh_persistence_failure_is_terminal(
        self,
        workflow_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        first = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", "test-agent"],
        )
        assert first.exit_code == 0, first.stdout

        def _fail_refresh(*args: object, **kwargs: object) -> None:
            raise OSError("simulated durable append failure")

        monkeypatch.setattr(
            "specify_cli.status.emit_inner_state_changed",
            _fail_refresh,
        )
        second = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG],
        )

        assert second.exit_code != 0
