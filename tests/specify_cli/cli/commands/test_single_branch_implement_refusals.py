"""``spec-kitty implement`` repo-root-lane refusals for single_branch (#5100 WP04 T018).

Drives the REAL ``implement()`` CLI entry point (wrapped in a throwaway
``typer.Typer()``, the established pattern for this command --
``tests/specify_cli/cli/commands/test_implement_bulk_edit_flag.py``) against
a hand-written single_branch repo-root manifest. Covers the contract's
refusal order (``contracts/single-branch-execution.md``, "Implement:
refusals") 2-4: wrong branch, occupied, dirty -- plus the resume exemption
and the two-missions-sharing-a-checkout case (US2.7).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from click.testing import Result

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.implement_support import (
    WriteCheckoutDirtyError,
    WriteCheckoutOccupiedError,
    WriteCheckoutWrongBranchError,
    _ensure_repo_root_checkout_available,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.review.lock import LOCK_DIR, LOCK_FILE
from specify_cli.status.store import read_events
from specify_cli.workspace.context import ResolvedWorkspace
from tests.utils import _seed_canonical_wp_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _implement_app() -> typer.Typer:
    from specify_cli.cli.commands.implement import implement as implement_fn

    app = typer.Typer()
    app.command(name="implement")(implement_fn)
    return app


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "trunk")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, mission_slug: str, mission_id: str, *, topology: str = "single_branch", target_branch: str = "trunk") -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "slug": mission_slug,
                "mid8": mission_id[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": target_branch,
                "topology": topology,
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": mission_slug,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_code_wp(feature_dir: Path, wp_id: str, *, dependencies: list[str] | None = None) -> None:
    deps = dependencies or []
    lines = [
        "---",
        f"work_package_id: {wp_id}",
        "title: Code change",
        f"dependencies: {deps!r}",
        "execution_mode: code_change",
        "owned_files:",
        "- src/**",
        "subtasks: []",
        "---",
        "",
        "Body.",
        "",
        "## Activity Log",
        "",
    ]
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text("\n".join(lines), encoding="utf-8")
    (feature_dir / "tasks.md").write_text(f"# Tasks\n\n## {wp_id} Code change\n", encoding="utf-8")


def _write_planning_wp(feature_dir: Path, wp_id: str, *, dependencies: list[str] | None = None) -> None:
    deps = dependencies or []
    lines = [
        "---",
        f"work_package_id: {wp_id}",
        "title: Planning artifact",
        f"dependencies: {deps!r}",
        "execution_mode: planning_artifact",
        "owned_files:",
        "- kitty-specs/**",
        "subtasks: []",
        "---",
        "",
        "Body.",
        "",
        "## Activity Log",
        "",
    ]
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text("\n".join(lines), encoding="utf-8")
    (feature_dir / "tasks.md").write_text(f"# Tasks\n\n## {wp_id} Planning\n", encoding="utf-8")


def _repo_root_manifest(mission_slug: str, mission_id: str, wp_id: str, *, target_branch: str = "trunk") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_branch="",
        target_branch=target_branch,
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=(wp_id,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _repo_root_manifest_multi(mission_slug: str, mission_id: str, wp_ids: tuple[str, ...]) -> LanesManifest:
    """Same repo-root manifest shape as :func:`_repo_root_manifest`, for
    several WPs sharing the ONE repo-root lane (dependency-readiness /
    no-merge-commit coverage need two WPs in the same checkout)."""
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_branch="",
        target_branch="trunk",
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=wp_ids,
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _build_mission(
    repo: Path,
    mission_slug: str,
    mission_id: str,
    wp_id: str = "WP01",
    *,
    topology: str = "single_branch",
    wp_kind: str = "code_change",
    target_branch: str = "trunk",
) -> Path:
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug, mission_id, topology=topology, target_branch=target_branch)
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    if wp_kind == "code_change":
        _write_code_wp(feature_dir, wp_id)
    else:
        _write_planning_wp(feature_dir, wp_id)
    write_lanes_json(feature_dir, _repo_root_manifest(mission_slug, mission_id, wp_id, target_branch=target_branch))
    _seed_canonical_wp_state(repo, mission_slug, wp_id, "planned", actor="system", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:30:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"planning: seed {mission_slug}")
    return feature_dir


def _resolved_workspace(repo: Path, mission_slug: str, wp_id: str, branch_name: str | None) -> ResolvedWorkspace:
    """A minimal, real ``ResolvedWorkspace`` for calling ``_ensure_repo_root_checkout_available``
    directly -- isolates each refusal from every OTHER check the full CLI runs first
    (review cycle-1 issue 3: the CLI-level test alone cannot tell "this refusal fired"
    from "something upstream fired instead")."""
    return ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id=wp_id,
        execution_mode="code_change",
        mode_source="frontmatter",
        resolution_kind="repo_root",
        workspace_name=f"{mission_slug}-{PLANNING_LANE_ID}",
        worktree_path=repo,
        branch_name=branch_name,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=[wp_id],
    )


def _run_implement(repo: Path, mission_slug: str, wp_id: str = "WP01", *, actor: str = "system") -> Result:
    return runner.invoke(_implement_app(), [wp_id, "--mission", mission_slug, "--json", "--actor", actor], catch_exceptions=False)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    _init_repo(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    return root


# ---------------------------------------------------------------------------
# Successful claim (control) -- also proves T016's implement.py stamp site.
# ---------------------------------------------------------------------------


def test_fresh_claim_succeeds_with_no_worktree_and_direct_repo_stamp(repo: Path) -> None:
    """Characterization (review cycle-1 nit 5): a happy-path claim also
    passes at the red commit 9383ee62's pre-``effective_root`` base, so it
    does not by itself discriminate any single WP04 change -- it documents
    the intended steady-state behavior (no worktree, ``direct_repo`` stamp)
    the other, discriminating refusal tests in this file are refusals
    AGAINST."""
    mission_slug = "impl-fresh"
    feature_dir = _build_mission(repo, mission_slug, "01IMPLFRESH00000000000001")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code == 0, result.output
    assert not (repo / ".worktrees").exists() or not any((repo / ".worktrees").iterdir())
    events = [e for e in read_events(feature_dir) if e.wp_id == "WP01"]
    assert events[-1].execution_mode == "direct_repo"


# ---------------------------------------------------------------------------
# Refusal 2: wrong branch
# ---------------------------------------------------------------------------


def test_wrong_branch_refuses(repo: Path) -> None:
    """End-to-end control: the CLI surfaces the remedy text (NFR-004).

    This alone cannot prove THIS refusal fired rather than some other
    upstream check (review cycle-1 issue 3) -- ``error_code`` is asserted
    directly, in isolation, by
    ``test_wrong_branch_refusal_is_isolated_and_carries_error_code_and_remedy``
    below, since ``implement.py``'s broad ``except Exception`` loses the
    structured exception's ``error_code`` before it reaches this JSON
    envelope.
    """
    mission_slug = "impl-wrong-branch"
    _build_mission(repo, mission_slug, "01IMPLWRONGBRANCH00000001")
    _git(repo, "checkout", "-q", "-b", "not-trunk")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code != 0
    assert "not-trunk" in result.output and "trunk" in result.output
    assert "Check out 'trunk'" in result.output


def test_wrong_branch_refusal_is_isolated_and_carries_error_code_and_remedy(repo: Path) -> None:
    """Unit-isolated (review cycle-1 issue 3): calls the refusal function
    DIRECTLY -- nothing upstream (workspace resolution, dependency gating,
    ``_ensure_vcs_in_meta``) can fire first or shadow this one -- and asserts
    the stable ``error_code`` a caller is meant to branch on (NFR-007),
    never a substring of the rendered message.

    Mutation-checked: commenting out the wrong-branch ``if`` in
    ``_ensure_repo_root_checkout_available`` makes this test fail (no
    exception raised); restoring it makes this test pass again.
    """
    mission_slug = "impl-wrong-branch-iso"
    _build_mission(repo, mission_slug, "01IMPLWRONGBRANCHISO001")
    _git(repo, "checkout", "-q", "-b", "not-trunk-iso")
    ws = _resolved_workspace(repo, mission_slug, "WP01", "trunk")

    with pytest.raises(WriteCheckoutWrongBranchError) as excinfo:
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)

    assert excinfo.value.error_code == "WRITE_CHECKOUT_WRONG_BRANCH"
    assert "Check out 'trunk'" in str(excinfo.value)


def test_planning_wp_of_single_branch_mission_refuses_wrong_branch(repo: Path) -> None:
    """A planning_artifact WP of a single_branch mission resolves
    ``branch_name=None`` (no expectation in the workspace contract), so the
    refusal skipped the wrong-branch check and the WP could be claimed with the
    checkout on the wrong branch -- recording the claim base on that HEAD.
    The expected branch now comes from the single write-ref rule regardless
    of WP kind."""
    from specify_cli.workspace.context import resolve_workspace_for_wp

    mission_slug = "impl-plan-wrong-branch"
    _build_mission(repo, mission_slug, "01IMPLPLANWRONGBRANCH001", wp_kind="planning_artifact")
    _git(repo, "checkout", "-q", "-b", "not-trunk-plan")

    ws = resolve_workspace_for_wp(repo, mission_slug, "WP01")

    assert ws.branch_name is None, "precondition: the planning arm carries no branch expectation"
    with pytest.raises(WriteCheckoutWrongBranchError) as excinfo:
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)
    assert excinfo.value.error_code == "WRITE_CHECKOUT_WRONG_BRANCH"
    assert "'trunk'" in str(excinfo.value)


def test_planning_wp_of_protected_single_branch_mission_expects_mission_branch(repo: Path) -> None:
    """The planning WP's expected branch follows meta.mission_branch (the mint) too."""
    import json

    from specify_cli.workspace.context import resolve_workspace_for_wp

    mission_slug = "impl-plan-protected"
    feature_dir = _build_mission(repo, mission_slug, "01IMPLPLANPROTECTED0001", wp_kind="planning_artifact")
    minted = "kitty/mission-impl-plan-protected-01IMPLPL"
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_branch"] = minted
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    ws = resolve_workspace_for_wp(repo, mission_slug, "WP01")

    with pytest.raises(WriteCheckoutWrongBranchError) as excinfo:
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)  # checkout is on trunk

    assert f"'{minted}'" in str(excinfo.value)


