"""WP03 / issue #2218 — create-time topology choice via ``--topology``.

``spec-kitty specify <name> --topology <value>`` lets the operator pick the
mission shape at creation. The flag accepts EXACTLY the four canonical
:class:`mission_runtime.MissionTopology` values
(``single_branch | lanes | coord | lanes_with_coord``) and rejects anything
else (notably NOT ``flat``). Coordination-branch minting is conditional:

* ``coord`` / ``lanes_with_coord`` mint the per-mission coordination branch and
  write ``coordination_branch`` into ``meta.json`` (today's behaviour);
* ``single_branch`` / ``lanes`` skip the mint and NEVER write
  ``coordination_branch``.

The operator's explicit enum choice is persisted verbatim into ``meta.json``'s
``topology`` field — it is NOT re-derived from ``classify_topology`` (which
cannot reproduce the ``lanes`` choice pre-``finalize-tasks`` because no
``lanes.json`` exists yet).

Test layers
-----------

* **T007** — red-first through the pre-existing ``spec-kitty specify --json``
  surface: ``--topology single_branch`` yields ``topology: single_branch`` and
  NO ``coordination_branch``; an invalid value is rejected (exit 2).
* **T008** — corroboration + the conditional-mint pure helper.
* **T009** — the mandatory end-to-end non-coord proof: a ``single_branch``
  mission with TWO dependency-free WPs, claimed back-to-back under
  ``auto_commit=False`` (exercising WP02's vcs-lock fix — without it the second
  claim ``Exit(1)``s), then a REAL merge, asserting four observable post-merge
  facts.
* **T010** — regression: omitting ``--topology`` is the byte-identical coord
  default (meta + minted coordination branch).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import Result

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Project / git fixtures (realistic on-disk repo — no resolver patching)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], repo)


def _init_project(tmp_path: Path) -> Path:
    """Initialise a real Spec Kitty project: git repo on ``main`` with the
    ``.kittify/config.yaml`` and ``kitty-specs/`` markers ``specify`` requires."""
    repo = tmp_path / "project"
    repo.mkdir(parents=True)
    _run(["git", "init", "-qb", "main", str(repo)], repo)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    kittify = repo / ".kittify"
    kittify.mkdir()
    # ``protection.protected_branches: []`` keeps the throwaway fixture's ``main``
    # unprotected so the T009 legacy-no-coord done-bookkeeping (which resolves its
    # destination from the checked-out HEAD) can persist locally. T009 proves
    # topology survival through implement+merge, NOT protected-branch policy; the
    # generic legacy-no-coord done-marking is already covered by the merge suite.
    # WP04 fail-closed (C-A1): create_mission_core (invoked via `specify`) requires
    # a non-empty activated mission-type set; this fixture's missions are all
    # created with the default software-dev type.
    (kittify / "config.yaml").write_text(
        "project_slug: topology-fixture\n"
        "protection:\n  protected_branches: []\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    (repo / "kitty-specs").mkdir()
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "chore: bootstrap spec-kitty project")
    return repo


def _read_meta(feature_dir: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return data


def _only_feature_dir(repo: Path) -> Path:
    specs = repo / "kitty-specs"
    dirs = [p for p in specs.iterdir() if p.is_dir()]
    assert len(dirs) == 1, f"expected exactly one mission dir, found {dirs!r}"
    return dirs[0]


@contextmanager
def _in_project(repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run with cwd inside *repo* so ``locate_project_root`` / ``assert_initialized``
    resolve to it; suppress the deprecation-prompt env gate noise."""
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION", "1")
    yield


def _invoke_specify(args: list[str]) -> Result:
    """Invoke the REAL ``spec-kitty specify`` surface via the main Typer app.

    Returns the Click result (``.exit_code``, ``.output``, ``.exception``).
    """
    from typer.testing import CliRunner

    from specify_cli import app as main_app

    return CliRunner().invoke(main_app, ["specify", *args])


# ---------------------------------------------------------------------------
# T007 — RED-first through ``spec-kitty specify --json``
# ---------------------------------------------------------------------------


