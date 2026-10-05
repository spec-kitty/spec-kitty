"""Characterization of ``spec-kitty implement`` through its public entry points (mission implement-degod, FR-009/FR-014).

Pins today's observable behaviour -- exit codes, console text, ``--json`` payloads, side-effect order,
and the state a refusal leaves behind -- before any source moves.  The suite drives only:

* the ``implement`` Typer command (the function ``agent action implement`` calls), mounted on a
  one-command Typer app and invoked with ``CliRunner``; see ``implement_cli`` for why not the root app;
* the ``implement`` function called the way ``agent action implement`` calls it (a plain Python call);
* real git repositories built in ``tmp_path``.

No assertion names a module-internal helper.  The few failures a real fixture cannot produce are
injected by logical name through ``patch_collaborator`` from ``_implement_dispatch.py``.

This suite was byte-frozen during the implement de-god (mission implement-degod) as a behaviour-
neutrality proof: 2,000+ lines could leave ``implement.py`` for the phase and seam modules and be
shown to change nothing observable.  That proof is spent once the de-god lands, so the freeze is
lifted and this is now a living characterization/contract suite -- a deliberate behaviour or message
change lands here red-first, as an explicit diff to the golden (for example correcting the
``Workspace allocation failed:`` framing on the pre-allocation HEAD-mismatch refusal).  When a later
work package moves a collaborator, only the ``DISPATCH`` values in ``_implement_dispatch.py`` change.

Each case records, in its docstring, the planted break that proves it red.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.models import ArgumentInfo, OptionInfo
from click.testing import Result
from typer.testing import CliRunner

from runtime.next import runtime_bridge
from specify_cli.cli.commands.agent.workflow import top_level_implement
from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from specify_cli.core.errors import PlacementResolutionRequired
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch, SafeCommitPathPolicyError
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import TransitionError, WorkPackageClaimConflict
from tests.specify_cli.cli.commands._implement_dispatch import original, patch_collaborator
from tests.utils import _seed_canonical_wp_state

TARGET = "trunk"
FIXED_TIME = "2026-10-04T00:00:00Z"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def init_repo(root: Path, branch: str = TARGET) -> Path:
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", branch)
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "config", "commit.gpgsign", "false")
    (root / ".kittify").mkdir()
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    return root


def activate_repo(root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the command at *root* and isolate it from the developer's global git config."""
    empty_config = tmp_path / "empty.gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    monkeypatch.setenv("COLUMNS", "240")
    monkeypatch.chdir(root)


@dataclass(frozen=True)
class Mission:
    """A seeded mission: where it lives and the identifiers a test asserts on."""

    repo: Path
    slug: str
    mission_id: str
    feature_dir: Path

    @property
    def meta_path(self) -> Path:
        return self.feature_dir / "meta.json"

    @property
    def events_path(self) -> Path:
        return self.feature_dir / "status.events.jsonl"

    def meta(self) -> dict[str, object]:
        loaded: dict[str, object] = json.loads(self.meta_path.read_text(encoding="utf-8"))
        return loaded

    def event_count(self) -> int:
        return len(self.events_path.read_text(encoding="utf-8").splitlines()) if self.events_path.exists() else 0


def _wp_text(wp_id: str, *, kind: str, deps: list[str], body: str = "Body.") -> str:
    owned = "src/**" if kind == "code_change" else "kitty-specs/**"
    return "\n".join(
        [
            "---",
            f"work_package_id: {wp_id}",
            f"title: {wp_id} {kind}",
            f"dependencies: {deps!r}",
            f"execution_mode: {kind}",
            "owned_files:",
            f"- {owned}",
            "subtasks: []",
            "---",
            "",
            body,
            "",
            "## Activity Log",
            "",
        ]
    )


