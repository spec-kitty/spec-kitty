"""Differential equivalence test — the C-004 deletion safety gate (FR-002, NFR-003).

This module feeds the **same** ``(topology, handle)`` matrix to EVERY
mission-surface resolution entry point and asserts each entry point returns an
**identical resolved directory** OR an **identical typed error** (same class AND
same ``error_code``). It is the gate that protects the C-004 strangler: no
duplicate resolver may be deleted while any matrix cell diverges. Every cell
agrees today; ``test_equivalence_detects_planted_divergence`` proves the
comparison still fails when one entry point diverges.

Entry points compared (read each before asserting over it):

* ``missions._read_path_resolver.resolve_handle_to_read_path`` (``require_exists=True``)
  — the WP04 re-point: ``_entry_points`` calls ``resolve_handle_to_read_path``
  (the mid8-deriving seam) under the ``"resolve_mission_read_path"`` cell label,
  NOT the mid8-blind ``resolve_mission_read_path`` primitive.  The
  ``require_exists=True`` contract makes a missing surface raise rather than
  return a composed-but-absent path — do NOT "correct" this leg back to the
  primitive, which would silently un-flip the matrix cells.
* ``coordination.surface_resolver.resolve_status_surface_with_anchor`` (``.read_dir``)
* ``status.aggregate.MissionStatus.load`` (``.read_dir`` / ``_resolve_read_dir``)
* ``mission_runtime.resolution`` boundary (ambiguous-handle translation probe)

The module-private ``_compose_primary_feature_dir`` leaf is the FR-009 companion to
``resolve_mission_read_path``; the ``coord-*|bare-slug`` cells pin that a bare slug
derives its mid8 and reaches the same coord worktree the surface/aggregate prefer.

What the matrix proves: for every ``(topology, handle)`` cell, all entry points
resolve the same directory or raise the same typed error.

Assertion discipline (a too-lenient assertion VOIDS the whole gate):

* dirs:   ``resolved_a.resolve() == resolved_b.resolve()`` — path equality, NOT
          "both non-None" / truthiness.
* errors: ``type(exc_a) is type(exc_b) and exc_a.error_code == exc_b.error_code``
          — same class AND same code, NOT "both raise something".
* No ``pytest.skip(...)`` / ``xfail`` anywhere in the matrix — a skip would
  hide a divergence.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    classify_topology,
    is_primary_artifact_kind,
    routes_through_coordination,
)
from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.lanes import (
    ExecutionLane,
    LanesManifest,
    write_lanes_json,
)
from specify_cli.migration.backfill_topology import (
    backfill_mission_topology,
    read_topology,
)
from specify_cli.missions._read_path_resolver import (
    MissionSelectorAmbiguous,
    StatusReadPathNotFound,
    _compose_primary_feature_dir,
    read_primary_meta,
    resolve_handle_to_read_path,
    resolve_planning_read_dir,
    stored_topology_from_meta,
)
from specify_cli.status.aggregate import MissionStatus

pytestmark = pytest.mark.git_repo

# Production-shaped identity: a real 26-char ULID (Mission Identity Model 083+),
# NOT a toy slug. ``mid8`` is the first 8 chars, the canonical disambiguator.
MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"
MID8 = MISSION_ID[:8]
MISSION_SLUG = "single-surface-resolver"
SLUG_WITH_MID8 = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

# Two missions that collide on the same mid8 prefix (the ambiguous-selector row).
_AMBIG_MID8 = "01KTAMBG"
_AMBIG_ID_A = _AMBIG_MID8 + "0AAAAAAAAAAAAAAAAA"  # 26-char ULID-shaped
_AMBIG_ID_B = _AMBIG_MID8 + "0BBBBBBBBBBBBBBBBB"


# ---------------------------------------------------------------------------
# Outcome: the normalized differential observation (dir-or-typed-error)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """A single entry point's observed result for one matrix cell.

    Exactly one of ``directory`` / (``error_type``, ``error_code``) is set. The
    equality used by the gate is the spelled-out shape from the module docstring
    — NEVER truthiness:

    * dirs agree iff their ``Path.resolve()`` values are equal;
    * errors agree iff the exception class is identical AND the ``error_code``
      string is identical.
    """

    directory: Path | None
    error_type: type[BaseException] | None
    error_code: str | None

    @classmethod
    def from_dir(cls, directory: Path) -> Outcome:
        return cls(directory=directory.resolve(), error_type=None, error_code=None)

    @classmethod
    def from_error(cls, exc: BaseException) -> Outcome:
        # ``error_code`` is the stable routing key the typed errors carry
        # (STATUS_READ_PATH_NOT_FOUND, MISSION_AMBIGUOUS_SELECTOR, ...). Errors
        # without one (e.g. CoordAuthorityUnavailable today) compare on type +
        # the sentinel below, so a type-only divergence is still a divergence.
        code = getattr(exc, "error_code", None)
        return cls(
            directory=None,
            error_type=type(exc),
            error_code=str(code) if code is not None else None,
        )

    @property
    def is_dir(self) -> bool:
        return self.directory is not None


def _observe(resolve: Callable[[], Path]) -> Outcome:
    """Run one entry point, capturing either its resolved dir or its exception.

    Any exception is captured (never swallowed): the gate's job is to compare the
    EXACT typed error across entry points, so the broad capture is intentional
    and the captured exception's type + ``error_code`` are asserted on.
    """
    try:
        resolved = resolve()
    except BaseException as exc:  # noqa: BLE001 — capture-and-compare is the gate
        return Outcome.from_error(exc)
    return Outcome.from_dir(resolved)


def _assert_equivalent(left: Outcome, right: Outcome, *, lhs: str, rhs: str) -> None:
    """Assert two entry points agree using the EXACT gate shapes.

    A too-lenient assertion (truthiness / "both non-None") would void the entire
    C-004 deletion gate, so the comparison is spelled out:

    * both dirs → ``Path.resolve()`` equality;
    * both errors → identical class AND identical ``error_code``;
    * one dir + one error → an unconditional divergence (the gate fires).
    """
    if left.is_dir and right.is_dir:
        assert left.directory == right.directory, f"{lhs} resolved {left.directory} but {rhs} resolved {right.directory} — directory divergence (C-004 gate)"
        return
    if not left.is_dir and not right.is_dir:
        assert left.error_type is right.error_type and left.error_code == right.error_code, (
            f"{lhs} raised {left.error_type}/{left.error_code} but {rhs} raised {right.error_type}/{right.error_code} — typed-error divergence (C-004 gate)"
        )
        return
    raise AssertionError(
        f"{lhs} produced {'dir' if left.is_dir else 'error'} "
        f"({left.directory or f'{left.error_type}/{left.error_code}'}) but {rhs} "
        f"produced {'dir' if right.is_dir else 'error'} "
        f"({right.directory or f'{right.error_type}/{right.error_code}'}) "
        "— dir-vs-error divergence (C-004 gate)"
    )


# ---------------------------------------------------------------------------
# Fixtures — realistic on-disk shapes (real git repo, real worktree layout)
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo_root: Path) -> None:
    """Initialise a real git repo with one commit (the worktree registry needs it)."""
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "gate@example.test")
    _git(repo_root, "config", "user.name", "Equivalence Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


def _stored_topology(repo_root: Path, slug: str) -> MissionTopology:
    """Read the WP02 **stored** topology the read-path boundary consumes.

    The surface-resolver leg (WP03-owned) takes ``topology`` as an explicit
    argument; the read-path leg reads it from ``primary_meta`` internally. To prove
    cross-leg CONVERGENCE the test must feed the surface leg the SAME stored value
    the read path uses — so it reads it here via the canonical extractor
    (:func:`stored_topology_from_meta`) from the primary meta, mirroring the
    boundary read (FR-010b).
    """
    primary_meta, _ = read_primary_meta(repo_root, slug)
    # ``stored_topology_from_meta`` is typed ``MissionTopology | None`` but mypy
    # widens its return to ``Any`` (the source module re-imports the enum locally);
    # the explicit ``isinstance`` narrows it back without a ``cast`` so this helper
    # stays type-clean (campsite #1970).
    stored = stored_topology_from_meta(primary_meta)
    if isinstance(stored, MissionTopology):
        return stored
    raw_branch = primary_meta.get("coordination_branch")
    branch = str(raw_branch) if isinstance(raw_branch, str) and raw_branch else None
    derived: MissionTopology = classify_topology(branch, has_lanes=False)
    return derived


def _coord_dir_slug(slug: str) -> str:
    """The on-disk coord dir slug: always carries the mid8 (post-WP03 grammar)."""
    return slug if slug.endswith(MID8) else SLUG_WITH_MID8


def _build_topology(repo_root: Path, *, topology: str, slug: str) -> None:
    """Materialise the realistic on-disk shape for one (topology, handle) cell.

    Layouts (per data-model.md):

    * ``no-coord``      — primary ``kitty-specs/<slug>/`` with meta, no coord branch.
    * ``coord-fresh``   — coord branch in git + ``.worktrees/<slug>-<mid8>-coord/``
      worktree dir populated with the mission dir + meta.
    * ``coord-behind``  — same populated coord worktree as ``coord-fresh``, but the
      primary checkout is ahead/diverged (an extra committed primary state). Per
      data-model.md the canonical cascade still prefers the coord surface, so the
      resolution outcome folds into ``coord-fresh`` (probed live, 2026-06-19).
    * ``coord-empty``   — coord branch in git + coord worktree root materialised but
      EMPTY (no mission dir).
    * ``coord-deleted`` — primary declares ``coordination_branch`` but the branch was
      never created (deleted from git) and no coord worktree exists.
    * ``flattened-stale-coord`` — the #2062 structural repro (quickstart R1 /
      spec.md FR-005). The mission was flattened mid-flight: the primary
      ``meta.json`` carries the WP02 **stored** ``topology: single_branch`` + a
      ``flattened: true`` provenance flag and NO ``coordination_branch`` (per the
      spec's R1 model), yet a MATERIALIZED-but-stale
      ``.worktrees/<slug>-<mid8>-coord/`` mission dir lingers on disk with a
      DIVERGENT (planned) status. The STORED topology drives every read leg to
      PRIMARY — the husk is structurally not consulted, so a stale ``-coord`` dir
      cannot re-open #2062. The on-disk primary dir always carries the composed
      ``<slug>-<mid8>`` name so the bare-human-slug handle resolves through
      :func:`resolve_bare_modern_mission_dir_name` (FR-004 bare-slug fold).
    """
    _init_repo(repo_root)
    primary_fields: dict[str, object] = {"mission_id": MISSION_ID}
    if topology not in ("no-coord", "flattened-stale-coord"):
        primary_fields["coordination_branch"] = COORD_BRANCH

    if topology == "flattened-stale-coord":
        # The primary dir ALWAYS carries the composed name so every handle form
        # (composed / bare-mid8 / ULID / bare-human-slug) resolves the same dir.
        composed_primary = repo_root / "kitty-specs" / SLUG_WITH_MID8
        _write_meta(
            composed_primary,
            mission_id=MISSION_ID,
            topology=MissionTopology.SINGLE_BRANCH.value,
            flattened=True,
        )
        (composed_primary / "status.events.jsonl").write_text('{"wp_id":"WP01","to_lane":"approved"}\n', encoding="utf-8")
        # Stale husk: a REAL registered ``-coord`` worktree carrying its OWN
        # ``meta.json`` (EVERY ``git worktree add`` checkout has one) + a DIVERGENT
        # (planned) status. The husk's meta is the detail that fires the surface
        # resolver's ``.worktrees`` short-circuit; OMITTING it (the earlier fixture)
        # silently masked the #2062 leak so the gate could never catch it (WP08
        # debbie BLOCKER). A real ``git worktree add`` registers the worktree, so the
        # registry-authority legs see it as a genuine coord worktree, not a husk
        # ``UNREGISTERED`` shape — proving the STORED topology (not on-disk shape) is
        # what re-anchors every leg to PRIMARY.
        coord_root = repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
        _git(repo_root, "worktree", "add", "-q", "-b", COORD_BRANCH, str(coord_root))
        husk = coord_root / "kitty-specs" / SLUG_WITH_MID8
        husk.mkdir(parents=True, exist_ok=True)
        _write_meta(husk, mission_id=MISSION_ID)
        (husk / "status.events.jsonl").write_text('{"wp_id":"WP01","to_lane":"planned"}\n', encoding="utf-8")
        return

    coord_slug = _coord_dir_slug(slug)
    coord_root = repo_root / ".worktrees" / f"{coord_slug}-coord"
    coord_feature_dir = coord_root / "kitty-specs" / coord_slug

    _write_meta(repo_root / "kitty-specs" / slug, **primary_fields)

    if topology == "coord-fresh":
        _git(repo_root, "branch", COORD_BRANCH)
        _write_meta(coord_feature_dir, **primary_fields)
    elif topology == "coord-behind":
        # Same populated coord worktree as coord-fresh, but the PRIMARY checkout is
        # ahead/diverged: commit the primary state so it advances past the coord
        # branch point. The canonical cascade still prefers the coord surface, so
        # this folds into coord-fresh (probed live 2026-06-19).
        _git(repo_root, "branch", COORD_BRANCH)
        _write_meta(coord_feature_dir, **primary_fields)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-qm", "primary ahead of coord (diverged)")
    elif topology == "coord-empty":
        _git(repo_root, "branch", COORD_BRANCH)
        coord_root.mkdir(parents=True)  # materialised, no mission dir
    elif topology == "coord-deleted":
        pass  # branch never created → declared-but-gone; no coord worktree


# ---------------------------------------------------------------------------
# Entry-point adapters — one closure per resolver, identical (slug, mid8) input
# ---------------------------------------------------------------------------


def _entry_points(repo_root: Path, slug: str, mid8: str) -> dict[str, Callable[[], Path]]:
    """Return the named resolution entry points to compare for one cell.

    The ``resolve_status_surface_with_anchor`` leg is fed the SAME WP02 stored
    topology the read-path leg reads internally (FR-010b cross-leg convergence):
    the surface resolver (WP03-owned) decides the PRIMARY-vs-coordination shape
    from the stored value, so threading it here proves both legs converge on
    PRIMARY for a flattened-stale-coord mission rather than diverging on the husk.
    """
    return {
        "resolve_mission_read_path": lambda: resolve_handle_to_read_path(repo_root, slug, require_exists=True),
        "resolve_status_surface_with_anchor": lambda: resolve_status_surface_with_anchor(repo_root, slug, _stored_topology(repo_root, slug)).read_dir,
        "MissionStatus.load": lambda: MissionStatus.load(repo_root, slug).read_dir,
    }


def _observe_all(repo_root: Path, slug: str, mid8: str) -> dict[str, Outcome]:
    return {name: _observe(fn) for name, fn in _entry_points(repo_root, slug, mid8).items()}


# ---------------------------------------------------------------------------
# T005 / T007 — the (topology × handle) matrix
# ---------------------------------------------------------------------------

# (test_id, topology, slug, mid8). Every cell is expected GREEN: all entry
# points agree on the resolved dir or on the typed error.
_MATRIX: list[tuple[str, str, str, str]] = [
    ("no-coord/bare", "no-coord", MISSION_SLUG, ""),
    ("no-coord/slug-mid8", "no-coord", SLUG_WITH_MID8, MID8),
    ("coord-fresh/bare", "coord-fresh", MISSION_SLUG, ""),
    ("coord-fresh/slug-mid8", "coord-fresh", SLUG_WITH_MID8, MID8),
    ("coord-behind/bare", "coord-behind", MISSION_SLUG, ""),
    ("coord-behind/slug-mid8", "coord-behind", SLUG_WITH_MID8, MID8),
    ("coord-empty/bare", "coord-empty", MISSION_SLUG, ""),
    ("coord-empty/slug-mid8", "coord-empty", SLUG_WITH_MID8, MID8),
    ("coord-deleted/bare", "coord-deleted", MISSION_SLUG, ""),
    ("coord-deleted/slug-mid8", "coord-deleted", SLUG_WITH_MID8, MID8),
    # WP04 (T023, FR-005/#2062 read leg) — the flattened-stale-coord topology ×
    # EVERY handle form. The mission was flattened mid-flight (stored
    # ``topology: single_branch``, NO ``coordination_branch``) but a stale ``-coord``
    # husk lingers on disk. The stored topology drives all three read legs
    # (read_path, surface, aggregate) to the PRIMARY dir regardless of the husk —
    # the structural #2062 read-leg close.
    ("flattened-stale-coord/slug-mid8", "flattened-stale-coord", SLUG_WITH_MID8, MID8),
    ("flattened-stale-coord/bare-mid8", "flattened-stale-coord", MID8, MID8),
    ("flattened-stale-coord/full-ulid", "flattened-stale-coord", MISSION_ID, MID8),
    ("flattened-stale-coord/bare-human-slug", "flattened-stale-coord", MISSION_SLUG, ""),
]


_EntryPointFactory = Callable[[Path, str, str], dict[str, Callable[[], Path]]]
_CANONICAL_ENTRY_POINT = "resolve_status_surface_with_anchor"


def _check_cell(
    repo_root: Path,
    topology: str,
    slug: str,
    mid8: str,
    entry_points: _EntryPointFactory,
) -> None:
    """Build one matrix cell and assert every entry point agrees with the canonical one.

    Pairwise against the surface resolver (the canonical selection authority per
    data-model.md), so a single divergent entry point fails the cell.
    """
    _build_topology(repo_root, topology=topology, slug=slug)
    outcomes = {name: _observe(fn) for name, fn in entry_points(repo_root, slug, mid8).items()}
    canonical = outcomes[_CANONICAL_ENTRY_POINT]
    for name, observed in outcomes.items():
        if name == _CANONICAL_ENTRY_POINT:
            continue
        _assert_equivalent(canonical, observed, lhs=_CANONICAL_ENTRY_POINT, rhs=name)


@pytest.mark.parametrize(
    ("topology", "slug", "mid8"),
    [pytest.param(topology, slug, mid8, id=test_id) for test_id, topology, slug, mid8 in _MATRIX],
)
def test_entry_points_agree_per_cell(tmp_path: Path, topology: str, slug: str, mid8: str) -> None:
    """T006: every entry point agrees on the dir OR the typed error for the cell.

    Asserts the exact gate shapes via :func:`_assert_equivalent`: dir equality is
    ``Path.resolve()`` equality; error equality is identical class AND identical
    ``error_code``.
    """
    _check_cell(tmp_path, topology, slug, mid8, _entry_points)


def test_equivalence_detects_planted_divergence(tmp_path: Path) -> None:
    """Planted-violation control: one diverging leg fails the real cell comparison.

    In a ``coord-fresh`` cell every entry point resolves the coordination dir. One
    leg is rewired to return the PRIMARY feature dir instead; ``_check_cell`` (the
    helper the matrix test calls) must then raise.
    """
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8

    def diverging_entry_points(repo_root: Path, slug: str, mid8: str) -> dict[str, Callable[[], Path]]:
        legs = _entry_points(repo_root, slug, mid8)
        legs["MissionStatus.load"] = lambda: primary_dir
        return legs

    with pytest.raises(AssertionError, match="directory divergence"):
        _check_cell(tmp_path, "coord-fresh", SLUG_WITH_MID8, MID8, diverging_entry_points)


# ---------------------------------------------------------------------------
# T007 — ambiguous-mid8 handle class (no silent first-match, FR-008)
# ---------------------------------------------------------------------------


def _build_ambiguous(repo_root: Path) -> None:
    """Two missions sharing a mid8 prefix → an ambiguous bare-mid8 handle."""
    _init_repo(repo_root)
    _write_meta(repo_root / "kitty-specs" / "alpha-surface", mission_id=_AMBIG_ID_A)
    _write_meta(repo_root / "kitty-specs" / "beta-surface", mission_id=_AMBIG_ID_B)


def test_ambiguous_mid8_handle_agrees(tmp_path: Path) -> None:
    """T007: a bare ambiguous mid8 raises the SAME typed error everywhere.

    FR-008 — no silent first-match. The resolver, surface, and aggregate must all
    raise ``MissionSelectorAmbiguous`` (``error_code == MISSION_AMBIGUOUS_SELECTOR``);
    a single entry point that silently picks a candidate is a divergence.
    """
    _build_ambiguous(tmp_path)
    outcomes = _observe_all(tmp_path, _AMBIG_MID8, "")

    canonical_name = "resolve_status_surface_with_anchor"
    canonical = outcomes[canonical_name]
    # The handle is genuinely ambiguous: the canonical authority MUST error.
    assert not canonical.is_dir, "ambiguous mid8 must not resolve to a directory (FR-008 no silent first-match)"
    assert canonical.error_code == "MISSION_AMBIGUOUS_SELECTOR"
    for name, observed in outcomes.items():
        if name == canonical_name:
            continue
        _assert_equivalent(canonical, observed, lhs=canonical_name, rhs=name)


# ---------------------------------------------------------------------------
# T007 — no-coord create→first-write window (→ primary, NOT a hard-fail)
# ---------------------------------------------------------------------------


def test_create_first_write_window_resolves_primary(tmp_path: Path) -> None:
    """T007: the create→first-write window resolves to PRIMARY, not a hard-fail.

    Distinct from ``coord-empty`` (WP04 T016 contract): primary has the spec dir +
    meta but NO ``coordination_branch`` declaration yet, so the primary checkout is
    authoritative and every entry point agrees on the primary dir. This must NOT be
    confused with the coord-empty hard-fail — a regression that hard-failed here
    would break first-write.
    """
    _init_repo(tmp_path)
    _write_meta(tmp_path / "kitty-specs" / SLUG_WITH_MID8, mission_id=MISSION_ID)
    outcomes = _observe_all(tmp_path, SLUG_WITH_MID8, MID8)

    canonical_name = "resolve_status_surface_with_anchor"
    canonical = outcomes[canonical_name]
    expected_primary = (tmp_path / "kitty-specs" / SLUG_WITH_MID8).resolve()
    assert canonical.directory == expected_primary, "create→first-write window must resolve to the primary checkout (WP04 T016)"
    for name, observed in outcomes.items():
        if name == canonical_name:
            continue
        _assert_equivalent(canonical, observed, lhs=canonical_name, rhs=name)


# ---------------------------------------------------------------------------
# T007 — mission_runtime boundary: typed-error preservation (FR-005)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T022 — PURE stored-topology cell (FR-010a, NFR-005): zero FS/git fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", list(MissionTopology))
def test_pure_stored_topology_projects_surface_placement(
    topology: MissionTopology,
) -> None:
    """T022: ``resolve_context_for_mission`` projects PRIMARY vs coordination by topology.

    The ADDITIVE pure cell (FR-010a): it feeds WP03's pure resolver
    ``resolve_context_for_mission`` for ALL FOUR ``MissionTopology`` values with a
    production-shaped 26-char ULID and asserts the projected ``MissionExecutionContext``
    surface placement — ``SINGLE_BRANCH`` / ``LANES`` → PRIMARY (``FLATTENED`` ref,
    ``routes_through_coordination`` False); ``COORD`` / ``LANES_WITH_COORD`` →
    coordination placement. ZERO FS/git fixtures (no ``tmp_path`` meta, no repo
    init, no ``load_meta`` monkeypatch): the resolver is PURE (it mirrors quickstart
    R0). This ADDS a proof; it does NOT replace the on-disk flattened-stale-coord
    row (T023), whose canonical authority is the live surface resolver.
    """
    from mission_runtime import (
        CommitTarget,
        routes_through_coordination,
    )
    from mission_runtime.context import BranchRefFragment, IdentityFragment
    from mission_runtime.resolution import resolve_context_for_mission

    # DoD-(a) THE WELD (FR-001b): pin the absolute per-topology surface placement to
    # a HARDCODED literal table, NOT ``routes_through_coordination(topology)`` (which
    # asserts the predicate against itself — a tautology). The grid is small and
    # stable, so the expectation is spelled out independently of the production
    # mapping. This is the over-collapse "everything→PRIMARY" mutant-killer that
    # MUST ship with the enum deletion.
    expected_routes_coord_by_topology = {
        MissionTopology.SINGLE_BRANCH: False,
        MissionTopology.LANES: False,
        MissionTopology.COORD: True,
        MissionTopology.LANES_WITH_COORD: True,
    }

    coordination_branch = COORD_BRANCH if topology in (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD) else None
    identity = IdentityFragment.derive(mission_id=MISSION_ID, mission_slug=MISSION_SLUG)
    branch_ref = BranchRefFragment(
        target_branch="feat/single-surface",
        coordination_branch=coordination_branch,
        destination_ref=CommitTarget(ref=coordination_branch or "feat/single-surface"),
    )
    context = resolve_context_for_mission(
        MISSION_ID,
        topology,
        action="specify",
        mission_slug=MISSION_SLUG,
        feature_dir=f"kitty-specs/{SLUG_WITH_MID8}",
        target_branch="feat/single-surface",
        identity=identity,
        branch_ref=branch_ref,
    )

    assert context.branch_ref is not None
    # The absolute per-topology surface pin (the WELD): COORD/LANES_WITH_COORD →
    # coordination, SINGLE_BRANCH/LANES → PRIMARY. Asserted via the topology
    # predicate, NOT a deleted per-ref enum.
    coord_cells = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)
    assert routes_through_coordination(topology) is expected_routes_coord_by_topology[topology]
    # PRIMARY (flattened) cells share the target ref; coord cells route the coord ref.
    if topology in coord_cells:
        assert routes_through_coordination(topology) is True
        assert context.branch_ref.destination_ref.ref == COORD_BRANCH
    else:
        assert routes_through_coordination(topology) is False
        assert context.branch_ref.destination_ref.ref == "feat/single-surface"


def test_runtime_boundary_translates_ambiguous_selector(tmp_path: Path) -> None:
    """T007: the mission_runtime boundary surfaces a translated typed error.

    FR-005 — typed errors must survive caller flattening. The
    ``mission_runtime.resolution`` boundary catches ``StatusReadPathNotFound`` and
    re-raises ``ActionContextError`` (preserving the code), AND (since WP05/FR-005,
    merged into this lane) also translates ``MissionSelectorAmbiguous`` →
    ``ActionContextError`` preserving ``MISSION_AMBIGUOUS_SELECTOR``. The former
    strict-xfail (WP05 closer) is drained here at the WP06 collapse: WP05 landed,
    so the cell is GREEN.
    """
    from mission_runtime import MissionArtifactKind
    from mission_runtime.resolution import ActionContextError, resolve_placement_only

    _build_ambiguous(tmp_path)
    with pytest.raises(ActionContextError) as excinfo:
        # The ambiguous-selector error fires before kind matters; any kind drives
        # the same boundary translation (write-surface-coherence WP02 / T031).
        resolve_placement_only(tmp_path, _AMBIG_MID8, kind=MissionArtifactKind.SPEC)
    # The translated boundary error must preserve the routing code (FR-005).
    assert excinfo.value.code == "MISSION_AMBIGUOUS_SELECTOR"


# ---------------------------------------------------------------------------
# WP01 (01KVRJ6P) — verification safety net
# ---------------------------------------------------------------------------
#
# Three additions gate every deletion/collapse downstream:
#
#   * T001 — differential cell: classify-on-read ≡ backfill-then-read, asserted
#     GREEN over the (topology × transient) matrix. The single-authority cleanup
#     mission deletes the perpetual re-inference arm; this cell proves the stored
#     ``topology`` an un-backfilled mission *would* derive on read is byte-for-byte
#     the SAME value a one-shot ``backfill_mission_topology`` persists. If the two
#     ever diverge, deleting the classify-on-read arm changes observable behaviour.
#
#   * DoD-(a) — absolute per-topology surface placement cell: an explicit value
#     table pinning SINGLE_BRANCH/LANES → PRIMARY (``routes_through_coordination``
#     False) and COORD/LANES_WITH_COORD → coordination (True). This is the ONLY
#     kill for the wrong-MAPPING mutant the leg-vs-leg differential gate cannot
#     catch (both legs could agree on the *wrong* surface). Complementary to T001,
#     never a replacement — keep BOTH.
#
#   * T002 — NFR-002 repro: an un-backfilled flattened mission with a stale
#     coord husk resolves PRIMARY (the #2062 legacy arm was drained by WP06).

# T001 transient axis: the orthogonal provenance/declaration variations that MUST
# NOT change the derived topology. Each entry is a meta-fields patch applied on top
# of the per-topology base meta.
_TRANSIENTS: tuple[tuple[str, dict[str, object]], ...] = (
    ("no-provenance", {}),
    ("flattened-true", {"flattened": True}),
    ("flattened-false", {"flattened": False}),
)


def _write_lanes_manifest(feature_dir: Path, slug: str) -> None:
    """Persist a real ``lanes.json`` via the production seam (``write_lanes_json``).

    The topology classifier reads only *presence* of a parseable ``lanes.json``
    (``_has_lanes``), so a single minimal-but-valid manifest built through the
    canonical writer is the production-shaped lanes signal — not a hand-rolled file.
    """
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=MISSION_ID,
        mission_branch=COORD_BRANCH,
        target_branch="feat/single-surface",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/foo.py",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-06-23T00:00:00+00:00",
        computed_from="dependency_graph+ownership",
    )
    write_lanes_json(feature_dir, manifest)


# (topology_enum, has_coord, has_lanes) — the four-cell topology axis built from
# the two orthogonal production signals (coordination_branch presence × lanes.json
# presence), the SAME pair ``classify_topology`` consumes.
_TOPOLOGY_AXIS: tuple[tuple[MissionTopology, bool, bool], ...] = (
    (MissionTopology.SINGLE_BRANCH, False, False),
    (MissionTopology.LANES, False, True),
    (MissionTopology.COORD, True, False),
    (MissionTopology.LANES_WITH_COORD, True, True),
)


def _build_unbackfilled_mission(
    feature_dir: Path,
    *,
    has_coord: bool,
    has_lanes: bool,
    transient: dict[str, object],
) -> None:
    """Materialise an UN-backfilled mission dir: NO ``topology`` key in meta.

    The fixture carries production-shaped identity (``MISSION_ID`` — a real 26-char
    ULID) and the orthogonal signals (``coordination_branch`` + ``lanes.json``) the
    classifier consumes, plus the transient provenance patch — but deliberately NO
    stored ``topology``, so ``read_topology`` exercises the classify-on-read arm.
    """
    fields: dict[str, object] = {"mission_id": MISSION_ID, **transient}
    if has_coord:
        fields["coordination_branch"] = COORD_BRANCH
    _write_meta(feature_dir, **fields)
    if has_lanes:
        _write_lanes_manifest(feature_dir, feature_dir.name)


@pytest.mark.parametrize(
    ("topology", "has_coord", "has_lanes"),
    [pytest.param(t, c, lanes, id=t.value) for (t, c, lanes) in _TOPOLOGY_AXIS],
)
@pytest.mark.parametrize(
    "transient",
    [pytest.param(patch, id=name) for name, patch in _TRANSIENTS],
)
def test_classify_on_read_equals_backfill_then_read(
    tmp_path: Path,
    topology: MissionTopology,
    has_coord: bool,
    has_lanes: bool,
    transient: dict[str, object],
) -> None:
    """T001: classify-on-read ≡ backfill-then-read for every (topology × transient).

    The deletion-safety differential for the single-authority cleanup: the value an
    un-backfilled mission derives on read (``read_topology`` over a meta with NO
    ``topology`` key — the classify-on-read arm) MUST equal the value
    ``backfill_mission_topology`` persists and a subsequent read returns
    (backfill-then-read). Asserted GREEN today across the full matrix; a divergence
    here means deleting the classify-on-read arm downstream is NOT behaviour-neutral.

    Distinct fixtures per leg (one is mutated by the backfill write, one is not) so
    the persisting backfill cannot contaminate the pure-read leg.
    """
    # Leg A — classify-on-read: read the un-backfilled meta directly (no write).
    classify_dir = tmp_path / "kitty-specs" / "classify"
    _build_unbackfilled_mission(classify_dir, has_coord=has_coord, has_lanes=has_lanes, transient=transient)
    classify_on_read = read_topology(classify_dir)

    # Leg B — backfill-then-read: persist via the production migration, then read.
    backfill_dir = tmp_path / "kitty-specs" / "backfill"
    _build_unbackfilled_mission(backfill_dir, has_coord=has_coord, has_lanes=has_lanes, transient=transient)
    result = backfill_mission_topology(backfill_dir)
    backfill_then_read = read_topology(backfill_dir)

    # The two legs converge (differential equivalence) ...
    assert classify_on_read is backfill_then_read, (
        f"classify-on-read derived {classify_on_read} but backfill-then-read derived {backfill_then_read} — the classify arm is NOT behaviour-neutral"
    )
    # ... AND both equal the expected cell (the absolute anchor, not pure leg-equality:
    # leg-vs-leg equality alone would pass even if BOTH derived the wrong topology).
    assert classify_on_read is topology
    # The backfill actually persisted the same value (idempotent migration contract).
    assert result.action == "wrote"
    assert result.topology == topology.value


def test_absolute_surface_placement_by_topology() -> None:
    """DoD-(a): pin PRIMARY-vs-coordination surface per topology by explicit table.

    The absolute companion to the leg-vs-leg differential gate: it spells out, with
    a HARDCODED expectation (not ``destination_kind_for_topology`` — that would be a
    tautology), which topology routes through coordination. This is the ONLY kill
    for the wrong-mapping mutant the differential gate cannot catch (both legs could
    agree on the same WRONG surface).

    ``routes_through_coordination`` is the stored-topology routing authority
    (FR-005 / FR-001b); a coord-less topology must return ``False`` and a
    coord-routing topology ``True``. The mapping topology → routes-through-coord is
    the contract:
      * SINGLE_BRANCH / LANES   → PRIMARY surface  (routes_through_coordination False)
      * COORD / LANES_WITH_COORD → coordination     (routes_through_coordination True)

    Negative control built in: PRIMARY-mapped cells assert ``False`` and
    coordination-mapped cells assert ``True`` — a single over-routing mutant
    (mapping a coord-less topology to coordination) fails the table, and a single
    under-routing mutant (mapping a coord topology to primary) fails it too.
    """
    expected_routes_through_coord: dict[MissionTopology, bool] = {
        MissionTopology.SINGLE_BRANCH: False,
        MissionTopology.LANES: False,
        MissionTopology.COORD: True,
        MissionTopology.LANES_WITH_COORD: True,
    }
    # Every topology member is pinned — a new enum member would KeyError here, an
    # intentional tripwire forcing the table to stay exhaustive.
    assert set(expected_routes_through_coord) == set(MissionTopology)

    for topology, routes in expected_routes_through_coord.items():
        assert routes_through_coordination(topology) is routes, f"{topology.value} expected routes_through_coordination={routes} — surface-placement mapping mutant"


# ---------------------------------------------------------------------------
# T002 — NFR-002 repro (un-backfilled flattened mission resolves PRIMARY)
# ---------------------------------------------------------------------------


def _build_unbackfilled_flattened_with_husk(repo_root: Path) -> tuple[Path, Path]:
    """Materialise an UN-backfilled flattened mission + a stale coord husk on disk.

    Mirrors ``_build_topology(..., topology="flattened-stale-coord")`` EXCEPT the
    primary ``meta.json`` carries NO stored ``topology`` key — only the ``flattened``
    provenance flag and ``mission_id``. This is the precise un-backfilled shape that
    drives ``stored_topology_from_meta`` → ``None`` → the legacy probe-based
    consults-coord-husk arm (the #2062 leak path WP06 drains). Returns
    ``(primary_dir, husk_dir)``.
    """
    _init_repo(repo_root)
    primary = repo_root / "kitty-specs" / SLUG_WITH_MID8
    # NO ``topology`` key — the un-backfilled flattened shape (FR-005 / NFR-002).
    _write_meta(primary, mission_id=MISSION_ID, flattened=True)
    (primary / "status.events.jsonl").write_text('{"wp_id":"WP01","to_lane":"approved"}\n', encoding="utf-8")
    coord_root = repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
    _git(repo_root, "worktree", "add", "-q", "-b", COORD_BRANCH, str(coord_root))
    husk = coord_root / "kitty-specs" / SLUG_WITH_MID8
    husk.mkdir(parents=True, exist_ok=True)
    _write_meta(husk, mission_id=MISSION_ID)
    (husk / "status.events.jsonl").write_text('{"wp_id":"WP01","to_lane":"planned"}\n', encoding="utf-8")
    return primary, husk


def test_unbackfilled_flattened_resolves_primary_not_husk(tmp_path: Path) -> None:
    """T002 (NFR-002): an un-backfilled flattened mission MUST resolve PRIMARY.

    Live RED→GREEN evidence — a static edit cannot satisfy it. Before WP06 the read
    path read NO stored ``topology`` (``stored_topology_from_meta`` → ``None``), fell
    into the legacy probe-based arm, found the materialized coord husk, and returned
    the STALE husk (the #2062 leak surviving on the un-backfilled path).

    WP06 (T015) drained that arm: the read-path BOUNDARY now ABSORBS the absent
    ``topology`` field into a concrete topology (``classify_from_meta`` →
    SINGLE_BRANCH for a flattened mission with no ``coordination_branch``), threading
    PRIMARY routing downstream — so the husk is structurally not consulted and this
    repro resolves PRIMARY (the strict-xfail was drained, not re-keyed). Asserts the
    OBSERVABLE resolved surface (the returned dir), never the internal call graph.
    """
    primary, husk = _build_unbackfilled_flattened_with_husk(tmp_path)
    resolved = resolve_handle_to_read_path(tmp_path, SLUG_WITH_MID8, require_exists=True).resolve()

    # Negative control: prove the husk is genuinely a DIFFERENT, present directory —
    # otherwise "resolves primary" could pass vacuously if the husk never existed.
    assert husk.resolve().exists()
    assert husk.resolve() != primary.resolve()

    assert resolved == primary.resolve(), (
        f"un-backfilled flattened mission resolved {resolved} but must resolve the "
        f"PRIMARY dir {primary.resolve()} — the stale coord husk "
        f"{husk.resolve()} must NOT be consulted (#2062 / NFR-002)"
    )


def test_unbackfilled_flattened_repro_resolves_primary_after_wp06(
    tmp_path: Path,
) -> None:
    """T002 companion: the un-backfilled flattened mission resolves PRIMARY (post-WP06).

    The companion that moved as a PAIR with the strict-xfail drain above. Before WP06
    this asserted the RED behaviour (the husk leaked) and kept the xfail honest; WP06
    (T015) absorbs the absent ``topology`` field at the read boundary, so this now
    asserts the GREEN contract directly — an executable, non-marker proof that the
    flattened mission resolves the PRIMARY dir, NOT the stale coord husk. Negative
    control: the husk is a genuinely distinct, present directory, so "resolves
    primary" cannot pass vacuously.
    """
    primary, husk = _build_unbackfilled_flattened_with_husk(tmp_path)
    try:
        resolved = resolve_handle_to_read_path(tmp_path, SLUG_WITH_MID8, require_exists=True).resolve()
    except StatusReadPathNotFound:  # pragma: no cover — defensive: not the fixed arm
        pytest.fail("expected the un-backfilled flattened repro to resolve PRIMARY after WP06's boundary absorption, but it raised StatusReadPathNotFound")
    # Negative control: the husk is a different, present dir (non-vacuous).
    assert husk.resolve().exists()
    assert husk.resolve() != primary.resolve()
    # POST-WP06 (GREEN): the boundary absorption routes the flattened mission to
    # PRIMARY; the stale coord husk is structurally not consulted (#2062 / NFR-002).
    assert resolved == primary.resolve(), (
        "post-WP06 the un-backfilled flattened mission must resolve the PRIMARY dir "
        f"{primary.resolve()} (boundary absorption), NOT the stale coord husk "
        f"{husk.resolve()} (#2062 / NFR-002)"
    )


# ---------------------------------------------------------------------------
# WP01 (retrospective-durable-home, FR-011 / #2136) — handle-safe PRIMARY read
# seam. The kind-aware read seam ``resolve_planning_read_dir`` feeds its
# PRIMARY-partition leg into the topology-BLIND leaf
# ``_compose_primary_feature_dir`` (read-side-seam-primary-primitive-closure-
# 01KYKMMT WP08 T035: the deleted public wrapper delegated to this same leaf).
# A bare ``mid8`` / human slug does NOT name the on-disk ``<slug>-<mid8>`` dir,
# so the raw-handle compose DIVERGED (the #2136 bug). WP01 canonicalizes IN THE
# CALLER (mirroring the live exemplars), leaving the primitive blind. These
# cells prove the cure THROUGH the read seam.
# ---------------------------------------------------------------------------

# A PRIMARY-partition kind drives the ``is_primary_artifact_kind`` leg the bug
# lives on. ``SPEC`` is canonically PRIMARY-partition (mission_runtime.artifacts).


def _primary_kind() -> MissionArtifactKind:
    """The PRIMARY-partition ``MissionArtifactKind`` driving the seam's bug leg.

    Asserts the partition membership so a re-shuffle in ``mission_runtime.artifacts``
    (the FR-006 one-line move) that flips ``SPEC`` off the PRIMARY partition fails
    loudly here rather than silently routing the test onto the STATUS leg.
    """
    kind = MissionArtifactKind.SPEC
    assert is_primary_artifact_kind(kind), "SPEC must be a PRIMARY-partition kind to exercise the PRIMARY leg of resolve_planning_read_dir (the #2136 bug leg)"
    return kind


def _build_canonical_primary(repo_root: Path) -> Path:
    """Materialise a canonical ``kitty-specs/<slug>-<mid8>/`` PRIMARY dir.

    Production-shaped identity (real 26-char ULID, mid8 = first 8 lowercase). The
    dir name is the COMPOSED ``<slug>-<mid8>`` — so a bare ``mid8`` or bare human
    slug has a genuinely WRONG literal-compose target (``kitty-specs/<bare>``),
    making the divergence observable (the false-green guard in T011's notes).
    """
    _init_repo(repo_root)
    canonical_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(canonical_dir, mission_id=MISSION_ID)
    return canonical_dir


def test_primary_read_seam_handle_equivalence(tmp_path: Path) -> None:
    """T011/T012 (FR-011): bare-mid8 ≡ bare-slug ≡ ``<slug>-<mid8>`` → SAME dir.

    Drives the PRE-EXISTING entry point ``resolve_planning_read_dir`` (the seam the
    #2136 bug lives in) on a PRIMARY-partition kind, three handle forms against ONE
    canonical ``<slug>-<mid8>`` primary dir:

    * the composed ``<slug>-<mid8>`` (the canonical anchor);
    * a bare lowercase ``mid8`` (``MID8`` — the canonical disambiguator alone);
    * a bare human slug (``MISSION_SLUG`` — no mid8 tail).

    RED on the pre-WP01 code: the PRIMARY leg passed the RAW handle to the
    topology-blind leaf, so the bare forms composed
    ``kitty-specs/<bare>`` — a DIFFERENT dir than the composed anchor. GREEN after
    the caller-canonicalization: all three fold to the SAME canonical dir.

    Asserts the OBSERVABLE resolved dir (``Path.resolve()`` equality), never the
    internal call graph. The canonical anchor is pinned to the on-disk composed dir
    (not mere leg-equality) so a "both wrong but equal" mutant cannot pass.
    """
    canonical_dir = _build_canonical_primary(tmp_path)
    kind = _primary_kind()
    expected = canonical_dir.resolve()

    composed = resolve_planning_read_dir(tmp_path, SLUG_WITH_MID8, kind=kind).resolve()
    bare_mid8 = resolve_planning_read_dir(tmp_path, MID8, kind=kind).resolve()
    bare_slug = resolve_planning_read_dir(tmp_path, MISSION_SLUG, kind=kind).resolve()

    # Absolute anchor: the composed handle resolves the real on-disk canonical dir.
    assert composed == expected, f"composed handle resolved {composed}, expected the canonical PRIMARY dir {expected}"
    # Equivalence: the bare forms fold to the SAME canonical dir (FR-011 / #2136).
    assert bare_mid8 == expected, f"bare mid8 {MID8!r} resolved {bare_mid8} but must fold to the canonical PRIMARY dir {expected} (handle-safe read seam — #2136)"
    assert bare_slug == expected, (
        f"bare slug {MISSION_SLUG!r} resolved {bare_slug} but must fold to the canonical PRIMARY dir {expected} (handle-safe read seam — #2136)"
    )


def test_primary_read_seam_ambiguous_handle_raises(tmp_path: Path) -> None:
    """T011 (FR-011 / C-009): an ambiguous handle raises, never silently picks.

    Two missions colliding on the same mid8 prefix → the bare mid8 is ambiguous.
    The PRIMARY leg's caller-canonicalization MUST propagate
    ``MissionSelectorAmbiguous`` (``MISSION_AMBIGUOUS_SELECTOR``) unchanged — the
    no-silent-fallback contract (WP07 regression class). A silent pick of either
    candidate dir is the regression this asserts against.
    """
    _build_ambiguous(tmp_path)
    kind = _primary_kind()

    with pytest.raises(MissionSelectorAmbiguous) as excinfo:
        resolve_planning_read_dir(tmp_path, _AMBIG_MID8, kind=kind)
    assert excinfo.value.error_code == "MISSION_AMBIGUOUS_SELECTOR"


def test_primary_read_seam_canonical_handle_is_noop(tmp_path: Path) -> None:
    """T013 (NFR-005): a canonical ``<slug>-<mid8>`` handle is a no-op.

    The ``meta.json``-present short-circuit leg of
    ``_canonicalize_bare_modern_handle`` returns the handle unchanged, so the
    canonical handle resolves to exactly the literal compose — byte-identical to the
    pre-WP01 behaviour for an already-canonical handle.
    """
    canonical_dir = _build_canonical_primary(tmp_path)
    kind = _primary_kind()

    resolved = resolve_planning_read_dir(tmp_path, SLUG_WITH_MID8, kind=kind).resolve()
    # No-op: the canonical handle resolves the literal composed dir — the SAME path
    # the blind primitive composes directly (the present-leg short-circuit).
    assert resolved == canonical_dir.resolve()
    assert resolved == _compose_primary_feature_dir(tmp_path, SLUG_WITH_MID8).resolve()


def test_primary_read_seam_unresolvable_handle_is_byte_identical(tmp_path: Path) -> None:
    """T013 (NFR-005): an unresolvable handle behaves EXACTLY as the blind compose.

    An unresolvable handle (no matching mission, no ``meta.json``) hits the
    unresolvable leg of ``_canonicalize_bare_modern_handle`` → the handle is
    returned unchanged → literal compose, byte-identical to the pre-WP01 raw-handle
    behaviour AND to a direct call into the blind primitive.
    """
    _init_repo(tmp_path)  # no kitty-specs, no mission at all
    kind = _primary_kind()
    handle = "no-such-mission"

    resolved = resolve_planning_read_dir(tmp_path, handle, kind=kind).resolve()
    # Byte-identical to the blind primitive's literal compose (no-op fold).
    assert resolved == _compose_primary_feature_dir(tmp_path, handle).resolve()


def test_primitive_stays_blind_under_bare_handle(tmp_path: Path) -> None:
    """T013 step 4 (NFR-005): the primitive STILL diverges for a bare handle.

    The cure lives in the CALLER, not the primitive. A direct call to the
    topology-blind ``_compose_primary_feature_dir`` leaf with a bare ``mid8`` STILL
    literal-composes the bare name (``kitty-specs/<mid8>``) — a DIFFERENT dir than
    the canonical ``<slug>-<mid8>``. This proves the primitive's blind contract is
    preserved (no canonicalization folded into its body — recursion-safety) and
    that the seam-level equivalence is genuinely the caller's doing.
    """
    canonical_dir = _build_canonical_primary(tmp_path)

    blind = _compose_primary_feature_dir(tmp_path, MID8).resolve()
    # The blind primitive composes the bare name verbatim — it does NOT canonicalize.
    assert blind == (tmp_path / "kitty-specs" / MID8).resolve()
    # ... and that is a genuinely DIFFERENT dir than the canonical one (non-vacuous).
    assert blind != canonical_dir.resolve()
