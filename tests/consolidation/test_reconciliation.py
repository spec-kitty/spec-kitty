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
from specify_cli.consolidation import git_probes
from specify_cli.consolidation.reconciliation import (
    TERMINUS_ENTRY_POINTS,
    ApprovedWpCommitSet,
    Divergence,
    LaneContribution,
    MergeOutcomeVerifier,
    UnroutedTerminusPathError,
    VerifyResult,
    VerifyStatus,
    build_approved_wp_set,
    detect_legacy_in_flight_state,
    route_terminus,
    write_post_fix_marker,
)
from specify_cli.consolidation.canceled_attestation import OVERRIDABLE_REASONS
from specify_cli.consolidation.state import clear_state
from specify_cli.consolidation.wp_attribution import (
    Attributed,
    CanceledPathState,
    Unattributable,
    UnattributableReason,
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


def test_build_claim_refuses_an_approved_lane_when_its_claim_base_does_not_resolve(tmp_path: Path) -> None:
    """The approval bound never passes for want of an answer (#5668).

    ``check_lane`` cannot measure a lane from a base that is not a commit, so the claim
    builder refuses naming that base instead of recording the lane tips unchecked. (A lane
    whose own branch is gone is a different case and stays tolerated as an empty lane.)
    """
    repo, feature_dir, manifest, _coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref="no-such-base-xyz")
    assert claim.refusal is not None
    assert "'no-such-base-xyz'" in claim.refusal and "does not resolve" in claim.refusal
    assert claim.bound_lane_tips == ()


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
    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    # Smuggle a removed WP's commit INTO the approved lane via a merge second parent.
    smuggled = _lane_commit(repo, coord_base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_pid = git_probes.patch_id_of(repo, smuggled)
    _git(repo, "checkout", "-q", lane_branch)
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _restamp_approvals(repo)
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


def _event(seq: int, wp: str, frm: str, to: str, *, at: str, lamport: int, lane_head: str | None = None) -> dict[str, object]:
    event: dict[str, object] = {
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
    if lane_head is not None:
        event["policy_metadata"] = {"lane_head": lane_head}
    return event


def _approve_events(seq_start: int, wp: str, *, day: int, claim_head: str, approved_head: str) -> list[dict[str, object]]:
    """The approval chain, every event stamped with a real lane tip.

    ``claim_head`` is the lane tip when the WP was claimed (before its commit) and
    ``approved_head`` the tip once its content was committed, both read from git by
    the caller; the log is written after the lane commits exist.
    """
    events: list[dict[str, object]] = []
    for i, (frm, to) in enumerate(_APPROVE_CHAIN, start=1):
        head = claim_head if i <= 2 else approved_head
        events.append(_event(seq_start + i, wp, frm, to, at=f"2026-01-{day:02d}T00:0{i}:00+00:00", lamport=i, lane_head=head))
    return events


def _commit_status_log(repo: Path, feature_dir: Path, events: list[dict[str, object]], message: str) -> None:
    """Write the status log and commit it on the target branch, AFTER the lane commits exist."""
    log = feature_dir / "status.events.jsonl"
    log.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")
    _git(repo, "add", str(log.relative_to(repo)))
    _git(repo, "commit", "-qm", message)


def _restamp_approvals(repo: Path) -> None:
    """Record that review approved every approved lane's CURRENT tip (#5668): the truthful stamp.

    For tests whose subject is something other than "content arrived after approval" (a
    smuggled second-parent commit, a superseded blob, a shared-file merge resolution) and
    that move a lane after the builder approved it. Rewrites the ``approved`` event of
    every work package that sits on an existing lane branch so its ``lane_head`` is that
    branch's tip now, and commits the log on the target branch.
    """
    from specify_cli.lanes.persistence import read_lanes_json

    _git(repo, "checkout", "-q", _TARGET)
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    tips: dict[str, str] = {}
    for lane in manifest.lanes:
        branch = lane_branch_name(_MISSION_SLUG, lane.lane_id, target_branch=_TARGET)
        if _git(repo, "branch", "--list", branch):
            tips.update({wp: _rev(repo, branch) for wp in lane.wp_ids})
    log = feature_dir / "status.events.jsonl"
    original = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = json.loads(json.dumps(original))
    for event in events:
        if event["to_lane"] == "approved" and event["wp_id"] in tips:
            event["policy_metadata"] = {**(event.get("policy_metadata") or {}), "lane_head": tips[event["wp_id"]]}
    if events == original:
        return
    _commit_status_log(repo, feature_dir, events, "restamp approvals at the lane tips")


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

    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap mission")
    coord_base = _rev(repo, "HEAD")

    # one lane branch per manifest WP, each with a real approved commit.
    lane_tips: dict[str, str] = {}
    for lane in manifest.lanes:
        branch = lane_branch_name(_MISSION_SLUG, lane.lane_id, target_branch=_TARGET)
        for wp in lane.wp_ids:
            lane_tips[wp] = _lane_commit(repo, coord_base, branch, f"src/{wp.lower()}.py", f"# {wp}\n")

    # the approved status log, written once the lane commits exist and stamped with their real tips.
    events: list[dict[str, object]] = []
    seq = 0
    for day, wp in enumerate(approved_wps, start=1):
        events.extend(_approve_events(seq, wp, day=day, claim_head=coord_base, approved_head=lane_tips[wp]))
        seq += 100
    if extra_events:
        events.extend(extra_events)
    _commit_status_log(repo, feature_dir, events, "approve mission WPs")
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
            target_branch=_TARGET,
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
    branch = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
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
    clear_state(repo, _MISSION_ID)
    assert detect_legacy_in_flight_state(repo, _MISSION_ID, is_resume=True) is not None


def test_clear_state_marker_clear_is_idempotent(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    clear_state(repo, _MISSION_ID)  # nothing on disk -> no error
    write_post_fix_marker(repo, _MISSION_ID)
    clear_state(repo, _MISSION_ID)
    clear_state(repo, _MISSION_ID)
    assert detect_legacy_in_flight_state(repo, _MISSION_ID, is_resume=True) is not None


# --------------------------------------------------------------------------- #
# NFR-005 non-vacuous call-site allowlist + self-mutation
# --------------------------------------------------------------------------- #


def test_all_six_terminus_entry_points_route(tmp_path: Path) -> None:
    expected = {
        "consolidate",
        "consolidate --resume",
        "consolidate --abort",
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

    from specify_cli.consolidation import executor

    source = inspect.getsource(executor._run_lane_based_consolidation_locked)
    gate = source.index("_phase_reconcile_before_teardown(run)")
    commit = source.index("_phase_commit_and_assert(run)")
    cleanup = source.index("_phase_cleanup_worktrees_and_branches(run)")
    push = source.index("_phase_push(run)")
    assert commit < gate < push < cleanup


def test_capture_claim_runs_before_first_mutating_phase() -> None:
    """The claim is captured before ``_phase_merge_lanes`` (the first mutation)."""
    import inspect

    from specify_cli.consolidation import executor

    source = inspect.getsource(executor._run_lane_based_consolidation_locked)
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
    multi_lane_paths: dict[str, tuple[LaneContribution, LaneContribution]] | None = None,
) -> ApprovedWpCommitSet:
    """A production (closed-world) SQUASH claim exercising the blob/deletion axes."""
    return ApprovedWpCommitSet(
        approved=approved,
        manifest_wp_ids=manifest_wp_ids,
        enforce_closed_world=True,
        authored_blobs=authored_blobs,
        authored_deletions=authored_deletions,
        multi_lane_paths=multi_lane_paths or {},
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
    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    # _build_mission already authored src/wp01.py (v1) on lane-a.
    v1_blob = git_probes.blob_id_at(repo, lane_branch, "src/wp01.py")
    _git(repo, "checkout", "-q", lane_branch)
    (repo / "src" / "wp01.py").write_text("# WP01 v2\n", encoding="utf-8")
    _git(repo, "add", "src/wp01.py")
    _git(repo, "commit", "-qm", "feat: wp01 v2")
    v2_blob = git_probes.blob_id_at(repo, lane_branch, "src/wp01.py")
    _git(repo, "checkout", "-q", _TARGET)
    assert v1_blob != v2_blob

    _restamp_approvals(repo)
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
    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    smuggled = _lane_commit(repo, coord_base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_blob = git_probes.blob_id_at(repo, smuggled, "src/wp99_removed.py")
    _git(repo, "checkout", "-q", lane_branch)
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", lane_branch)  # both wp01 + smuggled land
    _git(repo, "branch", "-qD", "lane-removed")

    _restamp_approvals(repo)
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
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
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
    from specify_cli.consolidation.reconciliation import _final_authored_deletions

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
    from specify_cli.consolidation.reconciliation import _final_authored_blobs, _final_authored_deletions

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
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    # _build_mission already committed src/wp02.py on lane-b; WP02 now removes it.
    _git(repo, "checkout", "-q", lane_b)
    _git(repo, "rm", "-q", "src/wp02.py")
    _git(repo, "commit", "-qm", "feat: wp02 removes its own file")
    _git(repo, "checkout", "-q", _TARGET)
    _restamp_approvals(repo)
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
    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap mixed-lane mission")
    coord_base = _rev(repo, "HEAD")

    branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_tip = _lane_commit(repo, coord_base, branch, "src/wp01.py", "# WP01 survivor\n")
    # the status log is written once the lane commit exists; every event carries the real lane tip.
    events = [
        *_approve_events(0, "WP01", day=1, claim_head=coord_base, approved_head=lane_tip),
        _event(9000, "WP02", "planned", "canceled", at="2026-03-01T00:00:00+00:00", lamport=1, lane_head=lane_tip),
    ]
    _commit_status_log(repo, feature_dir, events, "mixed-lane mission events")
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
    branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
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
    branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    smuggled = _lane_commit(repo, coord_base, "lane-removed", "src/wp99_removed.py", "REMOVED\n")
    smuggled_pid = git_probes.patch_id_of(repo, smuggled)
    _git(repo, "checkout", "-q", branch)
    _git(repo, "merge", "-q", "--no-edit", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", branch)  # survivor + smuggled both land
    _git(repo, "branch", "-qD", "lane-removed")

    _restamp_approvals(repo)
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
    from specify_cli.consolidation.reconciliation import _collect_excluded

    repo, _feature_dir, manifest, coord_base = _build_mixed_lane_mission(tmp_path)
    branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
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
    branch = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    all_tip_commits = set(git_probes.commits_in_range(repo, coord_base, branch))
    assert all_tip_commits
    assert all_tip_commits <= claim.excluded_shas
    assert not (all_tip_commits & claim.authored_shas)


# --------------------------------------------------------------------------- #
# Merge-resolution-aware Seam A attribution (terminus-merge-resolution-
# attribution / #5051-adjacent, FR-002/003/009). A path authored by EXACTLY TWO
# approved lanes at DISJOINT hunks squashes to a legitimate 3-way-merged blob
# (equal to neither lane's own final blob) — ``multi_lane_paths`` names the two
# contributing lanes and ``is_legitimate_three_way_resolution`` simulates their
# deterministic ``git merge-tree`` resolution. Every unsound shape (>2 lanes, a
# conflicting resolution, binary, an unresolvable lane commit, git<2.38) stays
# fail-closed — see ``test_squash_three_way_merge_resolution_is_unattributable``
# below for the genuine same-line-conflict residual this recognizer does NOT
# (and, by design, cannot) close.
# --------------------------------------------------------------------------- #


def _build_shared_file_lanes(
    tmp_path: Path,
    *,
    lane_wp_pairs: tuple[tuple[str, str], ...],
    shared_path: str = "src/shared.py",
    initial_lines: tuple[str, ...] | None = None,
) -> tuple[Path, Path, LanesManifest, str]:
    """A mission whose lanes ALL declare ``shared_path`` in write_scope, with the
    file already present at the coord base (so each lane's own first-commit can
    edit a disjoint region of it directly — no second-parent merge needed).
    Returns ``(repo, feature_dir, manifest, coord_base)``; one EMPTY lane branch
    per ``(lane_id, wp_id)`` pair is cut from ``coord_base`` — the caller adds
    each lane's own edit commit(s)."""
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
    lines = list(initial_lines or (f"line {i}\n" for i in range(1, 11)))
    shared = repo / shared_path
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text("".join(lines), encoding="utf-8")
    lanes = [
        ExecutionLane(
            lane_id=lane_id,
            wp_ids=(wp,),
            write_scope=(shared_path,),
            predicted_surfaces=("code",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for lane_id, wp in lane_wp_pairs
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
    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap mission with shared file")
    coord_base = _rev(repo, "HEAD")
    events: list[dict[str, object]] = []
    seq = 0
    for day, (lane_id, wp) in enumerate(lane_wp_pairs, start=1):
        branch = lane_branch_name(_MISSION_SLUG, lane_id, target_branch=_TARGET)
        _git(repo, "branch", branch, coord_base)
        # The lane is empty here, so its real tip is the coord base: each caller's own
        # edit commit lands AFTER this approval, which is exactly what the stamp records.
        events.extend(_approve_events(seq, wp, day=day, claim_head=_rev(repo, branch), approved_head=_rev(repo, branch)))
        seq += 100
    _commit_status_log(repo, feature_dir, events, "approve shared-file mission WPs")
    return repo, feature_dir, manifest, coord_base


def _edit_shared_line(repo: Path, branch: str, shared_path: str, line_index: int, text: str) -> str:
    """Checkout *branch*, replace line *line_index* of *shared_path*, commit; return the new SHA."""
    _git(repo, "checkout", "-q", branch)
    full_path = repo / shared_path
    lines = full_path.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[line_index] = text
    full_path.write_text("".join(lines), encoding="utf-8")
    _git(repo, "add", shared_path)
    _git(repo, "commit", "-qm", f"feat: edit {shared_path}@{line_index}")
    sha = _rev(repo, branch)
    _restamp_approvals(repo)
    return sha


def test_collect_authored_multi_lane_paths_present_for_exactly_two_lanes(tmp_path: Path) -> None:
    """FR-009: a path touched by EXACTLY TWO approved lanes' own final blobs is
    present in ``multi_lane_paths`` with both lane ids and their still-resolvable
    (raw SHA) lane commits."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    a_sha = _edit_shared_line(repo, lane_a, "src/shared.py", 0, "A\n")
    b_sha = _edit_shared_line(repo, lane_b, "src/shared.py", 9, "B\n")
    _git(repo, "checkout", "-q", _TARGET)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert "src/shared.py" in claim.multi_lane_paths
    contrib_a, contrib_b = claim.multi_lane_paths["src/shared.py"]
    assert {contrib_a.lane_id, contrib_b.lane_id} == {"lane-a", "lane-b"}
    assert {contrib_a.lane_commit, contrib_b.lane_commit} == {a_sha, b_sha}


def test_collect_authored_multi_lane_paths_absent_for_single_lane_path(tmp_path: Path) -> None:
    """A path only ONE approved lane touches never enters ``multi_lane_paths`` —
    the existing single-lane ``authored_blobs`` fast path already attributes it
    (the disjoint-write-scope invariant's common case)."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert not claim.multi_lane_paths
    assert any(path == "src/wp01.py" for path, _blob in claim.authored_blobs)


def test_collect_authored_multi_lane_paths_absent_for_three_lane_path(tmp_path: Path) -> None:
    """A path touched by THREE approved lanes stays absent from
    ``multi_lane_paths`` (2-way ``merge-tree`` folding is order-dependent /
    nondeterministic for N>2 — Decision 2, ``research.md``); those paths stay
    fail-closed, never simulated."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"), ("lane-c", "WP03"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    for lane_id, line_idx, text in (("lane-a", 0, "A\n"), ("lane-b", 4, "B\n"), ("lane-c", 9, "C\n")):
        branch = lane_branch_name(_MISSION_SLUG, lane_id, target_branch=_TARGET)
        _edit_shared_line(repo, branch, "src/shared.py", line_idx, text)
    _git(repo, "checkout", "-q", _TARGET)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)
    assert "src/shared.py" not in claim.multi_lane_paths


def test_squash_passes_disjoint_hunk_two_lane_merge_resolution(tmp_path: Path) -> None:
    """Contract row A2 / T004: two approved lanes edit DISJOINT hunks of ONE
    shared file; the squash target's clean 3-way-merged blob (equal to neither
    lane's own final blob) is a legitimate merge resolution, not removed
    content — PASS.

    RED before T003 (the merged blob was absent from the flat, single-lane
    ``authored_blobs`` set, so the axis false-FAILed a genuinely clean squash);
    GREEN after (the merge-resolution recognizer attributes it)."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    _edit_shared_line(repo, lane_a, "src/shared.py", 0, "line 1 EDITED BY LANE A\n")
    _edit_shared_line(repo, lane_b, "src/shared.py", 9, "line 10 EDITED BY LANE B\n")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", lane_a)
    _git(repo, "merge", "-q", "--no-edit", lane_b)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert "src/shared.py" in claim.multi_lane_paths
    contributions = claim.multi_lane_paths["src/shared.py"]
    assert {c.lane_id for c in contributions} == {"lane-a", "lane-b"}
    squash_claim = replace(claim, verify_reachability=False)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim)
    assert result.is_pass, result.divergence.describe() if result.divergence else result.refusal_reason


def test_squash_fails_closed_when_carrier_lane_tip_smuggles_second_parent_hunk_into_two_lane_path(
    tmp_path: Path,
) -> None:
    """Data-loss guard (#5124 landing fold — closes a reopened #4977 carrier-lane
    threat). A ``LaneContribution.lane_commit`` is a raw lane TIP and CAN be a
    merge commit; ``three_way_merge_blob`` feeds it that commit's FULL tree, not
    just its first-parent authorship. If a contributing lane's tip is a merge
    commit whose resulting tree, for the shared path, is CONTENT-IDENTICAL to
    its (smuggling) second parent — a "trivial" content resolution git's own
    ``--name-only`` diff omits from the merge commit's OWN change list, so
    ``_final_authored_walk`` never revisits that path there and instead records
    the lane's OLDER, still-clean pre-merge blob as authored — the merge tip's
    ACTUAL tree nonetheless carries the smuggled hunk. Pre-guard, the simulation
    still fed that merge tip's FULL tree as one of its two inputs, reproduced
    the smuggled hunk, matched the target, and attributed it — the smuggled
    content SHIPPED even though it was never in ``authored_blobs``. This is the
    exact two-lane intersection of the existing single-lane
    ``_plant_carrier_smuggled_commit`` tests (smuggled content on a DISTINCT
    path) and ``test_squash_passes_disjoint_hunk_two_lane_merge_resolution``
    (two lanes, one shared path, no merge commit): two approved lanes edit
    DISJOINT lines of one shared path, and one of them ALSO smuggles a third,
    unrelated (NOT-approved) lane's disjoint-line edit into that SAME path via
    a merge tip.

    The guard requires each contribution's own tip-tree blob at *path* to equal
    its recorded first-parent-authored blob before trusting the simulation; a
    mismatch here (the merge tip's tree carries the smuggled line, the recorded
    authored blob does not) refuses to simulate, so the path stays
    unattributable -> FAIL. Pre-guard this test is RED (the smuggled content is
    attributed and the gate wrongly PASSes)."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    a_sha = _edit_shared_line(repo, lane_a, "src/shared.py", 0, "line 1 EDITED BY LANE A\n")
    b_edit_sha = _edit_shared_line(repo, lane_b, "src/shared.py", 9, "line 10 EDITED BY LANE B\n")
    clean_b_blob = git_probes.blob_id_at(repo, b_edit_sha, "src/shared.py")

    # An unrelated, NOT-approved lane smuggles a disjoint-line edit into lane-b
    # via lane-b's TIP merge commit (mirrors ``_plant_carrier_smuggled_commit``'s
    # #4977 carrier mechanism, but on the SAME shared path, not a distinct one).
    # Branched from lane-b's OWN edit (not the shared coord base) so the merge's
    # resulting tree for this path is content-identical to the smuggling side —
    # a "trivial" resolution ``git show --name-only`` omits from M's own diff,
    # which is exactly why ``_final_authored_walk`` records the OLDER, clean
    # ``b_edit_sha`` blob as lane-b's authored content while ``lane_commit``
    # (the raw tip) is the merge commit M whose actual tree carries the smuggle.
    _git(repo, "branch", "lane-removed", b_edit_sha)
    _edit_shared_line(repo, "lane-removed", "src/shared.py", 4, "SMUGGLED-REMOVED\n")
    _git(repo, "checkout", "-q", lane_b)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "lane-removed")
    merge_sha = _rev(repo, lane_b)
    _git(repo, "branch", "-qD", "lane-removed")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", lane_a)
    _git(repo, "merge", "-q", "--no-edit", lane_b)
    target_blob = git_probes.blob_id_at(repo, _TARGET, "src/shared.py")

    _restamp_approvals(repo)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert "src/shared.py" in claim.multi_lane_paths
    contributions = claim.multi_lane_paths["src/shared.py"]
    by_lane = {c.lane_id: c for c in contributions}
    contrib_a, contrib_b = by_lane["lane-a"], by_lane["lane-b"]
    assert contrib_a.lane_commit == a_sha
    # lane-b's recorded TIP is the merge commit (the hole this guard closes);
    # its OWN recorded authored blob correctly stays the clean, pre-merge blob.
    assert contrib_b.lane_commit == merge_sha
    assert contrib_b.authored_blob == clean_b_blob
    # The merge commit's FULL tree carries the smuggled hunk -- diverges from
    # the lane's own authored blob, which is exactly what the guard detects.
    assert git_probes.blob_id_at(repo, merge_sha, "src/shared.py") != clean_b_blob

    squash_claim = replace(claim, verify_reachability=False)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim)
    assert result.status is VerifyStatus.FAIL, (
        f"expected the smuggled hunk to stay unattributable, got {result.status}: {result.divergence.describe() if result.divergence else result.refusal_reason}"
    )
    assert result.divergence is not None
    assert any(path == "src/shared.py" and blob == target_blob for path, blob in result.divergence.unattributable_blobs), result.divergence.unattributable_blobs


def test_squash_fails_closed_when_path_touched_by_more_than_two_approved_lanes(tmp_path: Path) -> None:
    """A5: a path touched by THREE approved lanes' clean, disjoint edits still
    FAILs closed — 2-way ``merge-tree`` folding is nondeterministic for N>2
    (Decision 2), so the merge-resolution recognizer never even runs for it."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"), ("lane-c", "WP03"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    branches = []
    for lane_id, line_idx, text in (("lane-a", 0, "A\n"), ("lane-b", 4, "B\n"), ("lane-c", 9, "C\n")):
        branch = lane_branch_name(_MISSION_SLUG, lane_id, target_branch=_TARGET)
        branches.append(branch)
        _edit_shared_line(repo, branch, "src/shared.py", line_idx, text)
    _git(repo, "checkout", "-q", _TARGET)
    for branch in branches:
        _git(repo, "merge", "-q", "--no-edit", branch)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert "src/shared.py" not in claim.multi_lane_paths
    squash_claim = replace(claim, verify_reachability=False)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(path == "src/shared.py" for path, _blob in result.divergence.unattributable_blobs)


def test_squash_fails_closed_on_binary_conflict_between_two_lanes(tmp_path: Path) -> None:
    """A6: a binary file two approved lanes both modified differently — git
    ``merge-tree`` cannot textually merge binaries and reports a conflict
    (rc=1) — stays unattributable (FAIL closed), never a silent attribution."""
    repo = _init_repo(tmp_path)
    (repo / "asset.bin").write_bytes(b"\x00\x01\x02BASE")
    _git(repo, "add", "asset.bin")
    _git(repo, "commit", "-qm", "seed binary")
    window_base = _rev(repo, _TARGET)
    _git(repo, "branch", "lane-a", window_base)
    _git(repo, "checkout", "-q", "lane-a")
    (repo / "asset.bin").write_bytes(b"\x00\x01\x02AAAA")
    _git(repo, "add", "asset.bin")
    _git(repo, "commit", "-qm", "a")
    a_sha = _rev(repo, "lane-a")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "branch", "lane-b", window_base)
    _git(repo, "checkout", "-q", "lane-b")
    (repo / "asset.bin").write_bytes(b"\x00\x01\x02BBBB")
    _git(repo, "add", "asset.bin")
    _git(repo, "commit", "-qm", "b")
    b_sha = _rev(repo, "lane-b")
    _git(repo, "checkout", "-q", _TARGET)
    (repo / "asset.bin").write_bytes(b"\x00\x01\x02RESOLVED")
    _git(repo, "add", "asset.bin")
    _git(repo, "commit", "-qm", "squash: resolved binary")

    claim = _squash_claim(
        approved={"WP01": (a_sha,), "WP02": (b_sha,)},
        # A non-empty, UNRELATED entry so the F1-corollary "authored_blobs and
        # authored_deletions both empty while approved is non-empty" REFUSE
        # branch (:meth:`MergeOutcomeVerifier._verify_squash_content`) does not
        # short-circuit before the window scan reaches ``asset.bin`` at all —
        # this test is about the BINARY-CONFLICT fail-closed guard, not that
        # unrelated one.
        authored_blobs=frozenset({("unrelated.py", "0" * 40)}),
        window_base=window_base,
        manifest_wp_ids=frozenset({"WP01", "WP02"}),
        multi_lane_paths={
            "asset.bin": (
                LaneContribution("lane-a", a_sha, git_probes.blob_id_at(repo, a_sha, "asset.bin")),
                LaneContribution("lane-b", b_sha, git_probes.blob_id_at(repo, b_sha, "asset.bin")),
            )
        },
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(path == "asset.bin" for path, _blob in result.divergence.unattributable_blobs)


def test_squash_fails_closed_when_lane_commit_ref_is_unresolvable(tmp_path: Path) -> None:
    """'Absent base' residual (T005): a ``multi_lane_paths`` entry whose recorded
    lane commit ref is no longer resolvable cannot even run the merge
    simulation — the probe errors, and the axis never attributes vacuously; the
    result is FAILED or REFUSED, but never PASSed."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    _edit_shared_line(repo, lane_a, "src/shared.py", 0, "A\n")
    _edit_shared_line(repo, lane_b, "src/shared.py", 9, "B\n")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", lane_a)
    _git(repo, "merge", "-q", "--no-edit", lane_b)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert "src/shared.py" in claim.multi_lane_paths  # the map WOULD support the simulation
    contribs = claim.multi_lane_paths["src/shared.py"]
    corrupted = {"src/shared.py": (LaneContribution(contribs[0].lane_id, "deadbeef" * 5, contribs[0].authored_blob), contribs[1])}
    squash_claim = replace(claim, verify_reachability=False, multi_lane_paths=corrupted)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim)
    assert not result.is_pass


def test_squash_fails_closed_when_merge_tree_write_tree_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A7: simulate git<2.38 (no ``--write-tree`` support) for an otherwise-clean
    disjoint-hunk 2-lane path — the recognizer must never attempt the
    (unsupported) flag; stays unattributable (FAIL closed), never a silent skip
    to PASS."""
    lane_wp_pairs = (("lane-a", "WP01"), ("lane-b", "WP02"))
    repo, feature_dir, manifest, coord_base = _build_shared_file_lanes(tmp_path, lane_wp_pairs=lane_wp_pairs)
    lane_a = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    lane_b = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    _edit_shared_line(repo, lane_a, "src/shared.py", 0, "A\n")
    _edit_shared_line(repo, lane_b, "src/shared.py", 9, "B\n")
    _git(repo, "checkout", "-q", _TARGET)
    _git(repo, "merge", "-q", "--no-edit", lane_a)
    _git(repo, "merge", "-q", "--no-edit", lane_b)

    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_window_base=coord_base)
    assert "src/shared.py" in claim.multi_lane_paths
    monkeypatch.setattr("specify_cli.consolidation.reconciliation.merge_tree_write_tree_available", lambda _repo_root: False)
    squash_claim = replace(claim, verify_reachability=False)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, squash_claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert any(path == "src/shared.py" for path, _blob in result.divergence.unattributable_blobs)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "#5021 residual-2: 3-way merge-resolution content on a path with NO "
        "registered merge driver (src/shared.py -- stock `git merge-file` / "
        "`git merge-tree`, not a `spec-kitty merge-driver-*`). The manually- "
        "resolved blob equals neither parent and is reconstructable by no "
        "deterministic function, so the blob-attribution axis cannot attribute "
        "it. Distinct from the #5038 deterministic-union-driver class FIXED by "
        "driver-replay attribution (terminus-projection-driver-replay-01M3EC1K "
        "WP01): that class's paths (e.g. traces/*.md) carry a REGISTERED driver "
        "whose deterministic output is reproducible in-process; this path has "
        "none, so no analogous replay proof is possible. Soundly unfixable "
        "(research.md Decision 3); tracked separately from #5038 as its own "
        "dedicated follow-up issue #5051."
    ),
)
def test_squash_three_way_merge_resolution_is_unattributable(tmp_path: Path) -> None:
    """C-003 residual (#5021 residual-2): two approved lanes edit the SAME path
    with NO registered merge driver; the squash resolves it to a third blob (!=
    either lane's first-parent blob) via a stock git conflict + manual
    resolution. The desired behavior is a PASS (a genuine resolution is not
    removed content), but the blob axis cannot attribute it, so it FAILs --
    pinned as a strict xfail, exercising a REAL 3-way scenario, never a bare
    marker. NOT the #5038 class (driver-governed paths, fixed this WP via
    driver-replay attribution) -- see the xfail reason above."""
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
        # terminus-merge-resolution-attribution: wires the claim through the
        # merge-resolution recognizer so this scenario genuinely exercises the
        # ``git merge-tree`` conflict path (rc=1 on this SAME-line edit) rather
        # than short-circuiting on the pre-widening "absent from authored_blobs"
        # check alone — the residual this pin documents is the CONFLICT case,
        # not merely "the map is empty".
        multi_lane_paths={"src/shared.py": (LaneContribution("WP01", a_sha, alpha_blob), LaneContribution("WP02", b_sha, beta_blob))},
    )
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    # Desired (not yet achievable): a genuine resolution is not "removed content".
    assert result.is_pass


# --------------------------------------------------------------------------- #
# Mixed-lane canceled-content axis (T022-T027, mixed-lane-authorship-
# soundness / #5046 WP05). ``_canceled_content_divergence`` is exercised
# directly against HAND-BUILT claims (every existing test in this file
# constructs ``ApprovedWpCommitSet`` by keyword) so each contract C3 row is a
# small, fast, isolated git shape -- the mixed-lane WIRING through
# ``build_approved_wp_set`` (T022/T023) is covered separately below, and the
# full end-to-end real-CLI proof lives in ``tests/terminus/test_mixed_lane_*.py``.
# --------------------------------------------------------------------------- #

_CANCELED_WP = "WP02"
_CANCELED_LANE = "lane-a"
_CANCELED_PATH = "src/pkg/shared.py"


def _state_commit(repo: Path, base_sha: str, branch: str, path: str, content: str | None) -> str:
    """Commit *path* to *content* (``None`` removes it) on a fresh *branch* cut
    from *base_sha* -- an independent snapshot, never required to share
    ancestry with any other ref this test builds (``path_state_at`` reads each
    ref's tree in isolation)."""
    _git(repo, "checkout", "-q", "-B", branch, base_sha)
    full = repo / path
    if content is None:
        if full.exists():
            full.unlink()
            _git(repo, "add", "-A")
        _git(repo, "commit", "--allow-empty", "-qm", f"state: {path} absent")
    else:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        _git(repo, "add", str(full))
        _git(repo, "commit", "-qm", f"state: {path}")
    sha = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", _TARGET)
    return sha


def _canceled_claim(*, canceled_content: frozenset[CanceledPathState], window_base: str | None) -> ApprovedWpCommitSet:
    """A hand-built claim carrying only the canceled-content axis under test --
    every other field defaults empty/off, matching this module's established
    "construct ``ApprovedWpCommitSet`` by keyword" convention."""
    return ApprovedWpCommitSet(
        excluded_window_base=window_base,
        canceled_content=canceled_content,
    )


def _entry(*, canceled_state: str | None, pre_state: str | None, pre_state_by_survivor: bool = False, path: str = _CANCELED_PATH) -> CanceledPathState:
    return CanceledPathState(
        wp_id=_CANCELED_WP,
        lane_id=_CANCELED_LANE,
        path=path,
        canceled_state=canceled_state,
        pre_state=pre_state,
        pre_state_by_survivor=pre_state_by_survivor,
    )


@pytest.fixture
def _canceled_content_repo(tmp_path: Path) -> tuple[Path, str]:
    """A bare init repo plus its base SHA -- every C3-row test cuts its own
    target/window-base branches from this base via :func:`_state_commit`."""
    repo = _init_repo(tmp_path)
    return repo, _rev(repo, _TARGET)


def test_canceled_content_row_target_carries_canceled_window_did_not_fails(_canceled_content_repo: tuple[Path, str]) -> None:
    """C3 row 4: T == canceled_state, W != canceled_state -> FAIL."""
    repo, base = _canceled_content_repo
    canceled_blob = git_probes.blob_id_at(repo, _state_commit(repo, base, "target", _CANCELED_PATH, "wp02 content\n"), _CANCELED_PATH)
    window = _state_commit(repo, base, "window", _CANCELED_PATH, None)  # absent at the window base
    target = _state_commit(repo, base, "target2", _CANCELED_PATH, "wp02 content\n")
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=None)}), window_base=window)
    result = MergeOutcomeVerifier(repo).verify(target, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert result.divergence.canceled_content == (_entry(canceled_state=canceled_blob, pre_state=None),)
    text = result.divergence.describe()
    assert f"carries canceled {_CANCELED_WP}'s change" in text
    assert f"'{_CANCELED_PATH}'" in text
    assert f"(lane {_CANCELED_LANE})" in text
    assert "re-run spec-kitty consolidate" in text


def test_canceled_content_row_survivor_undone_fails(_canceled_content_repo: tuple[Path, str]) -> None:
    """C3 row 5: T == canceled_state == W, pre_state_by_survivor=True -> FAIL
    (SC-007: a surviving lane commit's approved change was undone)."""
    repo, base = _canceled_content_repo
    shared_sha = _state_commit(repo, base, "shared", _CANCELED_PATH, "shared value\n")
    canceled_blob = git_probes.blob_id_at(repo, shared_sha, _CANCELED_PATH)
    entry = _entry(canceled_state=canceled_blob, pre_state=None, pre_state_by_survivor=True)
    claim = _canceled_claim(canceled_content=frozenset({entry}), window_base=shared_sha)
    result = MergeOutcomeVerifier(repo).verify(shared_sha, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert entry in result.divergence.canceled_content


def test_canceled_content_row_target_already_had_it_unchanged(_canceled_content_repo: tuple[Path, str]) -> None:
    """C3 row 6: T == canceled_state == W, pre_state_by_survivor=False -> no
    finding (R4: the target already carried it, inherited from the base)."""
    repo, base = _canceled_content_repo
    shared_sha = _state_commit(repo, base, "shared2", _CANCELED_PATH, "shared value\n")
    canceled_blob = git_probes.blob_id_at(repo, shared_sha, _CANCELED_PATH)
    claim = _canceled_claim(
        canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=None, pre_state_by_survivor=False)}),
        window_base=shared_sha,
    )
    result = MergeOutcomeVerifier(repo).verify(shared_sha, claim)
    assert result.is_pass


