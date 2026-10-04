"""End to end: a single_branch mission's for_review commit gate in its write checkout.

Originally the #5100 acceptance suite (spec.md US2, "A single_branch mission
runs in its write checkout"). #5100 is fixed; this file is now a permanent
guard that keeps only what no cheaper test pins:

- the for_review commit-gate trio (a committed owned file lets ``for_review``
  succeed without ``--force``; the first-claim ``meta.json`` lock commit is not
  qualifying work; stray repo-root files are never auto-committed), and
- the ``topology=lanes`` control (non-vacuity: the identical fixture creates a
  lane worktree stamped ``worktree``).

The finalize lane shape, the implement refusals (wrong branch, occupancy,
dirty checkout, resume exemption), the ``direct_repo`` stamp, the protected
mission-branch mint and the ``--commit-to-target`` override moved to the
stub/integration guards in ``tests/lanes/test_compute_lanes_single_branch.py``,
``tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py``,
``tests/core/test_mission_create_protected_single_branch.py`` and
``tests/git/test_protection_policy_mission_scope.py`` (#5620 planted-break
evidence).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli import app as root_app
from tests._factories import make_mission
from tests.specify_cli.charter_preflight._fixtures import (
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
    write_metadata,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_WORK_BRANCH = "issue-5100-work"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _assert_setup_ok(label: str, cli_result: object) -> None:
    """Pre-assert a SETUP command's exit code with a distinct message.

    Every setup step in a fixture is asserted this way (never left to fail
    implicitly later) so a fixture crash can never masquerade as one of
    this file's own assertions.
    """
    exit_code = getattr(cli_result, "exit_code", None)
    output = getattr(cli_result, "output", cli_result)
    assert exit_code == 0, f"setup step {label!r} failed (exit {exit_code}): {output}"


def _seed_repo(tmp_path: Path, *, name: str) -> Path:
    """A minimal, real git repo with a fully-fresh charter (implement's
    freshness preflight must pass) on an UNPROTECTED work branch."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "issue-5100@example.invalid")
    _git(repo, "config", "user.name", "Issue 5100 Regression")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    charter_path, metadata_path = seed_charter(repo)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo)
    seed_charter_yaml(repo)
    seed_manifest(repo, built_in_only=False)
    seed_graph(repo)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    # single_branch missions must run on an UNPROTECTED target (US3 covers
    # the protected-target mission-branch mint, WP08).
    _git(repo, "checkout", "-b", _WORK_BRANCH)
    return repo


def _write_two_code_wps(repo: Path, feature_dir: Path) -> None:
    """Write WP01 (no deps) + WP02 (depends on WP01)."""
    (feature_dir / "spec.md").write_text("# Spec\n\n## Functional Requirements\n\n- **FR-001**: repro.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\n**Language/Version**: Python 3.11\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\n- [ ] T001 alpha\n\n## Work Package WP02\n\n**Dependencies**: WP01\n\n- [ ] T002 beta\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks").mkdir(exist_ok=True)
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: First code WP\ndependencies: []\n"
        "requirement_refs: [FR-001]\nexecution_mode: code_change\nowned_files: [src/wp01.py]\n"
        "authoritative_surface: src/wp01.py\nsubtasks: [T001]\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ntitle: Second code WP\ndependencies: [WP01]\n"
        "requirement_refs: [FR-001]\nexecution_mode: code_change\nowned_files: [src/wp02.py]\n"
        "authoritative_surface: src/wp02.py\nsubtasks: [T002]\n---\n\n# WP02\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "wp01.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "src" / "wp02.py").write_text("VALUE = 2\n", encoding="utf-8")


def _build_mission(
    repo: Path,
    slug: str,
    *,
    topology: MissionTopology,
    **overrides: object,
) -> tuple[str, Path]:
    result = make_mission(repo, slug, topology=topology, target_branch=_WORK_BRANCH, **overrides)
    feature_dir = result.feature_dir
    mission_slug = result.mission_slug
    _write_two_code_wps(repo, feature_dir)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"seed mission {mission_slug}")
    return mission_slug, feature_dir


def _finalize(mission_slug: str) -> Result:
    return runner.invoke(root_app, ["agent", "mission", "finalize-tasks", "--mission", mission_slug, "--json"])


def _implement(wp_id: str, mission_slug: str, *, json_output: bool = False) -> Result:
    args = ["implement", wp_id, "--mission", mission_slug]
    if json_output:
        args.append("--json")
    return runner.invoke(root_app, args)


def _move_to_for_review(wp_id: str, mission_slug: str) -> Result:
    return runner.invoke(root_app, ["agent", "tasks", "move-task", wp_id, "--to", "for_review", "--mission", mission_slug, "--json"])


def _read_events(feature_dir: Path) -> list[dict[str, Any]]:
    path = feature_dir / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _lane_worktrees(repo: Path, mission_slug: str) -> list[Path]:
    worktrees_dir = repo / ".worktrees"
    if not worktrees_dir.exists():
        return []
    return sorted(worktrees_dir.glob(f"{mission_slug}*-lane-*"))


@pytest.fixture
def single_branch_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path]:
    repo = _seed_repo(tmp_path, name="repo")
    mission_slug, feature_dir = _build_mission(repo, "issue-5100-single-branch", topology=MissionTopology.SINGLE_BRANCH)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    return repo, mission_slug, feature_dir