def _manifest(
    slug: str,
    mission_id: str,
    *,
    topology: str,
    wp_ids: tuple[str, ...],
    target: str,
    layout: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] | None = None,
) -> LanesManifest:
    lane_id = PLANNING_LANE_ID if topology == "single_branch" else "lane-a"
    if layout is not None:
        lanes = [
            ExecutionLane(lane_id=lid, wp_ids=ids, write_scope=("src/**",), predicted_surfaces=("core",), depends_on_lanes=deps, parallel_group=index)
            for index, (lid, ids, deps) in enumerate(layout)
        ]
        return LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=mission_id,
            mission_branch=f"kitty/mission-{slug}",
            target_branch=target,
            lanes=lanes,
            computed_at=FIXED_TIME,
            computed_from="characterization",
        )
    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch="" if topology == "single_branch" else f"kitty/mission-{slug}",
        target_branch=target,
        lanes=[
            ExecutionLane(
                lane_id=lane_id,
                wp_ids=wp_ids,
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=FIXED_TIME,
        computed_from="characterization",
    )


def build_mission(
    repo: Path,
    slug: str,
    mission_id: str,
    *,
    topology: str = "lanes",
    wps: dict[str, tuple[str, list[str]]] | None = None,
    states: dict[str, str] | None = None,
    target: str = TARGET,
    write_lanes: bool = True,
    lane_wps: tuple[str, ...] | None = None,
    layout: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] | None = None,
    meta_extra: dict[str, object] | None = None,
    spec_text: str | None = None,
    commit: bool = True,
) -> Mission:
    """Seed one mission with real files and (by default) commit the seed.

    ``wps`` maps ``WP id -> (execution_mode, dependencies)``; ``states`` maps ``WP id -> lane`` for the
    canonical status log (default ``planned``; ``"genesis"`` seeds nothing).  ``topology`` is the
    ``meta.json`` topology; the lanes manifest is shaped to match.
    """
    wps = wps or {"WP01": ("code_change", [])}
    states = states or {}
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mission_slug": slug,
        "slug": slug,
        "mid8": mission_id[:8].lower(),
        "mission_type": "software-dev",
        "target_branch": target,
        "topology": topology,
        "created_at": FIXED_TIME,
        "friendly_name": slug,
    }
    meta.update(meta_extra or {})
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if spec_text is not None:
        (feature_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    for wp_id, (kind, deps) in wps.items():
        (feature_dir / "tasks" / f"{wp_id}-test.md").write_text(_wp_text(wp_id, kind=kind, deps=deps), encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n" + "".join(f"## {wp_id}\n" for wp_id in wps), encoding="utf-8")
    if write_lanes:
        write_lanes_json(feature_dir, _manifest(slug, mission_id, topology=topology, wp_ids=lane_wps or tuple(wps), target=target, layout=layout))
    for wp_id in wps:
        lane = states.get(wp_id, "planned")
        if lane != "genesis":
            _seed_canonical_wp_state(repo, slug, wp_id, lane, actor="system", assignee="Owner", shell_pid="1234", timestamp=FIXED_TIME)
    if commit:
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", f"planning: seed {slug}")
    return Mission(repo=repo, slug=slug, mission_id=mission_id, feature_dir=feature_dir)


# ---------------------------------------------------------------------------
# Test plumbing
# ---------------------------------------------------------------------------

SLUG = "demo-mission"
MISSION_ID = "01DEMOMISSION00000000000A"
OTHER_SLUG = "other-mission"
OTHER_ID = "01OTHERMISSION0000000000B"
LANE_BRANCH = "kitty/mission-demo-mission-lane-a"
LANE_WORKTREE = ".worktrees/demo-mission-lane-a"
ARGS = ["WP01", "--mission", SLUG, "--actor", "tester"]
#: Far-future stamp so a seeded transition sorts after the real-clock claim events.
LATE = "2099-01-01T00:00:00Z"
SOFT_COMMIT_WARNING = "Warning: Could not auto-commit lane change:"
SOFT_STATUS_WARNING = "Warning: Could not update WP status:"

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def implement_cli(*args: str) -> Result:
    """Invoke the ``implement`` Typer command (the very function ``agent action implement`` calls).

    It is mounted on a throwaway single-command app rather than the root app: the root callback
    rebuilds the global agent-skill assets on every invocation (~1.2 s), which is not behaviour of
    this command.
    """
    app = typer.Typer()
    app.command()(top_level_implement)
    return runner.invoke(app, list(args))


def flat(text: str) -> str:
    """Whitespace-normalised console text: tree/box glyphs dropped, wrapping undone."""
    return " ".join(re.sub(r"[│├└─╭╮╰╯●○]", " ", text).split())


def underlying(result: Result) -> BaseException | None:
    """The original exception behind ``implement``'s ``raise typer.Exit(1) from exc``."""
    context = getattr(result.exception, "__context__", None)
    return getattr(context, "__cause__", None)


def snapshot(mission: Mission) -> dict[str, object]:
    """Everything a refused claim must leave untouched."""
    repo = mission.repo
    worktrees = repo / ".worktrees"
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        "worktrees": sorted(p.name for p in worktrees.iterdir()) if worktrees.exists() else [],
        "meta": mission.meta_path.read_bytes(),
        "events": mission.event_count(),
        "porcelain": git(repo, "status", "--porcelain", "--untracked-files=no"),
    }


def assert_refused(result: Result, *fragments: str) -> None:
    assert result.exit_code == 1, result.output
    text = flat(result.output)
    for fragment in fragments:
        assert fragment in text, f"{fragment!r} not in: {text}"


@pytest.fixture(autouse=True)
def _reset_ambient_warning_latch() -> Iterator[None]:
    """Each case is its own command run: re-arm the once-per-process charter warning around it.

    Without this, the first case consumes the warning that ``test_implement_preflight`` later asserts.
    """
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    return root


@pytest.fixture()
def main_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose integration branch is the protected default ``main``."""
    root = init_repo(tmp_path / "repo", "main")
    activate_repo(root, monkeypatch, tmp_path)
    return root


def lanes_mission(repo: Path, **kwargs: Any) -> Mission:
    return build_mission(repo, SLUG, MISSION_ID, **kwargs)


# ---------------------------------------------------------------------------
# Family 1: argument guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [[], ["--recover"]], ids=["plain", "with-recover"])
def test_missing_mission_selector_exits_2_before_anything_else(repo: Path, extra: list[str]) -> None:
    """Planted break (proven red): change the no-selector ``Exit(2)`` to ``Exit(1)``."""
    mission = lanes_mission(repo)
    before = snapshot(mission)

    result = implement_cli("WP01", *extra)

    assert result.exit_code == 2
    assert "Error: --mission <slug> is required" in flat(result.output)
    assert snapshot(mission) == before


# ---------------------------------------------------------------------------
# Family 2: refusals in the "validate" step (exit 1, tailored text, nothing written)
# ---------------------------------------------------------------------------


def test_unfinalized_wp_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the genesis refusal in the claim preconditions (the WP then claims)."""
    mission = lanes_mission(repo, states={"WP01": "genesis"})
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(result, "WP WP01 is not finalized; run `spec-kitty agent mission finalize-tasks`")
    assert snapshot(mission) == before


def test_dependency_not_approved_is_refused_with_the_full_message(repo: Path) -> None:
    """Planted break (proven red): disable the dependency-readiness refusal (the WP then claims)."""
    mission = lanes_mission(
        repo,
        wps={"WP01": ("code_change", []), "WP02": ("code_change", ["WP01"])},
        states={"WP01": "for_review"},
    )
    before = snapshot(mission)

    result = implement_cli("WP02", "--mission", SLUG, "--actor", "tester")

    assert_refused(
        result,
        "dependencies_not_satisfied: WP02 depends on WP01; all dependencies must be approved or done before implementation can start",
    )
    assert snapshot(mission) == before


def test_protected_status_commit_target_is_refused_when_auto_commit_is_on(main_repo: Path) -> None:
    """Planted break (proven red): make the protected-branch predicate always return ``None``."""
    mission = lanes_mission(main_repo, target="main")
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Refusing to start implementation status on protected branch 'main' before mutating status files.",
        "or rerun with --no-auto-commit when you intentionally want to handle the status artifact commit manually.",
    )
    assert snapshot(mission) == before