def test_canceled_content_row_target_is_pre_state_unchanged(_canceled_content_repo: tuple[Path, str]) -> None:
    """C3 row 3 (pre-state branch): T == pre_state -> no finding (the canceled
    change never landed on the target at all)."""
    repo, base = _canceled_content_repo
    pre_sha = _state_commit(repo, base, "pre", _CANCELED_PATH, "pre-existing\n")
    pre_blob = git_probes.blob_id_at(repo, pre_sha, _CANCELED_PATH)
    canceled_sha = _state_commit(repo, base, "canceled", _CANCELED_PATH, "wp02 content\n")
    canceled_blob = git_probes.blob_id_at(repo, canceled_sha, _CANCELED_PATH)
    window = _state_commit(repo, base, "window3", _CANCELED_PATH, "window value\n")
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=pre_blob)}), window_base=window)
    result = MergeOutcomeVerifier(repo).verify(pre_sha, claim)
    assert result.is_pass


def test_canceled_content_row_target_is_window_base_unchanged(_canceled_content_repo: tuple[Path, str]) -> None:
    """C3 row 3 (window-base branch): T == W (and T != pre_state) -> no finding."""
    repo, base = _canceled_content_repo
    window = _state_commit(repo, base, "window4", _CANCELED_PATH, "window value\n")
    window_blob = git_probes.blob_id_at(repo, window, _CANCELED_PATH)
    canceled_sha = _state_commit(repo, base, "canceled4", _CANCELED_PATH, "wp02 content\n")
    canceled_blob = git_probes.blob_id_at(repo, canceled_sha, _CANCELED_PATH)
    pre_sha = _state_commit(repo, base, "pre4", _CANCELED_PATH, "some pre state\n")
    pre_blob = git_probes.blob_id_at(repo, pre_sha, _CANCELED_PATH)
    assert window_blob not in {canceled_blob, pre_blob}
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=pre_blob)}), window_base=window)
    result = MergeOutcomeVerifier(repo).verify(window, claim)
    assert result.is_pass