def test_lanes_control_creates_lane_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control for AS2 (non-vacuity): the IDENTICAL fixture under
    ``topology=lanes`` creates exactly one lane worktree, stamped
    ``worktree``."""
    repo = _seed_repo(tmp_path, name="repo")
    mission_slug, feature_dir = _build_mission(repo, "issue-5100-lanes-control", topology=MissionTopology.LANES)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    _assert_setup_ok("finalize-tasks (control)", _finalize(mission_slug))

    result = _implement("WP01", mission_slug, json_output=True)
    assert result.exit_code == 0, result.output

    lane_worktrees = _lane_worktrees(repo, mission_slug)
    assert len(lane_worktrees) == 1, f"expected exactly one lane worktree, got {lane_worktrees}"

    events = _read_events(feature_dir)
    wp01_in_progress = [e for e in events if e.get("wp_id") == "WP01" and e.get("to_lane") == "in_progress"]
    assert wp01_in_progress and wp01_in_progress[-1].get("execution_mode") == "worktree"


def test_for_review_without_force(single_branch_mission: tuple[Path, str, Path]) -> None:
    """AS4 + control AS5: a committed owned file lets for_review succeed
    without ``--force``, stamped ``direct_repo``; with no commit it is
    refused."""
    repo, mission_slug, feature_dir = single_branch_mission
    _assert_setup_ok("finalize-tasks", _finalize(mission_slug))
    _assert_setup_ok("implement WP01", _implement("WP01", mission_slug))

    # Control: subtasks ARE done, so the unchecked-subtask gate cannot be what
    # refuses; only the COMMIT gate (no implementation commit since claim) can.
    mark_done = runner.invoke(root_app, ["agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission_slug, "--json"])
    _assert_setup_ok("mark-status T001 done", mark_done)
    refused = _move_to_for_review("WP01", mission_slug)
    assert refused.exit_code != 0, refused.output
    assert "no implementation commit" in refused.output, refused.output

    (repo / "src" / "wp01.py").write_text("VALUE = 100\n", encoding="utf-8")
    _git(repo, "add", "src/wp01.py")
    _git(repo, "commit", "-m", "feat(WP01): deliverable")

    moved = _move_to_for_review("WP01", mission_slug)
    assert moved.exit_code == 0, moved.output

    events = _read_events(feature_dir)
    for_review = [e for e in events if e.get("wp_id") == "WP01" and e.get("to_lane") == "for_review"]
    assert for_review and for_review[-1].get("execution_mode") == "direct_repo"


def test_first_claim_meta_lock_commit_is_not_qualifying_work(single_branch_mission: tuple[Path, str, Path]) -> None:
    """A2: the first claim's ``meta.json`` VCS-lock commit lands AFTER the
    claim base is recorded, but is bookkeeping, not implementation work: both
    ``move-task`` and ``status emit`` must refuse a no-work WP."""
    _repo, mission_slug, feature_dir = single_branch_mission
    _assert_setup_ok("finalize-tasks", _finalize(mission_slug))
    _assert_setup_ok("implement WP01", _implement("WP01", mission_slug))
    _assert_setup_ok(
        "mark-status T001 done",
        runner.invoke(root_app, ["agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission_slug, "--json"]),
    )

    emitted = runner.invoke(root_app, ["agent", "status", "emit", "WP01", "--to", "for_review", "--actor", "claude", "--mission", mission_slug, "--json"])
    assert emitted.exit_code != 0, emitted.output
    assert "no implementation commit" in emitted.output, emitted.output

    moved = _move_to_for_review("WP01", mission_slug)
    assert moved.exit_code != 0, moved.output
    assert "no implementation commit" in moved.output, moved.output
    assert not [e for e in _read_events(feature_dir) if e.get("wp_id") == "WP01" and e.get("to_lane") == "for_review"]


def test_for_review_never_auto_commits_stray_repo_root_files(single_branch_mission: tuple[Path, str, Path]) -> None:
    """A1a: ``move-task --to for_review`` must not sweep every dirty path of
    the repository-root checkout into a "deliverables" commit -- neither a
    stray file, nor as a way for a no-work WP to pass the gate."""
    repo, mission_slug, feature_dir = single_branch_mission
    _assert_setup_ok("finalize-tasks", _finalize(mission_slug))
    _assert_setup_ok("implement WP01", _implement("WP01", mission_slug))
    _assert_setup_ok(
        "mark-status T001 done",
        runner.invoke(root_app, ["agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission_slug, "--json"]),
    )
    (repo / ".env.local").write_text("SECRET=1\n", encoding="utf-8")
    (repo / "src" / "wp01.py").write_text("VALUE = 100\n", encoding="utf-8")
    head_before = _git(repo, "rev-parse", "HEAD")

    moved = _move_to_for_review("WP01", mission_slug)

    assert moved.exit_code != 0, moved.output
    assert _git(repo, "rev-parse", "HEAD") == head_before, "no auto-commit may land on the target branch"
    assert ".env.local" not in _git(repo, "ls-files"), "a stray file must never be committed"
    assert not [e for e in _read_events(feature_dir) if e.get("wp_id") == "WP01" and e.get("to_lane") == "for_review"]
