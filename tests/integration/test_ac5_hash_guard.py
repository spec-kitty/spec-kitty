"""AC-5 / SC-001 / SC-005 — the SOLE full-lifecycle stable-hash acceptance.

Proves NFR-001 by construction: across a full **driven** WP lifecycle
(claim -> mark-subtask-done -> note -> tracker-ref -> review-reject ->
review-approve -> history), the raw-byte content hash of ``tasks/WP##.md`` and
the WP's ``tasks.md`` section changes **0 times** — AND a persisted event exists
for each driven action (proof-of-drive: a green test with no events is a fail).

Driven at ``status_phase: 1`` (flag ON, the shipped event-sourced write path)
through the canonical Typer entry points — never by hand-editing files. This is
the mission-level acceptance; the WP06/T025 ``test_wp_file_hash_stability.py``
slice is only the move-task writer cut and does NOT stand in for it.

Two-sided (proof the guard bites): deliberately reverting any writer cut so a
runtime write leaks back into the WP file / tasks.md turns this red.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from charter.hasher import hash_content
from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event, read_event_stream
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "001-ac5-hash-guard"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _wp_section(tasks_md: Path, wp_id: str) -> str:
    """Extract the WP's ``## WP##ID ...`` section from tasks.md (heading -> next
    ``## `` heading or EOF). This is the ``tasks.md`` section AC-5 pins."""
    content = tasks_md.read_text(encoding="utf-8")
    match = re.search(rf"(^## {re.escape(wp_id)}\b.*?)(?=\n## |\Z)", content, flags=re.DOTALL | re.MULTILINE)
    assert match, f"WP section for {wp_id} not found in tasks.md"
    return match.group(1)


def _build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Materialise a ``status_phase: 1`` (flag ON) lanes mission with WP01
    seeded to ``planned`` and one CHECKBOX subtask in tasks.md."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "wp10@example.invalid")
    _git(repo, "config", "user.name", "WP10 AC5 Guard")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01): the
    # rejection-write path now threads a REAL ``commit_artifact`` call and
    # raises on a non-"committed" result. ``ProtectionPolicy.resolve`` treats
    # "main" as protected by default, so this real-git fixture needs the
    # override to let the review-cycle artifact's commit genuinely succeed --
    # mirrors ``tests/review/test_cycle.py``'s ``_unprotect_main`` idiom.
    (repo / ".kittify" / "config.yaml").write_text(
        "auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8"
    )

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"  # flag ON: event-only writes; byte-stable file
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 - Core\n\n- [ ] T001 Build the thing\n",
        encoding="utf-8",
    )
    # No lane/agent/shell_pid/tracker frontmatter fields -> the flag-ON mirror is
    # a no-op and the file must stay byte-stable across every driven action.
    # T001 IS on the authored ``subtasks:`` roster (the canonical ownership
    # source since #2816 IC-10). The #2513 rollback reset
    # (``_mt_rollback_subtasks_reset``) and the review gate read only this
    # roster: an empty roster would leave T001 untouched on a reject, so the
    # subsequent ``mark-status T001 done`` would be a correct no-op
    # (already-satisfied) and the proof-of-drive step would have no basis (#6243).
    (tasks_dir / "WP01-core.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Core\n"
        "agent: claude\n"
        "subtasks: [T001]\n"
        "tracker_refs: []\n"
        "dependencies: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed ac5 hash-guard fixture")

    # Seed genesis -> planned so the WP exists in the log at planned.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-planned",
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )

    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _write_review_cycle(feature_dir: Path, cycle: int, verdict: str) -> str:
    """Write a ``review-cycle-N.md`` approval artifact next to the WP file."""
    wp_dir = feature_dir / "tasks" / "WP01-core"
    wp_dir.mkdir(parents=True, exist_ok=True)
    (wp_dir / f"review-cycle-{cycle}.md").write_text(
        f"---\n"
        f"cycle_number: {cycle}\n"
        f"mission_slug: {feature_dir.name}\n"
        f"reviewed_at: '2026-04-30T12:00:00Z'\n"
        f"reviewer_agent: reviewer-renata\n"
        f"verdict: {verdict}\n"
        f"wp_id: WP01\n"
        f"---\n\nReview body.\n",
        encoding="utf-8",
    )
    return f"review-cycle://{feature_dir.name}/WP01-core/review-cycle-{cycle}.md"