def test_canceled_content_row_merged_with_independent_change_refuses(_canceled_content_repo: tuple[Path, str]) -> None:
    """C3 row 7: T is neither canceled_state, pre_state, nor W -> REFUSE (R2)."""
    repo, base = _canceled_content_repo
    canceled_sha = _state_commit(repo, base, "canceled5", _CANCELED_PATH, "wp02 content\n")
    canceled_blob = git_probes.blob_id_at(repo, canceled_sha, _CANCELED_PATH)
    pre_sha = _state_commit(repo, base, "pre5", _CANCELED_PATH, "pre state\n")
    pre_blob = git_probes.blob_id_at(repo, pre_sha, _CANCELED_PATH)
    window = _state_commit(repo, base, "window5", _CANCELED_PATH, "window value\n")
    target = _state_commit(repo, base, "target5", _CANCELED_PATH, "totally independent value\n")
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=pre_blob)}), window_base=window)
    result = MergeOutcomeVerifier(repo).verify(target, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None
    assert _CANCELED_LANE in result.refusal_reason
    assert _CANCELED_WP in result.refusal_reason
    assert f"'{_CANCELED_PATH}'" in result.refusal_reason
    assert "merged with an independent change" in result.refusal_reason
    assert "re-run spec-kitty consolidate" in result.refusal_reason


def test_canceled_content_deletion_row_renders_deleted_by(_canceled_content_repo: tuple[Path, str]) -> None:
    """Deletion shape (``canceled_state is None``): FAIL renders "deleted by
    canceled <WP>", distinct from the add/modify "carries ... change" wording
    (WP02's rendering contract)."""
    repo, base = _canceled_content_repo
    target = _state_commit(repo, base, "target6", _CANCELED_PATH, None)  # WP02 deleted it
    window = _state_commit(repo, base, "window6", _CANCELED_PATH, "was here\n")  # window base still had it
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state=None, pre_state="deadbeef" * 5)}), window_base=window)
    result = MergeOutcomeVerifier(repo).verify(target, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    text = result.divergence.describe()
    assert f"deleted by canceled {_CANCELED_WP}" in text
    assert f"'{_CANCELED_PATH}'" in text
    assert "re-run spec-kitty consolidate" in text


def test_canceled_content_window_base_unresolved_refuses(_canceled_content_repo: tuple[Path, str]) -> None:
    """Entries exist but ``excluded_window_base`` is ``None`` -> REFUSE
    (T024's own fail-closed guard, distinct from the reachability path's)."""
    repo, base = _canceled_content_repo
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state="a" * 40, pre_state=None)}), window_base=None)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None
    assert "window base" in result.refusal_reason


