"""#4403 — the ``_resolve_status_surface_dir`` DELETED arm raises via the factory.

The ci-aggregate diff-cover gate (>=90% changed critical-path lines) found the
one routed ``CoordinationBranchDeleted.for_mission`` site with no covering
test: the effective-root arm of
:func:`mission_runtime.resolution._resolve_status_surface_dir`
(``src/mission_runtime/resolution.py``), reached through the
:func:`mission_runtime.mission_context_for` SSOT facade when an owned-checkout
caller threads ``effective_root``. The other four routed sites are pinned by
their owning seams' tests (``tests/specify_cli/coordination/``,
``tests/specify_cli/missions/``); this file pins the fifth end-to-end on the
real DELETED shape — a mission whose stored meta declares a coordination
branch that no longer exists in git (the #3012 fixture shape: the branch is
absent locally and from every remote, and no coord worktree is registered).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char ULID, mid8 = first 8 chars
# (Mission Identity Model 083+), matching the on-disk composed dir name.
_MISSION_ID = "01KW7SURFACDELETED4403001"[:26]
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = "status-surface-deleted-arm"
_SLUG_WITH_MID8 = f"{_MISSION_SLUG}-{_MID8}"
_COORD_BRANCH = f"kitty/mission-{_SLUG_WITH_MID8}-coord"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _build_coord_deleted_mission(repo_root: Path) -> Path:
    """Real git repo whose mission declares a coordination branch that does not exist.

    Same narrow shape as ``tests/merge/test_coord_deleted_degrade_paths.py``:
    the branch must be absent locally AND from every remote
    (``_coord_branch_exists`` consults ``refs/remotes/`` too), and no coord
    worktree may be registered — normal post-merge state yields UNMATERIALIZED
    (→ PRIMARY) instead, which is why this fixture never creates the branch.
    """
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "status-surface-4403@example.test")
    _git(repo_root, "config", "user.name", "Status Surface Deleted Arm")

    feature_dir = repo_root / "kitty-specs" / _SLUG_WITH_MID8
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "slug": _SLUG_WITH_MID8,
                "friendly_name": _MISSION_SLUG,
                "mission_type": "software-dev",
                "target_branch": "main",
                "coordination_branch": _COORD_BRANCH,
                "topology": "coord",
            }
        ),
        encoding="utf-8",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "init mission declaring a nonexistent coord branch")
    return feature_dir


def test_effective_root_status_surface_deleted_raises_via_factory(tmp_path: Path) -> None:
    """The owned-checkout status-surface read refuses a DELETED coord branch.

    ``mission_context_for(..., effective_root=...)`` drives
    ``_resolve_status_surface_dir``'s effective-root arm: meta declares a
    ``coord`` topology and a ``coordination_branch`` that no longer exists, the
    single probe answers ``CoordState.DELETED``, and the arm must raise through
    the ONE ``CoordinationBranchDeleted.for_mission`` factory (#4403) — never a
    hand-rolled payload — with the payload fields the factory owns: the
    ``coord_feature_dir``-composed candidate, the seam-resolved primary dir of
    the owned checkout, and the remediation next_step.
    """
    from mission_runtime import mission_context_for
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir = _build_coord_deleted_mission(repo)

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        mission_context_for(repo, _SLUG_WITH_MID8, effective_root=repo)

    err = excinfo.value
    assert err.error_code == "COORDINATION_BRANCH_DELETED"
    assert err.repo_root == repo
    assert err.mission_slug == _SLUG_WITH_MID8
    assert err.mid8 == _MID8
    assert err.coordination_branch == _COORD_BRANCH
    # The factory composes the candidate through the single grammar — the
    # double-suffix guard keeps the already-composed slug unchanged.
    assert err.coord_candidate == coord_feature_dir(repo, _SLUG_WITH_MID8, _MID8)
    # This site's primary anchor is the seam-resolved owned-checkout dir.
    assert err.primary_candidate == feature_dir
    assert "doctor coordination --fix" in err.next_step