def _run(args: list[str]) -> Result:
    return CliRunner().invoke(tasks_app, args)


def test_ac5_hash_stable_across_driven_lifecycle_with_proof_of_drive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)
    wp_file = feature_dir / "tasks" / "WP01-core.md"
    tasks_md = feature_dir / "tasks.md"

    baseline_wp = hash_content(wp_file.read_text(encoding="utf-8"))
    baseline_section = hash_content(_wp_section(tasks_md, "WP01"))

    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: needs rework.\n", encoding="utf-8")

    def stream_len() -> int:
        s = read_event_stream(feature_dir)
        return len(s.transitions) + len(s.annotations)

    def drive(label: str, args: list[str]) -> None:
        """Run one canonical action; assert byte-stability + proof-of-drive."""
        events_before = stream_len()
        result = _run(args)
        assert result.exit_code == 0, f"[{label}] failed:\n{result.output}"
        assert hash_content(wp_file.read_text(encoding="utf-8")) == baseline_wp, (
            f"[{label}] rewrote tasks/WP01.md bytes (AC-5 violated)"
        )
        assert hash_content(_wp_section(tasks_md, "WP01")) == baseline_section, (
            f"[{label}] rewrote the WP01 tasks.md section bytes (AC-5 violated)"
        )
        assert stream_len() > events_before, (
            f"[{label}] persisted NO event — the action never fired (proof-of-drive)"
        )

    m = ["--mission", _MISSION_SLUG, "--no-auto-commit", "--json"]

    # 1. claim (planned -> claimed): claim triple rides the transition sidecar.
    drive("claim", ["move-task", "WP01", "--to", "claimed", "--shell-pid", "424242",
                    "--agent", "claude", "--note", "claiming for work", *m])
    # 2. mark-subtask-done: CHECKBOX completion is event-sourced (no tasks.md write).
    drive("mark-subtask-done", ["mark-status", "T001", "--status", "done", *m])
    # 3. add note (claimed -> in_progress): the note is an off-axis annotation.
    drive("note", ["move-task", "WP01", "--to", "in_progress", "--note", "starting work", *m])
    # 4. tracker-ref append (in_progress -> for_review): FR-006 union delta.
    drive("tracker-ref", ["move-task", "WP01", "--to", "for_review", "--tracker-ref", "TR-1", *m])
    # 5. reviewer picks it up (for_review -> in_review). No --agent: that field is
    #    the claim OWNER (implementer); a reviewer move must not re-stamp it.
    drive("in_review", ["move-task", "WP01", "--to", "in_review", *m])
    # 6. review-reject (in_review -> planned): evidence-gated, force-free (FR-015).
    drive("review-reject", ["move-task", "WP01", "--to", "planned",
                            "--review-feedback-file", str(feedback), *m])

    # Re-drive to in_review so the approve edge is reachable. The reject reset the
    # subtask roster (event-sourced), so re-mark it done to satisfy the gate.
    drive("re-claim", ["move-task", "WP01", "--to", "claimed", "--shell-pid", "424242",
                       "--agent", "claude", *m])
    drive("re-mark-subtask", ["mark-status", "T001", "--status", "done", *m])
    # 7. history append: a driven ``## Activity Log`` / History note. The canonical
    #    event-sourced history append is the note annotation move-task emits
    #    (HistoryAdded / InnerStateChanged note) — byte-stable at flag ON. (The
    #    standalone ``add-history`` command remains an UN-cut WP-file god-writer —
    #    it unconditionally rewrites the WP body — so it is deliberately NOT used
    #    here; that gap is attributable to the activity-log eviction lane
    #    (WP05/WP08), not WP10, and is reported as a residual out-of-scope finding.)
    drive("history-note", ["move-task", "WP01", "--to", "in_progress",
                           "--note", "closeout audit note", *m])
    drive("re-for_review", ["move-task", "WP01", "--to", "for_review", *m])
    drive("re-in_review", ["move-task", "WP01", "--to", "in_review", *m])

    # 8. review-approve (in_review -> approved): evidence-gated, force-free.
    approval_ref = _write_review_cycle(feature_dir, 2, "approved")
    drive("review-approve", ["move-task", "WP01", "--to", "approved",
                             "--reviewer", "reviewer-renata", "--approval-ref", approval_ref, *m])