def test_canceled_content_git_probe_error_refuses(_canceled_content_repo: tuple[Path, str]) -> None:
    """An unresolvable target/window ref -> REFUSE, not a crash (fail-closed)."""
    repo, base = _canceled_content_repo
    window = _state_commit(repo, base, "window7", _CANCELED_PATH, "value\n")
    claim = _canceled_claim(canceled_content=frozenset({_entry(canceled_state="a" * 40, pre_state=None)}), window_base=window)
    result = MergeOutcomeVerifier(repo).verify("not-a-real-ref-at-all", claim)
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason is not None
    assert "canceled-content" in result.refusal_reason


def test_canceled_content_empty_claim_is_noop(_canceled_content_repo: tuple[Path, str]) -> None:
    """No canceled-content entries at all (every existing claim) -> pure no-op,
    even with ``excluded_window_base=None`` -- byte-identical to pre-#5046."""
    repo, base = _canceled_content_repo
    claim = ApprovedWpCommitSet(manifest_wp_ids=frozenset())
    assert MergeOutcomeVerifier(repo)._canceled_content_divergence(_TARGET, claim) == ([], None)
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).is_pass


@pytest.mark.parametrize("verify_reachability", [True, False], ids=["merge_rebase", "squash"])
def test_canceled_content_fail_merges_into_pass_strategy_result(_canceled_content_repo: tuple[Path, str], verify_reachability: bool) -> None:
    """T024: a strategy PASS becomes FAIL carrying only the canceled-content
    divergence, under BOTH strategies (C-003 independence)."""
    repo, base = _canceled_content_repo
    canceled_sha = _state_commit(repo, base, "canceled8", _CANCELED_PATH, "wp02 content\n")
    canceled_blob = git_probes.blob_id_at(repo, canceled_sha, _CANCELED_PATH)
    window = _state_commit(repo, base, "window8", _CANCELED_PATH, None)
    target = _state_commit(repo, base, "target8", _CANCELED_PATH, "wp02 content\n")
    claim = ApprovedWpCommitSet(
        manifest_wp_ids=frozenset(),
        excluded_window_base=window,
        canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=None)}),
        verify_reachability=verify_reachability,
    )
    result = MergeOutcomeVerifier(repo).verify(target, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert result.divergence.canceled_content
    # No OTHER axis fired -- this claim carries no approved/authored/excluded
    # commits at all, so every other divergence field stays empty.
    assert result.divergence.missing_approved == ()
    assert result.divergence.reachable_excluded == ()
    assert result.divergence.unattributable_content == ()
    assert result.divergence.unattributable_blobs == ()
    assert result.divergence.unattributable_deletions == ()


def test_canceled_content_fail_merges_onto_existing_divergence(_canceled_content_repo: tuple[Path, str]) -> None:
    """T024: when the strategy axis ITSELF FAILs, the canceled-content entries
    are combined onto the SAME ``Divergence`` (``dataclasses.replace``), never
    replacing the strategy's own findings."""
    repo, base = _canceled_content_repo
    missing_sha = "b" * 40
    canceled_sha = _state_commit(repo, base, "canceled9", _CANCELED_PATH, "wp02 content\n")
    canceled_blob = git_probes.blob_id_at(repo, canceled_sha, _CANCELED_PATH)
    window = _state_commit(repo, base, "window9", _CANCELED_PATH, None)
    target = _state_commit(repo, base, "target9", _CANCELED_PATH, "wp02 content\n")
    claim = ApprovedWpCommitSet(
        approved={"WP01": (missing_sha,)},
        manifest_wp_ids=frozenset({"WP01"}),
        excluded_window_base=window,
        canceled_content=frozenset({_entry(canceled_state=canceled_blob, pre_state=None)}),
    )
    result = MergeOutcomeVerifier(repo).verify(target, claim)
    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert result.divergence.missing_approved == (("WP01", missing_sha),)
    assert result.divergence.canceled_content


def test_canceled_content_strategy_refuse_wins_over_fail_candidates() -> None:
    """A strategy REFUSE always stays REFUSE, never downgraded by merging in
    canceled-content FAIL candidates (REFUSE precedes FAIL throughout this
    module) -- exercised at the ``_merge_canceled_content_into_result`` seam
    directly, the merge point every strategy branch routes through."""
    from specify_cli.consolidation.reconciliation import _merge_canceled_content_into_result

    refused = VerifyResult.refused("claim integrity gone")
    merged = _merge_canceled_content_into_result(refused, [_entry(canceled_state="a" * 40, pre_state=None)])
    assert merged is refused


# --------------------------------------------------------------------------- #
# Mixed-lane WIRING (T022/T023) -- build_approved_wp_set + resolve_canceled_wp
# --------------------------------------------------------------------------- #


def _build_mixed_lane_entered_mission(
    tmp_path: Path,
    *,
    stamp_attribution: bool = True,
    entered_implementation: bool = True,
    canceled_path: str = _CANCELED_PATH,
    canceled_content: str = "wp02 content\n",
    wp01_approved_again: bool = False,
) -> tuple[Path, Path, LanesManifest, str, str]:
    """A single lane-a shared by an approved WP01 and a canceled WP02 that
    entered implementation and made one real commit -- the minimal C2 "mixed
    lane" shape, git-backed (real lane-tip commits, real event stamps).

    WP02's commit lands after WP01's approval, so the approval-stamp bound refuses the
    lane (#5720). *wp01_approved_again* records that review approved WP01 again at the
    lane tip, after WP02's cancel: the shape for a test whose subject is the
    canceled-content resolution that runs once the bound passes."""
    repo = _init_repo(tmp_path)
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": _MISSION_SLUG, "mission_id": _MISSION_ID, "mission_type": "software-dev", "target_branch": _TARGET}),
        encoding="utf-8",
    )
    lane = ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01", "WP02"),
        write_scope=("src/pkg",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch=_TARGET,
        lanes=[lane],
        computed_at=_now_iso(),
        computed_from="mixed-lane-recon-test",
    )
    from specify_cli.lanes.persistence import write_lanes_json

    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap mixed-lane mission")
    coord_base = _rev(repo, "HEAD")

    lane_branch = lane_branch_name(_MISSION_SLUG, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    def head() -> str:
        return _rev(repo, "HEAD")

    events: list[dict[str, object]] = [
        _event(i, "WP01", frm, to, at=f"2026-01-01T00:0{i}:00+00:00", lamport=i) for i, (frm, to) in enumerate(_APPROVE_CHAIN, start=1)
    ]
    for e in events:
        # WP01's approval is always stamped: the stamp names the commit review approved, and
        # ``stamp_attribution`` is only the knob for the CANCELED work package's own events.
        e["policy_metadata"] = {"lane_head": coord_base}

    if not entered_implementation:
        events.append(_event(90, "WP02", "planned", "canceled", at="2026-01-02T00:00:00+00:00", lamport=6))
    else:
        e_claim = _event(90, "WP02", "planned", "claimed", at="2026-01-02T00:00:00+00:00", lamport=6)
        if stamp_attribution:
            e_claim["policy_metadata"] = {"lane_head": head()}
        events.append(e_claim)
        e_prog = _event(91, "WP02", "claimed", "in_progress", at="2026-01-02T00:01:00+00:00", lamport=7)
        if stamp_attribution:
            e_prog["policy_metadata"] = {"lane_head": head()}
        events.append(e_prog)

        full = repo / canceled_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(canceled_content, encoding="utf-8")
        _git(repo, "add", str(full))
        _git(repo, "commit", "-qm", "feat: WP02 canceled content")

        e_cancel = _event(92, "WP02", "in_progress", "canceled", at="2026-01-02T00:02:00+00:00", lamport=8)
        if stamp_attribution:
            e_cancel["policy_metadata"] = {"lane_head": head()}
        events.append(e_cancel)
        if wp01_approved_again:
            rework = (("approved", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))
            events.extend(
                _event(93 + step, "WP01", frm, to, at=f"2026-01-02T00:1{step}:00+00:00", lamport=9 + step, lane_head=head())
                for step, (frm, to) in enumerate(rework)
            )

    _git(repo, "checkout", "-q", _TARGET)
    (feature_dir / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")
    _git(repo, "add", str((feature_dir / "status.events.jsonl").relative_to(repo)))
    _git(repo, "commit", "-qm", "record mixed-lane events")

    return repo, feature_dir, manifest, coord_base, lane_branch


def test_mixed_lane_wiring_unattributable_no_stamp_refuses(tmp_path: Path) -> None:
    """T022: a mixed lane's canceled WP with real commits but no attribution
    stamp -> the WHOLE claim REFUSEs, naming the lane, the WP, and the
    ``no_stamp`` reason's own ``no commit attribution`` phrase (WP02 T008's
    binding rendering contract)."""
    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=False)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    assert claim.surface_resolved
    assert claim.refusal is not None
    assert "mixed lane lane-a" in claim.refusal
    assert "WP02" in claim.refusal
    assert "no commit attribution" in claim.refusal
    assert "re-run spec-kitty consolidate" in claim.refusal


def test_mixed_lane_wiring_resolved_populates_canceled_content(tmp_path: Path) -> None:
    """T023: a resolvable mixed lane populates ``canceled_content`` from the
    resolver's ``Attributed`` outcome, and the claim does NOT refuse.

    WP01 was approved again after WP02's commit, so the approval-stamp bound passes
    (#5720) and the canceled-content resolution is what the claim reports."""
    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, wp01_approved_again=True)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
        excluded_window_base=coord_base,
    )
    assert claim.refusal is None
    assert claim.surface_resolved
    assert len(claim.canceled_content) == 1
    entry = next(iter(claim.canceled_content))
    assert entry.wp_id == "WP02"
    assert entry.lane_id == "lane-a"
    assert entry.path == _CANCELED_PATH


