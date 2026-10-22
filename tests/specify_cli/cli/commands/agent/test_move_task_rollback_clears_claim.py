"""#2512: ``move-task --to planned`` RELEASES a stale agent/shell_pid claim.

Field repro: an agent process was killed by macOS idle-sleep, leaving
``agent: "claude-code"`` / ``shell_pid: "41417"`` behind. ``move-task WPxx --to
planned`` reset the event-log lane back to ``planned`` but did NOT clear the
claim, so the next orchestrator resume call failed ``LANE_ALLOCATION_FAILED``.

Re-pointed for the WP-runtime-state eviction (WP10 closeout). The god-write is
cut (WP06, FR-006/FR-007/FR-008): runtime state — including the claim triple —
is event-sourced, so the claim now lives in the reduced snapshot (the
``planned -> claimed`` transition's ``policy_metadata``), NOT WP frontmatter.
The old frontmatter clearer (``_mt_clear_rollback_claim_markers``) was deleted
with the god-write; the release is now emitted off-axis as an
``InnerStateChanged`` from ``_mt_emit_runtime_state`` (#2512 delta).

These tests drive the real ``move-task`` entry point at ``status_phase: 1``
(flag ON — the event-sourced write path, the shipped dual-write end-state) and
assert:

* a rolled-back WP exposes **no live claim** — the reduced snapshot's
  ``agent``/``shell_pid`` slots are released (falsy) where they were live before
  (proof-of-drive positive control);
* the WP file stays **byte-stable** across the rollback (event-only, AC-5);
* an explicit ``--agent`` on rollback RE-PLANTS a fresh claim (override case).
"""

from __future__ import annotations

import json
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
from specify_cli.status.reducer import reduce as reduce_snapshot
from specify_cli.status.store import read_event_stream
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "001-rollback-clears-claim"
_STALE_PID = 41417
_STALE_AGENT = "claude-code"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _content_hash(path: Path) -> str:
    return hash_content(path.read_text(encoding="utf-8"))


def _seed_claim_to_in_review(feature_dir: Path) -> None:
    """Seed genesis -> planned -> claimed(claim triple) -> ... -> in_review.

    The ``planned -> claimed`` transition carries the claim triple on its
    ``policy_metadata`` (FR-004), exactly as the real claim path does, so the
    reduced snapshot exposes a LIVE claim before the rollback under test.
    """
    hops = [
        (Lane.GENESIS, Lane.PLANNED, None),
        (
            Lane.PLANNED,
            Lane.CLAIMED,
            {"shell_pid": _STALE_PID, "agent": _STALE_AGENT},
        ),
        (Lane.CLAIMED, Lane.IN_PROGRESS, None),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW, None),
        (Lane.FOR_REVIEW, Lane.IN_REVIEW, None),
    ]
    for idx, (frm, to, policy_metadata) in enumerate(hops, start=1):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{idx}",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=frm,
                to_lane=to,
                at=f"2026-01-01T00:00:0{idx}+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
                policy_metadata=policy_metadata,
            ),
        )


