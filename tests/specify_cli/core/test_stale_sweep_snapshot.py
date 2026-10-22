"""WP05 (coord-write-placement-closure-01KYCF83) / T020-T023 — stale-sweep
claim-liveness off the reduced snapshot, driven through the real
``spec-kitty agent action implement`` claim entry point (DIRECTIVE_041), plus
the frontmatter write-retirement + reader-scope proof this WP's Definition of
Done requires.

**Landing note (2026-08, `tests/regression/` campsite clean).** This is a
permanent guard, not a red-first reproduction, so it carries no `regression`
marker and lives with its direct sibling
``tests/specify_cli/core/test_stale_detection_snapshot_liveness.py`` here
rather than in `tests/regression/`. It partially overlaps that sibling (both
cover live/dead snapshot-PID staleness flips) but adds a real angle the
sibling does not: this file seeds the claim through the real
``implement`` CLI entry point (verified during this relocation — the
sibling's ``_claim`` helper writes the event directly, never invoking a CLI
command), so it also exercises the frontmatter write-retirement and
liveness-reader-scope invariants the CLI path can uniquely disturb.

**Scope note (live-evidence finding, recorded per DIRECTIVE_041/failing-test
discipline — this is NOT a fabricated red).** WP05 was planned against IC-07's
description of the codebase where ``stale_detection.py``'s
``_is_claiming_process_alive`` still read ``shell_pid`` directly out of WP
frontmatter, ``task_metadata_validation.py`` carried a comparable frontmatter
reader, and ``frontmatter.py`` was the live authoring seam for the claim
``shell_pid``/``agent`` dual-write. By the time this WP actually executed, the
entire reader-migration-before-retire sequence had already landed via prior,
already-merged work predating this mission (the FR-005/#2684 and #2816
"runtime-state corpus cutover" missions, commits ``04953ea44``/``7c1a10163``
and ``452f296fa``/``dfe6b2ead``/``65a2bb780`` — verified via
``git log main..HEAD -- <file>`` returning empty for all three of this WP's
owned production files, i.e. zero commits on this mission's base for any of
them):

* ``core/stale_detection.py``'s ``check_wp_staleness`` already resolves
  ``shell_pid``/``shell_pid_created_at`` unconditionally from the reduced
  snapshot whenever a ``feature_dir`` is supplied
  (``_resolve_claim_liveness_inputs`` -> ``_read_wp_runtime_snapshot_state``),
  never blending in the frontmatter-extracted arguments (C-001). This is
  exhaustively covered already by
  ``tests/specify_cli/core/test_stale_detection_snapshot_liveness.py``
  (a prior mission's own WP05, T018/T021) — this file adds the CLI-entry-point
  angle that file does not cover (a real ``implement`` claim, not a direct
  ``emit_status_transition`` call).
* ``task_metadata_validation.py`` never had a liveness reader to migrate: its
  only ``shell_pid`` reference is ``repair_lane_mismatch``'s parameter, which
  is folded into a free-text Activity-Log audit note (MIGRATION-ONLY legacy
  lane repair) and is never read back as a claim-liveness signal by
  ``detect_lane_mismatch``/``validate_task_metadata``/``scan_all_tasks_for_mismatches``.
  There is no reader in this file for T022 to migrate.
* the claim ``shell_pid``/``agent`` frontmatter write is already retired
  unconditionally — ``workflow_executor.py::_implement_write_claim_and_commit``
  documents "the WP file is NOT mutated for the claim... this function writes
  0 runtime bytes to the WP file", confirmed by the pre-existing
  ``tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py``
  and by WP04's own
  ``tests/specify_cli/cli/commands/agent/test_claim_event_source.py`` (this
  mission, already merged; relocated out of ``tests/regression/`` in the
  2026-08 landing fold). ``frontmatter.py`` itself never contained the
  write function (the god-write lived in ``tasks_move_task.py``'s deleted
  ``_mt_dual_write_wp_file``) — it only carries the ``shell_pid``/
  ``SHELL_PID_BASELINE_FIELD`` field-order position and the
  ``WP_RUNTIME_FIELDS`` legacy-classification set (both retained
  intentionally, out of this WP's scope to remove: ``WP_RUNTIME_FIELDS`` is
  exercised by ``implement_cores.py``'s dirty-tree-only-runtime-diff guard,
  owned by a different WP, and still legitimately classifies
  ``base_branch``/``base_commit``/``planning_base_branch`` which genuinely
  ARE still written at workspace-creation time).

This file therefore cannot be red-first for a reader migration or a write
deletion (there is neither a live frontmatter read nor a live frontmatter
write left to change): it LOCKS IN the current, already-correct behavior as
WP05's own owned regression coverage (create_intent), proven through the real
CLI claim entry point rather than the lower-level ``emit_status_transition``
call the prior mission's coverage used.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.core.stale_detection import LIVE_CLAIM_PROCESS_REASON, check_wp_staleness
from specify_cli.frontmatter import read_frontmatter, write_frontmatter
from specify_cli.status import read_events
from specify_cli.task_metadata_validation import (
    detect_lane_mismatch,
    repair_lane_mismatch,
    validate_task_metadata,
)

pytestmark = pytest.mark.fast

_MISSION_SLUG = "wp05-stale-sweep-snapshot-demo"


def _write_wp_file(path: Path, wp_id: str, *, subtasks: tuple[str, ...] = ("T001",)) -> None:
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": list(subtasks),
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
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
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


def _seed_mission(workflow_repo: Path, *, subtasks: tuple[str, ...] = ("T001",)) -> tuple[Path, Path]:
    """Seed a single-WP, planned-lane mission ready for an implementation claim."""
    feature_dir = workflow_repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    subtask_rows = "\n".join(f"- [ ] {task_id} Placeholder task" for task_id in subtasks)
    (feature_dir / "tasks.md").write_text(f"## WP01 Test\n\n{subtask_rows}\n", encoding="utf-8")
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", subtasks=subtasks)
    from specify_cli.status import Lane, StatusEvent
    from tests._support.status_seed import seed_status_event

    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="test-WP01-planned",
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )
    _write_current_analysis_report(feature_dir, workflow_repo)
    worktree_path = lane_worktree_path(workflow_repo, _MISSION_SLUG)
    _mint_fake_worktree(workflow_repo, worktree_path)
    return feature_dir, wp_path


def _claim_wp01(mission_slug: str = _MISSION_SLUG, agent: str = "test-agent") -> Result:
    return CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", agent],
    )


# ---------------------------------------------------------------------------
# T020/T021 — stale-sweep claim-liveness resolves off the reduced snapshot,
# proven through the real CLI claim entry point (two-sided: live + dead PID).
# ---------------------------------------------------------------------------


class TestStaleSweepResolvesLivenessFromSnapshot:
    def test_live_snapshot_pid_after_real_claim_suppresses_stale(
        self, workflow_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A real ``implement`` claim carries the claiming shell's live PID
        (``os.getppid()``) in the emitted event's ``policy_metadata``. This
        test does not fake the PID: it lets the real claim path capture the
        actual test-runner process PID, then asserts stale-sweep sees it as
        alive via the real ``is_process_alive`` check (no liveness stub)."""
        feature_dir, wp_path = _seed_mission(workflow_repo)
        worktree_path = lane_worktree_path(workflow_repo, _MISSION_SLUG)

        result = _claim_wp01()
        assert result.exit_code == 0, result.stdout

        events = read_events(feature_dir)
        claimed = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
        assert claimed, f"expected a claimed transition, got: {events}"
        assert isinstance(claimed[-1].policy_metadata["shell_pid"], int)

        outcome = check_wp_staleness(
            "WP01",
            worktree_path,
            threshold_minutes=10,
            shell_pid=None,  # frontmatter-sourced arg is ignored -- feature_dir wins (C-001)
            shell_pid_baseline=None,
            feature_dir=feature_dir,
        )

        assert outcome.is_stale is False
        assert outcome.stale.reason == LIVE_CLAIM_PROCESS_REASON

    def test_dead_snapshot_pid_after_real_claim_falls_through_to_timestamp_check(
        self, workflow_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same real claim path, but the snapshot PID is forced dead
        (monkeypatched at the PID-VALUE level, mirroring the prior mission's
        two-sided proof pattern) -- the outcome must NOT carry
        ``LIVE_CLAIM_PROCESS_REASON`` (the fresh/live-process short-circuit is
        skipped), proving the decision is snapshot-driven rather than an
        unconditional "always fresh" default."""
        feature_dir, wp_path = _seed_mission(workflow_repo)
        worktree_path = lane_worktree_path(workflow_repo, _MISSION_SLUG)
        monkeypatch.setattr("specify_cli.core.stale_detection.is_process_alive", lambda pid: False)
        monkeypatch.setattr(
            "specify_cli.core.stale_detection.is_claiming_process_alive",
            lambda pid, baseline: False,  # noqa: ARG005
        )

        result = _claim_wp01()
        assert result.exit_code == 0, result.stdout

        outcome = check_wp_staleness(
            "WP01",
            worktree_path,
            threshold_minutes=10,
            shell_pid=None,
            shell_pid_baseline=None,
            feature_dir=feature_dir,
        )

        assert outcome.stale.reason != LIVE_CLAIM_PROCESS_REASON

    def test_no_claim_event_yields_conservative_not_alive_not_crash(
        self, workflow_repo: Path
    ) -> None:
        """Edge case (T021): a mission with no claim event at all -- the
        snapshot has no entry for the WP -- degrades to "not provably alive"
        rather than raising or falsely reporting live."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        worktree_path = lane_worktree_path(workflow_repo, _MISSION_SLUG)

        outcome = check_wp_staleness(
            "WP01",
            worktree_path,
            threshold_minutes=10,
            shell_pid=None,
            shell_pid_baseline=None,
            feature_dir=feature_dir,
        )

        assert outcome.stale.reason != LIVE_CLAIM_PROCESS_REASON


# ---------------------------------------------------------------------------
# T023 — the frontmatter shell_pid/agent write is already retired: the WP
# file stays byte-stable across a real claim (no runtime bytes land in it).
# ---------------------------------------------------------------------------


class TestClaimFrontmatterWriteRetired:
    def test_wp_file_carries_no_shell_pid_or_agent_bytes_after_real_claim(
        self, workflow_repo: Path
    ) -> None:
        feature_dir, wp_path = _seed_mission(workflow_repo)
        before = wp_path.read_bytes()

        result = _claim_wp01()
        assert result.exit_code == 0, result.stdout

        after = wp_path.read_bytes()
        assert after == before, "the WP file must stay byte-identical across the claim"

        frontmatter, _body = read_frontmatter(wp_path)
        # The pre-seeded placeholders stay empty -- nothing populated them.
        assert frontmatter.get("shell_pid") == ""
        assert frontmatter.get("agent") == ""

        del feature_dir  # unused beyond the seeding side effect


# ---------------------------------------------------------------------------
# T022 — task_metadata_validation.py has no claim-liveness reader to migrate:
# its only shell_pid reference is an inert audit-note parameter.
# ---------------------------------------------------------------------------


class TestTaskMetadataValidationHasNoLivenessReader:
    def test_repair_lane_mismatch_shell_pid_is_audit_note_only_never_a_structured_field(
        self, tmp_path: Path
    ) -> None:
        """``repair_lane_mismatch``'s ``shell_pid`` parameter is folded into
        the free-text Activity-Log note -- it is never written back as a
        structured, re-readable frontmatter field, so there is nothing here
        for a claim-liveness reader to consume.

        **Live-evidence finding (out of WP05/FR-008 scope, noted honestly per
        DIRECTIVE_041 rather than silently worked around):** this assertion
        reads the repaired file's raw text rather than round-tripping it
        through :func:`specify_cli.frontmatter.read_frontmatter`. A
        pre-existing, unrelated bug in this function's use of
        ``specify_cli.template.renderer.parse_frontmatter`` -- whose third
        return value is ``raw_frontmatter_text``, not padding, but is
        destructured here as ``padding`` and threaded into
        ``build_document(..., padding)`` -- corrupts the closing ``---``
        delimiter on every repair, which the strict reader then rejects as
        malformed. This bug is orthogonal to the shell_pid claim-liveness
        migration WP05 owns (C-002: "only these two readers + the one write
        retirement" -- a frontmatter-parsing defect in the legacy
        migration-only lane-repair path is neither); it is reported to the
        orchestrator rather than fixed under this WP's scope.
        """
        task_file = tmp_path / "tasks" / "doing" / "WP01.md"
        task_file.parent.mkdir(parents=True)
        write_frontmatter(
            task_file,
            {"work_package_id": "WP01", "lane": "planned", "title": "Test"},
            "\n",
        )

        was_repaired, error = repair_lane_mismatch(task_file, agent="claude", shell_pid="99999")

        assert was_repaired is True
        assert error is None
        raw = task_file.read_text(encoding="utf-8-sig")
        # yaml.dump line-wraps the free-text note (backslash continuation across
        # a wrapped line), so assert both tokens are present rather than an
        # exact contiguous substring.
        assert "shell_pid" in raw and "99999" in raw, "the pid must land in the free-text audit note"
        assert not re.search(r"^shell_pid\s*:", raw, flags=re.MULTILINE), (
            "shell_pid must never be written as a standalone structured frontmatter field "
            "by the legacy repair path"
        )

    def test_validate_task_metadata_never_inspects_shell_pid(self, tmp_path: Path) -> None:
        """``validate_task_metadata``/``detect_lane_mismatch`` validate lane
        + required-field shape only -- a frontmatter ``shell_pid`` value
        (live, stale, or absent) never changes their verdict, confirming
        there is no claim-liveness decision embedded in this module."""
        task_file = tmp_path / "tasks" / "planned" / "WP01.md"
        task_file.parent.mkdir(parents=True)
        write_frontmatter(
            task_file,
            {
                "work_package_id": "WP01",
                "lane": "planned",
                "title": "Test",
                "shell_pid": "123456",
            },
            "\n",
        )

        issues_with_pid = validate_task_metadata(task_file)

        frontmatter, body = read_frontmatter(task_file)
        del frontmatter["shell_pid"]
        write_frontmatter(task_file, frontmatter, body)
        issues_without_pid = validate_task_metadata(task_file)

        assert issues_with_pid == issues_without_pid == []
        has_mismatch, _expected, _actual = detect_lane_mismatch(task_file)
        assert has_mismatch is False