def test_mixed_lane_wiring_never_entered_implementation_is_noop(tmp_path: Path) -> None:
    """T022's own gate (delegated to ``resolve_canceled_wp``): a canceled WP
    that never entered implementation contributes nothing, and the claim
    still does not refuse."""
    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, entered_implementation=False)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    assert claim.refusal is None
    assert claim.canceled_content == frozenset()


@pytest.mark.parametrize("mixed", [False, True], ids=["plain-lane", "mixed-lane"])
def test_claim_reads_the_event_log_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mixed: bool) -> None:
    """NFR-001 (#5668): every claim with a code lane reads the status event log ONCE.

    The approved-bound check needs the approval stamps of every claim; it shares the read
    with the canceled-dependency and mixed-lane resolutions through one ``_ClaimEventLog``,
    so a mixed lane does not pay a second read. (Before #5668 a plain lane paid none.)
    """
    from specify_cli.status import read_events as real_read_events

    if mixed:
        repo, feature_dir, manifest, coord_base, _lane = _build_mixed_lane_entered_mission(tmp_path, wp01_approved_again=True)
        canceled = frozenset({"WP02"})
    else:
        repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01",))
        canceled = frozenset()
    reads: list[Path] = []

    def _counting_read(read_dir: Path) -> object:
        reads.append(read_dir)
        return real_read_events(read_dir)

    monkeypatch.setattr("specify_cli.status.read_events", _counting_read)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=canceled)
    assert claim.refusal is None
    assert len(reads) == 1


def test_mixed_lane_wiring_events_unreadable_refuses(tmp_path: Path) -> None:
    """NFR-002: a mixed lane whose ``status.events.jsonl`` is corrupted ->
    REFUSE naming the ``events_unreadable`` shape, not a raised exception.

    Exercised at ``_resolve_mixed_lane_canceled_content`` directly (module-
    private, same-package access — this file's established pattern), NOT
    through ``build_approved_wp_set``: ``materialize_snapshot`` reads the SAME
    file through the identically-strict ``read_event_stream`` parser BEFORE
    this function is ever reached, so a fully-corrupted file already refuses
    one step earlier via the pre-existing "coordination surface could not be
    materialized" path (unrelated to #5046) — the file-corruption REFUSE this
    test proves is the WIRING inside ``_resolve_mixed_lane_canceled_content``
    itself, which is exactly what production reaches if ``read_events`` ever
    raises for a reason ``materialize_snapshot``'s own read tolerated.
    """
    from specify_cli.consolidation.reconciliation import _resolve_mixed_lane_canceled_content

    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    (feature_dir / "status.events.jsonl").write_text("{not valid json\n", encoding="utf-8")

    work_packages = {"WP01": {"lane": "approved"}, "WP02": {"lane": "canceled"}}
    canceled_content, attested, refusal = _resolve_mixed_lane_canceled_content(
        repo, feature_dir, manifest, work_packages, frozenset({"WP02"}), coord_base, None, canceled_lane_commits=frozenset()
    )
    assert canceled_content == frozenset()
    assert attested == frozenset()
    assert refusal is not None
    assert "mixed lane lane-a" in refusal
    # The events_unreadable detail comes from the shared _DETAIL_TEMPLATES text.
    assert "the mission's lifecycle event log could not be read" in refusal
    assert "WP02" in refusal
    assert "re-run spec-kitty consolidate" in refusal
    assert "cannot be overridden" in refusal


