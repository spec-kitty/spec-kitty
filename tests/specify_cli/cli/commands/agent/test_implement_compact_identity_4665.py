"""Regression tests for #4665 — fresh full-identity implement claim
reconciliation (WP01), driven through the REAL ``agent action implement`` CLI
surface (``cli.commands.agent.workflow.app``).

Root cause (grounded, file:line): two live claim-emit sites disagree on the
actor SHAPE for the SAME logical agent —
``cli.commands.implement``'s workspace-create claim
(``effective_actor = actor or "implement-command"``, ``implement.py:1881``,
via ``_start_wp_implementation_status``) passes the raw compact
``tool:model:profile:role`` STRING, while
``cli.commands.agent.workflow_executor._implement_start_claim``
(``workflow_executor.py:744``) passes a structured DICT built by
``build_self_asserting_actor``. ``_actor_key``/``_actors_compatible``
(``status/work_package_lifecycle.py``) projected these two shapes to
different values, so the SECOND (in-process, same-invocation) claim rejected
its own first claim with ``WorkPackageClaimConflict`` (#4665).

Harness scope note: a fully materialized-from-scratch lane worktree (real
``create_lane_workspace`` git plumbing) is exercised by
``test_implement_single_resolution.py`` and the lane-allocator suite; that
mechanism is orthogonal to this WP's actor-identity-representation scope.
This test instead reproduces the exact defect at its real boundary by (1)
calling ``cli.commands.implement._start_wp_implementation_status`` directly —
the SAME function ``top_level_implement`` calls for its workspace-create
claim, with the SAME compact-string actor shape — against a pre-faked lane
worktree (mirroring ``test_implement_runtime_frontmatter_claim.py``'s
established harness), and then (2) driving the REAL
``agent action implement`` CLI command for the SAME logical agent. Step (2)
is the one live CLI invocation under test: internally it reaches
``workflow_executor._implement_start_claim`` (the dict-actor emit site) for
an already-``in_progress`` WP with ``--agent`` still supplied — exactly the
code path #4665 rejects. Git side effects (target-branch checkout,
``safe_commit``) are monkeypatched away; the claim/status side runs for real.

Red-first evidence (ADR 2026-07-17-1, MF2): base SHA ``25ba0b5d79`` (lane tip
immediately before WP01 T001). On that base,
``test_fresh_full_identity_claim_completes_in_one_invocation_no_self_conflict``
fails with exit code 1 and stdout containing::

    Error: WP WP01 is already claimed for implementation by
    'codex:gpt-6:python-pedro:implementer'

(the exact live-run output is recorded in this file's introducing commit
body).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.cli.commands.implement import _start_wp_implementation_status
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_MISSION_SLUG = "wp01-actor-identity-4665-demo"
_FULL_IDENTITY = "codex:gpt-6:python-pedro:implementer"


# ---------------------------------------------------------------------------
# Harness (adapted from test_implement_runtime_frontmatter_claim.py -- a NEW,
# WP01-owned test module per create_intent, not an extension of that file,
# which is not in this WP's owned_files).
# ---------------------------------------------------------------------------


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    event = StatusEvent(
        event_id=f"test-{wp_id}-{lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _write_wp_file(path: Path, wp_id: str) -> None:
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
    """Seed a single-WP mission with a pre-faked lane worktree.

    Returns ``(feature_dir, wp_path)``.
    """
    feature_dir = workflow_repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01")
    _seed_wp_lane(feature_dir, "WP01", lane)
    _write_current_analysis_report(feature_dir, workflow_repo)
    _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, _MISSION_SLUG))
    return feature_dir, wp_path


def _run_workspace_create_claim(feature_dir: Path, workflow_repo: Path, *, actor: str) -> None:
    """The REAL ``top_level_implement`` workspace-create claim (compact-string
    actor shape), called directly against the pre-faked worktree above --
    this WP's scope is the actor-identity reconciliation, not lane-creation
    mechanics (see module docstring)."""
    _start_wp_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        effective_actor=actor,
        workspace_path=lane_worktree_path(workflow_repo, _MISSION_SLUG),
        status_execution_mode="worktree",
        repo_root=workflow_repo,
    )


# ---------------------------------------------------------------------------
# T001 — the #4665 regression, through the real CLI (RED on base, MF2).
# ---------------------------------------------------------------------------


class TestFreshFullIdentityClaim:
    def test_fresh_full_identity_claim_completes_in_one_invocation_no_self_conflict(self, workflow_repo: Path) -> None:
        """Scenario 1 (FR-001): the compact-string workspace-create claim
        (simulating what ``top_level_implement`` just did, same invocation)
        followed by the REAL ``agent action implement --agent <same
        identity>`` CLI call MUST succeed and render the prompt -- not
        self-conflict. RED on base (exit 1, "already claimed")."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor=_FULL_IDENTITY)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", _FULL_IDENTITY],
        )

        assert result.exit_code == 0, result.stdout
        assert "already claimed" not in result.stdout
        assert "WP01" in result.stdout

    def test_same_identity_reinvoke_is_idempotent_resume(self, workflow_repo: Path) -> None:
        """Scenario 2 (FR-002): re-invoking under the SAME identity resumes
        idempotently."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor=_FULL_IDENTITY)

        first = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", _FULL_IDENTITY],
        )
        assert first.exit_code == 0, first.stdout

        second = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", _FULL_IDENTITY],
        )
        assert second.exit_code == 0, second.stdout
        assert "already claimed" not in second.stdout

    def test_different_identity_is_refused(self, workflow_repo: Path) -> None:
        """Scenario 3 (FR-002/FR-008): a genuinely different agent is still
        refused. Already green on base."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor=_FULL_IDENTITY)

        result = CliRunner().invoke(
            workflow.app,
            [
                "implement",
                "WP01",
                "--mission",
                _MISSION_SLUG,
                "--agent",
                "claude:sonnet:reviewer-renata:implementer",
            ],
        )

        assert result.exit_code != 0
        assert "already claimed" in result.stdout

    def test_generic_actor_claim_remains_reclaimable(self, workflow_repo: Path) -> None:
        """Scenario 4 (FR-010): a WP claimed by a generic placeholder actor
        stays re-claimable by a real full identity. Already green on base."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor="implement-command")

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", _FULL_IDENTITY],
        )

        assert result.exit_code == 0, result.stdout
        assert "already claimed" not in result.stdout


# ---------------------------------------------------------------------------
# T004 — representation x comparison matrix (NFR-002), live through the CLI.
# ---------------------------------------------------------------------------


class TestActorIdentityMatrixLive:
    def test_matrix_row_a_dict_and_compact_string_same_agent_no_conflict(self, workflow_repo: Path) -> None:
        """(a) same agent, compact string (workspace-create claim) vs the
        real CLI's structured-dict claim -> no conflict, live."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor=_FULL_IDENTITY)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", _FULL_IDENTITY],
        )

        assert result.exit_code == 0, result.stdout

    def test_matrix_row_d_same_tool_differing_profile_is_idempotent_live(self, workflow_repo: Path) -> None:
        """(d) same tool, differing profile, both implementers -> the
        existing tool-scoped impl-claim discipline treats the second claim
        as an idempotent resume (documented, not silently changed)."""
        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor="codex:gpt-6:python-pedro:implementer")

        result = CliRunner().invoke(
            workflow.app,
            [
                "implement",
                "WP01",
                "--mission",
                _MISSION_SLUG,
                "--agent",
                "codex:gpt-9:reviewer-renata:implementer",
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert "already claimed" not in result.stdout

    def test_transition_actor_and_runtime_agent_slot_converge_live(self, workflow_repo: Path) -> None:
        """US1-AC5 / C-006: after the real CLI claim completes, the
        transition-derived ``actor`` slot and the runtime ``agent`` slot
        resolve to the SAME canonical tool-scoped identity."""
        from specify_cli.status import reduce as wf_reduce
        from specify_cli.status.store import read_events as wf_read_events
        from specify_cli.status.work_package_lifecycle import _actor_key

        feature_dir, _wp_path = _seed_mission(workflow_repo)
        _run_workspace_create_claim(feature_dir, workflow_repo, actor=_FULL_IDENTITY)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", _MISSION_SLUG, "--agent", _FULL_IDENTITY],
        )
        assert result.exit_code == 0, result.stdout

        snapshot = wf_reduce(wf_read_events(feature_dir))
        wp_state = snapshot.work_packages["WP01"]
        assert _actor_key(wp_state["actor"]) == "codex"
        assert _actor_key(wp_state["agent"]) == "codex"
