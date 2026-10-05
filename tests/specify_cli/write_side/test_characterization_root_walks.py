"""Root-walk + surface + store + lanes characterization (T003 / T004 / T005).

Pins the *current* resolved value of every write-side root-walk site and the
status write surface across the three real topologies, BEFORE the adoption
touches them (NFR-003 verification-by-deletion). These rows are GREEN on HEAD
and must stay green across the adoption (equivalence / idempotency).

The five root-walk sites the adoption deletes (`feature_dir.parent.parent` /
ancestor scans):

* ``status/emit.py::_feature_status_lock_root``
* ``status/work_package_lifecycle.py::_repo_root_for_lock``
* ``status/lifecycle_events.py::repo_root_for_lifecycle_log``
* ``status/store.py::_SlugResolver._find_mission_specs_root``
* ``coordination/status_transition.py::_repo_root_for_feature``

Each is characterized HERE driving the bare (no explicit ``repo_root``) path and
compared against the canonical resolver the adoption routes them to
(``resolve_canonical_root`` / ``get_main_repo_root``) — read and write resolving
the SAME root via the SAME resolver IS the symmetry proof (SC-002). The
status-write surface (T003) is pinned to the **coord** authority (C-007 — never
``primary_root``). The lanes-dir placement (T005, FR-008 oracle) is pinned to the
coord surface under coord topology and to the flat surface with no coord.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind
from mission_runtime.resolution import resolve_placement_only
from specify_cli.coordination.status_transition import _repo_root_for_feature
from specify_cli.coordination.surface_resolver import (
    WorktreeTopology,
    classify_worktree_topology,
    resolve_status_surface,
)
from specify_cli.core.paths import get_main_repo_root, resolve_canonical_root
from specify_cli.lanes.persistence import resolve_lanes_dir
from specify_cli.status.lifecycle_events import repo_root_for_lifecycle_log
from specify_cli.status.store import _SlugResolver
from specify_cli.workspace.root_resolver import resolve_status_lock_root

from .topology_fixtures import (
    KITTY_SPECS,
    build_coord,
    build_primary,
    build_submodule,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# T003 — coord-topology root parity across all 5 root-walk sites
# ---------------------------------------------------------------------------


def test_coord_root_walk_sites_current_values_before_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The HEAD (before) oracle for all 5 root-walk sites under coord topology.

    Driven WITHOUT explicit ``repo_root`` from the coord worktree CWD. This is
    the highest-value characterization in the net: it surfaces the REAL current
    divergence between the five sites that the adoption (FR-001) unifies onto
    ``workspace.primary_root`` (= the canonical MAIN root). Two classes exist on
    HEAD:

    * **Already canonical** — the consolidated ``resolve_status_lock_root``
      helper follows the worktree pointer to the MAIN root via
      ``resolve_canonical_root`` (WP02 consolidation).
    * **Still walks to the worktree root** — ``coord::_repo_root_for_feature``
      and ``lifecycle::repo_root_for_lifecycle_log`` resolve ``parent.parent`` =
      the COORD-WORKTREE root, NOT the canonical main root.

    Pinning BOTH values here is the before/after oracle (D-5): after the adoption
    every site must resolve the canonical main root, so the WP that touches the
    second class will show this test's expectations converge (WP05/WP03 update
    the now-canonical values). The net is therefore NOT vacuously green — it
    encodes the exact pre-adoption divergence.
    """
    coord = build_coord(tmp_path)
    monkeypatch.chdir(coord.coord_worktree)
    coord_fd = coord.coord_feature_dir
    main_root = coord.expected_primary_root  # the canonical MAIN repo root
    worktree_root = coord.coord_worktree.resolve()

    # The canonical resolver (the adoption target) follows the worktree pointer.
    assert resolve_canonical_root(coord_fd) == main_root
    assert get_main_repo_root(coord.coord_worktree) == main_root

    # Class 1 — lock sites route to the canonical main root via the shared resolver.
    assert resolve_status_lock_root(coord_fd, None) == main_root

    # Class 2 — integrated tree: BOTH class-2 sites converge on the canonical MAIN
    # root (FR-001 / R5 / D-12). ``coord::_repo_root_for_feature`` (WP05) and
    # ``lifecycle::repo_root_for_lifecycle_log`` (WP03) both used to walk
    # ``parent.parent`` to the COORD-WORKTREE root (the FR-001 divergence); both now
    # route through the canonical worktree-pointer resolver, so read and write
    # resolve the SAME canonical root (SC-002/SC-003).
    assert _repo_root_for_feature(coord_fd, None) == main_root
    log_path = coord_fd / "status.events.jsonl"
    assert repo_root_for_lifecycle_log(log_path) == main_root

    # Guard that the coord worktree root genuinely differs from the main root
    # (topology sanity), so both class-2 adoptions above are provably non-trivial.
    assert main_root != worktree_root


