"""Shared real-CLI review-loop harness (mission ``rework-is-not-an-override``, #5196).

Drives a real LANES (non-coord) mission through the production ``move-task``
Typer app, one hop at a time, with three identities on DISTINCT tools (the
ownership guard compares tool keys via ``_actor_key`` -- same-tool identities
would silently bypass it, C-007).

Only ``GENESIS -> PLANNED`` is seeded; every later hop goes through the CLI so
event timestamps are real and ordered after the rejection.

This is a helper module (leading underscore: never collected by pytest).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent import workflow as workflow_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

IMPLEMENTER = "claude:opus:implementer-ivan:implementer"
REVIEWER = "codex:gpt-5:reviewer-renata:reviewer"
THIRD = "gemini:2.5-pro:python-pedro:implementer"

MISSION_SLUG = "rework-loop-fixture-01M3MQZZ"
WP = "WP01"
ARBITER_NOTE = "arbiter: rejection superseded by design decision"
ARBITER_CLI_MARKER = "Arbiter override recorded"

ROUTES = ("for_review_to_planned", "in_review_to_planned", "in_review_to_in_progress")

_FORCE = "--force"


@dataclass
class ReworkMission:
    """A materialised LANES mission plus a record of every CLI argv sent."""

    repo: Path
    feature_dir: Path
    mission_slug: str
    wp_dir: Path
    argvs: list[list[str]] = field(default_factory=list)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReworkMission:
    """Materialise a ``status_phase: 1`` lanes mission with WP01 at ``planned``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "5196@example.invalid")
    _git(repo, "config", "user.name", "Rework Loop")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8")
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=(WP,))
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n", encoding="utf-8")
    (tasks_dir / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Core\nsubtasks: []\ntracker_refs: []\ndependencies: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed rework-loop fixture")
    # Seed ONLY genesis -> planned; every later hop is a real CLI move.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-genesis-planned",
            mission_slug=MISSION_SLUG,
            wp_id=WP,
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:01+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )
    monkeypatch.chdir(repo)
    # Accept any args: ``agent tasks status`` calls it with arguments.
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda *_a, **_k: repo)
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return ReworkMission(repo=repo, feature_dir=feature_dir, mission_slug=MISSION_SLUG, wp_dir=tasks_dir)


def move(m: ReworkMission, wp: str, to: str, agent: str, *extra: str) -> Result:
    """Invoke ``agent tasks move-task`` through the real Typer app.

    ``--agent`` is mandatory: omitting it switches the ownership guard off.
    """
    assert agent, "--agent is mandatory (omitting it disables the ownership guard)"
    argv = ["move-task", wp, "--to", to, "--mission", m.mission_slug, "--agent", agent, *extra]
    m.argvs.append(argv)
    return CliRunner().invoke(tasks_app, argv)


def argv_log(m: ReworkMission) -> list[list[str]]:
    """Every argv the harness sent, in order."""
    return [list(a) for a in m.argvs]


def drive_to_for_review(m: ReworkMission, agent: str = IMPLEMENTER) -> None:
    """``planned -> claimed -> in_progress -> for_review`` as separate unforced CLI moves."""
    for target in ("claimed", "in_progress", "for_review"):
        result = move(m, WP, target, agent)
        assert result.exit_code == 0, f"{target}: {result.output}"


def reject(
    m: ReworkMission,
    route: str,
    reviewer: str = REVIEWER,
    cycle: int = 1,
    allow_force: bool = False,
) -> int:
    """Reject WP01 via ``route``; return the raw-log index of the rejection event.

    For ``in_review_*`` routes the reviewer first claims ``for_review -> in_review``.
    ``allow_force`` adds ``--force`` to the setup steps (some routes need it on the
    base); the rejection step is setup, not the thing under test.
    """
    assert route in ROUTES, route
    force = (_FORCE,) if allow_force else ()
    if route != "for_review_to_planned":
        claim = move(m, WP, "in_review", reviewer, *force)
        assert claim.exit_code == 0, f"review claim: {claim.output}"
    feedback = m.repo / f"review-feedback-{cycle}.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")
    target = "planned" if route.endswith("_to_planned") else "in_progress"
    result = move(m, WP, target, reviewer, "--review-feedback-file", str(feedback), *force)
    assert result.exit_code == 0, f"reject {route}: {result.output}"
    idxs = [i for i, e in enumerate(events(m)) if _is_lane_event(e) and e.get("to_lane") == target]
    assert idxs, "rejection event not found in the raw log"
    return idxs[-1]