def test_mixed_lane_wiring_unattributable_precedes_missing_approved_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T022: refusals take precedence over FAIL by construction -- a mixed
    lane's Unattributable outcome refuses the claim BEFORE the usual
    approved/authored/excluded collectors ever run, even when a resolvable
    (non-mixed) part of the manifest would otherwise FAIL."""
    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)

    def _fake_resolve(*_args: object, **kwargs: object) -> Unattributable:
        return Unattributable(UnattributableReason.CONTESTED_COMMIT, f"{kwargs['canceled_wp_id']} in {kwargs['lane_id']}: contested (test double)")

    monkeypatch.setattr("specify_cli.consolidation.reconciliation.resolve_canceled_wp", _fake_resolve)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    assert claim.refusal is not None
    assert "contested (test double)" in claim.refusal
    assert claim.approved == {}  # the usual collectors never ran


@pytest.mark.parametrize(
    "reason",
    [
        UnattributableReason.OPEN_WINDOW,
        UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP,
        UnattributableReason.CONTESTED_COMMIT,
        UnattributableReason.SPINE_UNREADABLE,
    ],
)
def test_mixed_lane_wiring_refusal_names_lane_wp_and_recovery_for_every_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: UnattributableReason
) -> None:
    """NFR-003: every Unattributable reason's composed refusal names the lane,
    the WP, and carries the recovery step -- the WIRING, not the reasons
    themselves (wp_attribution's own suite pins those exhaustively)."""
    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)

    def _fake_resolve(*_args: object, **kwargs: object) -> Unattributable:
        return Unattributable(reason, f"detail for {reason.value}")

    monkeypatch.setattr("specify_cli.consolidation.reconciliation.resolve_canceled_wp", _fake_resolve)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    assert claim.refusal is not None
    assert "lane-a" in claim.refusal
    assert "WP02" in claim.refusal
    assert f"detail for {reason.value}" in claim.refusal
    assert "re-run spec-kitty consolidate" in claim.refusal


def test_mixed_lane_wiring_passes_shared_bookkeeping_predicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The claim builder hands ``resolve_canceled_wp`` the SAME bookkeeping
    denylist the verifier itself uses (``functools.partial(_is_bookkeeping,
    ...)``), never a duplicate -- proved by calling the ``is_bookkeeping``
    callback the resolver received and comparing it against the module-level
    ``_is_bookkeeping`` function directly."""
    from specify_cli.consolidation.reconciliation import _is_bookkeeping

    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    captured: dict[str, object] = {}

    def _fake_resolve(*_args: object, **kwargs: object) -> Attributed:
        captured["is_bookkeeping"] = kwargs["is_bookkeeping"]
        return Attributed(commits=frozenset(), canceled_content=frozenset())

    monkeypatch.setattr("specify_cli.consolidation.reconciliation.resolve_canceled_wp", _fake_resolve)
    build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    is_bookkeeping = captured["is_bookkeeping"]
    for path in (".kittify/state.json", f"kitty-specs/{_MISSION_SLUG}/meta.json", "src/pkg/shared.py"):
        assert is_bookkeeping(path) == _is_bookkeeping(path, _MISSION_SLUG, f"kitty-specs/{_MISSION_SLUG}")


def test_mixed_lane_fully_canceled_single_wp_lane_is_not_mixed(tmp_path: Path) -> None:
    """A lane whose ONLY WP is simultaneously ``approved`` in the Lamport
    snapshot AND canceled-with-provenance per the caller (the "provenance
    override" shape ``_unresolvable_approved_lane_branches`` already exempts)
    is NOT a mixed lane -- there is no surviving WP to compare against, and
    such a lane's branch may legitimately not even exist."""
    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01", "WP02"))
    lane_b_branch = lane_branch_name(_MISSION_SLUG, "lane-b", target_branch=_TARGET)
    _git(repo, "branch", "-qD", lane_b_branch)  # WP02's lane branch no longer exists

    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    assert claim.refusal is None
    assert claim.canceled_content == frozenset()
    assert "WP01" in claim.approved


# --------------------------------------------------------------------------- #
# Byte-identical pin (Objectives & Success Criteria) -- no issue-5018-class
# regression surface: every pre-existing collector-derived field stays
# EXACTLY what the unmodified collectors compute, for both a non-mixed and a
# mixed-lane input.
# --------------------------------------------------------------------------- #


def test_claim_fields_are_byte_identical_to_unmodified_collectors_non_mixed(tmp_path: Path) -> None:
    from specify_cli.consolidation.reconciliation import (
        _collect_approved_shas,
        _collect_authored,
        _collect_excluded,
    )
    from specify_cli.status import materialize_snapshot

    repo, feature_dir, manifest, coord_base = _build_mission(tmp_path, approved_wps=("WP01", "WP02"))
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base)

    snapshot = materialize_snapshot(feature_dir)
    work_packages = snapshot.work_packages or {}
    expected_approved = _collect_approved_shas(repo, manifest, work_packages, coord_base)
    expected_authored_shas, expected_authored_patch_ids, expected_authored_blobs, expected_authored_deletions, expected_multi_lane_paths, *_ = _collect_authored(
        repo, manifest, work_packages, coord_base, canceled_lane_commits=frozenset()
    )
    expected_excluded_shas, expected_excluded_patch_ids = _collect_excluded(
        repo, manifest, coord_base, frozenset(), authored_shas=expected_authored_shas, authored_patch_ids=expected_authored_patch_ids
    )

    assert claim.approved == expected_approved
    assert claim.authored_shas == expected_authored_shas
    assert claim.authored_patch_ids == expected_authored_patch_ids
    assert claim.authored_blobs == expected_authored_blobs
    assert claim.authored_deletions == expected_authored_deletions
    assert claim.multi_lane_paths == expected_multi_lane_paths
    assert claim.excluded_shas == expected_excluded_shas
    assert claim.excluded_patch_ids == expected_excluded_patch_ids
    assert claim.canceled_content == frozenset()  # non-mixed mission: always empty


def test_claim_fields_are_byte_identical_to_unmodified_collectors_mixed_lane(tmp_path: Path) -> None:
    """The SAME pin, but for a genuinely mixed-lane mission -- proves the new
    T022/T023 wiring never perturbs the pre-existing collector fields even
    when it DOES populate ``canceled_content``."""
    from specify_cli.consolidation.reconciliation import (
        _collect_approved_shas,
        _collect_authored,
        _collect_excluded,
    )
    from specify_cli.status import materialize_snapshot

    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, wp01_approved_again=True)
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
    )
    assert claim.canceled_content  # the axis DID populate

    snapshot = materialize_snapshot(feature_dir)
    work_packages = snapshot.work_packages or {}
    expected_approved = _collect_approved_shas(repo, manifest, work_packages, coord_base)
    expected_authored_shas, expected_authored_patch_ids, expected_authored_blobs, expected_authored_deletions, expected_multi_lane_paths, *_ = _collect_authored(
        repo, manifest, work_packages, coord_base, canceled_lane_commits=frozenset()
    )
    expected_excluded_shas, expected_excluded_patch_ids = _collect_excluded(
        repo, manifest, coord_base, frozenset({"WP02"}), authored_shas=expected_authored_shas, authored_patch_ids=expected_authored_patch_ids
    )

    assert claim.approved == expected_approved
    assert claim.authored_shas == expected_authored_shas
    assert claim.authored_patch_ids == expected_authored_patch_ids
    assert claim.authored_blobs == expected_authored_blobs
    assert claim.authored_deletions == expected_authored_deletions
    assert claim.multi_lane_paths == expected_multi_lane_paths
    assert claim.excluded_shas == expected_excluded_shas
    assert claim.excluded_patch_ids == expected_excluded_patch_ids


# --------------------------------------------------------------------------- #
# recovery_guidance() REFUSE wording correction (D-4b / WP07: every REFUSE now
# restores the target, so the sentence claiming "nothing was mutated" is wrong).
# --------------------------------------------------------------------------- #


def test_refuse_recovery_guidance_reflects_target_restoration() -> None:
    result = VerifyResult.refused("some coordination-surface problem")
    guidance = result.recovery_guidance()
    assert "some coordination-surface problem" in guidance
    assert "restored" in guidance.lower()
    assert "no refs/worktrees were mutated" not in guidance  # the corrected (pre-#5046) claim


def test_refuse_recovery_guidance_does_not_double_a_trailing_period() -> None:
    result = VerifyResult.refused("mixed lane lane-a: canceled WP02 cannot be attributed, then re-run spec-kitty consolidate.")
    guidance = result.recovery_guidance()
    assert "consolidate.." not in guidance
    # Re-pinned 2026-09-29 (#5318/#5296 FR-009): the restore sentence now names every
    # branch the single rollback authority restores, not only the target.
    assert "then re-run spec-kitty consolidate. Every branch this consolidation moved" in guidance


def test_fail_recovery_guidance_reflects_target_restoration() -> None:
    result = VerifyResult.failed(Divergence(unattributable_deletions=("src/pkg/legacy.py",)))
    guidance = result.recovery_guidance()
    # Re-pinned 2026-09-29 (#5318/#5296 FR-009): see the REFUSE twin above.
    assert "is being restored to its pre-consolidation commit" in guidance
    assert "a branch marked NOT restored still carries this run's commits" in guidance
    assert "no refs/worktrees were mutated" not in guidance


# --------------------------------------------------------------------------- #
# FR-012 — operator-attested override (#5046 landing)
# --------------------------------------------------------------------------- #