def test_coord_status_write_surface_is_coord_authority_never_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T003 / C-007: the status WRITE surface stays on the coord authority.

    ``resolve_status_surface`` for a coord-declaring mission must land inside a
    ``.worktrees/<m>-coord`` root — NOT collapse to the primary checkout. The
    write half of the surface fragment becomes load-bearing in WP05; this pins
    the value it must preserve.
    """
    coord = build_coord(tmp_path)
    monkeypatch.chdir(coord.coord_worktree)

    surface = resolve_status_surface(coord.coord_worktree, coord.mission_slug)
    # The surface is the coord worktree authority, never the primary root.
    assert ".worktrees" in surface.parts
    assert surface.name == "status.events.jsonl"
    # It is NOT under the primary main-root kitty-specs dir.
    primary_surface_dir = coord.main_root / KITTY_SPECS / coord.mission_slug
    assert primary_surface_dir not in surface.parents

    # The placement / write-target is the coordination branch (C-TARGET coord arm).
    # The status write surface resolves with STATUS_STATE (coord-preserving) kind
    # (write-surface-coherence WP02 / T031): coord topology keeps the coord branch.
    placement = resolve_placement_only(
        coord.main_root, coord.mission_slug, kind=MissionArtifactKind.STATUS_STATE
    )
    assert placement.ref == coord.coord_branch


# ---------------------------------------------------------------------------
# T003 — primary-topology root parity (the flat baseline)
# ---------------------------------------------------------------------------


def test_primary_all_root_walk_sites_resolve_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a plain primary checkout every root-walk site resolves the repo root."""
    primary = build_primary(tmp_path)
    monkeypatch.chdir(primary.repo_root)
    fd = primary.feature_dir
    expected = primary.expected_primary_root

    assert resolve_canonical_root(fd) == expected
    assert resolve_status_lock_root(fd, None) == expected
    assert _repo_root_for_feature(fd, None) == expected
    assert repo_root_for_lifecycle_log(fd / "status.events.jsonl") == expected


# ---------------------------------------------------------------------------
# T004 — submodule-topology characterization (the .git-FILE ancestor-walk hazard)
# ---------------------------------------------------------------------------


