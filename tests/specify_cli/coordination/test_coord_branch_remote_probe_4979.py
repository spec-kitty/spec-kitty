"""Repro #4979 — the coordination branch-existence probe never consults the
remote, so a coord branch that lives only on origin (single-branch / shallow /
CI clone, or a pruned local branch) is misclassified as "never
created"/"deleted".

Mechanism (root cause, FR-001/FR-002/FR-003/FR-007): ``_coord_branch_exists``
(``src/specify_cli/coordination/surface_resolver.py``) decides branch
presence from only the local head (``refs/heads/<coord>``) plus
already-fetched remote-tracking refs (``refs/remotes/*/<coord>``, the #2614
residual). Neither exists on a checkout that never fetched the coordination
branch — a ``git clone --single-branch -b main``, or a full clone whose
remote-tracking ref for the coord branch was pruned — even though the branch
is still reachable via ``git ls-remote`` on a configured remote. The probe
reports "absent", which fires ``CoordinationBranchDeleted`` on the read path
(#1848 data-loss carve-out) for a branch that was never deleted.

RED-first (T001): built through the REAL git plumbing (a genuine bare origin,
a genuine push, a genuine single-branch clone / branch prune) and the REAL
production read entry point (``mission_runtime.placement_seam(...).read_dir``,
the same seam ``coord-read-fail-closed-01M38VVH`` pins in
``tests/mission_runtime/test_coord_read_seam.py``), not a mocked subprocess
boundary. Pre-fix, both remote-only fixtures raise ``CoordinationBranchDeleted``
(RED — the branch was never deleted). Post-fix they raise
``CoordinationWorktreeUnmaterialized`` instead (FR-007 — a remote-only branch
is present-but-unmaterialized, never a silent empty-primary substitution, and
never the deleted-branch verdict).

Section B (added at T003, once the shared ``remote_branch_lookup`` primitive
exists) pins NFR-001: the remote round-trip fires ONLY after the local-head
and ``refs/remotes/`` fast paths both miss.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
    _coord_branch_exists,
)
from specify_cli.core.mission_creation import MissionCreationResult
from specify_cli.git.remote_probes import RemoteLookup
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_WORK_BRANCH = "remote-probe-4979-work"


# ---------------------------------------------------------------------------
# Fixture helpers — real git only, no subprocess mocking (ATDD real-vector rule)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _init_git_repo(repo, branch=_WORK_BRANCH)
    return repo


def _create_coord_mission(repo: Path, slug: str) -> MissionCreationResult:
    """Mint a real COORD-topology mission (coordination branch created in git,
    never materialized as a worktree — mirrors
    ``test_coord_read_seam.py::test_unmaterialized_coord_read_raises_instead_of_empty_primary``).
    """
    result = _create_mission(repo, slug, MissionTopology.COORD)
    assert result.coordination_branch, "fixture precondition: coord branch must be minted"
    return result


def _bare_origin(tmp_path: Path, name: str = "origin.git") -> Path:
    bare = tmp_path / name
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    return bare


def _push(repo: Path, bare: Path, *branches: str) -> None:
    _git(repo, "remote", "add", "origin", str(bare))
    for branch in branches:
        _git(repo, "push", "-q", "origin", f"{branch}:{branch}")


def _configure_clone(clone: Path) -> None:
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")
    _git(clone, "config", "commit.gpgsign", "false")


def _remote_tracking_branch_names(repo: Path) -> set[str]:
    """Branch names (``<remote>/`` prefix stripped) carried by ``refs/remotes/``.

    Mirrors ``_coord_branch_exists``'s own ``refs/remotes/`` scan exactly
    (partition once on the FIRST ``/`` after the ``refs/remotes/`` prefix) so
    a branch name containing ``/`` (every coordination branch does —
    ``kitty/mission-<slug>``) is not mis-truncated by a naive ``rsplit``.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "for-each-ref", "--format=%(refname)", "refs/remotes/"],
        capture_output=True,
        text=True,
        check=True,
    )
    prefix = "refs/remotes/"
    names: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.startswith(prefix):
            continue
        _, _, branch = line[len(prefix) :].partition("/")
        names.add(branch)
    return names


def _prune_remote_tracking_ref(repo: Path, coord_branch: str) -> None:
    """Delete ``refs/remotes/origin/<coord_branch>`` while origin still carries
    the branch — simulates a stale/pruned remote-tracking cache (the
    "pruned-origin variant" #4979 names): a plain ``git push`` updates the
    local remote-tracking ref by default (git >= a long-standing default), so
    a bare push+local-branch-delete alone is NOT remote-only — the
    already-fixed #2614 ``refs/remotes/`` scan would still find it. Deleting
    the tracking ref directly is what actually reproduces "neither
    refs/heads/<coord> nor refs/remotes/*/<coord> resolves, yet origin's
    `git ls-remote` still lists it".
    """
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "-d", f"refs/remotes/origin/{coord_branch}"],
        check=True,
    )