def test_missing_lanes_manifest_is_refused(repo: Path) -> None:
    """Planted break (proven red): make the missing-manifest check never raise."""
    mission = lanes_mission(repo, write_lanes=False)
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "lanes.json is required for",
        "Run 'spec-kitty agent mission finalize-tasks' to compute execution lanes",
        "run 'spec-kitty doctor mission-state --fix --mission <slug>' to rebuild lanes.json from the event log.",
    )
    assert snapshot(mission) == before


def test_corrupt_lanes_manifest_is_refused(repo: Path) -> None:
    """Planted break (proven red): return ``None`` instead of raising on a malformed manifest."""
    mission = lanes_mission(repo)
    (mission.feature_dir / "lanes.json").write_text("{not json", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "corrupt lanes.json")
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(result, "lanes.json at", "is corrupt or malformed: Expecting property name enclosed in double quotes")
    assert snapshot(mission) == before


def test_wp_outside_the_lanes_manifest_is_refused(repo: Path) -> None:
    """Planted break (proven red): drop the 'not assigned to any lane' raise in workspace resolution."""
    mission = lanes_mission(
        repo,
        wps={"WP01": ("code_change", []), "WP02": ("code_change", [])},
        lane_wps=("WP01",),
    )
    before = snapshot(mission)

    result = implement_cli("WP02", "--mission", SLUG, "--actor", "tester")

    assert_refused(result, "WP02 resolved to execution_mode='code_change' but is not assigned to any lane in")
    assert snapshot(mission) == before


BULK_SPEC = "# Spec\nA codemod to rename across the repo: bulk edit with find-and-replace.\n"


def test_unacknowledged_bulk_edit_inference_is_refused_and_the_flag_lets_it_through(repo: Path) -> None:
    """Planted break (proven red): disable the un-acknowledged bulk-edit inference refusal."""
    mission = lanes_mission(repo, spec_text=BULK_SPEC)
    before = snapshot(mission)

    refused = implement_cli(*ARGS)

    assert_refused(
        refused,
        "Bulk Edit Inference Warning",
        "(score: 12/4):",
        "Matched: 'rename across' (3pt), 'bulk edit' (3pt), 'codemod' (3pt), 'find-and-replace' (3pt)",
        "If this IS a bulk edit, set change_mode to 'bulk_edit' in meta.json.",
        "re-run with --acknowledge-not-bulk-edit to suppress.",
    )
    assert snapshot(mission) == before

    acknowledged = implement_cli(*ARGS, "--acknowledge-not-bulk-edit")

    assert acknowledged.exit_code == 0, acknowledged.output
    assert (repo / LANE_WORKTREE).is_dir()


def test_bulk_edit_mission_without_an_occurrence_map_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the occurrence-gate failure branch."""
    mission = lanes_mission(repo, meta_extra={"change_mode": "bulk_edit"})
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Bulk Edit Gate: BLOCKED",
        "Occurrence map required for bulk_edit missions.",
        "Create or fix occurrence_map.yaml before proceeding",
    )
    assert snapshot(mission) == before


def test_uncommitted_structural_planning_change_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the structural-change refusal."""
    mission = lanes_mission(repo, spec_text="# Spec\n")
    (mission.feature_dir / "spec.md").unlink()
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Error: Uncommitted structural planning-artifact changes (deletions/renames) cannot be auto-committed to the coordination branch:",
        "D kitty-specs/demo-mission/spec.md",
        "Commit these structural changes to the coordination branch yourself (e.g. `git rm`/`git mv` + commit), then re-run the claim.",
    )
    assert snapshot(mission) == before