def test_specify_topology_single_branch_writes_no_coordination_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--topology single_branch`` persists ``topology=single_branch`` and writes
    NO ``coordination_branch`` key into ``meta.json``.

    RED against pre-WP03 code: ``--topology`` is an unknown option → exit 2.
    """
    repo = _init_project(tmp_path)
    with _in_project(repo, monkeypatch):
        result = _invoke_specify(["single-branch-demo", "--topology", "single_branch", "--json"])

    assert result.exit_code == 0, (
        f"specify --topology single_branch failed (exit {result.exit_code}):\n"
        f"{result.output}\n{getattr(result, 'exception', None)!r}"
    )
    feature_dir = _only_feature_dir(repo)
    meta = _read_meta(feature_dir)
    assert meta["topology"] == "single_branch"
    assert "coordination_branch" not in meta, (
        "single_branch must NOT write a coordination_branch key (#2218)"
    )


def test_specify_topology_rejects_non_enum_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-enum value (``flat``) is rejected by enum validation (exit 2), and no
    mission directory is created."""
    repo = _init_project(tmp_path)
    with _in_project(repo, monkeypatch):
        result = _invoke_specify(["flat-rejected-demo", "--topology", "flat", "--json"])

    assert result.exit_code == 2, (
        f"non-enum --topology flat must be rejected with exit 2, got {result.exit_code}:\n{result.output}"
    )
    assert not [p for p in (repo / "kitty-specs").iterdir() if p.is_dir()], (
        "a rejected --topology value must not create a mission directory"
    )


# ---------------------------------------------------------------------------
# T008 — conditional-mint helper + explicit-choice persistence (lanes case)
# ---------------------------------------------------------------------------


def test_topology_mints_coordination_branch_truth_table() -> None:
    """The pure decision helper mints for the coordination-bearing cells only.

    Reused directly by ``create_mission_core``; testing it here pins the
    mint-or-skip contract independently of the create path (complexity ≤ 15
    DoD — the decision is an extracted pure helper)."""
    from mission_runtime import MissionTopology

    from specify_cli.missions._create import topology_mints_coordination_branch

    assert topology_mints_coordination_branch(MissionTopology.COORD) is True
    assert topology_mints_coordination_branch(MissionTopology.LANES_WITH_COORD) is True
    assert topology_mints_coordination_branch(MissionTopology.SINGLE_BRANCH) is False
    assert topology_mints_coordination_branch(MissionTopology.LANES) is False