def test_submodule_root_walk_sites_stop_at_submodule_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T004 / NFR-002: under a real submodule, root resolution STOPS at the
    submodule root — it must NOT walk up into the enclosing superproject.

    This is the #2011 hazard surface. ``resolve_canonical_root`` (the adoption
    target) stops correctly; the write-side walks are pinned here so the swap to
    ``primary_root`` is provably equivalent for the submodule class too.
    """
    sub = build_submodule(tmp_path)
    monkeypatch.chdir(sub.submodule_root)
    fd = sub.feature_dir
    expected = sub.expected_primary_root  # the submodule's own root

    # Guard: the submodule .git is a FILE (the real topology), not a directory.
    assert (sub.submodule_root / ".git").is_file()
    # And the canonical resolver stops at the submodule root, not the parent.
    assert resolve_canonical_root(fd) == expected
    assert get_main_repo_root(sub.submodule_root) == expected
    assert expected != sub.superproject_root.resolve()

    # The write-side root walks, driven bare, agree with the canonical resolver.
    assert resolve_status_lock_root(fd, None) == expected
    assert _repo_root_for_feature(fd, None) == expected


# ---------------------------------------------------------------------------
# T005 — store.py ancestor-scan + lanes placement characterization
# ---------------------------------------------------------------------------


def test_store_slug_resolver_finds_specs_root_for_slug_dir(tmp_path: Path) -> None:
    """T005 / S-7: ``_SlugResolver`` resolves the mission_id via its ancestor
    scan for the canonical ``kitty-specs/<slug>`` feature-dir shape.

    The scan (``_find_mission_specs_root``) is FR-001's deletion target; pin its
    observable behavior (slug → mission_id) so the swap to ``primary_root`` has a
    green deletion-proof.
    """
    primary = build_primary(tmp_path)
    resolver = _SlugResolver(primary.feature_dir)

    # The specs root is the kitty-specs dir one level up from the feature dir.
    assert resolver._mission_specs_root == primary.feature_dir.parent
    # And it resolves the slug to the real ULID mission_id from meta.json.
    assert resolver.resolve(primary.mission_slug) == primary.mission_id
    # An unknown slug resolves to None (orphaned-event path).
    assert resolver.resolve("does-not-exist-01kv9w0x") is None


def test_store_slug_resolver_handles_deeper_nesting(tmp_path: Path) -> None:
    """T005 / S-7: the ``two_up`` arm — a feature dir nested one level deeper
    than ``kitty-specs/<slug>`` still finds the specs root (the scan's fallback).
    """
    primary = build_primary(tmp_path)
    nested = primary.feature_dir / "subdir"
    nested.mkdir(parents=True, exist_ok=True)
    resolver = _SlugResolver(nested)
    # candidate=feature_dir, two_up=kitty-specs — the two_up arm fires.
    assert resolver._mission_specs_root == primary.feature_dir.parent


def test_store_slug_resolver_non_kitty_specs_falls_back_to_parent(
    tmp_path: Path,
) -> None:
    """T005 / S-7: when the feature dir is NOT in a ``kitty-specs/<slug>`` shape,
    ``_find_mission_specs_root`` falls back to the feature dir's parent.

    ``_SlugResolver`` is a **feature-dir-relative** sibling lookup (it reads
    co-located ``meta.json``), so it anchors on ``feature_dir`` — pure path
    arithmetic, CWD-invariant, and robust when the dir is not inside a git repo.
    It does NOT route through ``resolve_canonical_root`` (that would jump to an
    unrelated repo root and miss the co-located meta.json — post-merge regression
    fix); the genuine lock-anchor sites (emit/wpl/lifecycle) keep the canonical
    resolver.
    """
    loose = tmp_path / "loose-dir"
    loose.mkdir(parents=True, exist_ok=True)

    resolver = _SlugResolver(loose)
    assert resolver._mission_specs_root == loose.parent


def test_lanes_dir_under_coord_resolves_to_coord_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T005 / FR-008 oracle: ``resolve_lanes_dir`` is pure path composition —
    given a coord feature dir it returns a path under that coord dir (GIGO).

    It does NOT decide the partition: ``lanes.json`` (LANE_STATE) is a PRIMARY
    artifact (INV-5 symmetry), and the partition decision lives in the
    kind-aware placement seam (``workspace.context.resolve_lane_state_dir``), not in this
    join helper. This characterizes the composition only.
    """
    coord = build_coord(tmp_path)
    monkeypatch.chdir(coord.coord_worktree)

    lanes = resolve_lanes_dir(coord.coord_feature_dir)
    assert lanes.name == "lanes.json"
    assert ".worktrees" in lanes.parts
    # The coord lanes dir is NOT under the primary main-root kitty-specs dir.
    primary_specs = coord.main_root / KITTY_SPECS / coord.mission_slug
    assert primary_specs not in lanes.parents


def test_lanes_dir_flat_resolves_to_primary_specs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T005 / FR-008 oracle (flat arm): with NO coord, the lanes-dir resolves
    under the primary checkout's ``kitty-specs/<slug>`` — the simple case.
    """
    primary = build_primary(tmp_path)
    monkeypatch.chdir(primary.repo_root)

    lanes = resolve_lanes_dir(primary.feature_dir)
    assert lanes == primary.feature_dir / "lanes.json"
    assert ".worktrees" not in lanes.parts


def test_coord_topology_classification_is_coord_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sanity guard for the coord fixture: git REALLY registers the worktree.

    A reviewer relies on this to confirm the coord fixture exercises the real
    coord-topology arm (not a husk ``-coord``-named plain dir).
    """
    coord = build_coord(tmp_path)
    monkeypatch.chdir(coord.coord_worktree)
    assert (
        classify_worktree_topology(coord.coord_feature_dir)
        is WorktreeTopology.COORD_WORKTREE
    )
