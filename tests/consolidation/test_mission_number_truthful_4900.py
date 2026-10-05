"""Regression tests for truthful mission numbering on consolidate (#4900).

``spec-kitty consolidate`` prints ``Assigned mission_number=N`` (from the
pre-squash mission-branch bake) but the ``meta.json`` merge driver treated a
target-owned ``mission_number`` as authoritative whenever it was merely
*present* -- even when it was ``null`` -- so the target's ``null`` won and
every mission ended up numbered ``1``. This module covers:

1. Driver unit: ``(null, 1) -> 1`` is the regression case; ``(3, 1) -> 3``
   ("target wins") and ``(missing key, 1) -> 1`` are controls.
2. Sequential consolidates through the real CLI entry point: two missions
   consolidated one after another must record ``1`` then ``2`` on the
   target branch, not ``null``/``1``/``1``.
3. A hand-numbered target: a target already carrying ``mission_number: 7``
   for one mission gives the next mission ``8``.
4. Fault-injected read-back mismatch: a corrupted read-back must exit
   non-zero and never print a false "Assigned" line.
5. The target-tree write never discards a decided number, never fabricates
   a stub ``meta.json``, and announces only after read-back verification.

Reuses fixture helpers from ``tests.integration.test_merge_lane_planning_data_loss``
(the real-CLI, real-git merge harness) and the driver-level helpers already
established in ``tests/consolidation/test_merge_drivers.py`` /
``test_merge_time_number_assignment.py`` / ``test_ordering_bake_seam.py``.
"""

from __future__ import annotations

import contextlib
import subprocess
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.drivers import MergeDriverOutcome, run_meta_driver
from specify_cli.consolidation.mission_number import is_assigned_mission_number

from tests.integration.test_merge_lane_planning_data_loss import (
    _commit_file,
    _git,
    _init_git_repo,
    _seed_wp_approved,
    _write_lanes_manifest,
    _write_meta,
    _write_wp_file,
)
from specify_cli.consolidation import phase_bookkeeping
from tests.consolidation.approval_stamps import restamp_log_at_lane_tips

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# 1. Driver unit -- direct body call + one subprocess-shell call.
# ---------------------------------------------------------------------------