def _append_attestation(repo: Path, feature_dir: Path, wp_id: str = "WP02", *, seq: int = 99, lamport: int = 50, lane_head: str | None = None) -> None:
    """Append a valid attestation record (the shape ``canceled_attestation`` writes)."""
    from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY, CANCELED_SUPERSEDED

    event = _event(seq, wp_id, "canceled", "canceled", at="2026-01-03T00:00:00+00:00", lamport=lamport)
    event.update(
        actor="operator",
        force=True,
        reason="operator attests canceled content absent or superseded: checked",
        reason_source="operator",
        policy_metadata={ATTESTATION_KEY: CANCELED_SUPERSEDED, **({"lane_head": lane_head} if lane_head else {})},
    )
    events_path = feature_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    _git(repo, "add", str(events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", "attest")


def _reapprove_wp01(repo: Path, feature_dir: Path, lane_branch: str, *, lamport: int = 60) -> None:
    """Record that review approved WP01 again at the CURRENT lane tip (back to ``in_progress``, then the review chain)."""
    head = _rev(repo, lane_branch)
    steps = (("approved", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))
    events_path = feature_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        for offset, (frm, to) in enumerate(steps):
            event = _event(900 + lamport + offset, "WP01", frm, to, at=f"2026-02-01T00:0{offset}:00+00:00", lamport=lamport + offset, lane_head=head)
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    _git(repo, "add", str(events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", "re-approve WP01 at the lane tip")


def test_attested_unstamped_mixed_lane_lifts_the_missing_stamp_but_not_the_approval_bound(tmp_path: Path) -> None:
    """An attested WP's ``no_stamp`` REFUSE is lifted, but its commits lie beyond WP01's approval stamp (#5720).

    The attestation covers attribution evidence only. WP02's own commit came after WP01
    was approved, so the claim refuses ``LANE_MOVED_AFTER_APPROVAL`` until WP01 is approved
    again at the lane tip; then it passes with the whole-lane fallback: no refusal, no per-WP content.
    """
    repo, feature_dir, manifest, coord_base, lane = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=False)
    _append_attestation(repo, feature_dir, lane_head=_rev(repo, lane))
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is not None
    assert claim.refusal.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert _CANCELED_PATH in claim.refusal
    assert "no commit attribution" not in claim.refusal

    _reapprove_wp01(repo, feature_dir, lane)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is None
    assert claim.canceled_content == frozenset()
    assert claim.attested_canceled_wp_ids == frozenset({"WP02"})


def _commit_on_lane(repo: Path, lane_branch: str, rel: str) -> None:
    """One more real content commit on *lane_branch* (leaves HEAD on the target)."""
    _git(repo, "checkout", "-q", lane_branch)
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("late\n", encoding="utf-8")
    _git(repo, "add", str(path))
    _git(repo, "commit", "-qm", f"feat: {rel}")
    _git(repo, "checkout", "-q", _TARGET)


@pytest.mark.parametrize("stamped", [True, False])
def test_attested_mixed_lane_refuses_content_committed_after_the_attestation(tmp_path: Path, stamped: bool) -> None:
    """#5668: an attestation lifts the attribution refusal, never the approved bound.

    Stamped or not, the attestation covers no commit: the late commit is beyond the
    approval stamp and the lane is refused, never skipped.
    """
    repo, feature_dir, manifest, coord_base, lane = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=False)
    _append_attestation(repo, feature_dir, lane_head=_rev(repo, lane) if stamped else None)
    _commit_on_lane(repo, lane, "src/late.py")
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is not None
    assert claim.refusal.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert "src/late.py" in claim.refusal


def test_attestation_never_lifts_visible_canceled_content(tmp_path: Path) -> None:
    """A FAIL stays a FAIL: attested, stamped, unsuperseded content is still collected."""
    repo, feature_dir, manifest, coord_base, _lane = _build_mixed_lane_entered_mission(tmp_path, wp01_approved_again=True)
    _append_attestation(repo, feature_dir)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is None
    assert {entry.path for entry in claim.canceled_content} == {_CANCELED_PATH}


def test_closed_world_reason_is_lifted_by_the_attestation_anchor_not_by_reason() -> None:
    """Review MAJOR: the closed world is bounded by the attestation stamp, never lifted wholesale."""
    assert UnattributableReason.COMMIT_OUTSIDE_WINDOWS not in OVERRIDABLE_REASONS


@pytest.mark.parametrize("reason", sorted(OVERRIDABLE_REASONS, key=lambda r: r.value))
def test_overridable_reason_refusal_names_the_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: UnattributableReason) -> None:
    repo, feature_dir, manifest, coord_base, lane = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    monkeypatch.setattr(
        "specify_cli.consolidation.reconciliation.resolve_canceled_wp",
        lambda *_a, **_k: Unattributable(reason, f"detail for {reason.value}"),
    )
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is not None
    assert '--attest-canceled-superseded WP02 --attest-reason "<what you checked>"' in claim.refusal
    assert "cannot clear" in claim.refusal
    # ... and an attestation lifts it. WP02's commit was made after WP01's approval, so the
    # approval-stamp bound refuses it until WP01 is approved again (#5720).
    _append_attestation(repo, feature_dir)
    lifted = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert lifted.refusal is not None and lifted.refusal.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert "--attest-canceled-superseded" not in lifted.refusal
    _reapprove_wp01(repo, feature_dir, lane)
    approved_again = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert approved_again.refusal is None


@pytest.mark.parametrize(
    "reason",
    [UnattributableReason.EVENTS_UNREADABLE, UnattributableReason.SPINE_UNREADABLE, UnattributableReason.CANCELED_LANE_CONTENT],
)
def test_infrastructure_refusal_is_not_overridable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: UnattributableReason) -> None:
    assert reason not in OVERRIDABLE_REASONS
    repo, feature_dir, manifest, coord_base, _lane = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    _append_attestation(repo, feature_dir)
    monkeypatch.setattr(
        "specify_cli.consolidation.reconciliation.resolve_canceled_wp",
        lambda *_a, **_k: Unattributable(reason, f"detail for {reason.value}"),
    )
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is not None
    assert "cannot be overridden" in claim.refusal
    assert "--attest-canceled-superseded" not in claim.refusal


def test_attested_wp_lifts_merged_with_independent_change(_canceled_content_repo: tuple[Path, str]) -> None:
    repo, base = _canceled_content_repo
    canceled_sha = _state_commit(repo, base, "canceled8", _CANCELED_PATH, "wp02 content\n")
    pre_sha = _state_commit(repo, base, "pre8", _CANCELED_PATH, "pre state\n")
    window = _state_commit(repo, base, "window8", _CANCELED_PATH, "window value\n")
    target = _state_commit(repo, base, "target8", _CANCELED_PATH, "totally independent value\n")
    entry = _entry(
        canceled_state=git_probes.blob_id_at(repo, canceled_sha, _CANCELED_PATH),
        pre_state=git_probes.blob_id_at(repo, pre_sha, _CANCELED_PATH),
    )
    refused = MergeOutcomeVerifier(repo).verify(target, _canceled_claim(canceled_content=frozenset({entry}), window_base=window))
    assert refused.status is VerifyStatus.REFUSE
    assert refused.refusal_reason is not None and f"--attest-canceled-superseded {_CANCELED_WP}" in refused.refusal_reason
    attested = replace(_canceled_claim(canceled_content=frozenset({entry}), window_base=window), attested_canceled_wp_ids=frozenset({_CANCELED_WP}))
    assert MergeOutcomeVerifier(repo).verify(target, attested).is_pass


def test_attested_wp_does_not_lift_canceled_content_fail(_canceled_content_repo: tuple[Path, str]) -> None:
    repo, base = _canceled_content_repo
    target = _state_commit(repo, base, "target9", _CANCELED_PATH, "wp02 content\n")
    window = _state_commit(repo, base, "window9", _CANCELED_PATH, "window value\n")
    entry = _entry(canceled_state=git_probes.blob_id_at(repo, target, _CANCELED_PATH), pre_state=None)
    attested = replace(_canceled_claim(canceled_content=frozenset({entry}), window_base=window), attested_canceled_wp_ids=frozenset({_CANCELED_WP}))
    assert MergeOutcomeVerifier(repo).verify(target, attested).status is VerifyStatus.FAIL


def test_closed_world_anchors_are_transitive_dependency_tips_plus_target_base() -> None:
    """Review BLOCKER: dependency-lane tips (transitively) and the target tip anchor the closed world."""
    from specify_cli.consolidation.reconciliation import _closed_world_anchors

    def lane(lane_id: str, deps: tuple[str, ...]) -> ExecutionLane:
        return ExecutionLane(lane_id=lane_id, wp_ids=(), write_scope=(), predicted_surfaces=(), depends_on_lanes=deps, parallel_group=0)

    manifest = LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch=_TARGET,
        lanes=[lane("lane-a", ()), lane("lane-b", ("lane-a", "lane-zz")), lane("lane-c", ("lane-b", "lane-a"))],
        computed_at=_now_iso(),
        computed_from="anchor-test",
    )
    anchors = _closed_world_anchors(manifest, manifest.lanes[2], "target-tip-sha", excluded_canceled_wp_ids=frozenset())
    assert anchors[-1] == "target-tip-sha"
    assert len(anchors) == 3  # lane-a, lane-b; the unknown lane-zz is ignored
    assert all("lane-" in a for a in anchors[:2])
    assert _closed_world_anchors(manifest, manifest.lanes[0], None, excluded_canceled_wp_ids=frozenset()) == []


def _commit_on_lane(repo: Path, lane_branch: str, path: str) -> str:
    _git(repo, "checkout", "-q", lane_branch)
    full = repo / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(f"{path}\n", encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", f"straggler {path}")
    sha = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", _TARGET)
    return sha


def test_attestation_exempts_only_commits_up_to_its_own_stamp(tmp_path: Path) -> None:
    """Review MAJOR: an attestation is bounded in time — a straggler committed AFTER it still REFUSEs."""
    repo, feature_dir, manifest, coord_base, lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    before = _commit_on_lane(repo, lane_branch, "src/pkg/before_attest.py")
    _append_attestation(repo, feature_dir, lane_head=_rev(repo, lane_branch))
    after = _commit_on_lane(repo, lane_branch, "src/pkg/after_attest.py")
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is not None, "a straggler committed after the attestation must still REFUSE"
    assert after[:10] in claim.refusal
    assert "'src/pkg/after_attest.py'" in claim.refusal
    assert before[:10] not in claim.refusal


def test_attestation_exempts_stragglers_from_the_closed_world_but_the_bound_refuses_until_reapproval(tmp_path: Path) -> None:
    """The attestation lifts the closed-world refusal for the stragglers it covers; the approval bound still refuses them (#5720)."""
    repo, feature_dir, manifest, coord_base, lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    _commit_on_lane(repo, lane_branch, "src/pkg/before_attest.py")
    unattested = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert unattested.refusal is not None and "outside every WP's recorded work window" in unattested.refusal
    _append_attestation(repo, feature_dir, lane_head=_rev(repo, lane_branch))
    attested = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert attested.refusal is not None
    assert attested.refusal.startswith("LANE_MOVED_AFTER_APPROVAL: ")
    assert "outside every WP's recorded work window" not in attested.refusal
    _reapprove_wp01(repo, feature_dir, lane_branch)
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is None
    assert {entry.path for entry in claim.canceled_content} == {_CANCELED_PATH}  # the visible FAIL still stands


# --------------------------------------------------------------------------- #
# One message names every refusal (#5720)
# --------------------------------------------------------------------------- #

_ALSO = "This Mission also has:"
_MOVED = "LANE_MOVED_AFTER_APPROVAL: "
_CLOSED_WORLD = "outside every WP's recorded work window"


def _claim_refusal(repo: Path, feature_dir: Path, manifest: LanesManifest, coord_base: str, canceled: frozenset[str] = frozenset({"WP02"})) -> str:
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=canceled)
    assert claim.refusal is not None
    return claim.refusal


