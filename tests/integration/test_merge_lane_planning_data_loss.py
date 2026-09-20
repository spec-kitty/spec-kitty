"""WP01/T001 — pin the lane-planning data-loss regression (FR-001).

This file holds two layers of regression pins:

1. ``TestMergeIncludesPlanningLane`` — the **bookkeeping** assertion: every WP
   from every lane (planning + code) must appear in ``MergeState.wp_order``
   and reach the per-WP ``_mark_wp_merged_done`` pass. This layer mocks out
   ``consolidate_lane_into_mission`` / ``integrate_mission_into_target`` so the merge plan
   can be inspected without a real on-disk merge.

2. ``TestPlanningArtifactReachesTarget`` — the **load-bearing** assertion:
   the planning-artifact file MUST be present on the target branch (``main``)
   after ``_run_lane_based_merge`` returns. This layer drives the **real**
   ``consolidate_lane_into_mission`` / ``integrate_mission_into_target`` / ``_merge_branch_into``
   functions against a real on-disk git repository. It mocks ONLY the side
   effects that touch state outside git (status emit, dossier sync, SaaS
   emit, stale-assertion check, sparse-checkout preflight, merge gates,
   post-merge invariants) — the merge itself runs through real ``git merge``.

   The negative case in the same class proves the documented design boundary
   from research.md D4: planning artifacts that live on a phantom
   ``kitty/mission-<slug>-lane-planning`` branch (instead of on the
   ``planning_base_branch`` as the design requires) do **not** reach the
   target branch.  This is by design — ``lane_branch_name("lane-planning",
   planning_base_branch="main")`` returns ``"main"``, so the merge never
   visits a separate planning lane branch.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy


pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@test.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test"])
    _run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"])
    (repo / "README.md").write_text("init\n")
    _run(["git", "-C", str(repo), "add", "."])
    _run(["git", "-C", str(repo), "commit", "-m", "init"])


def _make_manifest_with_planning_and_code(slug: str) -> MagicMock:
    """Build a fake LanesManifest with three code WPs and one planning-artifact WP."""
    manifest = MagicMock()
    manifest.target_branch = "main"
    manifest.mission_branch = f"kitty/mission-{slug}"

    lane_a = MagicMock()
    lane_a.lane_id = "lane-a"
    lane_a.wp_ids = ["WP01", "WP02", "WP03"]

    lane_planning = MagicMock()
    lane_planning.lane_id = "lane-planning"
    lane_planning.wp_ids = ["WP04"]

    manifest.lanes = [lane_a, lane_planning]
    return manifest


def _seed_wp_done_raw(feature_dir: Path, mission_slug: str, wp_ids: list[str]) -> None:
    """Seed every ``wp_ids`` entry as ``done`` directly on the event log (#4764/T007).

    ``_assert_mission_terminal_ready`` reads ``status.events.jsonl``/``reduce``
    directly, so a mission with no real event log now refuses before any
    mutation. This bookkeeping-layer test mocks the merge internals wholesale
    and never writes WP prompt files, so the lighter raw-event seed (rather
    than the real emit-pipeline walk ``_seed_wp_approved`` performs) is
    sufficient and keeps this layer's fast-feedback intent.
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = feature_dir / "status.events.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as handle:
        for index, wp_id in enumerate(wp_ids):
            event = {
                "actor": "test",
                "at": "2026-04-07T00:00:00+00:00",
                "event_id": f"TESTPLANWPORD{wp_id}{index:03d}",
                "evidence": None,
                "execution_mode": "direct_repo",
                "feature_slug": mission_slug,
                "force": True,
                "from_lane": "planned",
                "reason": "test seed",
                "review_ref": None,
                "to_lane": "done",
                "wp_id": wp_id,
            }
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    from specify_cli.status.reducer import materialize

    materialize(feature_dir)


# ---------------------------------------------------------------------------
# Layer 1 — bookkeeping (mocked merge functions)
# ---------------------------------------------------------------------------


class TestMergeIncludesPlanningLane:
    """FR-001 bookkeeping: planning-lane WPs MUST appear in MergeState wp_order
    and must reach the per-WP mark-done pass.

    This layer mocks ``consolidate_lane_into_mission`` and ``integrate_mission_into_target``
    so we can inspect the plan without driving real git.  It is the
    fast-feedback regression pin for the lane-iteration / WP-iteration loops.
    """

    def test_merge_state_wp_order_includes_planning_lane_wps(self, tmp_path: Path) -> None:
        slug = "test-planning-data-loss"
        _init_git_repo(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        _seed_wp_done_raw(feature_dir, slug, ["WP01", "WP02", "WP03", "WP04"])

        manifest = _make_manifest_with_planning_and_code(slug)

        captured_states: list[list[str]] = []

        def fake_save_state(state, repo_root):  # noqa: ANN001
            # Capture wp_order on every save so we can assert what was committed.
            captured_states.append(list(state.wp_order))

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        completed_wps_seen: list[str] = []

        def fake_mark_wp_merged_done(repo_root, mission_slug, wp_id, target_branch):  # noqa: ANN001
            completed_wps_seen.append(wp_id)

        def fake_run_command(cmd, *args, **kwargs):  # noqa: ANN001
            if "merge-base" in cmd:
                return (0, "abc123\n", "")
            return (0, "", "")

        patches = [
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state", side_effect=fake_save_state),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.merge.executor.require_no_sparse_checkout"),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done", side_effect=fake_mark_wp_merged_done),
            patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
            patch("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done"),
            patch("specify_cli.post_merge.stale_assertions.run_check"),
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
            patch("specify_cli.policy.config.load_policy_config"),
            patch("specify_cli.merge.executor.run_command", side_effect=fake_run_command),
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch"),
            # WP10 (#2057): branch preflight + target asserts moved to seams;
            # appended last to keep positional mock indices stable.
            patch("specify_cli.merge.executor._check_mission_branch", return_value=(True, None)),
            patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
            patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        ]
        with contextlib.ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            mock_run_check = mocks[10]
            mock_gates = mocks[11]
            mock_policy = mocks[12]

            stale_report = MagicMock()
            stale_report.findings = []
            mock_run_check.return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mock_gates.return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mock_policy.return_value = policy

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        # FR-001 assertion 1: every initial save must include all WPs from
        # both code AND planning lanes.
        assert captured_states, "save_state was never called — merge state never persisted"
        first_state = captured_states[0]
        assert set(first_state) == {"WP01", "WP02", "WP03", "WP04"}, (
            f"FR-001 regression: MergeState.wp_order does not contain every WP "
            f"from every lane. Got {first_state!r}, expected all of WP01..WP04 "
            f"(WP04 is in lane-planning and must NOT be silently dropped)."
        )

        # FR-001 assertion 2: the planning-lane WP must reach the per-WP
        # mark-done loop.
        assert "WP04" in completed_wps_seen, (
            f"FR-001 regression: WP04 (lane-planning) was not marked done. "
            f"Marked WPs: {completed_wps_seen!r}. The planning lane was either "
            "skipped in the lane iteration or its WPs were filtered out of the "
            "completion pass."
        )

        # And the code-lane WPs were all marked too.
        for wp in ("WP01", "WP02", "WP03"):
            assert wp in completed_wps_seen, f"{wp} was dropped from the merge"


# ---------------------------------------------------------------------------
# Layer 2 — real merge against real git (no mocks of consolidate_lane_into_mission /
# integrate_mission_into_target / _merge_branch_into).
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path, slug: str, *, mission_id: str | None = None) -> None:
    """Write a minimal meta.json for a mission directory.

    ``mission_id`` defaults to ``None`` (legacy shape). Passing a canonical
    ULID writes the MODERN shape, which the post-commit target-history
    assertion (``_assert_merged_wps_done_on_target``) requires — it early-returns
    on a legacy mission, so target-branch durability can only be asserted with a
    modern mission.
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "data-loss regression pin",
        "purpose_context": "real-merge planning-artifact reach-target test",
    }
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_lanes_manifest(
    feature_dir: Path,
    slug: str,
    *,
    code_wp_ids: list[str],
    planning_wp_ids: list[str],
    target_branch: str = "main",
    mission_branch: str | None = None,
) -> LanesManifest:
    """Build a real LanesManifest with a code lane and a planning lane and write it to disk."""
    if mission_branch is None:
        mission_branch = f"kitty/mission-{slug}"
    lanes: list[ExecutionLane] = []
    if code_wp_ids:
        lanes.append(
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=tuple(code_wp_ids),
                write_scope=("src/foo.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        )
    if planning_wp_ids:
        lanes.append(
            ExecutionLane(
                lane_id="lane-planning",
                wp_ids=tuple(planning_wp_ids),
                write_scope=(),
                predicted_surfaces=("planning",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        )
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=slug,  # legacy form: mission_id == mission_slug
        mission_branch=mission_branch,
        target_branch=target_branch,
        lanes=lanes,
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def _commit_file(
    repo: Path,
    *,
    branch: str,
    relpath: str,
    content: str,
    message: str,
) -> str:
    """Check out *branch*, write *relpath* with *content*, commit, return the commit SHA."""
    _git(repo, "checkout", branch)
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", message)
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return sha


def _file_on_branch(repo: Path, branch: str, relpath: str) -> bool:
    """Return True iff *relpath* exists on *branch* (via ``git ls-tree``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "--name-only", "-r", branch, "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and relpath in result.stdout.splitlines()


def _rel_paths(paths: object, repo: Path) -> set[str]:
    if paths is None:
        return set()
    return {str(Path(path).relative_to(repo)) for path in paths}  # type: ignore[arg-type]


@contextlib.contextmanager
def _real_merge_external_mocks(repo_root: Path):
    """Mock only the side effects that touch state OUTSIDE git.

    The real consolidate_lane_into_mission, integrate_mission_into_target, and
    _merge_branch_into are NOT mocked — they execute real ``git merge``.
    """
    patches = [
        # External side effects (status emit, dossier, SaaS, stale-assertion check)
        patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
        patch("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.merge.executor.run_check"),
        # Preflight / gates / policy / sparse-checkout — out of scope for
        # this data-loss regression
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        # mission_number assignment scans kitty-specs/ and rewrites meta.json on
        # the mission branch via a temp worktree — not the focus of the
        # data-loss regression.  Keep it out of the way.
        patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
        # Post-merge invariant fires on `git status --porcelain` output that
        # includes the test-only files — short-circuit it for this test.
        # The merge has already run through real git by the time this would
        # raise.
        patch("specify_cli.merge.executor._classify_porcelain_lines", return_value=([], 0)),
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[7].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[8].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[3].return_value = stale_report
        ms[4].return_value = stale_report
        yield {
            "mark_done": ms[0],
            "assert_done": ms[1],
            "safe_commit": ms[2],
        }


@contextlib.contextmanager
def _real_invariant_external_mocks(repo_root: Path):
    """Like :func:`_real_merge_external_mocks` but runs the REAL post-merge
    working-tree invariant (``_classify_porcelain_lines`` is NOT mocked) AND
    the REAL raw porcelain read.

    This is the F2 / porcelain-hole regression surface. It proves two things:

    1. The post-merge working-tree invariant tolerates the ``meta.json`` dirtied
       by planning-only mission_number assignment when it is in ``expected_paths``
       (F2) — and that this tolerance is genuinely load-bearing now that the
       invariant reads RAW porcelain (``meta.json`` sorts first inside
       ``kitty-specs/<slug>/`` and its intact ``" M ..."`` line is classifiable).
    2. An UNEXPECTED divergent tracked file that sorts FIRST is caught — the
       raw-porcelain read no longer silently drops the first line.

    ``safe_commit`` stays mocked so we can inspect the committed path set without
    driving a real commit onto the (protected) target branch.

    ``_refresh_primary_checkout_after_merge`` is mocked to a no-op so a
    deliberately-dirtied tracked file survives to the invariant.  The invariant
    now reads ``git status --porcelain`` via a RAW capture (not via
    :func:`specify_cli.core.git_ops.run_command`, whose whole-output ``.strip()``
    would remove the leading status column of the *first* porcelain line only),
    so the first dirty line — whatever sorts first — is classified correctly.
    """
    patches = [
        patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
        patch("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.merge.executor.run_check"),
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
        patch("specify_cli.merge.executor._refresh_primary_checkout_after_merge"),
        # NOTE: _classify_porcelain_lines is intentionally NOT mocked here —
        # the real post-merge working-tree invariant must run so the F2 fix
        # (meta.json in expected_paths) is exercised.
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[7].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[8].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[3].return_value = stale_report
        ms[4].return_value = stale_report
        yield {
            "mark_done": ms[0],
            "assert_done": ms[1],
            "safe_commit": ms[2],
        }


def _bootstrap_legacy_planning_only_mission(
    repo: Path, slug: str, *, baseline_merge_commit: str | None = "0" * 40
) -> Path:
    """Bootstrap a LEGACY planning-only mission (meta.json WITHOUT mission_id).

    ``mission_number`` is null (needs assignment) and, by default, a
    ``baseline_merge_commit`` is already present so ``_record_baseline_merge_commit``
    returns ``None`` (legacy mission) — the exact pre-conditions under which
    ``meta.json`` is dirtied by ``_assign_planning_only_mission_number_if_needed``
    and reaches the post-merge invariant. Returns the feature_dir.
    """
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks").mkdir(parents=True)

    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "legacy planning-only invariant pin",
        "purpose_context": "post-merge invariant must classify the dirtied meta.json",
    }
    if baseline_merge_commit is not None:
        meta["baseline_merge_commit"] = baseline_merge_commit
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    _write_lanes_manifest(
        feature_dir,
        slug,
        code_wp_ids=[],
        planning_wp_ids=["WP01"],
    )
    # #4764/T007: _assert_mission_terminal_ready now hard-refuses a mission
    # with a non-approved WP before any mutation, so every test built on this
    # shared bootstrap needs WP01 seeded approved -- otherwise the merge
    # refuses before ever reaching the post-merge invariant these tests
    # actually exercise (and a test that merely asserts `pytest.raises(typer.Exit)`
    # would start passing vacuously, for the wrong reason).
    _write_wp_file(feature_dir, "WP01")
    _seed_wp_approved(feature_dir, slug, "WP01")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({slug}): bootstrap legacy planning mission")

    planning_relpath = f"kitty-specs/{slug}/research/decision-A.md"
    _commit_file(
        repo,
        branch="main",
        relpath=planning_relpath,
        content="# Decision A\n\nPlanning artifact body.\n",
        message=f"plan({slug}): commit planning artifact on target",
    )
    return feature_dir


class TestLegacyPlanningOnlyMetaInvariant:
    """F2: a LEGACY planning-only mission (meta.json WITHOUT mission_id) that
    needs a mission_number assigned must NOT trip the real post-merge
    working-tree invariant.

    Defect: ``_assign_planning_only_mission_number_if_needed`` dirties
    ``meta.json`` and returns its path into ``mission_number_meta_path``, which
    is appended to ``files_to_commit`` but was NEVER added to ``expected_paths``.
    When ``_record_baseline_merge_commit`` returns ``None`` (legacy mission with
    a pre-existing baseline), and ``meta.json`` is classified by the real
    post-merge invariant, the dirtied ``meta.json`` becomes an offending line →
    ``typer.Exit(1)``, failing the merge.

    This is the REAL scenario: ``meta.json`` sorts FIRST in the dirty set inside
    ``kitty-specs/<slug>/`` and — because the invariant now reads RAW porcelain —
    its intact ``" M ..."`` line is genuinely classifiable. The F2 fix
    (``meta.json`` ∈ ``expected_paths``) is therefore load-bearing rather than
    synthetic: the load-bearing variant below proves that without that
    membership the invariant flags ``meta.json`` and fails the merge.
    """

    def test_legacy_planning_only_meta_json_does_not_trip_invariant(
        self, tmp_path: Path
    ) -> None:
        slug = "legacy-planning-only-meta-invariant"
        _init_git_repo(tmp_path)
        feature_dir = _bootstrap_legacy_planning_only_mission(tmp_path, slug)

        with _real_invariant_external_mocks(tmp_path) as mocks:
            # Must NOT raise typer.Exit — the real post-merge invariant runs
            # against RAW porcelain and must tolerate the dirtied meta.json
            # (the F2 fix: meta.json ∈ expected_paths).
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        # mission_number was assigned (dirtying meta.json), confirming the
        # invariant ran against a genuinely-dirty meta.json that sorts first.
        post_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert isinstance(post_meta.get("mission_number"), int), (
            "fixture precondition: mission_number must have been assigned so "
            "meta.json is dirty when the invariant runs"
        )

        # The dirtied meta.json must be in the committed path set (F2 fix:
        # it is added to both files_to_commit AND expected_paths).
        committed_paths: set[str] = set()
        for call in mocks["safe_commit"].call_args_list:
            committed_paths.update(_rel_paths(call.kwargs.get("paths"), tmp_path))
        assert f"kitty-specs/{slug}/meta.json" in committed_paths, (
            "F2 regression: planning-only mission_number meta.json was not "
            "committed after merge."
        )

    def test_meta_json_membership_is_load_bearing(self, tmp_path: Path) -> None:
        """Prove meta.json tolerance in the merge invariant is load-bearing.

        Post-WP01 (#2251) the merge dirty-tree classifier ``_classify_porcelain_lines``
        converged onto a single self-bookkeeping authority, which independently
        recognizes ``meta.json``. meta.json is therefore now tolerated by TWO
        mechanisms: the F2 ``expected_paths`` membership AND that unified
        self-bookkeeping check (the F2 membership is now redundant belt-and-suspenders).

        lifecycle-gate-execution-context-01KY72GQ WP11 (IC-07a): the retired
        ``mission_runtime.is_self_bookkeeping_path`` authority this test patched is
        folded onto the canonical churn owner's self-bookkeeping leg
        (:func:`specify_cli.coordination.coherence.is_self_bookkeeping_churn`),
        which ``_classify_porcelain_lines`` now imports function-locally each call —
        so patching the attribute on ``coordination.coherence`` (the module the
        fresh import resolves against) is the equivalent seam (T062).

        To prove the invariant genuinely exercises meta.json — and would flag it absent
        ALL tolerance — this strips BOTH: it drops the F2 membership from
        ``expected_paths`` AND neutralizes the self-bookkeeping recognition for this
        meta.json only. With both stripped, the real invariant (reading RAW porcelain)
        flags the dirtied ``meta.json`` first line and fails the merge with ``typer.Exit``,
        confirming its intact ``" M ..."`` line reaches classification and is caught.
        """
        # WP10 (#2057): the post-merge porcelain invariant runs in the executor
        # seam, reading _classify_porcelain_lines from its own module binding.
        import specify_cli.coordination.coherence as coherence_mod
        import specify_cli.merge.executor as merge_mod

        slug = "legacy-planning-only-meta-loadbearing"
        _init_git_repo(tmp_path)
        feature_dir = _bootstrap_legacy_planning_only_mission(tmp_path, slug)
        meta_rel = f"kitty-specs/{slug}/meta.json"

        real_classify = merge_mod._classify_porcelain_lines
        real_is_self_bookkeeping_churn = coherence_mod.is_self_bookkeeping_churn
        classified_lines: list[str] = []

        def classify_without_meta_membership(
            lines: list[str], expected_paths: set[str], **kwargs: object
        ) -> tuple[list[str], int]:
            # Drop the F2 membership to recreate the pre-fix expected_paths.
            # Forward any keyword-only args (e.g. ``residue_predicate``) intact so
            # this spy stays signature-agnostic to the production classifier.
            classified_lines.extend(lines)
            return real_classify(lines, expected_paths - {meta_rel}, **kwargs)

        def is_self_bookkeeping_churn_without_meta(path: object) -> bool:
            # WP01 (#2251) folded is_self_bookkeeping_path into the classifier
            # (WP11 further folded it onto the canonical owner); neutralize it for
            # THIS meta.json only so the tolerance is fully stripped and the
            # invariant must fall back to catching the dirtied meta.json (the
            # load-bearing behavior this test proves).
            if str(path).endswith("meta.json"):
                return False
            return real_is_self_bookkeeping_churn(path)

        with (
            _real_invariant_external_mocks(tmp_path),
            patch.object(
                merge_mod,
                "_classify_porcelain_lines",
                side_effect=classify_without_meta_membership,
            ),
            patch.object(
                coherence_mod,
                "is_self_bookkeeping_churn",
                side_effect=is_self_bookkeeping_churn_without_meta,
            ),
            pytest.raises(typer.Exit),
        ):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        # The dirtied meta.json was genuinely the file that tripped the
        # invariant (its intact " M " line reached classification). The final
        # bookkeeping rollback restores the uncommitted mission_number after
        # this artificial failure, so the persisted meta returns to null.
        assert f" M {meta_rel}" in classified_lines
        post_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert post_meta.get("mission_number") is None


class TestPostMergePorcelainHole:
    """Porcelain-hole regression: an UNEXPECTED divergent tracked file that
    sorts FIRST must be CAUGHT by the post-merge working-tree invariant.

    Pre-fix the invariant read porcelain via ``run_command`` whose whole-output
    ``.strip()`` removed the leading status column of the FIRST line, so the
    first divergent path was silently dropped by ``_classify_porcelain_lines``
    (``len(line) < 4 or line[2] != " "``) and the invariant did NOT raise.

    This test drives the REAL invariant with REAL porcelain — neither the
    porcelain read nor ``_classify_porcelain_lines`` is mocked. After the
    raw-read fix the first line survives intact and the invariant raises
    ``typer.Exit``.
    """

    def test_unexpected_first_sorting_tracked_file_is_caught(
        self, tmp_path: Path
    ) -> None:
        slug = "post-merge-porcelain-hole"
        _init_git_repo(tmp_path)
        _bootstrap_legacy_planning_only_mission(tmp_path, slug)

        # An UNEXPECTED tracked file that sorts FIRST inside kitty-specs/<slug>/
        # ("aaa-..." < "meta.json"). It is committed (tracked) and then dirtied
        # so it diverges from HEAD. It is NOT in expected_paths, so the invariant
        # MUST flag it — but ONLY if its first porcelain line is read intact.
        unexpected_rel = f"kitty-specs/{slug}/aaa-unexpected.md"
        _commit_file(
            tmp_path,
            branch="main",
            relpath=unexpected_rel,
            content="unexpected v1\n",
            message=f"chore({slug}): add unexpected tracked file",
        )
        (tmp_path / unexpected_rel).write_text("unexpected v2\n", encoding="utf-8")

        with _real_invariant_external_mocks(tmp_path), pytest.raises(typer.Exit):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        # Sanity: the unexpected file is genuinely dirty (it diverges from HEAD),
        # proving the invariant raised because it classified this first line.
        status = subprocess.run(
            ["git", "-C", str(tmp_path), "status", "--porcelain", "--", unexpected_rel],
            capture_output=True,
            text=True,
            check=False,
        )
        assert unexpected_rel in status.stdout


def _write_wp_file(feature_dir: Path, wp_id: str, *, agent: str = "researcher-ryan") -> None:
    """Write a minimal WP prompt file with an ``agent`` so _mark_wp_merged_done
    can synthesize done evidence from an approved lane state."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} planning\n"
        f"agent: {agent}\ndependencies: []\n---\n\nBody.\n",
        encoding="utf-8",
    )


def _seed_wp_approved(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Drive a WP to ``approved`` via the real status-emit pipeline."""
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import ReviewResult, TransitionRequest

    # Seed out of the non-display 'genesis' state into 'planned' (as
    # finalize-tasks does) before walking the lane lifecycle.
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="planned",
            actor="seed",
            force=True,
            reason="seed",
        )
    )
    for to_lane in ("claimed", "in_progress", "for_review", "in_review"):
        # Post-#2160 the ``in_progress -> for_review`` gate is fail-closed and
        # requires completed subtasks or force+reason. This helper manufactures
        # a terminal ``approved`` state for a merge/persistence test — it is not
        # exercising the subtask gate — so the gating hop is seeded with force.
        gating = to_lane == "for_review"
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
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
            mission_slug=mission_slug,
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