def _build_flag_on_mission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, wp_agent: str = "reviewer"
) -> tuple[Path, Path]:
    """Materialise a ``status_phase: 1`` (flag ON) lanes mission with WP01
    seeded to ``in_review`` carrying a live claim. Returns ``(repo, feature_dir)``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "wp10@example.invalid")
    _git(repo, "config", "user.name", "WP10 Rollback Claim")
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
    meta["status_phase"] = "1"  # flag ON: event-only writes, byte-stable WP file
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n", encoding="utf-8"
    )
    # No ``lane``/``agent``/``shell_pid`` frontmatter fields -> the flag-ON lane
    # mirror is a no-op and the file is byte-stable across the driven rollback.
    (tasks_dir / "WP01-core.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Core\n"
        f"agent: {wp_agent}\n"
        "subtasks: []\n"
        "tracker_refs: []\n"
        "dependencies: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed rollback-clears-claim fixture")
    _seed_claim_to_in_review(feature_dir)

    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(
        tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, [])
    )
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _snapshot_wp_state(feature_dir: Path) -> dict[str, object]:
    stream = read_event_stream(feature_dir)
    snapshot = reduce_snapshot(stream.transitions, stream.annotations)
    return snapshot.work_packages.get("WP01") or {}


def _move(args: list[str]) -> Result:
    return CliRunner().invoke(tasks_app, ["move-task", *args])


def test_rollback_to_planned_releases_claim_in_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain rollback to planned RELEASES the prior claim: the reduced
    snapshot's ``agent``/``shell_pid`` slots go falsy (no live claim), whereas
    they were live before the rollback (proof-of-drive positive control)."""
    repo, feature_dir = _build_flag_on_mission(tmp_path, monkeypatch)
    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: rework requested.\n", encoding="utf-8")

    # Positive control: BEFORE the rollback the claim is live in the snapshot.
    before = _snapshot_wp_state(feature_dir)
    assert before.get("shell_pid") == _STALE_PID
    assert before.get("agent") == _STALE_AGENT

    result = _move(
        [
            "WP01", "--to", "planned", "--mission", _MISSION_SLUG,
            "--review-feedback-file", str(feedback), "--no-auto-commit", "--json",
        ]
    )
    assert result.exit_code == 0, result.output

    after = _snapshot_wp_state(feature_dir)
    # No live claim: both claim slots are released (falsy) after the rollback.
    assert not after.get("shell_pid"), f"shell_pid not released: {after.get('shell_pid')!r}"
    assert not after.get("agent"), f"agent not released: {after.get('agent')!r}"


def test_rollback_release_is_event_only_wp_file_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The #2512 release is event-only: a release ``InnerStateChanged`` is
    persisted and the WP file stays byte-identical across the rollback (AC-5)."""
    repo, feature_dir = _build_flag_on_mission(tmp_path, monkeypatch)
    wp_file = feature_dir / "tasks" / "WP01-core.md"
    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: rework requested.\n", encoding="utf-8")

    hash_before = _content_hash(wp_file)
    annotations_before = len(read_event_stream(feature_dir).annotations)

    result = _move(
        [
            "WP01", "--to", "planned", "--mission", _MISSION_SLUG,
            "--review-feedback-file", str(feedback), "--no-auto-commit", "--json",
        ]
    )
    assert result.exit_code == 0, result.output

    # Event-only: a release annotation landed...
    stream = read_event_stream(feature_dir)
    assert len(stream.annotations) > annotations_before, "no release annotation persisted"
    release = [
        a for a in stream.annotations
        if a.wp_id == "WP01" and a.delta.release_runtime_claim
    ]
    assert release, "no InnerStateChanged released the claim (release_runtime_claim marker)"
    # ...and the WP file bytes did not change.
    assert _content_hash(wp_file) == hash_before, "rollback rewrote tasks/WP01.md bytes"


def test_rollback_with_explicit_agent_replants_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit ``--agent`` on rollback RE-PLANTS a fresh claim (override
    case): the snapshot ``agent`` slot carries the supplied value, not the
    release sentinel. ``--force`` bypasses the orthogonal claim-owner mismatch
    guard so the override path itself is what is exercised."""
    repo, feature_dir = _build_flag_on_mission(tmp_path, monkeypatch)
    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: rework requested.\n", encoding="utf-8")

    result = _move(
        [
            "WP01", "--to", "planned", "--mission", _MISSION_SLUG,
            "--review-feedback-file", str(feedback), "--agent", "fresh-claimer",
            "--force", "--no-auto-commit", "--json",
        ]
    )
    assert result.exit_code == 0, result.output

    after = _snapshot_wp_state(feature_dir)
    assert after.get("agent") == "fresh-claimer", (
        "explicit --agent on rollback must re-plant a fresh claim, not release it"
    )
