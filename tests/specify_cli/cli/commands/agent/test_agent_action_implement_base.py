"""#6753 — the dispatched agent path accepts ``--base`` and carries it to the allocator.

`spec-kitty next` and the `/spec-kitty.implement` shim both dispatch
``spec-kitty agent action implement <WP> --agent <name>``. Before this change that
command had no ``--base``, so an agent following the documented loop could not act
on the remedy #6753 names; only the internal top-level ``spec-kitty implement
--base`` had it.

* FR-004 — ``agent action implement --base <ref>`` parses and the value reaches the
  create-path dispatch (the real production call ``top_level_implement``), while the
  same invocation without ``--base`` carries ``None`` (the same-fixture control that
  proves the capture can observe the value).
* FR-005 — the allocator's base-refusal routes are untouched: the reuse route still
  refuses an explicit base, unchanged by the new option.

The test drives the real Typer command through ``CliRunner``; only the create-path
dispatch itself is replaced, because actually cutting a lane worktree here would
re-test ``allocate_lane_worktree`` (covered by WP01 and ``test_lane_base_honoring``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status import Lane, StatusEvent
from specify_cli.workspace.context import ResolvedWorkspace
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

pytestmark = pytest.mark.fast

_MISSION_SLUG = "stale-coord-lane-base-demo"
_WP_ID = "WP01"


def _write_wp_file(path: Path, wp_id: str) -> None:
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": ["T001"],
        "title": f"{wp_id} Test",
        "phase": "Phase 0",
        "execution_mode": "code_change",
        "owned_files": ["src/demo/**"],
        "authoritative_surface": "src/demo/",
        "assignee": "",
        "agent": "",
        "shell_pid": "",
        "review_status": "",
        "reviewed_by": "",
        "dependencies": [],
    }
    body = f"# {wp_id} Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z - system - Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _seed_status(feature_dir: Path, wp_id: str, lane: str = "planned") -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{lane}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _seed_analysis(feature_dir: Path, repo_root: Path) -> None:
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )


def _mint_worktree(repo_root: Path) -> None:
    """Mark the resolved lane workspace as a real git worktree (#1833 husk guard)."""
    workspace = lane_worktree_path(repo_root, _MISSION_SLUG)
    workspace.mkdir(parents=True, exist_ok=True)
    gitdir = repo_root / ".git" / "worktrees" / workspace.name
    gitdir.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")


@pytest.fixture()
def workflow_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A non-git project root whose mission is ready for an implementation claim."""
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
    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow.safe_commit", lambda **kwargs: True)

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=(_WP_ID,), predicted_surfaces=("workflow",))
    _write_wp_file(tasks_dir / "WP01-test.md", _WP_ID)
    _seed_status(feature_dir, _WP_ID)
    _seed_analysis(feature_dir, repo_root)
    return repo_root


def _capture_create_dispatch(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> dict[str, object]:
    """Replace the create-path dispatch, capturing its kwargs and materializing the lane.

    ``top_level_implement`` is what ``_create_workspace`` calls to cut the lane; the
    captured kwargs are the value that reaches ``create_lane_workspace`` →
    ``allocate_lane_worktree`` in production.
    """
    captured: dict[str, object] = {}

    def _fake_top_level_implement(**kwargs: object) -> None:
        captured.update(kwargs)
        _mint_worktree(repo_root)

    monkeypatch.setattr(workflow, "top_level_implement", _fake_top_level_implement)
    return captured


def _invoke(*extra: str) -> object:
    return CliRunner().invoke(
        workflow.app,
        ["implement", _WP_ID, "--mission", _MISSION_SLUG, "--agent", "test-agent", *extra],
    )


# ---------------------------------------------------------------------------
# FR-004 — the option exists and the value reaches the create-path dispatch.
# ---------------------------------------------------------------------------


def test_base_option_is_carried_to_the_create_dispatch(workflow_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_create_dispatch(monkeypatch, workflow_repo)

    result = _invoke("--base", "main")

    assert result.exit_code == 0, result.stdout  # type: ignore[attr-defined]
    assert captured, "the create-path dispatch was never reached"
    assert captured.get("base") == "main", f"the explicit base must reach the lane-creation dispatch, got {captured.get('base')!r}"


def test_absent_base_option_carries_none(workflow_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same-fixture control: the capture can observe ``None`` as well as a value."""
    captured = _capture_create_dispatch(monkeypatch, workflow_repo)

    result = _invoke()

    assert result.exit_code == 0, result.stdout  # type: ignore[attr-defined]
    assert captured, "the create-path dispatch was never reached"
    assert captured.get("base") is None, f"no --base must carry None (pre-#6753 behaviour), got {captured.get('base')!r}"


def test_base_option_is_advertised_in_help() -> None:
    """The option surface exists on the documented command, not only in the parser."""
    result = CliRunner().invoke(workflow.app, ["implement", "--help"])
    # Rich draws a box border through the help column, so drop the non-ASCII
    # frame and then normalise whitespace before matching a phrase.
    ascii_only = "".join(ch if ord(ch) < 128 else " " for ch in result.output)  # type: ignore[attr-defined]
    help_text = " ".join(ascii_only.split())

    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "--base" in help_text
    assert "Explicit base ref for the lane workspace" in help_text
    assert "current target branch tip" in help_text


# ---------------------------------------------------------------------------
# FR-005 — the new option buys no silent no-op: an existing lane still refuses.
# ---------------------------------------------------------------------------


def test_existing_lane_refuses_an_explicit_base(workflow_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lane that already exists cannot be re-parented, so ``--base`` is refused.

    #3281's reuse self-heal replaces the create-path dispatch on this branch, so
    without an explicit refusal here the operator's ``--base`` would be accepted
    and silently dropped -- exactly the no-op the allocator's reuse route
    (``UnhonorableBaseError``) exists to prevent.
    """
    captured = _capture_create_dispatch(monkeypatch, workflow_repo)
    _mint_worktree(workflow_repo)  # the lane already exists

    result = _invoke("--base", "main")

    assert result.exit_code == 1, result.stdout  # type: ignore[attr-defined]
    assert "cannot re-parent an already-committed lane" in result.stdout  # type: ignore[attr-defined]
    assert "--base" in result.stdout  # type: ignore[attr-defined]
    # The lane the operator now has cannot be re-parented, so the refusal names the
    # discard-and-re-cut step -- the remedy the WP01 warning points at must be
    # reachable in the sequence that warning creates (independent-review follow-up).
    assert "git worktree remove" in result.stdout  # type: ignore[attr-defined]
    assert "git branch -D" in result.stdout  # type: ignore[attr-defined]
    assert not captured, "an existing lane must not reach the create-path dispatch"


def test_checkout_root_resolution_keeps_the_ignored_warning(workflow_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A checkout-root workspace has no parent to choose, so ``--base`` is ignored.

    Parity with the top-level command's FR-007 behaviour: ``spec-kitty implement
    --base`` warns and proceeds on a repository-root (planning / single_branch
    repo-root) lane. ``_ensure_workspace_materialized`` routes those through the
    same reuse self-heal, so the dispatched path must not turn that into a
    refusal -- a guard that blocks a legitimate action is the #2017 failure mode.
    """
    checkout_root = ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id=_WP_ID,
        execution_mode="code_change",
        mode_source="lane",
        resolution_kind="repo_root",
        workspace_name=_MISSION_SLUG,
        worktree_path=workflow_repo,
        branch_name="main",
        lane_id=None,
        lane_wp_ids=[_WP_ID],
    )
    assert checkout_root.runs_in_checkout_root
    monkeypatch.setattr(workflow, "resolve_workspace_for_wp", lambda *a, **k: checkout_root)
    captured = _capture_create_dispatch(monkeypatch, workflow_repo)

    result = _invoke("--base", "main")
    output = result.stdout  # type: ignore[attr-defined]

    assert "cannot re-parent an already-committed lane" not in output, output
    assert "Warning: --base is ignored for repository-root planning work" in output, output
    assert not captured, "a checkout-root workspace must not reach the create-path dispatch"
