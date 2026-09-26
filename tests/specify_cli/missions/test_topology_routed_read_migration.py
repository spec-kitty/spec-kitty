"""WP04 (read-side-seam-primary-primitive-closure-01KYKMMT), T025.

Pins the husk guarantee for the three ``migrate-fail-loud`` sites this WP
routed off the topology-blind ``primary_feature_dir_for_mission`` wrapper onto
``placement_seam(repo_root, handle).read_dir(MissionArtifactKind.PRIMARY_METADATA)``
(T023):

* ``specify_cli.agent_tasks_ports.RealFsReader.primary_anchor_dir``
  (``agent_tasks_ports.py:266`` in the WP02 census).
* ``specify_cli.cli.commands.mission_type._resolve_mission_handle``'s
  ``MissionNotFoundError`` fallback leg (``mission_type.py:1069``).
* ``specify_cli.cli.commands.mission_type.close_cmd``'s primary re-anchor
  (``mission_type.py:610``) -- covered by the EXISTING real-worktree
  integration suite ``tests/integration/test_mission_close_discard_coord_teardown.py``,
  whose ``coord_mission`` fixture already materialises a coordination worktree
  whose mission dir carries no ``meta.json`` (a husk in every sense this
  module tests directly): reverting the routed line at ``mission_type.py:610``
  back to the pre-fix no-op was verified, by hand, to red 4 of its 9 tests
  (``test_close_discard_tears_down_coordination_worktree_and_branch``,
  ``test_close_discard_flattens_coordination_branch_from_meta``,
  ``test_close_without_discard_tears_down_coord_worktree``,
  ``test_close_discard_fails_closed_on_corrupt_lanes_json``) -- so a fresh,
  narrower husk fixture here would only duplicate coverage that already exists
  and is already red-first proven. This module does not re-derive that proof;
  it exercises the two sites that suite does NOT touch.

``decisions/emit.py:71`` (the WP02 ledger's one ``resolve_feature_dir_for_mission``
``migrate-fail-loud`` verdict) is deliberately OUT of scope here: this WP found
that routing it collides with the coord-authority write gate's OWN permanent
sanction of that exact call (the since-deleted ``test_resolution_authority_gates.py``'s
``_COORD_WRITE_BY_DESIGN``/allow-list), which would red 4 gate tests. It was
left unrouted and reported as a WP02/WP01 cross-ledger gap rather than forced
through -- see the WP04 handoff report. There is therefore no husk pin for it:
pinning a guarantee the site does not (yet) have would be dishonest.

WP02's census for this WP is non-empty (T023 routed 3 real sites), so the
SC-005 zero-case discharge does not apply.

Fixtures build a real git repository under pytest's ``tmp_path`` (never a bare
``/tmp`` path) with production-shaped identity (a real 26-char Crockford ULID
+ its 8-char mid8, per NFR-003) -- no resolver is patched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.agent_tasks_ports import MissionHandle, RealFsReader
from specify_cli.cli.commands.mission_type import _resolve_mission_handle
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from tests.specify_cli._read_seam_migration_fixtures import (
    build_coord_husk,
    build_coord_materialized,
    coord_branch_name,
    coord_worktree_root,
    make_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity (NFR-003: no fabricated short ids).
_MISSION_ID = "01KYKMMTWP0400000000000001"
_MID8 = _MISSION_ID[:8]
_HUMAN_SLUG = "topology-routed-read-migration-fixture"
_COMPOSED = f"{_HUMAN_SLUG}-{_MID8}"


def _make_git_repo(tmp_path: Path, name: str) -> Path:
    """A minimal real git repo with the ``.kittify`` marker + ``kitty-specs/``."""
    return make_git_repo(
        tmp_path,
        name,
        user_email="wp04-fixture@spec-kitty.test",
        user_name="WP04 Fixture",
        readme_text="wp04 fixture repo\n",
    )


def _write_meta(
    feature_dir: Path,
    *,
    slug: str,
    mission_id: str,
    topology: str,
    coordination_branch: str | None,
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mission_slug": slug,
        "slug": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "vcs": "git",
        "topology": topology,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _seed_coord_husk(tmp_path: Path, name: str) -> tuple[Path, Path]:
    """A coord-topology mission whose coordination worktree is a HUSK.

    Real coord branch exists in git; the coord worktree's mission dir is
    physically present (a ``status.events.jsonl`` sibling, mirroring a
    materialised-but-status-only checkout) but carries NO ``meta.json`` --
    the exact husk shape ``resolve_action_context`` / the kind-blind
    primitives can silently land on. Returns ``(repo, primary_dir)``.
    """
    repo = _make_git_repo(tmp_path, name)
    branch = coord_branch_name(_COMPOSED)
    primary_dir = build_coord_husk(
        repo,
        _COMPOSED,
        branch,
        coord_worktree_root(repo, _COMPOSED),
        write_primary_meta=lambda feature_dir: _write_meta(
            feature_dir,
            slug=_COMPOSED,
            mission_id=_MISSION_ID,
            topology="coord",
            coordination_branch=branch,
        ),
    )
    return repo, primary_dir


def _seed_coord_materialized(tmp_path: Path, name: str) -> tuple[Path, Path]:
    """A coord-topology mission whose coordination worktree is FULLY populated
    (carries its own ``meta.json`` too) -- the NFR-001 materialized-case twin
    of :func:`_seed_coord_husk`."""
    repo = _make_git_repo(tmp_path, name)
    branch = coord_branch_name(_COMPOSED)

    def _write(feature_dir: Path) -> None:
        _write_meta(
            feature_dir,
            slug=_COMPOSED,
            mission_id=_MISSION_ID,
            topology="coord",
            coordination_branch=branch,
        )

    primary_dir, _coord_mission_dir = build_coord_materialized(
        repo,
        _COMPOSED,
        branch,
        coord_worktree_root(repo, _COMPOSED),
        write_primary_meta=_write,
        write_coord_meta=_write,
    )
    return repo, primary_dir


# ===========================================================================
# Site 1 -- agent_tasks_ports.py:266 (RealFsReader.primary_anchor_dir)
# ===========================================================================


def test_primary_anchor_dir_resolves_primary_not_coord_husk(tmp_path: Path) -> None:
    """T025: on a coord-husk mission, ``primary_anchor_dir`` resolves the
    PRIMARY dir -- zero husk substitutions.

    Red-first (NFR-003): reverting the T023 routing (back to the raw
    ``primary_feature_dir_for_mission(canonical)`` call) does not change this
    assertion's *outcome* on this fixture -- the wrapper itself already
    delegates to the identical seam call (WP03 T019) -- so the meaningful
    red-first proof for THIS site is the co-location unit test
    ``tests/specify_cli/cli/commands/agent/test_tasks_ports.py::
    test_canonicalizer_fold_is_co_located_inside_the_adapter_method``, which
    was hand-verified to fail against the pre-WP04 method body (see the WP04
    handoff report). This test instead pins the OBSERVABLE husk guarantee any
    future refactor of this method must preserve.
    """
    repo, primary_dir = _seed_coord_husk(tmp_path, "husk-fs-reader")
    reader = RealFsReader()
    handle = MissionHandle(repo_root=repo, mission_slug=_COMPOSED)

    resolved = reader.primary_anchor_dir(handle)

    assert resolved.resolve() == primary_dir.resolve()
    coord_mission_dir = repo / ".worktrees" / f"{_COMPOSED}-coord" / "kitty-specs" / _COMPOSED
    assert resolved.resolve() != coord_mission_dir.resolve()
    assert (resolved / "meta.json").exists()


def test_primary_anchor_dir_identical_for_materialized_mission(tmp_path: Path) -> None:
    """NFR-001: behaviour preservation for the non-husk (fully materialized)
    coord case -- identical resolved directory."""
    repo, primary_dir = _seed_coord_materialized(tmp_path, "materialized-fs-reader")
    reader = RealFsReader()
    handle = MissionHandle(repo_root=repo, mission_slug=_COMPOSED)

    resolved = reader.primary_anchor_dir(handle)

    assert resolved.resolve() == primary_dir.resolve()


# ===========================================================================
# Site 2 -- mission_type.py:1069 (_resolve_mission_handle fallback leg)
# ===========================================================================


def test_resolve_mission_handle_fallback_resolves_primary_not_coord_husk(
    tmp_path: Path,
) -> None:
    """T025: the ``MissionNotFoundError`` fallback leg (mission_type.py:1069)
    resolves the PRIMARY dir on a coord-husk mission -- zero husk
    substitutions.

    A BARE human slug (no ``-mid8`` suffix) is not matched by the identity
    resolver (it keys on the on-disk dir NAME, which here is the composed
    ``_COMPOSED`` name) -- exactly the ``MissionNotFoundError`` shape
    ``tests/missions/test_write_placement_handle_canonicalization_2136.py::
    test_mission_handle_bare_human_slug_folds_to_composed_dir`` already pins
    for a FLAT mission. This test adds the coord-husk dimension that sibling
    test does not cover.
    """
    repo, primary_dir = _seed_coord_husk(tmp_path, "husk-resolve-handle")

    resolved = _resolve_mission_handle(repo, _HUMAN_SLUG)

    assert resolved.feature_dir.resolve() == primary_dir.resolve()
    coord_mission_dir = repo / ".worktrees" / f"{_COMPOSED}-coord" / "kitty-specs" / _COMPOSED
    assert resolved.feature_dir.resolve() != coord_mission_dir.resolve()
    assert resolved.mission_id == _MISSION_ID


def test_resolve_mission_handle_fallback_identical_for_materialized_mission(
    tmp_path: Path,
) -> None:
    """NFR-001: behaviour preservation for the non-husk (fully materialized)
    coord case -- identical resolved directory."""
    repo, primary_dir = _seed_coord_materialized(tmp_path, "materialized-resolve-handle")

    resolved = _resolve_mission_handle(repo, _HUMAN_SLUG)

    assert resolved.feature_dir.resolve() == primary_dir.resolve()


def test_resolve_mission_handle_fallback_raises_on_ambiguous_handle(
    tmp_path: Path,
) -> None:
    """C-009: an ambiguous handle still raises structured -- no silent pick
    introduced by the routed seam call."""
    repo = _make_git_repo(tmp_path, "ambiguous-resolve-handle")
    ambig_mid8 = "01KAMBWP04"[:8]
    for suffix, mid_suffix in (("alpha", "AAAAAAAAAAAAAAAA"), ("beta", "BBBBBBBBBBBBBBBB")):
        mission_id = f"{ambig_mid8}0{mid_suffix}"[:26]
        slug = f"ambig-wp04-{suffix}-{ambig_mid8}"
        _write_meta(
            repo / "kitty-specs" / slug,
            slug=slug,
            mission_id=mission_id,
            topology="single_branch",
            coordination_branch=None,
        )

    with pytest.raises(MissionSelectorAmbiguous):
        _resolve_mission_handle(repo, ambig_mid8)


# ===========================================================================
# Direct seam sanity -- both routed sites share one call shape
# ===========================================================================


def test_seam_read_dir_primary_metadata_never_raises_on_coord_husk(tmp_path: Path) -> None:
    """Sanity check on the shared chokepoint both routed sites call through:
    ``placement_seam(...).read_dir(PRIMARY_METADATA)`` never raises for a
    coord-husk mission (NFR-002 -- a PRIMARY kind must not begin raising on
    husk / empty / deleted-coord)."""
    repo, primary_dir = _seed_coord_husk(tmp_path, "husk-seam-sanity")

    resolved = placement_seam(repo, _COMPOSED).read_dir(MissionArtifactKind.PRIMARY_METADATA)

    assert resolved.resolve() == primary_dir.resolve()
