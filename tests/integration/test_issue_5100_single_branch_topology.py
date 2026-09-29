"""#5100 red-first acceptance: single_branch topology executes in the write
checkout (spec.md US2, "A single_branch mission runs in its write checkout").

Committed FIRST, alone (charter C-011 / ATDD-First Discipline), before any
WP05 implementation commit. On the mission's ``planning_base_branch``
(``compute_lanes`` still ignoring ``topology`` entirely -- today's #5100
defect) this file is RED on assertions, never a fixture crash:

- Test 1 fails on the LANE-COUNT assertion (``compute_lanes`` still splits
  WP01/WP02 into ordinary code lanes instead of one ``lane-planning`` lane).
- Test 2 fails on the ``.worktrees/*-lane-a`` assertion (``implement``
  materialises an ordinary lane worktree for the single_branch mission's
  code WP).

Tests 7 and 8 are ``xfail(strict=True, reason="WP08")`` -- the
protected-target mission-branch mint and the ``--commit-to-target``
override land in a LATER work package of this mission.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
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

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

runner = CliRunner()

_WORK_BRANCH = "issue-5100-work"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _assert_setup_ok(label: str, cli_result: object) -> None:
    """Pre-assert a SETUP command's exit code with a distinct message.

    Every setup step in a fixture is asserted this way (never left to fail
    implicitly later) so a fixture crash can never masquerade as one of
    this file's own red-first acceptance assertions.
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


def _write_two_code_wps(repo: Path, feature_dir: Path, *, wp02_independent: bool = False) -> None:
    """Write WP01 (no deps) + WP02.

    ``wp02_independent`` (review cycle 1, Issue 1): by default WP02 depends
    on WP01, which is exactly right for the finalize/lane-manifest tests
    (1) and the readiness-preserving tests (2, 4) -- but it means
    ``implement WP02`` while WP01 is ``in_progress`` is refused by
    DEPENDENCY READINESS, before the write-checkout occupancy check ever
    runs. ``test_second_implement_refused_names_in_progress_wp`` (AS6)
    needs the OCCUPANCY refusal specifically, so it passes
    ``wp02_independent=True`` to remove the dependency-gate interference
    and isolate the real discriminator.
    """
    wp02_deps_prose = "None" if wp02_independent else "WP01"
    wp02_deps_frontmatter = "[]" if wp02_independent else "[WP01]"
    (feature_dir / "spec.md").write_text("# Spec\n\n## Functional Requirements\n\n- **FR-001**: repro.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\n**Language/Version**: Python 3.11\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\n- [ ] T001 alpha\n\n"
        f"## Work Package WP02\n\n**Dependencies**: {wp02_deps_prose}\n\n- [ ] T002 beta\n",
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
        f"---\nwork_package_id: WP02\ntitle: Second code WP\ndependencies: {wp02_deps_frontmatter}\n"
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
    wp02_independent: bool = False,
    **overrides: object,
) -> tuple[str, Path]:
    result = make_mission(repo, slug, topology=topology, target_branch=_WORK_BRANCH, **overrides)
    feature_dir = result.feature_dir
    mission_slug = result.mission_slug
    _write_two_code_wps(repo, feature_dir, wp02_independent=wp02_independent)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"seed mission {mission_slug}")
    return mission_slug, feature_dir


def _finalize(mission_slug: str):
    return runner.invoke(root_app, ["agent", "mission", "finalize-tasks", "--mission", mission_slug, "--json"])


def _implement(wp_id: str, mission_slug: str, *, json_output: bool = False):
    args = ["implement", wp_id, "--mission", mission_slug]
    if json_output:
        args.append("--json")
    return runner.invoke(root_app, args)


def _move_to_for_review(wp_id: str, mission_slug: str):
    return runner.invoke(root_app, ["agent", "tasks", "move-task", wp_id, "--to", "for_review", "--mission", mission_slug, "--json"])


def _read_events(feature_dir: Path) -> list[dict]:
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


