"""Red-first: single-home write location for review-cycle + mark-status (WP08).

Mission ``coord-artifact-single-home-01M3V4BE``, FR-003/FR-007/SC-003. At the
lane base:

* A rejection on a coordination-routed Mission writes ``review-cycle-N.md``
  into the REPOSITORY ROOT checkout -- ``_review_cycle_wp_dir``'s own
  docstring discloses this is the WORK_PACKAGE_TASK (PRIMARY) default --
  even though ``commit_router.commit_artifact(..., kind=REVIEW_CYCLE)``
  already stages that same content onto the coordination branch via git
  plumbing ("stage-in-root-then-copy"). That leaves a transient PRIMARY
  residue the spec's "Transient staging" edge case forbids.
* ``mark-status``'s write leg (``_ms_resolve_read_dir``'s non-owned arm)
  resolves the WRITE location from ``resolve_status_surface(...).parent`` --
  a READ-oriented resolver -- instead of the write-location accessor, so a
  pre-fix EMPTY coordination Mission never gets seeded/materialized by this
  writer (FR-014's "a read resolver is never a write location").

Every scenario below drives the real, documented CLI entry point
(``spec-kitty agent tasks move-task`` / ``mark-status``), never a
reimplementation of the production code path.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.agent_tasks_ports import MissionHandle, RealCoordCommitRouter, default_ports
from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.coordination.coord_seed import CoordSeedForkRefused
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status import TransitionRequest
from tests._factories import make_mission
from tests._factories.coord_mission import make_fork_fixture

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP_ID = "WP01"
_WP_SLUG = "WP01-cycle-write-dir"
_TARGET_BRANCH = "topic/cycle-write-dir"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.name", "WP08 fixture")
    _git(repo, "config", "user.email", "wp08-fixture@spec-kitty.test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init WP08 fixture")


def _write_wp(feature_dir: Path, *, wp_slug: str = _WP_SLUG, subtasks: tuple[str, ...] = ()) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / f"{wp_slug}.md"
    if subtasks:
        subtasks_lines = "".join(f"  - {task_id}\n" for task_id in subtasks)
        subtasks_block = f"subtasks:\n{subtasks_lines}"
    else:
        subtasks_block = "subtasks: []\n"
    content = (
        "---\n"
        f"work_package_id: {_WP_ID}\n"
        "title: WP08 cycle-write-dir fixture\n"
        "execution_mode: code_change\n"
        f"{subtasks_block}"
        "owned_files:\n  - src/wp08-fixture/**\n"
        "authoritative_surface: src/wp08-fixture/\n"
        "---\n\n# WP08 fixture\n"
    )
    wp_path.write_text(content, encoding="utf-8")
    tasks_md = feature_dir / "tasks.md"
    if not tasks_md.exists():
        tasks_md.write_text("# Tasks\n", encoding="utf-8")
    return wp_path


def _unmaterialize_coord_worktree(repo: Path, mission_slug: str, mid8: str) -> Path:
    """Drop the worktree create seeded, keeping its branch (UNMATERIALIZED).

    Create now materializes the coordination surface eagerly. Scenarios that
    still need a never-checked-out local head establish that state explicitly.
    """
    coord_worktree = CoordinationWorkspace.worktree_path(repo, mission_slug, mid8)
    assert coord_worktree.exists(), "create seeds the coordination worktree"
    _git(repo, "worktree", "remove", "--force", str(coord_worktree))
    assert not coord_worktree.exists()
    return coord_worktree


def _seed_in_review(repo: Path, mission_slug: str, status_dir: Path) -> None:
    request = TransitionRequest(
        feature_dir=status_dir,
        mission_slug=mission_slug,
        repo_root=repo,
        wp_id=_WP_ID,
        to_lane="in_review",
        actor="wp08-seed",
        force=True,
        reason="seed reviewable state",
        execution_mode="worktree",
    )
    result = default_ports().coord.commit_status(request, capability=GuardCapability.STANDARD)
    assert result.event is not None and result.event.to_lane.value == "in_review"


def _build_coord_fixture(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    _init_repo(repo)
    created = make_mission(repo, "cycle-write-dir", topology=MissionTopology.COORD, target_branch=_TARGET_BRANCH)
    mission_slug = created.mission_slug
    _write_wp(created.feature_dir)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed WP08 fixture work package")
    handle = MissionHandle(repo_root=repo, mission_slug=mission_slug)
    status_dir = RealCoordCommitRouter().feature_write_dir(handle)
    _seed_in_review(repo, mission_slug, status_dir)
    return repo, mission_slug


def _reject(repo: Path, mission_slug: str, feedback_text: str) -> dict[str, Any]:
    feedback = repo.parent / f"{mission_slug}-feedback-{len(feedback_text)}.md"
    feedback.write_text(feedback_text, encoding="utf-8")
    args = [
        "tasks",
        "move-task",
        _WP_ID,
        "--to",
        "planned",
        "--mission",
        mission_slug,
        "--agent",
        "reviewer-renata",
        "--reviewer",
        "reviewer-renata",
        "--json",
        "--auto-commit",
        "--review-feedback-file",
        str(feedback),
    ]
    with chdir(repo):
        result = CliRunner().invoke(agent_app, args, catch_exceptions=True)
    assert result.exit_code == 0, result.output
    for line in result.output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            payload: dict[str, Any] = json.loads(line)
            return payload
    raise AssertionError(f"no JSON payload in move-task output: {result.output!r}")


def _coordination_worktree_for(repo: Path, coord_ref: str) -> Path | None:
    current_path: Path | None = None
    for line in _git(repo, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{coord_ref}" and current_path is not None:
            return current_path
    return None


def test_rejection_writes_review_cycle_in_place_on_coordination_worktree_with_no_root_residue(
    tmp_path: Path,
) -> None:
    """FR-003/FR-007: a coordination-routed rejection writes
    review-cycle-1.md directly into the coordination worktree (the owning
    surface), never the repository root checkout -- and the root checkout
    carries no residue afterward (spec edge case "Transient staging")."""
    repo, mission_slug = _build_coord_fixture(tmp_path)

    payload = _reject(repo, mission_slug, "**Issue**: Missing regression test.\n")
    assert payload.get("result") == "success", payload

    coord_ref = placement_seam(repo, mission_slug).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    relative = f"kitty-specs/{mission_slug}/tasks/{_WP_SLUG}/review-cycle-1.md"

    shown = subprocess.run(
        ["git", "-C", str(repo), "show", f"{coord_ref}:{relative}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert shown.returncode == 0, f"review-cycle-1.md not committed on {coord_ref!r}: {shown.stderr}"

    coord_worktree = _coordination_worktree_for(repo, coord_ref)
    assert coord_worktree is not None, "no coordination worktree materialized for the review ref"
    on_disk = coord_worktree / relative
    assert on_disk.is_file(), f"review-cycle-1.md must be written in place under {coord_worktree}"
    assert on_disk.read_text(encoding="utf-8") == shown.stdout

    root_artifact_dir = repo / "kitty-specs" / mission_slug / "tasks" / _WP_SLUG
    root_artifacts = sorted(p.name for p in root_artifact_dir.glob("review-cycle-*.md")) if root_artifact_dir.exists() else []
    assert root_artifacts == [], f"review-cycle residue in the repository root checkout: {root_artifacts}"

    status = _git(repo, "status", "--porcelain", "--", f"kitty-specs/{mission_slug}").stdout
    assert status.strip() == "", f"dirty root checkout after a coordination rejection: {status!r}"


def test_second_rejection_continues_cycle_numbering_on_the_coordination_surface(
    tmp_path: Path,
) -> None:
    """Cycle numbering must keep counting the EXISTING coordination-surface
    siblings, not restart at 1 because the writer now looks in a different
    (and initially empty) directory than before."""
    repo, mission_slug = _build_coord_fixture(tmp_path)
    _reject(repo, mission_slug, "**Issue**: First pass.\n")

    handle = MissionHandle(repo_root=repo, mission_slug=mission_slug)
    status_dir = RealCoordCommitRouter().feature_write_dir(handle)
    _seed_in_review(repo, mission_slug, status_dir)
    _reject(repo, mission_slug, "**Issue**: Second pass.\n")

    coord_ref = placement_seam(repo, mission_slug).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    relative = f"kitty-specs/{mission_slug}/tasks/{_WP_SLUG}/review-cycle-2.md"
    shown = subprocess.run(
        ["git", "-C", str(repo), "show", f"{coord_ref}:{relative}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert shown.returncode == 0, f"review-cycle-2.md not found on {coord_ref!r}: {shown.stderr}"


def test_mark_status_materializes_coordination_surface_via_the_write_accessor(
    tmp_path: Path,
) -> None:
    """T045/FR-014: mark-status's write leg must resolve through
    ``ports.coord.feature_write_dir`` (the write-location accessor), not the
    read-oriented ``resolve_status_surface(...).parent`` -- so a pre-fix
    EMPTY coordination Mission is materialized/seeded by this writer instead
    of silently appending to the PRIMARY checkout only.

    Create seeds the worktree eagerly, so the unmaterialized local head is
    engineered by removing that worktree before mark-status runs.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    created = make_mission(repo, "mark-status-write-dir", topology=MissionTopology.COORD, target_branch=_TARGET_BRANCH)
    mission_slug = created.mission_slug
    mid8 = str(created.meta["mid8"])
    _write_wp(created.feature_dir, subtasks=("T001",))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed WP08 mark-status fixture")

    coord_worktree = _unmaterialize_coord_worktree(repo, mission_slug, mid8)

    args = ["tasks", "mark-status", "T001", "--status", "done", "--mission", mission_slug, "--json"]
    with chdir(repo):
        result = CliRunner().invoke(agent_app, args, catch_exceptions=True)
    assert result.exit_code == 0, result.output

    # A real `git worktree add`-backed materialization (the write-location
    # accessor), never a plain `mkdir` landing a file at the same PATH by
    # coincidence (a naive filesystem write is not registered as a worktree).
    registered_worktrees = {
        Path(line.removeprefix("worktree ")) for line in _git(repo, "worktree", "list", "--porcelain").stdout.splitlines() if line.startswith("worktree ")
    }
    assert coord_worktree in registered_worktrees, (
        "mark-status's write leg must materialize/seed the coordination "
        "surface via the write-location accessor (a real git worktree), not "
        "a read-only fallback or a bare filesystem write at the same path"
    )
    events_file = coord_worktree / "kitty-specs" / mission_slug / "status.events.jsonl"
    assert events_file.is_file(), f"expected a status event log at {events_file}"
    assert "T001" in events_file.read_text(encoding="utf-8")


