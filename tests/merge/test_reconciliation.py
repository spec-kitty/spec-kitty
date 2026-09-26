"""Unit tests for the Terminus Reconciliation Gate (WP06 / S-D, #5001).

Every test drives REAL on-disk git — ``git``/``subprocess`` is NEVER mocked (RN-Q3
/ contract §"Property test"), so the verifier's reachability + patch-id probes run
for real. Approved commit SHAs are always sourced from lane-branch git tips, never
status rows. The claim-integrity tests build a real coordination mission (meta +
lanes.json + status log) so the Lamport membership path
(``materialize_snapshot``) is exercised end to end.

Covers:
* T025 verifier — PASS / FAIL(missing|excluded) / REFUSE(fail-closed); FAIL never
  mutates; non-vacuous excluded check even with an empty canceled set; bounded
  (window-scoped) excluded scan (NFR-003).
* T027 claim — lane-tip sourcing, Lamport membership (a committed rejection is
  honored and the builder never touches LWW ``reduce_parsed``), fail-closed on an
  unmaterializable surface / a claim empty against a populated manifest.
* T028 git probes — reachability, patch-id equivalence across a cherry-pick,
  ancestry→tree-equality integration under squash.
* FR-012 legacy detection (refuse a resumed pre-fix state, no auto-heal).
* NFR-005 non-vacuous call-site allowlist + self-mutation (a 7th path fails).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.merge import git_probes
from specify_cli.merge.reconciliation import (
    TERMINUS_ENTRY_POINTS,
    ApprovedWpCommitSet,
    Divergence,
    MergeOutcomeVerifier,
    UnroutedTerminusPathError,
    VerifyResult,
    VerifyStatus,
    build_approved_wp_set,
    clear_post_fix_marker,
    detect_legacy_in_flight_state,
    route_terminus,
    write_post_fix_marker,
)

pytestmark = [pytest.mark.git_repo]

_MISSION_SLUG = "terminus-recon-01M5001Z"
_MISSION_ID = "01M5001Z" + "0" * 18  # 26-char ULID-shaped id
_TARGET = "main"

_APPROVE_CHAIN: tuple[tuple[str, str], ...] = (
    ("planned", "claimed"),
    ("claimed", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
    ("in_review", "approved"),
)


# --------------------------------------------------------------------------- #
# real-git helpers (no mocking)
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-qb", _TARGET, str(repo)], check=True)
    _git(repo, "config", "user.email", "t@t.co")
    _git(repo, "config", "user.name", "Recon Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    return repo


def _lane_commit(repo: Path, base: str, branch: str, filename: str, body: str) -> str:
    """Cut *branch* from *base*, add a real commit, return its SHA (leaves HEAD on target)."""
    _git(repo, "branch", branch, base)
    _git(repo, "checkout", "-q", branch)
    path = repo / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _git(repo, "add", str(path))
    _git(repo, "commit", "-qm", f"feat: {filename}")
    sha = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", _TARGET)
    return sha


# --------------------------------------------------------------------------- #
# git_probes (T028)
# --------------------------------------------------------------------------- #


def test_sha_reachable_from_true_after_merge(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    assert git_probes.sha_reachable_from(repo, sha, _TARGET) is False
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    assert git_probes.sha_reachable_from(repo, sha, _TARGET) is True


def test_sha_reachable_from_fails_closed_on_empty_or_bad(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert git_probes.sha_reachable_from(repo, "", _TARGET) is False
    assert git_probes.sha_reachable_from(repo, "deadbeef" * 5, _TARGET) is False


def test_patch_id_equivalence_across_cherry_pick(tmp_path: Path) -> None:
    """A cherry-picked copy has a DIFFERENT sha but the SAME patch-id (RN-F4)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    original = _lane_commit(repo, base, "lane-a", "leak.py", "leaked\n")
    # Carrier has its OWN preceding commit, so cherry-picking the same diff lands
    # on a different parent -> new sha, identical patch-id.
    _git(repo, "branch", "carrier", base)
    _git(repo, "checkout", "-q", "carrier")
    (repo / "carrier.py").write_text("carrier\n", encoding="utf-8")
    _git(repo, "add", "carrier.py")
    _git(repo, "commit", "-qm", "carrier own work")
    _git(repo, "cherry-pick", original)
    copy_sha = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", _TARGET)
    assert copy_sha != original
    assert git_probes.patch_id_of(repo, original) == git_probes.patch_id_of(repo, copy_sha)
    assert git_probes.patch_id_of(repo, original) != ""