def test_uncommitted_topology_demotion_of_meta_json_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the demotion refusal (the demotion is then committed silently)."""
    coord = "kitty/mission-demo-mission-01demomi"
    mission = lanes_mission(repo, meta_extra={"coordination_branch": coord})
    git(repo, "branch", coord)
    flattened = mission.meta()
    flattened.pop("coordination_branch")
    mission.meta_path.write_text(json.dumps(flattened, indent=2), encoding="utf-8")
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        f"Uncommitted change to kitty-specs/demo-mission/meta.json silently demotes demo-mission off its coordination branch ('{coord}' -> absent).",
        "Restore `coordination_branch` in meta.json if this was accidental.",
    )
    assert snapshot(mission) == before


def test_claiming_from_inside_another_missions_lane_worktree_is_refused(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted break (proven red): make the checkout-identity check always return (the claim then proceeds).

    Invoked through ``implement_cli`` (``CliRunner``).  In production, a cwd under ``.worktrees/``
    is refused first by the ``require_main_repo`` location guard on the command function; the suite-wide
    ``_neutralize_worktree_detection`` conftest stub disables that guard, so this case pins the inner
    checkout-identity refusal behind it.  The location guard itself is covered by
    ``tests/agent/test_context_validation_unit.py`` (``real_worktree_detection``).
    """
    lanes_mission(repo)
    other = build_mission(repo, OTHER_SLUG, OTHER_ID)
    assert implement_cli("WP01", "--mission", OTHER_SLUG, "--actor", "tester").exit_code == 0
    foreign_worktree = repo / ".worktrees" / "other-mission-lane-a"
    assert foreign_worktree.is_dir()
    before = snapshot(other)
    monkeypatch.chdir(foreign_worktree)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Refusing a WP-execution write for demo-mission WP01: the invoking checkout does not own this mission's execution workspace.",
        "(or this mission's repository-root/primary checkout). You are most likely inside another mission's lane worktree.",
        "(or the repository root) and retry.",
    )
    assert snapshot(other) == before
    assert not (repo / LANE_WORKTREE).exists()


# ---------------------------------------------------------------------------
# Family 3: refusals in the "create" step (exit 1, "Workspace allocation failed:")
# ---------------------------------------------------------------------------


def single_branch_mission(repo: Path, **kwargs: Any) -> Mission:
    return build_mission(repo, SLUG, MISSION_ID, topology="single_branch", **kwargs)


def test_single_branch_claim_from_the_wrong_branch_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the wrong-branch check in the repository-root checkout refusal."""
    mission = single_branch_mission(repo)
    git(repo, "checkout", "-q", "-b", "not-trunk")
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Workspace allocation failed: The write checkout at",
        "is on branch 'not-trunk', but demo-mission WP01 expects 'trunk'. Check out 'trunk' in",
    )
    assert snapshot(mission) == before
    assert "vcs" not in mission.meta()


def test_single_branch_claim_with_a_dirty_checkout_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the dirty-tree check in the repository-root checkout refusal."""
    mission = single_branch_mission(repo)
    (repo / "dirty.py").write_text("X = 1\n", encoding="utf-8")
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Workspace allocation failed: The write checkout at",
        "has uncommitted changes: dirty.py. Commit or stash them before claiming demo-mission WP01.",
    )
    assert snapshot(mission) == before
    assert "vcs" not in mission.meta()


def test_single_branch_claim_while_another_mission_is_in_progress_is_refused(repo: Path) -> None:
    """Planted break (proven red): disable the occupancy check in the repository-root checkout refusal."""
    mission = single_branch_mission(repo)
    build_mission(repo, OTHER_SLUG, OTHER_ID, topology="single_branch", states={"WP01": "in_progress"})
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Workspace allocation failed: other-mission WP01 is already in_progress in the shared write checkout at",
        "on branch 'trunk'. Move WP01 out of in_progress (approve, reject, or block it) before claiming demo-mission WP01.",
        'run: spec-kitty agent tasks move-task WP01 --to blocked --mission other-mission --note "<reason>" (use --to canceled instead if the work is abandoned)',
    )
    assert snapshot(mission) == before
    assert "vcs" not in mission.meta()


def destroy_lane(repo: Path, *, record_tip: bool = True) -> str:
    """Claim, commit real work on the lane, then delete its worktree and branch; return the work SHA."""
    assert implement_cli(*ARGS).exit_code == 0
    worktree = repo / LANE_WORKTREE
    (worktree / "feature.py").write_text("value = 42\n", encoding="utf-8")
    git(worktree, "add", "feature.py")
    git(worktree, "commit", "-q", "-m", "feat: real work")
    work_sha = git(worktree, "rev-parse", "HEAD")
    if not record_tip:
        git(repo, "update-ref", "-d", f"refs/spec-kitty/lane-tip/{LANE_BRANCH}")
    git(repo, "worktree", "remove", "--force", str(worktree))
    git(repo, "branch", "-D", LANE_BRANCH)
    return work_sha