def test_flat_topology_review_cycle_still_lands_on_primary(tmp_path: Path) -> None:
    """C-008: a ``single_branch``/``lanes`` Mission is byte-identical to
    before -- the write home is still the repository root checkout."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    created = make_mission(repo, "cycle-write-dir-flat", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TARGET_BRANCH)
    mission_slug = created.mission_slug
    _write_wp(created.feature_dir)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed WP08 flat fixture")

    handle = MissionHandle(repo_root=repo, mission_slug=mission_slug)
    status_dir = RealCoordCommitRouter().feature_write_dir(handle)
    _seed_in_review(repo, mission_slug, status_dir)

    payload = _reject(repo, mission_slug, "**Issue**: Flat topology control.\n")
    assert payload.get("result") == "success", payload

    on_disk = repo / "kitty-specs" / mission_slug / "tasks" / _WP_SLUG / "review-cycle-1.md"
    assert on_disk.is_file()


def test_has_prior_rejection_and_fix_mode_see_a_primary_only_local_only_cycle(
    tmp_path: Path,
) -> None:
    """Decision ``plan.design.review-cycle-read-fallback`` (WP08 cycle 2, B1).

    A rejection recorded BEFORE this Mission's single-home write flip (a
    ``local_only`` outcome, e.g. ``--no-auto-commit``) physically lives ONLY
    in the PRIMARY repository-root checkout -- it was never staged onto the
    coordination surface. The coordination worktree for this WP exists and is
    materialized (the steady state every OTHER reader test observes) but
    carries NOTHING for this WP: ``has_prior_rejection`` and the fix-mode
    render must still find the PRIMARY-only cycle (C-002 read-only fallback),
    never silently miss it (fail-open)."""
    from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection
    from specify_cli.cli.commands.agent.workflow_executor import implement_try_render_fix_mode_prompt
    from specify_cli.review.artifacts import AffectedFile, ReviewCycleArtifact
    from specify_cli.status import Lane, StatusEvent
    from specify_cli.status.store import append_event

    repo = tmp_path / "repo"
    _init_repo(repo)
    created = make_mission(repo, "primary-only-cycle", topology=MissionTopology.COORD, target_branch=_TARGET_BRANCH)
    mission_slug = created.mission_slug
    wp_slug = "WP01-primary-only"
    _write_wp(created.feature_dir, wp_slug=wp_slug)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed primary-only-cycle fixture")

    # Materialize the coordination surface for THIS WP's status log, but
    # never touch its review-cycle directory there -- reproducing the
    # pre-single-home shape exactly (a materialized coord surface that is
    # simply silent about this WP's rejection history).
    handle = MissionHandle(repo_root=repo, mission_slug=mission_slug)
    status_dir = RealCoordCommitRouter().feature_write_dir(handle)

    # The old-style local-only artifact: written directly to PRIMARY, never
    # staged onto the coordination surface (no commit_router involved).
    feedback_text = "**Issue**: pre-single-home local-only rejection.\n"
    sub_artifact_dir = created.feature_dir / "tasks" / wp_slug
    sub_artifact_dir.mkdir(parents=True, exist_ok=True)
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id=_WP_ID,
        mission_slug=mission_slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-01-01T00:00:00Z",
        affected_files=[AffectedFile(path="src/app.py", line_range="1-5")],
        reproduction_command="pytest tests/review -q",
        body=feedback_text,
    ).write(sub_artifact_dir / "review-cycle-1.md")

    pointer = f"review-cycle://{mission_slug}/{wp_slug}/review-cycle-1.md"
    append_event(
        status_dir,
        StatusEvent(
            event_id="coord-seed-reject-primary-only",
            mission_slug=mission_slug,
            wp_id=_WP_ID,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    assert has_prior_rejection(created.feature_dir, wp_slug, _WP_ID) is True, (
        "has_prior_rejection must see a PRIMARY-only local-only cycle on a materialized coordination Mission (fail-open otherwise)"
    )

    prompt_path = implement_try_render_fix_mode_prompt(
        fix_mode_active=True,
        feature_dir=created.feature_dir,
        wp_slug=wp_slug,
        review_feedback_ref=pointer,
        review_feedback_file=sub_artifact_dir / "review-cycle-1.md",
        workspace_path=repo,
        mission_slug=mission_slug,
        normalized_wp_id=_WP_ID,
        repo_root=repo,
    )
    assert prompt_path is not None, "fix-mode render must not silently skip a PRIMARY-only local-only cycle"
    assert feedback_text.strip() in prompt_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD])
def test_rejection_on_a_never_touched_coordination_surface_still_materializes_in_place(tmp_path: Path, topology: MissionTopology) -> None:
    """Review cycle 2 B4 (MU2): every OTHER test in this file pre-materializes
    the coordination worktree (via ``RealCoordCommitRouter().feature_write_dir``
    or a prior ``mark-status``/``commit_status`` call) before the rejection
    under test runs, so ``read_dir`` and ``write_dir`` resolve to the SAME
    already-existing path and a writer reverted to the read-mode
    ``_review_cycle_wp_dir`` resolver is indistinguishable from the fix
    (mutation-surviving per review-WP08.md B4's MU2 finding).

    This drives :func:`create_rejected_review_cycle` as the first coordination
    write after the surface is torn back down. Create seeds the worktree
    eagerly, so the never-checked-out local head is engineered by removing
    that worktree first. Only the write-side accessor's own
    materialize-on-write behavior can make the assertion below pass.
    """
    from specify_cli.review.cycle import create_rejected_review_cycle

    repo = tmp_path / "repo"
    _init_repo(repo)
    created = make_mission(repo, "fresh-unmaterialized", topology=topology, target_branch=_TARGET_BRANCH)
    mission_slug = created.mission_slug
    mid8 = str(created.meta["mid8"])
    wp_slug = "WP01-fresh"
    _write_wp(created.feature_dir, wp_slug=wp_slug)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed fresh-unmaterialized fixture")

    coord_worktree = _unmaterialize_coord_worktree(repo, mission_slug, mid8)
    registered_before = {
        Path(line.removeprefix("worktree ")) for line in _git(repo, "worktree", "list", "--porcelain").stdout.splitlines() if line.startswith("worktree ")
    }
    assert coord_worktree not in registered_before, "fixture precondition: no prior write has registered the worktree"

    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission_slug,
        wp_id=_WP_ID,
        wp_slug=wp_slug,
        body="**Issue**: fresh-surface materialization check.\n",
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )

    registered_after = {
        Path(line.removeprefix("worktree ")) for line in _git(repo, "worktree", "list", "--porcelain").stdout.splitlines() if line.startswith("worktree ")
    }
    assert coord_worktree in registered_after, (
        "a review-cycle rejection on a never-touched Mission must materialize "
        "the coordination surface via the write-location accessor (a real git "
        "worktree), not a read-mode resolver that would see nothing there yet"
    )
    on_disk = coord_worktree / "kitty-specs" / mission_slug / "tasks" / wp_slug / "review-cycle-1.md"
    assert on_disk.is_file(), f"expected the review cycle written in place under {coord_worktree}"

    # The discriminating assertion against MU2: `read_dir`'s declared
    # EMPTY/UNMATERIALIZED fallback silently ANCHORS to the PRIMARY
    # repository-root checkout (it does not raise -- see
    # ``PlacementSeam.read_dir``'s docstring, "identical raising is NOT
    # identical anchoring"). A writer reverted to that read-mode resolver
    # would therefore physically write the bytes into the ROOT checkout
    # instead (leaving residue there) even though the commit router's own,
    # independent coordination-branch resolution still materializes the
    # worktree above as a side effect of staging the commit -- so the
    # worktree-registration check alone does not catch this mutant.
    root_artifact_dir = repo / "kitty-specs" / mission_slug / "tasks" / wp_slug
    root_artifacts = sorted(p.name for p in root_artifact_dir.glob("review-cycle-*.md")) if root_artifact_dir.exists() else []
    assert root_artifacts == [], f"review-cycle residue in the repository root checkout: {root_artifacts}"
    status = _git(repo, "status", "--porcelain", "--", f"kitty-specs/{mission_slug}").stdout
    assert status.strip() == "", f"dirty root checkout after a never-touched-Mission rejection: {status!r}"


def test_review_cycle_write_on_a_genuinely_forked_surface_raises_coord_seed_fork_refused(
    tmp_path: Path,
) -> None:
    """Review cycle 2 B4: ff74a9800a (Phase 2 durability-matrix re-pin) moved
    every durability-matrix write-path cell OFF the pre-fix forked shape (a
    coordination branch whose status log has genuinely, irreconcilably
    diverged from the root copy) onto a committed, seed-trailer-bearing
    surface instead -- correctly, since that IS the steady state a real
    Mission reaches. But that re-pin left the genuine fork-refusal outcome
    pinned NOWHERE for a review-cycle WRITE: ``write_dir``'s seed-time
    fork-safety check is the ONLY thing standing between a genuinely forked
    coordination branch and a silent, wrong-surface write.

    ``create_rejected_review_cycle`` must raise ``CoordSeedForkRefused``
    directly against :func:`make_fork_fixture`'s
    ``"root_uncommitted_coord_untracked"`` shape (the #5519 fork shape: a
    root-only status row, uncommitted, diverging from a second row appended
    once the coordination Mission dir exists) -- never silently write to
    either surface.
    """
    from specify_cli.review.cycle import create_rejected_review_cycle

    fixture = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD)

    with pytest.raises(CoordSeedForkRefused):
        create_rejected_review_cycle(
            main_repo_root=fixture.repo_root,
            mission_slug=fixture.mission_dir_name,
            wp_id=_WP_ID,
            wp_slug=_WP_ID,
            body="**Issue**: pre-fix forked surface.\n",
            reviewer_agent="reviewer-renata",
            commit_router=RealCoordCommitRouter(),
        )


def test_move_task_renders_coord_seed_fork_refused_as_an_error_not_a_traceback(
    tmp_path: Path,
) -> None:
    """The CLI-layer counterpart: ``move-task --review-feedback-file`` must
    surface the same ``CoordSeedForkRefused`` as a clean ``Error: ...`` line
    (exit 1), never an unhandled traceback, when the WP being rejected sits
    on a genuinely forked coordination Mission."""
    fixture = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD)
    mission_slug = fixture.mission_dir_name
    repo = fixture.repo_root

    tasks_dir = repo / "kitty-specs" / mission_slug / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{_WP_ID}.md").write_text(
        "---\nwork_package_id: WP01\ntitle: fork CLI probe\nexecution_mode: code_change\nsubtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (repo / "kitty-specs" / mission_slug / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add WP01 for fork CLI probe")

    feedback = repo.parent / "fork-cli-feedback.md"
    feedback.write_text("**Issue**: pre-fix forked surface (CLI).\n", encoding="utf-8")

    args = [
        "tasks",
        "move-task",
        _WP_ID,
        "--to",
        "planned",
        "--mission",
        mission_slug,
        "--agent",
        "reviewer-renata",
        "--reviewer",
        "reviewer-renata",
        "--review-feedback-file",
        str(feedback),
        "--force",
    ]
    with chdir(repo):
        result = CliRunner().invoke(agent_app, args, catch_exceptions=True)

    assert result.exit_code == 1
    assert "Error:" in result.output, result.output
    assert "coordination seed refused" in result.output, result.output
    assert "Traceback" not in result.output, result.output


def test_review_cycle_write_on_a_published_consolidated_mission_resolves_to_primary(
    tmp_path: Path,
) -> None:
    """Research D23 (review-WP08.md B4): a PUBLISHED (post-consolidation)
    Mission's REVIEW_CYCLE write resolves straight to PRIMARY -- the merged
    repository-root checkout -- WITHOUT ever probing coordination state, even
    when the coordination branch has been fully deleted. WP04's own
    ``test_write_dir_e2_eligible_kind_bypasses_deleted_coordination_branch``
    (``tests/mission_runtime/test_placement_seam_write_dir.py``) pins this at
    the ``PlacementSeam.write_dir`` primitive; this closes the gap the
    reviewer named -- WP08's OWN caller (``create_rejected_review_cycle``,
    the real rejection writer) must exercise the same bypass end-to-end, not
    merely the underlying seam.
    """
    from specify_cli.review.cycle import create_rejected_review_cycle
    from tests.mission_runtime.test_consolidated_resolution import (
        _build_e2_mission_coord_fully_retired,
        _init_git_repo,
    )

    repo = tmp_path / "repo"
    _init_git_repo(repo)
    mission_slug, feature_dir, _target_branch, coordination_branch = _build_e2_mission_coord_fully_retired(repo, mid8="01KYT4CC", mission_number=501)
    assert not _branch_exists_locally(repo, coordination_branch), "fixture precondition: coordination branch must be fully deleted (PUBLISHED)"

    outcome = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission_slug,
        wp_id=_WP_ID,
        wp_slug="WP01-evidence",
        body="**Issue**: PUBLISHED-mission rejection.\n",
        reviewer_agent="reviewer-renata",
        commit_router=None,
    )

    on_disk = feature_dir / "tasks" / "WP01-evidence" / "review-cycle-1.md"
    assert on_disk.is_file(), f"expected the review cycle written to the PRIMARY (merged) checkout at {on_disk}"
    assert outcome.persistence.classification == "local_only"


def _branch_exists_locally(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode == 0