def test_specify_topology_lanes_persists_choice_without_coord_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--topology lanes`` is STORED verbatim (``topology=lanes``) with NO
    coordination branch.

    This is the case ``classify_topology`` cannot reproduce at create time (no
    ``lanes.json`` exists pre-finalize → it would derive ``single_branch``), so
    a green result proves the explicit operator choice is persisted, not
    re-derived from the classifier (#2218)."""
    repo = _init_project(tmp_path)
    with _in_project(repo, monkeypatch):
        result = _invoke_specify(["lanes-choice-demo", "--topology", "lanes", "--json"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    meta = _read_meta(_only_feature_dir(repo))
    assert meta["topology"] == "lanes", (
        "the explicit 'lanes' choice must be persisted, not re-derived to 'single_branch'"
    )
    assert "coordination_branch" not in meta


# ---------------------------------------------------------------------------
# T010 — regression: omitted flag is the byte-identical coord default
# ---------------------------------------------------------------------------


def test_specify_omitted_topology_defaults_to_coord_and_mints_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Omitting ``--topology`` reproduces today's behaviour exactly: the mission
    is ``topology=coord`` and a coordination branch is minted and recorded
    (NFR-001 backward-compat)."""
    repo = _init_project(tmp_path)
    with _in_project(repo, monkeypatch):
        result = _invoke_specify(["coord-default-demo", "--json"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    feature_dir = _only_feature_dir(repo)
    meta = _read_meta(feature_dir)
    assert meta["topology"] == "coord"
    coord_branch = meta.get("coordination_branch")
    assert isinstance(coord_branch, str) and coord_branch.startswith("kitty/mission-"), (
        f"omitted --topology must mint a coordination branch (got {coord_branch!r})"
    )
    # The minted branch must actually exist as a real git ref.
    refs = _git(feature_dir.parents[1], "branch", "--list", coord_branch).stdout
    assert coord_branch in refs, f"minted coordination branch {coord_branch!r} is not a real ref"


def _add_origin_on_main(repo: Path, tmp_path: Path) -> None:
    """Give *repo* an ``origin`` whose HEAD is ``main`` so ``resolve_primary_branch``
    resolves the primary branch from ``origin/HEAD`` independently of the branch
    currently checked out (Method 1 in ``core.git_ops.resolve_primary_branch``)."""
    bare = tmp_path / "origin.git"
    _run(["git", "init", "-qb", "main", "--bare", str(bare)], repo)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")


def test_specify_omitted_topology_on_non_primary_branch_derives_single_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#2581: omitting ``--topology`` on a NON-primary feature branch now derives
    ``single_branch`` (no coordination branch minted) through the shared
    context-derivation — closing the gotcha at the ``/spec-kitty.specify`` entry
    point, not just ``agent mission create``. On the primary branch (T010) the
    default stays ``coord``; here, with ``origin/HEAD -> main`` and HEAD on a
    feature branch, the derivation sees a genuine primary/non-primary mismatch."""
    repo = _init_project(tmp_path)
    _add_origin_on_main(repo, tmp_path)
    _git(repo, "checkout", "-qb", "feat/non-primary-change")
    with _in_project(repo, monkeypatch):
        result = _invoke_specify(["non-primary-demo", "--json"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    feature_dir = _only_feature_dir(repo)
    meta = _read_meta(feature_dir)
    assert meta["topology"] == "single_branch", meta
    assert "coordination_branch" not in meta, (
        f"a non-primary-branch specify without --pr-bound must NOT mint a "
        f"coordination branch (got {meta.get('coordination_branch')!r})"
    )


# ---------------------------------------------------------------------------
# T009 — mandatory end-to-end non-coord proof
#
# The single load-bearing test (FR-005). It proves the create-time
# ``single_branch`` third shape survives the coord-or-legacy fallbacks across
# the implement + merge loop, AND genuinely exercises WP02's vcs-lock fix.
#
# Structure (each load-bearing path runs for real):
#   1. REAL ``create_mission_core(topology=single_branch)`` — no coord branch.
#   2. REAL ``implement()`` for TWO dependency-free WPs back-to-back under
#      ``auto_commit=False``. The first claim's real ``_ensure_vcs_in_meta``
#      leaves a one-time vcs-lock self-write uncommitted in ``meta.json``; the
#      second claim's REAL dirty-tree guard must drop that lock-only diff and
#      pass (WP02 #2222 fix). Without WP02's fix the second claim ``Exit(1)``s
#      BEFORE allocation, so ``create_lane_workspace.call_count`` stays at 1 and
#      this test goes RED. Only the post-guard worktree allocation + status
#      emit are patched — the canonical repo-harness pattern (the real
#      ``git worktree add`` is the brittle part, not the contract under test).
#   3. REAL merge: ``_run_lane_based_consolidation`` runs real ``consolidate_lane_into_mission``
#      / ``integrate_mission_into_target`` (file content reaches target) and real
#      ``_mark_wp_merged_done`` (event log reaches done). Only side effects that
#      touch state OUTSIDE git are mocked.
#
# Four observable post-merge assertions: (a) merged file content on target,
# (b) status event log reaches done via the lane reader/reducer, (c)
# ``read_topology == single_branch`` after the full loop, (d) NO
# ``coordination_branch`` key EVER written to ``meta.json``.
# ---------------------------------------------------------------------------


def _no_coord_branch(feature_dir: Path, checkpoint: str) -> None:
    """Assert ``coordination_branch`` is absent at *checkpoint* (T009 fact d)."""
    meta = _read_meta(feature_dir)
    assert "coordination_branch" not in meta, (
        f"a coordination_branch key was written to meta.json at '{checkpoint}' — "
        f"a single_branch mission must NEVER mint or record one (#2218)."
    )


def _write_lanes(feature_dir: Path, slug: str, mission_branch: str) -> None:
    from kernel.clock import now_utc_iso

    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=slug,
            mission_branch=mission_branch,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/a/**",),
                    predicted_surfaces=("code",),
                    depends_on_lanes=(),
                    parallel_group=0,
                ),
                ExecutionLane(
                    lane_id="lane-b",
                    wp_ids=("WP02",),
                    write_scope=("src/b/**",),
                    predicted_surfaces=("code",),
                    depends_on_lanes=(),
                    parallel_group=0,
                ),
            ],
            computed_at=now_utc_iso(),
            computed_from="test-fixture",
        ),
    )


def _write_wp_file(feature_dir: Path, wp_id: str, owned_glob: str) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}-root.md").write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} dependency-free root\n"
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "agent: python-pedro\n"
        "owned_files:\n"
        f"  - {owned_glob}\n"
        f"authoritative_surface: {owned_glob.rstrip('*')}\n"
        "---\n"
        f"# {wp_id}\n",
        encoding="utf-8",
    )


def _seed_planned(feature_dir: Path, slug: str, wp_id: str) -> None:
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import TransitionRequest

    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=wp_id,
            to_lane="planned",
            actor="seed",
            force=True,
            reason="seed",
        )
    )


def _seed_wp_approved(feature_dir: Path, slug: str, wp_id: str) -> None:
    """Drive a WP from planned to approved via the REAL status-emit pipeline."""
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import ReviewResult, TransitionRequest

    _seed_planned(feature_dir, slug, wp_id)
    for to_lane in ("claimed", "in_progress", "for_review", "in_review"):
        # Post-#2160 the ``in_progress -> for_review`` gate is fail-closed and
        # requires completed subtasks or force+reason. This helper manufactures
        # a terminal ``approved`` state for an end-to-end topology test — it is
        # not exercising the subtask gate — so the gating hop is seeded with force.
        gating = to_lane == "for_review"
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=slug,
                wp_id=wp_id,
                to_lane=to_lane,
                actor="seed",
                force=gating,
                reason="seed: manufacture reviewable state" if gating else None,
            )
        )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=slug,
            wp_id=wp_id,
            to_lane="approved",
            actor="seed",
            evidence={
                "review": {
                    "reviewer": "reviewer-renata",
                    "verdict": "approved",
                    "reference": f"review-{wp_id}",
                }
            },
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="approved",
                reference=f"review-{wp_id}",
            ),
        )
    )


@contextmanager
def _claim_allocation_patched(repo: Path, feature_dir: Path) -> Iterator[MagicMock]:
    """Run REAL ``implement()`` through its REAL guards, patching only the
    post-guard worktree allocation + status emit (canonical repo-harness pattern).

    The single returned mock's ``call_count`` is the signal: a claim the
    dirty-tree guard BLOCKS aborts in the validate stage and never reaches
    allocation; a claim that PASSES reaches it. ``charter`` preflight is bypassed
    (no charter is staged in this fixture)."""
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    def _workspace(wp_id: str, lane_id: str) -> MagicMock:
        return MagicMock(
            workspace_path=repo / ".worktrees" / f"{feature_dir.name}-{lane_id}",
            branch_name=f"kitty/mission-{feature_dir.name}-{lane_id}",
            lane_id=lane_id,
            mission_branch=f"kitty/mission-{feature_dir.name}",
            is_reuse=False,
        )

    create_mock = MagicMock(
        side_effect=lambda *a, **k: _workspace(
            k.get("wp_id", a[0] if a else "WP"), "lane-a"
        )
    )
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
                return_value=CharterPreflightResult(passed=True, checks=[]),
            )
        )
        stack.enter_context(
            patch("specify_cli.cli.commands.implement.create_lane_workspace", create_mock)
        )
        stack.enter_context(
            patch(
                "specify_cli.cli.commands.implement.start_implementation_status",
                MagicMock(return_value=MagicMock(status_changed=False)),
            )
        )
        yield create_mock


@contextmanager
def _real_merge_external_mocks(repo: Path) -> Iterator[None]:
    """Mock ONLY side effects that touch state outside git. The real
    ``consolidate_lane_into_mission`` / ``integrate_mission_into_target`` (file reaches target)
    and the real ``_mark_wp_merged_done`` (event log reaches done) run."""
    with ExitStack() as stack:
        for target in (
            "specify_cli.consolidation.executor.commit_merge_bookkeeping",
            "specify_cli.post_merge.stale_assertions.run_check",
            "specify_cli.consolidation.executor.run_check",
            "specify_cli.consolidation.executor.require_no_sparse_checkout",
            "specify_cli.cli.commands.consolidate._enforce_git_preflight",
            "specify_cli.consolidation.executor._classify_porcelain_lines",
            # Post-merge invariants that validate meta-baking we deliberately
            # mock away (safe_commit + mission-number bake). Orthogonal to the
            # topology-survival contract; the merge itself already ran for real.
            "specify_cli.consolidation.executor._assert_baseline_merge_commit_on_target",
            "specify_cli.consolidation.executor._assert_merged_wps_done_on_target",
            "specify_cli.consolidation.executor._refresh_primary_checkout_after_merge",
        ):
            stack.enter_context(patch(target))
        stack.enter_context(
            patch(
                "specify_cli.consolidation.executor._bake_mission_number_into_mission_branch",
                return_value=None,
            )
        )
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        stack.enter_context(
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates", return_value=gate_eval)
        )
        policy = MagicMock()
        policy.merge_gates = []
        stack.enter_context(patch("specify_cli.policy.config.load_policy_config", return_value=policy))
        # _classify_porcelain_lines patched above returns a MagicMock; pin a
        # clean ([],0) so the post-merge porcelain invariant short-circuits.
        from specify_cli.consolidation import executor as _executor

        _executor._classify_porcelain_lines.return_value = ([], 0)
        yield


def test_single_branch_mission_survives_implement_and_merge_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T009 (FR-005): a create-time ``single_branch`` mission completes the
    implement + merge loop and the four observable facts hold."""
    import typer

    from mission_runtime import MissionTopology
    from specify_cli.cli.commands.implement import implement
    from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
    from specify_cli.core.mission_creation import create_mission_core
    from specify_cli.consolidation.config import MergeStrategy
    from specify_cli.migration.backfill_topology import read_topology
    from specify_cli.status.models import Lane
    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    repo = _init_project(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION", "1")

    # 1. REAL create — single_branch, no coordination branch.
    result = create_mission_core(
        repo,
        "two-wp-single-branch",
        topology=MissionTopology.SINGLE_BRANCH,
    )
    feature_dir = result.feature_dir
    slug = feature_dir.name
    assert result.meta["topology"] == "single_branch"
    assert result.coordination_branch is None
    _no_coord_branch(feature_dir, "after create_mission_core")

    # 2. Planning artifacts: lanes.json (2 dependency-free code lanes), WP files,
    #    planned status seeds. Commit so the tree is clean before the claims.
    mission_branch = f"kitty/mission-{slug}"
    _write_lanes(feature_dir, slug, mission_branch)
    _write_wp_file(feature_dir, "WP01", "src/a/**")
    _write_wp_file(feature_dir, "WP02", "src/b/**")
    _seed_planned(feature_dir, slug, "WP01")
    _seed_planned(feature_dir, slug, "WP02")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"chore({slug}): finalize two-WP single_branch mission")

    # 3. REAL back-to-back auto_commit=False claims (exercises WP02's vcs-lock fix).
    #
    # Post-cutover a real claim leaves only meta.json's one-time vcs-lock
    # self-write (``_ensure_vcs_in_meta``); runtime claim state is event-sourced
    # and the WP file is byte-stable. That directly produces the lock-only
    # residue this regression needs to place in front of the second claim.
    meta_rel = (feature_dir / "meta.json").relative_to(repo).as_posix()
    with _claim_allocation_patched(repo, feature_dir) as create_mock:
        implement("WP01", mission=slug, auto_commit=False, recover=False)
        # The real claim must have written the vcs-lock self-write to meta.json.
        assert _read_meta(feature_dir).get("vcs") == "git", (
            "the real claim path must have written the vcs-lock self-write to meta.json"
        )
        dirty_paths = sorted(
            line[3:] for line in _git(repo, "status", "--porcelain").stdout.splitlines() if line.strip()
        )
        assert dirty_paths == [meta_rel], (
            f"precondition: the only residue facing the second claim must be the "
            f"lock-dirty meta.json, got {dirty_paths!r}"
        )
        # ...and that residue is a lock-FIELD-ONLY diff — the exact case WP02
        # governs (asserted via the production decision helper).
        from kernel.vcs_lock import is_vcs_lock_only_change

        committed_meta = json.loads(_git(repo, "show", f"HEAD:{meta_rel}").stdout)
        assert is_vcs_lock_only_change(committed_meta, _read_meta(feature_dir)), (
            "the sole residue must be a vcs-lock-only meta.json diff (WP02 scope)"
        )
        # The SECOND claim's REAL dirty-tree guard must drop the lock-only meta and
        # pass. Without WP02's fix it Exit(1)s here (count stays 1).
        try:
            implement("WP02", mission=slug, auto_commit=False, recover=False)
        except typer.Exit as exc:  # pragma: no cover - only on a real regression
            raise AssertionError(
                f"the second auto_commit=False claim aborted (exit {exc.exit_code}); "
                f"it was blocked by the first claim's uncommitted vcs-lock self-write "
                f"(#2222 / WP02 regression)."
            ) from exc
    assert create_mock.call_count == 2, (
        "both back-to-back auto_commit=False claims must reach workspace allocation; "
        "a count < 2 means the second claim was blocked by the first claim's "
        "uncommitted vcs-lock self-write (WP02 #2222 regression)."
    )
    _no_coord_branch(feature_dir, "after two implement claims")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"chore({slug}): commit vcs-lock residue")

    # 4. Build real lane branches with code content; drive WPs to approved; merge.
    _git(repo, "branch", mission_branch, "main")
    for lane_id, wp_id, relpath, body in (
        ("lane-a", "WP01", "src/a/foo.py", "def foo():\n    return 'WP01-single-branch'\n"),
        ("lane-b", "WP02", "src/b/bar.py", "def bar():\n    return 'WP02-single-branch'\n"),
    ):
        lane_branch = f"{mission_branch}-{lane_id}"
        _git(repo, "branch", lane_branch, "main")
        _git(repo, "checkout", lane_branch)
        target = repo / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        _git(repo, "add", relpath)
        _git(repo, "commit", "-m", f"feat({slug}): {wp_id} adds {relpath}")
    _git(repo, "checkout", "main")

    for wp_id in ("WP01", "WP02"):
        _seed_wp_approved(feature_dir, slug, wp_id)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"chore({slug}): WPs approved")

    with _real_merge_external_mocks(repo):
        _run_lane_based_consolidation(
            repo_root=repo,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    # ---- Four observable post-merge facts -------------------------------------
    # (a) the WP file CONTENT is present on the merge-target branch.
    for relpath, needle in (
        ("src/a/foo.py", "WP01-single-branch"),
        ("src/b/bar.py", "WP02-single-branch"),
    ):
        blob = _git(repo, "show", f"main:{relpath}").stdout
        assert needle in blob, (
            f"FR-005 regression (a): {relpath} content did not reach main after merge"
        )

    # (b) the status event log reaches done via the lane reader/reducer.
    snapshot = reduce(read_events(feature_dir))
    for wp_id in ("WP01", "WP02"):
        assert snapshot.work_packages[wp_id]["lane"] == Lane.DONE.value, (
            f"FR-005 regression (b): {wp_id} did not reach done in the persisted event log"
        )

    # (c) read_topology stays single_branch AFTER the full loop.
    assert read_topology(feature_dir) is MissionTopology.SINGLE_BRANCH, (
        "FR-005 regression (c): topology did not survive the implement+merge loop"
    )

    # (d) no coordination_branch key was EVER written.
    _no_coord_branch(feature_dir, "after merge")