def _assert_remote_only(site: Path, coord_branch: str) -> None:
    """Fixture precondition: neither a local head nor a remote-tracking ref
    resolves the coord branch at *site*, but ``git ls-remote origin`` still
    lists it — the exact ambiguity #4979 is about.
    """
    local = subprocess.run(
        ["git", "-C", str(site), "rev-parse", "--verify", "--quiet", f"refs/heads/{coord_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert local.returncode != 0, f"fixture precondition failed: local head {coord_branch!r} still resolves at {site}"
    tracked = _remote_tracking_branch_names(site)
    assert coord_branch not in tracked, f"fixture precondition failed: refs/remotes/*/{coord_branch} still resolves at {site}"
    ls_remote = subprocess.run(
        ["git", "-C", str(site), "ls-remote", "--heads", "origin", coord_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ls_remote.returncode == 0 and ls_remote.stdout.strip(), f"fixture precondition failed: origin no longer lists {coord_branch!r} via ls-remote"


# ---------------------------------------------------------------------------
# Section A — RED-first: remote-only coord branch must not be "deleted"
# ---------------------------------------------------------------------------


def test_pruned_local_branch_remote_only_coord_branch_is_not_deleted(tmp_path: Path) -> None:
    """FR-001/FR-007 (#4979): a coord branch pushed to origin, then pruned
    locally (local head deleted AND its remote-tracking ref pruned/stale —
    the "pruned-origin variant"), still exists on origin — the probe must
    report it present, and the read path must raise
    ``CoordinationWorktreeUnmaterialized`` (materialize/fetch recovery),
    never ``CoordinationBranchDeleted`` (flatten recovery — genuinely wrong
    here) and never a silent empty-primary substitution.

    A plain ``git push`` already updates the local remote-tracking ref by
    default, so branch-delete alone is NOT remote-only — the already-fixed
    #2614 ``refs/remotes/`` scan would still find it. Pruning the
    remote-tracking ref too is what reproduces the actual ambiguity.

    Pre-fix (RED): ``_coord_branch_exists`` returns ``False`` (local head and
    ``refs/remotes/`` both miss; no remote consultation exists yet), so the
    read path raises ``CoordinationBranchDeleted`` instead.
    """
    repo = _repo(tmp_path)
    result = _create_coord_mission(repo, "remote-probe-pruned")
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    bare = _bare_origin(tmp_path)
    _push(repo, bare, result.target_branch, coord_branch)
    _git(repo, "branch", "-D", coord_branch)
    _prune_remote_tracking_ref(repo, coord_branch)

    _assert_remote_only(repo, coord_branch)

    assert _coord_branch_exists(repo, coord_branch) is True, (
        "#4979: _coord_branch_exists must treat a remote-only coord branch as "
        "present (FR-001) — it must consult `git ls-remote` once the local "
        "head and refs/remotes/ fast paths both miss."
    )

    seam = placement_seam(repo, result.mission_slug)
    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        seam.read_dir(MissionArtifactKind.STATUS_STATE)
    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert "materializ" in excinfo.value.next_step.lower()
    assert "flatten" not in excinfo.value.next_step.lower()
    # FR-006: a remote-only branch must lead with fetch-first guidance, not
    # the local-head "self-materialize" wording.
    assert f"git fetch origin {coord_branch}" in excinfo.value.next_step


def test_single_branch_clone_remote_only_coord_branch_is_not_deleted(tmp_path: Path) -> None:
    """FR-001/FR-007 (#4979): a `git clone --single-branch -b <target>` never
    fetches the coord branch at all — the same remote-only ambiguity as the
    pruned-branch fixture above, reached via the other real-world vector the
    issue names (CI / shallow / single-branch checkouts).

    Pre-fix (RED): identical failure mode to the pruned-branch variant.
    """
    repo = _repo(tmp_path)
    result = _create_coord_mission(repo, "remote-probe-singlebranch")
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    bare = _bare_origin(tmp_path)
    _push(repo, bare, result.target_branch, coord_branch)

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", "--single-branch", "-b", result.target_branch, str(bare), str(clone)],
        check=True,
    )
    _configure_clone(clone)

    _assert_remote_only(clone, coord_branch)

    assert _coord_branch_exists(clone, coord_branch) is True, (
        "#4979: a single-branch clone must still resolve the coord branch as present via `git ls-remote` (FR-001)."
    )

    seam = placement_seam(clone, result.mission_slug)
    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        seam.read_dir(MissionArtifactKind.STATUS_STATE)
    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert "materializ" in excinfo.value.next_step.lower()
    assert "flatten" not in excinfo.value.next_step.lower()
    # FR-006: a remote-only branch must lead with fetch-first guidance, not
    # the local-head "self-materialize" wording.
    assert f"git fetch origin {coord_branch}" in excinfo.value.next_step


# ---------------------------------------------------------------------------
# Section A companion — FR-002/FR-003: genuine deletion is preserved
# ---------------------------------------------------------------------------


def test_reachable_remote_clean_miss_still_reports_absent(tmp_path: Path) -> None:
    """FR-002/FR-003 (#4979): when a configured, reachable remote genuinely
    does not carry the branch (a CLEAN-MISS — ``git ls-remote`` exits 0 with
    empty output on every remote) and no local head exists either, the probe
    must still report the branch absent — the legitimate
    flatten/``CoordinationBranchDeleted`` recovery path must survive the fix.

    Not a regression by itself (this already passes pre-fix, since the old
    code never needs a remote to answer "absent" here) — a preservation
    companion to the two RED tests above, using the same fixture family, so a
    fix that over-corrects toward "always present" is caught in the same file.
    """
    repo = _repo(tmp_path)
    result = _create_coord_mission(repo, "remote-probe-cleanmiss")
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    bare = _bare_origin(tmp_path)
    # Only the target branch is pushed — origin genuinely never carries the
    # coordination branch (a reachable remote, clean-miss).
    _push(repo, bare, result.target_branch)
    _git(repo, "branch", "-D", coord_branch)

    ls_remote = subprocess.run(
        ["git", "-C", str(repo), "ls-remote", "--heads", "origin", coord_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ls_remote.returncode == 0 and not ls_remote.stdout.strip(), "fixture precondition failed: origin must reachably clean-miss the coord branch"

    assert _coord_branch_exists(repo, coord_branch) is False, (
        "FR-002: a genuinely-absent coord branch (reachable remote, clean miss; no local head) must still report absent."
    )

    seam = placement_seam(repo, result.mission_slug)
    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        seam.read_dir(MissionArtifactKind.STATUS_STATE)
    assert excinfo.value.error_code == "COORDINATION_BRANCH_DELETED"


# ---------------------------------------------------------------------------
# Section B (T003) — NFR-001: the remote round-trip fires ONLY after the
# local-head and refs/remotes/ fast paths both miss
# ---------------------------------------------------------------------------


def test_no_remote_lookup_when_local_head_hits(tmp_path: Path) -> None:
    """NFR-001: a coord branch that is still a local head must resolve without
    ever consulting the remote primitive — the common full-clone / local-head
    path pays zero network cost."""
    repo = _repo(tmp_path)
    result = _create_coord_mission(repo, "remote-probe-localhead-fastpath")
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    with patch("specify_cli.coordination.surface_resolver.remote_branch_lookup") as mock_lookup:
        assert _coord_branch_exists(repo, coord_branch) is True
    mock_lookup.assert_not_called()


def test_no_remote_lookup_when_refs_remotes_scan_hits(tmp_path: Path) -> None:
    """NFR-001: a coord branch resolvable via an already-fetched
    ``refs/remotes/*/<coord>`` ref (the #2614 fast path) must not fire the
    remote primitive either — pins the ordering invariant the module docstring
    on :func:`_coord_branch_exists_via_remote` names."""
    repo = _repo(tmp_path)
    result = _create_coord_mission(repo, "remote-probe-refsremotes-fastpath")
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    bare = _bare_origin(tmp_path)
    _push(repo, bare, result.target_branch, coord_branch)
    _git(repo, "branch", "-D", coord_branch)
    # Deliberately do NOT prune the remote-tracking ref this time — `git push`
    # already left `refs/remotes/origin/<coord_branch>` in place, so the
    # #2614 fast path must resolve this without ever reaching the remote arm.
    assert coord_branch in _remote_tracking_branch_names(repo)

    with patch("specify_cli.coordination.surface_resolver.remote_branch_lookup") as mock_lookup:
        assert _coord_branch_exists(repo, coord_branch) is True
    mock_lookup.assert_not_called()


def test_remote_lookup_is_consulted_only_once_both_fast_paths_miss(tmp_path: Path) -> None:
    """Sanity companion: when both fast paths genuinely miss, the remote
    primitive IS consulted exactly once (proves the mock above is a real
    negative, not a patch that silently never wires up)."""
    repo = _repo(tmp_path)
    result = _create_coord_mission(repo, "remote-probe-lookup-invoked")
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    bare = _bare_origin(tmp_path)
    _push(repo, bare, result.target_branch, coord_branch)
    _git(repo, "branch", "-D", coord_branch)
    _prune_remote_tracking_ref(repo, coord_branch)

    with patch(
        "specify_cli.coordination.surface_resolver.remote_branch_lookup",
        return_value=RemoteLookup.HIT,
    ) as mock_lookup:
        assert _coord_branch_exists(repo, coord_branch) is True
    mock_lookup.assert_called_once_with(repo, coord_branch)
