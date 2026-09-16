"""#3243 regression: reject -> fix -> re-approve needs no override flag.

Field repro (mission ``local-event-webhook-01KZ3YQJ``): a cycle-1 rejection
appeared to write a byte-identical duplicate at ``review-cycle-2.md``, and the
cycle-2 approval was then BLOCKED on that stale duplicate as an "unresolved
rejection", forcing ``--skip-review-artifact-check`` after a manual
stale-duplicate diagnosis.

This suite drives the real ``move-task`` entry point through the full loop and
locks in both halves of the fix:

* a single rejection writes EXACTLY ONE ``review-cycle-N.md`` artifact (no
  duplicate at N+1; allocation is ``max(parsed) + 1``, one write site,
  serialized under the feature-status lock);
* the ordinary cycle-2 approval over a standing rejection proceeds WITHOUT
  ``--skip-review-artifact-check`` — the rejected-verdict guard no longer
  fails the approve path closed (FR-001, mission
  review-verdict-write-integrity-01KZ1CGF), and the approval itself is
  recorded as a new ``review-cycle-N+1.md`` artifact numbered by the same
  max+1 authority.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "001-reject-fix-approve"
_WP_SLUG_DIR = Path("kitty-specs") / _MISSION_SLUG / "tasks" / "WP01-core"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _seed_hops(feature_dir: Path, hops: list[tuple], at_day: str) -> None:
    """Seed canonical lane transitions directly into the event log."""
    for idx, (frm, to) in enumerate(hops, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{at_day}-{idx}",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=frm,
                to_lane=to,
                at=f"{at_day}T00:00:0{idx}+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
            ),
        )


def _build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Materialise a ``status_phase: 1`` lanes mission with WP01 at ``in_review``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "3243@example.invalid")
    _git(repo, "config", "user.name", "Reject Fix Approve")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    # Unprotect "main" so the rejection write's real commit path can succeed —
    # mirrors ``tests/review/test_cycle.py``'s ``_unprotect_main`` idiom.
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8")
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n", encoding="utf-8")
    (tasks_dir / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Core\nagent: reviewer\nsubtasks: []\ntracker_refs: []\ndependencies: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed reject-fix-approve fixture")
    _seed_hops(
        feature_dir,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
            (Lane.FOR_REVIEW, Lane.IN_REVIEW),
        ],
        at_day="2026-01-01",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _cycle_artifacts(repo: Path) -> list[str]:
    return sorted(str(p.relative_to(repo)) for p in repo.rglob("review-cycle-*.md"))


def _move(args: list[str]):
    return CliRunner().invoke(tasks_app, ["move-task", *args])


def test_reject_fix_approve_cycle_needs_no_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)

    # Cycle-1 rejection: the reviewer runs the command the review prompt
    # prints, feedback authored at the advertised path.
    feedback = repo / "review-feedback-1.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")
    rejected = _move(
        [
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            _MISSION_SLUG,
            "--agent",
            "reviewer",
        ]
    )
    assert rejected.exit_code == 0, rejected.output

    # One rejection, ONE artifact: no byte-identical duplicate at N+1.
    assert _cycle_artifacts(repo) == [str(_WP_SLUG_DIR / "review-cycle-1.md")], _cycle_artifacts(repo)

    # The implementer fixes the work; the WP flows back to in_review.
    _seed_hops(
        feature_dir,
        [
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
            (Lane.FOR_REVIEW, Lane.IN_REVIEW),
        ],
        at_day="2026-01-02",
    )

    # Cycle-2 approval: the ordinary path — NO --skip-review-artifact-check,
    # no arbiter override. A stale rejection predating the fix must not block.
    approved = _move(
        [
            "WP01",
            "--to",
            "approved",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            "reviewer",
            "--note",
            "Review passed",
        ]
    )
    assert approved.exit_code == 0, approved.output

    # The approval is recorded as exactly one new artifact, numbered max+1 —
    # the writer never re-uses the rejection's cycle number and never writes
    # a duplicate alongside it.
    assert _cycle_artifacts(repo) == [
        str(_WP_SLUG_DIR / "review-cycle-1.md"),
        str(_WP_SLUG_DIR / "review-cycle-2.md"),
    ], _cycle_artifacts(repo)
