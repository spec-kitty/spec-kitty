"""T032 (coord-artifact-single-home-01M3V4BE, FR-002a / US1.4-1.5).

Seeding the coordination surface at create time must not depend on the
TARGET-branch scaffold commit landing (US1.4, protected-primary), and a
create that fails after the coordination seed/commit must undo it
failure-atomically: the coordination worktree and a newly-minted branch are
removed; a branch this create merely REUSED is CAS-reset to its own
pre-create tip, never deleted (US1.5).

Drives the real production entry point (``create_mission_core``) over real
temporary git repositories -- no commit mocks for the assertions.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ulid import ULID as _RealULID

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationError, _create_mission_core_failure_atomic, create_mission_core
from specify_cli.lanes.branch_naming import mission_dir_name, resolve_mid8
from specify_cli.missions._create import coordination_branch_name

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _init_repo(repo: Path, *, branch: str) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    (repo / "kitty-specs" / ".gitkeep").touch()
    _git(repo, "init", "-b", branch)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _install_hook(repo: Path, body: str) -> None:
    """Real git fault: a repo-local hook (``core.hooksPath`` pinned so a global setting cannot bypass it)."""
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", str(hooks))


def _refuse_on_branch(branch_pattern: str, message: str, *, before: str = "") -> str:
    """Hook body: run ``before``, then refuse every commit whose branch matches ``branch_pattern``."""
    return f'case "$(git rev-parse --abbrev-ref HEAD)" in\n  {branch_pattern}) {before}echo "{message}" >&2; exit 1 ;;\nesac\nexit 0\n'


def _summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


@pytest.fixture(autouse=True)
def _cwd_outside_any_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worktree-context guard reads the real process cwd, and pytest may run
    from inside a lane worktree. Run each create from the ``tmp_path`` fixture
    repository so the real guard sees a non-worktree checkout (no patch)."""
    monkeypatch.chdir(tmp_path)


# ---------------------------------------------------------------------------
# (a) Protected-primary create still materializes and seeds (US1.4)
# ---------------------------------------------------------------------------


def test_protected_primary_still_seeds_coordination_surface(tmp_path: Path) -> None:
    """``main`` is protected by default -- the target scaffold commit is a
    disclosed bootstrap skip, but the coordination surface is still
    materialized, seeded and committed (unconditionally, T031/T032)."""
    _init_repo(tmp_path, branch="main")

    result = create_mission_core(
        tmp_path,
        "protected-seed",
        topology=MissionTopology.COORD,
        target_branch="main",
        allow_worktree_context=True,
        **_summary("protected-seed"),
    )

    assert result.meta["topology"] == MissionTopology.COORD.value
    coordination_branch = result.meta["coordination_branch"]
    assert coordination_branch, "a coord create must mint a coordination branch even on a protected primary"
    coord_tree = _git(tmp_path, "ls-tree", "-r", "--name-only", coordination_branch).splitlines()
    assert f"kitty-specs/{result.mission_slug}/status.events.jsonl" in coord_tree
    assert f"kitty-specs/{result.mission_slug}/meta.json" not in coord_tree, "no PRIMARY file belongs on the coordination branch (US1.3)"
    # The target branch, meanwhile, never received a scaffold commit at all
    # (the bootstrap skip): it still sits at its pre-create tip.
    target_tree = _git(tmp_path, "ls-tree", "-r", "--name-only", "main").splitlines()
    assert f"kitty-specs/{result.mission_slug}/meta.json" not in target_tree


# ---------------------------------------------------------------------------
# (b) Failure-atomic rollback after the seed (US1.5)
# ---------------------------------------------------------------------------