def test_planning_wp_of_lanes_mission_keeps_no_branch_expectation(repo: Path) -> None:
    """Control: outside single_branch a planning WP's repo root is the ordinary
    shared planning root -- no branch expectation (``branch_name is None``)."""
    from specify_cli.workspace.context import resolve_workspace_for_wp

    mission_slug = "impl-plan-lanes-control"
    _build_mission(repo, mission_slug, "01IMPLPLANLANESCTRL0001", topology="lanes", wp_kind="planning_artifact")

    assert resolve_workspace_for_wp(repo, mission_slug, "WP01").branch_name is None


# ---------------------------------------------------------------------------
# Refusal 3: occupied (US2.7: two missions sharing a checkout)
# ---------------------------------------------------------------------------


def test_another_mission_in_progress_refuses(repo: Path) -> None:
    other_slug = "impl-occupant"
    _build_mission(repo, other_slug, "01IMPLOCCUPANT0000000001")
    _seed_canonical_wp_state(repo, other_slug, "WP01", "in_progress", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:45:00Z")
    mission_slug = "impl-claimant"
    _build_mission(repo, mission_slug, "01IMPLCLAIMANT000000001")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code != 0
    assert other_slug in result.output and "WP01" in result.output
    assert "Move WP01 out of in_progress" in result.output


def test_occupied_refusal_is_isolated_and_carries_error_code_and_remedy(repo: Path) -> None:
    """Unit-isolated (review cycle-1 issue 3): a THIRD mission sits in the
    same write checkout with WP01 ``in_progress``; calling the refusal
    function directly for a distinct claimant WP proves this is the check
    that fires -- no branch mismatch, no dirty tree.

    Mutation-checked: commenting out the occupancy check makes this test
    fail; restoring it makes it pass again.
    """
    other_slug = "impl-occupant-iso"
    _build_mission(repo, other_slug, "01IMPLOCCUPANTISO000001")
    _seed_canonical_wp_state(repo, other_slug, "WP01", "in_progress", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:45:00Z")
    mission_slug = "impl-claimant-iso"
    _build_mission(repo, mission_slug, "01IMPLCLAIMANTISO00001")
    ws = _resolved_workspace(repo, mission_slug, "WP01", "trunk")

    with pytest.raises(WriteCheckoutOccupiedError) as excinfo:
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)

    assert excinfo.value.error_code == "WRITE_CHECKOUT_OCCUPIED"
    message = str(excinfo.value)
    assert "Move WP01 out of in_progress" in message
    assert "on branch 'trunk'" in message
    assert f'spec-kitty agent tasks move-task WP01 --to blocked --mission {other_slug} --note "<reason>"' in message


def test_occupancy_scan_runs_once_per_implement_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``implement`` refuses early and again at allocation; the full-repo
    occupancy scan (every candidate mission's status log) must run ONCE per
    call, not once per refusal pass."""
    from specify_cli.lanes import checkout_occupancy

    real_scan = checkout_occupancy.in_progress_wps_in_write_checkout
    calls: list[tuple[str, str] | None] = []

    def _counting_scan(*args: Any, **kwargs: Any) -> list[tuple[str, str]]:
        calls.append(kwargs.get("exclude"))
        scanned: list[tuple[str, str]] = real_scan(*args, **kwargs)
        return scanned

    monkeypatch.setattr(checkout_occupancy, "in_progress_wps_in_write_checkout", _counting_scan)
    mission_slug = "impl-scan-once"
    _build_mission(repo, mission_slug, "01IMPLSCANONCE0000000001")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code == 0, result.output
    assert calls == [(mission_slug, "WP01")]


def test_create_lane_workspace_repeats_occupancy_scan_unless_verified(repo: Path) -> None:
    """The threaded flag is opt-in: a direct ``_ensure_repo_root_checkout_available``
    call still scans; ``occupancy_verified=True`` skips only the occupancy step
    (an occupant that appeared in the meantime is NOT re-detected, but the
    cheap wrong-branch / dirty checks still run)."""
    other_slug = "impl-occupant-verified"
    _build_mission(repo, other_slug, "01IMPLOCCUPVERIFIED00001")
    _seed_canonical_wp_state(repo, other_slug, "WP01", "in_progress", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:45:00Z")
    mission_slug = "impl-claimant-verified"
    _build_mission(repo, mission_slug, "01IMPLCLAIMVERIFIED0001")
    ws = _resolved_workspace(repo, mission_slug, "WP01", "trunk")

    with pytest.raises(WriteCheckoutOccupiedError):
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)
    assert _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws, occupancy_verified=True) is True


# ---------------------------------------------------------------------------
# Refusal 4: dirty checkout
# ---------------------------------------------------------------------------


def test_dirty_checkout_refuses(repo: Path) -> None:
    mission_slug = "impl-dirty"
    _build_mission(repo, mission_slug, "01IMPLDIRTY000000000001")
    (repo / "uncommitted.py").write_text("X = 1\n", encoding="utf-8")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code != 0
    assert "uncommitted.py" in result.output
    assert "Commit or stash them" in result.output


def test_refused_implement_leaves_no_tracked_changes_and_no_vcs_lock(repo: Path) -> None:
    """#5100 A3: a refused implement writes nothing behind (no VCS lock in meta.json).

    The mission's ``meta.json`` carries no ``vcs`` key, so ``_ensure_vcs_in_meta``
    WOULD write the lock if it ran before the dirty-checkout refusal.
    """
    mission_slug = "impl-dirty-a3"
    feature_dir = _build_mission(repo, mission_slug, "01IMPLDIRTYA3000000001")
    assert "vcs" not in json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    (repo / "uncommitted-a3.py").write_text("X = 1\n", encoding="utf-8")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code != 0
    assert "uncommitted-a3.py" in result.output
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert "vcs" not in json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))


def test_dirty_refusal_is_isolated_and_carries_error_code_and_remedy(repo: Path) -> None:
    """Unit-isolated (review cycle-1 issue 3): correct branch, no occupant --
    only the dirty-tree check can fire.

    Mutation-checked: commenting out the dirty-tree check makes this test
    fail; restoring it makes it pass again.
    """
    mission_slug = "impl-dirty-iso"
    _build_mission(repo, mission_slug, "01IMPLDIRTYISO00000001")
    (repo / "uncommitted-iso.py").write_text("X = 1\n", encoding="utf-8")
    ws = _resolved_workspace(repo, mission_slug, "WP01", "trunk")

    with pytest.raises(WriteCheckoutDirtyError) as excinfo:
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)

    assert excinfo.value.error_code == "WRITE_CHECKOUT_DIRTY"
    assert "uncommitted-iso.py" in str(excinfo.value)
    assert "Commit or stash them" in str(excinfo.value)


def test_review_lock_in_write_checkout_is_not_dirty(repo: Path) -> None:
    """``agent action review`` leaves ``.spec-kitty/review-lock.json`` untracked
    in the repository-root write checkout; the tool's own lock must not refuse
    the next claim as "dirty" (a user was told to commit or stash a lock file).
    The real operator edit beside it still refuses, so the exemption is not
    "any dirt"."""
    mission_slug = "impl-review-lock"
    _build_mission(repo, mission_slug, "01IMPLREVIEWLOCK000001")
    lock = repo / LOCK_DIR / LOCK_FILE
    lock.parent.mkdir()
    lock.write_text("{}\n", encoding="utf-8")
    ws = _resolved_workspace(repo, mission_slug, "WP01", "trunk")

    assert _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws) is True

    (repo / "uncommitted-lock.py").write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(WriteCheckoutDirtyError) as excinfo:
        _ensure_repo_root_checkout_available(repo, mission_slug, "WP01", ws)
    assert "uncommitted-lock.py" in str(excinfo.value)
    assert LOCK_DIR not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Review cycle-1 issue 1: the refusals are scoped to single_branch missions.
# ---------------------------------------------------------------------------


def test_lanes_topology_planning_wp_allows_dirty_checkout(repo: Path) -> None:
    """A lanes-topology planning_artifact WP resolves to the SAME repo-root
    ``lane-planning`` lane a single_branch WP does, but its checkout is the
    ordinary shared planning root, not a single_branch write checkout -- a
    dirty tree there is the normal planning state and must stay allowed
    (review cycle-1 issue 1's own reproduction: base 3ca95083 == exit 0 for
    a lanes mission with a dirty repo root; HEAD before this fix == exit 1
    ``WRITE_CHECKOUT_DIRTY``).

    Does not also switch HEAD off the mission's expected branch: that is a
    SEPARATE, pre-existing ``safe_commit`` destination-branch check
    (unrelated to this WP's write-checkout refusals), not something this
    fix scopes or is responsible for.
    """
    mission_slug = "impl-lanes-planning-control"
    _build_mission(repo, mission_slug, "01IMPLLANESCONTROL0001", topology="lanes", wp_kind="planning_artifact")
    (repo / "operator_scratch.txt").write_text("scratch\n", encoding="utf-8")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code == 0, result.output


def test_mission_writing_to_another_branch_does_not_occupy_the_checkout(repo: Path) -> None:
    """A finished mission on another write branch does not occupy the checkout (#5680).

    Driven through ``spec-kitty implement``; the paired controls are
    :func:`test_another_mission_in_progress_refuses` (a live occupant on the
    same branch still refuses) and the resume test below.

    Mission A wrote to ``trunk`` and left WP01 ``in_progress`` there. The
    operator then cut ``next-topic`` from that tip and created mission B on
    it. A's status copy on ``next-topic`` is not A's live status surface (A
    writes to ``trunk``), so it must not occupy the write checkout for B.
    """
    occupant = "impl-landed-elsewhere"
    _build_mission(repo, occupant, "01IMPLLANDEDELSEWHERE001")
    _seed_canonical_wp_state(repo, occupant, "WP01", "in_progress", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:45:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "status: occupant WP01 in_progress")
    _git(repo, "checkout", "-q", "-b", "next-topic")
    claimant = "impl-next-topic"
    _build_mission(repo, claimant, "01IMPLNEXTTOPIC000000001", target_branch="next-topic")
    assert _git(repo, "branch", "--show-current") == "next-topic"

    result = _run_implement(repo, claimant)

    assert result.exit_code == 0, result.output
    assert "WRITE_CHECKOUT_OCCUPIED" not in result.output


# ---------------------------------------------------------------------------
# Resume exemption: occupancy and dirty are both skipped for THIS wp
# ---------------------------------------------------------------------------


def test_resuming_the_already_in_progress_wp_is_exempt_from_occupancy_and_dirty(repo: Path) -> None:
    """Characterization (review cycle-1 nit 5): mutation-checked positively
    for M3 (removing the resume exemption fails this test), but a happy-path
    success is also the SAME outcome the CLI would give with the whole
    refusal block absent -- the isolated dirty/occupied unit tests above are
    what actually pin each individual check's absence."""
    mission_slug = "impl-resume"
    _build_mission(repo, mission_slug, "01IMPLRESUME0000000000001")
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "in_progress", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:45:00Z")
    # A prior successful claim already committed the in_progress transition;
    # what makes this a genuine RESUME is the operator's own uncommitted
    # work-in-progress on top of that, not an uncommitted status transition
    # (implement's own pre-existing "auto-commit planning artifacts" step
    # handles that separately and is out of this WP's scope).
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "status: WP01 in_progress")
    (repo / "in_progress_work.py").write_text("X = 1\n", encoding="utf-8")

    result = _run_implement(repo, mission_slug, actor="claude")

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Review cycle-1 issue 4: dependency-readiness refusal must not be shadowed
# by, or confused with, WRITE_CHECKOUT_OCCUPIED.
# ---------------------------------------------------------------------------


def test_dependency_not_ready_refuses_before_occupancy_check(repo: Path) -> None:
    """WP02 depends on WP01, which sits at ``for_review`` -- not yet
    ``approved``/``done``. ``implement WP02`` must be refused on dependency
    READINESS (``_ensure_wp_claim_preconditions`` -- T012/Contract 3 runs
    BEFORE any workspace allocation), never ``WRITE_CHECKOUT_OCCUPIED`` --
    WP01 sitting in the SAME repo-root checkout as an unresolved-but-not-
    in_progress WP must not masquerade as "occupied"."""
    mission_slug = "impl-dep-not-ready"
    mission_id = "01IMPLDEPNOTREADY000001"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug, mission_id)
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    _write_code_wp(feature_dir, "WP01")
    _write_code_wp(feature_dir, "WP02", dependencies=["WP01"])
    write_lanes_json(feature_dir, _repo_root_manifest_multi(mission_slug, mission_id, ("WP01", "WP02")))
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "for_review", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")
    _seed_canonical_wp_state(repo, mission_slug, "WP02", "planned", actor="system", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"planning: seed {mission_slug}")

    result = _run_implement(repo, mission_slug, wp_id="WP02")

    assert result.exit_code != 0
    assert "dependencies_not_satisfied" in result.output
    assert "WP01" in result.output
    assert "WRITE_CHECKOUT_OCCUPIED" not in result.output
    assert "already in_progress in the shared write checkout" not in result.output


# ---------------------------------------------------------------------------
# Review cycle-1 issue 4: implementing a repo-root-lane WP creates no merge
# commit -- pins the worktree_allocator.py skip hunk.
# ---------------------------------------------------------------------------


def test_implement_creates_no_merge_commit_for_a_repo_root_lane(repo: Path) -> None:
    mission_slug = "impl-no-merge-commit"
    _build_mission(repo, mission_slug, "01IMPLNOMERGECOMMIT0001")

    result = _run_implement(repo, mission_slug)

    assert result.exit_code == 0, result.output
    merges = _git(repo, "log", "--merges", "--oneline")
    assert merges == ""