def test_destroyed_lane_with_unabsorbed_work_is_refused(repo: Path) -> None:
    """Planted break (proven red): return instead of raising ``DestroyedLaneError`` for unabsorbed lane work."""
    mission = lanes_mission(repo)
    work_sha = destroy_lane(repo)
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Workspace allocation failed: cannot allocate lane 'lane-a' for 'WP01':",
        "its branch 'kitty/mission-demo-mission-lane-a' and worktree are both gone, the WP is still non-terminal,",
        f"its recorded lane work tip '{work_sha}' is not absorbed by the target branch",
        f"restore it with `git branch {LANE_BRANCH} refs/spec-kitty/lane-tip/{LANE_BRANCH}`",
        f"or deliberately abandon it with `git update-ref -d refs/spec-kitty/lane-tip/{LANE_BRANCH}`",
    )
    assert getattr(underlying(result), "error_code", None) == "DESTROYED_LANE"
    assert snapshot(mission) == before
    assert not (repo / LANE_WORKTREE).exists()


def test_destroyed_lane_without_a_recorded_tip_is_refused(repo: Path) -> None:
    """Planted break (proven red): return instead of raising ``LaneWorkTipUnknownError`` when no tip is recorded."""
    mission = lanes_mission(repo)
    destroy_lane(repo, record_tip=False)
    before = snapshot(mission)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Workspace allocation failed: cannot allocate lane 'lane-a' for 'WP01':",
        "no trustworthy lane work tip is recorded to classify it by -- refusing rather than guessing.",
        f"inspect `git reflog {LANE_BRANCH}` or `git fsck --lost-found` for stranded commits;",
        "run `spec-kitty context cleanup` to clear its stale workspace record and retry.",
    )
    assert getattr(underlying(result), "error_code", None) == "LANE_WORK_TIP_UNKNOWN"
    assert snapshot(mission) == before


def test_dependency_lane_merge_conflict_prints_the_next_step(repo: Path) -> None:
    """Planted break (proven red): drop the ``Next step:`` print for allocator errors that carry one."""
    mission = lanes_mission(
        repo,
        wps={"WP01": ("code_change", []), "WP02": ("code_change", ["WP01"])},
        layout=(("lane-a", ("WP01",), ()), ("lane-b", ("WP02",), ("lane-a",))),
    )
    assert implement_cli(*ARGS).exit_code == 0
    lane_a = repo / LANE_WORKTREE
    (lane_a / "src").mkdir()
    (lane_a / "src" / "x.py").write_text("A\n", encoding="utf-8")
    git(lane_a, "add", "-A")
    git(lane_a, "commit", "-q", "-m", "lane a content")
    mission_branch_worktree = repo.parent / "mission-branch-checkout"
    git(repo, "worktree", "add", "-q", str(mission_branch_worktree), "kitty/mission-demo-mission")
    (mission_branch_worktree / "src").mkdir()
    (mission_branch_worktree / "src" / "x.py").write_text("B\n", encoding="utf-8")
    git(mission_branch_worktree, "add", "-A")
    git(mission_branch_worktree, "commit", "-q", "-m", "mission branch content")
    git(repo, "worktree", "remove", "--force", str(mission_branch_worktree))
    for lane in ("for_review", "approved"):
        _seed_canonical_wp_state(repo, SLUG, "WP01", lane, actor="reviewer", assignee="Owner", shell_pid="1", timestamp=LATE)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "approve WP01")
    before = snapshot(mission)

    result = implement_cli("WP02", "--mission", SLUG, "--actor", "tester")

    assert_refused(
        result,
        "Workspace allocation failed: cannot auto-merge dependency lane 'lane-a' (kitty/mission-demo-mission-lane-a) into lane 'lane-b': the merge conflicts.",
        "Next step: merge 'kitty/mission-demo-mission-lane-a' into lane 'lane-b' manually,",
        "resolve the conflicts, commit, then re-run the implement command for this WP.",
    )
    assert getattr(underlying(result), "error_code", None) == "DEPENDENCY_LANE_MERGE_CONFLICT"
    assert snapshot(mission)["events"] == before["events"]


def test_unresolvable_base_ref_fails_after_the_vcs_lock_and_the_planning_commit(repo: Path) -> None:
    """Planted break (proven red): move the VCS lock after the ``--base`` validation (``vcs`` then never lands)."""
    mission = lanes_mission(repo)
    (mission.feature_dir / "notes.md").write_text("late planning note\n", encoding="utf-8")
    head_before = git(repo, "rev-parse", "HEAD")
    events_before = mission.event_count()

    result = implement_cli(*ARGS, "--base", "nonexistent-ref")

    assert_refused(result, "Error: Base ref 'nonexistent-ref' does not resolve. Try 'git fetch' or 'git branch -a' to see available refs.")
    # Order quirk pinned as-is: the VCS lock and the planning commit both ran before the base was checked.
    assert mission.meta()["vcs"] == "git"
    assert git(repo, "rev-parse", "HEAD") != head_before
    assert git(repo, "log", "-1", "--format=%s") == "chore: planning artifacts for demo-mission"
    assert mission.event_count() == events_before
    assert not (repo / ".worktrees").exists()