@contextlib.contextmanager
def _real_persistence_external_mocks(repo_root: Path):
    """Mock only genuinely external side-effects (dossier sync, SaaS/mission-
    closed emit, diff summary, stale-assertion network check) while running the
    REAL ``_mark_wp_merged_done`` and ``_assert_merged_wps_reached_done`` so the
    done-marking persistence is actually exercised.

    ``safe_commit`` and the post-merge invariant (``_classify_porcelain_lines``)
    are mocked: the done events are persisted to ``feature_dir/status.events.jsonl``
    by the real status-emit pipeline *before* any commit, so persistence is
    provable without driving a commit onto the protected target branch. The
    real-invariant path is covered separately by
    ``TestLegacyPlanningOnlyMetaInvariant`` (F2).
    """
    patches = [
        patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.merge.executor.run_check"),
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
        patch("specify_cli.merge.executor._classify_porcelain_lines", return_value=([], 0)),
        # NOTE: _mark_wp_merged_done and _assert_merged_wps_reached_done are
        # intentionally NOT mocked — the real done-marking persistence runs.
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[5].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[6].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[1].return_value = stale_report
        ms[2].return_value = stale_report
        yield {"safe_commit": ms[0]}


@contextlib.contextmanager
def _real_bookkeeping_commit_external_mocks(repo_root: Path):
    """Like ``_real_persistence_external_mocks`` but the bookkeeping commit runs
    for REAL — ``commit_merge_bookkeeping`` is NOT mocked.

    This is the intent-proving surface (#2934): it lets the real merge land the
    status *pair* on the target branch so a test can read it back from committed
    history (``git show main:...``), rather than only asserting what was
    *requested* of a mocked commit. Only genuine external boundaries stay stubbed
    (dossier sync, SaaS/mission-closed emit, diff summary, stale-assertion network
    check, git preflight, gates/policy, the mission-number branch bake). The
    post-merge working-tree invariant (``_classify_porcelain_lines``) stays
    short-circuited because the disposable fixture repo carries test-only
    untracked paths the invariant would otherwise flag.
    """
    patches = [
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.merge.executor.run_check"),
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
        patch("specify_cli.merge.executor._classify_porcelain_lines", return_value=([], 0)),
        # NOTE: commit_merge_bookkeeping, _mark_wp_merged_done, and
        # _assert_merged_wps_done_on_target are intentionally NOT mocked — the
        # real bookkeeping commit lands on the target branch and the executor's
        # own post-commit durability assertion runs.
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[4].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[5].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[0].return_value = stale_report
        ms[1].return_value = stale_report
        yield {}


class TestPlanningOnlyDoneMarkingPersists:
    """F1: planning-only closeout must REALLY mark each WP done and persist the
    transition, not just call mocked side-effects.

    The previous planning-only merge test mocked ``_mark_wp_merged_done`` /
    ``_assert_merged_wps_reached_done`` and only asserted they were called — the
    "WP reaches done and persists" guarantee was unproven. This test runs the
    real done-marking pipeline and reads the persisted events back.

    NOTE: the fixture leaves ``coordination_branch`` ABSENT (the primary-checkout
    surface). The ``coordination_branch``-set variant is deliberately deferred to
    https://github.com/Priivacy-ai/spec-kitty/issues/1726.
    """

    def test_planning_only_done_events_are_persisted_and_readable(
        self, tmp_path: Path
    ) -> None:
        from specify_cli.status.models import Lane
        from specify_cli.status.reducer import reduce
        from specify_cli.status.store import read_events

        slug = "real-merge-planning-only-done-persist"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, slug)
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=[],
            planning_wp_ids=["WP01", "WP02"],
        )
        for wp_id in ("WP01", "WP02"):
            _write_wp_file(feature_dir, wp_id)
            _seed_wp_approved(feature_dir, slug, wp_id)

        # Pre-condition: WPs are approved (not yet done) in the persisted log.
        pre = reduce(read_events(feature_dir))
        assert pre.work_packages["WP01"]["lane"] == Lane.APPROVED.value
        assert pre.work_packages["WP02"]["lane"] == Lane.APPROVED.value
        # coordination_branch must be absent for this primary-checkout case.
        assert "coordination_branch" not in json.loads(
            (feature_dir / "meta.json").read_text(encoding="utf-8")
        )

        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap approved planning mission")

        planning_relpath = f"kitty-specs/{slug}/research/decision-A.md"
        _commit_file(
            tmp_path,
            branch="main",
            relpath=planning_relpath,
            content="# Decision A\n\nPlanning artifact body.\n",
            message=f"plan({slug}): commit planning artifact on target",
        )

        with _real_persistence_external_mocks(tmp_path):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        # The real done-marking pipeline must have persisted a done transition
        # for every WP, readable back from the canonical event log.
        post = reduce(read_events(feature_dir))
        assert post.work_packages["WP01"]["lane"] == Lane.DONE.value, (
            "F1 regression: WP01 did not reach done in the persisted event log."
        )
        assert post.work_packages["WP02"]["lane"] == Lane.DONE.value, (
            "F1 regression: WP02 did not reach done in the persisted event log."
        )
        # And the done transitions are concretely present in the JSONL log.
        done_events = [e for e in read_events(feature_dir) if e.to_lane == Lane.DONE]
        done_wps = {e.wp_id for e in done_events}
        assert done_wps == {"WP01", "WP02"}, (
            f"F1 regression: expected persisted done transitions for WP01/WP02, "
            f"got {done_wps!r}."
        )


