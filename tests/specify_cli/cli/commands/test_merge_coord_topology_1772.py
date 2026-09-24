"""Scope: #1772 coord-topology merge & path/status hardening (WP14).

ATDD-first (C-011) regression pin for #1772. These tests reproduce the three
ways ``spec-kitty merge`` failed on a healthy, fully-approved
coordination-topology mission and, on retry, silently produced a zero-code
squash-merge while reporting success:

- Bug 3 (FR-037): the retry gated lane integration on the per-WP ``done``
  status (already recorded before the abort, so ``MergeState.completed_wps``
  listed every WP), skipped all lanes, and squashed ZERO code while reporting
  success. The fix gates integration on the actual lane tree-diff vs. the
  mission branch and fails loudly when a squash would integrate zero diffs.
- Bug 0 (FR-035): finalize/recovery + merge staging passed tracked
  ``.worktrees/`` content to ``git add``. ``spec-kitty doctor coordination``
  must flag pre-existing tracked ``.worktrees/`` content.
- Bug 4 (FR-038): post-merge validation read a ``.worktrees/`` worktree path
  that is never tracked in a branch tree. Validation must resolve the
  in-branch status path.

These tests drive the REAL lane-skip + ``consolidate_lane_into_mission`` /
``integrate_mission_into_target`` / ``_merge_branch_into`` functions against a real
on-disk git repository. They mock ONLY the side effects that touch state
outside git (status emit, dossier sync, SaaS emit, stale-assertion check,
sparse-checkout preflight, merge gates, mission_number bake, post-merge
working-tree invariant, in-branch validation).
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

# Import the status package before any coordination submodule. The production
# CLI entrypoint (``specify_cli/__init__``) imports ``status`` before ``merge``;
# importing ``merge`` first (as a test module does) would otherwise reach
# ``coordination/__init__`` -> ``transaction`` -> ``status`` mid-initialization
# and trip a known import-order cycle. Mirroring the production order here keeps
# this regression test importable under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import MergeState, save_state

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _file_on_branch(repo: Path, branch: str, relpath: str) -> bool:
    """Return True iff *relpath* exists on *branch* (via ``git ls-tree``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "--name-only", "-r", branch, "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and relpath in result.stdout.splitlines()


# ---------------------------------------------------------------------------
# Coord-topology fixture
# ---------------------------------------------------------------------------

MISSION_SLUG = "coord-topology-1772"
MISSION_ID = "01CRDTOPO000000000000001772"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"


def _write_meta(feature_dir: Path) -> None:
    """meta.json declaring a coordination_branch (coord-topology mission)."""
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MISSION_ID[:8],
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "coord-topology merge regression (#1772)",
        "purpose_context": "merge must integrate lane diffs or fail loudly",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_manifest(feature_dir: Path) -> LanesManifest:
    """A single code lane (legacy branch naming via mission_id == slug)."""
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        # mission_id == slug => legacy lane_branch_name form
        # ``kitty/mission-<slug>-lane-a`` which consolidate_lane_into_mission constructs.
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/feature_code.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _bootstrap_coord_mission(
    repo: Path,
    *,
    with_tracked_worktrees_junk: bool = False,
    lane_code_relpath: str = "src/feature_code.py",
) -> Path:
    """Bootstrap a coord-topology mission with a code lane carrying a real diff.

    Returns the feature_dir.
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)

    # status.events.jsonl in-branch (tracked). Pre-record per-WP done events so
    # the in-branch status path resolves and post-merge validation can read it.
    done_event = {
        "actor": "merge",
        "at": now_utc_iso(),
        "event_id": "01HXYZDONE0000000000000001",
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "approved",
        "to_lane": "done",
        "wp_id": "WP01",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(done_event) + "\n", encoding="utf-8"
    )
    # Derived status snapshot (tracked alongside the event log in real
    # missions; the bookkeeping safe_commit stages it, so it must exist).
    (feature_dir / "status.json").write_text(
        json.dumps({"event_count": 1, "work_packages": {"WP01": {"lane": "done"}}})
        + "\n",
        encoding="utf-8",
    )

    if with_tracked_worktrees_junk:
        # Tracked ``.worktrees/<m>-coord/…`` junk (the F-07 pollution).
        junk = repo / ".worktrees" / f"{MISSION_SLUG}-coord" / "kitty-specs" / MISSION_SLUG
        junk.mkdir(parents=True)
        (junk / "meta.json").write_text("{}\n", encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap coord mission")

    # Create the coordination/mission branch at the current tip. Deliberately
    # a bare `git branch` (NOT a materialized worktree) here: some consumers
    # of this shared harness (tests/merge/test_issue_2709_squash_provenance.py)
    # need to `git checkout COORD_BRANCH` in the MAIN worktree AFTER bootstrap
    # to seed further commits directly onto it — a materialized worktree of
    # the same branch would make that checkout fail ("already checked out in
    # another worktree"). Consumers that drive a real `_run_lane_based_merge`
    # and need the coord STATUS_STATE read to succeed (post-#4959,
    # `CoordinationWorktreeUnmaterialized` otherwise) call
    # `_materialize_coord_worktree` themselves, once any direct COORD_BRANCH
    # checkout in the main worktree is done.
    _git(repo, "branch", COORD_BRANCH)

    # Create the lane branch with a REAL code diff that is NOT on the mission
    # branch nor on main.
    lane_branch = f"kitty/mission-{MISSION_SLUG}-lane-a"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / lane_code_relpath
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def feature() -> int:\n    return 1772\n", encoding="utf-8")
    _git(repo, "add", lane_code_relpath)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for WP01")
    _git(repo, "checkout", "main")

    return feature_dir


def _materialize_coord_worktree(repo: Path) -> Path:
    """Materialize the coordination worktree for ``COORD_BRANCH`` at its CURRENT tip.

    Post-#4959, a coord-topology ``_run_lane_based_merge`` STATUS_STATE read
    raises ``CoordinationWorktreeUnmaterialized`` when the declared
    coordination branch exists in git but its worktree was never
    materialized — ``_bootstrap_coord_mission`` deliberately leaves it bare
    (see the comment there) so callers that still need to ``git checkout
    COORD_BRANCH`` in the MAIN worktree post-bootstrap are not blocked.

    Call this ONLY once every direct checkout of ``COORD_BRANCH`` in the main
    worktree is done, with the main worktree currently on a DIFFERENT branch —
    git refuses to check out a branch that is already checked out elsewhere,
    including into a new worktree.
    """
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MISSION_ID[:8])
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    return coord_worktree


@contextlib.contextmanager
def _real_merge_external_mocks(*, real_baseline_recording: bool = False):
    """Mock only the side effects that touch state OUTSIDE git.

    The real ``consolidate_lane_into_mission``, ``integrate_mission_into_target``,
    ``_merge_branch_into`` and the real lane-skip decision are NOT mocked —
    they execute real ``git merge`` so the #1772 zero-diff squash bug
    reproduces (or is fixed).

    With ``real_baseline_recording=True`` the #1827 baseline-recording flow is
    ALSO left real (``_record_baseline_merge_commit``, the bookkeeping
    ``safe_commit``, and ``_assert_baseline_merge_commit_on_target``) so the
    FR-010 / AC-A3 regression test can assert the recorded
    ``baseline_merge_commit`` lands in the target branch's committed
    ``meta.json``.
    """
    baseline_recording_targets = {
        "specify_cli.merge.executor._record_baseline_merge_commit",
        "specify_cli.merge.executor._assert_baseline_merge_commit_on_target",
        "specify_cli.merge.executor.commit_merge_bookkeeping",
    }
    patch_specs: list[tuple[str, dict[str, object]]] = [
        ("specify_cli.merge.done_bookkeeping._mark_wp_merged_done", {}),
        ("specify_cli.merge.executor._record_merged_wps_done_for_merge", {}),
        ("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done", {}),
        ("specify_cli.merge.executor._assert_merged_wps_done_on_target", {}),
        ("specify_cli.merge.executor._record_baseline_merge_commit", {"return_value": None}),
        ("specify_cli.merge.executor._assert_baseline_merge_commit_on_target", {}),
        ("specify_cli.merge.executor.commit_merge_bookkeeping", {}),
        ("specify_cli.merge.executor.run_check", {}),
        ("specify_cli.merge.executor.require_no_sparse_checkout", {}),
        ("specify_cli.cli.commands.merge._enforce_git_preflight", {}),
        ("specify_cli.merge.executor._enforce_review_artifact_consistency", {}),
        ("specify_cli.merge.executor._enforce_canonical_status_history", {}),
        ("specify_cli.merge.executor._warn_or_confirm_hollow_reviews", {}),
        ("specify_cli.merge.executor._bake_mission_number_into_mission_branch", {"return_value": None}),
        ("specify_cli.merge.executor._refresh_primary_checkout_after_merge", {}),
        # Post-merge working-tree invariant fires on test-only files; the merge
        # has already run through real git by the time this would raise.
        ("specify_cli.merge.executor._classify_porcelain_lines", {"return_value": ([], 0)}),
        ("specify_cli.policy.merge_gates.evaluate_merge_gates", {}),
        ("specify_cli.policy.config.load_policy_config", {}),
        ("specify_cli.merge.executor.has_remote", {"return_value": False}),
    ]
    with contextlib.ExitStack() as stack:
        mocks: dict[str, MagicMock] = {}
        for target, kwargs in patch_specs:
            if real_baseline_recording and target in baseline_recording_targets:
                continue
            mocks[target] = stack.enter_context(patch(target, **kwargs))
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["specify_cli.policy.merge_gates.evaluate_merge_gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        mocks["specify_cli.policy.config.load_policy_config"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["specify_cli.merge.executor.run_check"].return_value = stale_report
        yield mocks


# ---------------------------------------------------------------------------
# T057 — FR-037: zero-diff squash on retry-after-abort must integrate or fail
# ---------------------------------------------------------------------------


def test_retry_after_abort_integrates_lane_code_or_fails_loudly(tmp_path: Path) -> None:
    """#1772 Bug 3 / FR-037: a retry whose MergeState marks every WP ``done``
    (an aborted-merge state) must NOT skip the lane and squash zero code while
    reporting success. It must integrate the real lane diff OR fail loudly.

    On current (pre-fix) code the lane-skip gates on ``completed_wps`` (a
    done-status proxy), skips the only lane, then ``integrate_mission_into_target``
    with ``allow_noop_squash=True`` returns ``already_applied=True`` — a silent
    zero-code success. The lane code never reaches ``main``.
    """
    _init_git_repo(tmp_path)
    _bootstrap_coord_mission(tmp_path)
    _materialize_coord_worktree(tmp_path)
    lane_code = "src/feature_code.py"

    # Pre-existing aborted-merge state: every WP already marked completed.
    state = MergeState(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        target_branch="main",
        wp_order=["WP01"],
        completed_wps=["WP01"],
        strategy="squash",
    )
    save_state(state, tmp_path)

    assert not _file_on_branch(tmp_path, "main", lane_code), (
        "fixture precondition: lane code must NOT be on main before merge"
    )

    integrated = False
    failed_loudly = False
    with _real_merge_external_mocks():
        try:
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )
        except typer.Exit as exc:
            # A loud structured failure (non-zero exit) is an acceptable outcome.
            failed_loudly = exc.exit_code != 0

    integrated = _file_on_branch(tmp_path, "main", lane_code)

    assert integrated or failed_loudly, (
        "#1772 FR-037 regression: merge reported success but integrated ZERO "
        "lane diffs — the lane code never reached the target branch and the "
        "merge did not fail loudly (silent zero-code squash)."
    )


# ---------------------------------------------------------------------------
# T057 — FR-037: a genuinely-clean retry must still integrate the lane code
# ---------------------------------------------------------------------------


def test_fresh_merge_integrates_lane_code(tmp_path: Path) -> None:
    """Healthy-merge path (NFR-001): with no aborted MergeState, a fresh merge
    integrates the lane code onto the target branch."""
    _init_git_repo(tmp_path)
    _bootstrap_coord_mission(tmp_path)
    _materialize_coord_worktree(tmp_path)
    lane_code = "src/feature_code.py"

    with _real_merge_external_mocks():
        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    assert _file_on_branch(tmp_path, "main", lane_code), (
        "healthy-merge regression: fresh merge did not integrate the lane code "
        "onto the target branch."
    )


# ---------------------------------------------------------------------------
# T027 (WP05, coordination-merge-stabilization-01KTXRVR) — FR-010 / AC-A3:
# baseline_merge_commit recording regression (#1827)
# ---------------------------------------------------------------------------


def test_merge_records_baseline_merge_commit_on_target(tmp_path: Path) -> None:
    """#1827 / FR-010 / AC-A3: a coord-topology merge must land
    ``baseline_merge_commit`` in the target branch's committed ``meta.json``.

    The #1827 defect was post-merge baseline validation running before
    ``_record_baseline_merge_commit`` had written the baseline; fixed in rc42
    (``9c8bff06f``) but never pinned by a regression test. This test runs a
    REAL coord-topology merge with the baseline-recording flow UNMOCKED
    (``_record_baseline_merge_commit`` → bookkeeping ``safe_commit`` →
    ``_assert_baseline_merge_commit_on_target``) and asserts via
    ``git show <target>:kitty-specs/<slug>/meta.json`` that the committed
    metadata carries ``baseline_merge_commit`` equal to the target-branch
    baseline SHA captured before the mission landed.

    Known bounded behavior (NOT fixed here — #1666 umbrella scope): if the
    merge crashes BETWEEN ``_record_baseline_merge_commit`` writing the
    working-tree ``meta.json`` and the bookkeeping ``safe_commit`` landing it
    on the target branch, a re-run finds the baseline already recorded in the
    working tree (the record step is a no-op on an existing value) while the
    committed history still lacks it until the re-run's bookkeeping commit
    succeeds. This test pins only the happy-path durability invariant; do not
    widen it to the crash-window re-run edge in this WP.
    """
    _init_git_repo(tmp_path)
    _bootstrap_coord_mission(tmp_path)
    _materialize_coord_worktree(tmp_path)

    # The baseline the merge must record: the target branch tip BEFORE the
    # mission lands (merge.py captures it via ``git rev-parse <target>``
    # before the mission→target merge).
    pre_merge_target_sha = _git(tmp_path, "rev-parse", "main").stdout.strip()

    with _real_merge_external_mocks(real_baseline_recording=True):
        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    committed = _git(
        tmp_path, "show", f"main:kitty-specs/{MISSION_SLUG}/meta.json"
    ).stdout
    committed_meta = json.loads(committed)
    recorded = committed_meta.get("baseline_merge_commit")
    assert recorded, (
        "#1827 regression: the committed meta.json on the target branch does "
        "not carry baseline_merge_commit — post-merge review cannot anchor "
        f"(MISSION_REVIEW_MODE_MISMATCH). Committed meta: {committed_meta!r}"
    )
    assert recorded == pre_merge_target_sha, (
        "#1827 regression: baseline_merge_commit on the target branch is not "
        "the pre-merge target baseline SHA.\n"
        f"  recorded:  {recorded!r}\n"
        f"  expected:  {pre_merge_target_sha!r}"
    )


def test_squash_applied_branch_is_integrated_by_tree_not_ancestry(tmp_path: Path) -> None:
    """FR-037: squash-resume idempotency must use content, not ancestry."""
    from specify_cli.cli.commands.merge import (
        _branch_trees_equal,
        _lane_already_integrated,
    )

    _init_git_repo(tmp_path)
    _git(tmp_path, "checkout", "-b", "mission")
    code_path = tmp_path / "src" / "feature_code.py"
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def feature() -> int:\n    return 1772\n", encoding="utf-8")
    _git(tmp_path, "add", "src/feature_code.py")
    _git(tmp_path, "commit", "-m", "feat: mission code")

    _git(tmp_path, "checkout", "main")
    _git(tmp_path, "merge", "--squash", "mission")
    _git(tmp_path, "commit", "-m", "squash mission")

    assert not _lane_already_integrated(tmp_path, "mission", "main")
    assert _branch_trees_equal(tmp_path, "mission", "main")


# ---------------------------------------------------------------------------
# T057 — FR-035: doctor flags tracked .worktrees/ content
# ---------------------------------------------------------------------------


def test_doctor_flags_tracked_worktrees_content(tmp_path: Path) -> None:
    """#1772 Bug 0 / FR-035: ``spec-kitty doctor coordination`` must flag
    pre-existing tracked ``.worktrees/`` content with a remediation hint."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app as doctor_app

    _init_git_repo(tmp_path)
    _bootstrap_coord_mission(tmp_path, with_tracked_worktrees_junk=True)

    runner = CliRunner()
    # #2059: the coordination command resolves repo_root in its sibling module
    # (_coordination_doctor), so patch the resolution seam there.
    with patch(
        "specify_cli.cli.commands._coordination_doctor.locate_project_root",
        return_value=tmp_path,
    ):
        result = runner.invoke(doctor_app, ["coordination", "--json"])

    assert result.exit_code == 1, (
        "doctor must exit 1 when tracked .worktrees/ content is present"
    )
    payload = json.loads(result.stdout)
    worktree_findings = [
        f
        for f in payload
        if f.get("error_code") == "TRACKED_WORKTREES_CONTENT"
    ]
    assert worktree_findings, (
        "#1772 FR-035 regression: doctor did not flag tracked .worktrees/ "
        f"content. Findings: {payload!r}"
    )
    assert worktree_findings[0]["severity"] == "error"
    assert worktree_findings[0]["next_step"], "must carry a remediation hint"


# ---------------------------------------------------------------------------
# T057 — FR-038: post-merge validation resolves the in-branch status path
# ---------------------------------------------------------------------------


def test_post_merge_validation_reads_in_branch_status_path(tmp_path: Path) -> None:
    """#1772 Bug 4 / FR-038: post-merge target validation must resolve the
    in-branch tracked ``kitty-specs/<m>/status.events.jsonl`` path, never a
    ``.worktrees/`` worktree path (``git show <branch>:.worktrees/…``)."""
    from specify_cli.cli.commands.merge import _assert_merged_wps_done_on_target

    _init_git_repo(tmp_path)
    feature_dir = _bootstrap_coord_mission(tmp_path)

    captured_refs: list[str] = []

    # WP08 (#2057): _assert_merged_wps_done_on_target moved to the
    # ``done_bookkeeping`` seam, so its ``run_command`` collaborator must be
    # spied there (patching the shim no longer intercepts the call).
    import specify_cli.merge.done_bookkeeping as db_mod

    real_run_command = db_mod.run_command

    def spy_run_command(cmd, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "show":
            captured_refs.append(cmd[2])
        return real_run_command(cmd, *args, **kwargs)

    # The done event is already committed in-branch on main via bootstrap.
    with patch.object(db_mod, "run_command", side_effect=spy_run_command):
        _assert_merged_wps_done_on_target(
            tmp_path,
            MISSION_SLUG,
            "main",
            ["WP01"],
            feature_dir=feature_dir,
            mission_id=MISSION_ID,
        )

    assert captured_refs, "expected a git show invocation for in-branch validation"
    for ref in captured_refs:
        assert ".worktrees" not in ref, (
            "#1772 FR-038 regression: post-merge validation read a .worktrees/ "
            f"path that is never tracked in a branch tree: {ref!r}"
        )
        assert "kitty-specs/" in ref, (
            f"post-merge validation must read the in-branch kitty-specs path: {ref!r}"
        )