# ---------------------------------------------------------------------------
# Family 4: success shapes (banner, state written, commits)
# ---------------------------------------------------------------------------


def test_lane_claim_allocates_the_worktree_and_commits_the_claim(repo: Path) -> None:
    """Planted break (proven red): skip the claim commit, or ignore the ``--actor`` value."""
    mission = lanes_mission(repo)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    text = flat(result.output)
    for expected in (
        "→ VCS locked to git in meta.json",
        "Detect feature context (Feature: demo-mission)",
        "Validate planning state (Lane: lane-a)",
        f"Resolve execution workspace (Lane lane-a: {LANE_WORKTREE})",
        "→ Mission branch: kitty/mission-demo-mission",
        f"→ Lane branch: {LANE_BRANCH}",
        "→ WP01 moved to 'doing'",
        "✓ Lane worktree ready",
        "CRITICAL: Change to the lane worktree before editing files",
        "export SPEC_KITTY_TEST_DB_NAME=test_demo_mission_lane_a",
    ):
        assert expected in text, expected
    assert (repo / LANE_WORKTREE).is_dir()
    assert git(repo, "log", "-1", "--format=%s") == "chore: WP01 claimed for implementation"
    assert mission.meta()["vcs"] == "git"
    lanes_by_wp = [json.loads(line) for line in mission.events_path.read_text(encoding="utf-8").splitlines() if '"kind"' not in line]
    assert [(e["from_lane"], e["to_lane"]) for e in lanes_by_wp if e["actor"] == "tester"] == [("planned", "claimed"), ("claimed", "in_progress")]


def test_no_auto_commit_leaves_the_claim_staged_only(repo: Path) -> None:
    """Planted break (proven red): remove the staged-only branch of the claim commit."""
    lanes_mission(repo)
    head_before = git(repo, "rev-parse", "HEAD")

    result = implement_cli(*ARGS, "--no-auto-commit")

    assert result.exit_code == 0, result.output
    assert "→ WP01 moved to 'doing' (auto-commit disabled, changes staged only)" in flat(result.output)
    assert git(repo, "rev-parse", "HEAD") == head_before


def test_single_branch_code_claim_runs_in_the_repository_root(repo: Path) -> None:
    """Planted break (proven red): disable the repository-root banner for a single_branch code WP."""
    mission = single_branch_mission(repo)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    text = flat(result.output)
    assert "✓ Repository-root workspace ready" in text
    assert "Work in the repository root checkout on branch trunk" in text
    assert "Resolve execution workspace (Lane lane-planning: .)" in text
    assert "→ Lane branch: trunk" in text
    assert not (repo / ".worktrees").exists()
    assert mission.meta()["vcs"] == "git"


def test_base_flag_on_a_repository_root_planning_wp_is_ignored_with_a_warning(repo: Path) -> None:
    """Planted break (proven red): drop the ``--base is ignored`` warning."""
    mission = single_branch_mission(repo, wps={"WP01": ("planning_artifact", [])})

    result = implement_cli(*ARGS, "--base", "nonexistent-ref")

    assert result.exit_code == 0, result.output
    text = flat(result.output)
    assert "Warning: --base is ignored for repository-root planning work" in text
    assert "→ Workspace contract: repository root planning workspace" in text
    assert "✓ Lane worktree ready" in text
    assert "Using explicit base ref" not in text
    assert mission.meta()["vcs"] == "git"


# ---------------------------------------------------------------------------
# Family 5: side-effect order, #4888, failure-injection tables (dispatch map)
# ---------------------------------------------------------------------------