class TestPlanningArtifactReachesTarget:
    """FR-001 load-bearing: planning-artifact files MUST end up on the target
    branch after ``_run_lane_based_merge`` runs against real git.

    These tests do NOT mock consolidate_lane_into_mission, integrate_mission_into_target,
    or _merge_branch_into — they exercise real ``git merge``, real branch
    refs, and real worktrees.  They mock only the side effects that touch
    state outside git (status emit, dossier sync, SaaS emit, etc.).
    """

    def test_planning_artifact_on_main_reaches_target_after_merge(
        self, tmp_path: Path
    ) -> None:
        """Design-correct case: planning artifact lives on planning_base (main).

        Per research.md D4, planning_artifact WPs "execute in the canonical
        repo with workspace_path: null" — so the artifact lives on the
        planning_base branch (typically main) and ``lane_branch_name(
        "lane-planning", planning_base_branch="main")`` returns ``"main"``
        so that ``consolidate_lane_into_mission`` for ``lane-planning`` brings any
        new commits from main into the mission branch (so the mission→main
        merge sees them).

        This test proves that:

        1. A code commit on lane-a reaches main.
        2. A planning-artifact commit committed on main BEFORE the merge
           survives the merge and is still on main afterward.
        """
        slug = "real-merge-planning-design-correct"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "tasks").mkdir(parents=True)
        _write_meta(feature_dir, slug)

        # Commit the lanes.json on main so it is visible to require_lanes_json.
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=["WP01"],
            planning_wp_ids=["WP02"],
        )
        # #4764/T007: _assert_mission_terminal_ready now hard-refuses a
        # mission with a non-approved WP before any mutation. This test's
        # intent is the planning-artifact data-loss check, not readiness, so
        # seed both WPs approved via the real status-emit pipeline (mirrors
        # the sibling real-merge tests below) to let the merge proceed.
        for wp_id in ("WP01", "WP02"):
            _write_wp_file(feature_dir, wp_id)
            _seed_wp_approved(feature_dir, slug, wp_id)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap mission fixture")

        # Commit a real planning artifact on main BEFORE the merge starts.
        # Per D4, this is the design-correct location for planning artifacts.
        planning_relpath = f"kitty-specs/{slug}/research/decision-A.md"
        _commit_file(
            tmp_path,
            branch="main",
            relpath=planning_relpath,
            content="# Decision A\n\nPlanning artifact body.\n",
            message=f"plan({slug}): commit planning artifact on planning_base",
        )

        # Create the mission branch from main.
        mission_branch = f"kitty/mission-{slug}"
        _git(tmp_path, "branch", mission_branch, "main")

        # Create the lane-a branch from main and add a real code commit.
        lane_a_branch = f"kitty/mission-{slug}-lane-a"
        _git(tmp_path, "branch", lane_a_branch, "main")
        code_relpath = "src/foo.py"
        _commit_file(
            tmp_path,
            branch=lane_a_branch,
            relpath=code_relpath,
            content="def foo():\n    return 1\n",
            message=f"feat({slug}): add foo function (WP01)",
        )

        # Return to main so the merge command does not run from a feature branch.
        _git(tmp_path, "checkout", "main")

        # Drive the real merge.  No mocks of consolidate_lane_into_mission /
        # integrate_mission_into_target / _merge_branch_into.
        with _real_merge_external_mocks(tmp_path):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,  # bypass preflight (already mocked)
            )

        # The actual data-loss check.  Both files must be on main after merge.
        assert _file_on_branch(tmp_path, "main", code_relpath), (
            f"FR-001 regression: code file {code_relpath} did not reach main "
            f"after merge.  ``git ls-tree main -- {code_relpath}`` returned empty."
        )
        assert _file_on_branch(tmp_path, "main", planning_relpath), (
            f"FR-001 regression (load-bearing): planning artifact "
            f"{planning_relpath} was DROPPED from main during the merge.  "
            f"It was committed to main before the merge, but it is not "
            f"present on main afterward.  This is the silent-data-loss case "
            f"FR-001 forbids."
        )

    def test_planning_artifact_only_merge_does_not_require_mission_branch(
        self, tmp_path: Path
    ) -> None:
        """All-planning research missions close from the target branch without a mission branch.

        Runs the REAL done-marking pipeline (``_mark_wp_merged_done`` /
        ``_assert_merged_wps_reached_done`` are NOT mocked). Only genuine system
        boundaries are stubbed — network side-effects (dossier sync, SaaS /
        mission-closed emit, stale-assertion check), the git preflight, and the
        ``commit_merge_bookkeeping`` git write (spied on, to inspect the staged
        path set without touching the protected target branch).

        Because the pipeline is real, the two WPs are seeded to ``approved``
        through the real status-emit pipeline first (as a finished mission would
        be), so the done transitions the merge appends produce a genuine
        ``status.events.jsonl``. The observable guarantees here are that both WPs
        persist as done and that bookkeeping requests the status *pair* — the
        append-only event log (sole authority) AND its derived ``status.json``.
        ``commit_merge_bookkeeping`` remains a boundary spy here, so this test
        does not independently prove target-branch history — that intent is
        proven by ``test_planning_only_bookkeeping_reaches_target_branch``, which
        runs the real bookkeeping commit and reads the log back from ``main``.

        History: an earlier version mocked ``_mark_wp_merged_done`` to pin the
        call-contract. That stub manufactured a zero-event mission the successful
        approved-to-done closeout path represented here cannot produce, so
        ``status.events.jsonl`` was never written and the requested-path assertion
        below tracked a mock artifact rather than real behavior (surfaced as
        #2934). Mocking internal system-under-test logic is the antipattern;
        boundaries are the only legitimate seam.
        """
        from specify_cli.status.models import Lane
        from specify_cli.status.reducer import reduce
        from specify_cli.status.store import read_events

        slug = "real-merge-planning-only-research"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, slug)
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=[],
            planning_wp_ids=["WP01", "WP02"],
        )
        for wp_id in ("WP01", "WP02"):
            _write_wp_file(feature_dir, wp_id)
            _seed_wp_approved(feature_dir, slug, wp_id)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap approved planning mission")

        planning_relpath = f"kitty-specs/{slug}/research/decision-A.md"
        _commit_file(
            tmp_path,
            branch="main",
            relpath=planning_relpath,
            content="# Decision A\n\nPlanning artifact body.\n",
            message=f"plan({slug}): commit planning artifact on target",
        )

        mission_branch = f"kitty/mission-{slug}"
        missing_branch = subprocess.run(
            ["git", "-C", str(tmp_path), "rev-parse", "--verify", f"refs/heads/{mission_branch}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert missing_branch.returncode != 0

        with _real_persistence_external_mocks(tmp_path) as mocks:
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        assert _file_on_branch(tmp_path, "main", planning_relpath)

        # The REAL done-marking pipeline drove both WPs to done in the canonical
        # event log (no mocked call-contract to inspect — the persisted outcome
        # is the assertion).
        post = reduce(read_events(feature_dir))
        assert post.work_packages["WP01"]["lane"] == Lane.DONE.value, (
            "WP01 did not reach done in the persisted event log."
        )
        assert post.work_packages["WP02"]["lane"] == Lane.DONE.value, (
            "WP02 did not reach done in the persisted event log."
        )

        meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert isinstance(meta.get("mission_number"), int)
        assert meta.get("baseline_merge_commit")

        committed_paths: set[str] = set()
        for call in mocks["safe_commit"].call_args_list:
            committed_paths.update(_rel_paths(call.kwargs.get("paths"), tmp_path))
        assert f"kitty-specs/{slug}/meta.json" in committed_paths
        # The append-only event log (sole authority) must be requested alongside
        # its derived snapshot — never the snapshot alone.
        assert f"kitty-specs/{slug}/status.events.jsonl" in committed_paths
        assert f"kitty-specs/{slug}/status.json" in committed_paths

    def test_planning_only_bookkeeping_reaches_target_branch(
        self, tmp_path: Path
    ) -> None:
        """The status pair must land ON THE TARGET BRANCH — intent, not just request.

        The sibling test above mocks ``commit_merge_bookkeeping`` (a boundary
        spy), so it can only prove the pair was *requested*, not that it reached
        ``main``. Per the intent-dominates principle, this test proves the actual
        contract: it runs the REAL bookkeeping commit against a modern mission
        (``mission_id`` present, so the executor's own post-commit
        ``_assert_merged_wps_done_on_target`` runs instead of early-returning),
        then reads the append-only event log back from ``main``'s committed tree
        (``git show main:...``) and reduces it — proving both WPs are ``done`` on
        the target branch, not merely in the working tree. If the merge left
        ``main`` at ``approved`` (the durability-gap shape), this reduction fails.
        """
        from specify_cli.status.models import Lane
        from specify_cli.status.reducer import reduce
        from specify_cli.status.store import read_events_from_text

        slug = "real-merge-planning-only-durability"
        # A modern (canonical-ULID) mission; shape mirrors the reliability fixture
        # default (not strictly validated at this seam, distinct per tmp repo).
        mission_id = "01KQKV85DURABILITY0000000000"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, slug, mission_id=mission_id)
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=[],
            planning_wp_ids=["WP01", "WP02"],
        )
        for wp_id in ("WP01", "WP02"):
            _write_wp_file(feature_dir, wp_id)
            _seed_wp_approved(feature_dir, slug, wp_id)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap approved modern mission")

        planning_relpath = f"kitty-specs/{slug}/research/decision-A.md"
        _commit_file(
            tmp_path,
            branch="main",
            relpath=planning_relpath,
            content="# Decision A\n\nPlanning artifact body.\n",
            message=f"plan({slug}): commit planning artifact on target",
        )

        with _real_bookkeeping_commit_external_mocks(tmp_path):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        # INTENT: read the append-only event log back from main's COMMITTED tree
        # (not the working tree) and prove both WPs are done on the target branch.
        events_text = _git(
            tmp_path, "show", f"main:kitty-specs/{slug}/status.events.jsonl"
        ).stdout
        target_snapshot = reduce(read_events_from_text(feature_dir, events_text))
        assert target_snapshot.work_packages["WP01"]["lane"] == Lane.DONE.value, (
            "WP01 is not done on the target branch — the done event did not reach main."
        )
        assert target_snapshot.work_packages["WP02"]["lane"] == Lane.DONE.value, (
            "WP02 is not done on the target branch — the done event did not reach main."
        )
        # The derived snapshot must accompany its source log on the target branch.
        _git(tmp_path, "show", f"main:kitty-specs/{slug}/status.json")

    def test_planning_artifact_on_phantom_lane_branch_is_NOT_reached(
        self, tmp_path: Path
    ) -> None:
        """Design-boundary negative case (research.md D4).

        Per ``lane_branch_name``, ``lane-planning`` resolves to the
        ``planning_base_branch`` (typically ``main``), NOT to a separate
        ``kitty/mission-<slug>-lane-planning`` branch.  Operators who
        accidentally commit planning artifacts to such a phantom branch
        will lose them at merge time — the merge never visits that branch.

        This test pins that boundary as a known limitation: planning
        artifacts MUST live on ``planning_base`` (main), not on a phantom
        lane-planning branch.
        """
        slug = "real-merge-planning-phantom-branch"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "tasks").mkdir(parents=True)
        _write_meta(feature_dir, slug)

        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=["WP01"],
            planning_wp_ids=["WP02"],
        )
        # #4764/T007: seed both WPs approved so the merge-ready precondition
        # lets the merge proceed far enough to exercise the phantom-branch
        # design-boundary check under test.
        for wp_id in ("WP01", "WP02"):
            _write_wp_file(feature_dir, wp_id)
            _seed_wp_approved(feature_dir, slug, wp_id)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap mission fixture")

        # Mission branch from main.
        mission_branch = f"kitty/mission-{slug}"
        _git(tmp_path, "branch", mission_branch, "main")

        # Code lane: real code commit.
        lane_a_branch = f"kitty/mission-{slug}-lane-a"
        _git(tmp_path, "branch", lane_a_branch, "main")
        code_relpath = "src/foo.py"
        _commit_file(
            tmp_path,
            branch=lane_a_branch,
            relpath=code_relpath,
            content="def foo():\n    return 1\n",
            message=f"feat({slug}): add foo function (WP01)",
        )

        # PHANTOM lane-planning branch — this is the misuse case.
        # The planning artifact lives ONLY here, not on main.
        phantom_planning_branch = f"kitty/mission-{slug}-lane-planning"
        _git(tmp_path, "branch", phantom_planning_branch, "main")
        orphan_relpath = f"kitty-specs/{slug}/research/orphaned-decision.md"
        _commit_file(
            tmp_path,
            branch=phantom_planning_branch,
            relpath=orphan_relpath,
            content="# Orphaned\n\nThis file lives on the phantom branch.\n",
            message=f"plan({slug}): commit planning artifact on PHANTOM branch (anti-pattern)",
        )

        _git(tmp_path, "checkout", "main")

        with _real_merge_external_mocks(tmp_path):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )

        # Code file did reach main.
        assert _file_on_branch(tmp_path, "main", code_relpath), (
            "Sanity: code file from lane-a should still reach main."
        )

        # Phantom planning artifact did NOT reach main — by design.
        # ``lane_branch_name("lane-planning", planning_base_branch="main")``
        # returns ``"main"``, so the merge never visits the phantom branch.
        # This is the documented design limitation we are pinning.
        assert not _file_on_branch(tmp_path, "main", orphan_relpath), (
            "Design-boundary regression: a planning artifact committed only "
            f"on the phantom branch {phantom_planning_branch} unexpectedly "
            f"reached main.  Per research.md D4, planning artifacts must "
            f"live on planning_base (main), and the merge does not visit a "
            f"separate ``kitty/mission-<slug>-lane-planning`` branch.  If "
            f"this assertion starts failing, the design has changed and the "
            f"D4 documentation must be updated."
        )


