"""Permanent guard: claim-time consolidation blocker (#2795, WP01, CLOSED).

**Landing note (2026-08, `tests/regression/` campsite clean).** #2795 is
fixed; this is a permanent regression guard, not a red-first reproduction, so
it carries no `regression` marker and lives with its sibling claim/VCS-lock
tests here rather than in `tests/regression/`. (#2795 is also the
Mechanism-A issue split out and closed separately from #2367, referenced by
`tests/merge/test_issue_2367_bake_strand.py`.) The issue number is kept as
history below.

The *reported* cause — a dirty coordination-worktree ``meta.json`` — is
**refuted**. The real mechanism, reproduced here through the pre-existing
entry points (DIRECTIVE_041):

1. A claim writes a VCS lock into the mission's ``meta.json`` via the
   production writer :func:`specify_cli.mission_metadata.set_vcs_lock`, which
   mutates *only* the ``vcs`` and ``vcs_locked_at`` keys.
2. That write lands in the **PRIMARY-partition** ``meta.json`` — the directory
   :func:`mission_runtime.placement_seam` resolves ``SPEC`` reads to. This
   test asserts that partition routing explicitly so the topology-agnostic
   nature of the fix (C-004) is pinned.
3. When the mission later tries to consolidate itself,
   :func:`specify_cli.git.ref_advance.advance_branch_ref` dirty-scans the
   checked-out worktree, sees the tracked ``M meta.json``, and misclassifies
   the lock stamp as destructive local state ->
   :class:`RefAdvanceDirtyWorktreeError`. The mission cannot advance its own
   branch ref.

The fix (WP01) teaches the dirty scan that a ``meta.json`` whose only diff
against HEAD is a subset of the VCS-lock fields is a regenerable claim stamp,
not operator data: the resync ``git reset --hard`` legitimately discards it and
the next claim regenerates it (behaviour-preserving, C-010). Historically a
*genuine* ``meta.json`` edit still blocked here (no false-open) when the caller
passed no residue predicate.

lifecycle-gate-execution-context-01KY72GQ WP13 (IC-07c) / FR-012 superseded
that narrower invariant for callers that inject the canonical churn owner: every
production ``advance_branch_ref`` caller (``merge/ordering.py``,
``lanes/merge.py``, ``coordination/commit_router.py``) now passes
``context=residue_when(is_toolchain_generated_churn)``, which classifies ANY ``meta.json``
change (not just a vcs-lock-only one) as spec-kitty's own bookkeeping churn —
closing the #2795 cross-gate disagreement
(``tests/architectural/test_cross_gate_churn_agreement.py``, C7) where
``merge/git_probes.py`` / ``review/dirty_classifier.py`` already exempted a
tracked-modified ``meta.json`` unconditionally. See
``test_genuine_meta_edit_no_longer_blocks_consolidation_when_residue_routed``
below for the superseding pin.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from mission_runtime import MissionArtifactKind, placement_seam

from kernel.meta_decode import MetaDecodeError, decode_meta
from kernel.vcs_lock import is_vcs_lock_only_change

from tests.residue_predicate import residue_when
from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    advance_branch_ref,
)
from specify_cli.mission_metadata import load_meta, set_vcs_lock

# This suite shells out to real git via subprocess fixtures; register it with the
# gate-coverage system (C-006) so test_no_new_orphan_surfaces recognises it.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "2795-claim-blocker"
MISSION_BRANCH = "kitty/mission-2795-claim-blocker"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _valid_meta() -> dict[str, object]:
    """A realistic, schema-valid mission ``meta.json`` payload."""
    return {
        "slug": MISSION_SLUG,
        "mission_slug": MISSION_SLUG,
        "friendly_name": "Claim-time consolidation blocker",
        "mission_type": "software-dev",
        "target_branch": "remediation/coord-lifecycle-gates",
        "created_at": "2026-07-24T00:00:00+00:00",
    }


def _build_repo_with_checked_out_mission_branch(root: Path) -> tuple[Path, Path, str]:
    """Return ``(repo_root, worktree, new_sha)``.

    ``repo_root`` sits on ``main``; ``worktree`` has ``MISSION_BRANCH`` checked
    out at the commit that carries the mission's ``meta.json``. ``new_sha`` is a
    fast-forward descendant of that tip, so :func:`advance_branch_ref` will
    advance ``MISSION_BRANCH`` and resync the worktree.
    """
    repo_root = root / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.invalid")
    _git(repo_root, "config", "user.name", "T")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seed")

    # The mission branch carries the PRIMARY-partition meta.json. Resolve the
    # write target through the production placement seam (SPEC read dir) so the
    # test pins the partition the real claim writes into.
    feature_dir = placement_seam(repo_root, MISSION_SLUG).read_dir(MissionArtifactKind.SPEC)
    assert feature_dir == repo_root / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(_valid_meta(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo_root, "checkout", "-q", "-b", MISSION_BRANCH)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "mission: seed meta.json")

    # A fast-forward descendant to advance the mission branch to.
    (repo_root / "docs").mkdir()
    (repo_root / "docs" / "note.md").write_text("consolidation target\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "mission: consolidation commit")
    new_sha = _git(repo_root, "rev-parse", "HEAD").stdout.strip()

    # Reset the mission branch back to the meta-seed commit so ``new_sha`` is a
    # genuine forward advance, and hand the checkout to a dedicated worktree so
    # repo_root does not hold MISSION_BRANCH itself.
    _git(repo_root, "reset", "--hard", "HEAD~1")
    _git(repo_root, "checkout", "-q", "main")
    worktree = root / "wt"
    _git(repo_root, "worktree", "add", "-q", str(worktree), MISSION_BRANCH)
    return repo_root, worktree, new_sha


def _stamp_vcs_lock(worktree: Path) -> None:
    """Apply the production claim-time VCS lock into the worktree's meta.json."""
    feature_dir = worktree / "kitty-specs" / MISSION_SLUG
    set_vcs_lock(feature_dir, vcs_type="git", locked_at="2026-07-24T01:23:45+00:00")


