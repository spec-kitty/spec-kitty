"""WP02 / FR-008: accept residual routing + M2 dirty-surface reconciliation.

``accept.py::_commit_residual_acceptance_artifacts`` used a raw ``git commit``
(``run_git(["commit", ...])``) scoped to the PRIMARY checkout only. Two bugs
followed from that:

* **Misrouting (T007)** — a coordination-topology mission's residual matrix /
  issue-matrix / status-view artifacts must land on the COORDINATION branch
  (the same surface :func:`~specify_cli.acceptance.matrix.write_acceptance_matrix`
  writes to under coord topology), but a raw ``git commit`` in the PRIMARY
  checkout can only ever commit files tracked in the PRIMARY tree — it has no
  way to reach a *different* git worktree at all.
* **M2 dirty-detection gap (T008)** — ``_spec_artifact_dirty_paths`` scanned
  only ``git_status_entries(repo_root)`` (the PRIMARY tree). Under coord
  topology the matrix write lands in the coordination worktree, a completely
  separate git checkout, so its dirt was invisible to the scan and the
  residual commit step silently no-opped, leaving the coord worktree dirty.

These tests build a REAL coordination-topology mission (a genuine
``git worktree`` materialised via the canonical
:class:`~specify_cli.coordination.workspace.CoordinationWorkspace`, not a
mock) and drive ``_spec_artifact_dirty_paths`` /
``_commit_residual_acceptance_artifacts`` directly — the same function-level
seam ``test_accept_clean_tree.py``'s
``test_residual_acceptance_commit_is_scoped_to_mission_paths`` already pins
for the PRIMARY-only case.

Identity is production-shaped: a full 26-char Crockford ULID and the
canonical on-disk ``<slug>-<mid8>`` layout (NFR-002/NFR-005), matching
``test_accept_gate_read_surface.py``'s coord fixture.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.acceptance.matrix import (
    AcceptanceMatrix,
    NegativeInvariant,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import (
    _commit_residual_acceptance_artifacts,
    _spec_artifact_dirty_paths,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

# Production-shaped identity (NFR-002/NFR-005): a full 26-char Crockford-base32
# ULID, its first-8-char mid8, and the canonical ``<slug>-<mid8>`` handle.
_MISSION_ID = "01KWZV91XFXPKTBE77QT3KRSW8"
_MID8 = _MISSION_ID[:8]  # "01KWZV91"
_SLUG = "accept-residual-partition"
_HANDLE = f"{_SLUG}-{_MID8}"
# The mission's OWN unprotected working branch (where accept "runs from").
# Deliberately distinct from the canonical coordination-branch grammar
# (``kitty/mission-<handle>``, see ``coord_reconstruct_branch``) so the two
# branches never collide when both are created in the same fixture.
_TARGET_BRANCH = f"feat/{_HANDLE}"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _porcelain(repo_root: Path) -> str:
    return _git(repo_root, "status", "--porcelain").stdout


def _head_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


def _write_meta(feature_dir: Path, *, coordination_branch: str | None) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        "mission_slug": _HANDLE,
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
    }
    if coordination_branch:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _initial_matrix() -> AcceptanceMatrix:
    return AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
            )
        ],
    )


def _build_coord_mission(repo_root: Path) -> tuple[Path, Path]:
    """Build a real coord-topology mission with a materialised coord worktree.

    Returns ``(primary_feature_dir, coord_feature_dir)``. The coord worktree is
    a genuine ``git worktree`` (via the canonical
    :class:`CoordinationWorkspace`), checked out on its own coordination
    branch — mirroring production, not a stub.
    """
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")

    primary_feature_dir = repo_root / "kitty-specs" / _HANDLE
    coord_branch = CoordinationWorkspace.branch_name(_HANDLE, _MID8)
    _write_meta(primary_feature_dir, coordination_branch=coord_branch)

    # A minimal committed baseline so the mission's own (unprotected) branch
    # and the coordination branch both have somewhere to fork from.
    # ``.worktrees/`` is gitignored (mirrors a real spec-kitty repo) so the
    # coord worktree materialised below never shows up as primary-tree dirt
    # itself (a nested-repo pointer would otherwise pollute the porcelain
    # assertions this suite makes about the PRIMARY surface staying clean).
    # ``.kittify/sync-state.json`` is a real spec-kitty gitignore entry (a
    # sync-event side effect of ``safe_commit``'s post-commit hook); ignoring
    # it here mirrors a real project so it never pollutes the primary-tree
    # cleanliness assertions this suite makes.
    (repo_root / ".gitignore").write_text(".worktrees/\n.kittify/sync-state.json\n")
    (repo_root / ".gitkeep").write_text("")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "init")
    _git(repo_root, "checkout", "-q", "-b", _TARGET_BRANCH)
    _git(repo_root, "branch", coord_branch)

    coord_root = CoordinationWorkspace.resolve(repo_root, _HANDLE, _MID8)
    coord_feature_dir = coord_root / "kitty-specs" / _HANDLE
    _write_meta(coord_feature_dir, coordination_branch=coord_branch)

    # Commit an initial (pending) matrix on the coord branch so the later
    # rewrite registers as tracked-modified dirt, not an untracked file (the
    # dirty scan deliberately excludes ``??`` — see
    # ``_spec_artifact_dirty_paths``'s docstring).
    write_acceptance_matrix(coord_feature_dir, _initial_matrix())
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "-m", "coord baseline")

    return primary_feature_dir, coord_feature_dir


def test_dirty_scan_detects_coord_worktree_residue(tmp_path: Path) -> None:
    """M2 (T006/T008): coord-worktree dirt is invisible to a primary-only scan.

    ``write_acceptance_matrix`` rewrites the matrix in the COORD worktree
    (mirroring what accept's readiness checks do); the PRIMARY checkout stays
    perfectly clean throughout. Pre-fix, ``_spec_artifact_dirty_paths`` only
    consulted ``git_status_entries(repo_root)`` (primary) and returned ``[]`` —
    the M2 gap this test proves RED against.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)

    # Rewrite the matrix on COORD only; primary never touched.
    resolved = AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
    )
    write_acceptance_matrix(coord_feature_dir, resolved)

    assert _porcelain(repo_root) == "", "primary must stay clean for this scenario"

    dirty = _spec_artifact_dirty_paths(repo_root, _HANDLE)

    assert f"kitty-specs/{_HANDLE}/acceptance-matrix.json" in dirty, (
        "coord-worktree dirt (where write_acceptance_matrix actually writes "
        "under coord topology) was not detected — M2 gap"
    )


