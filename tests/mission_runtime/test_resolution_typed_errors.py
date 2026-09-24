"""WP05 typed-error pass-through: MissionSelectorAmbiguous must translate to
ActionContextError at the mission_runtime boundary.

When ``resolve_action_context`` / ``resolve_placement_only`` is called with an
ambiguous mission handle (one that matches more than one mission in the repo),
the underlying ``specify_cli`` exception ``MissionSelectorAmbiguous`` must be
caught at the ``resolution.py`` boundary and re-raised as the single
consumer-facing type ``ActionContextError`` with the specific stable code
``MISSION_AMBIGUOUS_SELECTOR`` — never escaped as a raw ``specify_cli``
exception (FR-005 / #2010 bug #15).

Red-state receipt (pre-fix, unmodified resolution.py):
    The try-block at resolution.py:183 only catches StatusReadPathNotFound.
    When the handle is ambiguous, MissionSelectorAmbiguous propagates up
    uncaught through resolve_action_context, escaping the mission_runtime
    boundary as a raw specify_cli exception. This test asserts that
    ActionContextError is raised with code MISSION_AMBIGUOUS_SELECTOR —
    which FAILS on unmodified code because MissionSelectorAmbiguous escapes
    instead.

Green-state (post-fix):
    The new ``except MissionSelectorAmbiguous`` arm in ``_resolve_mission_slug``
    translates the raw exception to ActionContextError(MISSION_AMBIGUOUS_SELECTOR),
    making the test pass.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    ActionContextError,
    MissionArtifactKind,
    MissionTopology,
    resolve_action_context,
    resolve_placement_only,
)
from specify_cli.core.mission_creation import MissionCreationResult

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Two missions that share the same human slug stripped of their numeric prefix.
# When the operator passes the bare human slug, the resolver matches both and
# raises MissionSelectorAmbiguous (C-CTX-4).
_MID8_A = "AABB1100"
_MID8_B = "CCDD2200"
_MISSION_ID_A = f"{_MID8_A}000000000000000000"  # 26-char ULID-shaped
_MISSION_ID_B = f"{_MID8_B}000000000000000000"  # 26-char ULID-shaped
_HUMAN_SLUG = "ambiguous-name"
_DIRNAME_A = f"001-{_HUMAN_SLUG}"
_DIRNAME_B = f"002-{_HUMAN_SLUG}"
# The bare human slug is the ambiguous handle: it matches both _DIRNAME_A and
# _DIRNAME_B when stripped of their numeric prefix.
_AMBIGUOUS_HANDLE = _HUMAN_SLUG


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )
    return r


def _build_mission(
    repo: Path,
    *,
    dirname: str,
    mission_id: str,
    mid8: str,
) -> Path:
    """Build a minimal mission directory with meta.json and commit it."""
    feature_dir = repo / "kitty-specs" / dirname
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_slug": dirname,
        "mission_type": "software-dev",
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    return feature_dir


@pytest.fixture
def ambiguous_repo(repo: Path) -> Path:
    """Repo with two missions sharing the same human slug (ambiguous handle)."""
    _build_mission(
        repo,
        dirname=_DIRNAME_A,
        mission_id=_MISSION_ID_A,
        mid8=_MID8_A,
    )
    _build_mission(
        repo,
        dirname=_DIRNAME_B,
        mission_id=_MISSION_ID_B,
        mid8=_MID8_B,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "two-ambiguous-missions")
    return repo


def test_ambiguous_handle_raises_action_context_error_with_specific_code(
    ambiguous_repo: Path,
) -> None:
    """Ambiguous handle → ActionContextError(MISSION_AMBIGUOUS_SELECTOR) at the boundary.

    Before the WP05 fix: MissionSelectorAmbiguous escapes resolve_action_context
    as a raw specify_cli exception (no ActionContextError wrapping, no stable code).
    After the fix: ActionContextError is raised with code MISSION_AMBIGUOUS_SELECTOR.
    """
    with pytest.raises(ActionContextError) as excinfo:
        resolve_action_context(
            ambiguous_repo,
            action="status",
            feature=_AMBIGUOUS_HANDLE,
        )

    assert excinfo.value.code == "MISSION_AMBIGUOUS_SELECTOR", (
        f"Expected code 'MISSION_AMBIGUOUS_SELECTOR', got {excinfo.value.code!r}. "
        "The MissionSelectorAmbiguous exception escaped the mission_runtime boundary "
        "as a raw specify_cli exception instead of being translated."
    )
    assert _AMBIGUOUS_HANDLE in str(excinfo.value), (
        "The error message must include the ambiguous handle so operators can diagnose."
    )


def test_ambiguous_handle_resolve_placement_only_raises_action_context_error(
    ambiguous_repo: Path,
) -> None:
    """resolve_placement_only must also translate MissionSelectorAmbiguous.

    The candidate_feature_dir_for_mission call in resolve_placement_only also
    routes through the read-path resolver, which can raise MissionSelectorAmbiguous.
    The translation must apply there too — not only in resolve_action_context.
    """
    with pytest.raises(ActionContextError) as excinfo:
        resolve_placement_only(
            ambiguous_repo,
            _AMBIGUOUS_HANDLE,
            kind=MissionArtifactKind.STATUS_STATE,
        )

    assert excinfo.value.code == "MISSION_AMBIGUOUS_SELECTOR", (
        f"Expected code 'MISSION_AMBIGUOUS_SELECTOR', got {excinfo.value.code!r}. "
        "MissionSelectorAmbiguous escaped resolve_placement_only untranslated."
    )


# ===========================================================================
# coord-read-fail-closed-01M38VVH WP01 T004 — regression pins (#4959, AC-S2)
# ===========================================================================
#
# T003 changed ONLY the ``CoordState.UNMATERIALIZED`` leg of
# ``_classify_artifact_surface``. These pins confirm the sibling states are
# byte-for-byte unchanged: ``DELETED`` still raises the pre-existing
# ``CoordinationBranchDeleted``; a PRIMARY-partition kind on the very same
# UNMATERIALIZED mission never raises (PRIMARY-partition kinds short-circuit
# before any coord probe); and the out-of-scope ``EMPTY`` / ``NONE`` states
# keep returning the PRIMARY surface.


def _create_coord_mission(repo: Path, slug: str) -> MissionCreationResult:
    """Build a real COORD-topology mission (branch minted, worktree absent).

    Thin wrapper so this module does not need to import the golden-path
    fixture module's git/kittify bootstrap twice — it reuses the exact same
    ``_create_mission`` / ``_init_git_repo`` primitives ``test_coord_read_seam
    .py`` already reuses from ``tests/integration/
    test_placement_partition_golden_path.py`` (mirroring, not duplicating).
    """
    from tests.integration.test_placement_partition_golden_path import (
        _create_mission,
        _init_git_repo,
    )

    _init_git_repo(repo, branch="main")
    result: MissionCreationResult = _create_mission(repo, slug, MissionTopology.COORD)
    return result


def test_deleted_coord_branch_still_raises_coordination_branch_deleted(
    tmp_path: Path,
) -> None:
    """Regression pin: ``DELETED`` is unaffected by the T003 UNMATERIALIZED
    change — a coord-partition read still raises ``CoordinationBranchDeleted``
    when the declared branch has been removed from git entirely."""
    from mission_runtime import placement_seam
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    repo = tmp_path / "repo"
    repo.mkdir()
    result = _create_coord_mission(repo, "coord-deleted-pin-demo")
    coordination_branch = result.coordination_branch
    assert coordination_branch, "fixture must mint a coordination branch"
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-D", coordination_branch],
        check=True,
        capture_output=True,
    )

    seam = placement_seam(repo, result.mission_slug)

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        seam.read_dir(MissionArtifactKind.STATUS_STATE)

    assert excinfo.value.error_code == "COORDINATION_BRANCH_DELETED"


def test_primary_kind_on_unmaterialized_coord_mission_does_not_raise(
    tmp_path: Path,
) -> None:
    """Regression pin: on the SAME UNMATERIALIZED mission the T003 fix now
    makes a coord-partition kind raise, a PRIMARY-partition kind
    (``PRIMARY_METADATA``) never raises — it short-circuits to PRIMARY before
    any coord probe (AH-1/AH-3), so the seam change is invisible to it."""
    from mission_runtime import placement_seam

    repo = tmp_path / "repo"
    repo.mkdir()
    result = _create_coord_mission(repo, "coord-unmat-primary-pin-demo")
    # No coord-worktree materialization: CoordState.UNMATERIALIZED.

    seam = placement_seam(repo, result.mission_slug)

    resolved = seam.read_dir(MissionArtifactKind.PRIMARY_METADATA)
    assert resolved.exists()
    assert resolved.name == result.mission_slug


def test_empty_and_none_coord_states_still_resolve_primary(tmp_path: Path) -> None:
    """Regression pin: ``EMPTY`` (coord root materialized, mission dir absent)
    and ``NONE`` (no coord topology) are OUT of this mission's scope and keep
    resolving the PRIMARY surface, never raising."""
    from mission_runtime import placement_seam
    from specify_cli.coordination.workspace import CoordinationWorkspace

    # NONE: a coord-less (SINGLE_BRANCH) mission never probes coord state.
    repo_none = tmp_path / "repo-none"
    repo_none.mkdir()
    from tests.integration.test_placement_partition_golden_path import (
        _create_mission,
        _init_git_repo,
    )

    _init_git_repo(repo_none, branch="main")
    result_none = _create_mission(repo_none, "coord-none-pin-demo", MissionTopology.SINGLE_BRANCH)
    seam_none = placement_seam(repo_none, result_none.mission_slug)
    resolved_none = seam_none.read_dir(MissionArtifactKind.STATUS_STATE)
    assert resolved_none.exists()

    # EMPTY: coord worktree root materialized, but its mission dir is absent.
    repo_empty = tmp_path / "repo-empty"
    repo_empty.mkdir()
    _init_git_repo(repo_empty, branch="main")
    result_empty = _create_coord_mission(repo_empty, "coord-empty-pin-demo")
    meta = json.loads((result_empty.feature_dir / "meta.json").read_text(encoding="utf-8"))
    mid8 = str(meta["mission_id"])[:8]
    # Materialize the coord worktree ROOT without ever writing a mission dir
    # into it — the EMPTY state (distinct from UNMATERIALIZED, where the root
    # itself does not exist yet).
    CoordinationWorkspace.resolve(repo_empty, result_empty.mission_slug, mid8)

    seam_empty = placement_seam(repo_empty, result_empty.mission_slug)
    resolved_empty = seam_empty.read_dir(MissionArtifactKind.STATUS_STATE)
    assert resolved_empty.exists()
    assert resolved_empty.name == result_empty.mission_slug