def test_driver_null_target_never_beats_assigned_mission_side(tmp_path: Path) -> None:
    """Regression case (#4900): ours (target) null, theirs (mission) 1 -> must be 1.

    Pre-fix, ``mission_number`` was copied from ``ours`` whenever the key was
    merely *present* -- even ``null`` -- clobbering the mission-side value.
    """
    ours = tmp_path / "O_A"
    theirs = tmp_path / "O_B"
    ours.write_text('{"mission_number": null, "status": "accepted"}', encoding="utf-8")
    theirs.write_text('{"mission_slug": "m", "mission_number": 1}', encoding="utf-8")

    outcome = run_meta_driver(str(tmp_path / "O_BASE"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged = json.loads(ours.read_text())
    assert merged["mission_number"] == 1, (
        f"#4900 regression: an unassigned target mission_number (null) must never override an assigned mission-side value. Got {merged['mission_number']!r}."
    )


def test_driver_assigned_target_wins(tmp_path: Path) -> None:
    """Control: ours=3, theirs=1 -> 3 (an assigned target value is authoritative)."""
    ours = tmp_path / "O_A"
    theirs = tmp_path / "O_B"
    ours.write_text('{"mission_number": 3, "status": "accepted"}', encoding="utf-8")
    theirs.write_text('{"mission_slug": "m", "mission_number": 1}', encoding="utf-8")

    outcome = run_meta_driver(str(tmp_path / "O_BASE"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged = json.loads(ours.read_text())
    assert merged["mission_number"] == 3


def test_driver_missing_key_takes_mission_side(tmp_path: Path) -> None:
    """Control: the key is absent from ours -> theirs wins."""
    ours = tmp_path / "O_A"
    theirs = tmp_path / "O_B"
    ours.write_text('{"status": "accepted"}', encoding="utf-8")
    theirs.write_text('{"mission_slug": "m", "mission_number": 1}', encoding="utf-8")

    outcome = run_meta_driver(str(tmp_path / "O_BASE"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged = json.loads(ours.read_text())
    assert merged["mission_number"] == 1


def test_driver_zero_and_negative_target_are_also_unset(tmp_path: Path) -> None:
    """0 and negative target-side values are unassigned too (data-model.md)."""
    for bad_value in (0, -1):
        ours = tmp_path / f"O_A_{bad_value}"
        theirs = tmp_path / f"O_B_{bad_value}"
        ours.write_text(json.dumps({"mission_number": bad_value}), encoding="utf-8")
        theirs.write_text('{"mission_slug": "m", "mission_number": 5}', encoding="utf-8")

        outcome = run_meta_driver(str(tmp_path / f"O_BASE_{bad_value}"), str(ours), str(theirs))

        assert outcome == MergeDriverOutcome()
        merged = json.loads(ours.read_text())
        assert merged["mission_number"] == 5


def test_driver_via_subprocess_shell_null_target(tmp_path: Path) -> None:
    """Same regression case, invoked through the real ``merge-driver-meta`` subprocess shell."""
    import subprocess
    import sys

    base = tmp_path / "O_BASE"
    ours = tmp_path / "O_A"
    theirs = tmp_path / "O_B"
    base.write_text("{}", encoding="utf-8")
    ours.write_text('{"mission_number": null}', encoding="utf-8")
    theirs.write_text('{"mission_slug": "m", "mission_number": 1}', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "specify_cli", "merge-driver-meta", str(base), str(ours), str(theirs)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    merged = json.loads(ours.read_text())
    assert merged["mission_number"] == 1


# ---------------------------------------------------------------------------
# Canonical "assigned" leaf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, True),
        (1, True),
        (0, False),
        (-1, False),
        (True, False),
        (False, False),
        (None, False),
        ("3", False),
        (3.0, False),
    ],
)
def test_is_assigned_mission_number_leaf(value: object, expected: bool) -> None:
    assert is_assigned_mission_number(value) is expected


# ---------------------------------------------------------------------------
# 2/3. Sequential consolidates + hand-numbered target -- real CLI.
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _mission_number_merge_mocks(repo_root: Path):
    """Real mission-branch bake + real bookkeeping commit; only genuine
    external side effects mocked.

    Mirrors ``_real_bookkeeping_commit_external_mocks`` in
    ``tests.integration.test_merge_lane_planning_data_loss`` but leaves
    ``_bake_mission_number_into_mission_branch`` UNMOCKED (real) -- the whole
    point of these tests is to exercise the real mission-branch bake, the
    real squash + merge-driver reconciliation, and the real target-tree write
    + read-back. Done-marking stays mocked; every fixture mission here is
    LEGACY (no ``mission_id``), so the executor's own post-commit
    done/baseline asserts early-return regardless.
    """
    patches = [
        patch("specify_cli.consolidation.done_bookkeeping._mark_wp_merged_done"),
        patch("specify_cli.consolidation.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.consolidation.phase_finalize.run_check"),
        patch("specify_cli.consolidation.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.consolidate._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch("specify_cli.consolidation.phase_bookkeeping._classify_porcelain_lines", return_value=([], 0)),
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[6].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[7].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[2].return_value = stale_report
        ms[3].return_value = stale_report
        yield {}


def _bootstrap_lanes_mission(repo: Path, slug: str) -> None:
    """A minimal LANES-topology (no coord) mission: one code WP, approved."""
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, slug)  # legacy: no mission_id
    _write_lanes_manifest(feature_dir, slug, code_wp_ids=["WP01"], planning_wp_ids=[])
    _write_wp_file(feature_dir, "WP01")
    _seed_wp_approved(feature_dir, slug, "WP01")


def _cut_mission_and_lane_branches(repo: Path, slug: str, *, code_relpath: str) -> None:
    """Cut the mission + lane branches, THEN advance target's OWN copy of
    this mission's ``meta.json`` (an ``accept``-style ``status: accepted``
    stamp -- a real target-authoritative field, per
    ``_TARGET_AUTHORITATIVE_META_FIELDS``) so BOTH sides genuinely change the
    same path since the merge base by the time the squash runs.

    This is the real-world topology, not an artificial one: per the
    coord/primary-partition model, planning artifacts (``meta.json``)
    already live on the target/primary branch, and ``spec-kitty accept``
    stamps ``status: accepted`` there BEFORE ``spec-kitty consolidate`` ever
    runs -- while the mission/lane branches (cut earlier, during
    implementation) never see that later target-side edit. Without this, the
    mission branch is the ONLY side that changes ``meta.json`` relative to
    the fork point, git resolves the file trivially (fast-path, taking
    theirs), and ``merge-driver-meta`` is never invoked at all -- masking
    #4900 entirely (a merge driver only fires when BOTH sides changed the
    path since the merge base).
    """
    mission_branch = f"kitty/mission-{slug}"
    _git(repo, "branch", mission_branch, "main")
    lane_branch = f"kitty/mission-{slug}-lane-a"
    _git(repo, "branch", lane_branch, "main")
    _commit_file(
        repo,
        branch=lane_branch,
        relpath=code_relpath,
        content="x = 1\n",
        message=f"feat({slug}): WP01 approved code",
    )
    _git(repo, "checkout", "main")
    restamp_log_at_lane_tips(repo, repo / "kitty-specs" / slug)

    meta_path = repo / "kitty-specs" / slug / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status"] = "accepted"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", str(meta_path.relative_to(repo)))
    _git(repo, "commit", "-m", f"chore({slug}): accept (status: accepted, target-side)")


def _consolidate(repo: Path, slug: str) -> None:
    with _mission_number_merge_mocks(repo):
        _run_lane_based_consolidation(
            repo_root=repo,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )


def _target_meta(repo: Path, slug: str) -> dict[str, object]:
    text = _git(repo, "show", f"main:kitty-specs/{slug}/meta.json").stdout
    return json.loads(text)


def test_sequential_consolidates_record_1_then_2_on_target(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Consolidating mission A then mission B records 1 and 2 on the
    target branch, matching the announced/printed numbers.

    #4900's exact reported shape, pre-fix: the
    pre-squash announcement prints 1 for BOTH missions, and the driver's
    "present wins, even null" rule clobbers each mission's assigned number
    back to null on the target -- so a second mission's scan over an
    all-null target also computes 1, not 2.
    """
    slug_a = "mission-4900-a"
    slug_b = "mission-4900-b"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug_a)
    _bootstrap_lanes_mission(tmp_path, slug_b)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap both missions")

    _cut_mission_and_lane_branches(tmp_path, slug_a, code_relpath="src/mission_a.py")
    _cut_mission_and_lane_branches(tmp_path, slug_b, code_relpath="src/mission_b.py")

    _consolidate(tmp_path, slug_a)
    meta_a = _target_meta(tmp_path, slug_a)
    assert meta_a.get("mission_number") == 1, (
        f"#4900 regression: mission {slug_a} should be recorded as mission_number=1 on the target branch. Got {meta_a.get('mission_number')!r}."
    )
    # The announced line must equal what
    # actually landed on the target, printed exactly once.
    output_a = capsys.readouterr().out
    assert output_a.count("Assigned mission_number=1") == 1, f"expected exactly one 'Assigned mission_number=1' line, got: {output_a!r}"

    _consolidate(tmp_path, slug_b)
    meta_b = _target_meta(tmp_path, slug_b)
    assert meta_b.get("mission_number") == 2, (
        f"#4900 regression: mission {slug_b}, consolidated second, should be "
        f"recorded as mission_number=2 on the target branch (mission A is 1). "
        f"Got {meta_b.get('mission_number')!r}."
    )
    output_b = capsys.readouterr().out
    assert output_b.count("Assigned mission_number=2") == 1, f"expected exactly one 'Assigned mission_number=2' line, got: {output_b!r}"

    # meta_a must still read 1 after mission B's consolidate (no cross-talk).
    meta_a_after = _target_meta(tmp_path, slug_a)
    assert meta_a_after.get("mission_number") == 1


def test_hand_numbered_target_gives_next_mission_8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A target with a hand-numbered mission (7) gives the next mission 8."""
    slug_existing = "mission-4900-existing"
    slug_new = "mission-4900-new"
    _init_git_repo(tmp_path)

    # A hand-numbered, already-merged mission directly on target.
    existing_dir = tmp_path / "kitty-specs" / slug_existing
    existing_dir.mkdir(parents=True)
    (existing_dir / "meta.json").write_text(
        json.dumps({"mission_slug": slug_existing, "mission_number": 7}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "hand-number existing mission at 7")

    _bootstrap_lanes_mission(tmp_path, slug_new)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap new mission")
    _cut_mission_and_lane_branches(tmp_path, slug_new, code_relpath="src/mission_new.py")

    _consolidate(tmp_path, slug_new)

    meta_new = _target_meta(tmp_path, slug_new)
    assert meta_new.get("mission_number") == 8, (
        f"#4900 regression: with a hand-numbered mission at 7 already on the target, the next consolidation must record 8. Got {meta_new.get('mission_number')!r}."
    )
    output = capsys.readouterr().out
    assert output.count("Assigned mission_number=8") == 1, f"expected exactly one 'Assigned mission_number=8' line, got: {output!r}"


def test_target_already_assigned_wins_over_stale_mission_branch_value(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Target wins: target already carries mission_number=3; the
    mission branch independently carries a STALE mission_number=5 (as if an
    earlier, now-superseded attempt wrote it there before target's own
    correct value was assigned). Consolidation must record 3, never
    overwrite it with the mission branch's 5.
    """
    slug = "mission-4900-target-wins"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap target-wins mission")

    mission_branch = f"kitty/mission-{slug}"
    _git(tmp_path, "branch", mission_branch, "main")
    lane_branch = f"kitty/mission-{slug}-lane-a"
    _git(tmp_path, "branch", lane_branch, "main")
    _commit_file(
        tmp_path,
        branch=lane_branch,
        relpath="src/target_wins.py",
        content="x = 1\n",
        message=f"feat({slug}): WP01 approved code",
    )

    # The mission branch independently carries a STALE mission_number=5.
    _git(tmp_path, "checkout", mission_branch)
    mission_meta_path = tmp_path / "kitty-specs" / slug / "meta.json"
    mission_meta = json.loads(mission_meta_path.read_text(encoding="utf-8"))
    mission_meta["mission_number"] = 5
    mission_meta_path.write_text(json.dumps(mission_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(tmp_path, "add", str(mission_meta_path.relative_to(tmp_path)))
    _git(tmp_path, "commit", "-m", f"chore({slug}): stale mission_number=5 on mission branch")

    # target's OWN copy already carries the CORRECT, authoritative value (3),
    # plus the accept-style edit so both sides genuinely diverge for the
    # squash driver.
    _git(tmp_path, "checkout", "main")
    restamp_log_at_lane_tips(tmp_path, tmp_path / "kitty-specs" / slug)
    target_meta_path = tmp_path / "kitty-specs" / slug / "meta.json"
    target_meta = json.loads(target_meta_path.read_text(encoding="utf-8"))
    target_meta["mission_number"] = 3
    target_meta["status"] = "accepted"
    target_meta_path.write_text(json.dumps(target_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(tmp_path, "add", str(target_meta_path.relative_to(tmp_path)))
    _git(tmp_path, "commit", "-m", f"chore({slug}): target already assigned mission_number=3")

    _consolidate(tmp_path, slug)

    meta = _target_meta(tmp_path, slug)
    assert meta.get("mission_number") == 3, (
        f"#4900 regression: the target already had mission_number=3; a stale mission-branch value (5) must never overwrite it. Got {meta.get('mission_number')!r}."
    )
    output = capsys.readouterr().out
    assert "Assigned mission_number=3" in output
    assert "mission_number=5" not in output


# ---------------------------------------------------------------------------
# 4. Fault-injected read-back mismatch.
# ---------------------------------------------------------------------------


def test_readback_mismatch_exits_nonzero_and_never_prints_false_assigned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A mismatched read-back must exit non-zero, name expected vs
    recorded, and never print a false "Assigned mission_number=" line.

    The merge driver runs as a SEPARATE subprocess, so patching ``drivers``
    in this test process has no effect on it. Instead this injects the fault
    in-process at the read seam :func:`baseline._read_committed_meta_json`
    (the same seam :func:`assert_baseline_merge_commit_on_target` and
    ``assert_mission_number_on_target`` both use) -- the mission is LEGACY
    (no ``mission_id``), so the baseline assert never calls this seam and
    only the mission_number assert is exercised.
    """
    slug = "mission-4900-mismatch"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap mismatch mission")
    _cut_mission_and_lane_branches(tmp_path, slug, code_relpath="src/mismatch.py")

    def _fake_read_committed_meta_json(main_repo, target_branch, meta_rel, mission_slug):  # noqa: ANN001
        return {"mission_number": 999}

    with (
        _mission_number_merge_mocks(tmp_path),
        patch(
            "specify_cli.consolidation.baseline._read_committed_meta_json",
            side_effect=_fake_read_committed_meta_json,
        ),
        pytest.raises(typer.Exit),
    ):
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    output = capsys.readouterr().out
    assert "Error:" in output
    assert "999" in output, output
    # The expected number and the remedy (--resume / git show) must
    # both be named, not just the recorded (wrong) value.
    assert "expected 1" in output, f"expected number (1) not named in error output: {output!r}"
    assert f"consolidate --mission {slug} --resume" in output, f"the --resume remedy is not named in error output: {output!r}"
    assert f"git show main:kitty-specs/{slug}/meta.json" in output, f"the git show remedy is not named in error output: {output!r}"
    assert "Assigned" not in output, (
        f"#4900 regression: a false 'Assigned mission_number=' line was printed even though read-back verification failed. Output: {output!r}"
    )


def test_resume_after_readback_failure_reverifies_and_records_correctly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A read-back failure on the FIRST run must not silently
    stick. ``consolidate --resume`` must re-verify and either record the
    correct number on the target or exit non-zero -- it must never exit 0
    with a null or wrong number on the target. Exercises the executor
    fallback (``_resolve_expected_mission_number``) and
    ``baseline.read_mission_number_from_ref`` on the resumed run.
    """
    slug = "mission-4900-resume"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap resume mission")
    _cut_mission_and_lane_branches(tmp_path, slug, code_relpath="src/resume.py")

    def _fake_read_committed_meta_json(main_repo, target_branch, meta_rel, mission_slug):  # noqa: ANN001
        return {"mission_number": 999}

    # First run: read-back verification fails (injected fault). The actual
    # commit underneath is real and correct -- only the VERIFICATION read is
    # faked, mirroring a corrupted read/transient failure rather than a
    # genuinely bad write.
    with (
        _mission_number_merge_mocks(tmp_path),
        patch(
            "specify_cli.consolidation.baseline._read_committed_meta_json",
            side_effect=_fake_read_committed_meta_json,
        ),
        pytest.raises(typer.Exit),
    ):
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )
    capsys.readouterr()  # discard first-run output

    # Second run: real ``--resume`` (same call; resumability is driven by the
    # persisted ConsolidationState, not an explicit flag), no fault injected.
    try:
        _consolidate(tmp_path, slug)
    except typer.Exit as exc:
        assert exc.exit_code != 0, "resume must never exit 0 without a truthful record"
    else:
        meta = _target_meta(tmp_path, slug)
        assert meta.get("mission_number") not in (None, 999), (
            f"resume regression: target mission_number must never be null or the "
            f"injected-mismatch value after a successful resume. Got {meta.get('mission_number')!r}."
        )
        assert meta.get("mission_number") == 1, (
            f"resume must re-derive and record the correct mission_number (1) on the target. Got {meta.get('mission_number')!r}."
        )
        output = capsys.readouterr().out
        assert output.count("Assigned mission_number=1") == 1, f"expected exactly one 'Assigned mission_number=1' line on resume, got: {output!r}"


# ---------------------------------------------------------------------------
# Direct unit coverage: baseline.read_mission_number_from_ref.
# ---------------------------------------------------------------------------


def test_read_mission_number_from_ref_assigned(tmp_path: Path) -> None:
    from specify_cli.consolidation.baseline import read_mission_number_from_ref

    _init_git_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": "m", "mission_number": 4}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "seed m with mission_number=4")

    assert read_mission_number_from_ref(tmp_path, "main", "m") == 4


def test_read_mission_number_from_ref_null(tmp_path: Path) -> None:
    from specify_cli.consolidation.baseline import read_mission_number_from_ref

    _init_git_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": "m", "mission_number": None}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "seed m with mission_number=null")

    assert read_mission_number_from_ref(tmp_path, "main", "m") is None


def test_read_mission_number_from_ref_unreadable_ref(tmp_path: Path) -> None:
    from specify_cli.consolidation.baseline import read_mission_number_from_ref

    _init_git_repo(tmp_path)

    assert read_mission_number_from_ref(tmp_path, "no-such-branch", "m") is None


# ---------------------------------------------------------------------------
# A mission-branch write failure must not discard the number.
# ---------------------------------------------------------------------------


def _failing_numwrite_worktree_add(real_run):  # noqa: ANN001, ANN202 -- test double factory
    """Wrap ``subprocess.run`` so ONLY the mission-branch bake's detached
    ``git worktree add`` (the ``kitty-numwrite-`` temp dir) fails; every other
    call (the target scan worktree, the squash, the merge driver, the
    bookkeeping commit) runs for real."""

    def _run(args, *a, **kw):  # noqa: ANN001, ANN002, ANN003, ANN202
        if isinstance(args, list) and args[:4] == ["git", "worktree", "add", "--detach"] and "kitty-numwrite-" in str(args[4]):
            return subprocess.CompletedProcess(args, 128, stdout="", stderr="fatal: injected worktree-add failure")
        return real_run(args, *a, **kw)

    return _run


def test_mission_branch_write_failure_still_records_number_on_target(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When the mission-branch write fails (``git worktree add``
    refused), the already-computed ``next_number`` must still be written onto
    the TARGET tree and read back -- never discarded so the consolidation exits
    0 with ``mission_number: null`` on the target."""
    slug = "mission-4900-branch-write-fails"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap branch-write-failure mission")
    _cut_mission_and_lane_branches(tmp_path, slug, code_relpath="src/branch_write_fails.py")

    with patch("subprocess.run", side_effect=_failing_numwrite_worktree_add(subprocess.run)):
        _consolidate(tmp_path, slug)

    meta = _target_meta(tmp_path, slug)
    assert meta.get("mission_number") == 1, (
        f"#4900 regression: a failed mission-branch write discarded the computed mission_number; target carries {meta.get('mission_number')!r}."
    )
    output = capsys.readouterr().out
    assert output.count("Assigned mission_number=1") == 1, output


def test_unassignable_mission_number_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When no number can be determined at all (the bake refuses the
    assignment), the consolidation surfaces it and exits non-zero instead of
    finishing with ``mission_number: null``."""
    from specify_cli.consolidation.baseline import MissionNumberVerificationError

    slug = "mission-4900-unassignable"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap unassignable mission")
    _cut_mission_and_lane_branches(tmp_path, slug, code_relpath="src/unassignable.py")

    refusal = MissionNumberVerificationError(f"cannot determine a mission_number for {slug!r}")
    with (
        patch("specify_cli.consolidation.phase_advance._bake_mission_number_into_mission_branch", side_effect=refusal),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _consolidate(tmp_path, slug)

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Error:" in output
    assert "cannot determine a mission_number" in output
    assert "Assigned" not in output


# ---------------------------------------------------------------------------
# The target-tree write/read must never fabricate or crash raw.
# ---------------------------------------------------------------------------


def _main_sha(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _assert_restored_to_pre_run(repo: Path, meta_path: Path, pre_run_meta: bytes, pre_run_main: str) -> None:
    """The rollback door restored ``main`` and its meta.json to the pre-run state -- never a stub."""
    restored = meta_path.read_bytes()
    assert restored == pre_run_meta, f"meta.json must be restored to its pre-run bytes; got {restored!r}"
    assert len(json.loads(restored)) > 1, "a one-key stub meta.json was fabricated"
    assert _main_sha(repo) == pre_run_main, "main must be rolled back to its pre-run tip"


def test_absent_target_meta_refuses_instead_of_fabricating(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """If the target meta.json is absent when the number is written onto
    the target tree, refuse (``Error:`` + exit 1) and never write a one-key
    ``{"mission_number": N}`` stub meta.json.

    The refusal is a post-mutation exit, so the single rollback door (#5385)
    restores the target to its pre-run tip: meta.json is back to its pre-run
    bytes (not the pre-phase bytes, which already carry the baked number)."""

    slug = "mission-4900-absent-target-meta"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap absent-target-meta mission")
    _cut_mission_and_lane_branches(tmp_path, slug, code_relpath="src/absent_meta.py")

    meta_path = tmp_path / "kitty-specs" / slug / "meta.json"
    pre_run_meta, pre_run_main = meta_path.read_bytes(), _main_sha(tmp_path)
    real_read = phase_bookkeeping._read_target_tree_mission_number

    def _delete_then_read(target_feature_dir: Path) -> int | None:
        original_bytes.append(meta_path.read_bytes())
        meta_path.unlink()
        return real_read(target_feature_dir)

    original_bytes: list[bytes] = []
    with (
        _mission_number_merge_mocks(tmp_path),
        patch.object(phase_bookkeeping, "_read_target_tree_mission_number", side_effect=_delete_then_read),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Error:" in output
    assert "Assigned" not in output
    assert original_bytes, "the injected target-tree read must have run"
    _assert_restored_to_pre_run(tmp_path, meta_path, pre_run_meta, pre_run_main)


def test_corrupt_target_meta_restores_and_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A corrupt target meta.json surfacing ``MissionMetaReadError`` from the
    target-tree mission_number read exits 1 with ``Error:``, not a raw traceback,
    and the single rollback door (#5385) restores the target to its pre-run tip:
    meta.json is back to its pre-run bytes."""

    slug = "mission-4900-corrupt-target-meta"
    _init_git_repo(tmp_path)
    _bootstrap_lanes_mission(tmp_path, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "bootstrap corrupt-target-meta mission")
    _cut_mission_and_lane_branches(tmp_path, slug, code_relpath="src/corrupt_meta.py")

    meta_path = tmp_path / "kitty-specs" / slug / "meta.json"
    pre_run_meta, pre_run_main = meta_path.read_bytes(), _main_sha(tmp_path)
    real_read = phase_bookkeeping._read_target_tree_mission_number
    original_bytes: list[bytes] = []

    def _corrupt_then_read(target_feature_dir: Path) -> int | None:
        original_bytes.append(meta_path.read_bytes())
        meta_path.write_text("{not json", encoding="utf-8")
        return real_read(target_feature_dir)

    with (
        _mission_number_merge_mocks(tmp_path),
        patch.object(phase_bookkeeping, "_read_target_tree_mission_number", side_effect=_corrupt_then_read),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Error:" in output
    assert "Assigned" not in output
    assert original_bytes, "the injected target-tree read must have run"
    _assert_restored_to_pre_run(tmp_path, meta_path, pre_run_meta, pre_run_main)


# ---------------------------------------------------------------------------
# The planning-only path announces only AFTER read-back.
# ---------------------------------------------------------------------------


def _bootstrap_planning_only_mission(repo: Path, slug: str) -> None:
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, slug)  # legacy: no mission_id, mission_number null
    _write_lanes_manifest(feature_dir, slug, code_wp_ids=[], planning_wp_ids=["WP01"])
    _write_wp_file(feature_dir, "WP01")
    _seed_wp_approved(feature_dir, slug, "WP01")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({slug}): bootstrap planning-only mission")


def test_planning_only_readback_failure_never_prints_assigned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """On the planning-only closeout the "Assigned" line must
    not print before the target read-back verification; a failed read-back
    exits non-zero with no "Assigned" line at all."""
    slug = "mission-4900-planning-only-mismatch"
    _init_git_repo(tmp_path)
    _bootstrap_planning_only_mission(tmp_path, slug)

    def _fake_read_committed_meta_json(main_repo, target_branch, meta_rel, mission_slug):  # noqa: ANN001
        return {"mission_number": 999}

    with (
        _mission_number_merge_mocks(tmp_path),
        patch(
            "specify_cli.consolidation.baseline._read_committed_meta_json",
            side_effect=_fake_read_committed_meta_json,
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _consolidate_unwrapped(tmp_path, slug)

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Error:" in output
    assert "999" in output
    assert "Assigned" not in output, f"planning-only path printed an unverified 'Assigned' line: {output!r}"


def test_planning_only_announces_once_after_verification(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Control: the planning-only closeout records the number
    on the target and announces it exactly once (after verification)."""
    slug = "mission-4900-planning-only-ok"
    _init_git_repo(tmp_path)
    _bootstrap_planning_only_mission(tmp_path, slug)

    _consolidate(tmp_path, slug)

    assert _target_meta(tmp_path, slug).get("mission_number") == 1
    output = capsys.readouterr().out
    assert output.count("Assigned mission_number=1") == 1, output


def _consolidate_unwrapped(repo: Path, slug: str) -> None:
    _run_lane_based_consolidation(
        repo_root=repo,
        mission_slug=slug,
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=MergeStrategy.SQUASH,
        allow_sparse_checkout=True,
    )