def record_order(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Wrap every collaborator in a recording spy that delegates to the real one."""
    calls: list[str] = []

    def spy(logical: str) -> Callable[..., Any]:
        real = original(logical)

        def recording(*args: Any, **kwargs: Any) -> Any:
            calls.append(logical)
            return real(*args, **kwargs)

        return recording

    patch_collaborator(monkeypatch, "target_branch", spy("target_branch"))
    patch_collaborator(monkeypatch, "dependency_gate", spy("dependency_gate"))
    patch_collaborator(monkeypatch, "planning_commit", spy("planning_commit"))
    patch_collaborator(monkeypatch, "bulk_edit_gate", spy("bulk_edit_gate"))
    patch_collaborator(monkeypatch, "resolve_workspace", spy("resolve_workspace"))
    patch_collaborator(monkeypatch, "vcs_lock", spy("vcs_lock"))
    patch_collaborator(monkeypatch, "allocate", spy("allocate"))
    patch_collaborator(monkeypatch, "start_status", spy("start_status"))
    patch_collaborator(monkeypatch, "claim_commit", spy("claim_commit"))
    patch_collaborator(monkeypatch, "safe_commit", spy("safe_commit"))
    # The operational-context builder is a lazy import from a foreign module, so it is wrapped there.
    real_context = runtime_bridge.build_operational_context_for_claim

    def context_spy(*args: Any, **kwargs: Any) -> Any:
        calls.append("operational_context")
        return real_context(*args, **kwargs)

    monkeypatch.setattr(runtime_bridge, "build_operational_context_for_claim", context_spy)
    return calls


def test_side_effects_run_in_the_documented_order(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted break (proven red): move the dependency gate after the planning commit."""
    mission = lanes_mission(repo)
    (mission.feature_dir / "late.md").write_text("late planning note\n", encoding="utf-8")
    calls = record_order(monkeypatch)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    assert calls == [
        "target_branch",
        "dependency_gate",
        "planning_commit",
        "bulk_edit_gate",
        "operational_context",
        "resolve_workspace",
        "vcs_lock",
        "allocate",
        "start_status",
        "claim_commit",
        "safe_commit",
    ]


def test_status_start_failure_after_the_workspace_exists_names_the_failure_point(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted break (proven red): disable the post-workspace branch of the failure message (#4888)."""
    mission = lanes_mission(repo)

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    patch_collaborator(monkeypatch, "start_status", boom)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Error: Workspace was created but starting the WP status failed: boom.",
        "The WP status transition may have already landed on the lane branch.",
        "Run `spec-kitty agent tasks status` to check the WP's actual lane before retrying.",
    )
    assert "Workspace allocation failed" not in flat(result.output)
    assert (repo / LANE_WORKTREE).is_dir()
    assert mission.event_count() == 2  # the two seeded planning lines only: no lifecycle event was recorded


def test_status_start_failure_with_a_landed_commit_names_the_sha(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted break (proven red): ignore ``commit_sha`` on the exception."""
    lanes_mission(repo)

    class Landed(RuntimeError):
        commit_sha = "abc"

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise Landed("recovery failed")

    patch_collaborator(monkeypatch, "start_status", boom)

    result = implement_cli(*ARGS)

    assert_refused(
        result,
        "Error: Workspace was created but starting the WP status failed: recovery failed.",
        "A status commit (sha=abc) may have already landed on the lane branch.",
    )
    assert "The WP status transition may have already landed" not in flat(result.output)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (WorkPackageClaimConflict("WP01", "someone-else", "tester"), "Error: WP WP01 is already claimed for implementation by 'someone-else'"),
        (TransitionError("illegal move"), "Error: Could not start implementation status: illegal move"),
    ],
    ids=["claim-conflict", "transition-error"],
)
def test_typed_status_start_errors_are_rendered_as_errors(repo: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, expected: str) -> None:
    """Planted break (proven red): stop handling the typed status-start errors (they fall through to the generic handler)."""
    lanes_mission(repo)

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise error

    patch_collaborator(monkeypatch, "start_status", raising)

    result = implement_cli(*ARGS)

    assert_refused(result, expected)
    assert "Workspace was created but" not in flat(result.output)


def test_allocation_failure_records_no_lifecycle_event(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted break (proven red): treat the workspace as already created before allocation runs (F-50 / #4888)."""
    mission = lanes_mission(repo)
    events_before = mission.event_count()

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("alloc boom")

    patch_collaborator(monkeypatch, "allocate", boom)

    result = implement_cli(*ARGS)

    assert_refused(result, "workspace allocation failed: alloc boom", "Error: Workspace allocation failed: alloc boom")
    assert "Workspace was created but" not in flat(result.output)
    assert "Next step:" not in flat(result.output)
    assert mission.event_count() == events_before
    assert not (repo / ".worktrees").exists()


def structured_error(name: str) -> Exception:
    error: Exception
    if name == "path-policy":
        error = SafeCommitPathPolicyError(offending_path=".worktrees/x", worktree_root=Path("/wt"))
        return error
    if name == "head-mismatch":
        error = SafeCommitHeadMismatch(destination_ref="trunk", observed_head="other", worktree_root=Path("/wt"))
        return error
    return PlacementResolutionRequired("placement unresolved")


@pytest.mark.parametrize(
    ("level", "kind"),
    [
        ("claim_commit", "path-policy"),
        ("claim_commit", "head-mismatch"),
        ("claim_commit", "placement"),
        ("safe_commit", "path-policy"),
        ("safe_commit", "head-mismatch"),
    ],
)
def test_structured_commit_errors_propagate_instead_of_becoming_soft_warnings(repo: Path, monkeypatch: pytest.MonkeyPatch, level: str, kind: str) -> None:
    """Planted break (proven red): fold the structured error into the soft warning.

    Either in the inner handler (safe_commit level only) or in the outer one (both levels), or drop ``from exc``.
    """
    lanes_mission(repo)
    error = structured_error(kind)

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise error

    patch_collaborator(monkeypatch, level, raising)

    result = implement_cli(*ARGS)

    assert result.exit_code == 1, result.output
    text = flat(result.output)
    assert SOFT_COMMIT_WARNING not in text
    assert SOFT_STATUS_WARNING not in text
    assert underlying(result) is error


@pytest.mark.parametrize(
    ("level", "warning"),
    [("safe_commit", SOFT_COMMIT_WARNING), ("claim_commit", SOFT_STATUS_WARNING)],
)
def test_generic_commit_failures_are_soft_warnings(repo: Path, monkeypatch: pytest.MonkeyPatch, level: str, warning: str) -> None:
    """Planted break (proven red): re-raise a generic failure instead of warning, in the inner handler or the outer one."""
    lanes_mission(repo)

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    patch_collaborator(monkeypatch, level, boom)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    text = flat(result.output)
    assert f"{warning} boom" in text
    assert "✓ Lane worktree ready" in text


def test_structured_error_from_a_direct_call_carries_its_type_as_the_cause(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted break (proven red): drop ``from exc`` from the wrapper's ``Exit(1)``, or fold the error into the soft warning."""
    lanes_mission(repo)
    error = structured_error("placement")

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise error

    patch_collaborator(monkeypatch, "claim_commit", raising)

    with pytest.raises(typer.Exit) as excinfo:
        top_level_implement(wp_id="WP01", mission=SLUG, json_output=False, recover=False, acknowledge_not_bulk_edit=False, actor="tester")

    assert excinfo.value.exit_code == 1
    assert type(excinfo.value.__cause__) is PlacementResolutionRequired


# ---------------------------------------------------------------------------
# Family 6: --json, programmatic call, --recover
# ---------------------------------------------------------------------------


def test_json_success_payload_is_the_only_stdout_document(repo: Path) -> None:
    """Planted break (proven red): rename a payload key, or stop capturing console output in --json mode."""
    lanes_mission(repo)

    result = implement_cli(*ARGS, "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "workspace": LANE_WORKTREE,
        "workspace_path": LANE_WORKTREE,
        "branch": LANE_BRANCH,
        "mission_slug": SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "wp_id": "WP01",
        "lane_id": "lane-a",
        "execution_mode": "code_change",
        "status": "created",
        "lane_test_env": {"SPEC_KITTY_TEST_DB_NAME": "test_demo_mission_lane_a"},
    }


def test_json_error_payload_carries_the_captured_console_summary(repo: Path) -> None:
    """Planted break (proven red): omit ``wp_id`` from the error payload, or stop capturing console output in --json mode."""
    lanes_mission(repo, states={"WP01": "genesis"})

    result = implement_cli(*ARGS, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert set(payload) == {"status", "error", "wp_id"}
    assert payload["status"] == "error"
    assert payload["wp_id"] == "WP01"
    assert "WP WP01 is not finalized; run `spec-kitty agent mission finalize-tasks`" in flat(payload["error"])


def test_recover_with_nothing_to_recover_reports_it_on_both_surfaces(repo: Path) -> None:
    """Planted break (proven red): change the JSON no-action payload, or the console no-action text."""
    mission = lanes_mission(repo)
    before = snapshot(mission)

    console_result = implement_cli(*ARGS, "--recover")
    json_result = implement_cli(*ARGS, "--recover", "--json")

    assert console_result.exit_code == 0
    assert "No crashed implementation sessions found." in flat(console_result.output)
    assert json_result.exit_code == 0
    assert json.loads(json_result.stdout) == {
        "status": "ok",
        "message": "No crashed implementation sessions found.",
        "recovered_wps": [],
        "worktrees_recreated": 0,
        "transitions_emitted": 0,
        "errors": [],
    }
    assert snapshot(mission) == before


def test_function_signature_is_the_programmatic_call_contract() -> None:
    """Planted break (proven red): replace the ``recover`` option default with a plain ``False``."""
    signature = inspect.signature(top_level_implement)
    parameters = signature.parameters

    assert list(parameters) == ["wp_id", "mission", "auto_commit", "json_output", "recover", "base", "acknowledge_not_bulk_edit", "actor"]
    assert isinstance(parameters["wp_id"].default, ArgumentInfo)
    assert parameters["mission"].default is None
    assert parameters["auto_commit"].default is None
    assert isinstance(parameters["json_output"].default, OptionInfo)
    assert isinstance(parameters["recover"].default, OptionInfo)
    assert parameters["base"].default is None
    assert parameters["acknowledge_not_bulk_edit"].default is False
    assert parameters["actor"].default is None
    assert hasattr(top_level_implement, "__wrapped__")
    assert inspect.unwrap(top_level_implement) is not top_level_implement


def test_programmatic_call_as_the_agent_action_makes_it_claims_the_wp(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Planted break (proven red): ignore ``actor`` (the claim records ``implement-command``)."""
    mission = lanes_mission(repo)

    returned = top_level_implement(wp_id="WP01", mission=SLUG, json_output=False, recover=False, acknowledge_not_bulk_edit=False, actor="tester")

    assert returned is None
    assert (repo / LANE_WORKTREE).is_dir()
    assert "✓ Lane worktree ready" in flat(capsys.readouterr().out)
    claimed = [json.loads(line) for line in mission.events_path.read_text(encoding="utf-8").splitlines() if '"to_lane"' in line]
    assert claimed[-1]["to_lane"] == "in_progress"
    assert claimed[-1]["actor"] == "tester"


def test_programmatic_call_that_leaves_the_option_defaults_enters_recovery_mode(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Planted break (proven red): coerce ``recover`` with ``is True`` (the #571 hazard disappears and the claim runs)."""
    mission = lanes_mission(repo)
    before = snapshot(mission)

    top_level_implement(wp_id="WP01", mission=SLUG, actor="tester")

    assert "No crashed implementation sessions found." in flat(capsys.readouterr().out)
    assert snapshot(mission) == before
