"""#3862 — the owned ``single_branch`` invariant is ONE enum-based predicate.

Item A: the invariant was expressed three times in two representations — a raw
``meta.get("topology") != "single_branch"`` string comparison in
``specify_cli.core.owned_mission.resolve_owned_mission`` and two byte-identical
enum comparisons + error tuples in this package's owned-placement arms
(``resolve_placement_only`` / ``resolve_artifact_surface``). All three now
dispose against the single :func:`mission_runtime.is_single_branch` predicate
(the two seam arms through the one hoisted ``_require_owned_single_branch``
guard), so the string and enum representations cannot drift apart.

Item B: the owned arm of :func:`mission_runtime.mission_context_for` ignores
its ``repo_root`` argument entirely (callers pass either ``owned.primary`` or
``owned.root``). That vestigial-ness is pinned here as a contract — the owned
derivation must stay invariant to ``repo_root`` — so a future edit that makes
``repo_root`` load-bearing on that arm fails this file and forces the
inconsistent caller pairings to be reconciled first.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    OwnedCheckout,
    is_single_branch,
    mission_context_for,
    resolve_artifact_surface,
    resolve_placement_only,
    single_branch_write_ref,
)
from tests._owned_fixtures import mint_test_fact

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char ULID, mid8 = first 8 chars
# (Mission Identity Model 083+), matching the on-disk composed dir name.
_MISSION_ID = "01KWOWNEDSSOT3862AAA000001"
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = "owned-single-branch-ssot"
_SLUG_WITH_MID8 = f"{_MISSION_SLUG}-{_MID8}"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _owned_fact(repo: Path, topology: MissionTopology) -> OwnedCheckout:
    """The fact for the mission ``_build_mission`` wrote into ``repo`` (WP18 re-point).

    ``repo`` plays the owned checkout; the repository root is a decoy sibling the
    owned arms must never read.
    """
    return mint_test_fact(
        repository_root=repo.parent / "decoy-repository-root",
        owned_root=repo,
        mission_dir=repo / "kitty-specs" / _SLUG_WITH_MID8,
        mission_slug=_SLUG_WITH_MID8,
        write_branch="main",
        topology=topology,
    )


def _build_mission(repo_root: Path, topology: str) -> Path:
    """Real git repo carrying one mission with the given stored ``topology``.

    Same narrow shape as ``tests/mission_runtime/test_status_surface_dir_deleted_arm.py``:
    a plain single repo (the owned arm is handed the fact for the repo
    itself), no coordination branch — ``lanes`` is the clean non-single_branch
    cell for the seam-level guard because it never enters coord-state
    classification.
    """
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "owned-ssot-3862@example.test")
    _git(repo_root, "config", "user.name", "Owned SSOT 3862")

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
                "topology": topology,
            }
        ),
        encoding="utf-8",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", f"init {topology} mission")
    return feature_dir


@pytest.mark.parametrize(
    ("topology", "expected"),
    [
        (MissionTopology.SINGLE_BRANCH, True),
        (MissionTopology.LANES, False),
        (MissionTopology.COORD, False),
        (MissionTopology.LANES_WITH_COORD, False),
        (None, False),
    ],
)
def test_is_single_branch_predicate(topology: MissionTopology | None, expected: bool) -> None:
    """The ONE predicate: true only for the coord-less, lane-less cell.

    A ``None`` (absent / malformed / degraded) stored-topology read is refused —
    fail-closed, matching the owned preflight's historical refusal of a missing
    value.
    """
    assert is_single_branch(topology) is expected


def test_placement_owned_arm_no_longer_refuses_by_topology(tmp_path: Path) -> None:
    """owned-checkout-lifecycle-authority WP04 (T019, FR-023, R-16): the
    placement-layer's OWN topology refusal (``_require_owned_single_branch``)
    is deleted — topology has exactly ONE authority now: the minter's
    ``allowed_topologies`` set (WP02's ``resolve_owned_mission``), applied
    once, at minting. A ``lanes`` mission's PRIMARY-kind placement resolves
    through ``resolve_placement_only``'s owned arm exactly like any other
    topology — the second refusal this guard used to raise is GONE.

    Paired with ``test_lifecycle_owned_mission_refuses_non_single_branch``
    below, which pins the OTHER half of the FR-023 contract: the minter still
    refuses a ``lanes`` mission for a LIFECYCLE command's allowed-topology set.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _build_mission(repo, "lanes")

    target = resolve_placement_only(repo, _SLUG_WITH_MID8, kind=MissionArtifactKind.SPEC, owned=_owned_fact(repo, MissionTopology.LANES))
    assert target.ref == "main"


def test_artifact_surface_owned_arm_no_longer_refuses_by_topology(tmp_path: Path) -> None:
    """``resolve_artifact_surface``'s owned arm: the SAME deleted guard, pinned
    identically to its ``resolve_placement_only`` sibling above (the two
    historically shared ONE hoisted refusal; now neither refuses)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir = _build_mission(repo, "lanes")

    surface = resolve_artifact_surface(repo, _SLUG_WITH_MID8, kind=MissionArtifactKind.SPEC, owned=_owned_fact(repo, MissionTopology.LANES))
    assert surface.path == feature_dir


def test_lifecycle_minter_refuses_lanes_topology(tmp_path: Path) -> None:
    """The OTHER half of the FR-023 / R-16 paired proof (T019 step 5,
    review cycle 1 non-blocking finding): a lifecycle command's minter
    (``specify_cli.core.owned_mission.resolve_owned_mission``, default
    ``LIFECYCLE_OWNED_TOPOLOGIES`` set) still refuses to MINT a fact for a
    ``lanes`` mission at all -- the refusal moved UP to the single minting
    authority; it did not disappear when the placement-layer's OWN
    ``_require_owned_single_branch`` guard was deleted (F1 above).

    This file's owned-arm tests above (``test_placement_owned_arm_no_longer_
    refuses_by_topology`` etc.) only exercise the placement layer with an
    ALREADY-MINTED (hand-built, via ``mint_test_fact``) fact -- exactly the
    case this test does not cover. Both together are the full FR-023
    contract: topology is refused exactly ONCE, at minting, never again at
    placement.
    """
    from mission_runtime import ActionContextError, OwnedRefusalCode
    from specify_cli.core.owned_mission import resolve_owned_mission

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "owned-ssot-3862@example.test")
    _git(repo_root, "config", "user.name", "Owned SSOT 3862")
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "seed")

    checkout = tmp_path / "checkout"
    _git(repo_root, "worktree", "add", "-qb", "codex/lanes-checkout", str(checkout))
    feature_dir = checkout / "kitty-specs" / _SLUG_WITH_MID8
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "slug": _SLUG_WITH_MID8,
                "mission_type": "software-dev",
                "target_branch": "codex/lanes-checkout",
                "topology": "lanes",
            }
        ),
        encoding="utf-8",
    )
    _git(checkout, "add", "-A")
    _git(checkout, "commit", "-qm", "lanes mission")

    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(repo_root, checkout, _SLUG_WITH_MID8)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED


def test_owned_arms_resolve_single_branch(tmp_path: Path) -> None:
    """Sanity: a ``single_branch`` mission resolves through both owned arms."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir = _build_mission(repo, "single_branch")

    fact = _owned_fact(repo, MissionTopology.SINGLE_BRANCH)
    target = resolve_placement_only(repo, _SLUG_WITH_MID8, kind=MissionArtifactKind.SPEC, owned=fact)
    assert target.ref == "main"
    surface = resolve_artifact_surface(repo, _SLUG_WITH_MID8, kind=MissionArtifactKind.SPEC, owned=fact)
    assert surface.path == feature_dir