def test_vcs_lock_only_meta_change_does_not_block_consolidation(tmp_path: Path) -> None:
    """A claim's VCS-lock stamp must not block the mission's self-consolidation.

    RED before the fix: ``advance_branch_ref`` raises
    ``RefAdvanceDirtyWorktreeError`` on the ``M meta.json`` lock stamp.
    GREEN after: the advance succeeds and the resync drops the regenerable lock.
    """
    repo_root, worktree, new_sha = _build_repo_with_checked_out_mission_branch(tmp_path)
    _stamp_vcs_lock(worktree)

    # The lock write landed in the PRIMARY partition and is a tracked M entry.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "kitty-specs/2795-claim-blocker/meta.json" in status
    assert " M " in status or status.startswith(" M")

    # Post-fix: consolidation advances cleanly despite the lock stamp.
    advance_branch_ref(
        repo_root,
        MISSION_BRANCH,
        new_sha,
        context=residue_when(is_toolchain_generated_churn),
    )

    advanced = subprocess.run(
        ["git", "rev-parse", MISSION_BRANCH],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    assert advanced == new_sha
    # The resync discarded the lock; the next claim regenerates it (C-010).
    resynced = load_meta(worktree / "kitty-specs" / MISSION_SLUG)
    assert resynced is not None
    assert "vcs_locked_at" not in resynced


def _write_genuine_meta_edit(worktree: Path) -> None:
    """Write an operator-meaningful ``meta.json`` change beyond the VCS-lock field set."""
    feature_dir = worktree / "kitty-specs" / MISSION_SLUG
    meta = load_meta(feature_dir)
    assert meta is not None
    meta["friendly_name"] = "Operator renamed this mission"
    meta["vcs"] = "git"
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_genuine_meta_edit_still_blocks_consolidation_without_residue_predicate(
    tmp_path: Path,
) -> None:
    """No false-open for a caller that supplies NO residue predicate: a real
    ``meta.json`` edit still refuses the advance via the narrow, content-aware
    vcs-lock-only check alone."""
    repo_root, worktree, new_sha = _build_repo_with_checked_out_mission_branch(tmp_path)
    _write_genuine_meta_edit(worktree)

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo_root, MISSION_BRANCH, new_sha)


