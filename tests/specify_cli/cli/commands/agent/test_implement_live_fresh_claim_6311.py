"""Live end-to-end guard for the fresh compact-actor implement claim (#6311).

Issue #6311 reports that a fresh claim with the documented compact
``tool:model:profile:role`` ``--agent`` value is refused by its own claim:

    spec-kitty agent action implement WP02 --mission <slug> \
        --agent claude:opus-5.5:<profile>:implementer
    Error: WP WP02 is already claimed for implementation by
    'claude:opus-5.5:<profile>:implementer'

Root cause (#4665, ``e455ce26c1``): two live emit sites hand the SAME logical
agent to the claim comparison in two SHAPES -- the workspace-create claim
(``cli.commands.implement_claim._start_wp_implementation_status``) passes the raw
compact STRING, while the start step
(``cli.commands.agent.workflow_executor._implement_start_claim``) passes a
structured actor DICT. ``_actor_key`` (``status/work_package_lifecycle.py``)
projected the two shapes to different keys, so the second, in-process claim
rejected the first. The fix reconciles the shapes in the CLI-local comparison
layer by parsing a compact string down to the bare tool; #6400 additionally
converged the claim emit sites on the structured shape.

Why this module exists (and why the neighbours do not already cover it): every
existing test of this defect replaces part of the live plumbing.

- ``test_implement_compact_identity_4665.py`` pre-fakes the lane worktree,
  monkeypatches ``safe_commit`` / target-branch checkout, and calls the
  workspace-create claim directly (its own header says so);
- ``status/test_actor_identity_reconciliation_4665.py`` and
  ``status/test_work_package_lifecycle.py`` drive ``start_implementation_status``
  against a seeded log, with no CLI and no workspace;
- ``test_implement_single_resolution.py`` materializes a topology-true but
  git-free worktree.

So the documented user flow -- one ``agent action implement`` invocation that
allocates a REAL lane worktree, claims the WP and renders the prompt -- had no
guard at all, which is what kept #6311 open behind ``triage:repro-needed``.
This module is that guard: a real git repository, a real lanes manifest, a
status log seeded only in ``planned``, and no monkeypatched git, no seeded
claim, no pre-created worktree.

Discriminating power (red baseline, measured live on a throwaway lanes mission
with ``spec-kitty-cli 4.0.0rc8``): with the pre-``e455ce26c1`` ``_actor_key``
restored in-process (compact string projected verbatim, in
``work_package_lifecycle`` and ``review_roles``), the same command prints

    Error: WP WP01 is already claimed for implementation by
    'claude:opus-5.5:python-pedro:implementer'

and exits 1. On this branch the identical flow exits 0 and renders the prompt.
The scenarios below are ordered so a vacuous pass is impossible: a genuinely
different tool must still be refused (``test_different_tool_is_still_refused``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status import Lane, StatusEvent
from specify_cli.status.store import read_events
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.regression, pytest.mark.git_repo]

_MISSION_SLUG = "live-claim-6311"
_MISSION_ID = derive_mission_id(_MISSION_SLUG)
_TARGET_BRANCH = "feat/live-claim-6311"
# The exact identity shape the issue reports, and the shape the docs teach.
_FULL_IDENTITY = "claude:opus-5.5:python-pedro:implementer"
_OTHER_TOOL_IDENTITY = "codex:gpt-6:python-pedro:implementer"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _write_wp_file(path: Path, wp_id: str) -> None:
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": ["T001"],
        "title": f"{wp_id} Live claim",
        "phase": "Phase 1",
        "execution_mode": "code_change",
        "owned_files": ["src/live_claim/**"],
        "authoritative_surface": "src/live_claim/",
        "assignee": "",
        "agent": "",
        "shell_pid": "",
        "review_status": "",
        "reviewed_by": "",
        "dependencies": [],
    }
    body = f"# {wp_id} Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z - system - Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _seed_planned_status(feature_dir: Path) -> None:
    """Seed ONLY the planning state ``finalize-tasks`` leaves behind.

    No claim event and no ``in_progress`` event: the claim under test must be
    the log's first ownership record, or the scenario proves nothing.
    """
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="test-WP01-genesis-planned",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="finalize-tasks",
            force=True,
            execution_mode="worktree",
        ),
    )


@pytest.fixture()
def live_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A REAL git repository carrying a lanes mission, with no lane worktree.

    Deliberately unpatched: ``git`` runs for real, so the lane worktree the
    claim resolves must be created by the real allocator (FR-005). Nothing here
    stubs ``safe_commit``, ``_ensure_target_branch_checked_out`` or
    ``create_lane_workspace``.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    # An explicit identity keeps the claim's auto-commit off the host default
    # (and out of any global config) without exposing a real address.
    _git(repo_root, "config", "user.name", "Spec Kitty Test")
    _git(repo_root, "config", "user.email", "test@example.invalid")

    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text(
        "vcs:\n  type: git\nproject:\n  uuid: live-claim-6311\n  slug: live-claim-6311\n",
        encoding="utf-8",
    )
    (repo_root / "README.md").write_text("# live claim fixture\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "chore: fixture baseline")
    _git(repo_root, "checkout", "-q", "-b", _TARGET_BRANCH)

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        (
            "{\n"
            f'  "mission_id": "{_MISSION_ID}",\n'
            f'  "mid8": "{_MISSION_ID[:8]}",\n'
            f'  "slug": "{_MISSION_SLUG}",\n'
            f'  "mission_slug": "{_MISSION_SLUG}",\n'
            f'  "friendly_name": "{_MISSION_SLUG}",\n'
            '  "mission_type": "software-dev",\n'
            f'  "target_branch": "{_TARGET_BRANCH}",\n'
            '  "created_at": "2026-01-01T00:00:00+00:00",\n'
            '  "topology": "lanes"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    write_single_lane_manifest(
        feature_dir,
        wp_ids=("WP01",),
        target_branch=_TARGET_BRANCH,
        mission_id=_MISSION_ID,
        predicted_surfaces=("workflow",),
    )
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001 live claim.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01 Live claim\n\n- [ ] T001 Placeholder\n", encoding="utf-8")
    _write_wp_file(tasks_dir / "WP01-live-claim.md", "WP01")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )
    _seed_planned_status(feature_dir)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "chore: live claim mission planning artifacts")

    # No network, no upgrade probe: NFR-001 (deterministic, fast) and a hard
    # reminder that this module must not depend on the host's release state.
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
    # The claim writes its rendered prompt under the per-user runtime root.
    # Pin that root inside tmp_path so the module writes nothing to the real
    # HOME (and cannot collide with a concurrent run on a shared host).
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "runtime-home"))
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root


def _run_implement(agent: str) -> Result:
    return CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", agent],
    )


def _wp01_events(repo_root: Path) -> list[StatusEvent]:
    return [event for event in read_events(repo_root / "kitty-specs" / _MISSION_SLUG) if event.wp_id == "WP01"]


# ---------------------------------------------------------------------------
# Scenario 1 (FR-001, FR-002, FR-005) — the documented flow, live.
# ---------------------------------------------------------------------------


def test_fresh_compact_claim_completes_in_one_invocation(live_repo: Path) -> None:
    """RED pre-``e455ce26c1``: exit 1, "already claimed". GREEN on this branch.

    One invocation covers the report's whole expectation -- claim, prompt, and
    the actor the claim recorded -- because re-invoking for each assertion would
    quietly change the thing under test (the second call is a resume).
    """
    worktree = live_repo / ".worktrees" / f"{_MISSION_SLUG}-lane-a"
    assert not worktree.exists(), "fixture must not pre-create the lane worktree"

    result = _run_implement(_FULL_IDENTITY)

    assert result.exit_code == 0, result.stdout
    assert "already claimed" not in result.stdout
    # The prompt really was rendered -- the report's complaint was "no prompt".
    assert "NEXT STEP" in result.stdout, result.stdout
    assert f"spec-kitty-implement-{_MISSION_SLUG}-WP01" in result.stdout, result.stdout

    # FR-002: the log's claim records the tool the compact identity names, so a
    # later resume compares like with like.
    events = _wp01_events(live_repo)
    assert events and events[-1].to_lane == Lane.IN_PROGRESS
    claimed = [event for event in events if event.to_lane in {Lane.CLAIMED, Lane.IN_PROGRESS}]
    assert claimed, "the claim emitted no status event"
    for event in claimed:
        actor = event.actor
        recorded = actor["tool"] if isinstance(actor, dict) else str(actor).split(":")[0]
        assert recorded == "claude"

    # FR-005: the allocator created the lane worktree for real. A hand-written
    # ".git" marker (the neighbouring modules' fixture) would not answer
    # ``rev-parse``, so this is what keeps the guard live.
    assert worktree.is_dir()
    assert _git(worktree, "rev-parse", "--is-inside-work-tree") == "true"


# ---------------------------------------------------------------------------
# Scenario 2 (FR-003) — a retry under the same identity resumes.
# ---------------------------------------------------------------------------


def test_same_identity_reinvoke_resumes_without_conflict(live_repo: Path) -> None:
    first = _run_implement(_FULL_IDENTITY)
    assert first.exit_code == 0, first.stdout
    lanes_before = [event.to_lane for event in _wp01_events(live_repo)]

    second = _run_implement(_FULL_IDENTITY)

    assert second.exit_code == 0, second.stdout
    assert "already claimed" not in second.stdout
    # A resume is a no-op on the LANE, not just an exit code: the resume refresh
    # may add an off-axis annotation, but it must never re-transition the WP.
    assert [event.to_lane for event in _wp01_events(live_repo)] == lanes_before


# ---------------------------------------------------------------------------
# Scenario 3 (FR-004) — the positive control.
# ---------------------------------------------------------------------------


def test_different_tool_is_still_refused(live_repo: Path) -> None:
    """FR-004: refusal still works, so scenarios 1-3 cannot pass vacuously."""
    first = _run_implement(_FULL_IDENTITY)
    assert first.exit_code == 0, first.stdout

    result = _run_implement(_OTHER_TOOL_IDENTITY)

    assert result.exit_code != 0
    assert "already claimed" in result.stdout