def test_rollback_after_seed_removes_worktree_and_branch(tmp_path: Path) -> None:
    """A failure injected right after the coordination seed/commit undoes both
    the coordination worktree and the branch THIS create minted, and restores
    the operator's original checkout."""
    _init_repo(tmp_path, branch="work")
    original_branch = _git(tmp_path, "branch", "--show-current").strip()
    # A real failure of the target scaffold commit (a hook refusing commits
    # on ``work``). Non-vacuity: the hook records whether the coordination
    # worktree genuinely existed at the time of the failure, so the rollback
    # assertions below are a real regression guard on T032's teardown -- not
    # merely observing that a worktree was never created in the first place.
    marker = tmp_path / ".git" / "worktree-present-at-failure"
    probe = f'ls -d "{tmp_path}/.worktrees/"rollback-seed* >/dev/null 2>&1 && echo yes > "{marker}"; '
    _install_hook(tmp_path, _refuse_on_branch("work", "injected failure after coordination seed", before=probe))

    with pytest.raises(RuntimeError, match="injected failure after coordination seed"):
        create_mission_core(
            tmp_path,
            "rollback-seed",
            topology=MissionTopology.COORD,
            allow_worktree_context=True,
            **_summary("rollback-seed"),
        )

    assert marker.read_text(encoding="utf-8").strip() == "yes", "the coordination worktree must be materialized BEFORE the injected failure (non-vacuity)"
    branches = [line for line in _git(tmp_path, "branch", "--list", "kitty/mission-*", "--format=%(refname:short)").splitlines() if line.strip()]
    assert branches == [], f"the minted coordination branch must be deleted on rollback, found: {branches}"
    worktrees = _git(tmp_path, "worktree", "list", "--porcelain")
    assert "rollback-seed" not in worktrees, "the coordination worktree must be removed on rollback"
    assert not (tmp_path / ".worktrees").exists() or not list((tmp_path / ".worktrees").glob("rollback-seed*"))
    assert _git(tmp_path, "branch", "--show-current").strip() == original_branch


# ---------------------------------------------------------------------------
# (c) A pre-existing coordination branch is RESET, not deleted
# ---------------------------------------------------------------------------


def test_preexisting_coordination_branch_is_reset_not_deleted(tmp_path: Path) -> None:
    """A coordination branch that pre-dates this create (silently reused,
    ``created=False``) is CAS-reset to its OWN pre-create tip on rollback --
    never deleted, since it is not this run's own mint (it may belong to
    another create / a prior healed Mission)."""
    _init_repo(tmp_path, branch="work")
    # The identity is fixed through the private input of the create body,
    # so the coordination branch name is known before the create runs.
    fixed_ulid = _RealULID()

    mid8 = resolve_mid8("", mission_id=str(fixed_ulid))
    mission_slug_formatted = mission_dir_name("reset-not-delete", mid8=mid8)
    coordination_branch = coordination_branch_name(mission_slug_formatted, str(fixed_ulid))

    # Pre-create the coordination branch, at the current (soon-to-be-target)
    # tip, BEFORE create runs -- simulating a pre-existing branch this create
    # will silently reuse rather than mint.
    _git(tmp_path, "branch", coordination_branch, "work")
    pre_existing_tip = _git(tmp_path, "rev-parse", coordination_branch).strip()
    # A real failure of the target scaffold commit. Non-vacuity: the hook records
    # the coordination branch tip at the failure, proving the seed/creation-events
    # commit genuinely moved the branch past its pre-existing tip, so "reset, not
    # deleted" below is a real CAS-reset regression guard.
    tip_marker = tmp_path / ".git" / "coordination-tip-at-failure"
    probe = f'git rev-parse "{coordination_branch}" > "{tip_marker}"; '
    _install_hook(tmp_path, _refuse_on_branch("work", "injected failure on reuse", before=probe))

    with pytest.raises(RuntimeError, match="injected failure on reuse"):
        _create_mission_core_failure_atomic(
            tmp_path,
            "reset-not-delete",
            topology=MissionTopology.COORD,
            allow_worktree_context=True,
            _mission_id=str(fixed_ulid),
            **_summary("reset-not-delete"),
        )

    tip_seen_before_failure = tip_marker.read_text(encoding="utf-8").split()
    assert tip_seen_before_failure and tip_seen_before_failure[0] != pre_existing_tip, (
        "the coordination seed/creation-events commit must move the branch before the injected failure (non-vacuity)"
    )
    # Still present (never deleted) and reset back to its pre-create tip
    # (the seed/creation-events commit that landed before the injected
    # failure must be undone).
    assert _git(tmp_path, "rev-parse", "--verify", coordination_branch).strip()
    assert _git(tmp_path, "rev-parse", coordination_branch).strip() == pre_existing_tip