def test_genuine_meta_edit_no_longer_blocks_when_residue_routed(tmp_path: Path) -> None:
    """lifecycle-gate-execution-context-01KY72GQ WP13 (IC-07c) / FR-012: for a
    caller that injects the canonical churn owner (every production
    ``advance_branch_ref`` caller does), a genuine ``meta.json`` edit is now ALSO
    exempted as spec-kitty's own bookkeeping churn -- closing the #2795 cross-gate
    disagreement where ``merge/git_probes.py`` / ``review/dirty_classifier.py``
    already exempted a tracked-modified ``meta.json`` unconditionally while
    ``advance_branch_ref`` alone still blocked it (C7,
    ``tests/architectural/test_cross_gate_churn_agreement.py``).

    This supersedes the former ``test_genuine_meta_edit_still_blocks_consolidation``,
    which asserted the OPPOSITE for this same scenario under the pre-WP13
    ``coord_owned_filenames`` mechanism (which never reached tracked entries at
    all, so this scenario was unaffected by it either way). The narrower,
    no-predicate contract (a genuine edit still blocks) is preserved separately by
    :func:`test_genuine_meta_edit_still_blocks_consolidation_without_residue_predicate`.
    """
    repo_root, worktree, new_sha = _build_repo_with_checked_out_mission_branch(tmp_path)
    _write_genuine_meta_edit(worktree)

    advance_branch_ref(
        repo_root,
        MISSION_BRANCH,
        new_sha,
        context=residue_when(is_toolchain_generated_churn),
    )

    advanced = subprocess.run(
        ["git", "rev-parse", MISSION_BRANCH],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    assert advanced == new_sha, (
        "post-WP13, a genuine meta.json edit is toolchain churn for a caller "
        "that injects is_toolchain_generated_churn; the advance must succeed."
    )


# --- Pure-helper unit coverage (retargeted onto the kernel comparator, WP02) ---
#
# ``ref_advance._is_vcs_lock_only_meta_change`` / ``_parse_meta_object`` were
# deleted; ref_advance now rides ``kernel.vcs_lock.is_vcs_lock_only_change``
# (sentinel: absent != present-but-null, C-005) and ``kernel.meta_decode``. The
# kernel comparator's argument order is ``(before=committed, after=worktree)`` --
# the OPPOSITE of the retired helper's ``(worktree, committed)`` -- so the calls
# below pass ``(committed, worktree)``.


def test_lock_only_change_is_recognised() -> None:
    committed = {"slug": "m", "vcs": "git"}
    worktree = {"slug": "m", "vcs": "git", "vcs_locked_at": "2026-07-24T00:00:00+00:00"}
    assert is_vcs_lock_only_change(committed, worktree) is True


def test_empty_diff_is_lock_only_under_kernel_comparator() -> None:
    # C-005 flip: the retired ref_advance helper returned False on an empty diff
    # ("nothing to tolerate"); the canonical kernel comparator treats two
    # identical mappings as lock-only (the empty set of differences is trivially
    # a subset of the lock fields) -> True.
    meta = {"slug": "m", "vcs": "git"}
    assert is_vcs_lock_only_change(dict(meta), dict(meta)) is True


def test_non_lock_key_change_blocks() -> None:
    committed = {"slug": "m", "friendly_name": "old"}
    worktree = {"slug": "m", "friendly_name": "new", "vcs_locked_at": "x"}
    assert is_vcs_lock_only_change(committed, worktree) is False


def test_added_meta_file_exceeds_lock_set() -> None:
    # committed == {} models a newly added meta.json; every key is "changed".
    worktree = {"slug": "m", "mission_type": "software-dev", "vcs": "git"}
    assert is_vcs_lock_only_change({}, worktree) is False


def test_added_meta_file_with_only_lock_keys_is_lock_only() -> None:
    # A degenerate meta.json carrying nothing but lock keys is still a stamp.
    assert is_vcs_lock_only_change({}, {"vcs": "git"}) is True


def test_decode_meta_none_mode_absorbs_malformed_and_non_object() -> None:
    # The silent-mode contract that replaces the retired ``_parse_meta_object``.
    assert decode_meta("{not json", on_malformed="none") is None
    assert decode_meta("[1, 2, 3]", on_malformed="none") is None
    assert decode_meta('{"vcs": "git"}') == {"vcs": "git"}


def test_decode_meta_raise_mode_fails_loud_on_malformed() -> None:
    # The fail-closed contract ref_advance now routes onto (FR-003..FR-007).
    with pytest.raises(MetaDecodeError):
        decode_meta("{not json", on_malformed="raise")
    with pytest.raises(MetaDecodeError):
        decode_meta("[1, 2, 3]", on_malformed="raise")
