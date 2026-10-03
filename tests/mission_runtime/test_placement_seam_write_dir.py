"""Red-first + green tests for ``PlacementSeam.write_dir`` (mission
coord-artifact-single-home-01M3V4BE, WP04, T018-T020).

See ``contracts/write-location-accessor.md`` and research D1/D22/D23.
Fixtures come from the shared WP02 harness (``tests/_factories/coord_mission.py``)
and the owned-fact minting helper (``tests/_owned_fixtures.py``), matching
WP03's own ``tests/coordination/test_coord_seed.py``.

Red at the base (before this WP's implementation commit): every test in this
file fails with ``AttributeError: 'PlacementSeam' object has no attribute
'write_dir'`` except ``test_read_dir_keeps_root_fallback_on_empty`` (the C-002
read-side control, which is green on both the base and the fix).
"""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Literal

import pytest

from mission_runtime import (
    ActionContextError,
    CommitTarget,
    Establishment,
    MissionArtifactKind,
    MissionTopology,
    OwnedCheckout,
    OwnedRefusalCode,
    TopologySurface,
    is_primary_artifact_kind,
    placement_seam,
    resolve_placement_only,
)
from specify_cli.coordination.surface_resolver import coord_branch_has_committed_artifact
from specify_cli.missions._read_path_resolver import StatusReadPathNotFound
from tests._factories.coord_mission import CoordMission, make_coord_mission, make_prefix_coord_mission
from tests._owned_fixtures import mint_test_fact
from tests.mission_runtime.test_consolidated_resolution import _build_e2_mission_coord_fully_retired

pytestmark = [pytest.mark.fast]