# ---------------------------------------------------------------------------
# WP02/T005 — #3131 P1 data-loss regression: the DEFAULT merge cleanup must
# honor a mission's meta.json retention policy, on a COORD-topology mission,
# driven at the CLI layer (where the ``True`` cleanup default lives).
# ---------------------------------------------------------------------------


_RETENTION_MISSION_ID = "01KX0000000RETENTIONCOORD01"
_RETENTION_MID8 = _RETENTION_MISSION_ID[:8].lower()
_RETENTION_SLUG = f"retention-repro-{_RETENTION_MID8}"
_RETENTION_MISSION_BRANCH = f"kitty/mission-{_RETENTION_SLUG}"


def _write_coord_retaining_meta(feature_dir: Path, slug: str) -> None:
    """meta.json for a COORD-topology mission that retains BOTH branches and worktrees."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _RETENTION_MISSION_ID,
        "mid8": _RETENTION_MID8,
        "mission_slug": slug,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": _RETENTION_MISSION_BRANCH,
        "mission_branch": _RETENTION_MISSION_BRANCH,
        "topology": "coord",
        "purpose_tldr": "retention regression pin (#3131)",
        "purpose_context": "merge default cleanup must honor meta.json retention",
        "retain_branches": True,
        "retain_worktrees": True,
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _invoke_merge_cli(repo: Path, extra_args: list[str]) -> object:
    """Invoke the real ``merge`` Typer command (CLI layer where the tri-state
    cleanup flags' default lives) — NOT ``_run_lane_based_merge`` directly,
    whose ``delete_branch``/``remove_worktree`` params have no default of
    their own."""
    import os

    from typer.testing import CliRunner

    from specify_cli.cli.commands.merge import merge

    app = typer.Typer()
    app.command()(merge)

    runner = CliRunner()
    original_cwd = os.getcwd()
    try:
        os.chdir(repo)
        return runner.invoke(app, extra_args, catch_exceptions=False)
    finally:
        os.chdir(original_cwd)


class TestRetentionConstraintSurvivesCleanup:
    """#3131 P1: the DEFAULT ``spec-kitty merge`` cleanup must honor a
    mission's ``meta.json`` retention policy across the success path.

    Non-vacuous per ``contracts/retention-resolver-contract.md``: a real
    COORD-topology mission (``coordination_branch`` present, mid8-embedded
    slug), a NON-planning lane, driven through the CLI ``merge`` entry with
    NO ``--delete-branch``/``--keep-branch``/``--remove-worktree``/
    ``--keep-worktree`` flags — letting the CLI's own default resolve. On
    current main that default is unconditional ``True``/``True``, so the
    mission branch, the lane branch, and the lane worktree are all deleted
    despite ``retain_branches: true`` / ``retain_worktrees: true`` in
    meta.json (RED). After WP02 lands, the same invocation resolves the
    default through ``resolve_merge_retention`` -> meta retain (GREEN).
    """

    @pytest.mark.regression
    def test_default_merge_honors_coord_retention_policy(
        self, tmp_path: Path
    ) -> None:
        slug = _RETENTION_SLUG
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        (feature_dir / "tasks").mkdir(parents=True)
        _write_coord_retaining_meta(feature_dir, slug)
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=["WP01"],
            planning_wp_ids=[],
            mission_branch=_RETENTION_MISSION_BRANCH,
        )
        # #4764/T007: seed WP01 approved so the merge-ready precondition lets
        # the merge proceed to the branch/worktree-retention behavior under test.
        _write_wp_file(feature_dir, "WP01")
        _seed_wp_approved(feature_dir, slug, "WP01")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap coord retaining mission")

        # Mission branch == coordination branch (coord topology).
        _git(tmp_path, "branch", _RETENTION_MISSION_BRANCH, "main")

        # Real code lane with a real commit.
        lane_a_branch = f"kitty/mission-{slug}-lane-a"
        _git(tmp_path, "branch", lane_a_branch, "main")
        code_relpath = "src/retention_repro.py"
        _commit_file(
            tmp_path,
            branch=lane_a_branch,
            relpath=code_relpath,
            content="def foo():\n    return 1\n",
            message=f"feat({slug}): add foo function (WP01)",
        )
        _git(tmp_path, "checkout", "main")

        # A REAL lane worktree, at the MODERN mid8-embedded path the cleanup
        # phase resolves for a modern (mission_id-bearing) mission — NOT the
        # legacy `<slug>-<lane>` path, and explicitly NOT the merge scratch
        # worktree.
        from specify_cli.lanes.branch_naming import worktree_path as _worktree_path_helper

        lane_worktree = _worktree_path_helper(
            tmp_path, slug, mission_id=_RETENTION_MISSION_ID, lane_id="lane-a"
        )
        _git(
            tmp_path,
            "worktree",
            "add",
            str(lane_worktree),
            lane_a_branch,
        )

        assert lane_worktree.exists(), "fixture invalid: lane worktree must exist pre-merge"
        assert _branch_exists(tmp_path, _RETENTION_MISSION_BRANCH), (
            "fixture invalid: mission/coordination branch must exist pre-merge"
        )
        assert _branch_exists(tmp_path, lane_a_branch), (
            "fixture invalid: lane branch must exist pre-merge"
        )

        with (
            _real_merge_external_mocks(tmp_path),
            # This fixture's modern (mission_id-bearing) meta.json makes the
            # target-branch done-durability assert run for real; it needs a
            # committed status.events.jsonl this test's mocked done-marking
            # never produces. That WP-bookkeeping durability is out of scope
            # for this branch/worktree-retention regression.
            patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
            patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        ):
            # NO --delete-branch/--keep-branch/--remove-worktree/--keep-worktree:
            # the CLI's own default resolves the cleanup decision.
            result = _invoke_merge_cli(
                tmp_path,
                ["--mission", slug, "--yes", "--allow-sparse-checkout"],
            )

        exit_code = getattr(result, "exit_code", None)
        assert exit_code == 0, (
            f"merge must succeed for this fixture (output: "
            f"{getattr(result, 'output', None)!r}, "
            f"exception: {getattr(result, 'exception', None)!r})"
        )

        # ANCHOR (INV-1 / FR-002): the mission/coordination branch survives.
        assert _branch_exists(tmp_path, _RETENTION_MISSION_BRANCH), (
            "#3131 P1 regression: the DEFAULT merge deleted the mission/"
            "coordination branch despite meta.json's retain_branches=true. "
            "The default cleanup decision must be resolved through "
            "resolve_merge_retention(), not an unconditional True."
        )
        # ANCHOR: a non-planning LANE branch survives.
        assert _branch_exists(tmp_path, lane_a_branch), (
            "#3131 P1 regression: the DEFAULT merge deleted the lane branch "
            "despite meta.json's retain_branches=true."
        )
        # ANCHOR: the lane WORKTREE survives (explicitly not the merge scratch
        # worktree — this is `.worktrees/<slug>-<mid8>-lane-<id>`).
        assert lane_worktree.exists(), (
            "#3131 P1 regression: the DEFAULT merge removed the lane worktree "
            "despite meta.json's retain_worktrees=true. The default cleanup "
            "decision must be resolved through resolve_merge_retention(), not "
            "an unconditional True."
        )

    def test_explicit_delete_override_still_reachable(self, tmp_path: Path) -> None:
        """Second assertion tier (added once enforcement lands, T005): an
        EXPLICIT ``--delete-branch``/``--remove-worktree`` override still
        deletes on the SAME retaining mission — proving the override path
        stays reachable and this class does not just assert "merge never
        deletes"."""
        slug = _RETENTION_SLUG + "-override"
        mission_branch = f"kitty/mission-{slug}"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        (feature_dir / "tasks").mkdir(parents=True)
        _write_coord_retaining_meta(feature_dir, slug)
        # Re-key the coord/mission branch marker to this slug's own branch.
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["mission_slug"] = slug
        meta["coordination_branch"] = mission_branch
        meta["mission_branch"] = mission_branch
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=["WP01"],
            planning_wp_ids=[],
            mission_branch=mission_branch,
        )
        # #4764/T007: seed WP01 approved so the merge-ready precondition lets
        # the merge proceed to the explicit-override behavior under test.
        _write_wp_file(feature_dir, "WP01")
        _seed_wp_approved(feature_dir, slug, "WP01")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap coord retaining mission")

        _git(tmp_path, "branch", mission_branch, "main")
        lane_a_branch = f"kitty/mission-{slug}-lane-a"
        _git(tmp_path, "branch", lane_a_branch, "main")
        code_relpath = "src/retention_repro_override.py"
        _commit_file(
            tmp_path,
            branch=lane_a_branch,
            relpath=code_relpath,
            content="def bar():\n    return 2\n",
            message=f"feat({slug}): add bar function (WP01)",
        )
        _git(tmp_path, "checkout", "main")

        from specify_cli.lanes.branch_naming import worktree_path as _worktree_path_helper

        lane_worktree = _worktree_path_helper(
            tmp_path, slug, mission_id=_RETENTION_MISSION_ID, lane_id="lane-a"
        )
        _git(tmp_path, "worktree", "add", str(lane_worktree), lane_a_branch)

        with (
            _real_merge_external_mocks(tmp_path),
            patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
            patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        ):
            result = _invoke_merge_cli(
                tmp_path,
                [
                    "--mission",
                    slug,
                    "--yes",
                    "--allow-sparse-checkout",
                    "--delete-branch",
                    "--remove-worktree",
                ],
            )

        exit_code = getattr(result, "exit_code", None)
        assert exit_code == 0, (
            f"merge must succeed for this fixture (output: "
            f"{getattr(result, 'output', None)!r}, "
            f"exception: {getattr(result, 'exception', None)!r})"
        )
        assert not _branch_exists(tmp_path, mission_branch), (
            "explicit --delete-branch must still delete the mission/coordination "
            "branch even though meta.json retains it -- the override path must "
            "stay reachable."
        )
        assert not _branch_exists(tmp_path, lane_a_branch), (
            "explicit --delete-branch must still delete the lane branch."
        )
        assert not lane_worktree.exists(), (
            "explicit --remove-worktree must still remove the lane worktree "
            "even though meta.json retains it -- the override path must stay "
            "reachable."
        )
        # FR-005/FR-006: an explicit CLI delete over a retaining policy must be
        # recorded as an operator-visible override notice, never silent.
        output = getattr(result, "output", "") or ""
        assert "explicit delete overrode retention policy for branches" in output
        assert "explicit delete overrode retention policy for worktrees" in output

    def test_malformed_retention_value_is_treated_as_retaining(
        self, tmp_path: Path
    ) -> None:
        """#3131 INV-4/T011: a malformed (non-boolean) ``retain_branches`` /
        ``retain_worktrees`` value in meta.json must NEVER ``bool()``-coerce
        to a delete — it resolves to retaining (fail-closed), with a
        malformed-value warning, exactly like an explicit ``true``."""
        slug = _RETENTION_SLUG + "-malformed"
        mission_branch = f"kitty/mission-{slug}"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        (feature_dir / "tasks").mkdir(parents=True)
        _write_coord_retaining_meta(feature_dir, slug)
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["mission_slug"] = slug
        meta["coordination_branch"] = mission_branch
        meta["mission_branch"] = mission_branch
        # Malformed: a non-boolean truthy-ish JSON value, never bool()-coerced.
        meta["retain_branches"] = "yes"
        meta["retain_worktrees"] = 1
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=["WP01"],
            planning_wp_ids=[],
            mission_branch=mission_branch,
        )
        # #4764/T007: seed WP01 approved so the merge-ready precondition lets
        # the merge proceed to the malformed-retention-value behavior under test.
        _write_wp_file(feature_dir, "WP01")
        _seed_wp_approved(feature_dir, slug, "WP01")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap malformed-retention mission")

        _git(tmp_path, "branch", mission_branch, "main")
        lane_a_branch = f"kitty/mission-{slug}-lane-a"
        _git(tmp_path, "branch", lane_a_branch, "main")
        _commit_file(
            tmp_path,
            branch=lane_a_branch,
            relpath="src/retention_repro_malformed.py",
            content="def baz():\n    return 3\n",
            message=f"feat({slug}): add baz function (WP01)",
        )
        _git(tmp_path, "checkout", "main")

        from specify_cli.lanes.branch_naming import worktree_path as _worktree_path_helper

        lane_worktree = _worktree_path_helper(
            tmp_path, slug, mission_id=_RETENTION_MISSION_ID, lane_id="lane-a"
        )
        _git(tmp_path, "worktree", "add", str(lane_worktree), lane_a_branch)

        with (
            _real_merge_external_mocks(tmp_path),
            patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
            patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        ):
            result = _invoke_merge_cli(
                tmp_path,
                ["--mission", slug, "--yes", "--allow-sparse-checkout"],
            )

        exit_code = getattr(result, "exit_code", None)
        assert exit_code == 0, (
            f"merge must succeed for this fixture (output: "
            f"{getattr(result, 'output', None)!r}, "
            f"exception: {getattr(result, 'exception', None)!r})"
        )
        assert _branch_exists(tmp_path, mission_branch), (
            "INV-4 regression: a malformed retain_branches value resolved to "
            "delete instead of fail-closed retain."
        )
        assert _branch_exists(tmp_path, lane_a_branch)
        assert lane_worktree.exists(), (
            "INV-4 regression: a malformed retain_worktrees value resolved to "
            "delete instead of fail-closed retain."
        )
        output = getattr(result, "output", "") or ""
        assert "malformed retain_branches value in meta.json" in output
        assert "malformed retain_worktrees value in meta.json" in output

    def test_dry_run_forecast_reflects_coord_retention_end_to_end(
        self, tmp_path: Path
    ) -> None:
        """#3131 FR-008/SC-003: the CLI ``merge --dry-run`` path (not just the
        forecast seam in isolation) threads the unset tri-state flags through
        ``resolve_merge_retention`` and reports the RESOLVED retain decision.
        Closes the merge.py -> run_dry_run_forecast wiring seam (the None->True
        collapse that FR-008's fold removed) with an end-to-end CLI assertion."""
        slug = _RETENTION_SLUG + "-dryrun"
        mission_branch = f"kitty/mission-{slug}"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        (feature_dir / "tasks").mkdir(parents=True)
        _write_coord_retaining_meta(feature_dir, slug)
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["mission_slug"] = slug
        meta["coordination_branch"] = mission_branch
        meta["mission_branch"] = mission_branch
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_lanes_manifest(
            feature_dir,
            slug,
            code_wp_ids=["WP01"],
            planning_wp_ids=[],
            mission_branch=mission_branch,
        )
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap dry-run retaining mission")
        _git(tmp_path, "branch", mission_branch, "main")

        # NO cleanup flags: the CLI default (unset tri-state) must resolve
        # through the mission's retention policy, not the pre-#3131 delete default.
        result = _invoke_merge_cli(
            tmp_path,
            ["--mission", slug, "--dry-run", "--json"],
        )
        exit_code = getattr(result, "exit_code", None)
        assert exit_code == 0, (
            f"dry-run must succeed (output: {getattr(result, 'output', None)!r}, "
            f"exception: {getattr(result, 'exception', None)!r})"
        )
        output = getattr(result, "output", "") or ""
        # The forecast prints a JSON object (possibly after a preamble line).
        json_line = next(
            line for line in output.splitlines() if line.strip().startswith("{")
        )
        payload = json.loads(json_line)
        # FR-008: resolved retain decision, not the flag-echo default.
        assert payload["delete_branch"] is False, (
            "FR-008 regression: CLI --dry-run did not honor meta retention "
            f"(payload delete_branch={payload.get('delete_branch')!r}). The "
            "merge.py -> run_dry_run_forecast wiring must pass the raw tri-state."
        )
        assert payload["remove_worktree"] is False
        assert payload["retention"]["branch_source"] == "meta"
        assert payload["retention"]["worktree_source"] == "meta"