def test_residual_commit_routes_matrix_to_coord_branch(tmp_path: Path) -> None:
    """T007: the residual commit lands on the COORD branch via commit_for_mission.

    Not a raw primary-checkout ``git commit`` — the primary branch gains NO new
    commit from this call, and the coord branch does.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    primary_head_before = _head_sha(repo_root)
    coord_head_before = _head_sha(coord_root)

    resolved = AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
    )
    write_acceptance_matrix(coord_feature_dir, resolved)

    created = _commit_residual_acceptance_artifacts(repo_root, _HANDLE)

    assert created is True

    # Primary gained NO commit — the router never touches the primary branch
    # for a coord-partition kind.
    assert _head_sha(repo_root) == primary_head_before
    # Coord DID gain a commit, and its tree is now clean.
    assert _head_sha(coord_root) != coord_head_before
    assert _porcelain(coord_root) == ""

    # Round-trip (T009): the committed matrix reads back with the resolved
    # invariant, not the stale pending baseline.
    read_back = read_acceptance_matrix(coord_feature_dir)
    assert read_back is not None
    assert read_back.negative_invariants[0].result == "confirmed_absent"

    show = subprocess.run(
        ["git", "-C", str(coord_root), "show", f"HEAD:kitty-specs/{_HANDLE}/acceptance-matrix.json"],
        capture_output=True,
        text=True,
    )
    assert show.returncode == 0, "acceptance-matrix.json is not committed at coord HEAD"
    assert json.loads(show.stdout)["negative_invariants"][0]["result"] == "confirmed_absent"


def test_residual_commit_keeps_primary_kind_residuals_working(tmp_path: Path) -> None:
    """DoD: PRIMARY-kind residuals (e.g. a dirty spec.md) must be unregressed.

    A flattened (no coordination_branch) mission's own primary artifact goes
    dirty; the residual commit must still land it directly on the current
    (unprotected) branch — the historical raw-git behaviour
    ``test_accept_clean_tree.py`` already pins, preserved by this WP.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir, coordination_branch=None)
    (feature_dir / "spec.md").write_text("# spec\nv1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "baseline")

    (feature_dir / "spec.md").write_text("# spec\nv2\n", encoding="utf-8")

    created = _commit_residual_acceptance_artifacts(repo_root, _SLUG)

    assert created is True
    assert _porcelain(repo_root) == ""
    show = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_SLUG}/spec.md"],
        capture_output=True,
        text=True,
    )
    assert show.returncode == 0
    assert "v2" in show.stdout


def test_residual_commit_handles_mixed_primary_and_coord_dirt(tmp_path: Path) -> None:
    """A batch mixing PRIMARY dirt (spec.md) and COORD dirt (matrix) commits both.

    Proves the seam is not hand-classified: primary residue lands directly on
    the current branch, coord residue lands on the coord branch, in the SAME
    ``_commit_residual_acceptance_artifacts`` call.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    (primary_feature_dir / "spec.md").write_text("# spec\nv1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add spec baseline")
    (primary_feature_dir / "spec.md").write_text("# spec\nv2\n", encoding="utf-8")

    resolved = AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
    )
    write_acceptance_matrix(coord_feature_dir, resolved)

    created = _commit_residual_acceptance_artifacts(repo_root, _HANDLE)

    assert created is True
    assert _porcelain(repo_root) == ""
    assert _porcelain(coord_root) == ""

    primary_show = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_HANDLE}/spec.md"],
        capture_output=True,
        text=True,
    )
    assert primary_show.returncode == 0
    assert "v2" in primary_show.stdout

    coord_show = subprocess.run(
        ["git", "-C", str(coord_root), "show", f"HEAD:kitty-specs/{_HANDLE}/acceptance-matrix.json"],
        capture_output=True,
        text=True,
    )
    assert coord_show.returncode == 0
    assert json.loads(coord_show.stdout)["negative_invariants"][0]["result"] == "confirmed_absent"