_COORD_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)
_E2_ELIGIBLE_COORD_KINDS = (
    MissionArtifactKind.ISSUE_MATRIX,
    MissionArtifactKind.TRACER_FILE,
    MissionArtifactKind.ACCEPTANCE_MATRIX,
    MissionArtifactKind.REVIEW_CYCLE,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _current_branch(path: Path) -> str:
    return _git(path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _for_each_ref(repo_root: Path) -> str:
    return _git(repo_root, "for-each-ref").stdout


def _worktree_list(repo_root: Path) -> str:
    return _git(repo_root, "worktree", "list", "--porcelain").stdout


def _init_flat_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
    (repo_root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "init")


def _build_flat_mission(repo_root: Path, *, mission_slug: str, mid8: str, target_branch: str, topology: MissionTopology) -> Path:
    """A minimal non-coordination (``lanes`` / ``single_branch``) mission.

    ``declared_read_surface`` short-circuits to PRIMARY for these topologies
    without ever probing coordination, so no coordination branch/worktree is
    needed here (mirrors ``tests/mission_runtime/test_placement_seam.py``'s
    ``_build_mission`` helper).
    """
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": f"{mid8}0000000000000000",
        "mission_slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "friendly_name": "write_dir flat-topology fixture",
        "topology": topology.value,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture")
    return feature_dir


def _mint_owned_coord_fact(coord: CoordMission, owned_root: Path) -> OwnedCheckout:
    owned_mission_dir = owned_root / "kitty-specs" / coord.mission_dir_name
    owned_mission_dir.mkdir(parents=True)
    return mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_mission_dir,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=MissionTopology.COORD,
    )


# ---------------------------------------------------------------------------
# T018 -- write_dir basic behaviour
# ---------------------------------------------------------------------------


def test_write_dir_coord_kind_on_prefix_empty_mission_is_coordination_surface(tmp_path: Path) -> None:
    """A pre-fix EMPTY coordination Mission's ``write_dir(STATUS_STATE)``
    seeds and resolves the COORDINATION surface -- the write side's EMPTY
    handling diverges from today's read-side PRIMARY fallback (the C-002
    control test below pins that the read side is unaffected)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    seam = placement_seam(coord.repo_root, coord.mission_dir_name)

    location = seam.write_dir(MissionArtifactKind.STATUS_STATE)

    assert location.surface == TopologySurface.COORD
    assert location.path == coord.coord_mission_dir
    assert location.path.exists()
    assert location.establishment == Establishment.SEEDED


def test_read_dir_keeps_root_fallback_on_empty(tmp_path: Path) -> None:
    """C-002 control: ``read_dir(STATUS_STATE)`` on the SAME EMPTY fixture
    keeps degrading to the repository-root checkout, unaffected by
    ``write_dir``'s establishment behaviour. Green at the base AND the fix."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    seam = placement_seam(coord.repo_root, coord.mission_dir_name)

    assert seam.read_dir(MissionArtifactKind.STATUS_STATE) == coord.root_mission_dir


def test_write_dir_primary_kind_is_side_effect_free(tmp_path: Path) -> None:
    """A PRIMARY-partition kind's ``write_dir`` equals ``read_dir`` exactly,
    with no coordination worktree ever materialized (C-008)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    seam = placement_seam(coord.repo_root, coord.mission_dir_name)

    location = seam.write_dir(MissionArtifactKind.SPEC)

    assert location.path == seam.read_dir(MissionArtifactKind.SPEC)
    assert location.surface == TopologySurface.PRIMARY
    assert location.establishment == Establishment.NONE
    assert location.coord_state_before is None
    assert not coord.coord_worktree_path.exists()


def test_write_dir_retrospective_equals_read_dir(tmp_path: Path) -> None:
    """RETROSPECTIVE stays on its own PRIMARY-partition home (H-1): confirm
    ``write_dir`` delegates to the SAME single authority ``read_dir`` does,
    never a second, independently-computed RETROSPECTIVE home."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    seam = placement_seam(coord.repo_root, coord.mission_dir_name)

    location = seam.write_dir(MissionArtifactKind.RETROSPECTIVE)

    assert location.path == seam.read_dir(MissionArtifactKind.RETROSPECTIVE)
    assert location.surface == TopologySurface.PRIMARY
    assert location.establishment == Establishment.NONE


@pytest.mark.parametrize("topology", (MissionTopology.LANES, MissionTopology.SINGLE_BRANCH))
def test_write_dir_non_coordination_topology_is_byte_identical_to_read_dir(tmp_path: Path, topology: MissionTopology) -> None:
    """C-008: every kind, on a non-coordination topology, resolves PRIMARY
    with no side effects -- byte-identical to ``read_dir`` for every single
    :class:`MissionArtifactKind` member."""
    repo = tmp_path / "repo"
    _init_flat_repo(repo)
    mission_slug = f"flat-mission-{topology.value}"
    target_branch = "design/flat-mission"
    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = _build_flat_mission(repo, mission_slug=mission_slug, mid8="01KYT3CC", target_branch=target_branch, topology=topology)
    seam = placement_seam(repo, mission_slug)

    for kind in MissionArtifactKind:
        location = seam.write_dir(kind)
        assert location.surface == TopologySurface.PRIMARY, kind
        assert location.path == seam.read_dir(kind) == feature_dir, kind
        assert location.establishment == Establishment.NONE, kind
        assert location.coord_state_before is None, kind
        assert seam.write_target(kind) == CommitTarget(ref=target_branch), kind


# ---------------------------------------------------------------------------
# D23 / binding correction round 3-4 (I10) -- PUBLISHED (E2) kinds resolve
# BEFORE any coordination-state probe, so a torn-down coordination worktree
# can never be reached or raised against.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _E2_ELIGIBLE_COORD_KINDS)
def test_write_dir_e2_eligible_kind_bypasses_deleted_coordination_branch(tmp_path: Path, kind: MissionArtifactKind) -> None:
    repo = tmp_path / "repo"
    _init_flat_repo(repo)
    mission_slug, feature_dir, _target_branch, _coordination_branch = _build_e2_mission_coord_fully_retired(repo, mid8="01KYT4AA", mission_number=401)
    seam = placement_seam(repo, mission_slug)

    location = seam.write_dir(kind)

    assert location.surface == TopologySurface.PRIMARY
    assert location.path == feature_dir
    assert location.establishment == Establishment.NONE
    assert location.coord_state_before is None


def test_write_dir_status_state_bypasses_deleted_coordination_branch(tmp_path: Path) -> None:
    """Operator ruling `plan.design.published-status-state-write`
    (coord-artifact-single-home-01M3V4BE WP14 cycle 2, B1) SUPERSEDES the
    prior binding-correction-round-3 text this test used to pin ("STATUS_STATE
    follows whatever write_target resolves today", i.e. a raised
    ``CoordinationBranchDeleted``): ``STATUS_STATE``'s WRITE side now joins
    the PUBLISHED/E2 short-circuit (``_is_published_write_short_circuit_kind``)
    so a PUBLISHED mission's event-log append — the retrospect /
    agent-retrospect auto-commit, the ONLY writer that can run
    post-consolidation — can never raise against a coordination branch
    consolidation has already torn down (the #5513/#5501 crash this ruling
    closes). ``DECISION_LOG`` keeps the OLD (still-raises) behaviour; see
    ``tests/mission_runtime/test_consolidated_resolution.py::
    test_e2_decision_log_still_probes_coordination_and_is_unaffected``, which
    pins that the short-circuit stays kind-scoped, not blanket. Shape-identical
    to the E2-eligible-kind test above."""
    repo = tmp_path / "repo"
    _init_flat_repo(repo)
    mission_slug, feature_dir, _target_branch, _coordination_branch = _build_e2_mission_coord_fully_retired(repo, mid8="01KYT4BB", mission_number=402)
    seam = placement_seam(repo, mission_slug)

    location = seam.write_dir(MissionArtifactKind.STATUS_STATE)

    assert location.surface == TopologySurface.PRIMARY
    assert location.path == feature_dir
    assert location.establishment == Establishment.NONE
    assert location.coord_state_before is None
    assert seam.write_target(MissionArtifactKind.STATUS_STATE) == CommitTarget(ref="main")


def test_write_dir_published_owned_status_stays_in_the_owned_checkout(tmp_path: Path) -> None:
    """A published coordination mission's status write from an owned checkout
    lands in that checkout, not the repository-root mission directory."""
    repo = tmp_path / "repo"
    _init_flat_repo(repo)
    mission_slug, feature_dir, target_branch, _coordination_branch = _build_e2_mission_coord_fully_retired(repo, mid8="01KYT4CC", mission_number=403)
    owned_root = tmp_path / "owned-checkout"
    owned_mission_dir = owned_root / "kitty-specs" / mission_slug
    owned_mission_dir.mkdir(parents=True)
    owned = mint_test_fact(
        repository_root=repo,
        owned_root=owned_root,
        mission_dir=owned_mission_dir,
        mission_slug=mission_slug,
        write_branch=target_branch,
        topology=MissionTopology.COORD,
    )

    location = placement_seam(repo, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE)

    assert location.surface is TopologySurface.PRIMARY
    assert location.path == owned_mission_dir
    assert location.surface_root == owned_root
    assert location.path != feature_dir
    assert location.establishment == Establishment.NONE


# ---------------------------------------------------------------------------
# T019 -- the owned coordination arm. Owned+coordination is not yet
# reachable through a real CLI flow today (LIFECYCLE_OWNED_TOPOLOGIES ==
# {SINGLE_BRANCH}, WP05 scout note) -- these are forward guards pinning that
# the SEAM itself threads ``owned`` through to ``establish_coord_write_location``
# correctly, for whenever that restriction lifts.
# ---------------------------------------------------------------------------


def test_write_dir_owned_coordination_materialized_lands_in_owned_coordination_workspace(tmp_path: Path) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)
    owned = _mint_owned_coord_fact(coord, tmp_path / "owned-checkout")

    location = placement_seam(coord.repo_root, coord.mission_dir_name, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE)

    assert location.surface == TopologySurface.COORD
    assert location.path == coord.coord_mission_dir
    assert location.establishment == Establishment.NONE