def test_patch_id_of_merge_commit_is_empty(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    _lane_commit(repo, base, "lane-b", "b.py", "B\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    merge_sha = _git(repo, "merge", "-q", "--no-edit", "--no-ff", "lane-b") or _rev(repo, "HEAD")
    # The no-ff merge commit carries no standalone diff -> empty patch-id.
    assert git_probes.patch_id_of(repo, _rev(repo, "HEAD")) == ""
    assert merge_sha is not None


def test_patch_id_of_raises_on_git_error(tmp_path: Path) -> None:
    """#5001 fail-closed-on-error: a NON-ZERO ``git show`` exit (bogus sha) is a
    git ERROR, not a legitimate empty patch-id, and must raise ``GitProbeError``
    so callers (``patch_ids_in_range``, ``_collect_excluded``, ``_collect_authored``,
    the closed-world scan) REFUSE/propagate instead of silently treating the
    errored probe as "no content" and skipping it."""
    repo = _init_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.patch_id_of(repo, "deadbeef" * 5)


def test_patch_id_of_empty_but_successful_output_still_returns_empty_string(
    tmp_path: Path,
) -> None:
    """A merge commit's ``git show`` EXITS 0 with an empty diff -> ``git patch-id``
    legitimately produces no fields. That is NOT a git error and must keep
    returning ``""`` rather than raising (the empty-but-successful case the fix
    must not disturb)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    _lane_commit(repo, base, "lane-b", "b.py", "B\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "--no-ff", "lane-b")
    assert git_probes.patch_id_of(repo, _rev(repo, "HEAD")) == ""


def test_changed_paths_of_raises_on_git_error(tmp_path: Path) -> None:
    """Same fail-closed-on-error distinction as ``patch_id_of``: a NON-ZERO
    ``git show --name-only`` exit (bogus sha) must raise ``GitProbeError`` so the
    closed-world content check (``_commit_is_content``) REFUSEs instead of
    treating the errored probe as "no changed paths" (never content) and
    silently skipping an un-attributable content commit whose probe errored."""
    repo = _init_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.changed_paths_of(repo, "deadbeef" * 5)


def test_changed_paths_of_empty_but_successful_output_still_returns_empty_list(
    tmp_path: Path,
) -> None:
    """A real commit that genuinely changes no files (``--allow-empty``) EXITS 0
    with no ``--name-only`` output. That is NOT a git error and must keep
    returning ``[]`` rather than raising."""
    repo = _init_repo(tmp_path)
    _git(repo, "commit", "--allow-empty", "-qm", "empty commit, no file changes")
    assert git_probes.changed_paths_of(repo, _rev(repo, "HEAD")) == []


def test_lane_integrated_by_tree_or_ancestry_squash(tmp_path: Path) -> None:
    """Squash breaks ancestry but the tree-equality axis still proves integration."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    _lane_commit(repo, base, "kitty/mission-x-lane-a", "a.py", "A\n")
    # mission branch carries the lane; squash-merge it into target.
    _git(repo, "branch", "kitty/mission-x", base)
    _git(repo, "checkout", "-q", "kitty/mission-x")
    _git(repo, "merge", "-q", "--no-edit", "kitty/mission-x-lane-a")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--squash", "kitty/mission-x")
    _git(repo, "commit", "-qm", "squash mission")
    # Ancestry alone is false (squash), but the combined probe is true (tree-equal).
    assert git_probes._lane_already_integrated(repo, "kitty/mission-x", _TARGET) is False
    assert git_probes.lane_integrated_by_tree_or_ancestry(repo, "kitty/mission-x", _TARGET) is True


# --------------------------------------------------------------------------- #
# MergeOutcomeVerifier (T025)
# --------------------------------------------------------------------------- #


def test_verify_passes_when_approved_reachable_and_nothing_excluded(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = ApprovedWpCommitSet(
        approved={"WP01": (sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.PASS
    assert result.is_pass


def test_verify_fails_when_approved_sha_unreachable(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")  # NOT merged into target
    claim = ApprovedWpCommitSet(
        approved={"WP01": (sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert result.divergence.missing_approved == (("WP01", sha),)


def test_verify_fails_when_excluded_sha_reachable(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    approved = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    excluded = _lane_commit(repo, base, "lane-cancel", "leak.py", "leaked\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "lane-cancel")  # excluded content rides in
    claim = ApprovedWpCommitSet(
        approved={"WP01": (approved,)},
        excluded_shas=frozenset({excluded}),
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(sha == excluded for sha, _pid in result.divergence.reachable_excluded)


def test_verify_fails_on_excluded_patch_id_from_relettered_copy(tmp_path: Path) -> None:
    """A cherry-picked (re-lettered) copy of canceled code is caught by patch-id."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    pre_target = _rev(repo, _TARGET)
    original = _lane_commit(repo, base, "lane-cancel", "leak.py", "leaked\n")
    canceled_pid = git_probes.patch_id_of(repo, original)
    # Advance target with unrelated work so the cherry-pick lands on a different
    # parent -> a DIFFERENT sha carrying the SAME diff (re-lettered copy).
    (repo / "filler.py").write_text("filler\n", encoding="utf-8")
    _git(repo, "add", "filler.py")
    _git(repo, "commit", "-qm", "unrelated target work")
    _git(repo, "cherry-pick", original)  # HEAD is target
    relettered = _rev(repo, _TARGET)
    assert relettered != original
    claim = ApprovedWpCommitSet(
        approved={},
        excluded_patch_ids=frozenset({canceled_pid}),
        excluded_window_base=pre_target,
        manifest_wp_ids=frozenset(),  # empty manifest -> not vacuous-refuse
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(pid == canceled_pid for _sha, pid in result.divergence.reachable_excluded)


def test_verify_never_mutates_on_fail(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    missing = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    target_before = _rev(repo, _TARGET)
    reflog_before = _git(repo, "reflog", "--format=%H")
    claim = ApprovedWpCommitSet(approved={"WP01": (missing,)}, manifest_wp_ids=frozenset({"WP01"}))
    MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert _rev(repo, _TARGET) == target_before
    assert _git(repo, "reflog", "--format=%H") == reflog_before


def test_verify_refuses_when_surface_unresolved(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    claim = ApprovedWpCommitSet(surface_resolved=False, manifest_wp_ids=frozenset({"WP01"}))
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_verify_refuses_on_explicit_claim_refusal(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    claim = ApprovedWpCommitSet(refusal="materialization boom")
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert "boom" in (result.refusal_reason or "")


def test_verify_refuses_when_claim_empty_but_manifest_lists_wps(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    claim = ApprovedWpCommitSet(approved={}, manifest_wp_ids=frozenset({"WP01", "WP02"}))
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE


def test_excluded_check_is_nonvacuous_when_canceled_set_empty(tmp_path: Path) -> None:
    """Positive control: an empty canceled set never false-positives, and the
    SAME planted commit added to the excluded set DOES fire (no silent no-op)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    pre_target = _rev(repo, _TARGET)
    approved = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    planted = _lane_commit(repo, base, "lane-cancel", "leak.py", "leaked\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "lane-cancel")
    planted_pid = git_probes.patch_id_of(repo, planted)

    # empty excluded set -> PASS (no false positive), but the primitive CAN see it.
    empty_claim = ApprovedWpCommitSet(
        approved={"WP01": (approved,)},
        excluded_window_base=pre_target,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, empty_claim).is_pass
    assert planted_pid in git_probes.patch_ids_in_range(repo, pre_target, _TARGET)

    # same planted patch-id in the excluded set -> FAIL (detector is real).
    firing_claim = ApprovedWpCommitSet(
        approved={"WP01": (approved,)},
        excluded_patch_ids=frozenset({planted_pid}),
        excluded_window_base=pre_target,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, firing_claim).status is VerifyStatus.FAIL


def test_excluded_patch_id_scan_is_window_bounded(tmp_path: Path) -> None:
    """NFR-003: the patch-id scan is bounded to base..target — an excluded
    patch-id already present BELOW the window base is not re-scanned."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    old_leak = _lane_commit(repo, base, "lane-old", "old.py", "old\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-old")  # lands BEFORE the window
    window_base = _rev(repo, _TARGET)  # window starts here, after old_leak
    approved = _lane_commit(repo, window_base, "lane-a", "a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    old_pid = git_probes.patch_id_of(repo, old_leak)
    claim = ApprovedWpCommitSet(
        approved={"WP01": (approved,)},
        excluded_patch_ids=frozenset({old_pid}),
        excluded_window_base=window_base,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    # old_pid is reachable overall, but OUTSIDE the window -> not flagged.
    assert old_pid not in git_probes.patch_ids_in_range(repo, window_base, _TARGET)
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_verify_reachability_false_defers_content_but_keeps_integrity(tmp_path: Path) -> None:
    """Squash mode (``verify_reachability=False``): CONTENT reachability is
    deferred (an approved SHA that is not reachable never false-fails under
    squash, though it FAILs under merge), but ALL fail-closed claim-integrity
    guards STILL apply — including the empty-claim-vs-populated-manifest (PP-F3)
    guard, which pre-fix was bypassed under squash (#5001 pre-merge FOLD-1)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    unreached = _lane_commit(repo, base, "lane-a", "a.py", "A\n")  # NOT merged into target
    # A NON-vacuous claim whose approved SHA is unreachable: squash defers the
    # content check -> PASS; the identical claim under merge FAILs (proving the
    # content axis genuinely ran and was genuinely deferred, not silently skipped).
    deferred = ApprovedWpCommitSet(
        approved={"WP01": (unreached,)},
        manifest_wp_ids=frozenset({"WP01"}),
        verify_reachability=False,
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, deferred).is_pass
    assert MergeOutcomeVerifier(repo).verify(_TARGET, replace(deferred, verify_reachability=True)).status is VerifyStatus.FAIL
    # An unresolved surface still REFUSES under the deferred (squash) mode.
    unresolved = ApprovedWpCommitSet(
        surface_resolved=False,
        manifest_wp_ids=frozenset({"WP01"}),
        verify_reachability=False,
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, unresolved).status is VerifyStatus.REFUSE


def test_squash_refuses_vacuous_claim_against_populated_manifest(tmp_path: Path) -> None:
    """FOLD-1 (#5001 pre-merge): claim integrity is strategy-INDEPENDENT — an empty
    derived claim while the manifest lists WPs is a vacuous-pass risk (PP-F3) and
    must REFUSE for SQUASH too, not just merge/rebase. Pre-fix the squash
    early-return short-circuited to PASS before this guard ran."""
    repo = _init_repo(tmp_path)
    vacuous = ApprovedWpCommitSet(
        approved={},
        manifest_wp_ids=frozenset({"WP01", "WP02"}),
        verify_reachability=False,  # squash
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, vacuous)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_squash_refuses_on_explicit_refusal_and_unresolved_surface(tmp_path: Path) -> None:
    """The other two claim-integrity REFUSE guards (explicit refusal, unresolved
    surface) also fire under squash — they always sat above the early return, this
    pins that they stay strategy-independent alongside the hoisted vacuous check."""
    repo = _init_repo(tmp_path)
    explicit = ApprovedWpCommitSet(refusal="materialization boom", verify_reachability=False)
    assert MergeOutcomeVerifier(repo).verify(_TARGET, explicit).status is VerifyStatus.REFUSE
    unresolved = ApprovedWpCommitSet(surface_resolved=False, manifest_wp_ids=frozenset({"WP01"}), verify_reachability=False)
    assert MergeOutcomeVerifier(repo).verify(_TARGET, unresolved).status is VerifyStatus.REFUSE


def test_squash_passes_when_claim_integrity_holds(tmp_path: Path) -> None:
    """Positive control: a squash claim whose integrity holds (non-vacuous, surface
    resolved, no refusal) still PASSES — the hoisted guards never false-refuse a
    legitimate squash (NFR-004)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")  # unreachable, but content deferred
    claim = ApprovedWpCommitSet(
        approved={"WP01": (sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        verify_reachability=False,
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_verify_refuses_when_closed_world_window_base_unresolved(tmp_path: Path) -> None:
    """FOLD-3 (#5001 pre-merge): under a production (``enforce_closed_world``) claim
    on the reachability path, an unresolvable window base means the excluded +
    closed-world axes CANNOT be evaluated. Pre-fix they silently no-op'd to PASS
    (fail-OPEN); they must now REFUSE (fail-closed)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")  # approved reachable -> _missing passes
    claim = ApprovedWpCommitSet(
        approved={"WP01": (sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        enforce_closed_world=True,
        authored_shas=frozenset({sha}),
        excluded_window_base=None,  # unresolvable transaction-start target tip
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_verify_does_not_refuse_on_none_window_base_without_closed_world(tmp_path: Path) -> None:
    """Back-compat: a hand-built claim (``enforce_closed_world`` unset) with no
    window base keeps its pre-widening PASS — the new window-base REFUSE is scoped
    to production claims only."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = ApprovedWpCommitSet(
        approved={"WP01": (sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        excluded_window_base=None,
        # enforce_closed_world defaults False
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_verify_refuses_on_git_probe_error_in_window(tmp_path: Path) -> None:
    """FOLD-3 (#5001 pre-merge): a git error while scanning the merge window must
    REFUSE (fail-closed), not collapse to PASS. Drive it with a NON-None but
    unresolvable window base, so ``commits_in_range`` errors mid-verify."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = ApprovedWpCommitSet(
        approved={"WP01": (sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        enforce_closed_world=True,
        authored_shas=frozenset({sha}),
        excluded_window_base="deadbeef" * 5,  # non-None, unresolvable -> rev-list errors
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_commits_in_range_raises_on_git_error(tmp_path: Path) -> None:
    """FOLD-3: an unresolvable ref is a git ERROR — distinct from a genuinely empty
    range — and must raise ``GitProbeError`` so the verifier can REFUSE."""
    repo = _init_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.commits_in_range(repo, "no-such-ref-xyz", _TARGET)


def test_patch_ids_in_range_raises_on_git_error(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.patch_ids_in_range(repo, "no-such-ref-xyz", _TARGET)


def test_commits_in_range_empty_range_is_not_an_error(tmp_path: Path) -> None:
    """A genuinely-empty range (base == tip) returns ``[]`` and never raises."""
    repo = _init_repo(tmp_path)
    assert git_probes.commits_in_range(repo, _TARGET, _TARGET) == []
    assert git_probes.patch_ids_in_range(repo, _TARGET, _TARGET) == set()


def test_build_claim_tolerates_unresolvable_lane_probe(tmp_path: Path) -> None:
    """FOLD-3 scope guard: the fail-closed ``GitProbeError`` signal is for the
    VERIFIER window scan, NOT the claim builder. Claim building has always
    tolerated an unresolvable lane-tip range (a fully-canceled lane has no branch;
    some topologies cut the branch after this read), yielding no commits for that
    lane rather than turning a legitimate merge into a spurious refusal. This pins
    that the builder does NOT raise / does NOT emit a refusal on such a probe
    error (regression guard for the squash-merge flows that rely on it)."""
    repo, feature_dir, manifest, _coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
    # An unresolvable coord base makes the lane-tip ``commits_in_range`` error; the
    # builder must tolerate it (empty lane), never raise or emit a refusal claim.
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref="no-such-base-xyz")
    assert claim.refusal is None
    assert claim.surface_resolved is True
    assert claim.approved == {"WP01": ()}  # lane tolerated as empty, not a refusal


# --------------------------------------------------------------------------- #
# Closed-world excluded-commit axis (#4945/#4977/#4981) — a window content commit
# attributable to NO approved WP is a FAIL, even when it is NOT in the TRACKED
# canceled set (it rode a carrier lane in via a merge's second parent).
# --------------------------------------------------------------------------- #


def _plant_carrier_smuggled_commit(repo: Path, base: str) -> tuple[str, str, str]:
    """Approved lane-a + a REMOVED WP's commit merged INTO it, both landed on target.

    Mirrors the #4945/#4977/#4981 mechanism at the verify() level (no CLI): the
    removed commit is a SECOND parent of a merge on the carrier lane, so it is NOT
    on the carrier's first-parent authorship spine. Returns
    ``(approved_sha, smuggled_sha, smuggled_pid)``; leaves HEAD on the target with
    both contents reachable.
    """
    approved_sha = _lane_commit(repo, base, "lane-a", "src/wp01.py", "APPROVED\n")
    smuggled_sha = _lane_commit(repo, base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_pid = git_probes.patch_id_of(repo, smuggled_sha)
    # Carrier lane-a merges the removed commit IN (second parent), then both land.
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    _git(repo, "branch", "-qD", "lane-removed")
    return approved_sha, smuggled_sha, smuggled_pid


def test_closed_world_fails_on_unattributable_window_content(tmp_path: Path) -> None:
    """A content commit in the window belonging to no approved WP → FAIL (divergence),
    even though the TRACKED excluded set is empty. The approved content itself stays
    attributable (never sacrificed) and the smuggled commit is named."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    approved_sha, smuggled_sha, smuggled_pid = _plant_carrier_smuggled_commit(repo, base)
    claim = ApprovedWpCommitSet(
        approved={"WP01": (approved_sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        enforce_closed_world=True,
        authored_shas=frozenset({approved_sha}),
        authored_patch_ids=frozenset({git_probes.patch_id_of(repo, approved_sha)}),
        excluded_window_base=base,
        mission_slug=_MISSION_SLUG,
        planning_prefix=None,  # leak / approved both under src/ — pure content
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    named = result.divergence.unattributable_content
    assert any(sha == smuggled_sha or pid == smuggled_pid for sha, pid in named), named
    # The approved content is attributable — the gate never flags legitimate work.
    assert all(sha != approved_sha for sha, _pid in named)


def test_closed_world_passes_on_bookkeeping_only_window_commit(tmp_path: Path) -> None:
    """A window commit that touches ONLY the mission planning/status surface is
    spec-kitty housekeeping, not content — the closed-world axis never flags it, so
    a legitimate merge still PASSES (NFR-004: no false-fail)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    approved_sha = _lane_commit(repo, base, "lane-a", "src/wp01.py", "APPROVED\n")
    # A bookkeeping commit landing straight on the target (only planning-dir paths).
    book = repo / "kitty-specs" / _MISSION_SLUG
    book.mkdir(parents=True)
    (book / "status.json").write_text('{"ok": true}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "chore: record done transitions")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = ApprovedWpCommitSet(
        approved={"WP01": (approved_sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        enforce_closed_world=True,
        authored_shas=frozenset({approved_sha}),
        authored_patch_ids=frozenset({git_probes.patch_id_of(repo, approved_sha)}),
        excluded_window_base=base,
        mission_slug=_MISSION_SLUG,
        planning_prefix=f"kitty-specs/{_MISSION_SLUG}",
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_closed_world_off_preserves_pre_widening_pass(tmp_path: Path) -> None:
    """With ``enforce_closed_world`` unset (a hand-built claim), the exact divergent
    structure that FAILs above PASSES — the widening is opt-in, so every existing
    claim keeps its pre-widening behavior byte-for-byte."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    approved_sha, _smuggled_sha, _smuggled_pid = _plant_carrier_smuggled_commit(repo, base)
    claim = ApprovedWpCommitSet(
        approved={"WP01": (approved_sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        excluded_window_base=base,
        # enforce_closed_world defaults to False; authored_* empty.
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_build_claim_authorship_excludes_merged_in_second_parent(tmp_path: Path) -> None:
    """``build_approved_wp_set`` enables the closed-world axis and derives authorship
    from each approved lane's FIRST-PARENT spine — a commit the lane merged in from
    another branch (second parent) is NOT counted as approved authorship, so it is
    caught as un-attributable when it reaches the target."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    # Smuggle a removed WP's commit INTO the approved lane via a merge second parent.
    smuggled = _lane_commit(repo, coord_base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_pid = git_probes.patch_id_of(repo, smuggled)
    _git(repo, "checkout", "-q", lane_branch)
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert claim.enforce_closed_world is True
    assert claim.authored_patch_ids  # the approved WP's own commit is present
    assert smuggled_pid not in claim.authored_patch_ids
    assert smuggled not in claim.authored_shas


# --------------------------------------------------------------------------- #
# claim builder (T027) — real coordination mission
# --------------------------------------------------------------------------- #


def _now_iso() -> str:
    return now_utc_iso()


def _event(seq: int, wp: str, frm: str, to: str, *, at: str, lamport: int) -> dict[str, object]:
    return {
        "actor": "reviewer" if to == "approved" else "impl",
        "at": at,
        "event_id": f"01HXYZ{seq:020d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": _MISSION_SLUG,
        "force": False,
        "from_lane": frm,
        "reason": None,
        "review_ref": f"review-{wp}" if to == "approved" else None,
        "to_lane": to,
        "wp_id": wp,
        "lamport_clock": lamport,
    }


def _approve_events(seq_start: int, wp: str, *, day: int) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for i, (frm, to) in enumerate(_APPROVE_CHAIN, start=1):
        events.append(_event(seq_start + i, wp, frm, to, at=f"2026-01-{day:02d}T00:0{i}:00+00:00", lamport=i))
    return events


def _build_mission(
    tmp_path: Path,
    *,
    approved_wps: tuple[str, ...],
    extra_events: list[dict[str, object]] | None = None,
    manifest_wps: tuple[str, ...] | None = None,
) -> tuple[Path, Path, LanesManifest, str]:
    """Return (repo, feature_dir, lanes_manifest, coord_base_sha).

    Builds a real repo: an approved status log per WP, a lanes.json, and one lane
    branch per WP carrying a real commit beyond the coordination base.
    """
    repo = _init_repo(tmp_path)
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    manifest_wps = manifest_wps or approved_wps

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _MISSION_SLUG,
                "mission_id": _MISSION_ID,
                "mission_type": "software-dev",
                "target_branch": _TARGET,
            }
        ),
        encoding="utf-8",
    )

    lanes = [
        ExecutionLane(
            lane_id=f"lane-{chr(ord('a') + idx)}",
            wp_ids=(wp,),
            write_scope=(f"src/{wp.lower()}.py",),
            predicted_surfaces=("code",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for idx, wp in enumerate(manifest_wps)
    ]
    manifest = LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch=_TARGET,
        lanes=lanes,
        computed_at=_now_iso(),
        computed_from="recon-test",
    )

    events: list[dict[str, object]] = []
    seq = 0
    for day, wp in enumerate(approved_wps, start=1):
        events.extend(_approve_events(seq, wp, day=day))
        seq += 100
    if extra_events:
        events.extend(extra_events)
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )

    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap mission")
    coord_base = _rev(repo, "HEAD")

    # one lane branch per manifest WP, each with a real approved commit.
    for lane in manifest.lanes:
        branch = lane_branch_name(_MISSION_SLUG, lane.lane_id, planning_base_branch=_TARGET, mission_id=_MISSION_ID)
        for wp in lane.wp_ids:
            _lane_commit(repo, coord_base, branch, f"src/{wp.lower()}.py", f"# {wp}\n")
    return repo, feature_dir, manifest, coord_base


def test_build_claim_sources_shas_from_lane_tips(tmp_path: Path) -> None:
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01", "WP02"))
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert claim.surface_resolved
    assert set(claim.approved) == {"WP01", "WP02"}
    lane_of = {wp: lane.lane_id for lane in manifest.lanes for wp in lane.wp_ids}
    for wp, shas in claim.approved.items():
        assert shas, f"{wp} lane tip carried no approved commit"
        branch = lane_branch_name(
            _MISSION_SLUG,
            lane_of[wp],
            planning_base_branch=_TARGET,
            mission_id=_MISSION_ID,
        )
        assert set(shas) == set(git_probes.commits_in_range(repo, coord_base, branch))


def test_build_claim_excludes_committed_rejection_lamport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A WP walked to ``approved`` then ``canceled`` is NOT in the approved claim,
    and the builder never touches the LWW ``reduce_parsed`` path (C-002 / Lamport)."""
    # WP02: approve chain then a committed cancel (later in the log).
    cancel_events = [
        _event(9000, "WP02", "approved", "canceled", at="2026-02-01T00:00:00+00:00", lamport=6),
    ]
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01", "WP02"), extra_events=cancel_events)

    # If the builder used LWW reduce_parsed, this raise would surface.
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("build_approved_wp_set must use the Lamport wrapper, not reduce_parsed")

    monkeypatch.setattr("specify_cli.status.reducer.reduce_parsed", _boom)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert claim.surface_resolved
    assert "WP01" in claim.approved
    assert "WP02" not in claim.approved  # committed rejection honored


def test_build_claim_collects_excluded_from_canceled_lane_tips(tmp_path: Path) -> None:
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",), manifest_wps=("WP01", "WP02"))
    # WP02's lane tip carries a real commit; treat WP02 as canceled-with-provenance.
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    branch = lane_branch_name(_MISSION_SLUG, "lane-b", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    expected = set(git_probes.commits_in_range(repo, coord_base, branch))
    assert expected
    assert expected <= claim.excluded_shas
    assert claim.excluded_patch_ids  # patch-ids collected for equivalence matching


def test_build_claim_fail_closed_on_unmaterializable_surface(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    missing_dir = repo / "kitty-specs" / "does-not-exist"
    manifest = LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch=_TARGET,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/wp01.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=_now_iso(),
        computed_from="recon-test",
    )
    # No status events at all -> empty approved while the manifest lists WP01.
    claim = build_approved_wp_set(repo, missing_dir, manifest, coord_base_ref="HEAD")
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE


# --------------------------------------------------------------------------- #
# FR-012 legacy detection
# --------------------------------------------------------------------------- #


def test_legacy_detection_none_for_fresh_merge(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert detect_legacy_in_flight_state(repo, _MISSION_ID, is_resume=False) is None


def test_legacy_detection_refuses_resume_without_marker(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    message = detect_legacy_in_flight_state(repo, _MISSION_ID, is_resume=True)
    assert message is not None
    assert "--abort" in message


def test_legacy_detection_passes_resume_with_marker(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    write_post_fix_marker(repo, _MISSION_ID)
    assert detect_legacy_in_flight_state(repo, _MISSION_ID, is_resume=True) is None
    clear_post_fix_marker(repo, _MISSION_ID)
    assert detect_legacy_in_flight_state(repo, _MISSION_ID, is_resume=True) is not None


def test_clear_post_fix_marker_is_idempotent(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    clear_post_fix_marker(repo, _MISSION_ID)  # missing_ok -> no error
    write_post_fix_marker(repo, _MISSION_ID)
    clear_post_fix_marker(repo, _MISSION_ID)
    clear_post_fix_marker(repo, _MISSION_ID)


# --------------------------------------------------------------------------- #
# NFR-005 non-vacuous call-site allowlist + self-mutation
# --------------------------------------------------------------------------- #


def test_all_six_terminus_entry_points_route(tmp_path: Path) -> None:
    expected = {
        "merge",
        "merge --resume",
        "merge --abort",
        "upgrade",
        "agent issue-verdict",
        "doctor coordination --fix",
    }
    assert expected == TERMINUS_ENTRY_POINTS
    for entry in expected:
        route_terminus(entry)  # must not raise


def test_route_terminus_rejects_seventh_unrouted_path() -> None:
    """Self-mutation: a synthetic 7th terminus path must fail the gate."""
    unrouted = "merge --brand-new-flag"
    assert unrouted not in TERMINUS_ENTRY_POINTS
    with pytest.raises(UnroutedTerminusPathError):
        route_terminus(unrouted)


def test_terminus_allowlist_is_the_concrete_floor() -> None:
    """Shrink-only floor: exactly the six governed entry points, no more, no less."""
    assert len(TERMINUS_ENTRY_POINTS) == 6


# --------------------------------------------------------------------------- #
# value-object ergonomics
# --------------------------------------------------------------------------- #


def test_verify_result_recovery_guidance_covers_each_status() -> None:
    passed = VerifyResult.passed()
    assert passed.is_pass
    refused = VerifyResult.refused("surface gone")
    assert "surface gone" in refused.recovery_guidance()
    failed = VerifyResult.failed(Divergence(missing_approved=(("WP01", "abc1234567"),)))
    guidance = failed.recovery_guidance()
    assert "WP01" in guidance and "torn down" in guidance


def test_gate_phase_runs_before_teardown_in_executor_sequence() -> None:
    """Ordering guarantee: the reconciliation gate is called after the
    commit/assert phase and BEFORE any cleanup/teardown or push in the linear
    phase caller (contract §"Ordering guarantee")."""
    import inspect

    from specify_cli.merge import executor

    source = inspect.getsource(executor._run_lane_based_merge_locked)
    gate = source.index("_phase_reconcile_before_teardown(run)")
    commit = source.index("_phase_commit_and_assert(run)")
    cleanup = source.index("_phase_cleanup_worktrees_and_branches(run)")
    push = source.index("_phase_push(run)")
    assert commit < gate < push < cleanup


def test_capture_claim_runs_before_first_mutating_phase() -> None:
    """The claim is captured before ``_phase_merge_lanes`` (the first mutation)."""
    import inspect

    from specify_cli.merge import executor

    source = inspect.getsource(executor._run_lane_based_merge_locked)
    capture = source.index("_capture_reconciliation_claim(run)")
    merge_lanes = source.index("_phase_merge_lanes(run)")
    assert capture < merge_lanes


def test_divergence_describe_reports_both_axes() -> None:
    div = Divergence(
        missing_approved=(("WP01", "a" * 40),),
        reachable_excluded=(("b" * 40, ""),),
    )
    text = div.describe()
    assert "approved WP01" in text
    assert "excluded" in text


def test_divergence_describe_renders_squash_unattributable_blob_honestly() -> None:
    """FIX B (Epic #5001 landing remediation): the squash axis attributes by
    ``(path, blob)`` tuples, not ``(sha, patch_id)`` — describing them through the
    ``(sha, patch_id)``-shaped ``unattributable_content`` field mislabels a repo
    path truncated to 10 chars as a "content commit" and a blob as a "patch-id".
    A dedicated ``unattributable_blobs`` field must render the FULL path and call
    the second element a blob, in both ``describe()`` and
    ``VerifyResult.recovery_guidance()``."""
    div = Divergence(unattributable_blobs=(("src/config/meta.json", "deadbeef" * 5),))
    text = div.describe()
    assert "src/config/meta.json" in text, text
    assert "blob" in text.lower(), text
    assert "patch-id" not in text.lower(), text
    assert "content commit" not in text.lower(), text

    guidance = VerifyResult.failed(div).recovery_guidance()
    assert "src/config/meta.json" in guidance, guidance


# --------------------------------------------------------------------------- #
# WS1 squash-sound blob-attribution content axis (#5013 / T012-T014).
#
# Under the DEFAULT squash strategy (``verify_reachability=False``) a PRODUCTION
# claim (``enforce_closed_world``) attributes every non-bookkeeping A/M path of
# the aggregate squash diff ``B..T`` against ``authored_blobs`` — the FINAL
# first-parent-authored ``(path, blob)`` per (lane, path). Content identity, never
# SHA/patch-id, so it survives squash. Every arm drives REAL on-disk git.
# --------------------------------------------------------------------------- #


def _squash_claim(
    *,
    approved: dict[str, tuple[str, ...]],
    authored_blobs: frozenset[tuple[str, str]],
    window_base: str | None,
    manifest_wp_ids: frozenset[str],
    planning_prefix: str | None = None,
    authored_deletions: frozenset[str] = frozenset(),
) -> ApprovedWpCommitSet:
    """A production (closed-world) SQUASH claim exercising the blob/deletion axes."""
    return ApprovedWpCommitSet(
        approved=approved,
        manifest_wp_ids=manifest_wp_ids,
        enforce_closed_world=True,
        authored_blobs=authored_blobs,
        authored_deletions=authored_deletions,
        excluded_window_base=window_base,
        mission_slug=_MISSION_SLUG,
        planning_prefix=planning_prefix,
        verify_reachability=False,  # squash
    )


def test_squash_authored_blobs_keep_final_not_superseded(tmp_path: Path) -> None:
    """F5: ``authored_blobs`` records the FINAL first-parent blob per (lane, path);
    a superseded intermediate ``v1`` is NOT admitted (so a canceled blob matching
    ``v1`` cannot be green-washed as attributable)."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    # _build_mission already authored src/wp01.py (v1) on lane-a.
    v1_blob = git_probes.blob_id_at(repo, lane_branch, "src/wp01.py")
    _git(repo, "checkout", "-q", lane_branch)
    (repo / "src" / "wp01.py").write_text("# WP01 v2\n", encoding="utf-8")
    _git(repo, "add", "src/wp01.py")
    _git(repo, "commit", "-qm", "feat: wp01 v2")
    v2_blob = git_probes.blob_id_at(repo, lane_branch, "src/wp01.py")
    _git(repo, "checkout", "-q", _TARGET)
    assert v1_blob != v2_blob

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert ("src/wp01.py", v2_blob) in claim.authored_blobs  # final kept
    assert ("src/wp01.py", v1_blob) not in claim.authored_blobs  # superseded dropped
    assert claim.authored_blobs  # always (path, blob) tuples, never blob-only
    assert all(isinstance(item, tuple) and len(item) == 2 for item in claim.authored_blobs)


def test_squash_fails_when_superseded_v1_blob_ships(tmp_path: Path) -> None:
    """A canceled blob matching the discarded ``v1`` rides to the target under
    squash ⇒ FAIL (F5: ``v1`` is not attributable to the superseded intermediate)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    # Author v2 on a side branch to capture a genuine, different blob.
    v2_sha = _lane_commit(repo, base, "authoring", "src/pkg/x.py", "v2\n")
    v2_blob = git_probes.blob_id_at(repo, v2_sha, "src/pkg/x.py")
    # Ship v1 on the target (the superseded content that must NOT be attributable).
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "x.py").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "squash: ships v1")
    claim = _squash_claim(
        approved={"WP01": (v2_sha,)},
        authored_blobs=frozenset({("src/pkg/x.py", v2_blob)}),
        window_base=base,
        manifest_wp_ids=frozenset({"WP01"}),
        planning_prefix=None,
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(path == "src/pkg/x.py" for path, _blob in result.divergence.unattributable_blobs)


def test_squash_fails_on_second_parent_smuggled_blob(tmp_path: Path) -> None:
    """A removed WP's blob merged in via a carrier lane's SECOND parent is on no
    approved lane's first-parent spine ⇒ absent from ``authored_blobs`` ⇒ FAIL,
    naming the smuggled path."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    smuggled = _lane_commit(repo, coord_base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_blob = git_probes.blob_id_at(repo, smuggled, "src/wp99_removed.py")
    _git(repo, "checkout", "-q", lane_branch)
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", lane_branch)  # both wp01 + smuggled land
    _git(repo, "branch", "-qD", "lane-removed")

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert ("src/wp99_removed.py", smuggled_blob) not in claim.authored_blobs
    squash_claim = replace(claim, verify_reachability=False)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(path == "src/wp99_removed.py" for path, _blob in result.divergence.unattributable_blobs)


def test_squash_passes_clean_no_false_fail(tmp_path: Path) -> None:
    """NFR-004 positive control: a clean squash whose every target blob is authored
    by an approved lane PASSes — the axis never false-fails a legitimate squash."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01", "WP02"))
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    _git(repo, "merge", "-q", "--no-edit", lane_a)
    _git(repo, "merge", "-q", "--no-edit", lane_b)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    squash_claim = replace(claim, verify_reachability=False)
    assert MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim).is_pass


def test_squash_refuses_when_authored_blobs_empty_but_approved_nonempty(tmp_path: Path) -> None:
    """F1 corollary: an empty ``authored_blobs`` while ``approved`` is non-empty is a
    fail-closed REFUSE under squash (never an empty-loop PASS)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "src/a.py", "A\n")
    claim = _squash_claim(
        approved={"WP01": (sha,)},
        authored_blobs=frozenset(),  # empty while approved lists WP01
        window_base=base,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_squash_refuses_on_probe_error_for_am_path(tmp_path: Path) -> None:
    """Fail-closed: a git error while scanning the squash window (unresolvable base)
    ⇒ REFUSE, never a vacuous PASS."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "src/a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = _squash_claim(
        approved={"WP01": (sha,)},
        authored_blobs=frozenset({("src/a.py", git_probes.blob_id_at(repo, _TARGET, "src/a.py"))}),
        window_base="deadbeef" * 5,  # non-None, unresolvable -> changed_paths errors
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_squash_refuses_on_none_window_base(tmp_path: Path) -> None:
    """The last NFR-001 fail-closed branch: a production squash claim whose window
    base is ``None`` cannot evaluate the blob axis ⇒ REFUSE (the reorder makes this
    fire under squash, above the old early-return)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    sha = _lane_commit(repo, base, "lane-a", "src/a.py", "A\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = _squash_claim(
        approved={"WP01": (sha,)},
        authored_blobs=frozenset({("src/a.py", git_probes.blob_id_at(repo, _TARGET, "src/a.py"))}),
        window_base=None,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None


def test_squash_masks_bookkeeping_paths(tmp_path: Path) -> None:
    """A window path under the mission planning prefix is bookkeeping, not content —
    masked by ``_is_bookkeeping_path`` even though its blob is unauthored ⇒ PASS."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    approved_sha = _lane_commit(repo, base, "lane-a", "src/wp01.py", "APPROVED\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    # A pure-bookkeeping change under kitty-specs/<slug>/ lands on the target.
    book = repo / "kitty-specs" / _MISSION_SLUG
    book.mkdir(parents=True)
    (book / "status.json").write_text('{"ok": true}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "chore: bookkeeping")
    claim = _squash_claim(
        approved={"WP01": (approved_sha,)},
        authored_blobs=frozenset({("src/wp01.py", git_probes.blob_id_at(repo, _TARGET, "src/wp01.py"))}),
        window_base=base,
        manifest_wp_ids=frozenset({"WP01"}),
        planning_prefix=f"kitty-specs/{_MISSION_SLUG}",
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_squash_hand_built_claim_without_closed_world_still_passes(tmp_path: Path) -> None:
    """Back-compat: a hand-built squash claim (``enforce_closed_world`` unset) keeps
    the pre-widening deferral PASS — the blob axis is opt-in, so existing unit
    claims never see new refusals/fails."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    unreached = _lane_commit(repo, base, "lane-a", "src/a.py", "A\n")  # NOT on target
    claim = ApprovedWpCommitSet(
        approved={"WP01": (unreached,)},
        manifest_wp_ids=frozenset({"WP01"}),
        verify_reachability=False,
        # enforce_closed_world defaults False; authored_blobs empty.
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_squash_refuses_vacuous_authorship_when_window_has_non_bookkeeping_content(tmp_path: Path) -> None:
    """FIX C (Epic #5001 landing remediation): a fail-OPEN vacuous PASS.

    When NO approved lane resolved to any commits (``approved == {"WP01": ()}``,
    the claim builder's tolerant "lane branch absent / already consolidated"
    shape) AND ``authored_blobs`` is empty, there is no authorship authority to
    attribute against. The axis used to PASS unconditionally in that case. But a
    non-bookkeeping Added/Modified path landing in the window while there is
    NO authorship authority at all is exactly the un-evaluable-claim shape the
    axis must REFUSE, not silently wave through — so it now inspects the window
    diff and REFUSEs when it finds one; only a genuinely content-free window
    (no A/M paths at all) still defers to PASS (NFR-004)."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    (repo / "src").mkdir()
    (repo / "src" / "leaked.py").write_text("leaked\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "feat: content with no authorship authority behind it")
    claim = _squash_claim(
        approved={"WP01": ()},  # no lane resolved any commits
        authored_blobs=frozenset(),
        window_base=base,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE, result.status
    assert result.refusal_reason is not None


def test_squash_vacuous_authorship_with_no_window_content_still_passes(tmp_path: Path) -> None:
    """FIX C positive control: a genuinely content-free window (no A/M paths at
    all) keeps the pre-#5001 PASS deferral — the new REFUSE guard never
    false-fails a legitimately empty window."""
    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    claim = _squash_claim(
        approved={"WP01": ()},
        authored_blobs=frozenset(),
        window_base=base,
        manifest_wp_ids=frozenset({"WP01"}),
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


# --------------------------------------------------------------------------- #
# #5022 / WP1 — squash DELETION-attribution axis (`authored_deletions`).
# --------------------------------------------------------------------------- #


def test_final_authored_deletions_add_then_delete_is_recorded(tmp_path: Path) -> None:
    """Add-then-delete within a lane: the lane's OWN final state for the path is
    deleted, so it must be recorded (#5022 / WP1 T002)."""
    from specify_cli.merge.reconciliation import _final_authored_deletions

    repo = _init_repo(tmp_path)
    base = _rev(repo, _TARGET)
    _git(repo, "branch", "lane-a", base)
    _git(repo, "checkout", "-q", "lane-a")
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "feat: add a.py")
    _git(repo, "rm", "-q", "src/a.py")
    _git(repo, "commit", "-qm", "feat: delete a.py")
    _git(repo, "checkout", "-q", _TARGET)
    spine = git_probes.first_parent_commits_in_range(repo, base, "lane-a")
    assert _final_authored_deletions(repo, spine) == {"src/a.py"}


def test_final_authored_deletions_delete_then_readd_is_not_recorded(tmp_path: Path) -> None:
    """Delete-then-re-add within a lane: the lane's final state for the path is
    PRESENT, so it must NOT be recorded as a deletion — it belongs in
    ``_final_authored_blobs`` instead (#5022 / WP1 T002)."""
    from specify_cli.merge.reconciliation import _final_authored_blobs, _final_authored_deletions

    repo = _init_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base: add a.py before the lane")
    base = _rev(repo, _TARGET)
    _git(repo, "branch", "lane-a", base)
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "rm", "-q", "src/a.py")
    _git(repo, "commit", "-qm", "feat: delete a.py")
    (repo / "src").mkdir(exist_ok=True)  # `git rm` prunes the now-empty directory
    (repo / "src" / "a.py").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "feat: re-add a.py")
    _git(repo, "checkout", "-q", _TARGET)
    spine = git_probes.first_parent_commits_in_range(repo, base, "lane-a")
    assert _final_authored_deletions(repo, spine) == set()
    blobs = _final_authored_blobs(repo, spine)
    assert any(path == "src/a.py" for path, _blob in blobs)


def test_squash_authorized_deletion_passes(tmp_path: Path) -> None:
    """S2: an approved lane's first-parent spine deletes path P — the deletion IS
    attributable (``P in authored_deletions``) ⇒ PASS. Also exercises the F1-
    corollary guard fix: ``authored_blobs`` is empty here (nothing was added or
    modified) but ``authored_deletions`` is non-empty, so the axis must NOT
    REFUSE on "empty authorship"."""
    repo = _init_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "keep.py").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pre-existing: add keep.py")
    window_base = _rev(repo, _TARGET)
    _git(repo, "branch", "lane-a", window_base)
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "rm", "-q", "src/keep.py")
    _git(repo, "commit", "-qm", "feat: remove keep.py")
    sha = _rev(repo, "lane-a")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    claim = _squash_claim(
        approved={"WP01": (sha,)},
        authored_blobs=frozenset(),
        authored_deletions=frozenset({"src/keep.py"}),
        window_base=window_base,
        manifest_wp_ids=frozenset({"WP01"}),
        planning_prefix=None,
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_squash_unattributed_deletion_fails(tmp_path: Path) -> None:
    """S1 (unit-level): a deletion in the squash window with no authored-deletion
    authority behind it is un-attributable ⇒ FAIL, named in
    ``Divergence.unattributable_deletions`` (#5022)."""
    repo = _init_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "keep.py").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pre-existing: add keep.py")
    window_base = _rev(repo, _TARGET)
    approved_sha = _lane_commit(repo, window_base, "lane-a", "src/other.py", "OTHER\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    # keep.py's removal rides the target with NO authorship behind it — mirrors a
    # canceled WP's deletion carried in via a carrier merge (#5022).
    _git(repo, "rm", "-q", "src/keep.py")
    _git(repo, "commit", "-qm", "squash: keep.py silently gone")
    claim = _squash_claim(
        approved={"WP01": (approved_sha,)},
        authored_blobs=frozenset({("src/other.py", git_probes.blob_id_at(repo, _TARGET, "src/other.py"))}),
        authored_deletions=frozenset(),
        window_base=window_base,
        manifest_wp_ids=frozenset({"WP01"}),
        planning_prefix=None,
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert "src/keep.py" in result.divergence.unattributable_deletions
    # The approved add is unaffected — never sacrificed to close the leak.
    assert not result.divergence.unattributable_blobs


def test_squash_bookkeeping_deletion_passes(tmp_path: Path) -> None:
    """S3: deletion of a mission-bookkeeping path is masked before attribution —
    PASS even with an empty ``authored_deletions`` (#5022)."""
    repo = _init_repo(tmp_path)
    book_dir = repo / "kitty-specs" / _MISSION_SLUG
    book_dir.mkdir(parents=True)
    (book_dir / "status.json").write_text('{"ok": true}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pre-existing: bookkeeping file")
    window_base = _rev(repo, _TARGET)
    approved_sha = _lane_commit(repo, window_base, "lane-a", "src/wp01.py", "APPROVED\n")
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    _git(repo, "rm", "-q", f"kitty-specs/{_MISSION_SLUG}/status.json")
    _git(repo, "commit", "-qm", "chore: bookkeeping cleanup")
    claim = _squash_claim(
        approved={"WP01": (approved_sha,)},
        authored_blobs=frozenset({("src/wp01.py", git_probes.blob_id_at(repo, _TARGET, "src/wp01.py"))}),
        authored_deletions=frozenset(),
        window_base=window_base,
        manifest_wp_ids=frozenset({"WP01"}),
        planning_prefix=f"kitty-specs/{_MISSION_SLUG}",
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_squash_rename_attributes_both_delete_and_add_halves(tmp_path: Path) -> None:
    """A rename surfaces under ``--no-renames`` as a delete + an add; both halves
    must be independently attributed — the deleted OLD path via
    ``authored_deletions``, the added NEW path via ``authored_blobs`` (#5022 T003
    adversarial)."""
    repo = _init_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "old.py").write_text("content\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pre-existing: add old.py")
    window_base = _rev(repo, _TARGET)
    _git(repo, "branch", "lane-a", window_base)
    _git(repo, "checkout", "-q", "lane-a")
    _git(repo, "mv", "src/old.py", "src/new.py")
    _git(repo, "commit", "-qm", "feat: rename old.py to new.py")
    sha = _rev(repo, "lane-a")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", "lane-a")
    new_blob = git_probes.blob_id_at(repo, _TARGET, "src/new.py")
    claim = _squash_claim(
        approved={"WP01": (sha,)},
        authored_blobs=frozenset({("src/new.py", new_blob)}),
        authored_deletions=frozenset({"src/old.py"}),
        window_base=window_base,
        manifest_wp_ids=frozenset({"WP01"}),
        planning_prefix=None,
    )
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


def test_squash_authored_deletion_union_across_two_lanes_passes(tmp_path: Path) -> None:
    """``authored_deletions`` is a UNION across ALL approved lanes, built end to
    end through :func:`build_approved_wp_set` (not a hand-built claim) — a
    deletion authored by lane-b's own first-parent spine is attributable."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01", "WP02"))
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    # _build_mission already committed src/wp02.py on lane-b; WP02 now removes it.
    _git(repo, "checkout", "-q", lane_b)
    _git(repo, "rm", "-q", "src/wp02.py")
    _git(repo, "commit", "-qm", "feat: wp02 removes its own file")
    _git(repo, "checkout", "-q", _TARGET)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert "src/wp02.py" in claim.authored_deletions
    _git(repo, "merge", "-q", "--no-edit", lane_a)
    _git(repo, "merge", "-q", "--no-edit", lane_b)
    squash_claim = replace(claim, verify_reachability=False)
    assert MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim).is_pass


def test_divergence_describe_renders_unattributable_deletion() -> None:
    """The deletion axis renders honestly — a PATH, never a blob (there is none),
    and the wording distinguishes "deleted" from the add/modify vocabulary."""
    div = Divergence(unattributable_deletions=("src/product/keep_me.py",))
    text = div.describe()
    assert "src/product/keep_me.py" in text, text
    assert "delet" in text.lower(), text

    guidance = VerifyResult.failed(div).recovery_guidance()
    assert "src/product/keep_me.py" in guidance, guidance


# --------------------------------------------------------------------------- #
# #5018 / WP2 — commit-level exclusion narrowing in a mixed lane.
# --------------------------------------------------------------------------- #


def _build_mixed_lane_mission(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str]:
    """ONE lane (``lane-a``) whose ``wp_ids`` list an approved survivor (WP01) and
    a canceled-with-provenance sibling (WP02). Only WP01 commits real code to the
    shared lane branch — the minimal shape that exercises #5018's granularity bug
    (a correct commit-granular exclusion must never exclude the survivor's own
    commit; the pre-fix lane-granular exclusion does)."""
    repo = _init_repo(tmp_path)
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _MISSION_SLUG,
                "mission_id": _MISSION_ID,
                "mission_type": "software-dev",
                "target_branch": _TARGET,
            }
        ),
        encoding="utf-8",
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch=_TARGET,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/wp01.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=_now_iso(),
        computed_from="recon-test-mixed-lane",
    )
    events = [
        *_approve_events(0, "WP01", day=1),
        _event(9000, "WP02", "planned", "canceled", at="2026-03-01T00:00:00+00:00", lamport=1),
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )
    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap mixed-lane mission")
    coord_base = _rev(repo, "HEAD")

    branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    _lane_commit(repo, coord_base, branch, "src/wp01.py", "# WP01 survivor\n")
    return repo, feature_dir, manifest, coord_base


def test_collect_excluded_narrows_mixed_lane_to_commit_granularity(tmp_path: Path) -> None:
    """#5018: a mixed lane's survivor commit must NOT be in ``excluded_shas`` —
    only commits attributable to NO approved lane's first-parent authorship stay
    excluded."""
    repo, feature_dir, manifest, coord_base = _build_mixed_lane_mission(tmp_path)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
        excluded_window_base=coord_base,
    )
    branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    survivor_sha = git_probes.commits_in_range(repo, coord_base, branch)[0]
    assert survivor_sha in claim.authored_shas
    assert survivor_sha not in claim.excluded_shas
    _git(repo, "merge", "-q", "--no-edit", branch)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.is_pass, result.divergence.describe() if result.divergence else result.refusal_reason


def test_collect_excluded_still_catches_second_parent_smuggled_commit_in_mixed_lane(tmp_path: Path) -> None:
    """C-001 adversarial: a canceled WP's commit smuggled into the MIXED lane via
    a merge's SECOND parent is NOT on the survivor's first-parent spine, so it is
    NOT subtracted from the excluded set — it stays excluded and FAILs when
    reachable (the #4977 safety net, narrowed granularity must never widen into
    reduced strictness)."""
    repo, feature_dir, manifest, coord_base = _build_mixed_lane_mission(tmp_path)
    branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    smuggled = _lane_commit(repo, coord_base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_pid = git_probes.patch_id_of(repo, smuggled)
    _git(repo, "checkout", "-q", branch)
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", branch)  # survivor + smuggled both land
    _git(repo, "branch", "-qD", "lane-removed")

    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
        excluded_window_base=coord_base,
    )
    assert smuggled not in claim.authored_shas
    assert smuggled in claim.excluded_shas or smuggled_pid in claim.excluded_patch_ids
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(sha == smuggled or pid == smuggled_pid for sha, pid in result.divergence.reachable_excluded)


def test_collect_excluded_subtracts_only_authored_shas_not_all(tmp_path: Path) -> None:
    """Unit-level pin of the #5018 subtraction formula: ``excluded_shas ←
    lane_tips − authored_shas`` / ``excluded_patch_ids ← lane_patch_ids −
    authored_patch_ids``. With NO authored subtraction the whole lane tip is
    excluded (pre-#5018 behavior); subtracting the survivor's own sha/patch-id
    removes ONLY that commit — the patch-id equivalence a re-lettered/cherry-
    picked copy relies on (RN-F4) is preserved for anything NOT subtracted."""
    from specify_cli.merge.reconciliation import _collect_excluded

    repo, _feature_dir, manifest, coord_base = _build_mixed_lane_mission(tmp_path)
    branch = lane_branch_name(_MISSION_SLUG, "lane-a", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    survivor_sha = git_probes.commits_in_range(repo, coord_base, branch)[0]
    survivor_pid = git_probes.patch_id_of(repo, survivor_sha)

    shas_none, pids_none = _collect_excluded(repo, manifest, coord_base, frozenset({"WP02"}))
    assert survivor_sha in shas_none
    if survivor_pid:
        assert survivor_pid in pids_none

    shas_sub, pids_sub = _collect_excluded(
        repo,
        manifest,
        coord_base,
        frozenset({"WP02"}),
        authored_shas=frozenset({survivor_sha}),
        authored_patch_ids=frozenset({survivor_pid}) if survivor_pid else frozenset(),
    )
    assert survivor_sha not in shas_sub
    if survivor_pid:
        assert survivor_pid not in pids_sub


def test_collect_excluded_fully_canceled_lane_stays_fully_excluded(tmp_path: Path) -> None:
    """A fully-canceled lane (no approved WP at all) is unchanged by the #5018
    narrowing — every one of its tip commits stays excluded, since
    ``_collect_authored`` never contributes authorship for a lane with no
    approved WP."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",), manifest_wps=("WP01", "WP02"))
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    branch = lane_branch_name(_MISSION_SLUG, "lane-b", planning_base_branch=_TARGET, mission_id=_MISSION_ID)
    all_tip_commits = set(git_probes.commits_in_range(repo, coord_base, branch))
    assert all_tip_commits
    assert all_tip_commits <= claim.excluded_shas
    assert not (all_tip_commits & claim.authored_shas)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "3-way merge-resolution content: final blob != either parent is not "
        "attributable to a single approved lane; bounded, file-disjoint-lane-"
        "mitigated; tracked follow-up"
    ),
)
def test_squash_three_way_merge_resolution_is_unattributable(tmp_path: Path) -> None:
    """C-003 residual: two approved lanes edit the SAME path; the squash resolves it
    to a third blob (!= either lane's first-parent blob). The desired behavior is a
    PASS (a genuine resolution is not removed content), but the blob axis cannot
    attribute it, so it FAILs — pinned as a strict xfail, exercising a REAL 3-way
    scenario, never a bare marker."""
    repo = _init_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "shared.py").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base shared")
    window_base = _rev(repo, _TARGET)
    a_sha = _lane_commit(repo, window_base, "lane-a", "src/shared.py", "alpha\n")
    b_sha = _lane_commit(repo, window_base, "lane-b", "src/shared.py", "beta\n")
    alpha_blob = git_probes.blob_id_at(repo, a_sha, "src/shared.py")
    beta_blob = git_probes.blob_id_at(repo, b_sha, "src/shared.py")
    # The squash resolves the conflict to a THIRD blob (neither parent verbatim).
    (repo / "src" / "shared.py").write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "squash: conflict-resolved shared")
    resolved_blob = git_probes.blob_id_at(repo, _TARGET, "src/shared.py")
    assert resolved_blob not in {alpha_blob, beta_blob}
    claim = _squash_claim(
        approved={"WP01": (a_sha,), "WP02": (b_sha,)},
        authored_blobs=frozenset({("src/shared.py", alpha_blob), ("src/shared.py", beta_blob)}),
        window_base=window_base,
        manifest_wp_ids=frozenset({"WP01", "WP02"}),
        planning_prefix=None,
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    # Desired (not yet achievable): a genuine resolution is not "removed content".
    assert result.is_pass
