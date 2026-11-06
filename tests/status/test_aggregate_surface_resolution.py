"""WP04 (FR-008) — aggregate surface-resolution negative + create-window tests.

These tests lock in the two behaviors WP04 consolidates in
``specify_cli.status.aggregate.MissionStatus``:

T016-a — **No silent first-match on an ambiguous mid8.** A bare ``mid8`` handle
that prefixes more than one mission's ``mission_id`` resolves to a *structured*
error (:class:`MissionSelectorAmbiguous`, ``error_code ==
MISSION_AMBIGUOUS_SELECTOR``) — never a lexically-first ``sorted(glob(...))``
pick. Mutation: re-introducing a silent-pick path that returns one of the two
candidate dirs makes ``MissionStatus.load`` return an aggregate instead of
raising, and ``test_ambiguous_mid8_handle_raises_typed_error`` fails.

T016-b — **The no-coord create→first-write window resolves PRIMARY.** A mission
whose primary checkout carries the spec dir + ``meta.json`` but declares **no**
``coordination_branch`` is in the create→first-write window: the primary checkout
is authoritative and ``MissionStatus.load`` must resolve ``read_dir`` to the
primary mission dir — NOT hard-fail. This is asserted as a cell DISTINCT from the
coord-empty hard-fail (a materialised-but-empty coord worktree → WP06's
``CoordAuthorityUnavailable``), because conflating the two would regress
first-write. Mutation: hard-failing the create-window (e.g. dropping the
``on_missing_meta`` primary fallback) makes ``load`` raise and
``test_create_window_no_coord_resolves_primary`` fails.

Fixtures are production-shaped: a real 26-char ULID (Mission Identity Model 083+),
the first 8 chars as the ``mid8`` disambiguator, and the real on-disk
``kitty-specs/<slug>-<mid8>/`` + ``.worktrees/<slug>-<mid8>-coord/`` layout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.missions._read_path_resolver import (
    MISSION_AMBIGUOUS_SELECTOR_CODE,
    MissionSelectorAmbiguous,
)
from specify_cli.status.aggregate import (
    MissionMetadataUnavailable,
    MissionStatus,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]  # git_repo: the coord-deleted fixtures init a real repo

# Production-shaped identity: a real 26-char ULID, mid8 = first 8 chars.
MISSION_ID = "01KVGCE8R8QJ3K5ZJ9E5008ABC"
MID8 = MISSION_ID[:8]  # "01KVGCE8"
MISSION_SLUG = "single-mission-surface"
SLUG_WITH_MID8 = f"{MISSION_SLUG}-{MID8}"

# Two distinct missions whose mission_ids share the SAME mid8 prefix → an
# ambiguous bare-mid8 handle (the FR-008 no-silent-first-match row).
_AMBIG_MID8 = "01KVAMBG"
_AMBIG_ID_A = _AMBIG_MID8 + "0AAAAAAAAAAAAAAAAA"  # 26-char ULID-shaped
_AMBIG_ID_B = _AMBIG_MID8 + "0BBBBBBBBBBBBBBBBB"


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


# ---------------------------------------------------------------------------
# T016-a — ambiguous mid8 → MISSION_AMBIGUOUS_SELECTOR (no silent first-match)
# ---------------------------------------------------------------------------


def test_ambiguous_mid8_handle_raises_typed_error(tmp_path: Path) -> None:
    """A bare ambiguous mid8 raises MissionSelectorAmbiguous, never a silent pick.

    FR-008 — ``MissionStatus.load`` routes mid8 disambiguation through the ONE
    canonical handle resolver, which raises a *structured* error on ambiguity.
    The old ``sorted(specs_dir.glob(f"{slug}-*/meta.json"))`` first-match path is
    gone; re-introducing any silent-pick path (returning one of the two candidate
    dirs) would make ``load`` succeed instead of raising — and fail this test.
    """
    _write_meta(tmp_path / "kitty-specs" / "alpha-surface", mission_id=_AMBIG_ID_A)
    _write_meta(tmp_path / "kitty-specs" / "beta-surface", mission_id=_AMBIG_ID_B)

    with pytest.raises(MissionSelectorAmbiguous) as excinfo:
        MissionStatus.load(repo_root=tmp_path, mission_slug=_AMBIG_MID8)

    # The stable routing code — asserted explicitly so a type-only divergence
    # (a different exception that happens to subclass the same base) is caught.
    assert excinfo.value.error_code == MISSION_AMBIGUOUS_SELECTOR_CODE
    assert excinfo.value.error_code == "MISSION_AMBIGUOUS_SELECTOR"
    # Both colliding candidates are named in the structured error (operator can
    # disambiguate) — proof the resolver saw BOTH and refused to pick one.
    assert set(excinfo.value.candidates) == {"alpha-surface", "beta-surface"}
    assert excinfo.value.handle == _AMBIG_MID8


def test_ambiguous_mid8_does_not_resolve_to_a_directory(tmp_path: Path) -> None:
    """The ambiguous handle yields NO aggregate at all (mutation tripwire).

    A silent first-match regression would return a populated
    :class:`MissionStatus` whose ``read_dir`` is one of the two colliding
    primary dirs. Asserting that ``load`` raises (rather than returning either
    candidate) is the direct mutation kill for the deleted glob.
    """
    dir_a = tmp_path / "kitty-specs" / "alpha-surface"
    dir_b = tmp_path / "kitty-specs" / "beta-surface"
    _write_meta(dir_a, mission_id=_AMBIG_ID_A)
    _write_meta(dir_b, mission_id=_AMBIG_ID_B)

    resolved: MissionStatus | None = None
    try:
        resolved = MissionStatus.load(repo_root=tmp_path, mission_slug=_AMBIG_MID8)
    except MissionSelectorAmbiguous:
        resolved = None

    assert resolved is None, (
        "ambiguous mid8 must not resolve to a MissionStatus pointing at "
        f"{dir_a} or {dir_b} (FR-008 no silent first-match)"
    )


def test_find_meta_path_propagates_ambiguous_selector(tmp_path: Path) -> None:
    """``_find_meta_path`` propagates ambiguity instead of swallowing it.

    The deleted code caught ``MissionSelectorAmbiguous`` (``candidate_dir =
    None``) and fell through to the silent glob. Calling the private helper
    directly proves the suppression is gone: an ambiguous bare mid8 raises the
    typed error straight out of ``_find_meta_path``. Mutation: re-adding the
    ``except MissionSelectorAmbiguous: candidate_dir = None`` swallow makes this
    return a ``(meta_path, dir)`` tuple instead of raising → this test fails.
    """
    _write_meta(tmp_path / "kitty-specs" / "alpha-surface", mission_id=_AMBIG_ID_A)
    _write_meta(tmp_path / "kitty-specs" / "beta-surface", mission_id=_AMBIG_ID_B)

    with pytest.raises(MissionSelectorAmbiguous) as excinfo:
        MissionStatus._find_meta_path(tmp_path, _AMBIG_MID8)

    assert excinfo.value.error_code == "MISSION_AMBIGUOUS_SELECTOR"
    assert set(excinfo.value.candidates) == {"alpha-surface", "beta-surface"}


# ---------------------------------------------------------------------------
# T016-b — no-coord create→first-write window resolves PRIMARY (NOT hard-fail)
# ---------------------------------------------------------------------------


def test_create_window_no_coord_resolves_primary(tmp_path: Path) -> None:
    """Create→first-write (no coordination_branch) resolves to the PRIMARY dir.

    The primary checkout carries the spec dir + ``meta.json`` but declares NO
    ``coordination_branch`` — the create→first-write window. The primary checkout
    is authoritative; ``load`` must resolve ``read_dir`` to the primary mission
    dir and classify the topology as ``legacy``, NOT hard-fail. This is a DISTINCT
    cell from coord-empty (see ``test_coord_empty_is_a_separate_hard_fail_cell``):
    a regression that hard-failed here would break first-write.
    """
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, mission_id=MISSION_ID)  # no coordination_branch

    ms = MissionStatus.load(repo_root=tmp_path, mission_slug=SLUG_WITH_MID8)

    assert ms.read_dir.resolve() == primary_dir.resolve(), (
        "create→first-write window must resolve to the primary checkout, not a "
        "coord path or a hard-fail (WP04 T016)"
    )
    assert ms.topology == "legacy"
    assert ms.mission_id == MISSION_ID
    assert ms.mid8 == MID8
    assert ms.coordination_branch is None


def test_create_window_bare_human_slug_resolves_primary(tmp_path: Path) -> None:
    """The create-window also resolves for the canonical literal dir name.

    The literal ``<slug>-<mid8>`` dir already names the canonical directory, so
    the meta read short-circuits on the pure-path happy path (no handle
    disambiguation, no git read) — proving the create-window resolution does not
    depend on a materialised git repo.
    """
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, mission_id=MISSION_ID, mission_slug=SLUG_WITH_MID8)

    ms = MissionStatus.load(repo_root=tmp_path, mission_slug=SLUG_WITH_MID8)

    assert ms.read_dir.resolve() == primary_dir.resolve()
    assert ms.topology == "legacy"


def test_bare_human_slug_resolves_composed_primary_meta(tmp_path: Path) -> None:
    """#2050 read mirror: a BARE human slug whose on-disk primary dir carries the
    composed ``<slug>-<mid8>`` name resolves that composed primary meta.

    Covers the ``_find_meta_path`` bare-modern-slug bridge (aggregate.py:524-529):
    the literal bare dir (``kitty-specs/single-mission-surface``) has no meta, so
    the shared ``resolve_bare_modern_mission_dir_name`` primitive re-anchors the
    meta read on the composed primary dir (``…-<mid8>``) — the same canonical
    primitive the ``agent status`` CLI consumes (NFR-004). Without this bridge the
    identity resolver (which keys on the dir NAME) cannot map a bare slug onto a
    composed dir name.
    """
    composed_primary = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(composed_primary, mission_id=MISSION_ID, mission_slug=SLUG_WITH_MID8)

    ms = MissionStatus.load(repo_root=tmp_path, mission_slug=MISSION_SLUG)

    assert ms.read_dir.resolve() == composed_primary.resolve()
    assert ms.mid8 == MID8


def test_missing_mission_dir_resolves_primary_via_on_missing_meta(
    tmp_path: Path,
) -> None:
    """A mission with NO dir at all resolves to PRIMARY (on_missing_meta path).

    This exercises the thin adapter's ``on_missing_meta = primary_candidate``
    contract directly: when neither ``meta.json`` nor the mission dir exists, the
    canonical surface raises ``FileNotFoundError`` and the delegator returns the
    caller-supplied primary directory (so the caller can render its own
    "directory not found" diagnostic) rather than letting the bare
    ``FileNotFoundError`` crash ``load``. Mutation: dropping the
    ``on_missing_meta`` fallback (letting ``FileNotFoundError`` escape) makes
    ``load`` raise here → this test fails.
    """
    # NB: ``kitty-specs/`` is created but the mission dir is NOT — neither the
    # dir nor meta.json exists, so the surface authority raises FileNotFoundError.
    (tmp_path / "kitty-specs").mkdir(parents=True)
    expected_primary = (tmp_path / "kitty-specs" / "ghost-mission").resolve()

    ms = MissionStatus.load(repo_root=tmp_path, mission_slug="ghost-mission")

    assert ms.read_dir.resolve() == expected_primary
    assert ms.topology == "legacy"
    assert ms.mission_id is None
    assert ms.mid8 == ""


def test_coord_empty_resolves_primary_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """coord-empty (materialised coord worktree, no mission dir) → PRIMARY (Option B).

    Inverted by mission 01KVN754 WP04 (out-of-map linearized edit: this file is
    WP05-owned, but the coord-empty cell breaks at THIS boundary). Previously the
    aggregate hard-failed with ``CoordAuthorityUnavailable``; under the operator-
    decided Option B (#1716/FR-003) the canonical surface returns the PRIMARY
    checkout + a loud warning, and the aggregate inherits PRIMARY with no aggregate
    code change. (The coord-*deleted* cell stays a hard-fail — see
    ``test_unmaterialized_coord_create_window_resolves_primary`` and WP05.)
    """
    import logging

    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_branch = f"kitty/mission-{SLUG_WITH_MID8}"
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(
        primary_dir,
        mission_id=MISSION_ID,
        coordination_branch=coord_branch,
        # WP08 (#2533) split the coord-empty warning by stored topology: a
        # coord mission WITH lanes still warns on an unexpected empty coord
        # (the TRUE-POSITIVE case this test pins); a solo (no-lanes)
        # ``MissionTopology.COORD`` mission does not — see
        # tests/coordination/test_surface_resolver_solo_coord_primary.py.
        topology="lanes_with_coord",
    )
    # Materialise the coord worktree ROOT but NOT its mission dir (coord-empty).
    coord_root = CoordinationWorkspace.worktree_path(tmp_path, SLUG_WITH_MID8, MID8)
    coord_root.mkdir(parents=True)

    with caplog.at_level(
        logging.WARNING, logger="specify_cli.coordination.surface_resolver"
    ):
        ms = MissionStatus.load(repo_root=tmp_path, mission_slug=SLUG_WITH_MID8)

    assert ms.read_dir.resolve() == primary_dir.resolve()
    # ADR 2026-11-06-2 (Mission lane-worktree-model-hardening WP05): the loud warning is
    # gone; this branch-without-log case is the read door's declared pre-seed fallback.
    assert not any(
        r.name == "specify_cli.coordination.surface_resolver"
        and r.levelno == logging.WARNING
        for r in caplog.records
    )


def test_unmaterialized_coord_create_window_resolves_primary(tmp_path: Path) -> None:
    """Coord declared but worktree NOT materialised → primary still authoritative.

    The companion to the coord-empty hard-fail: when ``coordination_branch`` is
    declared but the coord worktree root does NOT yet exist (the pre-first-write
    window), the aggregate keeps the PRIMARY checkout authoritative — the canonical
    surface composes the coord path as-is and defers the authority decision to the
    aggregate call site, which holds the create-window gate. A regression that
    routed this to the composed (non-existent) coord dir would break first-write
    on a freshly-created coord mission.
    """
    import subprocess

    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(
        primary_dir,
        mission_id=MISSION_ID,
        coordination_branch=f"kitty/mission-{SLUG_WITH_MID8}",
    )
    # Production-shaped R2 (#1889): the mission repo is real and the DECLARED
    # branch exists in it while the coord worktree root is still absent — that
    # ref is what splits CoordState.UNMATERIALIZED from the #1848 DELETED
    # data-loss verdict. Relying on the non-repo "treat as present" escape hatch
    # instead made this fixture host-dependent: on any machine where an ambient
    # checkout sits above basetemp (#154) the probe consulted THAT repo, found
    # no such branch, and raised CoordinationBranchDeleted out of a
    # create-window read.
    _init_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "branch", f"kitty/mission-{SLUG_WITH_MID8}"],
        check=True,
        capture_output=True,
        text=True,
    )

    ms = MissionStatus.load(repo_root=tmp_path, mission_slug=SLUG_WITH_MID8)

    assert ms.read_dir.resolve() == primary_dir.resolve(), (
        "declared-but-unmaterialised coord must keep the primary checkout "
        "authoritative until the worktree exists (create→first-write window)"
    )


def test_declared_coord_in_guest_of_ambient_repo_resolves_primary(
    tmp_path: Path,
) -> None:
    """#154 regression: a mission root that merely SITS INSIDE an unrelated
    checkout must not inherit that repo's ref space.

    The aggregate-wiring fixtures build an ad-hoc ``<tmp>/repo`` without git
    init; on any host where an ambient ancestor checkout sits above basetemp
    the deleted-branch probe consulted the AMBIENT repo, found no such branch,
    and raised ``CoordinationBranchDeleted`` out of a first write. The
    declared-branch probe treats a guest of a foreign checkout as R2′
    (branch present), so this load resolves PRIMARY exactly as it does on a
    clean host."""
    import subprocess

    outer = tmp_path / "ambient-checkout"
    outer.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(outer)], check=True)
    guest_repo = outer / "repo"
    primary_dir = guest_repo / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(
        primary_dir,
        mission_id=MISSION_ID,
        coordination_branch=f"kitty/mission-{SLUG_WITH_MID8}",
    )

    ms = MissionStatus.load(repo_root=guest_repo, mission_slug=SLUG_WITH_MID8)

    assert ms.read_dir.resolve() == primary_dir.resolve()


def _init_repo(repo_root: Path) -> None:
    """Real git repo with one commit (``_coord_branch_exists`` needs a repo)."""
    import subprocess

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    _git("init", "-q")
    _git("config", "user.email", "agg@example.test")
    _git("config", "user.name", "Aggregate Coord Deleted")
    _git("commit", "--allow-empty", "-qm", "init")


@pytest.mark.git_repo
def test_coord_deleted_hard_fails_with_coordination_branch_deleted(
    tmp_path: Path,
) -> None:
    """coord-deleted (declared branch gone from git, no coord worktree) → hard-fail.

    WP05 (T023, #1848/FR-005): a declared ``coordination_branch`` that has been
    DELETED from git while the coord worktree is absent is DATA LOSS, not a degraded
    read. ``MissionStatus.load`` now propagates ``CoordinationBranchDeleted``
    (``error_code == COORDINATION_BRANCH_DELETED``) VERBATIM — the aggregate's
    more-specific ``except CoordinationBranchDeleted: raise`` sits AHEAD of the
    ``StatusReadPathNotFound`` → ``CoordAuthorityUnavailable`` re-wrap, so the loud
    data-loss verdict is no longer masked. Mutation: removing that handler (or
    placing it after the SRPNF re-wrap) re-spells the error
    ``CoordAuthorityUnavailable`` and this test fails.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    _init_repo(tmp_path)
    coord_branch = f"kitty/mission-{SLUG_WITH_MID8}"
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(
        primary_dir,
        mission_id=MISSION_ID,
        coordination_branch=coord_branch,
    )
    # The branch is DECLARED in meta.json but never created in git, and no coord
    # worktree exists → the DELETED topology state.

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        MissionStatus.load(repo_root=tmp_path, mission_slug=SLUG_WITH_MID8)
    assert excinfo.value.error_code == "COORDINATION_BRANCH_DELETED"
    assert excinfo.value.coordination_branch == coord_branch


# ---------------------------------------------------------------------------
# T014 structural guard — no second mid8 silent-glob path remains in aggregate
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# WP01 raw-bypass — save() diagnostic path routes through the blessed
# path-constructor (no raw ``repo_root / KITTY_SPECS_DIR / <slug>`` even on
# the identity-missing error path)
# ---------------------------------------------------------------------------


def test_save_without_identity_raises_via_blessed_path_constructor(
    tmp_path: Path,
) -> None:
    """``save()`` on an identity-less aggregate raises through the resolver.

    When a ``MissionStatus`` carries no ``mission_id`` (legacy/un-minted
    mission), ``save()`` cannot persist via ``BookkeepingTransaction`` and must
    raise :class:`MissionMetadataUnavailable`. WP01 routes the *diagnostic*
    ``primary_candidate`` / ``meta_path`` through the blessed
    kind-aware ``placement_seam(...).read_dir(PRIMARY_METADATA)`` seam rather than a raw
    ``repo_root / KITTY_SPECS_DIR / <slug>`` self-composition — even on this
    error path. This test executes that branch (the function-local import + the
    ``diag_primary = placement_seam(...).read_dir(PRIMARY_METADATA)`` call) and asserts the
    payload is exactly what the constructor yields. Mutation: re-inlining a raw
    path here (or dropping the guard) makes the payload diverge or the call not
    raise → this test fails.
    """
    expected_primary = placement_seam(tmp_path, MISSION_SLUG).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )

    aggregate = MissionStatus(
        mission_slug=MISSION_SLUG,
        mission_id=None,
        mid8="",
        topology="legacy",
        read_dir=tmp_path / "kitty-specs" / MISSION_SLUG,
        repo_root=tmp_path,
    )

    with pytest.raises(MissionMetadataUnavailable) as excinfo:
        aggregate.save(operation="status transition")

    err = excinfo.value
    assert err.mission_slug == MISSION_SLUG
    assert err.primary_candidate.resolve() == expected_primary.resolve()
    assert err.meta_path.resolve() == (expected_primary / "meta.json").resolve()
    assert "mission_id is required" in str(err)


def test_save_with_blank_mid8_raises_via_blessed_path_constructor(
    tmp_path: Path,
) -> None:
    """A present ``mission_id`` but blank ``mid8`` also hits the diagnostic path.

    The guard is ``mission_id is None or not self.mid8`` — a (data-corruption)
    aggregate with an identity but an empty ``mid8`` disambiguator likewise
    cannot acquire a ``BookkeepingTransaction`` and must raise through the same
    blessed-path diagnostic branch. Covering this second disjunct arm keeps the
    guard from silently narrowing to ``mission_id is None`` alone.
    """
    expected_primary = placement_seam(tmp_path, MISSION_SLUG).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )

    aggregate = MissionStatus(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mid8="",  # corrupt: identity present but disambiguator missing
        topology="legacy",
        read_dir=tmp_path / "kitty-specs" / MISSION_SLUG,
        repo_root=tmp_path,
    )

    with pytest.raises(MissionMetadataUnavailable) as excinfo:
        aggregate.save(operation="status transition")

    assert excinfo.value.primary_candidate.resolve() == expected_primary.resolve()