@pytest.fixture
def single_branch_mission_independent_wps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path]:
    """Review cycle 1, Issue 1: WP02 has NO dependency on WP01, so a claim
    attempt on WP02 while WP01 is in_progress is discriminated by
    write-checkout OCCUPANCY alone, never masked by dependency readiness."""
    repo = _seed_repo(tmp_path, name="repo")
    mission_slug, feature_dir = _build_mission(
        repo,
        "issue-5100-single-branch-indep",
        topology=MissionTopology.SINGLE_BRANCH,
        wp02_independent=True,
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    return repo, mission_slug, feature_dir


def test_finalize_writes_single_repo_root_lane(single_branch_mission: tuple[Path, str, Path]) -> None:
    """AS1: finalize-tasks writes a manifest with exactly one repo-root lane
    holding every WP."""
    _repo, mission_slug, feature_dir = single_branch_mission

    result = _finalize(mission_slug)
    _assert_setup_ok("finalize-tasks", result)

    lanes = json.loads((feature_dir / "lanes.json").read_text(encoding="utf-8"))
    assert len(lanes["lanes"]) == 1, f"expected exactly ONE lane, got {lanes['lanes']}"
    lane = lanes["lanes"][0]
    assert lane["lane_id"] == "lane-planning"
    assert set(lane["wp_ids"]) == {"WP01", "WP02"}


def test_implement_runs_in_repo_root_without_lane_artifacts(single_branch_mission: tuple[Path, str, Path]) -> None:
    """AS2: implement WP01 exits 0, creates no ``.worktrees/`` or
    ``kitty/mission-*`` ref, resolves to the write checkout, and stamps the
    claim/in_progress events ``direct_repo``."""
    repo, mission_slug, feature_dir = single_branch_mission
    _assert_setup_ok("finalize-tasks", _finalize(mission_slug))

    result = _implement("WP01", mission_slug, json_output=True)
    assert result.exit_code == 0, result.output

    assert not _lane_worktrees(repo, mission_slug), "no .worktrees/*-lane-* directory may be created"
    mission_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/kitty/mission-*")
    assert mission_refs == "", f"no kitty/mission-* ref may be created, found: {mission_refs!r}"

    payload = json.loads(result.output)
    assert payload["workspace_path"] == ".", "the resolved workspace must be the write checkout (repo root)"

    events = _read_events(feature_dir)
    wp01_events = [e for e in events if e.get("wp_id") == "WP01"]
    claimed = [e for e in wp01_events if e.get("to_lane") == "claimed"]
    in_progress = [e for e in wp01_events if e.get("to_lane") == "in_progress"]
    assert claimed, "no 'claimed' event recorded for WP01"
    assert claimed[-1].get("execution_mode") == "direct_repo"
    assert in_progress, "no 'in_progress' event recorded for WP01"
    assert in_progress[-1].get("execution_mode") == "direct_repo"


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

    # Control: no commit since claim -> refused.
    refused = _move_to_for_review("WP01", mission_slug)
    assert refused.exit_code != 0, refused.output

    (repo / "src" / "wp01.py").write_text("VALUE = 100\n", encoding="utf-8")
    _git(repo, "add", "src/wp01.py")
    _git(repo, "commit", "-m", "feat(WP01): deliverable")
    mark_done = runner.invoke(root_app, ["agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission_slug, "--json"])
    _assert_setup_ok("mark-status T001 done", mark_done)

    moved = _move_to_for_review("WP01", mission_slug)
    assert moved.exit_code == 0, moved.output

    events = _read_events(feature_dir)
    for_review = [e for e in events if e.get("wp_id") == "WP01" and e.get("to_lane") == "for_review"]
    assert for_review and for_review[-1].get("execution_mode") == "direct_repo"


def test_second_implement_refused_names_in_progress_wp(single_branch_mission_independent_wps: tuple[Path, str, Path]) -> None:
    """AS6: WP01 in_progress; implement of an INDEPENDENT WP02 (no
    dependency on WP01 -- review cycle 1, Issue 1) is refused by
    write-checkout OCCUPANCY, naming WP01, with nothing created.

    Asserting the specific ``WriteCheckoutOccupiedError`` message (not just
    a non-zero exit) is what proves this is the occupancy refusal and not
    a same-shaped dependency-readiness refusal: M6 (occupancy check
    disabled) turns this test red -- see the mutation evidence in the
    commit message.
    """
    repo, mission_slug, _feature_dir = single_branch_mission_independent_wps
    _assert_setup_ok("finalize-tasks", _finalize(mission_slug))
    _assert_setup_ok("implement WP01", _implement("WP01", mission_slug))

    before = _lane_worktrees(repo, mission_slug)
    result = _implement("WP02", mission_slug)

    assert result.exit_code != 0
    assert "already in_progress in the shared write checkout" in result.output, result.output
    assert "WP01" in result.output, result.output
    assert _lane_worktrees(repo, mission_slug) == before, "nothing may be created on refusal"


def test_dirty_checkout_refused_but_resume_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS8, in two isolated halves (review cycle 1, Issue 1) so neither
    check is masked by write-checkout OCCUPANCY:

    - Half A: on a mission where NOTHING is in_progress yet, an untracked
      file outside spec-kitty paths refuses a genuinely first-ever claim,
      naming the dirty path (the ``WriteCheckoutDirtyError`` message).
      M7 (dirty check disabled) turns this half red.
    - Half B: on a SEPARATE, freshly-clean mission, WP01 is claimed while
      clean, THEN the same dirt appears; resuming WP01 tolerates it (the
      resume exemption) and the in_progress event is stamped
      ``direct_repo``.
    """
    # --- Half A: dirty refuses a genuinely new (first-ever) claim. ---
    repo_a = _seed_repo(tmp_path, name="repo-dirty-new")
    mission_a, _feature_dir_a = _build_mission(repo_a, "issue-5100-dirty-new", topology=MissionTopology.SINGLE_BRANCH)
    monkeypatch.chdir(repo_a)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    _assert_setup_ok("finalize-tasks (dirty-new)", _finalize(mission_a))
    (repo_a / "scratch_outside_spec_kitty.txt").write_text("untracked\n", encoding="utf-8")

    first_claim = _implement("WP01", mission_a)
    assert first_claim.exit_code != 0, "a genuinely new claim must be refused while the checkout is dirty"
    assert "scratch_outside_spec_kitty.txt" in first_claim.output, first_claim.output

    # --- Half B: resuming an already-in_progress WP tolerates the same dirt. ---
    repo_b = _seed_repo(tmp_path, name="repo-dirty-resume")
    mission_b, feature_dir_b = _build_mission(repo_b, "issue-5100-dirty-resume", topology=MissionTopology.SINGLE_BRANCH)
    monkeypatch.chdir(repo_b)
    _assert_setup_ok("finalize-tasks (dirty-resume)", _finalize(mission_b))
    _assert_setup_ok("implement WP01 (clean claim)", _implement("WP01", mission_b))

    (repo_b / "scratch_outside_spec_kitty.txt").write_text("untracked\n", encoding="utf-8")

    resume = _implement("WP01", mission_b)
    assert resume.exit_code == 0, f"resuming the already-in_progress WP must tolerate the dirt: {resume.output}"

    events = _read_events(feature_dir_b)
    wp01_in_progress = [e for e in events if e.get("wp_id") == "WP01" and e.get("to_lane") == "in_progress"]
    assert wp01_in_progress and wp01_in_progress[-1].get("execution_mode") == "direct_repo"


@pytest.mark.xfail(strict=True, reason="WP08")
def test_protected_target_mints_mission_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS1 (US3): a single_branch mission created on a protected target
    (``main``, no override) mints ``kitty/mission-<slug>-<mid8>``, checked
    out in the write checkout, with no worktree. Lands in WP08 (IC-05)."""
    repo = _seed_repo(tmp_path, name="protected-repo")
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    _git(repo, "checkout", "main")

    result = make_mission(repo, "issue-5100-protected", topology=MissionTopology.SINGLE_BRANCH, target_branch="main")

    minted_branch = f"kitty/mission-issue-5100-protected-{result.meta.get('mission_id', '')[:8].lower()}"
    assert _git(repo, "branch", "--show-current") == minted_branch
    assert result.meta.get("mission_branch") == minted_branch
    assert not (repo / ".worktrees").exists()


@pytest.mark.xfail(strict=True, reason="WP08")
def test_commit_to_target_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS3 (US3): ``--commit-to-target`` mints no mission branch. A usage
    error today (the flag does not exist yet); lands in WP08."""
    repo = _seed_repo(tmp_path, name="commit-to-target-repo")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    _git(repo, "checkout", "main")

    result = runner.invoke(
        root_app,
        [
            "agent",
            "mission",
            "create",
            "issue-5100-commit-to-target",
            "--topology",
            "single_branch",
            "--commit-to-target",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload.get("mission_branch") is None
    mission_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/kitty/mission-*")
    assert mission_refs == ""