def test_a_mixed_lane_refusal_is_followed_by_the_approval_bound_refusal_in_one_text(tmp_path: Path) -> None:
    """The first refusal stays byte-identical; the bound refusal the operator would meet next follows it, in one text."""
    from specify_cli.consolidation.reconciliation import _ClaimEventLog, _resolve_mixed_lane_canceled_content
    from specify_cli.status import materialize_snapshot

    repo, feature_dir, manifest, coord_base, lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    _commit_on_lane(repo, lane_branch, "src/pkg/late.py")

    refusal = _claim_refusal(repo, feature_dir, manifest, coord_base)

    _content, _attested, closed_world_alone = _resolve_mixed_lane_canceled_content(
        repo,
        feature_dir,
        manifest,
        materialize_snapshot(feature_dir).work_packages or {},
        frozenset({"WP02"}),
        coord_base,
        None,
        canceled_lane_commits=frozenset(),
        event_log=_ClaimEventLog(feature_dir),
    )
    assert closed_world_alone is not None and _CLOSED_WORLD in closed_world_alone
    assert refusal.startswith(closed_world_alone + "\n\n" + _ALSO + "\n" + _MOVED), refusal
    assert "src/pkg/late.py" in refusal.partition(_ALSO)[2]
    assert refusal.count(_MOVED) == 1


@pytest.mark.parametrize("attest_first", [True, False], ids=["attest-then-reapprove", "reapprove-then-attest"])
def test_a_mixed_lane_with_a_late_commit_needs_both_the_new_approval_and_the_attestation(tmp_path: Path, attest_first: bool) -> None:
    """Approving WP01 again does not clear the closed world, the attestation does not clear the bound, and the order does not matter."""
    repo, feature_dir, manifest, coord_base, lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    _commit_on_lane(repo, lane_branch, "src/pkg/late.py")
    assert _ALSO in _claim_refusal(repo, feature_dir, manifest, coord_base)

    steps = [
        lambda: _append_attestation(repo, feature_dir, lane_head=_rev(repo, lane_branch)),
        lambda: _reapprove_wp01(repo, feature_dir, lane_branch),
    ]
    first, second = steps if attest_first else steps[::-1]
    first()
    after_first = _claim_refusal(repo, feature_dir, manifest, coord_base)
    # One act alone leaves exactly the other problem, no more.
    if attest_first:
        assert after_first.startswith(_MOVED) and _CLOSED_WORLD not in after_first
    else:
        assert _CLOSED_WORLD in after_first and _MOVED not in after_first and _ALSO not in after_first
    second()
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert claim.refusal is None, claim.refusal


def test_every_canceled_work_package_that_refuses_is_named_in_the_one_text(tmp_path: Path) -> None:
    """Two canceled work packages on a mixed lane, neither with attribution evidence: both refusals, in WP order, and the bound after them."""
    repo, feature_dir, manifest, coord_base, _lane_branch = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=False)
    events_path = feature_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        for seq, (frm, to) in enumerate((("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "canceled")), start=70):
            handle.write(json.dumps(_event(seq, "WP03", frm, to, at=f"2026-01-04T00:0{seq - 70}:00+00:00", lamport=seq), sort_keys=True) + "\n")
    _git(repo, "add", str(events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", "WP03 canceled without stamps")
    three_wp_lane = replace(manifest, lanes=[replace(lane, wp_ids=("WP01", "WP02", "WP03")) for lane in manifest.lanes])

    refusal = _claim_refusal(repo, feature_dir, three_wp_lane, coord_base, frozenset({"WP02", "WP03"}))

    first, second, also = (refusal.find(marker) for marker in ("canceled WP02 cannot be attributed", "canceled WP03 cannot be attributed", _ALSO))
    assert 0 <= first < second < also, refusal
    assert refusal.count("mixed lane lane-a: canceled WP0") == 2


def test_the_first_refusal_stands_alone_when_the_approval_bound_cannot_be_computed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A git probe failure, and an unreadable event log, each leave the first refusal as the whole message."""
    from specify_cli.consolidation import reconciliation
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.status import StoreError

    _repo, feature_dir, _manifest, _base, _lane = _build_mixed_lane_entered_mission(tmp_path)

    def probe_failed() -> reconciliation._BoundVerdict:
        raise GitProbeError("git log failed")

    assert reconciliation._compound_refusal("first", probe_failed, reconciliation._ClaimEventLog(feature_dir)) == "first"

    def unreadable(_dir: Path) -> list[object]:
        raise StoreError("corrupt line 3")

    monkeypatch.setattr("specify_cli.status.read_events", unreadable)
    bound = reconciliation._BoundVerdict(refusal="bound")
    assert reconciliation._compound_refusal("first", lambda: bound, reconciliation._ClaimEventLog(feature_dir)) == "first"


# --------------------------------------------------------------------------- #
# Nothing a canceled work package does covers a commit made after the approval (#5720)
# --------------------------------------------------------------------------- #

#: ``None`` is the commit made after WP01's approval; a pair is a forced ``(from, to)`` move of WP02.
_COMMIT = None
_LAUNDERING_SHAPES: dict[str, tuple[tuple[str, str] | None, ...]] = {
    "no-further-event": (_COMMIT,),
    "forced-recancel": (_COMMIT, ("canceled", "canceled")),
    "recancel-from-planned": (_COMMIT, ("canceled", "planned"), ("planned", "canceled")),
    "blocked-window-around-the-commit": (("canceled", "blocked"), _COMMIT, ("blocked", "canceled")),
    "review-window-around-the-commit": (("canceled", "for_review"), _COMMIT, ("for_review", "canceled")),
}


def _force_wp02(repo: Path, feature_dir: Path, lane_branch: str, frm: str, to: str, *, seq: int) -> None:
    """Append one forced operator move of WP02, stamped at the current lane tip as the status shells stamp it."""
    event = _event(200 + seq, "WP02", frm, to, at=f"2026-03-01T00:{seq:02d}:00+00:00", lamport=20 + seq, lane_head=_rev(repo, lane_branch))
    event.update(actor="operator", force=True, reason="forced", reason_source="operator")
    events_path = feature_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    _git(repo, "add", str(events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", f"force WP02 {frm} -> {to}")


@pytest.mark.parametrize("shape", sorted(_LAUNDERING_SHAPES))
def test_no_status_move_of_a_canceled_work_package_covers_a_commit_made_after_the_approval(tmp_path: Path, shape: str) -> None:
    """No status event of a canceled work package covers a commit for the approval-stamp bound.

    Whatever the operator does to WP02 around a commit made after WP01's approval, the first
    refusal names ``LANE_MOVED_AFTER_APPROVAL`` for it, and a canceled-superseded attestation
    recorded at the lane tip leaves exactly that refusal.
    """
    repo, feature_dir, manifest, coord_base, lane = _build_mixed_lane_entered_mission(tmp_path, entered_implementation=False)
    late = ""
    for seq, step in enumerate(_LAUNDERING_SHAPES[shape]):
        if step is _COMMIT:
            late = _commit_on_lane(repo, lane, "src/pkg/late.py")
        else:
            _force_wp02(repo, feature_dir, lane, *step, seq=seq)

    unattested = _claim_refusal(repo, feature_dir, manifest, coord_base)
    assert _MOVED in unattested and late[:7] in unattested.partition(_MOVED)[2], unattested

    _append_attestation(repo, feature_dir, lane_head=_rev(repo, lane))
    attested = _claim_refusal(repo, feature_dir, manifest, coord_base)
    assert attested.startswith(_MOVED) and late[:7] in attested, attested


@pytest.mark.parametrize("entry", ["claim-builder", "orchestrator-entry"])
def test_canceled_work_committed_after_the_approval_refuses_until_the_work_package_is_approved_again(tmp_path: Path, entry: str) -> None:
    """A canceled work package's own stamped work window, opened after WP01's approval, exempts none of its commits (#5720).

    The canceled-work attribution assigns the commit to WP02 and there is no closed-world
    refusal, so the approval-stamp refusal is the whole message. Once WP01 is approved
    again at the lane tip the bound passes, and the claim reports WP02's content for the
    canceled-content check.
    """
    from specify_cli.consolidation.reconciliation import _BOTH_NEEDED, approved_bound_refusal

    repo, feature_dir, manifest, coord_base, lane = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=True)
    wp02_commit = _rev(repo, lane)

    def refusal() -> str | None:
        if entry == "claim-builder":
            return build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"})).refusal
        text: str | None = approved_bound_refusal(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
        return text

    refused = refusal()
    assert refused is not None and refused.startswith(_MOVED), refused
    assert wp02_commit[:7] in refused and _CANCELED_PATH in refused
    assert _ALSO not in refused and _BOTH_NEEDED not in refused

    _reapprove_wp01(repo, feature_dir, lane)
    assert refusal() is None
    claim = build_approved_wp_set(repo, feature_dir, manifest, coord_base_ref=coord_base, excluded_canceled_wp_ids=frozenset({"WP02"}))
    assert {entry_.path for entry_ in claim.canceled_content} == {_CANCELED_PATH}


def test_two_canceled_work_packages_cannot_hide_a_commit_made_after_the_approval_between_them(tmp_path: Path) -> None:
    """Canceled work made after the approval refuses even when a second canceled work package supersedes it (#5720).

    WP02 is reopened and writes a file; WP03 overwrites it and then writes WP02's bytes
    back. Each canceled work package's content is superseded or equal to its own pre-state,
    so the canceled-content resolution finds nothing; WP01 was never approved again.
    """
    repo, feature_dir, manifest, coord_base, lane = _build_mixed_lane_entered_mission(tmp_path, entered_implementation=False)
    late = "src/pkg/late.py"

    def write(content: str) -> str:
        _git(repo, "checkout", "-q", lane)
        (repo / late).parent.mkdir(parents=True, exist_ok=True)
        (repo / late).write_text(content, encoding="utf-8")
        _git(repo, "add", late)
        _git(repo, "commit", "-qm", f"late: {content.strip()}")
        sha = _rev(repo, "HEAD")
        _git(repo, "checkout", "-q", _TARGET)
        return sha

    _force_wp02(repo, feature_dir, lane, "canceled", "in_progress", seq=0)
    first = write("payload\n")
    _force_wp02(repo, feature_dir, lane, "in_progress", "canceled", seq=1)
    events_path = feature_dir / "status.events.jsonl"

    def wp03(seq: int, frm: str, to: str) -> None:
        event = _event(300 + seq, "WP03", frm, to, at=f"2026-03-02T00:{seq:02d}:00+00:00", lamport=40 + seq, lane_head=_rev(repo, lane))
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        _git(repo, "add", str(events_path.relative_to(repo)))
        _git(repo, "commit", "-qm", f"WP03 {frm} -> {to}")

    wp03(0, "planned", "claimed")
    wp03(1, "claimed", "in_progress")
    write("junk\n")
    write("payload\n")
    wp03(2, "in_progress", "canceled")
    three_wp_lane = replace(manifest, lanes=[replace(lane_, wp_ids=("WP01", "WP02", "WP03")) for lane_ in manifest.lanes])

    refusal = _claim_refusal(repo, feature_dir, three_wp_lane, coord_base, frozenset({"WP02", "WP03"}))

    assert refusal.startswith(_MOVED) and first[:7] in refusal, refusal