def test_write_dir_owned_coordination_workspace_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirrors WP03's own ``test_owned_arm_translates_workspace_failure``
    (``tests/coordination/test_coord_seed.py``), through the seam instead of
    calling ``establish_coord_write_location`` directly -- T019's point is
    that the SEAM passes ``owned`` through unmolested."""
    from specify_cli.coordination import coord_seed as cs

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    owned = _mint_owned_coord_fact(coord, tmp_path / "owned-checkout")

    def _boom(owned_arg: object, mission_slug: str, mid8: str) -> None:
        raise RuntimeError("workspace unavailable")

    monkeypatch.setattr(cs, "_establish_owned_coord_workspace", _boom)

    with pytest.raises(ActionContextError) as excinfo:
        placement_seam(coord.repo_root, coord.mission_dir_name, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value


# ---------------------------------------------------------------------------
# T020 -- property tests: agreement (write_dir <-> write_target) and purity
# (resolve_placement_only / write_target / read_dir never materialize, seed
# or move a ref -- write_dir is the ONE sanctioned side-effecting accessor).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_write_dir_agrees_with_write_target_on_materialized(tmp_path: Path, topology: MissionTopology) -> None:
    """``write_dir(kind).surface`` agrees with ``write_target(kind).ref`` by
    construction, for EVERY :class:`MissionArtifactKind`: a
    ``surface="coordination"`` result's checked-out branch IS
    ``write_target(kind).ref``."""
    coord = make_coord_mission(tmp_path, topology, materialized=True)
    seam = placement_seam(coord.repo_root, coord.mission_dir_name)

    for kind in MissionArtifactKind:
        location = seam.write_dir(kind)
        target = seam.write_target(kind)
        if is_primary_artifact_kind(kind):
            assert location.surface == TopologySurface.PRIMARY, kind
            assert location.path == seam.read_dir(kind), kind
            assert target == CommitTarget(ref=coord.target_branch), kind
        else:
            assert location.surface == TopologySurface.COORD, kind
            assert target == CommitTarget(ref=coord.coordination_branch), kind
            assert location.path.exists(), kind
            assert _current_branch(location.surface_root) == target.ref, kind


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
@pytest.mark.parametrize("worktree", ("absent", "empty"))
def test_read_side_seams_never_materialize_seed_or_move_a_ref(tmp_path: Path, topology: MissionTopology, worktree: Literal["absent", "empty"]) -> None:
    """Purity control (contract postconditions): on an UNMATERIALIZED / EMPTY
    fixture, ``resolve_placement_only`` / ``write_target`` / ``read_dir``
    make ZERO git writes for ANY :class:`MissionArtifactKind` -- only
    ``write_dir`` may establish. Remote-less fixtures throughout (the DELETED
    arm's network probe is out of scope here, per the brownfield scout's
    purity-probe note)."""
    coord = make_prefix_coord_mission(tmp_path, topology, worktree=worktree)
    seam = placement_seam(coord.repo_root, coord.mission_dir_name)
    refs_before = _for_each_ref(coord.repo_root)
    worktrees_before = _worktree_list(coord.repo_root)
    mission_dir_existed_before = coord.coord_mission_dir.exists()

    for kind in MissionArtifactKind:
        for probe in (
            lambda k=kind: resolve_placement_only(coord.repo_root, coord.mission_dir_name, kind=k),
            lambda k=kind: seam.write_target(k),
            lambda k=kind: seam.read_dir(k),
        ):
            # Sanctioned raises (e.g. CoordinationWorktreeUnmaterialized for
            # a coord-partition kind on the "absent" fixture) are fine here
            # -- purity means NO MUTATION, not NO RAISE.
            with contextlib.suppress(ActionContextError, StatusReadPathNotFound):
                probe()

    assert _for_each_ref(coord.repo_root) == refs_before
    assert _worktree_list(coord.repo_root) == worktrees_before
    assert coord.coord_mission_dir.exists() == mission_dir_existed_before


# ---------------------------------------------------------------------------
# T020 -- checkout_root re-anchor (binding correction round 3): a PRIMARY
# result's checkout_root is the MAIN repo root (or owned.owned_root), never
# ``self.repo_root`` verbatim -- pinned by calling from a lane worktree,
# where a naive "self.repo_root verbatim" implementation would disagree with
# ``path``.
# ---------------------------------------------------------------------------


def test_write_dir_checkout_root_reanchors_from_a_lane_worktree(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    lane_worktree = tmp_path / "a-lane-worktree"
    _git(coord.repo_root, "worktree", "add", "-b", "a-lane-branch", str(lane_worktree), "HEAD")

    seam = placement_seam(lane_worktree, coord.mission_dir_name)
    location = seam.write_dir(MissionArtifactKind.SPEC)

    assert location.surface_root == coord.repo_root
    assert location.surface_root != lane_worktree
    assert location.path == coord.root_mission_dir


def test_write_dir_coord_kind_from_a_lane_worktree_uses_the_main_repo(tmp_path: Path) -> None:
    """A COORD write started inside a lane worktree lands on the main
    repository's coordination worktree.

    The PRIMARY arm already re-anchors (the test above). The COORD arm used
    to compose ``.worktrees/<slug>-coord`` under the lane checkout, then
    crash when that stray worktree met the re-anchored mission directory.
    """
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    lane_worktree = tmp_path / "a-lane-worktree"
    _git(coord.repo_root, "worktree", "add", "-b", "a-lane-branch", str(lane_worktree), "HEAD")

    location = placement_seam(lane_worktree, coord.mission_dir_name).write_dir(MissionArtifactKind.STATUS_STATE)

    assert not (lane_worktree / ".worktrees").exists()
    assert location.surface is TopologySurface.COORD
    assert location.surface_root == coord.coord_worktree_path
    assert location.path == coord.coord_mission_dir


# ---------------------------------------------------------------------------
# D4 naming fix (binding correction round 3) -- ``coord_branch_has_committed_artifact``'s
# explicit git-error arm, consulted by D22's self-materialization informational
# log (reached only when an UNMATERIALIZED local head already carries content).
# ---------------------------------------------------------------------------


def test_coord_branch_has_committed_artifact_git_binary_missing_fails_closed_loudly(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """The git-BINARY-unavailable arm is now explicit (binding correction):
    it fails closed to ``True`` (present, so the caller refuses/self-heals
    defensively), AND it is observable -- a ``WARNING``, never a silent
    ``True`` indistinguishable from a legitimate absence."""
    import kernel.git.runner as git_runner_module

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("git executable not found")

    # The listing goes through the one ``kernel.git`` subprocess seam, which reports
    # a missing binary as ``GitCommandError``.
    monkeypatch.setattr(git_runner_module.subprocess, "run", _boom)

    with caplog.at_level(logging.WARNING, logger="specify_cli.coordination.surface_resolver"):
        result = coord_branch_has_committed_artifact(
            Path("/does/not/matter"),
            "some-coord-branch",
            "some-mission-slug",
            MissionArtifactKind.ISSUE_MATRIX,
        )

    assert result is True
    assert any("could not list" in record.getMessage() and "git executable not found" in record.getMessage() for record in caplog.records), [
        r.getMessage() for r in caplog.records
    ]


def test_coord_branch_has_committed_artifact_uses_mid8_composed_mission_dir(tmp_path: Path) -> None:
    """The naming fix itself (D4 / binding correction round 3): a bare
    ``mission_slug`` that does NOT embed its own ``mid8`` suffix is a MISS
    (false negative) under the pre-WP04 ``kitty-specs/<slug>/`` composition,
    but a correct HIT once ``mid8`` is threaded through -- the exact
    under-match the brownfield scout's naming-fix note names."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "coord")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    bare_slug = "a-bare-slug"
    mid8 = "01KYT5EE"
    matrix_path = repo / "kitty-specs" / f"{bare_slug}-{mid8}" / "issue-matrix.json"
    matrix_path.parent.mkdir(parents=True)
    matrix_path.write_text("{}", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "committed matrix under the mid8-suffixed dir")

    # Without mid8: composes the bare-slug subtree ("kitty-specs/a-bare-slug/"),
    # which this branch does NOT carry -- a false negative under the pre-WP04
    # composition.
    assert coord_branch_has_committed_artifact(repo, "coord", bare_slug, MissionArtifactKind.ISSUE_MATRIX) is False
    # With mid8: composes the REAL mid8-suffixed subtree and finds it.
    assert coord_branch_has_committed_artifact(repo, "coord", bare_slug, MissionArtifactKind.ISSUE_MATRIX, mid8=mid8) is True