# ---------------------------------------------------------------------------
# (d) B2 (review cycle 2, HIGH): the rollback context must be recorded BEFORE
# ``write_dir`` runs, not only once ``_seed_coord_surface_for_create``
# returns -- a failure INSIDE the seed (after ``write_dir`` has already
# materialized the worktree) must not orphan the minted branch/worktree.
# Three points a failure can strike between materialization and the
# coordination commit landing: two injected (parametrized below) and the
# coordination commit itself, failed for real by a git hook.
# ---------------------------------------------------------------------------


def _assert_no_coordination_leftovers(repo: Path, slug: str, original_branch: str, failure_point: str) -> None:
    branches = [line for line in _git(repo, "branch", "--list", "kitty/mission-*", "--format=%(refname:short)").splitlines() if line.strip()]
    assert branches == [], f"no coordination branch may be left orphaned (failure point: {failure_point}), found: {branches}"
    worktree_list = _git(repo, "worktree", "list", "--porcelain")
    assert slug not in worktree_list, f"no coordination worktree registry entry may survive (failure point: {failure_point}): {worktree_list!r}"
    assert not (repo / ".worktrees").exists() or not list((repo / ".worktrees").glob(f"{slug}*")), (
        f"no coordination worktree directory may survive on disk (failure point: {failure_point})"
    )
    assert _git(repo, "branch", "--show-current").strip() == original_branch


@pytest.mark.parametrize(
    "failure_target",
    [
        # Inside ``write_dir`` itself, AFTER it has materialized the
        # coordination worktree (the exact half-built-surface shape US1.5
        # forbids: the generic rollback's ``git branch -D`` would otherwise
        # fail because the branch is still checked out in the worktree).
        "specify_cli.coordination.coord_seed._seed_coord_surface",
        # After the seed returns, before the coordination commit. No real
        # reproduction exists for a failure at exactly this step, so the
        # orchestrator's own call is replaced (kept with rationale).
        "specify_cli.core.mission_creation._emit_create_events",
    ],
    ids=["inside_write_dir_seed", "emit_create_events"],
)
def test_rollback_covers_every_seed_injection_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_target: str) -> None:
    """B2: no leftover branch, worktree or worktree-registry entry at the injected points."""
    _init_repo(tmp_path, branch="work")
    original_branch = _git(tmp_path, "branch", "--show-current").strip()

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected")

    monkeypatch.setattr(failure_target, _raise)

    slug = "probe-" + failure_target.rsplit(".", 1)[-1].strip("_").replace("_", "-")[:24]
    with pytest.raises(RuntimeError, match="injected"):
        create_mission_core(
            tmp_path,
            slug,
            topology=MissionTopology.COORD,
            allow_worktree_context=True,
            **_summary(slug),
        )

    _assert_no_coordination_leftovers(tmp_path, slug, original_branch, failure_target)


def test_rollback_covers_a_failed_coordination_commit(tmp_path: Path) -> None:
    """B2, third injection point: the coordination commit itself fails for real (a
    ``pre-commit`` hook refuses every commit on ``kitty/mission-*``)."""
    _init_repo(tmp_path, branch="work")
    original_branch = _git(tmp_path, "branch", "--show-current").strip()
    _install_hook(tmp_path, _refuse_on_branch("kitty/mission-*", "injected coordination commit refusal"))

    slug = "probe-commit-coord-create-events"
    with pytest.raises(MissionCreationError, match="injected coordination commit refusal"):
        create_mission_core(
            tmp_path,
            slug,
            topology=MissionTopology.COORD,
            allow_worktree_context=True,
            **_summary(slug),
        )

    _assert_no_coordination_leftovers(tmp_path, slug, original_branch, "commit_coord_create_events")