def events(m: ReworkMission) -> list[dict[str, Any]]:
    """Raw JSON lines of ``status.events.jsonl`` (lane events AND annotations)."""
    path = m.feature_dir / "status.events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _is_lane_event(event: dict[str, Any]) -> bool:
    return "to_lane" in event and "from_lane" in event


def lane_events_after(m: ReworkMission, idx: int) -> list[dict[str, Any]]:
    """Lane-transition events strictly after RAW line index ``idx``."""
    return [e for i, e in enumerate(events(m)) if i > idx and _is_lane_event(e)]


def forced_after(m: ReworkMission, idx: int) -> int:
    """Count of lane events after raw index ``idx`` with ``force: true`` (SC-001)."""
    return sum(1 for e in lane_events_after(m, idx) if e.get("force") is True)


def review_cycle_files(m: ReworkMission) -> list[str]:
    """Sorted names of ``review-cycle-*.md`` under ``tasks/WP01-*/``."""
    return sorted(p.name for p in m.wp_dir.glob("WP01-*/review-cycle-*.md"))


def _raw_log_review_override(m: ReworkMission) -> bool:
    for event in events(m):
        delta = event.get("delta")
        review = delta.get("review") if isinstance(delta, dict) else None
        if isinstance(review, dict) and all(review.get(k) for k in ("at", "actor", "wp_id", "reason")):
            return True
    return False


def _forward_review_ref(m: ReworkMission, wp: str) -> bool:
    return any(e.get("wp_id") == wp and e.get("from_lane") == "planned" and e.get("review_ref") is not None for e in events(m) if _is_lane_event(e))


def _status_output(m: ReworkMission, wp: str) -> str:
    status = CliRunner().invoke(tasks_app, ["status", "--mission", m.mission_slug])
    assert status.exit_code == 0 and wp in status.output, f"status probe is blind: {status.output}"
    return str(status.output)


def override_probes(m: ReworkMission, wp: str = WP, move_output: str = "") -> dict[str, bool]:
    """Each value is True iff that surface shows an arbiter override.

    * ``raw_log_review_override`` -- raw log scan for a COMPLETE ``ReviewOverride``
      (all four of at/actor/wp_id/reason non-empty; every rejection writes an
      empty-field ``review`` clear delta, which must not count). Mirrors what
      ``_persist_review_artifact_override`` writes (``tasks_materialization.py``).
    * ``reduced_overrides`` -- ``arbiter.get_arbiter_overrides_for_wp`` non-empty.
    * ``forward_review_ref`` -- a lane event ``planned -> *`` carrying a
      ``review_ref`` (an arbiter-forward move copies the rejection's ref).
    * ``cli_marker`` -- "Arbiter override recorded" in the move's CLI output.
    * ``status_history`` -- human ``agent tasks status`` shows the arbiter
      history section (``tasks_status_cmd._st_render_arbiter``).

    NOTE: ``reduced_overrides`` and ``status_history`` share one source
    (``get_arbiter_overrides_for_wp``); they are NOT independent evidence.
    """
    from specify_cli.review.arbiter import get_arbiter_overrides_for_wp

    status_text = _status_output(m, wp)
    return {
        "raw_log_review_override": _raw_log_review_override(m),
        "reduced_overrides": bool(get_arbiter_overrides_for_wp(m.feature_dir, wp)),
        "forward_review_ref": _forward_review_ref(m, wp),
        "cli_marker": ARBITER_CLI_MARKER in move_output,
        "status_history": "Arbiter Override History" in status_text or "rejected → overridden" in status_text,
    }


def implement(m: ReworkMission, agent: str, monkeypatch: pytest.MonkeyPatch) -> Result:
    """Run the production ``agent action implement WP01 --agent <agent>`` in-process.

    Adapted from ``test_implement_runtime_frontmatter_claim.py``: the git-commit
    and target-branch plumbing is stubbed, the claim/status-event side runs for
    real. Records the argv (no ``--force`` is ever passed).
    """
    assert agent, "--agent is mandatory"
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(m.repo))
    monkeypatch.setattr(workflow_module, "_ensure_target_branch_checked_out", lambda repo_root, mission_slug: (repo_root, "main"))
    monkeypatch.setattr(workflow_module, "safe_commit", lambda **_kwargs: True)
    (m.feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (m.feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=m.feature_dir,
        repo_root=m.repo,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )
    workspace = lane_worktree_path(m.repo, m.mission_slug)
    workspace.mkdir(parents=True, exist_ok=True)
    gitdir = m.repo / ".git" / "worktrees" / workspace.name
    gitdir.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    argv = ["implement", WP, "--mission", m.mission_slug, "--agent", agent]
    m.argvs.append(["action", *argv])
    return CliRunner().invoke(workflow_module.app, argv)