def test_mission_context_for_owned_arm_is_repo_root_invariant(tmp_path: Path) -> None:
    """Item B pin: the owned arm's answer does not depend on ``repo_root``.

    The owned callers thread ``owned`` alongside a ``repo_root`` they
    fill inconsistently (``owned.primary`` vs ``owned.root`` vs a CWD-derived
    root) — harmless ONLY because the owned arm never reads ``repo_root``.
    This test pins that structural vestigial-ness: resolving the same mission
    with wildly different ``repo_root`` values (including a path that is not a
    repository at all) must produce the byte-identical :class:`MissionContext`.
    If a future change makes ``repo_root`` load-bearing on this arm, this fails
    and the inconsistent caller pairings must be reconciled before it lands.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _build_mission(repo, "single_branch")

    fact = _owned_fact(repo, MissionTopology.SINGLE_BRANCH)
    baseline = mission_context_for(repo, _SLUG_WITH_MID8, owned=fact)
    assert baseline.topology is MissionTopology.SINGLE_BRANCH

    for vestigial_root in (
        repo,  # the owned root itself (the ``owned.root`` caller shape)
        tmp_path,  # an unrelated existing directory
        tmp_path / "not-a-repository",  # a path that does not even exist
    ):
        context = mission_context_for(vestigial_root, _SLUG_WITH_MID8, owned=fact)
        assert context == baseline


# ---------------------------------------------------------------------------
# single_branch_write_ref -- the ONE write-branch rule (#5100 FR-007/012)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("topology", "mission_branch", "expected"),
    [
        (MissionTopology.SINGLE_BRANCH, "kitty/mission-x-aaaaaaaa", "kitty/mission-x-aaaaaaaa"),
        (MissionTopology.SINGLE_BRANCH, None, "main"),
        (MissionTopology.SINGLE_BRANCH, "", "main"),
        (MissionTopology.SINGLE_BRANCH, 7, "main"),
        (MissionTopology.LANES, "kitty/mission-x-aaaaaaaa", "main"),
        (MissionTopology.COORD, "kitty/mission-x-aaaaaaaa", "main"),
        (None, "kitty/mission-x-aaaaaaaa", "main"),
    ],
)
def test_single_branch_write_ref_rule(topology: MissionTopology | None, mission_branch: object, expected: str) -> None:
    assert single_branch_write_ref(topology, mission_branch, "main") == expected


# ---------------------------------------------------------------------------
# #5100 -- ONE stored-topology parser. ``MissionTopology.from_stored`` pins the
# edge cases once; the three public readers must agree with it exactly.
# ---------------------------------------------------------------------------

_STORED_TOPOLOGY_CASES: list[tuple[object, MissionTopology | None]] = [
    ("single_branch", MissionTopology.SINGLE_BRANCH),
    ("lanes", MissionTopology.LANES),
    ("coord", MissionTopology.COORD),
    ("lanes_with_coord", MissionTopology.LANES_WITH_COORD),
    ("SINGLE_BRANCH", None),  # value form is case-sensitive; the NAME is not a value
    ("", None),
    ("not-a-real-topology", None),
    (42, None),
    (["single_branch"], None),
    (None, None),
]


@pytest.mark.parametrize(("raw", "expected"), _STORED_TOPOLOGY_CASES)
def test_from_stored_parses_only_exact_member_values(raw: object, expected: MissionTopology | None) -> None:
    assert MissionTopology.from_stored(raw) is expected


@pytest.mark.parametrize(("raw", "expected"), _STORED_TOPOLOGY_CASES)
def test_every_stored_topology_reader_agrees_with_from_stored(raw: object, expected: MissionTopology | None) -> None:
    from specify_cli.core.owned_mission import _stored_topology
    from specify_cli.migration.backfill_topology import stored_topology
    from specify_cli.missions._read_path_resolver import stored_topology_from_meta

    meta = {"topology": raw}
    assert stored_topology(meta) is expected
    assert stored_topology_from_meta(meta) is expected
    assert _stored_topology(meta) is expected


def test_every_stored_topology_reader_treats_absent_key_and_missing_meta_as_none() -> None:
    from specify_cli.core.owned_mission import _stored_topology
    from specify_cli.migration.backfill_topology import stored_topology
    from specify_cli.missions._read_path_resolver import stored_topology_from_meta

    assert stored_topology({}) is None
    assert stored_topology_from_meta({}) is None
    assert _stored_topology({}) is None
    assert _stored_topology(None) is None
